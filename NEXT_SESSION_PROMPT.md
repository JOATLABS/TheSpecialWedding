# Next Session Prompt — Couple Portal Redesign + Verify Prior Work

You are continuing development on "The Special Wedding" SaaS platform. This session has TWO priorities:

1. **Verify and fix everything implemented in the prior session** (couple portal consolidation)
2. **Redesign the couple-facing portal to match the platform's design system**

---

## CRITICAL RULES (READ BEFORE DOING ANYTHING)

- **EVERYTHING MUST BE DONE THROUGH THE FRONTEND, NOT BY MANUALLY TRIGGERING APIs.** Every feature must be testable by clicking through the UI in the browser.
- **DO NOT create new standalone modules or pages when existing ones can be extended.** The entire reason this work exists is because a previous AI built the couple portal as a separate app instead of integrating into existing pages. Do not repeat that mistake.
- **DO NOT start the dev servers yourself.** The user runs them via Docker. Ask the user to confirm servers are up before testing.
- **Ask the user before making design decisions.** Do not assume — present options and wait for approval.
- **Test everything in the browser after implementing.** Use the planner tab and couple tab to verify.

---

## PART 1: Verify and Fix Prior Session Work

The prior session moved couple portal features out of the standalone `/admin/couple-portal` page and into existing platform pages. Some of this work was written but NOT fully tested. You need to verify each item works end-to-end through the frontend.

### Test Credentials
- **Planner login**: `test_planner_package@thespecialwedding.io` / `testPlannerPackage123!`
- **Couple login**: `test_couple1@thespecialwedding.io` / `testCouplePass123!`
- **Wedding ID**: `wedding_1774312551367`
- **Planner URL**: `http://localhost:3000/admin/login`
- **Couple URL**: `http://localhost:3000/couple/login`

### 1a. Program & Notes on Weddings Page (`/admin/weddings`)

**What was done**: Added "Program" (indigo button) and "Notes" (amber button) to each wedding card on the Weddings list page. Each opens a popup modal.

**File**: `/app/admin/weddings/page.tsx`

**What to verify**:
- Both buttons appear on the wedding card for `wedding_1774312551367`
- Clicking "Program" opens a modal showing wedding events (Traditional Ceremony, Reception)
- The wedding MUST have events configured first — go to Configure (`/admin/weddings/wedding_1774312551367`) and add events if none exist (Traditional Ceremony + Reception)
- Can add a program item (title, time, description) to an event — item appears in the list after adding
- Can delete a program item — item disappears after deleting
- Clicking "Notes" opens a modal showing couple notes
- Can add a note, see status tracking, reply to notes

**Known bugs from prior session**:
- After adding/deleting program items, the UI sometimes doesn't refresh. A `key` prop was added to `ProgramModalContent` to force re-mount: `key={JSON.stringify(modalEvents.map(e => e.order_of_events?.length || 0))}`. Verify this works.
- Delete sometimes showed "not found" toast even though the delete succeeded at the API level. Check if this is still happening.
- After saving events on the Configure page and returning to Weddings list, buttons sometimes disappear due to Turbopack caching. Hard refresh (Cmd+Shift+R) fixes this — just be aware.

**API endpoints used**:
- `GET /weddings/{wedding_id}` → returns `wedding.events` array with `order_of_events[]`
- `POST /couple-portal/events/{event_index}/order-of-events` — add program item
- `DELETE /couple-portal/events/{event_index}/order-of-events/{item_id}` — delete program item
- Note: `couple_portal_router` has NO `/admin` prefix

### 1b. Custom Templates on Forms Page (`/admin/forms`)

**What was done**: Added a "Custom Templates" section to the existing Forms page, between the Forms library section and the Create modal. Uses glassmorphism card style matching the existing page design.

**File**: `/app/admin/forms/page.tsx`

**What to verify**:
- Navigate to `/admin/forms` — the "Custom Templates" section should appear below "Forms library"
- Section shows a loading spinner, then either "No custom templates yet" or a grid of template cards
- Each template card shows: name, description, field count, category badge, created date
- "Use Template" button expands an inline form name input + Create/Cancel buttons
- Creating from template calls the API and adds a new form to the forms library
- Delete button removes a template with confirmation dialog

