"""Pydantic request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
    plan: str


class BillingActivate(BaseModel):
    # The Gammal Tech payment id, already verified client-side via the SDK.
    payment_id: str = Field(min_length=1, max_length=128)
    plan: str = Field(default="pro", max_length=32)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
