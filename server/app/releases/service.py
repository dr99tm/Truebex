"""Signed release manifests, the feed and download URLs (5.13, 5.14, §6.4).

A release is published on the host by server/scripts/publish_release.py (or
uploaded by an admin with a manifest signed off-host): the installer goes to
storage at releases/{version}/{platform}/{file}, and a row keeps the
manifest's canonical JSON with its rel-* signature exactly as signed. The
API host never holds a rel-* private key, so it can serve manifests but not
forge one the updater would accept.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError
from ..growth.service import record_download
from ..licence import clock, signing
from ..licence.jcs import canonicalize
from ..storage import Store
from . import semver
from .models import Release

SCHEMA = "truebex-release/1"
FEED_SCHEMA = "truebex-releases/1"
CHANNELS = ("stable", "beta")
PLATFORMS = ("win64",)
FEED_LIMIT = 10
DOWNLOAD_TTL_S = 900  # contract 5.14: valid 15 minutes
MAX_NOTES_BYTES = 20 * 1024
MAX_UPLOAD_BYTES = 90 * 1024 * 1024  # POST /admin/releases; bigger files use the script
_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,199}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TIME = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
MANIFEST_KEYS = {
    "schema", "version", "channel", "platform", "published_at", "mandatory",
    "min_update_from", "notes_md", "notes_url", "installer",
}


def storage_key(version: str, platform: str, file: str) -> str:
    return f"releases/{version}/{platform}/{file}"


def notes_url(version: str) -> str:
    return f"{get_settings().site_url.rstrip('/')}/changelog/#{version}"


def manifest_errors(m: object) -> list[str]:
    """Why a manifest is not a valid truebex-release/1 document (empty = valid)."""
    if not isinstance(m, dict):
        return ["the manifest must be a JSON object"]
    errors: list[str] = []
    missing = MANIFEST_KEYS - set(m)
    if missing:
        errors.append("missing: " + ", ".join(sorted(missing)))
    if m.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    version = m.get("version")
    if not semver.is_valid(version):
        errors.append("version must be SemVer 2.0.0")
    if m.get("channel") not in CHANNELS:
        errors.append("channel must be stable or beta")
    elif m.get("channel") == "stable" and semver.is_valid(version) and semver.is_prerelease(version):
        errors.append("a stable release cannot be a pre-release version")
    if m.get("platform") not in PLATFORMS:
        errors.append("platform must be one of " + ", ".join(PLATFORMS))
    if not isinstance(m.get("published_at"), str) or not _TIME.match(m["published_at"]):
        errors.append("published_at must be RFC 3339 UTC (…Z)")
    if not isinstance(m.get("mandatory"), bool):
        errors.append("mandatory must be true or false")
    muf = m.get("min_update_from")
    if muf is not None and not semver.is_valid(muf):
        errors.append("min_update_from must be SemVer or null")
    notes = m.get("notes_md")
    if not isinstance(notes, str) or len(notes.encode("utf-8")) > MAX_NOTES_BYTES:
        errors.append("notes_md must be text of at most 20 KB")
    if not isinstance(m.get("notes_url"), str):
        errors.append("notes_url must be a URL")
    inst = m.get("installer")
    if not isinstance(inst, dict):
        errors.append("installer must be {file, bytes, sha256}")
    else:
        if not isinstance(inst.get("file"), str) or not _FILE.match(inst["file"]):
            errors.append("installer.file must be a plain file name")
        if not isinstance(inst.get("bytes"), int) or isinstance(inst.get("bytes"), bool) or inst["bytes"] <= 0:
            errors.append("installer.bytes must be a positive integer")
        if not isinstance(inst.get("sha256"), str) or not _HEX64.match(inst["sha256"]):
            errors.append("installer.sha256 must be 64 lowercase hex")
    try:
        canonicalize(m)
    except TypeError as exc:
        errors.append(str(exc))
    return errors


def signature_ok(manifest: dict, signature: dict) -> bool:
    """Verifies against the published rel-* keys (RELEASE_PUBLIC_KEYS)."""
    return signing.verify(manifest, signature, signing.keys_by_use("release"))


def build_manifest(
    *,
    version: str,
    channel: str,
    platform: str,
    file_name: str,
    size: int,
    sha256: str,
    notes_md: str,
    mandatory: bool = False,
    min_update_from: str | None = None,
    published_at: datetime | None = None,
    notes_url_: str | None = None,
) -> dict:
    return {
        "schema": SCHEMA,
        "version": version,
        "channel": channel,
        "platform": platform,
        "published_at": clock.rfc3339(published_at or clock.now()),
        "mandatory": mandatory,
        "min_update_from": min_update_from,
        "notes_md": notes_md,
        "notes_url": notes_url_ or notes_url(version),
        "installer": {"file": file_name, "bytes": size, "sha256": sha256},
    }


def _existing(db: Session, version: str, platform: str) -> Release | None:
    return db.scalar(select(Release).where(Release.version == version, Release.platform == platform))


def register(db: Session, store: Store, manifest: dict, signature: dict, data: BinaryIO) -> Release:
    """Store the installer and record a release whose signature already verified."""
    errors = manifest_errors(manifest)
    if errors:
        raise ContractError("validation_failed", 422, "; ".join(errors), {"errors": errors})
    version, platform = manifest["version"], manifest["platform"]
    if _existing(db, version, platform) is not None:
        raise ContractError("conflict", 409, f"Release {version} ({platform}) is already published.")
    inst = manifest["installer"]
    key = storage_key(version, platform, inst["file"])
    info = store.put(key, data, content_type="application/octet-stream")
    if info.bytes != inst["bytes"] or info.sha256 != inst["sha256"]:
        store.delete(key)
        raise ContractError(
            "installer_mismatch",
            422,
            "The file's size or SHA-256 differs from the manifest.",
            {"bytes": info.bytes, "sha256": info.sha256},
        )
    row = Release(
        version=version,
        platform=platform,
        channel=manifest["channel"],
        manifest=canonicalize(manifest),
        signature=signature["value"],
        kid=signature["kid"],
        storage_key=key,
        published_at=clock.parse_rfc3339(manifest["published_at"]),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def publish(
    db: Session,
    store: Store,
    *,
    version: str,
    channel: str,
    platform: str,
    file_path: str | Path,
    notes_md: str,
    private_key,
    kid: str,
    mandatory: bool = False,
    min_update_from: str | None = None,
    published_at: datetime | None = None,
) -> Release:
    """What publish_release.py does: hash, write the manifest, sign, store, register."""
    path = Path(file_path)
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    manifest = build_manifest(
        version=version,
        channel=channel,
        platform=platform,
        file_name=path.name,
        size=size,
        sha256=digest.hexdigest(),
        notes_md=notes_md,
        mandatory=mandatory,
        min_update_from=min_update_from,
        published_at=published_at,
    )
    signature = signing.sign(manifest, private_key, kid)
    with path.open("rb") as fh:
        return register(db, store, manifest, signature, fh)


def entry(row: Release) -> dict:
    return {
        "manifest": json.loads(row.manifest),
        "signature": {"alg": signing.ALG, "kid": row.kid, "value": row.signature},
        "download": f"/releases/{row.version}/download?platform={row.platform}",
    }


def feed(db: Session, channel: str, platform: str) -> dict:
    rows = [
        r
        for r in db.scalars(
            select(Release).where(Release.platform == platform, Release.withdrawn_at.is_(None))
        )
        if channel == "beta" or (r.channel == "stable" and not semver.is_prerelease(r.version))
    ]
    rows.sort(key=lambda r: (semver.key(r.version), clock.aware(r.published_at)), reverse=True)
    rows = rows[:FEED_LIMIT]
    return {
        "schema": FEED_SCHEMA,
        "channel": channel,
        "platform": platform,
        "latest": rows[0].version if rows else None,
        "releases": [entry(r) for r in rows],
    }


def find_live(db: Session, version: str, platform: str) -> Release:
    row = _existing(db, version, platform) if semver.is_valid(version) else None
    if row is None or row.withdrawn_at is not None:
        raise ContractError("not_found", 404, f"There is no release {version} for {platform}.")
    return row


def download_url(db: Session, store: Store, row: Release) -> dict:
    manifest = json.loads(row.manifest)
    inst = manifest["installer"]
    url = store.signed_get_url(row.storage_key, expires_in=DOWNLOAD_TTL_S, filename=inst["file"])
    now = clock.now()
    # Counted for the admin Growth panel (PF13's download_events): no personal data.
    record_download(db, version=row.version, platform=row.platform, channel=row.channel, at=now)
    return {
        "url": url,
        "expires_at": clock.rfc3339(now + timedelta(seconds=DOWNLOAD_TTL_S)),
        "bytes": inst["bytes"],
        "sha256": inst["sha256"],
    }
