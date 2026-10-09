"""SSO for Enterprise organisations (PF3): the owner's connection settings
and verified domains under /orgs/{id}, and the browser sign-in under
/auth/sso (start, OIDC callback, SAML metadata and ACS).

A finished sign-in redirects to `${SITE_URL}/login/sso/#token=…&next=…`.
A failed one answers 401 `sso_failed`: the shared envelope, or a short page
with a way back when a browser asks for HTML.
"""

import html

from fastapi import APIRouter, Depends, Form, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..contract_http import ContractError, enveloped
from ..database import get_db
from ..deps import get_current_user
from ..licence import clock
from ..models import User
from ..orgs import service as orgs
from ..sso import domains, saml, service
from ..sso.schemas import DomainAdd, SsoSettings

router = APIRouter(tags=["sso"], dependencies=[enveloped()])


# --- the owner's settings ---------------------------------------------------------------


@router.get("/orgs/{org_id}/sso")
def get_sso(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    org, _ = orgs.require(db, org_id, current, "owner")
    return service.connection_json(db, org)


@router.put("/orgs/{org_id}/sso")
def put_sso(
    org_id: str, body: SsoSettings, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Secrets are write-only. The first time SSO becomes required the answer
    carries `break_glass_code`, shown once."""
    org, _ = orgs.require(db, org_id, current, "owner")
    return service.save(db, org, current.id, body, clock.now())


@router.delete("/orgs/{org_id}/sso", status_code=status.HTTP_204_NO_CONTENT)
def delete_sso(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    org, _ = orgs.require(db, org_id, current, "owner")
    service.remove(db, org, current.id, clock.now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orgs/{org_id}/sso/break-glass")
def new_break_glass(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """A fresh one-time code for owners; the previous one stops working."""
    org, _ = orgs.require(db, org_id, current, "owner")
    return {"break_glass_code": service.new_break_glass(db, org, current.id, clock.now())}


@router.get("/orgs/{org_id}/domains")
def list_domains(org_id: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    org, _ = orgs.require(db, org_id, current, "owner")
    return [domains.domain_json(d) for d in domains.list_for(db, org)]


@router.post("/orgs/{org_id}/domains", status_code=status.HTTP_201_CREATED)
def add_domain(
    org_id: str,
    body: DomainAdd,
    response: Response,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    org, _ = orgs.require(db, org_id, current, "owner")
    row, created = domains.add(db, org, current.id, body.domain, clock.now())
    if not created:
        response.status_code = status.HTTP_200_OK
    return domains.domain_json(row)


@router.post("/orgs/{org_id}/domains/{domain}/verify")
def verify_domain(
    org_id: str, domain: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    org, _ = orgs.require(db, org_id, current, "owner")
    return domains.domain_json(domains.verify(db, org, current.id, domain, clock.now()))


@router.delete("/orgs/{org_id}/domains/{domain}", status_code=status.HTTP_204_NO_CONTENT)
def remove_domain(
    org_id: str, domain: str, current: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    org, _ = orgs.require(db, org_id, current, "owner")
    domains.remove(db, org, current.id, domain, clock.now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- the browser sign-in ---------------------------------------------------------------


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def _failure(request: Request, exc: ContractError) -> Response:
    if not _wants_html(request):
        raise exc
    login = f"{get_settings().site_url.rstrip('/')}/login/"
    page = (
        "<!doctype html><html lang=en><meta charset=utf-8><meta name=robots content=noindex>"
        "<meta name=viewport content='width=device-width,initial-scale=1'><title>Sign-in failed · Truebex</title>"
        "<body style='font-family:system-ui,sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem;"
        "background:#0b0d10;color:#e8eaed'><h1 style='font-size:1.4rem'>Single sign-on did not finish</h1>"
        f"<p>{html.escape(exc.detail)}</p><p><a style='color:#7cc4ff' href='{html.escape(login)}'>"
        "Back to sign in</a></p></body></html>"
    )
    return HTMLResponse(page, status_code=exc.status)


@router.get("/auth/sso/start")
def sso_start(
    request: Request,
    email: str = Query(min_length=3, max_length=320),
    next: str | None = Query(default=None, max_length=500),  # noqa: A002 - the query name
    format: str | None = Query(default=None, pattern=r"^(json|redirect)$"),  # noqa: A002
    db: Session = Depends(get_db),
):
    """302 to the organisation's identity provider; 404 `sso_not_found` when
    the e-mail's domain has none. `format=json` (or Accept: application/json)
    answers `{url}` instead, for the site's "Continue with SSO"."""
    try:
        url = service.start(db, email, next, clock.now())
    except ContractError as exc:
        if format == "json" or "application/json" in request.headers.get("accept", ""):
            raise
        return _failure(request, exc)
    if format == "json" or (format is None and "application/json" in request.headers.get("accept", "")):
        return JSONResponse({"url": url}, headers={"Cache-Control": "no-store"})
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND, headers={"Cache-Control": "no-store"})


@router.get("/auth/sso/oidc/callback")
def oidc_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=4096),
    state: str | None = Query(default=None, max_length=512),
    error: str | None = Query(default=None, max_length=200),
    db: Session = Depends(get_db),
):
    try:
        if error or not code or not state:
            raise ContractError("sso_failed", 401, "The identity provider did not sign you in. Start again.")
        user, next_ = service.finish_oidc(db, code=code, state=state, now=clock.now())
    except ContractError as exc:
        return _failure(request, exc)
    return RedirectResponse(service.site_redirect(user, next_), status_code=status.HTTP_302_FOUND,
                            headers={"Cache-Control": "no-store"})


@router.get("/auth/sso/saml/{org_slug}/metadata")
def saml_metadata(org_slug: str, db: Session = Depends(get_db)) -> Response:
    org = orgs.by_slug(db, org_slug)
    if org is None:
        raise ContractError("not_found", 404, "There is no such organisation.")
    return Response(saml.sp_metadata(org), media_type="application/samlmetadata+xml")


@router.post("/auth/sso/saml/{org_slug}/acs")
def saml_acs(
    request: Request,
    org_slug: str,
    SAMLResponse: str = Form(max_length=1_000_000),  # noqa: N803 - the SAML binding's field name
    RelayState: str | None = Form(default=None, max_length=512),  # noqa: N803
    db: Session = Depends(get_db),
):
    """A cross-site POST by design (no CSRF token): the signature, InResponseTo
    and the replay cache protect it."""
    try:
        user, next_ = service.finish_saml(
            db, org_slug=org_slug, saml_response=SAMLResponse, relay_state=RelayState, now=clock.now()
        )
    except ContractError as exc:
        return _failure(request, exc)
    return RedirectResponse(service.site_redirect(user, next_), status_code=status.HTTP_302_FOUND,
                            headers={"Cache-Control": "no-store"})
