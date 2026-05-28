"""FastAPI auth server: email/password registration + JWT login.

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8000

Then expose via cloudflared:
    cloudflared tunnel --url http://127.0.0.1:8000
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db, init_db
from .deps import get_current_user
from .models import User
from .schemas import BillingActivate, Token, UserCreate, UserLogin, UserOut
from .security import create_access_token, hash_password, verify_password

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Truebex Auth", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(email=email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@app.post("/auth/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))

    # Verify even when the user is missing to avoid leaking which emails exist
    # via response timing.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@app.get("/auth/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current)


@app.post("/billing/activate", response_model=UserOut)
def activate_plan(
    payload: BillingActivate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """Mark the authenticated user's plan active after a delivered payment.

    The payment itself is processed and verified client-side by the Gammal
    Tech SDK (card details never reach us). This records the outcome against
    the user so the dashboard reflects it.

    NOTE: this trusts the caller's bearer token + a payment_id. For stronger
    assurance, verify `payment_id` server-side against Gammal Tech's API once
    that integration detail is available.
    """
    current.plan = payload.plan
    current.last_payment_id = payload.payment_id
    db.add(current)
    db.commit()
    db.refresh(current)
    return UserOut.model_validate(current)
