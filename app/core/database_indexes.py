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


async def create_table_indexes():
    """
    Create indexes for tables collection (seating orchestration)

    Key queries:
    1. Get tables by wedding_id (seating page)
    """
    collection = mongo.db["tables"]

    try:
        # 1. Wedding ID - Most frequent query (list tables for seating page)
        await collection.create_index(
            [("wedding_id", ASCENDING)],
            name="idx_table_wedding_id"
        )
        logger.info("Created index: idx_table_wedding_id")

        logger.info("All table indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating table indexes: {str(e)}")
        return False


async def create_guest_indexes():
    """
    Create indexes for guests collection

    Key queries:
    1. Get guests by wedding_id (guest list)
    2. Lookup guest by token (login)
    3. Lookup by phone (verification)
    4. Lookup by email
    """
    collection = mongo.db["guests"]
    try:
        # 1. Wedding ID - Most frequent query (list guests)
        await collection.create_index(
            [("wedding_id", ASCENDING)],
            name="idx_wedding_id"
        )
        logger.info("Created index: idx_wedding_id")

        # 2. Token - Unique lookup for guest auth
        await collection.create_index(
            [("token", ASCENDING)],
            name="idx_token",
            unique=True
        )
        logger.info("Created index: idx_token")

        # 3. Phone - Lookup for verification
        await collection.create_index(
            [("phone", ASCENDING)],
            name="idx_guest_phone"
        )
        logger.info("Created index: idx_guest_phone")

        # 4. Email - Lookup
        await collection.create_index(
            [("email", ASCENDING)],
            name="idx_guest_email"
        )
        logger.info("Created index: idx_guest_email")

        # 5. Table ID - For seating queries (find guests at a specific table)
        await collection.create_index(
            [("table_id", ASCENDING)],
            name="idx_table_id"
        )
        logger.info("Created index: idx_table_id")

        # 6. Wedding + Table compound index (for seating page queries)
        await collection.create_index(
            [("wedding_id", ASCENDING), ("table_id", ASCENDING)],
            name="idx_wedding_table"
        )
        logger.info("Created index: idx_wedding_table")

        logger.info("All guest indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating guest indexes: {str(e)}")
        return False


async def create_plus_one_indexes():
    """
    Create indexes for plus_ones collection

    Key queries:
    1. Get plus ones by guest_id
    """
    collection = mongo.db["plus_ones"]
    try:
        # 1. Guest ID - Foreign key lookup
        await collection.create_index(
            [("guest_id", ASCENDING)],
            name="idx_guest_id"
        )
        logger.info("Created index: idx_guest_id")

        return True
    except Exception as e:
        logger.error(f"Error creating plus_one indexes: {str(e)}")
        return False


async def create_rsvp_indexes():
    """
    Create indexes for rsvps collection

    Key queries:
    1. Get RSVP by guest_id
    """
    collection = mongo.db["rsvps"]
    try:
        # 1. Guest ID - Foreign key lookup
        await collection.create_index(
            [("guest_id", ASCENDING)],
            name="idx_guest_id"
        )
        logger.info("Created index: idx_guest_id")

        return True
    except Exception as e:
        logger.error(f"Error creating rsvp indexes: {str(e)}")
        return False


async def create_subscription_indexes():
    """
    Create indexes for subscription-related collections
    """
    plans_collection = mongo.db["subscription_plans"]
    subs_collection = mongo.db["user_subscriptions"]
    usage_collection = mongo.db["usage_tracking"]

    try:
        # Subscription Plans
        await plans_collection.create_index(
            [("sort_order", ASCENDING)],
            name="idx_plan_sort_order"
        )
        logger.info("Created index: idx_plan_sort_order")

        # User Subscriptions
        # 1. Look up by user + status (most common)
        await subs_collection.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)],
            name="idx_user_status"
        )
        # 2. Look up by email + status (for feature gates)
        await subs_collection.create_index(
            [("user_email", ASCENDING), ("status", ASCENDING)],
            name="idx_email_status"
        )
        # 3. Look up by plan + status (for plan deletion checks)
        await subs_collection.create_index(
            [("plan_id", ASCENDING), ("status", ASCENDING)],
            name="idx_plan_status"
        )
        # 4. Status filtering (for analytics)
        await subs_collection.create_index(
            [("status", ASCENDING)],
            name="idx_status"
        )
        logger.info("Created user_subscription indexes")

        # Usage Tracking
        await usage_collection.create_index(
            [("user_id", ASCENDING), ("current_month", ASCENDING)],
            name="idx_user_month"
        )
        logger.info("Created usage_tracking indexes")

        return True
    except Exception as e:
        logger.error(f"Error creating subscription indexes: {str(e)}")
        return False


