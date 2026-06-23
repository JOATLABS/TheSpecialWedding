# Fix admin session cookie / proxy auth-domain drift

## Summary

- The staging symptom — "Login successful" followed by a redirect loop back to `/admin/login` — is caused by a **split auth contract**: login succeeds via bearer token and `AdminContext` hydrates from `localStorage`, but [proxy.ts](../../proxy.ts) blocks every non-exempt `/admin/*` request unless the `admin_token` cookie is visible. When the cookie is scoped host-only to the API hostname, the frontend hostname cannot see it and the proxy redirects back to login.
- **Trigger (exposed the latent defect):** the April 14, 2026 deployment refactor (`3ea0f3c` — "refactor deployment workflows to use environment-scoped URLs") introduced distinct frontend and API hostnames in staging, making a host-only cookie invisible across the boundary.
- **Underlying defect (latent pre-April 13):** [app/utils/auth_utils.py](../../app/utils/auth_utils.py) `set_auth_cookie()` did not pass a `domain=` parameter, so cookies were host-only by default. Benign as long as frontend and API shared a hostname; broken the moment they didn't.
- **Fix that already shipped (April 16, `a1a8140`):** the same file now contains `resolve_cookie_domain()` (lines 169–221) and `_get_cookie_domain()` (lines 224–230), and `set_auth_cookie()` now passes `domain=_get_cookie_domain()` (line 258). `scripts/deploy/verify_environment.py` gained `verify_auth_cookie_scope()`, `verify_auth_cookie_response()`, and `verify_frontend_admin_session()` (lines 111–190) to validate the cookie end-to-end.
- **What this PR is actually for:** confirm the April 16 fix is live in staging, close the two gaps the fix left open, and lock in a regression test for the divergent-hostname failure mode so this cannot silently re-regress.

## Scope correction from earlier draft

An earlier draft attributed the regression to an April 14 change in `auth_utils.py`. That was wrong on the facts — `auth_utils.py` was untouched between April 13 and April 15; the cookie-domain logic landed April 16. Similarly, the earlier draft's proposed deploy-verify extension is already implemented. This PR does **not** re-propose those items. It addresses the residue: validation in staging, one missing logging branch, and a regression test.

## Why this is not the April 15 planner-billing change

The April 15 commit (`4e3da0d`) adds `app/utils/planner_billing_scope.py` and applies it to profile-field serialization in `app/api/admin_auth.py`. It does not touch login, token minting, cookie setting, or the proxy. Root-admin login is affected too, which already rules out a planner-scoped cause; planner-billing-scope does the opposite of what the symptom requires.

## Implementation changes

- **Confirm the April 16 fix is deployed to staging.** Run `scripts/deploy/verify_environment.py` against staging and check that `verify_auth_cookie_scope` and `verify_frontend_admin_session` both pass for root-admin and a smoke planner identity. If either fails, the fix is not live and the next step is a staging deploy, not a code change.
- **Add the missing critical-log branch in `resolve_cookie_domain()`.** When neither `COOKIE_DOMAIN`, `FRONTEND_URL`, nor `NEXT_PUBLIC_API_BASE_URL` produces a domain that is a shared suffix of both frontend and API hostnames, the function currently falls back silently. Log a `logger.critical(...)` with the three candidate values (not secrets) so a misconfigured environment surfaces in deploy logs instead of as an end-user redirect loop.
- **Keep `proxy.ts` as-is.** The proxy guard is behaving exactly as designed; removing it would relax authentication. The fix target is the cookie contract, not the proxy.
- **Add a `CHANGELOG.md` entry** under the April 16 fix describing the regression in behavioral terms: "login succeeds but admin routes redirect back to login after deployment to environment-scoped URLs; root cause was host-only admin cookie, fixed by domain derivation in `auth_utils.py`."

## Test plan

- **Unit coverage for `resolve_cookie_domain()`** with these cases:
  - Explicit `COOKIE_DOMAIN` → returned verbatim
  - `FRONTEND_URL` and `API_BASE_URL` share a suffix → suffix returned
  - Only one of the URL env vars present → derive from that one
  - No env var produces a shared-suffix domain → critical-log branch fires, function returns `None` (host-only fallback is acceptable only with the log)
  - Environment is `local` → skip domain derivation entirely (preserve existing dev ergonomics)
- **Regression test for the divergent-hostname failure mode.** In the integration layer, point `FRONTEND_URL` at one hostname and `API_BASE_URL` at another, log in, assert `Set-Cookie` has a `Domain=` attribute that is visible to both, then replay the session against the proxy and assert `/admin/planner` does *not* 302 to `/admin/login`. This is the bug the April 16 fix solved; without this test, a future refactor can quietly drop the `domain=` parameter again.
- **Dual-identity staging smoke.** Run verification against root-admin and the staging smoke planner fixture. PR1 is still waiting on `STAGING_SMOKE_TEAM_MEMBER_EMAIL` / `STAGING_SMOKE_TEAM_MEMBER_PASSWORD` to exist (see `CLAUDE.md` → "Deployment follow-ups"), so team-member identity is out of scope for this PR.
- **Cookie-only SSE check.** Current `verify_sse()` authenticates `/admin/notifications/stream` with the bearer token via `requests.Session`. Add a separate check that connects with the cookie alone and no `Authorization` header — this is the only path that actually exercises the cookie contract for streaming auth.

## Assumptions

- The trigger is the April 14 deployment refactor (`3ea0f3c`), not an earlier calendar or sync change on April 13.
- The underlying defect predates April 13 but was latent because staging did not previously have divergent frontend/API hostnames.
- The April 15 planner-billing change (`4e3da0d`) is orthogonal — it runs post-authentication on profile-field serialization and cannot explain root-admin being affected.
- The deployed service environment in staging is the source of truth for env vars at runtime; CI placeholder URLs are not.

## Verification checklist

- [ ] `scripts/deploy/verify_environment.py` against staging passes for both root-admin and the staging smoke planner
- [ ] Inspecting staging `/admin/token` response shows `Set-Cookie: admin_token=...; Domain=.<shared-suffix>; ...`
- [ ] Requesting staging `/admin/planner` with only the cookie (no `Authorization` header) does not redirect to `/admin/login`
- [ ] Requesting staging `/admin/notifications/stream` with only the cookie holds open instead of 401ing
- [ ] Unit tests for `resolve_cookie_domain()` all five branches pass
- [ ] New divergent-hostname integration regression test passes
- [ ] Critical-log branch triggers (and is visible in logs) when `FRONTEND_URL` and `API_BASE_URL` have no shared suffix
