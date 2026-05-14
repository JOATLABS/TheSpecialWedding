# Planner Calendar Redesign — Mockup (no code yet)

**Status:** Design proposal. Awaiting Etastic's approval before any
implementation. Per the project rule, this is a mockup-first artifact.

**Companion file:** `planner_calendar_redesign_preview.html` (open in
a browser to see brand-aligned visual treatment of all three views).

**Scope:** Restructure `/admin/planner/calendar` so the calendar grid
itself is the focal point, condense the metric strip, move calendar
connections to a dedicated settings page, and add a post-OAuth
calendar-picker modal so we stop auto-creating connection rows for
every iCal feed Google syncs into the user's account.

---

## Decisions locked (from the question round on 2026-05-13)

- **Connections live on a separate page** at
  `/admin/planner/settings/calendars`. Main calendar page shows only a
  compact status pill linking to it. Pattern from Cal.com / Reclaim.ai.
- **Day click opens a right-side slide-over panel** showing that day's
  tasks, meetings, and external events grouped, with quick-create
  buttons. Pattern from Notion Calendar / Google Calendar mini-view.
- **Post-OAuth calendar picker modal** appears the first time after a
  successful callback. The planner checks which calendars to actually
  sync; we only create `calendar_connections` rows + Aurinko
  subscriptions for the checked ones.

---

## Problem statement

Today's `/admin/planner/calendar` page (verified in the 2026-05-13
Chrome session):

1. **Top metric row.** Four large cards spanning full width
   (`INTERNAL MEETINGS / SHARED CALENDARS / BUSY/FREE IMPORTS /
   VISIBLE ITEMS`) showing single-digit numbers. ~140 px of vertical
   space for low-density information.
2. **Calendar Connections card.** Big card with provider connect
   buttons + one row per detected calendar. With one Google account
   linked, this surfaces every iCal feed Google syncs in (Cushion,
   Family, holidays, etc.) — pushes the actual calendar grid below
   the fold.
3. **Calendar grid.** The thing the planner came to look at. Lives
   below ~900 px of chrome on a 1440×900 viewport.
4. **Right rail.** Upcoming, Availability, Legend. Useful but
   currently invisible until the user scrolls.

User feedback verbatim: *"the page is too long; the card metric at
the top could be reduced; the calendar can be redesigned to show
task on the side as the days are clicked on."*

---

## Information architecture after redesign

| Surface | Where | Contents |
|---|---|---|
| Main calendar | `/admin/planner/calendar` | Grid (focal), filter bar, status pill, compact metric strip, optional slide-over for selected day |
| Connections | `/admin/planner/settings/calendars` (NEW route) | Provider buttons, connection list, per-calendar Settings modal, health/disconnect |
| Calendar picker | Modal triggered post-OAuth | Choose which Google calendars to sync, set primary/default-write, before connection rows are created |

---

## View 1 — Redesigned Calendar Page

### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Sidebar (existing, ~240 px)                                              │
│                                                                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Header row                                                          │ │
│ │   Shared Planner Calendar                            [+ New event] │ │
│ │   Business + external meetings, each visibility-tied              │ │
│ │                                          [● Google · 1 active →]  │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Compact metric strip (single row, ~36 px tall)                     │ │
│ │ • 0 internal meetings  • 0 shared  • 0 imports  • 173 visible items│ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Filter bar                                                          │ │
│ │ [All weddings ▾][All staff ▾][All sources ▾][All visibility ▾]    │ │
│ │ [Today] [‹] May 2026 [›]                       [Calendar | Agenda] │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌─────────────────────────────────────────┬──────────────────────────┐ │
│ │ Calendar grid (Sun–Sat, ~5 rows)        │ Side rail (collapsed     │ │
│ │                                          │ unless day selected)     │ │
│ │  S  M  T  W  T  F  S                    │                          │ │
│ │  •  •  •  •  •  1  2                    │ • Upcoming               │ │
│ │  3  4  5  6  7  8  9                    │ • Availability           │ │
│ │ 10 11 12 [13] 14 15 16                   │ • Legend                 │ │
│ │ 17 18 19 20 21 22 23                    │                          │ │
│ │ 24 25 26 27 28 29 30                    │                          │ │
│ └─────────────────────────────────────────┴──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Status pill (replaces the whole Calendar Connections card)

Single-line pill in the page header, e.g.:

```
● Google · 1 active · Webhooks OK     Manage →
```

States:
- `Google · 1 active · Webhooks OK` (green dot) — happy path
- `Google · 1 active · Webhook failed for 3 calendars` (amber dot)
  with a `Resync` action inline
- `No calendar connected` (slate dot) with `+ Connect a calendar`
  action inline

Clicking `Manage` routes to `/admin/planner/settings/calendars`.

### Compact metric strip

One horizontal row of pills replacing the 4-card grid:

```
0 internal meetings  ·  0 shared  ·  0 imports  ·  173 visible items
```

