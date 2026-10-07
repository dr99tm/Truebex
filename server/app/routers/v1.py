"""The public developer API, authenticated and metered by API key.

These endpoints are the starting surface for integrations; product
endpoints (projects, assets, exports) get added here as they ship.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..billing.service import effective_plan
from ..database import get_db
from ..deps import ApiCaller, api_key_auth
from ..plans import get_plan
from ..usage import used_this_month

router = APIRouter(prefix="/v1", tags=["developer api"])


@router.get("/ping")
def ping(caller: ApiCaller = Depends(api_key_auth)) -> dict:
    """Check that a key works. Counts toward usage like any call."""
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@router.get("/account")
def account(
    caller: ApiCaller = Depends(api_key_auth), db: Session = Depends(get_db)
) -> dict:
    """The key's owner, plan, and this month's usage."""
    plan = get_plan(effective_plan(db, caller.user))
    used = used_this_month(db, caller.user.id)
    return {
        "email": caller.user.email,
        "plan": plan.id,
        "key": {"id": caller.key.id, "name": caller.key.name, "prefix": caller.key.prefix},
        "usage": {
            "used": used,
            "limit": plan.monthly_requests,
            "remaining": max(plan.monthly_requests - used, 0),
        },
    }
