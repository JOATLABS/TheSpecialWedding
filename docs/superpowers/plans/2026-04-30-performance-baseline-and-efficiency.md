# Performance Baseline And Cost Efficiency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make performance the next major development track by proving why one planner with one wedding is slow, recording a repeatable baseline, and tying capacity to monthly infrastructure cost.

**Architecture:** Live performance verification belongs in `testbed/`. The baseline driver seeds isolated testbed state, measures the same backend endpoints the planner dashboard depends on, writes durable artifacts under `docs/performance/baselines/`, and leaves a cleanup pair. Narrow unit tests that already exist can stay where they are, but new performance and live metrics tests for this track must be testbed drivers.

**Tech Stack:** FastAPI, MongoDB/Motor, Next.js, Cloudflare Workers metrics snapshot cron, existing `platform_metrics` collection, existing `audit_logs` collection, and `testbed/harness.py`.

---

## Acceptance Matrix

| Requirement | Acceptance Evidence | Owner Surface |
| --- | --- | --- |
| One-planner/one-wedding slowness is measured before optimization | `testbed/verify_performance_baseline.py` writes a baseline JSON artifact with endpoint timings | Planner dashboard |
| Average seconds baseline is recorded | Baseline artifact includes avg, p50, p95, max, request count, and failure count per endpoint group | `docs/performance/baselines/` |
| Load per dollar is recorded | Baseline artifact includes monthly infrastructure cost, successful requests/sec/$, and dashboard sessions/hour/$ | Testbed cost model |
| Infrastructure metrics snapshots are reliable | `testbed/verify_metrics_snapshot_no_body.py` proves `POST /metrics/snapshot` works without a request body | Cloudflare Worker + backend |
| Public homepage PageSpeed baseline is tracked | `docs/performance/pagespeed-insights-2026-04-30.md` records the Google report and future repeatable checks live in `testbed/` | Public homepage |
| Performance tests live in testbed | New live/performance verification files are `testbed/verify_*.py` with cleanup pairs | `testbed/` |
| Improvement work is target-driven | Every performance fix compares against the latest accepted baseline and states expected impact | Changelog + baseline report |
| Work remains safe for live data | Testbed drivers use isolated `+tag@` accounts and cleanup scripts; Locust remains read-only | Testbed + Locust |

## Entry Points To Inventory

- Planner dashboard: `/admin/planner`
- Planner profile bootstrap: `GET /admin/profile`
- Planner dashboard payload: `GET /admin/planner/metrics`
- Planner engagement payload: `GET /admin/engagement-signals`
- Planner AI insight payload: `GET /admin/ai/weddings/{wedding_id}/insights`
- Admin shell and route guard: `app/contexts/AdminContext.tsx`, `app/components/AdminRouteGuard.tsx`
- Public wedding pages: `GET /{slug}`, `GET /{slug}/gallery`
- Couple portal reads: `GET /couple/profile`, `GET /couple/portal/dashboard`, `GET /couple/portal/events`
- Platform health and snapshots: `GET /admin/platform/health`, `POST /metrics/snapshot`, `GET /metrics/snapshot`
- Load harness: `loadtests/locustfile.py`
- Live verification harness: `testbed/harness.py`
- Public homepage PageSpeed reports: `docs/PageSpeed Insights.pdf`, `docs/Desktop PageSpeed Insights.pdf`

## Source Of Truth

- Live baseline truth: `testbed/verify_performance_baseline.py`
- Snapshot cron contract truth: `testbed/verify_metrics_snapshot_no_body.py`
- Request timing truth: live driver timings plus `audit_logs.response_time_ms`
- Infrastructure truth: `platform_metrics` snapshots generated from `build_platform_health_payload()`
- Cost truth: `testbed/performance_cost_model.example.json` copied to an environment-specific local file
- Public PageSpeed truth: `docs/performance/pagespeed-insights-2026-04-30.md`
- Durable reporting truth: `docs/performance/baselines/`

## Invariants

