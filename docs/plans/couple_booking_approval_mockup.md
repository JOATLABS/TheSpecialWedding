# Couple-Booking Approval Flow — Mockup (no code yet)

**Status:** Design proposal. Awaiting Etastic's approval before any
implementation. Per the project rule, this is a mockup-first artifact.

**Scope:** The "C" decision (build the full couple-booking flow + the
external-edit accept/reject pair). Closes the 10 failing tests in
`tests/backend/test_couple_booking_approval_flow.py` and the
`verify_couple_booking_lifecycle.py` testbed driver.

**Not in scope of this mockup:**
- Frontend file rename `GoogleCalendarConnect.tsx` → `CalendarConnect.tsx`
  (unrelated cleanup).

**Decisions locked (no longer open):**
- **Scheduler approach:** hybrid — call Aurinko's
  ``GET /v1/book/account/profiles/{profile}/availability`` for open
  windows, but route the couple's pick through our approval service
  (Aurinko does not natively support approval-before-confirm). Book on
  Aurinko via ``POST /v1/book/account/profiles/{profile}`` only after
  the planner approves (or immediately if
  ``couple_booking_auto_confirm`` is true on the connection).
- **`couple_booking_auto_confirm` default:** TRUE per test contract.
  Semantics: auto-confirm when the couple picks from planner-vetted
  slots; require approval for couple-proposed times.
- **Conference link:** calendar-only by default. Optional per-connection
  default (`conference_provider_default`) + per-meeting override.
  Aurinko app has Zoom, Webex, MS Teams Bot enabled under Messaging;
  triggered via Aurinko booking with ``startConference=true``.
- **Couple submits the request from the couple portal** (authenticated).
- **Email notifications:** in-app for planner via
  ``MEETING_BOOKING_REQUEST`` + email to planner on new request; email
  to couple on approve/decline.
- **URL convention:** keep code's `/admin/planner/calendar/connections/provider/*`
  paths. Aurinko prod URLs will be updated to match
  (`/admin/planner/calendar/connections/provider/callback`); the
  localhost:3000 frontend URL already matches.

---

## 1. Design contract recovered from the test file

`tests/backend/test_couple_booking_approval_flow.py` is the authoritative
spec. From it:

### Enums

```
MeetingLifecycleStatus
├── PENDING_APPROVAL  ← new, comes before SCHEDULED in enum order
├── SCHEDULED         (existing)
├── RESCHEDULED       (existing)
├── CANCELLED         (existing)
└── COMPLETED         (existing)

PlannerNotificationTypes
└── MEETING_BOOKING_REQUEST = "meeting_booking_request"  ← new
```

### Model fields

```
CalendarConnectionModel
└── couple_booking_auto_confirm: bool = True   ← NEW, per-calendar toggle

TeamPermissions  (and ROLE_PRESETS)
├── couple_bookable: bool          ← NEW. Can this team-member's calendar
│                                     receive couple-initiated bookings?
└── approve_couple_bookings: bool  ← NEW. Can this team-member approve
                                      bookings on the owner's calendars?
```

Defaults across the three role presets (per test contract):

| role   | couple_bookable | approve_couple_bookings |
|--------|-----------------|--------------------------|
| admin  | ✓               | ✓                        |
| editor | ✓               | ✓                        |
| viewer | ✗               | ✗                        |

### Endpoints (each requires `expected_version: int` query param for
optimistic concurrency)

```
POST /admin/planner/calendar/meetings/{task_id}/accept-external-change
POST /admin/planner/calendar/meetings/{task_id}/reject-external-change
POST /admin/planner/calendar/meetings/{task_id}/approve-booking
POST /admin/planner/calendar/meetings/{task_id}/decline-booking
```

The first two close **task #21** (the "modified externally" badge consumer
for Aurinko webhook writes). The second two are the **couple-booking
approval pair**. Different state machines; shared concurrency primitive.

### Service-layer regression pin (Q19)

`calendar_provider_service.update_connection` must include
`couple_booking_auto_confirm` in its allow-list — otherwise the planner UI
toggle reaches Pydantic but never reaches Mongo.

---

## 2. Two flows, kept separate

The test file conflates them under "approval flow" but they're orthogonal:

### Flow A — Couple-booking approval (NEW feature)

