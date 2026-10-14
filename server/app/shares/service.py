"""Shares (share-bundle §5.4-5.11, §6.2): create from a manifest, publish once
every file has arrived, list, change, revoke; the public page data and the
visit counter; expiry and purge.

Limits per tier come from the account's plan (`seats.seat_source`):
`limits.share_links` live shares; `limits.share_days` and
`limits.share_bytes` when the matrix has them (a MINOR proposal to
licence-api §6.3), else SHARE_MAX_DAYS and SHARE_MAX_BYTES. A 403
`quota_exceeded` names the caller's plan and the lowest plan that lifts it.

PF5b (share-bundle 1.1): 5.4 with `replace_share_id` is an Update. A live
share keeps serving its bundle while the new one uploads (the app's stub:
state `live`, its `version` and `bundle_id`; the new title and expiry apply
at once); 5.5 swaps in the new files, `bundle_id` and `version` + 1, drops
the old files nothing else uses and keeps the slug, the url and the visits.
"""

import math
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..licence import clock, seats
from ..licence.ids import uuid7_hex
from ..models import User
from ..plans import PLANS, get_plan
from ..storage import get_store
from ..uploads import service as uploads
from ..uploads.credentials import UploadCaller
from ..uploads.models import UploadSession
from . import card, derivatives, manifest
from .models import Share, ShareDerivative, ShareVisit

STATES = ("uploading", "live", "expired", "revoked")
PURGE_AFTER = timedelta(days=7)
# An unpublished share stops holding a live-share slot once its upload ends.
UPLOADING_HOLDS_SLOT = uploads.SESSION_LIFETIME
STALE_UPLOADING = timedelta(days=7)
PAGE_URL_SECONDS = 3600
# Signed URLs end on a 5-minute boundary at least an hour away, so the page's
# preload and the data's URL are the same URL within a 5-minute window.
URL_BUCKET_SECONDS = 300
SLUG_ALPHABET = string.ascii_letters + string.digits
SLUG_LENGTH = 10
VISIT_DAYS = 30


@dataclass(frozen=True)
class Limits:
    links: int | None
    days: int
    bytes: int


def _plan_limits(tier) -> Limits:
    s = get_settings()
    days = tier.limits.get("share_days")
    size = tier.limits.get("share_bytes")
    return Limits(
        links=tier.limits.get("share_links"),
        days=int(days) if days else s.share_max_days,
        bytes=int(size) if size else s.share_max_bytes,
    )


def limits_for(db: Session, user: User) -> Limits:
    return _plan_limits(get_plan(seats.seat_source(db, user).plan))


def _plan_data(db: Session, user: User, admits) -> dict:
    """403 `quota_exceeded`'s `plan` (the caller's) and `upgrade_to`: the
    lowest plan above it whose limits admit the request, or None (PF5b; the
    app's Upgrade dialog shows it)."""
    plan = get_plan(seats.seat_source(db, user).plan)
    higher = sorted((t for t in PLANS.values() if t.rank > plan.rank), key=lambda t: t.rank)
    return {"plan": plan.id, "upgrade_to": next((t.id for t in higher if admits(_plan_limits(t))), None)}


def limits_json(lim: Limits) -> dict:
    return {"share_links": lim.links, "share_days": lim.days, "share_bytes": lim.bytes}


def share_url(slug: str | None) -> str | None:
    return f"{get_settings().share_base}/view/{slug}" if slug else None


def card_url(slug: str, version: int = 1) -> str:
    """The link-preview image. After an Update its URL changes (`?v=`), so a
    preview cache that keys on the image URL fetches the new one."""
    url = f"{get_settings().share_base}/s/{slug}/card.jpg"
    return f"{url}?v={version}" if version > 1 else url


def download_name(name: object) -> str:
    """The name a file downloads as: the last segment of its manifest name
    (a name may hold folders, PF5b), never a quote or a control character."""
    last = next((part for part in reversed(str(name or "").split("/")) if part), "")
    clean = "".join("_" if ch in '"\\' or ord(ch) < 32 or ord(ch) == 127 else ch for ch in last).strip()
    return clean or "file"


def _gone(share: Share) -> ContractError:
    return ContractError(
        "share_gone", 410, "This share has ended.", {"state": share.state, "ended_at": clock.rfc3339(share.revoked_at or share.expires_at)}
    )


def _not_found() -> ContractError:
    return ContractError("not_found", 404, "No such share.")


# --- state ----------------------------------------------------------------------


