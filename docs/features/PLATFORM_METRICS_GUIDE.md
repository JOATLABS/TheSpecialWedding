# Platform Metrics Implementation Guide

## Overview
The Platform Metrics system provides comprehensive analytics and insights for ROOT_ADMIN users to monitor platform health, user engagement, revenue metrics, and system performance.

## Architecture

### Components
1. **Backend Service**: `app/services/platform_analytics_service.py`
   - Aggregates data from multiple collections (users, weddings, forms, subscriptions, etc.)
   - Calculates real-time metrics with caching support
   - Integrates with performance monitoring middleware for actual response times

2. **API Endpoints**: `app/api/platform_analytics.py`
   - `/api/saas/analytics/overview` - Main metrics endpoint
   - `/api/saas/analytics/{metric_type}` - Detailed metrics by category
   - `/api/saas/analytics/export` - Export metrics in JSON/CSV
   - `/api/saas/analytics/refresh-cache` - Force cache refresh

3. **Frontend Dashboard**: `app/admin/metrics/page.tsx`
   - Interactive dashboard with timeframe selection
   - Real-time data fetching from backend API
   - Responsive grid layout with metric cards

## Metrics Categories

### 1. User Metrics
- **Total Users**: All registered users in the system
- **Active Users**: Users who have logged in recently
- **New Users This Month**: Registrations in current month
- **Growth Rate**: Month-over-month growth percentage

### 2. Subscription Metrics
- **Total Subscriptions**: All subscription records
- **Active Subscriptions**: Currently active paid subscriptions
- **Trial Users**: Users on free trial
- **Churned This Month**: Cancelled subscriptions
- **MRR**: Monthly Recurring Revenue
- **ARR**: Annual Recurring Revenue (MRR × 12)

### 3. Usage Metrics
- **Weddings Created**: Total weddings in the system
- **Forms Created**: Custom forms built by users
- **Guests Managed**: Total guests across all weddings
- **Emails Sent**: Transactional emails delivered
- **SMS Sent**: SMS notifications sent

### 4. Performance Metrics
- **Uptime**: System availability percentage
- **Average Response Time**: Real-time API response times from monitoring
- **Error Rate**: Percentage of failed requests
- **API Calls Today**: Total API requests processed
- **P50/P95/P99**: Response time percentiles
- **Cache Hit Rate**: Redis cache effectiveness

### 5. Revenue Metrics
- **Total Revenue**: Cumulative revenue generated
- **Monthly Growth**: Revenue growth percentage
- **ARPU**: Average Revenue Per User
- **Customer LTV**: Lifetime Value estimation

## Data Sources

### Real-Time Data Collection
The system collects metrics from multiple sources:
- MongoDB collections: users, weddings, forms, guests, subscriptions
- Redis cache: Performance metrics from PerformanceMonitoringMiddleware
- Audit logs: API usage, errors, and security events

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

### Redis Caching
- Metrics are cached with hourly granularity
- Cache key format: `analytics:{metric_type}:{timeframe}:{date-hour}`
- TTL: 1 hour for recent data, longer for historical
- Automatic cache invalidation on data changes

### Cache Warming
- Background tasks pre-calculate common metrics
- Cache refresh endpoint for manual updates
- Graceful fallback to database queries if cache misses

## Security & Access Control

### ROOT_ADMIN Only Access
```python
if not current_user.is_root_admin:
    raise HTTPException(
        status_code=403,
        detail="Access denied. ROOT_ADMIN role required."
    )
```

### Audit Logging
- All metrics access is logged
- Failed access attempts recorded
- Export operations tracked for compliance

## API Usage

### Fetching Overview Metrics
```typescript
// Frontend implementation
const response = await apiRequest(
    `/api/saas/analytics/overview?timeframe=${timeframe}`,
    'GET'
);
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