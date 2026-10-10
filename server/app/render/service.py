"""Jobs as their owner sees them (contract 5.1-5.6).

* 5.1 submit: the kind's rules, the plan's feature (403 `plan_required`), the
  project visible to the caller with `at_seq` at or before its head (409
  `seq_ahead`), an estimate, the quota (403 `quota_exceeded`). A `tiles` job
  of a followed set joins the set's queued one. `Idempotency-Key` replays.
* 5.2 status (long-polled by the router on `rev`), 5.3 list, 5.4 cancel, 5.5
  output with file URLs, 5.6 this month's cost units.

A job belongs to the account that submitted it (`account_kind` "user";
organisations with PF3): only that account sees it (others get 404).
"""

import base64
import re
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from ..models import User
from ..projects import service as projects
from ..projects.caller import ProjectCaller
from ..projects.models import Project, ProjectOp, ProjectSnapshot
from ..storage import get_store
from ..uploads import service as uploads
from . import estimates, quotas, sets, tiles
from .models import RenderJob, RenderSet
from .queue import ENDED, bump, notify_claim, notify_job

QUALITIES = ("draft", "standard", "high")
PACK_ITEMS = ("renders", "panoramas", "sheets", "boq")
MAX_VIEWS = 50
MAX_CHANGED = sets.MAX_CHANGED
PAGE_DEFAULT = 50
PAGE_MAX = 100
OUTPUT_URL_TTL = 3600
STATES = ("queued", "claimed", "running", "succeeded", "failed", "cancelled", "expired")
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_FORMAT = re.compile(r"^o5/(\d+)$")


def _invalid(field: str, message: str, **data) -> ContractError:
    return ContractError(
        "validation_failed", 422, f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}], **data},
    )


def _num(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def record_json(job: RenderJob) -> dict:
    """The job record every 5.x answer carries (plus additive keys)."""
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "state": job.state,
        "rev": job.rev,
        "project_id": job.project_id,
        "at_seq": job.at_seq,
        "progress": round(float(job.progress or 0), 3),
        "message": job.message or "",
        "created_at": clock.rfc3339(job.created_at),
        "started_at": clock.rfc3339(job.started_at),
        "finished_at": clock.rfc3339(job.finished_at),
        "attempts": job.attempts,
        "cost_units_estimate": _num(job.cost_units_estimate),
        "cost_units": _num(job.cost_units),
        "output_ready": job.state == "succeeded" and job.output_key is not None,
        "error": job.error,
        # Additive (readers ignore keys they do not know).
        "views": list(job.views or []),
        "changed_count": len(job.changed or []),
        "base_job_id": job.base_job_id,
        "quality": job.quality,
        "follow": bool(job.follow),
        "class": job.worker_class,
        "updated_at": clock.rfc3339(job.updated_at),
    }


# --- 5.1 ---------------------------------------------------------------------------------


def doc_version_needed(db: Session, project_id: str, at_seq: int) -> int:
    """The newest document version the job's log range holds: the snapshot's,
    and every `o5/<n>` after it up to `at_seq`."""
    project = db.get(Project, project_id)
    snap = db.scalar(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project_id, ProjectSnapshot.at_seq <= at_seq)
        .order_by(ProjectSnapshot.at_seq.desc())
        .limit(1)
    )
    need = snap.doc_version if snap is not None else (project.doc_version if project is not None else 0)
    after = snap.at_seq if snap is not None else 0
    formats = db.scalars(
        select(ProjectOp.delta_format)
        .where(
            ProjectOp.project_id == project_id,
            ProjectOp.server_seq > after,
            ProjectOp.server_seq <= at_seq,
            ProjectOp.delta_format.is_not(None),
        )
        .distinct()
    )
    for fmt in formats:
        m = _FORMAT.match(fmt or "")
        if m:
            need = max(need, int(m.group(1)))
    return need


def _ids(values: object, field: str, limit: int) -> list[str]:
    if not isinstance(values, list):
        raise _invalid(field, "a list of 32-hex ids")
    if len(values) > limit:
        raise _invalid(field, f"at most {limit} ids", limit=limit)
    out = []
    for v in values:
        if not isinstance(v, str) or not _HEX32.match(v.lower()):
            raise _invalid(field, "32 lowercase hex characters each")
        out.append(v.lower())
    return sorted(set(out)) if field == "changed" else list(dict.fromkeys(out))


