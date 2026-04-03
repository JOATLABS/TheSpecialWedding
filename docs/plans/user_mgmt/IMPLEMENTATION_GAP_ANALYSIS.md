# Team Management Feature — Implementation Gap Analysis

**Review Date:** 2026-03-14
**Reviewer:** Code Review Agent
**Scope:** Full codebase audit against `TEAM_MANAGEMENT_PLAN.md` (7 phases)
**Files Examined:** ~30+ backend + frontend files

---

## Executive Summary

Phases 1, 2, and 4 are **fully implemented** with all planned functionality present and all 30 of the 36 code review fixes applied. Phase 5 (Frontend) is ~90% complete with two notable gaps. **Phase 3 is the critical gap** — only 9 of 19 API files have received team permission protection, leaving 10 files unprotected. Phase 6 is structurally complete but missing some detail-level enrichment.

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Data Models & DB | **Complete** | 100% |
| Phase 2: Backend Service & API | **Complete** | 100% |
| Phase 3: Protect Existing Endpoints | **Incomplete** | ~47% |
| Phase 4: Invite Email & Accept Flow | **Complete** | 100% |
| Phase 5: Frontend — Team Management | **Mostly Complete** | ~90% |
| Phase 6: Activity Logging & Notifications | **Mostly Complete** | ~75% |
| Phase 7: Testing & Verification | Not assessed | — |

---

## Phase 1: Data Models & Database Layer — COMPLETE

All planned components are present and correctly implemented:

- **`app/models/team_member.py`** — All enums (`TeamMemberRole`, `TeamMemberStatus`, `WeddingAccessType`), `ROLE_PRESETS` with 12 permissions across 3 roles, full Pydantic model suite (`TeamPermissions`, `InviteTeamMemberRequest`, `UpdateTeamMemberRequest`, `AcceptInviteRequest`, `TeamMemberResponse`, `TeamSeatsResponse`, `TeamPermissionsResponse`, `InviteInfoResponse`).
- **`app/models/user_extended.py`** — `parent_planner_id` and `team_member_id` fields added.
- **`app/core/database_indexes.py`** — All 5 team_members indexes created: `(owner_id, email)` unique, `invite_token` unique/sparse, `user_id` sparse, `(owner_id, status, created_at)`, `(user_id, status)` sparse. Plus `parent_planner_id` index on users collection.

**No gaps found.**

---

## Phase 2: Backend Service & API — COMPLETE

All planned components are present with all code review fixes applied:

- **`app/services/team_management_service.py`** — All 11 methods implemented. Key fixes confirmed: atomic accept via `find_one_and_update`, optimistic seat enforcement, `_validate_wedding_ownership` with `$in` query, bounded background tasks (max 100), `_ensure_utc` helper, cache invalidation hooks.
- **`app/api/team_management.py`** — All 12 endpoints present at `/admin/team` prefix. Rate limiting on public endpoints, feature gate dependency, ObjectId validation, proxy-aware IP extraction.
- **`app/dependencies/feature_gates.py`** — `require_team_management` dependency implemented.
- **`app/dependencies/auth_extended.py`** — `ExtendedAuthUser` extended with all team fields. `require_team_or_planner`, `require_team_permission`, `enforce_team_permission` all present. TTL cache (60s, max 500) with `asyncio.Lock`, cache invalidation on permission changes, throttled `last_active_at`.
- **`app/main.py`** — Team management router registered.

**No gaps found.**

---

## Phase 3: Protect Existing Endpoints — CRITICAL GAP

**This is the largest implementation gap.** The plan requires all planner endpoints to support team members by swapping `require_wedding_planner` to `require_team_or_planner` and adding `enforce_team_permission()` on mutation endpoints.

### Implemented (9 of 19 files):

