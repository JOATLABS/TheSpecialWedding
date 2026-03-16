# Advertising Feature — Code Review Report

**Date:** March 16, 2026
**Scope:** Full advertising feature codebase (Stages 1–3)
**Reviewed against:** `docs/mockups/vendors/Vendor_Ad_Mockups.html` (8-tab source of truth)

---

## Dimension Ratings

| Dimension       | Rating   | Summary |
|-----------------|----------|---------|
| Security        | B+       | Auth checks solid; minor gaps in vendor-role access |
| Performance     | B        | Rollup pipeline well-designed; N+1 stats fetch; unbounded cursor in leaderboard |
| Correctness     | C+       | Critical `$or` query bug; field name mismatches; missing enum value |
| Maintainability | A-       | Clean separation of concerns; good docstrings; changelog discipline |

---

## Critical Issues

### 1. `$or` Query Construction Bug — `advertising_service.py` lines 206–215, 840–850

**Severity: HIGH (Correctness)**

Both `get_sponsored_vendors()` and `get_sponsored_vendors_filtered()` build a date range filter using `$or` but append conditions to the `$or` list in a way that produces an invalid or overly permissive MongoDB query. The intent is "vendors where end_date is null OR end_date >= now", but the query structure appends to an `$or` that already contains placement conditions, creating an unintended logical grouping.

**Impact:** Expired sponsored vendors may continue to appear in ad serving, or valid vendors may be excluded depending on how MongoDB evaluates the malformed query.

**Fix:** Use `$and` to combine the date-range `$or` with other query conditions:

```python
date_filter = {
    "$or": [
        {"end_date": None},
        {"end_date": {"$gte": now}},
    ]
}
query = {
    "$and": [
        {"is_active": True, "placement": placement},
        date_filter,
    ]
}
```

### 2. Frontend/Backend Field Name Mismatch — `advertisingApi.ts` vs `advertising_service.py`

**Severity: HIGH (Correctness)**

The TypeScript `AdPreferences` interface uses `hidden_vendors: string[]` but the backend model and service return `hidden_vendor_ids: string[]`. This means the planner-side hide/unhide flow is likely broken in the frontend — preferences load but the hidden vendor list is always empty on the client.

**Fix:** Align the field name in `advertisingApi.ts` to `hidden_vendor_ids`, or add a response serialization alias in the backend model.

### 3. Missing `dashboard_rail` Placement in Backend Enum — `advertising.py` line ~52

**Severity: MEDIUM (Correctness)**

The frontend `advertisingApi.ts` defines `AdPlacement` with 5 values including `'dashboard_rail'`, but the backend `AdPlacement` enum only has 4 values: `vendor_rail`, `vendor_detail`, `milestone_module`, `directory_boost`. Any event recorded with `placement: 'dashboard_rail'` will fail Pydantic validation.

**Fix:** Add `dashboard_rail = "dashboard_rail"` to the backend `AdPlacement` enum.

---

## Security Findings

### 4. Lead Endpoints Missing Vendor-Role Authorization

**Severity: MEDIUM**

`GET /admin/ads/leads` and `GET /admin/ads/leads/{id}` require only `current_user` (any authenticated user). Vendors should be scoped to see only their own leads. Currently any authenticated user can read all leads by omitting filters.

**Recommendation:** Add vendor-role scoping — if the caller is a vendor, auto-filter by their `vendor_profile_id`. If root admin, allow full access.

### 5. Rollup/Backfill Endpoints Lack Admin Guard

**Severity: LOW**

`POST /dashboard/rollup` and `POST /dashboard/backfill` appear to be admin-only operations but the authorization check should be verified. The backfill endpoint with `days_back=90` triggers 90 sequential aggregation pipelines — an unauthenticated or low-privilege caller could cause significant load.

### Positive: Event Endpoint Auth

The `POST /events` endpoint correctly auto-fills `planner_id` from the authenticated user's profile, preventing spoofed attribution. The `recordAdEvent()` client function silently swallows errors — correct for analytics that shouldn't break the user flow.

---

## Performance Findings

### 6. N+1 Stats Fetch in Admin Page — `page.tsx` `fetchVendorData()`

**Severity: MEDIUM**

The admin page sequentially fetches stats for each sponsored vendor in a loop. With 50+ vendors, this creates 50+ API calls.

**Recommendation:** Add a batch stats endpoint or include stats in the sponsored vendors list response. This is noted in the changelog as deferred to Phase 4 but worth flagging.

### 7. Unbounded Cursor in `get_dashboard_stats()` — `ad_rollup_service.py` line 480

**Severity: LOW**

`get_dashboard_stats()` returns all matching documents with no limit. With many vendors across 30+ days, this could return thousands of documents.

**Fix:** Add a `limit` parameter (default 1000) or paginate.

### 8. `$addToSet` in Rollup Aggregation — `ad_rollup_service.py` line 198–199

**Severity: LOW**

Using `$addToSet` for `unique_planners_set` and `unique_weddings_set` in the aggregation can consume significant memory for high-traffic vendors on busy days. The sets are only used for their `len()`.

**Alternative for scale:** Use `$addToSet` with a `$size` in a subsequent `$project` stage, or switch to HyperLogLog approximation when event volumes grow.

### Positive: Rollup Architecture