**Code that was added** (verify it's all present and correct):
- State: `customTemplates`, `customTplLoading`, `creatingFromTpl`, `newTplFormName`
- Functions: `fetchCustomTemplates`, `handleCreateFromCustomTemplate`, `handleDeleteCustomTemplate`
- `fetchCustomTemplates()` is called in the existing `useEffect`
- UI section between `</section>` (Forms library) and `<Transition>` (Create modal)

**API endpoints used**:
- `GET /couple-portal/form-templates` → `{ templates: [...] }`
- `POST /couple-portal/form-templates/create-form` → body: `{ template_id, form_name }`
- `DELETE /couple-portal/form-templates/{id}`
- Uses `formsApi.resolveBaseUrl()` which returns `getApiBaseUrl()` (same as `localhost:8000`)

**IMPORTANT**: This was written but NEVER tested in the browser. It may not render at all if there's a compilation error. Check the browser console for errors.

### 1c. Meetings → Calendar Task Category (`/admin/planner/calendar`)

**What was done**:
- Added `'meeting'` ("Couple Meeting") as a `TaskCategory` in the task system
- Removed the standalone green "Meetings" button and modal from the Calendar page header
- Removed `MeetingsModalContent` function and `Meeting` interface (~250 lines)
- Removed `meetingModalOpen` state

**Files changed**:
- `/app/services/calendarApi.ts` — added `'meeting'` to `TaskCategory` union and `CATEGORY_LABELS`
- `/app/admin/planner/calendar/components/TaskModal.tsx` — added `'meeting'` to `CATEGORIES` array
- `/app/admin/planner/calendar/page.tsx` — removed meetings button, modal, state, and function

**What to verify**:
- No green "Meetings" button in Calendar page header — only "+ New Task" should remain
- Click "+ New Task" — the Category dropdown should include "Couple Meeting" as an option
- The "All Categories" filter dropdown on the calendar should include "Couple Meeting"
- Can create a task with category "Couple Meeting", assign to a wedding, set start/end times, recurring, reminder
- No TypeScript errors from the removal

### 1d. Task Modal Compact Layout

**What was done**: Rewrote the Create/Edit Task modal form to fit on screen without scrolling.

**File**: `/app/admin/planner/calendar/components/TaskModal.tsx`

**New layout**:
- Row 1: Title input (full width)
- Row 2: Wedding / Category / Priority / Color — 4 columns (`grid grid-cols-4 gap-3`)
- Row 3: Start date+time / End date+time / All-day checkbox — inline with `flex items-end gap-3`
- Row 4: Due date / Reminder / Google Cal checkbox — inline
- Row 5: Single description textarea (2 rows, merged old Description + Notes)
- Row 6: Cancel / Create buttons

**What to verify**:
- All fields visible on screen without scrolling when modal opens
- Time inputs not cut off (widened to `w-32`)
- All-day checkbox works (hides time inputs)
- Google Cal checkbox appears for new tasks, hidden when editing
- Form submits successfully — task appears on calendar
- Edit mode populates all fields correctly

### 1e. Dialog Component Fix

**What was done**: Modified the shared Dialog component to not hardcode `max-w-lg` so callers can specify their own width. Added `max-h-[90vh] overflow-y-auto` as defaults.

**File**: `/app/components/ui/Dialog.tsx`

**Current state of DialogContent's inner div**:
```
className={`relative bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6 w-full max-h-[90vh] overflow-y-auto mx-4 ${className}`}
```

**What to verify**:
- TaskModal renders at `max-w-3xl` (not squeezed to `max-w-lg`)
- Other Dialog users still work: `CollectPaymentModal` (`sm:max-w-md`), `PaymentMilestones` (`sm:max-w-lg`, `sm:max-w-md`), `VendorPaymentModal` (`sm:max-w-lg`)
- None of these modals are broken by the change

### 1f. Messages on Inbox Page (`/admin/inbox`)

**What was done**: In a prior session (before this one), unified couple messaging was moved to the Inbox page. This should already be working but verify:
- Navigate to `/admin/inbox`
- Couple messages should appear in the unified inbox
- Can send messages to couples, receive replies

---

## PART 2: Redesign the Couple-Facing Portal

The couple-facing portal at `/couple/dashboard` currently looks like a completely separate app. It has its own layout (sticky header + horizontal tab bar with 10 tabs), its own color scheme, and its own design patterns. **It needs to be completely redesigned to match the platform.**

### Current Couple Portal Architecture

**Files**:
- `/app/couple/layout.tsx` — Minimal layout, just `min-h-screen bg-gray-50 dark:bg-slate-900`
- `/app/couple/dashboard/page.tsx` — 2156 lines, single mega-component with 10 tabs
- `/app/couple/login/page.tsx` — Login page
- `/app/couple/setup/page.tsx` — Initial setup
- `/app/couple/forms/[formId]/page.tsx` — Individual form view

**Current tabs** (defined as `TabType`):
`'overview' | 'timeline' | 'payments' | 'contracts' | 'forms' | 'updates' | 'messages' | 'meetings' | 'registry' | 'faq'`

**Current layout**: Sticky header with couple name + logout → horizontal scrolling tab bar → tab content area

**Auth mechanism**: Uses `localStorage` for `couple_token` and `couple_data`. Fetches dashboard via `GET /couple/portal/dashboard`.

### Target Design (Match the Platform)

The planner side uses:
- **Sidebar** (`/app/admin/components/Sidebar.tsx`) — Collapsible, dark theme, nav links with icons
- **Top header** (`/app/admin/components/TopHeader.tsx`) — Mobile menu toggle, theme switch, notifications, user menu
- **Layout** (`/app/admin/layout.tsx`) — Mesh gradient background with floating blurred circles, `bg-light-bg dark:bg-dark-bg`, transitions on sidebar collapse
- **Main content**: `flex-1 p-4 sm:p-6 lg:p-8 space-y-6`
- **Card pattern**: `bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700`
- **Dark mode colors**: `slate-` palette (`dark:bg-slate-800`, `dark:bg-slate-700`, `dark:border-gray-700`)
- **Theme context**: `ThemeProvider` from `/app/contexts/ThemeContext.tsx`
- **Page headers**: `PageHeader` component from `/app/admin/components/PageHeader.tsx`

### What to Build

#### 2a. Couple Sidebar Component

Create `/app/couple/components/CoupleSidebar.tsx`:
- Same structure as the admin Sidebar but with couple-specific nav items
- Nav items (merged from the 10 tabs):
  1. **Dashboard** (overview — countdown, stats, planner info, QR code, push notifications)
  2. **Timeline** (wedding events with order of events and notes)
  3. **Payments** (merge Payments + Contract tabs — payment history, contract details, payment summary)
  4. **Forms** (pending forms to fill out)
  5. **Inbox** (merge Messages + Updates tabs — couple-planner messaging and wedding updates)
  6. **Registry** (gift registries CRUD)
  7. **FAQ** (frequently asked questions CRUD)
- **Remove Meetings** — meetings are now planner tasks with "Couple Meeting" category, the couple doesn't need a separate view
- Logo at top linking to `/couple/dashboard`
- Collapsible on desktop, drawer on mobile
- Same dark theme as planner sidebar

#### 2b. Couple Top Header Component

Create `/app/couple/components/CoupleTopHeader.tsx`:
- Same structure as admin TopHeader
- Mobile menu toggle (hamburger icon)
- Theme toggle (light/dark)
- Couple name display
- Logout button
- Unread message indicator (optional)

#### 2c. Couple Layout Rewrite

Rewrite `/app/couple/layout.tsx`:
- Wrap in `ThemeProvider` (reuse from `/app/contexts/ThemeContext.tsx`)
- Add mesh gradient background (same as admin layout)
- Include CoupleSidebar and CoupleTopHeader
- Main content area with proper padding: `p-4 sm:p-6 lg:p-8 space-y-6`
- Handle auth redirect (if no `couple_token`, redirect to `/couple/login`)
- Create a CoupleContext or similar to share auth state + dashboard data across sidebar and content

#### 2d. Dashboard Page Rewrite

Rewrite `/app/couple/dashboard/page.tsx`:
- Convert from tab-based single component to either:
  - **Option A**: Keep as single page with section switching via sidebar (simpler, less routing)
  - **Option B**: Split into separate route pages under `/couple/dashboard/`, `/couple/timeline/`, etc.
- **Option A is recommended** to avoid creating many new files and routes
- Apply platform card styles to all sections:
  - Cards: `bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700`
  - Text: `text-slate-900 dark:text-white` for headings, `text-slate-600 dark:text-slate-400` for secondary
  - Buttons: Use indigo for primary actions, consistent with planner side
  - Stats cards: Same grid pattern as planner dashboard
- Remove the old sticky header and horizontal tab bar entirely
- Each "section" becomes what renders in the main content area when the corresponding sidebar item is active

#### 2e. Merge Sections

**Payments + Contract → "Payments"**:
- Show contract summary at top (package name, status, signed date)
- Payment history below (list of milestones with status badges)
- Payment summary (total, paid, remaining)

**Messages + Updates → "Inbox"**:
- Messages section: real-time messaging with planner (already has send/receive UI)
- Updates section below or as a sub-tab: wedding updates/announcements from planner
- Unread count badge on sidebar nav item

**Remove Meetings tab entirely.**

### Design Tokens Reference

From the platform's Tailwind config and existing pages:

```
// Backgrounds
bg-light-bg dark:bg-dark-bg          // Page background
bg-white dark:bg-slate-800           // Card background
bg-gray-50 dark:bg-slate-900         // Alternate section background

// Borders
border-gray-200 dark:border-gray-700 // Standard card border
border-slate-200 dark:border-slate-700 // Alternate border

// Text
text-slate-900 dark:text-white       // Primary heading
text-gray-700 dark:text-gray-300     // Body text
text-gray-500 dark:text-gray-400     // Secondary/muted text
text-gray-600 dark:text-gray-400     // Label text

// Cards
rounded-xl shadow-sm                 // Standard card rounding + shadow
p-4 or p-6                           // Card padding

// Buttons (primary)
bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg

// Mesh gradient (in layout)
bg-primary-400/30 blur-[100px] animate-float   // Top-left blob
bg-secondary-400/30 blur-[100px] animate-float  // Bottom-right blob
opacity-40 dark:opacity-20                       // Container opacity
```

### Technical Notes

- **Frontend**: Next.js 16.1.6 (Turbopack), React 19, TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), Motor (MongoDB async driver)
- **Couple auth**: JWT with `require_couple_auth` dependency, stored in `localStorage` as `couple_token`
- **API base**: `getApiBaseUrl()` from `/app/utils/env.ts`
- **Couple dashboard API**: `GET /couple/portal/dashboard` returns all data in one call
- **Couple messages API**: `GET/POST /couple/portal/messages`, `GET /couple/portal/messages/unread-count`
- **Wedding IDs**: String format like `wedding_1774312551367` (NOT ObjectIds)
- **The admin Sidebar component is at**: `/app/admin/components/Sidebar.tsx` — use as reference
- **The admin TopHeader is at**: `/app/admin/components/TopHeader.tsx` — use as reference
- **The admin layout is at**: `/app/admin/layout.tsx` — use as structural reference
- **ThemeContext**: `/app/contexts/ThemeContext.tsx` — reuse for couple portal