- A single planner with one wedding must not require more than one blocking dashboard payload before useful dashboard content renders.
- New performance tests for this development track must live in `testbed/`, with a cleanup pair when they seed or mutate state.
- No performance metric should be silently dropped because one optional sink, such as Workers Analytics Engine, is missing.
- Read-only load testing must not send OTPs, reminders, payments, contract signatures, or external vendor mutations.
- Cost metrics must label what they include and exclude; SMS, email, AI, Stripe fees, and R2 egress are variable vendor costs unless explicitly entered.
- Every baseline must name environment, commit SHA when available, worker count when available, Redis state when available, frontend/backend deployment mode, and test account shape.

## Recommendations

1. Treat the one-planner slowdown as a performance incident until the testbed baseline identifies the bottleneck.
2. Run the testbed baseline before changing planner dashboard code, then rerun it after each optimization.
3. Make `/admin/planner/metrics` the only blocking dashboard data request before useful content renders.
4. Defer engagement signals and AI insights until after the dashboard is usable unless the baseline proves they are non-blocking.
5. Collapse duplicate profile/session checks during first navigation.
6. Add database indexes only after measured endpoint or Mongo evidence points to the query shape.
7. Surface average seconds, p95 seconds, slowest blocking endpoint, monthly infrastructure cost, and successful requests/sec/$ in root admin.
8. Keep public homepage PageSpeed work separate from planner dashboard API work. The Google reports point at mobile LCP/image delivery and desktop TBT/main-thread work; the planner complaint points at authenticated app/API latency.

---

### Task 1: Keep Hourly Metrics Snapshots Alive

**Files:**
- Modify: `app/api/platform_metrics.py`
- Create: `testbed/verify_metrics_snapshot_no_body.py`
- Create: `testbed/cleanup_metrics_snapshot_no_body_state.py`
- Later modify: `cloudflare-workers/metrics-snapshot-cron.js`

- [ ] **Step 1: Backend accepts no-body snapshot ingestion**

`POST /metrics/snapshot` must accept an empty request body. When the body is empty, it builds live platform health metrics and persists them as the snapshot payload.

- [ ] **Step 2: Verify with the testbed driver**

Run:

```bash
python testbed/testbed.py up
python testbed/verify_metrics_snapshot_no_body.py
python testbed/cleanup_metrics_snapshot_no_body_state.py
```

Expected: the verifier posts with no body, reads the same snapshot through `GET /metrics/snapshot`, confirms root-admin history includes it, and the cleanup removes the inserted snapshot.

- [ ] **Step 3: Normalize Cloudflare Analytics Engine latency fields**

In `cloudflare-workers/metrics-snapshot-cron.js`, read both current and legacy field names:

```javascript
const avgMs = endpoint.avg_response_time_ms ?? endpoint.avg_response_time;
const maxMs = endpoint.max_response_time_ms ?? endpoint.max_response_time;
enqueueMetric('performance', 'avg_response_ms', avgMs, endpointName);
enqueueMetric('performance', 'max_response_ms', maxMs, endpointName);
enqueueMetric('performance', 'request_count', endpoint.request_count, endpointName);
```

Add any live worker verification as a testbed verifier, not under `tests/`.

---

### Task 2: Establish The Testbed Baseline Driver

**Files:**
- Create: `testbed/verify_performance_baseline.py`
- Create: `testbed/cleanup_performance_baseline_state.py`
- Create: `testbed/performance_cost_model.example.json`
- Create: `docs/performance/baselines/.gitkeep`
- Modify: `testbed/README.md`

- [ ] **Step 1: Seed the smallest realistic fixture**

The driver must create one isolated paid planner using `test_planner+perfbaseline@thespecialwedding.io`, create one wedding through the real planner route, and keep all state cleanup-scoped to that plus-variant email.

- [ ] **Step 2: Measure blocking planner-dashboard backend endpoints**

The first baseline must measure:

- `GET /admin/profile`
- `GET /admin/planner/metrics`
- `GET /admin/engagement-signals`
- optionally `GET /admin/ai/weddings/{wedding_id}/insights`

AI insight timing is optional because it can spend credits and call an external provider.

- [ ] **Step 3: Calculate cost efficiency**

Read the monthly infrastructure cost from a testbed cost-model JSON file and calculate:

