"""A local OpenID Connect provider for the SSO tests and the human test, in the
manner of mock_wayl.py: discovery, JWKS, authorize and token, ID tokens
signed RS256 with the TEST key in tests/fixtures/sso/.

Tests mount it as the server's HTTP client (`oidc.http_client`); a person runs
it next to the local API (from server/):

    .venv\\Scripts\\python.exe -m uvicorn tests.mock_oidc:app --port 8098

and configures the SSO tab with issuer http://127.0.0.1:8098, client id
`truebex-local`, client secret `mock-oidc-secret`. /authorize signs in
whoever the login hint names (the work e-mail typed on the site), or
`?email=` when given, without asking for a password: it is a test stand-in.
"""

import base64
import hashlib
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import jwk, jwt

FIXTURES = Path(__file__).parent / "fixtures" / "sso"
KEY_PEM = (FIXTURES / "oidc_test_key.pem").read_text(encoding="ascii")
KID = "mock-1"
CLIENT_ID = "truebex-local"
CLIENT_SECRET = "mock-oidc-secret"
DEFAULT_EMAIL = "c@example.com"

# code -> what /authorize saw; TWEAKS change the next ID tokens (tests).
CODES: dict[str, dict] = {}
TWEAKS: dict = {}
SEEN: list[dict] = []


def reset() -> None:
    CODES.clear()
    TWEAKS.clear()
    SEEN.clear()


def public_jwk() -> dict:
    key = jwk.construct(KEY_PEM, "RS256").public_key().to_dict()
    return {**key, "kid": KID, "use": "sig", "alg": "RS256"}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


app = FastAPI(title="Mock OIDC provider (tests only)")


def _issuer(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@app.get("/.well-known/openid-configuration")
def discovery(request: Request) -> dict:
    iss = _issuer(request)
    return {
        "issuer": iss,
        "authorization_endpoint": f"{iss}/authorize",
        "token_endpoint": f"{iss}/token",
        "jwks_uri": f"{iss}/jwks",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
    }


@app.get("/jwks")
def jwks() -> dict:
    return {"keys": [public_jwk()]}


@app.get("/authorize")
def authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    code_challenge_method: str,
    scope: str = "",
    login_hint: str | None = None,
    email: str | None = None,
):
    SEEN.append(dict(request.query_params))
    if response_type != "code" or client_id != CLIENT_ID or code_challenge_method != "S256":
        raise HTTPException(400, "bad authorization request")
    if "openid" not in scope.split():
        raise HTTPException(400, "scope must include openid")
    code = secrets.token_urlsafe(24)
    CODES[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "nonce": nonce,
        "challenge": code_challenge,
        "email": (email or login_hint or DEFAULT_EMAIL).lower(),
        "issuer": _issuer(request),
    }
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}{urlencode({'code': code, 'state': state})}", status_code=302)


def _client(request: Request, form_id: str | None, form_secret: str | None) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Basic "):
        cid, _, secret = base64.b64decode(auth[6:]).decode().partition(":")
    else:
        cid, secret = form_id or "", form_secret or ""
    if cid != CLIENT_ID or secret != CLIENT_SECRET:
        raise HTTPException(401, "invalid_client")
    return cid


@app.post("/token")
def token(
    request: Request,
    grant_type: str = Form(),
    code: str = Form(),
    redirect_uri: str = Form(),
    code_verifier: str = Form(),
    client_id: str | None = Form(default=None),
    client_secret: str | None = Form(default=None),
) -> dict:
    cid = _client(request, client_id, client_secret)
    grant = CODES.pop(code, None)
    if grant_type != "authorization_code" or grant is None or grant["client_id"] != cid:
        raise HTTPException(400, "invalid_grant")
    if grant["redirect_uri"] != redirect_uri:
        raise HTTPException(400, "invalid_grant: redirect_uri")
    if _b64(hashlib.sha256(code_verifier.encode()).digest()) != grant["challenge"]:
        raise HTTPException(400, "invalid_grant: PKCE")
    access = secrets.token_urlsafe(24)
    now = int(time.time())
    email = grant["email"]
    claims = {
        "iss": grant["issuer"],
        "sub": hashlib.sha256(email.encode()).hexdigest()[:24],
        "aud": cid,
        "iat": now,
        "exp": now + 300,
        "nonce": grant["nonce"],
        "email": email,
        "email_verified": True,
        "name": email.split("@")[0].title(),
        "at_hash": _b64(hashlib.sha256(access.encode()).digest()[:16]),
    }
    claims.update({k: v for k, v in TWEAKS.items() if not k.startswith("_")})
    for key in TWEAKS.get("_drop", ()):
        claims.pop(key, None)
    key_pem = TWEAKS.get("_key_pem", KEY_PEM)
    id_token = jwt.encode(claims, key_pem, algorithm="RS256", headers={"kid": TWEAKS.get("_kid", KID)})
    return {"access_token": access, "token_type": "Bearer", "expires_in": 300, "id_token": id_token}
