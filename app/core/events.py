"""
Event Sourcing and Domain Events System
"""
from typing import Dict, List, Any, Optional, Type, Callable, Awaitable, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum
import json
import asyncio
from app.core.database_async import async_mongo
from app.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Domain event types"""
    # User events
    USER_REGISTERED = "user.registered"
    USER_EMAIL_VERIFIED = "user.email_verified"
    USER_SUBSCRIPTION_CHANGED = "user.subscription_changed"
    # Wedding events
    WEDDING_CREATED = "wedding.created"
    WEDDING_UPDATED = "wedding.updated"
    WEDDING_DELETED = "wedding.deleted"
    WEDDING_PUBLISHED = "wedding.published"
    # Guest events
    GUEST_ADDED = "guest.added"
    GUEST_UPDATED = "guest.updated"
    GUEST_RSVP_SUBMITTED = "guest.rsvp_submitted"
    GUEST_CHECKED_IN = "guest.checked_in"
    # Form events
    FORM_CREATED = "form.created"
    FORM_SUBMITTED = "form.submitted"
    FORM_RESPONSE_RECEIVED = "form.response_received"
    # Security events
    LOGIN_ATTEMPTED = "security.login_attempted"
    LOGIN_FAILED = "security.login_failed"
    SUSPICIOUS_ACTIVITY = "security.suspicious_activity"
    PASSWORD_CHANGED = "security.password_changed"
    EMAIL_CHANGED = "security.email_changed"
    EMAIL_CHANGE_REQUESTED = "security.email_change_requested"
    # System events
    SUBSCRIPTION_LIMIT_EXCEEDED = "system.subscription_limit_exceeded"
    PAYMENT_PROCESSED = "system.payment_processed"
    EMAIL_SENT = "system.email_sent"
    SMS_SENT = "system.sms_sent"


class DomainEvent(BaseModel):
    """Base domain event"""
    event_id: str = Field(default_factory=lambda: f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}")
    event_type: EventType
    aggregate_id: str  # ID of the entity this event relates to
    aggregate_type: str  # Type of entity (user, wedding, guest, etc.)
    event_data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    version: int = 1

    class Config:
        use_enum_values = True


class EventStore:
    """Event store for persisting and retrieving domain events"""

    def __init__(self):
        self._async_mongo = async_mongo

    @property
    def events_collection(self):
        """Get events collection with proper error handling"""
        return self._async_mongo._get_collection("domain_events")

    @property
    def snapshots_collection(self):
        """Get snapshots collection with proper error handling"""
        return self._async_mongo._get_collection("aggregate_snapshots")

    async def append_event(self, event: DomainEvent) -> bool:
        """Append event to the event store"""
        try:
            await self.events_collection.insert_one(event.model_dump())
            # Cache recent events for performance
            await cache.set(
                f"recent_event:{event.event_id}",
                event.model_dump(),
                expire=3600  # 1 hour
            )

            logger.info(f"Event stored: {event.event_type} for {event.aggregate_type}:{event.aggregate_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store event {event.event_id}: {str(e)}")
            return False

    async def get_events(
        self,
        aggregate_id: str,
        aggregate_type: str,
        from_version: int = 0
    ) -> List[DomainEvent]:
        """Get events for a specific aggregate"""
        try:
            cursor = self.events_collection.find({
                "aggregate_id": aggregate_id,
                "aggregate_type": aggregate_type,
                "version": {"$gt": from_version}
            }).sort("timestamp", 1)

            events = []
            async for event_doc in cursor:
                events.append(DomainEvent(**event_doc))

            return events

        except Exception as e:
            logger.error(f"Failed to retrieve events for {aggregate_type}:{aggregate_id}: {str(e)}")
            return []

    async def get_events_by_type(
        self,
        event_type: EventType,
        limit: int = 100,
        offset: int = 0
    ) -> List[DomainEvent]:
        """Get events by type"""
        try:
            cursor = self.events_collection.find({
                "event_type": event_type.value
            }).sort("timestamp", -1).skip(offset).limit(limit)

            events = []
            async for event_doc in cursor:
                events.append(DomainEvent(**event_doc))

            return events

        except Exception as e:
            logger.error(f"Failed to retrieve events by type {event_type}: {str(e)}")
            return []

    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        snapshot_data: Dict[str, Any],
        version: int
    ) -> bool:
        """Save aggregate snapshot for performance optimization"""
        try:
            await self.snapshots_collection.replace_one(
                {
                    "aggregate_id": aggregate_id,
                    "aggregate_type": aggregate_type
                },
                {
                    "aggregate_id": aggregate_id,
                    "aggregate_type": aggregate_type,
                    "snapshot_data": snapshot_data,
                    "version": version,
                    "timestamp": datetime.now(timezone.utc)
                },
                upsert=True
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save snapshot for {aggregate_type}:{aggregate_id}: {str(e)}")
            return False

    async def get_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest snapshot for an aggregate"""
        try:
            snapshot = await self.snapshots_collection.find_one({
                "aggregate_id": aggregate_id,
                "aggregate_type": aggregate_type
            })

            return snapshot

        except Exception as e:
            logger.error(f"Failed to retrieve snapshot for {aggregate_type}:{aggregate_id}: {str(e)}")
            return None


