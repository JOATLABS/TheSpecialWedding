# Task 1 — Canonical storefront domain claim and manual verification

## Context

This is the first implementation slice of the 2026-07-15 production storefront
gap closure. The existing custom-domain service reserves a hostname and calls
Cloudflare immediately. Replace that unsafe entry path with an owner-scoped,
expiring application ownership claim that both manual DNS and later Domain
Connect automation must use.

Preserve the existing dirty storefront changes and the working provider
compensation/reconciliation logic unless this task explicitly strengthens it.
Do not edit subscription records, storefront publication, slug state, public
package/review/media/inquiry logic, or unrelated files.

## Required behavior

1. Add typed request/response contracts and routes under
   `/admin/storefront/custom-domain` for:
   - `POST /preflight`
   - `POST /claim`
   - `POST /verify`
   - local-only `GET /status`
   - explicit `DELETE /`
2. Keep the legacy `POST /admin/storefront/custom-domain` source-compatible,
   but make it create/resume the manual claim. It must not create a Cloudflare
   hostname before verified ownership.
3. Preflight must:
   - normalize IDNA and reject unsafe/platform hostnames;
   - identify apex versus subdomain and reject apex self-service;
   - accept intent `new` or `migration`;
   - inspect NS, A, AAAA, CNAME, CAA, and TXT through an injected DNS resolver;
   - return authoritative DNS provider evidence, conflicts, expected records,
     and recommended `manual`/`assisted_migration` flow;
   - perform no Cloudflare mutation.
4. Claim must:
   - require the current custom-domain capability;
   - reserve one normalized hostname per owner and owner per hostname;
   - create a cryptographically random 256-bit challenge with a seven-day
     expiry;
   - use `_tsw-storefront.<hostname>` TXT
     `tsw-verification=<token>` plus `<hostname>` CNAME to the configured target;
   - store encrypted token material plus a digest; never store plaintext;
   - rotate token/attempt identity for a new expired/released attempt;
   - return the record values needed for manual setup.
5. Verify must query DNS independently. Missing, mismatched, expired, or stale
   TXT proof remains `dns_setup_pending`/`action_required` and never calls
   Cloudflare. Exact current TXT proof marks ownership verified and invokes the
   existing Cloudflare create path at most once through owner/revision CAS.
6. Preserve independent application, provider-hostname, SSL, routing-DNS, and
   HTTPS check fields. Do not collapse all pending/error states into one opaque
   value. Actual HTTPS checking may remain pending for the later worker slice,
   but cannot be reported passed without evidence.
7. An ambiguous create may not adopt a pre-existing exact Cloudflare row. Store
   a pre-create provider-ID snapshot and adopt only one demonstrably new ID for
   the current attempt. Otherwise enter `operator_review`.
8. `GET /status` is a durable local read and makes no provider call. Owner status
   and explicit disconnect remain accessible after entitlement loss when a row
   already exists. New claim, ownership activation, and provider creation remain
   entitlement-gated.
9. Disconnect records deletion intent, performs exact provider deletion where a
   provider ID exists, and persists a 90-day tombstone/deletion receipt instead
   of erasing all lifecycle evidence. It never changes subscription,
   publication, or slug state.
10. Add collections/indexes needed now for domain operations, retry due/lease,
    and tombstones. Names must be stable and tests must prove uniqueness/TTL.
11. Errors must use a stable structured envelope with code, message,
    customer_action, retryable, support_id, and optional field/provider details.
    No raw Cloudflare JSON belongs in customer messages.
12. Retain current owner-scope/tenant checks and compare-and-swap fences.

## TDD and verification contract

- Write focused failing tests first and run them to the expected failure before
  production changes.
- Cover at least: claim without Cloudflare call, cross-tenant collision, stale
  CNAME rejection, missing/mismatched/expired/rotated TXT, exact proof, verify
  idempotency, callback-shaped input not proving DNS, unsafe ambiguous adoption,
  status/disconnect after entitlement loss, and durable indexes/tombstone.
- Prefer a new focused DNS verification test module plus existing storefront
  domain/API/index tests.
- Run the focused backend suite with
  `PYTHONPATH=. .venv.nosync/bin/pytest ... -q` and report exact counts.
- Do not commit. This is a shared dirty checkout.
- Before handoff, inspect the diff as a hostile reviewer and report all
  remaining Task 1 gaps honestly.

## Report

Write the full report to
`.superpowers/sdd/storefront-task-1-report.md` and return only status, changed
files, red/green commands and counts, and concerns.
