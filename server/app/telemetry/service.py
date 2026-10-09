"""Telemetry ingestion: the platform side of contracts/telemetry.md §5.

Every function here takes what the router read off the wire and either
returns the contract's 202 body or raises a ContractError carrying the §7
code. Nothing stored here carries an IP address or an account id; the one
personal field is feedback.email (5.4 with `reply` and a device token).
"""

import hashlib
import json
import logging
import platform
import re
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import __version__, ratelimit
from ..config import get_settings
from ..contract_http import ContractError, validation_fields
from ..database import SessionLocal
from ..models import (
    CrashGroup,
    CrashReport,
    Feedback,
    TelemetryBatch,
    TelemetryDeletion,
    TelemetryEvent,
)
from ..storage import get_store
from . import scanner

log = logging.getLogger("truebex.telemetry")
settings = get_settings()

CONFIG_PATH = Path(__file__).parent / "config.json"

MiB = 1024 * 1024
EVENTS_MAX_BYTES = 256 * 1024
EVENTS_MAX = 500
CRASH_MAX_BYTES = 21 * MiB
MINIDUMP_MAX_BYTES = 20 * MiB
LOG_MAX_BYTES = 256 * 1024
FEEDBACK_MAX_BYTES = 9 * MiB
SCREENSHOT_MAX_BYTES = 8 * MiB
DELETION_DAYS = 30
# 60 requests an hour per installation (and per address, in the router).
PER_HOUR = 60

Hex32 = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
Version = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+\-]+$")]


# --- wire shapes (§5, §6.2) ----------------------------------------------------


class _Wire(BaseModel):
    # Readers ignore keys they do not know (MINOR versions are additive).
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AppInfo(_Wire):
    version: Version
    channel: str = Field(default="stable", max_length=16)
    build: str = Field(default="shipping", max_length=16)


class Hardware(_Wire):
    gpu: str | None = Field(default=None, max_length=128)
    vram_gb: int | None = Field(default=None, ge=0, le=4096)
    ram_gb: int | None = Field(default=None, ge=0, le=65536)
    cpu_threads: int | None = Field(default=None, ge=0, le=4096)
    displays: int | None = Field(default=None, ge=0, le=64)


class Event(_Wire):
    seq: int = Field(ge=0)
    at: datetime
    name: str = Field(min_length=1, max_length=64)
    props: dict[str, Any] = Field(default_factory=dict)


class EventBatch(_Wire):
    schema_: Literal["truebex-telemetry/1"] = Field(alias="schema")
    install_id: Hex32
    session_id: Hex32
    batch_id: Hex32
    app: AppInfo
    os: str = Field(max_length=64)
    locale: str | None = Field(default=None, max_length=35)
    plan: str | None = Field(default=None, max_length=32)
    hw: Hardware | None = None
    events: list[Event] = Field(max_length=EVENTS_MAX)


class CrashException(_Wire):
    code: str | None = Field(default=None, max_length=32)
    module: str | None = Field(default=None, max_length=200)
    offset: str | None = Field(default=None, max_length=32)


class CrashReportIn(_Wire):
    schema_: Literal["truebex-crash/1"] = Field(alias="schema")
    crash_id: Hex32
    install_id: Hex32
    app: AppInfo
    os: str = Field(max_length=64)
    hw: Hardware | None = None
    at: datetime | None = None
    kind: Literal["crash", "hang", "gpu_lost", "ensure"]
    exception: CrashException | None = None
    callstack: list[Annotated[str, Field(max_length=512)]] = Field(default_factory=list, max_length=64)
    uptime_s: int | None = Field(default=None, ge=0)
    gpu_driver: str | None = Field(default=None, max_length=64)


class FeedbackIn(_Wire):
    schema_: Literal["truebex-feedback/1"] = Field(alias="schema")
    feedback_id: Hex32
    install_id: Hex32
    kind: Literal["bug", "idea", "question", "praise"]
    text: str = Field(min_length=1, max_length=5000)
    reply: bool = False
    app: AppInfo
    os: str = Field(max_length=64)


class DeleteIn(_Wire):
    install_secret: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


# --- helpers ---------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def iso(dt: datetime | None) -> str | None:
    """RFC 3339 UTC with Z, as every contract endpoint emits times."""
    dt = _aware(dt)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


@lru_cache
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def public_config() -> dict:
    """5.1: the allow-list, sampling and the kill switch."""
    if not settings.telemetry_ingestion_enabled:
        raise unavailable()
    cfg = dict(load_config())
    cfg["enabled"] = bool(settings.telemetry_events_enabled)
    return cfg


def unavailable() -> ContractError:
    return ContractError("unavailable", 503, "Telemetry is switched off for now.")


def too_large(what: str) -> ContractError:
    return ContractError("too_large", 413, f"The {what} is larger than the contract allows.")


