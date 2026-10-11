"""Truebex: the Python SDK of the Truebex developer API.

    import truebex

    client = truebex.Client()  # reads TRUEBEX_API_KEY
    project = client.projects.create(name="API House", doc_version=38)
    job = client.jobs.create(kind="pack", project_id=project["project_id"], at_seq=0, params={"items": ["sheets"]})

Every operation of openapi/v1.json is a method of a group (`client.projects`,
`.jobs`, `.uploads`, `.shares`, `.market`, `.feeds`, `.webhooks`,
`.account`); answers are plain dicts typed by `truebex.models`. Errors raise
`TruebexError`; `verify_webhook` checks a webhook's signature.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from ._http import DEFAULT_BASE_URL, UNSET, TruebexError, Transport
from ._operations import GROUPS, OPERATIONS
from ._version import __version__
from .webhooks import WebhookVerificationError, verify_webhook

__all__ = ["Client", "TruebexError", "WebhookVerificationError", "verify_webhook", "OPERATIONS", "UNSET", "__version__"]


class Client:
    """A client for one API key.

    `base_url` defaults to https://api.truebex.com; `max_retries` covers 429,
    5xx and network errors (writes only with an idempotency key)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        user_agent: str | None = None,
    ) -> None:
        self._transport = Transport(api_key, base_url, timeout, max_retries, user_agent)
        for name, cls in GROUPS.items():
            setattr(self, name, cls(self._transport))

    def __repr__(self) -> str:  # never shows the key
        return f"truebex.Client(base_url={self._transport.base_url!r})"

    def upload(self, purpose: str, files: Iterable[bytes], content_type: str = "application/octet-stream") -> dict:
        """Open an upload for `files` (purpose share, snapshot or job-input) and
        send every part that is missing; returns the upload's status (5.3)."""
        blobs = {hashlib.sha256(data).hexdigest(): data for data in files}
        opened = self.uploads.create(  # type: ignore[attr-defined]
            purpose=purpose,
            files=[{"sha256": sha, "bytes": len(data), "content_type": content_type} for sha, data in blobs.items()],
        )
        size = opened["part_bytes"]
        for f in opened["files"]:
            if f["state"] in ("present", "complete"):
                continue
            data = blobs[f["sha256"]]
            for n in range(max(1, -(-len(data) // size))):
                if n in f.get("received", []):
                    continue
                self.uploads.put_part(opened["upload_id"], f["sha256"], n, data[n * size : (n + 1) * size])  # type: ignore[attr-defined]
        return self.uploads.get(opened["upload_id"])  # type: ignore[attr-defined]
