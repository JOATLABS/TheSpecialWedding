# Behavioral Analytics — Known Issues

**Date**: 2026-04-02 (updated after deep code review)
**Version**: 2.28.0
**Scope**: `behavioral_analytics_service.py`, `behavioral_analytics.py`, `behavioralAnalyticsApi.ts`, admin/planner/couple dashboard integrations

---

## CRITICAL — Server won't start

### C1: Import crash — `get_current_active_user` does not exist
- **File**: `app/api/behavioral_analytics.py` line 14
- **Description**: `from app.dependencies.auth_extended import require_root_admin, get_current_active_user` — the function `get_current_active_user` does not exist in `auth_extended.py`. The correct name is `get_current_user_extended`. Used on lines 59, 90, 118.
- **Impact**: Server crashes on startup with `ImportError`.
- **Fix**: Change to `get_current_user_extended`. Already partially applied but see C2.
- **Status**: PARTIALLY FIXED (import name changed, but see C2 for the second import crash)

### C2: Import crash — `ExtendedAuthUser` imported from wrong module
- **File**: `app/api/behavioral_analytics.py` line 16
- **Description**: `from app.models.user_extended import ExtendedAuthUser` — the module `app/models/user_extended.py` contains `UserModel` and `AdminUserModel`, not `ExtendedAuthUser`. The class is defined in `app/dependencies/auth_extended.py`. Every other API file imports it from there (e.g., `app/api/stripe_payment.py`, `app/api/budget.py`, `app/api/contracts.py`).
- **Impact**: Server crashes on startup with `ImportError` even after C1 is fixed.
- **Fix**: Change to `from app.dependencies.auth_extended import require_root_admin, get_current_user_extended, ExtendedAuthUser` and remove line 16.
- **Status**: OPEN

---

## CRITICAL — Security

### C3: Admin non-responders and budget-breakdown endpoints have NO authorization
- **File**: `app/api/behavioral_analytics.py` lines 88-128
- **Description**: The `/weddings/{wedding_id}/non-responders` and `/weddings/{wedding_id}/budget-breakdown` endpoints use `Depends(get_current_user_extended)` which only authenticates — it does not authorize. Any authenticated user (vendor, team member with no permissions, any planner) can query ANY wedding's guest list and budget by guessing a wedding ID. The codebase pattern for wedding-scoped endpoints is `Depends(require_team_or_planner)` + `check_wedding_access(current_user, wedding_id)`.
- **Impact**: Unauthorized data access. A planner can see another planner's guest details and budget.
- **Fix**: Replace `Depends(get_current_user_extended)` with `Depends(require_team_or_planner)` and add `check_wedding_access(current_user, wedding_id)` call before querying.
- **Status**: OPEN

### C4: Engagement signals endpoint skips team permission enforcement
- **File**: `app/api/behavioral_analytics.py` lines 58-76
- **Description**: Uses `Depends(get_current_user_extended)` with a hand-rolled `if current_user.role not in (...)` check. The codebase pattern (see `planner_metrics.py`) is `Depends(require_team_or_planner)` + `enforce_team_permission(current_user, "view_analytics")`. Without this, team members without analytics permission can see engagement data. Additionally, the query doesn't scope to accessible weddings via `get_accessible_wedding_ids(current_user)` — a team member with `assigned` wedding access can see signals for ALL of the planner's weddings.
- **Impact**: Team members bypass permission controls. Breaks the team permission model.
- **Fix**: Use `Depends(require_team_or_planner)`, call `enforce_team_permission(current_user, "view_analytics")`, and use `get_accessible_wedding_ids(current_user)` to scope the query.
- **Status**: OPEN

---

## CRITICAL — Data correctness

