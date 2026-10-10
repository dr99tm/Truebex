"""The telemetry admin dashboard's API (admins only, `require_admin`).

GET   /admin/telemetry/summary?days=30              installs per day, versions, top events, timings, crash-free sessions
GET   /admin/telemetry/crashes                      crash groups (aliases left by symbolication hidden)
GET   /admin/telemetry/crashes/{signature}          a group with its latest reports and frames
PATCH /admin/telemetry/crashes/{signature}          status, title, fixed_in (the app's known issue), note
GET   /admin/telemetry/reports/{crash_id}/minidump  signed download URL (900 s); /log likewise
GET   /admin/telemetry/export.csv?tab=…&days=…      CSV of the overview, crashes or feedback tab
GET   /admin/feedback                               the inbox
PATCH /admin/feedback/{feedback_id}                 status
GET   /admin/feedback/{feedback_id}/screenshot      signed URL (900 s); /log likewise
POST  /admin/feedback/{feedback_id}/reply           e-mail the person (only when an address is stored)
GET   /admin/symbols, POST /admin/symbols           private Breakpad symbols per app version
"""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import require_admin
from ..mail import send_mail
from ..models import CrashGroup, CrashReport, Feedback, SymbolFile, TelemetryDaily, TelemetryEvent
from ..storage import get_store
from ..telemetry.jobs import percentile
from ..telemetry.service import iso
from ..telemetry.symbolicate import parse_sym

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
settings = get_settings()

Signature = Annotated[str, Path(pattern=r"^[0-9a-f]{16}$")]
Id32 = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
LINK_SECONDS = 900
SYMBOLS_MAX_BYTES = 90 * 1024 * 1024
CRASH_KINDS = ("crash", "hang", "gpu_lost")


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _window(days: int) -> tuple[date, datetime]:
    start = _today() - timedelta(days=days - 1)
    return start, datetime.combine(start, time.min, tzinfo=timezone.utc)