async def create_user_indexes():
    """
    Create indexes for users collection
    """
    collection = mongo.get_users_collection()
    try:
        # 1. Email - Unique lookup
        await collection.create_index(
            [("email", ASCENDING)],
            name="idx_user_email",
            unique=True
        )
        logger.info("Created index: idx_user_email")

        return True
    except Exception as e:
        logger.error(f"Error creating user indexes: {str(e)}")
        return False


async def create_reminders_sent_indexes():
    """
    Create indexes for reminders_sent collection (SMS/Email logs)

    Key queries:
    1. Get logs by wedding_id
    2. Get logs by message_sid (Twilio status callback lookup)
    3. Get logs by delivery status
    4. Get logs by provider (twilio/telnyx/resend)
    """
    collection = mongo.db["reminders_sent"]
    try:
        # 1. Wedding ID - Filter logs by wedding
        await collection.create_index(
            [("wedding_id", ASCENDING), ("sent_at", DESCENDING)],
            name="idx_wedding_sent"
        )
        logger.info("Created index: idx_wedding_sent")

        # 2. Message SID - Twilio status callback lookup (unique, sparse for legacy records)
        await collection.create_index(
            [("message_sid", ASCENDING)],
            name="idx_message_sid",
            unique=True,
            sparse=True  # Allow null for legacy records without message_sid
        )
        logger.info("Created index: idx_message_sid (unique, sparse)")

        # 3. Delivery status - Filter by status
        await collection.create_index(
            [("delivery_status", ASCENDING), ("sent_at", DESCENDING)],
            name="idx_delivery_status_sent"
        )
        logger.info("Created index: idx_delivery_status_sent")

        # 4. Provider - Filter by SMS provider
        await collection.create_index(
            [("provider", ASCENDING), ("sent_at", DESCENDING)],
            name="idx_provider_sent"
        )
        logger.info("Created index: idx_provider_sent")

        # 5. Guest ID - Lookup logs for a specific guest
        await collection.create_index(
            [("guest_id", ASCENDING), ("sent_at", DESCENDING)],
            name="idx_guest_sent"
        )
        logger.info("Created index: idx_guest_sent")

        logger.info("All reminders_sent indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating reminders_sent indexes: {str(e)}")
        return False


async def create_payment_indexes():
    """
    Create indexes for payment_requests collection

    Key queries:
    1. Look up by payment_intent_id (webhook handling)
    2. List by user_id sorted by created_at (dashboard)
    """
    collection = mongo.db["payment_requests"]
    try:
        # 1. Payment Intent ID - Unique lookup
        await collection.create_index(
            [("payment_intent_id", ASCENDING)],
            name="idx_payment_intent_id",
            unique=True
        )
        logger.info("Created index: idx_payment_intent_id")

        # 2. User ID + Created At - For list view
        await collection.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_created"
        )
        logger.info("Created index: idx_user_created")

        return True
    except Exception as e:
        logger.error(f"Error creating payment_requests indexes: {str(e)}")
        return False


async def create_stripe_customer_indexes():
    """
    Create indexes for stripe_customers collection

    Key queries:
    1. Look up by user_id (most common)
    2. Look up by stripe_customer_id (webhook handling)
    """
    collection = mongo.db["stripe_customers"]
    try:
        # 1. User ID - Unique lookup
        await collection.create_index(
            [("user_id", ASCENDING)],
            name="idx_user_id",
            unique=True
        )
        logger.info("Created index: idx_user_id")

        # 2. Stripe Customer ID - Unique lookup
        await collection.create_index(
            [("stripe_customer_id", ASCENDING)],
            name="idx_stripe_customer_id",
            unique=True,
            sparse=True
        )
        logger.info("Created index: idx_stripe_customer_id")

        return True
    except Exception as e:
        logger.error(f"Error creating stripe_customers indexes: {str(e)}")
        return False


async def create_all_indexes():
    """Create all database indexes (called on app startup)"""
    try:
        await create_support_ticket_indexes()
        await create_wedding_indexes()
        await create_table_indexes()  # Seating orchestration
        await create_guest_indexes()
        await create_plus_one_indexes()
        await create_rsvp_indexes()
        await create_subscription_indexes()
        await create_user_indexes()
        await create_reminders_sent_indexes()  # SMS delivery tracking
        await create_payment_indexes()  # Payment processing
        await create_stripe_customer_indexes()  # Stripe customers
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
        "query": {"phone": "+14054005000"},
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
