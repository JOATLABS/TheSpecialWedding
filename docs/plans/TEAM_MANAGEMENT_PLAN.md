# Team Management Feature — Implementation Plan

## Overview

Add team/user management so that a planner (the account owner / admin) can invite team members to their account, assign roles with customizable permissions, and scope access per-wedding or across all weddings. This feature is plan-gated using the existing `staff_seats` field on subscription plans.

---

## Phase 1: Data Model & Database Layer

### 1A. New MongoDB Collection: `team_members`

```python
{
    "_id": ObjectId,
    "owner_id": str,              # The planner (account owner) user _id
    "owner_email": str,           # Denormalized for fast queries
    "user_id": str | None,        # Links to users collection once they accept invite
    "email": str,                 # Team member's email
    "first_name": str | None,
    "last_name": str | None,
    "status": str,                # "pending" | "active" | "deactivated"

    # Role & Permissions
    "role": str,                  # "admin" | "editor" | "viewer" (preset starting point)
    "custom_permissions": {       # Overrides from the role preset
        "manage_guests": bool,
        "manage_budget": bool,
        "manage_gallery": bool,
        "manage_seating": bool,
        "manage_vendors": bool,
        "send_rsvp": bool,
        "send_reminders": bool,
        "manage_forms": bool,
        "view_analytics": bool,
        "manage_wedding_settings": bool,
        "manage_contracts": bool,
        "manage_packages": bool,
    },

    # Wedding Scope
    "wedding_access": str,        # "all" | "assigned"
    "assigned_wedding_ids": [str], # Only used when wedding_access == "assigned"

    # Invitation
    "invite_token": str,
    "invite_token_expires_at": datetime,
    "invited_at": datetime,
    "accepted_at": datetime | None,

    # System
    "created_at": datetime,
    "updated_at": datetime,
    "deactivated_at": datetime | None,
}
```

### 1B. Extend `users` Collection

When a team member accepts an invite, a new user document is created in the `users` collection with:
- `role`: `"team_member"` (new role)
- `parent_planner_id`: the owner's user _id
- `team_member_id`: reference back to the `team_members` doc

### 1C. Role Presets (defined in code, not DB)

```python
ROLE_PRESETS = {
    "admin": {
        "manage_guests": True, "manage_budget": True, "manage_gallery": True,
        "manage_seating": True, "manage_vendors": True, "send_rsvp": True,
        "send_reminders": True, "manage_forms": True, "view_analytics": True,
        "manage_wedding_settings": True, "manage_contracts": True, "manage_packages": True,
    },
    "editor": {
        "manage_guests": True, "manage_budget": True, "manage_gallery": True,
        "manage_seating": True, "manage_vendors": False, "send_rsvp": False,
        "send_reminders": False, "manage_forms": True, "view_analytics": True,
        "manage_wedding_settings": False, "manage_contracts": False, "manage_packages": False,
    },
    "viewer": {
        "manage_guests": False, "manage_budget": False, "manage_gallery": False,
        "manage_seating": False, "manage_vendors": False, "send_rsvp": False,
        "send_reminders": False, "manage_forms": False, "view_analytics": True,
        "manage_wedding_settings": False, "manage_contracts": False, "manage_packages": False,
    },
}
```

### 1D. Database Indexes

- `team_members`: compound index on `(owner_id, email)` unique
- `team_members`: index on `invite_token` for fast accept lookups
- `team_members`: index on `user_id` for auth lookups
- `users`: index on `parent_planner_id` for team queries

### Files to create/modify:
- **NEW** `app/models/team_member.py` — Pydantic models
- **MODIFY** `app/models/user_extended.py` — Add `parent_planner_id`, `team_member_id` fields
- **MODIFY** `app/core/database_indexes.py` — Add team_members indexes

---

## Phase 2: Backend Service & API

### 2A. New Service: `TeamManagementService`

**File:** `app/services/team_management_service.py`

