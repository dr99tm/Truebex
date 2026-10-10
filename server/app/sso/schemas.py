"""Request bodies of the SSO routes. Unknown keys are ignored."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class SsoSettings(_Body):
    kind: Literal["oidc", "saml"]
    # OIDC
    issuer: Annotated[str, Field(max_length=512)] | None = None
    client_id: Annotated[str, Field(max_length=256)] | None = None
    # Write-only: empty keeps the stored secret.
    client_secret: Annotated[str, Field(max_length=2048)] | None = None
    # SAML: the IdP metadata, or the three values by hand.
    idp_metadata_xml: Annotated[str, Field(max_length=200_000)] | None = None
    idp_entity_id: Annotated[str, Field(max_length=512)] | None = None
    idp_sso_url: Annotated[str, Field(max_length=1024)] | None = None
    idp_cert_pem: Annotated[str, Field(max_length=20_000)] | None = None
    enabled: bool = True
    required: bool = False


class DomainAdd(_Body):
    domain: Annotated[str, Field(min_length=3, max_length=253)]
