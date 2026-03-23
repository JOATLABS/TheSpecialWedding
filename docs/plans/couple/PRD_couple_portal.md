# PRD: Couple Portal — The Special Wedding

**Author:** Etastic
**Last Updated:** 2026-03-22
**Status:** In Progress (Phase 1 partially built)

---

## 1. Problem Statement

Wedding planners on The Special Wedding platform currently have no structured way to collaborate with their couples digitally. Couples receive scattered updates via email, WhatsApp, or phone calls, and have no centralized place to view their wedding timeline, make payments, sign contracts, provide input on event programs, or communicate with their planner. The existing token-based payment portal (`/portal/[token]`) only surfaces contract and payment info — it's read-only, unauthenticated, and disconnected from the broader wedding data.

This gap creates three problems: (1) planners waste time repeating status updates that couples could self-serve, (2) couples feel disconnected from their own wedding planning process, and (3) critical data collection (dietary preferences, song requests, vendor preferences) happens informally and gets lost.

The cost of not solving this is measurable — planners report spending 3-5 hours per week per wedding on status communication alone, couples default to competitors with client portals, and data collection errors lead to day-of issues.

---

## 2. Goals

**User Goals:**
- Couples can view the full state of their wedding (timeline, budget summary, guest counts, payments) without contacting the planner — reducing ad-hoc status requests by 80%+
- Couples can complete planner-assigned forms (data collection) digitally, replacing paper/email workflows
- Couples can review and comment on the order of events for each ceremony, giving planners structured feedback instead of scattered messages
- Couples can view and sign contracts and track payment schedules from a single dashboard

**Business Goals:**
- Increase planner retention by offering a client-facing portal that differentiates The Special Wedding from competitors
- Reduce planner time spent on status communication by 60%+, allowing them to take on more weddings
- Create a stickier product — once couples and planners are collaborating in-portal, switching costs increase
- Generate data for wedding archival and analytics (post-wedding insights for planners)

---

## 3. Non-Goals

- **Couple-to-guest communication** — Couples will not manage guest lists, send RSVPs, or communicate with guests through this portal. That's the planner's domain. (Separate feature, different user flow.)
- **Payment processing within the couple portal** — Couples view payment status and schedules, but actual payment processing continues through the existing Stripe-backed payment portal. (Avoids duplicating payment infrastructure.)
- **Real-time co-editing** — Couples and planners will not co-edit documents, seating charts, or floor plans simultaneously. (Too complex for v1; collaborative notes cover the feedback use case.)
- **Multi-couple per wedding** — Each wedding has one couple portal login. Supporting separate logins for each partner is a future consideration. (Adds auth complexity without clear demand.)
- **Mobile native app** — The portal is web-first and responsive. No iOS/Android app in scope. (PWA is a future consideration.)

---

## 4. User Stories

### Couple Stories (Priority Order)

**Authentication & Access:**
- As a couple, I want to receive a magic link from my planner so that I can set up my portal account without needing to register manually.
- As a couple, I want to log in with my email and password so that I can access my wedding dashboard securely.
- As a couple, I want my session to last 24 hours so that I don't need to log in every time I check my wedding details.

**Dashboard & Overview:**
- As a couple, I want to see a countdown to my wedding date, venue info, and planner contact details so that I have key details at a glance.
- As a couple, I want to see aggregated guest stats (total invited, confirmed, declined, pending) so that I understand the RSVP status without seeing individual guest info.
- As a couple, I want to see a budget summary (total budget, spent, remaining) so that I know where we stand financially.

**Payments & Contracts:**
- As a couple, I want to view my payment schedule with amounts, due dates, and statuses so that I know what I owe and when.
- As a couple, I want to review and digitally sign contracts so that I don't need to print, sign, and scan documents.
- As a couple, I want to see a running total of what I've paid vs. what remains so that I can plan my finances.

**Forms & Data Collection:**
- As a couple, I want to see which forms my planner has shared with me so that I can complete them on time.
- As a couple, I want to fill out forms with various field types (text, select, date, checkbox, etc.) so that I can provide the data my planner needs.
- As a couple, I want to see if I've already submitted a form so that I don't duplicate my responses.

**Order of Events & Collaborative Notes:**
- As a couple, I want to view the detailed order of events for each ceremony (e.g., Grand Entrance → First Dance → Cake Cutting) so that I know the run of show.
- As a couple, I want to leave notes on specific program items (e.g., "Can we use Ed Sheeran for the first dance?") so that my planner gets structured feedback.
- As a couple, I want to leave general notes on an event (e.g., "Keep the reception under 3 hours") so that my planner knows our preferences.
- As a couple, I want to see the status of my notes (pending, seen, addressed) so that I know my planner has acknowledged my feedback.

