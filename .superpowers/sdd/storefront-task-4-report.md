# Task 4 Report — Storefront production configuration and provider runbook

Date: 2026-07-15

## Outcome

Task 4's configuration, documentation, deterministic template validation, and
contract tests are green. The work does **not** claim that a live customer
domain, Cloudflare for SaaS, Domain Connect, or the R2 upload data path is ready.
Those outcomes require the external receipts listed below.

Anti-drift check: the work stayed on storefront production configuration,
operator/customer domain onboarding, environment contracts, and their tests. It
did not change subscription tiers, downgrade/unpublish a planner, mutate live
DNS, call a provider with customer credentials, or implement unrelated
storefront UI/runtime work.

## Acceptance matrix

| Requirement | Status | Evidence |
| --- | --- | --- |
| Independent typed custom-domain, Domain Connect, and Cloudflare mutation flags | Pass | `Settings` aliases/defaults are pinned by `test_storefront_domain_control_plane_has_typed_independent_feature_flags`. All four flags default false. |
| Dedicated Cloudflare for SaaS token | Pass for configuration/client boundary | `CloudflareService` reads `CLOUDFLARE_SAAS_API_TOKEN`; a test proves `CLOUDFLARE_API_TOKEN` cannot silently enable the custom-hostname client. Runtime mutation-flag enforcement itself is owned by the Task 3 runtime lane (Franklin) after hostile review identified the cross-module call gate. |
| Production Compose/env/testbed parity | Pass | The configuration contract checks every required name in `.env.example`, `testbed/.env.example`, and `docker-compose.production.yml`; production Compose renders successfully. |
| Non-mutating readiness | Pass for Task 4 configuration contract | `get_storefront_domain_readiness()` distinguishes disabled, provider-mutations-disabled, missing, invalid, and ready without calling a provider or touching slug/publication state. |
| Production operator and customer setup guide | Pass | The guide now starts with the real customer journey, exact provider roles, provider-specific manual steps, automatic/manual UX, migration, status, support, retry, disconnect/tombstone, rollback, R2, Resend, and doctor commands. |
| Domain Connect template and key-publication procedure | Locally pass; externally blocked | Candidate template and deterministic validator pass. Online Editor evidence, public-key publication, official repository merge, and provider onboarding are not claimed. |
| Engineering changelog truth | Pass | The changelog records token separation, guide/template work, and all external blockers including the R2 `AccessDenied` state. |

## What changed or was reviewed to completion

- `.env.example`
  - Added/verified every storefront, Domain Connect, R2, and Resend contract
    name.
  - Corrected the legacy `CLOUDFLARE_API_TOKEN` comment: it is R2/established
    control-plane use only, never Cloudflare for SaaS custom-host management.
- local ignored `.env`
  - Added fail-closed feature flags, fixed non-secret production names, safe
    defaults, and blank credential/config placeholders.
  - No secret value was printed, copied from another credential, or invented.
- `app/core/settings.py`
  - Typed aliases for independent domain flags, the dedicated SaaS token, fixed
    origins, platform domains, Domain Connect IDs/version/key/callback, `S3_REGION`,
    and `RESEND_FROM_NAME`.
- `app/services/cloudflare_service.py`
  - Dedicated SaaS token boundary; no silent R2-token fallback.
- `app/services/config_validator.py`
  - Friendly, non-secret, non-mutating domain readiness and partial-config
    recommendations independent from slug/media/inquiry state.
- `docker-compose.production.yml`
  - Passes every runtime setting into the API service.
- `testbed/.env.example`
  - Mirrors safe disabled/default storefront and provider values.
- `domain-connect/templates/thespecialwedding.com.storefront-subdomain.json`
  - Candidate signed, `hostRequired`, subdomain-only TXT+CNAME template targeting
    `domains.thespecialwedding.com`.
- `testbed/validate_storefront_domain_connect_template.py`
  - Deterministic local drift/schema/security checks; it explicitly refuses to
    equate a local pass with repository/provider approval.
- `tests/backend/test_storefront_production_configuration.py`
  - Eight production configuration/template contracts.
- `tests/backend/test_config_validator.py`
  - Updated three stale tests to the separate SaaS token plus fallback-origin
    contract; retained independent R2 token tests.
- `docs/guides/STOREFRONT_INFRASTRUCTURE_SETUP.md`
  - Comprehensive researched production runbook.
- `CHANGELOG.md`
  - Engineering truth and explicit remaining external work.

## Research applied

### Domain Connect and comparable onboarding UX

