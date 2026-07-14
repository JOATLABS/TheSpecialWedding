# Planner Storefront Infrastructure Setup

This is the operator runbook for enabling planner storefront image uploads and
optional custom domains. It covers infrastructure and environment configuration;
it does not change subscription tiers, planner accounts, saved storefront
settings, or publication state.

The platform-slug storefront and custom domains are deliberately separate:

- `/storefront/{slug}` is the canonical preview and public storefront path.
- A custom domain is an optional Cloudflare for SaaS projection of the same
  storefront.
- Losing or omitting custom-domain configuration must not remove the platform
  slug, unpublish a storefront, or edit a subscription.
- New image uploads and custom-domain operations fail closed when their
  infrastructure cannot be verified.

Configure staging first with staging-only buckets, tokens, hostnames, and test
planner data. Do not copy production planner data into staging.

## Request and media topology

```text
Platform URL
  https://thespecialwedding.io/storefront/{slug}
                    |
                    v
              Next.js storefront

Customer custom hostname
  store.customer.example
          | CNAME
          v
  STOREFRONT_CNAME_TARGET
          |
          v
  Cloudflare for SaaS fallback origin -> the same Next.js storefront

Planner browser
  | presigned PUT
  v
Private R2 staging bucket (storefront/ prefix)
  | backend verifies, decodes, strips metadata, and re-encodes
  v
Public blog-assets bucket -> BLOG_MEDIA_DOMAIN
```

The staging bucket is temporary and private. It must never be reused as a
public media bucket or attached to `r2.dev` or an enabled R2 custom domain.

## Environment matrix

Do not place `CLOUDFLARE_API_TOKEN`, S3 credentials, or any other secret in a
`NEXT_PUBLIC_*` variable.

### Values shared by frontend and backend

These values participate in host-authority classification and must agree in a
split-service deployment:

| Variable | Required | Contract |
| --- | --- | --- |
| `FRONTEND_URL` | Yes | Exact public frontend origin for the environment, such as `https://thespecialwedding.io`. |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Public backend origin used by deployment checks, frontend fallback, and host classification. Next.js may inline it during build, so changing it requires a rebuilt/redeployed frontend image. |
| `STOREFRONT_PLATFORM_DOMAINS` | Yes in production | JSON array or comma-separated platform-owned domains. Include every first-party frontend domain for that environment; do not include planner domains. |
| `STOREFRONT_CNAME_TARGET` | For custom domains | Hostname only, without scheme or path. It is the Cloudflare for SaaS CNAME target shown to planners. |

`INTERNAL_API_BASE_URL` or `BACKEND_SERVICE_URL` remains the preferred internal
frontend-to-backend target in a split deployment. It does not replace the public
host values above.

### Backend-only Cloudflare and R2 values

