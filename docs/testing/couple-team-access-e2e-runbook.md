# Couple + Team Access E2E Runbook

**Purpose:** end-to-end validation for planner ownership normalization, couple lifecycle enforcement, team permission alignment, and the `Communications` cutover for couple messaging.

**Last Updated:** April 7, 2026

## 1. Scope

Use this runbook when changes touch any of these areas:

1. Planner ownership source of truth on weddings, couples, or team members
2. Couple portal access lifecycle:
   `pending_setup`, `active`, `revoked_by_planner`, `owner_cancelled`, `archived_readonly`
3. Team-member permissions:
   `manage_couple_portal`, `message_couples`, `send_rsvp`, `send_reminders`
4. Planner `Communications` routes and couple conversation access
5. Planner subscription cancellation / reactivation side effects on couples and team members

This runbook is not just visual QA. Every scenario must verify:

1. the browser behavior
2. the network request / response
3. the reread after refresh
4. the persisted state in MongoDB when DB access is available

## 2. What Changed

This runbook covers the behavior implemented across these files:

1. Ownership helpers:
   `app/utils/planner_ownership.py`
2. Ownership drift reporting:
   `app/scripts/report_planner_ownership_drift.py`
3. Couple lifecycle:
   `app/services/couple_lifecycle_service.py`
4. Couple auth and route guard:
   `app/api/couple_auth.py`
   `app/dependencies/couple_auth.py`
   `app/contexts/CoupleAuthContext.tsx`
   `app/components/CoupleRouteGuard.tsx`
5. Planner-side couple management and messaging:
   `app/api/couple_invite.py`
   `app/api/couple_portal.py`
6. Team permissions and UI gating:
   `app/models/team_member.py`
   `app/admin/utils/teamAccess.ts`
   `app/admin/components/Sidebar.tsx`
   `app/admin/communications/components/CommunicationsTabs.tsx`
7. Planner cancellation / reactivation side effects:
   `app/services/subscription_service.py`
   `app/services/stripe_service.py`
   `app/services/team_management_service.py`

## 3. Preconditions

### Required Services

1. Backend running on one hostname consistently, for example `http://localhost:8000`
2. Frontend running on one hostname consistently, for example `http://localhost:3000`
3. MongoDB available
4. Stripe test mode configured if you want to verify cancellation / reactivation through the real billing portal

Important:

1. Do not mix `localhost` and `127.0.0.1` during the same run unless you are explicitly testing CORS normalization.
2. Use the same host family for frontend and backend when possible.

### Required Accounts

Prepare these before starting:

| Role | Minimum Data Needed |
|---|---|
| Planner owner | Active account, at least 2 weddings, at least 1 active couple account, access to planner billing |
| Root admin | Able to inspect and, if needed, cancel or assign subscriptions through API |
| Team member | At least 1 accepted team member account whose permissions can be edited repeatedly |
| Couple active | Existing set-up couple account on a non-archived wedding |
| Couple invite | Fresh invite token or a wedding with no linked couple account yet |

### Required Test Data

Prepare these records:

1. `Wedding A`
   active, assigned to the planner owner, linked to an active couple account
2. `Wedding B`
   active, assigned to the planner owner, not assigned to the scoped team member
3. Optional `Wedding C`
   used for archive / unarchive checks
4. One couple conversation already present for `Wedding A`
5. One team member that can be toggled between:
   `admin`, `editor`, `viewer`, and custom permissions

## 4. Preflight

Run these before any browser work:

```bash
python -m app.scripts.report_planner_ownership_drift
./.venv/bin/python -m pytest \
  tests/backend/test_planner_ownership.py \
  tests/backend/test_couple_lifecycle_service.py \
  tests/backend/test_couple_auth_lifecycle.py \
  tests/backend/test_couple_permission_contract.py -q
```

Expected:

1. The ownership drift report completes without unresolved owners.
2. The targeted backend suite passes.

If you want the optional dry-run report artifact:

```bash
python -m app.scripts.report_planner_ownership_drift --verbose
```

### Ownership Report Pass Criteria

The report is acceptable when:

1. `weddings_unresolved = 0`
2. `couples_owner_unresolved = 0`
3. `team_members_owner_unresolved = 0`

If any drift exists, do not proceed blindly. Resolve it first or run:

```bash
python -m app.scripts.report_planner_ownership_drift --apply
```

only on a controlled environment where backfill is allowed.

## 5. Evidence To Capture

For each major scenario keep:

1. one screenshot of the final UI state
2. the relevant network request and response
3. the URL after the action
4. DB evidence if available

