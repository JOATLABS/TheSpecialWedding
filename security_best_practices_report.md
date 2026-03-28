# Security Best Practices Report

## Executive Summary

This review focused on deployment readiness across FastAPI backend services, Next.js frontend surfaces, schema-to-API-to-frontend alignment, public resources/blog delivery, unused or unwired code paths, and notable latency/security gaps.

The project is materially improved and passes static verification (`npm run build`, `npm test -- --runInBand`, and `python3 -m compileall app`). Public resources/blog alignment is largely in good shape for production. However, the codebase is **not fully production-ready** until the active Server-Sent Events authentication flow stops placing bearer tokens in URL query strings and FastAPI documentation/schema exposure is disabled or gated in production.

## Critical Findings

### SP-001: SSE authentication places JWTs in URL query strings

**Impact:** Auth tokens can leak through access logs, browser history, proxy layers, monitoring tools, and copy-pasted URLs, creating an avoidable credential exposure path for authenticated admin/planner sessions.

- Backend documentation and handler explicitly require `?token=<jwt>` for notification streaming in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py:7](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py#L7), [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py:35](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py#L35), and [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py:176](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/notification_stream.py#L176).
- The frontend constructs the EventSource connection with the raw JWT in the URL in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/SSEContext.tsx:106](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/SSEContext.tsx#L106).
- This violates common secure-session handling guidance for web apps because URLs are not a safe transport for bearer credentials.

## High Findings

### SP-002: FastAPI docs and OpenAPI schema remain exposed in production

- The application creates `FastAPI(...)` without conditionally disabling `docs_url`, `redoc_url`, or `openapi_url` in production at [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py:363](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py#L363).
- The root health/info response also advertises `/docs` directly in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py:599](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py#L599).
- For an authenticated platform with many admin, billing, public-token, and operational endpoints, leaving interactive docs/schema open in production increases reconnaissance surface and makes route discovery easier than necessary.

## Medium Findings

### SP-003: Knowledge base status contract is inconsistent across model, API, and frontend

- The canonical model allows `pending_review` in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py:64](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py#L64), [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py:103](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py#L103), and [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py:179](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/models/knowledge_base.py#L179).
- The API create/update request validators reject or partially reject that status in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py:39](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py#L39) and [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py:74](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py#L74).
- The editor UI only exposes `draft` and `published` in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx:56](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx#L56) and [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx:327](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/components/kb/ArticleEditor.tsx#L327).
- This is a real schema/API/frontend drift issue and will continue to produce confusing behavior, rejected values, or dead states.

### SP-004: KB feedback summary route is double-prefixed and appears unwired

- The route is defined as `/admin/kb/feedback-summary` in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py:386](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/api/knowledge_base.py#L386).
- The router itself is also mounted globally under `/admin` in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py:588](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/main.py#L588).
- That makes the effective path `/admin/admin/kb/feedback-summary`.
- No live frontend consumer was found for `feedback-summary`, which makes this both a route misconfiguration and stale/unwired API surface.

### SP-005: KB list/search endpoints fetch full article bodies and strip them after retrieval

- The service includes `content` in search matching in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py:145](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py#L145).
- It then performs `find(query)` without projection in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py:163](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py#L163).
- Only after the documents are retrieved does it remove `content` from the list payload in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py:175](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/services/knowledge_base_service.py#L175).
- This is a latency and bandwidth inefficiency that will get worse as article count and article size grow.

## Low Findings

### SP-006: Legacy admin auth/API context stack remains in the repo but does not appear to be mounted

- A full older auth provider still exists in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/AuthContext.tsx:48](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/AuthContext.tsx#L48) and [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/APIContext.tsx:13](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/contexts/APIContext.tsx#L13).
- The active admin tree uses `AdminProvider` in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/layout.tsx:116](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/admin/layout.tsx#L116), and no active consumers were found for the old provider/hook stack.
- This is cleanup debt rather than an active vulnerability, but it increases cognitive load and the chance of future drift.

## Confirmed Healthy Areas

### Resources/blog production path is largely aligned

- `/resources` is server-rendered and hydrates from the shared blog API fetch path in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/page.tsx:11](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/page.tsx#L11).
- Shared resource/blog types and fallback controls live in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/resourcesShared.ts:23](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/resourcesShared.ts#L23).
- The direct article route shares server fetching and only keeps static fallback behavior outside production in [/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/blog/[slug]/page.tsx:15](/Users/emmanuelakinwale/Desktop/WeddingWebApp/app/resources/blog/[slug]/page.tsx#L15).
- This is no longer the primary deployment blocker it was earlier. The remaining static fallback dual-source behavior is intentionally limited to non-production.

### Inbound email HTML rendering is sanitized server-side

- The admin inbox renders HTML bodies in the UI, but the service sanitizes the returned HTML before delivery to the frontend.
- This path did not present as a current release blocker during review.

## Verification Performed

- `npm run build` — passed
- `npm test -- --runInBand` — passed (`17/17`)
- `python3 -m compileall app` — passed

## Deployment Readiness

### Recommended Readiness Call

- **Ready for staging**
- **Not fully production-ready** until:
  1. SSE auth stops sending JWTs in URL query strings.
  2. FastAPI docs/OpenAPI exposure is disabled or gated in production.

### Important Follow-Up, But Not Immediate Launch Blockers

1. Align KB status handling across schema, API, and editor UI.
2. Fix or remove the double-prefixed KB feedback summary route.
3. Add projection-based KB list/search retrieval to avoid moving large article bodies unnecessarily.
4. Remove or clearly deprecate the legacy auth/API context stack.
