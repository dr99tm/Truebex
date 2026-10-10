"""Request bodies of the organisation routes. Unknown keys are ignored."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Name = Annotated[str, Field(min_length=1, max_length=100)]
Role = Literal["owner", "admin", "billing", "member"]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class OrgCreate(_Body):
    name: Name


class OrgRename(_Body):
    name: Name


class RoleChange(_Body):
    role: Role


class InviteCreate(_Body):
    email: EmailStr
    role: Role = "member"
    seat: Literal["named", "floating", "none"] = "none"


class InviteToken(_Body):
    token: Annotated[str, Field(min_length=16, max_length=128)]


class SeatSettings(_Body):
    floating: Annotated[int, Field(ge=0, le=100_000)]


class SeatChange(_Body):
    kind: Literal["named", "floating", "none"]