Methods:
- `invite_team_member(owner, email, role, custom_permissions, wedding_access, assigned_wedding_ids)` — Creates team_members doc, sends invite email
- `resend_invite(owner, team_member_id)` — Regenerates token, resends email
- `accept_invite(token, password, first_name, last_name)` — Creates user in users collection, updates team_members status
- `list_team_members(owner_id)` — Returns all team members for the planner
- `get_team_member(owner_id, team_member_id)` — Get single member details
- `update_team_member(owner_id, team_member_id, updates)` — Update role, permissions, wedding access
- `deactivate_team_member(owner_id, team_member_id)` — Soft-delete (set status=deactivated, deactivate user)
- `reactivate_team_member(owner_id, team_member_id)` — Reactivate a deactivated member
- `remove_team_member(owner_id, team_member_id)` — Hard delete (remove from team_members AND users)
- `check_seat_limit(owner_id)` — Validates against plan's staff_seats limit
- `get_member_permissions(user_id)` — Used by auth middleware to resolve effective permissions

### 2B. New API Router: `team_management.py`

**File:** `app/api/team_management.py`
**Prefix:** `/admin/team`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/admin/team/invite` | require_wedding_planner + feature_gate | Invite a new team member |
| GET | `/admin/team/members` | require_wedding_planner | List all team members |
| GET | `/admin/team/members/{id}` | require_wedding_planner | Get member details |
| PATCH | `/admin/team/members/{id}` | require_wedding_planner | Update member role/permissions/wedding access |
| POST | `/admin/team/members/{id}/resend-invite` | require_wedding_planner | Resend invitation email |
| POST | `/admin/team/members/{id}/deactivate` | require_wedding_planner | Deactivate member |
| POST | `/admin/team/members/{id}/reactivate` | require_wedding_planner | Reactivate member |
| DELETE | `/admin/team/members/{id}` | require_wedding_planner | Remove member permanently |
| GET | `/admin/team/seats` | require_wedding_planner | Get seat usage vs. plan limit |
| POST | `/admin/team/accept-invite` | PUBLIC (no auth) | Accept invitation + set password |
| GET | `/admin/team/invite-info/{token}` | PUBLIC (no auth) | Get invite details for the setup page |
| GET | `/admin/team/permissions` | require_team_or_planner | Get current user's effective permissions |

### 2C. Feature Gate

- **NEW** `require_team_management` dependency in `app/dependencies/feature_gates.py`
  - Checks `staff_seats > 0` on the planner's plan
  - Returns 403 with `upgrade_required: true` if not available
- Add `"team_management": True/False` to plan features dict for plans that include it

### 2D. Auth Changes

**Modify:** `app/dependencies/auth_extended.py`

- Extend `ExtendedAuthUser` with:
  - `is_team_member: bool`
  - `parent_planner_id: str | None`
  - `team_permissions: dict | None`
  - `team_wedding_access: str | None` ("all" or "assigned")
  - `team_assigned_wedding_ids: list[str]`
- In `get_current_user_extended()`: when role == "team_member", load team_members doc and populate the above fields
- Modify `check_wedding_access()`: team members check their `wedding_access` and `assigned_wedding_ids`
- **NEW** `require_team_or_planner` dependency — allows both planner owners and their team members
- **NEW** `require_team_permission(permission_name)` — factory that checks if the team member has a specific permission

### Files to create/modify:
- **NEW** `app/services/team_management_service.py`
- **NEW** `app/api/team_management.py`
- **MODIFY** `app/dependencies/auth_extended.py` — Team member auth + permission checks
- **MODIFY** `app/dependencies/feature_gates.py` — Add team_management gate
- **MODIFY** `app/main.py` — Register team_management router
- **MODIFY** `app/core/database_indexes.py` — Add team_members indexes

---

## Phase 3: Protect Existing Endpoints with Team Permissions

This is a critical phase. Every existing planner endpoint needs to be updated so team members can use them (with their scoped permissions), while planner-owners continue to work as before.

### Strategy

Replace `require_wedding_planner` with `require_team_or_planner` on all planner endpoints, then wrap sensitive actions with `require_team_permission("permission_name")`.

| Module | Permission Required |
|--------|-------------------|
| `guest.py`, `admin_rsvp.py`, `guest_export.py` | `manage_guests` |
| `budget.py` | `manage_budget` |
| `gallery_admin.py`, `gallery_upload.py` | `manage_gallery` |
| `tables.py` (seating) | `manage_seating` |
| `vendor_management.py`, `vendor_dashboard.py` | `manage_vendors` |
| `reminder.py`, `reminder_twilio.py`, `reminder_telnyx.py`, `email_reminders.py` | `send_reminders` |
| `rspv.py` (send RSVP) | `send_rsvp` |
| `forms.py` | `manage_forms` |
| `planner_metrics.py` | `view_analytics` |
| `wedding.py` (settings) | `manage_wedding_settings` |
| `contracts.py` | `manage_contracts` |
| `packages.py` | `manage_packages` |

For GET/read endpoints: team members with ANY permission can read data for weddings they have access to.
For POST/PUT/DELETE (mutations): require the specific permission.

### Wedding Scoping

Team members with `wedding_access == "assigned"` need their queries filtered to only their `assigned_wedding_ids`. This will be handled by a utility function `get_accessible_wedding_ids(user)` that returns either "all" or a specific list, used in every wedding-related query.

### Files to modify:
- All API files listed in the table above (~15 files)
- Each change is small: swap the dependency and add permission checks on mutation endpoints

---

## Phase 4: Invite Email & Accept Flow

### 4A. Invite Email Template

Using the existing ResendEmailService pattern:
- Styled email with planner's company name, role assigned, link to accept
- Link format: `https://thespecialwedding.io/admin/team/accept?token={token}`
- Token expires in 7 days (configurable)

