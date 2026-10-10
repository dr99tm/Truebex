"""The operation log (contract 5.6, 5.7, §6.2, §6.3).

Push: one transaction that first locks the project row (an UPDATE, which is
`BEGIN IMMEDIATE`-equivalent on SQLite, where it takes the write lock, and a
row lock on Postgres), then takes the operations in array order:

1. an `op_id` already stored (or earlier in this batch) → `duplicate` with its number;
2. else any accepted operation W of another replica with
   `W.server_seq > op.base_seq` sharing a `touched` id, or any `restore` after
   `base_seq` (it touches everything) → `rejected` with `winning` (≤ 50, in
   order) and the rest of the batch `not_processed`;
3. else `server_seq = head + 1`.

Numbers are contiguous because only the lock holder assigns them. The server
never decodes a delta or runs an action: it checks sizes, ids and order.
Deltas over 64 KiB live in storage at `projects/{pid}/ops/{server_seq}.bin`.
"""

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..contract_http import ContractError, validation_fields
from ..licence import clock
from ..storage import get_store
from . import quotas
from .models import OpTouched, Project, ProjectOp
from .service import is_hex32, not_found

MAX_OPS = 200
MAX_PUSH_BYTES = 16 * 1024 * 1024
MAX_DELTA_BYTES = 4 * 1024 * 1024
INLINE_DELTA_BYTES = 64 * 1024
MAX_ACTION_BYTES = 64 * 1024
MAX_TOUCHED = 10_000
MAX_WINNING = 50
PULL_LIMIT_MAX = 1000
PULL_LIMIT_DEFAULT = 500
WAIT_MAX_S = 25
# A pull stops adding operations past this many delta bytes (`more` = true).
PULL_MAX_BYTES = 16 * 1024 * 1024
KINDS = ("delta", "action")
# agent-interface.md §5: the tools that may travel as log `action` operations;
# `place` only for objects and products.
LOG_SAFE_TOOLS = ("place", "move", "resize", "fill", "apply_theme")
PLACE_LOG_SAFE_KINDS = ("object", "product")
_B64_MAX_CHARS = 4 * ((MAX_DELTA_BYTES + 2) // 3)
_IN_CHUNK = 500


class OpIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    op_id: str = Field(max_length=32)
    author: str = Field(max_length=32)
    author_kind: str = Field(max_length=8)
    at: str = Field(max_length=40)
    touched: list[str] = Field(default_factory=list)
    kind: str = Field(max_length=16)
    name: str = Field(default="", max_length=80)
    base_seq: int = Field(ge=0)
    replica_id: str | None = Field(default=None, max_length=32)
    delta_format: str | None = Field(default=None, max_length=32)
    delta: str | None = None
    action: dict | None = None


class PushIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    replica_id: str = Field(max_length=32)
    ops: list[OpIn]


@dataclass
class ParsedOp:
    op_id: str
    author: str
    author_kind: str
    at: str
    touched: list[str]
    kind: str
    name: str
    base_seq: int
    delta_format: str | None
    delta: bytes | None
    action: dict | None


def _invalid(field: str, message: str, **extra) -> ContractError:
    return ContractError(
        "validation_failed",
        422,
        f"{field}: {message}",
        {"fields": [{"field": field, "in": "body", "message": message}], **extra},
    )


def _no_constants(name: str):
    """NaN and Infinity are not JSON: stored, they would break every later pull."""
    raise ValueError(name)


def _parse_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or "T" not in value:
        raise ValueError("an RFC 3339 time with a zone")


def _check_action(action: dict, where: str) -> None:
    if len(json.dumps(action, separators=(",", ":")).encode()) > MAX_ACTION_BYTES:
        raise _invalid(where, "an action is at most 64 KiB")
    tool = action.get("tool")
    if tool not in LOG_SAFE_TOOLS:
        raise _invalid(f"{where}.tool", f"{tool!r} is not a log-safe tool ({', '.join(LOG_SAFE_TOOLS)})")
    args = action.get("args")
    if not isinstance(args, dict):
        raise _invalid(f"{where}.args", "an object")
    if tool == "place" and args.get("kind") not in PLACE_LOG_SAFE_KINDS:
        raise _invalid(f"{where}.args.kind", "place travels in the log only for object and product")
    if action.get("permission") != "edit":
        raise _invalid(f"{where}.permission", "log actions carry the edit permission")
    for key in ("session", "request_id"):
        if not is_hex32(str(action.get(key, "")).lower()):
            raise _invalid(f"{where}.{key}", "32 hex characters")


def parse_push(raw: bytes, author_id: str) -> tuple[str, list[ParsedOp]]:
    """Validate a push body (§6.2, §7): 413 past 200 operations, 422 otherwise."""
    if len(raw) > MAX_PUSH_BYTES:
        raise ContractError("too_large", 413, "A push carries at most 16 MiB.", {"limit": MAX_PUSH_BYTES})
    try:
        data = json.loads(raw, parse_constant=_no_constants)
    except (ValueError, UnicodeDecodeError):
        raise _invalid("body", "JSON without NaN or Infinity")
    if isinstance(data, dict) and isinstance(data.get("ops"), list) and len(data["ops"]) > MAX_OPS:
        raise ContractError(
            "too_large", 413, f"A push carries at most {MAX_OPS} operations.", {"limit": MAX_OPS, "ops": len(data["ops"])}
        )
    try:
        body = PushIn.model_validate(data)
    except ValidationError as exc:
        errors = [{**e, "loc": ("body", *e.get("loc", ()))} for e in exc.errors()]
        fields = validation_fields(errors)
        first = fields[0] if fields else {"field": "body", "message": "invalid"}
        raise ContractError("validation_failed", 422, f"{first['field']}: {first['message']}", {"fields": fields})
    replica_id = body.replica_id.lower()
    if not is_hex32(replica_id):
        raise _invalid("replica_id", "32 hex characters")
    if not body.ops:
        raise _invalid("ops", "at least one operation")
    out: list[ParsedOp] = []
    for i, op in enumerate(body.ops):
        where = f"ops[{i}]"
        op_id = op.op_id.lower()
        if not is_hex32(op_id):
            raise _invalid(f"{where}.op_id", "32 hex characters")
        author = op.author.lower()
        if not is_hex32(author):
            raise _invalid(f"{where}.author", "32 hex characters")
        if op.author_kind not in ("person", "agent"):
            raise _invalid(f"{where}.author_kind", "person or agent")
        if op.author_kind == "person" and author != author_id:
            raise _invalid(f"{where}.author", "a person's operations carry their own author_id (licence 5.7)")
        if op.replica_id is not None and op.replica_id.lower() != replica_id:
            raise _invalid(f"{where}.replica_id", "the push's replica_id")
        try:
            _parse_at(op.at)
        except ValueError as exc:
            raise _invalid(f"{where}.at", str(exc))
        if len(op.touched) > MAX_TOUCHED:
            raise _invalid(f"{where}.touched", f"at most {MAX_TOUCHED} ids")
        touched = [t.lower() if isinstance(t, str) else "" for t in op.touched]
        if not all(is_hex32(t) for t in touched):
            raise _invalid(f"{where}.touched", "32 hex characters each")
        if any(a >= b for a, b in zip(touched, touched[1:])):
            raise _invalid(f"{where}.touched", "sorted and unique")
        if op.kind not in KINDS:
            raise _invalid(f"{where}.kind", "delta or action (restore is appended by the server)")
        delta = None
        if op.kind == "delta":
            if op.delta is None or op.action is not None:
                raise _invalid(f"{where}.delta", "a delta operation carries delta and no action")
            if not op.delta_format or not op.delta_format.startswith("o5/") or not op.delta_format[3:].isdigit():
                raise _invalid(f"{where}.delta_format", "o5/<DocumentVersion>")
            if len(op.delta) > _B64_MAX_CHARS:
                raise _invalid(f"{where}.delta", "at most 4 MiB decoded", limit=MAX_DELTA_BYTES)
            try:
                delta = base64.b64decode(op.delta, validate=True)
            except (binascii.Error, ValueError):
                raise _invalid(f"{where}.delta", "base64")
            if len(delta) > MAX_DELTA_BYTES:
                raise _invalid(f"{where}.delta", "at most 4 MiB decoded", limit=MAX_DELTA_BYTES)
        else:
            if op.action is None or op.delta is not None:
                raise _invalid(f"{where}.action", "an action operation carries action and no delta")
            _check_action(op.action, f"{where}.action")
        out.append(
            ParsedOp(
                op_id=op_id,
                author=author,
                author_kind=op.author_kind,
                at=op.at,
                touched=touched,
                kind=op.kind,
                name=op.name,
                base_seq=op.base_seq,
                delta_format=op.delta_format if op.kind == "delta" else None,
                delta=delta,
                action=op.action,
            )
        )
    return replica_id, out


# --- wire form ------------------------------------------------------------------


def delta_key(project_id: str, server_seq: int) -> str:
    return f"projects/{project_id}/ops/{server_seq}.bin"


def _delta_bytes(row: ProjectOp) -> bytes | None:
    if row.delta is not None:
        return bytes(row.delta)
    if row.delta_key:
        with get_store().open(row.delta_key) as fh:
            return fh.read()
    return None


def op_json(row: ProjectOp, *, with_delta: bool = True) -> dict:
    delta = _delta_bytes(row) if with_delta and row.kind == "delta" else None
    return {
        "op_id": row.op_id,
        "server_seq": row.server_seq,
        "replica_id": row.replica_id,
        "author": row.author,
        "author_kind": row.author_kind,
        "at": row.at,
        "kind": row.kind,
        "name": row.name,
        "base_seq": row.base_seq,
        "touched": list(row.touched or []),
        "delta_format": row.delta_format,
        "delta": base64.b64encode(delta).decode("ascii") if delta is not None else None,
        "action": row.action,
        "restore": row.restore,
    }


def at_now() -> str:
    """The server's clock as an operation's `at` (RFC 3339, milliseconds)."""
    now = clock.now().astimezone(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# --- push ------------------------------------------------------------------------


def lock_project(db: Session, project_id: str) -> Project:
    """Begin the write transaction with the project row locked; returns it fresh."""
    db.execute(
        update(Project).where(Project.project_id == project_id).values(head_seq=Project.head_seq)
    )
    project = db.execute(
        select(Project).where(Project.project_id == project_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if project is None or project.deleted_at is not None:
        db.rollback()
        raise not_found()
    return project


def _chunks(items: list, n: int = _IN_CHUNK):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _conflicts(db: Session, project_id: str, op: ParsedOp, replica_id: str) -> list[int]:
    seqs: set[int] = set()
    for chunk in _chunks(op.touched):
        seqs.update(
            db.scalars(
                select(OpTouched.server_seq).where(
                    OpTouched.project_id == project_id,
                    OpTouched.entity_id.in_(chunk),
                    OpTouched.server_seq > op.base_seq,
                    OpTouched.replica_id != replica_id,
                )
            )
        )
    seqs.update(
        db.scalars(
            select(ProjectOp.server_seq).where(
                ProjectOp.project_id == project_id,
                ProjectOp.kind == "restore",
                ProjectOp.server_seq > op.base_seq,
            )
        )
    )
    return sorted(seqs)


def _winning(db: Session, project_id: str, seqs: list[int]) -> tuple[list[dict], bool]:
    rows = db.scalars(
        select(ProjectOp)
        .where(ProjectOp.project_id == project_id, ProjectOp.server_seq.in_(seqs[:MAX_WINNING]))
        .order_by(ProjectOp.server_seq)
    ).all()
    out, size, more = [], 0, len(seqs) > MAX_WINNING
    for row in rows:
        if out and size + row.delta_bytes > PULL_MAX_BYTES:
            more = True
            break
        out.append(op_json(row))
        size += row.delta_bytes
    return out, more


def append(db: Session, project: Project, op: ParsedOp, replica_id: str, *, restore: dict | None = None) -> ProjectOp:
    """Write one accepted operation at head + 1 (the caller holds the lock)."""
    seq = project.head_seq + 1
    row = ProjectOp(
        project_id=project.project_id,
        server_seq=seq,
        op_id=op.op_id,
        replica_id=replica_id,
        author=op.author,
        author_kind=op.author_kind,
        kind=op.kind,
        name=op.name,
        at=op.at,
        received_at=clock.now(),
        base_seq=op.base_seq,
        touched=op.touched,
        delta_format=op.delta_format,
        delta_bytes=len(op.delta) if op.delta is not None else 0,
        action=op.action,
        restore=restore,
    )
    if op.delta is not None and len(op.delta) > INLINE_DELTA_BYTES:
        key = delta_key(project.project_id, seq)
        get_store().put(key, op.delta, content_type="application/octet-stream")
        row.delta_key = key
        project.bytes += len(op.delta)
    else:
        row.delta = op.delta
    db.add(row)
    if op.touched:
        db.add_all(
            OpTouched(project_id=project.project_id, server_seq=seq, entity_id=t, replica_id=replica_id)
            for t in op.touched
        )
    project.head_seq = seq
    return row


def push(
    db: Session, project_id: str, replica_id: str, ops: list[ParsedOp], *, owner_id: int, bytes_cap: int | None
) -> tuple[dict, list[dict]]:
    """Apply §6.3 to a validated batch. Returns (5.6's answer, the accepted
    operations). `bytes_cap` is the owner's `cloud_bytes`, read before the lock
    (reading the plan may write)."""
    project = lock_project(db, project_id)
    try:
        if replica_id == project.server_replica_id:
            raise _invalid("replica_id", "this replica id is the server's own")
        head = project.head_seq
        for i, op in enumerate(ops):
            if op.base_seq > head:
                raise _invalid(f"ops[{i}].base_seq", f"at most head_seq ({head})", head_seq=head)
        stored: dict[str, int] = {}
        for chunk in _chunks(list({op.op_id for op in ops})):
            stored.update(
                db.execute(
                    select(ProjectOp.op_id, ProjectOp.server_seq).where(
                        ProjectOp.project_id == project_id, ProjectOp.op_id.in_(chunk)
                    )
                ).all()
            )
        offloaded = sum(
            len(op.delta) for op in ops if op.op_id not in stored and op.delta is not None and len(op.delta) > INLINE_DELTA_BYTES
        )
        if offloaded and bytes_cap is not None:
            used = quotas.bytes_used(db, owner_id)
            if used + offloaded > bytes_cap:
                raise quotas.exceeded("cloud_bytes", bytes_cap, used)

        results: list[dict] = []
        accepted: list[ProjectOp] = []
        stopped = False
        for op in ops:
            if stopped:
                results.append({"op_id": op.op_id, "status": "not_processed"})
                continue
            if op.op_id in stored:
                results.append({"op_id": op.op_id, "status": "duplicate", "server_seq": stored[op.op_id]})
                continue
            seqs = _conflicts(db, project_id, op, replica_id)
            if seqs:
                winning, more = _winning(db, project_id, seqs)
                results.append(
                    {"op_id": op.op_id, "status": "rejected", "reason": "conflict", "winning": winning, "more": more}
                )
                stopped = True
                continue
            row = append(db, project, op, replica_id)
            stored[op.op_id] = row.server_seq
            accepted.append(row)
            results.append({"op_id": op.op_id, "status": "accepted", "server_seq": row.server_seq})
        if accepted:
            project.updated_at = clock.now()
        answer = {"head_seq": project.head_seq, "results": results}
        wire = [op_json(r) for r in accepted]
        db.commit()
    except BaseException:
        db.rollback()
        raise
    return answer, wire


# --- pull --------------------------------------------------------------------------


def read_after(db: Session, project_id: str, after: int, limit: int) -> dict:
    project = db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise not_found()
    rows = db.scalars(
        select(ProjectOp)
        .where(ProjectOp.project_id == project_id, ProjectOp.server_seq > after)
        .order_by(ProjectOp.server_seq)
        .limit(limit + 1)
    ).all()
    more = len(rows) > limit
    out, size = [], 0
    for row in rows[:limit]:
        if out and size + row.delta_bytes > PULL_MAX_BYTES:
            more = True
            break
        out.append(op_json(row))
        size += row.delta_bytes
    return {"ops": out, "head_seq": project.head_seq, "more": more}


def check_pull_args(after: int, limit: int, wait_s: float) -> None:
    if after < 0:
        raise ContractError("validation_failed", 422, "after: 0 or more.", {"fields": [{"field": "after", "in": "query", "message": "0 or more"}]})
    if not 1 <= limit <= PULL_LIMIT_MAX:
        raise ContractError(
            "validation_failed", 422, f"limit: 1 to {PULL_LIMIT_MAX}.",
            {"fields": [{"field": "limit", "in": "query", "message": f"1 to {PULL_LIMIT_MAX}"}]},
        )
    if not 0 <= wait_s <= WAIT_MAX_S:
        raise ContractError(
            "validation_failed", 422, f"wait_s: 0 to {WAIT_MAX_S}.",
            {"fields": [{"field": "wait_s", "in": "query", "message": f"0 to {WAIT_MAX_S}"}]},
        )