| File | Permission Checks | Notes |
|------|-------------------|-------|
| `guest.py` | 5x enforce_team_permission (manage_guests) | Uses `require_wedding_planner_only` instead of `require_team_or_planner` |
| `admin_rsvp.py` | 3x enforce_team_permission (manage_guests) | Same decorator issue |
| `guest_export.py` | 1x enforce_team_permission | Limited coverage |
| `budget.py` | 8x enforce_team_permission (manage_budget) | Good coverage |
| `tables.py` | 6x enforce_team_permission (manage_seating) | Uses `require_admin_or_planner` |
| `vendor_management.py` | 19x enforce_team_permission (manage_vendors) | Extensive but wrong decorator |
| `reminder_telnyx.py` | 3x enforce_team_permission | send_reminders, send_rsvp |
| `email_reminders.py` | 4x enforce_team_permission | send_rsvp, send_reminders |
| `planner_calendar.py` | 7x enforce_team_permission | Uses manage_calendar (not in plan) |

### NOT Implemented (10 of 19 files):

| File | Required Permission | Impact |
|------|-------------------|--------|
| **gallery_admin.py** | manage_gallery | Team members cannot manage gallery |
| **gallery_upload.py** | manage_gallery | Team members cannot upload to gallery |
| **vendor_dashboard.py** | manage_vendors | Team members cannot view vendor dashboard |
| **reminder.py** | send_reminders | Team members cannot manage reminders |
| **reminder_twilio.py** | send_reminders | Team members cannot send Twilio reminders |
| **forms.py** | manage_forms | Team members cannot manage forms |
| **planner_metrics.py** | view_analytics | Team members cannot view analytics |
| **wedding.py** | manage_wedding_settings | Team members cannot manage wedding settings |
| **contracts.py** | manage_contracts | Team members cannot manage contracts |
| **packages.py** | manage_packages | Team members cannot manage packages |

### Additional Issues:

1. **Inconsistent decorator usage:** The implemented files use `require_wedding_planner_only` or `require_admin_or_planner` instead of the planned `require_team_or_planner`. This may still work but doesn't match the plan.
2. **`get_accessible_wedding_ids()` not used:** The wedding scoping utility exists in `auth_extended.py` but is NOT called by any of the 19 API files. This means team members with `wedding_access="assigned"` may still see all weddings in these endpoints.
3. **manage_calendar permission:** `planner_calendar.py` uses `manage_calendar` which is not in the `ROLE_PRESETS` or `ALL_PERMISSION_KEYS`. This will always fail for team members.

---

## Phase 4: Invite Email & Accept Flow — COMPLETE

- **Email:** `_send_invite_email()` method in team_management_service.py generates HTML invite emails with company name, role, permissions display, and acceptance link. Uses generic `send_email()` with `email_type="team_invite"`.
- **Accept Page:** `src/app/admin/team/accept/page.tsx` is complete with token-based invite lookup, form for name + password, password validation, and redirect to login on success.

**No gaps found.**

---

## Phase 5: Frontend — Team Management Page — MOSTLY COMPLETE

### Fully Implemented:
- **Team page** (`src/app/admin/planner/team/page.tsx`) — Complete with seat usage, invite button, member table, status tabs, search, stats cards, action buttons, empty state.
- **Invite modal** (`InviteTeamMemberModal.tsx`) — Email, role cards, permission toggles, wedding access selector, portal rendering, keyboard accessibility.
- **Edit modal** (`EditTeamMemberModal.tsx`) — Pre-populated form, role/permission/wedding editing.
- **Constants** (`teamConstants.ts`) — Shared ROLES, ALL_PERMISSIONS, ROLE_DEFAULTS.
- **Sidebar** (`Sidebar.tsx`) — Team nav item visible for planners only; team members see permission-filtered navigation.

### Gaps Found:

**GAP 5A: AdminContext missing team member fields**
- `src/app/contexts/AdminContext.tsx` — The `UserProfile` interface does NOT include `is_team_member`, `team_permissions`, or `wedding_scope` fields. However, the Sidebar code references `userProfile.is_team_member` and `userProfile.team_permissions`, which means these checks will fail at runtime.
- The plan requires fetching from `/admin/team/permissions` on login to populate these fields.

