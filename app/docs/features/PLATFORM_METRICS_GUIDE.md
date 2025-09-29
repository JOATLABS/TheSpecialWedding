# Platform Metrics Implementation Guide (Current State)

## Overview
The Platform Metrics page in the admin area currently synthesises high-level counts using existing admin endpoints. A dedicated analytics service has **not** been built yet, so most of the metrics shown are estimates or hard-coded placeholders.

## Architecture

### Components in the codebase today
1. **Frontend Dashboard**: `app/admin/metrics/page.tsx`
   - Calls `/api/admin/users` and `/api/admin/subscription-plans`
   - Derives metrics client-side with lightweight calculations
   - Fills in missing values (usage, performance, revenue) with constants until real data is available

2. **API Endpoints / Services**
   - There is no `platform_analytics_service.py` module
   - `/api/saas/analytics/overview` is referenced in the UI but is not implemented; the call is wrapped in a `catch(() => null)` guard
   - No Redis caching or background aggregation exists

## Metrics Categories

### 1. User Metrics (derived client-side)
- **Total Users**: Count of `/api/admin/users`
- **Active Users**: Filtered by `is_active` flag
- **New Users This Month**: Calculated by comparing `created_at` timestamps
- **Growth Rate**: Derived from current month sign-ups vs total

### 2. Subscription Metrics (approximations)
- **Total Subscriptions**: Users with a `subscription_plan_id`
- **Active Subscriptions**: Users with `subscription_status === 'active'`
- **Trial Users**: Users with `subscription_status === 'trialing'`
- **Churned This Month**: Hard-coded to `0` pending activity logs
- **MRR / ARR**: Estimated by multiplying plan counts by assumed prices

### 3. Usage Metrics (placeholders)
- **Weddings Created**: Currently `0`
- **Forms Created**: Currently `0`
- **Guests Managed**: Currently `0`
- **Emails Sent**: Currently `0`
- **SMS Sent**: Currently `0`

### 4. Performance Metrics (static placeholders)
- **Uptime**: Hard-coded to `99.9`
- **Average Response Time**: Hard-coded to `245`
- **Error Rate**: Hard-coded to `0.1`
- **API Calls Today**: Hard-coded to `0`
- **P50/P95/P99**: Not calculated
- **Cache Hit Rate**: Not calculated

### 5. Revenue Metrics (estimates)
- **Total Revenue**: Active subscriber count × assumed yearly plan price
- **Monthly Growth**: Uses a constant `15.3` when new sign-ups exist
- **ARPU**: Fixed estimate
- **Customer LTV**: Fixed estimate

## Data Sources

### Real-Time Data Collection
Not yet implemented. Future work should aggregate from:
- MongoDB collections: users, weddings, forms, guests, subscriptions
- Monitoring tooling (once built) for performance data
- Audit logs for API usage, errors, and security events

### Performance Monitoring Integration
```python
# PerformanceMonitoringMiddleware stores metrics in Redis:
{
    "/api/endpoint": {
        "avg_response_time": 0.245,
        "request_count": 1234,
        "percentiles": {
            "p50": 0.200,
            "p95": 0.450,
            "p99": 0.890
        }
    }
}
```

## Caching Strategy

### Redis Caching (planned)
- Metrics caching has not been implemented
- Once the analytics service exists, define cache keys such as `analytics:{metric_type}:{timeframe}:{date-hour}`
- Establish TTL and invalidation strategy alongside the service work

### Cache Warming (planned)
- Background aggregation tasks have not been created
- `/api/saas/analytics/refresh-cache` does not exist yet
- Metrics currently fall back to client-side calculations only

## Security & Access Control

### ROOT_ADMIN Only Access
Access control is handled by existing admin context/auth flows. Dedicated analytics endpoints should enforce ROOT_ADMIN scoping when they are built.

### Audit Logging (not yet available)
- No audit trail is captured for the placeholder metrics page
- Logging requirements should be captured in the backlog when the backend is implemented

## API Usage

### Fetching Overview Metrics
```typescript
// Frontend implementation (with fallback until endpoint exists)
const analyticsResponse = await apiRequest('/api/saas/analytics/overview', 'GET')
  .catch(() => null);

if (!analyticsResponse) {
  // Use derived data instead of backend metrics
}
```

### Available Timeframes
- `7days`: Last 7 days
- `30days`: Last 30 days (default)
- `90days`: Last 90 days
- `1year`: Last year

