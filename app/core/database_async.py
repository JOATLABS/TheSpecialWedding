"""
Async MongoDB connection with connection pooling
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging
from app.core.settings import settings

logger = logging.getLogger(__name__)


class AsyncMongoConnector:
    """
    Async MongoDB connector with connection pooling
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """Connect to MongoDB with connection pooling"""
        try:
            self.client = AsyncIOMotorClient(
                settings.get_database_url(),
                maxPoolSize=settings.mongo_max_pool_size,
                minPoolSize=settings.mongo_min_pool_size,
                maxIdleTimeMS=60000,  # 1 minute idle timeout
                serverSelectionTimeoutMS=5000,  # 5 second server selection timeout
                connectTimeoutMS=10000,  # 10 second connection timeout
                socketTimeoutMS=20000,  # 20 second socket timeout
            )

            self.db = self.client[settings.mongo_db]

            # Test the connection
            await self.client.server_info()
            logger.info(f"Connected to MongoDB: {settings.mongo_db}")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    # Collection getters with async support
    @property
    def guests(self):
        """Get guests collection"""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db["guests"]
    def _get_collection(self, collection_name: str):
        """Helper method to get collection with proper error handling"""
        if self.db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.db[collection_name]
    @property
    def users(self):
        """Get users collection"""
        return self._get_collection("users")
    @property
    def admin_users(self):
        """Get admin users collection"""
        return self._get_collection("admin_users")
    @property
    def weddings(self):
        """Get weddings collection"""
        return self._get_collection("weddings")
    @property
    def rsvps(self):
        """Get rsvps collection"""
        return self._get_collection("rsvps")
    @property
    def plus_ones(self):
        """Get plus ones collection"""
        return self._get_collection("plus_ones")
    @property
    def gallery(self):
        """Get gallery collection"""
        return self._get_collection("gallery")
    @property
    def forms(self):
        """Get forms collection"""
        return self._get_collection("forms")
    @property
    def form_responses(self):
        """Get form responses collection"""
        return self._get_collection("form_responses")
    @property
    def form_distributions(self):
        """Get form distributions collection"""
        return self._get_collection("form_distributions")
    @property
    def subscription_plans(self):
        """Get subscription plans collection"""
        return self._get_collection("subscription_plans")
    @property
    def ai_usage(self):
        """Get AI usage collection"""
        return self._get_collection("ai_usage")
    @property
    def vendors(self):
        """Get vendors collection"""
        return self._get_collection("vendors")
    @property
    def wedding_checklist(self):
        """Get wedding checklist collection"""
        return self._get_collection("wedding_checklist")
    @property
    def saas_content(self):
        """Get SAAS content collection"""
        return self._get_collection("saas_content")
    @property
    def audit_logs(self):
        """Get audit logs collection"""
        return self._get_collection("audit_logs")
    @property
    def otp_codes(self):
        """Get OTP codes collection"""
        return self._get_collection("otp_codes")
    @property
    def otp_audit_log(self):
        """Get OTP audit log collection"""
        return self._get_collection("otp_audit_log")
    @property
    def access_logs(self):
        """Get access logs collection"""
        return self._get_collection("access_logs")
    async def create_indexes(self):
        """Create database indexes for performance optimization"""
        try:
            # Guests indexes
            await self.guests.create_index("wedding_id")
            await self.guests.create_index("email")
            await self.guests.create_index("invitation_code")
            await self.guests.create_index([("wedding_id", 1), ("email", 1)], unique=True)
            # Users indexes
            await self.users.create_index("email", unique=True)
            await self.users.create_index("role")
            await self.users.create_index("is_active")
            await self.users.create_index("subscription.plan_id")

            # Admin users indexes
            await self.admin_users.create_index("email", unique=True)

            # Weddings indexes
            await self.weddings.create_index("slug", unique=True)
            await self.weddings.create_index("planner_id")
            await self.weddings.create_index("date")
            await self.weddings.create_index([("planner_id", 1), ("date", -1)])
            # RSVPs indexes
            await self.rsvps.create_index("wedding_id")
            await self.rsvps.create_index("guest_id")
            await self.rsvps.create_index([("wedding_id", 1), ("guest_id", 1)], unique=True)
            # Forms indexes
            await self.forms.create_index("wedding_id")
            await self.forms.create_index("is_active")
            await self.forms.create_index([("wedding_id", 1), ("is_active", 1)])
            # Form responses indexes
            await self.form_responses.create_index("form_id")
            await self.form_responses.create_index("wedding_id")
            await self.form_responses.create_index("guest_id")
            await self.form_responses.create_index("submitted_at")

            # Subscription plans indexes
            await self.subscription_plans.create_index("is_active")
            await self.subscription_plans.create_index("price")

            # Audit logs indexes
            await self.audit_logs.create_index("timestamp")
            await self.audit_logs.create_index("event_type")
            await self.audit_logs.create_index("user_id")
            await self.audit_logs.create_index("ip_address")
            await self.audit_logs.create_index([("timestamp", -1), ("event_type", 1)])
            # OTP codes indexes (Context7 best practices)
            await self.otp_codes.create_index(
                "expires_at",
                expireAfterSeconds=0,  # TTL index for automatic cleanup
                background=True
            )
            await self.otp_codes.create_index(
                [("wedding_id", 1), ("contact", 1), ("verified", 1)],
                name="otp_lookup_idx",
                background=True
            )
            await self.otp_codes.create_index(
                [("guest_id", 1), ("contact_type", 1), ("created_at", -1)],
                name="rate_limit_idx",
                background=True
            )
            await self.otp_codes.create_index(
                [("guest_id", 1), ("verified", 1)],
                name="guest_otp_idx",
                background=True
            )
            await self.otp_codes.create_index(
                [("verified", 1), ("created_at", 1)],
                name="cleanup_idx",
                background=True
            )
            # OTP audit log indexes
            await self.otp_audit_log.create_index(
                "timestamp",
                expireAfterSeconds=7776000,  # 90-day TTL
                name="audit_ttl_idx",
                background=True
            )
            await self.otp_audit_log.create_index(
                [("wedding_id", 1), ("timestamp", -1)],
                name="audit_wedding_idx",
                background=True
            )
            await self.otp_audit_log.create_index(
                [("event_type", 1), ("success", 1), ("timestamp", -1)],
                name="audit_event_idx",
                background=True
            )
            # Access logs indexes
            await self.access_logs.create_index("timestamp")
            await self.access_logs.create_index("type")
            await self.access_logs.create_index("wedding_id")
            await self.access_logs.create_index([("timestamp", -1), ("type", 1)])

            logger.info("Database indexes created successfully (including OTP security indexes)")

        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")


# Global async mongo connector instance
async_mongo = AsyncMongoConnector()


async def init_database():
    """Initialize database connection and indexes"""
    await async_mongo.connect()
    await async_mongo.create_indexes()


async def close_database():
    """Close database connection"""
    await async_mongo.disconnect()