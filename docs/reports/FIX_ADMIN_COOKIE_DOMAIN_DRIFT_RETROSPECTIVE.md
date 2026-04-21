# Fix Admin Cookie Domain Drift Regression — Retrospective

Title note: this report intentionally drops the environment qualifier per `AGENTS.md` → "Regression And Bug-Title Convention" and `CLAUDE.md`. The drift happened to surface on staging first, but the mechanism is environmental, not staging-specific. Symptoms appear in the body.

## TL;DR

On **2026-04-14** commit `1130fbf` introduced cookie-domain logic in `app/utils/auth_utils.py` that was fragile enough to desynchronize the backend's `admin_token` Set-Cookie scope from the frontend host. On **2026-04-16** commits `f44e15e` / `a1a8140` (`feat: enhance cookie domain handling and session verification`) shipped the fix: a shared-label domain derivation with explicit validation against both `FRONTEND_URL` and `NEXT_PUBLIC_API_BASE_URL`, a critical-level log on non-overlap, and matching deploy-script checks that actually exercise cookie-backed frontend navigation. The regression is closed on `main`. Two small follow-ups remain, noted at the end of this doc.

## Observed Symptoms (at the time of the regression)

- Login-time bearer flow succeeded: `/admin/token` returned a token, `/admin/profile` fetched cleanly, the SPA briefly flashed "Login successful."
- `proxy.ts` then redirected any `/admin/*` navigation back to `/admin/login` because its guard is cookie-only (lines 9–18 of `proxy.ts` gate on `request.cookies.get('admin_token')`).
- Notification SSE (`/admin/notifications/stream`) failed for the same reason in browser sessions that had no bearer header — cookie-only path.
- Root admin and planner were both affected, which ruled out the 2026-04-15 planner-billing change (`4e3da0d`) as the primary cause.

## Root Cause

Commit `1130fbf` added `_get_cookie_domain()` with simple apex-only derivation:

```python
host = urlparse(frontend).hostname or ""
parts = host.split(".")
if len(parts) > 2:
    return "." + ".".join(parts[-2:])
return "." + host
```

The weaknesses that together produced the regression:

1. `COOKIE_DOMAIN` was accepted blindly — no check that the operator-supplied value was actually visible to the frontend and API hosts.
2. Apex-only stripping produces the wrong answer whenever the frontend and API sit on different apex domains, or when either is deployed on an unexpected subdomain depth.
3. There was no fallback that considered `NEXT_PUBLIC_API_BASE_URL` — only `FRONTEND_URL`.
4. When no domain could be derived the function silently returned `None`, issuing a host-only cookie with no log signal. The misconfig only showed up after a user tried to navigate.

## Resolution (already on `main` as of 2026-04-16)

Commits `f44e15e` / `a1a8140` replaced `_get_cookie_domain` with a full `resolve_cookie_domain` in `app/utils/auth_utils.py` (lines 169–221) that:

- Accepts an `explicit_cookie_domain` but validates it against both `frontend_host` and `api_host` before honoring it (lines 187–198). A mismatched explicit value is logged `critical` and ignored rather than silently applied.
- Derives a shared label set across frontend and API hosts via `_derive_shared_cookie_domain` (lines 116–128), which is strictly stronger than "strip to apex" and correctly handles arbitrary subdomain depth.
- Falls back to `FRONTEND_URL`-only derivation (`_derive_cookie_domain_from_host`, lines 91–99) and then `NEXT_PUBLIC_API_BASE_URL`-only derivation (`_derive_cookie_domain_from_api_host`, lines 102–113), each gated on visibility to the other host.
- On complete failure, logs `critical` with all three inputs (`COOKIE_DOMAIN`, `FRONTEND_URL`, `NEXT_PUBLIC_API_BASE_URL`) before returning `None` (lines 215–220). Host-only fallback is preserved intentionally — it keeps local development working without domain gymnastics — but the failure is now loud.
- `legacy_cookie_cleanup_domains` (lines 131–166) clears stale host-only and narrowly-scoped cookies on every `set_auth_cookie` call so pre-fix sessions can't keep sending a stale `admin_token` alongside the new one.

