# Security Best Practices Report

## Executive Summary

This report was refreshed on April 1, 2026 after re-checking the earlier release-hardening work and reviewing the newer guest memories and public-link flows.

Current status:

- The project is **ready for staging**.
- The earlier **critical** and **high** deployment blockers remain fixed.
- No new **critical**, **high**, or currently-open **medium** app-code findings remain in this refresh.
- The guest-facing RSVP and OTP handoff flow was remediated in this pass by exchanging invite tokens into a short-lived HttpOnly guest session and moving the guest UI onto session-backed OTP and RSVP endpoints.
- The remaining work now splits into two tracks:
  - production-like validation of the already-fixed blockers and the new guest-session flow
  - retirement of temporary legacy query-token compatibility once older emailed links age out

## New Or Remaining Findings

### SP-008: Guest RSVP and OTP handoff no longer persist raw invite tokens in browser state — Medium / Resolved

**Impact:** The prior guest flow extended raw invite-token exposure by translating path-token invites back into query parameters, persisting tokens in browser storage, and reusing the raw token as the client credential for OTP, RSVP, and gallery access. That avoidable exposure window is now closed in the canonical flow.

Evidence of the fix in the current codebase:

- Guest invite links are now exchanged into a short-lived HttpOnly `guest_access_session` cookie via [app/api/guest_verification.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/guest_verification.py) and [app/dependencies/guest_access.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/dependencies/guest_access.py).
- The canonical invite page now performs a one-time exchange and lands the browser on `/{slug}#rsvp` instead of translating the invite token back into a query-string URL in [app/[slug]/invite/[token]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/[slug]/invite/[token]/page.tsx).
- The public landing page now uses the guest session endpoint instead of `sessionStorage` durability, while still immediately cleaning legacy `?rsvp_token=` links during compatibility exchange in [app/[slug]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/[slug]/page.tsx).
- OTP request, OTP verify, RSVP submit, and verified gallery fetches now use session-backed endpoints in:
  - [app/api/otp.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/otp.py)
  - [app/api/rspv.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/rspv.py)
  - [app/api/gallery_public.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/gallery_public.py)
  - [app/components/RSVPModal.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/components/RSVPModal.tsx)
  - [app/components/RSVPForm.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/components/RSVPForm.tsx)
  - [app/components/GuestVerificationModal.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/components/GuestVerificationModal.tsx)
  - [app/utils/publicGallery.ts](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/utils/publicGallery.ts)
- Guest-facing API responses now strip the raw guest token before returning guest data in [app/services/guest_verification_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/guest_verification_service.py) and [app/services/otp_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/otp_service.py).

### SP-008A: Temporary legacy query-token compatibility remains as bounded low-risk debt — Low / Scheduled Cleanup

**Impact:** Already-issued legacy guest links that still carry `?rsvp_token=` or `/otp/verify?token=` can still place the token on the first inbound request line before the app exchanges it into the safer guest session and cleans the visible URL. This no longer creates long-lived browser storage or canonical client reuse, but it can still show up once in edge logs or copied legacy URLs until those old links age out.

Current bounded compatibility points:

- [app/[slug]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/[slug]/page.tsx) still accepts `rsvp_token` only long enough to exchange it and immediately remove it from the address bar.
- [app/otp/verify/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/otp/verify/page.tsx) still accepts a legacy `token` query param only long enough to exchange it and immediately rewrite the URL to a slug-only form.

This is now scheduled cleanup, not a staging blocker.

## Rechecked Healthy Areas

### Couple, account setup/reset, and team invite flows now use canonical path tokens with immediate query cleanup

- Couple invitation and couple reset links now generate canonical path-token URLs in [app/api/couple_invite.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/couple_invite.py) and [app/api/couple_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/couple_auth.py).
- General account setup, admin reset-password, and team invitation emails now generate canonical path-token URLs in [app/services/user_management_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/user_management_service.py) and [app/services/team_management_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/team_management_service.py).
- The public entry pages for couple setup, couple reset, admin setup-account, admin reset-password, and team accept now redirect legacy `?token=` URLs onto canonical path-token routes before the client settles on the old address bar state in:
  - [app/couple/setup/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/couple/setup/page.tsx)
  - [app/couple/reset-password/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/couple/reset-password/page.tsx)
  - [app/setup-account/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/setup-account/page.tsx)
  - [app/reset-password/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/reset-password/page.tsx)
  - [app/admin/team/accept/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/team/accept/page.tsx)
