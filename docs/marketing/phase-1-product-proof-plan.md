# Phase 1 Product-Proof Implementation Plan

Status: approved for implementation on 2026-07-12.

This document is the acceptance source for the Phase 1 homepage hero,
homepage product-proof stories, `/features`, product screenshot capture, and
demo-video capture workflow. It supersedes the hero, feature-card, comparison,
and screenshot recommendations in `docs/marketing-refresh-plan.md`. It does not
authorize new planner, couple, guest, venue, or vendor product features.

The external positioning source is `TSW - social media strategy.pdf`, especially
pages 3-11, 14-15, 22, and 24. The product claim is:

> The Special Wedding is the connected operating system built specifically for
> wedding planners. It replaces a patchwork of disconnected tools with one
> planner-owned workspace.

## Source of truth

- Product data remains in its existing canonical collections and services. The
  capture system creates isolated fixture records; it does not introduce a
  second application data model.
- `planner_tasks` remains the schedule-item source of truth. External calendars
  are projections and are not required for a marketing capture.
- The canonical capture dataset is one fictional planner studio managing one
  featured fictional wedding, with one secondary wedding used only to make the
  planner dashboard truthful.
- The canonical public assets live under `public/marketing/product-proof/` and
  are manually captured from the visible frontend after the testbed driver
  verifies the seeded backend state.
- `app/data/marketingCaptureScenes.json` is the shared machine-readable source
  for all 17 scene IDs, sessions, routes, stable text, and safe interactions;
  the product manifest and Python testbed fail if they drift from it.
- Public demo-video URLs remain unset until the corresponding media passes the
  capture receipt, safety scan, human frame review, and website playback check.

## Acceptance matrix

| ID | Surface or lifecycle | Acceptance evidence |
| --- | --- | --- |
| P1 | Reset and seed | One testbed driver resets only records owned by the marketing-capture seed, creates the account and subscription, runs the canonical workspace seeder, and verifies required documents before browser capture. Re-running is idempotent. |
| P2 | Tenant safety | The driver refuses non-local environments. Existing non-seed users, weddings, slugs, and owner-scoped records are never overwritten. Cleanup targets both the seed source and fixed isolated IDs. |
| P3 | Identity safety | Every visible name, email, business, image, phone, token, contract number, and message belongs to the approved fictional showcase world. No personal names, smoke/test labels, local paths, raw tokens, or real-looking private contact data appear in a frame. |
| P4 | Planner command center | Morning View renders two weddings with meaningful setup progress, unread work, RSVP movement, an upcoming meeting, vendor/budget state, and a clear next action. No zero-only, loading, or AI-error presentation is accepted. |
| P5 | Connected wedding record | The featured wedding has current setup-guide state, event days, privacy, story, gallery, vendor and couple configuration. One safe event edit can be saved and then observed in the planner, couple, and public surfaces. |
| P6 | Couple and public experience | The couple portal and public microsite use the same fictional wedding and show populated schedule, messages, registry/FAQ, forms, memories, contract/payment checkpoint, story, gallery, and RSVP-facing details appropriate to each role. Planner-only data remains private. |
| P7 | Guests and seating | Guest, RSVP, plus-one, meal, declined-status, table, floor-plan, scale, fixture, and layout-check data agree. A browser assignment or move persists after reload. |
| P8 | Planner boundaries | Unified communications, forms, reminders, and support threads demonstrate structured self-service and planner-owned boundaries without sending real email or SMS. |
| P9 | Business workflow | Vendor directory/CRM, assignment, contract, quote, budget, payment milestone, and planner package records agree on owner, wedding, vendor, currency, and amounts. No real signature, payment, or external message is triggered. |
| P10 | Remaining product proof | Gallery, guest memories, knowledge base, team permissions/activity, calendar/tasks, and payment surfaces are populated enough to prove their marketed behavior, not merely that a route exists. |
| P11 | Still-image capture | Every marketed product surface has a named capture scene, required session, route, stable-state selector, optional safe interaction, output path, safety assertions, and its own explicit human-review receipt tied to the exact Git build and untouched PNG checksum. A human drives visible Chrome at browser zoom 100% in DevTools `Responsive` mode at 1440x900 and DPR 1, then uses `Capture screenshot` and inspects the original PNG. Scripted navigation, scripted screenshots, generated shared receipts, full-size-page capture, cropping, resizing, and stitching are forbidden. |
| P12 | Homepage hero | The hero uses one strong populated command-center proof, preserves the existing brand system and CTA flow, and clearly says the product is built for wedding planners. It does not auto-cycle stale screenshots. |
| P13 | Homepage stories | The feature section contains four outcome-led stories: Connection Over Tools, Disorganization Tax, Couple Experience plus Boundaries, and Built for Planners. Each story uses current product proof and describes a connected outcome rather than a feature count. |
| P14 | Features page | The top of `/features` uses the same four outcomes. Detailed capabilities remain discoverable lower on the page. The 29-row competitor matrix no longer leads or defines the product story; comparison research remains available through `/compare`. |
| P15 | Video capture | Recording executes explicit feature actions and verifies visible results. Generic waypoint cursor motion and engineering-review framing are removed. A 60-90 second connected web story and social derivatives may publish only after safety and playback gates pass. |
| P16 | Frontend proof | Automated contracts pass, the testbed lifecycle passes, and manually driven visible Chrome verifies page identity, non-blank UI, no framework overlay, console health, seeded interactions, desktop, and mobile layouts. Screenshots and a capture receipt identify the exact tested build. |