### C5: `state_history` is never written anywhere in the codebase
- **File**: `app/services/behavioral_analytics_service.py` lines 526-540
- **Description**: The MRR trial-to-paid conversion query relies on `state_history` entries like `{from: "trial", to: "active", at: "..."}`. But searching the entire codebase (all `.py`, `.ts`, `.tsx` files), `state_history` is only defined as a schema field in `app/models/subscription.py` with `default_factory=list`. No service, webhook handler, or API endpoint ever `$push`es entries into it. The field is always an empty array `[]`.
- **Impact**: Trial conversion count and rate will ALWAYS be 0. The MRR movement section on the admin dashboard will always show 0 trial conversions.
- **Fix**: Either (a) implement `state_history` writes in the Stripe webhook handler when subscription status transitions occur, or (b) rewrite the trial conversion query to use an alternative signal — e.g., subscriptions where `status == "active"` AND `trial_start_date` exists AND `trial_start_date` was within the measurement window.
- **Status**: OPEN

### C6: `state_history.at` string comparison is fragile and mismatched
- **File**: `app/services/behavioral_analytics_service.py` line 533
- **Description**: Even if `state_history` were populated, the `$elemMatch` compares `"at": {"$gte": thirty_days_ago.isoformat()}`. Python's `datetime.isoformat()` produces `"2026-03-03T00:00:00+00:00"` while the model example shows `at` stored as `"2025-08-15T10:30:00Z"`. The different timezone suffix format (`+00:00` vs `Z`) breaks lexicographic comparison. If `at` were stored as a proper BSON datetime instead of a string, the string comparator would fail silently.
- **Impact**: Even if state_history were populated, the query would return incorrect or no results.
- **Fix**: Store `at` as a BSON datetime, and compare with a datetime object not an ISO string.
- **Status**: OPEN

### C7: Retention cohort month boundary math skips months
- **File**: `app/services/behavioral_analytics_service.py` line 305
- **Description**: `cohort_start = (now.replace(day=1) - timedelta(days=months_ago * 30)).replace(day=1, ...)`. For April 1 with `months_ago=2`: subtracts 60 days = January 31, then `.replace(day=1)` = January 1. For `months_ago=1`: subtracts 30 days = March 2, replace = March 1. For `months_ago=3`: subtracts 90 days = January 1, replace = January 1. Result: cohorts for April, March, January, January — February is skipped entirely and January appears twice.
- **Impact**: Retention cohort table shows duplicate months and missing months. Data is wrong.
- **Fix**: Use `dateutil.relativedelta(months=N)` for proper calendar month arithmetic, or manually compute month boundaries without `timedelta(days=30)`.
- **Status**: OPEN

### C8: Retention cohort uses `max()` instead of set union
- **File**: `app/services/behavioral_analytics_service.py` line 370
- **Description**: `retained = max(login_count, activity_count)` does not compute a set union. If 8 users logged in and 5 different users were active in activity_logs, the true retained count could be up to 13 unique users, but `max()` returns 8.
- **Impact**: Retention percentages undercount retained users when the two signal sources have low overlap.
- **Fix**: Return distinct email sets from both queries, compute `len(login_emails | activity_emails)`.
- **Status**: OPEN

---

## HIGH — Performance

### H1: No caching layer — every dashboard load runs 30+ DB queries
- **File**: `app/services/behavioral_analytics_service.py` (all methods)
- **Description**: Every call to `compile_behavioral_metrics()` executes 6+ concurrent task groups, each running multiple aggregation pipelines against live collections. No snapshot or cache mechanism exists.
- **Impact**: Concurrent admin dashboard loads create significant DB read pressure. Gets worse with data growth.
- **Fix**: Add a scheduled snapshot pattern matching `PlatformMetricsService` — compute on cron, store in a `behavioral_metrics_snapshots` collection, serve from snapshot.
- **Status**: OPEN

