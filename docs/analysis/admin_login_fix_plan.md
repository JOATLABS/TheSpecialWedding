# Admin Login Fix Implementation Plan

## Context
- Multi-tenant access model requires root admins, planners, and vendors to land on role-scoped dashboards after authentication, so any fix must preserve per-role routing and isolation expectations.【F:docs/features/MULTI_TENANT_ROADMAP.md†L12-L57】【F:docs/architecture/01-system-context.md†L5-L78】
- Current regression stems from AdminContext recursively triggering `fetchUserProfile` during initial render, which collides with the admin landing page's own profile bootstrap and prevents `/admin/page.tsx` from building.【F:ADMIN_LOGIN_ISSUE_ANALYSIS.md†L15-L67】【F:app/contexts/AdminContext.tsx†L42-L64】【F:app/admin/page.tsx†L12-L39】

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
