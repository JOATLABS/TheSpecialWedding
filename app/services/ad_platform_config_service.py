"""
Ad Platform Config Service

Manages the singleton platform configuration document and data pipeline status.
Also handles data exports for the admin Platform Config tab.

Includes an application-level TTL cache to reduce DB reads for feature flags.
The cache auto-invalidates after CACHE_TTL_SECONDS (default 60s) or on writes.

Collection: ad_platform_config (singleton, _id="singleton")
"""

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ── Application-level config cache ──
CACHE_TTL_SECONDS = 60  # Re-read from DB at most once per minute

_config_cache: dict[str, Any] | None = None
_config_cache_ts: float = 0.0
_cache_lock: asyncio.Lock = asyncio.Lock()


def invalidate_config_cache():
    """Force cache refresh on next read. Called after writes."""
    global _config_cache, _config_cache_ts
    _config_cache = None
    _config_cache_ts = 0.0


def _serialize_export_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, list):
        return [_serialize_export_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_export_value(item) for key, item in value.items()}
    return value


# Default config values — used when no config document exists yet
DEFAULT_CONFIG = {
    "_id": "singleton",
    # Feature Flags
    "ads_enabled": True,
    "show_sponsored_badge": True,
    "enable_event_tracking": True,
    "require_creative_review": True,
    "auto_approve_returning_vendors": False,
    # Serving Limits
    "max_sponsored_per_page": 3,
    "impressions_per_session": 5,
    "freq_cap_per_campaign_planner_day": 3,
    "review_sla_hours": 48,
    "max_campaigns_per_vendor": 5,
    # Fraud Detection
    "max_clicks_per_planner_campaign_hour": 5,
    "hide_rate_auto_pause_threshold": 3,
    "click_velocity_window_minutes": 5,
    "auto_void_suspicious_clicks": True,
    # Vendor Signup
    "vendor_domain": "vendor.thespecialwedding.io",
    "auto_approve_signups": False,
    "require_profile_completion": True,
    "min_images_for_campaign": 1,
}