## Entry-point and parity inventory

| Domain object | Create or seed entry points | Edit/display entry points that must agree | Reset/delete boundary |
| --- | --- | --- | --- |
| Planner and subscription | `scripts/setup_smoke_accounts.py`, subscription seed | `/admin/login`, `/admin/planner`, route guards and billing profile reads | Dedicated seed identity only; never a customer planner |
| Wedding configuration | marketing workspace seeder, planner wedding APIs | `/admin/weddings`, `/admin/weddings/[id]`, `/couple/dashboard`, `/[slug]` | Fixed showcase wedding IDs plus seed-source check |
| Schedule items and events | wedding event fields, `planner_tasks` | Morning View, wedding configuration, couple portal, public schedule, calendar | Seed-owned wedding/task records only; no provider sync target guessed |
| Couple portal | smoke account seed, couple invite/account store | couple login/dashboard, messages, forms, memories, contracts | Seed couple ID/email and showcase wedding only |
| Guests, RSVPs and seating | guest/RSVP/plus-one/table/layout collections | guest management, RSVP summaries, seating canvas and exports | Showcase wedding IDs; seating child records removed with parents |
| Communications and support | couple messages, reminder/email logs, support tickets | planner inbox, couple messages, guest support thread | Local/test transports only; cleanup by owner and seed source |
| Vendors and finance | vendor profiles/assignments/contracts, budget categories/items, packages/payments | planner vendor CRM, contract canvas/portal, budget, payments | Showcase owner/wedding/vendor IDs; no external payment/signature |
| Forms and media | form templates/responses, gallery/memory metadata | form canvas/public form/couple form, gallery, memory review/export | Seed-owned documents and approved repository media only |
| Team and knowledge base | team-member/activity and published KB fixtures | team management/audit and public/authenticated KB | Showcase planner scope only |
| Marketing assets | capture scene manifest | homepage hero, homepage stories, `/features`, demo manifest | Generated assets replaced atomically; rejected media stays non-public |

## Invariants

1. Explicit planner/couple intent is never replaced by a capture convenience.
2. Every seeded child record carries the featured wedding and owner scope that
   its production service expects.
3. Seed reruns replace or upsert only seed-owned records. Cleanup can be run
   before, after, or during recovery from a partial run.
4. Dates derive from one injected capture anchor and one IANA timezone so event,
   meeting, reminder, and payment displays cannot drift independently.
5. The dataset may include realistic operational complexity, but it must not
   include real people, real customer data, raw legal/payment secrets, or an
   action that contacts an external party.
6. A screenshot is accepted only after its route is stable, relevant values are
   visible, images are loaded, the console is clean, and forbidden visible text
   is absent.
7. Final stills and walkthrough footage are produced only through a manually
   driven visible browser. Seed, preflight, and validation automation never
   substitutes for the visible capture or the review of the original artifact.
   Pending stills remain hidden from public marketing surfaces, and changing a
   status alone cannot publish an image without its exact per-image receipt.
8. The capture runtime deliberately disables the Google Maps embed and the
   public wedding must render its intentional Directions fallback without a
   provider error or console failure.
9. The same raster is not forced into incompatible placements. Each public use
   declares its crop or has a dedicated capture.
10. Public video status remains `recording` until approved assets exist. Missing,
   rejected, or stale files cannot silently re-enable a launcher.

## Verification gate

At minimum, sign-off requires:

1. Focused red-green tests for the seed contract, testbed driver, capture scene
   manifest, Phase 1 marketing data, and public demo safety.
2. The paired testbed driver and cleanup scripts run successfully against the
   local services.
3. CI-aligned frontend lint, type-check, unit tests, and build.
4. Manually driven visible-Chrome verification of the seeded planner flow,
   couple flow, public wedding, homepage, and `/features` on desktop and mobile.
5. A hostile review covering tenant scope, stale routes, edit persistence,
   timezone round-trips, data/privacy leakage, crop behavior, copy alignment,
   and whether any claimed connection is only decorative.