### Response Format
```json
{
    "success": true,
    "data": {
        "users": {
            "total": 1234,
            "active": 890,
            "new_this_month": 45,
            "growth_rate": 12.5
        },
        "subscriptions": {
            "total": 456,
            "active": 320,
            "trial": 89,
            "churned_this_month": 12,
            "mrr": 9280,
            "arr": 111360
        },
        "usage": {
            "weddings_created": 678,
            "forms_created": 234,
            "guests_managed": 45678,
            "emails_sent": 12345,
            "sms_sent": 5678
        },
        "performance": {
            "uptime": 99.95,
            "avg_response_time": 245,
            "error_rate": 0.05,
            "api_calls_today": 23456
        },
        "revenue": {
            "total_revenue": 234567,
            "monthly_growth": 15.3,
            "average_revenue_per_user": 48,
            "lifetime_value": 1200
        }
    },
    "timeframe": "30days"
}
```

## Frontend Testing IDs

The metrics dashboard includes testing IDs for automated testing:
- `timeframe-selector`: Timeframe dropdown
- `metric-total-users`: Total users card
- `metric-active-users`: Active users card
- `metric-mrr`: MRR card
- `metric-arr`: ARR card
- `value-total-users`: Total users value
- `value-active-users`: Active users value
- `value-mrr`: MRR value
- `value-arr`: ARR value

## Environment Configuration

Required environment variables in `.env`:
```env
# Application Settings
ENVIRONMENT=development
APP_NAME=Wedding WebApp API
APP_VERSION=1.3.0

# Redis Configuration (for caching)
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Performance Monitoring
ENABLE_METRICS=true
```

## Troubleshooting

### Common Issues

1. **Metrics not updating**
   - Check Redis connection: `docker logs wedding-redis`
   - Force cache refresh: Call `/api/saas/analytics/refresh-cache`
   - Verify MongoDB connectivity

2. **Performance metrics showing zeros**
   - Ensure PerformanceMonitoringMiddleware is enabled
   - Check Redis for `performance_metrics` key
   - Verify middleware ordering in `app/main.py`

3. **Access denied errors**
   - Verify user has `is_root_admin` flag
   - Check authentication token validity
   - Review audit logs for access attempts

### Debug Commands
```bash
# Check Redis cache
docker exec -it wedding-redis redis-cli
> GET analytics:overview:30days:*
> GET performance_metrics

# Monitor API logs
docker logs -f wedding-api | grep analytics

# Check MongoDB metrics
docker exec -it wedding-mongo mongosh
> use wedding
> db.users.countDocuments({is_active: true})
```

## Future Enhancements

### Planned Features
1. **Real-time WebSocket updates**: Live metric updates without refresh
2. **Custom date ranges**: User-defined timeframe selection
3. **Metric alerts**: Threshold-based notifications
4. **Trend analysis**: Historical comparisons and predictions
5. **Export scheduling**: Automated report generation
6. **Metric drill-downs**: Detailed views per metric category

### Performance Optimizations
1. **Materialized views**: Pre-aggregated metrics in MongoDB
2. **Time-series database**: InfluxDB for performance metrics
3. **GraphQL subscriptions**: Efficient real-time updates
4. **Worker queues**: Background metric calculation

## Testing

### Unit Tests
Located in `tests/unit/test_platform_analytics_service.py`:
- Metric calculation accuracy
- Cache hit/miss scenarios
- Error handling

### Integration Tests
Located in `tests/integration/test_metrics_dashboard.py`:
- API endpoint responses
- Access control verification
- Data consistency checks

### Playwright E2E Tests
Located in `tests/e2e/test_metrics_dashboard.spec.ts`:
- Dashboard loading
- Timeframe switching
- Metric value updates
- Error state handling

## Maintenance

### Regular Tasks
1. **Weekly**: Review cache hit rates and optimize TTLs
2. **Monthly**: Analyze slow queries and add indexes
3. **Quarterly**: Review metric definitions with stakeholders

### Monitoring Checklist
- [ ] Redis memory usage < 80%
- [ ] API response time < 500ms
- [ ] Cache hit rate > 70%
- [ ] No error spikes in logs
- [ ] Metrics match manual calculations

## Support

For issues or questions:
1. Check this documentation
2. Review error logs in Docker containers
3. Contact the development team
4. File an issue in the project repository