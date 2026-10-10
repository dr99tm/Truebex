"""Plan gates and quotas of the project service (contract §4, §7).

* `cloud.sync` (the entitlement feature): creating a project, pushing or
  uploading a snapshot from a device, and inviting need it (403
  `plan_required` with `data.feature`).
* Limits `cloud_projects` (projects owned), `cloud_bytes` (snapshot blobs and
  offloaded deltas of the projects owned) and `project_members` (people on a
  project, the owner and pending invitations included): 403 `quota_exceeded`
  with `data.limit`, `data.used` and `data.quota`.

The limit keys are a MINOR proposal for licence-api.md §6.3 (PF4 As-built).
Until the owner adds them to catalogue.json `limits`, the placeholders below
apply; a value in the catalogue wins as soon as it is there. None = no limit.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import seats
from ..models import User
from ..plans import Plan, get_plan
from .models import Project

GIB = 1024 * 1024 * 1024
FEATURE = "cloud.sync"
KEYS = ("cloud_projects", "cloud_bytes", "project_members")

# Placeholders "from GD7" (the guide has no matrix yet).
PLACEHOLDER: dict[str, dict[str, int | None]] = {
    "free": {"cloud_projects": 0, "cloud_bytes": 0, "project_members": 1},
    "pro": {"cloud_projects": 50, "cloud_bytes": 10 * GIB, "project_members": 5},
    "studio": {"cloud_projects": 200, "cloud_bytes": 50 * GIB, "project_members": 10},
    "team": {"cloud_projects": 500, "cloud_bytes": 200 * GIB, "project_members": 50},
    "enterprise": {"cloud_projects": None, "cloud_bytes": None, "project_members": None},
}


def plan_of(db: Session, user: User) -> Plan:
    # Looked up at call time: PF3 (and tests) swap seats.seat_source.
    return get_plan(seats.seat_source(db, user).plan)


def limit(plan: Plan, key: str) -> int | None:
    if key in plan.limits:
        return plan.limits[key]
    return PLACEHOLDER.get(plan.id, PLACEHOLDER["free"])[key]


def require_feature(db: Session, user: User, feature: str = FEATURE) -> Plan:
    plan = plan_of(db, user)
    if feature not in plan.features:
        raise ContractError(
            "plan_required",
            403,
            "Cloud projects come with a paid plan or the trial. Upgrade to save to the cloud.",
            {"feature": feature, "plan": plan.id},
        )
    return plan


def exceeded(key: str, limit_value: int, used: int) -> ContractError:
    what = {
        "cloud_projects": f"Your plan holds {limit_value} cloud projects.",
        "cloud_bytes": "Your plan's cloud storage is full.",
        "project_members": f"A project on this plan holds {limit_value} people.",
    }[key]
    return ContractError(
        "quota_exceeded", 403, f"{what} Upgrade or make room to continue.", {"limit": limit_value, "used": used, "quota": key}
    )


def projects_owned(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count()).select_from(Project).where(Project.owner_user_id == user_id, Project.deleted_at.is_(None))
    ) or 0


def bytes_used(db: Session, owner_id: int) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(Project.bytes), 0)).where(
                Project.owner_user_id == owner_id, Project.deleted_at.is_(None)
            )
        )
        or 0
    )


def check_projects(db: Session, owner: User, plan: Plan) -> None:
    cap = limit(plan, "cloud_projects")
    used = projects_owned(db, owner.id)
    if cap is not None and used + 1 > cap:
        raise exceeded("cloud_projects", cap, used)


def check_bytes(db: Session, owner: User, extra: int) -> None:
    if extra <= 0:
        return
    cap = limit(plan_of(db, owner), "cloud_bytes")
    used = bytes_used(db, owner.id)
    if cap is not None and used + extra > cap:
        raise exceeded("cloud_bytes", cap, used)


def bytes_quota(db: Session, owner: User) -> dict:
    """5.3's `quota`: the owner's limit and what their projects use."""
    return {"bytes": limit(plan_of(db, owner), "cloud_bytes"), "bytes_used": bytes_used(db, owner.id)}


def check_members(db: Session, owner: User, people: int) -> None:
    cap = limit(plan_of(db, owner), "project_members")
    if cap is not None and people + 1 > cap:
        raise exceeded("project_members", cap, people)