Recommended artifact folder:

`output/playwright/couple-team-access/`

## 6. Expected Permission Matrix

Use this as the browser truth table.

| Scenario | Weddings Nav | Communications Nav | Couple Access Section | Couple Conversation | Communications Tabs |
|---|---:|---:|---:|---:|---|
| Planner owner | Yes | Yes | Yes | Yes | Inbox, Invites, Reminders, Individual, History |
| Team admin default | Yes | Yes | Yes | Yes | Inbox, Invites, Reminders, Individual, History |
| Team editor default | Yes | No | Yes | No | None |
| Team viewer default | No | No | No | No | None |
| Wedding-settings only | Yes | No | Yes | No | None |
| Guest-communications only | No | Yes | No | No | Reminders, Individual, History |
| Couple-messaging only | No | Yes | No | Yes | Inbox only |
| Assigned-only couple team | Yes | Yes | Yes for assigned wedding only | Yes or No based on `message_couples` | Must be blocked on unassigned weddings |

Known current nuance:

1. direct navigation to a denied wedding detail route for a viewer currently renders `Wedding Not Found`
2. treat that as a pass for access denial unless the product intentionally changes the copy

## 7. Browser Scenarios

### 7.1 Planner Owner Baseline

Goal: prove the owner sees all canonical surfaces.

Steps:

1. Log in as the planner owner.
2. Confirm the sidebar shows `Weddings` and `Communications`.
3. Open `/admin/weddings`.
4. Open `Wedding A`.
5. On the wedding detail screen, open the `Couple` tab.
6. Confirm the `Couple Access` section is visible.
7. Open `/admin/communications/inbox?wedding_id=<WeddingA>`.
8. Confirm the inbox loads and the couple conversation is selectable.
9. Switch to `/admin/communications/invites`, `/reminders`, `/individual`, and `/history`.

Network to watch:

1. `GET /admin/profile`
2. `GET /admin/team/permissions`
3. `GET /admin/couple-portal/couples`
4. `GET /admin/couple-portal/conversations`

Expected:

1. all pages load without access denial
2. `Couple Access` is visible
3. the couple conversation appears in `Inbox`
4. all communications tabs are visible

### 7.2 Couple Invite, Setup, and Login

Goal: verify the active lifecycle path from invite to authenticated portal.

Steps:

1. As planner owner, open `Wedding B` -> `Couple` tab.
2. Click `Invite Couple`.
3. Submit the couple email and names.
4. Confirm the row appears in `Couple Access` with status `Pending Setup`.
5. Complete setup through the invite link.
6. Sign in as the couple.
7. Hard refresh the dashboard.

Network to watch:

1. `POST /admin/couple-portal/invite`
2. `POST /couple/setup-password`
3. `GET /couple/profile`
4. `GET /couple/portal/dashboard`

Expected:

1. invite request returns `200`
2. the planner UI shows `Pending Setup`
3. setup returns `200`
4. the couple reaches `/couple/dashboard`
5. refresh still works

DB checks:

1. `couple_users.access_state = "active"`
2. `couple_users.setup_completed = true`
3. `couple_users.is_active = true`
4. `couple_users.owner_cancelled_at = null`
5. `couple_users.revoked_at = null`

### 7.3 Couple Revoke and Restore

Goal: verify manual planner blocking is separate from owner cancellation.

Steps:

1. As planner owner, open `Wedding A` -> `Couple` tab.
2. Click `Revoke Access`.
3. In a fresh couple session, try to sign in.
4. Confirm the login page shows the paused-access banner.
5. As planner owner, click `Restore Access`.
6. Sign in as the same couple again.

Network to watch:

1. `PATCH /admin/couple-portal/couples/{couple_id}/revoke`
2. `POST /couple/login`
3. `GET /couple/profile`
4. `PATCH /admin/couple-portal/couples/{couple_id}/restore`

Expected:

1. revoke returns `200`
2. blocked login returns `403`
3. the login page shows `Portal access paused`
4. restore returns `200`
5. couple login works again

DB checks:

After revoke:

1. `access_state = "revoked_by_planner"`
2. `is_active = false`
3. `revoked_at != null`
4. `owner_cancelled_at = null`

After restore:

1. `access_state = "active"` or `pending_setup` for an invite that was never completed
2. `revoked_at = null`
3. `owner_cancelled_at = null`

### 7.4 Planner Cancellation and Reactivation

Goal: verify owner cancellation suspends both couples and team members, then restores only eligible records.

Preferred full E2E path:

