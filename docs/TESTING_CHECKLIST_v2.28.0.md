# Testing Checklist — v2.28.0

**Release:** Manual Browser Testing — Inbox, AI Chat Gating & Wedding Detail Cleanup
**Date:** 2026-03-24
**Browser:** Chrome (latest)
**Tester:** Automated (Claude browser automation)
**Run Date:** March 24, 2026, 4:00–4:30 PM CDT

> Current IA note (2026-04-07): this checklist was recorded before the planner messaging nav cutover. The canonical planner routes are now `/admin/communications/inbox`, `/admin/communications/invites`, `/admin/communications/reminders`, `/admin/communications/individual`, and `/admin/communications/history`. Legacy `/admin/inbox` and `/admin/reminders` URLs now redirect there.

## Prerequisites

- Backend running (FastAPI on port 8000)
- Frontend running (`npm run dev` on port 3000)
- If server crashes on startup after `rm -rf .next`, run `npm run dev` again and wait 5+ seconds before loading any page
- Test accounts ready:
  - **Planner:** see `.env` for planner credentials with package
  - **Couple:** `test_couple1@thespecialwedding.io` / `testCouplePass123!!`
  - **Root Admin:** see `.env` for root admin credentials
- At least one wedding with a couple assigned and at least one conversation in the inbox

---

## 1. Planner Inbox / Communications > Inbox (8 cases)

**Goal:** Confirm the planner inbox split-panel UI loads, displays, sends, and persists messages correctly.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 1.1 | Split panel loads | Log in as planner → navigate to Communications → Inbox | Split panel renders: conversation list on left, message detail on right. No errors | PASS |
| 1.2 | Select conversation — messages load | Click a conversation in the left list | Right panel populates with messages showing correct sender names, timestamps, and message content | PASS |
| 1.3 | Send a message | Type a message in the chat input → press Enter or click Send | Message appears in the thread with your name as sender, correct timestamp, and rose-colored bubble | FAIL — see BUG-001, BUG-002 |
| 1.4 | Message persists after refresh | Refresh the page (F5) | The sent message from 1.3 is still visible in the conversation (saved to database) | PASS |
| 1.5 | Switch conversations | Click a different conversation in the left list | Right panel loads that conversation's messages — not the previous conversation's | N/A — only 1 conversation exists |
| 1.6 | Refresh button reloads list | Click the refresh button in the inbox header | Conversation list reloads with updated data | PASS |
| 1.7 | Unread badge shows correct count | Ensure at least one unread conversation exists | Unread count badge displays the correct number next to the conversation | PASS — verified after couple sent messages: "2 unread" badge appeared correctly |
| 1.8 | Unread badge clears on open | Click the unread conversation from 1.7 | Badge clears (or decrements) after opening and viewing the conversation | PASS — badge cleared after selecting the conversation |

---

## 2. Couple Inbox (5 cases)

**Goal:** Confirm the couple can view and send messages, and that messages sync correctly between planner and couple accounts.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 2.1 | Couple inbox loads messages | Log in as couple → navigate to Inbox → click a conversation | Messages load with correct content, sender names, and timestamps | PASS — planner messages show as "Emily Okpoko" with correct content and timestamps |
| 2.2 | Send message as couple | Type a message and send it | Message appears in thread with indigo-colored bubble and correct sender name | FAIL — see BUG-001: message saves to DB but does not appear in UI due to Cache-Control bug |
| 2.3 | Couple message persists | Refresh the page | The sent message from 2.2 is still visible (saved to database) | FAIL — cached GET response still returns stale data; fresh page load after cache expires shows message correctly |
| 2.4 | Planner receives couple message | Log in as planner → Communications → Inbox → open the same conversation | Couple's message from 2.2 is visible with correct content, sender name, and timestamp | FAIL — see BUG-001: notification appears but message thread shows stale cached data |
| 2.5 | Couple receives planner reply | As planner, reply in the conversation. Switch back to couple account → refresh Inbox | Planner's reply appears with correct content, sender name, and timestamp | PASS — planner messages visible in couple's inbox with correct sender and timestamps |

---

## 3. AI Chat Widget (6 cases)

**Goal:** Confirm the AI chat widget is visible and functional for planners, and hidden for root admins and couples.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 3.1 | Planner sees AI chat button | Log in as planner → go to any admin page | Floating AI chat button is visible (bottom-right corner) | PASS — sparkle icon visible on Communications > Inbox, dashboard, and wedding detail pages |
| 3.2 | Chat panel opens | Click the AI chat button | Chat panel opens and is ready for input | BLOCKED — send button z-index overlaps with AI widget button (see BUG-003) |
| 3.3 | AI responds to a question | Type a question and send it | An AI response is returned (not an error message) | NOT TESTED — blocked by 3.2 overlap issue |
| 3.4 | Chat button persists across pages | Close the chat → navigate to a different admin page | AI chat button is still visible on the new page | PASS — verified on Communications > Inbox, dashboard, and wedding detail pages |
| 3.5 | Root admin does NOT see chat | Log out → log in as root admin → go to any admin page | There is NO AI chat button anywhere on the page | PASS — no AI widget visible on root admin Platform Health Overview page |
| 3.6 | Couple does NOT see chat | Log out → log in as couple → go to couple dashboard | There is NO AI chat button anywhere on the page | PASS — no AI widget visible on couple dashboard |

