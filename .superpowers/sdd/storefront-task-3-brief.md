# Task 3 — Domain Connect, provider reconciliation, and background recovery

## Context

Build the automatic DNS authorization adapter and durable recovery worker on
top of Task 1's claim/manual-verification invariant. Automatic setup is a
customer-authorized DNS-provider redirect; it never receives customer DNS
credentials and never bypasses authoritative DNS proof.

## Required behavior

1. Add safe `_domainconnect` discovery and exact template-version support
   queries. HTTPS/443 only; reject credentials/fragments/IP literals and
   loopback/private/link-local/multicast/reserved/internal destinations;
   revalidate DNS and every redirect, cap redirects/response size/timeouts, and
   initially allow authorization only for Cloudflare.
2. Add RS256-signed synchronous authorization URLs generated only by the
   backend. Use configured provider/service/template/key IDs and fixed CNAME
   target. Put a one-time 256-bit flow token inside the signed redirect URI
   because Cloudflare ignores `state`; persist only its digest and TTL.
3. Add authorize, callback, and authenticated completion endpoints. Callback
   records authorization/cancellation and 303-redirects to
   `/admin/packages?storefront=domain&attempt=<id>`; it never activates DNS.
   Completion consumes the owner-scoped unexpired flow once and schedules DNS
   verification with existing bearer-auth/Origin protections.
4. Add explicit retry endpoint using Cloudflare's no-change PATCH with original
   SSL method/type, rate limits, and enqueue semantics. Status refresh is not a
   retry.
5. Preserve raw provider/SSL/errors/validation records and map stable app states,
   including `active_redeploying`, blocked/action-required, operator-review,
   deletion, and expiry. Active requires ownership, routing, provider-hostname,
   SSL, and HTTPS evidence.
6. Add a leased, leader-elected domain reconciliation scheduler following the
   existing media/inquiry scheduler patterns. Use due/lease indexes, bounded
   batches, jittered backoff, cleanup retry, ambiguous create reconciliation,
   drift checks, and safe shutdown.
7. Two consecutive routing mismatches separated by at least ten minutes revoke
   only custom-host routing and alert; the platform slug/publication remain
   untouched.
8. Add structured logs/support IDs and durable provider operation receipts. Do
   not include secret tokens or full hostnames in metric labels.
9. Feature flags independently gate discovery, authorization, and Cloudflare
   mutations. Invalid custom-domain configuration must not break slug storefront
   startup.
10. Create the repository Domain Connect template and deterministic validator.
    Automatic setup remains hidden unless live discovery reports exact support;
    no test may mark external approval as passed.

## TDD and verification contract

- Tests first with observed RED, then minimal implementation and GREEN.
- Cover SSRF/rebinding/redirect defenses, exact-template support, signing
  canonicalization, token replay/expiry/owner scope, callback-not-proof,
  cancellation, retry separation/throttle, worker lease/backoff, active
  invariants, drift, and flags.
- Cloudflare and discovery network behavior use injected transports/resolvers.
  Do not mutate live Cloudflare resources in unit tests.
- Run focused backend tests and Ruff on changed Python files; report counts.
- Do not commit. Shared dirty checkout.

## Report

Write `.superpowers/sdd/storefront-task-3-report.md`; return status, changed
files, red/green commands/counts, and concerns only.