class EventBus:
    """Event bus for publishing and subscribing to domain events"""

    def __init__(self):
        self.subscribers: Dict[EventType, List[Union[Callable[[DomainEvent], Awaitable[None]], Callable[[DomainEvent], None]]]] = {}
        self.event_store = EventStore()

    def subscribe(self, event_type: EventType, handler: Union[Callable[[DomainEvent], Awaitable[None]], Callable[[DomainEvent], None]]):
        """Subscribe to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed handler {handler.__name__} to {event_type}")

    async def publish(self, event: DomainEvent):
        """Publish an event to all subscribers"""
        # Store event first
        await self.event_store.append_event(event)
        # Notify subscribers
        if event.event_type in self.subscribers:
            tasks = []
            for handler in self.subscribers[event.event_type]:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(event))
                else:
                    # Run sync handler in executor
                    tasks.append(asyncio.get_event_loop().run_in_executor(None, handler, event))
            # Execute all handlers concurrently
            if tasks:
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Error in event handlers for {event.event_type}: {str(e)}")
        logger.info(f"Published event: {event.event_type}")


# Global event bus instance
event_bus = EventBus()


# Event factory functions
class EventFactory:
    """Factory for creating domain events"""
    @staticmethod
    def user_registered(user_id: str, email: str, role: str) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.USER_REGISTERED,
            aggregate_id=user_id,
            aggregate_type="user",
            event_data={
                "email": email,
                "role": role,
                "registration_timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    @staticmethod
    def wedding_created(wedding_id: str, planner_id: str, title: str) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.WEDDING_CREATED,
            aggregate_id=wedding_id,
            aggregate_type="wedding",
            event_data={
                "planner_id": planner_id,
                "title": title,
                "creation_timestamp": datetime.now(timezone.utc).isoformat()
            },
            user_id=planner_id
        )
    @staticmethod
    def guest_rsvp_submitted(guest_id: str, wedding_id: str, response: str) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.GUEST_RSVP_SUBMITTED,
            aggregate_id=guest_id,
            aggregate_type="guest",
            event_data={
                "wedding_id": wedding_id,
                "response": response,
                "submission_timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    @staticmethod
    def subscription_limit_exceeded(user_id: str, resource_type: str, limit: int) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.SUBSCRIPTION_LIMIT_EXCEEDED,
            aggregate_id=user_id,
            aggregate_type="user",
            event_data={
                "resource_type": resource_type,
                "limit": limit,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            user_id=user_id
        )
    @staticmethod
    def login_failed(email: str, ip_address: str, reason: str) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.LOGIN_FAILED,
            aggregate_id=email,
            aggregate_type="security",
            event_data={
                "ip_address": ip_address,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            metadata={
                "security_event": True,
                "severity": "medium"
            }
        )
    @staticmethod
    def password_changed(user_id: str, email: str, ip_address: str = None) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.PASSWORD_CHANGED,
            aggregate_id=user_id,
            aggregate_type="user",
            event_data={
                "email": email,
                "ip_address": ip_address,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            metadata={
                "security_event": True,
                "severity": "low"
            },
            user_id=user_id
        )
    @staticmethod
    def email_change_requested(user_id: str, old_email: str, new_email: str, ip_address: str = None) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.EMAIL_CHANGE_REQUESTED,
            aggregate_id=user_id,
            aggregate_type="user",
            event_data={
                "old_email": old_email,
                "new_email": new_email,
                "ip_address": ip_address,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            metadata={
                "security_event": True,
                "severity": "medium"
            },
            user_id=user_id
        )
    @staticmethod
    def email_changed(user_id: str, old_email: str, new_email: str) -> DomainEvent:
        return DomainEvent(
            event_type=EventType.EMAIL_CHANGED,
            aggregate_id=user_id,
            aggregate_type="user",
            event_data={
                "old_email": old_email,
                "new_email": new_email,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            metadata={
                "security_event": True,
                "severity": "medium"
            },
            user_id=user_id
        )


# Decorator for automatically publishing events
def publishes_event(event_factory_func: Callable[..., DomainEvent]):
    """Decorator to automatically publish events from service methods"""
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # Create and publish event
            try:
                event = event_factory_func(*args, **kwargs, result=result)
                await event_bus.publish(event)
            except Exception as e:
                logger.error(f"Failed to publish event from {func.__name__}: {str(e)}")

            return result

        return wrapper
    return decorator


# Event handlers setup
async def setup_event_handlers():
    """Setup default event handlers"""
    async def log_security_events(event: DomainEvent):
        """Log security-related events"""
        if event.metadata.get("security_event"):
            logger.warning(f"Security event: {event.event_type} - {event.event_data}")
    async def update_subscription_usage(event: DomainEvent):
        """Update subscription usage counters"""
        if event.event_type in [
            EventType.WEDDING_CREATED,
            EventType.FORM_CREATED,
            EventType.EMAIL_SENT
        ]:
            # Update usage tracking
            from app.services.subscription_service import SubscriptionService
            subscription_service = SubscriptionService()
            if event.user_id:
                # Increment appropriate usage counter
                if event.event_type == EventType.WEDDING_CREATED:
                    subscription_service.increment_usage(event.user_id, "weddings", 1)
                elif event.event_type == EventType.EMAIL_SENT:
                    subscription_service.increment_usage(event.user_id, "emails", 1)
    async def send_notifications(event: DomainEvent):
        """Send notifications for important events"""
        if event.event_type == EventType.GUEST_RSVP_SUBMITTED:
            # Send notification to wedding planner
            logger.info(f"RSVP notification: Guest {event.aggregate_id} responded to wedding {event.event_data['wedding_id']}")
    # Subscribe handlers
    event_bus.subscribe(EventType.LOGIN_FAILED, log_security_events)
    event_bus.subscribe(EventType.SUSPICIOUS_ACTIVITY, log_security_events)
    event_bus.subscribe(EventType.WEDDING_CREATED, update_subscription_usage)
    event_bus.subscribe(EventType.FORM_CREATED, update_subscription_usage)
    event_bus.subscribe(EventType.EMAIL_SENT, update_subscription_usage)
    event_bus.subscribe(EventType.GUEST_RSVP_SUBMITTED, send_notifications)
    logger.info("Event handlers setup complete")