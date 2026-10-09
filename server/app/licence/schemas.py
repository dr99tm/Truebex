"""Request bodies of the licence API (contract §5). Unknown keys are ignored."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .links import normalise_code

# sha256 hex made by the app (contract §6.2).
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
AppVersion = Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+-]+$")]
DeviceName = Annotated[str, Field(min_length=1, max_length=100)]
Id32 = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class LinkStart(_Body):
    device_name: DeviceName
    fingerprint: Fingerprint
    app_version: AppVersion


class LinkPoll(_Body):
    poll_secret: Annotated[str, Field(min_length=16, max_length=128)]


class LinkApprove(_Body):
    link_code: Annotated[str, Field(max_length=16)]
    approve: bool = True

    @field_validator("link_code")
    @classmethod
    def _code(cls, v: str) -> str:
        code = normalise_code(v)
        if code is None:
            raise ValueError("a link code is 8 characters like QX7D-K9MP")
        return code


class Activate(_Body):
    fingerprint: Fingerprint
    device_name: DeviceName
    os: Annotated[str, Field(max_length=100)] = ""
    app_version: AppVersion
    replace_device_id: Id32 | None = None


class EntitlementRequest(_Body):
    fingerprint: Fingerprint
    app_version: AppVersion | None = None


class TrialRequest(_Body):
    plan: Literal["pro"] = "pro"
