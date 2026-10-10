"""What every /v1 route group shares (PF12): the scope dependencies, the
project caller a key becomes, and the documented error answers."""

from fastapi import Depends, Response

from ...deps import ApiCaller, api_key_auth, api_key_scope
from ...projects.caller import ProjectCaller
from .models import ErrorEnvelope

RATE_HEADERS = ("X-RateLimit-Limit", "X-RateLimit-Remaining")


def scope(name: str):
    """`Depends` for a route needing `name` (authenticates and meters the key)."""
    return Depends(api_key_scope(name))


AnyKey = Depends(api_key_auth)


def doc(scope_name: str | None, model=None, status: int = 200, *, errors: tuple[int, ...] = (401, 403, 404, 422, 429)) -> dict:
    """`responses=` and `openapi_extra=` for a route: its answer, the shared
    error envelope and the scope it needs (`x-truebex-scope`)."""
    texts = {
        400: "Unsupported contract version (`contract_version`).",
        401: "Missing, malformed, invalid or revoked API key (`unauthenticated`).",
        403: "The key lacks the scope (`forbidden`, `data.needed`), the role is too low, or the plan lacks the feature.",
        404: "Unknown, or not visible to this key's account (`not_found`).",
        409: "Conflict with the resource's state (the `code` says which).",
        410: "Gone (`upload_expired`).",
        413: "Too large (`too_large`).",
        422: "Validation failed (`validation_failed`, `data.fields`), or a contract rule (`code`).",
        429: "Burst limit or monthly quota reached (`rate_limited`, `retry_after_s`).",
    }
    responses: dict = {code: {"model": ErrorEnvelope, "description": texts[code]} for code in errors}
    if model is not None:
        responses[status] = {"model": model, "description": "Success"}
    out = {"responses": responses}
    if scope_name:
        out["openapi_extra"] = {"x-truebex-scope": scope_name}
    return out


def project_caller(api: ApiCaller) -> ProjectCaller:
    return ProjectCaller(user=api.user, kind="api_key", key_id=api.key.id)


def carry(out, response: Response):
    """An answer built as a Response (idempotency replays) keeps the key's
    X-RateLimit-* headers."""
    if isinstance(out, Response):
        for name in RATE_HEADERS:
            if name in response.headers:
                out.headers[name] = response.headers[name]
    return out