def _job_input_files(db: Session, user: User, inputs: object) -> dict:
    if inputs in (None, {}):
        return {"upload_id": None, "files": {}}
    if not isinstance(inputs, dict) or not isinstance(inputs.get("files", {}), dict):
        raise _invalid("inputs", "{upload_id, files: {name: sha256}}")
    files = inputs.get("files") or {}
    if len(files) > 50:
        raise _invalid("inputs.files", "at most 50 files")
    for name, sha in files.items():
        if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9_]{0,39}$", name) or not isinstance(sha, str) or not _SHA.match(sha):
            raise _invalid("inputs.files", "names map to the SHA-256 of a job-input upload")
    missing = uploads.missing_files(db, user.id, list(files.values()))
    if missing:
        raise _invalid("inputs.files", "every file is uploaded first (purpose job-input)", missing=missing)
    upload_id = inputs.get("upload_id")
    return {"upload_id": upload_id if isinstance(upload_id, str) and _HEX32.match(upload_id) else None, "files": dict(files)}


def submit(db: Session, caller: ProjectCaller, body: dict) -> tuple[RenderJob, bool]:
    """Validate and queue a job. Returns (the job, joined an existing one)."""
    user = caller.user
    kind_name = body.get("kind")
    from ..analysis import submit as analysis_submit  # PF11: wind, energy, acoustics, texture

    if analysis_submit.handles(kind_name):
        return analysis_submit.submit(db, caller, body)
    kind = quotas.KINDS.get(kind_name) if isinstance(kind_name, str) else None
    if kind is None:
        raise _invalid("kind", f"one of {', '.join(quotas.KINDS)}")
    project_id = body.get("project_id")
    if not isinstance(project_id, str) or not _HEX32.match(project_id):
        raise _invalid("project_id", "the project's 32-hex id")
    at_seq = body.get("at_seq")
    if not isinstance(at_seq, int) or isinstance(at_seq, bool) or at_seq < 0:
        raise _invalid("at_seq", "a sequence number, 0 or more")
    views = _ids(body.get("views") or [], "views", MAX_VIEWS)
    changed = _ids(body.get("changed") or [], "changed", MAX_CHANGED)
    quality = body.get("quality") or "standard"
    if quality not in QUALITIES:
        raise _invalid("quality", f"one of {', '.join(QUALITIES)}")
    follow = body.get("follow") is True
    if follow and kind.name != "panorama":
        raise _invalid("follow", "only a panorama set can follow the log")
    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise _invalid("params", "an object")
    if kind.name == "panorama" and not views:
        raise _invalid("views", "a panorama job names its saved views (1 to 50)")
    if kind.name == "pack":
        items = params.get("items")
        if not isinstance(items, list) or not items or any(i not in PACK_ITEMS for i in items):
            raise _invalid("params.items", f"one or more of {', '.join(PACK_ITEMS)}")
        params = {"items": list(dict.fromkeys(items))}
    base = None
    if kind.name == "tiles":
        base_id = body.get("base_job_id")
        if not isinstance(base_id, str) or not _HEX32.match(base_id):
            raise _invalid("base_job_id", "a tiles job names the panorama job it updates")
        if "changed" not in body or body.get("changed") is None:
            raise _invalid("changed", "the changed entity ids ([] = every face)")
    plan = quotas.require_feature(db, user, kind)
    project, _member = projects.open_project(db, caller, project_id, "viewer")
    if at_seq > project.head_seq:
        raise ContractError(
            "seq_ahead", 409, f"at_seq {at_seq} is past the project's head ({project.head_seq}). Push first.",
            {"head_seq": project.head_seq},
        )
    if kind.name == "tiles":
        base = db.get(RenderJob, body["base_job_id"])
        if (
            base is None
            or base.account_id != user.id
            or base.project_id != project_id
            or base.kind not in ("panorama", "tiles")
            or base.output_key is None
        ):
            raise _invalid("base_job_id", "a finished panorama or tiles job of this project")
        if base.set_id is None and base.finished_at is not None and clock.aware(base.finished_at) < clock.now() - tiles.GC_KEEP:
            # Its tiles may be collected: render a new panorama instead.
            raise _invalid("base_job_id", "a panorama finished within the last 90 days")
        base_views = list(base.views or [])
        views = views or base_views
        if any(v not in base_views for v in views):
            raise _invalid("views", "the base job's views")
    inputs = _job_input_files(db, user, body.get("inputs"))
    now = clock.now()
    set_id = (base.set_id or None) if base is not None else None
    if set_id:
        row = sets.lock_set(db, set_id)
        joined = sets.queued_job(db, set_id) if row is not None and row.active else None
        if joined is not None:
            sets.coalesce(db, joined, [] if row.stale else changed, at_seq, now)
            row.stale = False
            db.commit()
            notify_job(joined.job_id)
            return joined, True
        # Still under the set's lock: the new job below is its only queued one.
    n_units = estimates.units(kind.name, views, params)
    estimate = estimates.estimate(db, kind.name, quality, n_units)
    quotas.check(db, user, plan, estimate)
    job = RenderJob(
        job_id=secrets.token_hex(16),
        account_kind=quotas.ACCOUNT_KIND,
        account_id=user.id,
        kind=kind.name,
        worker_class=kind.worker_class,
        state="queued",
        rev=1,
        project_id=project_id,
        at_seq=at_seq,
        views=views,
        changed=changed,
        base_job_id=base.job_id if base is not None else None,
        set_id=set_id,
        quality=quality,
        follow=follow,
        inputs=inputs,
        params=params,
        priority=plan.rank,
        doc_version_needed=doc_version_needed(db, project_id, at_seq),
        created_at=now,
        queued_at=now,
        updated_at=now,
        est_units=n_units,
        cost_units_estimate=estimate,
    )
    if follow:
        job.set_id = job.job_id
        sets.create(db, job, now)
    db.add(job)
    db.commit()
    notify_claim()
    return job, False