def invalid(detail: str, fields: list[dict] | None = None) -> ContractError:
    return ContractError("validation_failed", 422, detail, {"fields": fields or []})


def privacy(v: scanner.Violation) -> ContractError:
    return ContractError(
        "privacy_violation", 422, v.message, {"field": v.field, "reason": v.reason}
    )


def _parse_json(raw: bytes | str, part: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise invalid(f"The {part} is not valid JSON.", [{"field": part, "message": "invalid JSON"}])
    if not isinstance(data, dict):
        raise invalid(f"The {part} must be a JSON object.", [{"field": part, "message": "not an object"}])
    return data


def _validate(model: type[BaseModel], data: dict):
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        fields = validation_fields(exc.errors())
        raise invalid(fields[0]["message"] if fields else "Invalid body.", fields)


def _limit_install(install_id: Any) -> None:
    if isinstance(install_id, str) and re.fullmatch(r"[0-9a-f]{32}", install_id):
        ratelimit.check(f"telemetry:install:{install_id}", per_minute=PER_HOUR / 60, burst=PER_HOUR)


def install_id_from_secret(secret: str) -> str:
    """§4: the first 32 hex of SHA-256 over the secret's 32 raw bytes."""
    return hashlib.sha256(bytes.fromhex(secret)).hexdigest()[:32]


# --- crash identity (§6.3) -------------------------------------------------------

_FRAME_RE = re.compile(
    r"^(?P<module>[^!+]+?)(?:!(?P<function>.+?))?(?:\+(?P<offset>0x[0-9A-Fa-f]+))?$"
)


def normalise_frame(frame: str) -> str:
    """`Module!Function` for a named frame, `Module!0xOFFSET` for a raw one."""
    m = _FRAME_RE.match(frame.strip())
    if not m:
        return frame.strip()
    module, function, offset = m.group("module"), m.group("function"), m.group("offset")
    if function:
        function = re.sub(r":\d+$", "", function.split("(", 1)[0]).strip()
        return f"{module}!{function}"
    if offset:
        return f"{module}!{hex(int(offset, 16))}"
    return module


def crash_signature(frames: list[str], exception: dict | None = None) -> str:
    """The first 16 hex of SHA-256 over the top five `module!function` frames,
    joined by newlines."""
    top = [normalise_frame(f) for f in frames[:5] if f and f.strip()]
    if not top and exception:
        top = [f"{exception.get('module') or 'unknown'}!{exception.get('offset') or exception.get('code')}"]
    return hashlib.sha256("\n".join(top).encode("utf-8")).hexdigest()[:16]


def resolve_group(db: Session, signature: str) -> str:
    """Follow aliases left by symbolication to the group a signature lives in."""
    seen = set()
    group = db.get(CrashGroup, signature)
    while group is not None and group.merged_into and group.merged_into not in seen:
        seen.add(signature)
        signature = group.merged_into
        group = db.get(CrashGroup, signature)
    return signature


def add_to_group(db: Session, report: CrashReport, title: str) -> CrashGroup:
    now = report.received_at
    group = db.get(CrashGroup, report.signature)
    if group is None:
        group = CrashGroup(
            signature=report.signature,
            first_seen=now,
            last_seen=now,
            count=0,
            versions=[],
            status="new",
            title=title[:300],
            kind=report.kind,
        )
        db.add(group)
    group.count = (group.count or 0) + 1
    group.last_seen = now
    if report.app_version not in (group.versions or []):
        group.versions = sorted([*(group.versions or []), report.app_version])
    return group


def known_issue(group: CrashGroup | None) -> dict | None:
    if group is None or not group.fixed_in:
        return None
    return {"title": group.title, "fixed_in": group.fixed_in}


# --- 5.2 events ---------------------------------------------------------------------


def ingest_events(db: Session, raw: bytes) -> dict:
    if not settings.telemetry_ingestion_enabled:
        raise unavailable()
    if len(raw) > EVENTS_MAX_BYTES:
        raise too_large("event batch")
    data = _parse_json(raw, "body")
    _limit_install(data.get("install_id"))
    if isinstance(data.get("events"), list) and len(data["events"]) > EVENTS_MAX:
        raise too_large("event batch")
    hit = scanner.scan_events(data)
    if hit:
        raise privacy(hit)
    batch: EventBatch = _validate(EventBatch, data)

    seen = db.get(TelemetryBatch, batch.batch_id)
    if seen is not None:
        return {"accepted": seen.accepted, "dropped": seen.dropped}
    if not settings.telemetry_events_enabled:
        return {"accepted": 0, "dropped": len(batch.events)}

    allowed: dict[str, list[str]] = load_config()["allowed"]
    now = _now()
    accepted = dropped = 0
    rows = []
    for ev in batch.events:
        keys = allowed.get(ev.name)
        if keys is None:
            dropped += 1
            continue
        props = {k: v for k, v in ev.props.items() if k in keys}
        dropped += len(ev.props) - len(props)
        accepted += 1
        rows.append(
            TelemetryEvent(
                received_at=now,
                install_id=batch.install_id,
                session_id=batch.session_id,
                batch_id=batch.batch_id,
                app_version=batch.app.version,
                channel=batch.app.channel,
                build=batch.app.build,
                os=batch.os,
                locale=batch.locale,
                plan=batch.plan,
                hw=batch.hw.model_dump(exclude_none=True) if batch.hw else None,
                seq=ev.seq,
                at=_aware(ev.at),
                name=ev.name,
                props=props,
            )
        )
    db.add(
        TelemetryBatch(
            batch_id=batch.batch_id,
            install_id=batch.install_id,
            received_at=now,
            accepted=accepted,
            dropped=dropped,
        )
    )
    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError:  # the same batch arrived twice at once
        db.rollback()
        seen = db.get(TelemetryBatch, batch.batch_id)
        return {"accepted": seen.accepted, "dropped": seen.dropped}
    return {"accepted": accepted, "dropped": dropped}


# --- 5.3 crash reports ------------------------------------------------------------


def _decode_log(raw: bytes | None, field: str = "log") -> str | None:
    if raw is None:
        return None
    if len(raw) > LOG_MAX_BYTES:
        raise too_large("log")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise invalid("The log is not UTF-8 text.", [{"field": field, "message": "not UTF-8"}])
    hit = scanner.scan_log(text, field)
    if hit:
        raise privacy(hit)
    return text


def ingest_crash(db: Session, report_raw: bytes | None, minidump: bytes | None, log_raw: bytes | None) -> dict:
    if not settings.telemetry_ingestion_enabled:
        raise unavailable()
    if report_raw is None:
        raise invalid("The report part is missing.", [{"field": "report", "message": "missing part"}])
    if minidump is not None and len(minidump) > MINIDUMP_MAX_BYTES:
        raise too_large("minidump")
    data = _parse_json(report_raw, "report")
    _limit_install(data.get("install_id"))
    hit = scanner.scan_crash(data)
    if hit:
        raise privacy(hit)
    log_text = _decode_log(log_raw)
    report: CrashReportIn = _validate(CrashReportIn, data)

    existing = db.get(CrashReport, report.crash_id)
    if existing is not None:
        group = db.get(CrashGroup, resolve_group(db, existing.signature))
        return {
            "crash_id": existing.crash_id,
            "signature": group.signature if group else existing.signature,
            "duplicate": True,
            "known_issue": known_issue(group),
        }

    now = _now()
    exception = report.exception.model_dump(exclude_none=True) if report.exception else None
    signature = resolve_group(db, crash_signature(report.callstack, exception))
    store = get_store()
    folder = f"telemetry/crashes/{now:%Y}/{now:%m}/{report.crash_id}"
    minidump_key = log_key = None
    if minidump:
        minidump_key = f"{folder}/minidump.dmp"
        store.put(minidump_key, minidump, content_type="application/octet-stream")
    if log_text is not None:
        log_key = f"{folder}/log.txt"
        store.put(log_key, log_text.encode("utf-8"), content_type="text/plain; charset=utf-8")

    row = CrashReport(
        crash_id=report.crash_id,
        received_at=now,
        kind=report.kind,
        install_id=report.install_id,
        app_version=report.app.version,
        os=report.os,
        hw=report.hw.model_dump(exclude_none=True) if report.hw else None,
        at=_aware(report.at),
        exception=exception,
        signature=signature,
        frames=list(report.callstack),
        minidump_key=minidump_key,
        log_key=log_key,
        symbolicated=False,
        gpu_driver=report.gpu_driver,
        uptime_s=report.uptime_s,
    )
    db.add(row)
    title = normalise_frame(report.callstack[0]) if report.callstack else f"{report.kind} in {(exception or {}).get('module', 'unknown')}"
    group = add_to_group(db, row, title)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return ingest_crash(db, report_raw, None, None)  # answered as a duplicate
    return {
        "crash_id": row.crash_id,
        "signature": signature,
        "duplicate": False,
        "known_issue": known_issue(group),
    }


# --- 5.4 feedback ------------------------------------------------------------------


def ingest_feedback(
    db: Session,
    feedback_raw: bytes | None,
    screenshot: bytes | None,
    log_raw: bytes | None,
    reply_email: Any,
) -> dict:
    """`reply_email` is a callable returning the account's e-mail for the
    request's device token (raising 401 for a revoked one), called only when
    the person asked for a reply."""
    if not settings.telemetry_ingestion_enabled:
        raise unavailable()
    if feedback_raw is None:
        raise invalid("The feedback part is missing.", [{"field": "feedback", "message": "missing part"}])
    if screenshot is not None:
        if len(screenshot) > SCREENSHOT_MAX_BYTES:
            raise too_large("screenshot")
        if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
            raise invalid("The screenshot must be a PNG image.", [{"field": "screenshot", "message": "not a PNG"}])
    data = _parse_json(feedback_raw, "feedback")
    _limit_install(data.get("install_id"))
    hit = scanner.scan_feedback(data)
    if hit:
        raise privacy(hit)
    log_text = _decode_log(log_raw)
    fb: FeedbackIn = _validate(FeedbackIn, data)

    existing = db.get(Feedback, fb.feedback_id)
    if existing is not None:
        return {"feedback_id": existing.feedback_id, "received_at": iso(existing.received_at), "duplicate": True}

    email = reply_email() if fb.reply else None
    now = _now()
    store = get_store()
    folder = f"telemetry/feedback/{fb.feedback_id}"
    screenshot_key = log_key = None
    if screenshot:
        screenshot_key = f"{folder}/screenshot.png"
        store.put(screenshot_key, screenshot, content_type="image/png")
    if log_text is not None:
        log_key = f"{folder}/log.txt"
        store.put(log_key, log_text.encode("utf-8"), content_type="text/plain; charset=utf-8")
    db.add(
        Feedback(
            feedback_id=fb.feedback_id,
            received_at=now,
            install_id=fb.install_id,
            kind=fb.kind,
            text=fb.text,
            reply=fb.reply,
            email=email,
            screenshot_key=screenshot_key,
            log_key=log_key,
            app_version=fb.app.version,
            os=fb.os,
            status="new",
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(Feedback, fb.feedback_id)
        return {"feedback_id": existing.feedback_id, "received_at": iso(existing.received_at), "duplicate": True}
    return {"feedback_id": fb.feedback_id, "received_at": iso(now), "duplicate": False}


# --- 5.5 deletion -------------------------------------------------------------------


def request_deletion(db: Session, raw: bytes) -> dict:
    """Always 202, known installation or not: the answer reveals nothing."""
    data = _parse_json(raw, "body")
    body: DeleteIn = _validate(DeleteIn, data)
    install_id = install_id_from_secret(body.install_secret)
    _limit_install(install_id)
    pending = db.scalars(
        select(TelemetryDeletion).where(
            TelemetryDeletion.install_id == install_id, TelemetryDeletion.completed_at.is_(None)
        )
    ).first()
    if pending is None:
        pending = TelemetryDeletion(install_id=install_id, requested_at=_now())
        db.add(pending)
        db.commit()
    return {
        "install_id": install_id,
        "complete_by": iso(_aware(pending.requested_at) + timedelta(days=DELETION_DAYS)),
    }


# --- API exceptions into the same crash store (kind "server") -----------------------


_SERVER_ROOT = Path(__file__).resolve().parents[2]


def _module_of(filename: str) -> str:
    """A dotted module name for a traceback file: `app.routers.auth`,
    `starlette.routing`; never a full path."""
    path = Path(filename)
    try:
        return ".".join(path.resolve().relative_to(_SERVER_ROOT).with_suffix("").parts)
    except (ValueError, OSError):
        pass
    parts = path.with_suffix("").parts
    if "site-packages" in parts:
        i = len(parts) - 1 - parts[::-1].index("site-packages")
        return ".".join(parts[i + 1 :])
    return path.stem


def record_server_exception(exc: BaseException, route: str | None = None) -> str | None:
    """Store an unhandled API exception as a crash report; returns its id."""
    try:
        tb = traceback.extract_tb(exc.__traceback__)
        frames = [f"{_module_of(fs.filename)}!{fs.name}:{fs.lineno}" for fs in reversed(tb)][:64]
        name = type(exc).__name__
        if not frames:
            frames = [f"{name}!raise"]
        exception = {"type": name, "route": route}
        crash_id = uuid.uuid4().hex
        with SessionLocal() as db:
            signature = resolve_group(db, crash_signature(frames))
            row = CrashReport(
                crash_id=crash_id,
                received_at=_now(),
                kind="server",
                install_id=None,
                app_version=__version__,
                os=platform.platform()[:64],
                exception=exception,
                signature=signature,
                frames=frames,
                symbolicated=True,
            )
            db.add(row)
            innermost = normalise_frame(frames[0]).split("!", 1)[-1]
            add_to_group(db, row, f"{name} in {innermost}" + (f" ({route})" if route else ""))
            db.commit()
        return crash_id
    except Exception:  # noqa: BLE001 - recording must never mask the original error
        log.exception("could not record a server exception")
        return None
