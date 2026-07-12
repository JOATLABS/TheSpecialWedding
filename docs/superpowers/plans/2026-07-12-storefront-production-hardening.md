# Storefront Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a secure, premium planner storefront whose internal slug preview, public publication, package rendering, custom-domain connection, media uploads, and inquiries work end to end without changing live subscription or account data.

**Architecture:** Storefront eligibility is resolved from the authenticated planner owner's active subscription and canonical plan feature flags. Settings remain planner-owned and durable; losing eligibility never edits the subscription, deletes settings, or clears the planner's publication choice—it only makes management and public serving fail closed until eligibility returns. A dedicated storefront service owns slug/settings/public DTO logic, a dedicated domain service owns Cloudflare state, and typed frontend clients consume `/admin/storefront/*` while public rendering consumes `/api/storefront/*`.

**Tech Stack:** FastAPI, Motor/MongoDB, Pydantic v2, Next.js App Router, React, TypeScript, Cloudflare for SaaS, R2 presigned PUT uploads, Node test runner, pytest/mongomock.

## Global Constraints

- Do not mutate any live user subscription, plan assignment, billing status, or account record as part of implementation or verification.
- `plan_solo` and `plan_boutique` do not include `planner_storefront` or `custom_domain`; `plan_signature` and `plan_enterprise` include both features.
- `planner_storefront` and `custom_domain` remain separate canonical feature flags even while the current tier mapping grants them to the same two plans.
- Boolean storefront eligibility reads the current `subscription_plans.features` catalog for the active owner subscription. It does not rewrite or consult historical `plan_snapshot` feature dictionaries.
- An eligibility loss does not clear `is_published`, delete settings, remove uploaded media, rewrite `plan_snapshot`, or modify a subscription; public and management reads simply fail closed while ineligible.
- Storefront management is planner-owner scoped. Team members, advertising vendors, couples, and unrelated admins cannot manage a planner storefront through these owner routes.
- Storefront settings are the source of truth for `slug`, explicitly authored public contact fields, design fields, module visibility, and `is_published`; Cloudflare is only a projection for an optional verified custom domain.
- Generic settings writes cannot set custom-domain lifecycle fields.
- Public responses expose allowlisted DTO fields only and include active, non-template packages only.
- Preview uses the platform slug path and authenticated admin session; it does not require a custom domain or public publication.
- Custom domains are public only after both hostname and SSL readiness are active; pending candidates never resolve publicly.
- Browser media uploads use the existing presigned-PUT R2 convention, a server-owned `storefront/{planner_id}` prefix, the existing JPEG/PNG/WebP allowlist, and a 5 MB client/server contract.
- New route and domain string constants must be centralized; service code must not introduce plan-name substring checks.
- All feature behavior follows test-driven development: each production change must be preceded by a focused failing test and recorded RED/GREEN evidence.
- Keep the existing dirty `main` checkout untouched; all work lands only on `codex/storefront-hardening` in the isolated worktree.

## Acceptance Matrix

