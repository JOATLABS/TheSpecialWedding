## 2024-05-22 - Robust Distributed Rate Limiting
**Vulnerability:** The existing rate limiting middleware was using an in-memory implementation (`defaultdict(deque)`) which is ineffective in a multi-worker environment (state is not shared) and had a potential memory leak (keys were never cleaned up).
**Learning:** In-memory rate limiting in a Python ASGI app running with multiple workers (e.g. Uvicorn/Gunicorn) provides false security as limits are per-process. It also risks memory exhaustion if not pruned.
**Prevention:** Use a distributed store like Redis for rate limiting counters. When implementing fallbacks, ensure efficient resource management (cleanup) and avoid locking around network calls to prevent performance bottlenecks.

## 2024-05-23 - Rate Limiting Coverage for Sensitive Endpoints
**Vulnerability:** Critical sensitive endpoints (OTP, guest verification) were excluded from strict rate limiting because they were not in the explicit `auth_paths` list, allowing potential brute force attacks.
**Learning:** Security middleware often relies on explicit path matching. If the list of protected paths is manually maintained and not comprehensive, new or obscure sensitive endpoints can be left exposed. Also, raising `HTTPException` inside middleware can be unreliable if not caught by upper layers; returning `JSONResponse` directly is safer for blocking actions.
**Prevention:** Use a centralized definition of sensitive paths or strict prefix matching. Regularly audit route definitions against security controls. For blocking middleware, return responses directly to ensure the client receives the correct status code.
