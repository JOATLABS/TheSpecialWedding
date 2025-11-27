from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
from collections import defaultdict, deque
from typing import Dict, Deque
import asyncio

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm
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

        # Store request timestamps for each IP
        self.requests: Dict[str, Deque[float]] = defaultdict(lambda: deque())
        self.auth_requests: Dict[str, Deque[float]] = defaultdict(lambda: deque())

        # Lock for thread safety
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
        auth_paths = ["/admin/token", "/admin/login", "/public/register", "/setup/complete"]
        return any(auth_path in path for auth_path in auth_paths)

    async def _cleanup_old_requests(self, request_queue: Deque[float], period: int):
        """Remove old requests outside the time window"""
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > period:
            request_queue.popleft()

    async def _is_rate_limited(self, client_ip: str, is_auth: bool) -> bool:
        """Check if the client has exceeded rate limits"""
        current_time = time.time()

        if is_auth:
            # Use stricter limits for auth endpoints
            await self._cleanup_old_requests(self.auth_requests[client_ip], self.auth_period)

            if len(self.auth_requests[client_ip]) >= self.auth_calls:
                return True

            self.auth_requests[client_ip].append(current_time)
        else:
            # Regular rate limiting
            await self._cleanup_old_requests(self.requests[client_ip], self.period)

            if len(self.requests[client_ip]) >= self.calls:
                return True

            self.requests[client_ip].append(current_time)

        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request with rate limiting"""

        # Skip rate limiting for health checks and CORS preflight requests
        if request.url.path.startswith("/health") or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        is_auth = self._is_auth_endpoint(request.url.path)

        async with self.lock:
            if await self._is_rate_limited(client_ip, is_auth):
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
        if is_auth:
            remaining = max(0, self.auth_calls - len(self.auth_requests[client_ip]))
            reset_time = int(time.time()) + self.auth_period
        else:
            remaining = max(0, self.calls - len(self.requests[client_ip]))
            reset_time = int(time.time()) + self.period

        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response