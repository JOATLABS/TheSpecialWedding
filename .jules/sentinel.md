## 2024-05-22 - Robust Distributed Rate Limiting
**Vulnerability:** The existing rate limiting middleware was using an in-memory implementation (`defaultdict(deque)`) which is ineffective in a multi-worker environment (state is not shared) and had a potential memory leak (keys were never cleaned up).
**Learning:** In-memory rate limiting in a Python ASGI app running with multiple workers (e.g. Uvicorn/Gunicorn) provides false security as limits are per-process. It also risks memory exhaustion if not pruned.
**Prevention:** Use a distributed store like Redis for rate limiting counters. When implementing fallbacks, ensure efficient resource management (cleanup) and avoid locking around network calls to prevent performance bottlenecks.