```
Couple                               Planner
─────────────────────                ──────────────────────
1. Opens "Request meeting"
   in couple portal
2. Submits {topic, duration,
   preferred_window}
                                     3. Receives in-app
                                        MEETING_BOOKING_REQUEST notif

    ┌── two branches ──┐
    │                  │
4a. Planner picks       4b. Couple was offered planner-
    3-5 slots from         curated slots already (re-book
    free windows           use case); picks one
                           → if couple_booking_auto_confirm
                             on that connection → SCHEDULED
                           → else → PENDING_APPROVAL
5. Couple picks one
   slot
6. Meeting created as
   PENDING_APPROVAL
7. Planner notif: "Booking
   ready for your approval"
                                     8. Reviews in /admin/planner/
                                        calendar?tab=requests
                                     9. Clicks Approve or Decline
                                        (with expected_version)
                                    10. Approve → SCHEDULED + Aurinko
                                        event created + ICS to couple
                                        Decline → CANCELLED + reason
                                        delivered to couple portal
```

**Key invariant the user emphasized:** Couple NEVER sees the planner's raw
calendar. Couple only sees what the planner has explicitly offered, OR
a planner-published "scheduler page" with pre-vetted rules.

### Flow B — External-edit accept/reject (closes task #21)

```
Aurinko webhook delivers              Planner
"event was modified externally"       ─────────────
─────────────────────
1. Webhook handler writes
   external_conflict_status =
   PENDING_REVIEW + external_*
   fields on the planner_task
                                       2. UI surfaces "modified
                                          externally" badge on the
                                          meeting card
                                       3. Planner expands tray →
                                          sees canonical vs external
                                          side-by-side diff
                                       4. Clicks Accept (adopt
                                          external as canonical) or
                                          Reject (overwrite Aurinko
                                          with canonical)
                                       5. expected_version pins
                                          optimistic concurrency
```

Same `expected_version` pattern; different state machine
(`external_conflict_status: none → pending_review → resolved`).

---

## 2.5 Visual language (per-surface palette + components)

The mockup spans two distinct portals, each with its own canonical design
language. Cross-pollinating tokens between the two is exactly the regression
`docs/frontend/COUPLE_PORTAL_VISUAL_AUDIT.md` flagged (P0/P1: hardcoded
slate-tokens and `font-serif` in couple surfaces instead of `wedding-*`
tokens and `font-heading`). This section pins the convention for the new
surfaces below so we don't repeat that mistake when implementing.

**Couple-facing surfaces (S1, S2):**
- Palette: `text-wedding-navy` for primary text and headings,
  `text-wedding-navy/70` for subtitles/body, `wedding-rose` for accent +
  focus rings, `wedding-sage` for soft secondary backgrounds, `wedding-gold`
  as hover/CTA-accent, `wedding-ivory` / `wedding-blush` for surface tints.
  Canonical hex stops live in `public/BRAND_ASSETS.md`.
- Typography: Playfair Display (`font-heading`) for the screen H1/H2;
  Cormorant Garamond (`font-elegant`, via `CardTitle`) for decorative card
  titles; Inter (`font-sans`) for body and form labels.
- Components: `PageHeader` for the screen title (slate tokens are baked
  into `PageHeader`'s body — the audit allows this since it's a shared
  cross-portal primitive); `GlassCard` (`depth="near"` or `"mid"`, `blur="xl"`)
  for the form/picker shell when the surface is auth-adjacent or single-task;
  `Card` (`bg-white rounded-2xl shadow-lg border border-slate-200`) for the
  in-dashboard, in-flow variant; `Button` `variant="primary"` for the
  affirmative CTA (`bg-wedding-rose hover:bg-wedding-gold`), `variant="secondary"`
  for the "request different times" / cancel action (`bg-white/70` +
  `text-wedding-navy` + rose hover); inputs follow the couple-login pattern —
  `rounded-xl border border-white/40 bg-white/60 px-4 py-3 text-wedding-navy
  shadow-inner focus:ring-2 focus:ring-wedding-rose/50`.

**Planner-facing surfaces (S3, S4, S5, S6):**
- Palette: slate-900/slate-700/slate-500 for text and borders, primary-*
  accents from the admin theme (`bg-primary-50`, `text-primary-600`),
  `bg-white dark:bg-slate-800` panels, amber for "needs review" badges.