| Scenario | Required result |
| --- | --- |
| Solo or Boutique planner opens `/admin/packages` | Configure Storefront opens storefront-specific upgrade UX and links to `/admin/planner/billing`; no settings/domain/upload mutation succeeds directly. |
| Signature or Enterprise planner with active subscription | Access endpoint reports storefront and custom-domain eligibility; settings can create/edit round-trip. |
| Missing, cancelled, expired, suspended, or past-due eligible-plan subscription | Access fails closed; stored settings and `is_published` remain unchanged; public route returns 404. |
| Team member or advertising vendor calls owner storefront routes | HTTP 403 with no write. |
| First settings save | Valid normalized unique slug persists with planner ownership and default `is_published=false`; no user-profile email or phone is published implicitly. |
| Edit save without changing slug/domain | Design, explicit contact fields, module flags, slug, and publication choice round-trip without clearing unrelated state. |
| Slug edit after first publication | Rejected with a stable-link explanation; changing a published slug requires a future redirect-alias lifecycle rather than silently breaking links. |
| Duplicate or reserved slug | HTTP 409/422; existing settings remain unchanged. |
| Draft preview | `/storefront/{slug}?preview=1` renders saved design for the authenticated owner even when unpublished; unauthenticated preview is 404. |
| Public slug | Only published, currently eligible settings resolve; no valid-user fallback exists. |
| Public packages | Query uses `planner_id`, `status="active"`, `is_template=false`; response maps `total_amount`, `currency`, and included services only. |
| Custom-domain create | Domain is normalized/validated/reserved uniquely; candidate is stored pending; generic settings cannot bypass it. |
| Custom-domain status | Candidate becomes active only when Cloudflare hostname and SSL are active. |
| Cloudflare missing credentials or create failure | HTTP 503/400; no mock or false-success row is persisted. |
| Custom-domain delete failure | Local active/pending state remains and request reports retryable failure; successful delete clears lifecycle fields. |
| Request to an active custom host root | Next proxy rewrites to `/storefront/{normalized-host}`; first-party/local hosts are never rewritten. |
| Image browse/drop | Keyboard, pointer, mobile picker, type, and 5 MB checks work; API returns `upload_url`, `cdn_url`, `key`, and `max_size_bytes`. |
| Storefront inquiry | Valid public storefront accepts rate-limited inquiry, stores owner-scoped allowlisted fields, and attempts planner notification; invalid/private storefront returns 404. |
| Settings modal close after pending uploads | Unsaved pending keys are deleted through the owner-scoped cleanup endpoint; saved referenced URLs remain. |
| Public/contact UI | Prices/services use the public DTO and inquiry form submits with visible success/error states. |

## Route Inventory

- Owner access/settings: `GET /admin/storefront/access`, `GET /admin/storefront/settings`, `POST /admin/storefront/settings`.
- Owner preview: `GET /admin/storefront/preview/{slug}`.
- Domain lifecycle: `POST /admin/storefront/custom-domain`, `GET /admin/storefront/custom-domain/status`, `DELETE /admin/storefront/custom-domain`.
- Media lifecycle: `GET /admin/storefront/upload-url`, `POST /admin/storefront/upload-complete`, `DELETE /admin/storefront/upload`.
- Public read/inquiry: `GET /api/storefront/{identifier}`, `POST /api/storefront/{identifier}/inquiries`.
- Frontend pages: `/admin/packages`, `/storefront/[identifier]`, and custom-host `/` rewritten by `proxy.ts`.

---

### Task 1: Canonical Entitlements And Plan Truth

**Files:**
- Create: `app/constants/storefront.py`
- Create: `app/services/storefront_entitlement_service.py`
- Create: `app/dependencies/storefront_access.py`
- Modify: `scripts/seed_subscription_plans.py`
- Modify: `app/api/subscription_management.py`
- Modify: `app/page.tsx`
- Modify: `public/llms.txt`
- Modify: `tests/unit/llmsTxt.test.ts`
- Test: `tests/backend/test_storefront_entitlements.py`
- Test: `tests/backend/test_storefront_plan_contract.py`

**Interfaces:**
- Produces constants `STOREFRONT_FEATURE = "planner_storefront"` and `CUSTOM_DOMAIN_FEATURE = "custom_domain"`.
- Produces `StorefrontEntitlements(owner_id: str, plan_id: str | None, storefront_enabled: bool, custom_domain_enabled: bool)`.
- Produces `StorefrontEntitlementService.resolve_for_owner(user_data: dict) -> StorefrontEntitlements` and `resolve_for_planner_id(planner_id: str) -> StorefrontEntitlements` using the active subscription's current plan catalog features.
- Produces `require_storefront_owner()` and `require_storefront_feature(feature_name)` dependencies.

- [x] **Step 1: Write entitlement and plan-contract tests**

  Add tests proving Solo/Boutique false, Signature/Enterprise true, active-status enforcement, current-catalog feature authority even when a stale snapshot exists, missing-data fail-closed behavior, planner-owner role enforcement, and no writes to `users`, `user_subscriptions`, or `subscription_plans`. Parse both seed sources and assert exact feature parity.

