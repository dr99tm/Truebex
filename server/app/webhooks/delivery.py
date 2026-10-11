"""Sending webhook deliveries (PF12), on the Standard Webhooks retry schedule:
immediately, 5 s, 5 min, 30 min, 2 h, 5 h, 10 h, 14 h, 20 h, 24 h (with ±10 %
jitter). A 2xx answer within WEBHOOKS_TIMEOUT_S (15 s) is a success; anything
else, a redirect included, is a failure and schedules the next attempt. An
endpoint failing for five days is disabled by `disable_failing`, which mails
its account once.
"""

import json
import logging
import random
import secrets
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import SessionLocal
from ..licence import clock
from ..models import User
from . import signing, urls
from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent

log = logging.getLogger("truebex.webhooks")

# Seconds after the previous attempt, for attempts 2..10 (attempt 1 is immediate).
SCHEDULE_S: tuple[int, ...] = (0, 5, 5 * 60, 30 * 60, 2 * 3600, 5 * 3600, 10 * 3600, 14 * 3600, 20 * 3600, 24 * 3600)
JITTER = 0.1
DISABLE_AFTER = timedelta(days=5)
KEEP = timedelta(days=30)
# Deliveries sent at once, and the longest one run of deliver_due keeps going.
PARALLEL = 8
RUN_BUDGET_S = 30.0
# A delivery claimed by a runner that died mid-send goes back to pending.
STUCK_AFTER = timedelta(minutes=5)
USER_AGENT = "Truebex-Webhooks/1"


def delay_before(attempt: int, *, rng: Callable[[], float] = random.random) -> timedelta:
    """The wait before `attempt` (2..10), jittered ±10 %."""
    base = SCHEDULE_S[attempt - 1]
    return timedelta(seconds=base * (1 + JITTER * (2 * rng() - 1)))


def client_factory() -> httpx.Client:
    """Patched in tests (an httpx.MockTransport)."""
    return httpx.Client(timeout=get_settings().webhooks_timeout_s, follow_redirects=False)


def body_of(event: WebhookEvent) -> bytes:
    return json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _post(endpoint: WebhookEndpoint, event: WebhookEvent, secret: str, now: datetime) -> tuple[int | None, int, str | None]:
    """(status code or None, milliseconds, error)."""
    host = (urlsplit(endpoint.url).hostname or "").lower()
    try:
        urls.check(endpoint.url)  # again at each delivery: DNS may point elsewhere now
    except urls.UrlRefused as exc:
        return None, 0, f"refused: {exc}"[:200]
    body = body_of(event)
    headers = {
        "content-type": "application/json",
        "user-agent": USER_AGENT,
        **signing.headers(secret, event.event_id, int(now.timestamp()), body),
    }
    started = time.monotonic()
    try:
        with client_factory() as client:
            res = client.post(endpoint.url, content=body, headers=headers)
        ms = int((time.monotonic() - started) * 1000)
        return res.status_code, ms, None if 200 <= res.status_code < 300 else f"HTTP {res.status_code}"
    except httpx.TimeoutException:
        return None, int((time.monotonic() - started) * 1000), "timed out"
    except httpx.HTTPError as exc:
        log.info("webhook to %s failed: %s", host, type(exc).__name__)
        return None, int((time.monotonic() - started) * 1000), f"connection failed ({type(exc).__name__})"


def send(db: Session, d: WebhookDelivery, now: datetime) -> bool:
    """One attempt. Records it, schedules the next on failure; commits."""
    endpoint, event = d.endpoint, d.event
    if not endpoint.active:
        d.status = "cancelled"
        d.next_attempt_at = None
        db.commit()
        return False
    secret = signing.unseal(endpoint.secret_enc)
    if secret is None:
        code, ms, error = None, 0, "the signing secret cannot be read: rotate it"
    else:
        code, ms, error = _post(endpoint, event, secret, now)
    ok = error is None and code is not None and 200 <= code < 300
    d.status = "succeeded" if ok else "failed"
    d.response_code = code
    d.response_ms = ms
    d.error = error
    d.next_attempt_at = None
    if ok:
        d.delivered_at = now
        endpoint.failing_since = None
    else:
        endpoint.failing_since = endpoint.failing_since or now
        if not d.manual and d.attempt < len(SCHEDULE_S):
            db.add(
                WebhookDelivery(
                    delivery_id=secrets.token_hex(16),
                    endpoint_id=endpoint.endpoint_id,
                    event_id=event.event_id,
                    attempt=d.attempt + 1,
                    status="pending",
                    next_attempt_at=now + delay_before(d.attempt + 1),
                    created_at=now,
                )
            )
    db.commit()
    return ok


