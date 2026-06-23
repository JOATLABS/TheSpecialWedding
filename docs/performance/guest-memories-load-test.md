# Guest Memories Load Test

This runbook measures the public guest memories write path for wedding-day
readiness. Run it only against a staging clone or disposable testbed wedding.
It creates real `guest_media_assets` rows and object-storage uploads.

## Required Environment

- `LOCUST_API_HOST` - staging API origin, for example `https://staging-api.example.com`
- `LOCUST_GUEST_MEDIA_SLUG` - wedding slug
- `LOCUST_GUEST_MEDIA_UPLOAD_TOKEN` - current guest memories upload token

Optional:

- `LOCUST_GUEST_MEDIA_PROFILES` - comma-separated profiles:
  `image_1mb_jpeg,image_5mb_png,image_25mb_webp,video_25mb_mp4,video_100mb_mp4,video_200mb_mov`
- `LOCUST_GUEST_MEDIA_BATCH_SIZES` - comma-separated batch sizes, for example `1,5,10,25`
- `LOCUST_GUEST_MEDIA_FIXTURE_DIR` - local sparse fixture file directory

## Commands

Smoke:

```bash
locust -f loadtests/guest_memories_locustfile.py --headless --users 5 --spawn-rate 1 --run-time 3m
```

Baseline:

```bash
LOCUST_GUEST_MEDIA_PROFILES=image_1mb_jpeg,image_5mb_png,video_25mb_mp4 \
LOCUST_GUEST_MEDIA_BATCH_SIZES=1,5 \
locust -f loadtests/guest_memories_locustfile.py --headless --users 25 --spawn-rate 5 --run-time 10m
```

Breakpoint ramp:

```bash
LOCUST_GUEST_MEDIA_PROFILES=image_1mb_jpeg,image_5mb_png,image_25mb_webp,video_25mb_mp4,video_100mb_mp4,video_200mb_mov \
LOCUST_GUEST_MEDIA_BATCH_SIZES=1,5,10,25 \
locust -f loadtests/guest_memories_locustfile.py --headless --users 100 --spawn-rate 10 --run-time 10m
```

Repeat the breakpoint ramp at `125`, `150`, and higher user counts until p95,
failure rate, or storage/API errors define the first saturation point.

## Record

- Average, p50, p95, and p99 for:
  - `GET guest-media context`
  - `POST guest-media upload-plan`
  - `PUT guest-media object <profile>`
  - `POST guest-media finalize`
- Failure rate by request name.
- First user count where p95, timeout, 429, 5xx, or direct upload errors become unacceptable.
- Backend CPU/memory, Mongo slow queries, Redis health, and object-storage errors during the same window.