def refresh_state(db: Session, share: Share, now: datetime | None = None) -> Share:
    """A live share past its expiry is expired (the job does it too, every 5 min)."""
    now = now or clock.now()
    if share.state == "live" and share.expires_at is not None and clock.aware(share.expires_at) <= now:
        share.state = "expired"
        share.purge_after = clock.aware(share.expires_at) + PURGE_AFTER
        db.add(share)
        db.commit()
    return share


def _owned(db: Session, user: User, share_id: str) -> Share:
    share = db.get(Share, share_id) if isinstance(share_id, str) and len(share_id) == 32 else None
    if share is None or share.account_id != user.id:
        raise _not_found()
    return refresh_state(db, share)


def _live_count(db: Session, account_id: int, now: datetime, *, exclude: str | None = None) -> int:
    live = select(func.count()).select_from(Share).where(Share.account_id == account_id, Share.state == "live")
    if exclude:
        live = live.where(Share.share_id != exclude)
    used = db.scalar(live.where((Share.expires_at.is_(None)) | (Share.expires_at > now))) or 0
    fresh = (
        select(func.count())
        .select_from(Share)
        .where(Share.account_id == account_id, Share.state == "uploading", Share.created_at > now - UPLOADING_HOLDS_SLOT)
    )
    if exclude:
        fresh = fresh.where(Share.share_id != exclude)
    return used + (db.scalar(fresh) or 0)


def _check_slots(db: Session, user: User, lim: Limits, now: datetime, *, exclude: str | None = None) -> None:
    if lim.links is None:
        return
    used = _live_count(db, user.id, now, exclude=exclude)
    if used >= lim.links:
        plural = "link" if lim.links == 1 else "links"
        raise ContractError(
            "quota_exceeded",
            403,
            f"Your plan keeps {lim.links} share {plural} live at a time. End one to share again.",
            {
                "kind": "share_links", "limit": lim.links, "used": used,
                **_plan_data(db, user, lambda t: t.links is None or used < t.links),
            },
        )


# --- JSON -----------------------------------------------------------------------


def visits_summary(db: Session, share_ids: list[str]) -> dict[str, dict]:
    if not share_ids:
        return {}
    rows = db.execute(
        select(
            ShareVisit.share_id,
            func.sum(ShareVisit.count),
            func.count(ShareVisit.id),
            func.max(ShareVisit.last_at),
        )
        .where(ShareVisit.share_id.in_(share_ids))
        .group_by(ShareVisit.share_id)
    ).all()
    out = {sid: {"total": 0, "unique": 0, "last_at": None} for sid in share_ids}
    for sid, total, unique, last in rows:
        out[sid] = {"total": int(total or 0), "unique": int(unique or 0), "last_at": clock.rfc3339(clock.aware(last))}
    return out


def visits_detail(db: Session, share_id: str, now: datetime) -> dict:
    summary = visits_summary(db, [share_id])[share_id]
    since = (now - timedelta(days=VISIT_DAYS - 1)).strftime("%Y-%m-%d")
    rows = db.execute(
        select(ShareVisit.day, func.sum(ShareVisit.count), func.count(ShareVisit.id))
        .where(ShareVisit.share_id == share_id, ShareVisit.day >= since)
        .group_by(ShareVisit.day)
        .order_by(ShareVisit.day)
    ).all()
    summary["by_day"] = [{"day": day, "count": int(c), "unique": int(u)} for day, c, u in rows]
    return summary


def share_json(share: Share, visits: dict | None = None) -> dict:
    return {
        "share_id": share.share_id,
        # 1.1: the bundle the share serves now, and 1 + its Updates.
        "bundle_id": share.bundle_id,
        "version": share.version or 1,
        "slug": share.slug,
        "url": share_url(share.slug),
        "title": share.title,
        "state": share.state,
        "created_at": clock.rfc3339(share.created_at),
        "published_at": clock.rfc3339(share.published_at),
        "expires_at": clock.rfc3339(share.expires_at),
        "revoked_at": clock.rfc3339(share.revoked_at),
        "bytes": share.bytes,
        "watermark": share.watermark,
        "visits": visits if visits is not None else {"total": 0, "unique": 0, "last_at": None},
    }


def one_json(db: Session, share: Share) -> dict:
    return share_json(share, visits_detail(db, share.share_id, clock.now()))


# --- 5.4 create -------------------------------------------------------------------


