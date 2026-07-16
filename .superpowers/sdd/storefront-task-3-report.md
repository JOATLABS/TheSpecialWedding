# Storefront Task 3 Report — Domain Connect and Provider Recovery

## Status

`DONE_WITH_CONCERNS`

The assigned backend lifecycle is implemented and its focused deterministic
suite is green. This is not a production-complete claim: no live customer DNS,
Cloudflare for SaaS hostname, certificate, or externally approved Domain
Connect template was exercised by this task, and the cross-owner hostname
dispute flow remains an explicit code gap.

## Anti-drift check

The work stayed on the requested production custom-domain backend: customer
authorization, authoritative DNS proof, provider provisioning and observation,
migration cutover, retries, disconnect compensation, and owner-scoped recovery.
It did not change storefront publication or downgrade/unpublish any planner. It
did not claim frontend validation, environment readiness, external provider
approval, or live DNS success.

## Official-source findings applied

- [Cloudflare Domain Connect](https://developers.cloudflare.com/dns/reference/domain-connect/)
  requires Cloudflare onboarding, synchronous signed requests, a published
  public key, and the signature as the final query parameter. The backend uses
  RS256, one-time expiring flow state, server-owned redirects, exact live
  discovery support, and leaves automatic setup unavailable until discovery is
  positive. Repository code cannot truthfully substitute for Cloudflare's
  external onboarding.
- [Cloudflare hostname validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/)
  separates hostname ownership (`status`) from certificate validation
  (`ssl.status`) and requires both plus DNS targeting for production. The
  persisted lifecycle and public DTO keep ownership, routing, provider
  hostname, certificate, and signed HTTPS proof as separate gates.
- [Cloudflare pre-validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/pre-validation/)
  documents that Orange-to-Orange, where the customer's authoritative DNS is
  already Cloudflare, cannot use the standard pre-validation migration flow and
  may route immediately when activated. Such migration preflight now fails
  closed with `cloudflare_o2o_migration_requires_assistance`; new-hostname
  Domain Connect remains eligible.
- [Cloudflare validation status](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/validation-status/)
  says production readiness requires custom-hostname active, SSL active, and
  DNS targeting. The reconciliation worker cannot mark a domain active without
  those observations plus application ownership and HTTPS route attestation.
- [Resend's domain verification API](https://resend.com/docs/api-reference/domains/verify-domain)
  and [verification troubleshooting flow](https://resend.com/docs/knowledge-base/what-if-my-domain-is-not-verifying)
  use asynchronous verification, visible per-record failures, propagation
  waiting, and an explicit restart action. This supports the implemented split
  between read-only observation and a throttled provider retry; refresh is not
  treated as proof or mutation.
- [Resend's cross-team Claim Domain API](https://resend.com/docs/api-reference/domains/claim-domain)
  creates a separate placeholder and TXT challenge when a domain is already
  owned by another team. Our current cross-owner path does not yet provide an
  equivalent separate claim object; it returns a non-leaking 409. This remains
  a concrete gap rather than a false-positive completion claim.
- [Firebase App Hosting custom domains](https://firebase.google.com/docs/app-hosting/custom-domain)
  distinguishes a new domain from a live migration, shows every required DNS
  record, separates setup/certificate/connected states, and warns that DNS
  update ordering is required to prevent downtime. The backend now preserves
  `new` versus `migration`, withholds the routing CNAME during migration
  pre-validation, exposes provider and certificate validation records, and
  enters `cutover_ready` before customer routing changes.
- [Google Cloud Run domain mapping](https://docs.cloud.google.com/run/docs/mapping-custom-domains)
  requires ownership verification followed by provider-side DNS changes and
  explicitly says its native mapping is not production-ready. It was used as a
  workflow comparison, not selected as this platform's production provider.

## Backend outcomes

- Safe Domain Connect discovery rejects unsafe schemes, hosts, redirects,
  rebinding/private targets, oversized responses, and unsupported template
  versions; provider authorization is currently allowlisted to Cloudflare.
- Signed synchronous authorization uses RS256 with a 2048-bit-or-greater key,
  a one-time 256-bit token digest, TTL, owner scope, and callback/completion
  separation. Callback authorization never proves DNS.
- Manual setup returns application ownership, provider ownership, certificate
  validation, and routing records with provider-specific relative host/proxy
  guidance. It also returns an expiring read-only instruction page contract for
  delegation to a customer's DNS administrator.
- Authoritative DNS checks query the delegated nameservers directly and fail
  closed on disagreement. Recursive DNS is used only to resolve public
  nameserver addresses; private and non-global targets are rejected.
- New hostnames and live migrations are separate lifecycles. Migrations verify
  ownership and provision hostname/certificate readiness before exposing the
  routing CNAME. Cloudflare-to-Cloudflare live migration is routed to assisted
  handling instead of pretending zero-downtime pre-validation is available.
- Read-only `observe` and provider-mutating `retry` are separate operations.
  Retry preserves the original SSL method/type and is throttled.
- The leased reconciliation worker covers authorization expiry/cancel,
  ambiguous provider create adoption, DNS/provider/SSL/HTTPS observation,
  jittered backoff, two-observation routing drift, and every disconnect cleanup
  stage.
- Reconciliation writes use lease token, exact revision, and exact deletion
  status comparisons. Stale observation, release, authorization, activation,
  and provider-adoption writes lose to a concurrent disconnect.
- Disconnect disables only the custom route before provider I/O, preserves the
  platform storefront, persists retryable provider failures, and leaves durable
  cleanup/tombstone receipts.
- Authoritative DNS provider and registrar are not conflated. The DNS provider
  and its control-panel URL are returned when detectable; registrar remains
  explicitly `unknown` until a bounded RDAP integration exists.

## Files changed in Task 3 scope

- `app/constants/storefront_domain.py`
- `app/api/storefront.py`
- `app/models/storefront.py`
- `app/services/storefront_dns_service.py`
- `app/services/storefront_domain_connect_service.py`
- `app/services/storefront_domain_reconciliation_service.py`
- `app/services/storefront_domain_service.py`
- `tests/backend/test_storefront_domain_connect.py`
- `tests/backend/test_storefront_domain_reconciliation.py`
- `tests/backend/test_storefront_domain_claims.py`
- `tests/backend/test_storefront_domain_service.py`
- `tests/backend/test_storefront_api_contract.py`
- `.superpowers/sdd/storefront-task-3-report.md`

The shared checkout contains concurrent storefront changes from sibling tasks.
This report does not attribute their frontend, configuration, documentation,
edge-probe, index, or testbed work to Task 3.

## TDD and verification evidence

### RED

The first expanded lifecycle batch was observed failing before implementation:

```text
159 collected; 140 passed; 19 failed
```

The final provider-specific correction was also demonstrated red first:

```text
PYTHONPATH=. .venv.nosync/bin/pytest \
  tests/backend/test_storefront_domain_claims.py::test_preflight_fails_closed_for_cloudflare_o2o_migration -q

1 failed: expected HTTPException, but preflight allowed the unsafe O2O migration
```

### GREEN — focused backend domain regression suite

```text
PYTHONPATH=. .venv.nosync/bin/pytest \
  tests/backend/test_storefront_domain_connect.py \
  tests/backend/test_storefront_domain_reconciliation.py \
  tests/backend/test_storefront_domain_claims.py \
  tests/backend/test_storefront_domain_service.py \
  tests/backend/test_storefront_api_contract.py \
  tests/backend/test_storefront_indexes.py \
  tests/backend/test_storefront_service.py -q

194 passed in 3.60s
```

### GREEN — lint and formatting

```text
.venv.nosync/bin/ruff check <13 Task 3 Python files>
All checks passed!

.venv.nosync/bin/ruff format --check <13 Task 3 Python files>
13 files already formatted
```

## Remaining concerns and blockers

1. **Cross-owner hostname conflict claims are not implemented.** A second
   owner receives `hostname_reserved` without learning the existing owner, but
   cannot start a fresh, separately stored, expiring TXT challenge like
   Resend's official claim flow. The safe follow-up is an append-only
   `storefront_domain_conflict_claims` lifecycle with claimant owner scope,
   encrypted token plus digest/TTL, authoritative proof, and operator review
   for active, recently routed, or deletion-ambiguous domains. It must never
   silently reassign the authoritative `storefront_domains` row.
2. **Automatic setup is not externally approved or live-proven.** Cloudflare
   must accept and publish the Domain Connect template and public-key domain.
   Until exact discovery returns it, the product must keep automatic setup
   hidden and offer manual setup.
3. **No live provider lifecycle was exercised.** This task did not create,
   validate, retry, activate, or delete a real Cloudflare custom hostname, nor
   change `thespecialwedding.com` DNS. Fallback-origin readiness, SaaS target,
   certificate issuance, account entitlements, quotas, and deletion receipts
   still need production-like provider evidence.
4. **Registrar detection is intentionally incomplete.** The system identifies
   authoritative DNS hosting from delegated nameservers but returns registrar
   as `unknown`. A bounded, cached RDAP lookup with timeout/privacy policy is a
   follow-up if registrar-specific guidance is required.
5. **Authoritative DNS transport lacks retained live-domain proof.** Unit tests
   use deterministic injected resolvers. A non-mutating testbed scenario should
   query a controlled public zone and retain authoritative observations before
   deployment sign-off.
6. **Frontend and environment proof are outside this task.** No modal layout,
   contrast, responsive behavior, browser E2E, environment-secret deployment,
   or setup-guide claim is made here. Those must be validated by their owning
   tasks and the visible testbed flow before the overall feature is called
   production-ready.
7. No commit was created.