- Typography: `font-heading` (Playfair Display) only on `PageHeader`;
  everything else is Inter (`font-sans`).
- Components: the admin `PageHeader`, admin tab strip, the same `Card`
  primitive but as it's rendered in `/admin/planner/calendar` today
  (`rounded-xl shadow-sm border border-slate-200`), and shadcn-style admin
  modals for the slot proposer.

**Shared cross-portal primitives** (no palette swap needed): `PageHeader`,
`Card`, `Button`, `GlassCard`, optimistic-concurrency error toast.

---

## 3. Surfaces (screen-by-screen)

### S1 — Couple portal: "Request a meeting"

*Palette:* `wedding-navy` text, `wedding-rose` accents/focus, `wedding-sage`
soft surface, `wedding-ivory`/`wedding-blush` shell tints.
*Typography:* Playfair Display H1 (`font-heading`), Cormorant Garamond
(`font-elegant`) decorative subtitle, Inter form labels and body.
*Components:* `PageHeader` (title) → `GlassCard depth="near" blur="xl"`
(shell) → labelled inputs styled like couple-login (`rounded-xl border
border-white/40 bg-white/60 ... focus:ring-wedding-rose/50`) → `Button
variant="secondary"` for chip-style duration toggles → `Button variant="primary"`
("Send request").

```
┌───────────────────────────────────────────────────┐
│  Request a meeting                                │  ← Playfair Display
│  with [Planner Name]                              │     wedding-navy, H1
├───────────────────────────────────────────────────┤
│  Topic *                                          │  ← Inter label,
│  ┌─────────────────────────────────────────────┐  │     wedding-navy
│  │ e.g. Final venue walkthrough               │  │  ← bg-white/60,
│  └─────────────────────────────────────────────┘  │     focus ring rose
│  Duration                                         │
│  [ 30 min ] [ 45 min ] [ 60 min ] [ 90 min ]     │  ← Button secondary;
│                                                   │     selected = filled
│  Preferred dates                                  │     wedding-rose
│  [ Next 7 days ] [ Next 14 days ] [ Specific ]   │
│  Notes for your planner                           │
│  ┌─────────────────────────────────────────────┐  │
│  │                                             │  │
│  └─────────────────────────────────────────────┘  │
│                       [ Send request ]            │  ← Button primary
│                                                   │     bg-wedding-rose
└───────────────────────────────────────────────────┘     hover wedding-gold
```

The shell sits inside the existing couple-dashboard mesh-gradient
background; the two rose/sage halo blurs (see couple-login lines 139-147)
carry over for visual continuity.

### S2 — Couple portal: "Pick a slot"

*Palette / typography / components:* same convention as S1. Each slot is a
`Button variant="secondary"` (unselected) → `variant="primary"`
(selected) so the wedding-rose fill confirms the choice without a separate
checkbox. The "request different times" affordance is `variant="secondary"`
so it sits visually subordinate to "Book this".

After planner sends slots:
```
┌───────────────────────────────────────────────────┐
│  Pick a time                                      │  ← Playfair Display H1
│  [Planner Name] proposed these for                │  ← Cormorant Garamond
│  "Final venue walkthrough" • 60 min               │     wedding-navy/70
├───────────────────────────────────────────────────┤
│  ○ Tue Jun 3, 2:00 PM – 3:00 PM EDT              │  ← slot buttons:
│  ● Wed Jun 4, 10:00 AM – 11:00 AM EDT  selected  │     unselected =
│  ○ Fri Jun 6, 4:30 PM – 5:30 PM EDT              │       secondary
│                                                   │     selected =
│  Conference: ⓘ Zoom link will be added            │       wedding-rose fill
│              automatically                        │  ← inline note,
│                                                   │     wedding-navy/70
│  [ None work — request different times ]          │  ← Button secondary
│                                  [ Book this ]    │  ← Button primary
└───────────────────────────────────────────────────┘
```

NOTE on the existing `app/couple/dashboard/components/SlotPicker.tsx`:
it currently uses slate-* tokens (the exact pattern the visual audit
flagged). Implementing S2 is an opportunity to bring that component onto
the wedding-* palette in the same commit — and the audit's P1 item
"couple portal slate-token regression" gets closed alongside this
feature rather than tracked as separate debt.

