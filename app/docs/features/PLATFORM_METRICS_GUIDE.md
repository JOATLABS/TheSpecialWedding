# Platform Metrics Implementation Guide (Current State)

## Overview
The Platform Metrics dashboard now pulls authenticated analytics from a dedicated backend aggregator. Instead of estimations,
the UI renders real counts for users, subscriptions, weddings, forms, notifications, and AI usage sourced directly from
MongoDB. Performance monitoring and cache layers remain future enhancements.

## Architecture

### Components
1. **Frontend Dashboard** – `app/admin/metrics/page.tsx`
   - Authenticates requests with the admin token supplied by `AdminContext`
   - Calls `/admin/saas/analytics/platform?timeframe=…` to retrieve pre-computed metrics
   - Renders Apple glass-styled cards for user, subscription, and operational data

2. **Analytics Aggregator** – `app/api/saas_config.py#get_platform_metrics`
   - Normalises timeframes (`7d`, `30d`, `90d`, `1y`) and calculates period start windows
   - Summarises MongoDB collections: `users`, `user_subscriptions`, `subscription_plans`, `weddings`, `guests`, `rsvps`,
     `forms`, `form_responses`, `notifications`, `email_logs`, and `ai_usage`
   - Returns a structured JSON payload containing counts, revenue totals, and plan breakdowns
   - Guards access with `require_root_admin`

## Delivered Metrics

### 1. User Metrics
- **Total Accounts**: `users.count_documents({})`
- **Active Accounts**: `users.count_documents({"is_active": True})`
- **New Accounts (Timeframe)**: `users.count_documents({"created_at": {"$gte": period_start}})`
- **Role Breakdown**: Mongo aggregation grouped by the `role` field

### 2. Subscription Metrics
- **Status Breakdown**: counts for `trial`, `active`, `cancelled`, and `expired` rows in `user_subscriptions`
- **Active Plans**: `subscription_plans.count_documents({"is_active": True})`
- **MRR / ARR**: derived from active subscriptions and plan pricing (monthly plans sum `price_monthly`, yearly plans
  prorated over 12 months)
- **Plan Breakdown**: per-plan active/trial user counts with associated revenue totals

### 3. Operational Metrics
- **Weddings**: total records, active statuses, upcoming dates (>= today), and creations inside the timeframe window
- **Guest & RSVP Totals**: raw counts from `guests` and `rsvps`
- **Forms**: active form count, new forms created in timeframe, and submission totals via `form_responses`

### 4. Communications & Automation
- **Notifications**: counts of `status: "sent"` notifications overall and within the timeframe
- **Email Logs**: total emails plus successful sends within the timeframe from `email_logs`
- **AI Usage**: total and in-period counts from `ai_usage`

### 5. Still Pending
- **System Performance**: uptime, latency, and error-rate instrumentation remains on the backlog
- **Churn Analytics**: dedicated churn and cohort analysis will arrive with subscription lifecycle tracking
- **Caching**: responses are generated on demand; Redis-backed caching is not yet implemented

## Data Sources

- `mongo.get_users_collection()` – role and lifecycle data
- `mongo.db["user_subscriptions"]` – subscription assignments with billing interval metadata
- `mongo.get_subscription_plans_collection()` – plan pricing for revenue calculations
- `mongo.get_weddings_collection()` – project cadence and upcoming events
- `mongo.get_forms_collection()` / `mongo.get_form_responses_collection()` – planner engagement metrics
- `mongo.db["notifications"]`, `mongo.db["email_logs"]`, `mongo.get_ai_usage_collection()` – outbound communication audit

The aggregator guards against malformed timestamps via `_normalize_datetime` helpers before counting timeframe-bound records.

## Security & Access Control

- The `/admin/saas/analytics/platform` endpoint is protected by `require_root_admin`
- Requests without a bearer token return HTTP 401/403
- The frontend relies on `AdminContext` to inject the token header; missing tokens surface a descriptive error message
- Audit logging for analytics access is not yet implemented and should be captured in the security backlog

## API Usage

### Fetching Platform Analytics
```typescript
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const response = await fetch(
  `${baseUrl}/admin/saas/analytics/platform?timeframe=${timeframe}`,
  {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  }
);
const metrics = await response.json();
```

### Available Timeframes
- `7d` – last 7 days
- `30d` – last 30 days (default)
- `90d` – last 90 days
- `1y` – last 365 days

### Response Shape
```json
{
  "generated_at": "2025-02-03T18:12:45.123456",
  "timeframe": "30d",
  "users": {
    "total": 245,
    "active": 198,
    "new_in_period": 24,
    "growth_rate": 9.8,
    "role_breakdown": {
      "wedding_planner": 180,
      "vendor": 40,
      "root_admin": 5
    }
  },
  "subscriptions": {
    "total": 210,
    "status_breakdown": {
      "trial": 18,
      "active": 180,
      "cancelled": 8,
      "expired": 4
    },
    "active_plans": 3,
    "monthly_recurring_revenue": 9850,
    "yearly_recurring_revenue": 21600,
    "projected_annual_revenue": 118200,
    "plan_breakdown": [
      {
        "plan_id": "plan_basic",
        "plan_name": "Basic",
        "active_users": 120,
        "trial_users": 10,
        "monthly_revenue": 6000,
        "yearly_revenue": 14400,
        "price_monthly": 50,
        "price_yearly": 480
      }
    ]
  },
  "operations": {
    "weddings": {
      "total": 68,
      "active": 52,
      "upcoming": 34,
      "created_in_period": 6,
      "guest_total": 5240,
      "rsvp_total": 3980
    },
    "forms": {
      "total": 145,
      "new_in_period": 12,
      "responses_total": 2840,
      "responses_in_period": 420
    },
    "communications": {
      "notifications_sent": 980,
      "notifications_in_period": 112,
      "email_logs_total": 4380,
      "emails_sent_in_period": 620,
      "ai_events_total": 840,
      "ai_events_in_period": 74
    }
  }
}
```

### Error Handling
- Invalid timeframe strings return HTTP 400 with `"Invalid timeframe. Use one of: 7d, 30d, 90d, 1y."`
- Database errors propagate as HTTP 500 responses with diagnostic detail for root admins

## Follow-Up Enhancements
- Add telemetry (uptime, latency, cache hit-rate) once observability tooling is integrated
- Introduce Redis caching to reduce load on frequently accessed collections
- Extend analytics to calculate churn, cohort analysis, and per-planner engagement trends
