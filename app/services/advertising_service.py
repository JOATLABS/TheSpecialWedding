"""
Advertising Service

Service for managing all advertising and sponsored vendor operations.
Handles feature flags, sponsored vendor management, and ad event tracking.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.models.advertising import (
    SponsoredVendor,
    AdEvent,
    AdvertisingFeatureFlag,
    AdPlacement,
    AdEventType,
)
from app.models.vendor import VendorCategory

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_object_id(id_str: str, field_name: str = "ID") -> ObjectId:
    """
    Validate and convert a string to ObjectId.

    Args:
        id_str: String ID to validate
        field_name: Field name for error message

    Returns:
        Validated ObjectId

    Raises:
        HTTPException: If ID format is invalid
    """
    if not id_str:
        raise HTTPException(status_code=400, detail=f"Missing {field_name}")
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")


# =============================================================================
# ADVERTISING SERVICE
# =============================================================================

class AdvertisingService:
    """
    Service for managing advertising features and sponsored vendors.

    Handles:
    - Feature flag management
    - Sponsored vendor CRUD operations
    - Ad event tracking and analytics
    """

    def __init__(self, db):
        """
        Initialize the advertising service.

        Args:
            db: Motor async database client
        """
        self.db = db
        self.sponsored_vendors = db["sponsored_vendors"]
        self.ad_events = db["ad_events"]
        self.ad_feature_flags = db["ad_feature_flags"]

    async def get_feature_flag(self) -> Dict[str, Any]:
        """
        Get the current advertising feature flag status.

        Creates a default flag if none exists.

        Returns:
            Feature flag document as dictionary
        """
        flag = await self.ad_feature_flags.find_one({"feature_key": "sponsored_vendors"})

        if not flag:
            # Create default flag if it doesn't exist
            default_flag = {
                "feature_key": "sponsored_vendors",
                "is_enabled": False,
                "enabled_by": None,
                "enabled_at": None,
                "config": {
                    "max_sponsored_per_page": 3,
                    "show_sponsored_badge": True,
                    "show_sponsored_label": True,
                    "enable_tracking": True,
                    "min_priority_threshold": 1,
                    "impressions_per_session_limit": 5,
                },
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            result = await self.ad_feature_flags.insert_one(default_flag)
            default_flag["_id"] = result.inserted_id
            flag = default_flag

        return flag

    async def toggle_feature_flag(
        self,
        is_enabled: bool,
        admin_email: str
    ) -> Dict[str, Any]:
        """
        Toggle the advertising feature flag.

        Args:
            is_enabled: Whether to enable or disable the feature
            admin_email: Email of admin making the change

        Returns:
            Updated feature flag document
        """
        updated_flag = await self.ad_feature_flags.find_one_and_update(
            {"feature_key": "sponsored_vendors"},
            {
                "$set": {
                    "is_enabled": is_enabled,
                    "enabled_by": admin_email,
                    "enabled_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=True,
            upsert=False,
        )

        if not updated_flag:
            raise HTTPException(status_code=404, detail="Feature flag not found")

        return updated_flag

    async def get_sponsored_vendors(
        self,
        placement: Optional[AdPlacement] = None,
        category_filter: Optional[VendorCategory] = None,
        wedding_stage: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get active sponsored vendors for a given placement.

        Only returns vendors if feature flag is enabled.
        Results are sorted by priority (highest first).

        Args:
            placement: Ad placement filter (optional)
            category_filter: Vendor category filter (optional)
            wedding_stage: Wedding stage filter (optional)
            limit: Maximum results to return

        Returns:
            List of active sponsored vendor documents
        """
        # Check if feature is enabled
        flag = await self.get_feature_flag()
        if not flag.get("is_enabled"):
            return []

        # Build query
        query = {
            "is_active": True,
        }

        # Add placement filter if provided
        if placement:
            query["placement"] = placement.value

        # Add category filter if provided
        if category_filter:
            query["target_categories"] = {
                "$in": [category_filter.value]
                if category_filter
                else []
            }

        # Add wedding stage filter if provided
        if wedding_stage:
            query["target_wedding_stages"] = {
                "$in": [wedding_stage]
            }

        # Filter by date range
        now = datetime.now(timezone.utc)
        query["$or"] = [
            {"start_date": {"$lte": now}},
            {"start_date": None},
        ]
        query["$or"].append(
            {"$and": [
                {"end_date": {"$gte": now}},
                {"end_date": {"$ne": None}},
            ]}
        )

        # Fetch sponsored vendors sorted by priority
        vendors = []
        async for vendor in (
            self.sponsored_vendors
            .find(query)
            .sort("priority", -1)
            .limit(limit)
        ):
            vendors.append(vendor)

        return vendors

    async def create_sponsored_vendor(
        self,
        data: Dict[str, Any],
        admin_email: str
    ) -> Dict[str, Any]:
        """
        Create a new sponsored vendor entry.

        Args:
            data: Sponsored vendor data
            admin_email: Email of admin creating the entry

        Returns:
            Created sponsored vendor document with _id
        """
        # Validate vendor_profile_id exists
        vendor_profile_id = validate_object_id(
            data.get("vendor_profile_id"),
            "vendor_profile_id"
        )

        sponsored_vendor = {
            "vendor_profile_id": str(vendor_profile_id),
            "placement": data.get("placement"),
            "priority": data.get("priority", 50),
            "headline": data.get("headline"),
            "description": data.get("description"),
            "is_active": data.get("is_active", True),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "target_categories": data.get("target_categories", []),
            "target_wedding_stages": data.get("target_wedding_stages", []),
            "created_by": admin_email,
            "impression_count": 0,
            "click_count": 0,
            "metadata": data.get("metadata", {}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.sponsored_vendors.insert_one(sponsored_vendor)
        sponsored_vendor["_id"] = result.inserted_id

        logger.info(
            f"Created sponsored vendor {result.inserted_id} for vendor {vendor_profile_id}"
        )

        return sponsored_vendor

    async def update_sponsored_vendor(
        self,
        sponsored_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing sponsored vendor.

        Args:
            sponsored_id: Sponsored vendor ID
            updates: Fields to update

        Returns:
            Updated sponsored vendor document

        Raises:
            HTTPException: If sponsored vendor not found
        """
        sponsored_id_obj = validate_object_id(sponsored_id, "sponsored_vendor_id")

        # Remove immutable fields
        updates.pop("id", None)
        updates.pop("_id", None)
        updates.pop("created_by", None)
        updates.pop("created_at", None)

        # Add updated_at timestamp
        updates["updated_at"] = datetime.now(timezone.utc)

        updated = await self.sponsored_vendors.find_one_and_update(
            {"_id": sponsored_id_obj},
            {"$set": updates},
            return_document=True,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Sponsored vendor not found")

        return updated

    async def delete_sponsored_vendor(self, sponsored_id: str) -> Dict[str, Any]:
        """
        Soft delete a sponsored vendor (set is_active=False).

        Args:
            sponsored_id: Sponsored vendor ID to delete

        Returns:
            Updated (deactivated) sponsored vendor document

        Raises:
            HTTPException: If sponsored vendor not found
        """
        sponsored_id_obj = validate_object_id(sponsored_id, "sponsored_vendor_id")

        deleted = await self.sponsored_vendors.find_one_and_update(
            {"_id": sponsored_id_obj},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=True,
        )

        if not deleted:
            raise HTTPException(status_code=404, detail="Sponsored vendor not found")

        logger.info(f"Deactivated sponsored vendor {sponsored_id}")

        return deleted

    async def record_ad_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Record an ad event (impression, click, etc).

        Also updates the sponsored vendor's impression/click counts.

        Args:
            event_data: Event data including event_type, sponsored_vendor_id, etc.

        Returns:
            Created ad event document with _id
        """
        # Validate IDs
        sponsored_id = validate_object_id(
            event_data.get("sponsored_vendor_id"),
            "sponsored_vendor_id"
        )
        vendor_id = validate_object_id(
            event_data.get("vendor_profile_id"),
            "vendor_profile_id"
        )

        event_type = event_data.get("event_type")

        ad_event = {
            "event_type": event_type,
            "sponsored_vendor_id": str(sponsored_id),
            "vendor_profile_id": str(vendor_id),
            "placement": event_data.get("placement"),
            "wedding_id": event_data.get("wedding_id"),
            "planner_id": event_data.get("planner_id"),
            "session_id": event_data.get("session_id"),
            "click_id": event_data.get("click_id"),
            "metadata": event_data.get("metadata", {}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.ad_events.insert_one(ad_event)
        ad_event["_id"] = result.inserted_id

        # Update sponsored vendor counts
        update_query = {}
        if event_type == AdEventType.IMPRESSION.value:
            update_query["$inc"] = {"impression_count": 1}
        elif event_type == AdEventType.CLICK.value:
            update_query["$inc"] = {"click_count": 1}

        if update_query:
            await self.sponsored_vendors.update_one(
                {"_id": sponsored_id},
                update_query,
            )

        logger.debug(
            f"Recorded {event_type} event for sponsored vendor {sponsored_id}"
        )

        return ad_event

    async def get_ad_stats(
        self,
        sponsored_vendor_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get analytics stats for a sponsored vendor.

        Returns impressions, clicks, CTR, and recent event count.

        Args:
            sponsored_vendor_id: Sponsored vendor ID
            days: Number of days to look back (default 7)

        Returns:
            Dictionary with stats including impressions, clicks, ctr, recent_events_count

        Raises:
            HTTPException: If sponsored vendor not found
        """
        sponsored_id_obj = validate_object_id(
            sponsored_vendor_id,
            "sponsored_vendor_id"
        )

        # Get the sponsored vendor
        sponsored = await self.sponsored_vendors.find_one({"_id": sponsored_id_obj})
        if not sponsored:
            raise HTTPException(status_code=404, detail="Sponsored vendor not found")

        # Calculate date range
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=days)

        # Count recent events
        recent_events = await self.ad_events.count_documents({
            "sponsored_vendor_id": sponsored_vendor_id,
            "created_at": {"$gte": period_start},
        })

        # Calculate CTR
        impressions = sponsored.get("impression_count", 0)
        clicks = sponsored.get("click_count", 0)
        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

        stats = {
            "sponsored_vendor_id": sponsored_vendor_id,
            "vendor_profile_id": sponsored.get("vendor_profile_id"),
            "placement": sponsored.get("placement"),
            "total_impressions": impressions,
            "total_clicks": clicks,
            "ctr": round(ctr, 2),
            "period_days": days,
            "recent_events_count": recent_events,
        }

        return stats

    async def health_check(self) -> bool:
        """
        Check if advertising service is healthy and database is accessible.

        Returns:
            True if service is healthy
        """
        try:
            await self.ad_feature_flags.find_one({})
            return True
        except Exception as e:
            logger.error(f"Advertising service health check failed: {e}")
            return False


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Note: The actual instance will be created per-request in the router
# to ensure fresh database connections
advertising_service = AdvertisingService
