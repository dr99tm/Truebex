"""Webhook endpoints as their account manages them (PF12): register, list,
change, delete, the delivery log, re-send, rotate and (website only) reveal
the secret, and a test event."""

import secrets

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..contract_http import ContractError
from ..licence import clock
from . import events, signing, urls
from .models import WebhookDelivery, WebhookEndpoint

MAX_ENDPOINTS = 10
PAGE_MAX = 100


class EndpointIn(BaseModel):
    url: str = Field(min_length=1, max_length=urls.MAX_URL)
    events: list[str] = Field(min_length=1, max_length=len(events.EVENT_TYPES))
    description: str = Field(default="", max_length=200)


class EndpointPatch(BaseModel):
    url: str | None = Field(default=None, min_length=1, max_length=urls.MAX_URL)
    events: list[str] | None = Field(default=None, min_length=1, max_length=len(events.EVENT_TYPES))
    description: str | None = Field(default=None, max_length=200)
    active: bool | None = None


def _not_found(what: str = "webhook endpoint") -> ContractError:
    return ContractError("not_found", 404, f"No such {what}.")


def _event_list(values: list[str]) -> list[str]:
    unknown = [v for v in values if v not in events.EVENT_TYPES]
    if unknown:
        raise ContractError(
            "validation_failed",
            422,
            f"events: unknown event {unknown[0]!r}.",
            {"fields": [{"field": "events", "in": "body", "message": f"one or more of {', '.join(events.EVENT_TYPES)}"}]},
        )
    return [e for e in events.EVENT_TYPES if e in values]


def own(db: Session, account_id: int, endpoint_id: str) -> WebhookEndpoint:
    row = db.get(WebhookEndpoint, endpoint_id) if isinstance(endpoint_id, str) and len(endpoint_id) == 32 else None
    if row is None or row.account_id != account_id:
        raise _not_found()
    return row


def delivery_json(d: WebhookDelivery) -> dict:
    return {
        "delivery_id": d.delivery_id,
        "endpoint_id": d.endpoint_id,
        "event_id": d.event_id,
        "event_type": d.event.type if d.event is not None else None,
        "attempt": d.attempt,
        "status": "pending" if d.status == "sending" else d.status,
        "next_attempt_at": clock.rfc3339(d.next_attempt_at),
        "response_code": d.response_code,
        "response_ms": d.response_ms,
        "error": d.error,
        "delivered_at": clock.rfc3339(d.delivered_at),
        "created_at": clock.rfc3339(d.created_at),
        "manual": bool(d.manual),
    }


def endpoint_json(db: Session, e: WebhookEndpoint, *, secret: str | None = None) -> dict:
    last = db.scalars(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == e.endpoint_id, WebhookDelivery.status.in_(("succeeded", "failed")))
        .order_by(WebhookDelivery.created_at.desc())
        .limit(1)
    ).first()
    out = {
        "endpoint_id": e.endpoint_id,
        "url": e.url,
        "events": list(e.events or []),
        "active": bool(e.active),
        "description": e.description or "",
        "failing_since": clock.rfc3339(e.failing_since),
        "disabled_reason": e.disabled_reason,
        "created_at": clock.rfc3339(e.created_at),
        "last_delivery": delivery_json(last) if last is not None else None,
    }
    if secret is not None:
        out["secret"] = secret
    return out


def list_json(db: Session, account_id: int) -> dict:
    rows = db.scalars(
        select(WebhookEndpoint).where(WebhookEndpoint.account_id == account_id).order_by(WebhookEndpoint.created_at)
    ).all()
    return {"endpoints": [endpoint_json(db, e) for e in rows], "events": list(events.EVENT_TYPES)}