1. As planner owner, open `/admin/planner/billing`.
2. Use `Cancel Subscription` so the Stripe billing portal drives the change.
3. Wait for the cancellation webhook and refresh planner state.
4. Try to sign in as:
   1. the planner owner
   2. a team member on that owner
   3. the active couple on `Wedding A`
5. Reactivate the subscription through the normal billing flow.
6. Repeat the login checks.

Deterministic QA path when Stripe portal is not available:

1. Use a root-admin controlled call to the subscription service entry point instead of the UI flow.
2. Only use this when you need lifecycle verification but cannot run the real billing portal.
3. Treat this as lifecycle verification, not full billing E2E.

Network to watch:

1. planner billing portal session creation:
   `POST /stripe/create-portal-session`
2. cancellation side effects eventually reflected in:
   `GET /admin/profile`
   `POST /couple/login`
   team-member login flow

Expected after cancellation:

1. planner access is blocked
2. team-member access is blocked
3. couple login returns `403`
4. couple login page shows paused-access messaging, not a generic bad-password error

Expected after reactivation:

1. planner access returns
2. team members suspended by owner cancellation can sign in again
3. couples blocked by owner cancellation can sign in again
4. manually revoked couples remain blocked

DB checks after cancellation:

1. `couple_users.access_state = "owner_cancelled"` for eligible couples
2. `couple_users.owner_cancelled_at != null`
3. `team_members.status = "suspended_owner_cancelled"` for active members
4. wedding and related resources may show `data_access_suspended_reason = "planner_subscription_cancelled"`

DB checks after reactivation:

1. `owner_cancelled_at = null` on restored couples
2. restored couples return to `active` or `pending_setup`
3. team members move back to `active`

### 7.5 Archived Wedding Read-Only Access

Goal: verify archive is distinct from blocking.

This flow is usually API-assisted because there is no dedicated planner UI control in the current app surface.

Steps:

1. Archive `Wedding C`.
2. Sign in as the linked couple.
3. Open `/couple/dashboard`.
4. Confirm the archive banner is visible.
5. Open Inbox, Registry, FAQ, and Memories.
6. Attempt a write action in one of those areas.
7. Unarchive the wedding.

Network to watch:

1. `POST /admin/couple-portal/archive?wedding_id=<id>`
2. `GET /couple/profile`
3. `GET /couple/portal/dashboard`
4. `DELETE /admin/couple-portal/archive?wedding_id=<id>`

Expected:

1. archived couple can still sign in
2. dashboard shows the archive banner
3. archive behaves as read-only, not blocked
4. after unarchive, the banner disappears and normal lifecycle rules resume

DB checks:

1. `couple_users.wedding_archived = true` after archive
2. `archived_weddings.original_wedding_id = <id>` exists
3. `wedding_archived = false` after unarchive

### 7.6 Team Permission Matrix

Goal: verify planner UI exposure matches backend enforcement.

Use one accepted team member account. Between each sub-case:

1. change the role or custom permissions in `/admin/planner/team`
2. sign out
3. sign in as the team member in a fresh session

#### Case A: Team Admin Default

Expected:

1. sidebar shows `Weddings` and `Communications`
2. wedding detail page shows `Couple Access`
3. `Communications -> Inbox` shows the couple conversation
4. no access denial on couple management or messaging routes

#### Case B: Team Editor Default

Expected:

1. sidebar shows `Weddings`
2. sidebar does not show `Communications`
3. wedding detail page still shows `Couple Access`
4. direct entry to `/admin/communications/inbox` is denied

#### Case C: Team Viewer Default

Expected:

1. no `Weddings` nav
2. no `Communications` nav
3. direct entry to `/admin/weddings` is denied
4. direct entry to a wedding detail page is denied

#### Case D: Wedding Settings Only

Custom permissions:

1. `manage_wedding_settings = true`
2. `manage_couple_portal = false`
3. `message_couples = false`

Expected:

1. `Weddings` nav visible
2. `Communications` nav hidden
3. no `Couple Access` section

#### Case E: Guest Communications Only

Custom permissions:

1. `send_reminders = true`
2. `send_rsvp = false`
3. `message_couples = false`
4. `manage_couple_portal = false`

Expected:

1. `Communications` nav visible
2. `Weddings` nav hidden
3. no couple conversation in `Inbox`
4. tabs visible:
   `Reminders`, `Individual`, `History`
5. tabs hidden:
   `Invites`

#### Case F: Couple Messaging Only

Custom permissions:

1. `message_couples = true`
2. `send_rsvp = false`
3. `send_reminders = false`
4. `manage_couple_portal = false`

Expected:

