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

---

## Multi-Tenancy Security Issues

The following issues represent critical vulnerabilities in tenant isolation. In this application, the tenant model is:
- **ROOT_ADMIN**: Platform administrator with access to all weddings
- **wedding_planner**: Can only access weddings where `assigned_planner_email` matches their email
- **vendor**: Can only access weddings they're explicitly assigned to

### 8. **CRITICAL: Unauthenticated Guest Search Exposes All Wedding Data**

**Severity:** CRITICAL
**CVSS Estimate:** 9.1 (Critical)

The `/invite/search` endpoint allows anyone to search for guests across ALL weddings without authentication.

**Affected files:**
- `app/api/guest.py` (lines 24-30)
- `app/services/guest_service.py` (lines 137-154)

**Vulnerability:**
```python
# guest.py - NO authentication required
@router.get("/invite/search", tags=["Guest"])
async def search_guest(phone: str = Query(None), name: str = Query(None)):
    return await guest_service.get_guest_by_phone_or_name(phone=phone, name=name)

# guest_service.py - NO wedding_id filter
async def get_guest_by_phone_or_name(self, phone: Optional[str] = None, name: Optional[str] = None):
    query = {}
    if phone:
        query["phone"] = phone
    # Searches ALL guests across ALL weddings!
    guest = await self.collection.find_one(query)
```

**Impact:**
- Attackers can enumerate all guest phone numbers and names
- Privacy breach exposing guest PII across all weddings
- Can be used for phishing/social engineering attacks

**Fix:**
1. Add authentication to the endpoint OR require wedding_id parameter
2. Add `wedding_id` filter to the query in `get_guest_by_phone_or_name()`

---

### 9. **CRITICAL: Reminder Service Sends SMS to ALL Guests Across ALL Weddings**

**Severity:** CRITICAL
**CVSS Estimate:** 8.8 (High)

The reminder service queries ALL guests and plus-ones without wedding filtering, allowing any authenticated planner to send SMS to guests from other planners' weddings.

**Affected files:**
- `app/api/reminder.py` (lines 13-15)
- `app/services/reminder_service.py` (lines 58, 78)

**Vulnerability:**
```python
# reminder_service.py - NO wedding_id filter!
def send_reminders(self, event_type: str, message: str, target_group: str):
    # Queries ALL guests in the system!
    for guest in self.guest_collection.find({}):
        # ... sends SMS to all matching guests

    # Queries ALL plus-ones in the system!
    for po in self.plus_one_collection.find({}):
        # ... sends SMS to all matching plus-ones
```

**Impact:**
- Any authenticated wedding planner can send SMS to ALL guests across ALL weddings
- Massive potential for abuse (spam, phishing, impersonation)
- Cost implications for SMS sending
- Reputation damage and legal liability

**Fix:**
1. Add `wedding_id` parameter to `send_reminders()` API endpoint
2. Filter queries: `self.guest_collection.find({"wedding_id": wedding_id})`
3. Verify the requesting user has access to the wedding via `check_wedding_access()`

---

### 10. **HIGH: Reminder Logs Expose All SMS History Across All Weddings**

**Severity:** HIGH
**CVSS Estimate:** 7.5 (High)

The `/reminders/logs` endpoint returns ALL SMS logs without tenant filtering.

**Affected files:**
- `app/api/reminder.py` (lines 17-19)
- `app/services/reminder_service.py` (lines 121-123)

**Vulnerability:**
```python
# reminder.py
@router.get("/reminders/logs", tags=["Admin"])
async def get_logs(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return await reminder_service.get_logs()  # No wedding filtering!

# reminder_service.py
async def get_logs(self):
    cursor = self.log_collection.find({}, {"_id": 0})  # Returns ALL logs!
    return await cursor.to_list(length=500)
```

**Impact:**
- Any authenticated planner can view SMS logs for ALL weddings
- Exposes guest phone numbers, message content, and timing data
- Privacy violation and potential GDPR/CCPA compliance issues

**Fix:**
1. Add `wedding_id` parameter to the logs endpoint
2. Filter logs by wedding_id and verify access via `check_wedding_access()`

---

### 11. **HIGH: RSVP Endpoints Expose All Data When wedding_id is Omitted**