def _upload_for(db: Session, caller: UploadCaller, share: Share) -> dict | None:
    """The share's upload session (a new one when the old ended), as 5.1 answers it."""
    now = clock.now()
    session = db.get(UploadSession, share.upload_id) if share.upload_id else None
    if session is not None and clock.aware(session.expires_at) > now:
        return uploads.opened_json(db, session)
    if share.state == "live" and share.pending_manifest is not None:
        waiting = share.pending_manifest  # an Update still uploading
    elif share.state == "uploading":
        waiting = share.manifest
    else:
        return None
    session = uploads.open_session(db, caller, purpose="share", files=_upload_files(waiting))
    share.upload_id = session.upload_id
    db.add(share)
    db.commit()
    return uploads.opened_json(db, session)


def _by_bundle(db: Session, account_id: int, bundle_id: str) -> Share | None:
    """The share serving this bundle, or the one whose Update waits with it."""
    return db.scalar(
        select(Share)
        .where(Share.account_id == account_id, (Share.bundle_id == bundle_id) | (Share.pending_bundle_id == bundle_id))
        .order_by(Share.created_at)
        .limit(1)
    )


def _upload_files(m: dict) -> list[dict]:
    return [{"sha256": f["sha256"], "bytes": f["bytes"], "content_type": f["content_type"]} for f in manifest.files(m)]


def _check_days(days: int, lim: Limits, now: datetime) -> None:
    if days > lim.days:
        raise ContractError(
            "expiry_too_far",
            422,
            f"A share link lasts at most {lim.days} days on your plan.",
            {"max_days": lim.days, "max_expires_at": clock.rfc3339(now + timedelta(days=lim.days))},
        )


def create(
    db: Session, caller: UploadCaller, user: User, *, title: str, days: int, m: object, replace: str | None = None
) -> tuple[Share, dict | None, bool]:
    """Returns (share, upload, created). `replace` is 1.1's `replace_share_id`."""
    if isinstance(m, dict) and isinstance(m.get("bundle_id"), str):
        existing = _by_bundle(db, user.id, m["bundle_id"])
        if existing is not None:
            refresh_state(db, existing)
            return existing, _upload_for(db, caller, existing), False
    errors = manifest.check(m)
    if errors:
        raise ContractError(
            "manifest_invalid", 422, f"The bundle's manifest breaks {len(errors)} rule(s): {errors[0]['message']}",
            {"errors": errors},
        )
    assert isinstance(m, dict)
    now = clock.now()
    lim = limits_for(db, user)
    _check_days(days, lim, now)
    size = manifest.total_bytes(m)
    if size > lim.bytes:
        raise ContractError(
            "quota_exceeded", 403, f"A share holds at most {lim.bytes} bytes on your plan; this one is {size}.",
            {"kind": "share_bytes", "limit": lim.bytes, "used": size, **_plan_data(db, user, lambda t: size <= t.bytes)},
        )
    if replace is not None:
        return _replace(db, caller, user, replace, title=title, days=days, m=m, size=size, now=now)
    _check_slots(db, user, lim, now)
    session = uploads.open_session(db, caller, purpose="share", files=_upload_files(m))
    share = Share(
        share_id=uuid7_hex(),
        account_id=user.id,
        bundle_id=m["bundle_id"],
        title=title,
        state="uploading",
        manifest=m,
        bytes=size,
        watermark=bool(m.get("watermark")),
        days=days,
        upload_id=session.upload_id,
        created_at=now,
        expires_at=now + timedelta(days=days),
    )
    db.add(share)
    try:
        db.commit()
    except IntegrityError:  # the same bundle_id raced in
        db.rollback()
        existing = _by_bundle(db, user.id, m["bundle_id"])
        if existing is None:
            raise
        return existing, _upload_for(db, caller, existing), False
    return share, uploads.opened_json(db, session), True


