"""OpenID Connect sign-in (Core 1.0, authorization code flow with RFC 7636
PKCE S256): discovery and JWKS from the issuer (cached 1 h, a new key id
refetches once), `state` and `nonce` per sign-in, the ID token checked for
signature, `iss`, `aud` (and `azp`), `exp`, `nonce` and `email_verified`.
"""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlsplit

import httpx
from jose import jwt
from jose.exceptions import JOSEError

from ..config import get_settings
from ..contract_http import ContractError

ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"]
CACHE_TTL_S = 3600
LEEWAY_S = 120
_discovery: dict[str, tuple[float, dict]] = {}
_jwks: dict[str, tuple[float, dict]] = {}


def http_client() -> httpx.Client:
    """The client for calls to identity providers (tests swap in the mock)."""
    return httpx.Client(timeout=10.0, follow_redirects=False)


def clear_caches() -> None:
    _discovery.clear()
    _jwks.clear()


def fail(detail: str) -> ContractError:
    return ContractError("sso_failed", 401, detail)


def normalise_issuer(url: str) -> str:
    return (url or "").strip().rstrip("/")


def issuer_is_acceptable(url: str) -> bool:
    """https, or plain http to this computer (the local mock provider)."""
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return True
    return parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")


def discover(issuer: str) -> dict:
    issuer = normalise_issuer(issuer)
    hit = _discovery.get(issuer)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    try:
        with http_client() as client:
            res = client.get(f"{issuer}/.well-known/openid-configuration")
        res.raise_for_status()
        data = res.json()
    except (httpx.HTTPError, ValueError):
        raise ContractError("sso_unavailable", 502, "The identity provider could not be reached. Try again.")
    if normalise_issuer(str(data.get("issuer", ""))) != issuer:
        raise fail("The identity provider's discovery document names another issuer.")
    for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not isinstance(data.get(field), str):
            raise fail(f"The identity provider's discovery document has no {field}.")
    _discovery[issuer] = (time.monotonic(), data)
    return data


def _keys(uri: str, *, refresh: bool = False) -> list[dict]:
    hit = _jwks.get(uri)
    if hit and not refresh and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1].get("keys", [])
    try:
        with http_client() as client:
            res = client.get(uri)
        res.raise_for_status()
        data = res.json()
    except (httpx.HTTPError, ValueError):
        raise ContractError("sso_unavailable", 502, "The identity provider's keys could not be fetched.")
    _jwks[uri] = (time.monotonic(), data)
    return data.get("keys", [])


def redirect_uri() -> str:
    return f"{get_settings().api_url.rstrip('/')}/auth/sso/oidc/callback"


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)  # 86 characters, inside RFC 7636's 43-128
    return verifier, b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def authorize_url(issuer: str, client_id: str, *, state: str, nonce: str, challenge: str, login_hint: str | None) -> str:
    meta = discover(issuer)
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri(),
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if login_hint:
        query["login_hint"] = login_hint
    sep = "&" if "?" in meta["authorization_endpoint"] else "?"
    return f"{meta['authorization_endpoint']}{sep}{urlencode(query)}"


def exchange_code(issuer: str, client_id: str, client_secret: str, code: str, verifier: str) -> dict:
    meta = discover(issuer)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": verifier,
        "client_id": client_id,
    }
    methods = meta.get("token_endpoint_auth_methods_supported") or ["client_secret_basic"]
    auth = None
    if "client_secret_basic" in methods:
        auth = (client_id, client_secret)
    else:
        form["client_secret"] = client_secret
    try:
        with http_client() as client:
            res = client.post(meta["token_endpoint"], data=form, auth=auth, headers={"Accept": "application/json"})
        data = res.json()
    except (httpx.HTTPError, ValueError):
        raise ContractError("sso_unavailable", 502, "The identity provider could not be reached. Try again.")
    if res.status_code != 200 or not isinstance(data.get("id_token"), str):
        raise fail("The identity provider refused the sign-in code.")
    return data


def verify_id_token(
    issuer: str, client_id: str, id_token: str, *, nonce: str, access_token: str | None
) -> dict:
    meta = discover(issuer)
    try:
        header = jwt.get_unverified_header(id_token)
    except JOSEError:
        raise fail("The identity provider's ID token is malformed.")
    alg, kid = header.get("alg"), header.get("kid")
    if alg not in ALGORITHMS:
        raise fail("The ID token is not signed with an accepted algorithm.")

    def pick(keys: list[dict]) -> dict | None:
        usable = [k for k in keys if k.get("use", "sig") == "sig"]
        if kid is not None:
            return next((k for k in usable if k.get("kid") == kid), None)
        return usable[0] if len(usable) == 1 else None

    key = pick(_keys(meta["jwks_uri"])) or pick(_keys(meta["jwks_uri"], refresh=True))
    if key is None:
        raise fail("The ID token is signed by a key the identity provider does not publish.")
    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=[alg],
            audience=client_id,
            issuer=meta["issuer"],
            access_token=access_token,
            options={"leeway": LEEWAY_S},
        )
    except JOSEError as exc:
        raise fail(f"The ID token did not verify ({type(exc).__name__}).")
    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != client_id:
        raise fail("The ID token was issued to another application.")
    if not nonce or not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise fail("The ID token does not answer this sign-in (nonce).")
    if claims.get("email_verified") is not True and str(claims.get("email_verified")).lower() != "true":
        raise fail("The identity provider did not confirm this e-mail address.")
    if not isinstance(claims.get("email"), str) or "@" not in claims["email"]:
        raise fail("The identity provider sent no e-mail address.")
    return claims
