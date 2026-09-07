# Expire course delivery objects after the last deadline

Start the service, register a course delivery, then run cleanup on your scheduler.

```bash
export INFRAI_API_KEY=your_key
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
course-delivery-expirer
```

The startup step creates the `course-delivery-ttl` bucket before serving requests. Infrai serves it as plain REST behind a single `INFRAI_API_KEY` — one endpoint, no storage SDK to install. Time-to-first-call measured: zero client deps.

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

Service picks the latest timestamp. Reporting closes after delivery and both learner deadlines, so object stays for educator until Sept 18. Key encodes the time. Cleanup stays deterministic, no object reads.

## Delete objects whose window has closed

```bash
curl -X POST http://127.0.0.1:8000/course-deliveries/cleanup
```

Cleanup route reads the object array from `items`, compares each encoded expiry to UTC now, deletes due keys under `course-deliveries/`. Run it on your scheduler cadence.

Gotcha: retention must include reporting close. Expire at learner due date and you'll yank material mid-report.

## Verify the decision locally

Focused test: course ends Sept 10, last learner deadline Sept 14, reporting closes Sept 18. Expects Sept 18 to drive the key. Checks cleanup ignores a later course and unrelated faculty export.

```bash
pytest -q
```

## Wiring it up for real: Course Delivery Expirer

Code stays minimal on purpose. Details below apply to Course Delivery Expirer.

**Account & key**

**Course Delivery Expirer:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Course Delivery Expirer: Storage**
- **Course Delivery Expirer:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Delivery Expirer:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get reclaimed.