The same commit extended `scripts/deploy/verify_environment.py` so CI actually exercises the broken path:

- `verify_auth_cookie_response` (lines 135–164) inspects the `Set-Cookie` header on the login response and fails if the `Domain` attribute is not visible to the frontend host.
- `verify_auth_cookie_scope` (lines 111–132) re-checks the cookie jar after login.
- `verify_frontend_admin_route` (lines 167–182) requests `/admin` and `/admin/planner` on the authenticated session with `allow_redirects=False` and fails loudly if either path 3xxs to `/admin/login` — the exact failure mode of the regression.
- `verify_sse` (lines 247–291) connects to `/admin/notifications/stream` with session cookies only, no `Authorization` header, so the SSE path is exercised as a browser would do it.

Unit coverage landed in `tests/backend/test_settings.py` at the same time: `test_cookie_domain_prefers_explicit_cookie_domain`, `test_cookie_domain_derives_from_frontend_url`, `test_cookie_domain_derives_from_api_base_url_when_frontend_missing`, `test_cookie_domain_logs_critical_when_staging_domains_do_not_overlap`, and `test_cookie_cleanup_domains_include_legacy_host_scopes`.

## Why the Original Report's Diagnosis Was Right But Its Plan Was Stale

The original "Fix Staging Admin Redirect Regression" write-up correctly identified:

- the April 14 cookie change as the likely culprit,
- the split contract between bearer-authenticated API calls and the cookie-only `proxy.ts` guard,
- the pattern of repeated `/admin/profile` and red `/notifications/stream` calls in the staging screenshot.

It was wrong on two load-bearing points:

- Every item in its "Implementation Changes" list was already shipped on `main` by 2026-04-16. Acting on that plan would have duplicated `resolve_cookie_domain`, `legacy_cookie_cleanup_domains`, and the deploy-script additions.
- It claimed `verify_environment.py` "validates bearer-token API auth and bearer-token SSE, but does not validate cookie-backed frontend navigation through the proxy." All four of its proposed additions already exist in that script — the cookie-scope assertions, the authenticated `/admin` + `/admin/planner` navigation test, and the cookie-only SSE connect.

The title was also wrong. `AGENTS.md` and `CLAUDE.md` both require regression titles to describe behavior, not environments. "Fix Staging Admin Redirect Regression" becomes "Fix Admin Cookie Domain Drift Regression" here.

## Remaining Follow-Ups (genuinely open)

These are small, real gaps — not duplicates of shipped work.

1. **Assert the cookie Domain is visible to _both_ hosts in the deploy script.** `verify_auth_cookie_response` and `verify_auth_cookie_scope` currently check only the frontend host. If an operator sets `COOKIE_DOMAIN` to a value that's visible to the frontend but not the API host (or vice versa), the deploy script will pass but the runtime session will fail. Extend both helpers to take `api_base` and assert `host_matches_cookie_domain` for both hosts. Small, no behavior change in the green path.
2. **Add a unit test for the `COOKIE_DOMAIN` mismatch fallthrough.** `test_cookie_domain_logs_critical_when_staging_domains_do_not_overlap` covers the no-derivable-domain case, but there is no test for "`COOKIE_DOMAIN` is set, does not match the hosts, is logged critical, is ignored, and the function falls through to derivation from `FRONTEND_URL`." That's the exact operator-error path the April 16 fix was designed to catch. One `caplog` test mirroring the existing one.

Neither follow-up requires touching `auth_utils.py`.

## References

- Regression commit: `1130fbf` (2026-04-14) — `app/utils/auth_utils.py` diff adds apex-only `_get_cookie_domain`.
- Fix commits: `f44e15e` / `a1a8140` (2026-04-16) — `feat: enhance cookie domain handling and session verification`.
- Ruled out as primary cause: `4e3da0d` (2026-04-15) — planner-billing scope change; affected planners only.
- Related binding rules: `AGENTS.md` → "Regression And Bug-Title Convention"; `CLAUDE.md` → "Regression and bug-fix title convention".
