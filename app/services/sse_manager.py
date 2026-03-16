"""
SSE (Server-Sent Events) Connection Manager

In-process pub/sub for real-time notification streaming.
Each authenticated user gets their own asyncio.Queue.
When a notification is created, the relevant user's queue gets an event pushed to it.
"""

import asyncio
import logging
from typing import Dict, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages SSE connections for real-time notification streaming."""

    # Maximum connections per user to prevent resource exhaustion
    MAX_CONNECTIONS_PER_USER = 10

    def __init__(self):
        # Map of user_email -> set of asyncio.Queue (one per browser tab/connection)
        self._connections: Dict[str, Set[asyncio.Queue]] = {}

    def connect(self, user_email: str) -> asyncio.Queue:
        """Register a new SSE connection for a user. Returns the queue to listen on."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        if user_email not in self._connections:
            self._connections[user_email] = set()

        # Enforce per-user connection limit to prevent memory leaks
        if len(self._connections[user_email]) >= self.MAX_CONNECTIONS_PER_USER:
            # Evict the oldest connection (arbitrary from set, but prevents unbounded growth)
            oldest = next(iter(self._connections[user_email]))
            self._connections[user_email].discard(oldest)
            logger.warning(f"SSE: Evicted stale connection for {user_email} (hit limit of {self.MAX_CONNECTIONS_PER_USER})")

        self._connections[user_email].add(queue)
        logger.info(f"SSE connected: {user_email} (total connections: {len(self._connections[user_email])})")
        return queue

    def disconnect(self, user_email: str, queue: asyncio.Queue):
        """Remove an SSE connection for a user."""
        if user_email in self._connections:
            self._connections[user_email].discard(queue)
            if not self._connections[user_email]:
                del self._connections[user_email]
            logger.info(f"SSE disconnected: {user_email}")

    async def broadcast_to_user(self, user_email: str, event_type: str, data: dict):
        """Send an event to all connections for a specific user."""
        if user_email not in self._connections:
            return

        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        dead_queues = set()
        for queue in self._connections[user_email]:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest message and retry
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except Exception:
                    dead_queues.add(queue)

        # Clean up dead connections
        for q in dead_queues:
            self._connections[user_email].discard(q)
        if dead_queues and not self._connections.get(user_email):
            self._connections.pop(user_email, None)

    async def broadcast_data_change(
        self,
        user_email: str,
        resource: str,
        action: str,
        wedding_id: str | None = None,
        record_id: str | None = None,
    ):
        """Notify a user that a data resource has changed.

        The frontend uses `resource` + `wedding_id` to decide which queries to
        invalidate — it never receives the actual data, just a "something changed"
        signal so it can refetch what it needs.

        Args:
            user_email: The planner/admin who owns the data.
            resource: One of 'guest', 'rsvp', 'wedding', 'plus_one', 'budget',
                      'table', 'invite', 'checkin'.
            action: One of 'created', 'updated', 'deleted', 'bulk_updated'.
            wedding_id: Optional — scopes the change to a specific wedding.
            record_id: Optional — the specific record that changed.
        """
        await self.broadcast_to_user(user_email, "data-change", {
            "resource": resource,
            "action": action,
            "wedding_id": wedding_id,
            "record_id": record_id,
        })

    @property
    def active_connections(self) -> int:
        """Total number of active SSE connections."""
        return sum(len(queues) for queues in self._connections.values())

    @property
    def connected_users(self) -> int:
        """Number of users with active SSE connections."""
        return len(self._connections)


# Singleton instance
sse_manager = SSEManager()
