# WeddingWebApp Security Remediation Phase Plan

Source report: `/Users/emmanuelakinwale/Desktop/WeddingWebApp/security_best_practices_report.md`

## Goal

Move the project from "ready for staging" to "safe for production release" without introducing auth regressions, breaking admin real-time behavior, or masking unresolved KB contract drift.

## Phase 0: Baseline and Release Guardrails

Purpose: lock down what "safe" means before changing auth or API surface.

Scope:
- Record current staging behavior for `/admin/notifications/stream`, `/docs`, `/redoc`, `/openapi.json`, `/`, and `/info`.
- Confirm how `ENVIRONMENT` is set in staging and production.
- Verify current admin login, refresh, and logout flows using the cookie-backed `admin_token` session path.
- Add or outline regression checks for:
  - admin login + token refresh
  - SSE connect / reconnect / hidden-tab recovery
  - docs visibility by environment

Exit criteria:
- A reviewer can describe the expected pre-change and post-change behavior for each blocker.
- Rollback plan exists for SSE auth transport and docs gating.

## Phase 1: Fix SP-001 SSE Auth Transport

Priority: release blocker

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/SSEContext.tsx`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/dependencies/auth_extended.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/admin_auth.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/utils/auth_utils.py`

Preferred approach:
- Authenticate the SSE endpoint from the existing `admin_token` HttpOnly cookie instead of `?token=<jwt>`.
- Keep REST endpoints on their current bearer-header path for now.
- Use `EventSource(..., { withCredentials: true })` when the frontend connects cross-origin to the API.

Why this order:
- The cookie session path already exists and is less risky than inventing a second token format.
- This isolates the production blocker without forcing a broad admin-auth rewrite.

Implementation notes:
- Remove `token: str = Query(...)` from the SSE handler contract.
- Reuse the cookie-aware auth dependency or a narrow helper built on the same rules.
- Remove all frontend code that appends the JWT to the stream URL.
- Update backend comments and endpoint descriptions so the repo no longer documents query-token auth as acceptable.
- Verify CORS and credential behavior for staging/production origin topology.

Fallback only if needed:
- If cookie-backed EventSource proves incompatible with the deployment topology, introduce a short-lived one-time stream ticket fetched over authenticated REST. Do not keep the raw JWT in the URL.

Validation:
- Browser network panel shows `/admin/notifications/stream` with no token in the URL.
- Access logs and client-visible URLs do not contain bearer credentials.
- SSE still reconnects after tab visibility changes and transient network loss.
- Expired/invalid sessions fail closed with a 401 and clean client logout behavior.

## Phase 2: Fix SP-002 Production Docs/OpenAPI Exposure

Priority: release blocker

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/core/settings.py`

Preferred approach:
- Make docs exposure an explicit environment-aware setting rather than an always-on default.
- Keep docs enabled in local development.
- Decide deliberately whether staging should keep docs on; default recommendation is yes for staging, no for production.

Implementation notes:
- Gate `docs_url`, `redoc_url`, and `openapi_url` when constructing `FastAPI(...)`.
- Remove or conditionally suppress the `docs_url` hint from `/`.
- Check whether any automation or monitoring assumes `/openapi.json` exists in production and update that dependency before rollout.

Validation:
- Development: `/docs` and `/openapi.json` remain available.
- Production: `/docs`, `/redoc`, and `/openapi.json` return 404 or equivalent gated behavior.
- Root/info payloads no longer advertise production docs unnecessarily.

## Phase 3: Resolve SP-003 KB Status Contract Drift

Priority: important follow-up

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx`

Decision required before code:
- Keep `pending_review` as a supported state end-to-end, or remove it from the canonical model completely.

Recommendation:
- Make one explicit product decision and enforce it everywhere.
- Do not leave the model more permissive than the API or UI.

Implementation notes:
- Align create/update validators with the chosen canonical status set.
- Align editor options and admin filters with the same set.
- Add request/response tests covering every allowed status.

Validation:
- No allowed status can be selected in the UI and then rejected by the API.
- No hidden status remains in the backend model without a clear product use.

## Phase 4: Resolve SP-004 KB Feedback Route Misconfiguration

Priority: important follow-up

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py`

Current issue:
- The endpoint is declared as `/admin/kb/feedback-summary` inside a router that is also mounted under `/admin`, producing `/admin/admin/kb/feedback-summary`.

Recommendation:
- First decide whether this endpoint should exist at all, since no live consumer was found.
- If needed, normalize it to a single-admin-prefix path and add a caller or admin test.
- If not needed, remove it to reduce stale API surface.

Validation:
- Route table shows only one intended path.
- There is either a tested consumer or the endpoint no longer exists.

## Phase 5: Resolve SP-005 KB List/Search Overfetching

Priority: important follow-up

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py`

Implementation notes:
- Keep search matching semantics intact, but add Mongo projection so list/search responses do not materialize `content` and `feedback` unnecessarily.
- Confirm projection still works with content-based filtering.
- Consider indexes or a text-search strategy later if article volume grows; that is separate from the immediate overfetch fix.

Validation:
- List/search payloads omit article bodies before serialization.
- Response size and latency are reduced for larger KB datasets.

## Phase 6: Resolve SP-006 Legacy Auth/API Context Cleanup

Priority: low-risk cleanup

Files involved:
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/AuthContext.tsx`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/APIContext.tsx`
- `/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/layout.tsx`

Implementation notes:
- Confirm there are still no active imports or runtime consumers.
- Remove dead files or replace them with clearly deprecated stubs if a softer transition is needed.
- Do this after Phase 1 so auth-related debugging is not muddied by unrelated cleanup.

Validation:
- Search shows no live imports of the legacy stack.
- Admin auth behavior is unchanged after cleanup.

## Phase 7: Final Verification and Production Promotion

Purpose: prove the blockers are fixed and the follow-up work did not regress staging.

Checklist:
- Run the existing backend/frontend test suites.
- Add targeted tests for SSE auth transport and docs gating if they do not already exist.
- Perform a browser verification of admin login, SSE connection, notification updates, and logout.
- Verify production config values before promotion, especially `ENVIRONMENT`, cookie `secure`, and allowed CORS origins.

Production readiness decision:
- Safe to promote only after Phases 1 and 2 are complete and validated.
- Phases 3 through 6 can follow immediately after, but they should not block staging unless they expose new correctness issues during implementation.