**Severity:** HIGH
**CVSS Estimate:** 7.5 (High)

The RSVP list and export endpoints return ALL RSVPs across all weddings when `wedding_id` is not provided.

**Affected files:**
- `app/api/admin_rsvp.py` (lines 22-27, 29-37)

**Vulnerability:**
```python
@router.get("/rsvps", tags=["Admin"])
async def get_rsvps(wedding_id: Optional[str] = Query(None), ...):
    # Only checks access IF wedding_id is provided
    if wedding_id and not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(...)
    # If wedding_id is None, returns ALL RSVPs!
    return await admin_service.get_all_rsvps(wedding_id)
```

**Impact:**
- Planners can view/export ALL RSVPs from all weddings by omitting `wedding_id`
- Exposes guest dietary preferences, attendance status, and personal info
- Privacy breach affecting all wedding guests

**Fix:**
1. Make `wedding_id` a required parameter OR
2. If `wedding_id` is None, filter to only weddings the planner has access to
3. For ROOT_ADMIN, explicitly handle the "all weddings" case

---

### 12. **MEDIUM: Budget Operations Rely on Service-Layer Access Control**

**Severity:** MEDIUM
**CVSS Estimate:** 5.3 (Medium)

Several budget endpoints delegate access control to the service layer instead of validating at the API layer, creating a fragile security pattern.

**Affected files:**
- `app/api/budget.py` (lines 160-179, 181-198, 263-282)

**Vulnerability:**
```python
@router.put("/budget/category/{category_id}", tags=["Budget"])
async def update_budget_category(category_id: str, update_data: UpdateBudgetCategoryRequest, ...):
    # Note: Wedding access is checked within the service by looking up the category
    # ← This comment admits the API layer doesn't verify access!
    updated_category = await budget_service.update_budget_category(category_id, ...)
```

**Impact:**
- If service layer check is missing or bypassed, cross-tenant access is possible
- Harder to audit security when access control is scattered
- Inconsistent pattern compared to other endpoints

**Fix:**
1. Fetch the category at the API layer
2. Verify `check_wedding_access(current_user, category.wedding_id)` before calling service
3. Apply this pattern consistently to `delete_budget_category` and `update_quote_status`

---

### 13. **MEDIUM: Frontend Admin Context Stores Token Without Wedding Scoping**

**Severity:** MEDIUM
**CVSS Estimate:** 4.3 (Medium)

The frontend `AdminContext.tsx` stores authentication tokens without associating them with specific wedding access, relying entirely on backend enforcement.

**Affected files:**
- `app/contexts/AdminContext.tsx`

**Issue:**
The frontend fetches user profile and stores `is_wedding_planner` flag but doesn't cache which weddings the user can access. All authorization is delegated to API calls, which is correct for security but creates UX issues where users may attempt to access weddings they don't own.

**Impact:**
- No client-side prevention of accessing unauthorized weddings
- Users may see 403 errors only after attempting actions
- Potential for confusion in multi-tenant scenarios

**Fix:**
1. Fetch and cache accessible wedding IDs on login
2. Implement client-side route guards to prevent navigation to inaccessible weddings
3. Filter wedding lists client-side to match backend permissions

---

## Summary: Multi-Tenancy Security Remediation Priority

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| #8 - Unauthenticated guest search | CRITICAL | Low | P0 - Immediate |
| #9 - SMS to all weddings (BOTH services) | CRITICAL | Medium | P0 - Immediate |
| #10 - SMS logs leak | HIGH | Low | P1 - This Sprint |
| #11 - RSVP data leak | HIGH | Low | P1 - This Sprint |
| #12 - Budget access pattern | MEDIUM | Medium | P2 - Next Sprint |
| #13 - Frontend scoping | MEDIUM | Medium | P2 - Next Sprint |
| #14 - Gallery duplicate routes | HIGH | Medium | P1 - This Sprint |
| #15 - Gallery admin no wedding scope | HIGH | Medium | P1 - This Sprint |
| #16 - Slug collision cross-tenant | CRITICAL | Medium | P0 - Immediate |
| #17 - Check-in cross-tenant | MEDIUM | Low | P2 - Next Sprint |

---

