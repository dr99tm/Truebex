"""The live share page (PF6 Scope 9; a MINOR proposal for share-bundle §5, §6.1).

A share manifest's panorama may name a followed set with `live_job_id`. The
share viewer then shows that set's tiles and long-polls
`GET /s/{slug}/live?rev=` (no credential: whoever holds the link), a
share-scoped read of the set's newest manifest, because 5.2 is owner-only.
Only a set of the share's own account is served; revoking the share (PF5)
ends it.

The share itself is PF5's: `resolve_share(db, slug)` asks PF5's
`shares.service.by_slug` (404 unknown, 410 ended) when that module is
present, and is swappable for tests (`set_share_resolver`).
"""

from collections.abc import Callable

from sqlalchemy.orm import Session

from ..contract_http import ContractError
from . import tiles
from .models import RenderJob, RenderSet

ShareResolver = Callable[[Session, str], dict]


def _pf5_resolver(db: Session, slug: str) -> dict:
    try:
        from ..shares import service as shares  # PF5
    except ImportError:
        raise ContractError("not_found", 404, "No such share.")
    share = shares.by_slug(db, slug)
    return {"account_id": share.account_id, "manifest": share.manifest}


_resolver: ShareResolver = _pf5_resolver


def set_share_resolver(fn: ShareResolver | None) -> None:
    global _resolver
    _resolver = fn or _pf5_resolver


def resolve(db: Session, slug: str, panorama: str | None) -> RenderSet:
    """The followed set a live share's panorama names (404 otherwise)."""
    share = _resolver(db, slug)
    panoramas = [p for p in (share.get("manifest") or {}).get("panoramas") or [] if isinstance(p, dict)]
    live = [p for p in panoramas if isinstance(p.get("live_job_id"), str)]
    if panorama:
        live = [p for p in live if p.get("id") == panorama]
    row = db.get(RenderSet, live[0]["live_job_id"]) if live else None
    if row is None or row.account_id != share["account_id"]:
        raise ContractError("not_found", 404, "This share has no live view.")
    return row


def state(db: Session, row: RenderSet) -> dict:
    """`{rev, job_id, at_seq, following, manifest}` (manifest with `tiles_base`)."""
    manifest = None
    if row.latest_job_id:
        job = db.get(RenderJob, row.latest_job_id)
        manifest = tiles.read_json(job.output_key) if job is not None and job.output_key else None
        if manifest is not None:
            manifest["tiles_base"] = tiles.tiles_base()
    return {
        "rev": row.rev,
        "job_id": row.latest_job_id,
        "follow_job_id": row.follow_job_id,
        "at_seq": row.at_seq,
        "following": bool(row.active),
        "manifest": manifest,
    }
