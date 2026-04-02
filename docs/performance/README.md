# Performance Optimizations

This directory contains documentation for all performance optimizations implemented in the Wedding Web App.

## Completed Optimizations

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

## Testing Scripts

All performance testing scripts are located in `/scripts/`:
- `test_bulk_endpoints.py` - Tests all bulk endpoints
- `test_n1_fix.py` - Performance comparison test
- `add_performance_indexes.py` - Database index creation

Load testing uses:
- `loadtests/locustfile.py` - Mixed read-only Locust scenarios for public, planner, and couple traffic
- `docs/performance/locust-load-test-plan.md` - Runbook, stages, guardrails, and success criteria

## Monitoring

To monitor performance improvements:
1. Check MongoDB Atlas performance metrics
2. Review application logs for query times
3. Use browser developer tools Network tab
4. Run performance test scripts regularly

## Next Steps

1. **Implement Redis caching** for frequently accessed data
2. **Add pagination** for large datasets
3. **Implement GraphQL** for flexible data fetching
4. **Add WebSocket** support for real-time updates

## Related Documentation

- [Security Documentation](../security/)
- [Architecture Documentation](../architecture/)
- [API Documentation](../backend/)