### H2: N+1 query pattern in planner engagement signals
- **File**: `app/services/behavioral_analytics_service.py` lines 668-722
- **Description**: `get_planner_engagement_signals()` loops through each wedding and runs 6-7 individual DB queries per wedding (last_activity, guest_count, invited_count, rsvp_count, recent_rsvps, form_count, form_submissions). A planner with 15 weddings triggers 90+ sequential DB round-trips.
- **Impact**: Planner dashboard load time scales linearly with wedding count. Slow for active planners.
- **Fix**: Batch queries using `$in` with all wedding IDs, then map results per-wedding in Python.
- **Status**: OPEN

### H3: Unbounded `to_list(length=None)` on potentially large collections
- **File**: `app/services/behavioral_analytics_service.py` lines 166-172, 314-320, 486-492, 501-507, 515-518
- **Description**: Several queries pull full result sets into memory with `to_list(length=None)` — all planners who signed up in 30 days, all their weddings, all new/churned/active subscriptions. No upper bound on result size.
- **Impact**: Memory usage grows with data. A spike in signups or subscriptions could cause OOM.
- **Fix**: Add `length=` limits or use cursor-based processing. For the activation funnel, cap with a reasonable limit and document the constraint.
- **Status**: OPEN

---

## HIGH — Frontend

### H4: `formatCurrency` called without null coalescing on budget values
- **File**: `app/couple/dashboard/page.tsx` lines 993-994, 1003
- **Description**: `BudgetBreakdownCard` calls `formatCurrency(breakdown.total_spent)` and `formatCurrency(breakdown.total_budgeted)` without null guards. If the API response is missing these fields, renders `$NaN` or crashes.
- **Fix**: Add `?? 0` coalescing: `formatCurrency(breakdown?.total_spent ?? 0)`.
- **Status**: OPEN

### H5: `BudgetBreakdownCard` doesn't guard `breakdown.categories` for null
- **File**: `app/couple/dashboard/page.tsx` line 982+
- **Description**: The early return checks `breakdown.category_count === 0` but doesn't check `breakdown.categories` itself. If the API returns `{category_count: 3, categories: null}`, the `.map()` will throw.
- **Fix**: Change guard to `if (!breakdown?.categories?.length) return null;`.
- **Status**: OPEN

### H6: Admin dashboard nested property access without optional chaining
- **File**: `app/admin/saas/page.tsx` lines 1045, 1096, 1135, 1180
- **Description**: `behavioralMetrics.activation_funnel.steps.map(...)`, `.retention_cohorts.cohorts.map(...)`, `.mrr_movement.current_mrr`, `.engagement_signals.rsvp_velocity` — all accessed without optional chaining. If any sub-object is null due to a partial backend failure, the dashboard crashes.
- **Fix**: Use `behavioralMetrics?.activation_funnel?.steps?.map(...)` etc.
- **Status**: OPEN

### H7: `WeddingReadinessCard` accesses `data.guest_stats` without null guard
- **File**: `app/couple/dashboard/page.tsx` lines 797-801
- **Description**: `const stats = data.guest_stats` then immediately `stats.guest_list_total` — no optional chaining. If `guest_stats` is undefined the component crashes.
- **Fix**: `const stats = data?.guest_stats ?? { guest_list_total: 0, responded: 0, invited: 0 }`.
- **Status**: OPEN

---

## MEDIUM

### M1: MRR net change percent returns 0.0 instead of null when previous MRR is zero
- **File**: `app/services/behavioral_analytics_service.py` lines 562-564
- **Description**: When `(current_mrr - net_mrr_change) <= 0` (all MRR is new this period), returns `0.0` instead of `null`. Dashboard shows "0%" when the real story is "infinite growth from zero" or "N/A".
- **Fix**: Return `null` and handle in frontend with "N/A" or "New" label.
- **Status**: OPEN

### M2: Planner engagement signals fail silently with no user feedback
- **File**: `app/admin/planner/page.tsx` line 218
- **Description**: If `fetchEngagementSignals(token)` fails, the `.catch()` only logs to console. The engagement map stays empty, wedding cards render without badges, and the planner has no way to know the feature failed.
- **Fix**: Add a subtle toast or "Engagement data unavailable" indicator.
- **Status**: OPEN

