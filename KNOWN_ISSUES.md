# Known Issues

1. **Cross-origin resource compatibility**
   `SecurityHeadersMiddleware` now applies COEP/COOP/CORP only to `/api/` paths and uses a scoped CSP. Public/admin pages no longer get cross-origin isolation headers, which avoids blocking third-party assets (e.g., Google Fonts/jsDelivr). If you re-enable isolation on pages, verify external assets send compatible headers (CORP/CORS) or add explicit allowances.

2. **Activity logging for user actions not implemented**
   The `/planner/activity-log` endpoint and `recent_activity` field in `/planner/metrics` return empty arrays. Activity logging for user-facing actions (RSVP submissions, guest additions, email sends, etc.) is not yet implemented.

   **What exists:**
   - `audit_logs` collection - HTTP request auditing via `app/middleware/audit_logging.py` (security-focused)
   - `security_audit_logs` collection - Security events via `app/services/security_audit_service.py`
   - `domain_events` collection - Event sourcing defined in `app/core/events.py` (not actively used)

   **What's missing:**
   - `activity_logs` collection for user-facing activity summaries
   - `ActivityLogService` to capture and store user actions
   - Hooks in services (guest_service, rsvp_service, reminder_service) to log activities
   - Query logic in `/planner/activity-log` endpoint

   **Affected files:**
   - `app/api/planner_metrics.py` (lines 230-254, 217-219)

   **Implementation approach:**
   1. Add `get_activity_logs_collection()` to `app/core/database.py`
   2. Create `app/services/activity_log_service.py` with methods to log activities
   3. Add activity logging calls to existing services when actions occur
   4. Update `/planner/activity-log` endpoint to query the collection
   5. Populate `recent_activity` in metrics from actual data

3. **Revenue metrics are placeholders**
   The `revenue_metrics` field in `/planner/metrics` returns zeros. Real revenue tracking requires integration with Stripe subscription data.

   **Affected files:**
   - `app/api/planner_metrics.py` (lines 212-215)

   **Implementation approach:**
   1. Query `users` collection for subscription data (stripe_subscription_id, subscription_status)
   2. Optionally integrate with Stripe API for actual payment amounts
   3. Calculate metrics based on subscription plans and wedding counts

4. **Navigation omits several planner and root admin pages**
   The top navigation defined in `app/admin/components/AdminHeader.tsx` does not expose multiple existing routes, so those pages are effectively unreachable without typing URLs directly.

   **Missing for wedding planners:**
   - `/admin/planner` (planner dashboard)
   - `/admin/planner/activity-log` (planner activity log)
   - `/admin/vendors` (vendor management)
   - `/admin/billing` (subscription management)
   - `/admin/budget/estimate`, `/admin/budget/templates`, `/admin/budget/quotes` (budget flows)

   **Missing for root admin:**
   - `/admin/platform/metrics` and `/admin/platform/errors` (platform diagnostics)
   - `/admin/import` (guest import)
   - `/admin/billing` (subscription management)

   **Impact:** Users with valid roles cannot navigate to these pages via the UI header; routes require manual URL entry or deep links.

   **Fix:** Expand `getNavLinks` in `app/admin/components/AdminHeader.tsx` (and mobile/desktop rendering) to include these paths per role, or add a dedicated planner sidebar with all planner routes.

5. **Admin UI uses API paths that don't exist**
   Several admin pages call endpoints prefixed with `/admin/...` that the backend does not expose, so the UI silently falls back to empty data.

   **Examples:**
   - `app/admin/notifications/page.tsx` calls `/admin/notification-templates` and `/admin/notifications`; backend exposes `/notification-templates` and `/notifications` (no `/admin` prefix).
   - `app/admin/support/page.tsx` calls `/api/admin/support/*` (status/respond/metrics), but backend support API routes are `/tickets`, `/tickets/{id}`, `/analytics`, etc. with no `/admin/support` prefix.
   - `app/admin/billing/page.tsx` calls `/admin/users/{userId}/subscription`; backend route is `/users/{user_id}/subscription` (no `/admin` prefix) and expects ObjectId, while the UI pulls `userId` from localStorage string.

   **Impact:** Admin pages render empty lists or fail actions because they never hit live endpoints.

   **Fix:** Align frontend paths with backend routes (drop `/admin` prefix and correct path segments/IDs), or add matching prefixed routes on the backend.

6. **Navigation omits several planner and root admin pages**
   (see issue #4 above; kept numbering stable after fixes)

7. **Wedding metering/usage flow has gaps and duplicate routes**
   The weddings API has overlapping routes and brittle metering that can double-charge or fail silently.

   **Problems:**
   - `app/api/wedding.py` declares two `/weddings` POST handlers (one typed `WeddingModel`, one raw `dict`) and two `/weddings` GET handlers; FastAPI will only honor the last definition, so one codepath (with metering logic differences) is effectively dead.
   - Metered usage reports call `stripe_service.report_meter_event` without checking `last_billed_at` or current period boundaries, so repeated create retries can double-bill. Deletions/updates never adjust usage or meter events.
   - Wedding creation persists via `WeddingService` which uses Motor sync-style calls (no `await`) and stores `_id` as provided; subsequent `update_one` in metering uses that `_id` directly, which will fail if the stored `_id` is an `ObjectId`.

   **Impact:** Inconsistent/duplicate route handling and non-idempotent metering can miscount wedding-based billing or fail to update `last_billed_at`.

   **Fix:** Consolidate `/weddings` routes, make `WeddingService` async/Motor-safe, gate metering with idempotency (e.g., check `last_billed_at` within period), and adjust usage on delete/restore flows.