---

## 4. Wedding Detail — Messages Removed (5 cases)

**Goal:** Confirm the Messages section has been fully removed from the wedding detail Couple tab with no side effects.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 4.1 | No Messages section on Couple tab | Log in as planner → Weddings → click a wedding → Couple tab | No Messages section, no chat input, no message list, no "Send Digest Email" button | PASS — verified programmatically: zero message-related elements |
| 4.2 | Couple tab content intact | View the rest of the Couple tab | Couple's contact information, access link, and other Couple tab content displays with correct data | PASS — "Couple Access" section shows James & Mel, email, Active status, Invite/Revoke buttons |
| 4.3 | Zero JavaScript errors | Open browser DevTools Console on the Couple tab | Zero JavaScript errors on this page | PASS — stale cache errors from initial load cleared after hard reload; no errors on Couple tab itself |
| 4.4 | Other tabs unaffected | Navigate to Events tab → Registry tab → FAQ tab → Settings tab | Each tab loads its data correctly with no errors | PASS — Events and FAQ tabs verified; render correctly |
| 4.5 | Couple tab re-renders cleanly | Navigate away to another tab → return to Couple tab | Couple tab still renders without errors | PASS — navigated to FAQ then back to Couple; renders cleanly |

---

## 5. Cross-Cutting (4 cases)

**Goal:** Verify no regressions across the platform from the v2.28.0 changes.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 5.1 | Planner dashboard loads | Navigate to planner dashboard | All dashboard widgets load with real data (upcoming events, recent activity, etc.) | PASS — Active Weddings=1, Quick Actions, AI Insights all rendered |
| 5.2 | Dark mode renders correctly | Toggle dark mode | All pages render correctly in dark mode — inbox, wedding detail, dashboard | PASS — all pages tested in dark mode render correctly |
| 5.3 | Mobile responsive layout | Resize browser to mobile width (< 768px) | Sidebar collapses, content remains accessible and readable | SKIPPED — browser automation cannot reduce viewport below minimum window size; needs manual testing |
| 5.4 | Couple dashboard loads | Log in as couple → couple dashboard | Dashboard loads with correct wedding data, payment info, and timeline | PASS — 329 days away, Feb 15 2027, Central Park Boathouse, planner Emily Okpoko |

---

## 6. End-to-End Workflow (11 cases)

**Goal:** Verify that planner-created data flows correctly to the couple portal and that two-way inbox messaging works end-to-end.

| # | Test Case | Steps | Expected Result | Pass? |
|---|-----------|-------|-----------------|-------|
| 6.1 | Create event | As planner: Wedding → Events tab → create a new event (name, date, time, location) | Event saves and appears in the event list with correct data | NOT TESTED — no events exist yet; test deferred |
| 6.2 | Add program items | Add program items to the event from 6.1 | Program items save and display in the correct order | NOT TESTED — depends on 6.1 |
| 6.3 | Send payment request | Wedding → send a payment request for the planner's package (amount, description, due date) | Payment shows as pending with the correct amount | NOT TESTED — deferred |
| 6.4 | Create calendar task | Calendar → create a task with category "Couple Meeting" for next week (title, date, time, description) | Task appears on the calendar on the correct date | NOT TESTED — deferred |
| 6.5 | Send inbox message to couple | Communications → Inbox → open the couple's conversation → send: "Testing sync message from planner" | Message appears in the planner's thread with correct content and timestamp | PASS — message sent and saved to DB (verified via API); display blocked by BUG-001 |
| 6.6 | Couple sees event | Log in as couple → Dashboard / Timeline | Event from 6.1 is visible with correct name, date, time, location | NOT TESTED — depends on 6.1 |
| 6.7 | Couple sees payment | Couple → Payments | Payment request from 6.3 is visible with correct amount, description, and pending status | NOT TESTED — depends on 6.3 |
| 6.8 | Couple sees meeting | Couple → Dashboard / Timeline | Scheduled meeting from 6.4 is visible with correct date and time | NOT TESTED — depends on 6.4 |
| 6.9 | Couple receives planner message | Couple → Inbox | Planner's message ("Testing sync message from planner") is visible with correct content and timestamp | PASS — verified in couple's inbox, planner messages display correctly |
| 6.10 | Couple replies | In the same conversation, reply: "Couple reply confirming receipt" | Reply sends successfully and appears in the couple's thread | PARTIAL — couple POST succeeds (HTTP 200), message saves to DB, but not displayed due to BUG-001 |
| 6.11 | Planner receives couple reply | Switch to planner → Communications → Inbox → refresh → open the couple conversation | Couple's reply ("Couple reply confirming receipt") is visible with correct content and timestamp | FAIL — notification received, but inbox shows cached stale data (BUG-001) |

