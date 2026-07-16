# Production Storefront Gap-Closure Progress

Canonical acceptance source:
`docs/guides/STOREFRONT_PRODUCTION_ACCEPTANCE_MATRIX.md`

Operator contract:
`docs/guides/STOREFRONT_INFRASTRUCTURE_SETUP.md`

The earlier `docs/superpowers/plans/2026-07-12-storefront-production-hardening.md`
is superseded and is not acceptance evidence.

Active objective: implement and visibly validate canonical storefront
capabilities, internal-slug preview, publication/content/media/inquiries, the
production custom-domain lifecycle, environment/operator guidance, and
reproducible frontend testbed evidence without changing subscription or account
data.

Anti-drift gate:

> “Evaluate the work you have done; are you drifting away from the fucking goal
> or are you still on task?”

## Completed

- The current checkout contains backend-owned storefront/custom-domain
  capability resolution and keeps custom-domain operations separate from slug,
  publication, and subscription state.
- The current checkout contains the claim-first domain lifecycle, Domain Connect
  flow records, authoritative-DNS observation, Cloudflare projection,
  reconciliation worker, operator-review APIs, instruction links, operations,
  tombstones, rollout allowlists, and independently gated cleanup.
- The storefront modal is organized around Design, Content & publish, and Domain
  workflows, with internal-slug preview kept independent from DNS.
- `.env.example`, production Compose, and the testbed example expose the
  storefront runtime variables. The focused configuration contract currently
  passes; that is supporting evidence only.
- A source-bound deterministic Playwright harness exists under `testbed/` and
  uses the real production frontend build, FastAPI routes/services, and isolated
  Mongo with deterministic provider adapters. Its existence is not a passing
  run.

## Remaining

- Run a fresh source-bound production frontend build and deterministic
  Playwright lifecycle after the latest fixes. Require Playwright JSON/JUnit/
  HTML, trace, video, screenshots, a hashed manifest, and successful cleanup.
- Perform and record the separate visible playback in the user-selected in-app
  Chrome browser. Automated screenshots do not satisfy this gate.
- Add a storefront-specific read-only operator doctor that checks cross-field
  Domain Connect configuration, rollout allowlists, Cloudflare/R2/Resend
  dependency readiness, and external-evidence receipts. The general
  `testbed/testbed.py doctor` command does not perform those checks.
- Reconcile every acceptance-matrix row with the new run manifest and visible
  playback before changing any internal row to `PASSED`.
- Record fresh focused backend/frontend/quality commands after all shared-file
  edits settle. Do not carry forward historical counts as current proof.

## Blocked

- Independently authoritative customer-zone proof is `BLOCKED`: no authorized
  real DNS-provider consent-to-disconnect lifecycle has been run.
- Live Cloudflare for SaaS fallback-origin/CNAME/custom-hostname/certificate/
  HTTPS and cleanup receipts are `BLOCKED` pending approved disposable
  infrastructure and credentials.
- Domain Connect automatic setup is `BLOCKED` pending public-key publication,
  official template acceptance, Cloudflare onboarding, exact discovery support,
  and a restricted real-account consent lifecycle.
- Live storefront R2 upload/finalize/privacy/lifecycle evidence and Resend
  delivery evidence are `BLOCKED` pending environment-scoped provider
  authorization.
- A same-zone canary, if later run, will not unblock the independent-provider
  row; the independently authoritative customer zone is a separate requirement.

## Failed evidence retained

- `testbed/.testbed/artifacts/storefront/runs/0bec60e8271d/run-manifest.json`
  records `automated_chromium=FAILED`, `cleanup=FAILED`,
  `in_app_chrome_playback=NOT RUN`, and `live_provider=BLOCKED`. It cannot be
  promoted to acceptance evidence. Post-run fixes require a new build-bound run.

## Out of scope

- subscription downgrade or mutation
- automatic storefront unpublish
- unrelated Redis, billing, account, or product work
- treating deterministic adapters, screenshots, mocked DNS, or same-zone DNS as
  independent-provider proof