def _claim(db: Session, now: datetime, limit: int) -> list[str]:
    """Mark up to `limit` due deliveries `sending` (a second runner skips them)."""
    ids = list(
        db.scalars(
            select(WebhookDelivery.delivery_id)
            .where(WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.next_attempt_at)
            .limit(limit)
        )
    )
    claimed = [
        delivery_id
        for delivery_id in ids
        if db.execute(
            update(WebhookDelivery)
            .where(WebhookDelivery.delivery_id == delivery_id, WebhookDelivery.status == "pending")
            .values(status="sending")
        ).rowcount
    ]
    db.commit()
    return claimed


def _send_one(delivery_id: str, now: datetime) -> bool:
    with SessionLocal() as db:
        d = db.get(WebhookDelivery, delivery_id)
        if d is None:
            return False
        try:
            return send(db, d, now)
        except Exception:  # noqa: BLE001 - one bad endpoint must not stop the rest
            db.rollback()
            log.exception("webhook delivery %s", delivery_id)
            db.execute(
                update(WebhookDelivery)
                .where(WebhookDelivery.delivery_id == delivery_id)
                .values(status="failed", error="internal error", next_attempt_at=None)
            )
            db.commit()
            return False


def deliver_due(db: Session, now: datetime | None = None) -> int:
    """Send due deliveries, oldest first, PARALLEL at a time, for at most
    RUN_BUDGET_S (the rest wait for the next run), so a slow receiver never
    holds up the other background jobs. Returns how many succeeded."""
    now = now or clock.now()
    db.execute(
        update(WebhookDelivery)
        .where(WebhookDelivery.status == "sending", WebhookDelivery.next_attempt_at <= now - STUCK_AFTER)
        .values(status="pending")
    )
    db.commit()
    started = time.monotonic()
    sent = 0
    with ThreadPoolExecutor(max_workers=PARALLEL, thread_name_prefix="webhooks") as pool:
        while time.monotonic() - started < RUN_BUDGET_S:
            batch = _claim(db, now, PARALLEL)
            if not batch:
                break
            sent += sum(pool.map(lambda delivery_id: _send_one(delivery_id, now), batch))
    return sent


def disable_failing(db: Session, now: datetime | None = None) -> int:
    """Endpoints failing for five days → inactive, pending deliveries cancelled,
    one e-mail to the account."""
    from .. import mail

    now = now or clock.now()
    rows = db.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.active.is_(True),
            WebhookEndpoint.failing_since.is_not(None),
            WebhookEndpoint.failing_since <= now - DISABLE_AFTER,
        )
    ).all()
    for endpoint in rows:
        endpoint.active = False
        endpoint.disabled_at = now
        endpoint.disabled_reason = "failing"
        endpoint.updated_at = now
        db.execute(
            update(WebhookDelivery)
            .where(WebhookDelivery.endpoint_id == endpoint.endpoint_id, WebhookDelivery.status == "pending")
            .values(status="cancelled", next_attempt_at=None)
        )
        db.commit()
        user = db.get(User, endpoint.account_id)
        if user is not None:
            site = get_settings().site_url.rstrip("/")
            mail.try_send(
                user.email,
                "webhook_disabled",
                {
                    "url": endpoint.url,
                    "since": clock.rfc3339(endpoint.failing_since),
                    "webhooks_url": f"{site}/dashboard/webhooks/",
                },
            )
    return len(rows)


def purge(db: Session, now: datetime | None = None) -> int:
    """Events (and their deliveries) older than 30 days."""
    now = now or clock.now()
    old = select(WebhookEvent.event_id).where(WebhookEvent.created_at < now - KEEP)
    db.execute(delete(WebhookDelivery).where(WebhookDelivery.event_id.in_(old)))
    res = db.execute(delete(WebhookEvent).where(WebhookEvent.created_at < now - KEEP))
    db.commit()
    return res.rowcount or 0
