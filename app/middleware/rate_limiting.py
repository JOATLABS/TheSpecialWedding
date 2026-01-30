from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import defaultdict, deque
from typing import Dict, Deque
import asyncio
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
        auth_period: int = 60
    ):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.auth_calls = auth_calls
        self.auth_period = auth_period

        # Store request timestamps for each IP (Fallback)
        self.requests: Dict[str, Deque[float]] = defaultdict(lambda: deque())
        self.auth_requests: Dict[str, Deque[float]] = defaultdict(lambda: deque())

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

    def _is_auth_endpoint(self, path: str) -> bool:
        """Check if the endpoint is authentication-related"""
        auth_paths = [
            "/admin/token",
            "/admin/login",
            "/public/register",
            "/setup/complete",
            "/otp/",
            "/reset-password",
            "/forgot-password",
            "/verify-email",
            "/weddings/verify-guest-access"
        ]
        return any(auth_path in path for auth_path in auth_paths)

    async def _cleanup_old_requests(self, request_queue: Deque[float], period: int):
        """Remove old requests outside the time window"""
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > period:
            request_queue.popleft()

    async def _check_redis_limit(self, client_ip: str, is_auth: bool) -> tuple[bool, int, int]:
        """
        Check rate limit using Redis.
        Returns: (is_limited, remaining, reset_time)
        """
        limit = self.auth_calls if is_auth else self.calls
        period = self.auth_period if is_auth else self.period
        endpoint_type = "auth" if is_auth else "api"

        # Use CacheKeys generator
        key = CacheKeys.rate_limit(client_ip, endpoint_type)

        try:
            # Simple fixed window implementation
            # INCR returns the new value
            if not cache.redis_client:
                 # Should not happen if check passed, but safety first
                 async with self.lock:
                    return await self._check_memory_limit(client_ip, is_auth)

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
                return await self._check_memory_limit(client_ip, is_auth)

    async def _check_memory_limit(self, client_ip: str, is_auth: bool) -> tuple[bool, int, int]:
        """
        Check rate limit using in-memory sliding window.
        Returns: (is_limited, remaining, reset_time)
        """
        # NOTE: This method must be called within an 'async with self.lock:' block

        limit = self.auth_calls if is_auth else self.calls
        period = self.auth_period if is_auth else self.period

        # Select appropriate storage
        requests_map = self.auth_requests if is_auth else self.requests
        request_queue = requests_map[client_ip]

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
        if len(requests_map) > 10000:
            # Clear 10% of keys roughly
            keys_to_remove = list(requests_map.keys())[:1000]
            for k in keys_to_remove:
                del requests_map[k]

        remaining = max(0, limit - len(request_queue))
        reset_time = int(time.time()) + period

        return False, remaining, reset_time

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with rate limiting"""

        # Skip rate limiting for health checks and CORS preflight requests
        if request.url.path.startswith("/health") or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_auth = self._is_auth_endpoint(request.url.path)

        # Optimization: Don't lock for Redis calls, only for in-memory operations
        if cache.enabled and cache.redis_client:
            is_limited, remaining, reset_time = await self._check_redis_limit(client_ip, is_auth)
        else:
            async with self.lock:
                is_limited, remaining, reset_time = await self._check_memory_limit(client_ip, is_auth)

        if is_limited:
            # Return rate limit exceeded error
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again later.",
                    "retry_after": self.auth_period if is_auth else self.period
                }
            )

        # Continue with the request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response
