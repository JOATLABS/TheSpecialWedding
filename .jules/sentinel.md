## 2024-05-23 - Rate Limit Bypass on New Sensitive Endpoints
**Vulnerability:** Rate limiting middleware used a hardcoded list of "auth endpoints" (limit 10/min) vs "normal endpoints" (limit 100/min). New sensitive endpoints (`/otp/`, `/reset-password`) were not added to this list, defaulting to the looser limit and increasing brute-force risk.
**Learning:** Security controls based on manual lists of routes (allow/deny lists) degrade over time as the application grows. Developers added new auth features without updating the central security middleware.
**Prevention:**
1. Use route-level decorators for rate limiting (co-located with code) instead of central middleware matching paths.
2. Or, tag routes in FastAPI (e.g., `tags=["Auth"]`) and have middleware inspect tags.
3. Add unit tests that enforce rate limits on all endpoints matching sensitive patterns (e.g. `*password*`, `*otp*`).
