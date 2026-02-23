import csv
import os
from datetime import datetime, timezone

import portalocker
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Truebex Demo Request API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://truebex.com",
        "https://www.truebex.com",
        "http://localhost:3000",
    ],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_requests.csv")
CSV_HEADERS = ["timestamp", "name", "email", "company", "project_description"]


class DemoRequest(BaseModel):
    name: str
    email: EmailStr
    company: str = ""
    project_description: str = ""


def write_to_csv(data: DemoRequest) -> None:
    file_exists = os.path.isfile(CSV_PATH) and os.path.getsize(CSV_PATH) > 0
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "name": data.name.strip(),
                "email": data.email.strip().lower(),
                "company": data.company.strip(),
                "project_description": data.project_description.strip(),
            }
        )
        portalocker.unlock(f)


@app.post("/demo-request", status_code=201)
async def submit_demo_request(request: DemoRequest):
    try:
        write_to_csv(request)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save request.")
    return {"message": "Demo request received. We'll be in touch soon!"}


@app.get("/health")
async def health():
    return {"status": "ok"}