- [x] **Step 2: Run the focused tests and capture RED**

  Run: `PYTHONPATH=. /Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/pytest tests/backend/test_storefront_entitlements.py tests/backend/test_storefront_plan_contract.py -q --tb=short`

  Expected RED: imports/constants are missing and current fallback plan features disagree.

- [x] **Step 3: Add canonical constants and entitlement resolution**

  Implement the immutable result type and fail-closed resolver. Resolve the planner owner's active subscription using canonical active statuses, load boolean features from the current `subscription_plans` row, leave `plan_snapshot` untouched, and never write during resolution. Reject non-planner owner roles before a route can use the result.

- [x] **Step 4: Align both seed paths and public plan copy**

  Bump `SEED_VERSION` to `2026-07-12T00:00:00+00:00`. Add both flags as false for Solo/Boutique and true for Signature/Enterprise in the boot seed and manual fallback. Update server-rendered/public authority copy so it no longer labels custom domains unsupported.

- [x] **Step 5: Run focused backend and public-copy tests and capture GREEN**

  Run the Step 2 command, then `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npm test -- tests/unit/llmsTxt.test.ts`.

- [x] **Step 6: Commit Task 1**

  Commit subject: `feat: centralize storefront entitlements`

---

### Task 2: Planner-Owned Settings, Stable Slug, Preview, And Public DTO

**Files:**
- Create: `app/models/storefront.py`
- Create: `app/services/storefront_service.py`
- Replace: `app/api/storefront.py`
- Modify: `app/core/database_indexes.py`
- Modify: `app/main.py`
- Test: `tests/backend/test_storefront_service.py`
- Test: `tests/backend/test_storefront_api_contract.py`
- Test: `tests/backend/test_storefront_indexes.py`

**Interfaces:**
- `normalize_storefront_slug(value: str) -> str` returns lowercase ASCII hyphenated slugs between 3 and 64 characters and rejects reserved identifiers.
- `StorefrontService.get_access(owner)`, `get_settings(owner)`, `update_settings(owner, payload)`, `get_owner_preview(owner, slug)`, and `get_public_storefront(identifier)` own all Mongo queries and DTO projection.
- Settings updates accept only `slug`, `title`, `description`, `contact_email`, `contact_phone`, `hero_asset_id`, `about_asset_id`, `theme_color`, `packages_enabled`, `reviews_enabled`, and `is_published`.
- Public DTO package fields are `_id`, `name`, `description`, `total_amount`, `currency`, and `services[{name, description}]`.

- [ ] **Step 1: Write service, route, and index tests**

  Cover create/edit round-trip, explicit contact privacy, slug normalization/conflicts, slug immutability after first publication, planner ownership, forbidden roles, generic-domain-field rejection, draft authenticated preview, unauthenticated preview denial, published eligibility, retained settings during eligibility loss, active non-template package filtering, strict public field projection, route prefixes/methods, and unique indexes for `planner_id` and `slug`.

- [ ] **Step 2: Run focused tests and capture RED**

  Run: `PYTHONPATH=. /Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/pytest tests/backend/test_storefront_service.py tests/backend/test_storefront_api_contract.py tests/backend/test_storefront_indexes.py -q --tb=short`

  Expected RED: service/models/indexes do not exist and current public fallback exposes any valid user.

- [ ] **Step 3: Implement models and service source of truth**

  Implement Pydantic request/response models with strict extra-field rejection, explicit contact validation, color/length validation, stable UTC timestamps, ownership-scoped upsert, duplicate-key translation to HTTP 409, stable-slug enforcement after first publication, and DTO projection. Do not accept domain lifecycle fields or arbitrary image URLs in settings.

- [ ] **Step 4: Implement owner/public routes and indexes**

  Mount authenticated routes only under `/admin/storefront/*`; retain public reads only under `/api/storefront/*`. Public reads require stored `is_published=true` plus current eligibility. Owner preview requires the authenticated owner, matching slug, and storefront eligibility but ignores publication. Add startup indexes through `create_all_indexes()`.

