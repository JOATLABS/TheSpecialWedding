"""
P1 Closeout — MongoDB Index Migrations (Forms, AI cache, Marketing)
────────────────────────────────────────────────────────────────────
Creates the indexes the post-Phase-D audit identified as missing for
the new query shapes shipped in Phases 1, A, B, C, D:

  • form_responses.find({form_id}).sort(submitted_at, -1).skip().limit() — paginated reads
  • form_distributions.find({form_id, status}) — distributions endpoint
  • form_distributions reminder-scheduler scan (5-key compound)
  • form_distributions.find_one({_id, form_id}) — token validation
  • form_uploads.find({form_id, distribution_id}) — quota + listing
  • form_uploads.find_one({_id, form_id, distribution_id}) — submission validation
  • marketing_leads.find_one({email, template_id}) — Phase C dedup (unique sparse)
  • ai_cache lookups (plan-isolated key + global TTL by expires_at)
  • ai_usage_log internal-feature daily quota counts
  • forms.find({created_by, seeded_from_catalog}) — Phase D seed dedup
  • forms.find({_id, is_active}) — owner+active fast path

Plus three TTL indexes that match the data we're already retaining
window-bounded:
  • marketing_leads created_at — 90 days
  • ai_usage_log created_at — 30 days
  • ai_cache expires_at — field-based (delete-when-datetime-passes)

Best-practice references:
  - MongoDB index docs (https://www.mongodb.com/docs/manual/indexes/)
  - MongoDB TTL indexes (https://www.mongodb.com/docs/manual/core/index-ttl/)
  - MongoDB partial indexes (operator allow-list documented at
    https://www.mongodb.com/docs/manual/core/index-partial/) — only
    $eq / $exists / $gt[e] / $lt[e] / $type / $and are permitted.

Idempotent + dry-run-safe — mirrors scripts/create_indexes_p0.py exactly.

Usage:
  python scripts/create_indexes_p1_forms_and_ai.py
  python scripts/create_indexes_p1_forms_and_ai.py --dry-run
"""

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# Index definitions: (collection, index_spec, kwargs).
# Key order in compound indexes matches the canonical query layout so
# Mongo's planner can use the index for both filter and sort without a
# second pass. Names are stable strings so re-runs are idempotent.
INDEXES = [
    # ── form_responses ───────────────────────────────────────────────
    # Paginated list per form, newest first (Phase 1 F4 + CSV export).
    (
        "form_responses",
        [("form_id", 1), ("submitted_at", -1)],
        {"name": "idx_form_id_submitted_at_desc"},
    ),
    # ── form_distributions ───────────────────────────────────────────
    # GET /admin/forms/{id}/distributions with optional status filter.
    (
        "form_distributions",
        [("form_id", 1), ("status", 1)],
        {"name": "idx_form_id_status"},
    ),
    # Reminder scheduler scan — match every condition of the eligibility
    # query in send_form_reminders so Mongo can use a single index for
    # the whole filter.
    (
        "form_distributions",
        [
            ("send_reminder", 1),
            ("submitted_at", 1),
            ("reminder_sent_at", 1),
            ("status", 1),
            ("sent_at", 1),
        ],
        {"name": "idx_reminder_eligibility"},
    ),
    # Public token-validation lookup (find_one by id+form scope).
    (
        "form_distributions",
        [("_id", 1), ("form_id", 1)],
        {"name": "idx_id_form_scope"},
    ),
    # ── form_uploads ─────────────────────────────────────────────────
    # Per-distribution aggregate quota + listing.
    (
        "form_uploads",
        [("form_id", 1), ("distribution_id", 1)],
        {"name": "idx_form_dist_uploads"},
    ),
    # Submission-time validation: file_id must belong to (form, distribution).
    (
        "form_uploads",
        [("_id", 1), ("form_id", 1), ("distribution_id", 1)],
        {"name": "idx_id_form_dist_validate"},
    ),
    # ── marketing_leads (Phase C) ────────────────────────────────────
    # Dedup lookup is the hot path on every public download submit.
    # Unique guarantees the idempotent (email, template_id) semantic at
    # the database layer; sparse skips legacy rows that pre-date the
    # field shape (unlikely but cheap to allow).
    (
        "marketing_leads",
        [("email", 1), ("template_id", 1)],
        {"unique": True, "sparse": True, "name": "idx_email_template_unique"},
    ),
    # 90-day TTL on marketing leads — GDPR-friendly automatic expiry.
    (
        "marketing_leads",
        [("created_at", 1)],
        {"expireAfterSeconds": 60 * 60 * 24 * 90, "name": "idx_marketing_leads_ttl"},
    ),
    # ── ai_cache ─────────────────────────────────────────────────────
    # Plan-isolated lookup with non-expired filter (Phase 1 wave-2).
    (
        "ai_cache",
        [
            ("feature", 1),
            ("tenant_id", 1),
            ("subscription_plan", 1),
            ("expires_at", 1),
        ],
        {"name": "idx_ai_cache_plan_isolated"},
    ),
    # Field-based TTL: docs are deleted when ``expires_at`` passes (the
    # documented MongoDB pattern for "delete when this datetime is
    # reached" is expireAfterSeconds=0 on a date-typed field).
    (
        "ai_cache",
        [("expires_at", 1)],
        {"expireAfterSeconds": 0, "name": "idx_ai_cache_expires_ttl"},
    ),
    # ── ai_usage_log ─────────────────────────────────────────────────
    # Internal-feature daily quota: count today's calls per (feature, tenant).
    (
        "ai_usage_log",
        [("feature", 1), ("tenant_id", 1), ("created_at", -1)],
        {"name": "idx_ai_usage_feature_tenant_date"},
    ),
    # 30-day usage-log retention.
    (
        "ai_usage_log",
        [("created_at", 1)],
        {"expireAfterSeconds": 60 * 60 * 24 * 30, "name": "idx_ai_usage_ttl"},
    ),
    # ── forms (Phase D) ──────────────────────────────────────────────
    # Phase D seed-dedup query. Partial index on the seeded subset only
    # so we don't pay for an index slot on every form doc — the same
    # pattern P0's idx_form_type_wedding uses.
    (
        "forms",
        [("created_by", 1), ("catalog_template_id", 1)],
        {
            "name": "idx_creator_catalog_seed",
            "partialFilterExpression": {"seeded_from_catalog": {"$eq": True}},
        },
    ),
    # Owner+active fast path used by every authenticated form lookup.
    (
        "forms",
        [("_id", 1), ("is_active", 1)],
        {"name": "idx_id_active"},
    ),
    # ── planner_notifications ────────────────────────────────────────
    # Covers get_notifications + get_notification_count: filter by
    # planner + unread state, sort by recency
    # (planner_notification_service.py:267-268, 281-283).
    (
        "planner_notifications",
        [("planner_id", 1), ("is_read", 1), ("created_at", -1)],
        {"name": "idx_planner_unread_recent"},
    ),
    # ── team_members ─────────────────────────────────────────────────
    # Covers _resolve_team_recipients fan-out scan over an owner's
    # active team members (planner_notification_service.py:530-537).
    (
        "team_members",
        [("owner_email", 1), ("status", 1)],
        {"name": "idx_owner_status"},
    ),
    # ── form_distributions ───────────────────────────────────────────
    # Covers send_form per-recipient dedup loop
    # (form_service.py:885) — find_one({form_id, recipient_email}).
    (
        "form_distributions",
        [("form_id", 1), ("recipient_email", 1)],
        {"name": "idx_form_recipient"},
    ),
]


async def create_indexes(dry_run: bool = False):
    from app.core.database import mongo

    if not await mongo.test_connection():
        raise RuntimeError("MongoDB connection test failed — aborting migration")

    try:
        for collection_name, index_spec, kwargs in INDEXES:
            index_name = kwargs.get("name", str(index_spec))
            collection = mongo.db[collection_name]

            existing = await collection.index_information()
            if index_name in existing:
                logger.info(f"  ✓ {collection_name}.{index_name} — already exists")
                continue

            if dry_run:
                logger.info(
                    f"  [DRY RUN] Would create {collection_name}.{index_name}: "
                    f"{index_spec}  kwargs={kwargs}"
                )
                continue

            logger.info(f"  → Creating {collection_name}.{index_name}: {index_spec}")
            await collection.create_index(index_spec, **kwargs)
            logger.info(f"  ✓ {collection_name}.{index_name} — created")

        logger.info("✅ P1 forms + AI + marketing index migration complete.")

    finally:
        # MongoConnector.close is synchronous.
        mongo.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create MongoDB indexes for P1 forms / AI cache / marketing"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    asyncio.run(create_indexes(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
