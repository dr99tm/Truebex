"""A tiny stand-in for api.thewayl.com, for clicking through checkout locally.

    .venv/Scripts/python.exe -m uvicorn tests.mock_wayl:app --port 8099

Then run the API with WAYL_API_BASE=http://127.0.0.1:8099 and any
WAYL_API_KEY / WAYL_WEBHOOK_SECRET. "Paying" on the mock link page marks the
link Complete, calls the webhook, and redirects back like Wayl does.
"""

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()
LINKS: dict[str, dict] = {}


@app.post("/api/v1/links", status_code=201)
async def create_link(request: Request, x_wayl_authentication: str = Header(default="")):
    if not x_wayl_authentication:
        raise HTTPException(401)
    body = await request.json()
    ref = body["referenceId"]
    LINKS[ref] = {**body, "status": "Created", "id": f"mock_{ref}", "total": str(body["total"])}
    url = f"{request.base_url}pay/{ref}"
    return {"data": {"id": LINKS[ref]["id"], "referenceId": ref, "url": url, "status": "Created"}}


@app.get("/api/v1/links/{ref}")
def get_link(ref: str, x_wayl_authentication: str = Header(default="")):
    if not x_wayl_authentication:
        raise HTTPException(401)
    if ref not in LINKS:
        raise HTTPException(404)
    return {"data": LINKS[ref]}


@app.get("/pay/{ref}", response_class=HTMLResponse)
def pay_page(ref: str):
    link = LINKS[ref]
    return (
        f"<h1>Mock Wayl</h1><p>{link['lineItem'][0]['label']}: {link['total']} IQD</p>"
        f"<form method=post action=/pay/{ref}><button id=pay>Pay</button></form>"
    )


@app.post("/pay/{ref}")
def pay(ref: str):
    link = LINKS[ref]
    link["status"] = "Complete"
    try:
        httpx.post(link["webhookUrl"], json={"referenceId": ref, "status": "Complete"}, timeout=10)
    except httpx.HTTPError:
        pass  # the return-page refresh covers a missed webhook
    sep = "&" if "?" in link["redirectionUrl"] else "?"
    return RedirectResponse(
        f"{link['redirectionUrl']}{sep}referenceId={ref}&orderid=mock", status_code=303
    )
