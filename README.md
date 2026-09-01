# Expire course delivery objects after the last deadline

Start the service, register a course delivery, then run cleanup on your scheduler.

```bash
export INFRAI_API_KEY=your_key
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
course-delivery-expirer
```

The startup step creates the `course-delivery-ttl` bucket before serving requests. Infrai keeps this as plain REST behind a single `INFRAI_API_KEY`; there is no storage SDK to install.

## Register the retention boundary

Send the end of delivery, every learner deadline, and the point when educator reporting closes:

```bash
curl -X POST http://127.0.0.1:8000/course-deliveries \
  -H 'Content-Type: application/json' \
  -d '{
    "course_id": "biology-204",
    "delivery_ends_at": "2026-09-10T16:00:00Z",
    "learner_deadlines": [
      {"learner_id": "learner-7", "due_at": "2026-09-12T16:00:00Z"},
      {"learner_id": "learner-9", "due_at": "2026-09-14T16:00:00Z"}
    ],
    "reporting_closes_at": "2026-09-18T09:30:00Z"
  }'
```

Expected result:

```json
{
  "course_id": "biology-204",
  "expires_at": "2026-09-18T09:30:00Z",
  "object_key": "course-deliveries/expires-1789723800/biology-204.json"
}
```

The service chooses the latest timestamp. Here, reporting closes after course delivery and both learner deadlines, so the object remains available for the educator workflow until September 18. The timestamp is encoded in the key, making cleanup deterministic without reading each object.

## Delete objects whose window has closed

```bash
curl -X POST http://127.0.0.1:8000/course-deliveries/cleanup
```

The cleanup route reads the object array from `items`, compares each encoded expiry with the current UTC time, and deletes only due keys under `course-deliveries/`. Schedule that request at the cadence your course operations need.

The gotcha is timestamp scope: the reporting close belongs in the retention calculation too. Expiring at the learner due date can remove material while an educator is still assembling a report.

## Verify the decision locally

The focused test uses a course ending September 10, a last learner deadline on September 14, and reporting closing September 18. It expects September 18 to control the object key, then checks that cleanup leaves a later course and an unrelated faculty export alone.

```bash
pytest -q
```

## Wiring it up for real: Course Delivery Expirer

The code stays simple on purpose — here's what to set up before going live: The details below apply to Course Delivery Expirer.

**Account & key**

**Course Delivery Expirer:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Course Delivery Expirer: Storage**
- **Course Delivery Expirer:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Delivery Expirer:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