- [Domain Connect 2.3 specification](https://github.com/Domain-Connect/spec/blob/master/Domain%20Connect%20Spec%20Draft.adoc)
  - Provider discovery uses `_domainconnect`; the DNS provider owns login and
    consent; synchronous and asynchronous flows are distinct; templates and
    providers require onboarding; signed requests publish the public key in DNS.
- [Official Domain Connect templates repository](https://github.com/Domain-Connect/templates)
  - Online Editor evidence, filename/schema rules, `syncPubKeyDomain`, secure
    parameter scoping, and PR review are required.
- [Resend's published Domain Connect template](https://github.com/Domain-Connect/Templates/blob/master/resend.com.mail.json)
  - Concrete automatic-configuration benchmark using a signed, reviewed
    template rather than customer DNS credentials.
- [Google TXT domain-verification flow](https://support.google.com/a/answer/16018515?hl=en)
  - Manual UX benchmark: select a known registrar, provide provider-specific
    instructions, retain a generic host path, copy an exact value, and explicitly
    verify.
- [Google CNAME explanation](https://knowledge.workspace.google.com/admin/domains/about-cname-records?hl=en)
  - Alias/target and DNS-host ownership model used in customer copy.

### Cloudflare for SaaS

- [Initial SaaS configuration](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/getting-started/)
- [Hostname validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/)
- [Common API readiness calls](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/common-api-calls/)
- [Pre-validation and O2O limitation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/pre-validation/)
- [O2O behavior](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/saas-customers/how-it-works/)
- [Custom-hostname API permission](https://developers.cloudflare.com/api/resources/custom_hostnames/methods/create/)
- [Remove custom hostnames](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/remove-custom-hostnames/)

The guide uses the provider's separate hostname, certificate, DNS, and HTTPS
truth. A certificate or successful handshake alone is not accepted as active.

### Manual DNS providers

- [Cloudflare DNS records](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/)
- [GoDaddy CNAME](https://www.godaddy.com/help/add-a-cname-record-19236)
- [Namecheap CNAME](https://www.namecheap.com/support/knowledgebase/article.aspx/9646/2237/how-to-create-a-cname-record-for-your-domain/)
- [Namecheap TXT](https://www.namecheap.com/support/knowledgebase/article.aspx/317/2237/how-do-i-add-txtspfdkimdmarc-records-for-my-domain/)
- [Squarespace DNS records](https://support.squarespace.com/hc/en-us/articles/31119879125645-DNS-records-for-web-hosting)
- [Route 53 record types](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html)

### R2 and Resend

- [R2 CORS API](https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/cors/)
- [R2 lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
- [R2 public-bucket controls](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [Resend domain management](https://resend.com/docs/dashboard/domains/introduction)
- [Resend verification troubleshooting](https://resend.com/docs/knowledge-base/what-if-my-domain-is-not-verifying)

## RED to GREEN evidence

Initial focused gate:

```text
PYTHONPATH=. .venv.nosync/bin/pytest \
  tests/backend/test_storefront_production_configuration.py \
  tests/backend/test_config_validator.py -q

4 failed, 18 passed
```

The failures were the missing production/provider/lifecycle guide contract and
three stale tests expecting the R2 token to authorize custom hostnames.

Final focused gate:

```text
22 passed in 0.45s
```

Additional validation:

```text
Domain Connect deterministic validator: PASS
Ruff on changed Task 4 Python/tests: PASS
docker compose -f docker-compose.production.yml config --quiet: PASS
testbed/testbed.py doctor: PASS (dependencies present; testbed session down)
Node 22 storefront testbed contract: 2/2 PASS
git diff --check on Task 4 files: PASS
```

Compose emitted only pre-existing blank optional Sentry/Umami warnings. It did
not emit a storefront configuration parse error.

## Environment safety receipt

The local `.env` was inspected by variable name and presence only.

- Task 4 custom-domain/Domain Connect plus `S3_REGION`/`RESEND_FROM_NAME` names:
  `18/18` present.
- Intentionally blank: `CLOUDFLARE_SAAS_API_TOKEN`, `CLOUDFLARE_ZONE_ID`, and
  `DOMAIN_CONNECT_PRIVATE_KEY`.
- All four custom-domain/Domain Connect rollout flags are false.
- The fixed non-secret hostnames/IDs and safe R2 concurrency/lifecycle defaults
  are present.
- The storefront staging bucket name remains blank in local `.env`; no live
  bucket name or credential was fabricated.

The existing R2 account/S3/Resend values were checked only as present/nonempty;
their values were not printed. External evidence from the live setup lane says
the storefront staging bucket exists and its controls are configured, but the
existing S3 access credential returns `AccessDenied` for the bucket. A new or
expanded bucket-scoped Object Read & Write credential is required before media
runtime can be called ready.

## Hostile review findings

1. The previous guide conflated R2 and Cloudflare for SaaS token permissions.
   Corrected in `.env.example`, tests, and the runbook.
2. The previous UX model reduced a production domain lifecycle to one text box
   and raw errors. The guide now requires a dedicated Domain journey, provider
   detection, automatic/manual branching, exact record UX, migration review,
   staged status, support IDs, and safe disconnect.
3. Automatic Domain Connect could have been falsely presented after a local
   template existed. The guide now requires public-key publication, repository
   acceptance, provider onboarding, and provider-specific E2E evidence before
   either discovery or authorization is enabled.
4. Bucket existence could have been called upload readiness. The live
   `AccessDenied` result is now an explicit blocker.
5. The Cloudflare mutation flag existed only in configuration readiness and did
   not yet guard every runtime write. This was escalated immediately; Franklin
   owns the cross-module Task 3 runtime gate. Task 4 does not conceal or close
   that finding.

## External blockers and remaining proof

- Production Cloudflare for SaaS zone/fallback origin/CNAME target active-state
  receipts.
- A scoped production `CLOUDFLARE_SAAS_API_TOKEN` and rotation receipt.
- New/expanded R2 S3 credential authorized for the staging bucket, followed by
  real reserve/PUT/finalize/private-access/lifecycle proof.
- Verified Resend sending subdomain and real test-delivery receipt.
- Domain Connect RS256 public-key DNS publication.
- Online Editor evidence and official template-repository PR approval.
- Separate onboarding/approval for every DNS provider advertised as automatic.
- Provider-branded automatic-flow cancel/approve/callback/replay/disconnect E2E.
- Real frontend E2E for manual Cloudflare, GoDaddy, Namecheap, Squarespace,
  Route 53, and generic paths, including contrast, modal layout, keyboard/focus,
  pending/retry/support, migration, active, disconnect, tombstone, and stale-DNS
  cleanup.
- Task 3 runtime mutation-flag enforcement and its negative tests.

Until those receipts exist, automatic configuration stays disabled, media
runtime is not called ready, and the platform slug remains available.
