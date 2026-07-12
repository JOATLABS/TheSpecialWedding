"""
Shared rate limiter for public FastAPI endpoints.
Uses Redis when available so limits hold across replicas, with an
in-memory fallback for local/dev environments without Redis.
"""

import ipaddress
import logging
import time
from collections import deque
from typing import Deque, Dict, Tuple

from fastapi import HTTPException, Request

from app.core.cache import CacheKeys, cache

logger = logging.getLogger(__name__)


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
    ):
        self.bucket_name = bucket_name
        self.default_requests_per_minute = default_requests_per_minute
        self.window_seconds = window_seconds
        self.max_ips_tracked = max_ips_tracked
        self.ip_requests: Dict[str, Deque[float]] = {}

    def _cleanup_old_requests(
        self, request_queue: Deque[float], current_time: float
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
    ) -> Tuple[bool, int, int]:
        key = CacheKeys.rate_limit(client_ip, self.bucket_name)
        current_count = await cache.increment(key, expire=self.window_seconds)
        if current_count is None:
            return self._check_memory_limit(client_ip, limit)

        ttl = await cache.ttl(key)
        reset_time = int(time.time()) + (ttl if ttl > 0 else self.window_seconds)
        remaining = max(0, limit - current_count)

        return current_count <= limit, remaining, reset_time

    def _check_memory_limit(self, client_ip: str, limit: int) -> Tuple[bool, int, int]:
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
    ) -> Tuple[bool, int, int]:
        limit = requests_per_minute or self.default_requests_per_minute

        if cache.enabled and cache.redis_client:
            try:
                return await self._check_redis_limit(client_ip, limit)
            except Exception as exc:
                logger.warning(
                    "Redis-backed rate limit failed for bucket %s: %s",
                    self.bucket_name,
                    exc,
                )

        return self._check_memory_limit(client_ip, limit)

    def get_stats(self) -> Dict[str, int]:
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
) -> RateLimiter:
    return RateLimiter(
        bucket_name=bucket_name,
        default_requests_per_minute=requests_per_minute,
        max_ips_tracked=max_ips,
        window_seconds=window_seconds,
    )


public_read_limiter = create_rate_limiter("public_read", requests_per_minute=60)
public_search_limiter = create_rate_limiter("public_search", requests_per_minute=30)
public_slug_limiter = create_rate_limiter("public_slug", requests_per_minute=100)


def get_client_ip(request: Request) -> str:
    """Resolve a client IP without trusting attacker-supplied proxy headers.

    Forwarding headers are accepted only when the direct peer is a private or
    loopback address, which is the expected shape for our ingress/reverse-proxy
    deployments. A public peer cannot choose a fresh rate-limit identity by
    sending a forged ``X-Forwarded-For`` value.
    """

    direct_ip = request.client.host if request.client else "unknown"
    try:
        direct_address = ipaddress.ip_address(direct_ip)
        trusted_proxy = direct_address.is_private or direct_address.is_loopback
    except ValueError:
        trusted_proxy = False

    if trusted_proxy:
        for header in (
            "CF-Connecting-IP",
            "True-Client-IP",
            "X-Real-IP",
            "X-Forwarded-For",
        ):
            value = request.headers.get(header)
            if not value:
                continue
            candidate = value.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            return candidate

    return direct_ip


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
