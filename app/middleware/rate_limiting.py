from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
import time
from collections import defaultdict, deque
from typing import Dict, Deque, Optional
import asyncio
import json
from urllib.parse import parse_qs
from app.core.cache import cache, CacheKeys
import logging

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis (preferred) or sliding window algorithm (fallback)
    """
    def __init__(
        self,
        app,
        calls: int = 100,  # Number of calls
        period: int = 60,  # Time period in seconds
        auth_calls: int = 10,  # Stricter limit for auth endpoints
        auth_period: int = 60,
        login_ip_calls: int = 30,
        login_principal_calls: int = 5,
        login_period: int = 60,
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.auth_calls = auth_calls
        self.auth_period = auth_period
        self.login_ip_calls = login_ip_calls
        self.login_principal_calls = login_principal_calls
        self.login_period = login_period

        # Store request timestamps for each IP/bucket (Fallback)
        self.request_windows: Dict[str, Deque[float]] = defaultdict(lambda: deque())

        # Lock for thread safety (Fallback)
        self.lock = asyncio.Lock()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers first (for reverse proxy setups)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"

    def _normalize_path(self, path: str) -> str:
        normalized = path.rstrip("/")
        return normalized or "/"

    def _get_rate_limit_config(self, path: str) -> tuple[str, int, int, bool]:
        """
        Resolve the rate-limit bucket and policy for a path.

        Returns: (bucket_name, calls_per_period, period_in_seconds, is_auth_endpoint)
        """
        normalized_path = self._normalize_path(path)

        exact_auth_limits = {
            "/admin/token/refresh": ("admin_token_refresh", max(self.auth_calls * 2, 20), 60),
            "/admin/token": ("admin_login_identity", self.login_principal_calls, self.login_period),
            "/admin/login": ("admin_login_page", self.login_ip_calls, self.login_period),
            "/couple/login": ("couple_login_identity", self.login_principal_calls, self.login_period),
            "/couple/setup-password": ("couple_setup_password", 5, 60),
            "/public/register": ("public_register", 3, 60),
            "/api/v1/vendors/signup": ("vendor_signup", 3, 60),
            "/reset-password": ("password_reset", 3, 60),
            "/forgot-password": ("password_reset", 3, 60),
            "/couple/reset-password": ("password_reset", 3, 60),
            "/couple/forgot-password": ("password_reset", 3, 60),
            "/verify-email": ("verify_email", self.auth_calls, self.auth_period),
            "/setup/complete": ("setup_complete", self.auth_calls, self.auth_period),
            "/weddings/verify-guest-access": ("guest_access", self.auth_calls, self.auth_period),
            "/api/v1/vendors/change-password": ("vendor_change_password", self.auth_calls, self.auth_period),
        }

        if normalized_path in exact_auth_limits:
            bucket, limit, period = exact_auth_limits[normalized_path]
            return bucket, limit, period, True

        prefix_limits = (
            # Dynamic guest verification paths must not fall through into the
            # generic API bucket or they will compete with unrelated traffic.
            ("/weddings/verify-guest-access/", "guest_access", self.auth_calls, self.auth_period, True),
            # Separate public wedding metadata and gallery reads from
            # authenticated planner/couple APIs so guest traffic cannot starve
            # internal dashboards behind the same source IP.
            ("/weddings/privacy-info/", "public_wedding_metadata", self.calls, self.period, False),
            ("/gallery", "public_gallery", self.calls, self.period, False),
            ("/weddings/guest-access/", "guest_access_session", self.calls, self.period, False),
            ("/admin/", "admin_api", self.calls, self.period, False),
            ("/couple/", "couple_api", self.calls, self.period, False),
        )

        for prefix, bucket, limit, period, is_auth in prefix_limits:
            if normalized_path.startswith(prefix):
                return bucket, limit, period, is_auth

        if normalized_path.startswith("/otp/"):
            return "otp", 5, 60, True

        return "api", self.calls, self.period, False

    def _get_additional_rate_limit_configs(self, path: str) -> list[tuple[str, int, int, bool]]:
        normalized_path = self._normalize_path(path)
        login_ip_limits = {
            "/admin/token": [("admin_login_ip", self.login_ip_calls, self.login_period, True)],
            "/couple/login": [("couple_login_ip", self.login_ip_calls, self.login_period, True)],
        }
        return login_ip_limits.get(normalized_path, [])

    def _uses_login_identity(self, bucket: str) -> bool:
        return bucket in {"admin_login_identity", "couple_login_identity"}

    async def _extract_login_identifier(self, request: Request) -> Optional[str]:
        try:
            raw_body = await request.body()
        except Exception:
            return None

        if not raw_body:
            return None

        content_type = request.headers.get("content-type", "").lower()
        email: Optional[str] = None

        if "application/json" in content_type:
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                candidate = payload.get("email") or payload.get("username")
                if isinstance(candidate, str):
                    email = candidate
        elif "application/x-www-form-urlencoded" in content_type:
            try:
                form_data = parse_qs(raw_body.decode("utf-8"))
            except UnicodeDecodeError:
                form_data = {}
            values = form_data.get("email") or form_data.get("username") or []
            if values and isinstance(values[0], str):
                email = values[0]

        if not email:
            return None

        normalized = email.strip().lower()
        return normalized or None

    async def _get_bucket_subject(self, request: Request, bucket: str, client_ip: str) -> str:
        if not self._uses_login_identity(bucket):
            return client_ip

        identifier = await self._extract_login_identifier(request)
        if identifier:
            return identifier

        return f"fallback:{client_ip}"

    async def _cleanup_old_requests(self, request_queue: Deque[float], period: int):
        """Remove old requests outside the time window"""
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > period:
            request_queue.popleft()

    async def _check_redis_limit(self, subject: str, bucket: str, limit: int, period: int) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis.
        Returns: (is_limited, remaining, reset_time)
        """
        key = CacheKeys.rate_limit(subject, bucket)

        try:
            # Simple fixed window implementation
            # INCR returns the new value
            if not cache.redis_client:
                 # Should not happen if check passed, but safety first
                 async with self.lock:
                    return await self._check_memory_limit(subject, bucket, limit, period)

            current_count = await cache.redis_client.incr(key)

            # If it's the first request (count == 1), set expiration
            if current_count == 1:
                await cache.redis_client.expire(key, period)

            # Get TTL for headers
            ttl = await cache.redis_client.ttl(key)
            reset_time = int(time.time()) + (ttl if ttl > 0 else period)
            remaining = max(0, limit - current_count)

            return current_count > limit, remaining, reset_time

        except Exception as e:
            logger.error(f"Redis rate limit check failed: {str(e)}")
            # Fallback to memory if Redis fails
            # We must acquire lock here as we are entering critical section for memory storage
            async with self.lock:
                return await self._check_memory_limit(subject, bucket, limit, period)

    async def _check_memory_limit(self, subject: str, bucket: str, limit: int, period: int) -> tuple[bool, int, int]:
        """
        Check rate limit using in-memory sliding window.
        Returns: (is_limited, remaining, reset_time)
        """
        # NOTE: This method must be called within an 'async with self.lock:' block

        bucket_key = f"{bucket}:{subject}"
        request_queue = self.request_windows[bucket_key]

        # Cleanup old requests
        await self._cleanup_old_requests(request_queue, period)

        # Check limit
        current_count = len(request_queue)
        if current_count >= limit:
            reset_time = int(time.time()) + period # Approximate
            return True, 0, reset_time

        # Add new request
        request_queue.append(time.time())

        # Cleanup memory if too many IPs are tracked (DoS protection)
        if len(self.request_windows) > 10000:
            # Clear 10% of keys roughly
            keys_to_remove = list(self.request_windows.keys())[:1000]
            for k in keys_to_remove:
                del self.request_windows[k]

        remaining = max(0, limit - len(request_queue))
        reset_time = int(time.time()) + period

        return False, remaining, reset_time

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with rate limiting"""

        # Skip rate limiting for health checks and CORS preflight requests
        if request.url.path.startswith("/health") or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        primary_bucket, primary_limit, primary_period, _ = self._get_rate_limit_config(request.url.path)
        rate_limit_targets = [
            (
                primary_bucket,
                primary_limit,
                primary_period,
                await self._get_bucket_subject(request, primary_bucket, client_ip),
            )
        ]
        for extra_bucket, extra_limit, extra_period, _ in self._get_additional_rate_limit_configs(request.url.path):
            rate_limit_targets.append(
                (
                    extra_bucket,
                    extra_limit,
                    extra_period,
                    await self._get_bucket_subject(request, extra_bucket, client_ip),
                )
            )

        header_remaining: Optional[int] = None
        header_reset: Optional[int] = None

        for bucket, limit, period, subject in rate_limit_targets:
            if cache.enabled and cache.redis_client:
                is_limited, remaining, reset_time = await self._check_redis_limit(subject, bucket, limit, period)
            else:
                async with self.lock:
                    is_limited, remaining, reset_time = await self._check_memory_limit(subject, bucket, limit, period)

            if header_remaining is None or remaining < header_remaining:
                header_remaining = remaining
                header_reset = reset_time

            if is_limited:
                retry_after = max(1, reset_time - int(time.time()))
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Try again later.",
                        "retry_after": retry_after,
                    },
                )
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(reset_time)
                return response

        # Continue with the request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Remaining"] = str(header_remaining if header_remaining is not None else 0)
        response.headers["X-RateLimit-Reset"] = str(header_reset if header_reset is not None else int(time.time()))

        return response
