"""Supplier feeds (contract marketplace-api §5.11–5.13, §6.4) on PF7's
importer engine, and their runs.

* Supplier systems use an API key of a member with the catalogue role
  (contract §4). A key made in the portal carries `supplier_id` and feeds
  that supplier only; an older key without it is accepted only when its
  owner is a catalogue member of exactly one supplier. Otherwise 403
  `not_supplier`.
* 5.11 checks the header (422 `feed_invalid`) and the size (413
  `too_large`), stores the file and queues a run; `market.feeds.run` runs
  queued feeds, one run per supplier at a time; a run with rejected rows
  e-mails the supplier.
* 5.12 registers an https URL that `market.feeds.pull` fetches every day at
  02:00 UTC (ETag, 50 MB, 60 s); private, loopback and link-local addresses
  are refused after DNS resolution (the request-forgery guard), at
  registration and on every fetch and redirect. A failed pull e-mails the
  supplier.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..market import importer, media
from ..market.catalogue import CATALOGUE_ROLES, member_role
from ..market.common import aware, now, rfc3339
from ..market.models import FeedRun, Supplier
from ..models import ApiKey, User
from ..security import API_KEY_PREFIX, hash_api_key
from . import notify
from .common import memberships
from .models import FeedSource

log = logging.getLogger("truebex.supplier")

PULL_TIMEOUT_S = 60.0
MAX_REDIRECTS = 3
# Runs left `running` this long were cut off (the server stopped): failed.
RUN_STALE_AFTER = timedelta(hours=2)
# DNS check for remote fetches (tests swap it).
public_host = media._public_address


@dataclass
class FeedCaller:
    user: User
    key: ApiKey
    supplier: Supplier


def _unauthenticated(detail: str) -> ContractError:
    return ContractError("unauthenticated", 401, detail, headers={"WWW-Authenticate": "Bearer"})


def caller_for_key(db: Session, raw: str | None) -> FeedCaller:
    if not raw or not raw.startswith(API_KEY_PREFIX):
        raise _unauthenticated("Send your supplier API key as Authorization: Bearer tbx_live_… or X-API-Key.")
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw)))
    if key is None or key.revoked_at is not None:
        raise _unauthenticated("Invalid or revoked API key.")
    user = db.get(User, key.user_id)
    if user is None:
        raise _unauthenticated("Invalid or revoked API key.")
    if key.supplier_id:
        supplier = db.get(Supplier, key.supplier_id)
        role = member_role(db, user, key.supplier_id) if supplier else None
        if supplier is None or role not in CATALOGUE_ROLES or supplier.status == "suspended":
            raise ContractError(
                "not_supplier", 403, "This key's owner is no longer a catalogue member of its supplier."
            )
    else:
        candidates = [s for s, role in memberships(db, user) if role in CATALOGUE_ROLES and s.status != "suspended"]
        if len(candidates) != 1:
            detail = (
                "This key's owner is a catalogue member of several suppliers: create a supplier key in the "
                "supplier portal (Team → Supplier keys)."
                if candidates
                else "This key's owner is not a catalogue member of a supplier."
            )
            raise ContractError("not_supplier", 403, detail)
        supplier = candidates[0]
    key.last_used_at = now()
    db.add(key)
    db.commit()
    return FeedCaller(user=user, key=key, supplier=supplier)


def get_run(db: Session, supplier: Supplier, feed_id: str) -> FeedRun:
    run = db.get(FeedRun, feed_id) if isinstance(feed_id, str) else None
    if run is None or run.supplier_id != supplier.supplier_id:
        raise ContractError("not_found", 404, "That feed run was not found.")
    return run


def upload(db: Session, supplier: Supplier, user: User, data: bytes, fmt: str, mode: str, source: str = "upload") -> FeedRun:
    try:
        return importer.queue(db, supplier, data, fmt, mode, source=source, by_user_id=user.id)
    except importer.FeedTooLarge as exc:
        raise ContractError("too_large", 413, str(exc), {"max_bytes": importer.MAX_BYTES, "max_rows": importer.MAX_ROWS})
    except importer.FeedInvalid as exc:
        raise ContractError("feed_invalid", 422, str(exc))


# --- Running queued feeds -----------------------------------------------------------------

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock(supplier_id: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(supplier_id, threading.Lock())


def run_queued(db: Session, *, supplier_id: str | None = None, fetcher=None, limit: int = 20) -> list[FeedRun]:
    """Run queued feeds, oldest first, one run per supplier at a time."""
    at = now()
    for stale in db.scalars(select(FeedRun).where(FeedRun.state == "running")):
        if stale.started_at and aware(stale.started_at) < at - RUN_STALE_AFTER:
            stale.state, stale.detail, stale.finished_at = "failed", "interrupted: the server stopped during the run", at
            db.add(stale)
    db.commit()
    stmt = select(FeedRun.feed_id, FeedRun.supplier_id).where(FeedRun.state == "queued").order_by(FeedRun.created_at)
    if supplier_id:
        stmt = stmt.where(FeedRun.supplier_id == supplier_id)
    done: list[FeedRun] = []
    for feed_id, sid in db.execute(stmt.limit(limit)).all():
        lock = _lock(sid)
        if not lock.acquire(blocking=False):
            continue  # this supplier has a run going: the next tick takes it
        try:
            busy = db.scalar(select(FeedRun.feed_id).where(FeedRun.supplier_id == sid, FeedRun.state == "running"))
            if busy:
                continue
            run = importer.execute(db, feed_id, fetcher=fetcher)
        finally:
            lock.release()
        if run is None:
            continue
        done.append(run)
        if run.state == "done" and run.rejected and run.source in ("upload", "pull", "portal"):
            supplier = db.get(Supplier, run.supplier_id)
            if supplier is not None:
                notify.feed_rejected(db, supplier, importer.report_json(run))
    return done


# --- The registered URL (5.12) and the daily pull --------------------------------------------


def next_pull_after(at: datetime) -> datetime:
    hour = get_settings().feed_pull_hour_utc
    slot = aware(at).replace(hour=hour, minute=0, second=0, microsecond=0)
    return slot if slot > aware(at) else slot + timedelta(days=1)


def check_url(url: str) -> str:
    """https only, a public host after DNS resolution; 422 otherwise."""
    if not media.is_https_url(url):
        raise ContractError(
            "validation_failed", 422, "url: an https address",
            {"fields": [{"field": "url", "in": "body", "message": "an https address"}]},
        )  # fmt: skip
    host = urlsplit(url).hostname or ""
    if not public_host(host):
        raise ContractError(
            "validation_failed", 422, "url: the host must be a public internet address",
            {"fields": [{"field": "url", "in": "body", "message": "private, loopback and unknown hosts are refused"}]},
        )  # fmt: skip
    return url


def source_of(db: Session, supplier: Supplier) -> FeedSource | None:
    return db.get(FeedSource, supplier.supplier_id)


def source_json(src: FeedSource | None) -> dict | None:
    if src is None:
        return None
    return {
        "url": src.url,
        "format": src.format,
        "mode": src.mode,
        "next_pull_at": rfc3339(src.next_pull_at),
        "last_pull_at": rfc3339(src.last_pull_at),
        "last_status": src.last_status,
        "last_error": src.last_error,
        "last_feed_id": src.last_feed_id,
    }


def set_source(db: Session, supplier: Supplier, user: User, url: str, fmt: str, mode: str) -> FeedSource:
    check_url(url)
    src = source_of(db, supplier) or FeedSource(supplier_id=supplier.supplier_id)
    if src.url != url:
        src.etag = None
    src.url, src.format, src.mode, src.created_by = url, fmt, mode, user.id
    src.next_pull_at = next_pull_after(now())
    db.add(src)
    db.commit()
    return src


def remove_source(db: Session, supplier: Supplier) -> None:
    src = source_of(db, supplier)
    if src is not None:
        db.delete(src)
        db.commit()


class PullError(Exception):
    pass


class HttpFeedFetcher:
    """GET with If-None-Match: (status, body, etag); https, public hosts,
    50 MB and 60 s; redirects followed (≤ 3) through the same checks."""

    def get(self, url: str, etag: str | None) -> tuple[int, bytes, str | None]:
        import httpx

        for _ in range(MAX_REDIRECTS + 1):
            if not media.is_https_url(url):
                raise PullError("only https addresses are read")
            if not public_host(urlsplit(url).hostname or ""):
                raise PullError("the host is not a public internet address")
            headers = {"User-Agent": "Truebex-Feeds/1"}
            if etag:
                headers["If-None-Match"] = etag
            try:
                with httpx.Client(timeout=PULL_TIMEOUT_S, follow_redirects=False) as client:
                    with client.stream("GET", url, headers=headers) as res:
                        if res.status_code in (301, 302, 303, 307, 308) and res.headers.get("location"):
                            url = urljoin(url, res.headers["location"])
                            continue
                        if res.status_code == 304:
                            return 304, b"", etag
                        if res.status_code != 200:
                            raise PullError(f"the server answered HTTP {res.status_code}")
                        body = bytearray()
                        for chunk in res.iter_bytes():
                            body.extend(chunk)
                            if len(body) > importer.MAX_BYTES:
                                raise PullError("the file is larger than 50 MB")
                        return 200, bytes(body), res.headers.get("etag")
            except httpx.HTTPError as exc:
                raise PullError(f"the address could not be read ({type(exc).__name__})") from exc
        raise PullError("too many redirects")


fetcher_factory = HttpFeedFetcher


def pull(db: Session, src: FeedSource, at: datetime, *, fetch=None) -> str:
    """Fetch one source and queue a run. Returns the new last_status."""
    supplier = db.get(Supplier, src.supplier_id)
    fetch = fetch or fetcher_factory()
    status, error, feed_id = "failed", None, None
    try:
        code, body, etag = fetch.get(src.url, src.etag)
        if code == 304:
            status = "not_modified"
        else:
            run = importer.queue(db, supplier, body, src.format, src.mode, source="pull", by_user_id=src.created_by)
            status, feed_id, src.etag = "queued", run.feed_id, etag
    except PullError as exc:
        error = str(exc)
    except importer.FeedTooLarge as exc:
        error = str(exc)
    except importer.FeedInvalid as exc:
        error = f"the file is not a valid {src.format.upper()} feed: {exc}"
    except Exception as exc:  # noqa: BLE001 - a broken feed never stops the others
        log.exception("feed pull %s failed", src.supplier_id)
        error = f"internal error ({type(exc).__name__})"
    src = db.get(FeedSource, src.supplier_id)
    src.last_pull_at, src.last_status, src.last_error = at, status, (error or "")[:300] or None
    if feed_id:
        src.last_feed_id = feed_id
    db.add(src)
    db.commit()
    if status == "failed" and supplier is not None:
        notify.feed_pull_failed(db, supplier, src.url, error or "")
    return status


def pull_due(db: Session, at: datetime, *, fetch=None) -> int:
    """Every source whose 02:00 UTC slot has come: pull it and set the next."""
    n = 0
    for src in list(db.scalars(select(FeedSource).where(FeedSource.next_pull_at <= at))):
        supplier = db.get(Supplier, src.supplier_id)
        if supplier is None or supplier.status == "suspended":
            src.next_pull_at = next_pull_after(at)
            db.add(src)
            db.commit()
            continue
        pull(db, src, at, fetch=fetch)
        src = db.get(FeedSource, src.supplier_id)
        src.next_pull_at = next_pull_after(at)
        db.add(src)
        db.commit()
        n += 1
    return n
