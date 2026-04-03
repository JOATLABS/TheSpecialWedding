# Locust Load Test Plan

This document defines a safe baseline load test for The Special Wedding using [Locust](https://locust.io/) and the repo-local script at [`/loadtests/locustfile.py`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/loadtests/locustfile.py).

## Goals

- Measure read-heavy planner, couple, and public wedding traffic under controlled load.
- Catch regressions in authentication, dashboard reads, guest-list reads, and public wedding page response times.
- Keep the test repeatable and safe for staging.

## Explicit Non-Goals

These scenarios are intentionally excluded because they create side effects or hit external vendors:

- OTP generation or verification
- RSVP submission
- Reminder sends
- Package sends or contract creation
- Contract signing
- Payment mutations

## Covered Scenarios

### 1. Public Wedding Traffic

User class: `PublicWeddingPageUser`

Requests:
- `GET /:slug`
- `GET /:slug/gallery`

Why:
- This is the highest-volume anonymous traffic surface.
- It exercises the public frontend, page rendering, and public wedding data fetch path.

### 2. Planner Read Traffic

User class: `PlannerApiUser`

Requests:
- `POST /admin/token`
- `GET /admin/profile`
- `GET /admin/planner/weddings`
- `GET /admin/guests`
- `GET /admin/packages`
- `GET /admin/contracts`

Why:
- This is the core authenticated planner workload.
- It exercises login, authorization, wedding listing, and guest-list reads without mutating production-like data.

### 3. Couple Portal Read Traffic

User class: `CouplePortalApiUser`

Requests:
- `POST /couple/login`
- `GET /couple/profile`
- `GET /couple/portal/dashboard`
- `GET /couple/portal/events`

Why:
- Couples repeatedly refresh dashboard and events near the wedding date.
- These endpoints aggregate multiple backing collections and are good regression detectors.

## Test Data Assumptions

The Locust script auto-loads `.env` when available and uses the existing seeded QA credentials:

- `TEST_PLANNER_WITH_PACKAGE_EMAIL`
- `TEST_PLANNER_WITH_PACKAGE_PASSWORD`
- `TEST_COUPLE_EMAIL`
- `TEST_COUPLE_PASSWORD`

Default wedding routing assumptions:

- `LOCUST_WEDDING_SLUG=james-and-mel`
- The planner account can access that wedding
- The couple account is already linked to that wedding

If you want to override them, set:

- `LOCUST_API_HOST`
- `LOCUST_FRONTEND_HOST`
- `LOCUST_WEDDING_ID`
- `LOCUST_WEDDING_SLUG`
- `LOCUST_PLANNER_EMAIL`
- `LOCUST_PLANNER_PASSWORD`
- `LOCUST_PLANNER_BEARER_TOKEN`
- `LOCUST_COUPLE_EMAIL`
- `LOCUST_COUPLE_PASSWORD`
- `LOCUST_COUPLE_BEARER_TOKEN`

Token overrides are useful for steady-state read benchmarks because they let you
separate login throttling from the authenticated read workload. If a bearer
token override is present, the Locust user skips the login request and reuses
the provided token.

## Install

Locust is not bundled in this repo today. Install it in the same Python environment you use for the backend:

```bash
pip install locust
```

## Recommended Stages

### Stage 1. Smoke

Purpose:
- Verify auth, routing, and basic stability before a longer run.

Command:

```bash
locust -f loadtests/locustfile.py --headless --users 6 --spawn-rate 2 --run-time 3m
```

Expected:
- 0 auth failures
- 0 unexpected 5xx bursts
- No obvious timeout cascade

### Stage 2. Baseline

Purpose:
- Establish normal staging performance under modest mixed traffic.

Command:

```bash
locust -f loadtests/locustfile.py --headless --users 25 --spawn-rate 5 --run-time 10m
```

Expected:
- Error rate under 1%
- Public page p95 under 800 ms
- Authenticated API p95 under 1.5 s

### Stage 3. Sustained Read Load

Purpose:
- Validate read-heavy planner and couple traffic over a longer interval.

Command:

```bash
locust -f loadtests/locustfile.py --headless --users 60 --spawn-rate 6 --run-time 20m
```

Expected:
- Stable median and p95 latencies after warm-up
- No monotonic memory growth
- No DB connection pool exhaustion

### Stage 4. Stress

Purpose:
- Find the first real saturation point in staging.

Command:

```bash
locust -f loadtests/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 10m
```

Watch for:
- 429/502/503 spikes
- queueing latency
- auth failures after initial success
- Mongo saturation and Redis degradation

## Local Development Run

If frontend and backend are running locally on the default ports from this repo:

```bash
locust -f loadtests/locustfile.py
```

The script defaults to:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`

## Production-Mode Local Run

For a trustworthy local baseline, do not benchmark `next dev` and `uvicorn --reload`.
Run the frontend and backend in production mode on alternate ports and point
Locust at those ports instead.

Example:

```bash
# terminal 1
PORT=3100 npm run start

# terminal 2
./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8100 --workers 2

# terminal 3
LOCUST_FRONTEND_HOST=http://127.0.0.1:3100 \
LOCUST_API_HOST=http://127.0.0.1:8100 \
locust -f loadtests/locustfile.py --headless --users 25 --spawn-rate 5 --run-time 10m
```

## What To Record

- Request count, failure rate, median, p95, and p99 per endpoint group
- CPU and memory for frontend and backend processes
- Mongo connection count, query latency, and slow query spikes
- Redis latency if enabled in the tested path
- Any error bursts in app logs during ramp-up and steady state

## Exit Criteria

Treat the run as acceptable when all of the following hold during Baseline and Sustained Read Load:

- Error rate stays below 1%
- No auth loop or session-refresh loop appears
- No endpoint group shows a sustained p95 regression greater than 25% versus the previous accepted baseline
- No unbounded resource growth appears in the backend processes

## Notes

- Use staging first, not production.
- Keep this harness read-only unless you intentionally build a separate mutation test suite.
- If you later want OTP, RSVP, reminders, or contract signing coverage, build those as isolated scenarios with vendor stubs or sandbox providers so the load test does not spam Twilio, Resend, or Stripe.
