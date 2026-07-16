# Planner Storefront Production Infrastructure and Domain Onboarding

This runbook defines the production contract for the planner storefront, image
uploads, inquiry mail, and optional customer-owned domains. It is written for
operators and support engineers, but begins with the customer journey because
the infrastructure is only correct when a real planner can understand and
complete the flow.

## Production truth

- `https://thespecialwedding.io/storefront/{slug}` remains the canonical
  storefront and preview path. Custom-domain failures must never unpublish,
  delete, rename, or downgrade that storefront.
- The supported custom-domain shape is a customer-owned **subdomain**, for
  example `events.customer.com`. Self-service apex domains are not supported.
  They need an explicitly designed assisted path and, depending on the DNS
  provider, Cloudflare Apex Proxying or a provider flattening feature.
- Manual DNS configuration is the required fallback for every provider.
- Domain Connect automatic configuration is **not approved or enabled yet**.
  The repository contains a candidate template for signed synchronous requests
  and a local validator, but there is no template-repository approval,
  DNS-provider onboarding receipt, or production signing-key publication. Keep
  the discovery and authorization flags off until every external gate in this
  guide is evidenced.
- No customer should ever give The Special Wedding their registrar password,
  DNS-provider password, API token, or Cloudflare account access. Automatic
  setup, when approved, redirects the customer to their DNS provider for login
  and consent. Manual setup leaves the customer in their provider's console.
- Configuration presence is not provider success. A custom domain is ready only
  when application ownership, customer routing DNS, Cloudflare hostname status,
  Cloudflare certificate status, and an application-bound HTTPS response all
  independently pass. Publication remains a separate storefront setting.

The implementation and this guide intentionally keep four capabilities
independent: platform-slug storefront, media upload, inquiry delivery, and
custom domains. A failure in one capability disables only that capability.

## The real customer journey

