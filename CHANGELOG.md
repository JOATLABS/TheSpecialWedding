# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Planner calendar now honors the shared dark/light theme toggle across the full route surface** (`/app/admin/planner/calendar/page.tsx`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/app/admin/planner/calendar/components/TaskModal.tsx`) — The theme toggle in the shared workspace header was already flipping the global `dark` class correctly, but the planner calendar route ignored it because the page shell, Google Calendar connection panel, and task modal were written almost entirely with light-only Tailwind tokens (`bg-white`, `text-slate-900`, `border-slate-200`, etc.) and no `dark:` counterparts. The calendar surface now follows the same admin dark-mode contract as the rest of the platform, including cards, filters, agenda items, availability panels, connection controls, and modal form fields. Live verification also reconfirmed that local UI checks can lie if `localhost:3000` is still serving the Desktop checkout instead of the active worktree, so this proof was run only after restarting both `3000` and `8000` from the current branch.
- **Admin and vendor authenticated workspaces now share one shell contract instead of drifting as parallel chrome implementations** (`/app/components/layout/WorkspaceChrome.tsx`, `/app/admin/layout.tsx`, `/app/admin/AdminLayoutClient.tsx`, `/app/admin/components/Sidebar.tsx`, `/app/admin/components/TopHeader.tsx`, `/app/portal/ads/layout.tsx`, `/tests/media-storage-centralization.spec.ts`) — Extracted shared workspace background, responsive sidebar state, shell frame, sidebar chrome, and top-header chrome so root admin, planner, and vendor surfaces stop re-implementing the same layout mechanics with small class drift. Admin and vendor still own their role-specific nav/auth behavior, but the actual shell now comes from one source of truth, and the browser regression helper was updated to the new vendor user-menu contract. Live verification also re-confirmed that local shell work can be invalidated by stale `localhost:3000` / `localhost:8000` processes serving the Desktop checkout, so the proof for this slice was run only after restarting both ports from the worktree.
- **Auth and runtime config contracts now fail closed instead of inventing missing state** (`/app/dependencies/auth_extended.py`, `/app/utils/env.ts`, `/tests/unit/envRuntimeConfig.test.ts`) — Added a typed `subscription_status` field to `ExtendedAuthUser` so planner billing and checkout code no longer depend on an undeclared dynamic attribute, and removed the server-side localhost API fallback from the frontend env runtime helper. Missing API base configuration now raises a real config error instead of silently pointing the app at a hardcoded local URL.
- **Frontend CI now exports the same placeholder build URL contract used by the image builds** (`/.github/workflows/ci.yml`) — Fixed the PR/frontend-check workflow failing in `next build` with `CRITICAL: Could not resolve API base URL` by exporting `FRONTEND_URL` to the standalone `npm run build` step. The runtime resolver in `app/utils/env.ts` already knows how to derive a server-side API origin from `FRONTEND_URL`, but the non-Docker CI build step was not passing that variable even though the Docker image builds already did.
- **Vendor admin/account lifecycle contracts now stay aligned between `/admin/ads` and the vendor portal shell** (`/app/services/campaignAdvertisingApi.ts`, `/app/admin/ads/page.tsx`, `/app/api/admin_auth.py`, `/app/portal/ads/layout.tsx`, `/tests/backend/test_planner_billing_scope.py`) — Fixed the root-admin `/admin/ads` crash by normalizing raw vendor-account rows from the admin ads API before rendering, instead of assuming a `status/vendor_name/vendor_email` shape the backend did not provide. Also exposed vendor onboarding fields like `business_name`, `vendor_account_status`, `logo_url`, and `must_change_password` from `/admin/profile`, and centralized vendor profile shaping in the portal shell so approved vendors reliably hit the forced-password screen on first login instead of silently bypassing it.
- **Vendor ad portal auth screens now use the shared platform visual language instead of a generic standalone login card** (`/app/portal/ads/layout.tsx`) — Removed the forced sans override from the vendor portal shell so it respects the platform typography, and replaced the plain login/password-change pages with the same wedding-branded glass auth treatment used elsewhere in the product. The vendor auth entry point now reads like part of The Special Wedding instead of a separate default-styled utility page.
- **Admin auth cookies now derive a deterministic shared staging/production domain, clear stale legacy variants, and deploy verification proves the frontend proxy path** (`/app/core/settings.py`, `/app/utils/auth_utils.py`, `/app/api/admin_auth.py`, `/scripts/deploy/verify_environment.py`, `/tests/backend/test_settings.py`, `/tests/integration/conftest.py`, `/tests/integration/test_01_auth.py`) — Fixed the “login succeeds but `/admin` stays on `/admin/login`” regression by making `COOKIE_DOMAIN` explicit and normalized when provided, otherwise deriving a shared cookie scope from `FRONTEND_URL` and `NEXT_PUBLIC_API_BASE_URL` instead of silently relying on a host-only API cookie. Auth responses now also clear older host-only and narrowly scoped cookie variants so pre-fix staging sessions do not keep sending a stale `admin_token`. The deploy smoke check now rejects admin sessions whose login response does not emit a frontend-visible `Domain=` cookie, proves `/admin` and `/admin/planner` survive the Next.js proxy after login, and verifies the notifications stream works with cookie auth alone so cookie/proxy drift fails before rollout.
- **Frontend dependency integrity now fails fast on stale npm installs and the repo is standardized on a single npm workflow** (`/.npmrc`, `/package.json`, `/scripts/ensure-deps.mjs`, `/README.md`, `/docs/setup/dependency-checklist.md`, `/.github/workflows/ci.yml`, `/Dockerfile.frontend`, `/Dockerfile.coolify`) — Replaced the old “`node_modules` exists” check with a real dependency preflight/doctor that verifies direct packages, local CLI binaries, supported Node/npm versions, and `npm ls` tree health before running frontend scripts. The repo now treats `package-lock.json` as the only maintained lockfile, uses repo-level npm config for `legacy-peer-deps`, aligns docs/CI/container installs on plain `npm ci`, adds an explicit `deps:doctor` recovery path, and validates the frontend install/build flow on both Node 20 and Node 24 instead of letting partial installs fail later as `sh: next: command not found`.
- **Browser-upload startup validation now proves bucket CORS per storage target instead of assuming reachable buckets are browser-ready** (`/app/core/settings.py`, `/app/services/media_storage.py`, `/app/services/config_validator.py`, `/tests/backend/test_settings.py`, `/tests/backend/test_media_storage_contract.py`, `/tests/backend/test_config_validator.py`) — Added a canonical `browser_upload_origins` settings property, taught the shared media-storage layer to verify Cloudflare R2 bucket CORS for direct presigned `PUT` uploads, and updated startup config warnings to flag only real browser-upload risks such as missing `PUT`/`Content-Type` CORS coverage on a ready bucket. This closes the remaining gap between “storage credentials work” and “real browser uploads will work” without reintroducing false warnings like the earlier `GUEST_MEDIA_DOMAIN` notification.
- **Vendor ad portal media now uses a shared upload UX instead of raw URL entry, with live browser coverage across all shipped vendor surfaces** (`/app/api/vendor_campaigns.py`, `/app/api/vendor_signup.py`, `/app/services/ad_upload_service.py`, `/app/services/ad_billing_service.py`, `/app/services/vendor_campaign_service.py`, `/app/services/vendor_signup_service.py`, `/app/services/campaignAdvertisingApi.ts`, `/app/portal/ads/layout.tsx`, `/app/portal/ads/components/VendorMediaUploader.tsx`, `/app/portal/ads/creatives/page.tsx`, `/app/portal/ads/campaigns/new/page.tsx`, `/app/portal/ads/settings/page.tsx`, `/scripts/testing/vendor_ad_media_fixture.py`, `/tests/backend/test_vendor_campaigns_api.py`, `/tests/backend/test_vendor_campaign_service.py`, `/tests/backend/test_vendor_signup_service.py`, `/tests/media-storage-centralization.spec.ts`, `/playwright.config.ts`) — Replaced vendor-facing logo and creative URL entry with one vendor-portal uploader backed by vendor-scoped ad-media upload contracts and prefix-separated asset ownership (`ads/{vendor_id}/...` vs `vendor-profiles/{vendor_id}/logo/...`). Creative create/edit flows and vendor settings now round-trip uploaded media correctly, managed replacements remove old vendor-owned assets, vendor logo changes sync into planner-facing campaign card snapshots, and the vendor portal now persists its shared auth token on login so the upload flows survive real browser navigations instead of dropping back to the login shell. The browser suite now proves creative upload from the creatives workspace, campaign-wizard creative upload, and vendor logo upload/replace/remove on `localhost:3000` against the real frontend.
- **Config warnings now follow the real storage contract instead of a generic env checklist** (`/app/services/config_validator.py`, `/tests/backend/test_config_validator.py`) — Removed `GUEST_MEDIA_DOMAIN` from the recommended environment warning contract because guest memories upload/download flows are private and rely on presigned URLs, not a public CDN origin. Storage warnings are now target-aware: ad/blog domains are only recommended when those buckets are actually configured, and configured-but-inaccessible buckets are surfaced as operational warnings instead of being treated as healthy because env vars exist. Clean startup now also resolves stale system-config notifications instead of leaving dead warnings active after the underlying config issue is fixed.
- **Storage readiness now reflects real bucket accessibility, and browser media regressions cover the live upload surfaces that matter** (`/app/core/settings.py`, `/app/services/media_storage.py`, `/app/services/guest_media_service.py`, `/app/services/guestMemoriesApi.ts`, `/app/couple/components/CoupleMemoriesSection.tsx`, `/app/couple/dashboard/page.tsx`, `/app/admin/memories/page.tsx`, `/app/admin/components/kb/ArticleEditor.tsx`, `/app/admin/components/blog/BlogArticleEditor.tsx`, `/tests/backend/test_media_storage_contract.py`, `/tests/media-storage-centralization.spec.ts`) — Shared media storage health checks now probe the configured bucket instead of treating “env vars exist” as equivalent to “browser uploads are ready,” so guest memories and planner memories can surface the real storage issue when a target bucket is inaccessible. The knowledge-base and blog editors now expose stable, accessible image upload controls instead of relying on placeholder text drift, and the live browser verification matrix now proves guest memories upload, the public gallery, planner gallery upload/delete, planner profile image upload/delete, and root-admin knowledge-base image upload against `localhost:3000`.
- **Media storage is now centralized behind one typed storage contract and split by domain service** (`/app/core/settings.py`, `/app/services/media_storage.py`, `/app/services/gallery_media_service.py`, `/app/services/ad_upload_service.py`, `/app/services/blog_upload_service.py`, `/app/services/guest_media_service.py`, `/app/services/vendor_service.py`, `/app/jobs/vendor_scraper/logo_uploader.py`, `/app/api/user_management.py`, `/app/api/admin_backup.py`, `/app/utils/upload_image.py`, `/tests/backend/test_media_storage_contract.py`, `/tests/backend/test_logo_uploader_storage.py`) — Replaced the old mixed gallery/blog/ad upload service with dedicated gallery, ad-asset, and blog-asset services backed by one shared S3/R2 client and target resolver. Bucket/domain normalization now lives in typed settings instead of raw env parsing inside services, adjacent storage consumers now use the same primary/guest/ad/blog target contract, and the stale hardcoded `wedding-gallery` helper path is gone. This reduces storage drift across gallery, profile image, guest media, vendor logo, backup, and blog flows and makes missing bucket/domain config fail deterministically at the storage boundary.
- **Gallery storage now reads the canonical app settings object instead of raw shell env, which fixes local/public gallery drift when `.env` is the source of truth** (`/app/services/gallery_upload_service.py`) — The legacy gallery service was bypassing `app.core.settings` and could end up pointed at a different bucket than the rest of the app runtime, which made `/gallery` fail with misleading `NoSuchBucket` errors even when the configured R2 account and guest-memories bucket were healthy. The gallery client now resolves bucket/endpoint/credentials/frontend URL from the same settings layer the rest of the backend uses.
- **Wedding privacy mode now updates public slug access immediately and the planner privacy editor no longer exposes dead controls** (`/app/admin/weddings/[id]/page.tsx`, `/app/admin/weddings/[id]/PrivacyModeSelector.tsx`, `/app/admin/weddings/[id]/privacySettings.ts`, `/app/api/wedding.py`, `/app/services/guest_verification_service.py`, `/app/utils/weddingPrivacyInfo.ts`, `/tests/backend/test_wedding_privacy_settings_contract.py`, `/tests/unit/privacySettings.test.tsx`, `/tests/unit/weddingPrivacyInfo.test.ts`) — Replaced the oversized native privacy dropdown with a compact mode selector, made privacy mode normalize and clear incompatible settings on save, removed planner-side verification toggles that were not actually enforced by the public slug flow, invalidated cached wedding privacy bootstrap data when planners update the wedding slug or privacy settings, and forced the public slug bootstrap fetch onto `no-store` so switching a wedding to `public` stops leaving `/:slug` and `/:slug/gallery` stuck behind stale verification prompts.
- **Planner suspension lifecycle is now centralized and stale wedding suspension flags no longer block active couple portals** (`/app/services/planner_access_lifecycle_service.py`, `/app/api/saas_config.py`, `/app/services/subscription_service.py`, `/app/services/stripe_service.py`, `/app/services/couple_lifecycle_service.py`, `/tests/backend/test_couple_lifecycle_service.py`, `/tests/backend/test_saas_config_planner_status.py`) — Centralized planner-owned suspension/reactivation cleanup for team members, couples, planner-owned data, and payment links so root-admin planner toggles, subscription cancellations, and Stripe reactivations all use the same downstream lifecycle behavior. Couple portal access now trusts the canonical planner/account lifecycle over stale `weddings.data_access_suspended_reason` flags, which fixes the real frontend case where couples were blocked on `/couple/login` even after the planner account had already been restored.
- **Vendor contract public signing now works in transaction-capable local dev and no longer serves stale contract state** (`/app/main.py`, `/app/services/vendorContractsApi.ts`, `/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/app/vendor-contract/publicContractPageState.ts`, `/tests/unit/publicContractPage.test.tsx`, `/tests/unit/vendorContractsApi.test.ts`) — Stopped the public vendor contract GET path from inheriting the backend’s generic 5-minute cache policy, forced the public contract fetches to `no-store`, and added regression coverage for already-signed initial loads so the vendor page now reflects the live contract status after signing instead of showing a cached unsigned view. The public sign flow also now surfaces backend error details rather than collapsing operational failures into a fake “check your connection” message, which made the local Mongo transaction prerequisite diagnosable during live verification.
- **Public vendor contract signing now treats duplicate sign attempts as idempotent** (`/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/tests/unit/publicContractPage.test.tsx`) — When the backend returns `Contract has already been signed`, the public contract page now closes the sign modal, refetches the canonical contract state, and lands on the signed confirmation instead of showing an error screen and noisy dev-console exception. The page also clears stale error state on successful refetch so repeat public access can recover cleanly after prior failures.
- **Shared calendar request-contract cleanup and targeting-mode policy layer** (`/app/api/planner_calendar.py`, `/app/models/calendar.py`, `/app/models/calendar_connection.py`, `/app/services/google_calendar_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/calendarApi.ts`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/tests/backend/test_shared_calendar_v1_contract.py`, `/docs/plans/calendar/NEXT_CONNECTION_POLICY_LAYER_SPEC.md`) — Removed the last legacy `sync_to_google` compatibility bridge from the shared calendar request surface by rejecting that field at the model boundary and routing canonical task sync intent entirely through `external_sync_requested`. Added the next decision-complete connection policy layer in repo docs and code via `sync_targeting_mode`, which separates connections that may participate in automatic target selection from those that must remain explicit-override-only. The new precedence is now documented and enforced as: hard connection capability, base scheduler access mode, additive user grants, restrictive role/item-type/wedding filters, targeting mode, then sync-policy target selection. Regression coverage now proves `manual_only` connections are excluded from automatic default resolution but still honored for valid explicit overrides.
- **Shared calendar contract cleanup and explicit connection access precedence** (`/app/api/planner_calendar.py`, `/app/models/calendar.py`, `/app/models/calendar_connection.py`, `/app/services/google_calendar_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/calendarApi.ts`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/tests/backend/test_shared_calendar_v1_contract.py`) — Removed the remaining legacy Google projection fields from the planner task response contract (`google_event_id`, `synced_to_google`) so external sync state now comes only from the canonical sync-summary projection, deleted the dead legacy calendar-token model, and stopped the planner task modal from reading the removed fields. Added an explicit connection-level `scheduler_access_mode` with a fixed precedence model: base connection access mode first, then additive user grants, then restrictive role/item-type/wedding filters, and only then sync-policy target selection. The planner connection UI now exposes that base access mode directly, while connection serialization hides redundant old self-grants left over from the earlier implicit model so the screen reflects operator intent instead of storage artifacts.
- **Shared calendar legacy-write cleanup and richer connection policy controls** (`/app/api/planner_calendar.py`, `/app/api/couple_portal.py`, `/app/core/database.py`, `/app/models/calendar_connection.py`, `/app/services/calendarApi.ts`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/app/admin/planner/calendar/page.tsx`, `/tests/backend/test_shared_calendar_v1_contract.py`) — Removed the remaining planner-calendar writes to legacy meeting/task sync fields during canonical meeting flows, switched generic task create/edit to use the canonical `external_sync_requested` flag instead of relying on `synced_to_google`, removed the dead `calendar_tokens` collection accessor after confirming there were no remaining runtime call sites, and dropped the last couple-portal planner-field read that still exposed `synced_to_google`. The planner connection panel now exposes connection-level scheduler roles, schedule-item-type restrictions, and wedding-scoped write policies on top of the existing user allowlist, with backend regression coverage proving those policies fail closed in sync-target resolution. Later unreleased follow-up work removed the remaining legacy response fields and added an explicit base access mode for connection-level scheduling policy.
- **Coolify deploy state now fails closed on image-tag drift and reports API errors directly** (`/scripts/deploy/coolify_api.py`, `/.github/workflows/coolify-deploy-shared.yml`, `/.github/workflows/deploy-coolify.yml`, `/.github/workflows/promote-coolify-production.yml`, `/.github/workflows/deploy-workers.yml`, `/cloudflare-workers/autopilot.wrangler.toml`, `/cloudflare-workers/backup.wrangler.toml`, `/cloudflare-workers/metrics-snapshot.wrangler.toml`, `/cloudflare-workers/trial.wrangler.toml`, `/cloudflare-workers/uptime.wrangler.toml`) — Replaced the shared Coolify deploy `curl -sf` calls with a checked Python helper that reads the current image reference, retries application updates with a merged writable payload when Coolify rejects a minimal image-only PATCH, verifies that the stored GHCR SHA actually changed before restart, and reuses the same contract for rollback so stale tags such as `c08446` cannot be silently restored. The GHCR target-tag preflight now lives in the reusable Coolify workflow for both staging and production, while the Cloudflare Workers workflow moved off the floating global Wrangler install onto a pinned CLI path, stopped mutating tracked Wrangler config in CI to discover KV IDs, and now expects a deterministic `CLOUDFLARE_UPTIME_KV_NAMESPACE_ID` variable instead of creating bindings on the fly.
- **Calendar scheduler workflow now drives production invite and maintenance endpoints** (`/.github/workflows/calendar-scheduler.yml`, `/scripts/deploy/trigger_scheduler.py`, `/scripts/deploy/github-secrets.example.env`, `/scripts/deploy/sync_github_secrets.sh`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`) — Added a repo-backed scheduled workflow that calls `/scheduler/calendar-invite-jobs` every 5 minutes and `/scheduler/calendar-maintenance` every 15 minutes for production using the existing HMAC scheduler contract, with manual staging support for validation. The new signer script keeps the auth logic consistent with the backend path contract, and the Coolify/GitHub secret docs now explicitly require matching per-environment scheduler HMAC secrets instead of leaving the new calendar queue/retry system dependent on manual scheduler setup.
- **PR 8 vendor contract regression lock-in and cleanup** (`/tests/backend/test_vendor_contract_admin_api.py`, `/tests/backend/test_vendor_contract_revisions.py`, `/tests/backend/test_vendor_contract_activity.py`, `/tests/backend/test_vendor_contract_security.py`, `/tests/unit/vendorContractsApi.test.ts`, `/tests/unit/vendorContractPreview.test.tsx`, `/tests/unit/vendorContractDetailPage.test.tsx`, `/tests/unit/paymentMilestones.test.tsx`, `/tests/unit/publicContractPage.test.tsx`, `/tests/unit/testDom.ts`, `/app/admin/vendors/contracts/[id]/ContractDetailPageClient.tsx`, `/app/admin/vendors/components/PaymentMilestones.tsx`, `/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/scripts/backfill_vendor_contract_security_fields.py`, `/app/core/database_indexes.py`) — Locked the vendor-contract module down with broader backend regression coverage for admin routes, lineage rules, activity synthesis, secure public access, and historical-version mutation guards; expanded frontend helper tests for the normalized contract API and canonical public path-token routes; and added dedicated runtime UI coverage for the planner detail page, contract-scoped payments surface, shared contract preview, and public vendor contract page using a small jsdom-based test harness plus injectable runtime seams. The App Router detail page now delegates to a dedicated client component so those runtime tests can exercise the real UI behavior without weakening route typing, and the backfill rollout plus vendor-contract index invariants are now documented as part of the stabilization pass.
- **Python 3.11 app boot compatibility now guards backend startup in CI** (`/app/api/forms.py`, `/app/dependencies/auth_extended.py`, `/docker-compose.test.yml`, `/tests/backend/conftest.py`, `/tests/backend/test_app_boot_smoke.py`, `/tests/backend/test_forms_api.py`, `/.github/workflows/ci.yml`) — Swapped backend `TypedDict` imports to `typing_extensions.TypedDict` so FastAPI/Pydantic can build response schemas under Python 3.11, expanded the backend smoke test to import the full app module, repaired stale forms API test doubles to match the current auth and async collection shape, filled in the backend test env defaults required for `Settings()` validation, and added the test-stack S3 bucket env vars required by vendor service startup. CI now runs that boot smoke test as a strict step before the legacy backend unit-test batch, which keeps this startup regression from hiding behind the broader deferred unit-test debt.
- **Built-image smoke test now matches backend startup env parity** (`/.github/workflows/ci.yml`) — The GHCR image smoke job now passes the same minimal host/URL/storage env expected by app import, including `ALLOWED_HOSTS`, `S3_REGION=auto`, and repo-level GitHub Actions vars for `S3_BUCKET_NAME` and `S3_AD_BUCKET_NAME`. Without that parity, the smoke backend died before liveness checks because `VendorService` hard-fails on a missing storage bucket env even though the earlier integration-compose stack was already healthy.
- **Staging deploy verification now supports insecure TLS explicitly** (`/.github/workflows/coolify-deploy-shared.yml`, `/.github/workflows/deploy-coolify.yml`, `/scripts/deploy/verify_environment.py`) — Added an opt-in `allow_insecure_tls` path for post-deploy verification so staging can continue running smoke checks against its current self-signed or incomplete certificate chain without disabling TLS verification globally. The verifier now routes all HTTP calls through a shared session, can suppress certificate validation only when requested, and logs backend/frontend retry failures with the returned HTTP body so future staging failures show the real upstream status instead of stopping at an SSL exception.
- **Coolify rollback now validates stored image tags before restoring them** (`/.github/workflows/coolify-deploy-shared.yml`) — The shared deploy workflow now logs into GHCR with package-read permissions and verifies that Coolify’s currently configured backend/frontend image tags still exist before treating them as rollback targets. If Coolify is carrying a stale or manually-entered tag that no longer exists in GHCR, the workflow now warns and skips the rollback for that service instead of patching staging back to a broken image reference such as `c08446`.
- **PR 7 follow-up tightened vendor contract backfill and public-read semantics** (`/scripts/backfill_vendor_contract_security_fields.py`, `/app/services/vendor_service.py`, `/tests/backend/test_vendor_contract_security.py`) — Normalized legacy-missing lineage fields in-memory before the vendor-contract security backfill detects conflicts, so old contracts with absent `root_contract_id`/`version_number` no longer false-positive as duplicate version groups during `--apply`. Public vendor contract reads also stop bumping `updated_at` on routine access and now reserve that field for actual lifecycle transitions such as the first `sent -> viewed` change.
- **Pending-setup couple copy-link now honors invite expiry** (`/app/api/couple_invite.py`, `/app/admin/weddings/[id]/page.tsx`, `/tests/backend/test_couple_permission_contract.py`) — Planner-side couple listing now only returns a copyable setup link when the stored invite token is still active, and the wedding admin couple tab no longer offers `Copy Link` for expired pending invites. Expired pending setups now clearly fall back to `Resend`, which prevents planners from copying dead invitation URLs.
- **Generic calendar-task permissions now own the legacy task path** (`/app/api/planner_calendar.py`, `/app/models/team_member.py`, `/app/admin/planner/calendar/page.tsx`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/admin/planner/team/teamConstants.ts`) — Moved the older task CRUD/list/month/upcoming/bulk/sync routes off the `require_wedding_planner` plus `manage_wedding_settings` gate and onto the calendar permission family instead: task reads now flow through shared-calendar access, task mutations require `manage_calendar_tasks`, and manual task sync requires `sync_calendar_tasks`. The planner calendar UI and team-permission surfaces were updated in parallel so general tasks no longer piggyback on wedding-settings access while the released meeting path stays unchanged.
- **Root agent delivery guardrails added** (`/AGENTS.md`) — Added a repo-level agent instruction file that makes the shared planner calendar roadmap and E2E runbook binding inputs for related work, and codifies the implementation gates that were missing during the shared calendar rollout: acceptance-matrix planning, route-and-flow parity checks across old and new entry points, owner-scope authorization verification, explicit-intent preservation, edit-flow round-trip requirements, lifecycle cleanup rules for connect/reconnect/disconnect/delete flows, timezone correctness requirements, adversarial pre-close review, and a stricter completion standard that does not treat passing static checks or happy-path tests as sufficient proof.
- **Sprint 5 QA review doc aligned to canonical meeting routes** (`/docs/qa/SPRINT5_CODE_REVIEW.md`) — Updated the historical Sprint 5 code review notes so they no longer present the retired planner-side `/admin/couple-portal/meetings` alias as the active meeting surface. The doc now points future readers at the canonical planner calendar meeting flow, keeps the couple-facing `/couple/portal/meetings` read path distinct, and reframes the old findings as historical alias issues versus current canonical responsibilities.
- **PR 1 couple-contract route ownership split** (`/app/api/contracts.py`, `/app/main.py`, `/app/api/vendor_management.py`, `/app/admin/money/page.tsx`, `/tests/integration/test_12_contracts_packages.py`) — Split the mixed couple-contract router into explicit admin, public, and cron routers so planner/couple admin endpoints now live canonically under `/admin/client-contracts/*`, public couple and portal routes stay at `/public/contracts/*` and `/public/portal/*`, vendor admin contracts remain owned by `/admin/contracts/*`, and the last in-repo root `/contracts/*` callers were migrated to the canonical admin namespace instead of being left behind on hidden aliases.
- **PR 2 vendor frontend contract-domain split** (`/app/services/vendorContractsApi.ts`, `/app/services/vendorManagementApi.ts`, `/app/admin/vendors/page.tsx`, `/app/admin/vendors/contracts/new/page.tsx`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/app/admin/vendors/components/PaymentMilestones.tsx`) — Split vendor frontend contract logic out of the mixed vendor management service into a dedicated `vendorContractsApi.ts` boundary, moved the current vendor contract screens/components onto that boundary, removed the duplicate contract form-data helper shape, and reduced `vendorManagementApi.ts` to non-contract vendor ownership only: directory, assignments, vendor dashboard, payment links, import helpers, and shared vendor category utilities.
- **PR 3 vendor contract DTO and transport normalization** (`/app/models/vendor_contracts.py`, `/app/models/vendor.py`, `/app/api/vendor_management.py`, `/app/services/vendor_service.py`, `/app/services/vendorContractsApi.ts`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/tests/backend/test_vendor_contract_admin_api.py`, `/tests/unit/vendorContractsApi.test.ts`) — Moved planner-to-vendor contract admin DTO ownership into a dedicated model module, removed the overlapping request-model split from `vendor.py`, converted vendor contract create/send/pay/apply flows from query-param and loose-dict transport to typed JSON bodies, normalized vendor form-data response keys, made apply-form-data return the updated contract object, and added targeted backend/frontend contract tests for the normalized request and response shapes.
- **PR 4 shared vendor contract document rendering** (`/app/components/contracts/ContractMarkdownRenderer.tsx`, `/app/components/contracts/VendorContractPreview.tsx`, `/app/admin/vendors/contracts/new/page.tsx`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/tests/unit/vendorContractPreview.test.tsx`) — Rebuilt vendor contract rendering around a shared sanitized markdown renderer plus a shared document preview/composition component, moved the planner canvas preview, planner detail view, and public vendor contract page onto that single rendering path, promoted `custom_clauses` into the shared document model, removed the remaining raw `whitespace-pre-wrap` contract-body rendering on those surfaces, and tightened the create flow so the saved contract document matches the planner preview instead of drifting across template and custom-edit paths.
- **PR 5 vendor contract revision and amendment lifecycle** (`/app/models/vendor.py`, `/app/models/vendor_contracts.py`, `/app/services/vendor_service.py`, `/app/api/vendor_management.py`, `/app/services/vendorContractsApi.ts`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/tests/backend/test_vendor_contract_revisions.py`, `/tests/backend/test_vendor_contract_admin_api.py`, `/tests/unit/vendorContractsApi.test.ts`) — Added explicit contract lineage metadata for planner-to-vendor contracts, introduced typed revision/amendment DTOs plus admin revision endpoints, enforced service-layer guards so non-current contracts cannot fork lineage and stale sibling drafts cannot supersede the live version, made original contract creation initialize root version metadata atomically with a pre-generated `_id`, surfaced revision history and draft creation controls in the planner detail page, and taught the public vendor contract flow to reject superseded links with a clear replaced-version experience instead of treating them as generic failures.
- **PR 6 vendor contract payments tab and activity timeline** (`/app/models/vendor_contracts.py`, `/app/services/vendor_service.py`, `/app/api/vendor_management.py`, `/app/services/vendorContractsApi.ts`, `/app/core/database_indexes.py`, `/app/admin/vendors/components/PaymentMilestones.tsx`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/tests/backend/test_vendor_contract_activity.py`, `/tests/backend/test_vendor_contract_admin_api.py`, `/tests/unit/vendorContractsApi.test.ts`) — Added a contract-scoped activity model and endpoint, logged major vendor contract lifecycle and payment events at the service layer, tightened milestone list/payment flows so the detail page no longer relies on an unscoped milestone boundary, replaced the contract detail page’s placeholder payments tab with the shared `PaymentMilestones` component in contract mode, replaced the fake activity tab with a real fetched timeline, and demoted the duplicate sidebar timeline into a compact key-dates summary so the page has one operational payments surface and one real chronological activity surface.
- **PR 6 follow-up historical-version payment guardrail** (`/app/services/vendor_service.py`, `/tests/backend/test_vendor_contract_activity.py`) — Closed the remaining backend parity gap after the PR 6 UI read-only split by rejecting milestone creation and payment recording against non-current vendor contract versions in the service layer, so historical revisions remain inspectable but cannot be mutated through direct API calls or stale clients. Added regression coverage to prove money mutations fail closed on superseded contract versions instead of silently updating the wrong lineage node.
- **PR 7 vendor contract token security and mutation integrity hardening** (`/app/models/vendor.py`, `/app/services/vendor_service.py`, `/app/api/vendor_contract_public.py`, `/app/core/database_indexes.py`, `/scripts/backfill_vendor_contract_security_fields.py`, `/tests/backend/test_vendor_contract_revisions.py`, `/tests/backend/test_vendor_contract_activity.py`, `/tests/backend/test_vendor_contract_security.py`) — Replaced live plaintext vendor contract access tokens with hash-based validation metadata, removed the hidden query-token public compatibility routes, centralized public token validation for current/revoked/expired contract checks, made contract signing and milestone payment recording require Mongo transaction support instead of silently falling back to partial writes, added security indexes for contract lineage and token uniqueness, introduced a dry-run/apply backfill script for legacy contract security fields, and hardened the public/payments boundary so stale historical contracts cannot be viewed, signed, or mutated through direct API calls outside the planner UI.
- **Support inbox unification for guest SMS and planner support threads** (`/app/admin/communications/components/CommunicationsInboxView.tsx`, `/app/admin/support/page.tsx`, `/app/admin/notifications/page.tsx`, `/app/admin/utils/teamAccess.ts`, `/app/api/support_management.py`, `/app/api/twilio_webhooks.py`, `/app/api/reminder.py`, `/app/services/support_service.py`, `/app/services/planner_notification_service.py`, `/app/utils/support_inbox_links.py`) — Extended the existing communications inbox merge pattern to include guest SMS support and planner/root-admin support tickets without changing the `support_tickets` storage model, moved public replies for support conversations into the inbox while keeping `/admin/support` as the operational dashboard, excluded SMS-origin tickets from the general support-ticket endpoints by default, deep-linked support notifications and emails into exact inbox threads, and hardened the support-thread flow so invalid deep links fail closed, SMS reads do not fake new activity, and non-resolving SMS replies advance `new` tickets to `in_progress`.

### Fixed

- **Couple archived-read parity, section auth-failure handling, and portable lifecycle browser regression** (`/app/api/couple_portal.py`, `/app/api/behavioral_analytics.py`, `/app/utils/couple_archived_read_model.py`, `/app/couple/lib/auth.ts`, `/app/couple/dashboard/page.tsx`, `/playwright.config.ts`, `/scripts/testing/couple_portal_lifecycle_fixture.py`, `/tests/backend/test_couple_archived_dashboard_contract.py`, `/tests/couple-portal-lifecycle.spec.ts`) — Archived couple analytics, registries, and FAQs now read from the archived snapshot instead of mixing empty payloads and live-data queries, and archived dashboard guest stats are derived from the archived guest/RSVP snapshot so the dashboard and direct reads share one contract. Couple dashboard subpanel fetches now collapse 401/403 responses through the same session-expired or blocked flow instead of degrading into partial toasts across meetings, inbox, payments, and analytics cards. The PR2 lifecycle Playwright regression no longer depends on one machine path or one inlined Python blob: the fixture seeding moved into a reusable repo script, the test harness now resolves the repo root and Python interpreter dynamically, and Playwright server startup is parameterized around env-configurable ports and backend interpreter selection.
- **Meeting invite uniqueness now enforced at the DB layer** (`/app/core/database_indexes.py`, `/tests/backend/test_shared_calendar_v1_contract.py`) — `meeting_invites(task_id, recipient_email)` is now enforced with a unique index instead of a non-unique helper index, and the shared calendar index bootstrap now removes legacy duplicate invite rows before creating that constraint so the uniqueness guarantee can actually be applied on existing data. Added regression coverage to lock both the dedupe pass and the unique index declaration into the shared-calendar contract suite.
- **Shared calendar invite lifecycle and scheduler-control follow-up** (`/app/services/meeting_invite_service.py`, `/app/api/planner_calendar.py`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/app/admin/planner/calendar/page.tsx`, `/app/services/calendarApi.ts`, `/tests/backend/test_shared_calendar_v1_contract.py`) — Closed the remaining outward-notification gap in the shared planner calendar flow by making material meeting edits send updated ICS requests to current couple recipients, making meeting deletion send ICS cancellations with the same stable UID before the canonical meeting is removed, and preserving invite audit rows with cancellation status instead of silently dropping local invite state. The planner calendar connection panel now also exposes a real owner-facing scheduler-access control for writable staff calendars using the existing team-member roster, so the new `allowed_scheduler_user_ids` authorization primitive is no longer backend-only. Regression coverage now protects both update/delete invite propagation and the new invite-state transitions.
- **Shared calendar guardrail follow-up for scope, sync targeting, and invite lifecycle** (`/app/services/calendar_aggregation_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/google_calendar_service.py`, `/app/services/meeting_invite_service.py`, `/app/api/planner_calendar.py`, `/app/models/calendar.py`, `/app/models/calendar_connection.py`, `/app/core/config.py`, `/app/services/calendarApi.ts`, `/tests/backend/test_shared_calendar_v1_contract.py`) — Closed the next review wave on the shared planner calendar v1 foundation by intersecting requested wedding filters with accessible wedding scope in the shared-calendar query path, parallelizing per-connection Google fetches for the shared view, adding per-calendar scheduler allowlists so team members cannot steer meetings onto other staff calendars without explicit permission, rejecting non-writable or sync-disabled default write targets, preventing deselected target cleanup from orphaning live provider events when delete fails, stabilizing ICS UIDs so meeting resend/reschedule flows update the same calendar item, rejecting unsupported `google_attendee` invite delivery in v1 instead of silently under-implementing it, and requiring explicit Google OAuth/token security keys in production instead of falling back to development-style defaults. Regression coverage now locks those invariants into the shared-calendar contract suite.
- **Couple form access parity and malformed-id hardening** (`/app/api/couple_portal.py`, `/tests/backend/test_couple_form_access_contract.py`) — Unified the couple-facing form visibility rule so both `GET /couple/portal/forms/{form_id}` and `POST /couple/portal/forms/submit` now enforce the same share predicates (`shared_with_couple`, `target_audience == "couple"`, or matching `couple_email`) instead of letting the read route bypass the submit route’s sharing checks. The couple form endpoints now also fail invalid `form_id` values closed with a stable `400 Invalid form ID format` response instead of relying on raw `ObjectId(...)` parsing behavior.
- **Shared calendar owner-scope and lifecycle hardening** (`/app/api/planner_calendar.py`, `/app/api/couple_portal.py`, `/app/dependencies/auth_extended.py`, `/app/services/calendar_sync_service.py`, `/app/services/google_calendar_service.py`, `/app/models/calendar.py`, `/tests/backend/test_shared_calendar_v1_contract.py`, `/tests/backend/test_couple_permission_contract.py`) — Closed the follow-up correctness gaps from the shared planner calendar rollout by enforcing owner-scoped meeting lookups on planner calendar meeting endpoints, validating target-wedding changes during meeting edits, rejecting assignee ids outside the planner business scope, making `custom` sync policy fail closed unless explicit allowed targets are selected, and preserving the canonical schedule item when provider deletion fails instead of deleting local sync mappings first. Backend coverage now also exercises custom-policy internal-only behavior, owner-scoped assignee validation, scoped meeting lookups, provider-delete failure handling, and the couple-portal meeting scheduling permission gate.
- **Retired duplicate planner-side couple meeting routes** (`/app/api/couple_portal.py`, `/tests/backend/test_couple_permission_contract.py`, `/tests/backend/test_shared_calendar_v1_contract.py`, `/docs/testing/couple-team-access-e2e-runbook.md`) — Removed the unused `/admin/couple-portal/meetings` planner alias routes after confirming the app code only calls the canonical `/admin/planner/calendar/meetings` surface and the roadmap/runbook treat that planner calendar API as the v1 source of truth. The remaining contract coverage now targets the canonical planner calendar meeting creation path plus the couple-side `/couple/portal/meetings` read path, and the active E2E runbook now watches the canonical planner calendar endpoints instead of the retired aliases.

## [2.28.7] - 2026-04-07

### Changed

- **Deployment workflow hardening** (`/.github/workflows/ci.yml`, `/.github/workflows/deploy-coolify.yml`, `/.github/workflows-disabled/deploy-kubernetes.yml.disabled`) — Disabled the legacy DOKS deploy workflow so `main` no longer fans out into an unintended Kubernetes production deploy, made manual staging deploys require an explicit existing GHCR image tag, validated that tag before handing it to Coolify, and switched the shared frontend image build to a neutral placeholder `FRONTEND_URL` so staging no longer bakes the production domain into the image.
- **CI bootstrap and workflow pruning for the Coolify path** (`/.github/workflows/ci.yml`, `/.github/workflows/deploy-coolify.yml`, `/.github/workflows/coolify-deploy-shared.yml`, `/.github/workflows-disabled/claude-code-review.yml.disabled`, `/.github/workflows-disabled/claude.yml.disabled`, `/.github/workflows-disabled/k8s-bootstrap.yml.disabled`, `/.github/workflows-disabled/pr-check.yml.disabled`, `/.github/workflows-disabled/release.yml.disabled`, `/.github/workflows-disabled/update-changelog.yml.disabled`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`) — Re-enabled the manually disabled `CI` workflow in GitHub, added manual `workflow_dispatch` bootstrapping for image builds on `main`, normalized GHCR image references to the lowercase `lopewale/*` namespace required by Docker/OCI, taught the shared Coolify deploy workflow to pin both image name and tag so digest-pinned app configs do not break promotions, and reduced the repo-controlled Actions set to the Coolify deploy path, dependency review, and Cloudflare worker deploys. GitHub-managed Copilot workflows still remain active outside the repo workflow files and must be disabled in repository settings if you want them gone too.

### Fixed

- **Twilio webhook form parsing typing cleanup** (`/app/api/twilio_webhooks.py`, `/tests/backend/test_twilio_webhooks_contract.py`) — Normalized Twilio’s form-encoded webhook payloads into a string-only map at the request boundary, added tolerant optional-integer parsing for `ErrorCode`, removed repeated `int(...)` calls from the status callback, preserved incoming-message handling on normalized string values only, and added focused backend coverage for valid, missing, malformed, and unexpected uploaded-form-value webhook payloads so the file now passes local `pyright` and targeted pytest verification without changing Twilio webhook behavior.
- **Tracked integration suite restored for CI** (`/.gitignore`, `/.github/workflows/ci.yml`, `/tests/integration/`) — Fixed the actual `Integration Tests (Full Stack)` failure mode: the workflow was executing `pytest tests/integration/` even though `.gitignore` was still excluding that suite from Git, so GitHub runners could never see the directory and failed before running a single test. The integration suite is now unignored so it can be committed as a first-class repo asset, the workflow creates `test-results/` before teeing logs, installs the plugin set from `requirements-test.txt` plus JWT support so `pytest.ini` stays valid on runners, and fails early with a clear error if `tests/integration/` ever disappears from a checked-out commit again.
- **CI and staging-gate recovery for the split Coolify pipeline** (`/app/core/settings.py`, `/app/api/autopilot.py`, `/app/services/wedding_service.py`, `/tests/integration/test_10_platform_operations.py`, `/tests/integration/test_11_security.py`, `/tests/integration/test_12_contracts_packages.py`, `/tests/integration/test_14_team_management.py`) — Closed the remaining blockers that were keeping `CI` from producing deployable artifacts for staging: local/test CORS parsing now expands loopback aliases consistently, authenticated planner/root-admin autopilot status and payment-monitoring routes no longer trip the cron-secret guard, the planner-ownership wedding listing path once again imports the shared `normalize_query_id` helper so Ruff stops failing on an undefined symbol, and the final web-push integration test now matches the real API contract by treating missing VAPID configuration as an intentional `503` unavailable state rather than a `500` server crash. With those fixes in place, the full integration suite now runs clean locally (`122 passed`), which restores the expected `CI -> build images -> deploy staging` path instead of dying before image publication.
- **PR 4 couple blocked-state UX and canonical owner cleanup** (`/app/api/couple_auth.py`, `/app/api/couple_portal.py`, `/app/services/couple_lifecycle_service.py`, `/app/contexts/CoupleAuthContext.tsx`, `/app/components/CoupleRouteGuard.tsx`, `/app/contexts/CoupleSSEContext.tsx`, `/app/couple/login/page.tsx`, `/app/couple/dashboard/page.tsx`, `/app/couple/lib/auth.ts`, `/app/couple/setup/CoupleSetupPageClient.tsx`, `/app/couple/reset-password/CoupleResetPasswordPageClient.tsx`, `/app/couple/forms/[formId]/page.tsx`, `/tests/backend/test_couple_owner_identity_cleanup.py`) — Hardened the couple auth surface so blocked couples no longer get flattened into a generic “invalid link” or silent login bounce. Couple auth now preserves backend 403 detail through the route guard, session revalidation, and login redirect; `/couple/login` shows the blocked-state reason as a persistent banner instead of only a toast; setup/reset verification screens surface the real planner-inactive or portal-unavailable reason instead of only saying the link expired; protected standalone form pages now treat 401/403 states the same way as the main dashboard; and the couple portal no longer falls back to `couple_users.planner_id` or `planner_email` as authoritative owner reads when resolving lifecycle state or planner notification targets.
- **PR 4 meeting visibility and couple-session cleanup follow-up** (`/app/api/couple_portal.py`, `/app/services/couple_lifecycle_service.py`, `/app/contexts/CoupleAuthContext.tsx`, `/app/components/CoupleRouteGuard.tsx`, `/app/contexts/CoupleSSEContext.tsx`, `/app/couple/login/page.tsx`, `/app/couple/dashboard/page.tsx`, `/app/couple/lib/auth.ts`, `/tests/backend/test_couple_lifecycle_service.py`, `/tests/backend/test_couple_permission_contract.py`) — Removed the last couple-owner fallback reads that could still treat `couple_users.planner_id` or `planner_email` as authoritative during portal lifecycle checks and planner notifications, carried blocked-session detail through the couple auth provider and route guard so `/couple/login` can show a persistent “portal access paused” message, and fixed the couple meeting flow to be wedding-scoped instead of actor-email-scoped so meetings created by team members still appear to the couple and to other authorized planner users.
- **PR 3 couple permission normalization across planner UI and backend enforcement** (`/app/models/team_member.py`, `/app/api/team_management.py`, `/app/api/couple_invite.py`, `/app/api/couple_portal.py`, `/app/admin/planner/team/teamConstants.ts`, `/app/admin/team/accept/AcceptInvitePageClient.tsx`, `/app/admin/utils/teamAccess.ts`, `/app/admin/components/Sidebar.tsx`, `/app/admin/components/AdminHeader.tsx`, `/app/admin/communications/components/CommunicationsInboxView.tsx`, `/app/admin/weddings/[id]/page.tsx`, `/tests/backend/test_couple_permission_contract.py`) — Split the old `manage_contracts` catch-all couple behavior into explicit `manage_couple_portal` and `message_couples` permissions, updated team presets and effective-permission payloads to expose the new keys, and moved planner-side couple invite, revoke/restore, archival, form-template, meeting, and messaging endpoints onto the correct permission boundary. The planner UI now uses the same distinction: team navigation only exposes `Communications` when a member can actually use communications, the couple tab in wedding details only appears for users who can manage the couple portal, and the unified inbox now gates guest email threads separately from couple conversations instead of leaking both through one `manage_contracts` check.
- **PR 2 couple/team lifecycle normalization for planner cancellation** (`/app/services/couple_lifecycle_service.py`, `/app/dependencies/couple_auth.py`, `/app/api/couple_auth.py`, `/app/api/couple_invite.py`, `/app/api/couple_portal.py`, `/app/services/subscription_service.py`, `/app/services/stripe_service.py`, `/app/services/email_service_resend.py`, `/app/services/team_management_service.py`, `/app/models/team_member.py`, `/app/services/cascade_delete_service.py`, `/tests/backend/test_couple_auth_lifecycle.py`, `/tests/backend/test_couple_lifecycle_service.py`) — Added an explicit couple portal lifecycle model (`pending_setup`, `active`, `revoked_by_planner`, `owner_cancelled`) with a shared resolver used by couple auth, invite/setup, and password-reset flows; planner cancellation and Stripe cancellation webhooks now bulk-mark owned couples as `owner_cancelled`, while reactivation explicitly restores only owner-cancelled couples. Archived weddings remain a separate read-only state, team lifecycle now formally declares `suspended_owner_cancelled`, planner data suspension follows canonical wedding ownership from PR 1, and the couple cancellation email now correctly says portal access is paused instead of promising free ongoing access.
- **Frontend typecheck and lint cleanup for duplicate/generated files** (`/app/admin/saas/page 2.tsx`, `/CHANGELOG 2.md`, `/tests/unit/budgetApi.test.ts`, `/tests/unit/formsApi.test.ts`, `/tests/unit/envRuntimeConfig.test.ts`, `/tests/unit/weddingPrivacyInfo.test.ts`, `/eslint.config.mjs`) — Removed two accidental tracked duplicates that were being swept into CI and breaking Next.js/TypeScript despite not being part of the real app surface, replaced the test-only `delete global.fetch` pattern with `Reflect.deleteProperty(...)`, updated env-runtime tests to mutate `NODE_ENV` through a mutable test-only view of `process.env`, and taught ESLint to ignore generated `.next` artifacts plus the repo-local `.venv` so local lint runs stop crawling vendored third-party code.
- **Backend Ruff gate cleanup and test harness hardening** (`/app/**`, `/tests/backend/test_platform_metrics.py`, `/tests/backend/test_settings.py`, `/app/services/web_push_service.py`, `/app/services/platform_metrics_service.py`) — Applied the repo’s pending Ruff auto-fixes across `app/`, cleaned up the remaining manual lint blockers without changing runtime intent, normalized the backend app surface with `ruff format` so the CI `ruff format --check app/` step stops failing, updated stale backend tests to the current auth/settings contract, made web-push dependencies load lazily so test stubs cannot poison module import during collection, and normalized the platform-metrics mongomock fallback to compare timestamps safely when naive test fixtures hit the fallback path.
- **Couple login/setup/reset now hard-navigate after auth is established** (`/app/couple/login/page.tsx`, `/app/couple/setup/CoupleSetupPageClient.tsx`, `/app/couple/reset-password/CoupleResetPasswordPageClient.tsx`) — Replaced the client-side `router.push('/couple/dashboard')` transitions used immediately after couple login, invite-based setup, and password reset with a full browser navigation. This avoids the public→protected auth bootstrap race where the route guard could see the stale public-page `unauthenticated` state for one render and bounce couples back to `/couple/login` even though the backend had already issued a valid `couple_token` cookie.
- **Planner↔couple messaging now uses explicit read acknowledgements plus live SSE updates** (`/app/api/couple_portal.py`, `/app/api/couple_notification_stream.py`, `/app/main.py`, `/app/hooks/useSSE.ts`, `/app/admin/communications/components/CommunicationsInboxView.tsx`, `/app/contexts/CoupleSSEContext.tsx`, `/app/couple/hooks/useCoupleSSE.ts`, `/app/couple/components/CoupleLayoutClient.tsx`, `/app/couple/dashboard/page.tsx`) — Removed the old read-on-GET side effects from both couple and planner message-history endpoints, added explicit planner/couple `POST .../messages/read` acknowledgements, added a conversation-summary endpoint for the planner inbox so it no longer builds couple threads from account metadata plus N+1 unread fetches, fixed stale couple-message notification deep links to open the communications inbox directly, and wired the existing admin SSE plus a new couple SSE stream so open planner/couple threads update live without reloads. The couple dashboard unread badge now refreshes from the SSE signal instead of waiting for a hard reload, while planner refresh now also refetches the selected couple thread instead of only the list pane.
- **Communications inbox wedding-context handoff** (`/app/admin/communications/components/CommunicationsInboxView.tsx`, `/app/admin/communications/components/CommunicationsRemindersView.tsx`) — Fixed the new communications workspace dropping planners back to `All Weddings` when they moved from a wedding-scoped communications tab into `Inbox`. Reminders now persist the selected wedding into the URL as `?wedding_id=...`, and the inbox view now hydrates and preserves that query param instead of stripping it during its initial render/validation cycle.
- **Living QA docs aligned to communications navigation** (`/docs/testing/deployment-browser-e2e-runbook.md`, `/docs/TESTING_CHECKLIST_v2.28.0.md`, `/docs/testing/comprehensive-inventory.md`) — Updated the operational runbook and testing references to use the canonical `/admin/communications/*` planner routes, documented that `/admin/inbox` and `/admin/reminders` are now legacy redirects, and annotated the historical interactive inventory so stale route ownership references do not mislead future QA or implementation work.
- **PR 1 ownership normalization for planner-owned weddings/couples/team access** (`/app/utils/planner_ownership.py`, `/app/services/wedding_service.py`, `/app/api/wedding.py`, `/app/api/couple_invite.py`, `/app/api/couple_portal.py`, `/app/services/couple_portal_service.py`, `/app/services/subscription_service.py`, `/app/services/stripe_service.py`, `/app/dependencies/auth_extended.py`, `/app/services/team_management_service.py`, `/app/scripts/report_planner_ownership_drift.py`, `/tests/backend/test_planner_ownership.py`) — Introduced a shared ownership helper so wedding-owner lookups now prefer `assigned_planner_id` with `assigned_planner_email` as legacy fallback, fixed team-member wedding listing and wedding access checks to use the planner owner instead of the acting team member email, corrected couple invites to mirror the wedding owner instead of the acting user, routed planner-cancellation couple notification targeting through weddings instead of stale `couple_users.planner_id` mirrors, synced couple owner mirrors whenever a wedding owner is updated, added a dry-run/apply ownership drift report for weddings/couples/team records, and added helper-unit coverage for the owner-query/match logic.

## [2.28.6] - 2026-04-07

### Added

- **Subscription cancellation cleanup orchestration** (`/app/services/subscription_service.py`, `/app/services/stripe_service.py`) — Both the admin cancellation path (`DELETE /users/{user_id}/subscription`) and the Stripe webhook path (`customer.subscription.deleted`) now execute a 5-phase cleanup: (1) team member bulk deactivation, (2) planner data suspension on weddings/packages/contracts, (3) payment link and scheduled payment pausing, (4) cancellation confirmation email to planner, (5) notification emails to affected couples. Optimistic locking via `version` field and a `cancellation_cleanup_completed` flag prevent double-execution when both paths fire for the same cancellation.
- **Cancellation email notifications** (`/app/services/email_service_resend.py`) — Added `send_subscription_cancelled_email()` confirming cancellation with 30-day data retention notice and resubscribe link, and `send_planner_cancelled_couple_notification()` informing couples their planner is inactive with payments paused.
- **Team member bulk deactivation/reactivation** (`/app/services/team_management_service.py`) — Added `bulk_deactivate_by_owner()` and `bulk_reactivate_by_owner()` methods that suspend or restore all team members and their user accounts when owner subscription status changes, including auth cache invalidation.
- **Planner data suspension/unsuspension** (`/app/services/cascade_delete_service.py`) — Added `suspend_planner_data()` and `unsuspend_planner_data()` methods that stamp/remove `data_access_suspended_at` and `data_access_suspended_reason` on weddings, packages, and contracts.
- **Subscription reactivation cleanup** (`/app/services/stripe_service.py`) — Added `_handle_reactivation_cleanup()` method that automatically reverses all cancellation suspension when a subscription transitions from cancelled/expired to active/trial. Wired into `_sync_subscription_state()` with previous-status detection so reactivation triggers on both new checkout and Stripe Customer Portal resubscription paths.

### Fixed

- **Couple notification lookup** (`/app/services/subscription_service.py`, `/app/services/stripe_service.py`) — Fixed couple notification to query the `couple_users` collection by `planner_id` instead of the non-existent `wedding.couple_id` field, which would have silently skipped all couple notifications.
- **Payment link pause/resume targeting both payment systems** (`/app/services/package_service.py`) — Rewrote `pause_planner_payment_links()` and `resume_planner_payment_links()` to correctly target both the `payment_links` collection (Stripe PaymentLinks deactivated via `stripe.PaymentLink.modify`) and the `scheduled_payments` collection (autopilot contract payments paused via status update), instead of only handling one collection with the wrong field name.
- **Stripe best practices: PaymentLink state verification before modify** (`/app/services/package_service.py`) — Added `stripe.PaymentLink.retrieve()` before `modify()` calls to skip already-inactive/already-active links, preventing Stripe API errors from duplicate webhook deliveries. Added granular `stripe.error.InvalidRequestError` vs `stripe.error.StripeError` exception handling per Stripe error-handling best practices.
- **Stripe best practices: atomic cancellation cleanup guard** (`/app/services/stripe_service.py`) — Replaced the non-atomic check-then-act cleanup guard with an atomic `find_one_and_update` that claims cleanup ownership in a single MongoDB operation, preventing race conditions when concurrent `customer.subscription.deleted` webhooks arrive for the same subscription.
- **Stripe best practices: reactivation idempotency guard** (`/app/services/stripe_service.py`) — Added atomic `find_one_and_update` guard to `_handle_reactivation_cleanup()` to prevent duplicate reactivation runs when both `customer.subscription.updated` and `checkout.session.completed` webhooks fire concurrently for the same resubscription.

## [2.28.5] - 2026-04-07

### Added

- **Hidden communications workspace route tree for planner messaging** (`/app/admin/communications/layout.tsx`, `/app/admin/communications/page.tsx`, `/app/admin/communications/inbox/page.tsx`, `/app/admin/communications/invites/page.tsx`, `/app/admin/communications/reminders/page.tsx`, `/app/admin/communications/individual/page.tsx`, `/app/admin/communications/history/page.tsx`, `/app/admin/communications/components/CommunicationsTabs.tsx`) — Added the new route-backed `/admin/communications/*` workspace behind the scenes without changing planner navigation yet. This introduces the final communications URL structure early so the next nav-cutover slice can switch destinations without re-implementing inbox or reminders behavior a second time.

### Changed

- **Inbox/reminders ownership extracted into shared communications views** (`/app/admin/communications/components/CommunicationsInboxView.tsx`, `/app/admin/communications/components/CommunicationsRemindersView.tsx`, `/app/admin/inbox/page.tsx`, `/app/admin/reminders/page.tsx`) — Moved the existing planner inbox and reminders page implementations into shared communications view components, then turned the legacy `/admin/inbox` and `/admin/reminders` pages into thin wrappers over those shared views. The legacy reminders route now also respects the existing `?tab=` deep-link shape instead of ignoring it, while the new communications child routes mount the same behavior with route-forced tabs instead of forking the page logic.
- **Planner navigation cut over to Communications** (`/app/admin/components/Sidebar.tsx`, `/app/admin/components/AdminHeader.tsx`, `/app/admin/planner/page.tsx`, `/app/admin/inbox/page.tsx`, `/app/admin/reminders/page.tsx`) — Replaced the standalone planner `Inbox` and `Reminders` destinations with a single `Communications` entry, pointed the planner dashboard quick action at the new `/admin/communications/reminders` route, and converted the legacy `/admin/inbox` and `/admin/reminders` pages into redirect shims so existing bookmarks and stale browser tabs still land on the canonical communications workspace.

### Fixed

- **Communication permission and wedding-access gaps on invite/reminder endpoints** (`/app/api/email_reminders.py`, `/app/api/reminder_utilities.py`, `/app/api/reminder_twilio.py`) — Added the missing `send_reminders` permission enforcement to individual email reminders, added `send_rsvp` permission enforcement plus wedding-access validation to personalized RSVP-link sending, and aligned the Twilio invite path with invite permissions instead of reminder permissions. This keeps the new communications workspace from inheriting the old silent permission drift between invite and reminder actions.
- **Planner notification deep links now resolve to communications history** (`/app/services/planner_notification_service.py`, `/app/api/reminder_twilio.py`, `/app/api/twilio_webhooks.py`) — Updated delivery-failure and bulk-send notification action URLs to the new `/admin/communications/history` route so the nav cutover does not leave platform-generated planner links pointing at retired standalone reminder pages.

## [2.28.4] - 2026-04-06

### Added

- **Dynamic OG image rendering for blog posts and vendor profiles** (`/app/api/og/route.tsx`, `/app/lib/og-utils.ts`) — Added an Edge `next/og` image route that renders source-aware cards for `/resources/blog/[slug]` and `/vendors/[id]`, using live article and vendor data with branded fallbacks when upstream records are unavailable.
- **Comparison content hub and competitor landing pages** (`/app/compare/layout.tsx`, `/app/compare/page.tsx`, `/app/compare/data.ts`, `/app/compare/[competitor]/page.tsx`) — Added a dedicated `/compare` hub plus source-qualified HoneyBook and Aisle Planner comparison pages with SEO metadata, structured data, and April 6, 2026 source-review framing.
- **Planner onboarding unsubscribe page** (`/app/unsubscribe/planner-onboarding/page.tsx`, `/app/unsubscribe/planner-onboarding/PlannerOnboardingUnsubscribeClient.tsx`) — Added a public frontend confirmation page for planner onboarding email opt-out so unsubscribe links resolve through the public web app instead of requiring a direct API-domain guess inside email templates.
- **Competitor verification research record** (`/docs/research/competitor-comparison-april-2026.md`) — Added a source-backed verification matrix covering the public features comparison rows and pricing references for HoneyBook, Aisle Planner, and Planning Pod.
- **Planner onboarding email sequence service** (`/app/services/planner_onboarding_email_service.py`) — Added a backend-managed planner onboarding sequence with day 0, 1, 3, 5, 8, and 12 emails, state tracking, skip/exit conditions, and claim-based duplicate-send protection.
- **Planner onboarding sequence tests** (`/tests/backend/test_planner_onboarding_email_service.py`) — Added targeted backend coverage for welcome send, day-1 send, day-1 skip, and Signature-plan exit behavior.

### Changed

- **Marketing copy and comparison framing** (`/app/page.tsx`, `/app/features/page.tsx`) — Reworked hero copy to lead with AI, the Couple Portal, and SMS reminders; standardized the public feature name to `Service Packages`; varied repeated CTA text; updated the public comparison table to use conservative source-backed pricing and an explicit April 2026 qualifier.
- **Comparison evidence traceability** (`/app/compare/[competitor]/page.tsx`, `/app/compare/evidence.ts`) — Inlined the public source ledger, row-level confidence labels, and official evidence URLs for the HoneyBook and Aisle Planner comparison pages so the publishable pages now expose the same traceability model as the research doc.
- **SEO metadata coverage for marketing, vendors, and blog content** (`/app/layout.tsx`, `/app/vendors/layout.tsx`, `/app/vendors/[id]/layout.tsx`, `/app/resources/blog/[slug]/page.tsx`, `/app/components/seo/BreadcrumbSchema.tsx`) — Added root-level Google/Bing verification hooks and Twitter `site` metadata, canonical URLs for `/vendors` and vendor profiles, breadcrumb JSON-LD for nested pages, and dynamic Twitter/Open Graph image references for blog articles and vendor profiles.
- **Planner email verification flow** (`/app/services/user_management_service.py`) — Replaced the one-off post-verification welcome email hook with sequence start logic for eligible wedding planners.

### Fixed

- **PWA manifest launch target** (`/public/manifest.json`) — Reset the manifest `start_url` from the couple dashboard path to `/` so install/open behavior no longer drops users into a planner-only route by default.
- **Scheduler coverage for onboarding emails** (`/app/api/scheduler_jobs.py`) — Added a scheduler endpoint for daily planner onboarding processing so the sequence runs through the existing authenticated cron pattern instead of relying on manual sends.
- **First-class planner onboarding unsubscribe behavior** (`/app/services/planner_onboarding_email_service.py`, `/app/api/user_management.py`, `/tests/backend/test_planner_onboarding_email_service.py`, `/.gitignore`) — Added sequence-scoped unsubscribe tokens, public status/confirm endpoints, explicit unsubscribe links in onboarding email footers, immediate sequence exit on opt-out, and versioned backend tests for the opt-out path.

## [2.28.3] - 2026-04-06

### Fixed

- **Root-admin notification inbox/read-state wiring** (`/app/admin/components/TopHeader.tsx`, `/app/admin/notifications/page.tsx`) — Fixed the root-admin bell taking users to the platform send/history screen instead of their own unread notification inbox. Root admins now land on a dedicated inbox tab backed by `/admin/user/notifications`, can mark alerts as read there, and keep the bell badge in sync with the actual unread state instead of being stranded with a badge that could not be cleared from the UI.
- **Planner reminders issue remediation flow** (`/app/admin/reminders/page.tsx`) — The reminders screen now correctly parses planner weddings, auto-selects the first available wedding, loads the matching guests with the current paginated guest API shape, and surfaces actionable issue drill-downs for unreachable guests, invalid/unreachable phone numbers, and SMS opt-outs. Each issue block now exposes the affected guests plus deep links into guest management so planners can fix the exact records instead of seeing only aggregate warning counts. Also corrected the admin plus-one fetch path from `/admin/plus-ones/...` to the mounted `/admin/plus-one/...` route to remove the silent 404 on the reminders screen.
- **Server-side guest filtering for planner guest management** (`/app/admin/guests/page.tsx`, `/app/api/guest.py`, `/app/services/guest_service.py`, `/app/core/database_indexes.py`, `/app/admin/utils/guestListResponse.ts`) — Replaced the page-local `All / RSVP'd / Awaiting RSVP` button filters with server-backed column filters and sorting for name, email, phone, group, RSVP state, plus-one state, phone-health, and SMS preference. The guest list now queries the full wedding dataset instead of filtering only the current page slice, returns consistent summary/filter metadata for the planner dashboard cards, and uses wedding-scoped Mongo indexes to keep the planner experience viable as guest counts grow.

## [2.28.2] - 2026-04-05

### Fixed

- **Stripe checkout gating, expiry recovery, and status normalization** (`/app/api/stripe_payment.py`, `/app/services/stripe_service.py`, `/app/models/subscription.py`, `/app/dependencies/auth_extended.py`, `/app/dependencies/feature_gates.py`, `/app/services/team_management_service.py`, `/app/services/platform_metrics_service.py`, `/app/scripts/sync_stripe_subscription.py`, `/scripts/resend_checkout_webhook.py`, `/app/utils/subscriptionStatus.ts`, `/app/components/AdminRouteGuard.tsx`, `/app/admin/components/TrialBanner.tsx`, `/app/admin/page.tsx`, `/app/admin/billing/page.tsx`, `/app/admin/planner/billing/page.tsx`, `/app/admin/saas/page.tsx`) — Locked the public checkout route down to true signup-retry states, blocked authenticated planners with active or delinquent subscriptions from spawning duplicate Checkout sessions, taught `checkout.session.expired` handling to roll `pending_checkout` records and users to `expired`, and normalized the internal status vocabulary so Stripe `trialing`, `incomplete`, `incomplete_expired`, and `unpaid` now resolve consistently across webhook sync, planner auth gating, feature entitlements, billing dashboards, and operational sync scripts. `past_due` is preserved as a first-class recoverable billing state instead of being silently collapsed into `suspended`.
- **Couple payment success and payment-method update completion** (`/app/pay/[id]/page.tsx`, `/app/pay/success/page.tsx`, `/app/portal/[token]/page.tsx`, `/app/components/contracts/StripePaymentCapture.tsx`, `/app/api/contracts.py`) — Finished the couple-facing Stripe flows by adding the missing `/pay/success` route, switching the public payment page to inline `confirmPayment(..., redirect: 'if_required')` handling for normal card payments, wiring the couple portal’s payment-method update button to the existing Stripe Elements capture component, and only showing the “saved” success state after the contract/default payment method update actually succeeds. The backend confirmation endpoint now validates the retrieved payment method, derives the card brand/last4 from Stripe, and stops redundantly re-attaching a method that the completed SetupIntent already attached.
- **Opaque public couple payment tokens** (`/app/api/stripe_payment.py`, `/app/components/payments/CollectPaymentModal.tsx`, `/app/core/database_indexes.py`, `/tests/backend/test_payment_intent_summary.py`) — Replaced the public `/pay/<payment_intent_id>` model with an app-owned opaque `public_token` stored on `payment_requests`, updated newly created planner payment links to use the opaque token instead of the raw Stripe object id, removed persisted `client_secret` copies from payment-request records, and tightened the public payment lookup endpoints so only the opaque token resolves the live Stripe PaymentIntent and its client secret.

## [2.28.1] - 2026-04-03

### Changed

- **Two-server Coolify staging-first rollout wiring** (`/.github/workflows/coolify-deploy-shared.yml`, `/.github/workflows/deploy-coolify.yml`, `/.github/workflows/promote-coolify-production.yml`, `/scripts/deploy/verify_environment.py`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`, `/docs/plans/DEPLOYMENT_STRATEGY_STATUS.md`, `/README.md`) — Replaced the old production-only split-service deploy flow with a real two-environment release path: CI still builds the frontend and backend once, staging now auto-deploys after successful `main` CI, and production is promoted manually by the exact same immutable SHA tag. Added a shared Coolify deploy/verify/rollback workflow, a reusable Python smoke verifier for frontend health, backend health, admin login, planner reads, public wedding load, couple login, couple dashboard, and SSE, and rewrote the deployment guide around two DO workload servers managed by Coolify Cloud rather than the earlier single-environment split-service assumption.
- **Frontend image made staging-promotable without rebuild** (`/app/utils/env.ts`, `/app/admin/guests/page.tsx`, `/app/admin/inbox/page.tsx`, `/app/admin/seating/page.tsx`, `/app/admin/weddings/[id]/seating/page.tsx`, `/app/admin/components/seating/SeatingConstraintsModal.tsx`, `/app/admin/planner/billing/connect.tsx`, `/app/admin/billing/success/page.tsx`, `/app/components/RequestRSVPLinkModal.tsx`, `/app/components/payments/CollectPaymentModal.tsx`, `/app/components/saas/SignupModal.tsx`, `/app/components/saas/apiClient.ts`, `/Dockerfile.frontend`, `/.github/workflows/ci.yml`, `/.env.example`) — Browser-side API routing now derives from the current hostname instead of depending on a production-only baked `NEXT_PUBLIC_API_BASE_URL`, while server-rendered frontend fetches rely on `INTERNAL_API_BASE_URL` / `FRONTEND_URL`. This lets the same frontend image move from staging to production without rebuilding, and CI now builds the frontend around `FRONTEND_URL` rather than a production-only public API URL.
- **Backend image artifact separation tightened** (`/Dockerfile.backend`) — Reworked the backend image into a small multi-stage build that filters the mixed `app/` tree down to Python-only sources before the runtime image is assembled. This removes the dead Next.js TS/TSX/CSS files from the backend container instead of merely deleting them in a later layer, so the production backend no longer ships the frontend source tree as wasted image payload.
- **GitHub Actions secret sync/rotation automation for the new Coolify rollout** (`/scripts/deploy/sync_github_secrets.sh`, `/scripts/deploy/github-secrets.example.env`, `/.gitignore`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`, `/README.md`) — Added a local env-driven `gh secret set` helper so the required Coolify deploy secrets and smoke-test credentials can be pushed into GitHub in one repeatable step instead of being managed by hand in the UI. The helper supports scoped updates for `shared`, `staging`, `production`, and `all`, and the deployment guide now documents the dry-run and rotation workflow.

### Fixed

- **Team invite acceptance lock rollback on validation errors** (`/app/services/team_management_service.py`, `/tests/backend/test_team_management_invite_lock.py`, `/.gitignore`) — The invite acceptance flow now releases its transitional `accepting` lock before re-raising handled `HTTPException`s such as password validation failures. This prevents pending invites from getting stranded in a non-terminal state that made later accept attempts look “already accepted” and blocked invite resend because resend only allows `pending` records.
- **Planner-scoped wedding gallery storage with legacy mitigation path** (`/app/services/gallery_upload_service.py`, `/app/api/gallery_admin.py`, `/app/api/gallery_public.py`, `/app/admin/weddings/[id]/page.tsx`, `/scripts/migrate_gallery_storage_layout.py`, `/tests/backend/test_gallery_storage_paths.py`, `/.gitignore`) — Wedding gallery uploads now write into planner-scoped prefixes while the admin and public read paths still understand the legacy `folder/{wedding-slug}/...` layout. Added merge/dedupe behavior for mixed old/new prefixes, public legacy fallback for live galleries that have not been reconciled yet, updated the wedding admin copy so planners stop being told to type obsolete storage paths, and added a dry-run/execute migration script that can copy existing legacy wedding assets into the new planner-scoped layout and update wedding document references before the public launch cutover.

## [2.28.0] - 2026-04-02

### Added

- **Behavioral analytics engine and cross-dashboard product metrics** (`/app/services/behavioral_analytics_service.py`, `/app/api/behavioral_analytics.py`, `/app/services/behavioralAnalyticsApi.ts`) — New `BehavioralAnalyticsService` computes WAU/MAU with stickiness ratio, a 5-step planner activation funnel (signed up → onboarding → first wedding → first invite → first RSVP), 4-month retention cohort analysis using the union of login and activity signals, MRR movement waterfall (new/churned/net/trial-to-paid), and week-over-week change indicators — all derived from existing collections via MongoDB aggregation pipelines without requiring new event tracking infrastructure. Exposes admin-auth endpoints under `/admin/behavioral-analytics`, `/admin/engagement-signals`, `/admin/weddings/{id}/non-responders`, and `/admin/weddings/{id}/budget-breakdown`, plus couple-auth cookie-based endpoints under `/couple/portal/non-responders` and `/couple/portal/budget-breakdown`.
- **Root admin dashboard product health surface** (`/app/admin/saas/page.tsx`) — Added four new sections after the existing Recent Signups panel: Product Health (WAU with trend arrows, MAU, stickiness ratio as north-star card), Activation Funnel (5-step gradient progress bars with step-to-step and overall conversion rates), Retention Cohorts + MRR Movement (side-by-side cohort table with color-coded retention badges and MRR waterfall with trial conversion rate), and Engagement Velocity (RSVP velocity trend, platform response rate, active engaged weddings count).
- **Planner dashboard per-wedding engagement signals** (`/app/admin/planner/page.tsx`) — Each wedding card in the planner dashboard now shows inline engagement badges: blue for recent RSVP activity, amber for 14+ day inactivity, red for zero RSVPs, orange for low response rates, purple for pending forms, and green for recently active weddings with no attention flags. Signals are computed server-side via `get_planner_engagement_signals()` and mapped per-wedding using a `useMemo` lookup.
- **Couple portal wedding readiness, non-responders, and budget breakdown** (`/app/couple/dashboard/page.tsx`) — Three new components in the couple dashboard: `WeddingReadinessCard` showing a weighted progress score (40% RSVP + 20% guest list + 20% events + 20% venue) with milestone checkboxes and color-coded progress bar; `NonRespondersCard` listing guests who haven't RSVPed sorted by days-since-invite with expandable list and urgency color coding; and `BudgetBreakdownCard` rendering a stacked bar chart plus per-category mini progress bars with a 10-color palette. Non-responders and budget data fetch through couple-auth cookie endpoints.

### Changed

- **Couple portal endpoints use dedicated couple-auth routes** (`/app/main.py`, `/app/api/behavioral_analytics.py`) — The couple-facing non-responders and budget breakdown endpoints use `require_couple_auth` with cookie-based JWT instead of admin Bearer token auth. The `couple_router` is registered at the `/couple` prefix so the couple dashboard calls `/couple/portal/non-responders` and `/couple/portal/budget-breakdown` with `coupleFetch()` credentials, matching the existing couple portal auth pattern.

### Fixed

- **Deployment documentation and split-service Coolify rollback alignment** (`/docs/plans/DEPLOYMENT_STRATEGY_STATUS.md`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`, `/README.md`, `/docs/architecture/Architecture_Doc.md`, `/docs/architecture/BRANCH_MANAGEMENT.md`, `/docs/automation/DEPLOYMENT.md`, `/docs/guides/DEPLOYMENT_SETUP.md`, `/.github/workflows/deploy-coolify.yml`) — Added a repo-grounded deployment strategy status document that separates the current single-container Coolify runtime from the recommended split-service Coolify path and explicitly marks older Vercel/DigitalOcean and droplet-only guides as historical. The split-service guide now matches the real GitHub Actions flow: API-driven deploys by Coolify application UUID rather than webhook-based deploys. The Coolify deploy workflow now records each service's pre-deploy image tag and uses that exact tag for automatic rollback instead of resetting to `latest`, which was not a true rollback after a bad image push.
- **Root admin planner invite modal viewport and mobile layout** (`/app/admin/users/page.tsx`) — Reworked the invite-planner modal to use a viewport-capped shell with an actual scrollable body, widened it to the existing admin modal width, and made the dense two-column sections responsive so long forms no longer clip below the fold without any visible scroll affordance on shorter screens or mobile-sized widths.
- **Single-container Coolify performance guardrails for public SSR and login bursts** (`/Dockerfile.coolify`, `/app/utils/env.ts`, `/app/utils/weddingPrivacyInfo.ts`, `/app/middleware/rate_limiting.py`, `/loadtests/locustfile.py`, `/docs/performance/locust-load-test-plan.md`) — The Coolify runtime now starts the backend through a dedicated wrapper that honors `WEB_CONCURRENCY` and falls back to a single worker automatically when Redis-backed cross-worker SSE fan-out is unavailable. Server-rendered public wedding bootstrap fetches now prefer the internal loopback API URL and use short revalidation instead of unconditional `no-store`, reducing self-inflicted frontend→backend proxy churn in the single-container deployment. Login throttling is now identity-aware with a separate IP backstop so multiple planners or team members behind one office IP do not trip a shared five-requests-per-minute bucket, and the Locust harness now supports bearer-token overrides so steady-state read benchmarks can exclude login churn.
- **Planner/couple/public read hot paths flattened for the single-container Coolify runtime** (`/app/api/planner_metrics.py`, `/app/services/couple_portal_service.py`, `/app/api/couple_portal.py`, `/app/services/guest_verification_service.py`, `/app/core/cache.py`) — Added short-TTL Redis-backed caches for planner wedding lists, couple portal dashboard payloads, and public wedding privacy bootstrap responses; narrowed planner/couple/privacy reads to the fields they actually render; and parallelized the couple dashboard fan-out instead of serially waiting on independent guest, budget, contract, forms, updates, and memories queries. In the production-shaped Locust rerun, the aggregate profile improved from `10` failures / `68.5 ms` average / `p99 1100 ms` / `24.1 s max` to `0` failures / `7.38 ms` average / `p99 24 ms` / `210 ms max`, with the previous `/admin/planner/weddings` and `/couple/portal/dashboard` tail spikes collapsing into low-double-digit millisecond reads.
- **Behavioral analytics auth, startup, and null-safety hardening** (`/app/api/behavioral_analytics.py`, `/app/services/behavioral_analytics_service.py`, `/app/admin/saas/page.tsx`, `/app/couple/dashboard/page.tsx`, `/tests/backend/test_behavioral_analytics_contract.py`) — Fixed the backend import crash by sourcing `ExtendedAuthUser` from the auth dependency module, moved planner/admin analytics routes onto the team-aware auth pattern, enforced the existing `view_analytics` permission, and added wedding-access checks before exposing per-wedding guest/budget data. Reworked planner engagement signals to respect team-member planner scope and batch wedding aggregates instead of issuing per-wedding N+1 queries. Retention cohorts now use true calendar month boundaries and a real union of login/activity users, trial conversion metrics no longer depend on the unwritten `state_history` field, and the SaaS/couple dashboards now tolerate partial analytics payloads without crashing on missing nested objects.
- **Behavioral analytics runtime cost reduced with cache-backed hot paths** (`/app/services/behavioral_analytics_service.py`, `/tests/backend/test_behavioral_analytics_contract.py`) — Added short-TTL caching for the root-admin behavioral dashboard payload and planner engagement signals, and replaced the remaining unbounded signup/cohort materializations with streamed cursor scans so the analytics endpoints stop recomputing the same heavy aggregates on every dashboard refresh.
- **Runtime warning cleanup for local and staging imports** (`/app/models/plus_one.py`, `/app/core/settings.py`, `/app/services/security_audit_service.py`, `/.env.example`, `/tests/backend/test_settings.py`) — Migrated the remaining Pydantic v1 config usage in the plus-one model to `ConfigDict(validate_by_name=True)` and moved security audit file logging onto a settings-backed repo-local path (`logs/security_audit.log`) with automatic directory creation and duplicate-handler suppression. This removes the noisy local import warnings without changing production override behavior.
- **MongoDB aggregation syntax for RSVP detection** (`/app/services/behavioral_analytics_service.py`) — Fixed invalid `$not: {$size: 0}` and duplicate `$ne` dict key patterns in the RSVP confirmation query. Now uses `$type: "array"` combined with `$ne: []` to correctly identify confirmed RSVPs (non-empty `attending` arrays), matching the existing `_calculate_rsvp_status()` logic in `planner_metrics.py`.

### Known Issues

- Behavioral analytics aggregation pipelines run on every dashboard load without caching — may become expensive at scale. Consider adding a scheduled snapshot pattern similar to `PlatformMetricsService`.
- The `fetchNonResponders()` and `fetchBudgetBreakdown()` functions in the TypeScript API service use admin Bearer-token auth and are intended for planner-side use only. Separate `fetchCoupleNonResponders()` and `fetchCoupleBudgetBreakdown()` functions are provided for couple-auth access.

## [Unreleased] - 2026-03-30

### Added

- **Locust read-only load test harness and runbook** (`/loadtests/locustfile.py`, `/docs/performance/locust-load-test-plan.md`, `/docs/performance/README.md`) — Added a repo-local Locust setup for safe staging load tests across the public wedding pages, planner dashboard reads, and couple portal reads. The harness deliberately excludes side-effecting flows such as OTP, RSVP submission, reminder sends, package sends, contract signing, and payment mutations, and the new performance runbook documents environment overrides, ramp stages, and pass/fail criteria.
- **Couple-owned guest memories uploads with QR intake, review, and export workflows** (`/app/[slug]/upload/[uploadToken]/page.tsx`, `/app/[slug]/upload/[uploadToken]/upload-client.tsx`, `/app/api/guest_memories.py`, `/app/services/guest_media_service.py`, `/app/services/guestMemoriesApi.ts`, `/app/couple/components/CoupleMemoriesSection.tsx`, `/app/couple/components/CoupleSidebar.tsx`, `/app/couple/dashboard/page.tsx`, `/app/models/wedding.py`, `/app/core/database_indexes.py`, `/app/services/couple_portal_service.py`) — Replaced the old guest check-in direction with a couple-facing guest media system: guests can scan a QR code, identify themselves, optionally tag uploads to a wedding event, upload photos or videos directly to a dedicated guest-media storage flow, and couples can review pending memories, keep or reject them, rotate or close the upload link, stream processed videos, download originals, and request bulk exports from the private couple portal.

### Changed

- **Public wedding bootstrap now distinguishes missing weddings from upstream failures** (`/app/[slug]/layout.tsx`, `/app/utils/weddingPrivacyInfo.ts`, `/tests/unit/weddingPrivacyInfo.test.ts`) — The `/:slug` server layout no longer collapses rate limits, backend errors, or malformed `privacy-info` responses into `notFound()`. True `404`s still render the wedding not-found route, while `429` and `5xx` failures now surface through the existing route error boundary instead of masquerading as missing weddings.
- **Route-family backend rate-limit buckets for public, admin, and couple traffic** (`/app/middleware/rate_limiting.py`, `/tests/backend/test_rate_limiting_middleware.py`) — Split the old shared non-auth `api` bucket into dedicated route-family buckets so public wedding metadata/gallery traffic no longer competes with authenticated planner and couple dashboard reads behind the same client IP. Also corrected dynamic guest-verification path matching so `/weddings/verify-guest-access/{slug}` no longer falls through into the generic bucket, and added focused middleware tests to pin the bucket classifier.
- **Dedicated billing sender for Stripe emails** (`/app/core/settings.py`, `/app/services/stripe_service.py`, `/.env.example`, `/README.md`, `/tests/backend/test_stripe_checkout_lifecycle.py`) — Stripe-originated billing notifications and subscription activation emails now use `RESEND_BILLING_EMAIL` when configured, falling back to the default transactional sender otherwise. This keeps invoice and billing communication on the new `billing@thespecialwedding.io` address without changing the sender identity for the rest of the platform’s emails.
- **Stripe planner checkout trial + activation lifecycle hardening** (`/app/services/stripe_service.py`, `/app/api/stripe_payment.py`, `/app/admin/planner/billing/page.tsx`, `/app/components/saas/SignupModal.tsx`, `/tests/backend/test_stripe_checkout_lifecycle.py`) — Planner billing and public signup now send explicit trial intent into Stripe Checkout instead of silently inheriting plan defaults. Zero-day invited planners and the public signup flow no longer pick up a hidden plan-level free trial, initial subscription activation emails/in-app notifications now come from `checkout.session.completed` after the local subscription sync finishes, and recurring `invoice.paid` notifications now skip the initial subscription invoice to avoid race-driven gaps and duplicate confirmation messages.
- **Planner billing-state truthfulness and invite-trial reset hardening** (`/app/admin/planner/billing/page.tsx`, `/app/admin/users/page.tsx`) — The planner billing surface now treats `pending_checkout`, `pending_payment`, `inactive`, and other unpaid statuses as payment-required states instead of falling through to the active-subscription management view, and the root-admin invite modal now resets from the fetched platform default without overwriting an explicit zero-day invite with a stale 30-day trial default.
- **Guest RSVP/OTP session hardening** (`/app/dependencies/guest_access.py`, `/app/api/guest_verification.py`, `/app/api/otp.py`, `/app/api/rspv.py`, `/app/api/gallery_public.py`, `/app/services/guest_verification_service.py`, `/app/services/otp_service.py`, `/app/services/rsvp_service.py`, `/app/[slug]/page.tsx`, `/app/[slug]/gallery/page.tsx`, `/app/[slug]/invite/[token]/page.tsx`, `/app/otp/verify/page.tsx`, `/app/components/RSVPModal.tsx`, `/app/components/RSVPForm.tsx`, `/app/components/GuestVerificationModal.tsx`, `/app/components/landing-page/LandingLayout.tsx`, `/app/utils/guestAccess.ts`, `/app/utils/publicGallery.ts`, `/app/core/settings.py`, `/.env.example`, `/tests/backend/test_guest_access_session_contract.py`) — Replaced the remaining guest-facing raw invite-token browser flow with a short-lived HttpOnly `guest_access_session` cookie. Invite links now exchange into a server-managed guest session, the landing page/OTP/RSVP/gallery flows now use session-backed endpoints with credentialed requests, guest-facing API responses stop echoing `guest.token`, and legacy query-token paths are reduced to one-time compatibility shims with immediate URL cleanup instead of long-lived browser storage.
- **Invited planner billing lifecycle alignment** (`/app/services/user_management_service.py`, `/app/dependencies/auth_extended.py`, `/app/components/AdminRouteGuard.tsx`, `/app/admin/page.tsx`, `/app/admin/components/TrialBanner.tsx`, `/app/contexts/AdminContext.tsx`, `/app/admin/planner/billing/page.tsx`) — Admin-invited planners now follow the same timed-trial-to-billing model as the rest of the subscription system: invited accounts with trial days still enter a real trial, while zero-day invites enter the existing payment-required Checkout state instead of slipping into usable unpaid planner access. Billing blocking, login redirects, banners, and the billing page now consistently treat unpaid `pending` / `pending_payment` / `inactive` planner states as billing-only access.
- **Resources/blog dark-surface typography fix and guest memories runbook expansion** (`/app/components/blog/MarkdownArticle.tsx`, `/app/resources/ResourcesClient.tsx`, `/app/resources/blog/[slug]/BlogArticleContent.tsx`, `/docs/testing/deployment-browser-e2e-runbook.md`) — Made the shared blog markdown renderer accept an explicit dark theme so article body copy and headings stay legible on the dark resources surfaces without relying on a global `dark` class, and expanded the deployment browser runbook to cover the planner guest-memories operations screen, public guest upload flow, and couple review/export validation path end to end.
- **Vendor public-link hardening** (`/app/api/vendor_forms.py`, `/app/api/vendor_contract_public.py`, `/app/services/vendor_service.py`, `/app/services/vendorManagementApi.ts`, `/app/admin/vendor/page.tsx`, `/app/vendor-form/[form_id]/page.tsx`, `/app/vendor-form/[form_id]/[token]/page.tsx`, `/app/vendor-form/[form_id]/VendorFormPageClient.tsx`, `/app/vendor-contract/[id]/page.tsx`, `/app/vendor-contract/[id]/[token]/page.tsx`, `/app/vendor-contract/[id]/PublicContractPageClient.tsx`, `/tests/backend/test_public_token_transport_contract.py`) — Canonical vendor form and vendor contract links now use path-scoped tokens instead of `?token=...`, legacy query-token links are immediately redirected onto the canonical path form, and public vendor contract signing now sends signer identity in the JSON body rather than the URL query string. Added focused regression coverage to pin the canonical routes and redirect behavior.
- **Couple, account-reset, and team-invite public-link hardening** (`/app/api/couple_invite.py`, `/app/api/couple_auth.py`, `/app/services/user_management_service.py`, `/app/services/team_management_service.py`, `/app/couple/setup/page.tsx`, `/app/couple/setup/[token]/page.tsx`, `/app/couple/setup/CoupleSetupPageClient.tsx`, `/app/couple/reset-password/page.tsx`, `/app/couple/reset-password/[token]/page.tsx`, `/app/couple/reset-password/CoupleResetPasswordPageClient.tsx`, `/app/setup-account/page.tsx`, `/app/setup-account/[token]/page.tsx`, `/app/setup-account/SetupAccountPageClient.tsx`, `/app/reset-password/page.tsx`, `/app/reset-password/[token]/page.tsx`, `/app/reset-password/ResetPasswordPageClient.tsx`, `/app/admin/team/accept/page.tsx`, `/app/admin/team/accept/[token]/page.tsx`, `/app/admin/team/accept/AcceptInvitePageClient.tsx`, `/tests/backend/test_setup_reset_token_transport_contract.py`) — Couple invite, couple reset-password, admin setup-account, admin reset-password, and team accept-invite links now use canonical path tokens instead of `?token=...`. Legacy query-token entry points remain temporarily compatible, but they immediately redirect onto the canonical path route. The client pages were split into explicit server wrappers plus client renderers so the redirect happens before the browser settles on the old query URL, and focused regression coverage now pins those canonical routes and updated email-link generators.
- **Security report refresh and residual public-token hardening plan** (`/security_best_practices_report.md`) — Re-audited the current codebase after the earlier SSE/docs/trusted-host hardening landed, confirmed that the critical/high blockers remain fixed, documented the safer guest-memories transport posture, and added two still-open medium findings for residual public URL-token transport and vendor-signing PII-in-query usage, along with a phased remediation plan.
- **Homepage testimonial hydration stabilization** (`/app/page.tsx`) — Deferred the public homepage marketing-data refresh until after the initial client hydration pass, and aligned the stale testimonial fallback copy with the current public testimonial API content so the landing page no longer trips a recoverable hydration mismatch when the browser replaces SSR fallback testimonials with admin-configured live content.
- **Planner-managed guest memories rollout operations** (`/app/admin/memories/page.tsx`, `/app/admin/memories/error.tsx`, `/app/admin/components/Sidebar.tsx`, `/app/components/guest-memories/GuestMemoriesSummaryCard.tsx`, `/app/couple/components/CoupleMemoriesSection.tsx`, `/app/api/guest_memories.py`, `/app/services/guestMemoriesApi.ts`, `/app/services/guest_export_service.py`, `/tests/backend/test_guest_memories_service.py`) — Added a planner-facing Guest Memories operations surface that reuses the existing memories backend state, QR generation, and styling primitives instead of creating a parallel feature stack. Planners can now choose a wedding, copy the active upload link, generate or download the QR code, download a printable guest-memories sign PDF, close or reopen uploads, rotate the upload link, and monitor high-level submission counts, while couples keep private review and download control inside the couple portal.
- **Guest memories privacy, validation, and durable job recovery hardening** (`/app/services/guest_media_service.py`, `/app/api/guest_memories.py`, `/app/main.py`, `/app/services/guestMemoriesApi.ts`, `/app/couple/components/CoupleMemoriesSection.tsx`, `/tests/backend/test_guest_memories_service.py`) — Locked guest memories back down to authenticated asset access instead of long-lived public bucket and video URLs, revalidated uploaded objects against the reserved file size and MIME contract during finalize, moved video ingest and export recovery onto the leader-elected background scheduler so work survives process restarts, removed duplicate list-fetch churn from the couple memories UI, and added focused backend regression coverage for the new finalize/privacy rules.
- **Guest memories Cloudflare Stream hardening** (`/app/services/guest_media_service.py`, `/tests/backend/test_guest_memories_service.py`, `/.env.example`, `/app/services/config_validator.py`) — Made Cloudflare Stream copies private at creation time instead of patching them after ingest, added origin allowlisting and failed-video state handling based on the Stream status payload, preflighted the signed R2 source URL for the HEAD and ranged-GET behavior Stream copy expects, reused short-lived signed playback tokens to reduce routine Cloudflare API churn, and removed the stale `GUEST_MEDIA_DOMAIN` guest-memories config path that no longer matches the authenticated delivery model.
- **Guest memories Stream env isolation** (`/app/services/guest_media_service.py`, `/.env.example`, `/app/services/config_validator.py`) — Kept the existing shared `CLOUDFLARE_ACCOUNT_ID` variable for account targeting and isolated only the guest-memories Stream credential behind `CLOUDFLARE_STREAM_API_TOKEN` so the feature no longer collides with any generic Cloudflare API token already used elsewhere in production.
- **Guest memories regression test packaging fix** (`/.gitignore`, `/tests/backend/test_guest_memories_service.py`) — Stopped the new backend regression coverage from being silently excluded by the repository ignore rules and made the test module import-safe in lean local Python environments so the guest-memories hardening assertions can actually run during backend verification.
- **Guest memories platform validation and lint hardening** (`/app/components/saas/PlannerAuthSection.tsx`, `/app/components/budget/CreateTemplateModal.tsx`, `/app/components/budget/RecordPaymentModal.tsx`, `/app/components/budget/VendorQuoteCard.tsx`, `/app/components/contracts/DigitalSignature.tsx`, `/app/components/landing-page/AnchorNav.tsx`, `/app/components/landing-page/EventLocationSection.tsx`, `/app/components/landing-page/WeddingDarkModeToggle.tsx`, `/app/components/saas/IsometricPlatformHero.tsx`, `/app/components/saas/PlannerAuthModal.tsx`, `/app/components/saas/SaasNav.tsx`, `/app/components/saas/WeddingThemedHero.tsx`, `/app/contexts/ThemeContext.tsx`, `/app/page.tsx`, `/app/verify-email/[token]/page.tsx`, `/.env.example`, `/app/services/config_validator.py`) — Cleared the remaining React Compiler and lint blockers surfaced during the guest-memories rollout, updated environment/config validation for the new storage and streaming requirements, and revalidated the release path with a clean `npm run lint`, a successful production `npm run build`, and a successful backend `python3 -m compileall app` pass.
- **Legacy planner check-in runtime retirement** (`/app/main.py`, `/app/api/checkin.py`, `/app/services/checkin_service.py`) — Removed the mounted admin check-in API and deleted the unused runtime implementation so the shipped product no longer exposes the abandoned guest check-in path alongside the new couple-owned guest memories flow.

- **Money dashboard aggregation, scheduler leadership, and deploy-gate cleanup** (`/app/admin/money/page.tsx`, `/app/api/budget.py`, `/app/api/contracts.py`, `/app/api/health.py`, `/app/api/stripe_payment.py`, `/app/services/budget_service.py`, `/app/services/contract_service.py`, `/app/main.py`, `/package.json`, `/eslint.config.mjs`, `/app/api/gallery_upload.py`, `/app/components/GuestVerificationModalOld.tsx`) — The money dashboard now reads joined incoming/outgoing payment overview endpoints instead of fanning out one HTTP request per contract and per wedding budget, the Stripe subscription endpoint now returns the plan limits/pricing the page already needs, and the readiness probe now checks the real Redis client instead of an undefined symbol. Background billing/rollup schedulers now use a Mongo-backed lease so only one replica runs them at a time, the ESLint gate now uses Next 16’s flat config instead of crashing before linting, and the legacy unwired gallery router / old guest verification modal were removed from the tree.
- **Public guest/gallery access dedupe and paginated gallery reads** (`/app/[slug]/layout.tsx`, `/app/[slug]/page.tsx`, `/app/[slug]/gallery/page.tsx`, `/app/components/GuestVerificationModal.tsx`, `/app/components/landing-page/LandingLayout.tsx`, `/app/api/gallery_public.py`, `/app/services/gallery_upload_service.py`, `/app/types/wedding.ts`, `/app/utils/publicGallery.ts`) — Public wedding routes now reuse the server-fetched privacy payload instead of refetching it in the guest verification modal, token-based invite access now follows the dedicated token endpoint instead of the generic verification POST, and verified gallery reads now reuse durable guest tokens/passwords instead of re-triggering the wrong auth path. Public gallery responses are now bounded and paginated with a load-more flow on the full gallery page, while the admin gallery list now paginates through the full bucket instead of truncating at the first object page.
- **Shared Redis-backed public and guest rate limiting** (`/app/core/cache.py`, `/app/utils/rate_limiter.py`, `/app/services/guest_verification_service.py`, `/app/api/blog.py`, `/app/api/knowledge_base.py`) — Public blog and knowledge-base read throttles now use shared Redis counters with proxy-aware client IP extraction instead of per-process in-memory deques, so the limits hold when API replicas scale out. Guest verification, RSVP token access, and RSVP-link resend throttles now use shared hashed Redis keys with memory fallback for local/dev, and the RSVP-link resend limiter now scopes by wedding as well as contact instead of unintentionally colliding across unrelated events.
- **Atomic guest verification attempt serialization** (`/app/core/cache.py`, `/app/services/guest_verification_service.py`, `/app/api/guest_verification.py`, `/app/api/gallery_public.py`, `/tests/backend/test_guest_verification_rate_limit.py`) — Guest page verification, RSVP token access, and RSVP-link resend now take a short-lived distributed lock before checking and recording failures, which removes the check-then-record race that previously allowed concurrent attempts sharing the same identifier to overshoot the lockout threshold. The lock scope now matches the shared failure-counter scope so password-protected and anonymous attempts are serialized correctly across replicas instead of only within one process.
- **Public vendor profile normalization and custom category rendering** (`/app/api/vendor_public.py`, `/app/vendors/page.tsx`, `/app/vendors/[id]/page.tsx`, `/app/vendors/[id]/layout.tsx`) — The public vendor API now backfills missing array fields like `service_subcategories` and `portfolio_urls` for older vendor records, preventing the public vendor detail page from crashing on sparse documents. The public directory and detail page also now render planner-defined custom vendor labels such as `Family MC` instead of collapsing every `other` category back to a generic `Other`.
- **Production hardening for SSE auth and FastAPI docs exposure** (`/app/api/notification_stream.py`, `/app/contexts/SSEContext.tsx`, `/app/core/settings.py`, `/app/main.py`, `/.env.example`, `/tests/backend/test_settings.py`, `/tests/backend/test_notification_stream_contract.py`) — The admin notification stream now authenticates from the existing `admin_token` HttpOnly cookie instead of accepting bearer JWTs in the URL query string, and interactive FastAPI docs/schema are now controlled by an explicit `ENABLE_API_DOCS` setting that defaults to enabled outside production and disabled in production. The root API payload now advertises `/docs` only when docs are actually exposed.
- **Knowledge base status contract and route cleanup** (`/app/models/knowledge_base.py`, `/app/api/knowledge_base.py`, `/app/services/knowledge_base_service.py`, `/app/admin/components/kb/ArticleEditor.tsx`, `/tests/backend/test_knowledge_base_contract.py`) — Removed the stray `pending_review` status from the KB contract, standardized the shared status set on `draft`, `published`, and `archived`, expanded the editor to match that contract, fixed the admin “all articles” service path so it can truly fetch every status, stopped the main article list query from loading full `content`/`feedback` blobs unnecessarily, and removed the unwired double-prefixed feedback-summary endpoint.
- **Legacy auth/API surface removal** (`/app/contexts/AdminContext.tsx`, `/app/hooks/index.ts`) — Completed the admin auth cleanup by treating `AdminProvider` / `useAdmin()` as the only supported admin auth and API surface, deleting the unused `AuthContext` / `APIContext` compatibility files and the dead generic request-hook layer that had only existed for that legacy model, and shrinking the shared hooks barrel back down to the live app hooks that still have real consumers.
- **Planner-defined vendor categories and wedding events** (`/app/models/vendor.py`, `/app/services/vendorManagementApi.ts`, `/app/services/vendor_service.py`, `/app/admin/vendors/page.tsx`, `/app/admin/vendors/contracts/[id]/page.tsx`, `/app/admin/vendors/contracts/new/page.tsx`, `/app/models/wedding.py`, `/app/types/wedding.ts`, `/app/utils/weddingEvents.ts`, `/app/utils/wedding_event_types.py`, `/app/admin/weddings/page.tsx`, `/app/admin/weddings/[id]/page.tsx`, `/app/components/RSVPForm.tsx`, `/app/admin/reminders/page.tsx`, `/app/admin/guests/page.tsx`, `/app/models/rsvp.py`, `/app/models/plus_one.py`, `/app/services/admin_rsvp_service.py`, `/app/services/reminder_service.py`, `/app/services/reminder_service_twilio.py`, `/app/services/reminder_service_telnyx.py`, `/app/services/couple_portal_service.py`, `/app/couple/dashboard/page.tsx`) — Planners can now use a first-class `MC / Host` vendor category, choose `Other` with a required custom vendor label, and define truly custom wedding event names without breaking RSVP, reminders, guest management, or couple-facing attendance summaries. The wedding editors now require a label before saving a custom event, and downstream contract/vendor screens render the real planner-defined category labels instead of collapsing them back to plain `Other`.
- **Vendor sponsored-ad dedup index repair** (`/app/core/database_indexes.py`) — Startup now detects and replaces stale local `idx_sponsored_ad_dedup` index definitions on `vendor_profiles` that incorrectly matched `null` `source_campaign_id` values and blocked ordinary planner vendor creation after the first row. This keeps sponsored-ad dedup protection for imported ad leads without breaking normal vendor directory use.
- **Fail-closed session resume across admin and couple portals** (`/app/contexts/AdminContext.tsx`, `/app/utils/adminAuthStorage.ts`, `/app/components/AdminRouteGuard.tsx`, `/app/admin/planner/page.tsx`, `/app/admin/saas/page.tsx`, `/app/contexts/CoupleAuthContext.tsx`, `/app/components/CoupleRouteGuard.tsx`, `/app/couple/layout.tsx`, `/app/couple/login/page.tsx`) — Long-idle browser resumes now do a single silent session revalidation on focus/pageshow/visibility return instead of leaving stale shells, hanging planner spinners, or zeroed SaaS cards on screen. Short window switches keep in-progress work intact when the session is still valid, while expired admin and couple sessions now clear state and redirect cleanly to login with an explicit session-expired message.
- **Couple dashboard guest tracker overhaul** (`/app/services/couple_portal_service.py`, `/app/couple/dashboard/page.tsx`) — Reworked the couple-facing dashboard metrics so guest information is no longer collapsed into a single “Guests invited” number. The portal now distinguishes guest list target, live guest list size, invites sent, responses received, attending, declined, awaiting response, response rate, and event-by-event attendance so couples can answer common RSVP questions without needing the planner for basic status checks.
- **Stripe contract-payment lifecycle hardening** (`/app/utils/stripeClient.ts`, `/app/components/contracts/StripePaymentCapture.tsx`, `/app/pay/[id]/page.tsx`, `/app/contracts/[token]/page.tsx`, `/app/services/autopilot_service.py`, `/app/services/stripe_service.py`, `/app/services/contract_service.py`, `/app/services/contract_email_service.py`, `/app/api/contracts.py`) — Contract and portal payment flows now share a single Stripe.js client across the session, preload it earlier, and use dynamic payment methods on SetupIntents instead of card-only configuration. Real contract charges now flow through one idempotent payment-success path for both deposits and scheduled installments, so budget sync, planner bell notifications, planner payment emails, and couple payment receipts with remaining-balance/payment-schedule breakdowns happen exactly once on actual charge success instead of being split between signing-time side effects and webhook retries.
- **Contract schema alignment and snapshot hydration** (`/app/models/autopilot.py`, `/app/services/package_service.py`, `/app/services/contract_service.py`, `/app/api/contracts.py`, `/app/contracts/[token]/page.tsx`, `/app/portal/[token]/page.tsx`, `/app/components/contracts/ContractTemplate.tsx`, `/app/services/contract_email_service.py`, `/app/services/contract_pdf_service.py`) — The autopilot contract model now explicitly carries planner branding/contact snapshot fields, package send snapshots the linked planner and wedding metadata into the contract, contract reads normalize `partner1_name` / `partner2_name` into a consistent couple display shape and backfill missing venue/planner/package snapshot fields from source records, the public contract endpoint exposes the planner details the frontend already expects, and the contract page, portal, emails, and PDF generator now all read the same schema instead of mixing the new couple model with legacy `name` / `partner_name` aliases.
- **Package contract delivery and couple payment/signature hardening** (`/app/services/package_service.py`, `/app/services/contract_email_service.py`, `/app/admin/packages/[id]/send/page.tsx`, `/app/components/contracts/StripePaymentCapture.tsx`, `/app/components/contracts/ContractTemplate.tsx`, `/app/contracts/[token]/page.tsx`, `/app/api/contracts.py`) — Package send now dispatches the couple invitation email as part of the success path and rolls back the contract if delivery fails, the planner success screen points to the real `/contracts/[token]` route, the couple contract payment step loads Stripe from the backend config instead of hanging on a missing `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`, payment capture now carries the Stripe customer ID through to the signature request so signing no longer dies with a 422 validation error, and the public contract template now preserves calendar dates without timezone drift.
- **Paid packages without installment schedules now charge in full on signing** (`/app/utils/payment_schedule.py`, `/app/services/package_service.py`, `/app/services/contract_service.py`, `/app/services/contract_email_service.py`, `/app/services/contract_pdf_service.py`, `/app/components/contracts/ContractTemplate.tsx`) — An empty package payment schedule is now treated as a single full-payment milestone due on signing instead of “save card but never charge”. Package snapshots, contract hydration, scheduled-payment creation, receipts, PDFs, and the public contract view now all resolve that fallback the same way, so couples signing a one-time package get a real charge path and the remaining-balance logic only stays nonzero when the planner explicitly configured installments.
- **Mixed-format resources/blog rendering hardening** (`/app/components/blog/MarkdownArticle.tsx`, `/app/resources/blog/[slug]/page.tsx`, `/app/services/blog_service.py`, `/app/utils/blog_content.py`, `/app/admin/components/blog/BlogArticleEditor.tsx`) — The shared blog renderer now supports markdown plus sanitized editorial HTML, the split-panel `/resources` reader and direct blog pages both use the same safe rich-text path, and admin blog writes normalize pasted HTML before storage so public articles no longer surface literal `<p>` and `<h3>` tags.
- **Package send contract date normalization** (`/app/services/package_service.py`, `/app/services/contract_service.py`, `/app/utils/mongo_dates.py`, `/app/admin/packages/[id]/send/page.tsx`) — Fixed the package send flow so wedding dates and scheduled-payment due dates are converted into Mongo-safe UTC datetimes instead of crashing on raw Python `date` objects, and cleaned up the linked-wedding autofill so couples named with `and` populate both partner fields while wedding dates keep their intended calendar day in the dropdown.
- **Public planner signup now requires email verification after checkout** (`/app/services/stripe_service.py`, `/app/admin/login/page.tsx`) — Stripe subscription webhooks no longer auto-mark `public_signup` planners as `email_verified`, so payment can complete without silently bypassing the verification gate. Paid-but-unverified planners now stay blocked from sign-in until they use the email link, and the planner login page shows a truthful post-checkout banner plus the actual backend auth error instead of collapsing verification failures into a generic bad-password message.
- **Manual test-account contract clarified** (`/.env.example`, `/README.md`, `/docs/architecture/DEVELOPER_SETUP.md`, `/scripts/setup_admin_user.py`, `/scripts/reset_test_user_data.py`) — Documented that only the root admin is bootstrap-created at startup, while the `TEST_*` identities in `.env` are manual QA fixtures for signup, payment, invite, and acceptance flows and must be recreated through the frontend after a reset.
- **Local test-user reset utility** (`/scripts/reset_test_user_data.py`) — Added a guarded reset script for local/dev environments that dry-runs by default, can wipe all account records plus user-generated planner/couple/vendor data when explicitly confirmed, and includes a verification mode to prove the `.env` test identities and reset collections are actually empty before reseeding.
- **Shared glass component light-mode pass** (`/app/admin/components/ui/glass/GlassButton.tsx`, `/app/admin/components/ui/glass/GlassCard.tsx`, `/app/admin/components/ui/glass/GlassTable.tsx`, `/app/admin/components/ui/glass/GlassPagination.tsx`) — Rebased the reusable admin glass primitives onto explicit light-mode borders, backgrounds, hover states, and dropdown styling instead of translucent white-only treatments so platform, guests, support, vendors, seating, weddings, and planner surfaces that depend on them inherit stronger light-mode contrast automatically.
- **Notifications page theme cleanup** (`/app/admin/notifications/page.tsx`) — Normalized the notifications workspace onto the same light-safe admin surfaces, inputs, tabs, cards, and modal styles used elsewhere in the dashboard, and removed several malformed/duplicated dark-mode utility strings so planner and root-admin notification views stay readable in both themes.
- **Theme audit continuation for forms and wedding configuration** (`/app/admin/forms/page.tsx`, `/app/admin/weddings/[id]/page.tsx`, `/app/admin/components/AdminHeader.tsx`) — Hardened the next set of light-mode gaps by replacing the forms creation studio’s dark-first left rail and option cards with explicit light surfaces and slate typography, giving the wedding detail hero actions readable light-mode button treatments over the bright header gradient, and fixing the older admin mobile header/menu hover states so navigation affordances remain visible outside dark mode.
- **Theme audit follow-up for planner/vendor flows** (`/app/admin/team/accept/page.tsx`, `/app/admin/vendor/page.tsx`) — Extended the light/dark audit beyond the planner team grid into the team-invite acceptance flow and vendor workspace, replacing dark-only cards, inputs, pills, and glass panels with explicit light surfaces and readable slate text while preserving the more dramatic dark presentation behind `dark:` overrides.
- **Team member invite acceptance hardening** (`/app/services/team_management_service.py`, `/app/utils/migrations.py`) — The team-member accept flow now consumes invite tokens by unsetting them instead of writing `null`, retries can repair half-finished invite acceptances that already created the linked `users` record, and a startup migration heals the previously stranded pending invites that were left behind by the unique `idx_invite_token` null-collision bug.
- **Planner team light-mode contrast alignment** (`/app/admin/planner/team/page.tsx`, `/app/admin/planner/team/InviteTeamMemberModal.tsx`, `/app/admin/planner/team/EditTeamMemberModal.tsx`, `/app/admin/planner/team/teamConstants.ts`) — Replaced the dark-only team-management cards, filters, table cells, and team-member modal shells with explicit light surfaces, readable slate text, and light-safe controls while preserving the existing darker treatment behind `dark:` overrides, so the planner team page now matches the rest of the planner portal in both themes.
- **Root-admin metrics accuracy pass** (`/app/services/platform_metrics_service.py`, `/app/admin/saas/page.tsx`, `/app/admin/billing/page.tsx`, `/app/admin/page.tsx`, `/app/admin/support/page.tsx`) — Re-aligned root-admin analytics with the live Mongo data by counting active users from recent logins instead of account enablement, excluding trials from MRR/ARR while still showing trial counts, surfacing unknown/pending subscription states in billing totals, unpacking the admin activity response envelope correctly, and mapping support cards to the metrics the backend actually provides.
- **Planner management page design realignment** (`/app/admin/users/page.tsx`) — Rebuilt the root-admin planner management surface around the same card, toolbar, table, and modal patterns used by the rest of the admin portal, replacing the older gradient-glass dashboard treatment with cleaner shared admin surfaces so the page now matches platform styling in both light and dark modes.
- **Root-admin account directory scope alignment** (`/app/admin/users/page.tsx`, `/app/admin/components/Sidebar.tsx`, `/app/admin/saas/page.tsx`, `/app/services/user_management_service.py`, `/app/api/user_management.py`) — Converted the old planner-only `/admin/users` screen into a true root-admin account directory with explicit role tabs, accurate scope summaries, SaaS drill-down links into matching account slices, and protected-account safeguards so root admins can inspect every account type without mistaking total platform counts for planner-only data.
- **Root-admin light-mode contrast pass** (`/app/admin/users/page.tsx`, `/app/admin/components/blog/BlogManager.tsx`, `/app/admin/components/blog/BlogCategorySidebar.tsx`, `/app/admin/components/blog/BlogArticleCard.tsx`, `/app/admin/components/blog/BlogArticleList.tsx`, `/app/admin/components/blog/BlogArticleEditor.tsx`, `/app/components/blog/MarkdownArticle.tsx`) — Replaced dark-only glass/text treatments on planner management and support-blog surfaces with explicit light-mode cards, inputs, and typography while preserving the darker glass styling behind `dark:` overrides, so root-admin pages keep readable hierarchy in both themes.
- **Admin ads density and role-route alignment** (`/app/admin/ads/page.tsx`, `/app/components/AdminRouteGuard.tsx`, `/app/contexts/AdminContext.tsx`, `/app/admin/weddings/page.tsx`, `/app/admin/weddings/[id]/page.tsx`) — Compacted the root-admin ad platform cards and queue spacing, made the ads tab rails/filter sections behave on narrower desktop widths, and tightened shared admin role redirects so root admins land on `/admin`, planners land on `/admin/planner`, and planner-only wedding surfaces stop exposing the root-admin shell to the planner detail editor.
- **Vendor portal settings admin-mode guard** (`/app/portal/ads/settings/page.tsx`, `/app/portal/ads/components/styles.ts`) — The vendor settings page now detects root-admin shell access and renders a deliberate admin preview state instead of throwing a broken “Failed to load profile” toast for non-vendor accounts, while also reusing shared vendor portal surface/input/button styles for the settings UI.
- **Lint warning cleanup** (`/app/admin/guests/page.tsx`, `/app/admin/platform/page.tsx`, `/app/admin/support/page.tsx`, `/app/admin/users/page.tsx`, `/app/admin/vendors/page.tsx`, `/app/couple/dashboard/page.tsx`) — Stabilized hook dependencies, pagination callbacks, and callback props so the frontend now passes ESLint without React hook warnings.
- **Blog/resources contract hardening** (`/app/resources/page.tsx`, `/app/resources/blog/[slug]/page.tsx`, `/app/admin/components/blog/BlogArticleEditor.tsx`, `/app/components/blog/MarkdownArticle.tsx`) — Unified markdown rendering between admin preview and public resources, wired `meta_title` into page metadata, aligned category display, and limited static blog fallbacks to non-production environments so deployed public content has one source of truth.
- **Resources server-rendered blog index** (`/app/resources/page.tsx`, `/app/resources/ResourcesClient.tsx`, `/app/resources/resourcesShared.ts`, `/app/resources/blog/serverApi.ts`) — Moved the public blog-card fetch to the server with ISR, extracted shared resources/blog contracts, and kept the split-panel reader as a client shell so `/resources` ships indexed article content and crawlable article links in initial HTML without duplicating public fetch logic.
- **Resources deployment hardening** (`/app/resources/page.tsx`, `/app/resources/ResourcesClient.tsx`, `/app/resources/blog/serverApi.ts`, `/app/sitemap.ts`) — Public blog/resources now distinguishes unavailable API responses from legitimate empty content, retries the blog feed client-side when the server render could not fetch it, and the sitemap no longer falls back to hardcoded blog slugs that can index dead URLs.
- **Couple budget sync alignment** (`/app/services/couple_portal_service.py`) — Rewired the couple dashboard budget summary to read the same canonical planner budget sources as the main budget surface, using `weddings.total_budget` plus `budget_categories.actual_spent` instead of the stale legacy `budgets` collection.
- **Alternate pricing renderer alignment** (`/app/components/saas/PricingSection.tsx`, `/app/admin/planner/billing/page.tsx`) — Updated the root-admin configurable pricing section to use the cookie-backed admin session bootstrap instead of legacy `authToken` storage checks, and wired its selected plan/interval redirect into the planner billing checkout surface.
- **Root-admin metrics fetch guards** (`/app/admin/platform/page.tsx`, `/app/admin/billing/page.tsx`, `/app/contexts/AdminContext.tsx`) — Prevented planner sessions from calling `/admin/platform/health` and related root-admin metrics endpoints before the frontend redirect runs, and fixed stale token/profile role drift in the shared admin context so protected pages wait for confirmed root-admin auth instead of logging noisy `403 Forbidden` fetch errors.
- **Platform errors scope clarity** (`/app/admin/platform/page.tsx`, `/docs/testing/deployment-browser-e2e-runbook.md`) — Removed the misleading mixed-scope error tab badge, added an explicit “Other Severities” current-page breakdown, and documented the 24-hour vs 30-day validation rules in the browser runbook so platform diagnostics are tested against the correct scope.
- **Platform error window reconciliation** (`/app/api/admin_platform_metrics.py`, `/app/admin/platform/page.tsx`, `/tests/backend/test_platform_metrics.py`, `/docs/testing/deployment-browser-e2e-runbook.md`) — Added a shared error-window selector, literal `critical`/`warning`/`other` severity buckets, and full filtered-result summaries so the Health tab and Errors tab now reconcile against the same selected window instead of mixing 24-hour, 30-day, and current-page-only counts.
- **Platform/root-admin defect fixes** (`/app/admin/platform/page.tsx`, `/app/admin/users/page.tsx`, `/app/api/planner_ad_preferences.py`, `/app/api/ai.py`, `/app/services/ai_service.py`, `/app/services/vendor_signup_service.py`, `/app/admin/budget/quotes/page.tsx`, `/app/admin/budget/templates/page.tsx`) — Aligned platform timestamps with the same admin timezone formatter used on the dashboard, replaced the broken planner “View Details” dead route with a real detail modal, fixed planner ad preference lookups to use the authenticated planner identity, stopped dashboard insights from masking upstream HTTP errors as generic 500s and let root-admin operational AI usage bypass planner subscription credit checks, corrected vendor signup service DB initialization, and authenticated the budget wedding pickers so they stop generating `/weddings` auth noise.
- **Wedding event time validation** (`/app/admin/weddings/[id]/page.tsx`, `/app/admin/weddings/page.tsx`, `/app/models/wedding.py`, `/app/services/wedding_service.py`) — Kept event times as strings but added shared frontend validation and backend normalization so planners can only save structured time values like `3:00 PM`, `3 PM`, or `15:00`.
- **Guest pagination performance** (`/app/admin/guests/page.tsx`, `/app/api/admin_rsvp.py`, `/app/api/plus_one.py`, `/app/services/admin_rsvp_service.py`, `/app/services/plus_one_service.py`) — Scoped RSVP and plus-one fetches to the currently paged guests instead of refetching wedding-wide related datasets on every page change.
- **Authentication docs refresh** (`/docs/security/AUTHENTICATION_SYSTEM.md`, `/docs/security/SECURITY.md`) — Rewrote stale two-cookie/browser-storage documentation to match the current secure-cookie plus in-memory token bootstrap model and current role set.

## [2.28.0] - 2026-03-24 — Planner Inbox, Couple Messaging, AI Chat Gating, Cache Fixes

### Added

- **Split-panel planner inbox** (`/app/admin/inbox/page.tsx`) — Full rewrite with conversation list + message detail split view, unread badges, real-time couple message display, and keyboard send (Enter).
- **Shared inbox UI components** — `ChatInput.tsx`, `MessageBubble.tsx`, `InboxListItem.tsx`, `SplitPanelInbox.tsx` for reuse across planner and couple portals.
- **Couple tab on wedding detail** (`/app/admin/weddings/[id]/page.tsx`) — New "Couple" tab with invite, revoke/restore access, and resend invite functionality.
- **Weddings list inline notes/replies** (`/app/admin/weddings/page.tsx`) — Expanded with 532 new lines: planner notes with reply threads, sticky notes UI, message compose with send button.
- **AI chat widget role gating** — Widget only renders for `is_wedding_planner` or `is_team_member` roles; hidden for root admins and couples.
- **Autopilot status endpoint** (`/app/api/autopilot.py`) — New `/admin/status` endpoint for autopilot metrics.
- **Vendor notification refactor** — Shared notification endpoints eliminating duplicate code across vendor portal.
- **Task recurrence in calendar** — TaskModal now supports recurring tasks with presets (daily, weekly, monthly) and iCal RRULE generation.
- **Couple portal UI components** — `CoupleSidebar.tsx`, `CoupleTopHeader.tsx`, `CoupleLayoutClient.tsx` for consistent layout matching admin portal.
- **Error boundaries** — Added `error.tsx` for inbox, weddings, budget, billing, dashboard, forms, guests, metrics, notifications, packages, calendar, platform, saas, seating, support, users, vendors, and ads pages.
- **Vendor portal notifications and settings pages** — New `/portal/ads/notifications/page.tsx` and `/portal/ads/settings/page.tsx`.
- **Cursor pagination utility** (`/app/utils/cursor_pagination.py`) — Reusable cursor-based pagination for API endpoints.
- **Rate limiter utility** (`/app/utils/rate_limiter.py`) — Configurable rate limiting for API routes.
- **Dependency management script** (`/scripts/update-deps.mjs`) — Automated dependency updates with dry-run, interactive, and auto modes.
- **Database scripts** — `cleanup_webhook_events.py` for Stripe webhook cleanup, `create_indexes_p0.py` for MongoDB index migration, `generate_types.sh` for TypeScript type generation from Pydantic models.
- **Testing checklist** (`/docs/TESTING_CHECKLIST_v2.28.0.md`) — Comprehensive v2.28.0 QA checklist with 39 test cases across 6 sections.
- **Architectural audit** (`/docs/qa/P0_ARCHITECTURAL_REFACTORS.md`) — P0 architectural refactors document.
- **Couple portal visual audit** (`/docs/frontend/COUPLE_PORTAL_VISUAL_AUDIT.md`) — Visual discrepancy audit between couple and planner portals.

### Changed

- **Cache-Control middleware** (`/app/main.py`) — Rewrote to handle Next.js `_next/` assets separately (no-cache in dev, immutable in prod), added `/couple-portal/`, `/couple/`, `/admin/` to no-cache rules, and added mutation method no-cache for POST/PUT/PATCH/DELETE.
- **Couple dashboard** (`/app/couple/dashboard/page.tsx`) — Added `cache: 'no-store'` to message fetch, major UI refactor with sidebar-driven navigation.
- **Planner inbox fetch** (`/app/admin/inbox/page.tsx`) — Added `cache: 'no-store'` to prevent stale message data.
- **Admin router ordering** — Reorganized to prioritize notification stream route.
- **Stripe service** (`/app/services/stripe_service.py`) — Retained email verification token for user consistency, refactored payment handling.
- **Couple portal service** — Switched to ResendEmailService for email sending.
- **User management service** — Improved email verification logic, cleans up tokens for already-verified users.
- **Couple login/setup pages** — Updated styles to align with design tokens, added password validation with visual feedback.
- **Wedding detail page** — Conditional ad rail layout, added couple tab.
- **Admin sidebar** — Updated navigation items and styling.
- **Image assets** — Optimized/replaced dashboard, budget, forms, and wedding config screenshots.
- **Icon imports in `[id]/page.tsx`** — Switched from barrel import to direct path imports to avoid Turbopack module factory instantiation bug.

### Fixed

- **BUG-001 (Critical):** Messages saved to DB but not displayed in inbox — caused by `Cache-Control: public, max-age=300` on `/couple-portal/` and `/admin/` routes falling through to catch-all. Fixed in middleware + frontend fetch calls.
- **BUG-003 (Low):** Wedding date rendering "20270" instead of "2027" in certain views.

### Known Issues

- **BUG-002 (Medium):** AI chat widget z-index overlaps with inbox send button on certain pages. Workaround: use Enter key to send.
- **Turbopack module factory error:** `lucide-react` barrel import triggers stale module factory instantiation in dev mode on `[id]/page.tsx`. Mitigated by switching to direct icon imports. Known Turbopack HMR bug tracked in vercel/next.js#84264.

### Removed

- **Couple portal standalone page** (`/app/admin/couple-portal/page.tsx`) — 1,770 lines removed; functionality moved to inbox and wedding detail couple tab.
- **Unused dependencies** — Removed `@dnd-kit/utilities`, `is-number`, `victory-vendor` from package.json.

---

## [2.27.0] - 2026-03-24 — Couple Portal Redesign: Match Platform Design System

### Context

The couple-facing portal at `/couple/dashboard` looked like a completely separate app with its own layout (sticky header + horizontal tab bar), color scheme, and design patterns. This release redesigns it to match the platform's sidebar + top header layout, design tokens, and interaction patterns.

### Added

- **CoupleSidebar** (`/app/couple/components/CoupleSidebar.tsx`) — Collapsible sidebar matching the admin Sidebar structure. Navigation items: Dashboard, Timeline, Payments, Forms, Inbox, Registry, FAQ. Badge counts for unread inbox messages and pending forms. Mobile drawer with overlay.
- **CoupleTopHeader** (`/app/couple/components/CoupleTopHeader.tsx`) — Top header matching admin TopHeader with mobile menu toggle, theme toggle (light/dark), couple name display, and sign out button.
- **CoupleLayoutClient** (`/app/couple/components/CoupleLayoutClient.tsx`) — Client-side layout wrapper with ThemeProvider, mesh gradient background (matching admin layout), and public/authenticated page routing.

### Changed

- **Couple layout** (`/app/couple/layout.tsx`) — Rewritten to use CoupleLayoutClient wrapper while preserving server-side metadata exports.
- **Couple dashboard** (`/app/couple/dashboard/page.tsx`) — Complete rewrite:
  - Replaced horizontal tab bar with sidebar-driven section navigation
  - Applied platform card styles: `bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700`
  - Switched primary color from slate to indigo to match platform buttons
  - Added responsive sidebar margin transitions matching admin layout
  - Improved all dark mode token usage to slate palette
  - Budget progress bar now color-coded (indigo → amber → red based on spend percentage)
- **Payments + Contract merged** — Combined into single "Payments" section showing contract summary, payment overview, contract sections, and payment schedule in one view.
- **Messages + Updates merged** — Combined into "Inbox" section with pill-toggle sub-tabs for Messages and Updates.
- **UX copy improvements** — Rewrote empty states, error messages, button labels, and section headings for clarity and warmth (e.g., "Needs your input" instead of "Pending", "Your big day is X days away" instead of "Counting Down", more helpful empty state guidance).

### Removed

- Standalone sticky header with couple name + logout button (replaced by sidebar + top header)
- Horizontal scrolling tab bar (replaced by sidebar navigation)
- Meetings tab (meetings are now planner tasks with "Couple Meeting" category)
- `MeetingsTab` component and `CoupleMeeting` interface

### Technical Notes

- Layout uses same ThemeProvider, mesh gradient, and responsive sidebar pattern as admin layout
- Section switching via state (Option A from spec) to avoid new routes
- All existing API endpoints preserved — no backend changes required
- Zero TypeScript compilation errors introduced

---

## [2.26.0] - 2026-03-23 — Couple Portal Consolidation: Integrate into Existing Platform Pages

### Context

The couple portal (planner side) was built as a standalone page with its own tabs and design language. This release walks that back — every couple portal feature is now integrated into the existing platform pages where it belongs, eliminating duplicate UI and keeping the planner workflow in one place per domain.

### Changed

- **Program & Couple Notes → Weddings page** — Added "Program" (indigo) and "Notes" (amber) popup modal buttons on each wedding card. Planners manage run-of-show items and couple notes directly from the Weddings list without navigating away. Full CRUD: add/delete program items per event, status tracking and replies on notes.
- **Messages → Inbox page** — Unified couple messaging into the existing Inbox page (done in prior session).
- **Form Templates → Forms page** — Added "Custom Templates" section to the existing Forms page. Planners can browse saved templates, create forms from them, and delete templates — all inline with the existing forms library using the same glassmorphism card style.
- **Meetings → Calendar task system** — Instead of a separate meetings module, added `meeting` ("Couple Meeting") as a task category in the existing Calendar task system. Planners schedule meetings using the same task form that already supports start/end times, recurring, Google Calendar sync, and reminders. Removed the standalone Meetings button and modal from the Calendar page (~250 lines deleted).
- **Task modal compact layout** — Rewrote the Create/Edit Task modal to fit all fields on screen without scrolling: 4-column row for Wedding/Category/Priority/Color, inline date+time rows, merged Description and Notes into a single textarea.
- **Dialog component fix** — Removed hardcoded `max-w-lg` from the shared Dialog component so callers can specify their own max-width. Added `max-h-[90vh] overflow-y-auto` as base defaults.

### Removed

- Standalone "Meetings" button and modal from Calendar page (replaced by task category)
- `MeetingsModalContent` component and `Meeting` interface from Calendar page (~250 lines)
- `meetingModalOpen` state from Calendar page

### Technical Notes

- `calendarApi.ts`: Added `'meeting'` to `TaskCategory` union and `CATEGORY_LABELS` map
- `TaskModal.tsx`: Added `'meeting'` to `CATEGORIES` array, widened time inputs, compact form layout
- `planner/calendar/page.tsx`: Removed meetings modal, button, state, and `MeetingsModalContent` function
- `components/ui/Dialog.tsx`: Removed hardcoded `max-w-lg`, added viewport-constrained scrolling
- `admin/forms/page.tsx`: Added custom templates state, fetch/create/delete handlers, and UI section
- Backend category field is a free string — no backend changes needed for meeting category

---

## [2.25.0] - 2026-03-23 — Full-Stack Alignment Audit: P2/P3 Remediation

### Context

Resolved 27 misalignment items (15 P2, 12 P3) identified in the full-stack alignment audit covering 69 API files, 23 models, 64 services, and 271 frontend files. A post-implementation code review caught and fixed 2 additional critical bugs before merge.

### Added

- **Rate Limiting** (`app/utils/rate_limiter.py`) — In-memory sliding window rate limiter with per-IP tracking, DoS protection (auto-eviction at 10k IPs), and pre-configured limiters: `public_read_limiter` (60/min), `public_search_limiter` (30/min), `public_slug_limiter` (100/min). Applied to 3 blog endpoints and 5 knowledge base endpoints.
- **Cursor-Based Pagination** (`app/utils/cursor_pagination.py`) — Base64-encoded cursors with `_id` + sort field for stable MongoDB pagination. Generic `CursorPage[T]` response model, `limit + 1` fetch pattern (no extra count query), `validated_cursor()` and `validated_cursor_limit()` FastAPI dependencies.
- **Error Boundaries** (~20 `error.tsx` files) — Next.js App Router error boundaries for all admin pages: ads, billing, budget, couple-portal, dashboard, forms, guests, inbox, metrics, notifications, packages, planner/billing, planner/calendar, platform, saas, seating, support, users, vendors, weddings.
- **Knowledge Base Feedback Summary** — `GET /admin/kb/feedback-summary` endpoint with MongoDB aggregation pipeline returning global stats, top 5 most/least helpful articles, and 20 most recent feedback comments.
- **Admin RSVP Contact Fields** — Optional `phone` and `email` on `AdminRSVPUpdateRequest`; guest contact info updated before RSVP creation (non-None only, prevents accidental blanking).

### Changed

- **Vendor Assignment Status Enum** (`app/models/vendor.py`) — Formalized `VendorAssignmentStatus(str, Enum)` with 6 states: `inquiry → quoted → contracted → confirmed → completed → cancelled`. Added state machine docstring, changed field type from `str` to enum, added validation in `vendor_service.py` and regex pattern on the API query parameter.
- **Payment Milestone Status Docs** — Added comprehensive state machine docstring to `PaymentMilestoneStatus` enum.
- **Budget TypeScript Cleanup** (`app/types/budget.ts`, budget pages, `PaymentHistoryPanel.tsx`) — Removed `_id: string` from `BudgetCategory`, `VendorQuote`, and `BudgetTemplate` interfaces. Eliminated all `category.id || category._id` fallback patterns across budget page, templates page, and payment history panel.
- **AdminContext Token Refresh** (`app/contexts/AdminContext.tsx`) — Added immediate post-login refresh for tokens with <10 min TTL. Introduced `activeToken` tracking so profile and team permissions fetches always use the freshest token.
- **SMS Config Logging** (`app/core/sms_config.py`) — Module-level docstring documenting all env vars for Twilio/Telnyx. Unknown provider values now log a warning with fallback behavior.
- **Trial Expiration Emails** (`app/services/trial_expiration_service.py`) — Retry logic (max 2 retries, 2s/4s exponential backoff), email validation, early return for unconfigured service, fixed subject line pluralization ("1 Day" vs "X Days"), individual failures no longer break the loop.
- **Offset Pagination Deprecation** (`app/utils/query_validation.py`) — Deprecation docstring on `validated_skip()` pointing to `cursor_pagination` module.
- **Planner Billing Migration Prep** (`app/admin/planner/billing/page.tsx`) — Destructured `apiRequest` from `useAdmin()` with TODO for migrating raw `fetch()` calls.

### Fixed

- **Stale Token in Profile Fetch** (Critical) — `AdminContext.tsx` profile fetch used original `access_token` instead of potentially refreshed token after post-login refresh, causing intermittent auth failures on login. Fixed with `activeToken` variable.
- **Cursor Pagination `$or` Overwrite** (Critical) — `query_filter.update(cursor_query)` silently dropped existing `$or` clauses. Changed to `{"$and": [query_filter, cursor_query]}` for safe filter merging.

### Code Review Ratings

| Dimension       | Rating | Notes                                           |
|-----------------|--------|-------------------------------------------------|
| Security        | A-     | Rate limiting in place; naming concern (info)   |
| Performance     | A      | Cursor pagination, no extra count queries        |
| Correctness     | A      | 2 critical bugs found and fixed during review    |
| Maintainability | A-     | Enums, deprecation notices, error boundaries     |

---

## [2.24.0] - 2026-03-23 — Couple Portal Sprint 6: Registry, FAQ, QR Code, Push Notifications & PWA

### Context

Sprint 6 builds out five features that were previously classified as P2 but had all backend infrastructure already in place. Registry and FAQ are full CRUD (couple and planner share the same data on the wedding model). QR code reuses the existing `generate_qr_code()` from guest export. Push notifications add couple-auth endpoints on top of the existing `WebPushService`. PWA adds manifest and service worker caching. SEO audit requirements (noindex, semantic HTML, ARIA labels, meta tags) baked into implementation.

### Added

- **Registry CRUD (Couple Portal)**
  - `GET /couple/portal/registries` — List registries from wedding model
  - `POST /couple/portal/registries` — Add registry item (syncs to wedding model)
  - `PUT /couple/portal/registries/{index}` — Update registry item by index
  - `DELETE /couple/portal/registries/{index}` — Delete registry item by index
  - Registry tab in couple dashboard: responsive grid, color-coded buttons, add/edit/delete UI

- **FAQ CRUD (Couple Portal)**
  - `GET /couple/portal/faqs` — List FAQs from wedding model
  - `POST /couple/portal/faqs` — Add FAQ item (syncs to wedding model)
  - `PUT /couple/portal/faqs/{index}` — Update FAQ item by index
  - `DELETE /couple/portal/faqs/{index}` — Delete FAQ item by index
  - FAQ tab in couple dashboard: accordion-style cards, optional external links, add/edit/delete UI

- **QR Code Widget**
  - `GET /couple/portal/qr-code` — Generate QR code PNG for couple portal URL (reuses `guest_export_service.generate_qr_code()`)
  - QR widget on Overview tab: generate + download PNG

- **Push Notifications (Couple-Side)**
  - `POST /couple/portal/push/subscribe` — Couple subscribes to browser push (couple auth)
  - `DELETE /couple/portal/push/unsubscribe` — Couple unsubscribes from push
  - `GET /couple/portal/push/status` — Check subscription status + VAPID key
  - Push notification widget on Overview tab: enable/disable with real-time status

- **PWA Support**
  - `/public/manifest.json` — App manifest (name, icons, start URL, display standalone)
  - Service worker caching: CacheFirst for static assets, NetworkFirst for HTML, StaleWhileRevalidate for images
  - Service worker registration in couple dashboard
  - Couple layout meta tags: `noindex`, `theme-color`, `apple-mobile-web-app` tags, viewport config

### Changed

- Extended `couple_portal.py` imports: `Response`, `guest_export_service`, `web_push_service`, `os`
- Updated couple dashboard `TabType` union: added `'registry' | 'faq'`
- Added `Gift`, `HelpCircle`, `QrCode`, `BellRing`, `Plus`, `Pencil`, `Trash2`, `ExternalLink`, `Download`, `BellOff` to lucide imports
- Updated PRD: reclassified P2-2, P2-3, P2-5, P2-6, P2-7 as "Built (Sprint 6)"

---

## [2.23.0] - 2026-03-22 — Couple Portal Sprint 5: Note Replies & Meeting Scheduling

### Context

Sprint 5 completes all P1 features for the Couple Portal: threaded note replies (P1-6) and recurring meeting scheduling with Google Calendar integration (P1-2).

### Added

- **Threaded Note Replies (P1-6)**
  - `POST /couple-portal/events/{event_index}/notes/{note_id}/reply` — Planner replies to event-level couple notes
  - `POST /couple-portal/events/{event_index}/order-of-events/{item_id}/notes/{note_id}/reply` — Planner replies to item-level couple notes
  - Replies stored with `reply_to` field in `EventNoteModel`, displayed threaded under parent notes
  - Replying auto-marks parent note as "addressed"
  - Planner NotesSection: reply button, inline reply input, threaded reply display with blue accent
  - Couple dashboard: planner replies shown threaded below original notes on both event and item levels

- **Recurring Meeting Scheduling (P1-2)**
  - `POST /couple-portal/meetings` — Planner schedules meetings with Google Calendar sync
  - `GET /couple-portal/meetings` — Planner lists meetings for a wedding
  - `DELETE /couple-portal/meetings/{meeting_id}` — Cancel meeting (removes from Google Calendar)
  - `GET /couple/portal/meetings` — Couple views upcoming meetings
  - Meetings stored as planner tasks with `category="meeting"` — reuses existing `planner_tasks` collection
  - Recurring support: weekly, biweekly, monthly presets with iCal RRULE generation
  - Google Calendar sync via existing `google_calendar_service`
  - Meetings tab in planner management page with scheduling form and meeting list
  - Meetings tab in couple dashboard showing upcoming meetings

### Changed

- `EventNoteModel` — Added `reply_to` field for threading support
- `TaskCategory` enum — Added `MEETING` category
- PRD status updated to "Complete (Sprints 1-5 — all P0 and P1 features built)"

## [2.22.0] - 2026-03-22 — Couple Portal Sprint 4: Archival, Form Templates, Error States, Polish

### Context

Sprint 4 focuses on wedding archival, reusable form templates, comprehensive error state handling for archived/revoked weddings, and mobile responsiveness polish.

### Added

- **Wedding Archival Flow**
  - `POST /couple-portal/archive` — Planner triggers full wedding data snapshot (guests, RSVPs, budget, contracts, forms, updates, messages)
  - `DELETE /couple-portal/archive` — Planner reverses archival, restores couple portal to active state
  - Archive button with confirmation modal in planner management page
  - Couples see read-only archived view with amber banner; write operations (messaging, forms, notes) blocked
  - Reuses existing `archive_wedding_data()` service with messages extension

- **Custom Form Templates**
  - `POST /couple-portal/form-templates` — Save any form as a reusable custom template
  - `GET /couple-portal/form-templates` — List all planner's saved templates
  - `POST /couple-portal/form-templates/create-form` — Create new form from template for a wedding
  - `DELETE /couple-portal/form-templates/{template_id}` — Delete saved template (with confirmation)
  - Form Templates tab in planner management page with template cards, "Use Template" flow, delete

- **Error State Handling**
  - Archived wedding write-blocks on: `POST /couple/portal/messages`, form submission, event notes, item notes
  - Consistent `403 Forbidden` with descriptive messages for archived wedding operations
  - MessagesTab shows disabled state with archive icon when wedding is archived
  - ObjectId validation on all Sprint 4 endpoints — returns `400 Bad Request` for invalid IDs

- **Database Indexes** (`database_indexes.py`)
  - `idx_custom_templates_planner` — Compound index `(planner_email, created_at DESC)` for template listing

### Changed

- **Mobile Responsiveness**
  - Tab bar uses responsive padding (`px-2.5 sm:px-4`) and text size (`text-xs sm:text-sm`) for small screens
  - Messages container uses viewport-relative height with min/max bounds
  - Wedding selector + archive button stack vertically on mobile, row on desktop

- **Planner Management Page**
  - Added "Form Templates" tab to section navigation
  - Archive button renders alongside wedding selector with `onArchived` callback for data refresh
  - Template delete requires confirmation dialog

### Security

- ObjectId format validation on all archive and template endpoints prevents malformed ID exceptions
- Wedding access checks (`check_wedding_access()`) on all planner endpoints
- Archived wedding state checked before every couple write operation
- Template ownership enforced — planners can only access/delete their own templates
- Template saving strips wedding-specific settings to prevent data leakage

---

## [2.21.0] - 2026-03-22 — Couple Portal Sprint 3: Messaging, Password Reset, Email Digests

### Context

Sprint 3 completes the Couple Portal's communication layer with real-time couple↔planner messaging, a full password reset flow for couples, and planner-triggered email digest summaries.

### Added

- **Couple ↔ Planner Messaging**
  - `POST /couple/portal/messages` — Couple sends a message to their planner
  - `GET /couple/portal/messages` — Couple retrieves message history (cursor-based pagination)
  - `GET /couple/portal/messages/unread-count` — Couple unread message count
  - `POST /couple-portal/messages` — Planner sends a message to the couple
  - `GET /couple-portal/messages` — Planner retrieves message history for a wedding
  - `GET /couple-portal/messages/unread-count` — Planner unread message count
  - Chat-style UI on both couple dashboard and planner management page
  - Read receipts (eye icon) for messages read by the other party
  - Real-time unread badge on Messages tab

- **Couple Password Reset Flow**
  - `POST /couple/forgot-password` — Request password reset email (anti-enumeration: consistent response)
  - `GET /couple/reset-password/validate/{token}` — Validate reset token without consuming it
  - `POST /couple/reset-password` — Atomic token consumption + password update via `find_one_and_update`
  - Forgot password page (`app/couple/forgot-password/page.tsx`)
  - Reset password page (`app/couple/reset-password/page.tsx`) with token validation, masked email display
  - "Forgot your password?" link added to couple login page
  - Branded HTML email template for reset link (matches invite email style)

- **Email Notification Digest**
  - `POST /couple-portal/send-digest` — Planner triggers digest email for a wedding's couple
  - `generate_couple_digest()` — Aggregates unread messages, new updates, upcoming payments (14 days), pending forms
  - `send_couple_digest_email()` — Branded HTML email with digest sections
  - "Send Digest Email" button in planner messaging section

- **Planner Notification Integration**
  - New notification types: `couple_message`, `couple_note` registered in `NotificationType` Literal
  - All couple actions notify planners via `planner_notification_service.create_notification()` (SSE + web push)
  - Existing `/planner/activity-notifications` API filters by type — no duplicate endpoints needed

- **Database Indexes** (`database_indexes.py`)
  - `idx_couple_reset_token` — Sparse index on `couple_users.password_reset_token`
  - `idx_messages_wedding_id` — Compound index `(wedding_id, _id DESC)` for message feed
  - `idx_messages_unread_couple` / `idx_messages_unread_planner` — Targeted indexes for unread counts

### Security

- Password reset uses atomic `find_one_and_update` to prevent token reuse race conditions
- Anti-enumeration on forgot-password: always returns identical response regardless of account existence
- Reset tokens: 32 hex chars, 1-hour expiry, invalidated on use
- Wedding existence validation before message insert
- `check_wedding_access()` enforced on planner unread count endpoint
- Read-mark operations execute before message fetch to prevent race conditions

---

## [2.20.0] - 2026-03-22 — Couple Portal Sprint 2: Planner Management + Order of Events CRUD + Contract Review

### Context

Sprint 2 builds on the Phase 1 foundation by adding the planner-side management page, full CRUD for the order of events / run of show, collaborative notes between couples and planners, contract review in the couple portal, and couple access management.

### Added

- **Planner Management Page** (`app/admin/couple-portal/page.tsx`)
  - Three-tab layout: Couples, Program / Run of Show, Couple Notes
  - Couples tab: view all couple accounts, invite new couples, resend invitations, revoke/restore access
  - Program tab: add/edit/delete order-of-events items per ceremony with time, duration, description
  - Notes tab: consolidated view of all couple notes with pending/seen/addressed status management

- **Order of Events CRUD API** (planner side)
  - `POST /couple-portal/events/{event_index}/order-of-events` — Add program item
  - `PUT /couple-portal/events/{event_index}/order-of-events/{item_id}` — Update item
  - `PUT /couple-portal/events/{event_index}/order-of-events/reorder` — Reorder items (drag-and-drop)
  - `DELETE /couple-portal/events/{event_index}/order-of-events/{item_id}` — Remove item
  - Optimistic concurrency control via `updated_at` version check prevents data loss from concurrent edits

- **Collaborative Notes API**
  - `POST /couple/portal/events/{event_index}/notes` — Couple adds event-level note
  - `POST /couple/portal/events/{event_index}/order-of-events/{item_id}/notes` — Couple adds item-level note
  - `PATCH /couple-portal/events/{event_index}/notes/{note_id}` — Planner updates note status
  - `PATCH /couple-portal/events/{event_index}/order-of-events/{item_id}/notes/{note_id}` — Planner updates item note status
  - Automatic planner notification on new couple notes (via `planner_notifications` collection)

- **Contract Review in Couple Portal**
  - `GET /couple/portal/contracts` — Dedicated endpoint returning contract sections, payment schedule, and status
  - `get_contract_for_couple()` — New service method in `CouplePortalService` (single DB query, no N+1)
  - Contract tab in couple dashboard: package name, status timeline, sections (terms/scope), payment summary and schedule

- **Couple Access Management**
  - `PATCH /couple-portal/couples/{couple_id}/revoke` — Revoke couple's portal access
  - `PATCH /couple-portal/couples/{couple_id}/restore` — Restore previously revoked access

- **Enhanced Couple Dashboard**
  - Timeline tab now shows expandable order of events with times, durations, and descriptions
  - Inline note submission: couples can add notes to specific program items or general event notes
  - Note status badges (pending/seen/addressed) visible to couples
  - New Contract tab with full contract details, sections, and payment schedule

### Security

- All planner endpoints use `require_team_or_planner` + `enforce_team_permission('manage_contracts')` + `check_wedding_access()`
- All couple endpoints use `require_couple_auth` dependency
- Optimistic concurrency control on order-of-events writes (409 Conflict on stale data)

---

## [2.19.0] - 2026-03-22 — Couple Portal (Phase 1) + Order of Events with Collaborative Notes

### Context

The platform had a basic token-based payment portal for couples (`/portal/[token]`) but no way for couples to log in, view wedding updates, fill out forms, or communicate with their planner. Planners also had no way to share a detailed order of events / run of show for each ceremony, and couples had no mechanism to leave feedback on program items.

### Added

- **Couple Authentication System**
  - `app/api/couple_auth.py` — Public auth endpoints: password setup from magic link, login (24-hour JWT), invite token verification, profile retrieval
  - `app/api/couple_invite.py` — Planner-side invitation management: invite couple via email, resend invite, list all couples (requires planner auth with `manage_contracts` permission)
  - `app/couple/login/page.tsx` — Couple login page with navy/gold wedding theme
  - `app/couple/setup/page.tsx` — Magic link password setup page with token verification
  - Couples stored in separate `couple_users` MongoDB collection (not the main `users` collection) for clean role separation

- **Couple Portal Dashboard**
  - `app/couple/dashboard/page.tsx` — Main dashboard with 5 tabs: Overview, Timeline, Payments, Forms, Updates
  - `app/couple/layout.tsx` — Root layout with gradient background
  - `app/couple/forms/[formId]/page.tsx` — Dynamic form filling page (text, email, phone, number, date, textarea, select, checkbox)
  - Overview tab: stat cards, budget progress, venue/planner info, upcoming events
  - Timeline tab: event cards with date, venue, attire, time details
  - Payments tab: package summary, individual payment items with status badges
  - Forms tab: shared forms list with pending/submitted status
  - Updates tab: planner update feed with milestone cards (gold/rose gradient)

- **Couple Portal Service Layer**
  - `app/services/couple_portal_service.py` — Aggregates data from weddings, guests, budgets, contracts, forms, and updates collections. Exposes only safe data (guest totals, budget totals — no individual records). Includes `archive_wedding_data()` for wedding archival.

- **Couple Portal API**
  - `app/api/couple_portal.py` — Dashboard data, events, paginated updates, form submission with planner notification, form details with existing responses, planner update creation

- **Order of Events / Run of Show**
  - `OrderOfEventsItemModel` — New Pydantic model for individual program steps (title, description, time, duration, display order, notes)
  - `EventNoteModel` — New Pydantic model for collaborative notes (author_role, text, status: pending/seen/addressed)
  - `EventModel.order_of_events` — Detailed program steps within each ceremony (e.g., Grand Entrance → First Dance → Cake Cutting → Toasts)
  - `EventModel.event_notes` — General event-level notes from planner or couple

- **New MongoDB Collections**
  - `couple_users` — Couple accounts with invite tokens, password hashes, wedding references
  - `couple_updates` — Planner-to-couple update feed with milestone support
  - `archived_weddings` — Complete wedding data snapshots for analytics after wedding completion

- **Planner UI**
  - Added "Couple Portal" nav item to `app/admin/components/Sidebar.tsx` with HeartHandshake icon

- **Documentation**
  - `docs/plans/couple/FEATURE_SCOPE_couple_portal.md` — Comprehensive feature spec (revised from original read-only scope)
  - `docs/plans/couple/portal-mockups.html` — Visual mockups for all 8 portal screens

### Changed

- **`app/models/wedding.py`** — Extended `EventModel` with two new optional fields: `order_of_events` (List[OrderOfEventsItemModel], defaults to []) and `event_notes` (List[EventNoteModel], defaults to []). Added `EventNoteModel` and `OrderOfEventsItemModel` classes. Fully backward-compatible — existing events without these fields deserialize with empty lists.

- **`app/types/wedding.ts`** — Added TypeScript interfaces `EventNote`, `OrderOfEventsItem` and extended `WeddingEvent` with optional `order_of_events` and `event_notes` fields.

- **`app/main.py`** — Registered three new routers: `couple_auth_router` (public), `couple_portal_router` (public), `couple_invite_router` (admin prefix).

### Backward Compatibility

- All new fields on `EventModel` use `default_factory=list`, so existing MongoDB documents load without any migration
- All existing consumers (weddings admin, guests page, RSVP form, landing page, couple dashboard) only access `type`, `date`, and `details` — unaffected by the new fields
- TypeScript types use optional (`?`) for new fields — no frontend compilation impact
- Verified with round-trip serialization tests against old documents, minimal documents, and new documents with full order-of-events data

## [2.18.0] - 2026-03-22 — Customer Reviews Configuration for SaaS Management

### Context

The SaaS landing page displayed customer testimonials, but they were hardcoded in `app/page.tsx` with a `// TODO: Fetch testimonials from API when endpoint exists` comment. The admin SaaS management page had no way to manage these reviews — the original "SaaS Content" tab that would have covered this was removed for performance reasons, leaving a gap between what appeared on the landing page and what root admins could configure.

### Added

- **`app/api/testimonials.py`** — Dedicated testimonials CRUD API with six endpoints:
  - `GET /saas/public/testimonials` — Public (no auth), returns active testimonials sorted by display order. Auto-seeds the collection with four default testimonials if empty.
  - `GET /saas/testimonials` — Admin listing of all testimonials (active + hidden), ROOT_ADMIN only.
  - `POST /saas/testimonials` — Create a new testimonial with name, company, role, quote, display order, and active flag.
  - `PUT /saas/testimonials/{id}` — Partial update of any testimonial fields.
  - `DELETE /saas/testimonials/{id}` — Permanent deletion.
  - `PUT /saas/testimonials/{id}/toggle` — Toggle active/inactive status.

- **Customer Reviews tab in `app/admin/saas/page.tsx`** — Fourth tab on the SaaS management page (alongside Overview, Subscription Plans, and Ad Platform):
  - Card grid displaying each testimonial with name, role, company, quote preview, active/hidden badge, display order, and last-updated date.
  - Inline Edit, Hide/Show, and Delete actions per card.
  - Modal form for creating and editing testimonials with fields for name, role, company, quote text, display order, and active checkbox.
  - Empty state with call-to-action when no testimonials exist.

### Changed

- **`app/page.tsx`** — Landing page now fetches testimonials from `GET /saas/public/testimonials` on mount via `useEffect`. Falls back to four hardcoded testimonials if the API is unreachable. Replaced two generic testimonials with four feature-rich testimonials covering the full platform (guest management, seating, budgets, contracts, AI pricing, vendor coordination, gallery, reminders, calendar sync, forms, wedding config, and knowledge base).

- **`app/api/saas_config.py`** — Updated `_get_default_saas_config()` testimonials array to match the new four-testimonial set and added a sync comment pointing to `testimonials.py`.

- **`app/main.py`** — Registered `testimonials_router` at `/saas` prefix.

### Migration Notes

- The `testimonials` MongoDB collection is auto-seeded on first read if empty — no manual migration required.
- Existing `saas_config.testimonials` data (in the monolithic config blob) is no longer the source of truth for the landing page; the dedicated `testimonials` collection is authoritative.
- The four default testimonials reference real platform features by name (seating orchestrator, contract canvas, forms canvas, etc.) to serve as both social proof and feature discovery.

## [2.17.0] - 2026-03-20 — Shared Pagination System for Admin Dashboard

### Context

The admin dashboard had ~25 pages with tables that either had no pagination at all (loading all records into the DOM), or had broken/inconsistent pagination implementations (some cursor-based, some client-side-only). Large datasets like platform errors (1000+ records) and guest lists were loading everything at once, causing slow renders and poor UX. The platform errors page was additionally stuck at 2 pages because the cursor lookup only searched the `errors` collection but not the `audit_logs` collection.

### Added

- **`app/admin/components/ui/glass/GlassPagination.tsx`** — New shared pagination component with two variants:
  - `full`: Shows page numbers, first/last buttons, per-page dropdown, and "Showing X–Y of Z" summary
  - `compact`: Minimal "Page X of Y" display with prev/next buttons for use as a top-of-table nav
  - Defensive defaults on all numeric props (`totalItems = 0`, `currentPage = 1`, etc.) so the component never crashes on `undefined` values
  - Optional `onPageChange` (called with `?.()` guard) so it can render safely even when callbacks aren't provided
  - Glass-morphism styling consistent with the existing design system

- **`app/admin/hooks/usePagination.ts`** — Shared pagination state hook providing:
  - `currentPage`, `itemsPerPage`, `totalItems`, `totalPages` (computed)
  - `setPage()`, `setItemsPerPage()`, `setTotalItems()`, `updateFromResponse()`
  - `queryParams` (ready-to-use `{ page, limit }` object) and `skip` (for skip/limit APIs)
  - Configurable `initialPage` and `initialItemsPerPage` (defaults to 50)

### Changed

- **`app/api/admin_platform_metrics.py`** — Replaced cursor-based pagination on `GET /errors/recent` with page-based (`page`, `limit` query params). Fixed `_normalize_timestamp()` which was producing `+00:00Z` (double timezone suffix) that JavaScript's `new Date()` rejected as Invalid Date. Backend now correctly splits pagination across both `errors` and `audit_logs` collections based on skip offset.

- **`app/admin/platform/page.tsx`** — Rewrote errors tab pagination from cursor-based state (`cursorHistory`, `nextCursor`, `prevCursor`, etc.) to `usePagination` hook + `GlassPagination` component. Changed table to `table-fixed` layout with explicit column widths to prevent horizontal overflow. Shortened column labels ("Acknowledged" → "Ack'd").

- **`app/services/guest_service.py`** + **`app/api/guest.py`** — Added `page`/`limit` params to `GET /guests`, replaced `to_list(length=None)` with skip/limit queries.

- **`app/api/user_management.py`** + **`app/services/user_management_service.py`** — Added `page`, `limit`, `search` pagination to user listing endpoints.

- **`app/api/wedding.py`** + **`app/services/wedding_service.py`** — Added `page`, `limit`, `search` pagination to wedding listing endpoints.

- **`app/admin/guests/page.tsx`** — Server-side pagination with compact top nav + full bottom pagination.

- **`app/admin/users/page.tsx`** — Server-side pagination with search, filter-reset-to-page-1 on input change.

- **`app/admin/vendors/page.tsx`** — Server-side pagination integrated with existing search/category/preferred filters.

- **`app/admin/weddings/page.tsx`** — Server-side pagination. Refactored client-side filtering from `useCallback` + `useEffect` (which caused infinite re-render loops) to a clean `useMemo` pattern with a separate filter-reset effect.

- **`app/admin/support/page.tsx`** — Server-side pagination with inline page-reset in filter event handlers.

- **`app/admin/planner/team/page.tsx`** — Server-side pagination with compact top + full bottom nav. Fixed incorrect `goToPage()` method calls (doesn't exist on the hook) to `setPage()`.

- **`app/admin/planner/activity-log/page.tsx`** — Server-side pagination with compact top + full bottom nav.

- **`app/admin/planner/billing/page.tsx`** — Client-side pagination for invoice history using `usePagination` with `Array.slice()`.

### Fixed

- **Infinite re-render loops on all paginated pages** — Every page that used `pagination` (the whole object) as a `useCallback` dependency caused infinite loops because `usePagination()` returns a new object reference on every render. Fixed by destructuring to specific primitive values (`pagination.currentPage`, `pagination.itemsPerPage`) in all dependency arrays.

- **Secondary infinite loop from `updateFromResponse`** — All pages were calling `pagination.updateFromResponse({ total, page })` which set both `totalItems` AND `currentPage`. Setting `totalItems` changed `totalPages`, which caused `setPage` (useCallback depending on `totalPages`) to be recreated, triggering filter-reset effects that called `setPage(1)`, changing `currentPage`, which triggered fetch callbacks. Replaced all `updateFromResponse()` calls with `setTotalItems()` across 7 pages.

- **Weddings page filter cascade loop** — `filterWeddings` was a `useCallback` depending on `allWeddings`. When fetch completed → `allWeddings` updated → `filterWeddings` recreated → effect fired → `pagination.setPage(1)` → `currentPage` changed → `fetchWeddings` triggered again. Fixed by converting to `useMemo` (pure computation, no side effects) with a separate `useEffect` that only resets page on actual filter input changes.

- **GlassPagination crash on undefined props** — Three planner pages passed `pagination={pagination}` as a single object prop instead of individual props. Since `GlassPaginationProps` has no `pagination` prop, all numeric values were `undefined`, causing `.toLocaleString()` crash. Fixed all usages to pass individual props AND added defensive defaults in the component itself.

- **Platform errors stuck at 2 pages** — Cursor-based pagination only searched the `errors` collection for the cursor document. When results spanned both `errors` and `audit_logs`, the cursor was never found and pagination broke. Replaced with page-based pagination.

- **Blank timestamps on platform errors** — `_normalize_timestamp()` appended `Z` to timestamps that already had `+00:00`, producing `+00:00Z` which JavaScript rejects. Fixed to replace `+00:00` with `Z` instead of appending.

- **Named vs default export mismatch** — Three planner pages used `import GlassPagination from ...` (default import) but the component uses `export function GlassPagination` (named export). Fixed all to `import { GlassPagination } from ...`.

### Migration Notes

- All paginated pages now default to 50 items per page with a per-page dropdown offering 10/25/50/100 options
- The `usePagination` hook's `updateFromResponse()` method still exists but is no longer called by any page — all pages use `setTotalItems()` instead to avoid re-render loops
- Backend pagination endpoints all follow the `?page=1&limit=50` pattern; the `usePagination` hook also exposes `skip` for APIs that use skip/limit
- No database migrations required — all changes are frontend pagination state + backend query parameter handling

## [2.16.0] - 2026-03-19 — Merge Business Analytics into SaaS Management + Fix Plan Breakdown Bugs

### Context

The admin dashboard had two separate pages for related data: "Business Analytics" (`/admin/metrics`) showed detailed platform metrics (user growth, subscription revenue, operational load), while "SaaS Management" (`/admin/saas`) had a basic Overview tab with just four metric cards and a plan distribution list. This split was confusing — the Business Analytics page had all the real data, but the SaaS Management Overview (the natural first stop) was too sparse to be useful.

Additionally, the Business Analytics Plan Breakdown table had three data bugs: a missing third plan, hardcoded "N/A" for user counts, and a missing status in the expected list.

### Fixed

- **Missing plan in Plan Breakdown** — `_calculate_revenue_summary()` in `platform_metrics_service.py` only showed plans that had active/trial subscriptions. Plans with zero subscriptions (e.g. a newly created plan) were silently omitted. Added a second query that fetches all active plans from `subscription_plans` and backfills any missing ones with zeroed-out values. Applied to both the main aggregation pipeline and the fallback path.
- **Hardcoded "N/A" for Active Users / Trial Users** — The frontend Plan Breakdown table had literal `<td>N/A</td>` instead of real data. The backend aggregation pipeline never counted users per plan. Added `active_users` and `trial_users` conditional counters to the `$group` stage, and updated the frontend to render `formatNumber(plan.active_users ?? 0)`.
- **Missing `pending_checkout` status** — The `expected_statuses` list in `_compile_subscription_metrics()` didn't include `pending_checkout`, which exists in the database. Added it so the status always appears with a default of 0.

### Changed

- **`app/admin/saas/page.tsx`** — Replaced the basic Overview tab with the full Business Analytics dashboard:
  - Added all Platform Metrics types (`PlatformMetricsResponse`, `TimeframeKey`, etc.) and helper functions (`formatCurrency`, `formatNumber`, `formatPercentage`)
  - New state: `metrics`, `metricsTimeframe`, `metricsLoading` (replaces old `analyticsOverview` and `planBreakdown`)
  - Replaced two API calls (`/saas/analytics/overview` + `/saas/analytics/revenue`) with a single `/saas/analytics/platform?timeframe=` call
  - Added `fetchMetricsOnly()` for lightweight timeframe changes without re-fetching plans/planners
  - Added `useMemo` hooks for `roleBreakdown` and `statusBreakdown`
  - Overview tab now shows: User Growth (4 cards), Subscription & Revenue (3 cards + Plan Breakdown table), Operational Load (Weddings, Forms, Communications), and Recent Signups (expanded from 3 to 5 entries with active/inactive badges)
  - Cleaned up unused `'planners'` from the tab type union
  - Updated page header: "SAAS Admin Dashboard" → "SaaS Management" with description "Platform analytics, subscription plans, and configuration"

- **`app/admin/metrics/page.tsx`** — Converted from the full Business Analytics page to a lightweight redirect (`router.replace('/admin/saas')`) so bookmarks, browser history, and stale links still work.

- **`app/admin/components/Sidebar.tsx`** — Removed the "Business Analytics" nav item (`/admin/metrics`) from the admin sidebar. Removed unused `TrendingUp` import.

- **`app/admin/components/AdminHeader.tsx`** — Consolidated duplicate header links: removed "Platform Management" and "Platform Metrics" entries, replaced with a single "SaaS Management" link to `/admin/saas`.

- **`app/admin/page.tsx`** — Updated the "Analytics" quick action card on the root admin dashboard to link to `/admin/saas` instead of `/admin/metrics`.

- **`app/services/platform_metrics_service.py`** — Backend fixes described in the Fixed section above. Both `_calculate_revenue_summary()` (main pipeline) and `_revenue_fallback()` now return `active_users` and `trial_users` per plan and backfill all active plans.

### Migration Notes

- `/admin/metrics` now redirects to `/admin/saas` — no dead links
- The `/admin/support` page's API call to `/admin/metrics/dashboard` is a backend API endpoint (not a frontend route) and is unaffected
- The Subscription Plans and Ad Platform tabs in SaaS Management are untouched
- All backend API endpoints remain unchanged — no Python route changes needed for the frontend migration

## [2.15.0] - 2026-03-19 — Advertising Campaign Platform Phase 3: Planner Interaction Flows

### Context

Phase 3 of the advertising platform rebuild. Phases 1-2 built the data models, vendor campaign service, admin moderation service, campaign rollup service, and all associated API routes. Phase 3 implements the two planner-facing interaction flows: "Add to Directory" and "Request Quote" — how planners engage with sponsored vendor cards in the rail.

The old architecture required a planner to manually find and add vendors. In the new campaign platform, vendors advertise independently, and planners interact with sponsored cards that appear contextually. These interactions create attribution trails (ad_leads, ad_events) and feed the campaign analytics pipeline.

### Added

- **`app/services/planner_ad_interaction_service.py`** — Planner ad interaction service
  - **Add to Directory flow** (roadmap 3.3): copies vendor info from active campaign into planner's `vendor_profiles` collection, tagged with `source: 'sponsored_ad'` and `source_campaign_id` for attribution. Creates `ad_lead` (type: `add_to_directory`, status: `converted`) and `ad_event` (type: `vendor_added_to_directory`). Increments campaign `lead_count` + `conversion_count`. Returns 409 if duplicate.
  - **Request Quote flow** (roadmap 3.4): creates `ad_lead` (type: `quote_request`, status: `pending`) with message and optional `wedding_context` (date, location, guest_count, venue, budget_range). Sends branded HTML email to vendor via Resend email service with reply-to set to planner's email. Auto-adds vendor to directory if not already present. Gracefully handles email service failures.
  - **Sponsored cards serving** (`get_sponsored_cards`): returns active campaigns enriched with primary creative, filtered to exclude vendors the planner already added, deduplicated by vendor_id, sorted by quality_score.
  - **Directory status check**: quick lookup for frontend button state (Add to Directory vs. Already Added).

- **`app/api/planner_ad_interactions.py`** — Planner ad interaction API router (4 routes at `/planner/ads/*`)
  - `GET /sponsored-cards` — Get contextual sponsored vendor cards for the planner rail. Supports location, categories (comma-separated), and limit (1-10) query params.
  - `POST /add-to-directory` (201) — Add vendor from campaign to planner's directory. Body: `{campaign_id, click_id?}`.
  - `POST /request-quote` (201) — Send quote request to vendor. Body: `{campaign_id, message, wedding_id?, wedding_context?, click_id?, auto_add_to_directory?}`. Message required (1-2000 chars).
  - `GET /directory-status` — Check if vendor already in planner's directory. Query: `campaign_id`.
  - Auth: `require_planner_or_admin` dependency — allows `is_wedding_planner` or root admin.
  - Request/response models: `AddToDirectoryRequest`, `RequestQuoteRequest`, `WeddingContext` (Pydantic).

### Changed

- **`app/main.py`** — Registered `planner_ad_interactions_router` (Planner Ad Interactions) between admin campaigns and vendor public routers.

### Architecture Notes

- Planner interaction flows operate on the NEW campaign-centric platform (`ad_campaigns`), NOT the old `sponsored_vendors` system
- Attribution chain: planner sees sponsored card → clicks Add/Quote → `ad_event` + `ad_lead` created with `campaign_id` → campaign counters incremented → appears in vendor portal leads → appears in campaign rollup stats
- VendorProfile entries created from campaigns are tagged with `source: 'sponsored_ad'`, `source_campaign_id`, `source_vendor_id`, `source_creative_id` for full attribution
- Email service is optional (injected via constructor); if unavailable, quote requests still succeed and appear in vendor portal leads
- Duplicate detection: planner cannot add the same campaign's vendor twice (keyed on `created_by` + `source_campaign_id`)

### Tests Added

- `tests/backend/test_planner_ad_interaction_service.py` — 33 async tests covering add-to-directory (11), request-quote (13), sponsored cards (6), directory status (3)
- `tests/backend/test_planner_ad_interactions_api.py` — 44 tests covering all 4 routes, auth boundaries, request validation, service integration, error handling

## [2.14.0] - 2026-03-19 — Advertising Campaign Platform Phase 2: Vendor & Admin Backend

### Context

This is Phase 2 of the advertising platform rebuild. The old architecture was keyed on `vendor_profile_id` from the planner vendor directory — external vendors could not advertise without a planner adding them first. The rebuild centers everything on `ad_campaigns` with independent vendor identity (`role: advertising_vendor`).

Phase 1 (v2.13.1) laid the data model foundation. Phase 2 builds the full service layer and API surface for both vendor self-service and root admin moderation.

### Added

- **`app/services/admin_campaign_service.py`** — Root admin campaign operations service
  - Review queue: FIFO by `submitted_at` with primary creative inlined for review card display
  - Review counts by status for dashboard widgets (pending_review, active, paused, rejected, draft, completed)
  - Campaign review actions: approve (auto-approves all pending creatives), reject, request-changes (returns to draft with notes)
  - Creative review: separate queue, approve, reject with notes
  - Campaign monitoring: list all campaigns across vendors, admin pause (policy concerns), admin deactivate (emergency kill from any non-terminal status)
  - Revenue/engagement dashboard: aggregates impressions, clicks, leads, unique planners from `ad_events` (free tier = $0 spend)
  - Planner feedback: surfaces hidden vendors, suppressed categories, reduced frequency requests
  - Fraud signals: list and update investigation status from `ad_fraud_signals` (7-day TTL)
  - Vendor account management: list `advertising_vendor` accounts
  - Platform config: get/update advertising feature flags

- **`app/api/vendor_campaigns.py`** — Vendor portal API router (14 routes at `/portal/ads/*`)
  - Campaign CRUD: `POST /campaigns`, `GET /campaigns`, `GET /campaigns/{id}`, `PUT /campaigns/{id}`, `DELETE /campaigns/{id}` (draft only)
  - Lifecycle: `POST /campaigns/{id}/submit` (validates readiness), `POST /campaigns/{id}/pause`
  - Stats: `GET /campaigns/{id}/stats` (lifetime totals + daily time series from `campaign_day_stats`)
  - Creatives: `POST /campaigns/{id}/creatives`, `GET /campaigns/{id}/creatives`, `PUT /creatives/{id}`, `POST /campaigns/{id}/creatives/{id}/set-primary`
  - Leads: `GET /leads` (all leads across vendor's campaigns)
  - Billing: `GET /billing` (placeholder, free tier)
  - Auth: `require_advertising_vendor` dependency — allows `is_advertising_vendor` or root admin

- **`app/api/admin_campaigns.py`** — Admin campaign API router (18 routes at `/admin/ads/campaigns/*`)
  - Review: `GET /review`, `GET /review/counts`, `PUT /{id}/approve`, `PUT /{id}/reject`, `PUT /{id}/request-changes`
  - Creative review: `GET /review/creatives`, `PUT /review/creatives/{id}/approve`, `PUT /review/creatives/{id}/reject`
  - Monitor: `GET /` (all campaigns), `PUT /{id}/pause`, `PUT /{id}/deactivate`
  - Dashboard: `GET /revenue`, `GET /feedback`, `GET /fraud-signals`, `PUT /fraud-signals/{id}`
  - Management: `GET /vendors`, `GET /config`, `PUT /config`
  - Auth: `require_root_admin` on all endpoints

- **`app/services/campaign_rollup_service.py`** — Campaign-centric daily rollup service
  - `campaign_day_stats` rollup: groups by `campaign_id` (not `sponsored_vendor_id`), includes event counts, lead breakdowns, unique reach, hourly distributions, CTR
  - `placement_day_stats` rollup: groups by placement type — platform-level reporting on which placements perform best
  - Only processes events with `campaign_id` set (new platform events, ignores legacy)
  - Enriches `vendor_id` from `ad_campaigns` collection
  - `backfill_rollups()` for initial setup or recovery
  - `compute_daily_rollup()` entry point runs both rollups

### Changed

- **`app/main.py`** — Registered new routers and integrated campaign rollup into nightly scheduler
  - Added `vendor_campaigns_router` (Vendor Campaigns) and `admin_campaigns_router` (Admin Campaigns)
  - Nightly scheduler now runs: legacy rollup → campaign rollup → expired campaign auto-completion
  - Legacy `advertising_router` kept for backward compatibility (will be removed in Phase 5)

### Architecture Notes

- Vendor campaigns router (`/portal/ads/*`) is fully independent from planner auth — vendors sign up at `vendor.thespecialwedding.io` with `role: advertising_vendor`
- Admin campaigns router (`/admin/ads/campaigns/*`) coexists with legacy `/admin/ads/*` router — no route conflicts because of the `/campaigns` prefix
- Campaign rollup service coexists with legacy `ad_rollup_service.py` — both run nightly, each processing their own event subset
- All new services follow the established pattern: `__init__(db)`, `_serialize()`, `_to_oid()`, async Motor operations

## [2.13.0] - 2026-03-18 — Trial & Subscription Lifecycle, Billing Paywall, Stripe Plan Sync

### Added

- **Trial expiration warning system** — 7-day early warning email + 3-day countdown (daily emails on days 3, 2, 1) before trial expires. Tracked via `trial_warning_sent` and `trial_countdown_last_day` fields
- **In-app trial banner** (`TrialBanner.tsx`) — persistent banner for planners within 3 days of expiration or with expired/cancelled subscriptions. Shows contextual messaging with "Upgrade Now" CTA
- **Billing paywall for expired planners** — expired/cancelled/suspended planners are redirected to `/admin/planner/billing` via `AdminRouteGuard`. Cannot access any feature pages until they resubscribe
- **Reactivation flow on billing page** — expired planners see "Reactivate Your Account" with plan cards and fresh Stripe Checkout sessions (not the Portal update flow which doesn't work for expired subs)
- **Subscription gate in `get_current_user_extended`** — path-based whitelist blocks expired planners on feature endpoints (402) while allowing access to profile, billing, and Stripe endpoints. Root admin always bypasses
- **Stripe plan change sync** — webhook handler now resolves `plan_id` from the current Stripe price on subscription items instead of relying on stale `metadata.plan_id`. Handles Portal-initiated plan changes correctly
- **User ID fallback in webhook handler** — when `metadata.user_id` is missing (Portal changes), looks up user from `user_subscriptions` or `stripe_customers` collection so both DB collections stay in sync
- **Migration script** (`migrate_subscription_fields.py`) — backfills `user_email`, `start_date`, `created_by` on existing `user_subscriptions` records + `trial_warning_sent`, `registration_source` on users. Runs on deploy via Dockerfile
- **Sync script** (`sync_stripe_subscription.py`) — manually syncs a user's subscription state from Stripe to the platform DB. Handles Stripe API v2023+ where period dates moved to subscription items
- **Force-expire script** (`force_expire_trial.py`) — test utility to force-expire a planner's trial for development testing
- **Knowledge base article** — "Understanding Your Trial, Billing & Subscription" added to `seed_knowledge_base.py` (category: billing-subscription)
- **ROOT_ADMIN email migration** in `setup_admin_user.py` — detects existing ROOT_ADMIN with different email and migrates it to match env var

### Fixed

- **Stripe webhook secret** — `.env` had placeholder `whsec_YOUR_NEW_VALUE`, replaced with actual Stripe CLI signing secret
- **Trial expiration no longer sets `is_active=False`** — expired planners keep `is_active=True` so they can still log in and reach the billing page. Only admin-deactivated accounts use `is_active=False`
- **Auth-layer trial expiration syncs both collections** — `get_current_user_extended` now updates `user_subscriptions` alongside `users` when auto-expiring a trial
- **Email failure no longer breaks expiration batch** — `send_trial_expired_email` wrapped in try/except so one failed email doesn't skip remaining users
- **SSE notification stream auth** (`notification_stream.py`) — replaced duplicated auth logic with call to `get_current_user_extended`, eliminating 401 polling from stale/divergent auth code
- **Budget endpoints** (`budget.py`) — 16 endpoints changed from `get_current_user_extended` to `require_admin_or_planner` to enforce subscription paywall
- **Advertising endpoints** (`advertising.py`) — 5 endpoints same fix
- **Frontend 402 handling** — `apiRequest` in `AdminContext.tsx` now redirects to billing on 402 instead of showing generic error. Login flow handles 402 from profile fetch gracefully
- **`datetime.utcnow()` deprecation** — replaced with `datetime.now(timezone.utc)` in `setup_admin_user.py`

### Changed

- **`UserModel`** — added `trial_warning_sent`, `trial_expired_at`, `registration_source` fields to match service layer usage
- **`UserUpdateModel`** — added `trial_end_date` field for admin user updates
- **`AdminRouteGuard`** — checks `subscription_status` and redirects expired planners to billing before rendering any page
- **`/admin/page.tsx`** — expired planners redirected to `/admin/planner/billing` instead of `/admin/planner` (prevents redirect loop)
- **Billing page** — treats expired/cancelled subscriptions same as no subscription, showing plan selection with "Reactivate Your Account" messaging and fresh checkout buttons
- **Dockerfile.coolify** — startup chain includes `migrate_subscription_fields.py`

## [2.12.4] - 2026-03-18 — Standalone Ad Admin Pages + Sidebar Navigation

### Fixed

- **Advertising page 422 crash** -- `/admin/advertising` called `getVendorDirectory(token, { limit: 1000 })` but backend enforces `limit <= 100`. Changed to `limit: 100`
- **Structured error parsing** -- Added `extractErrorMessage()` helper to `vendorManagementApi.ts` that handles string, dict (feature gate), and array (Pydantic 422) error formats. Applied to all 24 API error handlers

### Added

- **4 standalone ad admin pages** -- Broke the tabbed `/admin/ads/console` into separate pages matching the mockup sidebar structure. Each page is its own route with `RootAdminGuard`, page header, and self-contained state:
  - `/admin/ads/creative-review` -- Campaign review queue with approve/reject/request changes
  - `/admin/ads/performance` -- Metrics, platform health, vendor leaderboard
  - `/admin/ads/config` -- Feature flags, serving limits, review workflow, data pipeline controls
  - `/admin/ads/revenue` -- Revenue placeholder (billing not active)
- **Root admin sidebar** -- 4 advertising nav items: Creative Review, All Campaigns, Performance, Ad Config. Each links directly to its own page (no tabs, no query params)

## [2.12.3] - 2026-03-18 — Feature Gate Error Handling & Drawer Visual Fix

### Fixed

- **Vendor dashboard 403 error crash** -- `getVendorDashboard` threw `[object Object]` when the feature gate returned a structured error dict. Now extracts `detail.message` string before throwing
- **7 vendor management API functions** with same broken error parsing -- `getVendorCategories`, `getWeddingVendors`, `getContractTemplates`, `getContracts`, `getPaymentMilestones`, `getPaymentLinks` all fixed to handle structured `detail` objects from feature gate 403s
- **Drawer stats grid** -- Changed from 2-column (Weddings, Total Revenue) to 3-column (Weddings, Rating, Starting at) matching the mockup spec. Shows `typical_price_min` with currency prefix

## [2.12.2] - 2026-03-17 — Full System QA: Data Flow Integrity & Visual Audit

### Security

- **planner_id enforcement** -- `POST /events` endpoint now always overrides `planner_id` from authenticated user instead of trusting frontend value

### Fixed

- **ObjectId serialization in rollup service** -- `get_dashboard_stats()` and `get_vendor_leaderboard()` now serialize `_id` fields via `_serialize_rollup_doc()`. Previously returned raw ObjectIds causing JSON serialization failures
- **wedding_id missing from drawer events** -- `SponsoredVendorDetailsDrawer` now accepts `weddingId` prop and passes it to all 4 `recordAdEvent` calls (vendor_profile_view, vendor_added_to_wedding, contact_click, dismiss). Previously all drawer interactions had null wedding attribution
- **WCAG touch targets** -- All interactive elements in admin console updated from 36px to 44px minimum height (10 instances: dropdowns, buttons, inputs)

### QA Audit Results (3 parallel agents)

- **API alignment**: 26 endpoints verified, all request/response structures match between TS interfaces and Python models
- **Visual fidelity**: 85% match against HTML mockups across all 8 views. No blocking gaps.
- **Data flow**: Event tracking chain verified from frontend through rollup. click_id attribution intact. CTR calculation correct (impression_served only). Wedding attribution now complete across all 5 frontend components.

## [2.12.1] - 2026-03-17 — Team Management Phases 5 & 6: Activity Logs & Notifications

### Added

- **Activity log enrichment (Phase 6A)** -- `log_activity()` now accepts `actor_name` and `actor_role` fields, stored on every log entry. All 6 team member log methods now include member name and role in messages (e.g. "John (Editor) accepted their team invitation" instead of "john@email.com accepted their team invitation")
- **Team notification types (Phase 6B)** -- Added 3 methods to `NotificationService`: `notify_team_member_accepted` (alerts owner when member joins), `notify_team_member_action` (alerts owner on high-impact team member actions with wedding context), `notify_team_member_deactivated` (alerts owner when member is deactivated)

### Verified (already implemented in prior sessions)

- Phase 5A: AdminContext `UserProfile` interface already has `is_team_member`, `team_permissions`, `team_wedding_access`, `team_assigned_wedding_ids` -- populated from `/admin/team/permissions` on login
- Phase 5B: Dashboard already filtered for team members via `get_accessible_wedding_ids()` in planner_metrics.py backend, with "Filtered View" notice on frontend

## [2.12.0] - 2026-03-17 — Team Management Phase 3: Endpoint Permission Protection

### Security

- **All 10 previously unprotected API files now have team permission enforcement.** Team members accessing these endpoints without the required permission will receive a 403 error instead of unrestricted access.

| File | Permission | Enforcement Count |
|------|-----------|------------------|
| gallery_admin.py | manage_gallery | 4 |
| gallery_upload.py | manage_gallery | 3 (NEW) |
| vendor_dashboard.py | manage_vendors | 2 (NEW) |
| reminder.py | send_reminders | 2 |
| reminder_twilio.py | send_reminders | 5 |
| forms.py | manage_forms | 9 |
| planner_metrics.py | view_analytics | 4 |
| wedding.py | manage_wedding_settings | 3 |
| planner_calendar.py | manage_wedding_settings | 7 |
| packages.py | manage_contracts | 7 (FIXED: was manage_packages) |

### Fixed

- **packages.py invalid permission key** -- Changed `manage_packages` (not in valid permission keys) to `manage_contracts`
- **gallery_upload.py missing protection** -- Added `enforce_team_permission` with `manage_gallery` to DELETE and POST endpoints
- **vendor_dashboard.py missing protection** -- Added `enforce_team_permission` with `manage_vendors` to PATCH task endpoint

## [2.11.9] - 2026-03-17 — Billing Page Layout Fix & Cancel Subscription Bug

### Fixed

- **Billing page card padding** — All `Card` components on the billing page were missing internal padding (`p-6`), causing text like "0 / 10", "0.0 / 50 GB" to clip against the right edge of the viewport
- **Billing page grid overflow** — Added `min-w-0` and `overflow-hidden` to both grid columns so content stays within its allocated track instead of bleeding past the column boundary
- **Cancel Subscription redirected to payment update** — The "Cancel Subscription" button called `handleManageBilling()` which sent no `flow_type` to the backend. The backend defaulted `null` to `"payment_method_update"`, so clicking cancel always opened Stripe's payment method page instead of the cancellation flow
- **Backend portal session default** — `create-portal-session` API no longer defaults `null` flow type to `"payment_method_update"`. A `null` flow type now opens the general Stripe billing portal overview

### Added

- **`subscription_cancel` Stripe portal flow** — New flow type supported in both frontend and backend. The "Cancel Subscription" button now opens Stripe's cancellation flow directly with the correct subscription ID
- **Cancel button styling** — Cancel Subscription button now has red border/text styling to visually distinguish it as a destructive action

## [2.11.8] - 2026-03-17 — Fix Package Creation Crash (Decimal BSON Serialization)

### Fixed

- **Package creation crash** — `WeddingPackage.total_amount` used Python `Decimal` type which BSON cannot encode, causing `InvalidDocument: cannot encode object: Decimal(...)` on `insert_one`. Changed to `float` in the model and service layer. Same fix applied to `ScheduleItem.amount` and `PaymentExecution.amount` to prevent the same issue in contracts
- **"Create & Activate" always saved as draft** — `CreatePackageRequest` was missing the `status` field so the frontend's status choice was silently dropped. Added `status: Optional[str]` with pattern validation to the request model so packages can be created directly as active

### Changed

- **`WeddingPackage.total_amount`** — `Decimal` → `float` (MongoDB stores as BSON double regardless)
- **`ScheduleItem.amount`** — `Decimal` → `float` for BSON compatibility
- **`PaymentExecution.amount`** — `Decimal` → `float` for BSON compatibility
- **`field_serializer` on `total_amount`** — Changed from `when_used='json'` to `when_used='always'` so float conversion applies in `model_dump()` too

## [2.11.7] - 2026-03-17 — Feature Flag Config ObjectId + AI Bug Verification

### Fixed

- **Feature flag config endpoint ObjectId** -- `PUT /admin/ads/feature-flag/config` now serializes `_id` to string before returning response

### Verified (already fixed in prior sessions)

- BUG-006: `model=model` in error handler -- already uses `locals().get("model", "unknown")`
- BUG-008: JSON parse failure -- already raises `AIInvalidResponseError` instead of returning raw object
- BUG-009: Credit deduction before validation -- already resolved because parsing happens inside `_call_gemini`, so `increment_usage` is only reached on valid responses

## [2.11.6] - 2026-03-17 — ObjectId Serialization & Attribution Tracking

### Fixed

- **ObjectId serialization across entire advertising service** -- All 15+ methods that return MongoDB documents now convert `_id` from ObjectId to string via `_serialize_doc()` helper. Prevents JSON serialization 500 errors on every ad-related API endpoint
- **Wedding ID attribution** -- `SponsoredVendorsRail` and `SponsoredMilestoneModule` now pass `wedding_id` in all `recordAdEvent` calls. All 4 milestone module instances on wedding detail page receive `weddingId` from route params

## [2.11.5] - 2026-03-17 — Advertising Frontend-Backend Alignment Audit

### Fixed

- **RecordAdEventRequest interface** -- Added missing `wedding_id`, `planner_id`, `session_id`, `click_id` fields; removed nonexistent `user_id`. Attribution tracking context was lost without these fields
- **create_lead() planner_id validation** -- Required `planner_id` field now enforced with 400 error instead of silently writing null
- **Date range null comparison** -- Sponsored vendor date queries now use `$in: [None]` + `$exists: false` for explicit null/missing coverage
- **Model timestamp fields** -- Added `created_at`/`updated_at` to AdEvent, AdLead, PlannerAdPreference, AdvertisingFeatureFlag models to match what service layer writes

### Added

- **Review status index** -- Compound index `(review_status, created_at)` on sponsored_vendors for review queue queries

## [2.11.4] - 2026-03-17 — Root Admin & Loading State Layout Consistency

### Fixed

- **Loading state `min-h-screen` overflow** — Replaced `min-h-screen` on loading/empty state returns across 6 pages (root admin dashboard, SaaS management, Billing, Vendors, Forms) with `py-24` padding so spinners center within the admin layout instead of pushing past the viewport
- **Forms loading state** — Removed decorative gradient background (`bg-gradient-to-br`) and glass-blur card from loading spinner to match the simple, consistent loading pattern used across all other pages

## [2.11.3] - 2026-03-17 — Ad Rail Layout Fix & Budget Page Ads

### Fixed

- **Vendors page ad layout** -- `SponsoredVendorsRail` moved from inline stacked position to proper right-sidebar column using `lg:grid-cols-4` grid layout, matching the Dashboard page pattern
- **SponsoredVendorDetailsDrawer build error** -- Replaced missing `@/hooks/useToast` import with `sonner` toast

### Added

- **Budget page sponsored vendors rail** -- Added `SponsoredVendorsRail` to the Budget page in a right-sidebar column. All four planner-facing pages (Dashboard, Vendors, Wedding Detail, Budget) now have consistent ad placement: horizontal scroll on mobile, vertical right rail on desktop

## [2.11.2] - 2026-03-17 — Root Admin Page Layout Consistency

### Fixed

- **Profile page centering** — Removed `max-w-4xl mx-auto` wrapper from Account Settings page so content fills the full available width like all other admin pages
- **Planner Billing page centering** — Removed `max-w-4xl mx-auto` from the no-subscription state and `max-w-5xl mx-auto` from the billing dashboard state
- **Platform page error state** — Replaced `max-w-4xl mx-auto` + `p-8` wrapper on the error fallback with standard `space-y-6` wrapper
- **Vendors page JSX parse error** — Fixed Turbopack build failure caused by a JSX comment placed between closing tags in the grid layout

## [2.11.1] - 2026-03-17 — Vendor Details Drawer Wiring

### Added

- **SponsoredVendorDetailsDrawer wired to card clicks** -- Clicking a sponsored vendor card in the SponsoredVendorsRail now opens a slide-out drawer with full vendor details, pricing, contact info, portfolio, and 4 action buttons instead of navigating to a new page

## [2.11.0] - 2026-03-17 — Dashboard UI Consistency & Inbox Resizable Panels

### Fixed

- **Page layout alignment** — Removed `max-w-*` + `mx-auto` centering from 8 admin pages (Calendar, Guests, Gallery, Inbox, Reminders, Weddings, Budget, Seating) so all pages fill the available width consistently, matching the admin layout's built-in padding
- **Wedding selector dropdown inconsistency** — Standardized the "Select Wedding" dropdown across all pages to use the same inline label + dropdown pattern with identical card container, border radius, padding, and focus ring styling. Previously each page had a unique style (Gallery had a heart-icon oversized dropdown, Reminders had a stacked label, Seating used glass-blur, Guests used a block label)
- **Sidebar active state for Dashboard** — `isActive()` in `Sidebar.tsx` now uses exact-match for `/admin/planner` instead of `startsWith`, so navigating to Calendar (`/admin/planner/calendar`) or Team (`/admin/planner/team`) no longer falsely highlights the Dashboard nav item
- **"Dashboard" label bleeding into sub-pages** — `getPageTitle()` in `layout.tsx` changed from `pathname.includes('/admin/planner')` to `pathname === '/admin/planner'` so Calendar, Team, and Billing pages no longer show "Dashboard" in the top header bar
- **Inbox page wrapper** — Replaced `min-h-screen bg-gray-50` + `max-w-7xl mx-auto px-4` with standard `space-y-6` wrapper matching all other pages

### Added

- **Inbox resizable panels** — The message list and preview panes now have a draggable vertical divider (grip handle) that lets planners resize the two panels horizontally between 20% and 70% width. Defaults to a 40/60 split. Uses mouse event listeners for smooth drag behavior with cursor feedback

### Changed

- **Budget page** — Replaced `Card` component wrapper for wedding selector with standard `div` to match the uniform card styling used across all pages
- **Seating page** — Replaced glass-blur (`backdrop-blur-xl`, `bg-white/70`) wedding selector with standard opaque card styling for visual consistency
- **Reminders page** — Consolidated the two-row wedding selector + channel picker into a single inline row within the standard card container

## [2.10.9] - 2026-03-17 — Views 3-5 QA Audit & Tech Debt Fixes

### Fixed

- **Feature flag config back-fill** — Existing feature flag documents in MongoDB now auto-migrate to include new review workflow config keys, preventing frontend crashes
- **Feature flag `_id` serialization** — ObjectId converted to string before JSON response
- **Category filter clobber** — `get_sponsored_vendors_filtered()` no longer overwrites `target_categories` when both category filter and hidden categories are set
- **Hidden vendor ObjectId validation** — Invalid ObjectId strings in hidden vendor preferences no longer crash the query
- **Dashboard stats unbounded cursor** — Added 5000-document limit to `get_dashboard_stats()`
- **Duplicate `getFeatureFlag` export** — Removed duplicate function in `advertisingApi.ts` that caused build error
- **`SponsoredVendor` TypeScript interface** — Added `review_status`, `reviewed_by`, `reviewed_at`, `review_notes` fields; removed unsafe `as any` casts

### Added

- **Campaigns table Budget column** — Shows daily/lifetime budget from campaign metadata
- **Campaigns table CPL column** — Placeholder for cost-per-lead (will compute from billing when Stripe is connected)
- **Review-aware status badges** — Campaign status now distinguishes pending_review, rejected, changes_requested from active/paused

### Verified

- View 3 (Directory Boosts) — `BoostedVendorCard` already integrated in vendor directory grid
- View 4 (Milestone Module) — `SponsoredMilestoneModule` already integrated on wedding detail page for 4 categories
- View 5 (Vendor Ad Manager) — Core dashboard complete with metrics, weekly chart, conversion funnel, campaigns table

## [2.10.8] - 2026-03-17 — View 7 Admin Moderation Console & Review Workflow

### Added

- **Creative review workflow** — Campaigns now submit as `pending_review` and require root admin approval before going live. New `AdReviewStatus` enum, review fields on `SponsoredVendor`, and `ReviewCampaignRequest` model
- **Review API endpoints** — `GET /admin/ads/review-queue`, `GET /admin/ads/review-queue/counts`, `PUT /admin/ads/sponsored-vendors/{id}/review`, `PUT /admin/ads/feature-flag/config`
- **View 7 Admin Console** (`/admin/ads/console`) — 4-tab root admin page: Creative Review (queue with approve/reject/request changes), Performance Dashboard (metrics, daily trend, leaderboard), System Config (feature flags, serving limits, review workflow, data pipeline), Revenue & Billing (placeholder with real vs. planned feature inventory)
- **Vendor placeholder pages** — `/admin/vendor/ads/campaigns` (campaign list), `/admin/vendor/ads/leads` (lead list with filters), `/admin/vendor/ads/billing` (free tier notice, tracked data, coming-soon roadmap)

### Changed

- **Campaign Wizard** — Submits with `is_active: false` and `review_status: "pending_review"` instead of auto-activating
- **Feature flag config** — Added `require_review`, `auto_approve_returning_vendors`, `review_sla_hours` to defaults

## [2.10.7] - 2026-03-17 — Ad Image Upload with Separate S3 Bucket

### Added

- **Separate R2 bucket for vendor ad assets** — New `vendor-ad-assets` bucket isolates ad creative from wedding gallery content. New env vars: `S3_AD_BUCKET_NAME`, `AD_MEDIA_DOMAIN`
- **`AdUploadService`** — Dedicated upload service for ad images (JPEG/PNG/WebP, max 5 MB) with presigned URL generation, keyed by `ads/{vendor_id}/{timestamp}_{filename}`
- **`GET /admin/ads/upload-url`** — Backend endpoint returning presigned PUT URL for the ad bucket
- **`POST /admin/ads/update-logo`** — Backend endpoint to persist CDN URL on vendor profile's `logo_url`
- **Campaign Wizard drag-and-drop image uploader** — Step 5 (Creative) now has a proper file upload zone with drag-and-drop, progress states, preview with remove, and file validation. Replaces the plain text URL input
- **`.env.example` rebuilt** — Full template with all current env variables using placeholder values

### Changed

- **`next.config.js`** — Added `AD_MEDIA_DOMAIN` to image `remotePatterns`

## [2.10.6] - 2026-03-17 — Stripe Webhook Resilience & API v13+ Compatibility

### Fixed

- **Checkout session missing metadata** — `stripe.checkout.Session.create()` now includes `metadata` with `user_id`, `plan_id`, and `billing_interval` on the checkout session itself (previously only set on `subscription_data.metadata`). This ensures `_handle_checkout_completed` can resolve the user even when the checkout session webhook fires before the subscription is queryable.

- **Webhook handler fallback for empty session metadata** — `_handle_checkout_completed` now falls back to retrieving `user_id` and `plan_id` from the Stripe subscription's metadata when the checkout session metadata is empty. Prevents permanent webhook failures with "Missing user_id or plan_id" for sessions created before the metadata fix.

- **Stripe API v13+ compatibility for subscription period dates** — `_sync_subscription_state` now reads `current_period_start` and `current_period_end` from subscription items (Stripe API v13+ location) with fallback to top-level fields (legacy) and `start_date`. Prevents period dates from defaulting to `now` on active subscriptions.

### Added

- **`scripts/resend_checkout_webhook.py`** — Utility script to manually replay checkout completion sync for users whose Stripe webhook was missed (e.g., during local development without `stripe listen`). Uses pymongo directly for portability.

## [2.10.5] - 2026-03-17 — Stripe Checkout: Subscription Record & Plan Sync Fixes

### Fixed

- **Subscription record missing status and created_at on checkout** — `create_checkout_session` upsert in `stripe_service.py` now sets `status: "pending_checkout"` and `$setOnInsert: {created_at}` so the admin billing dashboard shows a proper state instead of `"unknown"` with empty timestamps before the Stripe webhook fires.

- **Users collection plan_id not updated during checkout** — When a user selects a plan during checkout via `/public/create-checkout-session`, the `users` collection `plan_id` was not updated (only the `user_subscriptions` record was). Now syncs `plan_id` on the user document when the checkout plan differs from what was stored at registration. (`app/api/stripe_payment.py`)

## [2.10.4] - 2026-03-16 — Migrate Bulk SMS to Twilio Service & Add Throughput Throttling

### Changed

- **Frontend bulk event reminder migrated from legacy to Twilio service** — `handleSendEventReminder()` now calls `POST /admin/reminders/twilio/send` instead of the legacy `POST /admin/reminders/send`, gaining delivery tracking, messaging service SID routing, retry logic, and error classification
- **SMS error handling improved on frontend** — Bulk event reminder SMS responses now surface errors to the user (previously silently ignored non-ok responses) and report skipped counts (no phone, opted out)

### Added

- **SMS throughput throttling** — All bulk SMS send loops (`TwilioReminderService.send_reminders()`, `TwilioRSVPReminderHelper.send_personalized_rsvp_links()`, `send-to-guests`, `send-to-plus-ones` endpoints) now include a configurable inter-message delay (default 350ms ≈ 2.8 req/s) to stay safely under the toll-free 3 MPS limit and avoid carrier flagging
- **`SMS_THROTTLE_DELAY_MS` env var** — Configurable throttle delay between SMS API calls (default: 350ms for toll-free). Set to 100ms after upgrading to high-throughput toll-free (25+ MPS), or 50ms for short codes

### Technical Notes

- Twilio 10DLC default throughput: 1 MPS per number (varies by Trust Score up to ~75 MPS)
- Toll-free default: 3 MPS (upgradeable to 25+ MPS)
- Short code: 100 MPS
- T-Mobile also enforces daily message limits per subscriber (separate from MPS)
- Twilio queues messages internally (up to 36,000 segments per US long code), but firing API calls too fast triggers 429 rate limits
- "Snowshoeing" (using multiple numbers to increase throughput) causes carrier filtering — use Messaging Service SID with a single sender pool instead

## [2.10.3] - 2026-03-16 — Wire Planner Ad Actions (mailto, VendorAssignment, Vendor Images)

### Added

- **Request Quote mailto integration** — Ad cards now open planner's native email client with vendor email pre-filled, contextual subject line, and pre-drafted body
- **Add to Wedding wiring** — Ad cards now create real VendorAssignment records via API instead of showing fake success toasts
- **AdLead attribution** — Both quote requests and add-to-wedding actions create AdLead records for full funnel tracking
- **Vendor image rendering** — Ad cards display vendor logo_url when available, falling back to category emoji

### Changed

- VendorProfile TypeScript interface now includes logo_url, service_radius, country, postal_code
- BoostedVendorCard no longer accepts onAddToWedding/onRequestQuote callbacks (handles internally)
- SponsoredVendorCard accepts weddingId/weddingName props for contextual actions

## [2.10.2] - 2026-03-16 — Fix Systemic Datetime Comparison Errors

### Fixed

- **Offset-naive vs offset-aware datetime errors across entire app** — MongoDB Motor client was not configured with `tz_aware=True`, causing all datetimes returned from MongoDB to be timezone-naive. Any comparison with `datetime.now(timezone.utc)` raised `TypeError: can't compare offset-naive and offset-aware datetimes`. This affected `/otp/request`, `/verify-email`, `/admin/profile`, and many other endpoints (~8800 errors in production). Fixed by adding `tz_aware=True` and `tzinfo=datetime.timezone.utc` to `AsyncIOMotorClient` in `app/core/database.py` — a single root fix that resolves all datetime comparison errors system-wide.

### Removed

- Temporary test endpoint `/public/test/lookup-verification-token/{email}` removed from `app/api/user_management.py`
- Debug logging and redundant per-method datetime workarounds removed from `app/services/user_management_service.py`

## [2.10.1] - 2026-03-16 — QA Fixes: Validator Edge Cases, SMS Fallback Safety & Partial Success UI

### Fixed

- **Empty string phone stored instead of null** — All phone validators (`GuestModel`, `UpdateGuestRequest`, `CreateGuestRequest`, `PlusOneModel`) returned `""` instead of `None` when given an empty string, allowing invalid empty phone values in the database. Now consistently return `None` for any falsy input. Same fix applied to email validators. (`app/models/guest.py`, `app/models/plus_one.py`)

- **Unsafe `or to` fallback in bulk SMS services** — `_send_sms()` in Twilio, Telnyx, and generic services used `normalize_phone_e164(to) or to`, which fell back to the raw unsanitized phone if normalization returned `None`. Now explicitly checks for `None` and returns a failure status with `invalid_number` error code instead of passing garbage to the SMS provider. (`app/services/reminder_service_twilio.py`, `app/services/reminder_service.py`, `app/services/reminder_service_telnyx.py`)

- **Email error message showed `None` instead of original value** — `ResendEmailService.send_email()` sanitized the email before the error message, so whitespace-only emails produced `"Invalid recipient email: None"`. Now preserves the original value for the error message. (`app/services/email_service_resend.py`)

- **Frontend partial success masked by error** — If guest SMS sent successfully but plus-one SMS endpoint returned an error, the UI threw and showed only the error, losing the guest success count. Both endpoints now catch errors independently and accumulate results, showing combined stats like "Sent 3 of 5. 2 failed." (`app/admin/reminders/page.tsx`)

## [2.10.0] - 2026-03-16 — Contact Validation, Plus-One Individual Messaging & Guest Page Filters

### Added

- **Shared contact sanitization utility** — New `app/utils/contact_sanitizer.py` with `sanitize_phone()`, `normalize_phone_e164()`, `sanitize_email()`, `validate_phone_format()`, and `validate_email_format()` functions used across all models and send-time services for consistent phone/email handling.

- **Plus-one individual SMS messaging** — New `POST /reminders/send-to-plus-ones` endpoint allows planners to send SMS reminders to specific plus-ones by ID. Includes wedding ownership verification (plus-one → guest → wedding chain), sms_opt_in compliance check, E.164 phone normalization, delivery tracking with message_sid, and activity logging with SSE broadcast. (`app/api/reminder_twilio.py`)

- **Plus-ones in individual messaging UI** — Reminders page MultiSelect now merges guests and plus-ones with prefixed values (`guest:{token}` / `plusone:{id}`). Plus-ones display as "Name (Host's +1)" with phone sublabel. `handleSendIndividualMessage` splits by prefix and calls both endpoints in parallel. (`app/admin/reminders/page.tsx`)

- **"Not Invited" guest tab** — Guest management page now has a dedicated "Not Invited" tab (previously lumped into "Awaiting RSVP") with correct filter logic checking `invite_sent` and RSVP status. (`app/admin/guests/page.tsx`)

- **Clickable stat cards** — All guest stat cards (Total, RSVP'd, Pending, Not Invited) now set the active tab filter on click, with a visual ring highlight on the active card. (`app/admin/guests/page.tsx`)

- **Email validators on GuestModel** — `GuestModel`, `UpdateGuestRequest`, and `CreateGuestRequest` now validate email format (strip whitespace, lowercase, regex check), matching the validation that `PlusOneModel` already had. (`app/models/guest.py`)

### Fixed

- **SMS opt-in compliance for plus-ones (Telnyx & generic)** — Telnyx and generic reminder services were sending SMS to plus-ones without checking `sms_opt_in` status. Both now skip explicitly opted-out plus-ones and track `skipped_opted_out` in return values. (`app/services/reminder_service.py`, `app/services/reminder_service_telnyx.py`)

- **Missing E.164 normalization in generic SMS service** — `reminder_service.py` `_send_sms()` passed raw phone numbers to Twilio without any E.164 formatting. Now uses `normalize_phone_e164()` to strip delimiters and prepend country code. (`app/services/reminder_service.py`)

- **Phone sanitization at model level** — All phone validators (`GuestModel`, `UpdateGuestRequest`, `CreateGuestRequest`, `PlusOneModel`) now sanitize input before validation — stripping whitespace, parentheses, dashes, dots, and spaces — so user-entered formats like `(234) 567-8901` are cleaned to `2345678901` instead of being rejected. (`app/models/guest.py`, `app/models/plus_one.py`)

- **Send-time phone sanitization (defense-in-depth)** — All SMS send paths now run `normalize_phone_e164()` on phone numbers read from MongoDB before passing to Twilio/Telnyx, catching any data that bypassed model validation (CSV imports, direct DB edits, legacy data). (`app/api/reminder_twilio.py`, `app/services/reminder_service_twilio.py`, `app/services/reminder_service.py`, `app/services/reminder_service_telnyx.py`)

- **Send-time email sanitization** — `ResendEmailService.send_email()` now sanitizes and validates recipient email before calling the Resend API, returning a clear error for invalid addresses instead of letting the API call fail. (`app/services/email_service_resend.py`)

- **CSV import phone/email sanitization** — `GuestImportService.import_csv()` now uses `sanitize_phone()` and `sanitize_email()` with format validation instead of basic `.strip()`, so phones with delimiters (e.g. `(234) 567-8901` from spreadsheets) are cleaned before storage. Invalid phone/email values are dropped but the guest is kept if the other contact method is valid. (`app/services/import_service.py`)

- **N+1 RSVP query in Telnyx service** — Replaced per-guest `find_one()` RSVP lookups with pre-fetch lookup map, matching the pattern used in the Twilio service. (`app/services/reminder_service_telnyx.py`)

## [2.9.2] - 2026-03-16 — Guest Import: Non-Blocking Planner Warnings

### Fixed

- **Planner-visible CSV skip feedback** — Guest CSV imports now return inline warnings for skipped rows with CSV row numbers and reasons (invalid name or missing valid contact info) so planners can correct bad entries without the import failing. The warnings render in both admin import screens after a successful upload. (`app/services/import_service.py`, `app/admin/guests/page.tsx`, `app/admin/import/page.tsx`)

## [2.9.1] - 2026-03-16 — Stripe Signup: Atomicity & Concurrency Hardening

### Fixed

- **Atomic Stripe customer creation** — `get_or_create_customer()` now rolls back the Stripe customer if the subsequent MongoDB write fails, preventing orphaned Stripe customers that are unreachable from the platform. Logs `CRITICAL` if the rollback itself fails for manual cleanup. (`app/services/stripe_service.py`)

- **Concurrent checkout race condition** — `create_checkout_session()` now uses `find_one_and_update` with a 30-minute active-window guard so a second concurrent checkout for the same user is rejected with HTTP 409 instead of silently overwriting the first session. The losing Stripe session is expired automatically. (`app/services/stripe_service.py`)

- **Transactional subscription sync** — `_sync_subscription_state()` now updates both the `user_subscriptions` and `users` collections inside a single MongoDB transaction, preventing split-brain states where one collection is updated but the other isn't. Gracefully falls back to sequential writes on standalone MongoDB (no replica set) with a warning. (`app/services/stripe_service.py`)

## [2.9.0] - 2026-03-16 — Stripe Signup: Security Audit & Critical Fixes

### Fixed

- **Payment bypass vulnerability** — Planners with `pending_payment` status could log in and use the platform without completing Stripe checkout. Added subscription status gate in auth middleware that blocks `pending_payment`, `cancelled`, `suspended`, and `expired` users with appropriate 402 messages. (`app/dependencies/auth_extended.py`)

- **Email enumeration on public checkout** — `POST /public/create-checkout-session` returned different error messages for valid vs. invalid emails, allowing attackers to enumerate registered users. Unified error messages to prevent information disclosure. (`app/api/stripe_payment.py`)

- **Webhook infinite retry on permanent failures** — Missing metadata or deleted users caused webhook handler to return 500, making Stripe retry forever. Now returns 200 for permanent failures (missing data, user not found) while preserving 500 for transient errors (DB timeout, network) so Stripe correctly retries only retriable failures. (`app/api/stripe_payment.py`)

- **User existence check in checkout webhook** — `_handle_checkout_completed` could activate subscriptions for deleted users. Added user existence verification before syncing subscription state. (`app/services/stripe_service.py`)

### Added

- **End-to-end Stripe signup test script** — Comprehensive test that exercises the full registration → email verification → plan listing → checkout session flow with cleanup, validation, and detailed error reporting. Run with `python tests/test_stripe_signup.py --api-url http://localhost:8000`. (`tests/test_stripe_signup.py`)

## [2.8.0] - 2026-03-16 — Advertising: UX Copy Audit & Terminology Alignment

### Fixed

- **Placement label consistency** — Campaign wizard placement labels now match the canonical `getAdPlacementLabel()` function across all views (Vendor Rail, Vendor Detail, Milestone Module, Directory Boost).

- **Category backend alignment** — Campaign wizard category options now send snake_case values matching backend `service_category` field (e.g., "photographer" not "Photography"), with human-readable labels for display.

- **Vendor-facing copy** — Replaced developer-facing language in View 5 data annotation and chart footnotes with vendor-friendly explanations of how performance tracking works.

- **UX microcopy improvements** — De-jargoned goal descriptions (removed CPC/CPL/CPA acronyms), clarified funnel labels ("Added to Wedding", "Bookings"), improved empty states, aligned mobile/desktop footer copy, enriched mobile tooltip, and showed human-readable pricing labels in campaign review step.

- **Price format consistency** — BoostedVendorCard now uses `vendorProfile.currency` instead of hardcoded `$`, matching SponsoredVendorCard behavior.

- **Ads sub-navigation** — Layout nav items now have distinct hrefs (/campaigns, /leads, /billing) so active state can function correctly.

## [2.7.0] - 2026-03-16 — Advertising: Vendor Ad Manager (View 5) & Campaign Wizard (View 6)

### Added

- **Vendor Ad Manager dashboard** — Full rewrite of vendor advertising overview with 5 performance metric cards (Impressions, Clicks, Click Rate, Leads, Cost/Lead) with period-over-period change indicators, Performance by Week recharts bar chart, 5-step Conversion Funnel visualization, and Active Campaigns table with per-vendor lead counts. Uses parallel `getDashboardStats` + `getAdLeads` API calls. (`app/admin/vendor/ads/page.tsx`)

- **6-step Campaign Creation Wizard** — Expanded from 5 to 6 steps matching mockup spec. New Pricing step (Step 4) with CPC/CPL/Fixed model selection and bid inputs. Budget step adds type toggle cards (Daily/Lifetime), estimated spend calculations, pacing strategy cards, and budget recommendation box. Creative step includes live preview with production-style "✦ Sponsored" badge. Full metadata capture for all wizard selections. (`app/admin/vendor/ads/campaigns/new/page.tsx`)

- **`directory_boost` placement in wizard** — Campaign wizard now includes Directory Boost as a fourth placement option alongside Vendor Rail, Vendor Directory, and Milestone Pages.

### Fixed

- **Accessibility improvements** — Added `aria-label` and `aria-pressed` on all toggle buttons in campaign wizard. Added date range validation (endDate >= startDate). Fixed annotation text contrast from gray-400 to gray-600 for WCAG AA compliance.

## [2.6.0] - 2026-03-16 — Advertising: Directory Boosts (View 3) & Milestone Modules (View 4)

### Added

- **BoostedVendorCard component** — New card for `directory_boost` placement with 120px image header, dual badges (⚡ Boosted + ✦ Sponsored), star ratings, price range, dual CTAs (Add to Wedding + Request Quote), full event tracking with click_id attribution, IntersectionObserver viewability, and WCAG 2.1 AA accessibility (44px targets, focus rings, ARIA). (`app/admin/vendors/components/BoostedVendorCard.tsx`)

- **SponsoredMilestoneModule component** — New contextual ad module for `milestone_module` placement. Renders max 2 sponsored vendor cards scoped to a milestone category (venue, photographer, catering, florist). Generates contextual why-tags from wedding data (distance, guest capacity, budget match). Auto-suppresses when milestone is booked. Includes "Why am I seeing this?" tooltip and section hide controls. (`app/admin/vendors/components/SponsoredMilestoneModule.tsx`)

- **Directory boost integration** — Vendor directory page fetches up to 2 boosted vendors, filters by planner preferences, renders them at the top of the grid before organic results, and shows boosted count indicator. (`app/admin/vendors/page.tsx`)

- **Milestone module integration** — Wedding detail page renders 4 milestone modules (venue, photographer, catering, florist) in the main content column with category-specific budget context and venue booking detection. (`app/admin/weddings/[id]/page.tsx`)

## [2.5.0] - 2026-03-16 — SSE Production Hardening: Cross-Worker Broadcast, Connection Consolidation & Nginx Tuning

### Added
- **Redis pub/sub for SSE cross-worker broadcast** — `SSEManager` now publishes events to a Redis channel so all uvicorn workers deliver data-change events to connected clients, not just the worker that handled the mutation; falls back to in-process delivery when Redis is unavailable (`app/services/sse_manager.py`)
- **SSE Redis listener lifecycle** — `start_redis_listener()` / `stop_redis_listener()` wired into FastAPI lifespan in `app/main.py` for clean startup/shutdown
- **Shared SSEProvider context** (`app/contexts/SSEContext.tsx`) — single EventSource connection per browser tab shared across all admin components via React context; eliminates the duplicate connection previously opened by TopHeader and useSSE independently
- **Reconnect catch-up refetch** — when the SSE connection recovers after network loss or laptop sleep, a synthetic `__reconnected__` event fires so all `useSSE` consumers automatically refetch stale data instead of silently showing outdated information
- **`useSSEEvent` hook** — low-level hook for subscribing to any SSE event type from the shared connection (used by TopHeader for notification-count/notification-new events)
- **Dedicated nginx SSE location blocks** — added to `nginx-api-ssl.conf`, `nginx-api-backend.conf`, and `nginx-load-balancer.conf` with `proxy_buffering off`, `proxy_read_timeout 3600s`, and `chunked_transfer_encoding off` so events stream immediately without proxy buffering
- **K8s SSE ingress** (`k8s/base/ingress-sse.yml`) — separate Ingress resource for `/admin/notifications/stream` with 1-hour timeouts and buffering disabled
- **Global SSE connection ceiling** — `MAX_GLOBAL_CONNECTIONS = 2000` prevents unbounded memory growth from SSE connections across all users; returns `ConnectionError` when exceeded
- **GZip bypass for SSE** — `SSEGzipBypassMiddleware` strips `Accept-Encoding` for SSE requests so the GZip middleware never buffers streaming event responses (`app/main.py`)
- **SSE broadcast on all remaining mutation endpoints** — `broadcast_data_change()` calls added to: `rsvp_service.py` (public RSVP submission), `email_reminders.py` (3 send endpoints), `reminder_twilio.py` (bulk SMS + individual reminders), `reminder_utilities.py` (personalized links), `wedding.py` (create/update/delete), `plus_one.py` (create/update/delete)

### Changed
- **TopHeader.tsx** — removed ~140 lines of standalone EventSource management (connection, reconnection, auth probing, visibility handling); now subscribes to the shared SSEProvider via `useSSEEvent` hook
- **useSSE.ts** — no longer creates its own EventSource; subscribes to the shared SSEProvider context and filters events by resource type and wedding ID
- **admin/layout.tsx** — wrapped admin layout with `<SSEProvider>` between AdminProvider and ConfirmDialogProvider

### Fixed
- **Multi-worker event delivery** — previously, only ~25% of SSE clients received data-change events because the in-process singleton was isolated per uvicorn worker process; Redis pub/sub ensures all workers deliver every event
- **Missed events after sleep/network loss** — previously no catch-up mechanism existed; clients that reconnected had stale UI until the next manual refresh or unrelated event
- **Nginx buffering delayed SSE events** — `proxy_buffering on` in the general location block could delay or stall event delivery; SSE now has its own unbuffered location
- **Duplicate browser connections** — 2 EventSource connections per tab (TopHeader + useSSE) consumed browser connection slots and doubled server-side queue memory; consolidated to 1

## [2.4.0] - 2026-03-16 — Advertising: Code Review, Responsive Rail, Accessibility & Type Safety

### Added

- **Responsive sponsored vendors rail** — Desktop (lg: 1024px+) renders a vertical stacked rail with max 3 cards in the planner dashboard right sidebar; mobile renders a horizontal snap-scroll carousel with navigation arrows. Both layouts match the Vendor_Ad_Mockups.html design spec. (`SponsoredVendorsRail.tsx`, `SponsoredVendorCard.tsx`)

- **Why-tag contextual relevance** — `getWhyTag()` function generates vendor-specific context (e.g., "Serves Austin · You may need a photographer") from profile data. Passed to both desktop and mobile card renders via `whyTag` prop. (`SponsoredVendorsRail.tsx`)

- **WCAG 2.1 AA accessibility** — Full accessibility pass on sponsored vendor components:
  - Semantic `<article>` cards with keyboard-accessible `<a>` link (Tab/Enter/Space navigable)
  - 44px minimum touch targets on hide button, scroll arrows, info button, and CTA buttons
  - ARIA carousel roles (`role="region"`, `aria-roledescription="carousel"`, `role="list"`, `role="listitem"`)
  - Tooltip ARIA (`role="tooltip"`, `aria-controls`, `aria-expanded`)
  - Live region (`aria-live="polite"`) announcing vendor dismissals to screen readers
  - `focus-within:ring-2` visual focus indicator on cards
  - Preferences control changed from `<span>` to `<button>`

- **Feature flag guard on event recording** — `record_ad_event` endpoint now checks if advertising feature is enabled before recording; returns skip response when disabled. Prevents phantom event accumulation. (`app/api/advertising.py`)

- **`wedding_overrides` in TypeScript interface** — `AdPreferences` now includes `wedding_overrides` field matching backend `PlannerAdPreference` model. (`advertisingApi.ts`)

### Fixed

- **$or query construction bug** — Date range filtering in `get_sponsored_vendors()` and `get_sponsored_vendors_filtered()` used malformed `$or` that could serve expired vendors. Replaced with proper `$and` + nested `$or`. (`advertising_service.py`)

- **CTR double-counting** — `total_impressions` summed `impression_served + impression_viewable` (a subset, not additive), deflating CTR. Fixed in daily rollup, dashboard stats, and vendor leaderboard to use `impression_served` only. (`ad_rollup_service.py`, `advertising.py`)

- **Lead endpoint vendor-role scoping** — Lead endpoints blocked vendor users entirely. Updated to allow vendors to see leads for their own profiles via email lookup with ObjectId conversion. (`advertising.py`)

- **Missing `dashboard_rail` placement enum** — Backend `AdPlacement` enum had 4 values but frontend needed 5. Added `DASHBOARD_RAIL = "dashboard_rail"`. (`models/advertising.py`)

- **Field name mismatch** — `AdPreferences.hidden_vendors` renamed to `hidden_vendor_ids` to match backend. (`advertisingApi.ts`)

- **Contrast failures** — Gray text on white backgrounds upgraded from `gray-300`/`gray-400`/`gray-500` to `gray-600` (5.7:1 ratio), meeting WCAG AA 4.5:1 requirement. (`SponsoredVendorCard.tsx`, `SponsoredVendorsRail.tsx`)

### Changed

- **Frontend AdEventType cleaned** — Removed 4 legacy types (`impression`, `viewable_impression`, `detail_view`, `assignment`) that don't exist in backend enum. Reduced from 15 to 12 values. `getEventTypeLabel` updated to match. (`advertisingApi.ts`)

- **Card component restructured** — `<div onClick>` replaced with `<article>` + `<a>` for accessibility. CTA buttons moved outside the link element to avoid nested interactive elements. (`SponsoredVendorCard.tsx`)

---

## [2.3.0] - 2026-03-16 — Landing Page Polish, Performance Fixes & Real-Time Architecture

### Added

- **Server-Sent Events (SSE) real-time update system** — Replaced 30-second polling with persistent SSE connections for instant data propagation across admin pages. Backend streams `guest_update`, `rsvp_update`, `wedding_update`, and `invite_sent` events. Frontend `useSSE` hook manages auto-reconnect with exponential backoff. (`app/api/sse.py`, `app/services/sse_manager.py`, `app/hooks/useSSE.ts`)
- **`usePolling` hook** — Configurable interval polling with visibility-aware pause/resume. Still available as a fallback when SSE is not supported. (`app/hooks/usePolling.ts`)
- **Shared normalised scroll ref for parallax sync** — `InfiniteScrollWrapper` writes the modulo-normalised scroll position to a shared React ref on every scroll event; `Modern3DBackground` reads from it in its rAF tick, eliminating any 1-frame desync at the loop boundary. (`app/components/ui/InfiniteScrollWrapper.tsx`, `app/components/landing-page/Modern3DBackground.tsx`, `app/components/landing-page/LandingLayout.tsx`)
- **Feature scope documents** — Couple Portal (`docs/FEATURE_SCOPE_couple_portal.md`) and Guest Check-In (`docs/FEATURE_SCOPE_guest_checkin.md`) with architecture, effort estimates, and implementation plans.
- **Performance & API Alignment Audit** — Full-stack review with 25 findings (6 critical, 8 high, 7 medium, 4 low) and prioritised action plan. (`docs/PERFORMANCE_AUDIT.html`)

### Fixed

- **Dashboard images returning 404** — `middleware.ts` matcher was intercepting static file paths because `isNonWeddingSlug()` returns true for any path containing a dot. Updated matcher to exclude dotted paths: `'/((?!_next/static|_next/image|api/|.*\\..*).*)'`. (`middleware.ts`)
- **Rose petal animation stopping at hero section** — `PetalCanvas` was inside the hero `<section>` with `overflow-hidden`. Moved to `<main>` level and changed from `absolute` to `fixed inset-0 z-10`. (`app/components/ui/PetalCanvas.tsx`, `app/page.tsx`)
- **Guest invite status not updating to "Pending" after SMS send** — The SMS service (`reminder_utilities.py`) sent via Twilio and logged to `reminders_sent` but never set `invite_sent: true` on the guest record. Added the missing `update_one()` after successful send. (`app/services/reminder_utilities.py`)
- **Registry section misaligned on couple slug page** — Changed from fixed `md:grid-cols-2` to dynamic grid (1/2/3 columns based on count), reduced padding and gaps. (`app/components/landing-page/LandingLayout.tsx`)

### Changed

- **Landing page copy updates** — Replaced "2.8s QR check-in speed" metric with "13 Tools in one platform". Replaced fabricated check-in testimonial with AI pricing quote. Updated fallback pricing feature from "QR check-in & live counts" to "AI pricing suggestions". (`app/page.tsx`)
- **Dashboard images switched to native `<img>`** — Replaced `next/image` `<Image>` components with `<img>` tags for dashboard screenshots. (`app/page.tsx`)
- **Auto-refresh on guest management page** — Replaced the `visibilitychange`-only listener with `usePolling` (30s) and then SSE for continuous real-time updates. (`app/admin/guests/page.tsx`)
- **Auto-refresh on planner dashboard** — Added real-time updates so wedding stats reflect new RSVPs and guest changes without manual reload. (`app/admin/planner/page.tsx`)

### Removed

- **SaaS admin content/theme tabs** — Removed "SAAS Content" tab (hero editor, statistics, trust indicators, animation settings) and "Theme & Design" tab (brand colors, backgrounds). Removed `ContentEditModal`, `DEFAULT_SAAS_CONFIG`, and related interfaces/functions. Landing page content is now hardcoded for performance. (`app/admin/saas/page.tsx`)

## [2.2.0] - 2026-03-15 — Vendor Advertising Platform (Stages 1–3), Critical Bugfixes & Ad Analytics

### Added

- **Sponsored Vendor Rail component** (`app/admin/vendors/components/SponsoredVendorCard.tsx`, `SponsoredVendorsRail.tsx`, `SponsoredVendorDetailsDrawer.tsx`):

  - Horizontal scrollable rail of sponsored vendor cards shown on planner dashboard and wedding detail pages
  - IntersectionObserver-based viewable impression tracking (50% visible for 1+ second)
  - Per-card `click_id` UUID generation for full conversion attribution across the click→lead→booking funnel
  - "Hide this vendor" dismiss control that persists via planner ad preferences API
  - "Why am I seeing this?" tooltip with HelpCircle icon explaining ad transparency
  - "See all sponsored vendors" footer link for expanded directory view
  - Wedding context selector dropdown for multi-wedding planners
  - Preference-based filtering: fetches planner preferences on mount, filters hidden vendors/categories, respects reduced frequency toggle
  - Details drawer with "Add to wedding", "Request quote", and "Message vendor" CTAs

- **Sponsored Vendor Rail placements** (`app/admin/planner/page.tsx`, `app/admin/weddings/[id]/page.tsx`):

  - Dashboard rail placement: right sidebar on the planner dashboard (`placement="dashboard_rail"`)
  - Milestone module placement: right sidebar on wedding detail page (`placement="milestone_module"`)

- **Ad event taxonomy** (`app/models/advertising.py`):

  - Expanded from 7 to 12 event types: `impression_served`, `impression_viewable`, `click`, `vendor_profile_view`, `vendor_added_to_wedding`, `lead_created`, `vendor_invited`, `lead_accepted`, `vendor_responded`, `dismiss`, `hover`, `contact_click`
  - Backend backward compatibility mapping for legacy event names (`impression` → `impression_served`, `viewable_impression` → `impression_viewable`, `detail_view` → `vendor_profile_view`, `assignment` → `vendor_added_to_wedding`)

- **Ad leads system** (`app/models/advertising.py`, `app/services/advertising_service.py`, `app/api/advertising.py`, `app/services/advertisingApi.ts`):

  - New `AdLead` model tracking planner-to-vendor interactions from sponsored ads with click_id attribution
  - Lead types: `quote_request`, `message`, `add_to_wedding`, `vendor_invite`
  - Lead statuses: `pending`, `contacted`, `responded`, `converted`, `closed`
  - Backend: `POST /admin/ads/leads`, `GET /admin/ads/leads`, `GET /admin/ads/leads/{id}`, `PUT /admin/ads/leads/{id}/status`
  - Frontend TypeScript types and API functions for full lead CRUD

- **Planner ad preferences** (`app/models/advertising.py`, `app/services/advertising_service.py`, `app/api/advertising.py`, `app/services/advertisingApi.ts`):

  - New `PlannerAdPreference` model with hidden vendor IDs, hidden categories, reduced frequency toggle, and per-wedding overrides
  - Backend: `GET /admin/ads/preferences`, `PUT hide-vendor`, `PUT hide-category`, `PUT reduce-frequency`, `DELETE unhide-vendor/{vendor_id}`
  - Frontend functions with correct HTTP methods and query parameter passing

- **Vendor ads dashboard** (`app/admin/vendor/ads/page.tsx`, `app/admin/vendor/ads/layout.tsx`):

  - 4-tab dashboard for vendor self-service: Overview (key metrics), Campaigns (table with status/metrics), Leads (table with status/actions), Billing (spend tracking)
  - Layout with sub-navigation header
  - "Advertising" nav link added to AdminHeader for vendor role users

- **Campaign creation wizard** (`app/admin/vendor/ads/campaigns/new/page.tsx`):

  - 5-step wizard: Goal selection → Placement & targeting → Budget configuration → Creative setup with live preview → Review & submit
  - Creates one `SponsoredVendor` entry per selected placement
  - Supports location targeting, service category targeting, daily/lifetime budgets, and custom creative (headline, description, image, CTA)

- **Public vendor profile page** (`app/api/vendor_public.py`, `app/vendors/[id]/page.tsx`, `app/vendors/[id]/layout.tsx`, `app/vendors/layout.tsx`):

  - Public (no auth) endpoint: `GET /api/v1/vendors/{vendor_id}/public` returning only safe fields (excludes internal_notes, tax_id, total_revenue)
  - Full-page vendor profile with hero section, contact card, portfolio gallery, and service area info
  - Registered in `main.py` on the public router

### Fixed

- **AdminContext.tsx crash — entire admin panel broken** (`app/contexts/AdminContext.tsx`):

  - Root cause: Provider value referenced `auth.isAuthenticated`, `auth.token`, `auth.login`, `api.apiRequest` etc. but no `auth` or `api` objects existed — every page crashed on render
  - Fix: replaced all references with direct variable names (`!!token`, `token`, `login`, `apiRequest`, etc.)

- **403 response incorrectly logged users out** (`app/contexts/AdminContext.tsx`):

  - `apiRequest()` and `fetchUserProfile()` both called `logout()` on HTTP 403 (permission denied) — should only logout on 401 (expired/invalid token)
  - Fix: 401 triggers logout, 403 is left for the caller to handle (e.g., show "access denied" message)

- **AI credit check key mismatch** (`app/api/ai.py`):

  - `credit_check.get("has_credits", True)` used wrong key — `check_credits()` returns `"allowed"` not `"has_credits"`
  - Fix: changed to `credit_check.get("allowed", True)` and aligned `credits_needed`/`credits_remaining` keys

- **InsufficientCreditsError missing required `message` parameter** (`app/api/ai.py`):

  - Constructor requires `message` as first positional arg, but it was omitted — raised `TypeError` instead of the intended credit error
  - Fix: added `message=credit_check.get("message", "Insufficient AI credits")` with correct key names

- **Vendor recommendation cache pollution** (`app/api/ai.py`):

  - When `request.wedding_id` was `None`, `tenant_id` fell back to plain `user_id`, causing cross-user cache collisions
  - Fix: use `f"user_{user_id}_no_wedding"` as tenant and force refresh when no wedding context

- **Undefined `model` variable in AI error handler** (`app/services/ai_service.py`):

  - `model` was defined inside `try` block but referenced in `except` — raised `NameError` masking the original error
  - Fix: `locals().get("model", "unknown")`

- **AIInvalidResponseError raised with args (takes none)** (`app/services/ai_service.py`):

  - JSON parse failure path passed an f-string to `AIInvalidResponseError()` which accepts no constructor args
  - Fix: `raise AIInvalidResponseError()` with no args, added warning log with parse details

- **Frontend-backend URL mismatch for advertising endpoints** (`app/api/advertising.py`):

  - Frontend called `/admin/ads/...` but backend router had prefix `/api/v1/ads`
  - Fix: changed backend router prefix to `/admin/ads`

- **toggleFeatureFlag sent JSON body instead of query parameter** (`app/services/advertisingApi.ts`):

  - Backend uses `is_enabled: bool = Query(...)` but frontend sent `{ is_enabled }` as JSON body
  - Fix: changed to query param in URL `?is_enabled=${isEnabled}`

- **FeatureFlag config field names misaligned** (`app/services/advertisingApi.ts`, `app/admin/advertising/page.tsx`):

  - Frontend: `enable_click_tracking`, `minimum_impression_threshold` — Backend: `enable_tracking`, `min_priority_threshold`, `impressions_per_session_limit`
  - Fix: aligned TypeScript interface and admin page to match backend field names

- **AdStats field name mismatch** (`app/services/advertisingApi.ts`):

  - Frontend: `recent_events` — Backend: `recent_events_count`
  - Fix: updated TypeScript `AdStats` interface

- **Event type mismatches between frontend and backend** (`SponsoredVendorCard.tsx`, `SponsoredVendorDetailsDrawer.tsx`):

  - Frontend sent `viewable_impression`, `detail_view`, `assignment` — Backend expected `impression_viewable`, `vendor_profile_view`, `vendor_added_to_wedding`
  - Fix: updated all frontend event strings to match backend `AdEventType` enum values

- **Missing FileText import** (`SponsoredVendorDetailsDrawer.tsx`):

  - "Request quote" CTA used `<FileText />` icon but it wasn't imported from lucide-react
  - Fix: added to imports

- **React rules-of-hooks violation** (`SponsoredVendorsRail.tsx`):

  - `useEffect` for impression tracking was placed after conditional `return null` statements — violates React's hook ordering rules and causes runtime crash
  - Fix: moved `useEffect` before all conditional returns

- **JSX structure broken in wedding detail page** (`app/admin/weddings/[id]/page.tsx`):

  - SponsoredVendorsRail insertion broke the grid layout div nesting — mismatched closing tags caused TypeScript compilation failure
  - Fix: corrected div hierarchy so `col-span-1` sidebar is properly nested as sibling to `col-span-3` main content inside the grid

- **Ad preferences endpoints — HTTP method and parameter mismatches** (`app/services/advertisingApi.ts`):

  - `hideAdVendor`: frontend POST with body → backend PUT with query param
  - `unhideAdVendor`: frontend POST with body → backend DELETE with path param
  - `hideAdCategory`: frontend POST with body → backend PUT with query param
  - `toggleReducedFrequency`: wrong URL path and param name
  - `updateAdLeadStatus`: URL missing `/status` suffix
  - `getAdLeads`: `offset` param name → backend uses `skip`
  - Fix: aligned all frontend API calls to match backend endpoint signatures exactly

- **CreateAdLeadRequest missing required `lead_type` field** (`app/services/advertisingApi.ts`):

  - Backend requires `lead_type: AdLeadType` but frontend interface omitted it entirely
  - Fix: added `lead_type`, `message`, `quote_amount`, `click_id`, `placement` fields to match backend schema

- **LeadStatus enum values misaligned** (`app/services/advertisingApi.ts`):

  - Frontend: `new`, `contacted`, `engaged`, `accepted`, `rejected`, `archived`
  - Backend: `pending`, `contacted`, `responded`, `converted`, `closed`
  - Fix: aligned frontend `LeadStatus` type to match backend `AdLeadStatus` enum

---

## [2.1.4] - 2026-03-10 — Budget Page Fixes, KB Typography & Inline Budget Editor

### Fixed

- **Date displaying as "March 7, 20260" on budget category cards** (`app/components/budget/BudgetCategoryCard.tsx`):

  - Root cause: `{category.percentage_of_total && (<span>...</span>)}` rendered the falsy number `0` as visible text when `percentage_of_total` was exactly `0` — React renders falsy numbers (`0`, `NaN`) as text nodes unlike `false`, `null`, or `undefined`
  - The stray `0` appended directly after the year in the "Last updated: March 7, 2026" line, producing "20260"
  - Fix: changed to `{!!category.percentage_of_total && (...)}` to coerce to boolean before the short-circuit

- **"Failed to fetch payment history" red error banner on Budget page** (`app/admin/budget/page.tsx`, `app/api/budget.py`):

  - The `GET /admin/weddings/{wedding_id}/payments` endpoint returned HTTP 500 — the exception bypassed FastAPI's `HTTPException` handler and was caught by the `ErrorHandlerMiddleware` (`BaseHTTPMiddleware`), which stripped the original error detail
  - Backend: changed error handling to return `JSONResponse` directly instead of raising `HTTPException`, added `exc_info=True` to the logger call for full stack traces in production logs
  - Frontend: payment history is non-critical — changed `catch` block to degrade gracefully with `console.warn` instead of setting error state that shows a red banner and toast

- **Knowledge Base articles rendering as unstyled plain text** (`tailwind.config.js`):

  - `ArticleView.tsx` uses Tailwind's `prose prose-slate dark:prose-invert` classes for markdown content, but the `@tailwindcss/typography` plugin was never installed
  - Headings, bullet lists, numbered lists, blockquotes, and code blocks were all present in the DOM (ReactMarkdown with remark-gfm parsed correctly) but had no visual styling
  - Installed `@tailwindcss/typography` and added `require('@tailwindcss/typography')` to the `plugins` array in `tailwind.config.js`

### Added

- **Inline total budget editor on Budget Overview card** (`app/components/budget/BudgetSummaryCard.tsx`, `app/api/budget.py`, `app/services/budgetApi.ts`, `app/admin/budget/page.tsx`):

  - Planners can now hover over the "Total Budget" metric in the Budget Overview card and click the pencil icon to edit the amount inline — saves via `PUT /admin/weddings/{wedding_id}/budget/total`
  - New backend endpoint `PUT /admin/weddings/{wedding_id}/budget/total` with `SetTotalBudgetRequest` model — writes directly to the wedding document's `total_budget` field
  - New frontend API method `budgetApi.setTotalBudget(token, weddingId, amount)`
  - Keyboard support: Enter to save, Escape to cancel
  - This supplements the existing total budget field on the Weddings configuration page, providing a quick shortcut without leaving the Budget dashboard

---

## [2.1.3] - 2026-03-03 — Email Service Type Safety & Root Admin Alerting

### Fixed

- **Type checker error on `email_service` calls** (`app/api/email_reminders.py`):

  - `email_service` is typed `Optional[ResendEmailService]` but four guard clauses only checked `if not email_available:` without narrowing the `None` type — added `or email_service is None` to guards at the `send_email_invites`, `send_email_invites_with_attachment`, `preview_invitation_email`, and `preview_reminder_email` endpoints to match the pattern already used in `send_email_reminders`, `send_individual_email`, and `get_email_logs`

- **Email service init error silently swallowed** (`app/api/email_reminders.py`):

  - The `except` block had a bare f-string `(f"Email service not available: {str(e)}")` that evaluated to nothing — replaced with `logger.error(...)` using the standard `logging.getLogger(__name__)` pattern used across other API modules

### Added

- **Root admin notification when email service fails to initialize** (`app/main.py`):

  - After environment validation in `lifespan()`, checks `email_available` flag and fires a `"critical"` priority in-app notification via `_create_root_admin_notification` from `config_validator.py` — covers runtime failures (bad API key, constructor exceptions) beyond the missing-env-var case already handled by the config validator

## [2.1.2] - 2026-03-03 — Email Reminders for Phoneless Guests, Plus-One Display Fix & Channel Picker

### Fixed

- **Email reminders not working for guests without phone numbers** (`app/admin/guests/page.tsx`, `app/api/email_reminders.py`, `app/admin/reminders/page.tsx`):

  - The reminder modal on the guests page was SMS-only — the send button was disabled when a guest had no phone number, and the handler only called the SMS endpoint (`/admin/reminders/send-to-guests`)
  - Added new `POST /admin/email/send-reminder-individual` endpoint in `email_reminders.py` with `IndividualEmailReminderModel` Pydantic model for sending a single reminder email via Resend
  - Rewrote `handleSendReminder` in `guests/page.tsx` to compute `sendSms`/`sendEmail` booleans based on selected channel and guest contact availability, then call the appropriate endpoint(s)
  - Fixed send button disabled logic from `!reminderModal.guest.phone` to `(!reminderModal.guest.phone && !reminderModal.guest.email)` so email-only guests can receive reminders
  - On the reminders page, fixed "Send Event Reminder" button disabled condition to allow email-only sends without requiring a custom message (`channel !== 'email'` guard)
  - Added error handling for email reminder API failures on the reminders page — errors were previously silently swallowed

- **Plus-one information not displaying in admin panel** (`app/services/admin_rsvp_service.py`, `app/api/plus_one.py`, `app/main.py`, `app/admin/guests/page.tsx`):

  - **Root cause (Coolify deployment):** `plus_one_router` was the only router registered outside the `/admin` prefix (at `/plus_one`). In the single-container Coolify deployment, the reverse proxy routes `/admin/*` to FastAPI but `/plus_one/*` was intercepted by Next.js, returning HTML instead of JSON — the frontend silently caught the error and showed `0/N` plus-ones
  - Registered `plus_one_router` under `/admin/plus-one` prefix in `main.py` (kept original `/plus_one` registration for public/backward-compat)
  - Updated frontend fetch URL from `/plus_one/wedding/` to `/admin/plus-one/wedding/` in `guests/page.tsx`
  - `admin_rsvp_service.py` used a dict comprehension `{guest_id: plus_one for ...}` which overwrote earlier entries when a guest submitted multiple plus-ones — changed to `setdefault(gid, []).append(p)` to preserve all plus-ones per guest
  - Added `plus_ones` array field to the RSVP response alongside backward-compatible singular `plus_one` field
  - Fixed broken `GET /plus_one/wedding/{id}` route in `plus_one.py` — was calling non-existent `get_plus_ones_by_wedding()` method, corrected to `get_plus_ones_by_wedding_id()`
  - Serialized `_id` fields to string in the plus-ones map to prevent ObjectId serialization errors

- **CSV export losing multiple plus-ones** (`app/services/admin_rsvp_service.py`):

  - `export_rsvps_to_csv` only exported the last plus-one per guest due to the same dict overwrite bug
  - Rewrote export to iterate `entry.get("plus_ones", [])` and create one CSV row per plus-one, with empty plus-one columns for guests without any

### Added

- **Channel picker for individual guest reminders** (`app/admin/guests/page.tsx`):

  - Planners can now choose to send reminders via **SMS**, **Email**, or **Both** using toggle buttons in the reminder modal
  - Channel picker auto-selects the best option based on guest contact info (e.g., defaults to Email if guest has no phone, SMS if no email, Both if both exist)
  - Send button label dynamically reflects selected channel ("Send via SMS", "Send via Email", "Send via SMS & Email")
  - Channel buttons are conditionally shown — SMS button hidden if no phone, Email button hidden if no email

- **Auto-refresh guest data on tab focus** (`app/admin/guests/page.tsx`):

  - Added `visibilitychange` event listener so guest/plus-one data automatically refreshes when the planner switches back to the admin tab — prevents stale data after submitting an RSVP in another tab

---

## [2.1.1] - 2026-03-03 — Seating DnD Fix, Dark Mode Animation Portal & Infinite Scroll

### Fixed

- **Dark mode toggle animation only visible on nav header** (`app/components/landing-page/AnchorNav.tsx`):

  - The veil sweep, shimmer line, and ring ripple overlays used `position: fixed; inset: 0` but were rendered as children of the `<nav>` element which has `backdrop-blur-sm` (`backdrop-filter: blur(4px)`)
  - Per CSS spec, `backdrop-filter` creates a containing block for fixed-position descendants, so the "full-screen" overlays were actually clipped to the nav bar's bounds
  - Wrapped animation overlays in `createPortal(... , document.body)` to render them at the root DOM level, escaping the nav's containing block
  - Veil sweep and ring ripple now correctly cover the entire viewport during dark mode transition

- **Seating drag-and-drop not working** (`app/admin/components/seating/TableNode.tsx`, `app/admin/seating/page.tsx`):

  - Reverted incorrect `closestCenter` collision detection — it always returned the nearest droppable even when dropping in empty canvas space, causing unintended guest assignments. Replaced with `pointerWithin` which only triggers when the pointer is actually inside a droppable zone
  - Separated draggable and droppable refs in `TableNode`: draggable ref on outer positioned wrapper (for table movement), droppable ref on inner card div (for receiving guest drops) — previously both were composed onto the same element causing self-collision
  - Removed `overflow-hidden` from the TableNode inner card which was clipping dragged guest elements when they moved outside the card boundary
  - Removed unused `MeasuringStrategy` import

- **Infinite scroll parallax jump at loop point** (`app/components/ui/InfiniteScrollWrapper.tsx`, `app/components/landing-page/Modern3DBackground.tsx`, `app/components/landing-page/LandingLayout.tsx`):

  - `Modern3DBackground` used raw `window.scrollY` for parallax offset, causing a visual jump of `height × 0.15` pixels when `InfiniteScrollWrapper` reset scroll position
  - Added `onPrimaryHeight` callback prop to `InfiniteScrollWrapper` using `ResizeObserver` to report primary content height
  - Added `loopHeight` prop to `Modern3DBackground` which normalizes `scrollY` with modulo (`scrollY % loopHeight`) for seamless looping
  - Switched parallax from React state updates (re-render per scroll) to a `requestAnimationFrame` loop writing directly to a DOM ref for smoother performance
  - Lifted `loopHeight` state in `LandingLayout` to connect the two sibling components

---

## [2.1.0] - 2026-03-03 — Stripe Audit, Error Boundaries, KB Permissions & Animation Fixes

### Added

- **ErrorBoundary wired into layouts** (`app/[slug]/layout.tsx`, `app/admin/layout.tsx`):

  - Connected the existing `ErrorBoundary.tsx` class component as a wrapper in both guest-facing and admin layouts
  - Created `app/[slug]/error.tsx` — Next.js route-level error boundary for guest pages with rose-themed UI and "Try Again" button
  - Created `app/admin/error.tsx` — Next.js route-level error boundary for admin pages with blue-themed UI and "Try Again" button
  - Guest and admin pages now have zero-downtime error recovery instead of full page crashes

- **PaymentCollectionButton wired into wedding management** (`app/admin/weddings/[id]/page.tsx`):

  - Connected the existing `PaymentCollectionButton.tsx` into the wedding detail page header actions (between "Seating Plan" and "Save Changes")
  - Planners can now collect payments from couples via Stripe directly from the wedding management page
  - Full payment flow verified end-to-end: button → modal → `POST /stripe/create-payment-intent` → shareable `/pay/{id}` link → Stripe Elements checkout → `/pay/success`

- **LiquidBackground wired into seating planner** (`app/admin/weddings/[id]/seating/page.tsx`):

  - Connected the existing Three.js `LiquidBackground.tsx` as a background layer behind the sidebar and canvas
  - Wrapped in `print:hidden` to exclude from print output
  - Content layers given `relative z-10` to sit above the background

- **Dark mode toggle animation** (`app/components/landing-page/AnchorNav.tsx`):

  - Ported veil sweep, shimmer line, and ring ripple animations from the orphaned `WeddingDarkModeToggle.tsx` into the existing compact `NavDarkModeToggle`
  - Full-screen veil sweep overlay with theme-aware gradient (reads `--theme-primary` / `--theme-secondary` CSS variables)
  - Shimmer line follows the veil sweep edge with glow effect
  - 3 staggered ring ripples expand outward from the button position
  - Button disabled during 1-second animation cycle; theme flips at 500ms midpoint
  - Added `AnimationStyles` component injecting global `@keyframes` via `<style jsx global>`

- **Knowledge Base seed script** (`app/scripts/seed_knowledge_base.py`):

  - 7 planner-facing articles seeded into `kb_articles` MongoDB collection on first deploy: Getting Started, Collect Payments, RSVP via SMS, Guest Management, Seating Planner, Theme Configuration, Troubleshooting
  - All articles marked `is_official: True`, `status: "published"`, authored by `root@thespecialwedding.io`
  - Idempotent — checks by slug before inserting to avoid duplicates on redeploy
  - Wired into `app/main.py` lifespan startup (after config validation, wrapped in try/except so failures don't prevent app start)

### Changed

- **Knowledge Base permissions locked to root admin** (`app/api/knowledge_base.py`, `app/admin/components/kb/KnowledgeBase.tsx`, `app/admin/components/kb/ArticleView.tsx`):

  - `POST /kb/articles` (create), `PUT /kb/articles/{id}` (update), `DELETE /kb/articles/{id}` (delete), `GET /kb/my-articles` — all changed from `require_admin_or_planner` to `require_root_admin`
  - Read endpoints and feedback endpoint remain `require_admin_or_planner` so planners can still browse and give feedback
  - Frontend: "Write Article" and "My Articles" buttons wrapped in `{isRootAdmin && ...}` conditional
  - Planner empty state updated to "No articles available in this category yet. Check back soon!"
  - `ArticleView.tsx` `canEdit` simplified from `isRootAdmin || author === currentUser` to just `isRootAdmin`

- **Stripe Checkout Session uses dynamic payment methods** (`app/services/stripe_service.py`):

  - Removed hardcoded `payment_method_types=["card"]` from `stripe.checkout.Session.create()`
  - Stripe now dynamically selects the optimal payment methods per customer from methods enabled in the Stripe Dashboard
  - Automatically enables Apple Pay, Google Pay, and other methods without code changes

- **Stripe exception imports modernized** (`app/services/stripe_service.py`):

  - Changed all `stripe.error.StripeError`, `stripe.error.InvalidRequestError`, `stripe.error.SignatureVerificationError` to direct imports: `from stripe import StripeError, InvalidRequestError, SignatureVerificationError`

### Fixed

- **Stripe `/config` endpoint blocked public payment page** (`app/api/stripe_payment.py`):

  - `GET /stripe/config` had `require_admin_or_planner` dependency, but the couple-facing payment page (`/pay/[id]`) calls it without authentication to initialize Stripe.js
  - Removed auth requirement — the publishable key (`pk_live_` / `pk_test_`) is designed by Stripe to be exposed in client-side code
  - Without this fix, every couple who clicked a payment link would get a 401 error and see a blank page

- **Dark mode animation veil color flipped mid-animation** (`app/components/landing-page/AnchorNav.tsx`):

  - Veil gradient was reading `!isDark` to determine color, but `isDark` flips at 500ms via `setTimeout`, causing React re-render that swapped the veil color halfway through the sweep
  - Added `goingDark` state that locks the transition direction at click time and doesn't change during animation
  - Veil gradient now reads `goingDark` instead of `!isDark`

- **Dark mode animation ring ripples popping in** (`app/components/landing-page/AnchorNav.tsx`):

  - Ring ripple elements had `opacity: 0` inline but keyframe `0%` set `opacity: 1`
  - During staggered animation delay (0s, 0.15s, 0.3s), the inline style took precedence, making rings invisible until delay ended then abruptly visible
  - Changed `animation-fill-mode` from `forwards` to `both` so keyframe `0%` values (including `opacity: 1`) apply during the delay period

### Dead Code Identified (pending removal)

- `app/components/GuestVerificationModalOld.tsx` — superseded by current verification flow
- `app/admin/components/AdminHeader.tsx` — unused legacy header
- `app/utils/tinyInvariantFallback.ts` — unused utility
- `app/admin/components/RootAdminGuard.tsx` — unused guard component
- `app/components/rsvp/SmsOptInForm.tsx` — SMS opt-in built directly into RSVPForm
- `app/components/landing-page/ParallaxSlideshow.tsx` — replaced by Modern3DBackground
- `app/admin/components/PermissionGate.tsx` — only 3 roles exist, no need for generic permission gate
- `app/dependencies/auth.py` — superseded by `auth_extended.py`
- `app/dependencies/auth_basic.py` — superseded by `auth_extended.py`

---

## [2.0.1] - 2026-03-03 — Guest-Facing Theme & Admin Modal Polish

### Changed

- **RSVP Modal Dynamic Theme Colors** (`app/components/RSVPModal.tsx`):

  - Replaced all hardcoded `wedding-rose` (#D4A5A5), `wedding-gold` (#E9C46A), and `wedding-blush` (#F8E8E8) Tailwind classes with dynamic colors pulled from the couple's `theme_config` (accent_color, secondary_color)
  - Added `hexToRgb()` and `lightenColor()` helper functions for computing rgba variants and blush tones at runtime
  - Sets CSS custom properties (`--rsvp-accent`, `--rsvp-accent-rgb`, `--rsvp-secondary`, `--rsvp-secondary-rgb`, `--rsvp-blush`) on `Dialog.Panel` so child components inherit theme colors via cascade
  - Background gradient glow now uses the couple's accent and secondary colors instead of hardcoded values
  - All buttons, error states, spinners, icons, and OTP input focus rings now reflect the couple's chosen palette
  - Safe fallbacks to original hardcoded values when `theme_config` is missing or incomplete

- **RSVP Form Dynamic Theme Colors** (`app/components/RSVPForm.tsx`):

  - Reads `wedding.theme_config` via the existing `useWedding()` hook
  - `FormCard` section titles use CSS variable `var(--rsvp-accent, #D4A5A5)` with built-in fallback
  - Focus rings use Tailwind's internal `--tw-ring-color` CSS variable override for dynamic accent color
  - Checkboxes and radios use the CSS `accent-color` property for native element theming
  - Error state inputs show dynamic accent-colored borders and backgrounds via `accentRgba()` helper
  - Event card hover borders, "Add Guest" button, and "Download Calendar Invite" button all use dynamic theme colors
  - All ~25 hardcoded `wedding-rose`/`wedding-gold`/`wedding-blush` references replaced with inline styles

- **Already RSVPed Screen Dynamic Theme Colors** (`app/components/AlreadyRSVPedScreen.tsx`):

  - Added `useContext(WeddingContext)` for null-safe theme access (avoids throwing unlike `useWedding()`)
  - Gradient accent bar, icon backgrounds, section titles, and buttons now use couple's theme colors
  - All ~8 hardcoded color references replaced

- **Seating Constraints Modal Redesign** (`app/admin/components/seating/SeatingConstraintsModal.tsx`):

  - Replaced green gradient header with app-standard purple/indigo gradient (`from-purple-600 to-indigo-600`) matching other admin modals
  - Added icon badge, subtitle, and styled close button in header
  - Constraint type toggles redesigned as card-style buttons (indigo for "Sit Together", rose for "Keep Apart")
  - Full-width dashed border "Add New Constraint" button with hover accent
  - Group hover reveal for delete buttons (Trash2 icon) instead of always-visible delete
  - Section headers with colored icon badges and count pills
  - Info footer showing constraint summary
  - `backdrop-blur-sm` overlay matching the app's modal design system
  - More breathing room with increased padding throughout

### Fixed

- **Hover Handler Event Target Safety** (`app/components/RSVPForm.tsx`, `app/components/AlreadyRSVPedScreen.tsx`):

  - Changed `e.target` to `e.currentTarget` in `onMouseEnter`/`onMouseLeave` handlers on "Download Calendar Invite Again", "+ Add Guest", and "View Wedding Page" buttons
  - Prevents broken hover effects if button content is ever wrapped in child elements (spans, icons), since `e.target` would reference the child instead of the button
  - Now consistent with event card hover handlers that already used `e.currentTarget`

- **Removed Dead Inline Style** (`app/components/RSVPForm.tsx`):

  - Removed `style={{ borderColor: undefined }}` from the "Download Calendar Invite Again" button — was a no-op that could confuse future maintainers

## [2.0.0] - 2026-03-01 — 1st Release: The Special Wedding SaaS Platform

The first production release of The Special Wedding as a full multi-tenant SaaS platform. This release transforms the original single-wedding website (v1.x at `thespecialwedding.com`) into a scalable platform for wedding planners at `thespecialwedding.io`. Built over 8+ months across 463 commits, consolidating all work from v1.3.0 through v1.7.0-rc.1.

**Key feature pillars:**

- **Multi-Tenant SaaS Architecture** — Org management, role-based access (Root Admin / Planner / Vendor), planner invitations with custom trial durations
- **Stripe Billing** — Subscription plans, checkout sessions, webhook idempotency, credit management
- **OTP Guest Verification** — Twilio SMS/email OTP for secure guest RSVP access, rate limiting, error-specific messages
- **AI-Powered Insights** — Google Gemini integration for budget insights, dashboard insights, seating optimization, contract drafting, with three-tier cache fallback
- **Vendor & Contract Management** — Contract creation, token-based vendor access, milestone payments, PDF generation, email delivery
- **Seating Chart System** — Drag-and-drop canvas, PDF/banner export (WeasyPrint), printable seating charts, capacity validation
- **Web Push Notifications** — VAPID-based browser push replacing self-hosted Ntfy, with per-device subscriptions
- **SMS Delivery Tracking** — Twilio webhook status callbacks, delivery health monitoring, phone status tracking, error classification
- **RSVP Enhancements** — Modal-based flow, already-RSVPed detection, Request RSVP Link for lost invitations, calendar ICS with timezone support, plus-one event inheritance
- **Activity & Audit Logging** — Comprehensive activity feed, TTL-based auto-cleanup, export/compliance endpoints
- **Cloudflare R2 Media Storage** — Gallery uploads with S3v4 signatures, presigned URLs, privacy-aware access
- **Coolify Deployment** — Single-server Docker deployment via `Dockerfile.coolify`, Cloudflare Workers for cron jobs
- **UI Overhaul** — Glassmorphism redesign, comprehensive dark mode, accessibility improvements, infinite scroll landing pages

### Added

- **AI Cache Stable Fallback Lookup** (`app/services/ai_cache_service.py`):

  - New `get_latest_cached_response(feature, tenant_id)` method finds the most recent cached AI response for a feature+tenant pair regardless of context hash
  - First tries non-expired entries, then falls back to expired entries as a last resort
  - Enables the "stale insights > no insights" resilience pattern across all AI features
- **Stable Cache Key Context for AI Endpoints** (`app/api/ai.py`):

  - Both `get_budget_insights` and `get_dashboard_insights` endpoints now pass a stable `cache_context` dict containing only primitive, non-volatile values (budget totals, guest counts, wedding date) to the AI service
  - Excludes volatile data (upcoming_tasks, vendor_payments, days_until_wedding) from cache key generation while still sending full context to the Gemini model for analysis
  - Prevents unnecessary cache misses on page reload when only dynamic/computed fields change
- **Three-Tier AI Fallback Chain** (`app/services/ai_service.py`):

  - Added `cache_context` parameter to `generate()` for stable cache key generation separate from the full AI context
  - Pre-API fallback: when exact cache key misses, checks for any recent cached response before making a Gemini API call
  - Post-failure fallback: on `InsufficientCreditsError` or generic exceptions, returns cached data with a warning instead of hard-erroring
  - Each fallback tier is logged with status (`cached`, `cached_fallback`, `error`) for operational visibility

### Fixed

- **AI Insights Fail to Reload After First Load** (`app/services/ai_service.py`, `app/api/ai.py`):

  - Root cause: volatile context data (upcoming_tasks, vendor_payments, computed days_until_wedding) changed on every page reload, generating a new SHA256 cache key hash each time, causing cache misses → Gemini API calls → credit burn → eventual credit exhaustion → hard error with no recovery
  - Fix: separated cache key generation (`cache_context` with stable primitives) from the full AI context sent to Gemini
- **AI Insights UI Destroyed on Error — Planner Dashboard** (`app/admin/planner/page.tsx`):

  - Error state no longer clears existing insights; previous insights remain visible below an amber warning banner
  - Added specific error messages for HTTP 402 (credits), 429 (rate limit), 503 (unavailable), 504 (timeout)
  - "Try again" retry button now passes `forceRefresh=true` so retry actually attempts a fresh Gemini call instead of hitting the cache again
- **AI Insights UI Destroyed on Error — Budget Page** (`app/admin/budget/page.tsx`):

  - Same pattern as planner dashboard: error no longer clears existing insights
  - Error display changed from red destructive alert to amber warning banner with retry button
  - Panel stays visible on error (`setShowAiInsights(true)` in catch block) so user sees error alongside any previous insights
  - Removed unnecessary toast notification for cached results
- **SMS Error Classifier Utility** (`app/utils/sms_error_classifier.py`):

  - New module that categorizes Twilio error codes into actionable groups: `temporary`, `permanent_recipient`, `account_level`, `compliance`, `unknown`
  - Helper functions: `classify_error()`, `should_retry()`, `is_account_level()`, `is_permanent_recipient()`, `is_compliance()`
  - Used by `_handle_delivery_failure()` in `twilio_webhooks.py` to route each failure to the correct handler
- **Phone Status Tracking on Guest Model** (`app/models/guest.py`):

  - Added `phone_status` field (values: `unknown`, `valid`, `invalid`, `landline`, `unreachable`, `unsubscribed`) and `phone_status_updated_at` to `GuestModel` and `UpdateGuestRequest`
  - Webhook failure handler now sets granular phone status based on Twilio error code (30006 → landline, 30003/30005 → unreachable, 21211/21612/21614 → invalid, 21610/30004/30007 → unsubscribed)
- **Planner Delivery Notification Helpers** (`app/services/planner_notification_service.py`):

  - `notify_delivery_failure()` — creates an in-app notification when an individual SMS or email delivery fails
  - `notify_bulk_delivery_summary()` — creates a summary notification after a bulk send with sent/failed/skipped counts
- **Skip Counters for Email Bulk Sends** (`app/services/email_service_resend.py`):

  - `send_rsvp_invitations()` now returns `skipped_no_email`, `skipped_no_token`, `skipped_opted_out`, and `unreachable_guests` alongside `sent`/`failed`
  - `send_reminders()` now returns `skipped_no_email` and `skipped_opted_out`
  - Planners can see exactly why guests were skipped instead of silent omission
- **Unreachable Guest Warnings in Reminders Page** (`app/admin/reminders/page.tsx`):

  - Wedding Details section now shows amber/red warnings for guests with no contact info, invalid/unreachable phones, or SMS opt-outs
  - Added `phone_status` and `sms_opt_in` to the `Guest` TypeScript interface
- **Skip Detail Display After Bulk Sends** (`app/admin/reminders/page.tsx`):

  - `handleSendInviteLinks`: Success message now shows skip breakdown (e.g., "Skipped: 3 no phone, 2 opted out")
  - `handleSendIndividualMessage`: Displays per-guest `failure_reasons` from the API response
  - All send handlers now call `fetchGuests()` after completion to refresh phone_status changes
- **Infinite Scroll Wheel Effect — SaaS Landing Page & Wedding Slug Page**:

  - Added continuous infinite scroll "wheel" effect where sections cycle in a smooth loop
  - **New file**: `app/components/ui/InfiniteScrollWrapper.tsx` — Reusable infinite scroll engine component
  - **SaaS landing page** (`app/page.tsx`): Rewritten to use `InfiniteScrollWrapper` for marketing sections
  - **Wedding slug page** (`app/components/landing-page/LandingLayout.tsx`): Rewritten to use `InfiniteScrollWrapper` for guest-facing sections
  - **Modified**: `app/components/landing-page/SectionWrapper.tsx` — Made `id` prop optional to support cloned sections
- **Banner-Quality Seating Chart Print** (`app/admin/components/seating/PrintableSeatingChart.tsx`):

  - **New file**: Full-screen print preview modal that renders positioned tables exactly as on the canvas
  - Opens a new browser window with complete HTML/CSS for clean printing
  - `@page` size set to 24×18 inches landscape for banner printing at print shops
  - `-webkit-print-color-adjust: exact` and `print-color-adjust: exact` for color fidelity
  - Wedding-themed design: gold (#E9C46A) decorative corner accents, navy (#1D3557) table headers, Playfair Display headings
  - Unseated guests shown in amber section at the bottom
  - Table cards display guest names with gold dot bullets and group labels
- **Seating Canvas Zoom Controls** (`app/admin/seating/page.tsx`):

  - Added zoom in/out/reset buttons for the seating canvas
  - Canvas uses CSS `transform: scale()` with delta adjustments for table positioning during drag
  - Stats bar showing tables, seated, unseated, and capacity counts

### Fixed

- **Unawaited Async Calls in Email Reminders API** (`app/api/email_reminders.py`):

  - Three endpoints were calling `email_service.send_rsvp_invitations()` and `email_service.send_reminders()` without `await`, returning coroutine objects instead of actual `{"sent": N, "failed": N}` results
  - All three calls now properly awaited
- **Sync Endpoint Calling Async Service — SMS Reminders** (`app/api/reminder_twilio.py`):

  - `send_reminder_twilio` was defined as `def` (sync) but calling an async service method
  - Changed to `async def` with `await`
- **Blocking `time.sleep()` in Email Service** (`app/services/email_service_resend.py`):

  - `time.sleep(0.6)` rate-limit delay was blocking the entire event loop for 0.6s per email
  - Replaced with `await asyncio.sleep(0.6)` in both `send_rsvp_invitations()` and `send_reminders()`
- **ObjectId Conversion Bug in Twilio Webhook Failure Handler** (`app/api/twilio_webhooks.py`):

  - `_handle_delivery_failure()` permanent_recipient and compliance handlers used `{"_id": guest_id}` where `guest_id` is a string — MongoDB `_id` fields require `ObjectId`, so these queries silently matched zero documents and never updated guest records
  - The broken fallback pattern `{"token": {"$exists": True}, "_id": guest_id}` was replaced with proper `_to_object_id(guest_id)` conversion
  - Extracted shared `_to_object_id()` helper to eliminate 5 duplicate inline `from bson import ObjectId` + try/except blocks across `_handle_delivery_failure`, `_attempt_email_fallback`, and `_notify_planner_delivery_failure`
- **Webhook Using Wrong Field for Phone Status** (`app/api/twilio_webhooks.py`):

  - Permanent recipient handler was setting `phone_verified: False` — a field that doesn't exist on the guest model
  - Now sets `phone_status` with granular values (`invalid`, `landline`, `unreachable`) plus `phone_status_updated_at`
  - Compliance handler now also sets `phone_status: "unsubscribed"` and records `sms_opt_out_reason` for all compliance codes (not just 21610)
- **Delivery Health Banner Mixing SMS and Email Metrics** (`app/admin/reminders/page.tsx`):

  - The "Last 24h Delivery" banner was computing rate from all `messageHistory` records including email logs, which inflated the "delivered" count via the `status === 'success'` fallback (email logs don't have Twilio's `delivery_status`)
  - Now pre-filters to SMS records only (`provider === 'twilio' || provider === 'telnyx'`) before computing delivery rate
  - Renamed banner to "Last 24h SMS Delivery" for clarity
- **N+1 Query in SMS Reminder Service** (`app/services/reminder_service_twilio.py`):

  - `send_reminders()` was doing a `find_one()` RSVP lookup per guest (N+1 queries)
  - Replaced with a single bulk query `rsvp_collection.find({"attending": event_type})` pre-loaded into a dictionary lookup
  - For a 200-guest wedding this reduces MongoDB round-trips from ~200 to 1
- **Seating Drag and Drop Not Working** (`app/admin/seating/page.tsx`, `app/admin/components/seating/*`):

  - **Problem**: Guests could not be dragged from the sidebar onto the seating canvas — dragged element was clipped by `overflow-hidden` on the sidebar container
  - **Root cause**: Missing `DragOverlay` component from `@dnd-kit/core`. Without it, the dragged DOM element stays within its parent container and gets clipped at the boundary
  - **Solution**: Added `DragOverlay` that renders a floating copy of the dragged item above all containers. Original item reduces opacity during drag (0.3 for guests, 0.5 for tables). Added `DragStartEvent`, `KeyboardSensor` for accessibility
  - **Impact**: Guests can now be smoothly dragged from sidebar to canvas and between tables
- **Seating Page Not Aligned with Dashboard Theme** (`app/admin/seating/page.tsx`, `app/admin/components/seating/*`):

  - **Problem**: Seating page used raw `bg-white dark:bg-slate-800` cards that didn't match the glass morphism pattern used across the planner dashboard
  - **Solution**:
    - All cards now use the dashboard glass pattern: `bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl border-white/50 dark:border-slate-700/50`
    - Removed heavy `LiquidBackground` (Three.js 3D sphere animation) — replaced with subtle CSS dot-grid pattern
    - `SeatingCanvas.tsx`: Dot grid, zoom support, empty state placeholder
    - `TableNode.tsx`: Glass theme, capacity utilization bar (green/amber/red), drag handle and delete icons on hover
    - `GuestItem.tsx`: Compact mode, drag opacity, glass styling
    - `Sidebar.tsx`: Glass theme, Lucide icons, group count badges, clear search button, `print:hidden`
    - `GlassButton.tsx`: Added `dark:` classes to `secondary` and `ghost` button variants
- **Dark Mode Text Invisible on Wedding Slug Page** (`app/hooks/useTheme.ts`, `app/styles/globals.css`, `app/components/landing-page/EventLocationSection.tsx`, `app/components/landing-page/OurStorySection.tsx`, `app/[slug]/page.tsx`):

  - **Problem**: On the couple's wedding slug page (e.g., `/emmanuel-peace`), many headings and text elements were invisible in dark mode. Section headings like "Wedding Details", "Our Story", "Wedding Party", venue names, dress code text, and side labels ("Bride's Side", "Groom's Side") all disappeared against dark backgrounds
  - **Root cause**: Two issues working together:
    1. The `.theme-primary`, `.theme-secondary`, and `.theme-accent` CSS classes used `color: var(--theme-primary)` with no dark mode variant — the theme primary color `#1e3a5f` (dark navy) was applied identically in both modes
    2. Multiple components used inline `style={{ color: theme?.primary_color }}` which overrides any Tailwind `dark:` class due to CSS specificity, making the globals.css fix insufficient on its own
  - **Solution**:
    - `useTheme.ts`: Added `lightenHex()` utility that lightens hex colors by a configurable percentage. Hook now computes and sets `--theme-primary-light`, `--theme-secondary-light`, `--theme-accent-light` CSS custom properties on the document root
    - `globals.css`: Added `:root` fallback values for the `-light` variables. Added `.dark` overrides for `.theme-primary`, `.theme-secondary`, `.theme-accent` (text) and `.theme-border-primary`, `.theme-border-secondary`, `.theme-border-accent` (border) that switch to the lightened variants
    - `EventLocationSection.tsx`: Removed 3 inline `style={{ color: theme?.primary_color }}` overrides (event dropdown, venue name, dress code). Replaced with `.theme-primary` and `.theme-border-primary` CSS classes
    - `OurStorySection.tsx`: Removed 5 inline style overrides — "Our Story" heading, "Wedding Party" heading, "Bride's Side" and "Groom's Side" subheadings, and member initial placeholders. Replaced with `.theme-primary`, `.theme-secondary`, `.theme-accent` classes
    - `app/[slug]/page.tsx`: Added `dark:` variants to all loading, error, verification, and "not found" states — backgrounds (`dark:from-slate-900 dark:to-slate-800`), text colors, cards, spinners, shadows. Applied to both the main component and `<Suspense>` fallback
  - **Impact**: All text on the wedding slug page is now readable in both light and dark mode, with theme colors automatically lightened for dark backgrounds

### Changed

- **OTP Verification API Optimization** (`app/services/otp_service.py`, `app/api/otp.py`, `app/components/RSVPModal.tsx`, `app/otp/verify/page.tsx`):

  - **Problem**: After OTP verification, frontend made a redundant API call to `/weddings/guest-access/{slug}/{token}` to fetch guest data that was already available
  - **Root cause**: `/otp/verify` endpoint only returned `{"message": "OTP verified"}` with no guest data, forcing frontend to re-fetch
  - **Solution**: Refactored `verify_otp_by_guest_id()` to return full guest data and auth method
  - **Backend changes**:
    - `generate_otp()` now stores `contact_type` in OTP record for accurate auth method tracking
    - `send_otp()` passes contact_type to generate_otp() and updates record on email fallback
    - `verify_otp_by_guest_id()` now returns `{success, guest, auth_method}` instead of `bool`
    - `/otp/verify` endpoint returns guest data and auth_method on success
  - **Frontend changes**:
    - RSVPModal and OTP verify page now use guest data directly from verify response
    - Eliminated redundant API call after OTP verification
  - **Impact**: Faster RSVP flow, reduced server load, accurate auth method tracking (phone_otp vs email_otp)
- **Platform Branding Update** (`app/layout.tsx`, `app/admin/components/Sidebar.tsx`, `public/favicon.svg`):

  - **Browser Favicon**: Added SVG favicon with interlinked rings icon in pink/rose gradient colors
  - **Root Layout Metadata**: Added Next.js metadata export with favicon (`/favicon.svg`) and apple touch icon (`/logo_all.png`)
  - **Admin Sidebar Logo**: Replaced Heart icon with "The Special Wedding" logo image
    - Expanded sidebar: Shows full logo with text (160x40)
    - Collapsed sidebar: Shows cropped logo icon (40x40)
  - **Files**:
    - Created `public/favicon.svg` - SVG rings icon for browser tab
    - Modified `app/layout.tsx` - Added metadata with icons configuration
    - Modified `app/admin/components/Sidebar.tsx` - Replaced Heart icon with NextImage component
  - **Impact**: Consistent branding across browser tabs and admin/planner dashboards

### Fixed

- **Onboarding Modal Not Staying Closed** (`app/admin/planner/page.tsx`):

  - **Problem**: The onboarding modal kept reappearing after planners dismissed it, making it impossible to close
  - **Root cause**: Race condition between the API call to mark onboarding complete and the profile refetch. If the profile returned before MongoDB reflected the update, the useEffect would reopen the modal with stale `onboarding_completed: false` data
  - **Solution**: Added `hasUserDismissedOnboarding` local state flag that tracks when the user has dismissed the modal in the current session, preventing the useEffect from reopening it even if profile data is momentarily stale
  - **Impact**: Planners can now dismiss the onboarding tour and it stays closed
- **Critical: Knowledge Base Model MRO Conflict** (`app/models/knowledge_base.py`):

  - **Problem**: App failed to import due to `TypeError: Cannot create a consistent method resolution order (MRO) for bases MongoModel, UserRelatedModel`
  - **Root cause**: `KnowledgeBaseArticleModel` inherited from both `MongoModel` and `UserRelatedModel`, but `UserRelatedModel` already inherits from `MongoModel` (diamond inheritance)
  - **Solution**: Changed inheritance to only `UserRelatedModel` since it already includes `MongoModel`
  - **Impact**: Knowledge base feature now loads correctly
- **Critical: Migration 006 Index Conflict Causing 502 Bad Gateway** (`app/utils/migrations.py`):

  - **Problem**: Production backend failed to start due to MongoDB `IndexOptionsConflict` error in migration 006
  - **Root cause**: Migration 006 created indexes without explicit names, while `database_indexes.py` created the same indexes with names (e.g., `idx_admin_activity_created`). MongoDB rejects duplicate indexes with different names.
  - **Solution**: Refactored migration 006 to only create TTL indexes (its unique purpose). Non-TTL indexes are now solely managed by `create_all_indexes()` in `database_indexes.py`.
  - **Changes**:
    - Removed duplicate non-TTL index creation for `admin_activity_log`, `activity_logs`, `audit_logs`, and `security_audit_logs`
    - Added `safe_create_ttl_index()` helper function with graceful error handling for "already exists" scenarios
    - Removed unused `down_func_name` variable (fixed linter warning)
  - **Impact**: Production backend starts successfully; planners can log in again

### Added

- **Seating Chart PDF Export Feature** (`app/services/seating_export_service.py`, `app/api/tables.py`, `app/admin/seating/page.tsx`):

  - **Purpose**: Allow planners to export seating charts as printable PDFs for large venue display posters
  - **New service** (`app/services/seating_export_service.py`):
    - `SeatingExportService` class with `generate_seating_chart_pdf()` method
    - Two layout styles: `visual` (floor plan with positioned tables) and `list` (table-by-table guest list)
    - Two paper sizes: `poster` (24×18 inches for venue display) and `tabloid` (11×17 inches for print shops)
    - Elegant styling with gold accents (#d4af37), wedding name header, and guest counts
    - HTML escaping via `_escape_html()` to prevent XSS in guest/table names
    - Supports round and rectangle table shapes with proper CSS styling
  - **New API endpoint** (`app/api/tables.py`):
    - `GET /admin/tables/{wedding_id}/export/pdf` - Export seating chart as PDF
    - Query parameters: `layout` (visual/list), `size` (poster/tabloid)
    - Returns PDF with `Content-Disposition: attachment` for download
    - Handles both string and ObjectId wedding formats for compatibility
  - **Frontend UI** (`app/admin/seating/page.tsx`):
    - New "Export PDF ▾" dropdown button in PageHeader actions
    - Poster and Tabloid size options with descriptions
    - Loading state during PDF generation
    - Dark mode support for dropdown menu
  - **Dependencies**:
    - Added `weasyprint>=62.0` to `requirements.txt`
    - Added system libraries to `Dockerfile.coolify`: libcairo2, libpango, libgdk-pixbuf2.0, libffi
  - **Impact**: Planners can print professional seating charts for venue escort tables
- **Comprehensive Activity Logging System for Planner Dashboard** (`app/services/activity_log_service.py`, `app/services/rsvp_service.py`, `app/api/guest.py`, `app/api/reminder_twilio.py`):

  - **Problem**: Planner activity dashboard (`/admin/planner/activity-log`) only showed support ticket logs - no RSVP, guest, or SMS activity
  - **New service** (`app/services/activity_log_service.py`):
    - Standardized `ActivityLogService` for logging to `activity_logs` collection
    - Activity type constants: `RSVP_RECEIVED`, `RSVP_UPDATED`, `GUEST_ADDED`, `GUEST_UPDATED`, `GUEST_DELETED`, `GUEST_IMPORTED`, `SMS_SENT`, `EMAIL_SENT`, `REMINDER_SENT`
    - Convenience methods: `log_rsvp_received()`, `log_guest_added()`, `log_guest_updated()`, `log_guest_deleted()`, `log_guests_imported()`, `log_sms_sent()`, `log_reminder_sent()`, `log_email_sent()`
  - **RSVP logging** (`app/services/rsvp_service.py`):
    - Added `log_rsvp_received()` call in `_notify_planner_rsvp()` method
    - Logs guest name, response status, plus-one count, and couple names
  - **Guest logging** (`app/api/guest.py`):
    - Added activity logging to `create_guest`, `update_guest`, and `delete_guest` endpoints
    - Logs guest name, changes made, and who performed the action
  - **SMS reminder logging** (`app/api/reminder_twilio.py`):
    - Added activity logging to `send_individual_reminders` endpoint
    - Groups SMS sends by wedding for cleaner activity feed
    - Logs recipient count, reminder type, and channel
  - **Impact**: Planner dashboard now shows comprehensive activity feed with RSVP submissions, guest management, and SMS sends
- **Activity/Audit Log Cleanup & Export Endpoints** (`app/api/admin_activity.py`, `app/api/admin_platform_metrics.py`):

  - **Problem**: No mechanism to prune old logs or export for audit compliance
  - **Admin activity log endpoints** (`app/api/admin_activity.py`):
    - `DELETE /admin/activity-log/cleanup` - Remove activities older than N days (default 90, range 7-365)
    - `GET /admin/activity-log/export` - Export activities as JSON or CSV with filters (action_type, entity_type, date range)
  - **Platform metrics endpoints** (`app/api/admin_platform_metrics.py`):
    - `DELETE /admin/platform/audit-logs/cleanup` - Cleanup audit logs (default 30 days)
    - `DELETE /admin/platform/security-logs/cleanup` - Cleanup security audit logs (default 180 days)
    - `GET /admin/platform/errors/export` - Export error logs as JSON or CSV
    - `POST /admin/platform/errors/{error_id}/acknowledge-and-delete` - Acknowledge single error with export
    - `POST /admin/platform/errors/acknowledge-and-delete-bulk` - Bulk acknowledge errors with export
  - **Export format**: JSON returns array of records; CSV returns downloadable format with headers
  - **Impact**: ROOT_ADMIN can now manage log retention and export for compliance auditing
- **TTL Indexes for Automatic Log Cleanup** (`app/core/database_indexes.py`, `app/utils/migrations.py`):

  - **Problem**: Activity and audit log collections grow indefinitely without cleanup
  - **New indexes** (`app/core/database_indexes.py`):

    - `create_admin_activity_log_indexes()` - Query indexes + 90-day TTL on `created_at`
    - `create_activity_logs_indexes()` - Query indexes + 90-day TTL on `timestamp`
    - `create_audit_logs_indexes()` - Query indexes + 30-day TTL on `timestamp`
    - `create_security_audit_logs_indexes()` - Query indexes + 180-day TTL on `timestamp`
    - `create_errors_indexes()` - Query indexes + 30-day TTL on `acknowledged_at`
  - **Migration 006** (`app/utils/migrations.py`):

    - Creates all TTL indexes on first deploy
    - Handles `IndexKeySpecsConflict` for existing indexes
  - **Retention policy**:

    | Collection              | TTL      | Reason                   |
    | ----------------------- | -------- | ------------------------ |
    | `admin_activity_log`  | 90 days  | Admin action history     |
    | `activity_logs`       | 90 days  | Planner activity         |
    | `audit_logs`          | 30 days  | High-volume HTTP logging |
    | `security_audit_logs` | 180 days | Security compliance      |
    | `errors`              | 30 days  | After acknowledgment     |
  - **Impact**: Database automatically prunes old logs, preventing storage bloat
- **Support Ticket Response Notifications for Planners** (`app/services/support_service.py`, `app/services/planner_notification_service.py`, `app/models/planner_notification.py`, `app/admin/notifications/page.tsx`):

  - **Problem**: When ROOT_ADMIN responded to a planner's support ticket, the planner received no notification
  - **New notification type**: Added `support_ticket_response` to `PlannerNotificationTypes` and `NotificationType` Literal
  - **New helper method**: `notify_support_ticket_response()` in `PlannerNotificationService` creates in-app notification with ticket details
  - **Modified `add_comment()` method**: Now triggers notification when ROOT_ADMIN responds (excludes internal comments and self-responses)
  - **Email notification**: New `_send_ticket_response_email()` method sends formatted HTML email to planner with ticket details and response content
  - **Activity logging**: Comments are now logged to `activity_logs` collection for audit trail
  - **Frontend**: Added `support_ticket_response` to TypeScript interface with teal color indicator and legend entry
  - **Flow**: ROOT_ADMIN adds comment → In-app notification + Email + Web Push (automatic via existing service) → Planner sees response in bell icon and receives email
  - **Guards**: Only non-internal comments trigger notifications; planner's own follow-up comments don't trigger self-notification
- **Request RSVP Link Feature** (`app/components/RequestRSVPLinkModal.tsx`, `app/components/landing-page/ThemedHeroSection.tsx`, `app/components/landing-page/LandingLayout.tsx`, `app/api/guest_verification.py`, `app/services/guest_verification_service.py`):

  - **Purpose**: Allow guests who lost their invitation link to request it via phone or email
  - **User flow**: Guest visits `/{slug}` landing page → clicks "Celebrate with us" button → enters phone/email → receives RSVP link via SMS or email
  - **New modal component** (`app/components/RequestRSVPLinkModal.tsx`):
    - Luxury/modern glassmorphism design with wedding theme colors
    - Phone/email toggle with auto-detection based on input
    - Loading spinner, success state, error handling
    - Dark mode support with gradient decorative border
  - **ThemedHeroSection update** (`app/components/landing-page/ThemedHeroSection.tsx`):
    - Added `onCelebrateClick?: () => void` prop to interface
    - Changed decorative div to interactive button with click handler
  - **LandingLayout integration** (`app/components/landing-page/LandingLayout.tsx`):
    - Added `showRSVPLinkModal` state management
    - Wired modal to ThemedHeroSection's `onCelebrateClick` callback
  - **New API endpoint** (`app/api/guest_verification.py`):
    - `POST /guests/request-rsvp-link` - Request RSVP link via phone or email
    - Pydantic model: `RequestRSVPLinkRequest` with `slug`, `contact`, `contact_type` fields
    - Always returns generic success message to prevent guest enumeration
  - **New service method** (`app/services/guest_verification_service.py`):
    - `request_and_send_rsvp_link()` - Core logic for guest lookup and link delivery
    - **Phone lookup**: Tries multiple stored formats (original, digits-only, E.164 with +1)
    - **Email lookup**: Case-insensitive MongoDB regex query
    - **SMS delivery**: Uses `TwilioReminderService._send_sms()`
    - **Email delivery**: Uses `ResendEmailService.send_email()` with HTML template
    - `_generate_rsvp_link_email_html()` - Professional email template with RSVP button
  - **Security features**:
    - Rate limiting: 3 requests per contact per 10 minutes (hashed contact)
    - Generic success messages prevent guest enumeration attacks
    - No cross-channel leakage (only sends to provided contact type)
    - Security event logging for audit trail
  - **Impact**: Guests can now recover their RSVP link without contacting the couple directly

### Changed

- **Defensive Field Access in Admin Activity Service** (`app/services/admin_activity_service.py`):

  - **Problem**: Direct dictionary access (`doc["field"]`) on MongoDB documents caused `KeyError` when documents had missing fields, resulting in 500 errors on activity log endpoints
  - **Fix**: Changed all field access in `get_activity_log()` and `get_recent_activities()` to use `.get()` with sensible defaults
  - **Example**: `doc["action_type"]` → `doc.get("action_type", "unknown")`
  - **Fields protected**: `admin_id`, `action_type`, `title`, `message`, `entity_type`, `entity_id`, `metadata`, `is_read`, `created_at`
  - **Impact**: Activity log endpoints now gracefully handle malformed or legacy documents
- **Enhanced Activity Type Color Mapping in Planner Dashboard** (`app/admin/planner/activity-log/page.tsx`):

  - **Problem**: Frontend only had colors for 4 activity types; new activity types showed default purple
  - **Added color mapping** for all activity types:
    - RSVP events: `rsvp_received` (green-500), `rsvp_updated` (green-400)
    - Guest events: `guest_added` (blue-500), `guest_updated` (blue-400), `guest_deleted` (blue-300), `guest_imported` (blue-600)
    - Communication: `email_sent` (yellow-500), `sms_sent` (orange-500), `reminder_sent` (amber-500)
    - Support: `support_ticket_created` (red-500), `support_ticket_comment` (red-400)
    - Wedding: `wedding_created` (indigo-500), `wedding_updated` (indigo-400)
  - **Impact**: Activity feed now shows visually distinct colors for each activity type
- **Platform Metrics Response Time Unit Standardization** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Eliminated redundant unit conversions**: Backend stored ms → API converted to seconds → Frontend converted back to ms
  - **New flow**: Backend stores ms → API returns ms directly → Frontend displays ms
  - **Field name changes** for clarity (explicit `_ms` suffix):

    | Old Name                      | New Name                           |
    | ----------------------------- | ---------------------------------- |
    | `avg_response_time`         | `avg_response_time_ms`           |
    | `min_response_time`         | `min_response_time_ms`           |
    | `max_response_time`         | `max_response_time_ms`           |
    | `p50`, `p95`, `p99`     | `p50_ms`, `p95_ms`, `p99_ms` |
    | `overall_avg_response_time` | `overall_avg_response_time_ms`   |
  - **Backend changes** (`app/api/admin_platform_metrics.py`):

    - Removed `/1000` divisions when returning response times
    - Updated field names in `_calculate_performance_metrics()` and `_calculate_endpoint_performance()`
  - **Frontend changes** (`app/admin/platform/page.tsx`):

    - Updated TypeScript interfaces (`PerformanceSummary`, `EndpointPerformance`) with new field names
    - Removed `* 1000` multiplications when displaying values
  - **Why**: Reduces cognitive overhead, prevents floating-point precision issues, and follows the principle of keeping data in its natural unit until display
- **AI Chat Service Availability & Health Monitoring** (`app/api/ai.py`):

  - **503 Service Unavailable**: When Google Gemini API is unavailable (network errors, API key issues, quota exceeded), the endpoint now returns proper 503 status instead of 500
  - **Why**: Frontend can detect 503 and show "AI temporarily unavailable" message instead of generic error; follows same pattern as Stripe, Telnyx, and email services in the codebase
  - **New endpoint**: `GET /admin/ai/health` - Health check for AI service monitoring
    - Returns: `{ status: "healthy"|"degraded"|"unhealthy", model, configured, api_key_set, error? }`
    - Tests actual API connectivity by making a minimal request to Gemini
    - Used by platform metrics dashboard for service status monitoring
  - **Enhanced error handling**:
    - `google.api_core.exceptions.GoogleAPIError` for API-level failures (quota, permissions)
    - `requests.exceptions.RequestException` for network connectivity issues
    - Both return 503 with `detail: "AI service temporarily unavailable"`
  - **Platform metrics integration**: AI health status now available alongside other service health checks (Stripe, Twilio, Web Push, Email)
- **Web Push Notifications (Replaces Ntfy)** (`app/services/web_push_service.py`, `app/api/web_push.py`, `app/admin/components/AccountSettingsModal.tsx`, `public/sw.js`):

  - **Complete replacement**: Removed self-hosted Ntfy server dependency in favor of standard Web Push API with VAPID authentication
  - **Why**: Ntfy required users to download a separate app, copy/paste subscription URLs, and perform manual setup - poor UX. Web Push is the industry standard (used by Gmail, YouTube, etc.) where users just click "Allow" and notifications work automatically
  - **New service** (`app/services/web_push_service.py`):
    - VAPID-based authentication using `pywebpush` library
    - Subscriptions stored in MongoDB `push_subscriptions` collection (per user, per device)
    - Methods: `save_subscription()`, `remove_subscription()`, `send_notification()`, `health_check()`
    - Handles expired subscriptions (404/410 responses) with automatic cleanup
  - **New API endpoints** (`app/api/web_push.py`):
    - `GET /admin/web-push/vapid-public-key` - Get VAPID public key for browser subscription
    - `POST /admin/web-push/subscribe` - Save browser push subscription
    - `DELETE /admin/web-push/unsubscribe` - Remove subscription by endpoint
    - `GET /admin/web-push/health` - Health check for monitoring
  - **Service worker** (`public/sw.js`):
    - Handles `push` events with JSON payload parsing
    - Handles `notificationclick` to focus/open app window
    - Handles `pushsubscriptionchange` for subscription renewal
  - **Frontend toggle fix** (`app/admin/components/AccountSettingsModal.tsx`):
    - Toggle now checks actual browser subscription state when modal opens
    - Previously showed DB preference which could be stale on different devices
    - Uses `navigator.serviceWorker.getRegistration()` and `pushManager.getSubscription()`
  - **Platform metrics updated** (`app/admin/platform/page.tsx`, `app/api/admin_platform_metrics.py`):
    - Changed `NtfyHealth` interface to `WebPushHealth`
    - Shows: configured, enabled, has_public_key, has_private_key, vapid_email, total_subscriptions
  - **Config validator updated** (`app/services/config_validator.py`, `app/api/config_errors.py`):
    - Replaced Ntfy alert sending with Web Push
    - Fixed type error: changed `False` sentinel to separate `_web_push_checked` flag
  - **Environment variables**:
    - Removed: `SERVICE_URL_NTFY`
    - Added: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL`
  - **Dependencies**: Added `pywebpush>=1.14.0` to `requirements.txt`
  - **Files removed**: `app/services/ntfy_service.py` (deleted)
  - **Generate VAPID keys**: `python -c "from pywebpush import generate_vapid_keys; k=generate_vapid_keys(); print(f'VAPID_PRIVATE_KEY={k[\"private_key\"]}\\nVAPID_PUBLIC_KEY={k[\"public_key\"]}')"`
- **RSVP Form Glassmorphism Redesign** (`app/components/RSVPForm.tsx`, `app/otp/verify/page.tsx`):

  - **Glass design system**: Complete redesign to match SaaS landing page aesthetic
  - **Dark theme**: `bg-slate-950` background with radial gradient overlays and subtle grid pattern
  - **Glass cards**: `backdrop-blur-xl`, `bg-white/5`, `border-white/10`, `rounded-3xl` styling
  - **FormCard component**: Glass card wrapper with wedding-rose uppercase tracking labels
  - **Events section**: Glass checkboxes with hover states (`hover:border-wedding-rose/40 hover:bg-wedding-rose/10`)
  - **Form inputs**: Dark glass inputs (`bg-white/5 text-white placeholder-slate-500`)
  - **Notifications section**: Glass opt-in cards with proper dark theme contrast
  - **Plus-ones section**: Glass guest cards with matching input styling
  - **Submit button**: `rounded-full` with `shadow-wedding-rose/40` glow effect
  - **Success state**: Glass card with wedding-rose accent checkmark and gradient bar
  - **OTP verify page**: Full glass design with matching background effects and animations
- **Plus-One Events Auto-Inherit** (`app/components/RSVPForm.tsx`):

  - Plus-ones now automatically inherit the main guest's selected events on RSVP submission
  - Previously: Plus-ones were submitted with empty `attending: []` array
  - Now: `filledPlusOnes.map(p => ({ ...p, attending: data.attending || [] }))`
  - Fixes "Attending: None" display issue in admin dashboard for plus-ones

### Fixed

- **Wedding ID Lookup Consistency** (`app/api/tables.py`, `app/api/guest_export.py`):

  - **Problem**: PDF export endpoints only queried weddings by string `_id`, failing for ObjectId-based weddings
  - **Solution**: Added dual-format lookup pattern: `ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id`
  - **Files updated**: Seating chart PDF export endpoint, Guest list PDF export endpoint
  - **Impact**: PDF exports now work regardless of whether wedding IDs are stored as strings or ObjectIds
- **Type Annotation Fixes in Twilio Reminder API** (`app/api/reminder_twilio.py`):

  - **Problem**: Pylance/mypy reported type errors for optional service instances and untyped dictionary
  - **Fix 1**: Added `Optional[TwilioReminderService]` and `Optional[TwilioRSVPReminderHelper]` type annotations for conditionally-initialized service variables
  - **Fix 2**: Added `dict[str, int]` type annotation to `wedding_sent_counts` dictionary
  - **Fix 3**: Removed unused `wedding_ids_logged` variable (dead code from previous implementation)
  - **Impact**: Clean type checking with no Pylance/mypy/Flake8 warnings
- **500 Errors on Activity Log Endpoints** (`app/services/admin_activity_service.py`, `app/api/admin_activity.py`):

  - **Root cause**: Direct dictionary access (`doc["field"]`) on MongoDB documents with missing fields raised `KeyError`, causing 500 responses on `/admin/activity-log` endpoints
  - **Fix** (`app/services/admin_activity_service.py`): Changed to defensive `.get()` access with defaults in `get_activity_log()` and `get_recent_activities()`
  - **Fix** (`app/api/admin_activity.py`): Added try-catch error handling to return graceful errors instead of 500
  - **Affected endpoints**: `GET /admin/activity-log`, `GET /admin/activity-log/recent`
  - **Impact**: Activity log endpoints now handle malformed documents gracefully and return empty results instead of crashing
- **RSVP Link SMS Status Check Bug** (`app/services/guest_verification_service.py`):

  - **Root cause**: Twilio `_send_sms()` returns `"status": "failed: {error}"` on failure, but code checked `!= "failed"` which always evaluated to `True`
  - **Fix**: Changed status check from `result.get("status") != "failed"` to `result.get("status") == "success"`
  - **Impact**: SMS send failures are now correctly detected and logged
- **RSVP Link SMS Phone Format Bug** (`app/services/guest_verification_service.py`):

  - **Root cause**: Service passed raw user input (e.g., `(319) 529-6088`) to Twilio, which added `+1` prefix creating invalid `+1(319) 529-6088`
  - **Fix**: Changed to pass `digits_only` (extracted digits) to Twilio, which then correctly formats as `+13195296088`
  - **Impact**: SMS delivery now works regardless of how user formats their phone number input
- **Gallery S3 Operations Failing on Cloudflare R2** (`app/services/gallery_upload_service.py`, `app/services/vendor_service.py`):

  - **Root cause**: Cloudflare R2 requires S3 Signature Version 4 (`s3v4`) for all operations, but boto3 defaults to v2
  - **Symptom**: `AccessDenied` errors on upload, list, and delete operations despite correct credentials
  - **Fix**: Added `config=Config(signature_version='s3v4')` to boto3 client initialization in both services
  - **Fix**: Added error code logging for better diagnostics on S3 operation failures
  - **Impact**: Gallery uploads, listing, and deletion now work correctly with Cloudflare R2
- **Gallery Image Delete Returning 405 Method Not Allowed** (`app/admin/gallery/upload/page.tsx`):

  - **Root cause**: Frontend called `DELETE /gallery` but the admin endpoint is registered at `DELETE /admin/gallery`
  - **Fix**: Changed delete endpoint from `/gallery` to `/admin/gallery` (line 313)
  - **Impact**: Planners can now delete gallery images from the upload management page
- **Private Wedding Gallery Page Returning 403 for Verified Guests** (`app/[slug]/gallery/page.tsx`):

  - **Root cause**: Gallery page was server-side rendered (SSR) and only called `GET /gallery` without guest verification
  - **Symptom**: Guest verifies on landing page → clicks "View Full Gallery" → 403 error because verification state wasn't persisted
  - **Fix**: Converted gallery page to client-side rendering (`'use client'`)
  - **Fix**: Added same verification flow as landing page using `WeddingContext` and `GuestVerificationModal`
  - **Fix**: Public weddings use `GET /gallery?wedding_slug={slug}`
  - **Fix**: Private weddings show verification modal, then use `POST /gallery/verified` with guest token/name/phone
  - **Alignment verified**:
    - `GuestVerificationModal` props: `slug`, `onVerified(wedding, guest?)` ✅
    - `WeddingContext` provides `privacy_mode` field ✅
    - `GalleryGrid` expects `images: {key, url}[]` ✅
    - Backend returns `[{key, url}]` from `gallery/{slug}/` prefix ✅
  - **Impact**: Guests on private weddings can now access the full gallery page after verification
- **Root Admin In-App Notifications Not Displaying** (`app/services/notification_service.py`, `app/services/support_service.py`, `app/utils/secure_error_handler.py`):

  - **Root cause**: Schema mismatch between notification creation and retrieval
    - Notifications created with `target_audience: "root_admin"` but fetched using `user_id` field
    - Root admin has no `user_id` in notifications collection - they use audience-based targeting
  - **Fix** (`app/services/notification_service.py`):
    - Added `get_root_admin_notifications()` method that queries by `target_audience: "root_admin"`
    - Updated `get_notifications()` to handle root admin case with proper audience query
    - Updated `mark_as_read()` and `mark_all_as_read()` to use audience-based queries for root admin
    - Added `delete_notification()` method with proper root admin support
  - **Fix** (`app/services/support_service.py`):
    - Changed notification `target_audience` from `"admin"` to `"root_admin"` for consistency
    - Root admin notifications now use correct audience identifier throughout
  - **Fix** (`app/utils/secure_error_handler.py`):
    - Changed notification `target_audience` from `"admin"` to `"root_admin"` for config error alerts
  - **Impact**: Root admin can now see notification bell count and all in-app notifications for:
    - Support ticket submissions from planners
    - Contact form submissions from public users
    - Configuration error alerts from the system
- **Notification System Schema Alignment** (Multiple files):

  - **API Validation** (`app/api/notification_management.py`):
    - Added `root_admin` to valid `target_audience` values in both `NotificationCreateModel` and `NotificationUpdateModel` validators
    - Previously API would reject notifications with `target_audience: "root_admin"` even though backend services created them
  - **TypeScript Interface** (`app/admin/notifications/page.tsx`):
    - Added `support_ticket`, `system_config`, and `sales_contact` to `PlannerNotification.type` union
    - These types are used by root admin notifications but were missing from the TypeScript interface
  - **Priority Value Standardization** (`app/models/support_ticket.py`, `app/api/reminder.py`, `app/api/twilio_webhooks.py`):
    - Changed default priority from `"normal"` to `"medium"` to match notification system
    - Standardized priority enum to `["low", "medium", "high", "urgent"]` across all systems
    - Previously support tickets used `"normal"` while notifications used `"medium"`
  - **ROOT_ADMIN_EMAIL Fallback** (`app/services/support_service.py`):
    - Updated fallback email domain from `.com` to `.io` to match SAAS platform domain
    - Changed from `thedeveloper@thespecialwedding.com` to `admin@thespecialwedding.io`
  - **Impact**: Full schema alignment between database models, API validation, and frontend TypeScript interfaces
- **Notification Recipient Dropdown Misaligned with Schema** (`app/admin/notifications/page.tsx`):

  - **Root cause**: Dropdown showed `"Trial Users"` and `"Premium Users"` options that don't exist in subscription schema
  - **Subscription status enum**: `PENDING_PAYMENT`, `TRIAL`, `ACTIVE`, `CANCELLED`, `EXPIRED`, `SUSPENDED` - no "premium"
  - **Fix**: Simplified dropdown to match backend `target_audience` values exactly:
    - `all` → All Users
    - `wedding_planners` → Wedding Planners
    - `vendors` → Vendors
  - **Fix**: Removed stale mapping logic - `recipientFilter` now passes directly to `target_audience`
  - **Fix**: Updated default state from `'all_users'` to `'all'`
  - **Impact**: Frontend dropdown now matches backend API validation and subscription schema
- **Root Admin Receiving Own Platform Notifications** (`app/services/notification_service.py`):

  - **Root cause**: Notification retrieval logic included `target_audience: "all"` for root admin
  - **Problem**: When root admin sends notification to "all users", they would also see it in their bell
  - **Fix**: Separated audience logic by role:
    - **Root admin** only sees: `target_audience: "root_admin"` (system alerts) + direct `user_id` targeting
    - **Planners/Vendors** see: `target_audience: "all"` + their role + direct targeting
  - **Fix**: Applied to both `get_user_notifications()` and `get_user_notification_count()` methods
  - **Impact**: Root admin notification bell only shows system alerts (support tickets, config errors, contact forms), not their own platform announcements
- **QR Code Preview Not Displaying in Guest Management** (`app/admin/guests/page.tsx`):

  - **Root cause**: The QR code modal used `<img src>` pointing directly to the authenticated API endpoint, but browsers don't send Authorization headers with image requests
  - **Fix**: Added state variables `qrImageUrl` and `qrImageLoading` to track fetched QR image
  - **Fix**: Added `useEffect` that fetches QR code with proper `Authorization: Bearer ${token}` header when modal opens
  - **Fix**: Converts response blob to object URL for display in the modal
  - **Fix**: Shows loading spinner while fetching, error state if fetch fails
  - **Fix**: Properly cleans up blob URL when modal closes to prevent memory leaks
- **Calendar Invite Download Not Working** (`app/components/RSVPForm.tsx`):

  - **Root cause 1**: Backend `EventDetailsModel.time` uses 12-hour format (`"3:00 PM"`) but frontend expected 24-hour (`"15:00"`)
  - **Root cause 2**: Backend model has no `endTime` field but frontend was trying to use it
  - **Root cause 3**: Invalid Date created when `eventDate` was undefined (`new Date("undefinedT15:00:00Z")`)
  - **Fix**: Added `parseTimeToISO()` helper that handles both 12-hour and 24-hour time formats
  - **Fix**: Use local time parsing instead of UTC to prevent timezone issues
  - **Fix**: Fallback to first event if no `white_wedding` event found, then to `wedding.date`
  - **Fix**: Default 3-hour event duration since backend doesn't have `endTime`
  - **Fix**: Proper ICS format with `\r\n` line endings and required headers (PRODID, CALSCALE, METHOD)
  - **Fix**: Added error handling and URL cleanup with `URL.revokeObjectURL()`
- **Calendar ICS Generates Only One Event with Wrong Time** (`app/components/RSVPForm.tsx`):

  - **Root cause 1**: `generateICS()` only picked one event (white_wedding or first) instead of all configured events
  - **Root cause 2**: `parseTimeToISO()` regex required colon - formats like "6PM" failed, defaulting to 12:00
  - **Symptom**: Planner configured Traditional (05/29 6PM), White Wedding (05/30 5PM), Reception - calendar showed only one event at 12:00PM
  - **Fix**: Enhanced `parseTimeToISO()` to handle hour-only formats: "6PM", "5pm", "6 PM" via new regex `/^(\d{1,2})\s*(am|pm)$/i`
  - **Fix**: Refactored `generateICS()` to loop through ALL `wedding.events` and create multiple VEVENT blocks
  - **Fix**: Each calendar event now has unique UID (`timestamp-index@wedding-rsvp`), event-specific title (e.g., "Traditional Ceremony - Peace & Emmanuel"), and correct time/location/attire
  - **Result**: Downloaded ICS now contains all wedding events with correct dates and times
- **Calendar ICS Missing Timezone Information** (`app/components/RSVPForm.tsx`, `app/models/wedding.py`, `app/types/wedding.ts`):

  - **Root cause**: ICS dates like `20260529T180000` had no timezone indicator - calendar apps interpreted in user's local timezone
  - **Impact**: Guests in different timezones would see wrong event times (e.g., 6 PM Chicago showing as 6 PM Lagos)
  - **Fix**: Added `timezone` field to `WeddingModel` (defaults to `America/Chicago`) and `EventDetailsModel` for per-event override
  - **Fix**: Added `timezone` field to TypeScript `Wedding` and `EventDetails` interfaces
  - **Fix**: ICS now includes `DTSTART;TZID=America/Chicago:20260529T180000` format with explicit timezone
  - **Fix**: Added `X-WR-TIMEZONE` header for calendar app compatibility (Google Calendar, Apple Calendar, Outlook)
  - **Result**: Calendar events now display in the correct wedding venue timezone regardless of guest's location

### Added

- **Wedding Timezone Configuration** (`app/models/wedding.py`, `app/types/wedding.ts`):

  - **New field**: `timezone` on `WeddingModel` - IANA timezone string (e.g., `America/Chicago`, `Africa/Lagos`)
  - **Default value**: `America/Chicago` (US Central Time) for backward compatibility
  - **Per-event override**: `EventDetailsModel.timezone` allows different timezones for events at different venues
  - **Frontend types**: Updated `Wedding` and `EventDetails` TypeScript interfaces
  - **Use case**: Planners can configure the correct timezone for their wedding venue, ensuring calendar downloads show accurate local times
- **Planner Timezone Preference** (`app/models/user_extended.py`, `app/admin/users/page.tsx`, `app/admin/saas/page.tsx`):

  - **New field**: `timezone` on `UserModel` - IANA timezone for display preferences (default: `America/Chicago`)
  - **Frontend types**: Added `timezone` to `Planner` and `WeddingPlanner` TypeScript interfaces
  - **Use case**: Planners see timestamps in their preferred timezone across the dashboard
- **Admin Dashboard Timestamp Consistency** (`app/utils/dateFormat.ts`, 20+ admin pages):

  - **Problem**: ~27 instances of browser-local `.toLocaleString()` caused different users to see different times for the same record
  - **Root cause**: Mix of UTC formatting (centralized utility) and browser-local formatting (direct `.toLocaleString()`)
  - **Enhanced utility** (`app/utils/dateFormat.ts`):
    - Added `getTimezoneAbbreviation()` - Gets timezone abbreviation (CST, EST, WAT) for display
    - Added `formatDateTimeWithTz()` - Format with timezone suffix (e.g., "Jan 30, 2026, 3:00 PM CST")
    - Added `formatAdminTimestamp()` - Primary function for admin dashboard timestamps with timezone indicator
    - Added `formatAdminDate()` - Date-only formatting for admin displays
    - Added `formatListTimestamp()` - Shorter format for tables/lists
    - All functions accept optional timezone parameter (defaults to `America/Chicago`)
  - **Pages updated**:
    - Root admin: `app/admin/page.tsx`, `app/admin/dashboard/page.tsx`
    - Weddings: `app/admin/weddings/page.tsx`, `app/admin/weddings/[id]/page.tsx`
    - Billing: `app/admin/billing/page.tsx`, `app/admin/money/page.tsx`, `app/admin/planner/billing/page.tsx`
    - Vendors: `app/admin/vendors/contracts/[id]/page.tsx`, `app/admin/vendors/contracts/new/page.tsx`, `app/admin/vendors/components/PaymentMilestones.tsx`, `app/admin/vendors/components/VendorPaymentModal.tsx`
    - Users: `app/admin/users/page.tsx`
    - Planner: `app/admin/planner/calendar/page.tsx`, `app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`
    - Forms: `app/admin/forms/[id]/edit/page.tsx`
    - Notifications: `app/admin/notifications/page.tsx`
    - Packages: `app/admin/packages/[id]/send/page.tsx`
  - **Result**: All admin timestamps now show consistent timezone-aware formatting with abbreviation suffix (e.g., "Jan 30, 2026, 3:00 PM CST")
- **Already RSVPed Detection** (`app/components/AlreadyRSVPedScreen.tsx`, `app/otp/verify/page.tsx`, `app/services/guest_verification_service.py`):

  - **Problem solved**: Guests re-visiting RSVP link after submission would go through OTP verification again (Twilio SMS cost ~$0.0079 each)
  - **Backend enhancement**: `get_rsvp_access_by_token()` now checks for existing RSVP in `rsvps` collection
    - Returns `rsvp: { has_rsvp, submitted_at, attending, dietary, plus_ones }` in response
    - Fetches associated plus-ones from `plus_ones` collection
  - **New component**: `AlreadyRSVPedScreen` shows existing RSVP status with glass design
    - Displays guest name, submission date, events attending, dietary restrictions
    - "Edit My RSVP" button to switch to edit mode
  - **Edit mode flow**: `editMode` state allows guests to modify their existing RSVP
  - **Cost savings**: Prevents unnecessary OTP SMS costs for return visitors
- **Twilio SMS Delivery Tracking** (`app/api/twilio_webhooks.py`, `app/services/reminder_service_twilio.py`, `app/core/database_indexes.py`):

  - **StatusCallback webhooks**: Track SMS delivery status (delivered/failed/undelivered) via Twilio webhooks
    - `POST /webhook/twilio/status` - Receives delivery status updates from Twilio
    - Updates `reminders_sent` collection with `delivery_status`, `delivery_events`, and `error_code`
  - **MessageSid tracking**: `_send_sms()` now returns dict with `message_sid` for delivery correlation
    - Log records include `message_sid`, `delivery_status`, `delivery_status_updated_at`, `delivery_events` fields
  - **Database indexes**: Added sparse unique index on `message_sid` field in `reminders_sent` collection
  - **Incoming SMS webhook**: `POST /webhook/twilio/incoming` handles STOP/HELP/START and support messages
    - Routes messages to assigned wedding planner or logs to errors collection for root admin
- **Twilio Platform Monitoring** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Backend health check**: `_check_twilio_health()` function checks:
    - Environment variables: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_MESSAGING_SERVICE_SID`, `TWILIO_STATUS_CALLBACK_URL`
    - 24h delivery stats from `reminders_sent` collection: total sent, delivered, failed, pending, delivery rate
    - Status: healthy (>=95%), degraded (>=80%), unhealthy (<80%)
  - **Frontend dashboard card**: New "SMS Service (Twilio)" card in External Services section
    - Shows configuration status, status callback status, delivery stats, and delivery rate percentage
    - Color-coded status indicators and warnings for missing configuration
- **Settings URL Helper** (`app/core/config.py`):

  - Added `get_required_url(url_name)` method to Settings class
  - Returns configured URL or raises ValueError if not set
  - Supports `FRONTEND_URL`, `NEXT_PUBLIC_API_BASE_URL`, `MEDIA_DOMAIN`

### Fixed

- **OTP Rate Limiting Now Uses Settings** (`app/services/otp_service.py`):

  - Fixed hardcoded `timedelta(minutes=4)` rate limit logic to use `settings.rate_limit_auth_period`
  - Rate limiting now uses `created_at` timestamp instead of confusing `expires_at` calculation
  - Both `send_otp()` (line 93) and `send_otp_by_contact()` (line 253) now use configurable rate limit
  - Default: 60 seconds from `RATE_LIMIT_AUTH_PERIOD` env variable
  - Clearer logging: shows seconds since last OTP was sent
- **Admin RSVP Service Async Bug** (`app/services/admin_rsvp_service.py`):

  - Fixed `get_all_rsvps()` using synchronous `list()` with async Motor driver
  - Changed `list(self.guest_collection.find(query))` to `await self.guest_collection.find(query).to_list(length=None)`
  - This bug caused the planner dashboard to fail silently when fetching RSVPs
- **OTP Service Dict Handling** (`app/services/otp_service.py`):

  - Fixed `send_otp()` and `send_otp_by_contact()` to handle dict return from `_send_sms()`
  - Extracts status with `result.get("status") if isinstance(result, dict) else result`
  - Prevents 500 errors when sending OTP via Twilio
- **Removed Slack Integration** (`app/api/twilio_webhooks.py`, `app/api/reminder.py`):

  - Replaced Slack webhook notifications with errors collection logging
  - Unassigned support tickets now appear in platform monitoring Errors tab
  - Root admin gets email notification for unassigned tickets
- **Seating Orchestration Enhancements** (`app/api/tables.py`, `app/admin/weddings/[id]/seating/page.tsx`, `app/admin/components/seating/*`, `app/core/database_indexes.py`):

  - **Server-side capacity validation**: API now rejects guest assignments that would exceed table capacity
    - Returns clear error message: "Cannot assign guests: table capacity is X, would have Y guests after assignment"
    - Prevents over-seating at the API level, not just frontend warnings
  - **Database indexes for seating performance**:
    - `idx_table_wedding_id` on `tables` collection for fast table listing
    - `idx_table_id` on `guests` collection for finding guests at a table
    - `idx_wedding_table` compound index for seating page queries
  - **Batch AI suggestion applications**: Changed from sequential to parallel API calls using `Promise.all()`
    - Significantly faster when applying AI seating suggestions across many tables
  - **Reduced motion accessibility**: LiquidBackground now uses `useReducedMotion` from framer-motion
    - Users with `prefers-reduced-motion: reduce` see a static gradient instead of 3D animation
  - **Capacity warning on drag-over**: Visual indicator when dragging guest to a full table
    - Orange highlight with warning icon and seat count when table is at capacity
  - **Full dark mode support for seating components**:
    - SeatingCanvas, TableNode, Sidebar, and all seating UI elements now support dark mode
    - Header bar, error banner, and modal all have proper `dark:` variants
  - **Frontend error handling**: `useTables` hook now parses API error details
    - Shows actual capacity error messages instead of generic "Failed to assign guests"
  - Validated against Tailwind CSS, dnd-kit, and framer-motion documentation via context7 MCP
- **Guest Export Features** (`app/api/guest_export.py`, `app/services/guest_export_service.py`, `app/admin/guests/page.tsx`):

  - **Individual QR Preview**: View/download QR code for single guest (for physical RSVP cards)
    - `GET /admin/guests/{guest_id}/qr` - Returns QR PNG inline with caching
    - `GET /admin/guests/{guest_id}/qr/download` - Returns QR PNG as attachment for download
    - QR codes link to: `{FRONTEND_URL}/{slug}/invite/{token}` (RSVP page)
  - **Guest List PDF Export**: Printable PDF of guest table
    - `GET /admin/guests/export/pdf` - Returns styled PDF with guest details
    - Columns: Name, Phone, Email, Group, RSVP Status, Dietary
    - Footer shows summary stats (Total, Attending, Pending, Declined)
    - Uses WeasyPrint with lazy import pattern (matches contract_pdf_service.py)
  - **Bulk QR ZIP Download**: Download QR codes as PNG files in a ZIP archive
    - `POST /admin/guests/export/qr-zip` - Returns ZIP of QR PNGs
    - Supports all guests or selected guests via `guest_ids` parameter
    - Files named: `GuestName_token.png` for uniqueness
  - **Frontend Integration** (`app/admin/guests/page.tsx`):
    - [QR] button on guest row actions opens modal with preview + download
    - Export dropdown with PDF, CSV, and ZIP options
    - "Download QR Codes" button in bulk actions bar for selected guests
    - QR Preview Modal with instant display and download button
  - **New Service**: `GuestExportService` with methods:
    - `generate_qr_code(url)` - Generate QR code PNG bytes using qrcode library
    - `build_rsvp_url(slug, token)` - Build RSVP URL for guest
    - `generate_guest_list_pdf(wedding_id, wedding_name)` - Generate styled PDF
    - `generate_guests_qr_zip(guests, slug)` - Generate ZIP archive
    - `get_single_guest_qr(guest_id, wedding_id)` - Get single guest QR with filename
  - **Security**: All endpoints require `require_wedding_planner_only` + `check_wedding_access()`
  - Validated against qrcode, weasyprint, and FastAPI documentation via context7 MCP
- **Bulk Error Acknowledgement Endpoint** (`app/api/admin_platform_metrics.py`):

  - New `POST /admin/platform/errors/acknowledge-bulk` endpoint for acknowledging multiple errors in a single API call
  - Accepts `BulkAcknowledgeRequest` with list of `error_ids`
  - Uses MongoDB `update_many` with `$or` operator to match both `error_id` and `_id` fields
  - Returns `acknowledged_count` and `requested_count` for accurate feedback
  - Replaces 200+ individual API calls with a single operation
  - Validated against PyMongo official documentation via context7 MCP
- **Cursor-Based Pagination for Error Dashboard** (`app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - Replaced `skip()`-based pagination with cursor-based pagination using `_id` range queries
  - **Backend changes:**
    - New `cursor` parameter (error_id from last item of previous page)
    - New `direction` parameter (`'next'` for older, `'prev'` for newer errors)
    - Uses `$lt`/`$gt` operators on indexed `_id` field for O(1) performance
    - Returns `next_cursor` and `prev_cursor` for navigation
  - **Frontend changes:**
    - Replaced page state with `cursorHistory` array for backward navigation
    - New handlers: `handleNextPage()`, `handlePrevPage()`, `handleFirstPage()`
    - Updated pagination controls to use cursor-based navigation
  - **Performance improvement:**
    - `skip()`: O(n) - degrades linearly with offset (page 1000 scans 1000*limit documents)
    - Cursor: O(1) - constant time regardless of how deep into dataset
  - Validated against MongoDB and React official documentation via context7 MCP
- **Error Table Endpoint Column Tooltip** (`app/admin/platform/page.tsx`):

  - Added `title` attribute and `cursor-help` class to truncated endpoint column
  - Full endpoint path now visible on hover for better UX
- **Plus-One Email and Opt-In Fields** (`app/models/plus_one.py`, `app/models/rsvp.py`, `app/services/rsvp_service.py`, `app/services/email_service_resend.py`, `app/components/RSVPForm.tsx`, `app/admin/guests/page.tsx`):

  - Added `email` field to plus-ones so planners can contact them directly
  - Added `sms_opt_in` and `email_opt_in` fields with consent tracking timestamps
  - New fields in `PlusOneModel`: `email`, `sms_opt_in`, `sms_opt_in_date`, `sms_opt_out_date`, `email_opt_in`, `email_opt_in_date`, `email_opt_out_date`
  - Frontend RSVP form now collects plus-one email and shows opt-in checkboxes with compliant consent language
  - Email reminder service (`send_reminders`) now supports `target_group: "plus-ones"` and `"all"` to send reminders to opted-in plus-ones
  - Admin guests page displays plus-one contact info (phone, email) and opt-in status badges (SMS, Email)
  - SMS reminder service already had partial plus-one support; now properly tracks opt-in status
- **Account Setup Name Collection** (`app/api/user_management.py`, `app/setup-account/page.tsx`):

  - Added `first_name` and `last_name` fields to `AccountSetupModel` with validation
  - Frontend form now collects planner's name during account setup
  - Backend passes name fields to `complete_account_setup()` service method
  - Planners no longer show as "Unnamed Planner" after completing account setup
- **Password Reset Flow** (`app/forgot-password/page.tsx`, `app/reset-password/page.tsx`, `app/api/user_management.py`, `app/services/user_management_service.py`):

  - Complete forgot password / reset password functionality for users who cannot log in
  - New API endpoints:
    - `POST /forgot-password` - Request password reset email (public, no auth)
    - `GET /reset-password/validate/{token}` - Validate reset token (public)
    - `POST /reset-password` - Reset password with token (public)
  - New frontend pages: `/forgot-password` (email input) and `/reset-password` (token validation + password entry)
  - Added "Forgot password?" link to admin login page
  - New database fields in `users` collection: `password_reset_token`, `password_reset_expires`, `password_reset_requested_at`
  - Security: Tokens expire after 1 hour, single-use, same response regardless of email existence, confirmation email after reset
  - Reference: [OWASP Password Reset Guidelines](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
- **Admin Activity Logging** (`app/services/admin_activity_service.py`, `app/api/admin_activity.py`, `app/admin/page.tsx`):

  - New service to track all important admin actions for audit and visibility
  - Activity types: `invitation_sent`, `invitation_resent`, `invitation_cancelled`, `planner_suspended`, `planner_activated`
  - New API endpoints:
    - `GET /admin/activity-log` - Paginated activity log (ROOT_ADMIN)
    - `GET /admin/activity-log/recent` - Recent activities for dashboard (ROOT_ADMIN)
  - Added "Recent Admin Activity" section to Platform Health Overview dashboard
  - New collection `admin_activity_log` with fields: `admin_id`, `action_type`, `title`, `message`, `metadata`, `created_at`
- **Invitation Management Enhancements** (`app/api/user_management.py`, `app/services/user_management_service.py`, `app/admin/users/page.tsx`):

  - New API endpoints for invitation visibility and control:
    - `GET /admin/invitations` - List invitations with status filtering (ROOT_ADMIN)
    - `GET /admin/invitations/stats` - Invitation counts by status (ROOT_ADMIN)
    - `POST /admin/invitations/{id}/resend` - Resend invitation email with new token (ROOT_ADMIN)
    - `POST /admin/invitations/{id}/cancel` - Cancel pending invitation (ROOT_ADMIN)
  - Added "Pending Invitations" stats card to Planner Management page
  - Added collapsible pending invitations section with email status indicators (sent/failed)
  - Enhanced `user_invitations` collection: `email_status`, `email_sent_at`, `resend_count`, `last_resent_at`, `cancelled_at`, `cancelled_by`
- **Push Notifications Toggle** (`app/admin/components/AccountSettingsModal.tsx`, `app/api/user_management.py`, `app/models/user.py`, `app/services/planner_notification_service.py`):

  - Added toggle switch in Account Settings modal for planners to enable/disable push notifications
  - New `push_notifications_enabled` field in `ProfileInfoModel` (defaults to `True` - opt-out model)
  - New `_check_push_enabled()` method in planner notification service checks user preference
  - Ntfy push notifications are skipped if planner has disabled them
  - Gives planners control over mobile/desktop push alerts while keeping in-app notifications active
- **Ntfy Push Notification Diagnostics & Error Logging** (`app/services/ntfy_service.py`, `app/api/admin_platform_metrics.py`, `app/admin/platform/page.tsx`):

  - **Health check endpoint integration**: Ntfy service status now visible in Platform Monitoring dashboard
  - New `health_check()` method in `NtfyNotificationService`:
    - Tests DNS resolution for ntfy server hostname
    - Tests HTTP connectivity with 5-second timeout
    - Reports status: `healthy`, `disabled`, `timeout`, `unreachable`, `auth_required`, or `error`
    - Returns diagnostic info: `configured`, `enabled`, `dns_resolved`, `connection_successful`, `server_url`, `error`
  - **Error logging to database**: Failed push notifications now logged to `errors` collection
    - New `_log_notification_failure()` method logs failures with topic, title, HTTP status, and server URL
    - Errors appear in Platform Monitoring → Errors tab for admin visibility
    - Severity set to `warning` with `source: "ntfy_service"`
  - **Backend integration** (`admin_platform_metrics.py`):
    - `GET /admin/platform/metrics` now includes `services.ntfy` health status
    - Metrics snapshot includes ntfy status for historical tracking
  - **Frontend integration** (`platform/page.tsx`):
    - New "External Services" card in Health tab showing ntfy status
    - Displays: status badge (healthy/disabled/error), configured, DNS resolved, connected, server URL
    - Shows error message with warning icon when ntfy is unhealthy
  - **Root cause identified**: Coolify domain misconfigured as `https://...:80` (HTTPS uses port 443, not 80)
    - Fix: Update Coolify environment variable to `SERVICE_URL_NTFY=http://notify.thespecialwedding.io`
  - Verified ntfy API format against official ntfy documentation via context7 MCP

### Fixed

- **Coolify Deployment — Missing Environment Variables** (`Dockerfile.coolify`, `.github/workflows/deploy.yml`):

  - **Dockerfile.coolify**: Added `BACKUP_SECRET`, `FRONTEND_URL`, `CRON_SECRET` as ARG/ENV declarations for Coolify injection
  - **deploy.yml**: Added `BACKUP_SECRET` and `FRONTEND_URL` to VPS deployment .env file
  - **deploy.yml**: Restricted workflow to only trigger on `feature-twilio-otp-improvements-final-submitted` branch (excluded `main`)
  - **deploy.yml**: Added comment clarifying `DEPLOYMENT_TARGET='coolify'` skips VPS SSH deployment
  - **Impact**: Backup cron authentication and guest export QR code URL generation now work correctly in Coolify deployments
  - Verified against GitHub Actions and Docker official documentation via context7 MCP
- **Cloudflare Workers — Documentation Comment Mismatch** (`cloudflare-workers/metrics-snapshot-cron.js`):

  - Documentation comment referenced `API_URL` but code correctly used `NEXT_PUBLIC_API_BASE_URL`
  - Fix: Updated comment to match actual environment variable name
- **Security: Delete table wedding scope** (`app/api/tables.py`):

  - Fixed guest unassignment query to include `wedding_id` filter when deleting tables
  - Prevents theoretical cross-wedding data leak
  - Query now: `{"table_id": table_id, "wedding_id": table["wedding_id"]}`
- **CRITICAL: Complete RSVP Invite Flow Broken — 7 Bugs** (`app/api/wedding.py`, `app/[slug]/invite/[token]/page.tsx`, `app/components/OTPFlow.tsx`, `app/otp/verify/page.tsx`, `app/admin/guests/page.tsx`, `app/admin/reminders/page.tsx`):

  - **Root cause**: `/weddings/slug/{slug}` endpoint was rewritten for security but stripped the response from `get_wedding_privacy_info()`, removing `id` and `events` that the invite page depends on
  - **Impact**: Guests clicking RSVP links saw 404 pages; SMS templates were missing the domain URL
  - **Bug 1 — Invite page 404** (`app/api/wedding.py:228`): Endpoint returned `{couple_names, slug, privacy_mode}` instead of full `privacy_info` response. Frontend sent `wedding_id=undefined` to guest endpoint → 404
    - Fix: Return `privacy_info` directly (already security-filtered by `get_wedding_privacy_info()`)
  - **Bug 1b — Frontend ID mismatch** (`app/[slug]/invite/[token]/page.tsx:27`): Used `wedding._id` but `get_wedding_privacy_info` returns `id` (no underscore)
    - Fix: `wedding._id` → `wedding.id`
  - **Bug 2 — OTPFlow wrong guest ID** (`app/components/OTPFlow.tsx:21,30`): Used `guest._id` but backend returns `guest.id`
    - Fix: `guest._id` → `guest.id`
  - **Bug 3 — OTP client API paths don't exist** (`app/components/OTPFlow.tsx:18`, `app/otp/verify/page.tsx:36,48,68`): Client-side fetches to `/api/otp/request`, `/api/otp/verify`, `/api/guest/invite/{token}` — no Next.js route handlers exist for these paths
    - Fix: Use `process.env.NEXT_PUBLIC_API_BASE_URL` as base URL for all client-side backend calls
  - **Bug 4 — Missing wedding_id in guest fetch** (`app/otp/verify/page.tsx:48`): Called `/api/guest/invite/{token}` without required `wedding_id` query param → 422
    - Fix: Use `/weddings/guest-access/{slug}/{token}` endpoint which returns both wedding and guest
  - **Bug 5 — RSVPForm missing WeddingContext** (`app/otp/verify/page.tsx:86`): `/otp/verify` page is NOT under `[slug]/` layout, so no WeddingContext provider exists → runtime error
    - Fix: Wrap RSVPForm in `<WeddingContext.Provider>` with wedding data fetched via guest-access endpoint
  - **Bug 6 — SMS template missing domain** (`app/admin/guests/page.tsx:610,2209`): `process.env.FRONTEND_URL` used in `'use client'` component — undefined in browser (no `NEXT_PUBLIC_` prefix)
    - Fix: `process.env.FRONTEND_URL || ''` → `window.location.origin`
  - **Bug 7 — SMS preview missing domain** (`app/admin/reminders/page.tsx:755`): Same env var issue as Bug 6
    - Fix: `process.env.FRONTEND_URL || ''` → `window.location.origin`
  - **OTPFlow slug param**: Added `slug` prop to OTPFlow component, passed through redirect URL to OTP verify page
  - Verified field names against database schemas: `WeddingModel._id` (string), `GuestModel.wedding_id` (string), `get_wedding_privacy_info()` returns `id: str(wedding._id)`
- **Guest Export QR Code — Wrong MongoDB Query Field** (`app/services/guest_export_service.py:420`):

  - `get_single_guest_qr()` queried weddings collection with `{"wedding_id": wedding_id}` but wedding documents use `_id` as primary key, not `wedding_id`
  - Query never matched any wedding → always returned `None` → QR code generation silently failed
  - Fix: `{"wedding_id": wedding_id}` → `{"_id": wedding_id}`
- **Guest Export API — Same Wrong Query Field Bug** (`app/api/guest_export.py:110,163`):

  - PDF export endpoint (`GET /guests/export/pdf`) queried `{"wedding_id": wedding_id}` → always returned `None` → PDF header showed "Wedding" instead of couple names
  - ZIP export endpoint (`POST /guests/export/qr-zip`) queried `{"wedding_id": request.wedding_id}` → always returned `None` → endpoint returned 404 "Wedding not found" for every request
  - Both fixes: `{"wedding_id": ...}` → `{"_id": ...}`
  - Note: Same bug pattern as `guest_export_service.py:420` fix above, but in the API layer
- **Guest Export URL Fallback Logic** (`app/services/guest_export_service.py:84-87`):

  - `build_rsvp_url()` had broken fallback logic for `FRONTEND_URL` environment variable
  - Code called `os.getenv("FRONTEND_URL", "")` then checked if empty and called it again with different default - the second call would still return empty string
  - Fix: Simplified to `os.getenv("FRONTEND_URL") or "https://thespecialwedding.io"`
  - **URL format**: Generates full RSVP URL as `{FRONTEND_URL}/{slug}/invite/{token}` (e.g., `https://thespecialwedding.io/emmanuel-peace/invite/abc123xyz`)
  - **Note**: Ensure `FRONTEND_URL` environment variable is set in Coolify to match your production domain
- **Cloudflare Workers — Multiple Configuration Issues** (`.github/workflows/deploy-workers.yml`, `cloudflare-workers/*.js`, `cloudflare-workers/*.wrangler.toml`):

  - **Issue 1 — Workflow branch condition**: Workflow only triggered on `main` or `development/saas-features`, not current branch `feature-twilio-otp-improvements-final-submitted`
    - Fix: Added current branch to trigger list and simplified condition using `startsWith()`
  - **Issue 2 — Metrics snapshot missing secrets**: `metrics-snapshot.wrangler.toml` deployment had no `wrangler secret put` commands
    - Fix: Added `NEXT_PUBLIC_API_BASE_URL`, `ADMIN_TOKEN`, `RESEND_API_KEY`, `ALERT_EMAIL`, `ROOT_ADMIN_EMAIL` secrets
  - **Issue 3 — Inconsistent API URL variable**: `trial-cron.js` and `metrics-snapshot-cron.js` used `env.API_URL` (hardcoded in wrangler.toml), other workers used `env.NEXT_PUBLIC_API_BASE_URL` (set via GitHub secrets)
    - Fix: Changed all workers to use `NEXT_PUBLIC_API_BASE_URL` for consistency
  - **Issue 4 — Hardcoded API URLs in wrangler.toml**: `trial.wrangler.toml` and `metrics-snapshot.wrangler.toml` had `API_URL = "https://api.thespecialwedding.io"` hardcoded
    - Fix: Removed hardcoded URLs, now all workers get API URL from GitHub secrets
  - **Issue 5 — Wrong admin dashboard URLs**: All workers had `https://admin.thespecialwedding.io/admin/*` (non-existent subdomain)
    - Fix: Changed to `https://thespecialwedding.io/admin/*` (path-based routing)
  - **Issue 6 — KV namespace replacement fragile**: sed command used `-i` with simple pattern that might not match
    - Fix: Added multiple pattern handling and better error logging
  - **Issue 7 — Typo in ALERT_EMAIL**: `trial.wrangler.toml` had `alertsd@thespecialwedding.io` (extra 'd')
    - Fix: Removed hardcoded email, now set via GitHub secrets
  - **Files modified**:
    - `.github/workflows/deploy-workers.yml`
    - `cloudflare-workers/autopilot-cron.js`
    - `cloudflare-workers/backup-cron.js`
    - `cloudflare-workers/uptime-cron.js`
    - `cloudflare-workers/trial-cron.js`
    - `cloudflare-workers/metrics-snapshot-cron.js`
    - `cloudflare-workers/trial.wrangler.toml`
    - `cloudflare-workers/metrics-snapshot.wrangler.toml`
- **Planner Notifications — Wrong Wedding Query Field** (`app/services/rsvp_service.py:150`, `app/services/stripe_service.py:1519`, `app/services/form_service.py:997`):

  - Same bug pattern as guest export: queried weddings collection with `{"wedding_id": wedding_id}` instead of `{"_id": wedding_id}`
  - **Impact**: Planner notifications silently failed — planners never received push/in-app notifications for:
    - RSVP updates (guest confirmed/declined attendance)
    - Payment received (Stripe payment success)
    - Form submissions (contact forms, vendor inquiries)
  - All three queries returned `None` → code exited early without sending notification
  - Fix: `{"wedding_id": wedding_id}` → `{"_id": wedding_id}` in all three services
  - Validated against `WeddingModel` schema: `id: str = Field(..., alias="_id")`
- **SMS/Email Opt-In Default Values** (`app/services/guest_service.py`, `app/services/import_service.py`):

  - Fixed new guests being created as "opted out" before receiving any message
  - **Root cause**: `sms_opt_in: False` and `email_opt_in: False` hardcoded on guest creation
  - **Impact**: Reminder service blocked messages for guests who hadn't opted out
  - **Fix**: Changed defaults to `True` (opted-in) - guests can opt-out later via RSVP form
  - `guest_service.py` line 242: `"sms_opt_in": False` → `"sms_opt_in": True`
  - `guest_service.py` line 243: `"email_opt_in": False` → `"email_opt_in": True`
  - `import_service.py`: Added explicit `"sms_opt_in": True, "email_opt_in": True` for imported guests
- **CSRF Middleware Blocking Guest RSVP Flow** (`app/main.py`, `app/core/settings.py`):

  - **Root cause**: CSRF middleware required `X-CSRF-Token` header + `csrf_token` cookie for all POST requests, but guest-facing pages don't have CSRF tokens
  - **Impact**: Guests clicking "Verify My Identity" on RSVP page saw "CSRF token missing in request header or cookie" error
  - **Analysis**: CSRF protection is redundant for this application because:
    1. Admin pages use JWT Bearer tokens (CSRF-immune by design - browsers don't auto-attach Authorization headers cross-origin)
    2. Guest pages use URL token-based auth (not vulnerable to CSRF - attacker would need to know the token)
    3. No session cookies are used that could be exploited
  - **Verified against OWASP guidelines**:
    - [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html): Custom request headers trigger CORS preflight, preventing cross-origin requests
    - [OWASP CSRF Attack](https://owasp.org/www-community/attacks/csrf): "all cookies will be submitted with every request" — JWT in Authorization header is not auto-attached
  - **Fix**: Removed CSRF middleware entirely
    - `app/main.py`: Removed `CSRFProtectionMiddleware` import and registration
    - `app/core/settings.py`: Changed `csrf_enabled` default from `True` to `False`
  - **Note**: CSRF middleware file (`app/middleware/csrf_protection.py`) retained with expanded `exclude_paths` documenting which endpoints would need exemption if CSRF is re-enabled:
    - `/otp/` - OTP endpoints (phone verification)
    - `/forgot-password` - Password recovery (email-based)
    - `/reset-password` - Password reset (uses reset token)
    - `/setup/` - Account setup (uses invitation token)
    - `/signup` - User registration
    - `/contact` - Contact forms (public)
- **OTP Request Returns Generic Error Message** (`app/services/otp_service.py`, `app/api/otp.py`):

  - **Root cause**: `send_otp()` returned `True/False` with no error details; API returned generic "Failed to send OTP" for all failure cases
  - **Impact**: Guests saw unhelpful error message when OTP failed (e.g., missing phone number displayed as "Failed to send OTP")
  - **Fix**: Modified `send_otp()` to return dict with specific error messages:
    - `{"success": False, "error": "Invalid guest ID format"}` — invalid ObjectId
    - `{"success": False, "error": "Please wait before requesting another code"}` — rate limited
    - `{"success": False, "error": "Guest not found"}` — guest doesn't exist
    - `{"success": False, "error": "No phone number on file. Please contact the wedding planner."}` — missing phone
    - `{"success": False, "error": "Failed to send SMS. Please try again later."}` — Twilio error
  - **Also fixed**: `/otp/verify` endpoint was calling wrong method (`verify_otp` instead of `verify_otp_by_guest_id`) and missing `async/await`
- **OTP Rate Limiting Math Error + Double-Submit Race Condition** (`app/services/otp_service.py`, `app/otp/verify/page.tsx`):

  - **Bug 1 — Rate limit blocks ALL resends for 5 minutes** (lines 73, 205):
    - **Root cause**: Condition `expires_at > datetime.utcnow() - timedelta(minutes=4)` should be `+ timedelta(minutes=4)`
    - **Why**: OTP expires in 5 minutes. To rate-limit for 1 minute: `expires_at > now + 4min` (sent < 1 min ago)
    - **Impact**: Current logic is ALWAYS true for valid OTPs, blocking ALL resends until OTP expires
    - **Fix**: Changed `- timedelta(minutes=4)` → `+ timedelta(minutes=4)` in both `send_otp()` and `send_otp_by_contact()`
  - **Bug 2 — Double-click causes "Invalid or expired OTP"** (`app/otp/verify/page.tsx`):
    - **Root cause**: No double-submit protection; OTP deleted on first successful verify, second request fails
    - **Impact**: Network shows success but UI shows error (first click succeeded, second failed)
    - **Fix**: Added `isSubmittingRef` guard to prevent concurrent verify requests
  - **Bug 3 — Frontend/backend timer mismatch** (`app/otp/verify/page.tsx`):
    - **Root cause**: Frontend hardcoded 60s cooldown but server blocked for 5 minutes (due to Bug 1)
    - **Fix**: Changed cooldown from 60 to 65 seconds (5 seconds buffer over server's 1-minute limit)
  - **Bug 4 — datetime.utcnow() deprecated** (`app/services/otp_service.py`):
    - **Root cause**: `datetime.utcnow()` returns naive datetime, deprecated in Python 3.12+
    - **Impact**: Potential timezone issues with MongoDB TTL index and comparison operations
    - **Fix**: Replaced all 7 occurrences with `datetime.now(timezone.utc)` (timezone-aware)
  - **Bug 5 — OTP verify success but RSVP form doesn't appear** (`app/otp/verify/page.tsx`):
    - **Root cause**: After OTP verify succeeds, `/weddings/guest-access/{slug}/{token}` fetch may fail; error thrown before `setIsVerified(true)`
    - **Impact**: OTP is consumed (deleted) but guest is stuck on verify screen with no way to proceed
    - **Fix**: Added `otpVerified` state to track OTP success separately; added retry UI when wedding data fetch fails after successful OTP verification
- **Forms API 404 Error** (`app/services/formsApi.ts`):

  - Fixed "Not Found" error when accessing Forms page in planner dashboard
  - **Root cause**: Frontend called `/admin/forms` but backend registers routes at `/forms` (no `/admin` prefix)
  - **Fix**: Removed `/admin` prefix from all form API paths in frontend service
  - Affected methods: `fetchForms`, `fetchTemplates`, `createBlankForm`, `createFromTemplate`, `duplicateForm`, `markScopeViewed`
  - Path changes:
    - `/admin/forms` → `/forms`
    - `/admin/form-templates` → `/form-templates`
    - `/admin/forms/from-template/{id}` → `/forms/from-template/{id}`
    - `/admin/forms/{id}/duplicate` → `/forms/{id}/duplicate`
    - `/admin/forms/{id}/views` → `/forms/{id}/views`
- **False Positive Error Acknowledgement** (`app/admin/platform/page.tsx`):

  - Fixed "Acknowledged 200 errors" toast showing success when all acknowledgements actually failed
  - Root cause: `Promise.allSettled()` marks promises as "fulfilled" even when HTTP response is 4xx/5xx
  - The code only checked `r.status === 'fulfilled'` without verifying `response.ok`
  - **Before:** 200 errors "acknowledged" but unacknowledged count remained 200
  - **After:** Uses bulk endpoint for single API call, properly reports actual success/failure count
  - Validated against MDN Fetch API documentation via context7 MCP
- **Duplicate `/admin/admin/` API Route Prefix** (`app/api/admin_activity.py`):

  - Fixed 404 errors on activity log endpoints due to double `/admin` prefix
  - Root cause: Router defined `prefix="/admin"` AND was mounted with `prefix="/admin"` in `main.py`
  - Changed `router = APIRouter(prefix="/admin", tags=["ROOT_ADMIN"])` to `router = APIRouter(tags=["ROOT_ADMIN"])`
  - Affected endpoints now work correctly:
    - `/admin/admin/activity-log` → `/admin/activity-log`
    - `/admin/admin/activity-log/recent` → `/admin/activity-log/recent`
  - Validated against FastAPI APIRouter documentation via context7 MCP
- **Notification Polling Performance & Resource Waste** (`app/admin/components/TopHeader.tsx`):

  - Fixed aggressive polling that continued even after authentication failures (401 errors)
  - **Issues fixed:**
    - Polling continued indefinitely despite 401 unauthorized responses
    - No exponential backoff on errors - same rate even during failures
    - Polling continued when browser tab was hidden (wasted resources)
    - No debouncing on window focus events - caused rapid duplicate requests
  - **Improvements:**
    - Added `stopPolling()` on 401 authentication errors - stops wasting server resources
    - Added Page Visibility API - pauses polling when tab is hidden, resumes when visible
    - Added exponential backoff: 60s → 120s → 240s → 300s (max) on consecutive errors
    - Added 2-second debounce on focus events to prevent rapid duplicate calls
    - Properly cleans up intervals on unmount and visibility changes
- **Double `/admin/admin/` Prefix in API Paths** (`app/admin/users/page.tsx`, `app/admin/page.tsx`):

  - Fixed 404 errors caused by duplicate `/admin` prefix in invitation and activity log API calls
  - Affected endpoints (all returning 404):
    - `/admin/admin/invitations` → fixed to `/admin/invitations`
    - `/admin/admin/invitations/stats` → fixed to `/admin/invitations/stats`
    - `/admin/admin/invitations/{id}/resend` → fixed to `/admin/invitations/{id}/resend`
    - `/admin/admin/invitations/{id}/cancel` → fixed to `/admin/invitations/{id}/cancel`
    - `/admin/admin/activity-log/recent` → fixed to `/admin/activity-log/recent`
  - Root cause: Frontend code incorrectly included `/admin` twice in URL paths
- **Profile Page API Path Mismatches** (`app/admin/profile/page.tsx`):

  - Fixed 404 errors on profile update operations (password, email, info, image)
  - Root cause: `user_management.py` profile endpoints are mounted WITHOUT `/admin` prefix, but frontend used `/admin/profile/...`
  - Fixed API paths:
    - `/admin/profile/password` → `/profile/password` (PUT)
    - `/admin/profile/email` → `/profile/email` (PUT)
    - `/admin/profile/info` → `/profile/info` (PUT)
    - `/admin/profile/image` → `/profile/image` (POST upload, DELETE remove)
  - Note: `GET /admin/profile` remains correct (served by `admin_auth.py` with `/admin` prefix)
  - This affects both root admin and planner profile pages
- **Account Settings Modal Issues** (`app/admin/components/AccountSettingsModal.tsx`, `app/api/admin_auth.py`):

  - Fixed "Not Found" error when clicking "Save Changes"
    - Root cause: Frontend was calling `/admin/profile/info` but endpoint is at `/profile/info` (no `/admin` prefix)
    - Fixed all API paths (password, email, info, image) to use correct endpoints
  - Fixed modal positioning (was appearing off-center/inside header dropdown)
    - Root cause: Modal was rendered inside `<header>` element, interfering with `fixed` positioning
    - Solution: Used React Portal (`createPortal`) to render modal at document.body level
    - Added `z-[9999]` to ensure modal appears above all other elements
  - Improved modal UI design:
    - Added gradient header background with subtitle
    - Redesigned tab navigation with pill-style selector
    - Improved Save button styling with shadow and better spacing
    - Added smooth animations (fade-in, zoom-in)
    - Better dark mode support
  - Added `push_notifications_enabled` field to `GET /admin/profile` response (defaults to `true`)
- **CRITICAL: User Management Operations Failing (Delete/Suspend/Activate)** (`app/services/user_management_service.py`):

  - Fixed "Failed to delete user" error when attempting to delete a planner from Planner Management page
  - Root cause: User ID passed as string but MongoDB stores `_id` as ObjectId - query never matched
  - Added `from bson import ObjectId` conversion to all user-by-ID queries:
    - `get_user()`: Now converts string to ObjectId before querying
    - `update_user()`: Now converts string to ObjectId before updating
    - `delete_user()`: Now converts string to ObjectId before find and delete
    - `suspend_user()`: Now converts string to ObjectId, also sets `is_suspended: True`
    - `activate_user()`: Now converts string to ObjectId, also sets `is_suspended: False`
    - `assign_wedding_to_planner()`: Now converts user_id string to ObjectId
  - Pattern now matches all other services in codebase (subscription_service, stripe_service, autopilot_service, etc.)
  - Also added `is_suspended` field to user document for frontend status display
- **Code Quality & Type Safety Fixes** (Multiple files):

  - **subscription_service.py**: Added missing `subscription_service = SubscriptionService()` singleton instance at end of file
    - Fixes `"subscription_service" is unknown import symbol` error when importing from other modules
  - **subscription_service.py**: Removed unused Pydantic model imports (`SubscriptionPlanModel`, `UserSubscriptionModel`, `UsageTrackingModel`, `SubscriptionStatus`, `BillingInterval`)
    - Service uses raw MongoDB dictionaries instead of these models
  - **user_management_service.py**: Removed unused `stripe_service` import (line 118)
    - The `stripe` module is imported directly elsewhere in the file
  - **user_management_service.py**: Fixed type error for `trial_end_date` timestamp conversion
    - Changed `datetime.fromtimestamp(subscription.trial_end)` to `datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None`
    - Handles case where `subscription.trial_end` is `None` (no trial period)
- **Root Admin Notification Badge Never Clears** (`app/services/notification_service.py`):

  - Fixed notification badge showing count that never clears for root admin
  - Root cause: Root admin was receiving their own notifications (via `target_audience: "all"`)
  - Added `{"created_by": {"$ne": user_email}}` filter to exclude notifications created by the current user
  - Modified `get_user_notifications()` at line 293 and `get_user_notification_count()` at line 481
  - Logical behavior: Creators should not receive their own announcements
  - Planners unaffected (they don't create notifications)
- **Platform Errors Tab Data Mismatch** (`app/api/admin_platform_metrics.py`):

  - Fixed Errors tab showing 0 errors while Dashboard showed 236 errors
  - Root cause: `audit_logs` collection (where HTTP 4xx/5xx errors are stored) was only queried when `acknowledged=None`
  - When "Unacknowledged" filter was selected (`acknowledged=False`), `audit_logs` were skipped entirely
  - Changed line 720 from `acknowledged is None` to `acknowledged is not True`
  - Now includes `audit_logs` for both "All" and "Unacknowledged" views, excludes only for "Acknowledged" view
  - `audit_logs` entries don't have an `acknowledged` field, so they're inherently unacknowledged
- **PlannerNotificationTypes Type Errors** (`app/models/planner_notification.py`):

  - Fixed 8 type errors in `planner_notification_service.py` where notification type constants were incompatible with `NotificationType` Literal
  - Root cause: Type checker saw `PlannerNotificationTypes.FORM_SUBMISSION` as `str`, not `Literal["form_submission"]`
  - Solution: Added `Final[Literal["..."]]` type annotations to all class constants
  - Changed from `FORM_SUBMISSION: Literal["form_submission"]` to `FORM_SUBMISSION: Final[Literal["form_submission"]]`
  - `Final` tells type checker the value is immutable and should preserve its literal type
  - Affected constants: `FORM_SUBMISSION`, `RSVP_UPDATE`, `GUEST_MESSAGE`, `PAYMENT_RECEIVED`, `PAYMENT_FAILED`, `CONTRACT_SIGNED`, `VENDOR_RESPONSE`, `REMINDER`, `SYSTEM`
- **Undefined Function in Metrics Snapshot** (`app/api/admin_platform_metrics.py:578`):

  - Fixed `NameError: name 'get_platform_metrics' is not defined` in `save_metrics_snapshot` endpoint
  - Changed `await get_platform_metrics(current_user)` to `await get_platform_health(current_user)`
  - The function was renamed but this call site was not updated
- **Frontend Password Validation Mismatch** (`app/setup-account/page.tsx`, `app/reset-password/page.tsx`):

  - Fixed password validation in account setup and reset pages to match backend requirements
  - Added visual password requirements checklist with real-time validation
  - Password now requires: 8+ characters, uppercase, lowercase, number, special character
  - Prevents user frustration from submitting valid-looking passwords that fail backend validation
  - Reference: Backend validators in `app/api/user_management.py:AccountSetupModel`, `ResetPasswordModel`
- **Success Message Not Displayed on Login** (`app/admin/login/page.tsx`):

  - Fixed login page to display success messages from URL query params
  - Messages now appear after account setup completion (`?message=Account setup completed!`)
  - Messages now appear after password reset (`?message=Password reset successful!`)
  - Auto-dismiss after 10 seconds with manual close button
  - Styled with emerald green success indicator matching app design
- **SAAS Admin Dashboard Hardcoded Statistics** (`app/admin/saas/page.tsx`):

  - Fixed "Total Weddings" showing hardcoded value `12` instead of actual database count
  - Fixed "Monthly Revenue" showing hardcoded value `$247` instead of real revenue data
  - Fixed "Plan Distribution" showing hardcoded user counts (`0 users`/`1 user`) instead of actual subscribers per plan
  - Added API calls to existing `/saas/analytics/overview` and `/saas/analytics/revenue` endpoints
  - Added `AnalyticsOverview`, `PlanBreakdown`, and `RevenueAnalytics` TypeScript interfaces
  - Dashboard now displays real-time statistics from the database
- **Planner Management Actions Dropdown Clipped** (`app/admin/users/page.tsx`):

  - Fixed Actions column 3-dot menu dropdown being cut off by parent container
  - Removed `overflow-hidden` from planners table card wrapper (line 919)
  - Changed table container from `overflow-x-auto` to `overflow-visible` (line 942)
  - Dropdown menu now renders fully visible outside the table boundaries
- **Profile Picture Upload Not Saving** (`app/api/user_management.py`):

  - Fixed profile image URL construction missing `https://` protocol prefix
  - URLs were being constructed as `media.domain.com/path` instead of `https://media.domain.com/path`
  - Added validation to ensure `MEDIA_DOMAIN` environment variable is set
  - Fixed both upload and delete endpoints to handle URL protocol consistently
- **Root Admin Settings Page UX** (`app/admin/components/TopHeader.tsx`, `app/admin/components/AccountSettingsModal.tsx`):

  - Converted ROOT_ADMIN settings from separate page to popup modal
  - Added dropdown menu to TopHeader username area with "Account Settings" and "Logout" options
  - Created `AccountSettingsModal` component with Profile Info, Change Password, and Change Email tabs
  - Profile picture upload/delete now works directly in the modal
  - Improves UX by matching planner settings popup pattern
- **Root Admin Subscription Management 404 Errors** (`app/admin/saas/page.tsx`):

  - Removed incorrect `/admin` prefix from subscription API calls
  - Changed `/admin/users/${id}/subscription` to `/users/${id}/subscription` at lines 705, 731, 767, 778
  - Fixes: Activate planner, deactivate planner, and assign plan operations now work correctly
  - Reference: subscription_router is registered without `/admin` prefix in `main.py`
- **Subscription Plans Not Showing in Admin** (`app/services/subscription_service.py:58`):

  - Fixed sort field mismatch: changed `display_order` to `sort_order`
  - Plans query now uses correct field name matching the model definition
  - Reference: `app/models/subscription.py:52` defines `sort_order: int`
- **Subscription Seed Script Errors** (`scripts/seed_subscription_plans.py`):

  - Added explicit null check for stripe module before accessing `stripe.api_key` (fixes Pylance error)
  - Updated exception handling to use `from stripe import StripeError` for Stripe v13+ compatibility
  - Replaced all emoji characters with text-based prefixes for professional logging:
    - `[SEED]`, `[INFO]`, `[OK]`, `[WARN]`, `[ERROR]`, `[DEBUG]`
    - `[EXISTS]`, `[CREATED]`, `[UPDATED]`, `[SKIP]`, `[PLAN]`
    - `[SUMMARY]`, `[VERIFY]`, `[DONE]`

### Changed

- **Custom Trial Duration for Planners** (`app/admin/saas/page.tsx`):
  - Added prompt for trial days when assigning subscriptions (lines 714, 787)
  - ROOT_ADMIN can now set custom trial periods (e.g., 150 days for 5-month trial)
  - Replaces hardcoded 14-day trial default

### Security

- **Multi-Tenant Data Isolation** (Multiple files):

  - **Guest Search Endpoint** (`app/api/guest.py`):
    - `/invite/search` now requires authentication via `require_wedding_planner_only`
    - Added mandatory `wedding_id` parameter to prevent cross-wedding guest enumeration
    - Added ownership verification via `check_wedding_access()` before returning results
  - **Guest Service** (`app/services/guest_service.py`):
    - `get_guest_by_phone_or_name()` now accepts and filters by `wedding_id`
    - Prevents planners from accessing guests outside their assigned weddings
  - **Gallery Admin Endpoints** (`app/api/gallery_admin.py`):
    - Added `verify_wedding_access_by_slug()` helper for ownership validation
    - All endpoints now validate wedding ownership via `assigned_planner_email` field
    - `/gallery/upload-url`: Validates planner access before generating presigned URL
    - `/gallery/file-url`: Extracts wedding_slug from key path and validates ownership
    - `DELETE /gallery`: Validates ownership before allowing file deletion
    - `/gallery/list`: Filters results by wedding access, returns empty for unauthorized
    - `/gallery/upload`: Validates wedding access before accepting uploads
  - **OTP Rate Limiting** (`app/services/otp_service.py`):
    - Added rate limiting to `send_otp_by_contact()` method (1 OTP per minute per guest)
    - Prevents OTP spam attacks while keeping endpoint public for guest verification
    - Uses existing OTP expiry (5 min) minus 4 min buffer to calculate rate limit window
- **CRITICAL: Settings Validation** (`app/core/settings.py`):

  - Removed insecure default `secret_key="changeme"` - now required from environment
  - Added `field_validator` requiring SECRET_KEY to be 32+ characters and not a common default
  - Removed insecure default `cors_origins=[]` - now required from environment
  - Added validator ensuring CORS_ORIGINS has at least one configured origin
  - Reference: [Pydantic Settings Management](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Fixed

- **CRITICAL: Build Failure - Unterminated Regexp Literal** (`app/admin/users/page.tsx`):

  - Added missing opening `<div>` tag after `</PageHeader>` component
  - File had 65 opening `<div` tags but only 58 closing `</div>` tags
  - Caused TypeScript/SWC parser to fail with misleading "Unterminated regexp literal" error
  - Root cause: JSX structure imbalance from orphan closing tag at line 1019
- **CRITICAL: Pricing Page TypeError - slice is not a function** (`app/components/saas/SignupModal.tsx:250`):

  - Fixed `(selectedPlan?.features || selectedPlan?.features_list || []).slice(0, 4)` pattern
  - Backend sends `features` as `Record<string, boolean>` (object), not array
  - When `features` is truthy (even `{}`), the `||` fallback to `features_list` never triggered
  - Objects don't have `.slice()` method, causing runtime TypeError on pricing page
  - Changed to: `(Array.isArray(selectedPlan?.features_list) ? selectedPlan.features_list : []).slice(0, 4)`
- **CRITICAL: N+1 Query Pattern** (`app/admin/guests/page.tsx`, `app/api/plus_one.py`, `app/services/plus_one_service.py`):

  - Added batch endpoint `GET /plus_one/plus-ones/wedding/{wedding_id}` to fetch all plus-ones for a wedding in single query
  - Replaced N individual API calls with single batch fetch, improving performance for large guest lists
  - Reference: [MongoDB Query Optimization](https://www.mongodb.com/docs/manual/core/query-optimization/)
- **HIGH: Race Condition in Plus-One Creation** (`app/services/plus_one_service.py:27-61`):

  - Implemented insert-then-verify pattern to prevent concurrent requests exceeding plus-one limits
  - If count exceeds limit after insert, rollback is performed automatically
  - Reference: [MongoDB Atomic Operations](https://medium.com/tales-from-nimilandia/handling-race-conditions-and-concurrent-resource-updates-in-node-and-mongodb-by-performing-atomic-9f1a902bd5fa)
- **HIGH: String/ObjectId Type Inconsistency** (`app/services/plus_one_service.py:124-162`):

  - Standardized `guest_id` storage as string in plus_ones collection
  - Fixed delete_plus_one to use ObjectId for guest collection lookups
  - Prevents lookup failures due to type mismatches
- **HIGH: Duplicate Router Registration** (`app/main.py:266-299`):

  - Removed 7 duplicate routers from admin_routers that were already registered publicly with route-level authentication
  - Affected routers: user_management, subscription, saas_config, forms, vendor_forms, vendor_management, contracts
  - Prevents redundant route registration and potential conflicts
- **HIGH: Plan Selection Race Condition** (`app/components/saas/SaasLandingPage.tsx:407-413`):

  - Added `useRef` to track if initial plan selection has been made
  - Removed `selectedPlan` from useEffect dependency array to prevent overwriting user's manual selection
  - Reference: [React useRef for Preventing Infinite Loops](https://blog.logrocket.com/solve-react-useeffect-hook-infinite-loop-patterns/)
- **Pricing Page TypeError** (`app/components/saas/SaasLandingPage.tsx`, `IntegratedHeroSection.tsx`, `SaasExperienceCarousel.tsx`):

  - Added `Array.isArray()` defensive checks before calling `.slice()` and spread operators
  - Prevents `Uncaught TypeError: .slice is not a function` during SSR hydration

### Verified (No Change Required)

- **Middleware Order** (`app/main.py:208-227`):
  - Verified CORS middleware executes BEFORE rate limiting (correct for preflight handling)
  - In FastAPI/Starlette, middleware added LAST executes FIRST on incoming requests
  - Reference: [FastAPI Middleware Ordering](https://medium.com/@saurabhbatham17/navigating-middleware-ordering-in-fastapi-a-cors-dilemma-8be88ab2ee7b)

### Pre-Launch QA Fixes (formerly 1.7.0-rc.1 - 2026-03-01)

Comprehensive QA review identified 66 frontend-backend alignment issues (21 CRITICAL, 24 HIGH, 16 MEDIUM, 5 LOW). All CRITICAL and HIGH severity issues fixed below. MEDIUM/LOW items also completed.

### Fixed

- **Budget: 9 CRITICAL endpoint path mismatches** (`app/services/budgetApi.ts`):

  - B1/B2: Vendor quotes GET/POST path (`vendor-quotes` → `quotes`)
  - B3: Quote status PUT path (`vendor-quotes` → `quotes`)
  - B4: Delete category path (`categories` → `category`, singular)
  - B5: Get quotes response unwrapping (backend returns `{quotes: [...]}`)
  - B7: Compare quotes path — query param → path param (`/quotes/compare/{category}`)
  - B8: Budget alerts GET path structure
- **AI: CRON_SECRET security vulnerability** (`app/api/autopilot.py`):

  - A2: Added fail-closed guard — if `CRON_SECRET` is not set, all cron requests are rejected instead of silently bypassed
- **AI: Seating and forecast mismatches** (`app/api/ai.py`, `app/admin/money/page.tsx`):

  - A1: Fixed seating optimization parameter mismatch — added all required guest fields
  - A3: Added AI client initialization check to seating endpoint
  - A4: Fixed forecast response shape — frontend reads flat response instead of nested `data.forecast`
- **Seating: ID format and data integrity** (`app/api/tables.py`, `app/api/guest.py`, `app/services/guest_service.py`):

  - T1: Invalid guest IDs now return validation error instead of being silently skipped
  - T8: Added atomic update with version check for concurrent table assignments
  - T4: Added server-side capacity validation with specific error when table is full
  - T7: Fixed constraint endpoint string vs ObjectId conversion
  - T2/T6: Guest deletion now cleans up orphan `must_sit_with`/`must_sit_apart` references
- **Stripe: Auth and billing page failures** (`app/admin/billing/success/page.tsx`, `app/admin/planner/billing/page.tsx`, `app/dependencies/feature_gates.py`):

  - S2: Fixed auth token name (`authToken` → `admin_token`)
  - S3: Subscription fetch uses actual `user_id` from auth context instead of email
  - S8: Feature gate checks both `user_id` and `user_email` for subscription lookup
- **Stripe: Webhook idempotency** (`app/services/stripe_service.py`):

  - S7: Added idempotency tracking via Stripe event ID to prevent duplicate processing
- **Contracts: 9 missing backend endpoints** (`app/api/contracts.py`):

  - C3: `POST /contracts` — full contract creation with vendor lookup, auto-generated number, secure token
  - C2: `POST /milestones/{milestone_id}/pay` — record vendor payment (pending → partial → paid)
  - C4: `PUT /contracts/{contract_id}/sections` — update sections with status validation
  - Added: `PUT /contracts/{contract_id}`, `POST /contracts/{contract_id}/send`, `POST /contracts/{contract_id}/milestones`, `GET /contracts/{contract_id}/form-data`, `POST /contracts/{contract_id}/apply-form-data`, `GET /milestones`
- **Contracts: Service-layer fixes** (`app/services/contract_service.py`):

  - C5: Auto-generates contract numbers in `CON-YYYYMMDD-XXXX` format
  - C11: Added 30-day token expiration; cancelled/completed contracts expire immediately
  - C13: Status transition validation — only draft/pending_review can be updated or sent
- **Contracts: Frontend alignment** (`app/admin/vendors/contracts/[id]/page.tsx`, `app/services/contract_email_service.py`):

  - C9: Wired up "View & Apply Form Data" button onClick handler
  - Fixed `GET /contracts/{contract_id}` response format (was `{contract: ...}`, frontend expects direct object)
  - Added `send_contract_email()` — HTML email with "View & Sign Contract" CTA
- **Contracts: Route ordering bug** (`app/api/contracts.py`):

  - Moved `/contracts/followup-drafts` routes before `/contracts/{contract_id}` to prevent FastAPI route shadowing

### Security

- B9-SEC: Added wedding access control to `update_budget_category()` and `delete_budget_category()` — closes cross-tenant data modification vulnerability
- A2: CRON_SECRET fail-closed guard prevents unauthenticated cron execution
- S7: Webhook idempotency prevents duplicate payment/subscription processing
- C11: Contract token expiration prevents indefinite public access to contract data

### Files Modified

**Backend (11 files):**
`app/api/budget.py`, `app/api/contracts.py`, `app/api/autopilot.py`, `app/api/ai.py`, `app/api/tables.py`, `app/api/guest.py`, `app/services/contract_service.py`, `app/services/contract_email_service.py`, `app/services/guest_service.py`, `app/services/stripe_service.py`, `app/dependencies/feature_gates.py`

**Frontend (5 files):**
`app/services/budgetApi.ts`, `app/admin/money/page.tsx`, `app/admin/billing/success/page.tsx`, `app/admin/planner/billing/page.tsx`, `app/admin/vendors/contracts/[id]/page.tsx`

### MEDIUM/LOW Issues (Completed 2026-03-02)

Remaining 24 MEDIUM/LOW severity issues addressed:

**AI (A6-A10):**

- A6: Added `Field` validation with `max_length` constraints to all AI request models (`ChatMessageRequest`, `DraftCommunicationRequest`, `ContractSectionRequest`, `GenerateMessageRequest`, `GenerateFormQuestionsRequest`)
- A7: Enhanced `/ai/health` endpoint — added API response time measurement and 24-hour error rate metrics from `ai_usage_log`
- A8: Added pre-flight AI credit check in `generate-contract-section` endpoint before expensive generation
- A9/A10: Already handled — `AIRateLimitError` and `AIServiceUnavailableError` provide rate limiting and fallback at the service layer

**Seating (T3, T5, T9):**

- T3: Verified `list_guests_by_wedding` already converts `_id` → `id` consistently (no change needed)
- T5: Added clarifying comments in `seating_export_service.py` confirming ObjectId → string normalization for guest-to-table lookup
- T9: Made `PrintableSeatingChart` branding dynamic — added `SeatingChartTheme` interface with configurable `accentColor`, `headerColor`, `headingFont`, `bodyFont` (defaults to gold/navy/Playfair Display)

**Stripe (S1, S4, S5, S6):**

- S1: Verified no fix needed — backend `PublicCreateCheckoutSessionRequest` ignores `user_id` and derives it from email lookup
- S4/S5: Verified no fix needed — card fields are already optional in `UserSubscription` interface with null guards in JSX
- S6: Added AI credits fetch from `/ai/credits` endpoint in billing page to populate `ai_credits_used` and `ai_credits_remaining`

**Contracts (C7, C8, C12, C14, C15, C16, C17):**

- C7: Added Stripe `PaymentMethod.retrieve` validation in sign endpoint — verifies payment method belongs to customer
- C8: Verified already handled — `_serialize_contract` converts `wedding_date` via `.isoformat()`
- C12: Improved email recipient resolution in `send_signed_confirmation` — falls back to `vendor_email` → `couple.email` → `signer_email`
- C14: Added HTML fallback in `contract_pdf_service.generate_pdf` — when WeasyPrint is unavailable, stores signed HTML document in R2 instead
- C15: Already addressed by A8 credit pre-check
- C16: Added `document_url` and `deposit_processed` to sign contract response
- C17: Added documented status constants (`CONTRACT_STATUS_DRAFT`, `EDITABLE_STATUSES`, `TERMINAL_STATUSES`, etc.) to `contract_service.py`

**Additional files modified:**
`app/services/seating_export_service.py`, `app/admin/components/seating/PrintableSeatingChart.tsx`, `app/services/contract_pdf_service.py`

### Code Review Fixes (2026-03-02)

Engineering alignment review across frontend, backend, database models, and endpoint parameters. Found and fixed 5 issues:

**Critical:**

- **C-1: Public vendor contract URLs returning 404** (`app/vendor-contract/[id]/page.tsx`, `app/services/vendorManagementApi.ts`):
  - Frontend was calling `/admin/public/contracts/{id}` — but the `vendor_management_router` is registered at prefix `/vendor-contract` (not `/admin`)
  - Fixed both the page component and `getPublicContract()`/`signPublicContract()` API helpers to use `/vendor-contract/public/contracts/{id}`
  - The separate new contract system (`app/contracts/[token]/page.tsx`) was already correctly aligned

**Medium:**

- **M-2: Budget alerts fully implemented** (`app/api/budget.py`, `app/services/budget_service.py`):
  - `GET /admin/budget/alerts/{wedding_id}` was returning a hardcoded empty array despite `_check_budget_alerts()` already creating real alerts in MongoDB
  - Added `get_budget_alerts()`, `mark_alert_as_read()`, `resolve_alert()` methods to `BudgetService`
  - Wired endpoint to service; added `PUT /admin/budget/alerts/{alert_id}/read` and `PUT /admin/budget/alerts/{alert_id}/resolve` endpoints matching `budgetApi.ts` frontend calls
- **M-1: Documented route dependency** (`app/admin/money/page.tsx`):
  - Money page calls contract/payment endpoints at root paths (`/contracts`, `/payments`) because `contracts_router` is registered without a prefix
  - Added documentation comment explaining the dependency

**Observations fixed:**

- **O-1: ContractStatus type synced** (`app/services/vendorManagementApi.ts`):
  - Added missing `'active'` status to `ContractStatus` type union and `getContractStatusColor()` map (`bg-teal-100 text-teal-800`)
- **O-2: Consistent `id`/`_id` across both contract systems** (`app/services/vendor_service.py`, `app/services/vendorManagementApi.ts`):
  - `vendor_service.py` only returned `_id` while `contract_service.py` returned both `id` and `_id` — inconsistent API shape
  - Added `_serialize_doc()` helper to `VendorService`; applied to all contract CRUD methods (create, list, get, get_by_token, create PDF)
  - Added `id?: string` to `VendorContract` and `PublicContract` TypeScript interfaces

**Files modified:**
`app/api/budget.py`, `app/services/budget_service.py`, `app/services/vendor_service.py`, `app/services/vendorManagementApi.ts`, `app/vendor-contract/[id]/page.tsx`, `app/admin/money/page.tsx`

---

## [1.6.1] - 2026-01-23

### Fixed

- **Cloudflare Workers - Deprecated MailChannels Replacement** (`cloudflare-workers/*.js`):

  - Replaced deprecated MailChannels API with [Resend API](https://resend.com/docs/api-reference/emails/send-email) in all workers
  - Updated email sending to use `POST https://api.resend.com/emails` with `Authorization: Bearer` header
  - Email configuration now uses environment variables: `ALERT_EMAIL` (from), `ROOT_ADMIN_EMAIL` (to)
  - Affected workers: `autopilot-cron.js`, `backup-cron.js`, `uptime-cron.js`
- **Cloudflare Workers - Request Timeout** (`cloudflare-workers/*.js`):

  - Added `fetchWithTimeout()` helper to all workers to prevent hanging requests
  - Uses `AbortController` with configurable timeout (10s default, 15s health checks, 30s API calls, 60s backups)
  - Reference: [Cloudflare Workers Context API](https://developers.cloudflare.com/workers/runtime-apis/context/)
- **Cloudflare Workers - Premature Termination** (`cloudflare-workers/backup-cron.js`):

  - Wrapped email sending calls with `ctx.waitUntil()` to prevent premature worker termination
  - Ensures async email operations complete even after response is returned
  - Reference: [Cloudflare Scheduled Handler](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/)
- **Cloudflare Workers - Alert Spam Prevention** (`cloudflare-workers/uptime-cron.js`):

  - Implemented KV-based alert debouncing (max 1 alert per hour during outages)
  - Added recovery notifications when service comes back online
  - Added `/status` endpoint to check current downtime state and last alert time
  - Uses [Cloudflare KV](https://developers.cloudflare.com/kv/get-started/) for state persistence
- **Cloudflare Workers - Hardcoded Values Removed**:

  - Removed all hardcoded API URLs and email addresses from worker files and wrangler.toml configs
  - All configuration now pulled from GitHub secrets during deployment
  - Changed environment variable from `API_URL` to `NEXT_PUBLIC_API_BASE_URL` for consistency with project conventions
  - Updated `deploy-workers.yml` to set secrets via `wrangler secret put`

### Added

- **Automated KV Namespace Creation** (`.github/workflows/deploy-workers.yml`):
  - Deploy workflow now automatically creates KV namespace for uptime-cron worker
  - Extracts namespace ID and updates `uptime.wrangler.toml` during deployment
  - No manual `wrangler kv:namespace create` step required
  - Reference: [Wrangler KV Commands](https://developers.cloudflare.com/kv/reference/kv-commands/)

### Changed

- **Deploy Workers Workflow** (`.github/workflows/deploy-workers.yml`):
  - Updated all workers to use `NEXT_PUBLIC_API_BASE_URL` instead of `API_URL`
  - Added `ALERT_EMAIL` and `ROOT_ADMIN_EMAIL` secrets to all worker deployments
  - Added KV namespace creation step before uptime worker deployment

## [1.6.0] - 2026-01-10

### Added

- **Plan Switching Endpoint** (`app/api/subscription_management.py`):

  - New endpoint `PATCH /users/{user_id}/subscription/billing-interval`
  - Allows users to switch between monthly and yearly billing with automatic proration
  - Users can only change their own subscription; ROOT_ADMIN can change any user's
  - Comment: "Proration is applied automatically: Switching to yearly credits unused monthly time"
- **AI Seating Validation** (`app/api/ai.py`):

  - New `validate_seating_suggestions()` function validates AI-generated table assignments
  - New `_extract_guest_id()` helper handles mixed string/object guest formats from different AI tiers
  - Validates guest IDs exist in original data, checks table capacity limits
  - Returns validation results with unassigned guests and over-capacity warnings
  - Comment: "Extract guest ID from various formats AI might return"
- **Enhanced Contract Follow-up Context** (`app/services/contract_followup_service.py`):

  - Added wedding context fields: venue_name, venue_location, cultural_style, guest_count, wedding_title
  - AI prompts now reference cultural considerations and wedding details
  - Batch fetch optimization to avoid N+1 queries (reduced from 100+ to ~3 queries)
  - Comment: "Batch fetch all weddings and planners to avoid N+1 queries"
- **AI System Prompts** (`app/services/ai_service.py`):

  - Added missing system prompts for `seating_medium` and `seating_large` AI tiers
  - Medium tier (150-300 guests): Focuses on family dynamics and relationship patterns
  - Large tier (300+ guests): Handles multiple sections, VIP tables, dietary clustering
- **Guest Table Assignment Field** (`app/models/guest.py`):

  - Added `table_id: Optional[str]` field to GuestModel and UpdateGuestRequest
  - Comment: "ID of assigned seating table"

### Fixed

- **MRR Calculation** (`app/services/subscription_service.py`):

  - Fixed Monthly Recurring Revenue to include BOTH monthly AND yearly subscriptions
  - Yearly subscriptions now calculated as `price_yearly / 12` (monthly equivalent)
  - Added MRR breakdown: from_monthly_billing, from_yearly_billing, subscriber counts
  - Added Annual Recurring Revenue (ARR) calculation
  - Comment: "MRR calculation - includes both monthly AND yearly. For yearly subscriptions, we calculate the monthly equivalent (price_yearly / 12)"
- **Stale Metering Retry Keys** (`app/api/metering.py`):

  - Fixed idempotency key generation to ALWAYS use current billing period
  - Previous bug used stale `billed_period` from wedding record which could be months old
  - Comment: "Idempotency key for retry: ALWAYS use current period since we're billing for NOW. Note: billed_period stores the LAST successful billing, not the target period"
- **Trial Days Default** (Multiple files):

  - Removed unintended 14-day trial default (user has no free trials)
  - `app/models/subscription.py`: AssignSubscriptionRequest.trial_days default 14→0
  - `app/api/subscription_management.py`: Removed `or 14` fallback in trial_days
  - `app/services/subscription_service.py`: assign_subscription trial_days default 14→0
  - `app/core/settings.py`: free_trial_days default 14→0
  - Comment: "Trial days (0 = no trial)"
- **useGuests Hook Race Condition** (`app/admin/hooks/useGuests.ts`):

  - Added AbortController to cancel in-flight requests when wedding changes
  - Added currentWeddingIdRef to prevent stale state updates
  - Clears guests on wedding switch to prevent stale data flash
  - Comment: "Track current request to prevent race conditions"
- **SignupModal Body Scroll** (`app/components/saas/SignupModal.tsx`):

  - Added body scroll lock when modal is open
  - Prevents background page scrolling while signup modal is displayed
- **CSS @import Order** (`app/styles/globals.css`):

  - Moved font @import to top of file (before @tailwind directives)
  - Fixes CSS rule ordering error: "@import rules must precede all rules"

### Changed

- **Stripe Service** (`app/services/stripe_service.py`):
  - Added `change_subscription_billing_interval()` method for plan switching
  - Uses Stripe's subscription modification with `proration_behavior: "create_prorations"`
  - Updates local database with new billing interval and period dates

## [1.5.0] - 2025-01-10

### Added

- **Payment Processing Safety**: Critical fixes for payment reliability

  - **Idempotency Keys**: All Stripe PaymentIntent.create calls now include idempotency keys to prevent double-charging
    - `autopilot_service.py`: Uses `autopilot_{payment_id}_attempt_{attempt_count}` format
    - `contract_service.py`: Uses `deposit_{contract_id}_{payment_id}` format
  - **Atomic Status Checks**: Payment retry and processing operations now use atomic MongoDB updates with status guards
    - Prevents race conditions when multiple cron instances or retry requests process the same payment
    - Both `retry_failed_payments()` and `_process_single_payment()` check status before proceeding
- **Subscription System Hardening**: Production-ready improvements for billing reliability

  - **Plan Grandfathering** (`app/services/subscription_service.py`):
    - Snapshot plan limits at subscription creation time
    - Users keep their original limits even if plan pricing/limits are modified later
    - Backwards compatible with existing subscriptions (falls back to current plan)
  - **Pricing Page Resilience** (`app/components/saas/PricingSection.tsx`):
    - Retry with exponential backoff (3 attempts: 1s → 2s → 4s)
    - localStorage cache (5-minute TTL) for offline resilience
    - User-friendly "Retrying..." status during fetch failures
    - Falls back to cached data if API is temporarily unavailable
  - **Atomic Seed Script** (`scripts/seed_subscription_plans.py`):
    - MongoDB upsert prevents race conditions on multi-container startup
    - `$setOnInsert` for created_at/created_by, `$set` for updateable fields
    - Idempotent Stripe product/price creation

### Fixed

- **Coolify Docker Build ARG Injection Bug** (`Dockerfile.coolify`):

  - Fixed CORS/API unreachable issue after Coolify deployment
  - Root cause: Coolify bug #7118 injects ARG statements at line 2, but Dockerfile starts with comments
  - ARG was being placed before `FROM` instruction, making it unavailable in build stage
  - Solution: Explicitly declare `ARG NEXT_PUBLIC_API_BASE_URL` after `FROM` instruction
  - Removed hardcoded default value - relies on Coolify's "Build Variable" setting
  - Reference: [Coolify Issue #7118](https://github.com/coollabsio/coolify/issues/7118)
- **Public API Security** (`app/api/subscription_management.py`):

  - Sanitized `/public/subscription-plans` response to exclude sensitive fields
  - Removed: `stripe_product_id`, `stripe_price_id_*`, `created_by`, `created_at`
  - Only returns public-safe fields needed for pricing display
- **S3 Variable Naming Mismatch**: Aligned code with `.env` file naming

  - Fixed `settings.py` aliases: `S3_ACCESS_KEY` → `S3_ACCESS_KEY_ID`, `S3_SECRET_KEY` → `S3_SECRET_ACCESS_KEY`
  - Added S3 variables to config_validator.py recommended list
  - Updated `DEPLOYMENT_SETUP.md` to use correct `S3_` prefix instead of `CLOUDFLARE_`
- **Stripe Webhook Secret**: Added `STRIPE_WEBHOOK_SECRET` to recommended environment variables in config validator

### Changed

- **SaaS Landing Page Hero**: Cleaned up broken demo functionality

  - Removed secondary CTA button ("Watch Demo") that opened non-existent demo_url
  - Changed header button from "Watch product tour" to "Explore features" linking to #features section
  - Made `hero_cta_secondary` optional in IntegratedHeroSection interface
- **Environment Variable Configuration**: Single source of truth policy

  - Removed all hardcoded URL fallbacks from `app/core/config.py` and `app/core/settings.py`
  - Missing critical env vars now trigger root admin notification at startup
  - Config validator (`app/services/config_validator.py`) notifies via Ntfy push + in-app notification

### Added

- **Ntfy Push Notifications**: Instant mobile/desktop push notifications for wedding planners via self-hosted Ntfy server

  - **New Service** (`app/services/ntfy_service.py`):
    - Self-hosted Ntfy integration (deployed on Coolify)
    - Unique topic per planner (hashed for privacy)
    - Emoji tags and priority levels per notification type
    - Helper methods: `send_rsvp_notification()`, `send_form_notification()`, `send_payment_notification()`, `send_contract_notification()`
  - **Config** (`app/core/config.py`): Added `SERVICE_URL_NTFY` environment variable
  - **Auto-Push**: Every planner activity notification also sends a push notification (non-blocking)
  - **New API Endpoints**:
    - `GET /admin/planner/push-subscription` - Get planner's unique Ntfy subscription URL
    - `POST /admin/planner/push-test` - Send test push notification
  - **Notification Types with Emoji Tags**:
    - Form submission: page_facing_up, inbox_tray
    - RSVP update: white_check_mark, busts_in_silhouette
    - Payment received: money_with_wings (high priority)
    - Payment failed: x, credit_card (urgent priority)
    - Contract signed: memo, black_nib (high priority)
    - Vendor response: package, handshake
  - **How Planners Subscribe**:
    1. Call `GET /admin/planner/push-subscription` to get unique topic URL
    2. Subscribe in Ntfy app (iOS/Android) or web browser
    3. Receive instant push notifications for all wedding activities
- **Planner Activity Notifications System**: Real-time activity notifications for wedding planners

  - **New MongoDB Collection**: `planner_notifications` for storing activity events
  - **Model** (`app/models/planner_notification.py`):
    - Notification types: `form_submission`, `rsvp_update`, `guest_message`, `payment_received`, `payment_failed`, `contract_signed`, `vendor_response`, `reminder`, `system`
    - Priority levels: low, medium, high
    - Deep links to relevant pages (action_url)
  - **Service** (`app/services/planner_notification_service.py`):
    - CRUD operations for planner notifications
    - Trigger helpers: `notify_form_submission()`, `notify_rsvp_update()`, `notify_payment_received()`, `notify_payment_failed()`, `notify_contract_signed()`, `notify_vendor_response()`
  - **API** (`app/api/planner_notifications.py`):
    - `GET /admin/planner/activity-notifications` - List notifications with filtering
    - `GET /admin/planner/activity-notifications/count` - Get unread count
    - `PUT /admin/planner/activity-notifications/{id}/read` - Mark as read
    - `PUT /admin/planner/activity-notifications/read-all` - Mark all as read
    - `DELETE /admin/planner/activity-notifications/{id}` - Delete notification
  - **Event Triggers**: Automatic notifications on:
    - RSVP submission → "John Doe confirmed attendance for 2 guests"
    - Form submission → "Jane Smith submitted a Contact Form"
    - Payment received → "$500.00 received from Customer"
    - Contract signed → "John Smith signed the contract"
  - **Bell Count**: Combined platform announcements + activity notifications
  - **Notifications Page**: Shows both platform and activity notifications, sorted by date
  - **Mark as Read**: Click notification to mark as read, "Mark all as read" button
  - **Real-time Bell Updates**: Bell refreshes on window focus and custom `notifications-updated` event
  - **New Notification Types**: Added colors for payment_received (emerald), payment_failed (red), contract_signed (indigo), vendor_response (amber)
- **Multi-Tenant Frontend Isolation**: Proper role-based access control

  - **Platform Page Consolidation**: Merged `/admin/platform/metrics` and `/admin/platform/errors` into single `/admin/platform` with tabs (Health, Errors, Performance, Backups)
  - **Root Admin Guards**: Added frontend access guards to `/admin/metrics`, `/admin/users`, `/admin/platform`
  - **Best Practices**: Toast notifications, loading states, `Promise.allSettled` for batch operations
- **Wedding Finance Autopilot (WFA)**: Automated payment collection system for wedding planners

  - **Package → Contract → Autopilot Flow**: Define packages once, couples sign, money flows automatically
  - **Data Models** (`app/models/autopilot.py`):
    - `Package`: Reusable service package templates with payment schedules
    - `Contract`: Signed agreements with couple info and Stripe payment methods
    - `ScheduledPayment`: Individual payment instances with retry logic
  - **AI Service Layer** (`app/services/ai_service.py`, `app/services/ai_cache_service.py`):
    - Gemini 2.0 Flash integration for budget insights, seating optimization, email drafting
    - Credit-based system: Boutique (100/mo), Signature (300/mo)
    - Content-addressed caching with TTL and event-driven invalidation
  - **Autopilot Engine** (`app/services/autopilot_service.py`):
    - Automatic payment processing via Stripe
    - Exponential backoff retry logic (24h → 48h → 96h)
    - Failed payment notifications
  - **Money Dashboard** (`app/admin/money/page.tsx`):
    - Unified financial view for planners
    - Incoming/outgoing payment tracking
    - Subscription summary with usage (weddings, AI credits)
    - Quick actions for payment retry, cancel, mark external, refund
  - **Contract API** (`app/api/contracts.py`):
    - Full CRUD for packages and contracts
    - Public signing endpoints (token-based, no auth)
    - Payment actions: retry, cancel, mark-paid-externally, refund
  - **Couple Portal**: Public dashboard for couples to view contracts and payment history
  - **Cloudflare Cron Workers**: Replaced Vercel crons with Cloudflare Workers
    - `uptime-cron.js`: Backend health monitoring every 5 minutes
    - `autopilot-cron.js`: Payment processing (due payments, retries, reminders)
  - **Cache Invalidation**: Budget and guest changes invalidate AI cache automatically
- **Enhanced Vendor Management System**: Comprehensive CRM for managing vendors, contracts, and payments

  - **Linear Tracking**: Epic [JOA-133](https://linear.app/joatlabs/issue/JOA-133) with 10 sub-tasks
  - **Backend Complete**: JOA-134 to JOA-140 (7 tickets)
  - **Frontend In Progress**: JOA-141 (Contract Canvas), JOA-142 (Payment Milestones), JOA-143 (VendorPaymentModal)
  - **PDF Contract Upload**: Planners can upload their own contract PDFs instead of using templates
    - S3 storage integration for secure document hosting
    - Full tracking workflow (draft → sent → viewed → signed)
    - Works alongside template-based contracts
  - **Form Data Integration**: Use vendor form submissions to populate contracts
    - Auto-extract fields from vendor inquiry forms
    - Smart suggestions for contract placeholders
    - One-click insertion of package details, pricing, and terms
  - **Contract Customization**: Edit contract sections after creation
    - Add/edit/remove sections with rich content
    - Custom clauses and terms additions
    - Modify terms & conditions and cancellation policies
  - **Payment Links**: Send Stripe payment links to vendors or couples
    - Multiple payment scenarios:
      - Couple → Vendor (vendor payment)
      - Couple → Planner (planning fee)
      - Vendor → Planner (referral commission)
    - Custom email messages and due dates
    - Real-time payment status tracking
    - Stripe webhook integration for automatic updates
  - **New Models**: `PaymentLink`, `ContractType`, `PayerType`, `RecipientType`
  - **New API Endpoints**:
    - `POST /admin/contracts/upload-pdf` - Upload existing PDF contracts
    - `GET /admin/contracts/{id}/form-data` - Get form data for contract
    - `POST /admin/contracts/{id}/apply-form-data` - Apply form data to placeholders
    - `PUT /admin/contracts/{id}/sections` - Update contract sections
    - `POST /admin/payment-links` - Create payment link
    - `POST /admin/payment-links/{id}/send` - Send payment link email
    - `GET /admin/payment-links` - List payment links
  - **Subscription Feature Gating**: `vendor_management` feature flag for plans
  - **Planner-Configurable Contract Settings**: Replaced hardcoded contract configuration with layered settings
    - Settings flow: `System Defaults (env vars) → Planner Preferences → Contract Creation`
    - Configurable options:
      - `token_expiry_days` (7-90): How long contract access links remain valid
      - `deposit_due_days` (1-60): Days after signing for deposit to be due
      - `payment_reminder_days`: Array of days before due date to send reminders
      - `auto_followup_days` (1-14): Days to auto-generate follow-up for unsigned contracts
      - `default_currency`: Default currency for contracts
    - New API endpoints:
      - `GET /vendors/settings/contract` - Get current settings with defaults
      - `PUT /vendors/settings/contract` - Update planner preferences
    - Added `ContractSettings` model and `contract_settings` field to `UserModel`

### Fixed

- **Vendor Service Security & Code Quality Fixes** (`app/services/vendor_service.py`):

  - **Authorization Hardening**: Added `created_by` parameter to `get_contract()` for ownership verification
    - All internal callers now pass `created_by` to enforce authorization: `send_contract()`, `update_contract()`, `update_contract_sections()`, `get_form_data_for_contract()`, `apply_form_data_to_contract()`, `create_payment_milestones()`
  - **Performance**: Added `get_dashboard_counts()` method using MongoDB aggregation
    - Replaced full document loads with efficient `count_documents()` and `$group` pipelines
    - Dashboard now fetches counts separately from limited recent items
  - **Data Integrity**: Fixed `get_payment_milestones()` to persist overdue status to database
    - Previously only marked milestones as overdue in memory, not persisted
    - Now updates MongoDB when milestones become overdue
  - **Code Quality**:
    - Added `validate_object_id()` utility function for consistent ObjectId validation
    - Added configuration constants: `TOKEN_EXPIRY_DAYS`, `DEPOSIT_DUE_DAYS`, `MAX_FILE_SIZE_MB`, `MEDIA_DOMAIN`
    - Renamed `type` parameter to `comm_type` in `_log_communication()` to avoid shadowing Python builtin
    - Moved `stripe` and `settings` imports to top-level (were inside functions)
    - Fixed silent error swallowing in `get_vendor_communications()` and `get_payment_links()` - now raise `HTTPException` instead of returning empty list
  - **Payment Links Expiration**: Added `expires_at` field to payment links
    - Expires 7 days after `due_date` or 30 days from creation if no due date
  - **Documentation**: Added docstring notes about atomic transaction limitations in `sign_contract()` and `record_payment()`
  - **Cleanup**: Removed unused model imports (`VendorProfile`, `VendorCategory`, etc.)
- **Budget Tracker API**: Fixed ObjectId serialization error causing "Failed to fetch budget summary"

  - Added proper serialization for MongoDB ObjectId fields in categories and alerts
  - Removed `ge=0` constraint on `remaining_budget` field to allow negative values when overspent
- **Wedding Party Sync**: Removed redundant "Wedding Party (Other)" group option

  - Wedding party now correctly comprises only: Maid of Honor, Bridesmaids, Best Man, Groomsmen
  - Updated guest group presets and wedding party sync mappings
- **Gallery Navigation**: Fixed 404 error on `/admin/gallery` - sidebar now correctly links to `/admin/gallery/upload`
- **Wedding Slug Collision**: Added unique slug enforcement to prevent URL conflicts when multiple planners use same couple names

  - Backend auto-appends suffix (e.g., `john-jane-2`) if slug already exists
  - Added unique database index on wedding slugs
- **Gallery Management Dark Mode**: Fixed dark mode styling on Gallery Management page

  - Updated titles, labels, tabs, cards, and badges for proper dark theme support
- **Wedding Party Sync API**: Fixed guest fetch using wrong API endpoint

  - Changed from `/admin/guests/{id}` to `/admin/guests?wedding_id={id}`
  - Added debug logging to help troubleshoot sync issues

## [1.4.0] - 2024-12-14

### Added

- **Planner Calendar & Task Management System**: Complete calendar feature for wedding planners to schedule and manage tasks
  - **Google Calendar Integration**:
    - OAuth 2.0 authentication flow with secure token storage
    - Two-way sync: tasks created in app sync to Google Calendar
    - Auto-refresh of expired tokens
    - Connect/disconnect functionality with token cleanup
  - **Task Management Backend** (`app/api/planner_calendar.py`):
    - Full CRUD operations for planner tasks
    - Task filtering by wedding, category, status, and date range
    - Bulk status updates for multiple tasks
    - Month view endpoint for calendar rendering
    - Upcoming tasks endpoint for dashboard widgets
  - **Calendar Models** (`app/models/calendar.py`):
    - `PlannerTaskModel` with comprehensive fields (priority, category, reminders, recurrence)
    - `CalendarTokenModel` for secure OAuth token storage
    - Support for all-day events and timed events
    - 17 wedding planning categories (venue, catering, photography, etc.)
  - **Google Calendar Service** (`app/services/google_calendar_service.py`):
    - Complete OAuth flow handling
    - Create, update, delete events in Google Calendar
    - Fetch events from connected calendar
    - Automatic token refresh on expiry
  - **Frontend Calendar UI** (`app/admin/planner/calendar/`):
    - Interactive month view calendar with task display
    - Click-to-create tasks on any date
    - Task modal for creating/editing with full field support
    - Google Calendar connection component with status display
    - Upcoming tasks sidebar widget
    - Priority-based color coding
    - OAuth callback page for handling Google authorization
  - **TypeScript API Client** (`app/services/calendarApi.ts`):
    - Full type definitions for tasks and calendar operations
    - Helper functions for formatting dates and priorities
    - Category and status label configurations
  - **Navigation**: Added "Calendar" item to planner sidebar navigation
  - **New Dependencies**: `google-api-python-client`, `google-auth-oauthlib`, `google-auth`, `icalendar`
  - **Database Collections**: Added `calendar_tokens` and `planner_tasks` collections
  - **Configuration**: Added Google OAuth settings to `app/core/config.py`
  - **Testing**:
    - Unit tests for calendar service (`tests/unit/test_calendar_service.py`)
    - E2E tests for calendar UI (`tests/planner-calendar.spec.ts`)
    - Pytest configuration (`pytest.ini`)
    - Added `pytest` and `pytest-asyncio` dependencies
- **Redis Service for Development**: Added Redis service to `docker-compose.yml` for development environment parity with production
- **System Metrics Monitoring**: Added `psutil` package to `requirements.txt` for CPU, memory, and disk monitoring in Platform Metrics dashboard
- **Authentication Loading State**: Added `isLoading` state to `AdminContext` for proper authentication state management
- **Comprehensive Dark Mode Support**: Full dark mode theming across all admin pages
  - Theme toggle in header supporting light/dark/system modes
  - ThemeContext for managing theme state with localStorage persistence
  - System preference detection via `prefers-color-scheme` media query
- Enhanced error handling and logging for SAAS configuration saves
- Clean configuration object creation to prevent circular references
- Authentication token validation for admin operations
- Type-safe parameter handling for configuration save operations
- **OTP Guest Verification System**: Complete one-time password verification flow for wedding guest access
  - New `/otp/send-by-contact` endpoint for sending verification codes by phone/email
  - Phone number normalization supporting multiple formats (E.164 variants)
  - Wedding-specific OTP verification with `wedding_id` context
  - Fallback mechanism for Twilio SMS (Messaging Service → Direct phone number)
- Security logging and rate limiting for guest verification attempts
- Debug logging throughout guest verification chain for troubleshooting

### Removed

- **Wedding Planners Tab from SaaS Page**: Removed duplicate "Wedding Planners" tab from `/admin/saas` page
  - Planner management is now exclusively accessed via the sidebar "Planners" navigation (`/admin/users`)
  - Eliminates duplicate functionality and reduces UI confusion
  - SaaS page now focuses on: Overview, Subscription Plans, SAAS Content, and Theme & Design

### Fixed

- **CRITICAL**: Fixed login redirect race condition in `AdminRouteGuard`
  - Added `isLoading` state to `AdminContext.tsx` to track authentication initialization
  - Updated `AdminRouteGuard.tsx` to wait for auth check completion before redirecting
  - Changed post-login navigation from `router.push()` to `window.location.href` for immediate redirect
  - Root cause: Guard was checking `isAuthenticated` before `useEffect` loaded token from storage
- **CRITICAL**: Fixed Platform Metrics page crashes due to undefined nested objects
  - Added optional chaining (`?.`) and nullish coalescing (`??`) throughout `app/admin/platform/metrics/page.tsx`
  - Protected access to `metrics.health.database`, `metrics.errors`, `metrics.business`, `metrics.performance`
  - Page now gracefully handles missing or incomplete API responses
- **CRITICAL**: Fixed API 404 errors for `/admin/platform/*` endpoints
  - Changed router prefix in `app/api/admin_platform_metrics.py` from `/admin/platform` to `/platform`
  - Router was included with `/admin` prefix in `main.py`, causing double prefix `/admin/admin/platform/`
- **Error Logs Page Dark Mode**: Fixed dark mode styling in `app/admin/platform/errors/page.tsx`
  - Added `bg-opacity-100 dark:bg-opacity-100` to Card components to prevent washed-out appearance
  - Fixed duplicate CSS classes in select dropdowns
  - Corrected hover state from `dark:bg-slate-700` to `dark:hover:bg-slate-700` on table rows
- **Missing Components**: Restored accidentally deleted files from git history
  - `app/contexts/ThemeContext.tsx` - Theme management context
  - `app/admin/components/Sidebar.tsx` - Admin sidebar navigation
  - `app/admin/components/TopHeader.tsx` - Admin top header component
- **Missing Dependencies**: Added `framer-motion` package for admin dashboard animations
- **Dark Mode Styling Fixes**: Comprehensive dark mode support across admin dashboard
  - Fixed `tailwind.config.js` to use `darkMode: 'class'` instead of `'media'` for class-based toggling
  - Fixed `Card` component (`app/components/ui/Card.tsx`) with `dark:bg-slate-800` backgrounds
  - Fixed `CardTitle` and `CardDescription` components with dark text variants
  - Fixed Platform Health Overview page (`/admin/page.tsx`) - all cards, tables, and metrics
  - Fixed SaaS Management page (`/admin/saas/page.tsx`) - navigation tabs and content
  - Fixed Platform Metrics page (`/admin/platform/metrics/page.tsx`) - hover states and quick action links
  - Fixed Error Details page (`/admin/platform/errors/[errorId]/page.tsx`) - all sections and badges
  - Removed hardcoded light backgrounds from vendors, guests, and weddings pages
  - Added dark mode hover states (`dark:hover:bg-slate-700`) throughout
  - Fixed select dropdowns, code blocks, and form elements for dark mode
- **CRITICAL**: Fixed async/await chain in guest verification flow preventing authentication
  - Made `verify_guest_access` async and added `await` to all service calls
  - Fixed coroutine access errors in `guest_verification_service.py`, `guest_verification.py`, `gallery_public.py`, `wedding.py`
- **CRITICAL**: Fixed OTP verification endpoint returning 403 when OTP is required
  - Now correctly returns `{otp_required: true, wedding_id}` response instead of throwing error
- **CRITICAL**: Fixed OTP service signature mismatch
  - Rewrote `verify_otp` method to accept `wedding_id`, `contact`, `otp_code` instead of `guest_id`, `otp`
  - Added phone number normalization for cross-format matching
- **CRITICAL**: Fixed frontend OTP endpoint URL from `/api/otp/send` to `/otp/send-by-contact`
- **CRITICAL**: Fixed NoneType error in OTP verification by adding missing Pydantic model fields
  - Added `otp_code` and `contact` fields to `GuestVerificationRequest` model
- Circular reference error in SAAS landing page content save functionality
- JSON stringify issues when saving SAAS configuration
- React state timing issues in modal save operations
- Improved error propagation and user feedback for failed saves
- Missing database fields in WeddingModel (`assigned_planner_id`, `updated_by`, `guest_count`, `total_budget`, `venue`)

### Changed

- Enhanced `handleSaveSaasConfig` function with better error handling
- Updated modal save handler to pass configuration directly
- Improved error message parsing from API responses
- **Guest Verification Flow**: Complete redesign from name/phone matching to secure OTP-based verification
  - Deprecated direct name/phone matching (vulnerable to social engineering)
  - Implemented two-step verification: contact submission → OTP validation
- Frontend `GuestVerificationModal.tsx` now captures and uses `wedding_id` from verification response
- Enhanced Twilio SMS service with automatic fallback from Messaging Service to direct phone number

### Security

- Added proper authentication checks for admin operations
- Implemented secure token validation for configuration saves
- **Enhanced Guest Verification Security**:
  - Input sanitization to prevent NoSQL injection attacks
  - Rate limiting (5 attempts per 5 minutes) to prevent brute force attacks
  - Security audit logging for all verification attempts
  - Constant-time password comparison to prevent timing attacks
  - Replaced vulnerable name/phone matching with secure OTP verification

## Unreleased

### Fixed

- **Couple portal archived/read-only lifecycle alignment** (`/app/api/couple_portal.py`, `/app/services/meeting_invite_service.py`, `/app/couple/dashboard/page.tsx`, `/app/couple/forms/[formId]/page.tsx`, `/app/couple/components/CoupleSidebar.tsx`, `/app/admin/weddings/[id]/page.tsx`, `/tests/backend/test_couple_archived_dashboard_contract.py`, `/tests/backend/test_meeting_invite_service_contract.py`, `/tests/couple-portal-lifecycle.spec.ts`, `/playwright.config.ts`) — Normalized the archived dashboard payload to a stable dashboard contract, made archived timeline and form surfaces render as explicitly read-only instead of looking like session failures, shipped a real couple meetings destination for invite emails under `/couple/dashboard?section=meetings`, aligned the admin wedding couple tab with backend lifecycle states like `owner_cancelled` and `archived_readonly`, and added browser-level regression coverage on the real local ports that the app derives for API requests.
- **Shared planner calendar hardening pass** (`/app/api/planner_calendar.py`, `/app/api/scheduler_jobs.py`, `/app/services/calendar_job_service.py`, `/app/services/calendar_idempotency_service.py`, `/app/services/calendar_maintenance_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/google_calendar_service.py`, `/app/services/meeting_invite_service.py`, `/app/services/calendar_audit_service.py`, `/app/services/calendarApi.ts`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/admin/planner/calendar/page.tsx`, `/app/core/database_indexes.py`, `/tests/backend/test_shared_calendar_v1_contract.py`, `/tests/backend/test_couple_permission_contract.py`) — Moved couple ICS invite send/update/cancel work off the meeting request path into a database-backed calendar job queue with scheduler processing, added meeting mutation idempotency and optimistic version checks, introduced per-target sync retry/backoff plus scheduled drift checks, classified Google rate-limit/quota/provider failures into retryable vs terminal states, added short-lived external-event caching for shared calendar aggregation, and wrote planner activity-log audit events for connection changes, meeting lifecycle changes, invite delivery, and sync retry/failure paths. The frontend idempotency wiring now uses per-intent keys for meeting create/update/delete flows instead of collapsing identical payloads globally, so flaky retries stay safe without turning a later deliberate duplicate meeting into a replayed response.
- **Shared planner calendar deferred cleanup tracked explicitly** (`/app/services/google_calendar_service.py`, `/app/models/calendar_connection.py`, `/app/models/calendar.py`) — The new hardening layer ships without removing the legacy `google_event_id` / `synced_to_google` mirrors or the legacy token collection writes yet, and without the future wedding/role-scoped calendar policy controls beyond `allowed_scheduler_user_ids`; those remain follow-up cleanup tasks rather than hidden assumptions inside the release-ready meeting flow.
- **Archived meetings copy now matches the backend contract** (`/app/couple/dashboard/page.tsx`, `/tests/couple-portal-lifecycle.spec.ts`) — Tightened the archived meetings banner text so it no longer implies archived portals still show saved meeting details when `/couple/portal/meetings` intentionally returns no active meetings for archived weddings, and extended the PR 2 browser regression to assert the archived meetings empty-state copy.
- **Couple invite recovery UX** (`/app/api/couple_invite.py`, `/app/admin/weddings/[id]/page.tsx`) — Exposed the current live `setup_link` for pending-setup couples and added a direct `Copy Link` action in the wedding couple tab, so planners can recover and share the active invite URL without rotating the token every time they need access again.
- **Couple portal identity normalization** (`/app/api/couple_auth.py`, `/app/dependencies/couple_auth.py`, `/app/api/couple_portal.py`, `/app/api/couple_notification_stream.py`, `/app/utils/couple_identity.py`, `/app/utils/couple_realtime.py`, `/tests/backend/test_couple_identity_subject.py`) — Switched couple session tokens from email-based subjects to stable couple-record ids, added legacy-session fallback that fails closed when one email maps to multiple couple accounts, moved couple realtime/push channels onto the same record-scoped principal, and blocked ambiguous duplicate-email login/reset flows instead of letting them resolve arbitrarily to the wrong wedding portal.
- **Planner calendar scope typing cleanup** (`/app/dependencies/auth_extended.py`, `/app/api/planner_calendar.py`) — Replaced the loose calendar-scope return type with a dedicated `TypedDict` so `accessible_wedding_ids` is inferred as `list[str] | None` instead of `object | None` at shared-calendar aggregation call sites.
- **Forms API typing cleanup** (`/app/api/forms.py`) — Replaced the loose owner-scope dictionary type with a dedicated `TypedDict` and split the static template catalog into a typed helper so repeated Pylance/mypy errors from `owner_scope[...]` and template lookups no longer cascade across the file.
- **Forms router startup blocker** (`/app/api/forms.py`) — Removed the invalid `Optional[Request]` route parameter from `GET /forms` so FastAPI no longer treats the injected request object as a response-model field and crashes during router registration at app startup.
- **Admin login double-attempt regression** (`/app/contexts/AdminContext.tsx`) — Removed the March 26, 2026 hard-refresh login handoff that was discarding the in-memory token before the destination admin route could hydrate, and now commits the authenticated token/profile atomically before using client-side navigation so successful admin sign-ins do not bounce back to `/admin/login` on the first attempt.
- **SaaS ad-platform migration completion** (`/app/admin/saas/page.tsx`) — Restored the missing ad-platform settings that were left behind during the move from `/admin/ads`, including fraud detection, vendor signup controls, data export, and pipeline status, and corrected the SaaS tab to use the real backend config keys instead of partial placeholder names.
- **Ad platform config source-of-truth cleanup** (`/app/admin/ads/page.tsx`, `/app/admin/saas/page.tsx`) — Removed the stale duplicate "Platform Config" tab from the root-admin ads page and added a direct deep link into the SaaS Management ad-platform tab so configuration now lives in one place instead of two diverging surfaces.
- **Planner communications ownership cleanup** (`/app/admin/guests/page.tsx`, `/app/admin/import/page.tsx`, `/app/admin/communications/components/CommunicationsRemindersView.tsx`, `/app/admin/communications/components/CommunicationsTabs.tsx`) — Removed the duplicate guest-page import/reminder modals, routed guest reminder and bulk-message actions into the canonical Communications workspace, hydrated the import page from the selected wedding context, and upgraded individual communications to handle guest email-only recipients so the move does not regress planner messaging capability.
- **Planner/team ownership and permissions follow-through** (`/app/core/settings.py`, `/app/api/planner_metrics.py`, `/app/services/team_management_service.py`, `/app/api/couple_portal.py`, `/app/api/forms.py`, `/app/services/form_service.py`, `/app/admin/communications/components/CommunicationsTabs.tsx`, `/app/admin/communications/components/CommunicationsRemindersView.tsx`) — Normalized local loopback CORS aliases for real browser QA, fixed planner-owned wedding queries and assigned-wedding validation to use the codebase’s string wedding ids for team members, moved form and custom-template ownership back to canonical planner scope instead of team-member email scope, and aligned communications tabs/direct routes with the actual team permission model so browser-verified team role combinations match backend enforcement.
- **Shared planner calendar v1 foundation** (`/app/api/planner_calendar.py`, `/app/services/google_calendar_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/calendar_aggregation_service.py`, `/app/services/meeting_invite_service.py`, `/app/admin/planner/calendar/page.tsx`, `/app/admin/planner/calendar/components/GoogleCalendarConnect.tsx`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/services/calendarApi.ts`, `/app/privacy/page.tsx`, `/app/terms/page.tsx`, `/app/support/page.tsx`, `/app/google-calendar/page.tsx`, `/app/google-data-deletion/page.tsx`) — Shifted planner scheduling to a business-owned shared-calendar model by adding signed Google OAuth state, encrypted calendar connections, per-target sync records, fail-closed sync target resolution, meeting invite delivery via email/ICS, a multi-connection planner calendar workspace, and public legal/help surfaces aligned to the shipped Google Calendar behavior.
- **Shared planner calendar review fixes** (`/app/api/planner_calendar.py`, `/app/api/couple_portal.py`, `/app/dependencies/auth_extended.py`, `/app/models/calendar.py`, `/app/services/google_calendar_service.py`, `/app/services/calendar_sync_service.py`, `/app/services/calendar_aggregation_service.py`, `/app/admin/planner/calendar/components/TaskModal.tsx`, `/app/services/calendarApi.ts`, `/tests/backend/test_shared_calendar_v1_contract.py`) — Closed the first QA review gaps in the shared calendar rollout by enforcing planner-business ownership on connection mutations, orphaning sync mappings when a connection is removed, preserving owner-managed connection settings on reconnect, attaching selected timezones to naive schedule inputs, persisting explicit sync-target overrides across edits, restoring calendar-specific permission enforcement in the couple meeting flow, and tightening availability to the selected staff calendars only, with focused regression coverage for those contracts.
- Separated admin token refresh rate limiting from login throttling so `/admin/token/refresh` no longer shares the 5-per-minute login bucket or throws a middleware exception group instead of a clean `429` response.
- Deduplicated client-side admin auth bootstrap refresh calls so concurrent mounts reuse one in-flight refresh request instead of stampeding the refresh endpoint.
### Security

- Added host-header allowlisting through FastAPI `TrustedHostMiddleware`, with trusted hosts derived from deployment URLs by default and overrideable via `ALLOWED_HOSTS`.

## [1.3.0] - 2024-08-21

### Added

- Comprehensive SAAS platform features and landing page
- User management service with invitation handling
- Account setup workflow for wedding planners
- Subscription plan seeding functionality
- Modern3D background design for SAAS landing page
- Mobile-friendly responsive design updates

### Fixed

- Email service rate limiting issues with Resend API (added 600ms delay between sends)
- Admin RSVP service JSON serialization errors with MongoDB ISODate objects
- RSVP form functionality and guest display in admin panel
- Guest ID handling for both string and ObjectId formats

### Changed

- Removed emojis from SAAS landing page for cleaner professional appearance
- Improved RSVP query handling to avoid MongoDB mixed type issues
- Enhanced error handling for missing guest IDs in RSVP operations

### Security

- Added proper authentication checks for admin operations
- Implemented secure token validation for configuration saves

## Previous Versions

### [1.2.x] - Various dates

- Core wedding planning functionality
- Guest management and RSVP system
- Admin panel development
- Gallery and vendor management features
- Email reminder system with Telnyx integration
- Multi-tenant architecture foundation

---

## Release Notes

### How to Read This Changelog

- **Added** for new features
- **Changed** for changes in existing functionality
- **Deprecated** for soon-to-be removed features
- **Removed** for now removed features
- **Fixed** for any bug fixes
- **Security** for vulnerability fixes

### Versioning

This project follows [Semantic Versioning](https://semver.org/):

- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality additions
- PATCH version for backwards-compatible bug fixes
- **Calendar scheduler target now follows environment config instead of a separate enable gate** (`/.github/workflows/calendar-scheduler.yml`, `/app/api/scheduler_jobs.py`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`) — Removed the `ENABLE_PRODUCTION_CALENDAR_SCHEDULER` control path and switched the scheduler workflow to use the environment-scoped `SCHEDULER_BASE_URL` variable as its API target, with preflight checks against `GET /health/readyz` and the scheduler routes so missing or not-yet-promoted environments skip cleanly instead of failing. `/scheduler/health` continues to report HMAC-backed scheduler configuration truthfully, and the deployment guide now documents the environment-scoped scheduler URL setup instead of a separate scheduler enable toggle.
- **Coolify deploy workflows now resolve environment URLs from GitHub environment config** (`/.github/workflows/coolify-deploy-shared.yml`, `/.github/workflows/deploy-coolify.yml`, `/.github/workflows/promote-coolify-production.yml`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`) — Removed the hardcoded staging and production frontend/API domains from the Coolify deploy and promotion workflows. The shared deploy workflow now resolves `FRONTEND_URL` and `NEXT_PUBLIC_API_BASE_URL` from the target GitHub environment and uses those values for environment links and smoke verification, so deployment URLs come from the same environment-scoped config as the app instead of being duplicated in workflow code.
- **Calendar scheduler preflight now degrades safely on malformed or absent environment URLs** (`/.github/workflows/calendar-scheduler.yml`) — Hardened the scheduler preflight step so it trims `SCHEDULER_BASE_URL`, validates that it is an HTTP(S) URL, and handles curl/body-file failures without crashing the job. Missing, malformed, or not-yet-live scheduler targets now resolve to a clean skip result instead of a red workflow failure.
- **Runtime smoke-account seeding now provisions deploy verification identities** (`/scripts/setup_smoke_accounts.py`, `/scripts/bootstrap_runtime.py`, `/Dockerfile`, `/Dockerfile.backend`, `/Dockerfile.coolify`, `/docker-compose.yml`, `/docker-compose.test.yml`, `/scripts/deploy/verify_environment.py`, `/docs/plans/COOLIFY_SPLIT_DEPLOY_GUIDE.md`) — Added an idempotent runtime seeder for smoke planner/couple/public-wedding accounts, separate from root-admin setup. Backend bootstraps now run through a single bootstrap script so startup seeding stays aligned across local, backend-only, and Coolify containers. Smoke public-slug handling now tolerates either a slug or a full URL so deploy verification and runtime seeding normalize the same way.
- **Media storage is now split by domain behind one explicit storage contract** (`/app/core/settings.py`, `/app/services/media_storage.py`, `/app/services/gallery_media_service.py`, `/app/services/blog_upload_service.py`, `/app/services/ad_upload_service.py`, `/app/services/guest_media_service.py`, `/app/services/vendor_service.py`, `/app/jobs/vendor_scraper/logo_uploader.py`, `/app/utils/upload_image.py`) — Replaced the mixed gallery/blog/ad storage service with targeted gallery, blog, and ad services backed by a shared typed media-storage layer. Secondary guest/ad/blog buckets and domains now fail closed instead of silently falling back to the primary media bucket/domain, and the deploy docs now reflect the corrected `knowledgeable-saas-blogs` bucket contract plus required browser-upload CORS on dedicated upload buckets.
- **Vendor ad portal signup now uses the shared auth shell instead of a one-off dark page** (`/app/portal/ads/layout.tsx`, `/app/portal/ads/components/VendorAuthShell.tsx`, `/app/portal/ads/signup/page.tsx`) — Unified the vendor signup route with the same wedding-branded auth shell, typography, and shared vendor style primitives already used by vendor login and forced password change. This closes the visual drift where `/portal/ads/signup` looked like a separate utility app instead of part of the platform.
- **Vendor authenticated workspace now follows the admin/planner shell contract** (`/app/portal/ads/layout.tsx`, `/app/portal/ads/page.tsx`, `/tests/media-storage-centralization.spec.ts`) — Removed the vendor-only authenticated chrome and moved the vendor portal onto the same `font-sans`, sidebar, top-header, and page-header rhythm used by the root-admin and planner surfaces. The vendor overview page no longer uses a separate marketing-style hero, and the browser regression now expects the new dashboard contract instead of the removed “Welcome back” landing panel.
- **Vendor ad portal public auth bootstrap and media-save races are now fail-closed** (`/app/portal/ads/layout.tsx`, `/app/services/campaignAdvertisingApi.ts`, `/app/portal/ads/components/VendorMediaUploader.tsx`, `/app/portal/ads/creatives/page.tsx`, `/app/portal/ads/campaigns/new/page.tsx`, `/app/portal/ads/settings/page.tsx`, `/tests/media-storage-centralization.spec.ts`) — Stopped the public vendor signup route from calling admin token refresh at all, switched authenticated ad-platform GETs to `no-store` so post-mutation reads cannot render stale creatives or logos, and made the shared vendor media uploader report inflight state so create/update/save/navigation paths block until uploads finish. The browser regression suite now waits for real preview replacement instead of relying on brittle timing.
- **Admin browser media tests now use the canonical root-admin env contract** (`/tests/media-storage-centralization.spec.ts`) — Removed the Playwright-only root-admin password alias and made the browser suite load `.env` directly, so root-admin KB/blog editor checks authenticate with the same `ROOT_ADMIN_EMAIL` and `ROOT_ADMIN_PASSWORD` values the app itself uses.
- **Guest memories upload now uses a real button-triggered file picker** (`/app/[slug]/upload/[uploadToken]/upload-client.tsx`, `/tests/unit/guestMemoriesUpload.test.tsx`, `/tests/unit/testDom.ts`) — Replaced the brittle label-hitbox upload surface with an explicit button that prefers the browser’s native `showPicker()` API and falls back to `click()` for older engines. Added focused frontend regression coverage for both picker paths so the public memories flow cannot silently lose file-picker activation again.
- **Public couple payments now use opaque request tokens end-to-end** (`/app/api/stripe_payment.py`, `/app/pay/[id]/page.tsx`, `/app/pay/success/page.tsx`, `/app/components/payments/CollectPaymentModal.tsx`, `/tests/backend/test_payment_intent_summary.py`) — Replaced the public payment-page and success-page contract with token-based `payment-request` endpoints that no longer surface raw Stripe `PaymentIntent.id` values. The planner-side payment modal now fails soft when clipboard permissions are denied and preserves its created-link state until the planner closes it, instead of unmounting the success view during a parent refresh.
