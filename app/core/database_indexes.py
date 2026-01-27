"""
MongoDB Index Definitions for Support Tickets
Ensures optimal query performance for multi-tenant support system
"""
from pymongo import ASCENDING, DESCENDING, TEXT
from app.core.database import mongo
import logging

logger = logging.getLogger(__name__)


async def create_support_ticket_indexes():
    """
    Create indexes for support_tickets collection

    Key queries that need optimization:
    1. Get tickets by assigned_to (planner isolation) + status
    2. Get unread tickets for a planner
    3. Find tickets by phone number (guest lookup)
    4. Get tickets by wedding_id
    5. Sort by created_at (recent first)
    6. Calculate SLA metrics by date range
    """
    collection = mongo.db["support_tickets"]

    try:
        # 1. Planner isolation + status filtering (most common query)
        await collection.create_index(
            [("assigned_to", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_assigned_status_created"
        )
        logger.info("Created index: idx_assigned_status_created")

        # 2. Unread tickets for planners
        await collection.create_index(
            [("assigned_to", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)],
            name="idx_assigned_unread"
        )
        logger.info("Created index: idx_assigned_unread")

        # 3. Phone number lookup (for finding guest history)
        await collection.create_index(
            [("phone", ASCENDING), ("created_at", DESCENDING)],
            name="idx_phone_created"
        )
        logger.info("Created index: idx_phone_created")

        # 4. Wedding-scoped queries
        await collection.create_index(
            [("wedding_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_wedding_status_created"
        )
        logger.info("Created index: idx_wedding_status_created")

        # 5. Guest-related tickets
        await collection.create_index(
            [("guest_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_guest_created"
        )
        logger.info("Created index: idx_guest_created")

        # 6. Source + provider filtering (SMS vs web tickets)
        await collection.create_index(
            [("source", ASCENDING), ("provider", ASCENDING)],
            name="idx_source_provider"
        )
        logger.info("Created index: idx_source_provider")

        # 7. SLA metrics queries (response time analysis)
        await collection.create_index(
            [("status", ASCENDING), ("first_response_time_minutes", ASCENDING)],
            name="idx_status_response_time"
        )
        logger.info("Created index: idx_status_response_time")

        # 8. Date-based queries for analytics
        await collection.create_index(
            [("created_at", DESCENDING)],
            name="idx_created_desc"
        )
        logger.info("Created index: idx_created_desc")

        # 9. Full-text search on message content (optional, for search feature)
        await collection.create_index(
            [("message", TEXT)],
            name="idx_message_text",
            default_language="english"
        )
        logger.info("Created index: idx_message_text (full-text search)")

        logger.info("All support ticket indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating support ticket indexes: {str(e)}")
        return False


async def create_wedding_indexes():
    """
    Create indexes for weddings collection

    Key queries that need optimization:
    1. Get wedding by slug (public URL access) - UNIQUE
    2. Get weddings by planner email
    3. Sort by date
    """
    collection = mongo.db["weddings"]

    try:
        # 1. Unique slug index (prevents collision across planners)
        await collection.create_index(
            [("slug", ASCENDING)],
            name="idx_slug_unique",
            unique=True,
            sparse=True  # Allow null slugs (for legacy data)
        )
        logger.info("Created index: idx_slug_unique (unique)")

        # 2. Planner lookup
        await collection.create_index(
            [("assigned_planner_email", ASCENDING)],
            name="idx_assigned_planner"
        )
        logger.info("Created index: idx_assigned_planner")

        # 3. Date-based sorting
        await collection.create_index(
            [("date", ASCENDING)],
            name="idx_wedding_date"
        )
        logger.info("Created index: idx_wedding_date")

        logger.info("All wedding indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating wedding indexes: {str(e)}")
        return False


async def create_guest_indexes():
    """
    Create indexes for guests collection

    Key queries that need optimization:
    1. Get guests by wedding_id (list guests)
    2. Get guest by token (guest access)
    3. Get guest by phone (search)
    4. Get guest by email (lookup)
    """
    collection = mongo.get_guest_collection()

    try:
        # 1. List guests by wedding (most common query)
        await collection.create_index(
            [("wedding_id", ASCENDING)],
            name="idx_wedding_id"
        )
        logger.info("Created index: idx_wedding_id")

        # 2. Guest access by token
        await collection.create_index(
            [("token", ASCENDING)],
            name="idx_token"
        )
        logger.info("Created index: idx_token")

        # 3. Phone lookup
        await collection.create_index(
            [("phone", ASCENDING)],
            name="idx_phone"
        )
        logger.info("Created index: idx_phone")

        # 4. Email lookup
        await collection.create_index(
            [("email", ASCENDING)],
            name="idx_email"
        )
        logger.info("Created index: idx_email")

        logger.info("All guest indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating guest indexes: {str(e)}")
        return False


async def create_all_indexes():
    """Create all database indexes (called on app startup)"""
    try:
        await create_support_ticket_indexes()
        await create_wedding_indexes()
        await create_guest_indexes()
        logger.info("All database indexes created/verified")
    except Exception as e:
        logger.error(f"Error creating database indexes: {str(e)}")


# Index usage examples and query patterns
QUERY_PATTERNS = {
    "planner_new_tickets": {
        "description": "Get new tickets for a specific planner",
        "query": {"assigned_to": "planner@example.com", "status": "new"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_assigned_status_created"
    },
    "planner_unread": {
        "description": "Get unread tickets for planner",
        "query": {"assigned_to": "planner@example.com", "is_read": False},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_assigned_unread"
    },
    "guest_history": {
        "description": "Get all tickets from a specific phone number",
        "query": {"phone": "+13195296088"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_phone_created"
    },
    "wedding_tickets": {
        "description": "Get all tickets for a wedding",
        "query": {"wedding_id": "abc123", "status": "new"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_wedding_status_created"
    },
    "sla_analysis": {
        "description": "Analyze average response times for resolved tickets",
        "query": {"status": "resolved", "first_response_time_minutes": {"$exists": True}},
        "uses_index": "idx_status_response_time"
    }
}
