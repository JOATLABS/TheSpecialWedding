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

The current checkout has **no accepted storefront completion receipt**. The most
recent retained deterministic run, `0bec60e8271d`, recorded
`automated_chromium=FAILED`, `cleanup=FAILED`,
`in_app_chrome_playback=NOT RUN`, and `live_provider=BLOCKED` in
`testbed/.testbed/artifacts/storefront/runs/0bec60e8271d/run-manifest.json`.
Those failures are evidence, not passes. Changes made after that run require a
new source-bound build and run before any internal row can move to `PASSED`.

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
| Access | Backend returns independent storefront/domain capabilities; restricted planners receive upgrade UX without loading settings | Backend entitlement/API tests and frontend transport contract | Restricted and eligible planner flows | `NOT RUN` | Post-fix source-bound browser rerun and visible playback pending |
| Preview | Save-for-preview and Preview use the internal slug without DNS | API/unit tests | Saved draft opens at `/storefront/{slug}?preview=1` | `NOT RUN` | Post-fix source-bound browser rerun and visible playback pending |
| Publication | Draft is not public; publish/unpublish changes only storefront visibility | Backend service/API tests | Draft 404, publish visible, unpublish 404 | `NOT RUN` | Post-fix source-bound browser rerun and visible playback pending |
| Public content | Only active non-template packages and published reviews render | Backend service tests with positive and negative fixtures | Storefront package/review inspection | `NOT RUN` | Post-fix source-bound browser rerun and visible playback pending |
| Media | Presigned upload, validation, finalize, replacement, cancellation, and recovery are owner-scoped | Backend/media and frontend lifecycle tests | Hero/about upload and preview | `NOT RUN` | Local browser rerun pending; live R2 lifecycle remains externally blocked |
| Inquiry | Validation, persistence, idempotency/rate limits, notification, and recovery are honest | Backend inquiry tests | Public form success and failure states | `NOT RUN` | Local browser rerun pending; live Resend delivery remains externally blocked |
| Domain preflight | Normalize IDNA, reject platform/apex hosts, discover authoritative DNS provider, inspect conflicts, and report auto/manual capability | DNS/preflight service and API tests | Invalid, apex, detected, and unknown-provider states | `NOT RUN` | Post-fix deterministic rerun and visible playback pending |
| Domain claim | Every attempt uses a fresh expiring TXT challenge; stale DNS cannot transfer ownership | Claim/state-machine tests | Manual record instructions and conflict state | `NOT RUN` | Post-fix deterministic rerun and visible playback pending |
| Domain Connect | Signed provider authorization is capability-gated; callback never activates; the one-time completion POST rejects ambient-cookie-only requests and replay; DNS is rechecked | Signing, discovery, Bearer/CSRF boundary, callback, replay, and API tests | Supported, unsupported, cancelled, and resumed flows | `NOT RUN` | Deterministic rerun pending; real provider authorization remains `BLOCKED` |
| Cloudflare lifecycle | Create occurs only after claim proof; raw hostname/SSL states remain separate; ambiguous creates reconcile safely | Cloudflare/state-machine/recovery tests | Pending hostname, pending SSL, active, and operator-review states | `NOT RUN` | Deterministic rerun pending; live Cloudflare lifecycle remains `BLOCKED` |
| Migration | Existing routing is not overwritten before prevalidation/cutover readiness | Migration state tests | Assisted-migration warning and cutover step | `NOT RUN` | Post-fix deterministic rerun and visible playback pending |
| Disconnect | Deletion intent, exact provider deletion, receipt/tombstone, retry, and DNS cleanup instructions; slug/publication unchanged | Lifecycle/recovery tests | Confirmation, failure/retry, and cleanup instructions | `NOT RUN` | Latest retained run failed cleanup; post-fix rerun required |
| Existing-owner diagnostics | Entitlement loss blocks new activation but preserves owner-scoped status, authoritative DNS observation, and disconnect without provider creation | Entitlement-loss/worker regressions | Existing-domain diagnostics with setup controls hidden | `NOT RUN` | Post-fix deterministic rerun and visible playback pending |
| Rollout and rollback | Exact owner/hostname allowlists fence claim, provider create/retry, and Domain Connect; rollback stops onboarding while cleanup remains enabled | Policy/config/provider-client tests | Pilot-unavailable state keeps the platform URL usable | `NOT RUN` | Focused checks are supporting evidence only; browser proof pending |
| Operator resolution | Root-admin-only, revision-fenced, audited decisions resolve assisted cutover, verified conflict denial/cancel, and demonstrably new ambiguous provider IDs without force-transfer | Operator authorization/CAS/replay tests | Customer remains in honest support-required state until resolution | `NOT RUN` | Operator runbook and visible customer state review pending |
| Operations | Durable deduplicated incidents and bounded backlog/provider metrics cover review, disconnect/certificate failure, provider 429/5xx, and worker backlog | Operational-monitor and worker tests | Support ID shown without raw provider payload | `NOT RUN` | Current-source integrated receipt pending |
| UI/accessibility | Existing design language, readable light/dark text, single scroll region, responsive tabs, focus/keyboard/status semantics | Frontend unit plus axe/browser assertions | Desktop dark/light, 320/375 px, keyboard flow | `NOT RUN` | Latest retained run failed contrast; post-fix rerun and visible review required |
| Configuration | Runtime, `.env.example`, Compose, testbed, and operator guide agree and fail closed only for the unavailable capability | Settings/deployment contract tests and storefront-specific doctor | Friendly configuration-unavailable state | `NOT RUN` | Focused config test passes; storefront dependency doctor and visible state remain pending |
| External provider | Real authorization, DNS, Cloudflare activation, HTTPS request, disconnect, and cleanup against an independently authoritative disposable zone | Live testbed artifact manifest | Visible live-provider playback | `BLOCKED` | No authorized independent zone lifecycle, Cloudflare receipt, or visible playback |
| Same-zone infrastructure canary | Exact platform-owned fallback, CNAME target, hostname/SSL, HTTPS edge route, and cleanup | Run-bound `storefront_same_zone_canary.py` receipt | Operator inspection only; not a customer flow | `NOT RUN` | Driver implemented; credentials and explicit live authorization are absent |