### 4B. Accept Invitation Page (Frontend)

**NEW** `src/app/admin/team/accept/page.tsx`

- Public page (no auth required)
- Fetches invite details via token
- Shows: planner company name, role assigned, permissions summary
- Form: first name, last name, password, confirm password
- On submit: calls `POST /admin/team/accept-invite`
- On success: redirect to login page with success message

### Files to create/modify:
- **NEW** `src/app/admin/team/accept/page.tsx`
- **MODIFY** `app/services/email_service_resend.py` — Add `send_team_invite_email()` method

---

## Phase 5: Frontend — Team Management Page

### 5A. Team Members Page

**NEW** `src/app/admin/planner/team/page.tsx`

Layout:
- Header: "Team Management" with seat usage badge (e.g., "3/5 seats used")
- "Invite Team Member" button (opens modal)
- Table/list of team members with columns:
  - Name, Email, Role, Status (active/pending/deactivated), Wedding Access, Actions
- Action buttons: Edit, Resend Invite, Deactivate/Reactivate, Remove
- Empty state for planners with no team members yet
- Upgrade prompt for planners whose plan has 0 staff_seats

### 5B. Invite Modal

**NEW** `src/app/admin/planner/team/components/InviteTeamMemberModal.tsx`

- Email input
- Role selector (Admin / Editor / Viewer dropdown)
- Permission toggles (pre-filled from role preset, individually toggleable)
- Wedding access selector: "All Weddings" or "Specific Weddings"
  - If "Specific Weddings": multi-select dropdown of the planner's weddings
- Invite button

### 5C. Edit Member Modal

**NEW** `src/app/admin/planner/team/components/EditTeamMemberModal.tsx`

- Same fields as invite but pre-populated
- Can change role (which resets permissions to preset) or customize individual permissions
- Can change wedding access scope

### 5D. Sidebar Navigation Update

**MODIFY** `src/app/admin/components/Sidebar.tsx`

- Add "Team" nav item under planner section with Users icon
- Route: `/admin/planner/team`
- Only visible when the planner's plan has `staff_seats > 0`

