"""Developer API key management (session-authenticated)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..billing.service import effective_plan
from ..database import get_db
from ..deps import get_current_user
from ..models import ApiKey, User
from ..plans import get_plan
from ..schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from ..security import generate_api_key

router = APIRouter(prefix="/keys", tags=["api keys"])


@router.get("", response_model=list[ApiKeyOut])
def list_keys(
    current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ApiKey]:
    return list(
        db.scalars(
            select(ApiKey)
            # PF8: supplier feed keys are managed in the supplier portal.
            .where(ApiKey.user_id == current.id, ApiKey.supplier_id.is_(None))
            .order_by(ApiKey.revoked_at.is_not(None), ApiKey.created_at.desc())
        )
    )


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: ApiKeyCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    plan = get_plan(effective_plan(db, current))
    active = db.scalar(
        select(func.count(ApiKey.id)).where(
            ApiKey.user_id == current.id, ApiKey.revoked_at.is_(None), ApiKey.supplier_id.is_(None)
        )
    )
    if (active or 0) >= plan.max_api_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"The {plan.name} plan allows {plan.max_api_keys} active keys. "
                "Revoke one or upgrade your plan."
            ),
        )
    full, prefix, digest = generate_api_key()
    key = ApiKey(user_id=current.id, name=payload.name.strip(), prefix=prefix, key_hash=digest)
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyCreated(**ApiKeyOut.model_validate(key).model_dump(), key=full)


@router.delete("/{key_id}", response_model=ApiKeyOut)
def revoke_key(
    key_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKey:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != current.id or key.supplier_id is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(key)
    return key
