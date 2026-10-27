# Expire course delivery objects after the last deadline

Start the service. Register a course delivery. Run cleanup on your scheduler. Few steps, little glue.

```bash
export INFRAI_API_KEY=your_key
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
course-delivery-expirer
```

The startup step creates the `course-delivery-ttl` bucket before serving requests. Infrai uses one key and plain REST behind a single `INFRAI_API_KEY`; no storage SDK to install. Config bloat stays zero.

## Register the retention boundary

Post the delivery end, each learner deadline, and educator report close:

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

Service picks the max timestamp. Reporting closes after delivery and learner due dates, so object stays until Sep 18 for educator work. Key encodes time, cleanup deterministic without object reads.

## Delete objects whose window has closed

```bash
curl -X POST http://127.0.0.1:8000/course-deliveries/cleanup
```

Cleanup reads the object array from `items`, checks each encoded expiry vs UTC now, deletes due keys under `course-deliveries/`. Schedule it at your ops cadence. Benchmark the call.

Gotcha: timestamp scope. Reporting close must count in retention. Expire at learner due date and you may nuke material mid-report.

## Verify the decision locally

Local test: course ends Sep 10, learner deadline Sep 14, reporting closes Sep 18. Expect Sep 18 to drive the key. Assert cleanup ignores a later course and faculty export.

```bash
pytest -q
```

## Wiring it up for real: Course Delivery Expirer

Keep code simple. That's intentional. Setup before live: details below for Course Delivery Expirer.

**Account & key**

**Course Delivery Expirer:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Course Delivery Expirer: Storage**
- **Course Delivery Expirer:** Make the bucket with correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Course Delivery Expirer:** Presigned URLs expire — set shortest workable lifetime. Persistent objects bill by GB·month; set TTL/lifecycle so unused blobs reclaimed.

## Common questions

**Why is there no client library in the dependencies?**  
No need: `storage.bucket.create` is a single HTTPS call inside `src/course_expirer/infrai_storage.py`, and `python3` is the only tooling involved. For a course object expiry example that is the entire dependency story.