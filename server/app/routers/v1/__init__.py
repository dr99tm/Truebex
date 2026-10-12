"""The public developer API, authenticated and metered by API key (PF12).

* `/v1/ping`, `/v1/account`: check a key; its owner, plan, scopes and usage.
* `/v1/projects…` (project-log 5.1-5.18, and the followed panorama sets of
  PF9, PF12a), `/v1/jobs…` (render-jobs 5.1-5.6), `/v1/uploads…` and
  `/v1/shares…` (share-bundle 5.1-5.9): the contract routes for API keys,
  through the contract routers' own handlers.
* `/v1/webhooks…`: endpoints, deliveries, re-send, secrets.

The marketplace reads (`/market/…` 5.1-5.6, a key lifts the anonymous limit)
and the supplier feeds (`/market/feeds…`, `supplier:feed`) are part of the
developer API too; they live in PF7's and PF8's routers. Every key call counts
toward the monthly quota and the per-key burst limit; a route group needs its
scope (app/scopes.py). Errors use the shared envelope. `install(app)` (main.py)
adds the dashboard's `/webhooks` routes and the shapes the document names
without a route of their own.
"""

from fastapi import APIRouter, Depends, FastAPI
from pydantic.json_schema import models_json_schema
from sqlalchemy.orm import Session

from ...billing.service import effective_plan
from ...contract_http import enveloped
from ...database import get_db
from ...deps import ApiCaller, api_key_auth
from ...licence import clock
from ...plans import get_plan
from ...scopes import author_for_key
from ...usage import used_this_month
from . import jobs, models, projects, shares, webhooks
from .common import doc

router = APIRouter(prefix="/v1", tags=["developer api"], dependencies=[enveloped()])


@router.get("/ping", operation_id="account_ping", **doc(None, models.Ping, errors=(401, 429)))
def ping(caller: ApiCaller = Depends(api_key_auth)) -> dict:
    """Check that a key works. Counts toward usage like any call."""
    return {"ok": True, "time": clock.rfc3339(clock.now())}


@router.get("/account", operation_id="account_get", **doc(None, models.Account, errors=(401, 429)))
def account(
    caller: ApiCaller = Depends(api_key_auth), db: Session = Depends(get_db)
) -> dict:
    """The key's owner, plan, scopes and this month's usage."""
    plan = get_plan(effective_plan(db, caller.user))
    used = used_this_month(db, caller.user.id)
    return {
        "email": caller.user.email,
        "plan": plan.id,
        "key": {
            "id": caller.key.id,
            "name": caller.key.name,
            "prefix": caller.key.prefix,
            "scopes": list(caller.scopes),
            "author": author_for_key(caller.key.id),
        },
        "usage": {
            "used": used,
            "limit": plan.monthly_requests,
            "remaining": max(plan.monthly_requests - used, 0),
        },
    }


router.include_router(projects.router)
router.include_router(jobs.router)
router.include_router(shares.router)
router.include_router(webhooks.router)

# Bodies the routes read raw (so the contracts' own 413 and 422 answers stay
# theirs): documented by reference, defined here.
EXTRA_SCHEMAS = (models.PushRequest, models.JobRequest)


def install(app: FastAPI) -> None:
    """main.py: the dashboard's webhook routes, and the extra shapes in the app's OpenAPI document."""
    app.include_router(webhooks.dashboard)
    base = app.openapi

    def openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        schema = base()
        _, defs = models_json_schema(
            [(model, "validation") for model in EXTRA_SCHEMAS], ref_template="#/components/schemas/{model}"
        )
        target = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, body in defs.get("$defs", {}).items():
            target.setdefault(name, body)
        return schema

    app.openapi = openapi
