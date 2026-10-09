"""Uploads (contract share-bundle v1.0, §5.1-5.3): open a session for a set of
files, send 8 MiB parts each with its SHA-256, read what has arrived.

Auth: a device token, a website session, or a worker token (purpose
`job-output` only). Every error uses the shared envelope.
"""

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..contract_http import ContractError, contract
from ..database import get_db
from ..uploads import service
from ..uploads.credentials import UploadCaller, get_upload_caller

router = APIRouter(prefix="/uploads", tags=["uploads"], dependencies=[contract("share-bundle", 1, 0)])


class UploadFileIn(BaseModel):
    sha256: str = Field(max_length=64)
    bytes: int
    content_type: str = Field(max_length=100)


class OpenUploadIn(BaseModel):
    purpose: str = Field(max_length=16)
    files: list[UploadFileIn] = Field(max_length=service.MAX_FILES)


@router.post("", status_code=201)
def open_upload(
    body: OpenUploadIn, caller: UploadCaller = Depends(get_upload_caller), db: Session = Depends(get_db)
) -> dict:
    session = service.open_session(db, caller, purpose=body.purpose, files=[f.model_dump() for f in body.files])
    return service.opened_json(db, session)


@router.get("/{upload_id}")
def upload_status(
    upload_id: str, caller: UploadCaller = Depends(get_upload_caller), db: Session = Depends(get_db)
) -> dict:
    return service.status_json(db, service.get_session(db, caller, upload_id))


@router.put("/{upload_id}/files/{sha256}/parts/{n}", status_code=204)
async def put_part(
    upload_id: str,
    sha256: str,
    n: int,
    request: Request,
    x_part_sha256: str | None = Header(default=None),
    caller: UploadCaller = Depends(get_upload_caller),
    db: Session = Depends(get_db),
) -> Response:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > service.PART_BYTES:
            raise ContractError(
                "too_large", 413, f"A part is at most {service.PART_BYTES} bytes.", {"limit": service.PART_BYTES}
            )
    await run_in_threadpool(service.put_part, db, caller, upload_id, sha256, n, bytes(body), x_part_sha256)
    return Response(status_code=204)