### S3 — Planner: Booking-requests inbox (NEW tab on /admin/planner/calendar)
```
┌────────────────────────────────────────────────────────────┐
│  Calendar   Tasks   Meetings   Requests (2)  Connections   │
├────────────────────────────────────────────────────────────┤
│  ▸ Sarah & David — Final venue walkthrough        2h ago   │
│    Requested: Next 7 days, 60 min                          │
│    [ Propose slots ]  [ Decline request ]                  │
│                                                            │
│  ▾ Lisa & Mike — Vendor sync                      Yesterday│
│    Couple picked: Wed Jun 4 10:00 AM – 11:00 AM (Editor    │
│    Calendar) PENDING YOUR APPROVAL                         │
│    Notes: "Caterer wants to walk through menu"             │
│    [ Approve & send invite ]  [ Decline ]                  │
└────────────────────────────────────────────────────────────┘
```

### S4 — Planner: Slot-proposer modal
When planner clicks "Propose slots" on a request:
```
┌───────────────────────────────────────────────────┐
│  Propose slots to Sarah & David                   │
├───────────────────────────────────────────────────┤
│  60 min on:                                       │
│  [Tue Jun 3 ▾]                                    │
│   ☑ 2:00–3:00 PM   (1 conflict — minor)          │
│   ☑ 4:00–5:00 PM   ✓ clear                       │
│   ☐ 6:00–7:00 PM   (outside business hours)      │
│  [Wed Jun 4 ▾]                                    │
│   ☑ 10:00–11:00 AM ✓ clear                       │
│   ☐ 1:00–2:00 PM   (1 conflict — Vendor sync)    │
│   ☑ 3:00–4:00 PM   ✓ clear                       │
│                                                   │
│  Couple sees: 4 slots selected                    │
│  ☐ Auto-confirm when couple picks one             │
│                       [ Cancel ] [ Send slots ]   │
└───────────────────────────────────────────────────┘
```

Free/busy comes from `client.list_events()` against the selected
connection's calendar. Slot suggestion: planner-side, NOT exposed to the
couple.

### S5 — Planner: External-edit accept/reject tray (Flow B)
Click a meeting card with the "modified externally" badge:
```
┌────────────────────────────────────────────────────────────┐
│  ⚠ Modified externally — needs review                       │
├────────────────────────────────────────────────────────────┤
│  Canonical (you)             │  Aurinko delivered          │
│  Final venue walkthrough     │  Final venue walkthrough    │
│  Tue Jun 3, 2:00 – 3:00 PM   │  Tue Jun 3, 3:00 – 4:00 PM  │
│  Calendly Studios            │  Calendly Studios           │
│  Notes: vendor walkthrough   │  Notes: vendor walkthrough  │
│                              │  ← someone moved this 1h    │
│                              │                             │
│  [ Reject — restore mine ]   │  [ Accept — adopt theirs ]  │
└────────────────────────────────────────────────────────────┘
```

### S6 — Connection settings (existing panel + new section)
On the existing `CalendarConnect` component's per-row settings:
```
┌─ Primary calendar — owner@example.com ────────────────────┐
│  ... existing fields (visibility, sync_enabled,           │
│      sync_targeting_mode, scheduler_access_mode, etc.) ...│
│                                                           │
│  ▸ Couple booking                                         │
│    ☑ Allow couples to request bookings on this calendar   │
│    ☑ Auto-confirm when I've already vetted the slots      │
│      (i.e. couple is picking from MY proposed times)      │
│    ☐ Auto-confirm couple-proposed times that fit free     │
│      windows (skip my approval — NOT recommended for      │
│      owners; useful for staff who screen all bookings)    │
│    Default duration: [ 60 min ▾ ]                        │
│    Buffer before/after: [ 15 min ▾ ]                     │
│    Allowed days: [ M T W T F ☐ S ☐ S ]                   │
└───────────────────────────────────────────────────────────┘
```

---

## 4. State machine

