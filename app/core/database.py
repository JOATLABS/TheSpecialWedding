"""
Async MongoDB connection using Motor
Maintains same API as PyMongo version for backward compatibility
"""

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class MongoConnector:
    def __init__(self, uri, db_name):
        """Initialize with URI and DB name - maintains backward compatibility"""
        try:
            self.client = AsyncIOMotorClient(
                uri,
                maxPoolSize=50,
                minPoolSize=10,
                maxIdleTimeMS=60000,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=20000,
                tz_aware=True,  # Return timezone-aware UTC datetimes
                tzinfo=__import__("datetime").timezone.utc,  # Set timezone to UTC
            )
            self.db = self.client[db_name]
            logger.info(f"Initialized Motor async client for database: {db_name}")
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB client: {str(e)}")
            raise

    def get_guest_collection(self):
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["guests"]

    def get_platform_metrics_collection(self):
        return self.db["platform_metrics"]

    def get_collection(self, name: str):
        return self.db[name]

    # SAAS collections - User management abstraction layer
    def get_users_collection(self):
        """Unified users collection for all user types (ROOT_ADMIN, wedding_planner, vendor)

        This is the single source of truth for user data access. All services should use
        this method instead of directly accessing mongo.db["users"] to maintain abstraction
        and enable future optimizations (caching, read replicas, monitoring).

        Returns:
            AsyncIOMotorCollection: The users collection
        """
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["users"]  # Unified collection for all user types

    def get_subscription_plans_collection(self):
        """Subscription plans configurable by ROOT_ADMIN"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["subscription_plans"]

    def get_saas_content_collection(self):
        """SAAS landing page content configurable by ROOT_ADMIN"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["saas_content"]

    def get_ai_usage_collection(self):
        """AI feature usage tracking for billing"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["ai_usage"]

    def get_vendors_collection(self):
        """Vendors created by wedding planners"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["vendors"]

    def get_wedding_checklist_collection(self):
        """Wedding checklist items that vendors can update"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["wedding_checklist"]

    def get_calendar_tokens_collection(self):
        """Google Calendar OAuth tokens for planners"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["calendar_tokens"]

    def get_calendar_connections_collection(self):
        """Connected external calendar identities and settings."""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["calendar_connections"]

    def get_calendar_event_syncs_collection(self):
        """Per-target external calendar sync mappings."""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["calendar_event_syncs"]

    def get_meeting_invites_collection(self):
        """Couple-facing invite delivery records for meetings."""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["meeting_invites"]

    def get_planner_tasks_collection(self):
        """Planner-specific tasks and calendar events"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["planner_tasks"]

    def get_admin_users_collection(self):
        """Legacy admin_users collection - returns users collection for backward compatibility

        Note: The admin_users collection no longer exists. All users (ROOT_ADMIN, wedding_planner, vendor)
        are now stored in the unified 'users' collection. This method is kept for backward compatibility
        with authentication code that still references it.
        """
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["users"]  # Redirect to unified users collection

    # Existing collections
    def get_weddings_collection(self):
        """Weddings collection - existing functionality"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["weddings"]

    def get_rsvps_collection(self):
        """RSVPs collection - existing functionality"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["rsvps"]

    def get_plus_ones_collection(self):
        """Plus ones collection - existing functionality"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["plus_ones"]

    def get_gallery_collection(self):
        """Gallery collection - existing functionality"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["gallery"]

    def get_forms_collection(self):
        """Forms collection - custom form builder"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["forms"]

    def get_couple_users_collection(self):
        """Couple portal account records."""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["couple_users"]

    def get_form_responses_collection(self):
        """Form responses collection - form submissions"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["form_responses"]

    def get_form_distributions_collection(self):
        """Form distributions collection - email tracking"""
        if self.db is None:
            raise RuntimeError("Database not connected")
        return self.db["form_distributions"]

    async def test_connection(self):
        """Test the database connection"""
        try:
            await self.client.server_info()
            logger.info("MongoDB connection test successful")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection test failed: {str(e)}")
            return False

    def close(self):
        """Close the database connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


mongo = MongoConnector(settings.MONGO_URI, settings.MONGO_DB)


# Helper functions for application lifecycle
async def init_database():
    """Initialize and test database connection"""
    success = await mongo.test_connection()
    if not success:
        raise RuntimeError("Failed to connect to MongoDB")
    logger.info("Database initialized successfully")


async def close_database():
    """Close database connection"""
    mongo.close()
    logger.info("Database closed successfully")