### M3: Activity logs TTL index (90 days) may clip retention cohort D90 data
- **File**: `app/core/database_indexes.py` TTL on `activity_logs`
- **Description**: TTL auto-deletes activity logs after 90 days. The D90 retention window queries activity_logs at exactly the 90-day threshold. If TTL runs during aggregation, the oldest cohort's D90 retention data is incomplete.
- **Fix**: Extend TTL to 120 days or add a buffer to the retention query window.
- **Status**: OPEN

### M4: TypeScript API service has unused admin-only functions
- **File**: `app/services/behavioralAnalyticsApi.ts`
- **Description**: `fetchNonResponders()` and `fetchBudgetBreakdown()` use Bearer-token admin auth but are not used by any frontend component. The couple dashboard calls `coupleFetch()` directly. Dead code adds confusion.
- **Fix**: Either wire the planner dashboard to use them, or remove them.
- **Status**: OPEN

---

## Summary

| Severity | Count | Blocks startup? |
|----------|-------|-----------------|
| CRITICAL (startup) | 2 | YES — C1, C2 |
| CRITICAL (security) | 2 | No — C3, C4 |
| CRITICAL (data) | 4 | No — C5, C6, C7, C8 |
| HIGH (performance) | 3 | No — H1, H2, H3 |
| HIGH (frontend) | 4 | No — H4, H5, H6, H7 |
| MEDIUM | 4 | No — M1, M2, M3, M4 |
| **Total** | **19** | |

