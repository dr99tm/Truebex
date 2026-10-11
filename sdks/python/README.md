# truebex — the Python SDK for the Truebex developer API

Typed access to projects, exports, shares, the marketplace, supplier feeds and
webhooks. Generated from the API's own OpenAPI document (`openapi/v1.json`),
so every operation of the API is a method here. Python 3.11+, no dependencies.

```bash
pip install truebex
```

## Authenticate

Create a key under **Dashboard → API keys** on truebex.com with the scopes you
need, and keep it in an environment variable, never in code:

```bash
export TRUEBEX_API_KEY=tbx_live_…
```

```python
import truebex

client = truebex.Client()  # reads TRUEBEX_API_KEY
print(client.account.get()["key"]["scopes"])
```

## Projects, exports, shares

```python
project = client.projects.create(name="API House", doc_version=38)  # projects:write
pid = project["project_id"]

ops = client.projects.pull_ops(pid, after=0, wait_s=25)             # projects:read, long-poll

job = client.jobs.create(                                           # jobs:write
    kind="pack", project_id=pid, at_seq=project["head_seq"], params={"items": ["sheets"]}
)
job = client.jobs.get(job["job_id"], rev=job["rev"], wait_s=25)
if job["state"] == "succeeded":
    print(client.jobs.output(job["job_id"]))

upload = client.upload("share", [open("living-room.jpg", "rb").read()])   # shares:write
```

Groups: `client.account`, `.projects`, `.jobs`, `.uploads`, `.shares`,
`.market`, `.feeds`, `.webhooks`. Answers are plain dicts typed by
`truebex.models`. Writes that take an `Idempotency-Key` get one automatically,
so the client retries them safely on 429, 5xx and network errors.

## Errors

```python
try:
    client.projects.delete(pid)
except truebex.TruebexError as err:
    print(err.status, err.code, err.detail, err.request_id)  # 403 session_required …
```

Branch on `err.code` (`forbidden` with `err.data["needed"]` for a missing
scope, `not_found`, `validation_failed`, `rate_limited` with `retry_after_s`).

## Webhooks: verify the signature

Truebex signs every delivery per the Standard Webhooks specification. Verify
the raw body before trusting it:

```python
event = truebex.verify_webhook(os.environ["TRUEBEX_WEBHOOK_SECRET"], request.headers, request.body)
if event["type"] == "project.ops_appended":
    ...
```

`verify_webhook` refuses a wrong signature and a timestamp more than 5 minutes
off (`truebex.WebhookVerificationError`).

## Publishing (Truebex staff)

Regenerate with `scripts\gen-sdks.ps1` at the repository root, then from
`sdks/python`: `py -3.12 -m build` and `py -3.12 -m twine upload dist/*`.