Same data, ~25% of the vertical real estate. If a metric is non-zero
it gets emphasis (brand-navy text, gold dot prefix); zeros use muted
slate.

### Day-click slide-over

Right-side panel slides in (width: ~360 px on desktop, full-bleed on
mobile, see Responsive section below). Contents:

```
─────────────────────────────────
Friday, May 15, 2026          ×
─────────────────────────────────
[+ Task] [+ Meeting] [+ Block]
─────────────────────────────────

TASKS (3)
  ☐ Confirm florist deposit
    Linked to: Josh & Esther wedding
  ☐ Send seating chart
    Linked to: Family Picnic wedding
  ☐ Follow up on RSVPs
    Linked to: Josh & Esther wedding

MEETINGS (1)
  10:00 — Venue walkthrough (60 min)
    Maple Hall · 3 attendees · Google Meet

EXTERNAL (0)
  Nothing on your connected calendars today.
─────────────────────────────────
```

Interaction:
- Click a task → opens existing task detail modal (no change).
- Click a meeting → opens existing meeting drawer (no change).
- `+ Task / + Meeting / + Block` open quick-create with the date
  pre-filled.
- `Escape` or `×` closes the panel.
- Clicking another day re-targets the panel.
- The grid cell for the selected day is ringed in `wedding-rose`.

---

## View 2 — Post-OAuth Calendar Picker Modal

### Trigger

Renders inside `app/admin/planner/calendar/callback/page.tsx`
*after* `completeCalendarCallback` returns successfully. Before this
modal closes, the backend has created the calendar_connections row
for the Aurinko account but has NOT yet created per-calendar rows or
webhook subscriptions. The picker drives which calendars become
connection rows.

### Layout

```
─────────────────────────────────────────────────────────────
                  Pick the calendars to sync                  ×
  We'll only sync events from the calendars you check.
  You can change this later under Settings → Calendars.
─────────────────────────────────────────────────────────────
emmanuel.t.akinwale@gmail.com · Google
─────────────────────────────────────────────────────────────

  ┌──┐  Primary calendar                 [Primary]
  │✓ │  emmanuel.t.akinwale@gmail.com    [Default write]
  └──┘  ─────────────────────────────────────────────
        Visibility:  ◉ Busy/free only  ◯ Full details
        Color:       [▢ rose]

  ┌──┐  Family
  │✓ │  Owner · writable
  └──┘  ─────────────────────────────────────────────
        Visibility:  ◉ Busy/free only  ◯ Full details
        Color:       [▢ sage]

  ┌──┐  Cushion — Bills & BNPL
  │  │  Subscribed feed · read-only
  └──┘  ─────────────────────────────────────────────
        (We can mirror busy blocks but won't sync events back.)

  ┌──┐  Holidays in United States
  │  │  Subscribed feed · read-only
  └──┘  ─────────────────────────────────────────────

─────────────────────────────────────────────────────────────
                            [Skip for now]  [Connect 2 calendars]
─────────────────────────────────────────────────────────────
```

### Behavior

- All checked rows: create `calendar_connections` + Aurinko webhook
  subscription on Submit.
- Unchecked rows: NOT created. The user can come back later via
  Settings → Add calendar.
- `Primary` and `Default write` badges are auto-applied to the first
  writable calendar; planner can flip them.
- Read-only subscribed feeds (iCal feeds Google pulls in from third
  parties) are visible but check-disabled and explicitly tagged
  "subscribed feed". This fixes the "Cushion - Bills & BNPL"
  surprise from 2026-05-13.

### Why not just sync everything

Three reasons we identified during the live OAuth run:

1. **Webhook subscription failures.** Aurinko refuses webhook
   subscriptions on read-only iCal-feed calendars, producing the
   "Webhook subscription failed for 3 calendars" banner.
2. **Personal noise.** Planners don't want their personal Cushion
   bill reminders showing up in the shared planner calendar.
3. **Industry pattern.** Cal.com, Calendly, Reclaim.ai, Motion all
   prompt for calendar selection post-OAuth, never bulk-import.

---

## View 3 — Settings Page (new route)

