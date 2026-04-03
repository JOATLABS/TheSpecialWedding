# Team Management — QA Review: Known Issues

**Review Date:** 2026-03-05
**Last Updated:** 2026-03-05
**Status:** All 32 issues resolved. Ready for integration testing.

---

## CRITICAL (6 issues — All Fixed)

### C1: `custom_permissions` vs `permissions` field mismatch
- **Area:** Cross-cutting (Backend → Frontend)
- **Files:** `app/services/team_management_service.py`, `app/models/team_member.py`, `EditTeamMemberModal.tsx`
- **Problem:** Backend returned `custom_permissions` in API response. Frontend expected `permissions`.
- **Fix:** Updated `_format_team_member()` to return `permissions` key; renamed field in `TeamMemberResponse`.
- **Status:** [x] Fixed

### C2: Accept page field name mismatch
- **Area:** Cross-cutting (Backend → Frontend)
- **Files:** `app/admin/team/accept/page.tsx`
- **Problem:** Frontend expected `owner_company_name` / `owner_email` but backend returns `company_name` / `planner_name`.
- **Fix:** Updated frontend `InviteInfo` interface and JSX to match backend response fields.
- **Status:** [x] Fixed

### C3: Missing feature gate on team router
- **Area:** Security / Billing
- **Files:** `app/api/team_management.py`
- **Problem:** No `require_team_management` dependency on team endpoints. Plans without staff_seats could bypass billing.
- **Fix:** Added `Depends(require_team_management)` to all 9 protected endpoints individually (public endpoints excluded).
- **Status:** [x] Fixed

### C4: Race condition on seat limit check
- **Area:** Data Integrity
- **Files:** `app/services/team_management_service.py`
- **Problem:** Seat check and insert were not atomic. Concurrent invites could exceed limits.
- **Fix:** Implemented optimistic approach — insert first, then count. If over limit, delete the new doc and raise 409.
- **Status:** [x] Fixed

### C5: Missing wedding ownership validation on update
- **Area:** Security
- **Files:** `app/services/team_management_service.py`, `app/api/team_management.py`
- **Problem:** `update_team_member()` didn't validate wedding IDs belong to the planner.
- **Fix:** Extracted shared `_validate_wedding_ownership()` helper; applied to both invite and update flows. Updated API route to pass `owner_email`.
- **Status:** [x] Fixed

### C6: Missing permission checks on budget mutation endpoints
- **Area:** Security
- **Files:** `app/api/budget.py`, `app/api/tables.py`, `app/api/vendor_management.py`, `app/api/planner_calendar.py`, `app/api/guest.py`
- **Problem:** Most budget, seating, vendor, and calendar mutation endpoints lacked `enforce_team_permission()` calls.
- **Fix:** Added 39 permission checks across 6 files covering budget, seating, vendor, and calendar operations.
- **Status:** [x] Fixed (includes M9)

---

## HIGH (11 issues — All Fixed)

### H1: Response model uses `str` instead of enums
- **Fix:** Changed `status`, `role`, `wedding_access` to use `TeamMemberStatus`, `TeamMemberRole`, `WeddingAccessType` enums.
- **Status:** [x] Fixed

### H2: Missing fields in `TeamMemberResponse`
- **Fix:** Added `user_id`, `owner_email`, `invite_token_expires_at` fields. Updated `_format_team_member()` to include them. Added `model_config` with `ConfigDict`.
- **Status:** [x] Fixed

### H3: Auth hydration extra DB query on every request
- **Fix:** Added 60-second TTL in-memory cache (`_team_cache`) with `_get_cached_team_data()` / `_set_team_cache()` helpers. Auto-prunes at 1000 entries.
- **Status:** [x] Fixed

### H4: Sequential wedding validation loop (N+1 queries)
- **Fix:** Replaced individual `find_one()` loop with single `$in` query using `count_documents()`. Falls back to ID-level error reporting only on failure.
- **Status:** [x] Fixed

### H5: Activity logging blocks response synchronously
- **Fix:** Changed all 5 activity logging calls from `await` to `asyncio.create_task()` for fire-and-forget execution.
- **Status:** [x] Fixed

### H6: Missing pagination on list endpoint
- **Fix:** Added `skip` (default 0) and `limit` (default 50, max 100) query params. Returns `{members, total, skip, limit}`.
- **Status:** [x] Fixed

### H7: ObjectId path parameters not validated
- **Fix:** Added `validate_object_id()` helper. Applied to all 6 endpoints with `team_member_id` path params. Returns 400 for invalid IDs.
- **Status:** [x] Fixed

### H8: No rate limiting on public endpoints
- **Fix:** Implemented `SimpleRateLimiter` class. Applied to `get_invite_info` (10/min) and `accept_invite` (5/min) with per-IP tracking.
- **Status:** [x] Fixed