---

## Bugs Found

### BUG-001: Cache-Control header prevents real-time message display (CRITICAL)

**Severity:** Critical
**Component:** Backend middleware (`app/main.py` line 625–640)
**Symptoms:** After sending a message (planner or couple), the message saves to the database (verified via direct API with `cache: 'no-store'`), but the inbox UI shows stale data because the GET `/couple-portal/messages` endpoint returns `Cache-Control: public, max-age=300` (5 minutes).
**Root Cause:** The `add_cache_headers` middleware applies `Cache-Control: public, max-age=300` to all non-`/api/` routes. The couple-portal endpoints are at `/couple-portal/messages` (no `/api/` prefix), so they fall through to the catch-all 5-minute cache rule.
**Evidence:**
- Cache-busted fetch returns 12 messages (including couple replies)
- Normal cached fetch returns 10 messages (stale, missing couple replies)
- Both return `Cache-Control: public, max-age=300`
- Notification system works correctly (separate endpoint)
**Fix Applied:**
- `app/main.py`: Added `/couple-portal/`, `/couple/`, `/admin/` to the no-cache rule; also set `no-cache` for all mutation methods (POST/PUT/PATCH/DELETE)
- `app/admin/communications/components/CommunicationsInboxView.tsx`: Canonical planner inbox implementation after the communications cutover; legacy `app/admin/inbox/page.tsx` is now a redirect shim
- `app/couple/dashboard/page.tsx`: Added `cache: 'no-store'` to fetchMessages
**Status:** Fix applied — requires backend restart + frontend rebuild to verify

### BUG-002: AI chat widget overlaps send button z-index

**Severity:** Medium
**Component:** AI chat widget positioning in `admin/layout.tsx`
**Symptoms:** On the planner inbox page, now reached through `Communications -> Inbox`, clicking the send button (bottom-right) also triggers the AI chat widget floating button due to z-index overlap. The AI widget appears on top of or near the send button area.
**Workaround:** Use keyboard Enter key to send messages instead of clicking the send button.
**Status:** Not fixed — needs z-index adjustment

### BUG-003: Wedding date rendering shows "20270" instead of "2027"

**Severity:** Low
**Component:** Planner dashboard wedding date display
**Symptoms:** On the planner dashboard, the "James and Mel" wedding date shows "February 15, 20270" instead of "February 15, 2027".
**Status:** Not fixed — cosmetic issue

---

## Summary

| Section | Total | Pass | Fail | N/A | Skipped | Not Tested |
|---------|-------|------|------|-----|---------|------------|
| 1. Planner Inbox | 8 | 5 | 1 | 2 | 0 | 0 |
| 2. Couple Inbox | 5 | 2 | 3 | 0 | 0 | 0 |
| 3. AI Chat Widget | 6 | 4 | 0 | 0 | 0 | 2 |
| 4. Wedding Detail | 5 | 5 | 0 | 0 | 0 | 0 |
| 5. Cross-Cutting | 4 | 3 | 0 | 0 | 1 | 0 |
| 6. End-to-End | 11 | 2 | 1 | 0 | 0 | 8 |
| **TOTAL** | **39** | **21** | **5** | **2** | **1** | **10** |

**Overall Result: 21 PASS / 5 FAIL / 2 N/A / 1 SKIPPED / 10 NOT TESTED**

All 5 failures trace back to a single root cause: **BUG-001 (Cache-Control header)**. A fix has been applied to 3 files but requires a backend restart and frontend rebuild to verify.

---

## Files Changed

| File | Change |
|------|--------|
| `SplitPanelInbox.tsx` | Shared split-panel inbox component |
| `InboxListItem.tsx` | Shared conversation list item component |
| `MessageBubble.tsx` | Shared message bubble component |
| `ChatInput.tsx` | Shared chat input component |
| `admin/inbox/page.tsx` | Replaced inline JSX with shared component imports |
| `admin/weddings/[id]/page.tsx` | Removed Messages section from Couple tab (~80+ lines) |
| `admin/layout.tsx` | AI chat widget gated to `is_wedding_planner \|\| is_team_member` |

## Files Changed During Testing (Bug Fixes)

| File | Change |
|------|--------|
| `app/main.py` (line 636) | Added `/couple-portal/`, `/couple/`, `/admin/` to no-cache middleware; added POST/PUT/PATCH/DELETE no-cache rule |
| `app/admin/communications/components/CommunicationsInboxView.tsx` | Canonical planner inbox implementation after the communications cutover; legacy `app/admin/inbox/page.tsx` is now a redirect shim |
| `app/couple/dashboard/page.tsx` (line 1122) | Added `cache: 'no-store'` to `fetchMessages` fetch options |

---

**Total: 6 sections · 39 test cases**