| Variable | Required | Contract |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID` | For uploads | Exactly 32 hexadecimal characters. It must identify the same account as `S3_ENDPOINT_URL`. |
| `CLOUDFLARE_API_TOKEN` | For uploads and custom domains | Secret Cloudflare REST bearer token scoped to the target account/zone. Grant account-level `Workers R2 Storage Read` for the staging bucket's managed-domain, custom-domain, CORS, and lifecycle controls plus zone-level `SSL and Certificates Write` for the SaaS zone. This is not an S3 access key. |
| `CLOUDFLARE_ZONE_ID` | For custom domains | Zone identifier for the Cloudflare for SaaS zone. |
| `S3_ENDPOINT_URL` | For uploads | Official account-scoped R2 endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, or the matching `.eu`/`.fedramp` jurisdiction endpoint. No path, query, credentials, or port. |
| `S3_REGION` | For uploads | Use `auto` for R2. |
| `S3_ACCESS_KEY_ID` | For uploads | R2 S3 credential scoped to the explicitly selected staging and blog-assets buckets with bucket-list plus object get/put/delete access. |
| `S3_SECRET_ACCESS_KEY` | For uploads | Secret paired with `S3_ACCESS_KEY_ID`. |
| `S3_STOREFRONT_STAGING_BUCKET_NAME` | For uploads | Dedicated private staging bucket. It must differ from every public media bucket. |
| `STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS` | For uploads | Integer from 1 through 7; default `1`. The bucket must have an enabled delete rule at least this strict. |
| `STOREFRONT_IMAGE_DECODE_CONCURRENCY` | Optional tuning | Integer `1` or `2`; default `1`. Keep `1` unless process memory has been measured under representative uploads. |
| `S3_BLOG_BUCKET_NAME` | For published images | Public blog-assets bucket that receives sanitized storefront assets. It cannot be the staging bucket. |
| `BLOG_MEDIA_DOMAIN` | For published images | Public CDN/domain used to serve sanitized assets from `S3_BLOG_BUCKET_NAME`. |

Browser-direct uploads also derive allowed origins from `FRONTEND_URL` and
`CORS_ORIGINS`. The exact frontend origin must be present.

### Optional trusted-ingress values

Public inquiry rate limits use the direct peer address unless both values below
are configured:

| Variable | Required | Contract |
| --- | --- | --- |
| `TRUSTED_PROXY_CIDRS` | Optional | JSON array or comma-separated CIDRs for only the direct ingress peers controlled by the platform. |
| `TRUSTED_PROXY_CLIENT_IP_HEADER` | Optional | One of `CF-Connecting-IP`, `True-Client-IP`, `X-Real-IP`, or `X-Forwarded-For`; ingress must overwrite it with one IP. |

Leave both unset unless the direct proxy networks are known and the ingress
guarantees a single overwritten header. An attacker-supplied forwarding header
must never become a rate-limit identity.

### Example shape

Use different real values for staging and production:

```dotenv
FRONTEND_URL=https://staging.thespecialwedding.io
NEXT_PUBLIC_API_BASE_URL=https://api.staging.thespecialwedding.io
STOREFRONT_PLATFORM_DOMAINS=["staging.thespecialwedding.io","thespecialwedding.io","thespecialwedding.com"]
STOREFRONT_CNAME_TARGET=storefronts-staging.thespecialwedding.io

CLOUDFLARE_ACCOUNT_ID=0123456789abcdef0123456789abcdef
CLOUDFLARE_ZONE_ID=replace-with-zone-id
CLOUDFLARE_API_TOKEN=replace-with-secret-token

S3_ENDPOINT_URL=https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com
S3_REGION=auto
S3_ACCESS_KEY_ID=replace-with-r2-access-key
S3_SECRET_ACCESS_KEY=replace-with-r2-secret
S3_BLOG_BUCKET_NAME=blog-assets-staging
BLOG_MEDIA_DOMAIN=blog-media-staging.thespecialwedding.io
S3_STOREFRONT_STAGING_BUCKET_NAME=storefront-staging-staging
STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS=1
STOREFRONT_IMAGE_DECODE_CONCURRENCY=1