```text
successful_requests_per_second_per_dollar =
  successful_requests_per_second / monthly_infrastructure_usd
```

Also calculate dashboard sessions/hour/$ from the measured endpoint group time.

- [ ] **Step 4: Write a durable artifact**

Write baseline JSON under:

```text
docs/performance/baselines/
```

The artifact must include fixture shape, endpoint summaries, raw results, cost model, and the next recommendation.

- [ ] **Step 5: Verify with testbed**

Run:

```bash
python testbed/testbed.py up --with-frontend
python testbed/verify_performance_baseline.py
python testbed/cleanup_performance_baseline_state.py
```

Expected: the verifier exits 0 and writes a baseline JSON artifact.

---

### Task 3: Add Browser-Observable Timing In Testbed

**Files:**
- Create: `testbed/verify_planner_dashboard_browser_baseline.py`
- Create: `testbed/cleanup_planner_dashboard_browser_baseline_state.py`

- [ ] **Step 1: Drive the real browser-visible planner dashboard**

Add a testbed verifier that uses the local frontend from `python testbed/testbed.py up --with-frontend`, signs in as an isolated plus-variant planner, navigates to `/admin/planner`, and records:

- dashboard ready milliseconds
- number of admin requests before usable content
- slowest blocking admin request
- console errors during load

- [ ] **Step 2: Keep the driver paired with cleanup**

The cleanup must remove the planner, wedding, and any state seeded for the browser run.

- [ ] **Step 3: Write browser timing into the baseline artifact**

The browser verifier can write a separate artifact or append a clearly named browser section to the same baseline report.

---

### Task 4: Add Public Homepage PageSpeed Baseline Lane

**Files:**
- Existing sources: `docs/PageSpeed Insights.pdf`, `docs/Desktop PageSpeed Insights.pdf`
- Create: `docs/performance/pagespeed-insights-2026-04-30.md`
- Future create: `testbed/verify_pagespeed_public_homepage_baseline.py`

- [ ] **Step 1: Preserve the Google report findings**

Record these values from the April 30, 2026 mobile report:

- Performance 61
- Accessibility 93
- Best Practices 100
- SEO 100
- FCP 3.4s
- LCP 15.8s
- TBT 50ms
- CLS 0
- Speed Index 7.6s
- Image delivery savings 4,340 KiB
- Total transfer 4,925 KiB

Record these values from the April 30, 2026 desktop report:

- Performance 57
- Accessibility 93
- Best Practices 100
- SEO 100
- FCP 0.8s
- LCP 1.1s
- TBT 11,150ms
- CLS 0.013
- Speed Index 7.3s
- Main-thread work 22.7s
- Long tasks 20
- Non-composited animations 6
- Image delivery savings 4,325 KiB
- Total transfer 5,057 KiB

- [ ] **Step 2: Build repeatable PageSpeed/Lighthouse verification in testbed**

Any repeatable public homepage Lighthouse/PageSpeed check must be a testbed driver. It should write artifacts to `docs/performance/baselines/` and should not live under `tests/`.

- [ ] **Step 3: Optimize public homepage LCP and TBT first**

Start with mobile image delivery and the LCP candidate, then attack desktop main-thread blocking. The desktop report shows 11,150ms TBT and 22.7s main-thread work, so animation/canvas/carousel deferral is part of the first public-site pass.

---

### Task 5: Optimize The Planner Dashboard First Paint

**Files:**
- Modify: `app/admin/planner/page.tsx`
- Modify: `app/api/planner_metrics.py`
- Verify: `testbed/verify_performance_baseline.py`
- Verify: browser timing testbed driver from Task 3

- [ ] **Step 1: Defer non-critical work**

Defer engagement signals and AI insights until the planner dashboard has rendered useful content, unless the baseline proves a different blocker.

- [ ] **Step 2: Keep the blocking payload narrow**

The dashboard should have one primary blocking payload. Secondary analytics, AI, and enrichment work should not delay first useful render.

- [ ] **Step 3: Compare before and after**

Run the testbed baseline before and after the optimization and record whether average seconds, p95 seconds, and slowest endpoint changed.

