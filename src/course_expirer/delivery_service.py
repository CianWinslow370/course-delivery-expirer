from __future__ import annotations

import base64
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .expiry_policy import CourseDeliveryRequest, ExpiryPlan, expired_object_keys, plan_expiry
from .infrai_storage import InfraiError, InfraiStorage

BUCKET = os.environ.get("COURSE_OBJECT_BUCKET", "course-delivery-ttl")


class CleanupResult(BaseModel):
    checked_at: datetime
    deleted_keys: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    storage = InfraiStorage()
    await storage.create_bucket(BUCKET)
    app.state.storage = storage
    yield
    await storage.close()


app = FastAPI(title="Course delivery expirer", lifespan=lifespan)


def get_storage(request: Request) -> InfraiStorage:
    return request.app.state.storage


@app.exception_handler(InfraiError)
async def infrai_error_handler(_: Request, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(
        status_code=status,
        content={"detail": {"code": exc.code, "message": str(exc)}},
    )


@app.post("/course-deliveries", response_model=ExpiryPlan, status_code=201)
async def register_course_delivery(
    request: CourseDeliveryRequest,
    storage: InfraiStorage = Depends(get_storage),
) -> ExpiryPlan:
    plan = plan_expiry(request)
    payload = base64.b64encode(
        json.dumps(request.model_dump(mode="json"), separators=(",", ":")).encode()
    ).decode()
    await storage.put_json(
        BUCKET,
        plan.object_key,
        payload,
        idempotency_key=f"course-delivery-{request.course_id}",
    )
    return plan


@app.post("/course-deliveries/cleanup", response_model=CleanupResult)
async def cleanup_course_deliveries(
    storage: InfraiStorage = Depends(get_storage),
) -> CleanupResult:
    checked_at = datetime.now(timezone.utc)
    keys = expired_object_keys(await storage.list_objects(BUCKET), checked_at)
    for key in keys:
        await storage.delete_object(BUCKET, key)
    return CleanupResult(checked_at=checked_at, deleted_keys=keys)


def run() -> None:
    uvicorn.run("course_expirer.delivery_service:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