**Priority order**: C1 + C2 (can't start server), then C3 + C4 (security holes), then C5-C8 (data is wrong), then H1-H7, then M1-M4.

---

## Vendor Scraper — Issues Found & Fixed (2026-04-02)

**Scope**: `vendor_scraper/config.py`, `run.py`, `export_json.py`, `manage_services.sh`, `vendor_service.py`, `vendor_import.py`, `VendorImportModal.tsx`, `vendorManagementApi.ts`

All issues below were found during the city→state refactor review and fixed in the same session.

### VS1: FIXED — Config loaded at import time crashed FastAPI server
- **File**: `app/jobs/vendor_scraper/config.py`
- **Was**: `STATES = _load_states()` at module level. If `states.json` was missing or malformed, the FastAPI server crashed at startup — not just the scraper CLI.
- **Fix**: Replaced with `get_states()` lazy loader. Config is only loaded when the scraper actually runs. Cached after first call.

### VS2: FIXED — No config validation on states.json
- **File**: `app/jobs/vendor_scraper/config.py`
- **Was**: `_load_states()` did `e["state"]` with no validation. A typo like `"satte": "OK"` threw an unhelpful `KeyError`.
- **Fix**: Added validation for required keys (`state`, `state_full`, `country`), type checks per entry, empty-file check, malformed-JSON error with line number.

### VS3: FIXED — Shell injection via states.json values
- **File**: `service-manager/manage_services.sh`
- **Was**: State names from `states.json` were interpolated directly into `bash -c` command string. A malicious state name like `"; rm -rf /; echo "` would execute arbitrary shell commands.
- **Fix**: (a) Sanitize state values with `tr -cd 'a-zA-Z0-9 .-'` after reading from JSON. (b) Pass `$states_file` as a `sys.argv` argument to the Python one-liner instead of string interpolation.

### VS4: FIXED — Multiple --state flags ignored (only last one used)
- **File**: `app/jobs/vendor_scraper/run.py`
- **Was**: `parser.add_argument("--state", type=str)` — argparse with `type=str` captures only the last value when multiple `--state` flags are passed (e.g. `--state "OK" --state "TX"`).
- **Fix**: Changed to `action="extend", nargs="+", dest="states"` — supports both `--state OK TX` and repeated `--state OK --state TX`.

### VS5: FIXED — MongoDB connection leak on early return
- **File**: `app/jobs/vendor_scraper/run.py`
- **Was**: If no matching states found, `run_scraper()` called `return` without `await mongo.close()`. Connection opened but never cleaned up.
- **Fix**: Wrapped scraper logic in `try/finally` block — `mongo.close()` always runs.

### VS6: FIXED — Insert/update stat counting always counted inserts
- **File**: `app/jobs/vendor_scraper/run.py`
- **Was**: `if result.get("_id"): stats["inserted"] += 1` — but `upsert_scraped_vendor` returns `_id` for BOTH inserts and updates (and skipped manual entries). Updates and skips were never counted.
- **Fix**: Now checks `result.get("source") == "manual"` for skips, `result.get("created_at") == result.get("updated_at")` for inserts (timestamps match only on insert), else update.

### VS7: FIXED — MongoDB regex injection in vendor dedup
- **File**: `app/services/vendor_service.py`
- **Was**: `{"$regex": f"^{business_name}$", "$options": "i"}` — `business_name` from user-uploaded JSON passed directly into regex. A name containing `.*` would match unintended documents.
- **Fix**: Added `import re` and used `re.escape(business_name)` and `re.escape(city)` before building the regex pattern.

### VS8: FIXED — Unbounded `to_list(length=None)` in export
- **File**: `app/jobs/vendor_scraper/export_json.py`
- **Was**: `cursor.to_list(length=None)` loaded all scraped vendors into memory at once. With state-level scraping producing more results, OOM risk increases.
- **Fix**: Rewrote export to stream results via `async for doc in cursor` with `batch_size=5000`, writing each document to the file incrementally. Also wrapped in `try/finally` for `mongo.close()`.

### VS9: FIXED — No file size limit on import modal
- **File**: `app/components/vendor/VendorImportModal.tsx`
- **Was**: `FileReader.readAsText()` called on any file. No size guard before parsing. A multi-MB file could freeze the browser tab.
- **Fix**: Added 10 MB max file size check (`MAX_FILE_SIZE_BYTES`) before `FileReader` starts. Shows clear error message with actual file size.

### VS10: FIXED — Import modal showed "0 Cities" when vendors lack city data
- **File**: `app/components/vendor/VendorImportModal.tsx`
- **Was**: Preview stat always counted unique `v.city` values. With state-level scraping, some vendors may not have `city` populated, showing "0 Cities" which is confusing.
- **Fix**: Falls back to counting unique `v.state` values and shows "States" label when city count is 0. Per-vendor row shows `v.city || v.state || '—'`.

### VS11: FIXED — Dead import in run.py
- **File**: `app/jobs/vendor_scraper/run.py`
- **Was**: `SYSTEM_CREATED_BY` imported from config but never used in run.py.
- **Fix**: Removed from import statement.

### VS12: FIXED — Scraper refactored from city-based to state-based
- **Files**: `config.py`, `run.py`, `export_json.py`, `manage_services.sh`, `vendor_service.py`, `vendor_import.py`, `vendorManagementApi.ts`, `VendorImportModal.tsx`, `vendor.py` model
- **Was**: Cities hardcoded in `PILOT_CITIES` across config.py, run.py, and manage_services.sh. User in Oklahoma couldn't add their own cities.
- **Fix**: Replaced with state-based `states.json` config. Search queries use full state name. CLI uses `--state`. Service manager reads states dynamically. All `scraped_from_city` references updated to `scraped_from_state` across 6 files.

---

### Vendor Scraper Summary

| Severity | Count | Status |
|----------|-------|--------|
| Security | 2 | FIXED — VS3, VS7 |
| Bug | 5 | FIXED — VS1, VS2, VS4, VS5, VS6 |
| Performance | 1 | FIXED — VS8 |
| Frontend | 2 | FIXED — VS9, VS10 |
| Code quality | 2 | FIXED — VS11, VS12 |
| **Total** | **12** | **ALL FIXED** |