The rollup pipeline design is sound — nightly `$match → $group → upsert` is idempotent, properly handles backfill, and the 2:00 AM UTC scheduling with error recovery (1-hour retry) is production-appropriate. The TTL index on `ad_events` (90 days) prevents unbounded collection growth.

---

## Correctness Findings

### 9. CTR Calculation Includes Both Served AND Viewable Impressions — `ad_rollup_service.py` lines 229–237

**Severity: MEDIUM**

The rollup computes `total_impressions = impression_served + impression_viewable`. Since `impression_viewable` is a subset of `impression_served` (a served impression that was also viewable), this double-counts impressions and deflates CTR.

**Fix:** Use only `impression_served` as the denominator for CTR, or only `impression_viewable` if you want viewable-CTR:

```python
total_impressions = doc.get("impression_served", 0)  # Standard CTR
# OR: doc.get("impression_viewable", 0)              # Viewable CTR
```

### 10. `vendor_profile_id` Not in Leads Aggregation Group Key — `ad_rollup_service.py` line 291

**Severity: LOW**

The events aggregation groups by `sponsored_vendor_id`, `vendor_profile_id`, and `placement`, but the leads aggregation only groups by `sponsored_vendor_id` and `placement`. The merge key uses `(sponsored_vendor_id, placement)`. This works if there's a 1:1 mapping between `sponsored_vendor_id` and `vendor_profile_id`, but if a vendor has multiple sponsored entries, leads could be attributed to the wrong profile.

### 11. Nightly Scheduler Sleep Precision — `main.py` lines 115–164

**Severity: LOW**

The scheduler calculates seconds until 2:00 AM and sleeps. However, if `seconds_until_2am` is 0 or negative (server started at exactly 2:00 AM UTC), it sleeps for ~24 hours. There's no edge-case handling for this.

### Positive: Idempotent Upserts

The `$set` upsert in Stage 3 correctly makes the rollup re-runnable. The `created_at` / `updated_at` timestamps properly distinguish first-insert from updates.

---

## Design Mockup Cross-Reference

Comparing the implementation against the 8-tab `Vendor_Ad_Mockups.html`:

| Mockup View | Implementation Status | Gap |
|-------------|----------------------|-----|
| **View 1: Planner Dashboard** (right rail) | `SponsoredVendorsRail.tsx` — horizontal scroll | **Layout mismatch**: Mockup shows 320px vertical right rail with stacked cards; implementation is horizontal scroll rail. Major UX difference. |
| **View 2: Vendor Drawer** | `SponsoredVendorDetailsDrawer.tsx` exists | Partially built. Needs verification against mockup's disclosure box, vendor stats, package pricing, 5 action buttons. |
| **View 3: Directory Boosts** | Backend enum has `directory_boost` | **Frontend not built.** No boosted cards in search results. No gold "⚡ Boosted" badge component. |
| **View 4: Milestone Module** | Backend enum has `milestone_module` | **Frontend not built.** No milestone-scoped sponsored vendor cards. Auto-dismiss on "booked" not implemented. |
| **View 5: Vendor Ad Manager** | Not started | **Not implemented.** Vendor portal with perf grid, weekly bars, conversion funnel, campaign table — all missing. |
| **View 6: Campaign Wizard** | Not started | **Not implemented.** 6-step wizard (Goal → Targeting → Budget → Pricing → Creative → Review). |
| **View 7: Admin Console** | `admin/advertising/page.tsx` (partial) | Analytics tab has basic stats. Missing: Creative Review queue, Revenue Dashboard, System Config, Planner Feedback tabs. |
| **View 8: System Flows** | Rollup pipeline + event tracking built | Architecture matches flow diagrams. Attribution via `click_id` is implemented. Fraud detection not yet built. |

**Key takeaway:** The backend data layer (models, events, rollup, indexes) is solid and well-aligned with the mockup's data requirements. The frontend is significantly behind — only View 1 (with layout mismatch) and partial View 2/7 are built. Views 3–6 are entirely missing.

---

## Maintainability Observations

**Strengths:**
- Clean service/API/model separation — each concern in its own file
- Comprehensive changelog with every change tracked
- Legacy event type mapping ensures backward compatibility
- 18 well-chosen indexes covering all query patterns
- TypeScript API client mirrors backend 1:1 (except the field name bug above)

**Areas for improvement:**
- `advertising_service.py` at 890 lines is getting large — consider splitting lead management into its own service
- The CSS-based charts in `page.tsx` should eventually use a proper charting library (as noted in the mockup which uses more sophisticated visualizations)
- Consider adding request/response type validation tests that catch frontend/backend model drift automatically

---

## Recommended Priority Order

1. **Fix `$or` query bug** — Sponsored vendors may be incorrectly served/hidden (Critical)
2. **Fix `hidden_vendors` / `hidden_vendor_ids` field name mismatch** — Planner preferences broken (Critical)
3. **Fix CTR double-counting** — Analytics accuracy is core to the "essential" data tracking goal (High)
4. **Add `dashboard_rail` to backend enum** — Prevents runtime validation errors (High)
5. **Add vendor-role scoping to lead endpoints** — Security gap before vendor portal launch (Medium)
6. **Convert SponsoredVendorsRail to vertical layout** — Match View 1 mockup design (Medium)
7. **Build Directory Boost + Milestone Module frontends** — Views 3–4 (Next phase)
8. **Build Vendor Ad Manager + Campaign Wizard** — Views 5–6 (Future phase)
