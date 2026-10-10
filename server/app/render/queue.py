"""The queue and the worker protocol (contract 5.7-5.10, §6.4, §8).

| State     | Entered by                              | Left by |
|-----------|-----------------------------------------|---------|
| queued    | 5.1, a requeue, the follow trigger      | a claim; 24 h queued -> expired; cancel -> cancelled |
| claimed   | 5.7 (lease = now + 120 s)               | the first heartbeat -> running; lapse -> requeue |
| running   | 5.8                                     | 5.9 -> succeeded; 5.10 -> requeue or failed; lapse -> requeue; cancel flag -> cancelled |

A claim is one conditional UPDATE of a `queued` row (picked with `FOR UPDATE
SKIP LOCKED` on Postgres; SQLite has one writer), so two workers never hold
one job and nothing is charged twice. The next job is the oldest of the
highest priority (the tier's rank) among the worker's kinds whose log the
worker can read (`doc_version_needed <= doc_version_max`). A set's `tiles`
jobs run one at a time and only once the set has a manifest, so each starts
from the newest picture. An ended attempt (a lapse, or a retryable failure)
requeues the job three times; the fourth ends it `failed`. A worker holds one
lease at a time: claiming again ends the one it still holds.
"""

import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.orm import Session, aliased

from .. import metering
from ..contract_http import ContractError
from ..licence import clock
from ..projects import waiters
from ..projects.models import Project, ProjectOp, ProjectSnapshot
from ..projects.ops import op_json
from ..projects.service import membership
from ..projects.snapshots import blob_key as snapshot_blob_key
from ..storage import get_store
from ..uploads import service as uploads
from ..uploads.models import UploadSession
from . import quotas, tiles
from .models import RenderJob, RenderSet, Worker

LEASE_S = 120
# Input URLs stay valid for the lease plus this.
URL_EXTRA_S = 600
MAX_RETRIES = 3
QUEUED_MAX = timedelta(hours=24)
CLAIM_WAIT_MAX_S = 20
STATUS_WAIT_MAX_S = 25
CLAIM_KEY = "render:claim"
FAIL_CODES = ("bad_input", "render_crash", "out_of_memory", "timeout", "engine_error", "doc_too_new")
LOG_TAIL_MAX = 64 * 1024
ENDED = ("succeeded", "failed", "cancelled", "expired")


def job_key(job_id: str) -> str:
    return f"render:job:{job_id}"


def notify_job(*job_ids: str | None) -> None:
    for job_id in job_ids:
        if job_id:
            waiters.notify(job_key(job_id))


def notify_claim() -> None:
    waiters.notify(CLAIM_KEY)


def bump(job: RenderJob, now: datetime) -> None:
    job.rev = (job.rev or 0) + 1
    job.updated_at = now