def _replace(
    db: Session, caller: UploadCaller, user: User, share_id: str, *, title: str, days: int, m: dict, size: int, now: datetime
) -> tuple[Share, dict | None, bool]:
    """5.4 with `replace_share_id` (1.1): the new manifest goes into that share.
    It takes no new live-share slot. An ended share answers 409 `replace_conflict`."""
    share = _owned(db, user, share_id)
    if share.state in ("expired", "revoked"):
        raise ContractError(
            "replace_conflict", 409, f"That share has ended ({share.state}). Share again to make a new link.",
            {"state": share.state, "share_id": share.share_id},
        )
    session = uploads.open_session(db, caller, purpose="share", files=_upload_files(m))
    share.title = title
    share.days = days
    share.upload_id = session.upload_id
    share.expires_at = now + timedelta(days=days)
    if share.state == "uploading":
        # Nothing is served yet: the share takes the new bundle at once.
        share.bundle_id = m["bundle_id"]
        share.manifest = m
        share.bytes = size
        share.watermark = bool(m.get("watermark"))
        share.pending_bundle_id = share.pending_manifest = None
    else:
        # Live: it keeps serving its bundle until 5.5 publishes this one.
        share.pending_bundle_id = m["bundle_id"]
        share.pending_manifest = m
    db.add(share)
    try:
        db.commit()
    except IntegrityError:  # the new bundle_id raced into another share
        db.rollback()
        existing = _by_bundle(db, user.id, m["bundle_id"])
        if existing is None:
            raise
        return existing, _upload_for(db, caller, existing), False
    return share, uploads.opened_json(db, session), True


# --- 5.5 publish ------------------------------------------------------------------


def _mint_slug(db: Session) -> str:
    while True:
        slug = "".join(secrets.choice(SLUG_ALPHABET) for _ in range(SLUG_LENGTH))
        if db.scalar(select(Share).where(Share.slug == slug)) is None:
            return slug


_MAGIC = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG\r\n\x1a\n",), "application/pdf": (b"%PDF-",)}


def _verify_files(m: dict, blobs: dict) -> None:
    """The stored bytes are what the manifest says they are."""
    from PIL import Image

    store = get_store()
    errors = []
    index = {f["sha256"]: i for i, f in enumerate(manifest.files(m))}
    for f in manifest.files(m):
        blob = blobs[f["sha256"]]
        with store.open(blob.storage_key) as fh:
            head = fh.read(16)
        if not any(head.startswith(sig) for sig in _MAGIC.get(f["content_type"], (b"",))):
            errors.append({"path": f"files[{index[f['sha256']]}]", "rule": "file_content"})
    for kind, items in (("panoramas", manifest.panoramas(m)), ("renders", manifest.renders(m))):
        for i, item in enumerate(items):
            try:
                with store.open(blobs[item["file"]].storage_key) as fh:
                    size = Image.open(fh).size
            except Exception:
                size = None
            if size != (item.get("width"), item.get("height")):
                errors.append({"path": f"{kind}[{i}].file", "rule": "file_content"})
    cover = manifest.cover(m)
    if cover is not None:
        try:
            with store.open(blobs[cover].storage_key) as fh:
                Image.open(fh).verify()
        except Exception:
            errors.append({"path": "cover", "rule": "file_content"})
    if errors:
        for e in errors:
            e["message"] = manifest.MESSAGES["file_content"]
        raise ContractError(
            "manifest_invalid", 422, "A file's content does not match the manifest.", {"errors": errors}
        )


def publish(db: Session, user: User, share_id: str) -> Share:
    share = _owned(db, user, share_id)
    update = share.pending_manifest is not None
    if share.state == "live" and not update:
        return share
    if share.state not in ("uploading", "live"):
        raise _gone(share)
    m = share.pending_manifest if update else share.manifest
    shas = manifest.file_shas(m)
    missing = uploads.missing_files(db, user.id, shas)
    if missing:
        n = len(missing)
        raise ContractError(
            "upload_incomplete", 422, f"This share is still missing {n} file{'s' if n != 1 else ''}.", {"missing": missing}
        )
    now = clock.now()
    if not update:
        _check_slots(db, user, limits_for(db, user), now, exclude=share.share_id)
    blobs = uploads.blobs_by_sha(db, user.id, shas)
    _verify_files(m, blobs)

    store = get_store()
    have = {
        (d.source_sha256, d.kind)
        for d in db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == share.share_id))
    }
    start = manifest.start_panorama(m)
    start_image = None
    for sha in dict.fromkeys(p["file"] for p in manifest.panoramas(m)):
        made, largest = derivatives.make(store, share_id=share.share_id, sha256=sha, source_key=blobs[sha].storage_key)
        for d in made:
            if (sha, d.kind) not in have:
                db.add(
                    ShareDerivative(
                        share_id=share.share_id, source_sha256=sha, kind=d.kind,
                        storage_key=d.key, width=d.width, height=d.height, bytes=d.bytes,
                    )
                )
        if start is not None and sha == start["file"]:
            start_image = largest
    key = f"shares/{share.share_id}/card.jpg"
    cover = manifest.cover(m)
    if cover is not None:
        # 1.1: the app's cover is the link preview (fitted to 1200 x 630).
        with store.open(blobs[cover].storage_key) as fh:
            image = card.from_cover(fh.read())
    else:
        render_image = None
        if start_image is None and manifest.renders(m):
            render_image = derivatives.open_rgb(store, blobs[manifest.renders(m)[0]["file"]].storage_key, draft_width=2400)
        image = card.compose(card.background_for(m, start_image, render_image), share.title)
    store.put(key, image, content_type="image/jpeg")

    uploads.add_refs(db, user.id, shas)
    old = share.manifest if update else None
    if update:
        # 5.5 of an Update: the share serves the new bundle from now on.
        share.manifest = m
        share.bundle_id = m["bundle_id"]
        share.bytes = manifest.total_bytes(m)
        share.watermark = bool(m.get("watermark"))
        share.version = (share.version or 1) + 1
        share.pending_bundle_id = None
        share.pending_manifest = None
    else:
        share.state = "live"
        share.expires_at = now + timedelta(days=share.days)
        share.version = 1
    share.card_key = key
    share.slug = share.slug or _mint_slug(db)
    share.published_at = now
    db.add(share)
    try:
        db.commit()
    except IntegrityError:  # another share of this account took the bundle_id meanwhile
        db.rollback()
        raise ContractError(
            "replace_conflict", 409, "Another share already serves this bundle.", {"bundle_id": m.get("bundle_id")}
        )
    if old is not None:
        _drop_replaced(db, share, old)
    return share


