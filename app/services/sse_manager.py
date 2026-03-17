"""
SSE (Server-Sent Events) Connection Manager

Hybrid in-process + Redis pub/sub for real-time notification streaming.
Each authenticated user gets their own asyncio.Queue (in-process) for the
SSE response generator.  When a mutation broadcasts an event, it is published
to a Redis channel so that *all* uvicorn workers deliver it to any connected
client — not just the worker that handled the mutation.

If Redis is unavailable the manager falls back to in-process-only delivery
(same as the original implementation) so the app keeps working even when
Redis is down.
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Global ceiling — reject new connections once this is hit across all users.
MAX_GLOBAL_CONNECTIONS = 2000

# Redis channel used for cross-worker SSE fan-out.
_REDIS_SSE_CHANNEL = "sse:broadcast"


class SSEManager:
    """Manages SSE connections for real-time notification streaming."""

    # Maximum connections per user to prevent resource exhaustion
    MAX_CONNECTIONS_PER_USER = 10

    def __init__(self):
        # Map of user_email -> set of asyncio.Queue (one per browser tab/connection)
        self._connections: Dict[str, Set[asyncio.Queue]] = {}
        # Redis subscriber connection (dedicated — cannot be shared with cache ops)
        self._redis_sub = None  # type: Optional[object]
        self._redis_pub = None  # type: Optional[object]
        self._listener_task: Optional[asyncio.Task] = None
        self._total_connections = 0

    # ------------------------------------------------------------------
    # Redis integration
    # ------------------------------------------------------------------

    async def start_redis_listener(self):
        """Start listening for cross-worker SSE events on Redis pub/sub.

        Called once during app startup (lifespan).  Uses a *dedicated* Redis
        connection for the subscriber because `redis.asyncio` pub/sub requires
        a long-lived blocking read.
        """
        try:
            from app.core.settings import settings
            if not settings.redis_enabled:
                logger.info("SSE Redis pub/sub disabled (REDIS_ENABLED=false)")
                return

            import redis.asyncio as aioredis

            # Build a dedicated connection for subscribing
            self._redis_sub = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=None,  # Blocking read for pub/sub
                retry_on_timeout=True,
            )
            # Build a separate connection for publishing
            self._redis_pub = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )

            await self._redis_pub.ping()
            logger.info("SSE Redis pub/sub connected")

            # Background task that reads from the Redis channel
            self._listener_task = asyncio.create_task(self._redis_listener())

        except Exception as e:
            logger.warning(f"SSE Redis pub/sub unavailable, falling back to in-process only: {e}")
            self._redis_sub = None
            self._redis_pub = None

    async def stop_redis_listener(self):
        """Cleanly shut down the Redis listener on app shutdown."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._redis_sub:
            await self._redis_sub.close()
        if self._redis_pub:
            await self._redis_pub.close()
        logger.info("SSE Redis pub/sub disconnected")

    async def _redis_listener(self):
        """Long-running task that subscribes to the Redis channel and fans out
        events to local in-process queues."""
        try:
            pubsub = self._redis_sub.pubsub()
            await pubsub.subscribe(_REDIS_SSE_CHANNEL)
            logger.info(f"SSE Redis listener subscribed to {_REDIS_SSE_CHANNEL}")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    payload = json.loads(message["data"])
                    user_email = payload.get("user_email")
                    event = payload.get("event")
                    if user_email and event:
                        await self._deliver_to_local_queues(user_email, event)
                except Exception as e:
                    logger.warning(f"SSE Redis listener: bad message: {e}")

        except asyncio.CancelledError:
            logger.info("SSE Redis listener cancelled")
            raise
        except Exception as e:
            logger.error(f"SSE Redis listener crashed: {e}", exc_info=True)

    async def _publish_via_redis(self, user_email: str, event: dict):
        """Publish an event to Redis so all workers can fan it out."""
        if not self._redis_pub:
            return False
        try:
            payload = json.dumps({"user_email": user_email, "event": event})
            await self._redis_pub.publish(_REDIS_SSE_CHANNEL, payload)
            return True
        except Exception as e:
            logger.warning(f"SSE Redis publish failed, falling back to local: {e}")
            return False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self, user_email: str) -> asyncio.Queue:
        """Register a new SSE connection for a user. Returns the queue to listen on."""
        # Global ceiling check
        if self._total_connections >= MAX_GLOBAL_CONNECTIONS:
            logger.error(f"SSE: Global connection limit ({MAX_GLOBAL_CONNECTIONS}) reached, rejecting {user_email}")
            raise ConnectionError("SSE connection limit reached")

        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        if user_email not in self._connections:
            self._connections[user_email] = set()

        # Enforce per-user connection limit to prevent memory leaks
        if len(self._connections[user_email]) >= self.MAX_CONNECTIONS_PER_USER:
            # Evict the oldest connection (arbitrary from set, but prevents unbounded growth)
            oldest = next(iter(self._connections[user_email]))
            self._connections[user_email].discard(oldest)
            self._total_connections -= 1
            logger.warning(f"SSE: Evicted stale connection for {user_email} (hit limit of {self.MAX_CONNECTIONS_PER_USER})")

        self._connections[user_email].add(queue)
        self._total_connections += 1
        logger.info(f"SSE connected: {user_email} (user={len(self._connections[user_email])}, global={self._total_connections})")
        return queue

    def disconnect(self, user_email: str, queue: asyncio.Queue):
        """Remove an SSE connection for a user."""
        if user_email in self._connections:
            if queue in self._connections[user_email]:
                self._connections[user_email].discard(queue)
                self._total_connections = max(0, self._total_connections - 1)
            if not self._connections[user_email]:
                del self._connections[user_email]
            logger.info(f"SSE disconnected: {user_email} (global={self._total_connections})")

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def _deliver_to_local_queues(self, user_email: str, event: dict):
        """Push an event to all in-process queues for a user (single worker)."""
        if user_email not in self._connections:
            return

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
            self._total_connections = max(0, self._total_connections - 1)
        if dead_queues and not self._connections.get(user_email):
            self._connections.pop(user_email, None)

    async def broadcast_to_user(self, user_email: str, event_type: str, data: dict):
        """Send an event to all connections for a specific user across all workers."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Try Redis first (reaches all workers)
        published = await self._publish_via_redis(user_email, event)

        if not published:
            # Fallback: deliver to this worker's local queues only
            await self._deliver_to_local_queues(user_email, event)

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
        """Total number of active SSE connections on this worker."""
        return self._total_connections

    @property
    def connected_users(self) -> int:
        """Number of users with active SSE connections on this worker."""
        return len(self._connections)


# Singleton instance
sse_manager = SSEManager()