### Files to Reference (Read Before Coding)

1. `/app/admin/layout.tsx` — Admin layout structure (sidebar + header + mesh gradient)
2. `/app/admin/components/Sidebar.tsx` — Sidebar component (collapsible, icons, nav links)
3. `/app/admin/components/TopHeader.tsx` — Top header component
4. `/app/contexts/ThemeContext.tsx` — Theme provider (light/dark toggle)
5. `/app/couple/dashboard/page.tsx` — Current couple dashboard (the 2156-line file to rewrite)
6. `/app/couple/layout.tsx` — Current couple layout (to rewrite)
7. `/app/admin/planner/page.tsx` — Planner dashboard (reference for card/stats layout style)

---

## Summary of All Changed Files from Prior Session

These files were modified and need verification:

| File | Change |
|------|--------|
| `/app/admin/weddings/page.tsx` | Added Program + Notes modal buttons and components |
| `/app/admin/forms/page.tsx` | Added Custom Templates section (state, handlers, UI) |
| `/app/services/calendarApi.ts` | Added `'meeting'` to TaskCategory and CATEGORY_LABELS |
| `/app/admin/planner/calendar/components/TaskModal.tsx` | Added `'meeting'` to CATEGORIES, compact form layout |
| `/app/admin/planner/calendar/page.tsx` | Removed Meetings button, modal, state, MeetingsModalContent |
| `/app/components/ui/Dialog.tsx` | Removed hardcoded max-w-lg, added max-h/overflow defaults |
| `/CHANGELOG.md` | Added [2.26.0] entry |

---

## Definition of Done

- [ ] All 6 verification items from Part 1 pass (tested through the frontend, not API calls)
- [ ] Couple portal has sidebar navigation matching platform style
- [ ] Couple portal has top header with theme toggle and logout
- [ ] Couple portal uses mesh gradient background
- [ ] All couple portal sections use platform card styles
- [ ] Meetings tab removed from couple portal
- [ ] Payments + Contract merged into single "Payments" section
- [ ] Messages + Updates merged into single "Inbox" section
- [ ] Couple portal responsive (mobile sidebar collapses to drawer)
- [ ] Dark mode works correctly on couple portal
- [ ] No TypeScript compilation errors
- [ ] CHANGELOG.md updated with couple portal redesign entry