- The corresponding client pages now take route-provided token props instead of reading token query parameters directly, while preserving the existing safer backend contracts that already validated tokens on path endpoints and sent tokens in request bodies.

### Vendor public flows now use canonical path tokens, and vendor contract signing no longer places PII in the URL

- Canonical vendor form links are now path-based in [app/api/vendor_forms.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/vendor_forms.py), [app/vendor-form/[form_id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-form/[form_id]/page.tsx), and [app/vendor-form/[form_id]/[token]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-form/[form_id]/[token]/page.tsx).
- Canonical vendor contract links are now path-based in [app/services/vendor_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/vendor_service.py), [app/vendor-contract/[id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-contract/[id]/page.tsx), and [app/vendor-contract/[id]/[token]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-contract/[id]/[token]/page.tsx).
- The public vendor contract signing payload now sends signer details in the request body, not in the URL, in [app/api/vendor_contract_public.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/vendor_contract_public.py), [app/vendor-contract/[id]/PublicContractPageClient.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-contract/[id]/PublicContractPageClient.tsx), and [app/services/vendorManagementApi.ts](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/vendorManagementApi.ts).
- Old query-token links are still accepted temporarily, but they are immediately redirected to canonical path-token routes by [app/vendor-form/[form_id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-form/[form_id]/page.tsx) and [app/vendor-contract/[id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-contract/[id]/page.tsx).

### Guest memories upload and review flow is using the safer transport model

- Guest memories public uploads use path-scoped upload tokens rather than query-string bearer parameters in [app/api/guest_memories.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/guest_memories.py).
- Upload tokens are hashed at rest, public access is rate-limited per client/token scope, uploaded objects are revalidated against reserved size and MIME constraints, and couple-facing asset access is re-exposed through authenticated app endpoints in [app/services/guest_media_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/guest_media_service.py).

### Inbound email HTML rendering is still sanitized server-side

- The admin inbox still renders HTML, but the rendering path remains server-sanitized before it reaches the frontend. This did not surface as a current blocker in the refresh.

### Form redirect URLs are still validated before use

- Redirect targets continue to be validated before the client follows them, which materially reduces open-redirect risk on the public form completion path.

## Previously Blocking Findings That Remain Resolved

### SP-001: SSE authentication no longer places bearer credentials in URL query strings

- The SSE endpoint now authenticates through the existing `admin_token` HttpOnly cookie in [app/api/notification_stream.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py).
- The frontend now opens `EventSource` without a `?token=` parameter and relies on `withCredentials` in [app/contexts/SSEContext.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/SSEContext.tsx).

### SP-002: FastAPI docs and OpenAPI exposure are now environment-gated

- Docs exposure is controlled by `ENABLE_API_DOCS` in [app/core/settings.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/core/settings.py).
- `docs_url`, `redoc_url`, and `openapi_url` are disabled automatically in production unless explicitly re-enabled in [app/main.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py).

### SP-003 / SP-004 / SP-005: KB contract, route, and retrieval alignment issues remain resolved

- The KB status contract is consistently `draft`, `published`, and `archived` across [app/models/knowledge_base.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py), [app/api/knowledge_base.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py), and [app/admin/components/kb/ArticleEditor.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx).
- The miswired double-prefixed feedback route is gone, and article list retrieval excludes large content fields at query time in [app/services/knowledge_base_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py).

### SP-006: Deprecated admin auth/API bridge surface remains removed

- The deprecated `AuthContext` / `APIContext` compatibility files and the dead generic admin request-hook chain are no longer part of the active app surface.
- [app/contexts/AdminContext.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/AdminContext.tsx) is now the only supported admin auth/API surface.

### SP-007: Host header validation remains enforced in the FastAPI middleware stack

- `ALLOWED_HOSTS` parsing and derived trusted-host generation live in [app/core/settings.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/core/settings.py).
- `TrustedHostMiddleware` is active in [app/main.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py).

## Verification Basis For This Refresh

This refresh included a concrete remediation pass plus focused regression verification.

Code paths explicitly rechecked:

- [app/api/guest_memories.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/guest_memories.py)
- [app/services/guest_media_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/guest_media_service.py)
- [app/api/vendor_forms.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/vendor_forms.py)
- [app/vendor-form/[form_id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-form/[form_id]/page.tsx)
- [app/api/vendor_contract_public.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/vendor_contract_public.py)
- [app/vendor-contract/[id]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/vendor-contract/[id]/page.tsx)
- [app/api/couple_auth.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/couple_auth.py)
- [app/api/couple_invite.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/couple_invite.py)
- [app/services/user_management_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/user_management_service.py)
- [app/services/team_management_service.py](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/team_management_service.py)
- [app/couple/setup/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/couple/setup/page.tsx)
- [app/couple/reset-password/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/couple/reset-password/page.tsx)
- [app/setup-account/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/setup-account/page.tsx)
- [app/reset-password/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/reset-password/page.tsx)
- [app/admin/team/accept/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/team/accept/page.tsx)
- [app/[slug]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/[slug]/page.tsx)
- [app/[slug]/invite/[token]/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/[slug]/invite/[token]/page.tsx)
- [app/otp/verify/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/otp/verify/page.tsx)

Latest known verification from the earlier hardening work already landed:

- `./.venv/bin/python -m pytest tests/backend/test_settings.py tests/backend/test_notification_stream_contract.py tests/backend/test_knowledge_base_contract.py tests/backend/test_guest_memories_service.py -q`
- `./.venv/bin/python -m compileall app`
- `npm run build`

Verification completed for this vendor-flow hardening pass:

- `./.venv/bin/python -m pytest tests/backend/test_public_token_transport_contract.py -q`
- `./.venv/bin/python -m compileall app`
- `npm run build`
- `curl -I -s 'http://localhost:3000/vendor-form/aaaaaaaaaaaaaaaaaaaaaaaa?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/vendor-form/aaaaaaaaaaaaaaaaaaaaaaaa/dummy-token`
- `curl -I -s 'http://localhost:3000/vendor-contract/aaaaaaaaaaaaaaaaaaaaaaaa?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/vendor-contract/aaaaaaaaaaaaaaaaaaaaaaaa/dummy-token`

Verification completed for this couple/account/team transport-hardening pass:

- `./.venv/bin/python -m pytest tests/backend/test_setup_reset_token_transport_contract.py -q`
- `./.venv/bin/python -m compileall app`
- `curl --max-time 10 -s -o /dev/null -D - 'http://localhost:3000/couple/setup?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/couple/setup/dummy-token`
- `curl --max-time 10 -s -o /dev/null -D - 'http://localhost:3000/couple/reset-password?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/couple/reset-password/dummy-token`
- `curl --max-time 10 -s -o /dev/null -D - 'http://localhost:3000/setup-account?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/setup-account/dummy-token`
- `curl --max-time 10 -s -o /dev/null -D - 'http://localhost:3000/reset-password?token=dummy-token'`
  Result: `307 Temporary Redirect` to `/reset-password/dummy-token`
- `curl --max-time 10 -s 'http://localhost:3000/admin/team/accept?token=dummy-token'`
  Result: Next.js dev-mode response includes a `NEXT_REDIRECT` digest targeting `/admin/team/accept/dummy-token`; this route is redirecting through the RSC payload rather than returning a bare `307` header in the current dev server.
- `npm run build`
  Result: currently blocked by an unrelated untracked local file, [app/admin/scraper/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/scraper/page.tsx), which is not part of this remediation slice and fails type-check in the current worktree.

Verification completed for this guest-session hardening pass:

- `./.venv/bin/python -m pytest tests/backend/test_guest_access_session_contract.py -q`
- `./.venv/bin/python -m pytest tests/backend/test_settings.py tests/backend/test_notification_stream_contract.py tests/backend/test_setup_reset_token_transport_contract.py tests/backend/test_guest_access_session_contract.py -q`
- `./.venv/bin/python -m compileall app`
- `npx eslint 'app/[slug]/page.tsx' 'app/[slug]/gallery/page.tsx' 'app/[slug]/invite/[token]/page.tsx' 'app/otp/verify/page.tsx' 'app/components/RSVPModal.tsx' 'app/components/RSVPForm.tsx' 'app/components/GuestVerificationModal.tsx' 'app/components/landing-page/LandingLayout.tsx' 'app/utils/publicGallery.ts' 'app/utils/guestAccess.ts'`
- `npm run build`
  Result: frontend build still reaches the same unrelated existing blocker in [app/admin/scraper/page.tsx](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/scraper/page.tsx), which is not part of this remediation slice and is not caused by the guest-session changes.

## Careful Phase Plan

### Phase 0: Hold The Current Staging Baseline

1. Do not reopen the already-fixed SSE or docs/OpenAPI changes while addressing the remaining items.
2. Keep the current staging posture as the control baseline for regression checks.
3. Decide up front whether SP-008 and SP-009 are required before production or are being accepted temporarily as scheduled medium-risk debt.

### Phase 1: Validate The Earlier Blockers In A Production-Like Environment

1. Confirm `/docs`, `/redoc`, and `/openapi.json` are absent when production settings are active and `ENABLE_API_DOCS` is unset.
2. Confirm `/admin/notifications/stream` still works through the real proxy/CDN path with cookie auth, reconnect behavior, and expected CORS behavior.
3. Confirm final deployed frontend/API domains are covered by derived trusted hosts or an explicit `ALLOWED_HOSTS` override.

### Phase 2: Normalize Vendor Public Flows First - Completed

1. Vendor form and vendor contract links now use canonical path tokens instead of `?token=...`.
2. Public vendor contract signing now sends signer data in the request body instead of the query string.
3. Backward-compatible handling for already-issued query-token links remains in place temporarily, with immediate redirect to the canonical path-token URL so the browser address bar is cleaned quickly.

### Phase 3: Normalize Couple Invite, Setup, Reset, And Team Invite Flows - Completed

1. Couple setup, couple reset-password, admin setup-account, admin reset-password, and team accept-invite emails now generate canonical path-token URLs instead of `?token=...`.
2. Legacy query-token pages now immediately redirect onto canonical path routes before the client settles on the legacy URL.
3. The existing backend validation and mutation contracts were preserved so this change stayed transport-focused and low-risk.

### Phase 4: Replace RSVP And OTP Query Persistence With A Short-Lived Access Exchange - Completed

1. The canonical invite route stays path-based, but it now exchanges the token into a short-lived HttpOnly `guest_access_session` cookie instead of translating the token back into `?rsvp_token=...`.
2. The landing page, OTP flow, RSVP submit path, and verified gallery reads now consume that guest session rather than reusing the raw invite token as a browser credential.
3. Guest-facing API responses no longer echo `guest.token` back into frontend state.
4. Legacy query-token entry points remain only as one-time compatibility shims with immediate URL cleanup.

### Phase 5: Retire Compatibility And Re-Verify Logging Hygiene

1. Remove temporary guest query-token compatibility once old emailed links are out of circulation.
2. Confirm application access logs, reverse-proxy logs, analytics tags, and error reporting no longer capture the residual one-time compatibility query parameters.
3. Keep the new guest-session regression coverage and add runtime staging checks for cookie exchange, resend/verify behavior, and session expiry.

## Deployment Readiness Call

### Recommended Readiness Call

- **Ready for staging**
- **No unresolved critical/high app-code findings**
- **No unresolved currently-open medium app-code findings**
- **Production sign-off depends on two things:**
  - validating the already-fixed SSE/docs/trusted-host behavior in the real deployment environment
  - validating the new guest-access session exchange and expiry behavior in the real deployment environment

### Practical Recommendation

If the goal is the narrow production-hardening bar discussed earlier, the original blockers are fixed and the guest RSVP/OTP transport issue is now also addressed in the canonical flow. The remaining security work is operational: verify the guest-session flow in staging and then retire the temporary compatibility shims once older emailed links are no longer expected to circulate.