## Required browser scenarios

These are the exact browser rows that must appear in the source-bound run
manifest. `NOT RUN` means the post-fix current checkout has no accepted receipt;
it does not promote a result from `0bec60e8271d`. Provider adapters may prove the
application state machine but never change an external note from `BLOCKED`.

| # | Required browser proof | Current status | External note |
| --- | --- | --- | --- |
| 1 | Restricted planner sees upgrade UX and no storefront-settings request is sent | `NOT RUN` | Not provider-dependent |
| 2 | Eligible modal is readable in light/dark desktop and 320/375 px mobile layouts | `NOT RUN` | Not provider-dependent |
| 3 | Keyboard tabs, focus trap, Escape/restoration, announcements, and copy controls work | `NOT RUN` | Not provider-dependent |
| 4 | Design and media save/preview through the internal slug without DNS | `NOT RUN` | Live R2 upload/finalize proof is `BLOCKED` |
| 5 | Draft 404 → publish → filtered packages/reviews → unpublish | `NOT RUN` | Not provider-dependent |
| 6 | Inquiry validation, success, duplicate/rate-limit, and delivery-failure states | `NOT RUN` | Live Resend delivery is `BLOCKED` |
| 7 | Invalid host, apex, platform host, and provider detection | `NOT RUN` | Independent authoritative-provider detection is `BLOCKED` |
| 8 | Domain Connect supported/unsupported/cancelled/resumed/callback-without-DNS | `NOT RUN` | Real provider consent is `BLOCKED` |
| 9 | Manual records, provider link, copies, and emailed read-only instructions | `NOT RUN` | Actual Resend delivery is `BLOCKED` |
| 10 | Missing/wrong/propagated DNS with expected-versus-observed values | `NOT RUN` | Independent authoritative DNS is `BLOCKED` |
| 11 | Fresh conflict claim without leaking another planner | `NOT RUN` | External conflict claim is `BLOCKED` |
| 12 | Provider hostname active while SSL pending is not connected | `NOT RUN` | Live Cloudflare state is `BLOCKED` |
| 13 | SSL active while HTTPS route fails is not connected | `NOT RUN` | Public certificate/route proof is `BLOCKED` |
| 14 | All five checks pass and the real custom URL opens the exact storefront | `BLOCKED` | Requires authorized independent DNS, Cloudflare, certificate, and HTTPS |
| 15 | Missing platform configuration shows friendly copy and never raw JSON | `NOT RUN` | Not provider-dependent |
| 16 | Existing-site migration preserves routing before prevalidation/cutover | `NOT RUN` | Live migration proof is `BLOCKED` |
| 17 | Activation does not publish/unpublish or alter subscription/account data | `NOT RUN` | Live provider mutation is `BLOCKED` |
| 18 | Disconnect failure/retry/provider receipt/customer DNS cleanup | `NOT RUN` | Live provider deletion is `BLOCKED` |
| 19 | Platform slug remains reachable throughout setup and disconnect | `NOT RUN` | Must pass deterministic and visible playback |
| 20 | Same-owner negative package/review fixtures prove filtering | `NOT RUN` | Not provider-dependent |

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
