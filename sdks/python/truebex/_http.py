"""The HTTP core of the Truebex SDK: standard library only.

Sends the key as `Authorization: Bearer`, the contract header of each
operation, an `Idempotency-Key` where the operation takes one (so a retry
never repeats a write), and retries 429, 5xx and network errors with backoff
(1, 2, 4 … s, honouring `Retry-After`). Errors raise `TruebexError` carrying
the shared envelope's `code`, `detail`, `data` and `request_id`. Keys are never
logged or put in an error message.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ._version import __version__

DEFAULT_BASE_URL = "https://api.truebex.com"
RETRY_STATUS = (408, 429, 500, 502, 503, 504, 530)


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET: Any = _Unset()


class TruebexError(Exception):
    """An error answer: branch on `code` (e.g. forbidden, not_found, rate_limited)."""

    def __init__(self, status: int, code: str, detail: str, *, data: Any = None, request_id: str | None = None, retry_after_s: int | None = None) -> None:
        super().__init__(f"{status} {code}: {detail}")
        self.status = status
        self.code = code
        self.detail = detail
        self.data = data
        self.request_id = request_id
        self.retry_after_s = retry_after_s


class Transport:
    def __init__(self, api_key: str | None, base_url: str, timeout: float, max_retries: int, user_agent: str | None) -> None:
        self.api_key = api_key or os.environ.get("TRUEBEX_API_KEY") or ""
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.user_agent = user_agent or f"truebex-python/{__version__}"

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: Any = UNSET,
        data: bytes | None = None,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
        idempotent: bool = False,
    ) -> Any:
        if not self.api_key:
            raise TruebexError(401, "unauthenticated", "No API key: pass api_key= or set TRUEBEX_API_KEY.")
        url = self.base_url + path
        if query:
            pairs = [(k, _q(v)) for k, v in query.items() if v is not None and v is not UNSET]
            if pairs:
                url += "?" + urlencode(pairs)
        h = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json", "User-Agent": self.user_agent}
        h.update(headers or {})
        body = data
        if json_body is not UNSET:
            body = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
            h["Content-Type"] = "application/json"
        elif content_type:
            h["Content-Type"] = content_type
        may_retry = method != "POST" or idempotent
        attempt = 0
        while True:
            try:
                with urlopen(Request(url, data=body, headers=h, method=method), timeout=self.timeout) as res:
                    raw = res.read()
                    if res.status == 204 or not raw:
                        return None
                    return json.loads(raw)
            except HTTPError as exc:
                raw = exc.read()
                retry_after = _retry_after(exc.headers.get("Retry-After"))
                if attempt < self.max_retries and exc.code in RETRY_STATUS and (may_retry or exc.code == 429):
                    attempt += 1
                    time.sleep(retry_after if retry_after is not None else _backoff(attempt))
                    continue
                raise _error(exc.code, raw, exc.headers.get("X-Request-Id")) from None
            except URLError as exc:
                if attempt < self.max_retries and may_retry:
                    attempt += 1
                    time.sleep(_backoff(attempt))
                    continue
                raise TruebexError(0, "network_error", f"Could not reach {self.base_url}: {exc.reason}") from None


def _q(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _backoff(attempt: int) -> float:
    return min(60.0, 2.0 ** (attempt - 1)) * (0.8 + 0.4 * random.random())


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None


def _error(status: int, raw: bytes, request_id: str | None) -> TruebexError:
    try:
        body = json.loads(raw)
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    detail = body.get("detail")
    return TruebexError(
        status,
        body.get("code") or f"http_{status}",
        detail if isinstance(detail, str) else f"Request failed ({status})",
        data=body.get("data"),
        request_id=body.get("request_id") or request_id,
        retry_after_s=body.get("retry_after_s"),
    )


def _multipart(fields: dict[str, Any], file_name: str) -> tuple[bytes, str]:
    boundary = "truebex" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields.items():
        if value is None or value is UNSET:
            continue
        out += f"--{boundary}\r\n".encode()
        if isinstance(value, (bytes, bytearray)):
            out += f'Content-Disposition: form-data; name="{name}"; filename="{file_name}"\r\n'.encode()
            out += b"Content-Type: application/octet-stream\r\n\r\n" + bytes(value) + b"\r\n"
        else:
            out += f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


class Resource:
    """A group of operations; `_operations.py` generates one per group."""

    def __init__(self, transport: Transport) -> None:
        self._t = transport

    def _call(
        self,
        op_id: str,
        *path_values: str,
        values: dict[str, Any] | None = None,
        data: bytes | None = None,
        idempotency_key: str | None = None,
        part_sha256: str | None = None,
        filename: str = "feed",
    ) -> Any:
        from ._operations import OPERATIONS

        op = OPERATIONS[op_id]
        path = op["path"]
        for name, value in zip(op["path_params"], path_values):
            path = path.replace("{" + name + "}", quote(str(value), safe=""))
        values = {k: v for k, v in (values or {}).items() if v is not UNSET}
        query = {k: values[k] for k in op["query"] if k in values}
        headers: dict[str, str] = {}
        if op["contract"]:
            headers["X-Truebex-Contract"] = op["contract"]
        idempotent = False
        if "idempotency-key" in op["headers"]:
            headers["Idempotency-Key"] = idempotency_key or uuid.uuid4().hex
            idempotent = True
        kw: dict[str, Any] = {}
        if op["body"] == "json":
            kw["json_body"] = {k: values[k] for k in op["body_props"] if k in values and values[k] is not None}
        elif op["body"] == "binary":
            kw["data"] = data
            kw["content_type"] = "application/octet-stream"
            if "x-part-sha256" in op["headers"]:
                headers["X-Part-Sha256"] = part_sha256 or hashlib.sha256(data or b"").hexdigest()
        elif op["body"] == "multipart":
            body, ctype = _multipart({k: values.get(k) for k in op["body_props"]}, filename)
            kw["data"], kw["content_type"] = body, ctype
        return self._t.request(op["method"], path, query=query, headers=headers, idempotent=idempotent, **kw)
