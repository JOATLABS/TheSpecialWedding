# Storefront Production Acceptance Matrix

This matrix is the implementation and sign-off source of truth for the
production storefront gap closure started on 2026-07-15. A row is complete
only when its automated checks and visible-browser evidence both exist.

## Invariants

- `storefront_settings` is authoritative for slug, design, content visibility,
  and publication.
- `storefront_domains` is authoritative for the planner-owned custom-domain
  lifecycle; Cloudflare is an external projection.
- The platform slug remains available independently of custom-domain setup.
- Custom-domain operations never publish, unpublish, change a slug, or mutate a
  subscription.
- New setup and activation require current capabilities. The owner may inspect
  and disconnect an existing mapping after entitlement loss; entitlement loss
  alone never deletes or disables an active mapping.
- A provider callback is not activation proof. Ownership TXT, routing CNAME,
  Cloudflare hostname, SSL, and HTTPS routing are verified independently.
- Customer DNS credentials and broad provider API tokens are never requested or
  stored.

## Current evidence snapshot

The current source-bound deterministic receipt is run `2c2262cbb4d6` at
`testbed/.testbed/artifacts/storefront/runs/2c2262cbb4d6/run-manifest.json`.
It records `automated_chromium=PASSED`, `persistence=PASSED`,
`account_and_subscription_immutability=PASSED`,
`deterministic_provider_control_plane=PASSED`, and `cleanup=PASSED`.
Playwright ran the ten exact required test/project pairs with zero unexpected or
flaky results, retained 27 run-bound scenario receipts, and sealed the artifacts
after the isolated runtime stopped.

The command intentionally exited nonzero with `EvidenceCoverageIncomplete`
because scenario 4 still lacks a configured object-storage upload/finalize/render
receipt and scenario 14 lacks an independently authoritative customer zone plus
scoped Cloudflare for SaaS credentials. `in_app_chrome_playback=NOT RUN` also
remains open. The deterministic receipt proves the application/browser state
machine; it is not live R2, Resend, Cloudflare, Domain Connect onboarding, public
certificate, or independent DNS-provider evidence.

The focused configuration contract currently passes with:

```bash
PYTHONPATH=. .venv.nosync/bin/python -m pytest \
  tests/backend/test_storefront_production_configuration.py -q
```

That focused result does not replace browser, provider, cleanup, or visible
playback evidence.

## Acceptance matrix

`Current status` is the overall sign-off status, not a statement that code or a
focused test is absent. Because this matrix requires both automated and visible
evidence, current-source rows remain `NOT RUN` until the clean rerun and visible
in-app Chrome review are recorded. The independent provider row remains
`BLOCKED`.