**Updates & Communication:**
- As a couple, I want to see a feed of updates from my planner so that I stay informed about wedding progress.
- As a couple, I want milestone cards for key achievements (venue booked, caterer confirmed, etc.) so that progress feels tangible.
- As a couple, I want to send messages to my planner within the portal so that I don't need to switch to email or WhatsApp.

**Scheduling:**
- As a couple, I want to schedule recurring check-in meetings with my planner so that we stay aligned throughout the planning process.
- As a couple, I want meeting reminders so that I don't miss our planning sessions.

**Archival:**
- As a couple, I want to access my wedding data even after the wedding is complete so that I can look back at the details.

### Planner Stories (Priority Order)

- As a planner, I want to invite a couple to their portal by entering their email so that they can set up their account.
- As a planner, I want to resend an invitation if the couple didn't receive or lost the first one.
- As a planner, I want to see a list of all my couples and their portal status (invited, active, archived) so that I can manage access.
- As a planner, I want to create an order of events for each ceremony with titles, times, and descriptions so that the couple can review the program.
- As a planner, I want to see notes the couple has left on program items so that I can incorporate their feedback.
- As a planner, I want to mark couple notes as "seen" or "addressed" so that the couple knows I've acknowledged their input.
- As a planner, I want to post updates to the couple's portal (with optional milestone card styling) so that couples stay informed without me emailing them.
- As a planner, I want to share specific forms with a couple so that I can collect structured data from them.
- As a planner, I want to be notified when a couple submits a form or leaves a note so that I can act on it promptly.
- As a planner, I want to archive a completed wedding so that the data is preserved for analytics but no longer clutters my active workspace.
- As a planner, I want to revoke a couple's portal access if needed so that I maintain control over who can see wedding data.

---

## 5. Requirements

### Must-Have (P0) — Portal cannot ship without these

| # | Requirement | Acceptance Criteria | Status |
|---|------------|---------------------|--------|
| P0-1 | **Magic link invite + password setup** | Planner enters couple email → couple receives email with link → couple sets password → account activates → couple can log in | Built |
| P0-2 | **Couple login with JWT** | Couple logs in with email/password → receives 24-hour JWT → dashboard loads with wedding data scoped to their wedding | Built |
| P0-3 | **Dashboard overview tab** | Shows wedding countdown, venue, planner contact, guest stat cards (totals only), budget summary bar | Built |
| P0-4 | **Timeline tab** | Shows all events with date, time, venue, location, attire | Built |
| P0-5 | **Payments tab** | Shows package name, payment schedule with statuses, amount paid/remaining | Built |
| P0-6 | **Forms tab + form filling** | Shows shared forms with pending/submitted status; couple can fill out and submit forms; planner receives notification | Built |
| P0-7 | **Updates tab** | Shows planner updates feed with pagination; milestone cards render with distinct styling | Built |
| P0-8 | **Planner: invite, resend, list couples** | Planner can invite couple, resend invite, see all couples with status | Built |
| P0-9 | **Planner: post updates** | Planner can create text updates and milestone cards visible to couple | Built |
| P0-10 | **Order of events model** | EventModel supports `order_of_events` (list of program steps) and `event_notes` (collaborative notes) — backward compatible with existing events | Built |
| P0-11 | **Planner management page** | `/admin/couple-portal/` page where planners manage invitations, post updates, view couple activity | Not started |
| P0-12 | **Order of events — planner CRUD** | Planner can add, edit, reorder, delete program steps within each event | Not started |
| P0-13 | **Order of events — couple view + notes** | Couple can view the program and leave notes on individual items or the event overall; notes show status | Not started |
| P0-14 | **Contract review in couple portal** | Couple can view contract details and status from the portal (read from existing contracts collection) | Not started |

### Nice-to-Have (P1) — Ship soon after core launch

| # | Requirement | Notes |
|---|------------|-------|
| P1-1 | **Inbound messaging** | Couple↔planner messaging within the portal. Near-real-time delivery, message history, notifications both ways |
| P1-2 | **Recurring meeting scheduling** | Couple and planner can schedule recurring check-ins, synced with planner's Google Calendar |
| P1-3 | **Planner notification center** | Consolidated view of couple activity — form submissions, new notes, messages — in the planner dashboard |
| P1-4 | **Couple password reset** | "Forgot password" flow for couple accounts |
| P1-5 | **Form templates** | Planners can save forms as reusable templates for common data collection |
| P1-6 | **Note replies** | Planner can reply to a couple's note inline, creating a threaded conversation on each program item |

### Future Considerations (P2) — Design for but don't build now