### 14. **HIGH: Duplicate Gallery Routes Bypass Privacy Controls**

**Severity:** HIGH
**CVSS Estimate:** 7.5 (High)

Two separate gallery API files exist with conflicting security models. The `gallery_upload.py` file exposes a public `/gallery` route that bypasses the privacy checks in `gallery_public.py`.

**Affected files:**
- `app/api/gallery_upload.py` (lines 30-34)
- `app/api/gallery_public.py` (lines 8-28)

**Vulnerability:**

```python
# gallery_upload.py - NO privacy check!
@router.get("/gallery", tags=["Guest"])
def public_gallery(wedding_slug: str = Query(...)):
    prefix = f"gallery/{wedding_slug}/"
    return gallery_service.list_uploaded_files(prefix=prefix)  # Returns all images!

# gallery_public.py - HAS privacy check
@router.get("/gallery", tags=["Guest"])
async def public_gallery(wedding_slug: str = Query(...)):
    # Checks privacy_mode before returning images
    if privacy_info.get("privacy_mode") == "public":
        return gallery_service.list_uploaded_files(prefix=prefix)
    raise HTTPException(status_code=403, ...)
```

**Impact:**
- If `gallery_upload.py` route is registered after `gallery_public.py`, it overrides the secure version
- Anyone can view ANY wedding's gallery by guessing the slug
- Privacy settings (password-protected, invite-only) are completely bypassed

**Fix:**
1. Remove duplicate `/gallery` route from `gallery_upload.py`
2. Consolidate all gallery routes into a single file with consistent security
3. Audit FastAPI route registration order

---

### 15. **HIGH: Gallery Admin Endpoints Allow Cross-Tenant Access**

**Severity:** HIGH
**CVSS Estimate:** 7.5 (High)

The `gallery_upload.py` admin endpoints only check for ROOT_ADMIN role but don't validate wedding ownership. Wedding planners using `gallery_admin.py` have proper checks, but the duplicate routes in `gallery_upload.py` don't.

**Affected files:**
- `app/api/gallery_upload.py` (lines 8-28)

**Vulnerability:**

```python
# get_upload_url - NO wedding_slug, uploads to generic location
@router.get("/gallery/upload-url", tags=["Admin"], dependencies=[Depends(require_root_admin)])
def get_upload_url(filename: str = Query(...)):
    # Generates presigned URL without wedding scope!
    key = f"gallery/{timestamp}_{filename}"  # Missing wedding_slug!
    return gallery_service.create_presigned_url(filename)

# delete_file - Can delete ANY wedding's files
@router.delete("/gallery/delete", tags=["Admin"], dependencies=[Depends(require_root_admin)])
def delete_file(key: str = Query(...)):
    return gallery_service.delete_file(key)  # No wedding ownership check!

# list_gallery_files - Lists ALL files across ALL weddings
@router.get("/gallery/list", tags=["Admin"], dependencies=[Depends(require_root_admin)])
def list_gallery_files():
    return gallery_service.list_uploaded_files()  # No wedding filter!
```

**Impact:**
- `get_upload_url()` generates URLs without wedding context, files end up in wrong location
- `delete_file()` allows deleting ANY file across ALL weddings by any ROOT_ADMIN
- `list_gallery_files()` exposes ALL wedding images
- Path traversal risk: crafted `key` could access files outside gallery folder

**Fix:**
1. Remove or deprecate duplicate routes from `gallery_upload.py`
2. Use `gallery_admin.py` as the single source of truth for admin gallery operations
3. All endpoints should require `wedding_slug` and verify access via `check_wedding_access()`
4. Add path validation to prevent directory traversal in `key` parameter

---

### 16. **CRITICAL: Wedding Slug Collision Allows Cross-Tenant Data Exposure**

**Severity:** CRITICAL
**CVSS Estimate:** 9.1 (Critical)

Wedding slugs are not globally unique and `get_wedding_by_slug()` does not filter by planner. If two planners create weddings with the same slug (e.g., "john-jane"), guests visiting that URL will see whichever wedding MongoDB returns first - potentially exposing the WRONG couple's private wedding data, photos, and guest list.