| Area | Required behavior | Automated evidence required | Visible-browser evidence required | Current status | Current receipt or blocker |
| --- | --- | --- | --- | --- | --- |
| Access | Backend returns independent storefront/domain capabilities; restricted planners receive upgrade UX without loading settings | Backend entitlement/API tests and frontend transport contract | Restricted and eligible planner flows | `NOT RUN` | Run `2c2262cbb4d6` automated receipt passed; separate in-app Chrome playback pending |
| Preview | Save-for-preview and Preview use the internal slug without DNS | API/unit tests | Saved draft opens at `/storefront/{slug}?preview=1` | `NOT RUN` | Run `2c2262cbb4d6` saved and reopened the internal-slug preview; separate playback pending |
| Publication | Draft is not public; publish/unpublish changes only storefront visibility | Backend service/API tests | Draft 404, publish visible, unpublish 404 | `NOT RUN` | Run `2c2262cbb4d6` passed the complete publication lifecycle; separate playback pending |
| Public content | Only active non-template packages and published reviews render | Backend service tests with positive and negative fixtures | Storefront package/review inspection | `NOT RUN` | Run `2c2262cbb4d6` passed positive and same-owner/foreign negative fixtures; separate playback pending |
| Media | Presigned upload, validation, finalize, replacement, cancellation, and recovery are owner-scoped | Backend/media and frontend lifecycle tests | Hero/about upload and preview | `BLOCKED` | Browser selection/decoding and slug preview passed; configured R2 upload/finalize/persist/render receipt is absent |
| Inquiry | Validation, persistence, idempotency/rate limits, notification, and recovery are honest | Backend inquiry tests | Public form success and failure states | `NOT RUN` | Deterministic browser and durable retry receipt passed; live Resend remains externally blocked and playback is pending |
| Domain preflight | Normalize IDNA, reject platform/apex hosts, discover authoritative DNS provider, inspect conflicts, and report auto/manual capability | DNS/preflight service and API tests | Invalid, apex, detected, and unknown-provider states | `NOT RUN` | Run `2c2262cbb4d6` automated receipt passed; separate playback pending |
| Domain claim | Every attempt uses a fresh expiring TXT challenge; stale DNS cannot transfer ownership | Claim/state-machine tests | Manual record instructions and conflict state | `NOT RUN` | Fresh private claim and non-transfer receipt passed; separate playback pending |
| Domain Connect | Signed provider authorization is capability-gated; callback never activates; the one-time completion POST rejects ambient-cookie-only requests and replay; DNS is rechecked | Signing, discovery, Bearer/CSRF boundary, callback, replay, and API tests | Supported, unsupported, cancelled, and resumed flows | `NOT RUN` | Consumed `authorized` and `cancelled` outcomes passed deterministically; real provider authorization remains `BLOCKED` and playback is pending |
| Cloudflare lifecycle | Create occurs only after claim proof; raw hostname/SSL states remain separate; ambiguous creates reconcile safely | Cloudflare/state-machine/recovery tests | Pending hostname, pending SSL, active, and operator-review states | `NOT RUN` | Deterministic adapter lifecycle passed; live Cloudflare remains `BLOCKED` and playback is pending |
| Migration | Existing routing is not overwritten before prevalidation/cutover readiness | Migration state tests | Assisted-migration warning and cutover step | `NOT RUN` | Deterministic provider-mutation snapshot passed; external migration and separate playback remain open |
| Disconnect | Deletion intent, exact provider deletion, receipt/tombstone, retry, and DNS cleanup instructions; slug/publication unchanged | Lifecycle/recovery tests | Confirmation, failure/retry, and cleanup instructions | `NOT RUN` | Run `2c2262cbb4d6` passed retry, provider deletion, tombstone, slug/publication continuity, and cleanup; playback pending |
| Existing-owner diagnostics | Entitlement loss blocks new activation but preserves owner-scoped status, authoritative DNS observation, and disconnect without provider creation | Entitlement-loss/worker regressions | Existing-domain diagnostics with setup controls hidden | `NOT RUN` | Deterministic lifecycle passed; separate playback pending |
| Rollout and rollback | Exact owner/hostname allowlists fence claim, provider create/retry, and Domain Connect; rollback stops onboarding while cleanup remains enabled | Policy/config/provider-client tests | Pilot-unavailable state keeps the platform URL usable | `NOT RUN` | Focused checks are supporting evidence only; browser proof pending |
| Operator resolution | Root-admin-only, revision-fenced, audited decisions resolve assisted cutover, verified conflict denial/cancel, and demonstrably new ambiguous provider IDs without force-transfer | Operator authorization/CAS/replay tests | Customer remains in honest support-required state until resolution | `NOT RUN` | Operator runbook and visible customer state review pending |
| Operations | Durable deduplicated incidents and bounded backlog/provider metrics cover review, disconnect/certificate failure, provider 429/5xx, and worker backlog | Operational-monitor and worker tests | Support ID shown without raw provider payload | `NOT RUN` | Current-source integrated receipt pending |
| UI/accessibility | Existing design language, readable light/dark text, single scroll region, responsive tabs, focus/keyboard/status semantics | Frontend unit plus axe/browser assertions | Desktop dark/light, 320/375 px, keyboard flow | `NOT RUN` | Run `2c2262cbb4d6` passed light/dark desktop plus 320/375/390 px and keyboard/axe/overflow guards; separate playback pending |
| Configuration | Runtime, `.env.example`, Compose, testbed, and operator guide agree and fail closed only for the unavailable capability | Settings/deployment contract tests and storefront-specific doctor | Friendly configuration-unavailable state | `NOT RUN` | Browser fail-closed copy passed; final configuration doctor and separate playback remain pending |
| External provider | Real authorization, DNS, Cloudflare activation, HTTPS request, disconnect, and cleanup against an independently authoritative disposable zone | Live testbed artifact manifest | Visible live-provider playback | `BLOCKED` | No authorized independent zone lifecycle, Cloudflare receipt, or visible playback |
| Same-zone infrastructure canary | Exact platform-owned fallback, CNAME target, hostname/SSL, HTTPS edge route, and cleanup | Run-bound `storefront_same_zone_canary.py` receipt | Operator inspection only; not a customer flow | `BLOCKED` | Driver implemented; credentials and explicit live authorization are absent |

## Required browser scenarios

These are the exact browser rows in source-bound run `2c2262cbb4d6`. Provider
adapters prove the application state machine but never change an external note
from `BLOCKED`. Scenario 4 is deliberately blocked as a whole even though its
design, real-file selection/decoding, friendly failure, save, and internal-slug
preview browser checks passed: configured object-storage round-trip proof is
still absent.