TRUSTED_PROXY_CIDRS=[]
# TRUSTED_PROXY_CLIENT_IP_HEADER=CF-Connecting-IP
```

The example account ID is intentionally fake. Never commit real tokens or
credentials.

## Configure Cloudflare for SaaS

1. Add the platform zone to the intended Cloudflare account and enable
   Cloudflare for SaaS.
2. Create a proxied DNS record for the fallback origin and point it to the
   deployed frontend origin.
3. Set that record as the Cloudflare for SaaS fallback origin and wait until its
   provider status is `Active`.
4. Create a friendly proxied CNAME target, such as
   `storefronts.thespecialwedding.io`, pointing to the fallback origin.
5. Set that exact hostname as `STOREFRONT_CNAME_TARGET` on both frontend and
   backend.
6. Create a scoped Cloudflare REST API token. Restrict it to the intended
   account and SaaS zone. This token is separate from the R2 S3 access-key pair.
   The application needs:
   - `SSL and Certificates Write` for create/get/list/delete custom-hostname calls.
   - Account-level `Workers R2 Storage Read` for the R2 managed-domain,
     custom-domain, CORS, and lifecycle REST endpoints. Bucket-scoped R2
     `Object Read & Write` S3 credentials do not authorize these control-plane
     REST calls.
7. Set `CLOUDFLARE_ZONE_ID`, `CLOUDFLARE_ACCOUNT_ID`, and the token on the
   backend only.

The application creates custom hostnames using TXT domain-control validation
and TLS 1.2 minimum. A hostname is routable only after both Cloudflare's
hostname status and certificate status are `active`. The planner UI displays
the customer DNS and validation records returned by Cloudflare.

For ordinary subdomains, the customer creates a CNAME from their storefront
hostname to `STOREFRONT_CNAME_TARGET`. Apex domains require a DNS-provider
flattening feature or Cloudflare's separately entitled apex-proxying behavior;
do not tell a customer to invent an apex CNAME where their DNS provider forbids
one.

## Configure the private R2 staging bucket

1. Create a bucket dedicated to this environment and set its name in
   `S3_STOREFRONT_STAGING_BUCKET_NAME`.
2. Confirm it is not any of the buckets configured by `S3_BUCKET_NAME`,
   `S3_GUEST_MEDIA_BUCKET_NAME`, `S3_AD_BUCKET_NAME`, `S3_BLOG_BUCKET_NAME`, or
   `S3_FORM_UPLOADS_BUCKET_NAME`.
3. Disable the Cloudflare-managed `r2.dev` URL.
4. Remove or disable every R2 custom domain attached to the staging bucket.
5. Add an enabled object-deletion lifecycle rule:
   - prefix: `storefront/`
   - action: delete objects
   - age: no more than `STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS` (one day by
     default)
6. Configure bucket CORS to allow the exact `FRONTEND_URL` origin to issue
   `PUT` requests with the `Content-Type` header. Add staging and production as
   separate exact rules only if one bucket is intentionally shared; separate
   buckets are preferred.
7. Create S3-compatible credentials scoped to the staging and blog-assets
   buckets with bucket-list plus object get, put, and delete access. Presigned
   browser PUTs use the same scoped credential; no bucket-admin permission is
   needed by the S3 data path.

The Cloudflare dashboard accepts this CORS-policy shape; replace the origin
with the exact environment frontend origin and do not use `*` in production:

```json
[
  {
    "AllowedOrigins": ["https://staging.thespecialwedding.io"],
    "AllowedMethods": ["PUT"],
    "AllowedHeaders": ["Content-Type"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

At upload reservation time, the backend rechecks all of the following through
Cloudflare's API:

- the R2 endpoint account matches `CLOUDFLARE_ACCOUNT_ID`;
- `r2.dev` access is disabled;
- no attached R2 custom domain is enabled;
- a qualifying `storefront/` deletion lifecycle exists.

If any check is unavailable or ambiguous, the reservation fails closed. The
backend never treats an unverifiable bucket as private.

## Deploy safely

1. Configure the staging frontend and backend with their independently scoped
   values.
2. Redeploy both services after changing storefront configuration. A change to
   `NEXT_PUBLIC_API_BASE_URL` specifically requires rebuilding/redeploying the
   frontend image because Next.js may inline it into middleware. The other
   server-side storefront host values are read at runtime, but an immutable
   deployment should still roll a new frontend instance so every request path
   sees one coherent configuration.
3. Review startup configuration warnings. Partial custom-domain configuration,
   invalid CNAME targets, unverifiable browser-upload CORS, and failed private
   staging/lifecycle preflight are reported to the root-admin configuration
   notification flow. A deliberate deployment with no custom-domain values
   produces no custom-domain warning; other missing platform or upload
   prerequisites are still reported independently. All external storage checks
   share one read-only three-second startup deadline, and configured secrets are
   redacted from warning text.
4. Verify staging using a dedicated test planner. Do not use a production
   planner or copy live customer data.
5. Promote the same application SHA to production, then set independently
   scoped production secrets and repeat the checks.

## Acceptance checks

Run these in order:

1. **Host boundary:** the platform host serves `/admin/packages`; an unknown or
   custom host requesting `/admin/packages` receives `404` rather than a login
   redirect.
2. **Slug preview:** an eligible test planner can save settings and open
   `/storefront/{slug}?preview=1` while the storefront remains unpublished.
3. **Public publication:** after explicit publication, `/storefront/{slug}`
   renders the same design and packages. Unpublishing makes the public read fail
   closed without deleting settings.
4. **Image pipeline:** reserve, upload, and finalize a small JPEG, PNG, or WebP.
   Confirm the stored public URL uses `BLOG_MEDIA_DOMAIN`, not the private staging
   bucket.
5. **Private staging:** confirm the test upload cannot be fetched through an
   `r2.dev` URL or an R2 custom domain and is covered by the deletion lifecycle.
6. **Custom domain:** connect a disposable test subdomain, install the DNS/TXT
   records shown in the UI, and wait for both hostname and SSL status to become
   active.
7. **Custom-host isolation:** the custom-host root renders its own storefront;
   another planner slug, admin routes, arbitrary API routes, and query variants
   return `404`.
8. **Inquiry:** submit once with an approved test recipient and confirm one
   visible success state, one inquiry record, and one planner notification.
9. **Disconnect:** remove the disposable custom domain through the application,
   confirm its root stops routing, and then remove the customer DNS records.

Do not mark the rollout ready based only on the Cloudflare dashboard showing a
certificate. The application requires the exact owner mapping, current premium
entitlement, explicit publication, active hostname status, and active SSL status.

## Failure and rollback behavior

- Missing custom-domain configuration disables new connect/refresh/delete
  provider operations; the platform slug remains the canonical path.
- Missing or unsafe R2 staging configuration disables new image reservations;
  previously published assets remain in the public bucket.
- A failed provider deletion remains recorded for background cleanup instead of
  pretending Cloudflare removed it.
- A provider `404` revokes the stale mapping so it cannot keep routing.
- Changing a subscription, downgrading a planner, or toggling publication is
  never an infrastructure rollback step.
- If a deployment must be rolled back, redeploy the previous application SHA.
  Keep the CNAME target and fallback origin stable while existing custom
  hostnames are still expected to work.

## Troubleshooting

| Symptom | Meaning and action |
| --- | --- |
| `Cloudflare custom-hostname credentials are not configured` | Set backend `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID`, then restart the backend. |
| `S3_ENDPOINT_URL must be an official account-scoped R2 endpoint` | Use the exact HTTPS R2 account endpoint without a bucket path, query, port, or credentials. |
| `S3_ENDPOINT_URL and CLOUDFLARE_ACCOUNT_ID must identify the same Cloudflare account` | Correct the endpoint or account ID; do not bypass the check. |
| `Storefront staging privacy and lifecycle could not be verified` | Check token scope, account ID, jurisdiction, bucket name, and Cloudflare API reachability. |
| `Storefront staging managed public access (r2.dev) must be verifiably disabled` | Disable the bucket's public development URL. |
| `Storefront staging custom domain access must be verifiably disabled` | Disable or remove every enabled R2 custom domain from the staging bucket. |
| `Storefront staging requires an enabled expiry lifecycle rule` | Add or tighten the enabled `storefront/` delete rule. |
| Upload CORS warning | Allow exact frontend origin + `PUT` + `Content-Type` on the staging bucket. |
| Custom domain remains pending | Confirm the fallback origin is active, customer CNAME points to `STOREFRONT_CNAME_TARGET`, and every TXT validation record displayed by the UI exists. |
| Custom-host `/admin/*` returns `404` | Expected tenant-boundary behavior. Admin routes are platform-host only. |

## Cloudflare references

- [Configure Cloudflare for SaaS](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/getting-started/)
- [Custom-hostname API and token permission](https://developers.cloudflare.com/api/resources/custom_hostnames/methods/create/)
- [Confirm custom-hostname readiness](https://developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/common-api-calls/)
- [R2 S3 endpoints and credentials](https://developers.cloudflare.com/r2/get-started/s3/)
- [R2 token types and permissions](https://developers.cloudflare.com/r2/api/tokens/)
- [R2 public access controls](https://developers.cloudflare.com/r2/buckets/public-buckets/)
- [R2 object lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
- [R2 browser-upload CORS](https://developers.cloudflare.com/r2/buckets/cors/)
- [R2 managed-domain status API](https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/domains/subresources/managed/methods/list/)
- [R2 custom-domain status API](https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/domains/subresources/custom/methods/list/)
- [R2 lifecycle status API](https://developers.cloudflare.com/api/resources/r2/subresources/buckets/subresources/lifecycle/methods/get/)
