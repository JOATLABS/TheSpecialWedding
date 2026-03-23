# Feature Test Coverage & Integrated QA Plan (March 2025)

This reference maps the 13 audited capabilities to the current automated coverage so we can plan the
frontend, backend, and integrated tests required for end-to-end confidence. The goal is to align with
the test pyramid best practice—unit and service tests as a foundation, with full-stack Playwright
journeys validating critical workflows once the remaining roadmap items ship.【F:app/docs/features/FEATURE_STATUS_AUDIT.md†L7-L64】【fb4e63†L1-L68】

## Coverage snapshot

| Capability | Backend automation | Frontend automation | Integrated / E2E status | Required actions before calling the feature "fully verified" |
| --- | --- | --- | --- | --- |
| Budget category & summary management | No dedicated regression yet; current backend suite only exercises payment, template, forms, metrics, notification, vendor, and trial services.【e854dc†L1-L2】 | None | None | Add service-level tests that cover category CRUD and summary card calculations, then script Playwright smoke covering category creation/edit/archive and dashboard totals. |
| Vendor quote workflow | None in backend suite today (quotes absent from the current test roster).【e854dc†L1-L2】 | None | None | Backfill budget quote service/API tests plus a UI flow that captures quote request, acceptance, and rating. |
| Guest CSV import pipeline | Not covered by automated backend tests; import helpers are untested in the existing suite.【e854dc†L1-L2】 | None | None | Introduce service/API tests for CSV parsing/validation and a Playwright flow that uploads a sample file and verifies guest records. |
| Secure form response CSV export | Backend export sanitisation lacks coverage, but the frontend helper is exercised by `fetchFormResponsesCsv` unit tests.【a8d3eb†L1-L64】 | `fetchFormResponsesCsv` validates request construction, auth headers, and filename parsing.【a8d3eb†L1-L64】 | None | Add FastAPI/service tests for export filtering and failure states, then script an E2E download smoke once backend coverage lands. |
| Payment tracking experience | Hardened by API regression tests that enforce wedding access and payment persistence.【d8653f†L96-L198】 | `budgetApi` suite covers payment posting and history fetching.【8a2a24†L32-L126】 | None | After category CRUD tests exist, add a Playwright flow that records a payment and confirms UI refreshes. |
| Custom budget template authoring | Budget service tests persist templates, validate totals, and enforce unique categories.【e067fc†L30-L114】 | `budgetApi` template tests normalise payloads and error handling.【8a2a24†L129-L200】 | None | Layer on UI automation for template creation and sharing once backend quote/template coverage is complete. |
| Form builder creation variants & analytics | FastAPI and service suites cover blank creation, sanitisation, duplication, and unread badge handling.【99778e†L90-L164】【9da2a8†L97-L157】 | `formsApi` tests assert REST payloads for blank, template, duplicate, and view-marking flows.【d5c4bc†L12-L112】 | None | Plan a Playwright scenario that exercises blank and template creation plus analytics tab, after notification work lands. |
| Planner metrics dashboard | No automated validation for `/admin/planner`; backend focus is currently on SaaS metrics, not planner views.【e854dc†L1-L2】 | None | None | Add service/controller tests for planner metrics aggregation, then cover the UI cards through Playwright once data APIs are locked. |
| Email notification automation | Notification service tests cover happy path, empty audiences, and disabled email client scenarios.【9f6dba†L1-L191】 | None | None | Add frontend unit tests around the announcement composer plus an end-to-end Playwright run that triggers a test announcement in staging. |
| Vendor dashboard workspace | Vendor dashboard service aggregation and task gating are validated in backend tests.【b9e45c†L49-L174】 | None | None | Script API contract tests for the Next.js client and a Playwright vendor login/task completion scenario. |
| Trial expiration security enforcement | Trial expiration suite covers auto-deactivation, warning outreach, config gates, and auth blocking.【f31544†L1-L200】 | None | None | Build a frontend regression that surfaces the expired-trial lock screen message once Playwright specs are in place. |
| Platform metrics analytics (in progress) | Aggregator tests compute totals and reject invalid timeframes.【ae8811†L62-L178】 | None | None | Expand backend tests to cover the remaining metrics sources, finish the UI implementation, then capture an E2E review of filters when the feature graduates from "in progress." |
| Form response notification system (in progress) | Not implemented yet; no tests exist for the roadmap placeholder.【F:app/docs/features/form-notifications-implementation.md†L1-L40】 | None | None | Ship the feature and its service/UI layers, then add backend, frontend, and integrated tests alongside delivery. |

## Immediate testing roadmap

1. **Stabilise backend coverage for legacy gaps.** Prioritise CSV import/export, vendor quotes, planner metrics, and category CRUD so every shipped capability has service or API regression tests before adding new UI automation.【e854dc†L1-L2】【a8d3eb†L1-L64】
2. **Introduce feature-level Playwright journeys.** Once backend gaps close and the remaining audited items ship, create Playwright specs per feature to exercise SaaS → admin navigation, authentication, primary workflows, and accessibility assertions using the existing config scaffold.【fb4e63†L1-L68】
3. **Track parity in the roadmap.** Update the feature audit when new tests land so "fully delivered" items also meet the integrated QA definition (backend + frontend + E2E) before marketing them as complete.【F:app/docs/features/FEATURE_STATUS_AUDIT.md†L7-L94】

This plan keeps us in the auditing stage until all 13 capabilities have backend coverage and at least one
frontend/integration path, after which we can begin implementing the outstanding features with confidence in
regression protection.