`/admin/planner/settings/calendars` — tab inside a future Settings
section. For this PR it can live as a standalone page; tabs can be
added when Settings has more sections.

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ Calendar settings                                                   │
│ Connections, sync rules, and webhook health.                        │
│                                                                     │
│ [+ Connect a calendar ▾]                                           │
│   ├ Google                                                          │
│   ├ Microsoft 365                                                   │
│   ├ iCloud                                                          │
│   └ Exchange / EWS                                                  │
│                                                                     │
│ ── Connected accounts ─────────────────────────────────────────────│
│                                                                     │
│ ▾ emmanuel.t.akinwale@gmail.com  ·  Google  ·  1 active  ·  ✓     │
│   ┌─────────────────────────────────────────────────────────────┐ │
│   │ Primary calendar              [active] [Default write]     │ │
│   │ Workspace user · Owner · Busy/free · Last check 2 min ago  │ │
│   │ [Settings] [Check health] [Disconnect]                     │ │
│   └─────────────────────────────────────────────────────────────┘ │
│   ┌─────────────────────────────────────────────────────────────┐ │
│   │ Family                        [active]                     │ │
│   │ Workspace user · Owner · Busy/free · Last check 2 min ago  │ │
│   │ [Settings] [Check health] [Disconnect]                     │ │
│   └─────────────────────────────────────────────────────────────┘ │
│                                                                     │
│ ▸ collapsed account groups would render here for multi-account     │
└─────────────────────────────────────────────────────────────────────┘
```

### Behavior

- Identical Settings modal we built today (Shared in team view, Sync
  enabled, Visibility mode, Default write target, Scheduler access
  section). No re-design needed — that modal stays.
- `Check health` / `Disconnect` per-row unchanged.
- The big chrome that used to sit on the calendar page (provider
  selector + per-row UI) lives only here now.

---

## Responsive

| Breakpoint | Behavior |
|---|---|
| `≥ 1280 px` | Calendar grid + persistent right rail (Upcoming / Availability / Legend). Slide-over replaces right rail when a day is clicked. |
| `768–1280 px` | Calendar grid full width. Right rail collapses to a button. Slide-over overlays the grid (z-50). |
| `< 768 px` | Agenda view by default. Day click slide-over is full-screen takeover with back button. Filter bar collapses to a single dropdown. |

---

## Brand application

Pulled from the project's existing brand variables (verified live on
2026-05-13 in the planner UI):

| Token | Hex | Used for |
|---|---|---|
| `wedding-rose` | `#D4A5A5` | Primary accent (selected day ring, primary buttons, brand pill) |
| `wedding-sage` | `#A8DADC` | Secondary accent (info badges, "shared" pills) |
| `wedding-gold` | `#E9C46A` | Metric emphasis (non-zero pill prefix dot), warning highlights |
| `wedding-navy` | `#1D3557` | Heading text on light bg, primary text on cards in light mode |

Typography stays as today: Playfair Display for the page heading
("Shared Planner Calendar"), Cormorant Garamond for italic captions
in the metric strip, Inter for everything else.

Dark mode is the current default; light mode auto via the existing
theme toggle.

---

## Open questions (please answer before I implement)

1. **Connect-button placement on the main calendar page.** When no
   calendars are connected at all, the status pill says
   "No calendar connected · + Connect a calendar". Should that
   `+ Connect` action open the picker inline, or send the user to
   `/admin/planner/settings/calendars`? My recommendation: send to
   Settings — fewer modal-in-modal cases.

2. **Slide-over panel persistence.** When a planner clicks May 15,
   navigates to a different page, then comes back to `/calendar` —
   should the slide-over re-open for May 15 (sticky), or close
   (ephemeral)? Recommendation: ephemeral. State lives in the URL
   only via `?date=2026-05-15` when you want to deep-link.

3. **Picker modal "Skip for now" semantics.** If the planner skips
   the picker entirely, do we (a) create zero connection rows and
   show an empty state, or (b) create one row for the primary
   calendar with sane defaults? Recommendation: (a). Skip means
   skip — give the user a clean state and a CTA to open the picker
   again from Settings.

4. **Right rail vs slide-over on wide screens.** On `≥ 1440 px` we
   could keep both visible simultaneously (right rail = global
   Upcoming, slide-over = selected day). Or always swap. I went
   with always-swap in the mockup above; tell me if you want
   side-by-side.

---

## What this mockup does NOT change

- The Settings modal we built today (per-calendar scheduler access /
  toggles). Moves verbatim to the new Settings page.
- The Aurinko OAuth flow, scope handling, or webhook signature
  verification — all unrelated.
- Any backend models, services, or API endpoints.
- The `couple-booking` flow (separate mockup).

---

## Files that would change if approved (informational only — no code yet)

```
NEW    app/admin/planner/settings/calendars/page.tsx       (extracted from current calendar page)
EDIT   app/admin/planner/calendar/page.tsx                 (remove connections, add slide-over + status pill)
EDIT   app/admin/planner/calendar/components/GoogleCalendarConnect.tsx  (moves to settings page)
NEW    app/admin/planner/calendar/components/DaySlideOver.tsx
NEW    app/admin/planner/calendar/callback/CalendarPickerModal.tsx
EDIT   app/admin/planner/calendar/callback/page.tsx        (render picker after success)
EDIT   app/services/calendar_provider_service.py           (skip auto-creating rows for un-picked calendars)
NEW    backend route: POST /admin/planner/calendar/connections/select  (commit picker choices)
```

Estimated PR size: ~600 LOC frontend, ~120 LOC backend, ~40 LOC tests.
Self-contained — no schema changes.
