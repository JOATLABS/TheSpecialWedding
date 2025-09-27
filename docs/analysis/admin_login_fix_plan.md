# Admin Login Fix Implementation Plan

## Context
- Multi-tenant access model requires root admins, planners, and vendors to land on role-scoped dashboards after authentication, so any fix must preserve per-role routing and isolation expectations.【F:docs/features/MULTI_TENANT_ROADMAP.md†L12-L57】【F:docs/architecture/01-system-context.md†L5-L78】
- Admin login worked in commit `910dc8075e6c80f28dce39486f876867227d86ff` (2025-09-22). Comparing that baseline to HEAD shows three regressions: the admin landing page now redirects before the provider rehydrates the JWT, the guard no longer blocks unauthenticated visitors, and the context stopped using the cookie-backed session check that guaranteed consistent state across tabs.【45302f†L1-L78】【9ccac6†L1-L31】【ac4c8a†L16-L63】【96a974†L1-L11】
- Next.js’ recommended session management flow stores the authenticated session in secure HttpOnly cookies and only exposes minimal client state, so the fix must reinstate cookie-based gating while keeping client-side helpers memoized to avoid unnecessary rerenders.【eadf82†L1-L48】【f660ae†L1-L10】


## Required Code Changes

### 1. `app/contexts/AdminContext.tsx`
- Remove the automatic `useEffect` that calls `fetchUserProfile()` when `token` changes to break the render loop and allow the admin page to control profile loading explicitly.【F:app/contexts/AdminContext.tsx†L59-L64】
- Wrap `fetchUserProfile` in `useCallback` and expose a memoized context value so consuming components do not retrigger effects on every render—a React best practice for context providers handling async fetchers.【F:app/contexts/AdminContext.tsx†L66-L145】
- Keep token discovery logic but gate profile clearing on logout to avoid stale context between tenants.

### 2. `app/admin/page.tsx`
- Maintain explicit profile bootstrap on mount (`initializeDashboard`) and extend role routing to align with multi-tenant dashboards (ROOT_ADMIN and planner → `/admin/weddings`, vendors or legacy admins → appropriate sections).【F:app/admin/page.tsx†L12-L58】
- Add defensive logging/redirects for unknown roles so the landing page fails closed if middleware ever misclassifies a user.

### 3. `app/admin/components/AdminGuard.tsx`
- Ensure the guard triggers a single profile fetch attempt by leveraging the memoized `fetchUserProfile` helper; show a loading indicator until profile data resolves, but avoid calling `fetchUserProfile` repeatedly once the plan above is in place.【F:app/admin/components/AdminGuard.tsx†L13-L36】
- Confirm role normalization and denial messaging remain intact for non-authorized tenants.【F:app/admin/components/AdminGuard.tsx†L37-L48】

### 4. Integration Validation & Tooling
- Rebuild Next.js app to confirm `/admin/page.js` chunk is generated again and that `/admin` no longer falls back to `[slug]` routes.【F:ADMIN_LOGIN_ISSUE_ANALYSIS.md†L52-L67】
- Execute authentication end-to-end tests (Playwright or Cypress) covering root admin, planner, and vendor login flows to guarantee role-specific redirects are restored.
- Run linting and unit test suites to prevent regressions elsewhere (React context and middleware touches warrant a full pass per internal engineering standards).

## Acceptance Criteria
- Admin dashboard route compiles successfully and redirects each role to its scoped dashboard.
- No automated profile fetch occurs before the admin shell determines routing, eliminating the circular dependency noted in the RCA.
- Manual QA confirms tenant isolation (planner cannot see other planner weddings) and that logout clears cached context state for the next login session.
- Restore the baseline “two-cookie” handshake: read the client-readable `admin_authenticated` flag before asserting `isAuthenticated`, and clear token storage when the cookie is absent so fresh logins and logouts stay in sync across tabs.【ac4c8a†L16-L63】【486302†L1-L48】
- Memoize `fetchUserProfile` and the context value so consumers such as `AdminGuard` do not re-trigger profile fetch loops; keep the auto-fetch effect but guard it with the memoized function to align with React context guidance.【F:app/contexts/AdminContext.tsx†L54-L144】
- When restoring the cookie check, continue persisting the bearer token in localStorage/sessionStorage during login because downstream API helpers still require an authorization header.【F:app/contexts/AdminContext.tsx†L125-L174】

### 2. `app/admin/page.tsx`
- Delay the redirect check until the provider has rehydrated the token or confirmed the session cookie so `/admin` no longer bounces users back to `/admin/login` during the race between context hydration and the page effect—a regression introduced after the September 22 baseline.【45302f†L1-L78】
- Keep the context-driven `fetchUserProfile` call but gate it behind the same memoized helper as the provider to avoid duplicate requests; retain the role-aware redirects that satisfy the multi-tenant contract.【F:app/admin/page.tsx†L12-L58】【F:app/admin/page.tsx†L60-L81】
- Add structured logging around unknown roles and profile-fetch failures so QA can triage routing mistakes quickly without exposing sensitive details to the UI.【F:app/admin/page.tsx†L60-L78】

### 3. `app/admin/components/AdminGuard.tsx`
- Reintroduce the baseline guardrail that immediately routes unauthenticated visitors to `/admin/login` using the cookie-backed `isAuthenticated` + `token` combination; this logic was removed after the baseline and is required to stop public traffic from reaching protected shells.【9ccac6†L1-L31】
- Keep the single-attempt profile fetch behavior with `attemptedRef`, but update the dependency array to use the memoized `fetchUserProfile` so the effect does not refire on every render.【F:app/admin/components/AdminGuard.tsx†L13-L36】
- Preserve the role normalization checks so unauthorized tenants receive an access-denied message rather than a silent failure.【F:app/admin/components/AdminGuard.tsx†L33-L48】

### 4. Integration Validation & Tooling
- Rebuild Next.js to confirm `/admin` renders without a login loop, and verify middleware respects the cookie flag after reinstating the baseline guard logic.【970fe1†L1-L20】
- Execute authentication end-to-end tests (Playwright or Cypress) covering root admin, planner, and vendor login flows to guarantee role-specific redirects are restored and tenants remain isolated.【F:tests/integration/test_auth_session.py†L1-L82】
- Run linting and unit test suites once code changes land; these touches span context, middleware, and guards, so a full regression run is required even though the fix targets authentication only.【dddc7b†L1-L29】

## Acceptance Criteria
- `/admin` loads without bouncing authenticated users back to `/admin/login`, and the guard prevents unauthenticated traffic from reaching any admin layout.
- AdminContext once again derives authentication state from the secure cookie so multi-tab and multi-tenant sessions stay consistent with Next.js best practices.【eadf82†L1-L48】【f660ae†L1-L10】
- Manual QA confirms tenant isolation (planner cannot see other planner weddings) and that logout clears cached context state for the next login session.【F:docs/features/MULTI_TENANT_ROADMAP.md†L12-L57】