**Affected files:**
- `app/services/wedding_service.py` (lines 53-63)
- `app/api/wedding.py` (lines 30-53) - no slug uniqueness check
- `app/core/database_indexes.py` - no unique index on slug

**Vulnerability:**

```python
# wedding_service.py - NO planner filter, returns FIRST match
async def get_wedding_by_slug(self, slug: str):
    wedding = await self.collection.find_one({"slug": slug})  # Returns ANY matching wedding!
    return wedding

# wedding.py create_wedding - NO slug uniqueness validation
@router.post("/weddings", tags=["Admin"])
async def create_wedding(wedding: WeddingModel, ...):
    # No check if slug already exists!
    result = await wedding_service.create_wedding(wedding_data)
```

**Attack Scenario:**
1. Planner A creates wedding with slug "john-jane" for their client
2. Planner B (malicious or coincidental) creates wedding with same slug "john-jane"
3. Guests visiting `thespecialwedding.com/john-jane` see whichever wedding was created first
4. If Planner B's wedding is returned, Planner A's guests see wrong wedding data
5. Planner B could intentionally harvest guest data by monitoring RSVPs to their decoy wedding

**Impact:**
- **Privacy breach**: Guests see wrong couple's wedding details, photos, guest list
- **Data harvesting**: Malicious planners could create decoy weddings to collect guest PII
- **Brand damage**: Couples see wrong wedding when sharing their link
- **RSVP confusion**: Guests may RSVP to wrong wedding
- **Gallery exposure**: Private photos shown to wrong guests

**Fix (Choose one or combine):**

**Option 1: Global unique slugs (simplest)**
```python
# Add unique index to MongoDB
await weddings_collection.create_index("slug", unique=True)

# Add validation in create_wedding
existing = await self.collection.find_one({"slug": wedding_data["slug"]})
if existing:
    raise HTTPException(status_code=400, detail="Slug already exists")
```

**Option 2: Planner-scoped slugs (better multi-tenancy)**
```python
# Compound unique index
await weddings_collection.create_index(
    [("slug", 1), ("assigned_planner_email", 1)],
    unique=True
)

# Update get_wedding_by_slug to require planner context OR use wedding_id
async def get_wedding_by_slug(self, slug: str, planner_email: str = None):
    query = {"slug": slug}
    if planner_email:
        query["assigned_planner_email"] = planner_email
    return await self.collection.find_one(query)
```

**Option 3: Use wedding_id in URLs instead of slug**
- Change public URLs from `/wedding/{slug}` to `/wedding/{id}`
- Slugs become display-only, not used for lookups
- IDs are guaranteed unique (MongoDB ObjectId)

---

### 17. **MEDIUM: Check-in Endpoints Allow Cross-Tenant Guest Check-in**

**Severity:** MEDIUM
**CVSS Estimate:** 5.3 (Medium)

The check-in endpoints allow any authenticated planner to check in guests from ANY wedding using just the guest token, without verifying they have access to that wedding.

**Affected files:**
- `app/api/checkin.py` (lines 9-15)
- `app/services/checkin_service.py` (lines 14-31, 33-45)

**Vulnerability:**

```python
# checkin.py - NO wedding access verification!
@router.post("/checkin/{token}", tags=["Admin"])
def check_in_guest(token: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return checkin_service.check_in_guest(token, current_user.email)  # Just passes token!

# checkin_service.py - Looks up guest by token only
async def check_in_guest(self, token: str, admin_email: str):
    guest = await self.guest_collection.find_one({"token": token})  # No wedding verification!
    # ... proceeds to check in without verifying caller has access to guest's wedding
```

**Impact:**
- Any authenticated planner can check in guests from other planners' weddings
- Planners could sabotage competitor weddings by checking in guests early
- Check-in data integrity compromised across tenants
- Guest tokens (which are in RSVP links) could be harvested and abused

**Fix:**

```python
# checkin.py - Add wedding access check
@router.post("/checkin/{token}", tags=["Admin"])
async def check_in_guest(token: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    # Get guest first to find wedding_id
    guest = await guest_service.get_guest_by_token(token)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    # Verify wedding access
    if not await check_wedding_access(current_user, guest.get("wedding_id")):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    return await checkin_service.check_in_guest(token, current_user.email)
```
