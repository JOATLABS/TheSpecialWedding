# Performance Baseline And Efficiency Program

Status: active next-development track as of 2026-04-30.

## Why This Exists

The platform feels slow with only one planner and one wedding. That means the first problem to solve is not large-scale throughput; it is attribution. We need to know whether the delay comes from browser boot, duplicated auth/profile calls, planner dashboard fan-out, database scans, AI insight loading, deployment runtime limits, or infrastructure cold paths.

The goal is to create a baseline before optimizing, then improve against that baseline until the planner experience feels fast with today's tiny data shape and remains measurable as traffic grows.

## North-Star Performance Questions

1. How many seconds does `/admin/planner` take before useful dashboard content is visible?
2. Which request is the slowest blocking request on first dashboard load?
3. What are average, p50, p95, p99, and max backend seconds per endpoint?
4. How many successful requests per second do we get per monthly infrastructure dollar?
5. Does latency grow because of request fan-out, database query shape, frontend bundle/render cost, or server resource saturation?

## Current Measurement Spine

- Backend request timing: `audit_logs.response_time_ms`
- Root-admin infrastructure view: `/admin/platform/health`
- Historical snapshots: `platform_metrics`
- Scheduled snapshot ingestion: Cloudflare Worker `metrics-snapshot-cron.js` calling `POST /metrics/snapshot`
- Live metrics snapshot contract: `testbed/verify_metrics_snapshot_no_body.py`
- Live one-planner baseline driver: `testbed/verify_performance_baseline.py`
- Load harness: `loadtests/locustfile.py`
- Existing Locust artifacts: `output/locust/*_stats.csv`
- Browser truth: Playwright trace/navigation timing for `/admin/planner`
- Public homepage PageSpeed truth: `docs/PageSpeed Insights.pdf`, `docs/Desktop PageSpeed Insights.pdf`, and `docs/performance/pagespeed-insights-2026-04-30.md`

## First Diagnostic Scope

Measure these surfaces first:

- `GET /admin/profile`
- `GET /admin/planner/metrics`
- `GET /admin/engagement-signals`
- `GET /admin/ai/weddings/{wedding_id}/insights`
- `/admin/planner` browser navigation timing
- Public `GET /{slug}` and `GET /{slug}/gallery`

The planner dashboard currently starts several independent requests during mount. `/admin/planner/metrics` then reads weddings, guests, RSVPs, plus-ones, subscriptions, users, plans, and activity logs. That may still be fine for one wedding, but it must be proven with timings instead of guessed from code.

## Baseline Artifact Contract

Each accepted baseline report must include:

- Date, environment, commit SHA, deployment mode
- Frontend URL and backend URL
- Backend worker count and Redis enabled/disabled state
- Test data shape, especially planner count, wedding count, guest count, RSVP count
- Monthly infrastructure cost included in the calculation
- Variable vendor costs excluded from the calculation
- Request count, failure rate, avg seconds, p50, p95, p99, max
- Successful requests/sec/$
- Browser dashboard-ready timing
- First bottleneck hypothesis and next fix

Baseline reports live in:

```text
docs/performance/baselines/
```

The live baseline test belongs in `testbed/`, not in `scripts/` or a generic
pytest suite, because it seeds real Mongo/Stripe test-mode state and measures a
running backend. New live/performance tests for this track should be testbed
drivers with cleanup pairs. The first drivers are:

```text
testbed/verify_metrics_snapshot_no_body.py
testbed/cleanup_metrics_snapshot_no_body_state.py
testbed/verify_performance_baseline.py
testbed/cleanup_performance_baseline_state.py
```

## Cost Model

Use monthly infrastructure cost only unless a report explicitly opts into variable vendor costs.

Included by default:

- Coolify/DigitalOcean server cost
- Mongo resource cost
- Redis resource cost
- Required always-on monitoring infrastructure

Excluded by default:

- Twilio SMS
- Resend email
- Google Gemini/AI usage
- Stripe processing fees
- R2 storage/egress unless entered explicitly

Primary efficiency metric:

```text
successful_requests_per_second_per_dollar =
  (locust_requests_per_second - locust_failures_per_second)
  / monthly_infrastructure_usd
```

## Recommendations

1. Treat the current one-planner slowness as a performance incident until the baseline proves otherwise.
2. Run `testbed/verify_performance_baseline.py` before changing dashboard code, then rerun it after every optimization.
3. Make `/admin/planner/metrics` the only blocking planner-dashboard data request before useful content renders.
4. Defer engagement signals and AI insights until after the dashboard is usable, unless the baseline proves they are already non-blocking.
5. Collapse duplicate auth/profile checks during first navigation; `/admin/profile` should not be called repeatedly to render one page.
6. Add indexes only after measured endpoint or Mongo evidence points to the query shape.
7. Record infrastructure cost with the baseline, but exclude SMS, email, AI, Stripe processing, and storage egress unless the report explicitly opts in.
8. Add root-admin cards for average seconds, p95 seconds, slowest blocking endpoint, monthly infrastructure cost, and successful requests/sec/$.
9. Keep public homepage PageSpeed work in its own lane: the April 30 reports show mobile Performance 61 with 15.8s LCP and 4,925 KiB transfer, plus desktop Performance 57 with 11,150ms TBT and 22.7s main-thread work. Optimize public image/LCP and public main-thread work separately from planner dashboard API latency.

## Google PageSpeed Public Homepage Baseline

The April 30, 2026 Google PageSpeed PDFs for `https://thespecialwedding.io/` are now captured as a public-site baseline:

[`docs/performance/pagespeed-insights-2026-04-30.md`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/docs/performance/pagespeed-insights-2026-04-30.md)

These reports are not evidence that planner dashboard APIs are slow. They are evidence that the public homepage needs mobile LCP/image-delivery work and desktop main-thread/TBT work. Treat these as related but separate performance lanes.

## First Improvement Bets

Do these only after the one-planner baseline identifies the bottleneck:

1. Defer AI insights and engagement signals until the planner dashboard has rendered useful content.
2. Add missing planner-dashboard indexes only where the measured slow queries prove they are needed.
3. Collapse duplicate profile/session checks on first planner navigation.
4. Cache planner dashboard aggregates briefly for the same actor and same wedding set.
5. Separate frontend boot/hydration timing from API timing so bundle work is not blamed on Mongo.

## Implementation Plan

The detailed task plan is stored at:

[`docs/superpowers/plans/2026-04-30-performance-baseline-and-efficiency.md`](/Users/emmanuelakinwale/Desktop/WeddingWebApp/docs/superpowers/plans/2026-04-30-performance-baseline-and-efficiency.md)