def _drop_replaced(db: Session, share: Share, old: dict) -> None:
    """After an Update is live: the old bundle's files lose this share's ref
    (a blob nothing else holds is deleted) and derivatives of panoramas the
    new bundle no longer has go. Run after the swap is committed, so a failed
    swap never loses a file the share still serves."""
    uploads.drop_refs(db, share.account_id, manifest.file_shas(old))
    keep = {p["file"] for p in manifest.panoramas(share.manifest)}
    stale = [
        d for d in db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == share.share_id)).all()
        if d.source_sha256 not in keep
    ]
    for d in stale:
        db.delete(d)
    db.commit()
    store = get_store()
    for d in stale:
        store.delete(d.storage_key)


# --- 5.6-5.9 ------------------------------------------------------------------------


def list_for(db: Session, user: User, state: str | None) -> list[Share]:
    now = clock.now()
    rows = db.scalars(select(Share).where(Share.account_id == user.id).order_by(Share.created_at.desc())).all()
    for share in rows:
        refresh_state(db, share, now)
    return [s for s in rows if state is None or s.state == state]


def get(db: Session, user: User, share_id: str) -> Share:
    return _owned(db, user, share_id)


def change(db: Session, user: User, share_id: str, *, title: str | None, expires_at: datetime | None) -> Share:
    share = _owned(db, user, share_id)
    if share.state == "revoked":
        raise _gone(share)
    now = clock.now()
    if expires_at is not None:
        when = clock.floor_s(expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc))
        lim = limits_for(db, user)
        latest = now + timedelta(days=lim.days)
        if when <= now:
            raise ContractError(
                "validation_failed", 422, "Pick an expiry date in the future.", {"fields": [{"field": "expires_at"}]}
            )
        if when > latest + timedelta(minutes=1):
            raise ContractError(
                "expiry_too_far", 422, f"A share link lasts at most {lim.days} days on your plan.",
                {"max_days": lim.days, "max_expires_at": clock.rfc3339(latest)},
            )
        when = min(when, latest)
        if share.state == "expired":
            if share.purged_at is not None:
                raise _gone(share)
            _check_slots(db, user, lim, now, exclude=share.share_id)
            share.state = "live"
            share.purge_after = None
        if share.state == "uploading":
            share.days = max(1, math.ceil((when - now).total_seconds() / 86400))
        share.expires_at = when
    if title is not None:
        share.title = title
    db.add(share)
    db.commit()
    return share


def revoke(db: Session, user: User, share_id: str) -> Share:
    share = _owned(db, user, share_id)
    if share.state == "revoked":
        return share
    now = clock.now()
    share.state = "revoked"
    share.revoked_at = now
    candidate = now + PURGE_AFTER
    current = clock.aware(share.purge_after)
    share.purge_after = min(current, candidate) if current else candidate
    db.add(share)
    db.commit()
    return share


# --- 5.10, 5.11: the public page --------------------------------------------------------