| # | Requirement | Architectural Consideration |
|---|------------|----------------------------|
| P2-1 | **Real-time messaging via WebSocket** | Service layer should support pluggable transport (polling → SSE → WebSocket) |
| P2-2 | **Registry display** | Wedding model already has `registries` array; just needs a couple dashboard widget |
| P2-3 | **FAQ display** | Wedding model already has `faqs` array; same as above |
| P2-4 | **Document sharing** | Consider R2 storage integration for planner-uploaded PDFs/images viewable by couple |
| P2-5 | **QR code for portal access** | Generate QR from couple portal URL for in-person sharing |
| P2-6 | **Push notifications** | Browser push for new updates/messages/form assignments |
| P2-7 | **PWA / mobile optimization** | Service worker, manifest, offline-first dashboard |
| P2-8 | **Multi-couple login** | Separate logins for each partner (requires auth model change) |
| P2-9 | **Wedding archival analytics dashboard** | Post-wedding insights: total spend, vendor ratings, timeline adherence |

---

## 6. Success Metrics

### Leading Indicators (Days–Weeks)

| Metric | Target | Stretch | Measurement |
|--------|--------|---------|-------------|
| Couple invite → account activation rate | 70% within 48 hours | 85% | `couple_users` where `status=active` / total invites sent |
| Weekly active couples | 60% of activated couples | 80% | Couple JWTs issued per week / total active couples |
| Form completion rate | 80% of shared forms submitted | 95% | `form_submissions` count / forms with `shared_with_couple=true` |
| Order of events note usage | 40% of couples leave ≥1 note | 60% | Couples with notes / total active couples |
| Planner update frequency | 2+ updates per wedding per week | 4+ | `couple_updates` count per wedding per week |

### Lagging Indicators (Weeks–Months)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Planner status-communication time reduction | 60% decrease | Self-reported planner survey (pre/post) |
| Couple satisfaction with portal | 4.5/5 rating | In-portal feedback widget |
| Planner retention (churn reduction) | 15% improvement | Monthly churn rate comparison |
| Ad-hoc couple inquiries (email/WhatsApp) | 50% reduction | Planner self-report |

**Evaluation cadence:** Leading indicators reviewed weekly for the first month post-launch; lagging indicators evaluated at 1 month and 3 months.

---

## 7. Open Questions

| # | Question | Owner | Blocking? |
|---|----------|-------|-----------|
| Q1 | Should couples be able to make payments directly from the couple portal, or continue using the existing `/portal/[token]` payment flow? | Product/Eng | Non-blocking (current approach: view-only payment schedule, pay via existing portal) |
| Q2 | Should the messaging feature use SSE (existing infrastructure), WebSocket, or a third-party service (e.g., Twilio Conversations)? | Eng | Non-blocking (P1 feature) |
| Q3 | Should couple portal access be revocable per-section (e.g., hide budget but show timeline), or is wedding-level on/off sufficient for v1? | Product | Non-blocking (start with on/off, design data model for per-section later) |
| Q4 | How should the meeting scheduling integrate with the couple's calendar (not just the planner's)? Google Calendar invite? iCal download? | Product/Eng | Non-blocking (P1 feature) |
| Q5 | Should archived weddings remain accessible to couples indefinitely, or should there be a retention period? | Product/Legal | Non-blocking (default: indefinite, revisit based on storage costs) |
| Q6 | Should the planner be able to assign forms to specific events (e.g., "Reception song requests" tied to the reception event)? | Product | Non-blocking (nice-to-have, would connect forms to order_of_events) |

---

## 8. Roadmap & Phasing

### Sprint 1 — Foundation (DONE)
*Auth, data layer, core dashboard*

- [x] Couple auth: magic link invite, password setup, login, JWT
- [x] Couple portal service layer (data aggregation from weddings, guests, budgets, contracts, forms)
- [x] Dashboard with 5 tabs: Overview, Timeline, Payments, Forms, Updates
- [x] Form filling page with field type support
- [x] Planner invite/resend/list API
- [x] Planner update creation API
- [x] Sidebar nav entry for "Couple Portal"
- [x] Visual mockups (8 screens)
- [x] Feature spec document
- [x] EventModel extension: `order_of_events` + `event_notes` (backward-compatible)

### Sprint 2 — Planner Management + Order of Events
*Planner-side UI, program management, collaborative notes*

