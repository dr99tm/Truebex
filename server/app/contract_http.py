"""Plumbing every contract router shares (PF14 §Design Plumbing; first user PF1).

* `contract(name, major, minor)`: a router dependency that reads the
  client's `X-Truebex-Contract: <name>/<major>.<minor>`, echoes the server's,
  and answers 400 `contract_version` (with `data.supported`) to a MAJOR it
  does not serve. A missing header is read as the current version.
* `ContractError(code, status, detail, data)`: raised anywhere in a contract
  route; its handler writes the shared error envelope
  `{detail, code, status, request_id, retry_after_s, data}`.
* FastAPI's 422 list becomes the same envelope on every route
  (`validation_failed` with `data.fields`; `detail` stays a string, as the
  site's `toError` expects, src/lib/api.ts). On contract routes plain
  HTTPExceptions are rewritten to the envelope too; other routers keep their
  existing `{"detail": …}` bodies for every other error.
* `RequestIdMiddleware`: every response carries `X-Request-Id`; the envelope
  repeats it as `request_id`. Logs carry it, never tokens or poll secrets.
"""

import logging
import re
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTRACT_HEADER = "X-Truebex-Contract"
REQUEST_ID_HEADER = "X-Request-Id"

log = logging.getLogger("truebex.contract")

# Status -> code for errors raised without one (contract §7: a body without
# `code` reads as http_<status>; these are the shared names).
_DEFAULT_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "too_large",
    422: "validation_failed",
    429: "rate_limited",
    503: "unavailable",
}


class ContractError(Exception):
    def __init__(
        self,
        code: str,
        status: int,
        detail: str,
        data: dict[str, Any] | None = None,
        *,
        retry_after_s: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.code = code
        self.status = status
        self.detail = detail
        self.data = data
        self.retry_after_s = retry_after_s
        self.headers = headers or {}


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = request.state.request_id = secrets.token_hex(16)
    return rid


class RequestIdMiddleware:
    """Pure ASGI (streams pass straight through): a fresh 32-hex id per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = secrets.token_hex(16)
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if REQUEST_ID_HEADER.lower() not in headers:
                    headers.append(REQUEST_ID_HEADER, rid)
            await send(message)

        await self.app(scope, receive, send_with_id)


def contract(name: str, major: int, minor: int):
    """Router dependency for a contract's routes (`APIRouter(dependencies=[…])`)."""
    ours = f"{name}/{major}.{minor}"
    pattern = re.compile(rf"^{re.escape(name)}/(\d+)\.(\d+)$")

    def dependency(request: Request, response: Response) -> None:
        request.state.contract = ours
        request.state.envelope = True
        response.headers[CONTRACT_HEADER] = ours
        sent = request.headers.get(CONTRACT_HEADER)
        if sent is None:
            return
        m = pattern.match(sent.strip())
        if m is None or int(m.group(1)) != major:
            raise ContractError(
                "contract_version",
                400,
                f"This server speaks {ours}. Update Truebex to continue.",
                {"supported": [ours], "received": sent[:64]},
            )

    return Depends(dependency)


def enveloped():
    """Router dependency: errors use the shared envelope (non-contract routes)."""

    def dependency(request: Request) -> None:
        request.state.envelope = True

    return Depends(dependency)


def _wants_envelope(request: Request) -> bool:
    return bool(getattr(request.state, "envelope", False))


def envelope_response(
    request: Request,
    *,
    status: int,
    code: str,
    detail: str,
    data: dict[str, Any] | None = None,
    retry_after_s: int | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    rid = request_id(request)
    out_headers = dict(headers or {})
    # Set here as well: errors from ServerErrorMiddleware never pass through
    # RequestIdMiddleware.
    out_headers[REQUEST_ID_HEADER] = rid
    contract_name = getattr(request.state, "contract", None)
    if contract_name:
        out_headers[CONTRACT_HEADER] = contract_name
    if retry_after_s is not None:
        out_headers.setdefault("Retry-After", str(retry_after_s))
    if status >= 500 or status in (401, 403, 429):
        log.info("%s %s -> %s %s (request %s)", request.method, request.url.path, status, code, rid)
    return JSONResponse(
        {
            "detail": detail,
            "code": code,
            "status": status,
            "request_id": rid,
            "retry_after_s": retry_after_s,
            "data": data,
        },
        status_code=status,
        headers=out_headers,
    )


_LOCATIONS = ("body", "query", "path", "header", "cookie")


def _field_path(loc: tuple | list) -> str:
    """`("body", "events", 0, "name")` -> `events[0].name`."""
    parts = list(loc[1:] if loc and loc[0] in _LOCATIONS else loc)
    out = ""
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def validation_fields(errors: list[dict]) -> list[dict[str, str]]:
    """Pydantic / FastAPI errors as `data.fields`: `{field, in, message}`."""
    fields = []
    for err in errors:
        loc = tuple(err.get("loc", ()))
        where = str(loc[0]) if loc and loc[0] in _LOCATIONS else "body"
        fields.append(
            {"field": _field_path(loc), "in": where, "message": str(err.get("msg", "invalid"))}
        )
    return fields


def install(app: FastAPI) -> None:
    """Register the middleware and handlers on the app."""
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(ContractError)
    async def _contract_error(request: Request, exc: ContractError) -> JSONResponse:
        return envelope_response(
            request,
            status=exc.status,
            code=exc.code,
            detail=exc.detail,
            data=exc.data,
            retry_after_s=exc.retry_after_s,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        if not _wants_envelope(request):
            return await http_exception_handler(request, exc)
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return envelope_response(
            request,
            status=exc.status_code,
            code=_DEFAULT_CODES.get(exc.status_code, f"http_{exc.status_code}"),
            detail=detail,
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        fields = validation_fields(list(exc.errors()))
        first = fields[0] if fields else {"field": "", "message": "Invalid request."}
        if _wants_envelope(request) and first["field"]:
            detail = f"{first['field']}: {first['message']}"
        else:
            # The first message alone, as the site showed it before (detail[0].msg).
            detail = first["message"]
        return envelope_response(
            request, status=422, code="validation_failed", detail=detail, data={"fields": fields}
        )