- [ ] **Step 5: Run focused tests and capture GREEN**

  Re-run the Step 2 command with zero failures.

- [ ] **Step 6: Commit Task 2**

  Commit subject: `feat: secure storefront settings and public data`

---

### Task 3: Custom Domain, Media, And Inquiry Lifecycles

**Files:**
- Create: `app/services/storefront_domain_service.py`
- Create: `app/services/storefront_inquiry_service.py`
- Modify: `app/services/cloudflare_service.py`
- Modify: `app/services/blog_upload_service.py`
- Modify: `app/api/storefront.py`
- Modify: `app/core/settings.py`
- Modify: `.env.example`
- Modify: `app/core/database_indexes.py`
- Test: `tests/backend/test_storefront_domain_service.py`
- Test: `tests/backend/test_storefront_media.py`
- Test: `tests/backend/test_storefront_inquiries.py`

**Interfaces:**
- `normalize_custom_domain(value: str) -> str` accepts a hostname only, lowercases/IDNA-normalizes it, and rejects schemes, ports, paths, localhost, IP literals, and first-party platform hosts.
- `StorefrontDomainService.connect(owner, domain)`, `refresh(owner)`, and `remove(owner)` own all Cloudflare/Mongo state transitions in `storefront_domains`, separate from `storefront_settings`.
- `CloudflareService` requires explicit token and zone configuration; no mock-success branch exists.
- Upload response is `{asset_id, upload_url, cdn_url, key, max_size_bytes}` with `key` inside `storefront/{owner_id}/`; `storefront_assets` is the source of truth for reserve/finalize/attach/cleanup state.
- Inquiry capture stores planner/slug/contact/wedding/message/request metadata and attempts planner email notification without losing the persisted inquiry if email delivery fails.

- [ ] **Step 1: Write domain, media, and inquiry failing tests**

  Cover normalization, duplicate reservation, pending versus active domain, hostname+SSL promotion, missing credentials, Cloudflare create/database compensation, delete failure state retention, owner-scoped upload prefixes, disallowed type/oversize finalization cleanup, foreign-key deletion denial, published-storefront inquiry gating, input validation, rate limiting, persistence, and notification failure resilience.

- [ ] **Step 2: Run focused tests and capture RED**

  Run: `PYTHONPATH=. /Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/pytest tests/backend/test_storefront_domain_service.py tests/backend/test_storefront_media.py tests/backend/test_storefront_inquiries.py -q --tb=short`

  Expected RED: current Cloudflare mock branch, client-controlled folder, and missing inquiry lifecycle violate assertions.

- [ ] **Step 3: Implement fail-closed Cloudflare lifecycle**

  Reserve and track candidates in `storefront_domains`, separate from design settings. Promote only when hostname status and SSL status are both active. Preserve the child row and mark cleanup retry state when provider deletion fails. Compensate by deleting the newly created Cloudflare hostname if Mongo persistence fails.

- [ ] **Step 4: Implement owner-scoped presign/finalize/delete**

  Remove the public `folder` parameter. Reserve an owner/slot-scoped asset, return canonical upload keys, sign the declared size where supported, HEAD-validate the same 5 MB/type contract before marking an asset ready, delete invalid completions, and reject finalize/cleanup/attach operations outside the authenticated owner.

- [ ] **Step 5: Implement public inquiry capture**

  Add `POST /api/storefront/{identifier}/inquiries`, validate the storefront through the same public resolver, apply per-IP/identifier rate limits, persist allowlisted fields, and send a planner notification using the existing Resend service contract.

- [ ] **Step 6: Run focused tests and capture GREEN**

  Re-run the Step 2 command with zero failures.

- [ ] **Step 7: Commit Task 3**

  Commit subject: `feat: complete storefront external lifecycles`

---

### Task 4: Typed Admin Configuration And Design Preview UX