| # | Required browser proof | Current status | External note |
| --- | --- | --- | --- |
| 1 | Restricted planner sees upgrade UX and no storefront-settings request is sent | `PASSED` | Not provider-dependent |
| 2 | Eligible modal is readable in light/dark desktop and 320/375 px mobile layouts | `PASSED` | Deterministic run also covered 390 px |
| 3 | Keyboard tabs, focus trap, Escape/restoration, announcements, and copy controls work | `PASSED` | Not provider-dependent |
| 4 | Design and media save/preview through the internal slug without DNS | `BLOCKED` | Browser design/file/preview checks passed; live R2 upload/finalize/persist/render proof is `BLOCKED` |
| 5 | Draft 404 → publish → filtered packages/reviews → unpublish | `PASSED` | Not provider-dependent |
| 6 | Inquiry validation, success, duplicate/rate-limit, and delivery-failure states | `PASSED` | Deterministic delivery recovery passed; live Resend delivery is `BLOCKED` |
| 7 | Invalid host, apex, platform host, and provider detection | `PASSED` | Independent authoritative-provider detection is still externally `BLOCKED` |
| 8 | Domain Connect supported/unsupported/cancelled/resumed/callback-without-DNS | `PASSED` | Deterministic consumed outcomes passed; real provider consent is `BLOCKED` |
| 9 | Manual records, provider link, copies, and emailed read-only instructions | `PASSED` | Durable email receipt passed; actual Resend delivery is `BLOCKED` |
| 10 | Missing/wrong/propagated DNS with expected-versus-observed values | `PASSED` | Deterministic DNS passed; independent authoritative DNS is `BLOCKED` |
| 11 | Fresh conflict claim without leaking another planner | `PASSED` | Deterministic privacy/non-transfer receipt passed; external conflict claim is `BLOCKED` |
| 12 | Provider hostname active while SSL pending is not connected | `PASSED` | Deterministic state passed; live Cloudflare state is `BLOCKED` |
| 13 | SSL active while HTTPS route fails is not connected | `PASSED` | Deterministic signed-probe state passed; public certificate/route proof is `BLOCKED` |
| 14 | All five checks pass and the real custom URL opens the exact storefront | `BLOCKED` | Requires authorized independent DNS, Cloudflare, certificate, and HTTPS |
| 15 | Missing platform configuration shows friendly copy and never raw JSON | `PASSED` | Not provider-dependent |
| 16 | Existing-site migration preserves routing before prevalidation/cutover | `PASSED` | Deterministic mutation snapshot passed; live migration proof is `BLOCKED` |
| 17 | Activation does not publish/unpublish or alter subscription/account data | `PASSED` | Account and subscription hashes matched; live provider mutation is `BLOCKED` |
| 18 | Disconnect failure/retry/provider receipt/customer DNS cleanup | `PASSED` | Deterministic deletion/tombstone receipt passed; live provider deletion is `BLOCKED` |
| 19 | Platform slug remains reachable throughout setup and disconnect | `PASSED` | Deterministic receipt passed; separate visible playback remains pending |
| 20 | Same-owner negative package/review fixtures prove filtering | `PASSED` | Not provider-dependent |

## Entry Points And Lifecycle

- Admin entry: `/admin/packages` → storefront modal.
- Admin APIs: `/admin/storefront/access`, settings/preview/media/inquiry
  dependencies, and `/admin/storefront/custom-domain/**`.
- Root-admin review UI: `/admin/platform?tab=storefront`.
- Root-admin review reads:
  `GET /admin/storefront/custom-domain/operator/reviews` and
  `GET /admin/storefront/custom-domain/operator/reviews/{review_id}`.
- Root-admin review decisions:
  `/admin/storefront/custom-domain/operator/o2o/approve`,
  `/admin/storefront/custom-domain/operator/conflict/resolve`, and
  `/admin/storefront/custom-domain/operator/ambiguous-create/adopt`.
- Public entry: `/storefront/{slug}` and exact custom-host resolution.
- Background entry: leader-elected media, inquiry, and domain reconciliation.
- Domain lifecycle: preflight → claim → automatic/manual DNS → ownership →
  provider provisioning → hostname validation → certificate validation → HTTPS
  verification → active → drift/retry → explicit disconnect → tombstone.

## Evidence Status Values

Use only `PASSED`, `FAILED`, `BLOCKED`, or `NOT RUN`. Same-zone, mocked, unit,
scripted, or prior-session evidence must not be relabelled as an independent
external-provider pass.

`deterministic` means the real frontend, FastAPI routes, services, and isolated
Mongo state machine running against deterministic provider adapters. It is
valid application-lifecycle evidence only. It is never proof of a customer DNS
provider, Cloudflare account, public certificate, or independent authoritative
zone.
