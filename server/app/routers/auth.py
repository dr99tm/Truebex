"""Account endpoints: email/password, Google Sign-In, and the current user."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import GoogleLogin, Token, UserCreate, UserLogin, UserOut
from ..security import create_access_token, hash_password, verify_password
from ..users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _token_for(user: User) -> Token:
    return Token(access_token=create_access_token(str(user.id)), user=user_out(user))


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google sign-in. Continue with Google.",
        )
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    return _token_for(user)


def verify_google_credential(credential: str) -> dict[str, Any]:
    """Verify a Google ID token's signature, issuer, audience and expiry.

    Raises ValueError when the token is not valid for our client id.
    """
    # Imported lazily so the server starts even without google-auth installed.
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )


@router.post("/google", response_model=Token)
def google_login(payload: GoogleLogin, db: Session = Depends(get_db)) -> Token:
    """Sign in or sign up with a Google ID token from Google Identity Services.

    - Known Google account → sign in.
    - Email already registered with a password → link Google to it.
    - Otherwise → create a new account with no password.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured.",
        )
    try:
        info = verify_google_credential(payload.credential)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google sign-in failed. Please try again.",
        )

    sub = str(info.get("sub") or "")
    email = str(info.get("email") or "").lower()
    if not sub or not email or not info.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Google account has no verified email address.",
        )

    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, hashed_password="")
        user.google_sub = sub
    # Keep profile details fresh on every sign-in.
    user.name = info.get("name") or user.name
    user.avatar_url = info.get("picture") or user.avatar_url
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token_for(user)


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    from ..billing.service import effective_plan

    effective_plan(db, current)  # expire lapsed plans before reporting
    return user_out(current)