def by_slug(db: Session, slug: str) -> Share:
    """The published share behind a link: 404 unknown, 410 ended."""
    share = None
    if isinstance(slug, str) and len(slug) == SLUG_LENGTH and slug.isalnum() and slug.isascii():
        share = db.scalar(select(Share).where(Share.slug == slug))
    if share is None or share.state == "uploading":
        raise _not_found()
    refresh_state(db, share)
    if share.state in ("expired", "revoked"):
        raise _gone(share)
    return share


def _expires_in() -> int:
    import time

    now = int(time.time())
    target = ((now + PAGE_URL_SECONDS) // URL_BUCKET_SECONDS + 1) * URL_BUCKET_SECONDS
    return target - now


def page_urls(db: Session, share: Share) -> dict:
    """Signed URLs of the share's files and derivatives (valid at least 1 h)."""
    store = get_store()
    m = share.manifest
    blobs = uploads.blobs_by_sha(db, share.account_id, manifest.file_shas(m))
    ttl = _expires_in()
    files = {}
    for f in manifest.files(m):
        blob = blobs.get(f["sha256"])
        if blob is None:
            continue
        name = download_name(f.get("name")) if f["content_type"] == "application/pdf" else None
        files[f["sha256"]] = store.signed_get_url(blob.storage_key, expires_in=ttl, filename=name)
    derived: dict[str, dict] = {}
    for d in db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == share.share_id)):
        derived.setdefault(d.source_sha256, {})[d.kind] = {
            "url": store.signed_get_url(d.storage_key, expires_in=ttl),
            "width": d.width,
            "height": d.height,
            "bytes": d.bytes,
        }
    return {"files": files, "derived": derived}


def page_data(db: Session, share: Share) -> dict:
    urls = page_urls(db, share)
    m = manifest.public(share.manifest)  # 1.1's plan and app_build stay private
    m["files"] = [{**f, "url": urls["files"].get(f["sha256"])} for f in manifest.files(m)]
    m["panoramas"] = [{**p, "derivatives": urls["derived"].get(p.get("file"), {})} for p in manifest.panoramas(m)]
    return {
        "title": share.title,
        "created_at": clock.rfc3339(share.created_at),
        "published_at": clock.rfc3339(share.published_at),
        "expires_at": clock.rfc3339(share.expires_at),
        "watermark": share.watermark,
        "designed_in": "Truebex",
        "url": share_url(share.slug),
        "version": share.version or 1,
        "manifest": m,
    }


def record_visit(db: Session, share: Share, visitor: str, now: datetime | None = None) -> None:
    now = now or clock.now()
    day = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    match = (ShareVisit.share_id == share.share_id, ShareVisit.day == day, ShareVisit.visitor == visitor)
    for _ in range(2):
        done = db.execute(update(ShareVisit).where(*match).values(count=ShareVisit.count + 1, last_at=now))
        if done.rowcount:
            db.commit()
            return
        db.add(ShareVisit(share_id=share.share_id, day=day, visitor=visitor, count=1, last_at=now))
        try:
            db.commit()
            return
        except IntegrityError:  # the same visitor's other tab got there first
            db.rollback()


# --- jobs -------------------------------------------------------------------------------


def expire(db: Session, now: datetime) -> int:
    """shares.expire: live shares past expiry, and uploads abandoned for 7 days."""
    n = 0
    for share in db.scalars(select(Share).where(Share.state == "live", Share.expires_at <= now)).all():
        share.state = "expired"
        share.purge_after = clock.aware(share.expires_at) + PURGE_AFTER
        n += 1
    stale = select(Share).where(Share.state == "uploading", Share.created_at <= now - STALE_UPLOADING)
    for share in db.scalars(stale).all():
        share.state = "expired"
        share.purge_after = now
        n += 1
    db.commit()
    return n


def purge(db: Session, now: datetime) -> int:
    """shares.purge: files, derivatives and the card of shares 7 days ended."""
    store = get_store()
    due = select(Share).where(Share.purge_after.is_not(None), Share.purge_after <= now, Share.purged_at.is_(None))
    n = 0
    for share in db.scalars(due).all():
        for d in db.scalars(select(ShareDerivative).where(ShareDerivative.share_id == share.share_id)).all():
            store.delete(d.storage_key)
            db.delete(d)
        if share.card_key:
            store.delete(share.card_key)
            share.card_key = None
        if share.published_at is not None:
            uploads.drop_refs(db, share.account_id, manifest.file_shas(share.manifest))
        share.purged_at = now
        n += 1
    db.commit()
    return n
