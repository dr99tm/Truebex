"""`/v1/jobs…`: render-jobs 5.1-5.6 for API keys (PF12; the contract's §4
lists API keys). `pack` jobs are the exports: the sheet PDF, renders,
panoramas and the bill of quantities.

Each route hands the call to the contract router's handler
(`app/routers/jobs.py`); submitting and cancelling need `jobs:write`, reading
`projects:read`. The overage cap stays on the website.
"""

import json

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ...contract_http import ContractError, contract
from ...database import get_db
from ...deps import ApiCaller
from ...idempotency import Idempotency, idempotent
from ...render import service
from .. import jobs as c
from . import models as m
from .common import doc, project_caller, scope

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[contract("render-jobs", 1, 1), Depends(c._small_body)])

Read = scope("projects:read")
Write = scope("jobs:write")


@router.post(
    "",
    status_code=201,
    operation_id="jobs_create",
    openapi_extra={
        "x-truebex-scope": "jobs:write",
        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/JobRequest"}}}},
    },
    responses=doc(None, m.Job, 201, errors=(401, 403, 404, 409, 413, 422, 429))["responses"],
)
async def submit(
    request: Request,
    response: Response,
    api: ApiCaller = Write,
    idem: Idempotency = idempotent("v1.jobs.submit"),
    db: Session = Depends(get_db),
):
    """Submit a job (5.1); answers the estimate in cost units. Send an `Idempotency-Key`."""
    raw = await request.body()  # read raw: the contract's handler validates the fields
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        raise ContractError(
            "validation_failed", 422, "body: a JSON object.", {"fields": [{"field": "body", "in": "body", "message": "a JSON object"}]}
        )
    return await run_in_threadpool(c.submit, response=response, body=body, caller=project_caller(api), idem=idem, db=db)


@router.get("/usage", operation_id="jobs_usage", **doc("projects:read", m.JobUsage))
def usage(api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """Cost units used this month and the allowance (5.6)."""
    return c.usage(caller=project_caller(api), db=db)


@router.get("", operation_id="jobs_list", **doc("projects:read", m.JobList))
def list_jobs(
    project_id: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    cursor: str | None = None,
    limit: int = service.PAGE_DEFAULT,
    api: ApiCaller = Read,
    db: Session = Depends(get_db),
) -> dict:
    """The account's jobs, newest first, by project, kind or state (5.3)."""
    return c.list_jobs(project_id=project_id, kind=kind, state=state, cursor=cursor, limit=limit, caller=project_caller(api), db=db)


@router.get("/{job_id}", operation_id="jobs_get", **doc("projects:read", m.Job))
async def get_job(job_id: str, rev: int | None = None, wait_s: float = 0, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """A job's status (5.2); with `rev` and `wait_s` ≤ 25 it waits for the next change."""
    return await c.get_job(job_id=job_id, rev=rev, wait_s=wait_s, caller=project_caller(api), db=db)


@router.post("/{job_id}/cancel", operation_id="jobs_cancel", **doc("jobs:write", m.Job, errors=(401, 403, 404, 409, 429)))
def cancel(job_id: str, api: ApiCaller = Write, db: Session = Depends(get_db)) -> dict:
    """Cancel a queued or running job (5.4)."""
    return c.cancel(job_id=job_id, caller=project_caller(api), db=db)


@router.get("/{job_id}/output", operation_id="jobs_output", **doc("projects:read", m.JobOutput, errors=(401, 403, 404, 409, 429)))
def output(job_id: str, response: Response, api: ApiCaller = Read, db: Session = Depends(get_db)) -> dict:
    """The finished job's output with file URLs (5.5); 409 `not_ready` before it succeeds."""
    return c.output(job_id=job_id, response=response, caller=project_caller(api), db=db)
