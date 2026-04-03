# Feature Scope: Couple Portal (Revised)

## Overview

A **fully interactive portal** where couples can manage key aspects of their wedding — view updates from their planner, make monthly payments, review and sign contracts, fill out data-collection forms, communicate with their planner, and schedule recurring meetings. Couples are invited via **magic link** from their planner and set up password-based accounts.

> **Revision Note:** This document supersedes the original read-only, token-based couple portal spec. The scope has expanded significantly to include authentication, payments, contracts, forms, messaging, scheduling, and wedding archival.

---

## What Exists Today

| Component | Status |
|-----------|--------|
| Payment portal (`/portal/[token]`) | Built — contract, payments, payment method |
| Wedding slug page (`/[slug]`) | Built — public landing page for guests |
| Wedding data model | Complete — events, budget, guests, theme_config |
| Couple authentication | **New** — Magic link invite + password setup (Phase 1 built) |
| Packages & billing | Built — package CRUD, payment schedules, AI pricing |
| Contracts | Built — sign, cancel, mark-paid, refund endpoints |
| Forms | Built — form CRUD with security validation |
| Email service | Built — Resend API via `email_service.send_email()` |

---

## Phase 1 — Core Portal (Current)

### 1. Couple Authorization (Magic Link + Password)

**Flow:**
1. Planner selects a wedding → clicks "Invite Couple" → enters couple's email
2. Backend creates a `couple_users` record with an invite token (`secrets.token_urlsafe(48)`, 7-day expiry)
3. Couple receives email with magic link → `/couple/setup?token=<invite_token>`
4. Couple verifies token, sets a password, account activates
5. Couple logs in at `/couple/login` with email + password → receives 24-hour JWT

