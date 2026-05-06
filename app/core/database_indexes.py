"""
MongoDB Index Definitions for Support Tickets
Ensures optimal query performance for multi-tenant support system
"""

import logging

from pymongo import ASCENDING, DESCENDING, TEXT

from app.core.database import mongo

logger = logging.getLogger(__name__)


async def _deduplicate_meeting_invites(collection) -> None:
    """Collapse legacy duplicate invite rows before enforcing uniqueness."""
    duplicate_groups = collection.aggregate(
        [
            {
                "$sort": {
                    "updated_at": DESCENDING,
                    "created_at": DESCENDING,
                    "_id": DESCENDING,
                }
            },
            {
                "$group": {
                    "_id": {
                        "task_id": "$task_id",
                        "recipient_email": "$recipient_email",
                    },
                    "ids": {"$push": "$_id"},
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]
    )

    removed_count = 0
    async for group in duplicate_groups:
        duplicate_ids = group.get("ids", [])[1:]
        if not duplicate_ids:
            continue
        await collection.delete_many({"_id": {"$in": duplicate_ids}})
        removed_count += len(duplicate_ids)

    if removed_count:
        logger.warning(
            "Removed %s duplicate meeting_invites rows before enforcing unique task/recipient constraint",
            removed_count,
        )


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

        await collection.create_index(
            [("assigned_planner_id", ASCENDING)],
            name="idx_assigned_planner_id",
            sparse=True,
        )
        logger.info("Created index: idx_assigned_planner_id")

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

        # 7. Wedding + name for guest list sorting and targeted planner lookups
        await collection.create_index(
            [("wedding_id", ASCENDING), ("name", ASCENDING)],
            name="idx_wedding_name",
        )
        logger.info("Created index: idx_wedding_name")

        # 8. Wedding + group_id for planner guest filters
        await collection.create_index(
            [("wedding_id", ASCENDING), ("group_id", ASCENDING)],
            name="idx_wedding_group",
        )
        logger.info("Created index: idx_wedding_group")

        # 9. Wedding + role for planner guest filters
        await collection.create_index(
            [("wedding_id", ASCENDING), ("role", ASCENDING)],
            name="idx_wedding_role",
        )
        logger.info("Created index: idx_wedding_role")

        # 10. Wedding + invite status for planner RSVP workflow filters
        await collection.create_index(
            [("wedding_id", ASCENDING), ("invite_sent", ASCENDING)],
            name="idx_wedding_invite_sent",
        )
        logger.info("Created index: idx_wedding_invite_sent")

        # 11. Wedding + phone status for reminders/remediation views
        await collection.create_index(
            [("wedding_id", ASCENDING), ("phone_status", ASCENDING)],
            name="idx_wedding_phone_status",
        )
        logger.info("Created index: idx_wedding_phone_status")

        # 12. Wedding + sms opt-in for delivery remediation views
        await collection.create_index(
            [("wedding_id", ASCENDING), ("sms_opt_in", ASCENDING)],
            name="idx_wedding_sms_opt_in",
        )
        logger.info("Created index: idx_wedding_sms_opt_in")

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

        # 2. Wedding-scoped dashboard aggregations
        await collection.create_index(
            [("wedding_id", ASCENDING)], name="idx_rsvp_wedding_id"
        )
        logger.info("Created index: idx_rsvp_wedding_id")

        # 3. Wedding + guest lookups for response parity checks
        await collection.create_index(
            [("wedding_id", ASCENDING), ("guest_id", ASCENDING)],
            name="idx_rsvp_wedding_guest",
        )
        logger.info("Created index: idx_rsvp_wedding_guest")

        return True
    except Exception as e:
        logger.error(f"Error creating rsvp indexes: {str(e)}")
        return False


async def create_form_indexes():
    """
    Create indexes for form dashboard and engagement signal queries.
    """
    forms_collection = mongo.get_forms_collection()
    responses_collection = mongo.get_form_responses_collection()

    try:
        await forms_collection.create_index(
            [("wedding_id", ASCENDING), ("is_active", ASCENDING)],
            name="idx_forms_wedding_active",
        )
        logger.info("Created index: idx_forms_wedding_active")

        await forms_collection.create_index(
            [("created_by", ASCENDING), ("created_at", DESCENDING)],
            name="idx_forms_created_by_created",
        )
        logger.info("Created index: idx_forms_created_by_created")

        await responses_collection.create_index(
            [("wedding_id", ASCENDING), ("submitted_at", DESCENDING)],
            name="idx_form_responses_wedding_submitted",
        )
        logger.info("Created index: idx_form_responses_wedding_submitted")

        await responses_collection.create_index(
            [("form_id", ASCENDING), ("submitted_at", DESCENDING)],
            name="idx_form_responses_form_submitted",
        )
        logger.info("Created index: idx_form_responses_form_submitted")

        return True
    except Exception as e:
        logger.error(f"Error creating form indexes: {str(e)}")
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
            partialFilterExpression={"archived_at": {"$exists": True}},
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
                "expired_reason": "checkout_session_expired",
            },
        )
        logger.info("Created TTL index: idx_abandoned_checkout_ttl (30 days)")

        # Regular index for archival job query performance
        await subs_collection.create_index(
            [("status", ASCENDING), ("cancelled_at", ASCENDING)],
            name="idx_status_cancelled_at",
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
                "pending_expires_at": {"$exists": True},
            },
        )
        logger.info("Created TTL index: idx_pending_payment_ttl (pending signups)")

        # 3. Advertising vendor status queries (Phase 10 - admin vendor list)
        await collection.create_index(
            [("role", ASCENDING), ("vendor_account_status", ASCENDING)],
            name="idx_user_role_vendor_status",
            partialFilterExpression={"role": "advertising_vendor"},
        )
        logger.info("Created index: idx_user_role_vendor_status (vendor admin queries)")

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
    1. Get payment request by public_token (unique)
    2. Get payment request by payment_intent_id (unique)
    3. Get payment requests by user_id sorted by created_at
    4. Get stripe customer by user_id (unique)
    """
    payment_requests = mongo.db["payment_requests"]
    stripe_customers = mongo.db["stripe_customers"]

    try:
        # Payment Requests - Unique lookup by app-owned public token
        await payment_requests.create_index(
            [("public_token", ASCENDING)],
            name="idx_payment_public_token",
            unique=True,
            sparse=True,
        )
        logger.info("Created index: idx_payment_public_token")

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
            [("created_at", DESCENDING)], name="idx_admin_activity_created"
        )
        logger.info("Created index: idx_admin_activity_created")

        # 2. Action type filter + created_at
        await collection.create_index(
            [("action_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_action_type_created",
        )
        logger.info("Created index: idx_action_type_created")

        # 3. Entity type filter + created_at
        await collection.create_index(
            [("entity_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_entity_type_created",
        )
        logger.info("Created index: idx_entity_type_created")

        # 4. Admin ID filter + created_at
        await collection.create_index(
            [("admin_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_admin_id_created",
        )
        logger.info("Created index: idx_admin_id_created")

        # 5. TTL index - Auto-delete after 90 days
        await collection.create_index(
            [("created_at", ASCENDING)],
            name="idx_admin_activity_ttl",
            expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
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
            [("timestamp", DESCENDING)], name="idx_activity_timestamp"
        )
        logger.info("Created index: idx_activity_timestamp")

        # 2. Created_at fallback sorting
        await collection.create_index(
            [("created_at", DESCENDING)], name="idx_activity_created_at"
        )
        logger.info("Created index: idx_activity_created_at")

        # 3. Wedding ID + timestamp
        await collection.create_index(
            [("wedding_id", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_wedding_timestamp",
        )
        logger.info("Created index: idx_wedding_timestamp")

        # 4. Planner email + timestamp
        await collection.create_index(
            [("planner_email", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_planner_timestamp",
        )
        logger.info("Created index: idx_planner_timestamp")

        # 5. Actor email + timestamp
        await collection.create_index(
            [("actor_email", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_actor_timestamp",
        )
        logger.info("Created index: idx_actor_timestamp")

        # 6. Activity type + timestamp
        await collection.create_index(
            [("type", ASCENDING), ("timestamp", DESCENDING)], name="idx_type_timestamp"
        )
        logger.info("Created index: idx_type_timestamp")

        # 7. Wedding ID + metadata.guest_id (for guest-specific activity filtering)
        await collection.create_index(
            [
                ("wedding_id", ASCENDING),
                ("metadata.guest_id", ASCENDING),
                ("timestamp", DESCENDING),
            ],
            name="idx_wedding_guest_timestamp",
            sparse=True,
        )
        logger.info("Created index: idx_wedding_guest_timestamp")

        # 8. Wedding + activity type for dashboard activity filters
        await collection.create_index(
            [
                ("wedding_id", ASCENDING),
                ("type", ASCENDING),
                ("timestamp", DESCENDING),
            ],
            name="idx_wedding_type_timestamp",
        )
        logger.info("Created index: idx_wedding_type_timestamp")

        # 9. TTL index - Auto-delete after 90 days
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_activity_logs_ttl",
            expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
        )
        logger.info("Created TTL index: idx_activity_logs_ttl (90 days)")

        logger.info("All activity_logs indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating activity_logs indexes: {str(e)}")
        return False


async def create_vendor_contract_activity_indexes():
    """
    Create indexes for vendor_contract_activities collection.

    Key queries:
    1. Contract detail timeline by contract_id
    2. Future lineage-wide activity by root_contract_id
    3. Optional filtering by activity_type
    """
    collection = mongo.db["vendor_contract_activities"]
    try:
        await collection.create_index(
            [("contract_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_vendor_contract_activity_contract_created",
        )
        logger.info("Created index: idx_vendor_contract_activity_contract_created")

        await collection.create_index(
            [("root_contract_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_vendor_contract_activity_root_created",
        )
        logger.info("Created index: idx_vendor_contract_activity_root_created")

        await collection.create_index(
            [("activity_type", ASCENDING), ("created_at", DESCENDING)],
            name="idx_vendor_contract_activity_type_created",
        )
        logger.info("Created index: idx_vendor_contract_activity_type_created")

        logger.info("All vendor_contract_activities indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating vendor_contract_activities indexes: {str(e)}")
        return False


async def create_vendor_contract_security_indexes():
    """
    Create vendor contract indexes for the hard invariants this module relies on:
    - unique token hashes for public access
    - unique version numbers inside one lineage
    - exactly one current version per lineage
    - fast planner and milestone queries for contract operations
    """
    contracts = mongo.db["vendor_contracts"]
    milestones = mongo.db["vendor_payment_milestones"]

    try:
        await contracts.create_index(
            [("access_token_hash", ASCENDING)],
            name="idx_vendor_contract_access_token_hash",
            unique=True,
            sparse=True,
        )
        logger.info("Created index: idx_vendor_contract_access_token_hash")

        await contracts.create_index(
            [("root_contract_id", ASCENDING), ("version_number", ASCENDING)],
            name="idx_vendor_contract_root_version_unique",
            unique=True,
        )
        logger.info("Created index: idx_vendor_contract_root_version_unique")

        await contracts.create_index(
            [("root_contract_id", ASCENDING)],
            name="idx_vendor_contract_single_current_version",
            unique=True,
            partialFilterExpression={"is_current_version": True},
        )
        logger.info("Created index: idx_vendor_contract_single_current_version")

        await contracts.create_index(
            [
                ("created_by", ASCENDING),
                ("is_current_version", ASCENDING),
                ("status", ASCENDING),
                ("updated_at", DESCENDING),
            ],
            name="idx_vendor_contract_planner_current_status_updated",
        )
        logger.info("Created index: idx_vendor_contract_planner_current_status_updated")

        await contracts.create_index(
            [("wedding_id", ASCENDING), ("vendor_profile_id", ASCENDING)],
            name="idx_vendor_contract_wedding_vendor",
        )
        logger.info("Created index: idx_vendor_contract_wedding_vendor")

        # Compound index supporting the wedding-detail Vendors tab and
        # contract-list filtering by wedding + current-version + status.
        # Background creation; partial filter not needed because the live
        # contract reads already constrain on is_soft_deleted: {$ne: True}
        # at query time.
        await contracts.create_index(
            [
                ("wedding_id", ASCENDING),
                ("is_current_version", ASCENDING),
                ("status", ASCENDING),
            ],
            name="idx_vendor_contract_wedding_current_status",
            background=True,
        )
        logger.info("Created index: idx_vendor_contract_wedding_current_status")

        await milestones.create_index(
            [
                ("contract_id", ASCENDING),
                ("status", ASCENDING),
                ("due_date", ASCENDING),
            ],
            name="idx_vendor_payment_milestones_contract_status_due",
        )
        logger.info("Created index: idx_vendor_payment_milestones_contract_status_due")

        await milestones.create_index(
            [("created_by", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)],
            name="idx_vendor_payment_milestones_created_by_status_due",
        )
        logger.info(
            "Created index: idx_vendor_payment_milestones_created_by_status_due"
        )

        logger.info("All vendor contract security indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating vendor contract security indexes: {str(e)}")
        return False


async def create_vendor_assignment_indexes():
    """
    Create indexes for vendor_assignments collection.

    Soft-deleted assignments coexist with fresh assignments for the same
    vendor on the same wedding via a partial unique index that excludes
    rows where ``is_deleted`` is True. The wedding-detail Vendors tab
    queries are served by a compound (wedding_id, status, is_deleted)
    index.
    """
    assignments = mongo.db["vendor_assignments"]
    try:
        # Partial unique index: enforce one live assignment per
        # (wedding, vendor) pair while still allowing soft-deleted rows
        # of the same pair to remain in the collection. Reads filter
        # ``is_deleted: {$ne: True}`` at query time, and the partial
        # filter expression here limits uniqueness to the same set.
        await assignments.create_index(
            [("wedding_id", ASCENDING), ("vendor_profile_id", ASCENDING)],
            name="idx_vendor_assignment_wedding_vendor_unique",
            unique=True,
            partialFilterExpression={"is_deleted": False},
            background=True,
        )
        logger.info("Created index: idx_vendor_assignment_wedding_vendor_unique")

        # Compound index supporting the wedding-detail Vendors tab.
        await assignments.create_index(
            [
                ("wedding_id", ASCENDING),
                ("status", ASCENDING),
                ("is_deleted", ASCENDING),
            ],
            name="idx_vendor_assignment_wedding_status_deleted",
            background=True,
        )
        logger.info("Created index: idx_vendor_assignment_wedding_status_deleted")

        logger.info("All vendor_assignments indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating vendor_assignments indexes: {str(e)}")
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
            [("timestamp", DESCENDING)], name="idx_audit_timestamp"
        )
        logger.info("Created index: idx_audit_timestamp")

        # 2. Response status + timestamp (for error filtering)
        await collection.create_index(
            [("response_status", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_status_timestamp",
        )
        logger.info("Created index: idx_status_timestamp")

        # 3. Path + timestamp (for endpoint analysis)
        await collection.create_index(
            [("path", ASCENDING), ("timestamp", DESCENDING)], name="idx_path_timestamp"
        )
        logger.info("Created index: idx_path_timestamp")

        # 4. Normalized route template + timestamp (aggregates /admin/weddings/{id})
        await collection.create_index(
            [("route_template", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_route_template_timestamp",
        )
        logger.info("Created index: idx_route_template_timestamp")

        # 5. TTL index - Auto-delete after 30 days (high volume collection)
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_audit_logs_ttl",
            expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
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
            [("timestamp", DESCENDING)], name="idx_security_timestamp"
        )
        logger.info("Created index: idx_security_timestamp")

        # 2. Event type + timestamp
        await collection.create_index(
            [("event_type", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_event_type_timestamp",
        )
        logger.info("Created index: idx_event_type_timestamp")

        # 3. Severity + timestamp
        await collection.create_index(
            [("severity", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_severity_timestamp",
        )
        logger.info("Created index: idx_severity_timestamp")

        # 4. TTL index - Auto-delete after 180 days (security compliance)
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_security_audit_logs_ttl",
            expireAfterSeconds=180 * 24 * 60 * 60,  # 180 days
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
                logger.debug(
                    f"Index {old_index_name} doesn't exist or couldn't be dropped: {e}"
                )
                pass  # Index doesn't exist, that's fine

        # 1. TTL index on timestamp - also serves as the timestamp sorting index
        # Auto-delete ALL errors after 30 days
        # Note: TTL indexes must use ASCENDING direction
        # For descending sort queries, MongoDB can traverse this index in reverse
        await collection.create_index(
            [("timestamp", ASCENDING)],
            name="idx_errors_timestamp_ttl",
            expireAfterSeconds=30 * 24 * 60 * 60,  # 30 days
        )
        logger.info("Created TTL index: idx_errors_timestamp_ttl (30 days)")

        # 2. Error ID lookup
        await collection.create_index(
            [("error_id", ASCENDING)], name="idx_error_id", unique=True, sparse=True
        )
        logger.info("Created index: idx_error_id")

        # 3. Acknowledged status + timestamp (for cleanup queries)
        await collection.create_index(
            [("acknowledged", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_acknowledged_timestamp",
        )
        logger.info("Created index: idx_acknowledged_timestamp")

        # 4. Severity + timestamp
        await collection.create_index(
            [("severity", ASCENDING), ("timestamp", DESCENDING)],
            name="idx_errors_severity_timestamp",
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
            [("slug", ASCENDING)], name="idx_slug_unique", unique=True
        )
        logger.info("Created index: idx_slug_unique")

        # 2. Category + status + created_at (main listing query)
        await collection.create_index(
            [
                ("status", ASCENDING),
                ("category", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_status_category_created",
        )
        logger.info("Created index: idx_status_category_created")

        # 3. Author's articles (my articles)
        await collection.create_index(
            [
                ("created_by", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_author_status_created",
        )
        logger.info("Created index: idx_author_status_created")

        # 4. Featured articles
        await collection.create_index(
            [
                ("status", ASCENDING),
                ("featured", DESCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_featured_articles",
        )
        logger.info("Created index: idx_featured_articles")

        # 5. Official platform docs
        await collection.create_index(
            [("status", ASCENDING), ("is_official", DESCENDING), ("order", ASCENDING)],
            name="idx_official_docs",
        )
        logger.info("Created index: idx_official_docs")

        # 6. Full-text search on title and content
        await collection.create_index(
            [("title", TEXT), ("content", TEXT), ("excerpt", TEXT)],
            name="idx_kb_text_search",
            default_language="english",
            weights={"title": 10, "excerpt": 5, "content": 1},
        )
        logger.info("Created index: idx_kb_text_search (full-text search)")

        # 7. View count for popular articles
        await collection.create_index(
            [("status", ASCENDING), ("view_count", DESCENDING)],
            name="idx_popular_articles",
        )
        logger.info("Created index: idx_popular_articles")

        logger.info("All KB articles indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating KB articles indexes: {str(e)}")
        return False


async def create_blog_articles_indexes():
    """
    Create indexes for blog_articles collection

    Key queries that need optimization:
    1. Get article by slug (single article view) - UNIQUE
    2. List published articles by category (main listing)
    3. Featured articles sorting
    4. Full-text search on title, excerpt, and content
    5. View count for popular articles
    """
    collection = mongo.db["blog_articles"]

    try:
        # 1. Unique slug index (for URL lookup)
        await collection.create_index(
            [("slug", ASCENDING)], name="idx_blog_slug_unique", unique=True
        )
        logger.info("Created index: idx_blog_slug_unique")

        # 2. Status + category + created_at (main listing query)
        await collection.create_index(
            [
                ("status", ASCENDING),
                ("category", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_blog_status_category_created",
        )
        logger.info("Created index: idx_blog_status_category_created")

        # 3. Featured articles
        await collection.create_index(
            [
                ("status", ASCENDING),
                ("featured", DESCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_blog_featured_articles",
        )
        logger.info("Created index: idx_blog_featured_articles")

        # 4. Full-text search on title, excerpt, and content
        await collection.create_index(
            [("title", TEXT), ("content", TEXT), ("excerpt", TEXT)],
            name="idx_blog_text_search",
            default_language="english",
            weights={"title": 10, "excerpt": 5, "content": 1},
        )
        logger.info("Created index: idx_blog_text_search (full-text search)")

        # 5. View count for popular articles
        await collection.create_index(
            [("status", ASCENDING), ("view_count", DESCENDING)],
            name="idx_blog_popular_articles",
        )
        logger.info("Created index: idx_blog_popular_articles")

        # 6. Published date sorting (public listing)
        await collection.create_index(
            [("status", ASCENDING), ("published_at", DESCENDING)],
            name="idx_blog_published_at",
        )
        logger.info("Created index: idx_blog_published_at")

        logger.info("All blog articles indexes created successfully")
        return True

    except Exception as e:
        logger.error(f"Error creating blog articles indexes: {str(e)}")
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
            [("token", ASCENDING)], name="idx_invitation_token", unique=True
        )
        logger.info("Created index: idx_invitation_token")

        # 2. Email lookup (check existing invitations)
        await collection.create_index(
            [("email", ASCENDING), ("created_at", DESCENDING)],
            name="idx_invitation_email_created",
        )
        logger.info("Created index: idx_invitation_email_created")

        # 3. TTL: Auto-delete expired invitations (pending only)
        # expires_at is 7 days from creation; 7-day grace after = 14 days total
        # partialFilterExpression ensures accepted/completed invitations are preserved
        await collection.create_index(
            [("expires_at", ASCENDING)],
            name="idx_invitation_expires_ttl",
            expireAfterSeconds=7 * 24 * 60 * 60,  # 7 days grace after expires_at
            partialFilterExpression={"status": "pending"},
        )
        logger.info(
            "Created TTL index: idx_invitation_expires_ttl (7 days grace, pending only)"
        )

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
            [
                ("owner_id", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_owner_status_created",
        )
        logger.info("Created index: idx_owner_status_created")

        # 5. Compound index for auth hydration query pattern (user_id + status)
        await collection.create_index(
            [("user_id", ASCENDING), ("status", ASCENDING)],
            name="idx_user_id_status",
            sparse=True,
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


async def create_advertising_indexes():
    """
    Create indexes for all advertising collections.

    Collections indexed:
    - sponsored_vendors: Ad serving queries (placement + priority sort)
    - ad_events: Analytics queries (vendor stats, type counts, placement analysis)
    - ad_leads: Lead funnel queries (status, vendor, planner, type)
    - ad_feature_flags: Singleton lookup by feature_key
    - planner_ad_preferences: Unique planner lookup
    - ad_stats_daily: Pre-aggregated rollup queries (date, vendor, placement)

    Total: 18 indexes across 6 collections
    """

    # =========================================================================
    # sponsored_vendors — 3 indexes (ad-serving hot path)
    # =========================================================================
    sponsored = mongo.db["sponsored_vendors"]
    try:
        # 1. Primary ad-serving query: active vendors for a placement, sorted by priority
        # Powers: get_sponsored_vendors(), get_sponsored_vendors_filtered()
        await sponsored.create_index(
            [
                ("is_active", ASCENDING),
                ("placement", ASCENDING),
                ("priority", DESCENDING),
            ],
            name="idx_sponsored_active_placement_priority",
        )
        logger.info("Created index: idx_sponsored_active_placement_priority")

        # 2. Vendor profile lookup (for vendor performance dashboard)
        await sponsored.create_index(
            [
                ("vendor_profile_id", ASCENDING),
                ("is_active", ASCENDING),
            ],
            name="idx_sponsored_vendor_profile",
        )
        logger.info("Created index: idx_sponsored_vendor_profile")

        # 3. Admin listing by creation date (recent first)
        await sponsored.create_index(
            [("created_at", DESCENDING)],
            name="idx_sponsored_created_desc",
        )
        logger.info("Created index: idx_sponsored_created_desc")

        # 4. Review queue queries: filter by review_status, sort by created_at
        # Powers: get_review_queue(), get_review_queue_counts()
        await sponsored.create_index(
            [("review_status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_sponsored_review_status_created",
        )
        logger.info("Created index: idx_sponsored_review_status_created")

        logger.info("All sponsored_vendors indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating sponsored_vendors indexes: {str(e)}")

    # =========================================================================
    # ad_events — 5 indexes (highest volume collection)
    # =========================================================================
    ad_events = mongo.db["ad_events"]
    try:
        # 1. Vendor stats query: count events for a vendor within date range
        # Powers: get_ad_stats() — the #1 most frequent analytics query
        await ad_events.create_index(
            [
                ("sponsored_vendor_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_vendor_date",
        )
        logger.info("Created index: idx_ad_events_vendor_date")

        # 2. Event type + date: dashboard overview (impression trend, click trend)
        await ad_events.create_index(
            [
                ("event_type", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_type_date",
        )
        logger.info("Created index: idx_ad_events_type_date")

        # 3. Three-field compound: per-vendor breakdown by event type over time
        # Powers: Vendor Performance tab — impressions vs clicks vs leads per vendor
        await ad_events.create_index(
            [
                ("sponsored_vendor_id", ASCENDING),
                ("event_type", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_vendor_type_date",
        )
        logger.info("Created index: idx_ad_events_vendor_type_date")

        # 4. Placement + date: compare performance across placements
        await ad_events.create_index(
            [
                ("placement", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_placement_date",
        )
        logger.info("Created index: idx_ad_events_placement_date")

        # 5. TTL index: auto-prune raw events after 90 days
        # Aggregated data preserved in ad_stats_daily indefinitely
        await ad_events.create_index(
            [("created_at", ASCENDING)],
            name="idx_ad_events_ttl",
            expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
        )
        logger.info("Created TTL index: idx_ad_events_ttl (90 days)")

        logger.info("All ad_events indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating ad_events indexes: {str(e)}")

    # =========================================================================
    # ad_leads — 4 indexes (lead funnel + vendor performance)
    # =========================================================================
    ad_leads = mongo.db["ad_leads"]
    try:
        # 1. Lead funnel: count leads by status within date range
        await ad_leads.create_index(
            [
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_leads_status_date",
        )
        logger.info("Created index: idx_ad_leads_status_date")

        # 2. Vendor-specific lead list (sorted by most recent)
        await ad_leads.create_index(
            [
                ("vendor_profile_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_leads_vendor_date",
        )
        logger.info("Created index: idx_ad_leads_vendor_date")

        # 3. Three-field compound: leads by type and status over time
        # Powers: Lead funnel stacked bar chart in dashboard
        await ad_leads.create_index(
            [
                ("lead_type", ASCENDING),
                ("status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_leads_type_status_date",
        )
        logger.info("Created index: idx_ad_leads_type_status_date")

        # 4. Per-planner lead history
        await ad_leads.create_index(
            [
                ("planner_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_leads_planner_date",
        )
        logger.info("Created index: idx_ad_leads_planner_date")

        logger.info("All ad_leads indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating ad_leads indexes: {str(e)}")

    # =========================================================================
    # planner_ad_preferences — 1 unique index
    # =========================================================================
    planner_prefs = mongo.db["planner_ad_preferences"]
    try:
        # Unique planner lookup — one preference doc per planner
        # Powers: get_planner_preferences(), hide_vendor(), unhide_vendor(), etc.
        await planner_prefs.create_index(
            [("planner_id", ASCENDING)],
            name="idx_planner_prefs_planner_id",
            unique=True,
        )
        logger.info("Created index: idx_planner_prefs_planner_id (unique)")
    except Exception as e:
        logger.error(f"Error creating planner_ad_preferences indexes: {str(e)}")

    # =========================================================================
    # ad_feature_flags — 1 unique index (singleton collection)
    # =========================================================================
    feature_flags = mongo.db["ad_feature_flags"]
    try:
        # Unique feature key lookup — prevents duplicate flags
        await feature_flags.create_index(
            [("feature_key", ASCENDING)],
            name="idx_feature_flags_key",
            unique=True,
        )
        logger.info("Created index: idx_feature_flags_key (unique)")
    except Exception as e:
        logger.error(f"Error creating ad_feature_flags indexes: {str(e)}")

    # =========================================================================
    # ad_stats_daily — 4 indexes (pre-aggregated rollup queries)
    # =========================================================================
    stats_daily = mongo.db["ad_stats_daily"]
    try:
        # 1. Unique compound: one rollup per vendor per placement per day
        # Enables upsert-based rollup computation ($merge with "on" clause)
        await stats_daily.create_index(
            [
                ("date", ASCENDING),
                ("sponsored_vendor_id", ASCENDING),
                ("placement", ASCENDING),
            ],
            name="idx_stats_daily_unique",
            unique=True,
        )
        logger.info("Created index: idx_stats_daily_unique (unique compound)")

        # 2. Vendor-specific stats sorted by date (Vendor Performance tab)
        await stats_daily.create_index(
            [
                ("sponsored_vendor_id", ASCENDING),
                ("date", DESCENDING),
            ],
            name="idx_stats_daily_vendor_date",
        )
        logger.info("Created index: idx_stats_daily_vendor_date")

        # 3. Date-descending scan for overview tab (all vendors in date range)
        await stats_daily.create_index(
            [("date", DESCENDING)],
            name="idx_stats_daily_date_desc",
        )
        logger.info("Created index: idx_stats_daily_date_desc")

        # 4. Placement + date for placement comparison analytics
        await stats_daily.create_index(
            [
                ("placement", ASCENDING),
                ("date", DESCENDING),
            ],
            name="idx_stats_daily_placement_date",
        )
        logger.info("Created index: idx_stats_daily_placement_date")

        logger.info("All ad_stats_daily indexes created successfully")
    except Exception as e:
        logger.error(f"Error creating ad_stats_daily indexes: {str(e)}")

    logger.info("All advertising indexes created/verified (19 total)")
    return True


async def create_campaign_platform_indexes():
    """
    Create indexes for the independent vendor advertising campaign platform.

    Collections: ad_campaigns, ad_creatives, campaign_day_stats,
    placement_day_stats, ad_fraud_signals, vendor_ad_billing.
    Also adds campaign_id indexes on existing ad_events and ad_leads.

    PRD Sections 6-8. Vendor images in separate R2 bucket (S3_AD_BUCKET_NAME).
    """

    # =========================================================================
    # ad_campaigns — 6 indexes
    # =========================================================================
    campaigns = mongo.db["ad_campaigns"]
    try:
        await campaigns.create_index(
            [("vendor_id", ASCENDING), ("status", ASCENDING)],
            name="idx_campaigns_vendor_status",
        )
        await campaigns.create_index(
            [("status", ASCENDING), ("submitted_at", DESCENDING)],
            name="idx_campaigns_status_submitted",
        )
        await campaigns.create_index(
            [
                ("status", ASCENDING),
                ("target_categories", ASCENDING),
                ("start_date", ASCENDING),
                ("end_date", ASCENDING),
            ],
            name="idx_campaigns_serving_eligibility",
        )
        await campaigns.create_index(
            [("status", ASCENDING), ("quality_score", DESCENDING)],
            name="idx_campaigns_active_quality",
        )
        await campaigns.create_index(
            [("created_at", DESCENDING)],
            name="idx_campaigns_created_desc",
        )
        await campaigns.create_index(
            [("vendor_email", ASCENDING)],
            name="idx_campaigns_vendor_email",
        )
        logger.info("All ad_campaigns indexes created (6)")
    except Exception as e:
        logger.error(f"Error creating ad_campaigns indexes: {str(e)}")

    # =========================================================================
    # ad_creatives — 3 indexes
    # =========================================================================
    creatives = mongo.db["ad_creatives"]
    try:
        await creatives.create_index(
            [("campaign_id", ASCENDING), ("review_status", ASCENDING)],
            name="idx_creatives_campaign_review",
        )
        await creatives.create_index(
            [("review_status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_creatives_review_queue",
        )
        await creatives.create_index(
            [("vendor_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_creatives_vendor_date",
        )
        logger.info("All ad_creatives indexes created (3)")
    except Exception as e:
        logger.error(f"Error creating ad_creatives indexes: {str(e)}")

    # =========================================================================
    # campaign_day_stats — 3 indexes
    # =========================================================================
    campaign_stats = mongo.db["campaign_day_stats"]
    try:
        await campaign_stats.create_index(
            [("date", ASCENDING), ("campaign_id", ASCENDING)],
            name="idx_campaign_stats_unique",
            unique=True,
        )
        await campaign_stats.create_index(
            [("campaign_id", ASCENDING), ("date", DESCENDING)],
            name="idx_campaign_stats_campaign_date",
        )
        await campaign_stats.create_index(
            [("vendor_id", ASCENDING), ("date", DESCENDING)],
            name="idx_campaign_stats_vendor_date",
        )
        logger.info("All campaign_day_stats indexes created (3)")
    except Exception as e:
        logger.error(f"Error creating campaign_day_stats indexes: {str(e)}")

    # =========================================================================
    # placement_day_stats — 2 indexes
    # =========================================================================
    placement_stats = mongo.db["placement_day_stats"]
    try:
        await placement_stats.create_index(
            [("date", ASCENDING), ("placement", ASCENDING)],
            name="idx_placement_stats_unique",
            unique=True,
        )
        await placement_stats.create_index(
            [("placement", ASCENDING), ("date", DESCENDING)],
            name="idx_placement_stats_trend",
        )
        logger.info("All placement_day_stats indexes created (2)")
    except Exception as e:
        logger.error(f"Error creating placement_day_stats indexes: {str(e)}")

    # =========================================================================
    # ad_fraud_signals — 2 indexes (including 7-day TTL)
    # =========================================================================
    fraud = mongo.db["ad_fraud_signals"]
    try:
        await fraud.create_index(
            [("campaign_id", ASCENDING), ("flagged_at", DESCENDING)],
            name="idx_fraud_campaign_flagged",
        )
        await fraud.create_index(
            [("created_at", ASCENDING)],
            name="idx_fraud_signals_ttl",
            expireAfterSeconds=7 * 24 * 60 * 60,  # 7 days
        )
        logger.info("All ad_fraud_signals indexes created (2, incl. TTL)")
    except Exception as e:
        logger.error(f"Error creating ad_fraud_signals indexes: {str(e)}")

    # =========================================================================
    # vendor_ad_billing — 2 indexes
    # =========================================================================
    billing = mongo.db["vendor_ad_billing"]
    try:
        await billing.create_index(
            [("vendor_id", ASCENDING), ("billing_period_start", DESCENDING)],
            name="idx_billing_vendor_period",
        )
        await billing.create_index(
            [("campaign_id", ASCENDING), ("billing_period_start", DESCENDING)],
            name="idx_billing_campaign_period",
        )
        logger.info("All vendor_ad_billing indexes created (2)")
    except Exception as e:
        logger.error(f"Error creating vendor_ad_billing indexes: {str(e)}")

    # =========================================================================
    # ad_events — add campaign_id compound index (supplements existing indexes)
    # =========================================================================
    ad_events = mongo.db["ad_events"]
    try:
        await ad_events.create_index(
            [
                ("campaign_id", ASCENDING),
                ("event_type", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_campaign_type_date",
            sparse=True,
        )
        await ad_events.create_index(
            [("click_id", ASCENDING)],
            name="idx_ad_events_click_id",
            unique=True,
            sparse=True,
        )
        # TTL index already created in create_advertising_indexes() as idx_ad_events_ttl
        # Fraud detection + event dedup: event_type + campaign + planner + time
        # Field order matches dedup query in planner_ad_interaction_service._is_duplicate_event
        await ad_events.create_index(
            [
                ("event_type", ASCENDING),
                ("campaign_id", ASCENDING),
                ("planner_id", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_ad_events_dedup_fraud",
        )
        # Session anomaly detection
        await ad_events.create_index(
            [("session_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_ad_events_session_date",
            sparse=True,
        )
        logger.info("Campaign platform ad_events indexes created (4)")
    except Exception as e:
        logger.error(f"Error creating campaign ad_events indexes: {str(e)}")

    # =========================================================================
    # ad_leads — add campaign_id index (supplements existing indexes)
    # =========================================================================
    ad_leads = mongo.db["ad_leads"]
    try:
        await ad_leads.create_index(
            [("campaign_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_ad_leads_campaign_date",
            sparse=True,
        )
        logger.info("Campaign platform ad_leads index created (1)")
    except Exception as e:
        logger.error(f"Error creating campaign ad_leads indexes: {str(e)}")

    # =========================================================================
    # vendor_profiles — sponsored ad dedup index (Phase 3)
    # =========================================================================
    vendor_profiles = mongo.db["vendor_profiles"]

    # Unique compound index for race-safe add-to-directory dedup
    # Only applies to profiles created from sponsored ads (partial filter).
    # Older local databases may already have a broken version of this index
    # that also matches null `source_campaign_id` values, which blocks manual
    # vendor creation for planners after the first vendor.
    desired_vendor_profile_index = {
        "key": [("created_by", 1), ("source_campaign_id", 1)],
        "unique": True,
        "partialFilterExpression": {"source_campaign_id": {"$type": "string"}},
    }
    existing_vendor_profile_indexes = await vendor_profiles.index_information()
    existing_sponsored_dedup = existing_vendor_profile_indexes.get(
        "idx_sponsored_ad_dedup"
    )

    if existing_sponsored_dedup:
        existing_key = existing_sponsored_dedup.get("key")
        existing_unique = existing_sponsored_dedup.get("unique", False)
        existing_partial = existing_sponsored_dedup.get("partialFilterExpression")

        if (
            existing_key != desired_vendor_profile_index["key"]
            or existing_unique != desired_vendor_profile_index["unique"]
            or existing_partial
            != desired_vendor_profile_index["partialFilterExpression"]
        ):
            await vendor_profiles.drop_index("idx_sponsored_ad_dedup")
            logger.info("Dropped stale idx_sponsored_ad_dedup index on vendor_profiles")

    await vendor_profiles.create_index(
        desired_vendor_profile_index["key"],
        unique=desired_vendor_profile_index["unique"],
        partialFilterExpression=desired_vendor_profile_index["partialFilterExpression"],
        name="idx_sponsored_ad_dedup",
    )

    # =========================================================================
    # vendor_profiles — scraper dedup & filtering indexes
    # =========================================================================
    try:
        # google_place_id unique index (sparse — only applies to scraped vendors)
        await vendor_profiles.create_index(
            [("google_place_id", ASCENDING)],
            unique=True,
            sparse=True,
            name="idx_vendor_google_place_id",
        )
        logger.info("Created index: idx_vendor_google_place_id")

        # Compound index for scraper name+city+category dedup
        await vendor_profiles.create_index(
            [
                ("business_name", ASCENDING),
                ("city", ASCENDING),
                ("service_category", ASCENDING),
            ],
            name="idx_vendor_name_city_category",
        )
        logger.info("Created index: idx_vendor_name_city_category")

        # Source filter (e.g. list all scraped vendors)
        await vendor_profiles.create_index(
            [("source", ASCENDING), ("is_active", ASCENDING)],
            name="idx_vendor_source_active",
        )
        logger.info("Created index: idx_vendor_source_active")

        logger.info("Vendor scraper indexes created (3)")
    except Exception as e:
        logger.error(f"Error creating vendor scraper indexes: {str(e)}")

    logger.info("All campaign platform indexes created/verified (25 total)")
    return True


async def create_billing_indexes():
    """
    Create indexes for billing-related collections

    Collections: ad_lead_charges, vendor_free_tier, vendor_ad_billing (additional indexes)

    Key queries:
    1. Get charges by campaign_id sorted by created_at (campaign charge history)
    2. Get charges by vendor_id sorted by created_at (vendor charge history)
    3. Get charge by lead_id (one charge per lead - unique)
    4. Get charge by stripe_invoice_item_id (Stripe reconciliation)
    5. Get free tier record by vendor_id (unique)
    6. Check active free tier by is_free and expires_at
    7. Get invoices by payment_status (invoice finalization queries)
    """

    # =========================================================================
    # ad_lead_charges — 4 indexes
    # =========================================================================
    ad_lead_charges = mongo.db["ad_lead_charges"]
    try:
        # 1. Campaign charge history (campaign_id + created_at descending)
        await ad_lead_charges.create_index(
            [("campaign_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_lead_charges_campaign_date",
        )
        logger.info("Created index: idx_lead_charges_campaign_date")

        # 2. Vendor charge history (vendor_id + created_at descending)
        await ad_lead_charges.create_index(
            [("vendor_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_lead_charges_vendor_date",
        )
        logger.info("Created index: idx_lead_charges_vendor_date")

        # 3. Unique index on lead_id (one charge per lead)
        await ad_lead_charges.create_index(
            [("lead_id", ASCENDING)],
            name="idx_lead_charges_lead_id",
            unique=True,
        )
        logger.info("Created index: idx_lead_charges_lead_id (unique)")

        # 4. Stripe reconciliation (sparse index for stripe_invoice_item_id)
        await ad_lead_charges.create_index(
            [("stripe_invoice_item_id", ASCENDING)],
            name="idx_lead_charges_stripe_invoice_item",
            sparse=True,
        )
        logger.info("Created index: idx_lead_charges_stripe_invoice_item (sparse)")

        logger.info("All ad_lead_charges indexes created (4)")
    except Exception as e:
        logger.error(f"Error creating ad_lead_charges indexes: {str(e)}")

    # =========================================================================
    # vendor_free_tier — 2 indexes
    # =========================================================================
    vendor_free_tier = mongo.db["vendor_free_tier"]
    try:
        # 1. Unique index on vendor_id (one record per vendor)
        await vendor_free_tier.create_index(
            [("vendor_id", ASCENDING)],
            name="idx_free_tier_vendor_id",
            unique=True,
        )
        logger.info("Created index: idx_free_tier_vendor_id (unique)")

        # 2. Active free tier lookup (is_free + expires_at)
        await vendor_free_tier.create_index(
            [("is_free", ASCENDING), ("expires_at", ASCENDING)],
            name="idx_free_tier_active_lookup",
        )
        logger.info("Created index: idx_free_tier_active_lookup")

        logger.info("All vendor_free_tier indexes created (2)")
    except Exception as e:
        logger.error(f"Error creating vendor_free_tier indexes: {str(e)}")

    # =========================================================================
    # vendor_ad_billing — additional payment_status index
    # =========================================================================
    vendor_ad_billing = mongo.db["vendor_ad_billing"]
    try:
        # Payment status index (for invoice finalization queries)
        await vendor_ad_billing.create_index(
            [("payment_status", ASCENDING)],
            name="idx_billing_payment_status",
        )
        logger.info("Created index: idx_billing_payment_status")

        logger.info("Additional vendor_ad_billing indexes created (1)")
    except Exception as e:
        logger.error(f"Error creating additional vendor_ad_billing indexes: {str(e)}")

    logger.info("All billing indexes created/verified (7 total)")

    # =========================================================================
    # planner_ad_preferences — 1 index
    # =========================================================================
    planner_prefs = mongo.db["planner_ad_preferences"]
    try:
        await planner_prefs.create_index(
            [("planner_id", ASCENDING)],
            name="idx_planner_prefs_planner_id",
            unique=True,
        )
        logger.info("Created index: idx_planner_prefs_planner_id (unique)")
    except Exception as e:
        logger.error(f"Error creating planner_ad_preferences indexes: {str(e)}")

    return True


async def create_couple_portal_indexes():
    """
    Create indexes for couple portal collections: couple_users, couple_updates, archived_weddings.

    Key queries:
    1. couple_users: login by email, invite token lookup, list by planner, list by wedding
    2. couple_updates: updates feed by wedding_id sorted by created_at
    3. archived_weddings: lookup by original wedding_id
    """
    try:
        couple_users = mongo.db["couple_users"]

        # Login: find by email (unique per wedding, not globally unique since same email could be in multiple weddings)
        await couple_users.create_index(
            [("email", ASCENDING), ("wedding_id", ASCENDING)],
            unique=True,
            name="idx_couple_email_wedding",
            background=True,
        )

        # Invite token lookup (used during setup flow)
        await couple_users.create_index(
            [("invite_token", ASCENDING)],
            name="idx_couple_invite_token",
            sparse=True,
            background=True,
        )

        # List couples by planner (planner management page)
        await couple_users.create_index(
            [("planner_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_couple_planner_created",
            background=True,
        )

        # List couples by wedding (portal service lookups)
        await couple_users.create_index(
            [("wedding_id", ASCENDING)], name="idx_couple_wedding", background=True
        )

        couple_updates = mongo.db["couple_updates"]

        # Updates feed: by wedding_id, sorted by created_at desc
        await couple_updates.create_index(
            [("wedding_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_updates_wedding_created",
            background=True,
        )

        archived_weddings = mongo.db["archived_weddings"]

        # Lookup archived wedding by original ID
        await archived_weddings.create_index(
            [("original_wedding_id", ASCENDING)],
            unique=True,
            name="idx_archived_original_id",
            background=True,
        )

        # Sprint 3: Password reset token lookup
        await couple_users.create_index(
            [("password_reset_token", ASCENDING)],
            name="idx_couple_reset_token",
            sparse=True,
            background=True,
        )

        # Sprint 3: couple_messages collection
        couple_messages = mongo.db["couple_messages"]

        # Message history per wedding (chronological feed)
        await couple_messages.create_index(
            [("wedding_id", ASCENDING), ("_id", DESCENDING)],
            name="idx_messages_wedding_id",
            background=True,
        )

        # Unread count queries (couple checking planner messages, planner checking couple messages)
        await couple_messages.create_index(
            [
                ("wedding_id", ASCENDING),
                ("sender_role", ASCENDING),
                ("read_by_couple", ASCENDING),
            ],
            name="idx_messages_unread_couple",
            background=True,
        )
        await couple_messages.create_index(
            [
                ("wedding_id", ASCENDING),
                ("sender_role", ASCENDING),
                ("read_by_planner", ASCENDING),
            ],
            name="idx_messages_unread_planner",
            background=True,
        )

        # Sprint 4: custom_form_templates collection
        custom_templates = mongo.db["custom_form_templates"]

        await custom_templates.create_index(
            [("planner_email", ASCENDING), ("created_at", DESCENDING)],
            name="idx_custom_templates_planner",
            background=True,
        )

        # Sprint 5: planner_tasks meeting queries
        planner_tasks = mongo.get_planner_tasks_collection()
        await planner_tasks.create_index(
            [
                ("wedding_id", ASCENDING),
                ("category", ASCENDING),
                ("planner_email", ASCENDING),
                ("start_date", ASCENDING),
            ],
            name="idx_planner_tasks_meeting_lookup",
            background=True,
        )

        logger.info(
            "Couple portal indexes created/verified (couple_users, couple_updates, couple_messages, archived_weddings, custom_form_templates, planner_tasks)"
        )

    except Exception as e:
        logger.error(f"Error creating couple portal indexes: {e}")


async def create_calendar_indexes():
    """
    Create indexes for shared planner calendar collections.

    Collections:
    1. planner_tasks
    2. calendar_connections
    3. calendar_event_syncs
    4. meeting_invites
    5. calendar_jobs
    6. calendar_idempotency_keys
    """
    try:
        planner_tasks = mongo.get_planner_tasks_collection()
        await planner_tasks.create_index(
            [
                ("owner_planner_id", ASCENDING),
                ("schedule_item_type", ASCENDING),
                ("start_date", ASCENDING),
            ],
            name="idx_planner_tasks_owner_type_start",
            background=True,
        )
        await planner_tasks.create_index(
            [("assigned_user_ids", ASCENDING), ("start_date", ASCENDING)],
            name="idx_planner_tasks_assignee_start",
            background=True,
        )
        await planner_tasks.create_index(
            [
                ("wedding_id", ASCENDING),
                ("schedule_item_type", ASCENDING),
                ("start_date", ASCENDING),
            ],
            name="idx_planner_tasks_wedding_type_start",
            background=True,
        )
        await planner_tasks.create_index(
            [
                ("owner_planner_email", ASCENDING),
                ("category", ASCENDING),
                ("start_date", ASCENDING),
            ],
            name="idx_planner_tasks_owner_email_category_start",
            background=True,
        )

        calendar_connections = mongo.get_calendar_connections_collection()
        await calendar_connections.create_index(
            [("owner_planner_id", ASCENDING), ("user_id", ASCENDING)],
            name="idx_calendar_connections_owner_user",
            background=True,
        )
        await calendar_connections.create_index(
            [("user_id", ASCENDING), ("connection_status", ASCENDING)],
            name="idx_calendar_connections_user_status",
            background=True,
        )
        await calendar_connections.create_index(
            [("owner_planner_id", ASCENDING), ("is_shared_in_team_view", ASCENDING)],
            name="idx_calendar_connections_owner_shared",
            background=True,
        )
        await calendar_connections.create_index(
            [("provider", ASCENDING), ("provider_account_email", ASCENDING)],
            name="idx_calendar_connections_provider_account",
            background=True,
        )
        # Legacy Google-era unique index (keyed on provider_account_email +
        # calendar_id). The new Aurinko schema keys on aurinko_account_id +
        # aurinko_calendar_id, so drop the old one if present.
        try:
            await calendar_connections.drop_index(
                "idx_calendar_connections_user_account_calendar"
            )
        except Exception as drop_exc:
            message = str(drop_exc).lower()
            if "ns not found" not in message and "index not found" not in message:
                logger.debug(
                    "Could not drop legacy idx_calendar_connections_user_account_calendar: %s",
                    drop_exc,
                )
        # Canonical uniqueness for the Aurinko-keyed schema: one row per
        # (planner owner, workspace user, Aurinko account, Aurinko calendar).
        await calendar_connections.create_index(
            [
                ("owner_planner_id", ASCENDING),
                ("user_id", ASCENDING),
                ("aurinko_account_id", ASCENDING),
                ("aurinko_calendar_id", ASCENDING),
            ],
            name="idx_calendar_connections_aurinko_compound",
            unique=True,
            background=True,
        )
        # Webhook-handler lookup: calendar_webhook_service.handle_event_change
        # resolves connection by (aurinko_account_id, aurinko_calendar_id).
        await calendar_connections.create_index(
            [
                ("aurinko_account_id", ASCENDING),
                ("aurinko_calendar_id", ASCENDING),
            ],
            name="idx_calendar_connections_aurinko_lookup",
            background=True,
        )

        calendar_event_syncs = mongo.get_calendar_event_syncs_collection()
        await calendar_event_syncs.create_index(
            [("task_id", ASCENDING), ("calendar_connection_id", ASCENDING)],
            name="idx_calendar_syncs_task_connection",
            unique=True,
            sparse=True,
            background=True,
        )
        await calendar_event_syncs.create_index(
            [
                ("target_user_id", ASCENDING),
                ("sync_status", ASCENDING),
                ("updated_at", DESCENDING),
            ],
            name="idx_calendar_syncs_target_status_updated",
            background=True,
        )
        await calendar_event_syncs.create_index(
            [("owner_planner_id", ASCENDING), ("task_id", ASCENDING)],
            name="idx_calendar_syncs_owner_task",
            background=True,
        )
        await calendar_event_syncs.create_index(
            [
                ("sync_status", ASCENDING),
                ("next_retry_at", ASCENDING),
                ("retryable_error", ASCENDING),
            ],
            name="idx_calendar_syncs_retry_queue",
            background=True,
        )
        await calendar_event_syncs.create_index(
            [
                ("sync_status", ASCENDING),
                ("last_drift_check_at", ASCENDING),
                ("calendar_connection_id", ASCENDING),
            ],
            name="idx_calendar_syncs_drift_checks",
            background=True,
        )

        meeting_invites = mongo.get_meeting_invites_collection()
        await _deduplicate_meeting_invites(meeting_invites)
        await meeting_invites.create_index(
            [("task_id", ASCENDING), ("recipient_email", ASCENDING)],
            name="idx_meeting_invites_task_recipient",
            unique=True,
            background=True,
        )
        await meeting_invites.create_index(
            [("wedding_id", ASCENDING), ("delivery_status", ASCENDING)],
            name="idx_meeting_invites_wedding_delivery_status",
            background=True,
        )
        await meeting_invites.create_index(
            [("wedding_id", ASCENDING), ("response_status", ASCENDING)],
            name="idx_meeting_invites_wedding_response_status",
            background=True,
        )

        calendar_jobs = mongo.get_calendar_jobs_collection()
        await calendar_jobs.create_index(
            [("status", ASCENDING), ("run_at", ASCENDING)],
            name="idx_calendar_jobs_status_run_at",
            background=True,
        )
        await calendar_jobs.create_index(
            [("dedupe_key", ASCENDING)],
            name="idx_calendar_jobs_dedupe_key",
            unique=True,
            background=True,
        )
        await calendar_jobs.create_index(
            [("expires_at", ASCENDING)],
            name="idx_calendar_jobs_expires_at_ttl",
            expireAfterSeconds=0,
            background=True,
        )

        calendar_idempotency = mongo.get_calendar_idempotency_collection()
        await calendar_idempotency.create_index(
            [("scope_key", ASCENDING), ("idempotency_key", ASCENDING)],
            name="idx_calendar_idempotency_scope_key",
            unique=True,
            background=True,
        )
        await calendar_idempotency.create_index(
            [("expires_at", ASCENDING)],
            name="idx_calendar_idempotency_expires_at_ttl",
            expireAfterSeconds=0,
            background=True,
        )

        logger.info("Shared planner calendar indexes created/verified")
    except Exception as e:
        logger.error(f"Error creating shared planner calendar indexes: {e}")


async def create_guest_media_indexes():
    """
    Create indexes for guest-uploaded memories and export jobs.

    Collections:
    1. guest_media_assets
    2. guest_media_exports
    """
    try:
        guest_media_assets = mongo.db["guest_media_assets"]

        await guest_media_assets.create_index(
            [("wedding_id", ASCENDING), ("uploaded_at", DESCENDING)],
            name="idx_guest_media_wedding_uploaded",
            background=True,
        )
        await guest_media_assets.create_index(
            [
                ("wedding_id", ASCENDING),
                ("review_status", ASCENDING),
                ("uploaded_at", DESCENDING),
            ],
            name="idx_guest_media_review_queue",
            background=True,
        )
        await guest_media_assets.create_index(
            [
                ("wedding_id", ASCENDING),
                ("media_type", ASCENDING),
                ("uploaded_at", DESCENDING),
            ],
            name="idx_guest_media_media_type",
            background=True,
        )
        await guest_media_assets.create_index(
            [
                ("wedding_id", ASCENDING),
                ("event_type", ASCENDING),
                ("uploaded_at", DESCENDING),
            ],
            name="idx_guest_media_event_type",
            background=True,
        )
        await guest_media_assets.create_index(
            [("upload_batch_id", ASCENDING)],
            name="idx_guest_media_upload_batch",
            background=True,
        )
        await guest_media_assets.create_index(
            [("original_key", ASCENDING)],
            name="idx_guest_media_original_key",
            unique=True,
            background=True,
        )
        await guest_media_assets.create_index(
            [("stream_uid", ASCENDING)],
            name="idx_guest_media_stream_uid",
            sparse=True,
            background=True,
        )
        await guest_media_assets.create_index(
            [
                ("wedding_id", ASCENDING),
                ("uploader_name", ASCENDING),
                ("uploaded_at", DESCENDING),
            ],
            name="idx_guest_media_uploader",
            background=True,
        )
        await guest_media_assets.create_index(
            [
                ("wedding_id", ASCENDING),
                ("upload_status", ASCENDING),
                ("created_at", DESCENDING),
            ],
            name="idx_guest_media_upload_status",
            background=True,
        )

        guest_media_exports = mongo.db["guest_media_exports"]

        await guest_media_exports.create_index(
            [("wedding_id", ASCENDING), ("created_at", DESCENDING)],
            name="idx_guest_media_exports_wedding_created",
            background=True,
        )
        await guest_media_exports.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="idx_guest_media_exports_status",
            background=True,
        )

        logger.info("Guest media indexes created/verified")
    except Exception as e:
        logger.error(f"Error creating guest media indexes: {e}")


async def create_all_indexes():
    """Create all database indexes (called on app startup)"""
    try:
        await create_support_ticket_indexes()
        await create_wedding_indexes()
        await create_table_indexes()  # Seating orchestration
        await create_guest_indexes()
        await create_plus_one_indexes()
        await create_rsvp_indexes()
        await create_form_indexes()
        await create_subscription_indexes()
        await create_user_indexes()
        await create_reminders_sent_indexes()  # SMS delivery tracking
        await create_payment_indexes()
        await (
            create_admin_activity_log_indexes()
        )  # Activity/Audit logging indexes with TTL for auto-pruning
        await create_activity_logs_indexes()
        await create_vendor_contract_activity_indexes()
        await create_vendor_contract_security_indexes()
        await create_vendor_assignment_indexes()
        await create_audit_logs_indexes()
        await create_security_audit_logs_indexes()
        await create_errors_indexes()
        await create_kb_articles_indexes()  # Knowledge Base articles
        await create_blog_articles_indexes()  # Blog articles
        await create_invitation_indexes()  # User invitation cleanup
        await create_team_member_indexes()  # Team management
        await create_advertising_indexes()  # Legacy advertising (19 indexes)
        await create_campaign_platform_indexes()  # Campaign platform (21 indexes)
        await create_billing_indexes()  # Billing collections (7 indexes)
        await create_couple_portal_indexes()  # Couple portal (6 indexes)
        await create_calendar_indexes()  # Shared planner calendar
        await create_guest_media_indexes()  # Couple guest memories
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
