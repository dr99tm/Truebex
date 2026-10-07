"""Helpers for turning User rows into API responses."""

from .models import User
from .schemas import UserOut


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        plan=user.plan,
        name=user.name,
        avatar_url=user.avatar_url,
        has_password=bool(user.hashed_password),
        google_linked=user.google_sub is not None,
    )