The manual UX should follow the same principles used by Google's domain setup:
identify the provider, offer current provider-specific instructions, retain a
generic fallback, copy exact record values, and require an explicit verify
step. Google documents that structure in its [domain-verification
guide](https://support.google.com/a/answer/16018515?hl=en). Resend is the
automation benchmark: it has a signed template in the [official Domain Connect templates repository](https://github.com/Domain-Connect/Templates/blob/master/resend.com.mail.json),
while still publishing DNS records, statuses, and provider help for manual
recovery.

The customer flow is:

| Stage | What the planner sees | What the backend must do | Safe failure |
| --- | --- | --- | --- |
| 1. Enter domain | A dedicated custom-domain flow, not a single text box beside design settings. Ask for the desired subdomain and whether it is new or already serving a live site. | Normalize the hostname; reject URLs, paths, IPs, platform domains, apex domains, wildcards, and names already claimed by another tenant. Check the active subscription and planner ownership on every request. | Preserve the slug URL and show a field-level explanation. No provider mutation. |
| 2. Preflight | Show the detected DNS provider, nameservers, existing routing records, and whether this is a safe new setup or an assisted migration. | Query authoritative DNS independently for NS, A, AAAA, CNAME, CAA, and relevant TXT data. Do not trust provider names or proof supplied by the browser. | If DNS is ambiguous or conflicts exist, offer assisted migration; do not overwrite records. |
| 3. Choose setup | Offer **Connect automatically with {provider}** only when Domain Connect discovery returns exact support for the approved template. Always offer **Set up manually**. | For automatic setup, discover `_domainconnect` and validate provider endpoints. For manual setup, create an expiring owner-scoped claim and generate exact TXT/CNAME instructions. | If discovery or authorization is disabled, unavailable, or unsupported, fall back to the provider-specific manual guide without calling it an error. |
| 4. Authorize or edit DNS | Automatic path: the customer leaves The Special Wedding, signs in at the DNS provider, reviews the exact changes, approves or cancels, and returns. Greenfield manual path: the customer copies the ownership TXT and routing CNAME. Migration path: the customer publishes only the ownership TXT first and does not replace live routing before the explicit cutover step. | Sign Domain Connect requests server-side; validate callback state, owner, hostname, attempt, expiry, redirect origin, and one-time use. The callback GET only records the provider result; the planner's completion POST requires an explicit verified Bearer token, rejects an ambient `admin_token` cookie by itself, and rejects replay after consuming the flow. On the manual path, observe TXT/CNAME from authoritative DNS. Never request customer DNS credentials. | Cancel returns to the still-usable slug storefront. Expired or mismatched claims require a fresh attempt. |
| 5. Provision Cloudflare | Five independent progress rows: ownership TXT, routing CNAME, Cloudflare hostname, SSL certificate, and HTTPS storefront response. Raw provider JSON is never the primary UI. | Only after application ownership is proven, create or resume exactly one Cloudflare custom hostname. Persist provider ID and operation receipt before exposing success. Routing remains a separate readiness check so migration can prevalidate without overwriting the existing site. | Retry only classified retryable failures. Ambiguous create/delete outcomes go to `operator_review`; do not blindly create again. |
| 6. Verify readiness | A clear success state and the final HTTPS URL. Pending states show the exact record still missing and a provider-specific help link. | Re-read authoritative DNS and Cloudflare. Require owner mapping, routing CNAME, provider hostname `active`, SSL `active`, and a signed challenge/response through the exact custom hostname and Next.js edge. A successful TLS handshake or generic `200` alone is insufficient. | Keep the slug live and surface a support ID. Do not show false success. |
| 7. Disconnect | Explain that disconnecting stops platform routing but does not edit the customer's DNS records; tell the customer which records to remove afterward. | Delete the exact persisted Cloudflare hostname, revoke application routing immediately, retain a `tombstone` and operation receipt, and retry provider cleanup when safe. | If provider deletion is ambiguous, mark cleanup pending/`operator_review`; never pretend deletion succeeded. |

The planner modal's stable information architecture is three tabs: **Design**,
**Content & publish**, and **Domain**. **Live preview** remains a persistent
header action rather than becoming a fourth tab. The Domain tab is a focused,
readable workflow rather than a narrow card below unrelated design controls.
When setup is pending, it also offers **Email DNS instructions**, an optional
note, and **Send instructions**. A planner may continue managing an existing
domain even while activation of new domains is disabled.

Each emailed instruction uses a revocable, read-only first-party URL at
`/domain-instructions/{token}`, valid for up to seven days and never beyond the
current claim expiry. The snapshot contains only the exact DNS
records, provider help, expiry, and setup context. It cannot publish, activate,
transfer, retry, or disconnect a domain. Treat the token as a secret: never put
it in analytics, logs, support IDs, cache keys, or referrers. The instruction
route suppresses analytics and uses `no-referrer`; the public backend read is
`GET /api/storefront/domain-instructions/{token}` and returns the same generic
not-found response for an unknown, expired, or revoked token.

The planner UI reloads active receipts from the owner-scoped
`GET /admin/storefront/custom-domain/instructions?attempt_id=...` endpoint and
can revoke each receipt even after the account loses permission to start a new
custom-domain setup. The receipt stores only a masked recipient hint, a hash,
and an encrypted link token; it never stores the recipient's plaintext email or
the public token. Sends are bounded per owner, setup attempt, recipient, and
number of active links. Retries reuse the same encrypted token and provider
idempotency key so a timeout or ambiguous delivery result cannot silently rotate
the link or create duplicate email delivery.

The [Domain Connect 2.3 specification](https://github.com/Domain-Connect/spec/blob/master/Domain%20Connect%20Spec%20Draft.adoc)
requires the provider-hosted authentication and consent step. It also says DNS
providers can require separate contracts, onboarding, or fees. A merged
template therefore does not prove that every provider supports it.

## Roles and trust boundaries

There are four distinct roles. The registrar and DNS host may be the same
company, but they are not interchangeable:

1. **Registrar** — authoritative for domain registration and delegation, not
   necessarily for the DNS records used by setup. The product may identify it as
   unknown; registrar identity must never be inferred from nameservers.
2. **Customer authoritative DNS provider** — authoritative for the customer's DNS zone. It
   authenticates the customer, displays the proposed DNS change, obtains
   consent, and writes records in an approved Domain Connect flow. In a manual
   flow, only the customer edits this provider's records.
3. **The Special Wedding** — authoritative for planner entitlement, storefront
   ownership, domain claims, expected DNS records, operation receipts, and
   application routing. It must independently observe DNS and never infer
   ownership from possession of a browser session alone.
4. **Cloudflare for SaaS** — terminates TLS for the customer hostname and routes
   it through The Special Wedding's SaaS zone to the platform fallback origin.
   It does not own the customer's DNS account and it does not replace Domain
   Connect.

The browser is not a trusted fourth party. Hostname, provider ID, callback
state, Cloudflare ID, and verification results from the browser must all be
validated against the authenticated planner and durable backend state.

## Planned fixed production origins

The production zone owned by The Special Wedding reserves these stable names.
They are required configuration, not proof that DNS, fallback status, or routing
is currently active. Keep their acceptance status `BLOCKED` until dated
Cloudflare and DNS receipts exist:

| Name | Owner | Purpose |
| --- | --- | --- |
| `storefront-origin.thespecialwedding.com` | The Special Wedding / Cloudflare | Proxied Cloudflare for SaaS fallback origin that reaches the production Next.js storefront. It must be `Active` before customer hostnames are created. |
| `domains.thespecialwedding.com` | The Special Wedding / Cloudflare | Friendly proxied CNAME target shown to customers. It points to `storefront-origin.thespecialwedding.com` and remains stable across application releases. |
| `domainconnect.thespecialwedding.com` | The Special Wedding | Domain Connect signing-key and callback authority. The template's `syncPubKeyDomain` and allowed redirect domain use this name. |

The Cloudflare-supported topology is:

```text
events.customer.com
  CNAME -> domains.thespecialwedding.com
             CNAME -> storefront-origin.thespecialwedding.com
                          -> Cloudflare for SaaS fallback origin
                          -> production storefront application
```

Create the fallback origin and CNAME target using Cloudflare's [Cloudflare for
SaaS setup guide](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/getting-started/).
The fallback and friendly target are platform records; customer DNS records are
not created in the `thespecialwedding.com` zone.

## Backend lifecycle, source of truth, and invariants

`storefront_domains` is the application source of truth. Cloudflare custom
hostnames are an external projection reconciled from persisted provider IDs and
operation receipts; provider responses do not become the canonical owner
record.

Supporting owner-scoped records are deliberately separate:

- `storefront_domain_flows` — one-time Domain Connect authorization and callback
  state with expiry;
- `storefront_domain_operations` — append-only provider attempts, request
  fingerprints, classified responses, and receipts;
- `storefront_domain_instruction_links` — revocable, expiring, read-only DNS
  instruction snapshots;
- `storefront_domain_conflict_claims` — fresh, claimant-owned ownership proofs
  for a hostname already reserved by another tenant, without exposing that
  tenant;
- `storefront_domain_tombstones` — disconnect intent and exact provider deletion
  evidence retained for 90 days.

The durable lifecycle is:

```text
preflight -> claim_pending -> dns_setup_pending -> provider_provisioning
          -> hostname_validation -> certificate_validation -> deploying -> active
          -> action_required / operator_review

reserved hostname -> fresh conflict claim -> operator_review (never auto-transfer)

active/pending -> disconnecting -> disconnected + tombstone + deletion receipt
                               -> disconnect_failed + retry lease + tombstone
```

The complete application-phase vocabulary is `claim_pending`,
`authorization_pending`, `authorization_cancelled`, `dns_setup_pending`,
`migration_prevalidation`, `cutover_ready`, `provider_provisioning`,
`hostname_validation`, `certificate_validation`, `deploying`, `active`,
`action_required`, `operator_review`, `disconnecting`, `disconnect_failed`,
`disconnected`, and `expired`. Raw Cloudflare hostname/SSL values are retained
separately and never substituted for these customer-facing phases.

Provider redirects and reloads resume at
`/admin/packages?storefront=domain&attempt=<one-time-attempt-id>`. `Check again`
only observes authoritative DNS/current status and may be used by an existing
owner after entitlement loss; it cannot create or retry a provider hostname.
`Retry verification` is the separate, throttled no-change Cloudflare PATCH and
remains behind current entitlement, rollout, and mutation gates.

Every transition must preserve these invariants:

- one normalized hostname can belong to only one planner;
- one planner can have only the supported number of active claims;
- every create, refresh, retry, callback, and disconnect checks both permission
  and planner ownership;
- a claim has a one-time attempt ID, encrypted verification token, digest,
  expiry, revision, and compare-and-set write boundary;
- provider mutations are disabled until ownership is verified;
- a fresh conflict proof cannot silently reassign a hostname; it moves to
  operator review and does not reveal the existing planner's identity;
- a retry resumes the recorded operation; it does not create a second
  Cloudflare hostname;
- provider `404` revokes stale application routing instead of leaving a ghost
  mapping;
- an ambiguous create or delete enters `operator_review` with a support ID;
- disconnect revokes routing before remote cleanup and writes a `tombstone` so
  delayed retries cannot resurrect the hostname;
- stale customer DNS is shown as customer cleanup work. The application never
  claims it removed a record from a DNS account it does not control;
- changes to plan tier or publication are not infrastructure rollback tools.

The final HTTPS observation uses the exact
`/.well-known/tsw-storefront-verification` route on the customer hostname. The
worker sends a short-lived HMAC challenge bound to domain row ID, planner owner,
normalized hostname, lifecycle revision, and nonce. The Next.js edge forwards
only that exact well-known path and host binding to the backend. It also adds a
request-bound HMAC made with `STOREFRONT_PROBE_INGRESS_SECRET`; FastAPI rejects
missing, malformed, replayed-to-another-host, or caller-forged ingress proofs
before reading a domain row or signing an attestation. The backend then returns
a matching signed attestation. The worker pins the resolved public IP,
keeps SNI and `Host` on the customer hostname, rejects redirects, limits the
body to 8 KiB, and accepts only the exact JSON attestation. All other custom-host
paths keep the normal storefront routing restrictions. `SECRET_KEY` supplies
the challenge/attestation key material. `STOREFRONT_PROBE_INGRESS_SECRET` is a
separate server-only credential shared only by the Next and FastAPI runtimes.
Both must contain at least 32 random bytes, and neither may be exposed through a
`NEXT_PUBLIC_*` variable. Missing ingress identity makes only the custom-domain
probe return `404`; the platform slug remains available.

Cloudflare exposes hostname and certificate validation separately. Production
readiness requires both statuses to be active and DNS to point to the SaaS
target, as described in Cloudflare's [hostname validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/)
and [common API calls](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/common-api-calls/)
documentation.

## Runtime feature flags

Roll the control plane out in independent stages:

| Variable | Production meaning | Initial value |
| --- | --- | --- |
| `STOREFRONT_CUSTOM_DOMAINS_ENABLED` | Enables the owner-scoped custom-domain product surface. | `false` until Cloudflare configuration and manual E2E proof pass. |
| `STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED` | Allows new hostname creation and explicit provider-validation retry. | `false` until the dedicated token, zone, fallback, target, cleanup, and rollback have passed staging. |
| `STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED` | Allows deletion of an exact persisted Cloudflare hostname during disconnect/reconciliation. It is independent so rollback can stop onboarding while cleanup continues. | `false` before the first provider hostname; `true` before enabling mutations and while any provider hostname or tombstone remains. |
| `STOREFRONT_CUSTOM_DOMAIN_ROLLOUT_MODE` | `allowlist` permits only exact pilot owners/hostnames; `general` permits every entitled planner. | `allowlist`. Do not use `general` without the external-provider and browser acceptance receipts. |
| `STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES` | JSON array or comma-separated exact normalized disposable/pilot hostnames. Wildcards and suffix matching are not supported. | Empty until an approved pilot hostname is recorded. |
| `STOREFRONT_CUSTOM_DOMAIN_PILOT_OWNER_IDS` | JSON array or comma-separated exact planner-owner IDs allowed to provision pilot hostnames. | Empty unless an owner-scoped pilot is approved. |
| `STOREFRONT_DOMAIN_CONNECT_DISCOVERY_ENABLED` | Allows read-only `_domainconnect` provider discovery and presentation of a supported provider. | `false` until the exact template is published and provider compatibility is recorded. |
| `STOREFRONT_DOMAIN_CONNECT_AUTHORIZATION_ENABLED` | Allows signed provider redirects and callbacks that can change customer DNS. | `false` until signing-key publication, callback validation, template approval, and provider-specific E2E proof pass. |
| `STOREFRONT_RUNTIME_REVISION` | Non-secret immutable backend deploy identity returned by provider readiness and bound into storefront testbed receipts. | Exact deployed Git SHA or deployment digest; never the Compose fallback `unknown` for acceptance. |
| `STOREFRONT_PROBE_INGRESS_SECRET` | Authenticates exact host/challenge forwarding from the server-side Next custom-host route to FastAPI. | One secret-manager value containing at least 32 random bytes, injected into both runtimes and never exposed to browsers. |

Disabling any flag is fail-closed for new work. It must not delete an existing
mapping, hide the platform slug, unpublish a storefront, block media, or lose an
inquiry.

## Environment contract

Secrets are backend-only. Never put Cloudflare, R2, Resend, or Domain Connect
secrets in `NEXT_PUBLIC_*` variables.

### Custom-domain and Domain Connect values

| Variable | Required when | Contract |
| --- | --- | --- |
| `CLOUDFLARE_SAAS_API_TOKEN` | Cloudflare mutation or cleanup enabled | Dedicated API token restricted to the production SaaS zone with `Zone Read` and `SSL and Certificates Write`. It is the only token the custom-hostname client may use. |
| `CLOUDFLARE_ZONE_ID` | Cloudflare mutation or cleanup enabled | Zone ID for the Cloudflare for SaaS zone containing the fixed production origins. |
| `STOREFRONT_FALLBACK_ORIGIN` | Custom domains enabled | Bare hostname `storefront-origin.thespecialwedding.com`. |
| `STOREFRONT_CNAME_TARGET` | Custom domains enabled | Bare hostname `domains.thespecialwedding.com`. |
| `STOREFRONT_PLATFORM_DOMAINS` | Every environment | JSON array or comma-separated first-party domains. Include `thespecialwedding.io` and `thespecialwedding.com`; never include planner domains. |
| `STOREFRONT_PROBE_INGRESS_SECRET` | Custom domains enabled | At least 32 random bytes shared by the server-side Next and FastAPI runtimes. Rotate both deployments together; a mismatch fails the HTTPS check closed. Never use `NEXT_PUBLIC_` or reuse `SECRET_KEY`, Cloudflare, R2, Resend, or Domain Connect credentials. |
| `DOMAIN_CONNECT_PROVIDER_ID` | Domain Connect | `thespecialwedding.com`, matching the template filename and payload exactly. |
| `DOMAIN_CONNECT_SERVICE_ID` | Domain Connect | `storefront-subdomain`, matching the template exactly. |
| `DOMAIN_CONNECT_TEMPLATE_VERSION` | Domain Connect | Approved template version; currently candidate version `1`. Changing DNS semantics requires a reviewed version increment. |
| `DOMAIN_CONNECT_PRIVATE_KEY` | Domain Connect authorization | Secret RS256 private key in the secret manager. Never place it in Git, images, logs, browser storage, or test receipts. |
| `DOMAIN_CONNECT_KEY_ID` | Domain Connect authorization | DNS key label, initially `_dcpubkeyv1`; include the selected key ID in signed requests. |
| `DOMAIN_CONNECT_PUBLIC_KEY_DOMAIN` | Domain Connect authorization | `domainconnect.thespecialwedding.com`. |
| `DOMAIN_CONNECT_CALLBACK_URL` | Domain Connect authorization | Exact HTTPS callback under `domainconnect.thespecialwedding.com`; no wildcard redirects. |

Cloudflare's custom-hostname API lists `SSL and Certificates Write` as the
accepted permission for create operations. Add `Zone Read` for bounded zone
identity/readiness checks, use a token scoped to only the SaaS zone, and rotate
it separately from every other Cloudflare credential.

### R2 storefront-media values

| Variable | Required when | Contract |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | R2 uploads | Account owning the selected R2 buckets; it must match the account in `S3_ENDPOINT_URL`. |
| `CLOUDFLARE_API_TOKEN` | R2 safety checks | Dedicated R2 control-plane read token. It verifies managed-domain, custom-domain, CORS, and lifecycle state. It must never silently enable custom hostnames. |
| `S3_ENDPOINT_URL` | R2 uploads | Official account-scoped R2 S3 endpoint, without bucket path, query, port, or credentials. |
| `S3_REGION` | R2 uploads | `auto`. |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | R2 uploads | S3-compatible R2 Object Read & Write credentials scoped to the staging and published buckets only. |
| `S3_STOREFRONT_STAGING_BUCKET_NAME` | Browser upload | `the-special-wedding-storefront-staging`; dedicated private temporary bucket, never the public media bucket. |
| `S3_BLOG_BUCKET_NAME` | Published media | `knowledgeable-saas-blogs`; receives verified, decoded, metadata-stripped, re-encoded storefront images beneath `storefront/`. |
| `BLOG_MEDIA_DOMAIN` | Published media | `blogs.thespecialwedding.io`; production custom domain for sanitized public assets. |
| `STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS` | Browser upload | `1` by default; no more than `7`. |
| `STOREFRONT_IMAGE_DECODE_CONCURRENCY` | Browser upload | `1` unless process memory has been measured. |

The SaaS token and R2 control token are deliberately separate:

- `CLOUDFLARE_SAAS_API_TOKEN` can manage only custom hostnames in the SaaS
  zone.
- `CLOUDFLARE_API_TOKEN` can read only the R2 controls required by the privacy
  doctor.
- S3 access keys can perform only required object operations on named buckets.

The current non-secret staging deployment bindings are:

```dotenv
S3_STOREFRONT_STAGING_BUCKET_NAME=the-special-wedding-storefront-staging
S3_BLOG_BUCKET_NAME=knowledgeable-saas-blogs
BLOG_MEDIA_DOMAIN=blogs.thespecialwedding.io
```

These names describe two different trust levels, not interchangeable aliases.
The browser uploads untrusted bytes only to the private staging bucket. After
the backend validates the declared length and MIME type, decodes the image,
rejects unsafe dimensions or animation, strips metadata through re-encoding,
and verifies the resulting object, it publishes the sanitized bytes beneath
`storefront/` in `knowledgeable-saas-blogs`. The planner storefront never
renders a staging-bucket URL.

This v1 deliberately reuses the existing sanitized public-media bucket. The
new planner-storefront bucket to provision and validate is
`the-special-wedding-storefront-staging`. If separate public-bucket billing,
retention, or blast-radius isolation becomes necessary, introduce a dedicated
public storefront bucket and media domain as an explicit migration; do not
silently repoint `S3_BLOG_BUCKET_NAME` or `BLOG_MEDIA_DOMAIN`.

Cloudflare's [R2 S3 setup guide](https://developers.cloudflare.com/r2/get-started/s3/)
requires an Access Key ID, Secret Access Key, and the account-scoped endpoint.
Create the data credential using **Object Read & Write** and **Apply to specific
buckets only**, selecting exactly the two buckets above. Cloudflare documents
that permission and the one-time secret display in its [R2 authentication
guide](https://developers.cloudflare.com/r2/api/tokens/). Do not substitute a
normal Cloudflare bearer token for the S3-compatible access key and secret.

Rotate one credential at a time in staging, verify, deploy the new secret,
restart application instances, verify again, then revoke the old credential.
Never log a token to prove it is configured; record presence, scope, creation
date, rotation owner, and provider verification result.

### Resend inquiry and instruction mail

| Variable | Required when | Contract |
| --- | --- | --- |
| `RESEND_API_KEY` | Email delivery | Environment-specific secret key; backend only. |
| `RESEND_FROM_EMAIL` | Email delivery | Address under a verified sending domain/subdomain. |
| `RESEND_FROM_NAME` | Email delivery | Human-readable sender, default `The Special Wedding`. |

Resend requires a verified owned domain and recommends a sending subdomain to
isolate reputation. Its dashboard reports `not_started`, `pending`, `verified`,
partial, temporary-failure, and failed states; treat only `verified` as ready.
See [Resend domain management](https://resend.com/docs/dashboard/domains/introduction)
and its [domain troubleshooting guide](https://resend.com/docs/knowledge-base/what-if-my-domain-is-not-verifying).

Use Resend for two different messages:

- inquiry notification to the planner, after the inquiry is durably committed;
- optional setup instruction/reminder containing the customer hostname and an
  expiring, revocable, read-only first-party instruction link. The public page
  shows the provider label, exact safe DNS records, and claim-bounded expiry; it
  does not authenticate the recipient into planner setup or expose a mutation.

Email delivery failure must not lose an inquiry or mark DNS verified. Inquiry
delivery persists its own retryable outcome for background recovery. DNS
instruction sends persist an operation receipt and expose an explicit resend;
the current implementation does **not** background-retry an instruction email,
so operators must not claim that it does. Customer retries are rate-limited and
reuse the existing secure link plus the same Resend idempotency key. Never email
customer DNS credentials,
Cloudflare tokens, Domain Connect private keys, or a provider callback bearer
token.

## Configure Cloudflare for SaaS

1. Add `thespecialwedding.com` to the intended production Cloudflare account,
   enable Cloudflare for SaaS, and confirm the account plan supports the required
   hostname volume and features.
2. Create a proxied `A`, `AAAA`, or `CNAME` named
   `storefront-origin.thespecialwedding.com` pointing to the actual production
   application origin. Designate it as the fallback origin and wait for
   fallback status `Active`.
3. Prove the origin reaches the correct application. Cloudflare explicitly
   notes that an active fallback status proves routing readiness, not that the
   record points to the intended application.
4. Create a proxied CNAME `domains.thespecialwedding.com` pointing to
   `storefront-origin.thespecialwedding.com`.
5. Create a dedicated token scoped only to this zone with `Zone Read` and `SSL
   and Certificates Write`; place it in the secret manager as
   `CLOUDFLARE_SAAS_API_TOKEN`.
6. Configure the zone ID and fixed hostnames. Keep
   `STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED=false`, rollout mode `allowlist`,
   and both pilot lists empty during the read-only doctor. Before the first
   provider create, enable `STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED=true` so a
   rollback cannot strand deletion.
7. Exercise one allowlisted disposable staging subdomain through create,
   ownership verification, pending states, active state, refresh, disconnect,
   remote deletion, and application tombstone before production enablement.

For a customer whose authoritative DNS is also Cloudflare, a proxied CNAME can
create an Orange-to-Orange flow. Cloudflare documents that this changes
pre-validation behavior. The default manual guide should recommend **DNS only**
for a predictable first setup; route an existing proxied record through assisted
migration rather than silently changing its proxy mode. See Cloudflare's
[O2O explanation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/saas-customers/how-it-works/)
and [pre-validation limitations](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/pre-validation/).

## Domain Connect onboarding: external gate

The candidate template is:

`domain-connect/templates/thespecialwedding.com.storefront-subdomain.json`

It creates a scoped application-ownership TXT record and a CNAME to
`domains.thespecialwedding.com`. It requires a `host` parameter, so it must not
be used for apex setup.

Before automatic setup can appear in production:

The current discovery client accepts only Cloudflare's exact Domain Connect
provider identity and approved HTTPS endpoints. A template discovered at any
other DNS provider remains manual-only until that provider receives its own
reviewed endpoint allowlist and real-account consent lifecycle. Do not describe
discovery as universal automatic DNS support.

1. Validate the exact candidate locally:

   ```bash
   PYTHONPATH=. .venv.nosync/bin/python testbed/validate_storefront_domain_connect_template.py
   ```

2. Run the Domain Connect Online Editor syntax, variable, apex, and subdomain
   checks. Save the editor result URL required by the repository PR process.
3. Generate an RS256 signing key outside the repository. Store the private key
   only in the production secret manager as `DOMAIN_CONNECT_PRIVATE_KEY`.
4. Publish the public key as one or more TXT records at
   `_dcpubkeyv1.domainconnect.thespecialwedding.com`, using the Domain Connect
   `p=<part>,a=RS256,d=<key-data>` format. Confirm public DNS reconstruction from
   two independent resolvers. Do not publish a private key.
5. Serve the exact HTTPS callback and restrict accepted redirect/callback values
   to `domainconnect.thespecialwedding.com`. Sign the complete encoded query
   string except `sig` and `key`, as required by the specification.
6. Submit the exact file to the [official Domain Connect templates
   repository](https://github.com/Domain-Connect/templates) using its PR
   template and current Online Editor evidence. A local pass is not repository
   approval.
7. Obtain and record DNS-provider onboarding for the exact provider ID, service
   ID, version, signing domain, callback, and environment. Cloudflare, GoDaddy,
   Namecheap, Squarespace, Route 53, and generic/manual availability are separate
   outcomes; do not infer one provider's approval from another.
8. Run provider-specific sandbox/disposable-domain E2E proof: discovery,
   provider-branded redirect, login owned by the provider, displayed changes,
   cancel, approve, callback replay rejection, authoritative DNS verification,
   Cloudflare hostname/SSL activation, disconnect, and stale-DNS instructions.
9. Only after signed approval receipts exist, enable discovery for proven
   providers. Enable authorization separately after callback and mutation proof.

Key rotation requires an overlap window: publish the new public-key label,
deploy signing with the new key ID, complete provider proof, stop issuing the old
key ID, wait past every signed-link/claim TTL, and only then remove the old TXT
record and private key.

## Manual DNS provider guides

The UI must render the exact record names returned by the backend. For a sample
hostname `events.customer.com`, the records are conceptually:

| Type | Name/host | Value/target | Purpose |
| --- | --- | --- | --- |
| TXT | `_tsw-storefront.events` (or the full `_tsw-storefront.events.customer.com`, depending on the provider) | `tsw-verification=<one-time-token>` | Proves application ownership. |
| CNAME | `events` (or full `events.customer.com`) | `domains.thespecialwedding.com` | Routes storefront traffic. |

The UI must label whether a provider wants a relative host or FQDN. It must not
make the customer guess. Never remove unrelated MX, TXT, CAA, A, AAAA, or CNAME
records. A CNAME cannot coexist with other records at the same owner name.

Provider detection is advisory, not an ownership fact. In particular,
`.googledomains.com` cannot be labeled as Google Cloud DNS with certainty:
Squarespace documents that its default delegation may use that suffix and that
other companies share its nameserver families. The product therefore presents
that delegation as **Google Cloud DNS or Squarespace DNS**, provides no
single-provider deep link, and asks the customer to confirm the DNS dashboard.
Only the branded `.squarespacedns.com` family receives the Squarespace console
link; shared `.nsone.net` and `.systemdns.com` names stay provider-unknown.
[Squarespace nameserver reference](https://support.squarespace.com/hc/en-us/articles/4404183898125-Making-changes-to-nameservers).

### Cloudflare DNS

1. Open the customer's zone in Cloudflare, then **DNS > Records > Add record**.
2. Add the ownership TXT record exactly as displayed.
3. Add the CNAME for the storefront subdomain targeting
   `domains.thespecialwedding.com`.
4. Use **DNS only** for the standard first-time flow. If the hostname is already
   proxied, stop and use assisted migration because O2O validation differs.
5. Return to The Special Wedding and select **I've added these records**. During
   later pending states, use **Check again** for read-only observation.

Official help: [Cloudflare create DNS
records](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/)
and [proxy status](https://developers.cloudflare.com/dns/proxy-status/).

### GoDaddy

1. Open the domain portfolio, choose the domain, and open **DNS**.
2. Add the TXT verification record. GoDaddy generally expects the relative host
   label, not the full zone name.
3. Add a CNAME with host `events` and value
   `domains.thespecialwedding.com`; leave unrelated records unchanged.
4. Save, return to The Special Wedding, and select **I've added these records**.
   During later pending states, use **Check again**.

Official help: [GoDaddy add a CNAME
record](https://www.godaddy.com/help/add-a-cname-record-19236).

### Namecheap

1. Open **Domain List > Manage > Advanced DNS**.
2. Add the TXT verification record under **Host Records**.
3. Add a CNAME for the relative subdomain host targeting
   `domains.thespecialwedding.com`.
4. Save all changes, return, and select **I've added these records**. During
   later pending states, use **Check again**.

Official help: [Namecheap CNAME
records](https://www.namecheap.com/support/knowledgebase/article.aspx/9646/2237/how-to-create-a-cname-record-for-your-domain/)
and [Namecheap TXT
records](https://www.namecheap.com/support/knowledgebase/article.aspx/317/2237/how-do-i-add-txtspfdkimdmarc-records-for-my-domain/).

### Squarespace Domains

1. Open the domain dashboard, select the domain, then open **DNS Settings**.
2. Add the displayed TXT verification record.
3. Add the storefront CNAME. Enter only the subdomain label where Squarespace
   automatically appends the root domain.
4. Save, return to The Special Wedding, and select **I've added these records**.
   During later pending states, use **Check again**.

Official help: [Squarespace DNS
records](https://support.squarespace.com/hc/en-us/articles/31119879125645-DNS-records-for-web-hosting).

### Amazon Route 53

1. Open the authoritative public hosted zone in Route 53 and choose **Create
   record**.
2. Create the TXT verification record. Route 53 displays TXT values with quotes;
   enter the backend value once and do not add duplicate semantic quotes.
3. Create a standard CNAME for the subdomain targeting
   `domains.thespecialwedding.com`.
4. Do not create a CNAME at the zone apex; Route 53 and DNS rules prohibit that
   shape. This product supports the subdomain path.
5. Save, return, and select **I've added these records**. During later pending
   states, use **Check again**.

Official help: [Route 53 supported record
types](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html).

### Generic or unknown DNS provider

1. Confirm where authoritative DNS is hosted; the registrar and DNS host may be
   different.
2. Open the page named **DNS records**, **Zone editor**, **DNS management**, or
   equivalent.
3. Add the exact TXT and CNAME shown in the product. Use relative labels if the
   provider appends the zone; use FQDNs only if its documentation requires them.
4. Do not change nameservers and do not delete unrelated records.
5. Save, wait for authoritative DNS to return the records, then select **I've
   added these records**. During later pending states, use **Check again**. If
   the provider rejects the values, contact that provider's
   support with the exact record type/name/value—not customer credentials.

Google uses the same provider-specific plus generic fallback pattern in its
[TXT verification workflow](https://support.google.com/a/answer/16018515?hl=en)
and explains the alias/target relationship in its [CNAME
documentation](https://knowledge.workspace.google.com/admin/domains/about-cname-records?hl=en).

## Greenfield setup versus assisted migration

### New, unused subdomain

1. Preflight finds no conflicting A, AAAA, or CNAME records.
2. Backend creates an expiring ownership claim.
3. Customer adds TXT and CNAME, or approves the exact Domain Connect change
   after that path is externally approved.
4. Backend verifies the authoritative ownership TXT, snapshots existing
   provider IDs, then creates the Cloudflare custom hostname exactly once.
   Routing CNAME, hostname status, SSL, and HTTPS remain independent readiness
   checks; provider creation alone is not connection success.
5. UI waits for hostname, certificate, DNS, and HTTPS readiness.

### Existing live hostname

An existing routing record means assisted migration, not an error and not an
automatic overwrite.

1. Capture existing A/AAAA/CNAME values, proxy mode, TTL, current HTTPS result,
   CAA records, and rollback owner in the operation receipt.
2. Lower TTL in advance if the provider supports it.
3. For non-O2O cases, use Cloudflare [pre-validation](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/pre-validation/)
   to validate ownership/certificate before cutover where supported.
4. Schedule the CNAME cutover, verify Cloudflare hostname and certificate
   statuses, authoritative DNS, storefront content, tenant isolation, and HTTPS.
5. If the acceptance window fails, restore the exact previous routing values.
   Do not delete the new Cloudflare hostname until routing is safely restored
   and its state is reconciled.

O2O hostnames cannot use the same pre-validation method; keep them on the
provider-specific assisted branch.

## Root-admin operator review

`operator_review` is a safety stop, not a generic retry state. The customer sees
support-required copy and a support ID while the platform slug remains usable.
Only the root-admin dependency may call these exact, revision-fenced endpoints:

| Review | Endpoint | Allowed decision | Required evidence |
| --- | --- | --- | --- |
| Cloudflare O2O migration | `POST /admin/storefront/custom-domain/operator/o2o/approve` | Approve one ownership-verified assisted cutover | Exact planner ID, hostname, claim attempt, current revision, and a written risk/rollback reason. Approval creates a one-use receipt; it is not customer-domain activation. |
| Fresh ownership conflict | `POST /admin/storefront/custom-domain/operator/conflict/resolve` | `denied` or `cancelled` only | Exact conflict claimant, hostname, attempt, revision, and reason. This endpoint never transfers the reserved hostname or reveals the current owner. |
| Ambiguous Cloudflare create | `POST /admin/storefront/custom-domain/operator/ambiguous-create/adopt` | Adopt one demonstrably new exact provider hostname ID | Exact provider ID must not exist in the pre-create snapshot; Cloudflare must independently list one exact hostname/ID match. Ambiguity remains in review. |

Every operator request must be copied from a freshly loaded review row. A `409`
revision mismatch means reload and re-investigate; never increment or guess the
revision. Preserve the returned `operation_id`, before/after revisions, actor,
reason, provider ID where applicable, and completion time as the audit receipt.
There is no force-transfer endpoint.

Operational monitoring persists deduplicated root-admin incidents for operator
review, disconnect/certificate failure, Cloudflare 429/5xx spikes, and worker
backlog. Triage by the customer-visible support ID, domain operation receipt,
exact planner/hostname scope, and current lifecycle revision. Do not paste raw
provider responses or instruction tokens into a customer message. The current
storefront configuration doctor validates local non-secret dependency presence,
feature-flag prerequisites, rollout fences, token separation, and the checked-in
Domain Connect contract. It deliberately makes no provider call; keep every
provider-dependent check `BLOCKED` until its separate receipt exists.

## R2 browser-upload safety

Use a private staging bucket and a separate public sanitized-asset bucket.

1. Disable the staging bucket's `r2.dev` URL and remove every staging custom
   domain.
2. Configure exact-origin CORS for `PUT` and `Content-Type`; do not use `*` in
   production. Cloudflare's [R2 CORS guide](https://developers.cloudflare.com/r2/buckets/cors/)
   requires the request origin, method, and headers to match the bucket policy,
   and its [R2 CORS API](https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/cors/)
   defines the response shape consumed by the storefront readiness check.
3. Add an enabled lifecycle deletion rule for the `storefront/` prefix with age
   no greater than `STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS`. See [R2 object
   lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/).
4. Reserve a five-minute presigned `PUT` on the account-scoped S3 endpoint,
   signed for the declared `Content-Type` and byte length. The browser must send
   the same `Content-Type`; Cloudflare documents that changing a signed header
   produces `403 SignatureDoesNotMatch`. See [R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/).
   Then let the backend verify, decode, strip metadata, re-encode, and upload
   only sanitized output to the public bucket.
5. Serve published output from `BLOG_MEDIA_DOMAIN`, never the staging bucket or
   an `r2.dev` URL. Cloudflare says `r2.dev` is for development and buckets are
   private by default in its [public bucket
   guide](https://developers.cloudflare.com/r2/buckets/public-buckets/).

Generate the S3-compatible access key and secret from the same Cloudflare
account named by `CLOUDFLARE_ACCOUNT_ID`, with object read/write/delete access
limited to the two storefront buckets. A valid Cloudflare bearer token or a
successful bucket-list API call is not an S3 data credential and must not be
substituted for these values. Before enabling uploads, use a read-only
`HeadBucket` against both exact bucket names. `403`, `AccessDenied`, or
`SignatureDoesNotMatch` keeps live media acceptance `BLOCKED`; rotate the data
credential, restart every API instance, and repeat the full browser lifecycle.
Never weaken bucket privacy or widen the application credential to make the
test pass.

Example staging CORS policy for the Cloudflare dashboard or S3-compatible CORS
configuration:

```json
[
  {
    "AllowedOrigins": ["https://thespecialwedding.io"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

The Cloudflare REST API represents the same rule with a `rules` array and a
nested `allowed` object (`origins`, `methods`, and `headers`). Do not paste the
dashboard/S3 shape directly into the REST endpoint. The application reads the
official REST response shape and verifies the exact deployed origin before it
reports browser uploads ready. CORS changes can take up to 30 seconds to
propagate according to Cloudflare's CORS guide.

## Operator checks and deployment acceptance

Never print secret values. Presence/absence and provider scope are sufficient
for a configuration receipt.

`testbed/storefront_configuration_doctor.py` validates canonical loaded settings,
the mutation/cleanup/allowlist fences, Domain Connect signing prerequisites, R2
and Resend presence, the immutable runtime revision, the checked-in template,
the trusted client-IP ingress contract, and a bounded read-only PING to the Redis
instance that protects public storefront inquiries across API replicas. It prints
no credential values and performs no Cloudflare, R2, Resend, DNS, Mongo, or
application-API operation.
Its `external_provider_acceptance` row always remains `BLOCKED`; passing the
local doctor must never be presented as Cloudflare, Domain Connect, independent
DNS-provider, R2 privacy, email-delivery, or browser evidence. Use `--json` for a
machine-readable non-secret local receipt.

Production storefront inquiries must use the same Redis settings consumed by
`CacheManager`: `REDIS_ENABLED=true`, `REDIS_HOST`, `REDIS_PORT`,
`REDIS_PASSWORD`, `REDIS_DB`, and `REDIS_MAX_CONNECTIONS`. The production Compose
file enables Redis, requires a deployment-managed password, and wires the API to
the `redis` service. If Redis is disabled or unreachable, new inquiry submissions
return a retryable friendly `503`; the public storefront, publication setting,
and platform slug remain unchanged. A per-process fallback is allowed only in
local/test environments because it cannot enforce one limit across replicas.

The inquiry rate key also depends on a trustworthy customer IP. The bundled
production Nginx overwrites `X-Real-IP` and reaches FastAPI over
`172.26.0.0/16`, so Compose defaults `TRUSTED_PROXY_CIDRS` to that network and
`TRUSTED_PROXY_CLIENT_IP_HEADER` to `X-Real-IP`. If the ingress topology changes,
set both values to the actual direct-proxy network and a header that proxy
overwrites. Never enable `CF-Connecting-IP` merely because Cloudflare is in front;
the immediately trusted ingress must validate the Cloudflare source and overwrite
the value first.

Run from the repository root:

```bash
# Render and validate production Compose without dumping the rendered document.
docker compose -f docker-compose.production.yml config --quiet

# Validate settings, token separation, Compose/env parity, guide, and template.
PYTHONPATH=. .venv.nosync/bin/pytest \
  tests/backend/test_storefront_production_configuration.py \
  tests/backend/test_config_validator.py \
  tests/backend/test_storefront_configuration_doctor.py -q

# Validate canonical storefront configuration without provider/network calls.
PYTHONPATH=. .venv.nosync/bin/python \
  testbed/storefront_configuration_doctor.py

# Validate the exact candidate Domain Connect template without provider calls.
PYTHONPATH=. .venv.nosync/bin/python \
  testbed/validate_storefront_domain_connect_template.py

# Inspect general local testbed tools only; this is not storefront readiness.
PYTHONPATH=. .venv.nosync/bin/python testbed/testbed.py doctor

# Build the exact frontend source and run the deterministic application
# lifecycle. This never becomes independent-provider evidence.
PYTHONPATH=. .venv.nosync/bin/python testbed/build_storefront_frontend.py
TESTBED_NON_INTERACTIVE=1 \
TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic \
TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE=disabled \
npm run test:e2e:storefront

# After the automated run, hold a new isolated source-bound fixture set for
# visible review in the user-selected in-app Chrome. This skips Playwright,
# blanks external-provider credentials, and cleans up on Ctrl-C.
TESTBED_NON_INTERACTIVE=1 \
TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic \
TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE=disabled \
.venv.nosync/bin/python testbed/serve_storefront_visible_playback.py
```

Deployment order:

1. Stage separate Cloudflare for SaaS, R2 control, R2 S3, Resend, and Domain
   Connect secrets; record only presence and approved scope.
2. Deploy with product, discovery, authorization, mutation, and cleanup flags
   false; rollout mode remains `allowlist` with empty exact pilot lists.
3. Run the startup configuration validator and authenticated
   `/admin/storefront/provider-readiness`; confirm it discloses no credential
   value and makes no provider mutation.
4. Confirm slug preview/publication, media, and inquiries independently.
5. In staging, enable cleanup first, add one exact disposable hostname/owner to
   the pilot allowlists, then enable manual custom-domain and Cloudflare
   mutation flags; complete the lifecycle and provider-delete receipt.
6. Enable production manual custom domains only in `allowlist` mode after
   staging receipts pass. `general` is a separate GA decision and must produce
   a new acceptance receipt.
7. Keep Domain Connect flags false until repository and provider onboarding
   receipts exist. Then enable discovery before authorization and prove the
   provider-branded customer flow in the real frontend.

The deterministic Playwright run must finish with zero unexpected/flaky tests,
no page/console/network/accessibility/overflow failures, a passing cleanup
receipt, and a manifest bound to the run nonce, source fingerprint, frontend
build, and backend runtime revision. Then replay the accepted flow separately in
the user-selected in-app Chrome browser. Playwright screenshots support that
review; they do not replace it.

A same-zone canary under `thespecialwedding.com` may prove the platform fallback
origin, CNAME target, custom-hostname/certificate lifecycle, routing, and cleanup.
It does not prove a customer journey at an independently operated DNS provider.
Production sign-off therefore also requires an authorized disposable hostname
under an independently authoritative customer zone. Until both exist, the
external-provider acceptance row remains `BLOCKED`.

Cloudflare supports custom hostnames that are subdomains of the SaaS provider
zone, while its O2O behavior applies to customer and SaaS zones in different
Cloudflare accounts. The canary therefore remains a platform-infrastructure
check, not an O2O or independent-customer check. See [Cloudflare custom-hostname
support](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/)
and [O2O prerequisites](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/saas-customers/how-it-works/).

Use a separate operator-only `CLOUDFLARE_PLATFORM_DNS_API_TOKEN`, scoped to DNS
Read and DNS Edit for `thespecialwedding.com`. Do not provide that token to the
application runtime, and do not reuse `CLOUDFLARE_SAAS_API_TOKEN`. The canary
refuses to run unless the exact hostname appears in both the test allowlist and
`STOREFRONT_CUSTOM_DOMAIN_PILOT_HOSTNAMES`, the exact zone ID is allowlisted,
mutations and cleanup are enabled, no prior DNS/custom-hostname record exists,
and the run-bound authorization string matches.

```bash
# No network calls or provider mutations; output remains BLOCKED.
PYTHONPATH=. .venv.nosync/bin/python \
  testbed/storefront_same_zone_canary.py --config-only

# Explicitly authorized create -> poll -> HTTPS -> delete lifecycle.
PYTHONPATH=. .venv.nosync/bin/python \
  testbed/storefront_same_zone_canary.py
```

The final JSON receipt is written beneath
`testbed/.testbed/artifacts/storefront/same-zone/`. A run passes only when the
fallback origin is active, the friendly target and origin records are exact and
proxied, the custom hostname and SSL are active, a system-trusted HTTPS request
reaches `/api/health-ssr` through Cloudflare, and both the provider hostname and
the exact canary DNS record are confirmed deleted. Cloudflare documents the
fallback and friendly-target requirements in its [SaaS setup guide](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/getting-started/)
and recommends deleting churned custom hostnames in its [removal guide](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/remove-custom-hostnames/).

The live frontend acceptance path must include:

- provider label and correct help link;
- both automatic and manual choices only when automatic is truly supported;
- readable record names/values with copy confirmation;
- migration warning before any destructive change;
- keyboard/focus/modal/scroll and color-contrast validation;
- pending, retryable, support-required, active, disconnecting, and disconnected
  states;
- no raw JSON as customer-facing error text;
- a separate visible playback in the user-selected in-app Chrome browser after
  the source-bound Playwright run; unit checks and screenshots do not replace it.

## Failure, disconnect, rollback, and support

| Symptom | Customer-facing interpretation | Operator action |
| --- | --- | --- |
| Custom-domain configuration unavailable | “Custom-domain setup is temporarily unavailable. Your platform storefront remains available.” | Check flags and presence of the SaaS token, zone ID, fallback origin, and CNAME target. Do not suggest unpublishing or changing plan state. |
| Ownership TXT missing | “We have not found the verification record yet.” | Show exact TXT name/value and provider guide; retry authoritative DNS with bounded backoff. |
| Routing record conflict | “This hostname already points somewhere else.” | Route to assisted migration. Preserve the old values; never overwrite automatically. |
| Cloudflare hostname pending | “Domain ownership is verified; secure routing is still being prepared.” | Refresh the persisted provider ID. Do not create another hostname. |
| SSL pending or errored | “Secure routing is still being prepared; this domain is not connected yet.” | Show Cloudflare's returned DCV record, check CAA and DNS, and follow [validation error guidance](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/hostname-validation/error-codes/). |
| Provider create/delete ambiguous | “Support must reconcile this attempt before it is safe to retry.” | Move to `operator_review`; inspect operation receipt and exact provider snapshot. |
| Disconnect cleanup pending | “The domain no longer routes in The Special Wedding; provider cleanup is still pending.” | Keep the `tombstone`, retry exact provider deletion, then tell the customer to remove stale TXT/CNAME records. |
| Customer changed CNAME away | Domain may become moved/deleted at Cloudflare, but stale SaaS records still require cleanup. | Revoke application routing and remove the Cloudflare custom hostname. Cloudflare recommends provider removal when a customer leaves in its [removal guide](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/domain-support/remove-custom-hostnames/). |

Application rollback means redeploying the previous application revision while
keeping `domains.thespecialwedding.com` and
`storefront-origin.thespecialwedding.com` stable. For an onboarding rollback,
set `STOREFRONT_CLOUDFLARE_MUTATIONS_ENABLED=false`, keep rollout mode
`allowlist`, and leave `STOREFRONT_CLOUDFLARE_CLEANUP_ENABLED=true` while any
provider hostname, deletion retry, or tombstone exists. Infrastructure rollback
must never silently delete customer mappings. Reconcile outstanding operation
receipts and tombstones before re-enabling new provisioning.

## Evidence state and external dependencies

These evidence classes are deliberately separate:

### Deterministic application lifecycle — `PASSED` for application-only scope

The real frontend/FastAPI/Mongo lifecycle can run against deterministic
DNS/Cloudflare/HTTPS/email adapters. Source-bound run `f14e71003557` passed the
ten exact required Playwright test/project pairs with zero unexpected/flaky
results, 18 of 20 browser scenarios, persistence, protected account and
subscription hashing, deterministic provider control-plane checks, cleanup, and
post-shutdown artifact sealing. Its manifest is
`testbed/.testbed/artifacts/storefront/runs/f14e71003557/run-manifest.json`.

The command exited nonzero by design because the evidence gate kept scenario 4
blocked without configured object-storage upload/finalize/persist/render proof
and scenario 14 blocked without an independently authoritative customer zone
and scoped Cloudflare for SaaS credentials. This receipt proves application
behavior only; it is not an external-provider completion receipt.

### Visible in-app Chrome — `RECORDED; PARTIAL ACCEPTANCE COVERAGE`

Current-source visible playback run `e19f7bcca1a7` is recorded at
`testbed/.testbed/artifacts/storefront/visible-playback/runs/e19f7bcca1a7/run-manifest.json`.
The user-selected browser visibly reviewed restricted gating, eligible
configuration, saved design state, provider detection, manual DNS records,
expected-versus-observed values, and connection-progress rows. The runner's
authenticated cleanup and final artifact seal both passed, and its browser
console had no warning/error entries. This receipt is local deterministic
playback only; it does not replace the blocked R2 upload round-trip or the
independently authoritative customer-provider journey.

### Independently authoritative provider — `BLOCKED`

The following require dated, environment-bound external receipts and must not be
described as present merely because a variable or bucket name is configured:

- Cloudflare for SaaS enablement for the production zone;
- fallback-origin and friendly-CNAME creation plus active-state proof;
- a zone-scoped `CLOUDFLARE_SAAS_API_TOKEN` with Zone Read and SSL and
  Certificates Write, including scope and rotation receipt;
- authorized bucket-scoped R2 S3 credentials plus end-to-end upload, finalize,
  lifecycle, CORS, and private-staging proof;
- a verified Resend sending subdomain and actual delivery proof;
- Domain Connect public-key publication, Online Editor evidence, official
  template-repository acceptance, and Cloudflare onboarding;
- provider-branded automatic consent/cancel/callback/replay receipts;
- same-zone platform canary proof; and
- an independently authoritative disposable customer-zone lifecycle through
  DNS, Cloudflare hostname/SSL, HTTPS, disconnect, provider deletion receipt,
  and customer DNS cleanup.

Until these exist, automatic DNS configuration and the external-provider
acceptance row remain `BLOCKED`. The platform slug remains the dependable
customer path.