def create(db: Session, account_id: int, body: EndpointIn) -> dict:
    count = db.scalar(select(func.count()).select_from(WebhookEndpoint).where(WebhookEndpoint.account_id == account_id)) or 0
    if count >= MAX_ENDPOINTS:
        raise ContractError(
            "quota_exceeded", 403, f"An account has at most {MAX_ENDPOINTS} webhook endpoints.", {"limit": MAX_ENDPOINTS, "used": count}
        )
    url = urls.check_or_422(body.url)
    chosen = _event_list(body.events)
    secret = signing.new_secret()
    now = clock.now()
    row = WebhookEndpoint(
        endpoint_id=secrets.token_hex(16),
        account_id=account_id,
        url=url,
        description=body.description.strip(),
        secret_enc=signing.seal(secret),
        events=chosen,
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    return endpoint_json(db, row, secret=secret)


def update(db: Session, account_id: int, endpoint_id: str, body: EndpointPatch) -> dict:
    row = own(db, account_id, endpoint_id)
    if body.url is not None:
        row.url = urls.check_or_422(body.url)
    if body.events is not None:
        row.events = _event_list(body.events)
    if body.description is not None:
        row.description = body.description.strip()
    if body.active is not None and body.active != row.active:
        row.active = body.active
        if body.active:  # switched back on: a fresh start
            row.failing_since = None
            row.disabled_at = None
            row.disabled_reason = None
        else:
            row.disabled_at = clock.now()
            row.disabled_reason = "owner"
    row.updated_at = clock.now()
    db.commit()
    return endpoint_json(db, row)


def remove(db: Session, account_id: int, endpoint_id: str) -> None:
    row = own(db, account_id, endpoint_id)
    db.delete(row)
    db.commit()


def deliveries(db: Session, account_id: int, endpoint_id: str, *, status: str | None = None, limit: int = 50) -> dict:
    own(db, account_id, endpoint_id)
    q = select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint_id)
    if status == "pending":
        q = q.where(WebhookDelivery.status.in_(("pending", "sending")))
    elif status:
        q = q.where(WebhookDelivery.status == status)
    rows = db.scalars(q.order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.attempt.desc()).limit(min(max(limit, 1), PAGE_MAX)))
    return {"deliveries": [delivery_json(d) for d in rows.unique()]}


def resend(db: Session, account_id: int, endpoint_id: str, delivery_id: str) -> dict:
    row = own(db, account_id, endpoint_id)
    old = db.get(WebhookDelivery, delivery_id) if isinstance(delivery_id, str) else None
    if old is None or old.endpoint_id != row.endpoint_id:
        raise _not_found("delivery")
    if not row.active:
        raise ContractError("endpoint_disabled", 409, "This endpoint is switched off. Switch it on to send to it.")
    now = clock.now()
    d = WebhookDelivery(
        delivery_id=secrets.token_hex(16),
        endpoint_id=row.endpoint_id,
        event_id=old.event_id,
        attempt=1,
        status="pending",
        next_attempt_at=now,
        manual=True,
        created_at=now,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return delivery_json(d)


def rotate(db: Session, account_id: int, endpoint_id: str) -> dict:
    row = own(db, account_id, endpoint_id)
    secret = signing.new_secret()
    row.secret_enc = signing.seal(secret)
    row.updated_at = clock.now()
    db.commit()
    return {"endpoint_id": row.endpoint_id, "secret": secret}


def reveal(db: Session, account_id: int, endpoint_id: str) -> dict:
    row = own(db, account_id, endpoint_id)
    secret = signing.unseal(row.secret_enc)
    if secret is None:
        raise ContractError("secret_unreadable", 409, "This secret can no longer be read. Rotate it to get a new one.")
    return {"endpoint_id": row.endpoint_id, "secret": secret}


def send_test(db: Session, account_id: int, endpoint_id: str) -> dict:
    row = own(db, account_id, endpoint_id)
    if not row.active:
        raise ContractError("endpoint_disabled", 409, "This endpoint is switched off. Switch it on to send to it.")
    now = clock.now()
    made = events.emit(
        db, [account_id], events.TEST_EVENT, {"endpoint_id": row.endpoint_id, "message": "A test event from Truebex."},
        now=now, endpoints=[row],
    )
    d = db.scalars(select(WebhookDelivery).where(WebhookDelivery.event_id == made[0].event_id)).first()
    return delivery_json(d)
