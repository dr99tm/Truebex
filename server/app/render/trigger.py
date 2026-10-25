"""A tiles job's trigger (render-jobs 1.3.0, CL4): the operations PF4's push
hook queued the job for, extended when later pushes join it.

A viewer stamps another writer's edit from it (CL4's stage table: T0 the
writer's `at`, T1 when the platform accepted the operation). Answered on a
tiles job's record as

    {"op_ids", "first_seq", "last_seq", "first_op_at", "first_accepted_at", "authors"}

op_ids and authors in server order, the times RFC 3339 UTC with milliseconds.
Stored on `render_jobs.trigger` as

    {"ops": [[server_seq, op_id], ...], "authors": [[server_seq, author], ...],
     "last_seq": n, "first_op_at": "...Z", "first_accepted_at": "...Z"}

so a merge keeps server order whatever order two pushes' hooks ran in. `ops`
keeps at most MAX_OPS, the earliest (a record is read on every long poll);
`last_seq`, the times and the authors still cover every operation. A tiles job
submitted by POST /jobs has none until a push joins it.
"""

from datetime import datetime, timezone

from ..licence import clock

MAX_OPS = 1000


def stamp(dt: datetime) -> str:
    """RFC 3339 UTC with milliseconds (a fixed width, so two compare as text)."""
    dt = clock.aware(dt).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _writer_at(value: object) -> str | None:
    """An operation's `at` (the writer's clock, any zone) in UTC."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp(parsed) if parsed.tzinfo is not None else None


def from_ops(ops: list[dict], accepted: dict[int, datetime], now: datetime) -> dict | None:
    """The trigger of operations on the wire (§6.2 with `server_seq`);
    `accepted` maps a server_seq to when the platform accepted it (`now` when
    it is not known)."""
    rows = sorted((int(op["server_seq"]), op) for op in ops if op.get("op_id") and op.get("server_seq") is not None)
    if not rows:
        return None
    ats = [at for at in (_writer_at(op.get("at")) for _, op in rows) if at is not None]
    first_accepted = stamp(min(clock.aware(accepted.get(seq) or now) for seq, _ in rows))
    authors: dict[str, int] = {}
    for seq, op in rows:
        if isinstance(op.get("author"), str):
            authors.setdefault(op["author"], seq)
    return {
        "ops": [[seq, op["op_id"]] for seq, op in rows[:MAX_OPS]],
        "authors": [[seq, author] for author, seq in authors.items()],
        "last_seq": rows[-1][0],
        # The stub's rule (RenderJobsStub.cpp OnOpsAccepted): no writer's time, the accepted one.
        "first_op_at": min(ats) if ats else first_accepted,
        "first_accepted_at": first_accepted,
    }


def merge(old: dict | None, new: dict | None) -> dict | None:
    """Two triggers as one: operations united in server order, the earliest
    times, the authors by first appearance."""
    if not old or not new:
        return old or new or None
    ops: dict[str, int] = {}
    for seq, op_id in [*old["ops"], *new["ops"]]:
        ops[op_id] = min(seq, ops.get(op_id, seq))
    authors: dict[str, int] = {}
    for seq, author in [*old["authors"], *new["authors"]]:
        authors[author] = min(seq, authors.get(author, seq))
    return {
        "ops": sorted(([seq, op_id] for op_id, seq in ops.items()), key=lambda r: (r[0], r[1]))[:MAX_OPS],
        "authors": sorted(([seq, author] for author, seq in authors.items()), key=lambda r: (r[0], r[1])),
        "last_seq": max(old["last_seq"], new["last_seq"]),
        "first_op_at": min(old["first_op_at"], new["first_op_at"]),
        "first_accepted_at": min(old["first_accepted_at"], new["first_accepted_at"]),
    }


def public(stored: dict | None) -> dict | None:
    """The record's `trigger`."""
    if not stored or not stored.get("ops"):
        return None
    return {
        "op_ids": [op_id for _, op_id in stored["ops"]],
        "first_seq": stored["ops"][0][0],
        "last_seq": stored["last_seq"],
        "first_op_at": stored["first_op_at"],
        "first_accepted_at": stored["first_accepted_at"],
        "authors": [author for _, author in sorted(stored["authors"], key=lambda r: (r[0], r[1]))],
    }
