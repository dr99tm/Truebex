"""What every contract router shares (contracts/*.md §3 and §7).

* `contract(name, major, minor)`: a router dependency that reads the client's
  `X-Truebex-Contract: <name>/<major>.<minor>`, answers 400 `contract_version`
  for a MAJOR this server does not serve, and echoes the server's own version.
* `ContractError`: raise it for any contract error; the handler writes the
  shared envelope `{detail, code, status, request_id, retry_after_s, data}`.
* `RequestIdMiddleware`: a 32-hex `request_id` per request, in the envelope
  and in the `X-Request-Id` response header.
* FastAPI's 422 list becomes `validation_failed` with `data.fields`; `detail`
  stays a string, as the site's `toError` expects (src/lib/api.ts).
"""

import re
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CONTRACT_HEADER = "X-Truebex-Contract"
_HEADER_RE = re.compile(r"^([a-z0-9-]+)/(\d+)\.(\d+)$")


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
        self.headers = dict(headers or {})
        if retry_after_s is not None:
            self.headers.setdefault("Retry-After", str(retry_after_s))


def request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = uuid.uuid4().hex
        request.state.request_id = rid
    return rid


def envelope(
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
    out = dict(headers or {})
    out["X-Request-Id"] = rid
    served = getattr(request.state, "contract", None)
    if served:
        out[CONTRACT_HEADER] = served
    return JSONResponse(
        status_code=status,
        content={
            "detail": detail,
            "code": code,
            "status": status,
            "request_id": rid,
            "retry_after_s": retry_after_s,
            "data": data,
        },
        headers=out,
    )


def contract(name: str, major: int, minor: int):
    """Router dependency for the endpoints of contract `name` at `major.minor`.

    A missing header is served as the current version; another contract's
    name or another MAJOR is refused. A newer MINOR is additive, so served.
    """
    served = f"{name}/{major}.{minor}"

    def dependency(request: Request, response: Response) -> str:
        request.state.contract = served
        response.headers[CONTRACT_HEADER] = served
        sent = request.headers.get(CONTRACT_HEADER)
        if sent is None:
            return served
        m = _HEADER_RE.match(sent.strip())
        if not m or m.group(1) != name or int(m.group(2)) != major:
            raise ContractError(
                "contract_version",
                400,
                f"This server speaks {served}. Update Truebex to continue.",
                {"supported": [served]},
            )
        return served

    return dependency


def _field_path(loc: tuple | list) -> str:
    out = ""
    for part in loc:
        if part in ("body", "query", "path", "header"):
            continue
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def validation_fields(errors: list[dict]) -> list[dict[str, str]]:
    return [{"field": _field_path(e.get("loc", ())), "message": e.get("msg", "")} for e in errors]


class RequestIdMiddleware:
    """Pure ASGI (no BaseHTTPMiddleware) so errors and streaming are untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = rid

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if "x-request-id" not in headers:
                    headers.append("X-Request-Id", rid)
            await send(message)

        await self.app(scope, receive, send_with_id)


def install(app: FastAPI) -> None:
    """Register the middleware and the envelope handlers on the app."""
    app.add_middleware(RequestIdMiddleware)

    @app.exception_handler(ContractError)
    async def _contract_error(request: Request, exc: ContractError) -> JSONResponse:
        return envelope(
            request,
            status=exc.status,
            code=exc.code,
            detail=exc.detail,
            data=exc.data,
            retry_after_s=exc.retry_after_s,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = validation_fields(list(exc.errors()))
        # The first message alone, as the site showed it before (detail[0].msg).
        detail = fields[0]["message"] if fields else "Invalid request."
        return envelope(
            request,
            status=422,
            code="validation_failed",
            detail=detail,
            data={"fields": fields},
        )
