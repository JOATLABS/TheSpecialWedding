"""
Shared rate limiter for public FastAPI endpoints.
Uses Redis when available so limits hold across replicas, with an
in-memory fallback for local/dev environments without Redis.
"""

import ipaddress
import logging
import time
from collections import deque

from fastapi import HTTPException, Request

from app.core.cache import CacheKeys, cache
from app.core.settings import settings

logger = logging.getLogger(__name__)


class SharedRateLimiterUnavailable(RuntimeError):
    """Raised when a security-sensitive limiter cannot reach shared Redis."""


class RateLimiter:
    """
    Rate limiter with Redis-backed shared counters and in-memory fallback.
    """

    def __init__(
        self,
        bucket_name: str,
        default_requests_per_minute: int = 60,
        window_seconds: int = 60,
        max_ips_tracked: int = 10000,
        require_shared_backend: bool = False,
    ):
        self.bucket_name = bucket_name
        self.default_requests_per_minute = default_requests_per_minute
        self.window_seconds = window_seconds
        self.max_ips_tracked = max_ips_tracked
        self.require_shared_backend = require_shared_backend
        self.ip_requests: dict[str, deque[float]] = {}

    def _cleanup_old_requests(
        self, request_queue: deque[float], current_time: float
    ) -> None:
        while request_queue and current_time - request_queue[0] > self.window_seconds:
            request_queue.popleft()

    def _cleanup_ips(self) -> None:
        empty_ips = [ip for ip, queue in self.ip_requests.items() if not queue]
        for ip in empty_ips:
            del self.ip_requests[ip]

        if len(self.ip_requests) > self.max_ips_tracked:
            sorted_ips = sorted(self.ip_requests.items(), key=lambda item: len(item[1]))
            for ip, _ in sorted_ips[: max(1, len(sorted_ips) // 10)]:
                del self.ip_requests[ip]

    async def _check_redis_limit(
        self, client_ip: str, limit: int
    ) -> tuple[bool, int, int]:
        key = CacheKeys.rate_limit(client_ip, self.bucket_name)
        current_count = await cache.increment(key, expire=self.window_seconds)
        if current_count is None:
            if self.require_shared_backend:
                raise SharedRateLimiterUnavailable(
                    f"Shared rate limiter unavailable for {self.bucket_name}"
                )
            return self._check_memory_limit(client_ip, limit)

        ttl = await cache.ttl(key)
        reset_time = int(time.time()) + (ttl if ttl > 0 else self.window_seconds)
        remaining = max(0, limit - current_count)

        return current_count <= limit, remaining, reset_time

    def _check_memory_limit(self, client_ip: str, limit: int) -> tuple[bool, int, int]:
        current_time = time.time()

        if client_ip not in self.ip_requests:
            self.ip_requests[client_ip] = deque()

        request_queue = self.ip_requests[client_ip]
        self._cleanup_old_requests(request_queue, current_time)

        if len(request_queue) >= limit:
            reset_time = int(current_time) + self.window_seconds
            return False, 0, reset_time

        request_queue.append(current_time)

        if len(self.ip_requests) % 100 == 0:
            self._cleanup_ips()

        remaining = max(0, limit - len(request_queue))
        reset_time = int(current_time) + self.window_seconds
        return True, remaining, reset_time

    async def is_allowed(
        self,
        client_ip: str,
        requests_per_minute: int = None,
    ) -> tuple[bool, int, int]:
        limit = requests_per_minute or self.default_requests_per_minute

        if cache.enabled and cache.redis_client:
            try:
                return await self._check_redis_limit(client_ip, limit)
            except SharedRateLimiterUnavailable:
                raise
            except Exception as exc:
                logger.warning(
                    "Redis-backed rate limit failed for bucket %s: %s",
                    self.bucket_name,
                    exc,
                )

        if self.require_shared_backend:
            logger.error(
                "Required shared rate limiter is unavailable for bucket %s",
                self.bucket_name,
            )
            raise SharedRateLimiterUnavailable(
                f"Shared rate limiter unavailable for {self.bucket_name}"
            )

        return self._check_memory_limit(client_ip, limit)

    def get_stats(self) -> dict[str, int]:
        total_ips = len(self.ip_requests)
        total_requests = sum(len(queue) for queue in self.ip_requests.values())
        return {
            "bucket_name": self.bucket_name,
            "total_ips_tracked": total_ips,
            "total_requests_in_window": total_requests,
            "window_seconds": self.window_seconds,
            "max_ips_tracked": self.max_ips_tracked,
        }


def create_rate_limiter(
    bucket_name: str,
    requests_per_minute: int = 60,
    max_ips: int = 10000,
    window_seconds: int = 60,
    require_shared_backend: bool = False,
) -> RateLimiter:
    return RateLimiter(
        bucket_name=bucket_name,
        default_requests_per_minute=requests_per_minute,
        max_ips_tracked=max_ips,
        window_seconds=window_seconds,
        require_shared_backend=require_shared_backend,
    )


public_read_limiter = create_rate_limiter("public_read", requests_per_minute=60)
public_search_limiter = create_rate_limiter("public_search", requests_per_minute=30)
public_slug_limiter = create_rate_limiter("public_slug", requests_per_minute=100)


def get_client_ip(request: Request) -> str:
    """Resolve a client IP without trusting attacker-supplied proxy headers.

    Forwarding headers are accepted only from an explicitly configured proxy
    network and only through the one header that ingress guarantees it
    overwrites. Private address space alone is never a trust signal.
    """

    direct_ip = request.client.host if request.client else "unknown"
    configured_header = settings.trusted_proxy_client_ip_header
    if not configured_header or not settings.trusted_proxy_cidrs:
        return direct_ip

    try:
        direct_address = ipaddress.ip_address(direct_ip)
        trusted_networks = [
            ipaddress.ip_network(cidr, strict=False)
            for cidr in settings.trusted_proxy_cidrs
        ]
    except ValueError:
        return direct_ip
    if not any(direct_address in network for network in trusted_networks):
        return direct_ip

    value = request.headers.get(configured_header)
    if not value or "," in value:
        return direct_ip
    candidate = value.strip()
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return direct_ip
    return candidate


async def check_rate_limit(
    client_ip: str,
    limiter: RateLimiter,
    requests_per_minute: int = None,
) -> None:
    is_allowed, remaining, reset_time = await limiter.is_allowed(
        client_ip,
        requests_per_minute=requests_per_minute,
    )

    if not is_allowed:
        retry_after = max(1, reset_time - int(time.time()))
        logger.warning("Rate limit exceeded for bucket %s", limiter.bucket_name)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": retry_after,
                "remaining": remaining,
                "reset_time": reset_time,
            },
        )