**Files:**
- Create: `app/services/storefrontApi.ts`
- Create: `app/components/storefront/StorefrontView.tsx`
- Create: `app/components/storefront/StorefrontImagePicker.tsx`
- Rewrite: `app/admin/packages/StorefrontSettingsModal.tsx`
- Rewrite: `app/admin/components/storefront/CustomDomainManager.tsx`
- Modify: `app/admin/packages/page.tsx`
- Modify: `app/components/ui/UpgradeModal.tsx`
- Test: `tests/unit/storefrontApi.test.ts`
- Test: `tests/unit/storefrontAdminContract.test.ts`

**Interfaces:**
- `StorefrontApiTransport` matches `AdminContext.apiRequest`.
- `getStorefrontAccess`, `getStorefrontSettings`, `saveStorefrontSettings`, `getStorefrontPreviewUrl`, `connectCustomDomain`, `refreshCustomDomain`, `removeCustomDomain`, `uploadStorefrontImage`, and `deleteStorefrontUpload` centralize exact `/admin/storefront/*` paths.
- `uploadStorefrontImage(file, slot, transport, fetchImpl)` validates JPEG/PNG/WebP and 5 MB before reserve, PUTs to `upload_url`, finalizes `asset_id`, and returns the ready asset.
- `StorefrontView` is a pure shared renderer used by both the modal's live design preview and the public storefront.

- [ ] **Step 1: Write typed client and admin-contract failing tests**

  Assert exact route families, payload/response keys, file checks, reserve/upload/finalize order, cleanup behavior, canonical access booleans rather than plan substring checks, storefront-specific upgrade copy/CTA, accessible file input semantics, slug/publication controls, custom-domain capability separation, live design preview behavior, and Save & Preview behavior.

- [ ] **Step 2: Run focused tests and capture RED**

  Run: `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npx tsx --test tests/unit/storefrontApi.test.ts tests/unit/storefrontAdminContract.test.ts`

  Expected RED: typed client is missing and current source contains `/api/storefront/*` plus plan substring gating.

- [ ] **Step 3: Implement typed client and entitlement-driven entry point**

  Fetch access on `/admin/packages`; open settings only when `storefront_enabled`, otherwise pass storefront-specific title, description, feature list, CTA label, and `/admin/planner/billing` destination to `UpgradeModal`.

- [ ] **Step 4: Implement settings, upload, and domain UX**

  Replace `any` settings with typed saved/draft state. Add explicit contact fields, editable pre-publication slug with platform URL, explicit publication switch, pointer/keyboard/mobile file input, local object-URL preview, error/success feedback, pending-asset tracking, and cleanup on close or failed save. Render custom-domain controls only when `custom_domain_enabled` and state clearly that domain operations apply immediately and are separate from design settings.

- [ ] **Step 5: Implement the real live design preview**

  Add Edit and Preview views inside the modal. Render the shared `StorefrontView` from current draft settings plus owner package/review preview data so unsaved design changes are visible without DNS, publication, or an external domain. Preview mode disables inquiry submission.

- [ ] **Step 6: Implement Save & Preview**

  Save the current design, then open `/storefront/{savedSlug}?preview=1` in a new tab. A draft can preview without being published and without a custom domain.

- [ ] **Step 7: Run focused tests and capture GREEN**

  Re-run the Step 2 command with zero failures.

- [ ] **Step 8: Commit Task 4**

  Commit subject: `feat: deliver storefront configuration workflow`

---

### Task 5: Public Storefront, Custom-Host Routing, And Conversion Flow

**Files:**
- Create: `app/storefront/storefrontTypes.ts`
- Create: `app/storefront/StorefrontInquiryForm.client.tsx`
- Rewrite: `app/storefront/[domain]/page.tsx`
- Create: `app/utils/storefrontHost.ts`
- Modify: `proxy.ts`
- Modify: `CHANGELOG.md`
- Test: `tests/unit/storefrontPublicContract.test.ts`
- Test: `tests/unit/storefrontHostRouting.test.ts`
- Test: `tests/unit/storefrontInquiryForm.test.tsx`