---

### Task 6: Add Indexes Only After Evidence

**Files:**
- Modify: `app/core/database_indexes.py`
- Verify: `testbed/verify_performance_baseline.py`

- [ ] **Step 1: Use measured evidence**

Only add indexes after the baseline or Mongo profiler shows the planner dashboard is waiting on query shape. Candidate indexes include:

- `rsvps.wedding_id`
- `forms(wedding_id, is_active)`
- `form_responses.wedding_id`
- `weddings(assigned_planner_email, status, date)`

- [ ] **Step 2: Verify index effect with testbed**

Run the same testbed baseline before and after index creation. Do not claim improvement without the artifact comparison.

---

### Task 7: Surface Load Per Dollar In Root Admin

**Files:**
- Modify: `app/api/admin_platform_metrics.py`
- Modify: `app/admin/platform/page.tsx`
- Verify: `testbed/verify_performance_baseline.py`

- [ ] **Step 1: Extend the backend payload**

Add an `efficiency` section to the platform health payload:

```python
"efficiency": {
    "monthly_infrastructure_cost_usd": configured_cost,
    "successful_requests_per_second_per_dollar": value,
    "avg_response_time_seconds": round(overall_avg_ms / 1000, 3),
    "cost_model_configured": configured_cost > 0,
}
```

Read the cost from `MONTHLY_INFRASTRUCTURE_COST_USD`; default to `0` and show `cost_model_configured=false`.

- [ ] **Step 2: Add root-admin cards**

In the Performance tab of `app/admin/platform/page.tsx`, add cards for:

- Average seconds
- P95 seconds
- Slowest blocking endpoint
- Successful requests/sec/$
- Monthly infrastructure cost

- [ ] **Step 3: Verify in the running app**

Use the testbed services and root-admin session to confirm the cards render from the real backend payload.

---

### Task 8: Close The First Baseline

**Files:**
- Create: `docs/performance/baselines/YYYY-MM-DD-one-planner-one-wedding.md`
- Create: `docs/performance/baselines/YYYY-MM-DD-one-planner-one-wedding.json`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run testbed baseline verification**

Run:

```bash
python testbed/testbed.py up --with-frontend
python testbed/verify_metrics_snapshot_no_body.py
python testbed/verify_performance_baseline.py
python testbed/cleanup_metrics_snapshot_no_body_state.py
python testbed/cleanup_performance_baseline_state.py
```

- [ ] **Step 2: Run the read-only Locust smoke baseline**

Run Locust only against read-only scenarios. Keep generated CSV output as input to the human report, but keep live verification in `testbed/`.

- [ ] **Step 3: Write the human report**

The Markdown report must include:

```markdown
# One Planner / One Wedding Performance Baseline

Date:
Environment:
Commit:
Frontend deployment mode:
Backend worker count:
Redis enabled:
Monthly infrastructure cost included:
Variable costs excluded:

## Testbed Timing
- Dashboard backend group measured:
- Slowest blocking endpoint:
- Average seconds:
- P50/P95/max seconds:
- Successful requests/sec/$:

## Browser Dashboard Timing
- Dashboard ready:
- Number of admin requests before usable content:
- Console errors:

## First Bottleneck Hypothesis
- Evidence:
- Next fix:
```

- [ ] **Step 4: Update the changelog**

Add a concise `CHANGELOG.md` entry explaining the baseline, the risk it addresses, and the next follow-up target.

---

## Hostile Review Checklist

Before calling this track ready:

1. Did any new live/performance test land outside `testbed/`?
2. Can the testbed drivers run twice without stale state breaking the second run?
3. Does every mutating verifier have a cleanup pair?
4. Does the baseline distinguish backend endpoint time from browser render time?
5. Does the cost model clearly say what is included and excluded?
6. Did an optimization improve the accepted baseline rather than only feeling faster locally?
7. Did any AI, SMS, email, Stripe, or external mutation run during a read-only load test?
8. Do root-admin metrics and the baseline artifact tell the same story?
9. Did public PageSpeed work accidentally get treated as proof of authenticated planner dashboard performance?
