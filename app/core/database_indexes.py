"""
MongoDB Index Definitions for Support Tickets
Ensures optimal query performance for multi-tenant support system
"""

import logging

from pymongo import ASCENDING, DESCENDING, TEXT

from app.core.database import mongo

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
            [
                ("assigned_to", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_assigned_status_created",
        )
        logger.info("Created index: idx_assigned_status_created")

        # 2. Unread tickets for planners
        await collection.create_index(
            [
                ("assigned_to", ASCENDING),
                ("is_read", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_assigned_unread",
        )
        logger.info("Created index: idx_assigned_unread")

        # 3. Phone number lookup (for finding guest history)
        await collection.create_index(
            [("phone", ASCENDING), ("created_at", DESCENDING)], name="idx_phone_created"
        )
        logger.info("Created index: idx_phone_created")

        # 4. Wedding-scoped queries
        await collection.create_index(
            [
                ("wedding_id", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_wedding_status_created",
        )
        logger.info("Created index: idx_wedding_status_created")

        # 5. Guest-related tickets
        await collection.create_index(
            [("guest_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_guest_created",
        )
        logger.info("Created index: idx_guest_created")

        # 6. Source + provider filtering (SMS vs web tickets)
        await collection.create_index(
            [("source", ASCENDING), ("provider", ASCENDING)], name="idx_source_provider"
        )
        logger.info("Created index: idx_source_provider")

        # 7. SLA metrics queries (response time analysis)
        await collection.create_index(
            [("status", ASCENDING), ("first_response_time_minutes", ASCENDING)],
            name="idx_status_response_time",
        )
        logger.info("Created index: idx_status_response_time")

        # 8. Date-based queries for analytics
        await collection.create_index(
            [("created_at", DESCENDING)], name="idx_created_desc"
        )
        logger.info("Created index: idx_created_desc")

        # 9. Full-text search on message content (optional, for search feature)
        await collection.create_index(
            [("message", TEXT)], name="idx_message_text", default_language="english"
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
            sparse=True,  # Allow null slugs (for legacy data)
        )
        logger.info("Created index: idx_slug_unique (unique)")

        # 2. Planner lookup
        await collection.create_index(
            [("assigned_planner_email", ASCENDING)], name="idx_assigned_planner"
        )
        logger.info("Created index: idx_assigned_planner")

        # 3. Date-based sorting
        await collection.create_index([("date", ASCENDING)], name="idx_wedding_date")
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
            [("wedding_id", ASCENDING)], name="idx_table_wedding_id"
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
            [("wedding_id", ASCENDING)], name="idx_wedding_id"
        )
        logger.info("Created index: idx_wedding_id")

        # 2. Token - Unique lookup for guest auth
        await collection.create_index(
            [("token", ASCENDING)], name="idx_token", unique=True
        )
        logger.info("Created index: idx_token")

        # 3. Phone - Lookup for verification
        await collection.create_index([("phone", ASCENDING)], name="idx_guest_phone")
        logger.info("Created index: idx_guest_phone")

        # 4. Email - Lookup
        await collection.create_index([("email", ASCENDING)], name="idx_guest_email")
        logger.info("Created index: idx_guest_email")

        # 5. Table ID - For seating queries (find guests at a specific table)
        await collection.create_index([("table_id", ASCENDING)], name="idx_table_id")
        logger.info("Created index: idx_table_id")

        # 6. Wedding + Table compound index (for seating page queries)
        await collection.create_index(
            [("wedding_id", ASCENDING), ("table_id", ASCENDING)],
            name="idx_wedding_table",
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
        await collection.create_index([("guest_id", ASCENDING)], name="idx_guest_id")
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
        await collection.create_index([("guest_id", ASCENDING)], name="idx_guest_id")
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
            [("sort_order", ASCENDING)], name="idx_plan_sort_order"
        )
        logger.info("Created index: idx_plan_sort_order")

        # User Subscriptions
        # 1. Look up by user + status (most common)
        await subs_collection.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)], name="idx_user_status"
        )
        # 2. Look up by email + status (for feature gates)
        await subs_collection.create_index(
            [("user_email", ASCENDING), ("status", ASCENDING)], name="idx_email_status"
        )
        # 3. Look up by plan + status (for plan deletion checks)
        await subs_collection.create_index(
            [("plan_id", ASCENDING), ("status", ASCENDING)], name="idx_plan_status"
        )
        # 4. Status filtering (for analytics)
        await subs_collection.create_index([("status", ASCENDING)], name="idx_status")
        logger.info("Created user_subscription indexes")

        # Usage Tracking
        await usage_collection.create_index(
            [("user_id", ASCENDING), ("current_month", ASCENDING)],
            name="idx_user_month",
        )
        logger.info("Created usage_tracking indexes")

        # TTL: Auto-delete archived subscriptions 180 days after archival
        await subs_collection.create_index(
            [("archived_at", ASCENDING)],
            name="idx_subscription_archived_ttl",
            expireAfterSeconds=180 * 24 * 60 * 60,  # 180 days
            partialFilterExpression={"archived_at": {"$exists": True}}
        )
        logger.info("Created TTL index: idx_subscription_archived_ttl (180 days)")

        # TTL: Auto-delete abandoned checkout subscriptions after 30 days
        # Targets ONLY records expired by checkout timeout (expired_reason set at
        # stripe_service._handle_checkout_expired). These records have no
        # stripe_subscription_id, so _sync_subscription_state won't touch updated_at.
        await subs_collection.create_index(
            [("updated_at", ASCENDING)],
            name="idx_abandoned_checkout_ttl",
            expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
            partialFilterExpression={
                "status": "expired",
                "expired_reason": "checkout_session_expired"
            }
        )
        logger.info("Created TTL index: idx_abandoned_checkout_ttl (30 days)")

        # Regular index for archival job query performance
        await subs_collection.create_index(
            [("status", ASCENDING), ("cancelled_at", ASCENDING)],
            name="idx_status_cancelled_at"
        )
        logger.info("Created index: idx_status_cancelled_at")

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
            [("email", ASCENDING)], name="idx_user_email", unique=True
        )
        logger.info("Created index: idx_user_email")

        # 2. TTL: Auto-delete stale pending signups
        # Users with subscription_status=pending_payment who never complete checkout
        # are automatically removed once pending_expires_at passes (set to 48h after registration)
        await collection.create_index(
            [("pending_expires_at", ASCENDING)],
            name="idx_pending_payment_ttl",
            expireAfterSeconds=0,
            partialFilterExpression={
                "subscription_status": "pending_payment",
                "pending_expires_at": {"$exists": True}
            }
        )
        logger.info("Created TTL index: idx_pending_payment_ttl (pending signups)")

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
            name="idx_wedding_sent",
        )
        logger.info("Created index: idx_wedding_sent")

        # 2. Message SID - Twilio status callback lookup (unique, sparse for legacy records)
        await collection.create_index(
            [("message_sid", ASCENDING)],
            name="idx_message_sid",
            unique=True,
            sparse=True,  # Allow null for legacy records without message_sid
        )
        logger.info("Created index: idx_message_sid (unique, sparse)")

        # 3. Delivery status - Filter by status
        await collection.create_index(
            [("delivery_status", ASCENDING), ("sent_at", DESCENDING)],
            name="idx_delivery_status_sent",
        )
        logger.info("Created index: idx_delivery_status_sent")

        # 4. Provider - Filter by SMS provider
        await collection.create_index(
            [("provider", ASCENDING), ("sent_at", DESCENDING)], name="idx_provider_sent"
        )
        logger.info("Created index: idx_provider_sent")

        # 5. Guest ID - Lookup logs for a specific guest
        await collection.create_index(
            [("guest_id", ASCENDING), ("sent_at", DESCENDING)], name="idx_guest_sent"
        )
        logger.info("Created index: idx_guest_sent")

        logger.info("All reminders_sent indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating reminders_sent indexes: {str(e)}")
        return False


async def create_payment_indexes():
    """
    Create indexes for payment-related collections (payment_requests, stripe_customers)

    Key queries:
    1. Get payment request by payment_intent_id (unique)
    2. Get payment requests by user_id sorted by created_at
    3. Get stripe customer by user_id (unique)
    """
    payment_requests = mongo.db["payment_requests"]
    stripe_customers = mongo.db["stripe_customers"]

    try:
        # Payment Requests - Unique lookup by intent ID
        await payment_requests.create_index(
            [("payment_intent_id", ASCENDING)],
            name="idx_payment_intent_id",
            unique=True,
        )
        logger.info("Created index: idx_payment_intent_id")

        # Payment Requests - List by user (recent first)
        await payment_requests.create_index(
            [("user_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_user_payment_history",
        )
        logger.info("Created index: idx_user_payment_history")

        # Stripe Customers - Unique lookup by user ID
        await stripe_customers.create_index(
            [("user_id", ASCENDING)], name="idx_stripe_customer_user", unique=True
        )
        logger.info("Created index: idx_stripe_customer_user")

        return True
    except Exception as e:
        logger.error(f"Error creating payment indexes: {str(e)}")
        return False


async def create_admin_activity_log_indexes():
    """
    Create indexes for admin_activity_log collection (ROOT_ADMIN actions)

    Key queries:
    1. Get activities sorted by created_at (recent first)
    2. Filter by action_type
    3. Filter by entity_type
    4. Filter by admin_id

    TTL index: Automatically delete entries older than 90 days
    """
    collection = mongo.db["admin_activity_log"]
    try:
        # 1. Created at sorting (most common query)
        await collection.create_index(
            [("created_at", DESCENDING)],
            name="idx_admin_activity_created"
        )
        logger.info("Created index: idx_admin_activity_created")

        # 2. Action type filter + created_at
        await collection.create_index(
            [("action_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_action_type_created"
        )
        logger.info("Created index: idx_action_type_created")

        # 3. Entity type filter + created_at
        await collection.create_index(
            [("entity_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_entity_type_created"
        )
        logger.info("Created index: idx_entity_type_created")

        # 4. Admin ID filter + created_at
        await collection.create_index(
            [("admin_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_admin_id_created"
        )
        logger.info("Created index: idx_admin_id_created")

        # 5. TTL index - Auto-delete after 90 days
        await collection.create_index(
            [("created_at", ASCENDING)],
            name="idx_admin_activity_ttl",
            expireAfterSeconds=90 * 24 * 60 * 60  # 90 days
        )
        logger.info("Created TTL index: idx_admin_activity_ttl (90 days)")

        logger.info("All admin_activity_log indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating admin_activity_log indexes: {str(e)}")
        return False


async def create_activity_logs_indexes():
    """
    Create indexes for activity_logs collection (planner activities)

    Key queries:
    1. Get activities by planner_email
    2. Get activities by wedding_id
    3. Sort by timestamp

    TTL index: Automatically delete entries older than 90 days
    """
    collection = mongo.db["activity_logs"]
    try:
        # 1. Timestamp sorting (most common query)
        await collection.create_index(
            [("timestamp", DESCENDING)],
            name="idx_activity_timestamp"
        )
        logger.info("Created index: idx_activity_timestamp")

        # 2. Created_at fallback sorting
        await collection.create_index(
            [("created_at", DESCENDING)],
            name="idx_activity_created_at"
        )
        logger.info("Created index: idx_activity_created_at")

        # 3. Wedding ID + timestamp
        await collection.create_index(
            [("wedding_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_wedding_timestamp"
        )
        logger.info("Created index: idx_wedding_timestamp")

        # 4. Planner email + timestamp
        await collection.create_index(
            [("planner_email", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_planner_timestamp"
        )
        logger.info("Created index: idx_planner_timestamp")

        # 5. Actor email + timestamp
        await collection.create_index(
            [("actor_email", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_actor_timestamp"
        )
        logger.info("Created index: idx_actor_timestamp")

        # 6. Activity type + timestamp
        await collection.create_index(
            [("type", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_type_timestamp"
        )
        logger.info("Created index: idx_type_timestamp")

        # 7. Wedding ID + metadata.guest_id (for guest-specific activity filtering)
        await collection.create_index(
            [("wedding_id", ASCENDING), ("metadata.guest_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_wedding_guest_timestamp",
            sparse=True,
        )
        logger.info("Created index: idx_wedding_guest_timestamp")

        # 8. TTL index - Auto-delete after 90 days
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_activity_logs_ttl",
            expireAfterSeconds=90 * 24 * 60 * 60  # 90 days
        )
        logger.info("Created TTL index: idx_activity_logs_ttl (90 days)")

        logger.info("All activity_logs indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating activity_logs indexes: {str(e)}")
        return False


async def create_audit_logs_indexes():
    """
    Create indexes for audit_logs collection (HTTP request auditing)

    Key queries:
    1. Get logs by timestamp
    2. Filter by response_status (errors)
    3. Filter by path (endpoint analysis)

    TTL index: Automatically delete entries older than 30 days (high volume)
    """
    collection = mongo.db["audit_logs"]
    try:
        # 1. Timestamp sorting
        await collection.create_index(
            [("timestamp", DESCENDING)],
            name="idx_audit_timestamp"
        )
        logger.info("Created index: idx_audit_timestamp")

        # 2. Response status + timestamp (for error filtering)
        await collection.create_index(
            [("response_status", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_status_timestamp"
        )
        logger.info("Created index: idx_status_timestamp")

        # 3. Path + timestamp (for endpoint analysis)
        await collection.create_index(
            [("path", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_path_timestamp"
        )
        logger.info("Created index: idx_path_timestamp")

        # 4. TTL index - Auto-delete after 30 days (high volume collection)
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_audit_logs_ttl",
            expireAfterSeconds=30 * 24 * 60 * 60  # 30 days
        )
        logger.info("Created TTL index: idx_audit_logs_ttl (30 days)")

        logger.info("All audit_logs indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating audit_logs indexes: {str(e)}")
        return False


async def create_security_audit_logs_indexes():
    """
    Create indexes for security_audit_logs collection

    TTL index: Automatically delete entries older than 180 days (compliance)
    """
    collection = mongo.db["security_audit_logs"]
    try:
        # 1. Timestamp sorting
        await collection.create_index(
            [("timestamp", DESCENDING)],
            name="idx_security_timestamp"
        )
        logger.info("Created index: idx_security_timestamp")

        # 2. Event type + timestamp
        await collection.create_index(
            [("event_type", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_event_type_timestamp"
        )
        logger.info("Created index: idx_event_type_timestamp")

        # 3. Severity + timestamp
        await collection.create_index(
            [("severity", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_severity_timestamp"
        )
        logger.info("Created index: idx_severity_timestamp")

        # 4. TTL index - Auto-delete after 180 days (security compliance)
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_security_audit_logs_ttl",
            expireAfterSeconds=180 * 24 * 60 * 60  # 180 days
        )
        logger.info("Created TTL index: idx_security_audit_logs_ttl (180 days)")

        logger.info("All security_audit_logs indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating security_audit_logs indexes: {str(e)}")
        return False


async def create_errors_indexes():
    """
    Create indexes for errors collection

    TTL index: Automatically delete acknowledged errors after 30 days
    """
    collection = mongo.db["errors"]
    try:
        # Migration: Drop old conflicting indexes if they exist
        for old_index_name in ["idx_errors_timestamp", "idx_errors_ttl"]:
            try:
                await collection.drop_index(old_index_name)
                logger.info(f"Dropped old conflicting index: {old_index_name}")
            except Exception as e:
                logger.debug(f"Index {old_index_name} doesn't exist or couldn't be dropped: {e}")
                pass  # Index doesn't exist, that's fine

        # 1. TTL index on timestamp - also serves as the timestamp sorting index
        # Auto-delete ALL errors after 30 days
        # Note: TTL indexes must use ASCENDING direction
        # For descending sort queries, MongoDB can traverse this index in reverse
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_errors_timestamp_ttl",
            expireAfterSeconds=30 * 24 * 60 * 60  # 30 days
        )
        logger.info("Created TTL index: idx_errors_timestamp_ttl (30 days)")

        # 2. Error ID lookup
        await collection.create_index(
            [("error_id", ASCENDING)],
            name="idx_error_id",
            unique=True,
            sparse=True
        )
        logger.info("Created index: idx_error_id")

        # 3. Acknowledged status + timestamp (for cleanup queries)
        await collection.create_index(
            [("acknowledged", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_acknowledged_timestamp"
        )
        logger.info("Created index: idx_acknowledged_timestamp")

        # 4. Severity + timestamp
        await collection.create_index(
            [("severity", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_errors_severity_timestamp"
        )
        logger.info("Created index: idx_errors_severity_timestamp")

        logger.info("All errors indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating errors indexes: {str(e)}")
        return False


async def create_kb_articles_indexes():
    """
    Create indexes for kb_articles collection (Knowledge Base)

    Key queries that need optimization:
    1. List published articles by category (main listing)
    2. Search by title/content (full-text search)
    3. Get article by slug (single article view)
    4. Get user's own articles (my articles)
    5. Featured/official articles sorting
    """
    collection = mongo.db["kb_articles"]

    try:
        # 1. Unique slug index (for URL lookup)
        await collection.create_index(
            [("slug", ASCENDING)],
            name="idx_slug_unique",
            unique=True
        )
        logger.info("Created index: idx_slug_unique")

        # 2. Category + status + created_at (main listing query)
        await collection.create_index(
            [("status", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)],
            name="idx_status_category_created"
        )
        logger.info("Created index: idx_status_category_created")

        # 3. Author's articles (my articles)
        await collection.create_index(
            [("created_by", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_author_status_created"
        )
        logger.info("Created index: idx_author_status_created")

        # 4. Featured articles
        await collection.create_index(
            [("status", ASCENDING), ("featured", DESCENDING), ("created_at", DESCENDING)],
            name="idx_featured_articles"
        )
        logger.info("Created index: idx_featured_articles")

        # 5. Official platform docs
        await collection.create_index(
            [("status", ASCENDING), ("is_official", DESCENDING), ("order", ASCENDING)],
            name="idx_official_docs"
        )
        logger.info("Created index: idx_official_docs")

        # 6. Full-text search on title and content
        await collection.create_index(
            [("title", TEXT), ("content", TEXT), ("excerpt", TEXT)],
            name="idx_kb_text_search",
            default_language="english",
            weights={"title": 10, "excerpt": 5, "content": 1}
        )
        logger.info("Created index: idx_kb_text_search (full-text search)")

        # 7. View count for popular articles
        await collection.create_index(
            [("status", ASCENDING), ("view_count", DESCENDING)],
            name="idx_popular_articles"
        )
        logger.info("Created index: idx_popular_articles")

        logger.info("All KB articles indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating KB articles indexes: {str(e)}")
        return False


async def create_invitation_indexes():
    """
    Create indexes for user_invitations collection

    Key queries:
    1. Token lookup (signup flow)
    2. Email lookup (check existing invitations)
    3. TTL cleanup for expired invitations
    """
    collection = mongo.db["user_invitations"]
    try:
        # 1. Token lookup (unique, for signup flow)
        await collection.create_index(
            [("token", ASCENDING)],
            name="idx_invitation_token",
            unique=True
        )
        logger.info("Created index: idx_invitation_token")

        # 2. Email lookup (check existing invitations)
        await collection.create_index(
            [("email", ASCENDING), ("created_at", DESCENDING)],
            name="idx_invitation_email_created"
        )
        logger.info("Created index: idx_invitation_email_created")

        # 3. TTL: Auto-delete expired invitations (pending only)
        # expires_at is 7 days from creation; 7-day grace after = 14 days total
        # partialFilterExpression ensures accepted/completed invitations are preserved
        await collection.create_index(
            [("expires_at", ASCENDING)],
            name="idx_invitation_expires_ttl",
            expireAfterSeconds=7 * 24 * 60 * 60,  # 7 days grace after expires_at
            partialFilterExpression={"status": "pending"}
        )
        logger.info("Created TTL index: idx_invitation_expires_ttl (7 days grace, pending only)")

        logger.info("All invitation indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating invitation indexes: {e}")
        return False


async def create_team_member_indexes():
    """
    Create indexes for team_members collection

    Key queries:
    1. List team members by owner (planner's team page)
    2. Fast invite token lookup (accept flow)
    3. User ID lookup (auth middleware — resolve team permissions)
    4. Prevent duplicate invites per planner
    5. Auth hydration: user_id + status for get_member_permissions
    """
    collection = mongo.db["team_members"]
    try:
        # 1. Unique constraint: one invite per email per planner
        await collection.create_index(
            [("owner_id", ASCENDING), ("email", ASCENDING)],
            name="idx_owner_email_unique",
            unique=True,
        )
        logger.info("Created index: idx_owner_email_unique")

        # 2. Invite token lookup (public accept endpoint)
        await collection.create_index(
            [("invite_token", ASCENDING)],
            name="idx_invite_token",
            unique=True,
            sparse=True,  # Allow null after token is consumed
        )
        logger.info("Created index: idx_invite_token")

        # 3. User ID lookup (auth middleware loads team data on every request)
        await collection.create_index(
            [("user_id", ASCENDING)],
            name="idx_team_member_user_id",
            sparse=True,  # Only populated once invite is accepted
        )
        logger.info("Created index: idx_team_member_user_id")

        # 4. Owner listing sorted by status + created (team management page)
        await collection.create_index(
            [("owner_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_owner_status_created",
        )
        logger.info("Created index: idx_owner_status_created")

        # 5. Compound index for auth hydration query pattern (user_id + status)
        await collection.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)],
            name="idx_user_id_status",
            sparse=True
        )
        logger.info("Created index: idx_user_id_status")

        # 6. Parent planner lookup on users collection (for team queries)
        users_collection = mongo.get_users_collection()
        await users_collection.create_index(
            [("parent_planner_id", ASCENDING)],
            name="idx_parent_planner_id",
            sparse=True,  # Only team_member users have this field
        )
        logger.info("Created index: idx_parent_planner_id (users collection)")

        logger.info("All team_member indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating team_member indexes: {str(e)}")
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
        await create_payment_indexes()
        await create_admin_activity_log_indexes() # Activity/Audit logging indexes with TTL for auto-pruning
        await create_activity_logs_indexes()
        await create_audit_logs_indexes()
        await create_security_audit_logs_indexes()
        await create_errors_indexes()
        await create_kb_articles_indexes()  # Knowledge Base articles
        await create_invitation_indexes()  # User invitation cleanup
        await create_team_member_indexes()  # Team management
        logger.info("All database indexes created/verified")
    except Exception as e:
        logger.error(f"Error creating database indexes: {str(e)}")


# Index usage examples and query patterns
QUERY_PATTERNS = {
    "planner_new_tickets": {
        "description": "Get new tickets for a specific planner",
        "query": {"assigned_to": "planner@example.com", "status": "new"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_assigned_status_created",
    },
    "planner_unread": {
        "description": "Get unread tickets for planner",
        "query": {"assigned_to": "planner@example.com", "is_read": False},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_assigned_unread",
    },
    "guest_history": {
        "description": "Get all tickets from a specific phone number",
        "query": {"phone": "+14054005000"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_phone_created",
    },
    "wedding_tickets": {
        "description": "Get all tickets for a wedding",
        "query": {"wedding_id": "abc123", "status": "new"},
        "sort": [("created_at", DESCENDING)],
        "uses_index": "idx_wedding_status_created",
    },
    "sla_analysis": {
        "description": "Analyze average response times for resolved tickets",
        "query": {
            "status": "resolved",
            "first_response_time_minutes": {"$exists": True},
        },
        "uses_index": "idx_status_response_time",
    },
}