**Interfaces:**
- `resolveStorefrontRewriteHost(hostHeader: string | null, pathname: string) -> string | null` returns a normalized custom host only for root-path requests on non-platform hosts.
- Public page fetches `/api/storefront/{identifier}` with revalidation; authenticated `preview=1` forwards the `admin_token` cookie to `/admin/storefront/preview/{slug}` with `cache: "no-store"`.
- Inquiry form posts the public request model and renders submitting, success, validation, rate-limit, and retry states.

- [ ] **Step 1: Write public rendering, host routing, and inquiry UI failing tests**

  Assert total-amount/currency/service rendering, no `price/features` legacy fields, preview auth forwarding/no-store behavior, active custom-host root rewrite, platform/local host pass-through, non-root custom-host pass-through, inquiry payload, and visible success/error states.

- [ ] **Step 2: Run focused tests and capture RED**

  Run: `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npx tsx --test tests/unit/storefrontPublicContract.test.ts tests/unit/storefrontHostRouting.test.ts tests/unit/storefrontInquiryForm.test.tsx`

  Expected RED: current page renders incompatible package fields, proxy has no host rewrite, and form has no submit handler.

- [ ] **Step 3: Implement public data rendering and authenticated preview fetch**

  Render only typed public DTO data through the shared `StorefrontView`, format currency through `Intl.NumberFormat`, display included service names, expose only settings-authored contact details, and keep preview requests private/no-store.

- [ ] **Step 4: Implement safe custom-host rewrite**

  Normalize `Host`/`x-forwarded-host`, exclude localhost, IPs, platform frontend/API/staging hosts, and rewrite only `/` to `/storefront/{encodedHost}`.

- [ ] **Step 5: Implement inquiry conversion flow**

  Replace the decorative form with the client component, associate every label/input, validate required fields, submit to the public inquiry route, and retain user-entered values on failure.

- [ ] **Step 6: Update changelog**

  Record the entitlement, route, privacy, lifecycle, preview, upload, package DTO, custom-host, and inquiry fixes plus any genuinely remaining operational follow-up.

- [ ] **Step 7: Run focused tests and capture GREEN**

  Re-run the Step 2 command with zero failures.

- [ ] **Step 8: Commit Task 5**

  Commit subject: `feat: launch secure public storefront flow`

---

## Final Verification And Hostile Review

**Storefront branch deployment gate: BLOCKED** until Task 3 restores the secure media/domain endpoints and Tasks 4-5 complete the typed admin, preview, inquiry, and public rendering contracts. Intermediate task commits are not independently deployable.

- [ ] Generate a whole-branch review package from `fbef0023` to `HEAD` and dispatch the final senior reviewer.
- [ ] Fix and re-review every Critical or Important finding.
- [ ] Run `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npm run lint`.
- [ ] Run `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npm run type-check`.
- [ ] Run `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npm test`.
- [ ] Run `PATH=/Users/emmanuelakinwale/.nvm/versions/node/v22.23.0/bin:$PATH npm run build`.
- [ ] Run `/Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/ruff check app/` and `/Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/ruff format --check app/` with `PYTHONPATH=.`.
- [ ] Run `PYTHONPATH=. /Users/emmanuelakinwale/Developer/WeddingWebApp/.venv.nosync/bin/pytest tests/backend/test_app_boot_smoke.py tests/backend/test_storefront_entitlements.py tests/backend/test_storefront_plan_contract.py tests/backend/test_storefront_service.py tests/backend/test_storefront_api_contract.py tests/backend/test_storefront_indexes.py tests/backend/test_storefront_domain_service.py tests/backend/test_storefront_media.py tests/backend/test_storefront_inquiries.py -q --tb=short`.
- [ ] Start the testbed with frontend, seed a Signature planner plus Solo planner, and visibly verify upgrade gating, settings round-trip, draft preview, publication, package rendering, image picker, domain pending state, and inquiry success in a real browser.
- [ ] Re-run `git diff --check fbef0023..HEAD` and inspect `git status --short`.
- [ ] Mark the goal complete only after the acceptance matrix and adversarial checklist are satisfied.