# --- 5.2-5.5 ------------------------------------------------------------------------------


def own_job(db: Session, user: User, job_id: str) -> RenderJob:
    job = db.get(RenderJob, job_id) if isinstance(job_id, str) and _HEX32.match(job_id) else None
    if job is None or job.account_kind != quotas.ACCOUNT_KIND or job.account_id != user.id:
        raise ContractError("not_found", 404, "No such job.")
    return job


def _encode_cursor(job: RenderJob) -> str:
    raw = f"{clock.aware(job.created_at).isoformat()}|{job.job_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        at, job_id = raw.split("|", 1)
        return datetime.fromisoformat(at), job_id
    except (ValueError, UnicodeDecodeError):
        raise ContractError(
            "validation_failed", 422, "cursor: use the next_cursor of the previous page.",
            {"fields": [{"field": "cursor", "in": "query", "message": "invalid"}]},
        )


def list_jobs(
    db: Session, user: User, *, project_id: str | None, kind: str | None, state: str | None, cursor: str | None, limit: int
) -> dict:
    if not 1 <= limit <= PAGE_MAX:
        raise ContractError(
            "validation_failed", 422, f"limit: 1 to {PAGE_MAX}.",
            {"fields": [{"field": "limit", "in": "query", "message": f"1 to {PAGE_MAX}"}]},
        )
    if state is not None and state not in STATES:
        raise ContractError(
            "validation_failed", 422, f"state: one of {', '.join(STATES)}.",
            {"fields": [{"field": "state", "in": "query", "message": "a job state"}]},
        )
    q = select(RenderJob).where(RenderJob.account_kind == quotas.ACCOUNT_KIND, RenderJob.account_id == user.id)
    if project_id:
        q = q.where(RenderJob.project_id == project_id)
    if kind:
        q = q.where(RenderJob.kind == kind)
    if state:
        q = q.where(RenderJob.state == state)
    if cursor:
        at, job_id = _decode_cursor(cursor)
        q = q.where(or_(RenderJob.created_at < at, and_(RenderJob.created_at == at, RenderJob.job_id < job_id)))
    rows = db.scalars(q.order_by(RenderJob.created_at.desc(), RenderJob.job_id.desc()).limit(limit + 1)).all()
    more = len(rows) > limit
    rows = rows[:limit]
    return {"jobs": [record_json(r) for r in rows], "next_cursor": _encode_cursor(rows[-1]) if more and rows else None}