def lock_job(db: Session, job_id: str) -> RenderJob | None:
    """Begin the write transaction with the job row locked; returns it fresh."""
    db.execute(update(RenderJob).where(RenderJob.job_id == job_id).values(rev=RenderJob.rev))
    return db.execute(
        select(RenderJob).where(RenderJob.job_id == job_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def _worker_idle(db: Session, worker_id: str | None, now: datetime) -> None:
    if worker_id:
        row = db.get(Worker, worker_id)
        if row is not None:
            row.idle_since = now


# --- ending an attempt ------------------------------------------------------------------


def end_attempt(db: Session, job: RenderJob, *, retry: bool, error: dict, now: datetime) -> None:
    """A lapse or a failure: requeue while retries remain, else `failed`."""
    from . import sets

    worker_id = job.worker_id
    job.lease_id = None
    job.lease_expires_at = None
    job.worker_id = None
    if job.cancel_requested:
        # Cancelled while running: it ends here, at no charge.
        job.state = "cancelled"
        job.finished_at = now
        job.message = ""
        sets.on_ended(db, job, now)
    elif retry and job.attempts < MAX_RETRIES:
        job.attempts += 1
        job.state = "queued"
        job.queued_at = now
        job.progress = 0.0
        job.message = f"Trying again ({error.get('code', 'error')})."
        job.output_upload_id = None
    else:
        job.attempts += 1
        job.state = "failed"
        job.finished_at = now
        job.message = ""
        job.error = {"code": error.get("code", "engine_error"), "message": str(error.get("message", ""))[:2000]}
        sets.on_ended(db, job, now)
    bump(job, now)
    _worker_idle(db, worker_id, now)


def lapse(db: Session, job_id: str, lease_id: str | None, *, force: bool = False, now: datetime | None = None) -> bool:
    """End a lease that ran out (or, with `force`, one its worker gave up)."""
    now = now or clock.now()
    job = lock_job(db, job_id)
    if (
        job is None
        or job.state not in ("claimed", "running")
        or job.lease_id != lease_id
        or (not force and job.lease_expires_at is not None and clock.aware(job.lease_expires_at) > now)
    ):
        db.rollback()
        return False
    end_attempt(db, job, retry=True, error={"code": "timeout", "message": "The worker stopped answering."}, now=now)
    db.commit()
    notify_job(job_id)
    notify_claim()
    return True


def reap(db: Session, now: datetime) -> int:
    """render.leases.reap: lapsed leases requeue or fail."""
    due = db.execute(
        select(RenderJob.job_id, RenderJob.lease_id).where(
            RenderJob.state.in_(("claimed", "running")), RenderJob.lease_expires_at < now
        )
    ).all()
    db.rollback()
    return sum(1 for job_id, lease_id in due if lapse(db, job_id, lease_id, now=now))


def expire(db: Session, now: datetime) -> int:
    """render.jobs.expire: queued for 24 h -> expired."""
    from . import sets

    ids = list(
        db.scalars(select(RenderJob.job_id).where(RenderJob.state == "queued", RenderJob.queued_at < now - QUEUED_MAX))
    )
    db.rollback()
    done = 0
    for job_id in ids:
        job = lock_job(db, job_id)
        if job is None or job.state != "queued" or clock.aware(job.queued_at) >= now - QUEUED_MAX:
            db.rollback()
            continue
        job.state = "expired"
        job.finished_at = now
        job.message = "Nothing could take this job within 24 hours."
        bump(job, now)
        sets.on_ended(db, job, now)
        db.commit()
        notify_job(job_id)
        done += 1
    return done


# --- 5.7 claim --------------------------------------------------------------------------


def _candidate(kinds: list[str], doc_version_max: int):
    j = RenderJob
    other = aliased(RenderJob)
    in_flight = exists().where(
        other.set_id == j.set_id, other.state.in_(("claimed", "running")), other.job_id != j.job_id
    )
    ready = exists().where(RenderSet.follow_job_id == j.set_id, RenderSet.latest_job_id.is_not(None))
    return (
        select(j.job_id)
        .where(
            j.state == "queued",
            j.kind.in_(kinds),
            j.doc_version_needed <= doc_version_max,
            or_(j.kind != "tiles", j.set_id.is_(None), and_(ready, ~in_flight)),
        )
        .order_by(j.priority.desc(), j.queued_at.asc(), j.job_id.asc())
        .limit(1)
    )


def try_claim(db: Session, worker: Worker, kinds: list[str], doc_version_max: int, now: datetime) -> str | None:
    """Take the next job atomically; returns its id (committed `claimed`) or None."""
    postgres = db.get_bind().dialect.name == "postgresql"
    for _ in range(8):
        q = _candidate(kinds, doc_version_max)
        if postgres:
            q = q.with_for_update(skip_locked=True, of=RenderJob)
        job_id = db.scalar(q)
        if job_id is None:
            db.rollback()
            return None
        res = db.execute(
            update(RenderJob)
            .where(RenderJob.job_id == job_id, RenderJob.state == "queued")
            .values(
                state="claimed",
                lease_id=secrets.token_hex(16),
                lease_expires_at=now + timedelta(seconds=LEASE_S),
                worker_id=worker.worker_id,
                claimed_at=now,
                progress=0.0,
                message="",
                rev=RenderJob.rev + 1,
                updated_at=now,
            )
        )
        if res.rowcount == 1:
            db.commit()
            return job_id
        db.rollback()  # another worker took it first: pick again
    return None


def release_held(db: Session, worker: Worker, now: datetime) -> None:
    """A worker that claims again has given up the job it still holds."""
    for job_id, lease_id in db.execute(
        select(RenderJob.job_id, RenderJob.lease_id).where(
            RenderJob.worker_id == worker.worker_id, RenderJob.state.in_(("claimed", "running"))
        )
    ).all():
        db.rollback()
        lapse(db, job_id, lease_id, force=True, now=now)
    db.rollback()


def _signed(key: str, ttl: int) -> str:
    return get_store().signed_get_url(key, expires_in=ttl)


def _snapshot_for(db: Session, job: RenderJob) -> ProjectSnapshot | None:
    return db.scalar(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == job.project_id, ProjectSnapshot.at_seq <= job.at_seq)
        .order_by(ProjectSnapshot.at_seq.desc(), ProjectSnapshot.created_at.desc())
        .limit(1)
    )


class BadInput(Exception):
    """The job cannot run; `stop_set`: its followed set must stop too."""

    def __init__(self, message: str, *, stop_set: bool = False) -> None:
        super().__init__(message)
        self.stop_set = stop_set


def claim_inputs(db: Session, job: RenderJob, now: datetime) -> dict:
    """5.7's `inputs`: the snapshot, the operations after it up to `at_seq` and
    the base manifest, each signed for the lease plus 10 minutes."""
    ttl = LEASE_S + URL_EXTRA_S
    project = db.get(Project, job.project_id) if job.project_id else None
    if job.project_id and (project is None or project.deleted_at is not None):
        raise BadInput("The project was deleted.", stop_set=True)
    if job.project_id and membership(db, job.project_id, job.account_id) is None:
        raise BadInput("The account is no longer on this project.", stop_set=True)
    snapshot, after = None, 0
    if project is not None:
        snap = _snapshot_for(db, job)
        if snap is not None:
            after = snap.at_seq

            def entry(sha: str | None, size: int | None) -> dict | None:
                if sha is None:
                    return None
                return {"sha256": sha, "bytes": size, "url": _signed(snapshot_blob_key(job.project_id, sha), ttl)}

            snapshot = {
                "at_seq": snap.at_seq,
                "doc_version": snap.doc_version,
                "tbxp": entry(snap.tbxp_sha256, snap.tbxp_bytes),
                "tbxpack": entry(snap.tbxpack_sha256, snap.tbxpack_bytes),
            }
    ops_url = None
    if project is not None:
        rows = db.scalars(
            select(ProjectOp)
            .where(ProjectOp.project_id == job.project_id, ProjectOp.server_seq > after, ProjectOp.server_seq <= job.at_seq)
            .order_by(ProjectOp.server_seq)
        ).all()
        key = tiles.job_file_key(job.job_id, f"inputs/ops-{after}-{job.at_seq}.json")
        tiles.put_json(key, {"ops": [op_json(r) for r in rows], "head_seq": job.at_seq, "more": False})
        ops_url = _signed(key, ttl)
    base_url = None
    if job.kind == "tiles":
        base = db.get(RenderJob, job.base_job_id) if job.base_job_id else None
        if base is None or base.output_key is None:
            raise BadInput("The base panorama has no manifest.")
        base_url = _signed(base.output_key, ttl)
    files = {}
    wanted = (job.inputs or {}).get("files") or {}
    blobs = uploads.blobs_by_sha(db, job.account_id, list(wanted.values()))
    for name, sha in wanted.items():
        blob = blobs.get(sha)
        if blob is None:
            raise BadInput(f"The input file {name} is no longer stored.")
        files[name] = {"sha256": sha, "bytes": blob.bytes, "url": _signed(blob.storage_key, ttl)}
    return {"snapshot": snapshot, "ops_url": ops_url, "base_manifest_url": base_url, "files": files}


def prepare_claim(db: Session, job_id: str, worker: Worker, now: datetime) -> dict | None:
    """Build 5.7's answer for a job just claimed. A job whose inputs are gone
    fails `bad_input` (None is returned and the worker claims again)."""
    from . import service, sets

    job = lock_job(db, job_id)
    if job is None or job.state != "claimed" or job.worker_id != worker.worker_id:
        db.rollback()
        return None
    if job.kind == "tiles" and job.set_id:
        follow_set = db.get(RenderSet, job.set_id)
        if follow_set is not None and follow_set.latest_job_id:
            job.base_job_id = follow_set.latest_job_id  # start from the newest picture
    try:
        inputs = claim_inputs(db, job, now)
    except BadInput as exc:
        end_attempt(db, job, retry=False, error={"code": "bad_input", "message": str(exc)}, now=now)
        follow_set = db.get(RenderSet, job.set_id) if job.set_id else None
        if exc.stop_set and follow_set is not None and follow_set.active:
            sets.stop(db, follow_set, now, reason=str(exc))
        db.commit()
        notify_job(job_id)
        return None
    session = UploadSession(
        upload_id=secrets.token_hex(16),
        account_id=job.account_id,
        credential_kind="worker",
        credential_id=worker.worker_id,
        purpose="job-output",
        files=[],
        created_at=now,
        expires_at=now + uploads.SESSION_LIFETIME,
    )
    db.add(session)
    job.output_upload_id = session.upload_id
    worker.idle_since = None
    worker.last_heartbeat_at = now
    db.commit()
    notify_job(job_id)
    return {
        # The worker writes the job file (§6.1) from these: the record plus
        # the changed ids and the kind's params.
        "job": {**service.record_json(job), "changed": list(job.changed or []), "params": dict(job.params or {})},
        "lease_id": job.lease_id,
        "lease_expires_at": clock.rfc3339(job.lease_expires_at),
        "inputs": inputs,
        "output_upload": {"upload_id": session.upload_id, "part_bytes": uploads.PART_BYTES},
    }


# --- 5.8-5.10 ---------------------------------------------------------------------------


def lease_lost() -> ContractError:
    return ContractError(
        "lease_lost", 409, "This lease has ended. Stop the job and discard its outputs.", {}
    )


def leased(db: Session, worker: Worker, job_id: str, lease_id: str, now: datetime) -> RenderJob:
    """The job under this worker's live lease (row locked), or 404 / 409 `lease_lost`."""
    job = lock_job(db, job_id) if isinstance(job_id, str) and len(job_id) == 32 else None
    if job is None:
        db.rollback()
        raise ContractError("not_found", 404, "No such job.")
    if job.state not in ("claimed", "running") or job.lease_id != lease_id or job.worker_id != worker.worker_id:
        db.rollback()
        raise lease_lost()
    if job.lease_expires_at is not None and clock.aware(job.lease_expires_at) <= now:
        db.rollback()
        lapse(db, job_id, lease_id, now=now)
        raise lease_lost()
    return job


def heartbeat(db: Session, worker: Worker, job_id: str, lease_id: str, progress: float, message: str, now: datetime) -> dict:
    from . import sets

    done = db.get(RenderJob, job_id) if isinstance(job_id, str) and len(job_id) == 32 else None
    if done is not None and done.state == "cancelled" and done.ended_lease_id == lease_id:
        return {"lease_expires_at": clock.rfc3339(now), "cancel": True}
    db.rollback()
    job = leased(db, worker, job_id, lease_id, now)
    worker_row = db.get(Worker, worker.worker_id)
    if worker_row is not None:
        worker_row.last_heartbeat_at = now
    if job.cancel_requested:
        job.state = "cancelled"
        job.finished_at = now
        job.ended_lease_id = lease_id
        job.lease_id = None
        job.lease_expires_at = None
        job.worker_id = None
        job.message = ""
        bump(job, now)
        sets.on_ended(db, job, now)
        _worker_idle(db, worker.worker_id, now)
        db.commit()
        notify_job(job_id)
        notify_claim()
        return {"lease_expires_at": clock.rfc3339(now), "cancel": True}
    progress = min(1.0, max(0.0, float(progress)))
    message = (message or "")[:200]
    changed = job.state != "running" or abs(job.progress - progress) > 1e-9 or job.message != message
    job.state = "running"
    job.started_at = job.started_at or now
    job.progress = progress
    job.message = message
    job.lease_expires_at = now + timedelta(seconds=LEASE_S)
    if changed:
        bump(job, now)
    else:
        job.updated_at = now
    db.commit()
    if changed:
        notify_job(job_id)
    return {"lease_expires_at": clock.rfc3339(job.lease_expires_at), "cancel": False}


def complete(
    db: Session, worker: Worker, job_id: str, lease_id: str, output: object, wall_s: float, used_class: str,
    render_log: object, now: datetime,
) -> RenderJob:
    """5.9: verify the output against §6.2 (or the pack shape) and the upload,
    publish it, charge the measured time, move the followed set on."""
    from . import overage, sets

    done = db.get(RenderJob, job_id) if isinstance(job_id, str) and len(job_id) == 32 else None
    if done is not None and done.ended_lease_id == lease_id and done.state == "succeeded":
        return done  # a repeat of the same completion (§8)
    # The overage terms in force now, read before the row lock (a plan lookup may write).
    terms = overage.terms_for(db, done.account_id) if done is not None else None
    db.rollback()
    job = leased(db, worker, job_id, lease_id, now)
    if job.cancel_requested:
        end_attempt(db, job, retry=False, error={"code": "cancelled", "message": ""}, now=now)
        job.ended_lease_id = lease_id
        db.commit()
        notify_job(job_id)
        notify_claim()
        raise lease_lost()
    # Charged at the class the worker's token was issued for, whatever it reports.
    used_class = worker.worker_class
    cost = quotas.cost_units(wall_s, used_class)
    if job.kind == "pack":
        errors = tiles.check_pack(output, job)
        blobs: dict = {}
        if not errors:
            errors, blobs = tiles.verify_pack(db, job, output)
    else:
        errors = tiles.check_manifest(output, job)
        blobs = {}
        if not errors:
            base = tiles.read_json(db.get(RenderJob, job.base_job_id).output_key) if job.base_job_id else None
            errors, blobs = tiles.verify_tiles(db, job, output, base)
    if errors:
        db.rollback()
        raise ContractError(
            "output_invalid", 422, f"The output breaks {len(errors)} rule(s): {errors[0]['message']}", {"errors": errors}
        )
    manifest = dict(output)
    manifest.pop("tiles_base", None)
    if job.kind == "pack":
        tiles.publish_pack(db, job, manifest, blobs)
    else:
        tiles.publish_tiles(db, blobs, now)
    tiles.put_json(tiles.manifest_key(job_id), manifest)
    if isinstance(render_log, (dict, list)):
        tiles.put_json(tiles.job_file_key(job_id, "render-log.json"), {"log": render_log} if isinstance(render_log, list) else render_log)
    job.state = "succeeded"
    job.finished_at = now
    job.started_at = job.started_at or now
    job.progress = 1.0
    job.message = ""
    job.cost_units = cost
    job.wall_s = float(wall_s)
    job.used_class = used_class
    job.app_version = str(manifest.get("app_version") or "")[:32] or None
    job.faces_rendered = manifest.get("faces_rendered") if isinstance(manifest.get("faces_rendered"), int) else None
    job.output_key = tiles.manifest_key(job_id)
    job.ended_lease_id = lease_id
    job.lease_id = None
    job.lease_expires_at = None
    job.error = None
    bump(job, now)
    metering.record(db, job.account_kind, job.account_id, quotas.METRIC, cost, metering.utc_day(now))
    metering.record(db, job.account_kind, job.account_id, f"{quotas.METRIC}.{job.kind}", cost, metering.utc_day(now))
    overage.accrue(db, job.account_id, cost, terms, now)
    follow_id = sets.on_success(db, job, now)
    _worker_idle(db, worker.worker_id, now)
    db.commit()
    notify_job(job_id, follow_id)
    notify_claim()
    return job


def fail(
    db: Session, worker: Worker, job_id: str, lease_id: str, code: str, message: str, retryable: bool, log_tail: str,
    now: datetime,
) -> RenderJob:
    done = db.get(RenderJob, job_id) if isinstance(job_id, str) and len(job_id) == 32 else None
    if done is not None and done.ended_lease_id == lease_id:
        return done  # a repeat of the same failure (§8)
    db.rollback()
    job = leased(db, worker, job_id, lease_id, now)
    store = get_store()
    attempt = job.attempts + 1
    store.put(
        tiles.job_file_key(job_id, "error.json"),
        json.dumps({"code": code, "message": message, "attempt": attempt, "worker_id": worker.worker_id, "at": clock.rfc3339(now)}).encode(),
        content_type="application/json",
    )
    if log_tail:
        store.put(tiles.job_file_key(job_id, "log-tail.txt"), log_tail.encode("utf-8")[-LOG_TAIL_MAX:], content_type="text/plain; charset=utf-8")
    end_attempt(db, job, retry=retryable and code != "bad_input", error={"code": code, "message": message}, now=now)
    job.ended_lease_id = lease_id
    db.commit()
    notify_job(job_id)
    notify_claim()
    return job