### 5E. Team Member Dashboard Adjustments

When a team member logs in, they should see a filtered dashboard:
- **MODIFY** `src/app/admin/planner/page.tsx` — Filter metrics to only accessible weddings
- **MODIFY** `src/app/admin/components/Sidebar.tsx` — Hide nav items for permissions the member doesn't have
- **MODIFY** `src/app/contexts/AdminContext.tsx` — Add team permissions and wedding scope to UserProfile interface, fetch from `/admin/team/permissions` on login

### Files to create/modify:
- **NEW** `src/app/admin/planner/team/page.tsx`
- **NEW** `src/app/admin/planner/team/components/InviteTeamMemberModal.tsx`
- **NEW** `src/app/admin/planner/team/components/EditTeamMemberModal.tsx`
- **MODIFY** `src/app/admin/components/Sidebar.tsx`
- **MODIFY** `src/app/admin/planner/page.tsx`
- **MODIFY** `src/app/contexts/AdminContext.tsx`

---

## Phase 6: Activity Logging & Notifications

### 6A. Team Activity Log

Extend the existing activity log system to track team actions:
- "John (Editor) updated guest RSVP for Emmanuel & Peace wedding"
- "Sarah (Admin) sent 50 RSVP reminders"

**MODIFY** `app/api/admin_activity.py` — Include team member name/role in logged actions

### 6B. Planner Notifications

When team members perform significant actions, notify the planner owner:
- Team member accepted invite
- Team member performed a destructive action (deleted guests, removed vendors, etc.)

**MODIFY** `app/services/notification_service.py` — Add team action notification types

---

## Phase 7: Testing & Verification

### 7A. Backend Tests
- Unit tests for `TeamManagementService`
- API integration tests for all `/admin/team/*` endpoints
- Permission enforcement tests (ensure a viewer can't mutate data)
- Wedding scoping tests (ensure assigned-only members can't access other weddings)
- Seat limit tests (ensure invites fail when seats are full)

### 7B. Frontend Tests
- Invite flow end-to-end
- Permission-based UI filtering (hidden nav items, disabled buttons)
- Wedding scope filtering in team member dashboard

### 7C. Manual QA Checklist
- [ ] Planner on plan with 0 seats sees upgrade prompt, not the team page
- [ ] Planner can invite, and invitee receives email
- [ ] Invitee can accept, set password, and log in
- [ ] Team member with "viewer" role cannot mutate any data
- [ ] Team member with "assigned" wedding access cannot see other weddings
- [ ] Planner admin can change a member's role and permissions take effect immediately
- [ ] Deactivated member cannot log in
- [ ] Reactivated member can log in again with old password
- [ ] Seat limit enforced: invite fails when all seats are filled
- [ ] Removing a member frees up a seat

---

## Implementation Order (Recommended)

| Step | Phase | Estimated Effort | Dependencies |
|------|-------|-----------------|--------------|
| 1 | Phase 1: Data Models & DB | Small | None |
| 2 | Phase 2A-2B: Service + API | Medium | Phase 1 |
| 3 | Phase 2C-2D: Feature Gate + Auth | Medium | Phase 1 |
| 4 | Phase 4: Invite Email + Accept Page | Small | Phase 2 |
| 5 | Phase 5A-5C: Team Management Page + Modals | Medium-Large | Phase 2 |
| 6 | Phase 5D-5E: Sidebar + Dashboard Adjustments | Medium | Phase 5 |
| 7 | Phase 3: Protect Existing Endpoints | Large (many files, careful work) | Phase 2D |
| 8 | Phase 6: Activity Logging | Small | Phase 3 |
| 9 | Phase 7: Testing | Medium | All above |

**Total new files:** ~7
**Total modified files:** ~25
**Risk areas:** Phase 3 (modifying existing endpoints) and Phase 2D (auth changes) are the highest-risk since they touch every existing planner workflow. These should be done carefully with thorough testing.