def cancel(db: Session, user: User, job_id: str) -> RenderJob:
    from .queue import lock_job

    own_job(db, user, job_id)
    job = lock_job(db, job_id)
    now = clock.now()
    if job.state == "queued":
        job.state = "cancelled"
        job.finished_at = now
        bump(job, now)
        sets.on_ended(db, job, now)
    elif job.state in ("claimed", "running"):
        if not job.cancel_requested:
            job.cancel_requested = True
            job.message = "Stopping…"
            bump(job, now)
    elif job.state == "succeeded" and job.follow and job.set_id == job.job_id:
        row = db.get(RenderSet, job.job_id)
        if row is not None:
            sets.stop(db, row, now)
        job.follow = False
        bump(job, now)
    else:
        db.rollback()
        raise ContractError(
            "job_finished", 409, f"This job has already {'finished' if job.state == 'succeeded' else job.state}.",
            {"state": job.state},
        )
    db.commit()
    notify_job(job.job_id)
    return job


def output(db: Session, user: User, job_id: str) -> dict:
    job = own_job(db, user, job_id)
    if job.state != "succeeded" or job.output_key is None:
        raise ContractError("not_ready", 409, "This job has no output yet.", {"state": job.state})
    data = tiles.read_json(job.output_key)
    if data is None:
        raise ContractError("not_found", 404, "This job's output is no longer stored.")
    from ..analysis import results as analysis_results  # PF11: §6.3 results with file URLs

    if analysis_results.handles_output(data):
        analysis_results.sign(job, data, OUTPUT_URL_TTL)
    elif data.get("schema", "").startswith("truebex-pack/"):
        store = get_store()
        source = job.output_key.rsplit("/", 1)[0]  # jobs/{the job that made it}
        for f in data.get("files", []):
            f["url"] = store.signed_get_url(
                f"{source}/files/{f['sha256']}", expires_in=OUTPUT_URL_TTL, filename=f.get("name")
            )
        data["urls_expire_at"] = clock.rfc3339(clock.now() + timedelta(seconds=OUTPUT_URL_TTL))
    else:
        data["tiles_base"] = tiles.tiles_base()
    data["rev"] = job.rev
    return data


# --- 5.6 ------------------------------------------------------------------------------------


def usage(db: Session, user: User) -> dict:
    from .. import metering

    plan = quotas.plan_of(db, user)
    start, end = quotas.month_bounds()
    used = metering.total(db, quotas.ACCOUNT_KIND, user.id, quotas.METRIC, start, end)
    limit = quotas.allowance(plan)
    by_kind = metering.by_metric(db, quotas.ACCOUNT_KIND, user.id, f"{quotas.METRIC}.", start, end)
    daily = metering.daily(db, quotas.ACCOUNT_KIND, user.id, quotas.METRIC, start, end)
    days = []
    day = start
    today = clock.now().date()
    while day < end and day <= today:
        days.append({"day": day.isoformat(), "cu": float(daily.get(day, Decimal(0)))})
        day += timedelta(days=1)
    reserved = quotas.in_flight_cu(db, user.id)
    allowed = quotas.overage_allowed(plan)
    cap = quotas.overage_cap(db, user.id) if allowed else Decimal(0)
    from .overage import used_this_month

    over = used_this_month(db, user.id)
    currency = _currency(db, user)
    return {
        "period_start": quotas.rfc3339_day(start),
        "period_end": quotas.rfc3339_day(end),
        "used_cu": float(used),
        "limit_cu": limit,
        "remaining_cu": float(max(Decimal(0), Decimal(limit) - used)) if limit is not None else None,
        "classes": {k: float(v) for k, v in quotas.class_weights().items()},
        "by_kind": {metric.split(".", 1)[1]: float(v) for metric, v in sorted(by_kind.items())},
        # Additive: the chart, in-flight estimates and the overage terms.
        "daily": days,
        "reserved_cu": float(reserved),
        "plan": plan.id,
        "overage": {
            "allowed": allowed,
            "cap_cu": float(cap),
            "used_cu": float(over),
            "price_minor": quotas.overage_price_minor(currency),
            "currency": currency,
        },
    }


def _currency(db: Session, user: User) -> str:
    from ..licence import seats

    sub = seats.seat_source(db, user).subscription
    return (sub.currency if sub is not None and sub.currency else "GBP").upper()


def recent_cost_by_kind(db: Session, start: datetime) -> dict[str, float]:
    rows = db.execute(
        select(RenderJob.kind, func.coalesce(func.sum(RenderJob.cost_units), 0))
        .where(RenderJob.state == "succeeded", RenderJob.finished_at >= start)
        .group_by(RenderJob.kind)
    ).all()
    return {kind: float(total or 0) for kind, total in rows}


def ended(job: RenderJob) -> bool:
    return job.state in ENDED
