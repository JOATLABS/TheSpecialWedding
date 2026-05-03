# Performance Optimizations

This directory contains documentation for all performance optimizations implemented in the Wedding Web App.

## Completed Optimizations

### Active. [Performance Baseline And Efficiency Program](./performance-baseline-and-efficiency.md)
- Establishes the one-planner/one-wedding baseline before optimization
- Tracks average seconds, p50/p95/p99, dashboard-ready browser timing, and load per monthly infrastructure dollar
- Keeps live/performance tests for this track under `testbed/`
- Uses `testbed/verify_performance_baseline.py` for live one-planner baseline verification
- Uses `docs/performance/baselines/` for durable baseline artifacts
- Status: Active next-development track as of April 30, 2026

### Active. [Google PageSpeed Insights Baseline - Public Homepage](./pagespeed-insights-2026-04-30.md)
- Captures the April 30, 2026 mobile and desktop PageSpeed reports for `https://thespecialwedding.io/`
- Current public homepage scores: mobile Performance 61, desktop Performance 57, Accessibility 93, Best Practices 100, SEO 100
- Mobile bottleneck: 15.8s LCP and 4,925 KiB transfer size
- Desktop bottleneck: 11,150ms TBT, 22.7s main-thread work, and 5,057 KiB transfer size
- Keeps repeatable PageSpeed/Lighthouse verification under `testbed/`

### 0. [Locust Load Test Plan](./locust-load-test-plan.md)
- Added a safe, read-only Locust harness for public wedding, planner, and couple traffic
- Uses repo-local `loadtests/locustfile.py`
- Completed: April 2, 2026

### 1. [Database Indexes](./database-indexes.md)
- Added 20+ compound indexes
- 60-70% query performance improvement
- Completed: January 21, 2025

### 2. [Bulk Query Optimizations](./bulk-optimizations.md)
- Eliminated N+1 query problems
- 81% overall performance improvement
- Completed: January 21, 2025

### 3. Redis Caching
- Enabled Redis caching configuration
- Ready for implementation
- Status: Configuration complete

## Performance Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Page Load Time | 2.8s | 0.49s | 82% faster |
| Database Queries | 311 | 7 | 98% reduction |
| Guest Data Fetch | 1200ms | 200ms | 83% faster |
| RSVP Loading | 800ms | 200ms | 75% faster |

## Performance Verification

Legacy local comparison utilities live in `/scripts/`:
- `test_bulk_endpoints.py` - Tests all bulk endpoints
- `test_n1_fix.py` - Performance comparison test
- `add_performance_indexes.py` - Database index creation

Live performance baseline tests live in `testbed/`:
- `testbed/verify_metrics_snapshot_no_body.py` - Proves the scheduled metrics snapshot endpoint accepts the Cloudflare cron's no-body POST shape
- `testbed/cleanup_metrics_snapshot_no_body_state.py` - Removes the inserted platform metrics snapshot
- `testbed/verify_performance_baseline.py` - Seeds one paid planner with one wedding, measures blocking planner-dashboard backend endpoints, and writes a baseline JSON artifact
- `testbed/cleanup_performance_baseline_state.py` - Cleans the isolated plus-variant planner fixture
- `testbed/performance_cost_model.example.json` - Example infrastructure-cost input for load-per-dollar calculations
- Future: `testbed/verify_pagespeed_public_homepage_baseline.py` should capture repeatable public homepage Lighthouse/PageSpeed artifacts

Load testing inputs use:
- `loadtests/locustfile.py` - Mixed read-only Locust scenarios for public, planner, and couple traffic
- `docs/performance/locust-load-test-plan.md` - Runbook, stages, guardrails, and success criteria
- `docs/performance/baselines/` - Accepted baseline reports and JSON artifacts

## Monitoring

To monitor performance improvements:
1. Check MongoDB Atlas performance metrics
2. Review application logs for query times
3. Use browser developer tools Network tab
4. Run performance test scripts regularly

## Next Steps

1. **Run the testbed one-planner/one-wedding baseline** before changing the planner dashboard
2. **Identify the slowest blocking path** across browser boot, auth/profile calls, planner metrics, engagement signals, AI insights, and database queries
3. **Tie capacity to cost** with successful requests/sec/$ and dashboard sessions/hour/$
4. **Optimize against the accepted baseline** instead of relying on local happy-path checks

## Related Documentation

- [Security Documentation](../security/)
- [Architecture Documentation](../architecture/)
- [API Documentation](../backend/)