class AdPlatformConfigService:
    """Service for managing advertising platform configuration."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.config_col = db["ad_platform_config"]

    # =========================================================================
    # GET / UPDATE CONFIG
    # =========================================================================

    async def get_config(self, bypass_cache: bool = False) -> dict[str, Any]:
        """
        Get the current platform config. Creates default if none exists.

        Uses application-level TTL cache (60s) to reduce DB reads on hot paths
        like ad serving. Pass bypass_cache=True for admin reads that must be fresh.

        Returns the config document without _id.
        """
        global _config_cache, _config_cache_ts

        # Return cached value if still fresh (lock-free fast path)
        if not bypass_cache and _config_cache is not None:
            if (time.time() - _config_cache_ts) < CACHE_TTL_SECONDS:
                return {**_config_cache}

        async with _cache_lock:
            # Double-check after acquiring lock (another coroutine may have refreshed)
            if not bypass_cache and _config_cache is not None:
                if (time.time() - _config_cache_ts) < CACHE_TTL_SECONDS:
                    return {**_config_cache}

            doc = await self.config_col.find_one({"_id": "singleton"})
            if not doc:
                # Initialize with defaults
                await self.config_col.insert_one({**DEFAULT_CONFIG})
                doc = {**DEFAULT_CONFIG}

            doc.pop("_id", None)

            # Update cache
            _config_cache = {**doc}
            _config_cache_ts = time.time()

        return doc

    async def update_config(
        self, updates: dict[str, Any], admin_email: str
    ) -> dict[str, Any]:
        """
        Partially update platform config. Only provided (non-None) fields are updated.
        Returns the updated config.
        """
        # Filter out None values
        clean_updates = {k: v for k, v in updates.items() if v is not None}
        if not clean_updates:
            return await self.get_config()

        clean_updates["updated_at"] = datetime.now(UTC)
        clean_updates["updated_by"] = admin_email

        await self.config_col.update_one(
            {"_id": "singleton"},
            {"$set": clean_updates},
            upsert=True,
        )

        logger.info(
            f"Platform config updated by {admin_email}: {list(clean_updates.keys())}"
        )
        invalidate_config_cache()
        return await self.get_config(bypass_cache=True)

    # =========================================================================
    # DATA PIPELINE STATUS
    # =========================================================================

    async def get_pipeline_status(self) -> dict[str, Any]:
        """
        Get data pipeline status: rollup health, collection stats, TTL info.
        Reads live data from MongoDB collections.
        """
        now = datetime.now(UTC)
        day_ago = now - timedelta(hours=24)

        # Get last rollup timestamp
        last_rollup = await self.db["campaign_day_stats"].find_one(
            sort=[("created_at", -1)]
        )
        last_rollup_time = last_rollup.get("created_at") if last_rollup else None

        # Events processed in last 24h
        events_24h = await self.db["ad_events"].count_documents(
            {"created_at": {"$gte": day_ago}}
        )

        # Rollup docs created in last 24h
        rollups_24h = await self.db["campaign_day_stats"].count_documents(
            {"created_at": {"$gte": day_ago}}
        )

        # Collection doc counts
        collections = [
            "ad_campaigns",
            "ad_creatives",
            "ad_events",
            "ad_leads",
            "campaign_day_stats",
            "placement_day_stats",
            "ad_fraud_signals",
            "ad_lead_charges",
            "marketing_leads",
            "vendor_ad_billing",
            "planner_ad_preferences",
        ]
        collection_stats = {}
        for col_name in collections:
            try:
                count = await self.db[col_name].estimated_document_count()
                collection_stats[col_name] = count
            except Exception:
                collection_stats[col_name] = 0

        # Determine health status
        if last_rollup_time and (now - last_rollup_time).total_seconds() < 48 * 3600:
            status = "healthy"
        elif last_rollup_time:
            status = "stale"
        else:
            status = "no_data"

        return {
            "status": status,
            "last_rollup": last_rollup_time.isoformat() if last_rollup_time else None,
            "events_processed_24h": events_24h,
            "rollup_docs_created_24h": rollups_24h,
            "ttl_ad_events_days": 90,
            "ttl_fraud_signals_days": 7,
            "collection_stats": collection_stats,
        }

    # =========================================================================
    # DATA EXPORT
    # =========================================================================

    async def export_data(
        self,
        dataset: str,
        date_range: str = "last_30_days",
        format: str = "json",
        limit: int = 1000,
    ) -> dict[str, Any]:
        """
        Export root-admin marketing and advertising data as JSON.
        CSV conversion happens on frontend.
        Returns rows + metadata.
        """
        now = datetime.now(UTC)

        def build_date_filter(field: str = "created_at") -> dict[str, Any]:
            if date_range == "last_7_days":
                return {field: {"$gte": now - timedelta(days=7)}}
            if date_range == "last_30_days":
                return {field: {"$gte": now - timedelta(days=30)}}
            if date_range == "last_90_days":
                return {field: {"$gte": now - timedelta(days=90)}}
            return {}

        # Date range filter
        date_filter = build_date_filter()

        # Dataset to collection mapping
        dataset_map = {
            "vendor_accounts": ("users", {"role": "advertising_vendor", **date_filter}),
            "active_campaigns": ("ad_campaigns", {"status": "active", **date_filter}),
            "all_campaigns": ("ad_campaigns", {**date_filter}),
            "campaign_performance": ("campaign_day_stats", {**date_filter}),
            "ad_events": ("ad_events", {**date_filter}),
            "ad_leads": ("ad_leads", {**date_filter}),
            "planner_feedback": ("planner_ad_preferences", {}),
            "campaign_daily_stats": ("campaign_day_stats", {**date_filter}),
            "placement_daily_stats": ("placement_day_stats", {**date_filter}),
            "fraud_signals": ("ad_fraud_signals", {**date_filter}),
            "marketing_leads": (
                "marketing_leads",
                build_date_filter("first_downloaded_at"),
            ),
        }

        if dataset not in dataset_map:
            return {"error": f"Unknown dataset: {dataset}", "rows": [], "total": 0}

        col_name, query = dataset_map[dataset]
        col = self.db[col_name]

        total = await col.count_documents(query)
        sort_field = (
            "first_downloaded_at" if dataset == "marketing_leads" else "created_at"
        )
        cursor = col.find(query).sort(sort_field, -1).limit(limit)
        rows = []
        async for doc in cursor:
            rows.append(_serialize_export_value(doc))

        return {
            "dataset": dataset,
            "date_range": date_range,
            "total": total,
            "returned": len(rows),
            "row_count": len(rows),
            "rows": rows,
        }