def _link(key: str | None, filename: str) -> dict:
    if not key or get_store().stat(key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such file.")
    url = get_store().signed_get_url(key, expires_in=LINK_SECONDS, filename=filename)
    expires = datetime.now(timezone.utc) + timedelta(seconds=LINK_SECONDS)
    return {"url": url, "expires_at": iso(expires)}


# --- overview ----------------------------------------------------------------------


@router.get("/telemetry/summary")
def summary(days: int = Query(30, ge=1, le=3650), db: Session = Depends(get_db)) -> dict:
    start, start_dt = _window(days)
    totals = db.execute(
        select(TelemetryDaily.day, TelemetryDaily.installs).where(
            TelemetryDaily.name == "*", TelemetryDaily.app_version == "*", TelemetryDaily.day >= start
        )
    ).all()
    per_day = {d: n for d, n in totals}
    installs_per_day = [
        {"day": (start + timedelta(days=i)).isoformat(), "count": per_day.get(start + timedelta(days=i), 0)}
        for i in range(days)
    ]

    versions: dict[str, set] = defaultdict(set)
    timings: dict[str, list[int]] = defaultdict(list)
    for name, version, install_id, props in db.execute(
        select(TelemetryEvent.name, TelemetryEvent.app_version, TelemetryEvent.install_id, TelemetryEvent.props)
        .where(TelemetryEvent.at >= start_dt)
    ):
        versions[version].add(install_id)
        ms = (props or {}).get("ms")
        if isinstance(ms, int) and not isinstance(ms, bool):
            timings[name].append(ms)

    top = db.execute(
        select(TelemetryDaily.name, func.sum(TelemetryDaily.events))
        .where(TelemetryDaily.name != "*", TelemetryDaily.app_version == "*", TelemetryDaily.day >= start)
        .group_by(TelemetryDaily.name)
        .order_by(func.sum(TelemetryDaily.events).desc())
        .limit(20)
    ).all()
    sessions = db.scalar(
        select(func.coalesce(func.sum(TelemetryDaily.events), 0)).where(
            TelemetryDaily.name == "app.start", TelemetryDaily.app_version == "*", TelemetryDaily.day >= start
        )
    )
    crashes = db.scalar(
        select(func.count()).select_from(CrashReport).where(
            CrashReport.kind.in_(CRASH_KINDS), CrashReport.received_at >= start_dt
        )
    )
    return {
        "days": days,
        "installs_per_day": installs_per_day,
        "versions": sorted(
            ({"version": v, "installs": len(ids)} for v, ids in versions.items()),
            key=lambda r: (-r["installs"], r["version"]),
        ),
        "top_events": [{"name": n, "events": int(c)} for n, c in top],
        "timings": [
            {"name": n, "p50_ms": percentile(v, 0.5), "p95_ms": percentile(v, 0.95), "samples": len(v)}
            for n, v in sorted(timings.items())
        ],
        "crash_free_sessions": round(max(0.0, 1 - crashes / sessions), 4) if sessions else None,
        "crashes": int(crashes or 0),
        "sessions": int(sessions or 0),
    }


# --- crashes ------------------------------------------------------------------------


def _group_out(g: CrashGroup) -> dict:
    return {
        "signature": g.signature,
        "title": g.title,
        "kind": g.kind,
        "status": g.status,
        "count": g.count,
        "first_seen": iso(g.first_seen),
        "last_seen": iso(g.last_seen),
        "versions": g.versions or [],
        "fixed_in": g.fixed_in,
        "note": g.note,
    }


def _report_out(r: CrashReport) -> dict:
    return {
        "crash_id": r.crash_id,
        "received_at": iso(r.received_at),
        "kind": r.kind,
        "app_version": r.app_version,
        "os": r.os,
        "gpu_driver": r.gpu_driver,
        "exception": r.exception,
        "frames": r.frames,
        "symbolicated": r.symbolicated,
        "has_minidump": r.minidump_key is not None,
        "has_log": r.log_key is not None,
    }


def _live_groups(db: Session):
    return db.scalars(
        select(CrashGroup)
        .where((CrashGroup.count > 0) | (CrashGroup.merged_into.is_(None)))
        .order_by(CrashGroup.last_seen.desc())
    ).all()


@router.get("/telemetry/crashes")
def crash_groups(db: Session = Depends(get_db)) -> list[dict]:
    return [_group_out(g) for g in _live_groups(db)]


@router.get("/telemetry/crashes/{signature}")
def crash_group(signature: Signature, db: Session = Depends(get_db)) -> dict:
    group = db.get(CrashGroup, signature)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such crash group.")
    reports = db.scalars(
        select(CrashReport)
        .where(CrashReport.signature == signature)
        .order_by(CrashReport.received_at.desc())
        .limit(50)
    ).all()
    return {**_group_out(group), "reports": [_report_out(r) for r in reports]}


class GroupPatch(BaseModel):
    status: Literal["new", "investigating", "fixed", "ignored"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    fixed_in: str | None = Field(default=None, max_length=32, pattern=r"^[0-9A-Za-z.+\-]*$")
    note: str | None = Field(default=None, max_length=2000)


@router.patch("/telemetry/crashes/{signature}")
def update_group(signature: Signature, body: GroupPatch, db: Session = Depends(get_db)) -> dict:
    group = db.get(CrashGroup, signature)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such crash group.")
    for name, value in body.model_dump(exclude_unset=True).items():
        if name == "fixed_in" and value == "":
            value = None
        setattr(group, name, value)
    db.commit()
    return _group_out(group)


@router.get("/telemetry/reports/{crash_id}/minidump")
def minidump_link(crash_id: Id32, db: Session = Depends(get_db)) -> dict:
    report = db.get(CrashReport, crash_id)
    return _link(report.minidump_key if report else None, f"{crash_id}.dmp")


@router.get("/telemetry/reports/{crash_id}/log")
def crash_log_link(crash_id: Id32, db: Session = Depends(get_db)) -> dict:
    report = db.get(CrashReport, crash_id)
    return _link(report.log_key if report else None, f"{crash_id}.log.txt")


# --- feedback ------------------------------------------------------------------------


def _feedback_out(f: Feedback) -> dict:
    return {
        "feedback_id": f.feedback_id,
        "received_at": iso(f.received_at),
        "kind": f.kind,
        "text": f.text,
        "reply": f.reply,
        "email": f.email,
        "app_version": f.app_version,
        "os": f.os,
        "status": f.status,
        "replied_at": iso(f.replied_at),
        "has_screenshot": f.screenshot_key is not None,
        "has_log": f.log_key is not None,
    }


def _feedback(db: Session, feedback_id: str) -> Feedback:
    fb = db.get(Feedback, feedback_id)
    if fb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such feedback.")
    return fb


@router.get("/feedback")
def inbox(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Feedback).order_by(Feedback.received_at.desc()).limit(500)).all()
    return [_feedback_out(f) for f in rows]


class FeedbackPatch(BaseModel):
    status: Literal["new", "replied", "closed"]


@router.patch("/feedback/{feedback_id}")
def update_feedback(feedback_id: Id32, body: FeedbackPatch, db: Session = Depends(get_db)) -> dict:
    fb = _feedback(db, feedback_id)
    fb.status = body.status
    db.commit()
    return _feedback_out(fb)


@router.get("/feedback/{feedback_id}/screenshot")
def screenshot_link(feedback_id: Id32, db: Session = Depends(get_db)) -> dict:
    return _link(_feedback(db, feedback_id).screenshot_key, f"{feedback_id}.png")


@router.get("/feedback/{feedback_id}/log")
def feedback_log_link(feedback_id: Id32, db: Session = Depends(get_db)) -> dict:
    return _link(_feedback(db, feedback_id).log_key, f"{feedback_id}.log.txt")


class Reply(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@router.post("/feedback/{feedback_id}/reply")
def reply(feedback_id: Id32, body: Reply, db: Session = Depends(get_db)) -> dict:
    fb = _feedback(db, feedback_id)
    if not fb.email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This person did not ask for a reply, so no address is stored.",
        )
    send_mail(
        fb.email,
        "feedback_reply",
        {"reply": body.text, "original": fb.text, "kind": fb.kind},
        reply_to=settings.support_email,
    )
    fb.status = "replied"
    fb.replied_at = datetime.now(timezone.utc)
    db.commit()
    return _feedback_out(fb)


# --- CSV export ------------------------------------------------------------------------


@router.get("/telemetry/export.csv")
def export_csv(
    tab: Literal["overview", "crashes", "feedback"] = "overview",
    days: int = Query(90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> Response:
    start, start_dt = _window(days)
    out = io.StringIO()
    w = csv.writer(out)
    if tab == "overview":
        w.writerow(["day", "event", "app_version", "events", "installs", "p50_ms", "p95_ms"])
        for r in db.scalars(
            select(TelemetryDaily)
            .where(TelemetryDaily.day >= start)
            .order_by(TelemetryDaily.day, TelemetryDaily.name, TelemetryDaily.app_version)
        ):
            w.writerow([r.day.isoformat(), r.name, r.app_version, r.events, r.installs, r.p50_ms, r.p95_ms])
    elif tab == "crashes":
        w.writerow(["signature", "title", "kind", "status", "fixed_in", "count", "first_seen", "last_seen", "versions"])
        for g in _live_groups(db):
            w.writerow([g.signature, g.title, g.kind, g.status, g.fixed_in or "", g.count,
                        iso(g.first_seen), iso(g.last_seen), " ".join(g.versions or [])])
    else:
        # No e-mail addresses in exports: replies go through the dashboard.
        w.writerow(["feedback_id", "received_at", "kind", "app_version", "status", "reply", "text"])
        for f in db.scalars(
            select(Feedback).where(Feedback.received_at >= start_dt).order_by(Feedback.received_at)
        ):
            w.writerow([f.feedback_id, iso(f.received_at), f.kind, f.app_version, f.status, f.reply, f.text])
    name = f"truebex-telemetry-{tab}-{_today().isoformat()}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --- symbols ---------------------------------------------------------------------------


def _symbol_out(s: SymbolFile) -> dict:
    return {
        "module": s.module,
        "debug_id": s.debug_id,
        "code_file": s.code_file,
        "version": s.version,
        "key": s.key,
        "uploaded_at": iso(s.uploaded_at),
    }


def store_symbols(db: Session, data: bytes, version: str) -> SymbolFile:
    """Parse a .sym file, store it in the Breakpad layout and record it
    (also used by server/scripts/upload_symbols.py on the host)."""
    table = parse_sym(data.decode("utf-8", "replace"))
    stem = table.module[:-4] if table.module.lower().endswith(".pdb") else table.module
    key = f"symbols/{table.module}/{table.debug_id}/{stem}.sym"
    get_store().put(key, data, content_type="text/plain; charset=utf-8")
    row = db.scalar(
        select(SymbolFile).where(SymbolFile.module == table.module, SymbolFile.debug_id == table.debug_id)
    )
    if row is None:
        row = SymbolFile(module=table.module, debug_id=table.debug_id)
        db.add(row)
    row.code_file = table.code_file
    row.version = version
    row.key = key
    row.uploaded_at = datetime.now(timezone.utc)
    db.commit()
    return row


@router.get("/symbols")
def list_symbols(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(SymbolFile).order_by(SymbolFile.uploaded_at.desc()).limit(500)).all()
    return [_symbol_out(s) for s in rows]


@router.post("/symbols", status_code=status.HTTP_201_CREATED)
async def upload_symbols(
    version: Annotated[str, Form(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+\-]+$")],
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
) -> dict:
    data = await file.read(SYMBOLS_MAX_BYTES + 1)
    if len(data) > SYMBOLS_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Symbol file too large.")
    try:
        row = store_symbols(db, data, version)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _symbol_out(row)