**Key Decisions:**
- Couples stored in a **separate `couple_users` collection** (not the main `users` collection) for clean role separation
- JWT includes `role: "couple"` and `wedding_id` for scoped access
- Invite tokens are single-use and expire after 7 days
- Access tokens expire after 24 hours (longer than planner's 60 min since couples check less frequently)

**Files:**
| File | Purpose |
|------|---------|
| `app/api/couple_auth.py` | Public auth endpoints: setup-password, login, verify-invite, profile |
| `app/api/couple_invite.py` | Planner-side: invite, resend-invite, list couples (requires planner auth) |
| `app/couple/login/page.tsx` | Couple login page with navy/gold wedding theme |
| `app/couple/setup/page.tsx` | Magic link password setup page |

### 2. Monthly Payments

Couples can view the payment schedule for the planner's selected package and track payment statuses.

**Visible to Couple:**
- Package name and total contract value
- Individual payment items with amounts, due dates, and status (paid/pending/overdue)
- Running totals: amount paid, amount remaining
- Payment method on file (last 4 digits only)

**Data Source:** Existing `contracts` and `packages` collections, aggregated by `couple_portal_service.py`.

### 3. Contract Review & Signature

Couples can review contracts from their planner or vendors and sign them digitally.

**Capabilities:**
- View contract details (terms, scope, pricing)
- Digital signature workflow
- Track contract status (pending, signed, cancelled)

**Data Source:** Existing `contracts` collection and contract API endpoints.

### 4. Data Collection Forms

Planners create forms and share them with the couple. Couples fill them out, and the data flows back to the planner.

**Flow:**
1. Planner creates a form (existing form CRUD) and marks it as `shared_with_couple: true` or `target_audience: "couple"`
2. Couple sees pending forms on their dashboard
3. Couple fills out the form (supports: text, email, phone, number, date, textarea, select, checkbox fields)
4. Submission saved to `form_submissions` collection
5. Planner receives notification of new submission

**Template Forms:** Planners can create reusable form templates for common data collection (guest dietary preferences, music requests, vendor preferences, etc.)

**Files:**
| File | Purpose |
|------|---------|
| `app/couple/forms/[formId]/page.tsx` | Dynamic form filling page with field type support |
| `app/api/couple_portal.py` | Form submission and retrieval endpoints |

### 5. Planner Updates Feed

Planners share updates with couples in a presentable design — both as a timeline feed and auto-generated milestone cards.

**Update Types:**
- **Regular updates** — Text-based status updates from the planner (category badges: venue, catering, photography, etc.)
- **Milestone cards** — Auto-generated visual cards for key wedding milestones (gold/rose gradient styling)

**Data Source:** New `couple_updates` collection.

**Endpoints:**
- `POST /couple-portal/updates` — Planner creates an update (planner auth)
- `GET /couple/portal/updates` — Couple retrieves paginated updates

### 6. Inbound Messaging

Direct messaging channel between couple and planner within the portal.

**Requirements:**
- Real-time or near-real-time message delivery
- Message history preserved
- Notification to planner when couple sends a message (and vice versa)

**Status:** Planned for Phase 1, implementation pending.

### 7. Recurring Meeting Scheduling

Couples and planners can schedule recurring meetings through the portal, improving the planner's existing calendar functionality.

**Requirements:**
- Schedule one-off or recurring meetings
- Sync with planner's calendar system
- Meeting reminders for both parties

**Status:** Planned for Phase 1, implementation pending.

### 8. Wedding Archival

When a planner removes a completed wedding, all data is archived to a separate MongoDB collection for analytics. The couple's login is preserved but data is served from the archive.

**Archive Process:**
1. Planner triggers "archive wedding" action
2. `archive_wedding_data()` snapshots all wedding-related data into a single `archived_weddings` document:
   - Wedding details, guests, RSVPs, budget items, contracts, forms, form submissions, couple updates
   - Analytics-friendly top-level fields (total guests, total budget, event count, etc.)
3. Couple can still log in → dashboard detects archived status → serves data from `archived_weddings`
4. Original data can be cleaned up from active collections

**File:** `app/services/couple_portal_service.py` → `archive_wedding_data()`

---

## Portal Dashboard Structure

### Route Architecture

```
/couple/login              → Couple login (public)
/couple/setup?token=xxx    → Magic link password setup (public)
/couple/dashboard          → Main dashboard (authenticated)
/couple/forms/[formId]     → Form filling page (authenticated)
```

### Dashboard Tabs

1. **Overview** — Wedding countdown, venue/planner info, stat cards (guest stats, budget progress), quick links
2. **Timeline** — Wedding events with dates, times, locations, dress code, details
3. **Payments** — Package summary, payment schedule with statuses, amount paid/remaining
4. **Forms** — List of shared forms with pending/submitted status, navigation to fill
5. **Updates** — Planner update feed with milestone cards, category-filtered

### Data Exposed to Couples

**Visible:**
- Couple names, wedding date, timezone, venue
- Events (all details from `wedding.events`)
- Guest count summary (totals only — invited, confirmed, declined, pending)
- Budget totals (total budget, spent, remaining — no line items)
- Payment schedule & individual payment statuses
- Contract status and terms
- Planner name, email, phone
- Shared forms and their submission status
- Planner updates and milestone cards

**Hidden:**
- Individual guest list / contact info
- Detailed budget line items
- Admin settings and planner dashboard
- Other weddings managed by the planner
- Other couple accounts

---

## Backend Architecture

### New Collections

| Collection | Purpose |
|------------|---------|
| `couple_users` | Couple accounts (email, password_hash, wedding_id, invite_token, status) |
| `couple_updates` | Planner-to-couple updates (wedding_id, type, title, content, category, milestone flag) |
| `archived_weddings` | Archived wedding data snapshots for completed weddings |

### New API Files

| File | Prefix | Auth | Purpose |
|------|--------|------|---------|
| `app/api/couple_auth.py` | `/couple/` | Public | Couple auth (login, setup, verify, profile) |
| `app/api/couple_invite.py` | `/admin/couple-portal/` | Planner JWT | Invitation management |
| `app/api/couple_portal.py` | `/couple/portal/` | Couple JWT | Dashboard data, forms, updates |

### Service Layer

| File | Purpose |
|------|---------|
| `app/services/couple_portal_service.py` | Aggregates data from weddings, guests, budgets, contracts, forms, updates; handles archival |

### Frontend Files

| File | Purpose |
|------|---------|
| `app/couple/layout.tsx` | Root layout with gradient background |
| `app/couple/login/page.tsx` | Login page (navy/gold theme) |
| `app/couple/setup/page.tsx` | Password setup from invite link |
| `app/couple/dashboard/page.tsx` | Main dashboard with 5 tabs |
| `app/couple/forms/[formId]/page.tsx` | Dynamic form filling |
| `app/couple/mockups/portal-mockups.html` | Visual mockups (8 screens) |

### Planner-Side UI

| File | Purpose |
|------|---------|
| `app/admin/couple-portal/page.tsx` | Planner management page for couple invitations, updates, form sharing |
| Sidebar entry added | "Couple Portal" nav item with HeartHandshake icon |

---

## Security

- **Authentication:** Password-based with bcrypt hashing (rounds=12), JWT tokens
- **Token security:** Invite tokens are `secrets.token_urlsafe(48)`, single-use, 7-day expiry
- **Access scoping:** Couple JWT includes `wedding_id` — all queries scoped to that wedding only
- **Privacy:** No individual guest data, no budget line items, no cross-wedding visibility
- **Timing attack mitigation:** Dummy password hash used when user not found (constant-time comparison)
- **Rate limiting:** Applied to login and token verification endpoints
- **Planner controls:** Planner can revoke couple access, resend invitations

---

## Phase 2 — Future Enhancements

| Feature | Description |
|---------|-------------|
| Real-time messaging | WebSocket-based chat between couple and planner |
| Video meeting integration | Calendar integration with Zoom/Google Meet links |
| Document sharing | Planner uploads documents (PDFs, inspiration boards) viewable by couple |
| Registry display | Show wedding registries linked to the wedding |
| FAQ display | Show wedding FAQs curated by the planner |
| QR code sharing | Generate QR codes for couple portal access |
| Push notifications | Browser push notifications for new updates/messages |
| Mobile-optimized PWA | Progressive web app for mobile couple experience |

---

## Effort Estimate (Phase 1)

| Phase | Effort |
|-------|--------|
| Backend — Auth system (couple_auth, couple_invite) | 6-8 hours |
| Backend — Portal service + APIs | 8-10 hours |
| Backend — Archival system | 3-4 hours |
| Frontend — Auth pages (login, setup) | 4-5 hours |
| Frontend — Dashboard (5 tabs) | 10-14 hours |
| Frontend — Form filling page | 3-4 hours |
| Frontend — Planner management page | 4-6 hours |
| Messaging integration | 6-8 hours |
| Meeting scheduling | 4-6 hours |
| Integration, testing & polish | 6-8 hours |
| **Total** | **54-73 hours** |

---

## Dependencies

- Existing packages/contracts system (for payment data)
- Existing forms system (for shared forms)
- Email service (Resend API — for magic link invitations)
- Stripe integration (for payment status)
- Planner's calendar system (for meeting scheduling)

---

## Testing

**Test Accounts:**
- Planner: `test_planner_package@thespecialwedding.io` / `testPlannerPackage123!`
- Couple: `test_couple1@thespecialwedding.io` / `testCouplePass123!`

**Test Flow:**
1. Log in as planner → create a package → assign to a wedding
2. From Couple Portal management → invite couple via email
3. Check email → click magic link → set password
4. Log in as couple → verify dashboard data, forms, payments, updates
