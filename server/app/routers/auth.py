"""Account endpoints: email/password, Google Sign-In, password reset by
e-mail (app/password_reset.py), and the current user."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import mail, password_reset, ratelimit
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..licence import clock
from ..models import User
from ..ratelimit import client_ip, limit
from ..schemas import ForgotPassword, GoogleLogin, ResetPassword, Token, UserCreate, UserLogin, UserOut
from ..security import create_access_token, hash_password, verify_password
from ..sso import service as sso  # PF3: the "SSO required" policy
from ..users import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _token_for(user: User) -> Token:
    return Token(access_token=create_access_token(str(user.id)), user=user_out(user))


class EmailTaken(Exception):
    """An account with this address already exists."""


def create_account(
    db: Session,
    email: str,
    password: str,
    *,
    name: str | None = None,
    email_verified_at: datetime | None = None,
) -> User:
    """A password account for `email` (lower-case). Raises `sso.use_sso` (403)
    for a domain whose organisation requires SSO and `EmailTaken` when the
    address has an account. /auth/register and the support API's /register
    (which passes `email_verified_at`) both make accounts here."""
    # PF3: addresses of an organisation that requires SSO sign up through it.
    required = sso.required_org(db, email)
    if required is not None:
        raise sso.use_sso(required, status.HTTP_403_FORBIDDEN)
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise EmailTaken(email)
    user = User(
        email=email, hashed_password=hash_password(password), name=name, email_verified_at=email_verified_at
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # the same address registered a moment earlier
        db.rollback()
        raise EmailTaken(email)
    db.refresh(user)
    return user


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    try:
        user = create_account(db, payload.email.lower(), payload.password)
    except EmailTaken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    return _token_for(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    # PF3: an organisation that requires SSO refuses passwords for its domains;
    # its owners keep a one-time break-glass code.
    required = sso.required_org(db, email)
    if required is not None and not payload.break_glass_code:
        raise sso.use_sso(required)
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
    if required is not None:
        from ..licence import clock

        sso.use_break_glass(db, required, user, payload.break_glass_code, clock.now())
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

    # PF3: an organisation that requires SSO refuses Google for its domains.
    required = sso.required_org(db, email)
    if required is not None:
        raise sso.use_sso(required)

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

    from ..licence.service import ensure_author_id

    effective_plan(db, current)  # expire lapsed plans before reporting
    ensure_author_id(db, current)  # PF9: the web client's operations carry it
    return user_out(current)


# --- password reset by e-mail ---------------------------------------------------------------

# Links asked for per address and in all (a sensible ceiling on mail), per hour.
FORGOT_PER_EMAIL = (5, 5)  # (per hour, burst)
FORGOT_ALL = (300, 100)


@router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[limit(client_ip, per_minute=20 / 60, burst=10, name="auth.forgot.ip")],
)
def forgot_password(
    payload: ForgotPassword, background: BackgroundTasks, db: Session = Depends(get_db)
) -> dict:
    """Mail a one-time reset link when the address has an account. The answer
    (and its timing: the mail goes in the background) is the same either way."""
    email = payload.email.lower()
    ratelimit.check(f"auth.forgot.email:{email}", per_minute=FORGOT_PER_EMAIL[0] / 60, burst=FORGOT_PER_EMAIL[1])
    ratelimit.check("auth.forgot.all", per_minute=FORGOT_ALL[0] / 60, burst=FORGOT_ALL[1])
    values = password_reset.request_reset(db, email, clock.now())
    if values is not None:
        background.add_task(mail.try_send, email, "password_reset", values)
    return {"status": "accepted"}


@router.post(
    "/password/reset",
    response_model=Token,
    dependencies=[limit(client_ip, per_minute=20 / 60, burst=10, name="auth.reset.ip")],
)
def reset_password(payload: ResetPassword, db: Session = Depends(get_db)) -> Token:
    """Set a new password with a link's token, and sign in. 410
    `reset_link_invalid` for an unknown, spent or expired link; 403
    `sso_required` when the domain's organisation requires SSO. Sessions
    signed before stay valid until they expire (24 h)."""
    user = password_reset.reset(db, payload.token, payload.password, clock.now())
    return _token_for(user)
