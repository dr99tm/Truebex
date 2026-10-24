"""An airflow job waits for its wind job (render-jobs 1.2.0 §6.5.3; PF11c).

An airflow job names the wind job of its direction (`params.wind_job_id`,
kept as the job's `base_job_id`), whose Cp it runs on. It stays `queued` and
no worker can claim it until that wind job has succeeded (`ready`, a clause
of the claim's candidate query, `render.queue._candidate`). When the wind job
fails, is cancelled or expires, every airflow job still waiting on it ends
`failed` with `bad_input` at no charge (`on_ended`, from
`render.sets.on_ended`, which every such end runs); when it succeeds, the
waiting jobs are told (`on_succeeded`: their message clears and their `rev`
moves, so a long poll on them returns). Both wake those jobs' long polls once
the transaction commits. So a study submits every job at once.

`wind_job_for` checks a submission's `wind_job_id` (422 on
params.wind_job_id): a wind job of the caller's own account with the same
speed, direction, reference height and terrain that has not failed, been
cancelled or expired. Another account's job reads exactly as an unknown id.
"""

import math
from datetime import datetime

from sqlalchemy import and_, event, exists, or_, select
from sqlalchemy.orm import Session, aliased

from ..render import quotas
from ..render.models import RenderJob
from .kinds import SITE_KEYS
from .validation import invalid

KIND = "airflow"
WIND = "wind"
WAITING = "Waits for its wind job to finish."
ENDED = {"failed": "failed", "cancelled": "was cancelled", "expired": "expired"}
_NOTIFY = "pf11c_airflow_notify"


def ready(j):
    """The claim's clause: not an airflow job, or one whose wind job has succeeded."""
    wind = aliased(RenderJob)
    return or_(j.kind != KIND, exists().where(and_(wind.job_id == j.base_job_id, wind.state == "succeeded")))


def _same(a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-9)
    return a == b


def wind_job_for(db: Session, user, params: dict) -> RenderJob:
    job = db.get(RenderJob, params["wind_job_id"])
    if job is None or job.account_kind != quotas.ACCOUNT_KIND or job.account_id != user.id or job.kind != WIND:
        raise invalid("params.wind_job_id", "a wind job of this account: the study's wind job of the same direction")
    differs = [k for k in SITE_KEYS if not _same((job.params or {}).get(k), params.get(k))]
    if differs:
        raise invalid(
            "params.wind_job_id", f"the wind job of the same {', '.join(differs)} (an airflow job runs on its Cp)", differs=differs
        )
    if job.state in ENDED:
        raise invalid("params.wind_job_id", f"a wind job that has not ended: this one {ENDED[job.state]}", state=job.state)
    return job


def _waiting(db: Session, wind_job_id: str) -> list[RenderJob]:
    q = select(RenderJob).where(RenderJob.kind == KIND, RenderJob.base_job_id == wind_job_id, RenderJob.state == "queued")
    if db.get_bind().dialect.name == "postgresql":
        q = q.with_for_update()
    return list(db.scalars(q))


def _note(db: Session, job_id: str) -> None:
    db.info.setdefault(_NOTIFY, set()).add(job_id)


def on_ended(db: Session, job: RenderJob, now: datetime) -> None:
    """A wind job failed, was cancelled or expired: its waiting airflow jobs end with it."""
    from ..render.queue import bump

    if job.kind != WIND or job.state not in ENDED:
        return
    for air in _waiting(db, job.job_id):
        air.state = "failed"
        air.finished_at = now
        air.message = ""
        air.error = {"code": "bad_input", "message": f"Its wind job {ENDED[job.state]}, so there is no outdoor pressure to run on. Submit the study again."}
        bump(air, now)
        _note(db, air.job_id)


def on_succeeded(db: Session, job: RenderJob, now: datetime) -> None:
    """A wind job succeeded: its airflow jobs can be claimed now (the claim's notify wakes the workers)."""
    from ..render.queue import bump

    if job.kind != WIND:
        return
    for air in _waiting(db, job.job_id):
        air.message = ""
        bump(air, now)
        _note(db, air.job_id)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    ids = session.info.pop(_NOTIFY, None)
    if ids:
        from ..render.queue import notify_job

        notify_job(*sorted(ids))


@event.listens_for(Session, "after_rollback")
def _after_rollback(session: Session) -> None:
    session.info.pop(_NOTIFY, None)