### H9: Weak password policy
- **Fix:** Added `_validate_password()` requiring 8+ chars, uppercase, lowercase, digit, and special character. Applied in `accept_invite()`.
- **Status:** [x] Fixed

### H10: Missing ARIA attributes and focus management in modals
- **Fix:** Added `role="dialog"`, `aria-modal="true"`, `aria-labelledby="modal-title"`, `aria-label` on close buttons, and focus trap with Escape key support to both modals.
- **Status:** [x] Fixed

### H11: `last_active_at` never updated
- **Fix:** Added throttled (5-minute) `last_active_at` update via `asyncio.create_task()` in `get_current_user_extended()`.
- **Status:** [x] Fixed

---

## MEDIUM (9 issues — All Fixed)

### M1: No permission key validation on update
- **Fix:** Added `@field_validator("custom_permissions")` to both `InviteTeamMemberRequest` and `UpdateTeamMemberRequest` validating against `ALL_PERMISSION_KEYS`.
- **Status:** [x] Fixed

### M2: Deactivated members can be updated
- **Fix:** Added status check in `update_team_member()` — raises 400 if member is deactivated.
- **Status:** [x] Fixed

### M3: Inconsistent error response format
- **Fix:** Standardized all `HTTPException` details to plain strings. Only seat limit error retains dict format (needed for `upgrade_required` flag).
- **Status:** [x] Fixed

### M4: Missing compound index for auth query
- **Fix:** Added `(user_id, status)` compound index with `sparse=True` in `create_team_member_indexes()`.
- **Status:** [x] Fixed

### M5: Frontend missing `useMemo` for filtered members
- **Fix:** Wrapped `filteredMembers` in `useMemo` with `[members, searchQuery, statusFilter]` dependencies.
- **Status:** [x] Fixed

### M6: No frontend request deduplication
- **Fix:** Changed `actionLoading` to `Record<string, boolean>` per-member tracking. Buttons disabled during loading. Early return if already loading.
- **Status:** [x] Fixed

### M7: Missing confirmation dialog on destructive actions
- **Fix:** Added `window.confirm()` dialogs to `handleDeactivate()` and `handleRemove()`.
- **Status:** [x] Fixed

### M8: Deactivated user `is_active` not verified in auth
- **Fix:** Verified `is_active` check already exists. Updated status code to 403 with clearer error message.
- **Status:** [x] Fixed

### M9: Missing seating/vendor permission checks
- **Fix:** Merged into C6 — 39 total permission checks added across budget, seating, vendor, and calendar endpoints.
- **Status:** [x] Fixed

---

## LOW (6 issues — Remaining / Backlog)

### L1: Duplicated permission constants across modals
- Both modals defined the same permission list inline.
- **Fix:** Created `teamConstants.ts` with shared `ROLES`, `ALL_PERMISSIONS`, `ROLE_DEFAULTS`. Updated both modals to import from it.
- **Status:** [x] Fixed

### L2: Missing `data-testid` attributes for testing
- No test IDs on key interactive elements.
- **Fix:** Added `data-testid` to all key elements: invite button, search, tabs, stat cards, member rows, action buttons, modal fields, accept page form.
- **Status:** [x] Fixed

### L3: No optimistic UI updates on actions
- Actions waited for API response before updating UI.
- **Fix:** Added optimistic state updates to deactivate/reactivate/remove handlers with rollback on failure.
- **Status:** [x] Fixed

### L4: Hardcoded z-index values in modals
- Modal z-index values were inconsistent.
- **Fix:** Standardized both modals to `z-[9999]` overlay / `z-[10000]` content.
- **Status:** [x] Fixed

### L5: Missing audit trail for permission changes
- `update_team_member()` didn't log changes to activity log.
- **Fix:** Added fire-and-forget `asyncio.create_task()` call to `log_team_member_updated()` after successful updates.
- **Status:** [x] Fixed

### L6: Verbose logging in service
- Service used basic string-formatted logging.
- **Fix:** Updated all log calls to use structured `[TeamMgmt:operation]` prefix format with `%s` parameterization.
- **Status:** [x] Fixed

---

## Verification

- **Python compilation:** All 21 modified files pass `py_compile` — zero errors
- **TypeScript compilation:** All 8 frontend files (incl. new `teamConstants.ts`) pass `tsc --noEmit` — zero errors

---

## Fix Progress Tracker

| Priority | Total | Fixed | Remaining |
|----------|-------|-------|-----------|
| CRITICAL | 6     | 6     | 0         |
| HIGH     | 11    | 11    | 0         |
| MEDIUM   | 9     | 9     | 0         |
| LOW      | 6     | 6     | 0         |
| **TOTAL**| **32**| **32**| **0**     |