- [ ] **Planner management page** (`/admin/couple-portal/page.tsx`): invite couples, view couple status, post updates, view activity feed
- [ ] **Order of events CRUD** (planner side): add/edit/reorder/delete program steps per event, assign times and descriptions
- [ ] **Order of events view** (couple side): render program in Timeline tab, expandable per-event
- [ ] **Collaborative notes UI** (couple side): add notes to program items or events, see status badges
- [ ] **Note management** (planner side): view couple notes inline, mark as seen/addressed, optional replies
- [ ] **Contract review** in couple dashboard: surface contract details and status from existing contracts collection
- [ ] **API endpoints**: order-of-events CRUD, note creation, note status updates

### Sprint 3 — Communication + Scheduling
*Messaging, meetings, notifications*

- [ ] **Inbound messaging**: couple↔planner messaging with history and notifications
- [ ] **Recurring meeting scheduling**: schedule check-ins, sync with planner calendar, reminders for both parties
- [ ] **Planner notification center**: consolidated feed of couple actions (form submissions, notes, messages)
- [ ] **Couple password reset**: forgot-password flow for couple accounts
- [ ] **Email notifications**: digest emails for unread updates, upcoming payments, pending forms

### Sprint 4 — Polish, Archival & Testing
*End-to-end flows, archival, edge cases*

- [ ] **Wedding archival flow**: planner triggers archive → data snapshot → couple sees archived view
- [ ] **Form templates**: planners save/reuse common form templates
- [ ] **Error states**: expired tokens, revoked access, archived wedding messaging
- [ ] **Mobile responsiveness**: test and polish all couple portal pages on mobile viewports
- [ ] **End-to-end testing**: full flow from planner invite → couple setup → dashboard → forms → notes → messaging
- [ ] **Performance**: lazy-load tabs, paginate updates/messages, optimize dashboard API response

### Sprint 5 — Future Enhancements (P2)
*Only if capacity allows or demand is clear*

- [ ] Registry and FAQ display widgets
- [ ] Document sharing (R2-backed)
- [ ] QR code generation for portal access
- [ ] Push notifications
- [ ] PWA / offline support

---

## 9. Technical Architecture Summary

### New Collections
| Collection | Purpose |
|------------|---------|
| `couple_users` | Couple accounts (email, password_hash, wedding_id, invite_token, status) |
| `couple_updates` | Planner-to-couple update feed |
| `archived_weddings` | Complete wedding data snapshots for post-wedding access |
| `couple_messages` (Sprint 3) | Couple↔planner message history |

### API Surface
| File | Auth | Purpose |
|------|------|---------|
| `couple_auth.py` | Public | Login, setup, verify, profile |
| `couple_invite.py` | Planner JWT | Invite, resend, list couples |
| `couple_portal.py` | Couple JWT | Dashboard, events, forms, updates, notes |

### Key Design Decisions
- **Separate `couple_users` collection** — couples are not planners, vendors, or team members. Clean role separation avoids auth complexity.
- **24-hour JWT** — couples check infrequently; longer sessions reduce login friction without significant security risk.
- **Privacy by aggregation** — couples see totals (guest counts, budget amounts), never individual records.
- **Order of events on EventModel** — kept on the existing model (not a separate collection) because it's tightly coupled to ceremonies and benefits from the same CRUD lifecycle.
- **Notes as embedded arrays** — notes live on `OrderOfEventsItemModel.notes` and `EventModel.event_notes` rather than a separate collection, since they're always read with their parent and the volume is low (dozens, not thousands).

---

## 10. Dependencies

| Dependency | Status | Impact if Delayed |
|------------|--------|-------------------|
| Packages/contracts system | Built | Cannot show payment schedule or contract status |
| Forms system | Built | Cannot share or submit forms |
| Email service (Resend) | Built | Cannot send magic link invitations |
| Stripe integration | Built | Cannot show payment statuses |
| Planner calendar (Google Calendar) | Built | Sprint 3 meeting scheduling blocked |
| Inbound email / messaging infra | Partially built | Sprint 3 messaging may need new infra |

---

## 11. Testing Plan

**Test Accounts:**
- Planner: `test_planner_package@thespecialwedding.io` / `testPlannerPackage123!`
- Couple: `test_couple1@thespecialwedding.io` / `testCouplePass123!`

**Test Flow (End-to-End):**
1. Planner logs in → creates a package → assigns to a wedding
2. Planner goes to Couple Portal → invites couple by email
3. Couple receives magic link → sets password → logs in
4. Couple views dashboard: overview stats, timeline, payments, forms
5. Planner creates order of events for a ceremony
6. Couple views program → leaves notes on items
7. Planner sees notes → marks as addressed
8. Planner shares a form → couple fills it out → planner gets notification
9. Planner posts update with milestone card → couple sees it in Updates tab
10. (Sprint 3) Couple sends message → planner receives and replies
11. (Sprint 4) Planner archives wedding → couple sees archived dashboard
