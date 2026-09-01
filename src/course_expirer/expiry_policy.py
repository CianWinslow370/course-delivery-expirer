from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class LearnerDeadline(BaseModel):
    learner_id: str = Field(min_length=1)
    due_at: datetime


class CourseDeliveryRequest(BaseModel):
    course_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    delivery_ends_at: datetime
    learner_deadlines: list[LearnerDeadline] = Field(min_length=1)
    reporting_closes_at: datetime

    @field_validator("delivery_ends_at", "reporting_closes_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("learner_deadlines")
    @classmethod
    def require_deadline_timezones(
        cls, deadlines: list[LearnerDeadline]
    ) -> list[LearnerDeadline]:
        if any(item.due_at.tzinfo is None or item.due_at.utcoffset() is None for item in deadlines):
            raise ValueError("learner deadlines must include a timezone")
        return deadlines


class ExpiryPlan(BaseModel):
    course_id: str
    expires_at: datetime
    object_key: str


def plan_expiry(request: CourseDeliveryRequest) -> ExpiryPlan:
    expires_at = max(
        request.delivery_ends_at,
        request.reporting_closes_at,
        *(deadline.due_at for deadline in request.learner_deadlines),
    ).astimezone(timezone.utc)
    epoch = int(expires_at.timestamp())
    return ExpiryPlan(
        course_id=request.course_id,
        expires_at=expires_at,
        object_key=f"course-deliveries/expires-{epoch}/{request.course_id}.json",
    )


def expired_object_keys(items: list[dict[str, object]], now: datetime) -> list[str]:
    now_epoch = int(now.astimezone(timezone.utc).timestamp())
    expired: list[str] = []
    for item in items:
        key = item.get("key")
        if not isinstance(key, str) or not key.startswith("course-deliveries/expires-"):
            continue
        expiry_part = key.split("/", 2)[1].removeprefix("expires-")
        if expiry_part.isdigit() and int(expiry_part) <= now_epoch:
            expired.append(key)
    return expired