**GAP 5B: Dashboard not filtered for team members**
- `src/app/admin/planner/page.tsx` — Currently shows all planner weddings without filtering by the team member's `wedding_access` and `assigned_wedding_ids`. A team member with "assigned" access would see metrics for weddings they shouldn't access.

---

## Phase 6: Activity Logging & Notifications — MOSTLY COMPLETE

### Implemented:
- **Activity log service** (`activity_log_service.py`) — Team member event types defined: `TEAM_MEMBER_INVITED`, `TEAM_MEMBER_ACCEPTED`, `TEAM_MEMBER_UPDATED`, `TEAM_MEMBER_DEACTIVATED`, `TEAM_MEMBER_REACTIVATED`, `TEAM_MEMBER_REMOVED`.
- **Notification service** (`notification_service.py`) — Generic notification infrastructure exists.

### Gaps Found:

**GAP 6A:** Activity logs do not include team member name/role in logged actions (plan says: "John (Editor) updated guest RSVP for Emmanuel & Peace wedding"). Currently only logs email/ID.

**GAP 6B:** Team-specific notification types not defined. The plan requires notifying the planner owner when a team member accepts an invite or performs destructive actions.

---

## P3 Backlog Items (from Code Review Report) — NOT ADDRESSED

These 6 items from the code review are still outstanding:

1. Rename `_format_team_member` → `_serialize_team_member`
2. Structured logging consistency
3. Bulk deactivation API
4. `last_active_at` fire-and-forget timeout
5. Password validation error messages expose exact policy
6. Activity log `create_task` try/except wraps creation not execution

---

## Prioritized Action Items

### CRITICAL (Must fix before production)

1. **Implement Phase 3 for 10 remaining API files** — gallery_admin, gallery_upload, vendor_dashboard, reminder, reminder_twilio, forms, planner_metrics, wedding, contracts, packages. Each needs `require_team_or_planner` + `enforce_team_permission()`.
2. **Wire up `get_accessible_wedding_ids()`** in all 19 API files for wedding scoping.
3. **Fix `manage_calendar` permission** in planner_calendar.py — either add it to ROLE_PRESETS or map to an existing permission.

### HIGH (Fix this sprint)

4. **Add team fields to AdminContext** — `is_team_member`, `team_permissions`, `team_wedding_access`, `team_assigned_wedding_ids` in `UserProfile` interface; fetch from `/admin/team/permissions` on login.
5. **Filter dashboard for team members** — Scope metrics in `page.tsx` to assigned weddings only.
6. **Standardize auth decorators** — Decide between `require_wedding_planner_only`, `require_admin_or_planner`, and `require_team_or_planner`. The plan uses `require_team_or_planner` consistently.

### MEDIUM (Fix next sprint)

7. **Enrich activity logs** with team member name and role.
8. **Add team-specific notification types** to notification_service.
9. **Address P3 backlog** from code review report.

---

## Security Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Security** | 7/10 | Strong permission model and owner isolation. Gap: 10 unprotected endpoint files allow team members to bypass permissions entirely on those features. Wedding scoping utility not wired up. |
| **Performance** | 8/10 | Good caching, batched queries, bounded resources. P3 backlog items are minor. |
| **Correctness** | 7/10 | Race conditions addressed. `manage_calendar` permission will always deny. AdminContext type mismatch will cause runtime errors for team members. |
| **Maintainability** | 8/10 | Clean architecture, shared constants, good separation. Some decorator inconsistency across API files. |
| **Frontend** | 8/10 | Excellent UX with optimistic updates, accessibility, portal modals. AdminContext gap blocks team member login experience. |

---

*Generated by parallel code review agents examining ~30+ files across backend and frontend.*
