"""An organisation's seats: named (one member's alone) and floating (a pool of
concurrent leases), and how they reach a device's entitlement.

The organisation's tier and seat count come from its live subscription
(`subscriptions.organisation_id`). Of those seats, `floating_seats` float
(capped at the total); the rest are named. A member holds at most one
assignment per organisation: `named`, or `floating` (may lease).

Leases (contract licence-api §6.1, 5.5, 5.11): a floating member's device
takes a lease with its entitlement document and renews it with every refresh
(`refresh_after` 30 min, `expires_at` 2 h); 5.11 hands it back; a lease not
renewed lapses with its document. Taking one locks the organisation row in
one transaction (a write to it: SQLite's RESERVED lock, Postgres's row lock),
so two devices can never take the last seat.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import mail
from ..billing.service import seats_assigned as subscription_seats
from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock
from ..licence.models import Device
from ..licence.seats import FIXED_TERM_PROVIDERS, Seat
from ..models import Subscription, User
from ..plans import get_plan
from . import audit
from .models import FloatingLease, OrgInvite, OrgMember, Organisation, SeatAssignment

LEASE_LIFE = timedelta(hours=2)
# Hand-assigned subscriptions (scripts/grant_org_seats.py); a period end, when
# given, is a fixed term.
MANUAL_PROVIDER = "manual"
# On equal tier rank: a seat of your own, then named, trial, floating, Free.
_PREFERENCE = {"personal": 4, "named": 3, "trial": 2, "floating": 1, "free": 0}


@dataclass(frozen=True)
class Pool:
    tier: str | None  # None: no live subscription, so no seats
    total: int
    named_total: int
    floating_total: int
    named_assigned: int
    floating_members: int
    floating_in_use: int
    subscription: Subscription | None


def _subscription(db: Session, org_id: str, now: datetime) -> Subscription | None:
    from .service import org_subscription

    return org_subscription(db, org_id, now)


def open_leases(db: Session, org_id: str, now: datetime) -> list[FloatingLease]:
    return list(
        db.scalars(
            select(FloatingLease)
            .where(
                FloatingLease.org_id == org_id,
                FloatingLease.released_at.is_(None),
                FloatingLease.expires_at > now,
            )
            .order_by(FloatingLease.leased_at)
        )
    )


def _count_in_use(db: Session, org_id: str, now: datetime) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(FloatingLease).where(
                FloatingLease.org_id == org_id,
                FloatingLease.released_at.is_(None),
                FloatingLease.expires_at > now,
            )
        )
        or 0
    )


def _assignments(db: Session, org_id: str, kind: str) -> list[SeatAssignment]:
    return list(
        db.scalars(
            select(SeatAssignment)
            .where(SeatAssignment.org_id == org_id, SeatAssignment.kind == kind)
            .order_by(SeatAssignment.assigned_at, SeatAssignment.user_id)
        )
    )


def pool(db: Session, org: Organisation, now: datetime) -> Pool:
    sub = _subscription(db, org.id, now)
    total = (sub.seats or 1) if sub is not None else 0
    floating = max(0, min(org.floating_seats or 0, total))
    return Pool(
        tier=sub.plan if sub is not None else None,
        total=total,
        named_total=total - floating,
        floating_total=floating,
        named_assigned=len(_assignments(db, org.id, "named")),
        floating_members=len(_assignments(db, org.id, "floating")),
        floating_in_use=_count_in_use(db, org.id, now),
        subscription=sub,
    )


def kind_of(db: Session, org_id: str, user_id: int) -> str:
    row = db.get(SeatAssignment, (org_id, user_id))
    return row.kind if row else "none"


def _no_seat_left(detail: str, **data) -> ContractError:
    return ContractError("no_seat_left", 409, detail, data or None)


def check_capacity(
    db: Session, org: Organisation, kind: str, now: datetime, *, pending_invites: bool = False
) -> Pool:
    p = pool(db, org, now)
    if p.tier is None:
        raise _no_seat_left(f"{org.name} has no subscription with seats yet.", total=0)
    if kind == "named":
        used = p.named_assigned
        if pending_invites:
            used += sum(
                1
                for inv in db.scalars(
                    select(OrgInvite).where(OrgInvite.org_id == org.id, OrgInvite.seat_kind == "named")
                )
                if _invite_pending(inv, now)
            )
        if used >= p.named_total:
            raise _no_seat_left(
                f"All {p.named_total} named seats of {org.name} are taken. Free one or buy more seats.",
                total=p.named_total, assigned=p.named_assigned,
            )
    elif kind == "floating" and p.floating_total == 0:
        raise _no_seat_left(
            f"{org.name} has no floating seats. Set how many seats float on the Seats tab first.", total=0
        )
    return p


def _invite_pending(inv: OrgInvite, now: datetime) -> bool:
    from .service import invite_status

    return invite_status(inv, now) == "pending"


def assign(db: Session, org: Organisation, actor_id: int | None, user_id: int, kind: str, now: datetime) -> str:
    """Give a member a `named` or `floating` seat, or take it away (`none`)."""
    if db.get(OrgMember, (org.id, user_id)) is None:
        raise ContractError("not_found", 404, "That person is not a member of this organisation.")
    current = db.get(SeatAssignment, (org.id, user_id))
    previous = current.kind if current else "none"
    if previous == kind:
        return kind
    if kind == "none":
        db.delete(current)
        end_leases(db, org_id=org.id, user_id=user_id, reason="seat_changed", now=now)
        audit.record(
            db, org.id, "seat.unassigned", actor=actor_id, target_kind="user", target_id=user_id, at=now,
            previous=previous,
        )
        db.commit()
        return "none"
    p = check_capacity(db, org, kind, now)
    if current is None:
        current = SeatAssignment(org_id=org.id, user_id=user_id, kind=kind, assigned_by=actor_id, assigned_at=now)
    else:
        current.kind, current.assigned_by, current.assigned_at = kind, actor_id, now
    db.add(current)
    if kind == "named":  # a named seat needs no lease
        end_leases(db, org_id=org.id, user_id=user_id, reason="seat_changed", now=now)
    audit.record(
        db, org.id, "seat.assigned", actor=actor_id, target_kind="user", target_id=user_id, at=now,
        seat=kind, previous=previous,
    )
    db.commit()
    member = db.get(User, user_id)
    actor = db.get(User, actor_id) if actor_id else None
    if member is not None:
        tier = get_plan(p.tier)
        mail.try_send(
            member.email,
            "org_seat_assigned",
            {
                "org_name": org.name,
                "actor": (actor.name or actor.email) if actor else org.name,
                "seat_name": kind,
                "plan_name": tier.name,
                "seat_line": "It is yours alone." if kind == "named" else (
                    "Floating seats are shared: Truebex takes one while it runs and hands it back when you close it."
                ),
                "link": f"{get_settings().site_url.rstrip('/')}/dashboard/organisation/",
            },
        )
    return kind


def set_floating(db: Session, org: Organisation, actor_id: int, floating: int, now: datetime) -> Pool:
    p = pool(db, org, now)
    if floating > p.total:
        raise ContractError(
            "validation_failed", 422, f"floating: at most {p.total} (the organisation's seats)",
            {"fields": [{"field": "floating", "in": "body", "message": f"at most {p.total}"}]},
        )
    if p.named_assigned > p.total - floating:
        raise _no_seat_left(
            f"{p.named_assigned} named seats are assigned, so at most {p.total - p.named_assigned} can float. "
            "Unassign named seats first.",
            named_assigned=p.named_assigned,
        )
    if floating != (org.floating_seats or 0):
        audit.record(
            db, org.id, "seats.floating_changed", actor=actor_id, target_kind="org", target_id=org.id, at=now,
            old=org.floating_seats or 0, new=floating,
        )
        org.floating_seats = floating
        db.add(org)
        db.commit()
    return pool(db, org, now)


def seats_json(db: Session, org: Organisation, now: datetime) -> dict:
    p = pool(db, org, now)
    leases = open_leases(db, org.id, now)
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_({l.user_id for l in leases})))} if leases else {}
    devs = (
        {d.device_id: d for d in db.scalars(select(Device).where(Device.device_id.in_({l.device_id for l in leases})))}
        if leases else {}
    )
    return {
        "tier": p.tier,
        "tier_name": get_plan(p.tier).name if p.tier else None,
        "total": p.total,
        "named": {"total": p.named_total, "assigned": p.named_assigned},
        "floating": {
            "total": p.floating_total,
            "in_use": p.floating_in_use,
            "members": p.floating_members,
            "leases": [
                {
                    "user": {
                        "user_id": l.user_id,
                        "email": users[l.user_id].email if l.user_id in users else None,
                        "name": users[l.user_id].name if l.user_id in users else None,
                    },
                    "device": {"device_id": l.device_id, "name": devs[l.device_id].name if l.device_id in devs else None},
                    "since": clock.rfc3339(l.leased_at),
                    "expires_at": clock.rfc3339(l.expires_at),
                }
                for l in leases
            ],
        },
    }


# --- seats as entitlements (seat_source and claim, app/licence/seats.py) -----------


def _score(seat: Seat) -> tuple[int, int]:
    return get_plan(seat.plan).rank, _PREFERENCE.get(seat.kind, 0)


def candidates(db: Session, user: User, now: datetime) -> list[Seat]:
    """The organisation seats `user` holds right now (named seats beyond a
    reduced seat count go to the earliest assigned)."""
    rows = db.execute(
        select(SeatAssignment, Organisation)
        .join(Organisation, Organisation.id == SeatAssignment.org_id)
        .join(OrgMember, (OrgMember.org_id == SeatAssignment.org_id) & (OrgMember.user_id == SeatAssignment.user_id))
        .where(SeatAssignment.user_id == user.id, Organisation.deleted_at.is_(None))
    ).all()
    out: list[Seat] = []
    for assignment, org in rows:
        p = pool(db, org, now)
        if p.tier is None:
            continue
        if assignment.kind == "named":
            order = [a.user_id for a in _assignments(db, org.id, "named")]
            if order.index(user.id) >= p.named_total:
                continue
        elif p.floating_total == 0:
            continue
        tier = get_plan(p.tier)
        sub = p.subscription
        period_end = clock.aware(sub.current_period_end)
        fixed = sub.provider in FIXED_TERM_PROVIDERS or sub.provider == MANUAL_PROVIDER
        out.append(
            Seat(
                kind=assignment.kind,
                plan=tier.id,
                devices_limit=tier.limits.get("devices"),
                org_id=org.id,
                org_name=org.name,
                ends_at=period_end if fixed else None,
                period_end=period_end,
                seats_total=p.total,
                # PF3a: the subscription's seats given to people (named + the floating pool).
                seats_assigned=subscription_seats(db, sub),
                subscription=sub,
            )
        )
    return out


def best_seat(db: Session, user: User, personal: Seat) -> Seat:
    return max([personal, *candidates(db, user, clock.now())], key=_score)


class _PoolFull(Exception):
    def __init__(self, error: ContractError) -> None:
        super().__init__(error.detail)
        self.error = error


def _lock(db: Session, org_id: str) -> None:
    """Take the organisation row's write lock until the commit: pysqlite opens
    its transaction at the first write, which takes SQLite's RESERVED lock;
    on Postgres the UPDATE holds the row lock (as SELECT ... FOR UPDATE)."""
    db.execute(
        update(Organisation).where(Organisation.id == org_id).values(lease_seq=Organisation.lease_seq + 1)
    )


def _take_lease(db: Session, seat: Seat, user: User, device: Device, now: datetime) -> None:
    expires = clock.floor_s(now) + LEASE_LIFE
    mine = db.scalar(
        select(FloatingLease).where(
            FloatingLease.org_id == seat.org_id,
            FloatingLease.device_id == device.device_id,
            FloatingLease.released_at.is_(None),
            FloatingLease.expires_at > now,
        )
    )
    if mine is not None:  # a refresh renews the lease with the document
        org = db.get(Organisation, seat.org_id)
        keep = pool(db, org, now).floating_total if org is not None and org.deleted_at is None else 0
        oldest = [l.id for l in open_leases(db, seat.org_id, now)][:keep]
        if mine.id not in oldest:
            # The pool shrank below the seats in use: the newest leases end at
            # their next refresh, the oldest keep theirs.
            mine.released_at, mine.end_reason = now, "pool_reduced"
            db.add(mine)
            audit.record(
                db, seat.org_id, "lease.released", actor=user.id, target_kind="device",
                target_id=device.device_id, at=now, reason="pool_reduced",
            )
            db.commit()
            raise _PoolFull(
                ContractError(
                    "no_seat_available",
                    409,
                    f"All {keep} floating seat{'' if keep == 1 else 's'} {'is' if keep == 1 else 'are'} in use. "
                    "Try again when someone closes Truebex.",
                    {"total": keep, "org_id": seat.org_id, "org_name": seat.org_name},
                )
            )
        mine.expires_at = expires
        db.add(mine)
        db.commit()
        return
    _lock(db, seat.org_id)
    org = db.get(Organisation, seat.org_id)
    if org is None or org.deleted_at is not None:
        db.rollback()
        raise _PoolFull(ContractError("no_seat_available", 409, "That organisation's seats are gone.", {"total": 0}))
    db.refresh(org)
    p = pool(db, org, now)
    if p.floating_in_use >= p.floating_total:
        db.rollback()
        audit.record(
            db, org.id, "lease.refused", actor=user.id, target_kind="device", target_id=device.device_id, at=now,
            total=p.floating_total,
        )
        db.commit()
        noun = "seat is" if p.floating_total == 1 else "seats are"
        raise _PoolFull(
            ContractError(
                "no_seat_available",
                409,
                f"All {p.floating_total} floating {noun} in use. Try again when someone closes Truebex.",
                {"total": p.floating_total, "org_id": org.id, "org_name": org.name},
            )
        )
    db.add(
        FloatingLease(org_id=org.id, user_id=user.id, device_id=device.device_id, leased_at=now, expires_at=expires)
    )
    audit.record(
        db, org.id, "lease.taken", actor=user.id, target_kind="device", target_id=device.device_id, at=now,
        device_name=device.name, expires_at=clock.rfc3339(expires),
    )
    db.commit()


def claim(db: Session, user: User, device: Device, seat: Seat, now: datetime, *, when_full: str = "raise") -> Seat:
    from ..licence.seats import personal_seat

    queue = [seat]
    if seat.kind == "floating":
        others = sorted(candidates(db, user, now), key=_score, reverse=True)
        queue += [s for s in others if (s.kind, s.org_id) != (seat.kind, seat.org_id)]
        queue.append(personal_seat(db, user))
    full: ContractError | None = None
    for option in queue:
        if option.kind != "floating":
            if full is not None and option.kind == "free" and when_full == "raise":
                raise full
            end_leases(db, device_id=device.device_id, reason="seat_changed", now=now)
            return option
        try:
            _take_lease(db, option, user, device, now)
        except _PoolFull as exc:
            full = full or exc.error
            continue
        end_leases(db, device_id=device.device_id, reason="seat_changed", now=now, keep_org=option.org_id)
        return option
    raise full or ContractError("no_seat_available", 409, "No floating seat is available.")


def end_leases(
    db: Session,
    *,
    reason: str,
    now: datetime,
    org_id: str | None = None,
    user_id: int | None = None,
    device_id: str | None = None,
    keep_org: str | None = None,
) -> int:
    """Hand open leases back to their pools (the caller commits)."""
    q = select(FloatingLease).where(FloatingLease.released_at.is_(None), FloatingLease.expires_at > now)
    if org_id is not None:
        q = q.where(FloatingLease.org_id == org_id)
    if user_id is not None:
        q = q.where(FloatingLease.user_id == user_id)
    if device_id is not None:
        q = q.where(FloatingLease.device_id == device_id)
    if keep_org is not None:
        q = q.where(FloatingLease.org_id != keep_org)
    rows = list(db.scalars(q))
    for lease in rows:
        lease.released_at = now
        lease.end_reason = reason
        db.add(lease)
        audit.record(
            db, lease.org_id, "lease.released", actor=lease.user_id, target_kind="device",
            target_id=lease.device_id, at=now, reason=reason,
        )
    return len(rows)


def release(db: Session, device: Device, now: datetime) -> bool:
    """5.11: hand this device's floating seat back. False when it holds none
    and its seat is not floating (409 `not_floating`); repeating is harmless."""
    if end_leases(db, device_id=device.device_id, reason="released", now=now):
        db.commit()
        return True
    return device.seat_kind == "floating"


def expire_leases(db: Session, now: datetime) -> int:
    """The licence.leases.expire job: leases whose document ran out return to
    the pool (a closed laptop's lease ends with its 2 h document)."""
    rows = list(
        db.scalars(
            select(FloatingLease).where(FloatingLease.released_at.is_(None), FloatingLease.expires_at <= now)
        )
    )
    for lease in rows:
        lease.released_at = clock.aware(lease.expires_at)
        lease.end_reason = "lapsed"
        db.add(lease)
        audit.record(
            db, lease.org_id, "lease.lapsed", actor=lease.user_id, target_kind="device",
            target_id=lease.device_id, at=now,
        )
    return len(rows)
