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
    AdLead,
    AdLeadStatus,
    AdLeadType,
    PlannerAdPreference,
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
        self.ad_leads = db["ad_leads"]
        self.planner_ad_preferences = db["planner_ad_preferences"]

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

        # Filter by date range using $and to combine with existing query conditions
        now = datetime.now(timezone.utc)
        date_filter = {
            "$and": [
                # Start date must be in the past or not set
                {"$or": [
                    {"start_date": {"$lte": now}},
                    {"start_date": None},
                ]},
                # End date must be in the future or not set
                {"$or": [
                    {"end_date": {"$gte": now}},
                    {"end_date": None},
                ]},
            ]
        }
        # Merge date filter into query using $and
        if "$and" in query:
            query["$and"].extend(date_filter["$and"])
        else:
            query["$and"] = date_filter["$and"]

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
            # Review workflow fields
            "review_status": data.get("review_status"),
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
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

    async def review_sponsored_vendor(
        self,
        sponsored_id: str,
        review_status: str,
        reviewer_email: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Review a sponsored vendor campaign (approve, reject, or request changes).

        When approved and the feature flag config requires review, the campaign
        becomes eligible for serving. When rejected or changes requested, the
        campaign stays inactive.

        Args:
            sponsored_id: Sponsored vendor ID
            review_status: New review status (approved, rejected, changes_requested)
            reviewer_email: Email of the admin performing the review
            review_notes: Optional reviewer notes

        Returns:
            Updated sponsored vendor document

        Raises:
            HTTPException: If sponsored vendor not found
        """
        sponsored_id_obj = validate_object_id(sponsored_id, "sponsored_vendor_id")

        now = datetime.now(timezone.utc)

        update_fields = {
            "review_status": review_status,
            "reviewed_by": reviewer_email,
            "reviewed_at": now,
            "updated_at": now,
        }

        if review_notes is not None:
            update_fields["review_notes"] = review_notes

        # If approved, activate the campaign; otherwise keep it inactive
        if review_status == "approved":
            update_fields["is_active"] = True
        elif review_status in ("rejected", "changes_requested"):
            update_fields["is_active"] = False

        updated = await self.sponsored_vendors.find_one_and_update(
            {"_id": sponsored_id_obj},
            {"$set": update_fields},
            return_document=True,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Sponsored vendor not found")

        logger.info(
            f"Sponsored vendor {sponsored_id} reviewed as {review_status} "
            f"by {reviewer_email}"
        )

        return updated

    async def get_review_queue(
        self,
        status_filter: Optional[str] = None,
        placement_filter: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get campaigns pending review or filtered by review status.

        Args:
            status_filter: Filter by review_status (default: pending_review)
            placement_filter: Filter by placement
            limit: Max results
            skip: Skip for pagination

        Returns:
            List of sponsored vendor documents with vendor profile info
        """
        query: Dict[str, Any] = {}

        if status_filter:
            query["review_status"] = status_filter
        else:
            query["review_status"] = "pending_review"

        if placement_filter:
            query["placement"] = placement_filter

        results = []
        async for doc in (
            self.sponsored_vendors
            .find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        ):
            # Enrich with vendor profile info for the review UI
            vendor_profile_id = doc.get("vendor_profile_id")
            if vendor_profile_id:
                try:
                    vendor_profile = await self.db.vendor_profiles.find_one(
                        {"_id": ObjectId(vendor_profile_id)},
                        {"business_name": 1, "email": 1, "logo_url": 1,
                         "service_category": 1, "phone": 1}
                    )
                    if vendor_profile:
                        doc["vendor_profile"] = {
                            "business_name": vendor_profile.get("business_name"),
                            "email": vendor_profile.get("email"),
                            "logo_url": vendor_profile.get("logo_url"),
                            "service_category": vendor_profile.get("service_category"),
                            "phone": vendor_profile.get("phone"),
                        }
                except Exception:
                    pass

            results.append(doc)

        return results

    async def get_review_queue_counts(self) -> Dict[str, int]:
        """
        Get counts of campaigns by review status for the queue stats bar.

        Returns:
            Dict with counts: {pending_review: N, approved: N, rejected: N, changes_requested: N}
        """
        pipeline = [
            {"$match": {"review_status": {"$ne": None}}},
            {"$group": {"_id": "$review_status", "count": {"$sum": 1}}},
        ]

        counts = {
            "pending_review": 0,
            "approved": 0,
            "rejected": 0,
            "changes_requested": 0,
        }

        async for doc in self.sponsored_vendors.aggregate(pipeline):
            status = doc["_id"]
            if status in counts:
                counts[status] = doc["count"]

        return counts

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

        # Backward compatibility: map legacy event type names to new enum values
        LEGACY_EVENT_TYPE_MAP = {
            "impression": AdEventType.IMPRESSION_SERVED.value,
            "viewable_impression": AdEventType.IMPRESSION_VIEWABLE.value,
            "detail_view": AdEventType.VENDOR_PROFILE_VIEW.value,
            "assignment": AdEventType.VENDOR_ADDED_TO_WEDDING.value,
        }
        if event_type in LEGACY_EVENT_TYPE_MAP:
            event_type = LEGACY_EVENT_TYPE_MAP[event_type]

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
        if event_type in [AdEventType.IMPRESSION_SERVED.value, AdEventType.IMPRESSION_VIEWABLE.value]:
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

    async def create_lead(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new ad lead from planner interest.

        Args:
            data: Lead data including planner_id, vendor_profile_id, lead_type, etc.

        Returns:
            Created ad lead document with _id
        """
        # Validate IDs
        sponsored_id = validate_object_id(
            data.get("sponsored_vendor_id"),
            "sponsored_vendor_id"
        )
        vendor_id = validate_object_id(
            data.get("vendor_profile_id"),
            "vendor_profile_id"
        )

        # Validate optional wedding_id if provided
        wedding_id = data.get("wedding_id")
        if wedding_id:
            wedding_id = validate_object_id(wedding_id, "wedding_id")

        ad_lead = {
            "sponsored_vendor_id": str(sponsored_id),
            "vendor_profile_id": str(vendor_id),
            "planner_id": data.get("planner_id"),
            "wedding_id": str(wedding_id) if wedding_id else None,
            "lead_type": data.get("lead_type"),
            "status": data.get("status", AdLeadStatus.PENDING.value),
            "click_id": data.get("click_id"),
            "placement": data.get("placement", AdPlacement.VENDOR_RAIL.value),
            "message": data.get("message"),
            "quote_amount": data.get("quote_amount"),
            "responded_at": None,
            "converted_at": None,
            "metadata": data.get("metadata", {}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await self.ad_leads.insert_one(ad_lead)
        ad_lead["_id"] = result.inserted_id

        logger.info(
            f"Created ad lead {result.inserted_id} from planner {ad_lead['planner_id']} "
            f"for vendor {vendor_id}"
        )

        return ad_lead

    async def get_leads(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get ad leads with optional filters.

        Args:
            filters: Query filters (vendor_id, planner_id, status, lead_type, etc.)
            limit: Maximum results to return
            skip: Number of results to skip

        Returns:
            List of ad lead documents
        """
        if filters is None:
            filters = {}

        leads = []
        async for lead in (
            self.ad_leads
            .find(filters)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        ):
            leads.append(lead)

        return leads

    async def get_lead(self, lead_id: str) -> Dict[str, Any]:
        """
        Get a specific ad lead by ID.

        Args:
            lead_id: Lead ID

        Returns:
            Ad lead document

        Raises:
            HTTPException: If lead not found
        """
        lead_id_obj = validate_object_id(lead_id, "lead_id")

        lead = await self.ad_leads.find_one({"_id": lead_id_obj})
        if not lead:
            raise HTTPException(status_code=404, detail="Ad lead not found")

        return lead

    async def update_lead_status(
        self,
        lead_id: str,
        status_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the status of an ad lead.

        Args:
            lead_id: Lead ID
            status_data: Status update data

        Returns:
            Updated ad lead document

        Raises:
            HTTPException: If lead not found
        """
        lead_id_obj = validate_object_id(lead_id, "lead_id")

        updates = {
            "status": status_data.get("status"),
            "updated_at": datetime.now(timezone.utc),
        }

        if status_data.get("responded_at"):
            updates["responded_at"] = status_data.get("responded_at")

        if status_data.get("converted_at"):
            updates["converted_at"] = status_data.get("converted_at")

        updated = await self.ad_leads.find_one_and_update(
            {"_id": lead_id_obj},
            {"$set": updates},
            return_document=True,
        )

        if not updated:
            raise HTTPException(status_code=404, detail="Ad lead not found")

        logger.info(f"Updated ad lead {lead_id} status to {updates.get('status')}")

        return updated

    async def get_planner_preferences(self, planner_id: str) -> Dict[str, Any]:
        """
        Get or create ad preferences for a planner.

        Args:
            planner_id: Planner email

        Returns:
            Planner ad preferences document
        """
        prefs = await self.planner_ad_preferences.find_one(
            {"planner_id": planner_id}
        )

        if not prefs:
            # Create default preferences if they don't exist
            default_prefs = {
                "planner_id": planner_id,
                "hidden_vendor_ids": [],
                "hidden_categories": [],
                "reduced_frequency": False,
                "wedding_overrides": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            result = await self.planner_ad_preferences.insert_one(default_prefs)
            default_prefs["_id"] = result.inserted_id
            prefs = default_prefs

        return prefs

    async def hide_vendor(self, planner_id: str, vendor_id: str) -> Dict[str, Any]:
        """
        Hide a sponsored vendor for a planner.

        Args:
            planner_id: Planner email
            vendor_id: Sponsored vendor ID to hide

        Returns:
            Updated preferences document
        """
        vendor_id_obj = validate_object_id(vendor_id, "vendor_id")

        prefs = await self.planner_ad_preferences.find_one_and_update(
            {"planner_id": planner_id},
            {
                "$addToSet": {"hidden_vendor_ids": str(vendor_id_obj)},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            upsert=True,
            return_document=True,
        )

        logger.info(f"Hidden vendor {vendor_id} for planner {planner_id}")

        return prefs

    async def unhide_vendor(self, planner_id: str, vendor_id: str) -> Dict[str, Any]:
        """
        Unhide a previously hidden vendor for a planner.

        Args:
            planner_id: Planner email
            vendor_id: Sponsored vendor ID to unhide

        Returns:
            Updated preferences document
        """
        vendor_id_obj = validate_object_id(vendor_id, "vendor_id")

        prefs = await self.planner_ad_preferences.find_one_and_update(
            {"planner_id": planner_id},
            {
                "$pull": {"hidden_vendor_ids": str(vendor_id_obj)},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            return_document=True,
        )

        if not prefs:
            # If no preferences exist, create default ones
            prefs = await self.get_planner_preferences(planner_id)

        logger.info(f"Unhidden vendor {vendor_id} for planner {planner_id}")

        return prefs

    async def hide_category(self, planner_id: str, category: str) -> Dict[str, Any]:
        """
        Hide a vendor category for a planner.

        Args:
            planner_id: Planner email
            category: VendorCategory value to hide

        Returns:
            Updated preferences document
        """
        prefs = await self.planner_ad_preferences.find_one_and_update(
            {"planner_id": planner_id},
            {
                "$addToSet": {"hidden_categories": category},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            upsert=True,
            return_document=True,
        )

        logger.info(f"Hidden category {category} for planner {planner_id}")

        return prefs

    async def toggle_reduced_frequency(
        self,
        planner_id: str,
        reduced: bool
    ) -> Dict[str, Any]:
        """
        Toggle reduced ad frequency for a planner.

        Args:
            planner_id: Planner email
            reduced: Whether to enable reduced frequency

        Returns:
            Updated preferences document
        """
        prefs = await self.planner_ad_preferences.find_one_and_update(
            {"planner_id": planner_id},
            {
                "$set": {
                    "reduced_frequency": reduced,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
            return_document=True,
        )

        logger.info(
            f"{'Enabled' if reduced else 'Disabled'} reduced frequency "
            f"for planner {planner_id}"
        )

        return prefs

    async def get_sponsored_vendors_filtered(
        self,
        planner_id: str,
        placement: Optional[AdPlacement] = None,
        category_filter: Optional[VendorCategory] = None,
        wedding_stage: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get active sponsored vendors filtered by planner preferences.

        Excludes hidden vendors and hidden categories based on planner preferences.
        Respects reduced_frequency setting if enabled.

        Args:
            planner_id: Planner email
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

        # Get planner preferences
        prefs = await self.get_planner_preferences(planner_id)
        hidden_vendors = prefs.get("hidden_vendor_ids", [])
        hidden_categories = prefs.get("hidden_categories", [])
        reduced_frequency = prefs.get("reduced_frequency", False)

        # Build query
        query = {
            "is_active": True,
            "_id": {"$nin": [ObjectId(vid) for vid in hidden_vendors if vid]},
        }

        # Add placement filter if provided
        if placement:
            query["placement"] = placement.value

        # Add category filter and respect hidden categories
        if category_filter:
            query["target_categories"] = {
                "$in": [category_filter.value]
            }

        # Exclude ads from hidden categories
        if hidden_categories:
            query["target_categories"] = {
                "$nin": hidden_categories
            }

        # Add wedding stage filter if provided
        if wedding_stage:
            query["target_wedding_stages"] = {
                "$in": [wedding_stage]
            }

        # Filter by date range using $and to combine with existing query conditions
        now = datetime.now(timezone.utc)
        date_filter = {
            "$and": [
                # Start date must be in the past or not set
                {"$or": [
                    {"start_date": {"$lte": now}},
                    {"start_date": None},
                ]},
                # End date must be in the future or not set
                {"$or": [
                    {"end_date": {"$gte": now}},
                    {"end_date": None},
                ]},
            ]
        }
        # Merge date filter into query using $and
        if "$and" in query:
            query["$and"].extend(date_filter["$and"])
        else:
            query["$and"] = date_filter["$and"]

        # Adjust limit if reduced frequency is enabled
        if reduced_frequency:
            limit = max(1, limit // 2)

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
