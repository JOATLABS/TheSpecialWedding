"""
In-memory rate limiter for FastAPI endpoints.
IP-based rate limiting with sliding window and automatic cleanup.
This is a first layer of protection; production relies on Cloudflare/Nginx.
"""
import time
import logging
from typing import Dict, Tuple
from collections import deque
from fastapi import HTTPException
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.
    Tracks requests per IP with automatic cleanup of old entries.
    """

    def __init__(
        self,
        default_requests_per_minute: int = 60,
        max_ips_tracked: int = 10000,
        ttl_seconds: int = 120
    ):
        """
        Initialize the rate limiter.

        Args:
            default_requests_per_minute: Default limit for endpoints
            max_ips_tracked: Maximum number of unique IPs to track (DoS protection)
            ttl_seconds: Time-to-live for request entries (cleanup window)
        """
        self.default_requests_per_minute = default_requests_per_minute
        self.max_ips_tracked = max_ips_tracked
        self.ttl_seconds = ttl_seconds

        # Store request timestamps per IP
        # Format: {"ip": deque([timestamp1, timestamp2, ...])}
        self.ip_requests: Dict[str, deque] = {}

    def _cleanup_old_requests(self, request_queue: deque) -> None:
        """Remove requests older than the TTL window."""
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > self.ttl_seconds:
            request_queue.popleft()

    def _cleanup_ips(self) -> None:
        """Remove IPs with empty request queues (memory cleanup)."""
        ips_to_remove = [ip for ip, queue in self.ip_requests.items() if len(queue) == 0]
        for ip in ips_to_remove:
            del self.ip_requests[ip]

        # If tracking too many IPs, do aggressive cleanup
        if len(self.ip_requests) > self.max_ips_tracked:
            # Sort by queue length and remove oldest 10% of tracked IPs
            sorted_ips = sorted(self.ip_requests.items(), key=lambda x: len(x[1]))
            num_to_remove = max(1, len(sorted_ips) // 10)
            for ip, _ in sorted_ips[:num_to_remove]:
                del self.ip_requests[ip]

    def is_allowed(
        self,
        client_ip: str,
        requests_per_minute: int = None
    ) -> Tuple[bool, int, int]:
        """
        Check if a request from client_ip is allowed.

        Args:
            client_ip: The client IP address
            requests_per_minute: Custom limit for this IP (overrides default)

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_time_unix)
        """
        limit = requests_per_minute or self.default_requests_per_minute
        period = 60  # 1 minute window

        current_time = time.time()

        # Get or create request queue for this IP
        if client_ip not in self.ip_requests:
            self.ip_requests[client_ip] = deque()

        request_queue = self.ip_requests[client_ip]

        # Clean old requests outside the window
        self._cleanup_old_requests(request_queue)

        # Check if limit exceeded
        if len(request_queue) >= limit:
            reset_time = int(current_time) + period
            return False, 0, reset_time

        # Add current request
        request_queue.append(current_time)

        # Periodic cleanup of old IPs
        if len(self.ip_requests) % 100 == 0:
            self._cleanup_ips()

        remaining = max(0, limit - len(request_queue))
        reset_time = int(current_time) + period

        return True, remaining, reset_time

    def get_stats(self) -> Dict:
        """Get statistics about the rate limiter."""
        total_ips = len(self.ip_requests)
        total_requests = sum(len(queue) for queue in self.ip_requests.values())

        return {
            "total_ips_tracked": total_ips,
            "total_requests_in_window": total_requests,
            "max_ips_tracked": self.max_ips_tracked,
            "ttl_seconds": self.ttl_seconds
        }


def create_rate_limiter(
    requests_per_minute: int = 60,
    max_ips: int = 10000
) -> RateLimiter:
    """Factory function to create a rate limiter instance."""
    return RateLimiter(
        default_requests_per_minute=requests_per_minute,
        max_ips_tracked=max_ips
    )


# Create default rate limiters for different endpoints
public_read_limiter = create_rate_limiter(requests_per_minute=60)
public_search_limiter = create_rate_limiter(requests_per_minute=30)
public_slug_limiter = create_rate_limiter(requests_per_minute=100)


def check_rate_limit(
    client_ip: str,
    limiter: RateLimiter,
    requests_per_minute: int = None
) -> None:
    """
    Check rate limit and raise HTTPException if exceeded.

    Args:
        client_ip: The client IP address
        limiter: The RateLimiter instance to use
        requests_per_minute: Optional custom limit

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    is_allowed, remaining, reset_time = limiter.is_allowed(
        client_ip,
        requests_per_minute=requests_per_minute
    )

    if not is_allowed:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": 60
            }
        )
