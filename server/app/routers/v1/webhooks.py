"""Webhook endpoints (PF12): `/v1/webhooks…` for API keys with
`webhooks:manage`, and `/webhooks…` for the website's dashboard (a session),
which may also reveal a secret. Both call `app/webhooks/endpoints.py`.

A secret is shown when the endpoint is made and when it is rotated.
"""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ...contract_http import enveloped
from ...database import get_db
from ...deps import ApiCaller, get_current_user
from ...models import User
from ...webhooks import endpoints as svc
from ...webhooks import jobs as _jobs  # noqa: F401  (webhooks.* jobs and the event sources)
from . import models as m
from .common import doc, scope

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
dashboard = APIRouter(prefix="/webhooks", tags=["webhooks"], dependencies=[enveloped()], include_in_schema=False)

Manage = scope("webhooks:manage")
STATUS = Query(default=None, pattern="^(pending|succeeded|failed|cancelled)$")


class WebhookCreate(svc.EndpointIn):
    """A receiver: an https URL and the events it wants."""


class WebhookUpdate(svc.EndpointPatch):
    """Change the URL, the events, the description, or switch it off and on."""


# --- /v1/webhooks (API keys) ------------------------------------------------------------------


@router.get("", operation_id="webhooks_list", **doc("webhooks:manage", m.WebhookEndpointList))
def list_endpoints(api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """The account's endpoints and the events they can subscribe to."""
    return svc.list_json(db, api.user.id)


@router.post("", status_code=201, operation_id="webhooks_create", **doc("webhooks:manage", m.WebhookEndpointWithSecret, 201))
def create_endpoint(body: WebhookCreate, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """Register an endpoint; the answer carries its signing secret, once."""
    return svc.create(db, api.user.id, body)


@router.patch("/{endpoint_id}", operation_id="webhooks_update", **doc("webhooks:manage", m.WebhookEndpoint))
def update_endpoint(endpoint_id: str, body: WebhookUpdate, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """Change an endpoint; `active: true` switches a disabled one back on."""
    return svc.update(db, api.user.id, endpoint_id, body)


@router.delete("/{endpoint_id}", status_code=204, operation_id="webhooks_delete", **doc("webhooks:manage"))
def delete_endpoint(endpoint_id: str, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> Response:
    """Delete an endpoint and its delivery log."""
    svc.remove(db, api.user.id, endpoint_id)
    return Response(status_code=204)


@router.get("/{endpoint_id}/deliveries", operation_id="webhooks_deliveries", **doc("webhooks:manage", m.WebhookDeliveryList))
def list_deliveries(
    endpoint_id: str,
    status: str | None = STATUS,
    limit: int = Query(default=50, ge=1, le=svc.PAGE_MAX),
    api: ApiCaller = Manage,
    db: Session = Depends(get_db),
) -> dict:
    """The delivery log, newest first: one row per attempt."""
    return svc.deliveries(db, api.user.id, endpoint_id, status=status, limit=limit)


@router.post(
    "/{endpoint_id}/deliveries/{delivery_id}/resend",
    status_code=201,
    operation_id="webhooks_resend",
    **doc("webhooks:manage", m.WebhookDelivery, 201, errors=(401, 403, 404, 409, 429)),
)
def resend(endpoint_id: str, delivery_id: str, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """Send a delivery's event again now (one attempt)."""
    return svc.resend(db, api.user.id, endpoint_id, delivery_id)


@router.post("/{endpoint_id}/secret/rotate", operation_id="webhooks_rotate_secret", **doc("webhooks:manage", m.WebhookSecret))
def rotate(endpoint_id: str, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """A new signing secret, shown once; the old one stops signing at once."""
    return svc.rotate(db, api.user.id, endpoint_id)


@router.post("/{endpoint_id}/test", status_code=201, operation_id="webhooks_test", **doc("webhooks:manage", m.WebhookDelivery, 201, errors=(401, 403, 404, 409, 429)))
def test_event(endpoint_id: str, api: ApiCaller = Manage, db: Session = Depends(get_db)) -> dict:
    """Queue a `webhook.test` event for this endpoint now."""
    return svc.send_test(db, api.user.id, endpoint_id)


# --- /webhooks (the dashboard, a session) -----------------------------------------------------


@dashboard.get("")
def dash_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    out = svc.list_json(db, user.id)
    from ...webhooks.events import DESCRIPTIONS

    out["descriptions"] = DESCRIPTIONS
    return out


@dashboard.post("", status_code=201)
def dash_create(body: WebhookCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return svc.create(db, user.id, body)


@dashboard.patch("/{endpoint_id}")
def dash_update(endpoint_id: str, body: WebhookUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return svc.update(db, user.id, endpoint_id, body)


@dashboard.delete("/{endpoint_id}", status_code=204)
def dash_delete(endpoint_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    svc.remove(db, user.id, endpoint_id)
    return Response(status_code=204)


@dashboard.get("/{endpoint_id}/deliveries")
def dash_deliveries(
    endpoint_id: str,
    status: str | None = STATUS,
    limit: int = Query(default=50, ge=1, le=svc.PAGE_MAX),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return svc.deliveries(db, user.id, endpoint_id, status=status, limit=limit)


@dashboard.post("/{endpoint_id}/deliveries/{delivery_id}/resend", status_code=201)
def dash_resend(endpoint_id: str, delivery_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return svc.resend(db, user.id, endpoint_id, delivery_id)


@dashboard.post("/{endpoint_id}/secret/rotate")
def dash_rotate(endpoint_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return svc.rotate(db, user.id, endpoint_id)


@dashboard.get("/{endpoint_id}/secret")
def dash_reveal(endpoint_id: str, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return svc.reveal(db, user.id, endpoint_id)


@dashboard.post("/{endpoint_id}/test", status_code=201)
def dash_test(endpoint_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return svc.send_test(db, user.id, endpoint_id)