```
                ┌──────────────────────────┐
                │  Couple submits request  │
                └────────────┬─────────────┘
                             ↓
                     ┌──────────────┐
        ┌─ planner ──│  REQUESTED   │
        │  proposes  └──────┬───────┘
        │  slots            │ planner declines
        │                   └──→ CANCELLED (with reason)
        ↓
┌─────────────────┐
│ SLOTS_PROPOSED  │  ← couple sees offered slots
└────────┬────────┘
         │ couple picks
         ↓
   ┌─────────────────────┐
   │ couple_booking_auto │
   │     _confirm        │
   │       ?             │
   └──┬──────────────┬───┘
      │ TRUE         │ FALSE
      ↓              ↓
 ┌──────────┐  ┌──────────────────┐
 │SCHEDULED │  │ PENDING_APPROVAL │
 └──────────┘  └────────┬─────────┘
                        │  planner approves   ┌──────────┐
                        ├────────────────────→│SCHEDULED │
                        │                     └──────────┘
                        │  planner declines   ┌──────────┐
                        └────────────────────→│CANCELLED │
                                              └──────────┘
```

Optimistic concurrency: every state transition takes `expected_version` and
bumps `planner_task.version` on success. Stale UI clicks 409.

---

## 5. Open design questions (need your call before code)

1. **Aurinko Scheduler product:** We can't reach the booking docs page
   right now. Two options:
   - **(a)** Build on top of free/busy + Aurinko event CRUD (what we
     already have working). Slot generation is server-side; the planner
     curates. **Pro:** full control, fits the "no auto-expose calendar"
     constraint. **Con:** more code.
   - **(b)** Use Aurinko's hosted scheduler page. **Pro:** less code.
     **Con:** less control over the approval flow; Aurinko's product may
     not support the "planner approves first" requirement.
   - **My recommendation: (a)** — matches the privacy concern you raised.

2. **Default for `couple_booking_auto_confirm`:** Test pins TRUE; you
   said "don't want couples to auto-book without approval." Resolution:
   the TRUE default is for the slot-offer path (planner already vetted
   the slots, so the couple's pick is implicitly approved by the planner).
   For raw couple-proposed times we'd require approval regardless. Confirm
   this interpretation matches your intent.

3. **Conference link:** Zoom auto-creation, manual URL paste, or "calendar
   item only"? `PlannerTaskModel` already has `conference_provider` +
   `conference_url`. I'd default to manual paste in v1; Zoom OAuth is
   another integration. Confirm.

4. **Where does the couple submit the initial request?** Couple portal
   has existing "meetings" surface. New "Request a meeting" CTA there. OR
   make it a planner-published booking link (e.g.
   `thespecialwedding.io/book/<planner-slug>`)? The portal version is
   safer (couple is already authenticated, no public-link spam).

5. **Notifications:** In-app via `PlannerNotificationTypes.MEETING_BOOKING_REQUEST`
   is pinned. Do we also send email to the planner? Email to the couple
   when the planner approves/declines?

---

## 6. Plan (after you approve the mockup)

1. **Models + enums** — extend `MeetingLifecycleStatus`, add
   `couple_booking_auto_confirm` field, `MEETING_BOOKING_REQUEST` notif
   type, role-preset keys, `TeamPermissions` model.
2. **Service layer** — add `couple_booking_auto_confirm` to
   `update_connection` allow-list (Q19). Add `create_booking_request`,
   `propose_slots`, `accept_booking_slot`, `approve_meeting`,
   `decline_meeting` to a new `couple_booking_service.py`.
3. **API routes** — the four endpoints + slot-proposal + couple-side
   submit/pick. All with `expected_version` where state mutates.
4. **Aggregation surface** — `_normalize_internal` already surfaces
   `external_*` (done this round). Add `meeting_status` rendering for
   PENDING_APPROVAL.
5. **Frontend** —
   - Couple portal: "Request a meeting" CTA + slot picker
   - Planner inbox: "Requests" tab + slot proposer modal + accept/reject
     external-edit tray + connection settings extension
6. **Tests** — the 10 failing tests pass. Add a testbed
   `verify_couple_booking_lifecycle.py` end-to-end run (exists in skeleton).
7. **Chrome verification with you watching** — the load-bearing one.

---

## 7. What I need from you before coding

- Sign-off (or edits) on the mockup above
- Answers to the 5 open questions in section 5
- Confirmation that Flow B (external-edit accept/reject) ships in the
  same PR as Flow A, or splits to a separate PR

Once those land, I'll go in the order above. Estimated diff: ~6 files
backend, ~4 files frontend, ~15 new tests.