1. `Communications` nav visible
2. `Weddings` nav hidden
3. `Inbox` visible
4. couple conversation visible
5. `Invites`, `Reminders`, `Individual`, and `History` hidden

#### Case G: Assigned-Wedding Couple Team

Custom permissions:

1. `manage_couple_portal = true`
2. optional `message_couples = true` depending on whether you want messaging included
3. `wedding_access = assigned`
4. `assigned_wedding_ids = [Wedding A]`

Expected:

1. team member can open `Wedding A`
2. team member cannot open `Wedding B`
3. couple management and messaging must only work on assigned weddings

Network to watch for all matrix cases:

1. `GET /admin/team/permissions`
2. `PATCH /admin/team/members/{team_member_id}`
3. `GET /admin/weddings`
4. `GET /admin/couple-portal/couples`
5. `GET /admin/couple-portal/conversations`

### 7.7 Couple Messaging Through Communications

Goal: verify the `Communications` cutover still supports planner <-> couple messaging under the new permissions.

Steps:

1. As planner owner or a team member with `message_couples = true`, open:
   `/admin/communications/inbox?wedding_id=<WeddingA>`
2. Open the couple conversation.
3. Send a message.
4. As the couple, open the Inbox and confirm the message appears without manual reselection tricks.
5. Reply as the couple.
6. Return to the planner and confirm the reply appears.
7. Click another communications tab and come back to `Inbox`.

Network to watch:

1. `POST /admin/couple-portal/messages`
2. `GET /admin/couple-portal/messages?wedding_id=<id>`
3. `POST /admin/couple-portal/messages/read`
4. `POST /couple/portal/messages`
5. `GET /couple/portal/messages`
6. `POST /couple/portal/messages/read`

Expected:

1. both sides can exchange messages if allowed
2. read state changes are done by explicit `POST .../messages/read`
3. `GET` message-history endpoints do not mutate unread state
4. wedding-scoped navigation back into `Inbox` preserves `wedding_id`

### 7.8 Meeting Ownership and Couple Visibility

Goal: verify meetings are stored against the canonical owner, not only the acting team member.

Steps:

1. Sign in as a team member with `manage_couple_portal = true`.
2. Create a meeting for `Wedding A`.
3. Sign in as the couple on `Wedding A`.
4. Open the dashboard or meetings surface and confirm the meeting is visible.

Network to watch:

1. `POST /admin/couple-portal/meetings`
2. `GET /couple/portal/meetings`
3. `GET /admin/couple-portal/meetings?wedding_id=<id>`

Expected:

1. meeting creation succeeds for the allowed team member
2. the couple sees the meeting
3. planner listing is scoped by `wedding_id`, not actor email

DB checks:

1. `planner_tasks.wedding_id = <WeddingA>`
2. `planner_tasks.planner_email = owner planner email`
3. `planner_tasks.scheduled_by_email = acting team member email`

## 8. API and DB Assertions

Use these as the final truth when browser behavior is ambiguous.

### Ownership

`weddings`

1. `assigned_planner_id` is populated
2. `assigned_planner_email` matches the owner

`couple_users`

1. `planner_id` and `planner_email` mirror the wedding owner
2. they are not treated as the authority when they disagree with the wedding

`team_members`

1. `owner_id` and `owner_email` match the planner owner
2. `status` uses declared states, including `suspended_owner_cancelled`

### Couple Lifecycle

`couple_users.access_state`

1. `pending_setup`
2. `active`
3. `revoked_by_planner`
4. `owner_cancelled`

Derived read-only state:

1. `archived_readonly` is effective when `wedding_archived = true`

### Team Permissions

Check `team_members.custom_permissions` and the effective `/admin/team/permissions` payload for:

1. `manage_couple_portal`
2. `message_couples`
3. `send_rsvp`
4. `send_reminders`

## 9. Exit Criteria

Do not mark the release ready until all of these are true:

1. Ownership drift report has no unresolved owners
2. Planner owner baseline passes
3. Invite -> setup -> login passes
4. Revoke -> blocked login -> restore passes
5. Cancellation / reactivation passes in at least one environment with realistic billing behavior
6. Archive / unarchive passes
7. Team permission matrix passes for all seven scenarios
8. Couple messaging through `Communications` passes
9. Meeting ownership / visibility passes

## 10. Existing Browser Matrix Reference

The last recorded permission-matrix run is here:

1. `output/playwright/team-permission-matrix/results.json`
2. `output/playwright/team-permission-matrix/*.png`

Use it as a baseline, not a substitute for rerunning the matrix after future changes.
