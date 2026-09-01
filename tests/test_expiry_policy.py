from datetime import datetime, timezone

from course_expirer.expiry_policy import (
    CourseDeliveryRequest,
    expired_object_keys,
    plan_expiry,
)


def test_reporting_window_controls_course_object_expiry() -> None:
    request = CourseDeliveryRequest.model_validate(
        {
            "course_id": "biology-204",
            "delivery_ends_at": "2026-09-10T16:00:00Z",
            "learner_deadlines": [
                {"learner_id": "learner-7", "due_at": "2026-09-12T16:00:00Z"},
                {"learner_id": "learner-9", "due_at": "2026-09-14T16:00:00Z"},
            ],
            "reporting_closes_at": "2026-09-18T09:30:00Z",
        }
    )

    plan = plan_expiry(request)

    assert plan.expires_at == datetime(2026, 9, 18, 9, 30, tzinfo=timezone.utc)
    assert plan.object_key == "course-deliveries/expires-1789723800/biology-204.json"


def test_cleanup_selects_only_due_course_delivery_objects() -> None:
    items = [
        {"key": "course-deliveries/expires-1789723800/biology-204.json"},
        {"key": "course-deliveries/expires-1790328600/chemistry-101.json"},
        {"key": "faculty-exports/weekly.csv"},
    ]
    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

    assert expired_object_keys(items, now) == [
        "course-deliveries/expires-1789723800/biology-204.json"
    ]

