"""
Vendor Campaign Service

Core business logic for vendor-created advertising campaigns.
Handles the full campaign lifecycle: create -> update -> submit -> review -> active -> complete.

Independent from the planner vendor directory. Vendors sign up at
vendor.thespecialwedding.io with role: advertising_vendor.

Images stored in separate R2 bucket: vendor-ad-assets (S3_AD_BUCKET_NAME).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.models.advertising_campaign import (
    CampaignStatus,
    CreativeReviewStatus,
)

logger = logging.getLogger(__name__)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId _id to string for JSON serialization."""
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


def _to_oid(val: str, field: str = "ID") -> ObjectId:
    """Validate and convert string to ObjectId."""
    if not val:
        raise HTTPException(status_code=400, detail=f"Missing {field}")
    try:
        return ObjectId(val)
    except InvalidId:
        raise HTTPException(status_code=400, detail=f"Invalid {field} format")


class VendorCampaignService:
    """
    Service for vendor-facing campaign operations.

    Reads/writes: ad_campaigns, ad_creatives, ad_events, ad_leads
    """

    def __init__(self, db):
        self.db = db
        self.campaigns = db["ad_campaigns"]
        self.creatives = db["ad_creatives"]
        self.ad_events = db["ad_events"]
        self.ad_leads = db["ad_leads"]

    # ─── Campaign CRUD ───────────────────────────────────────────────

    async def create_campaign(
        self,
        vendor_id: str,
        vendor_email: str,
        vendor_name: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a new draft campaign for an advertising vendor."""
        # ── Profile Completeness Gate (Phase 10) ──────────────────
        from app.services.vendor_signup_service import check_profile_completeness
        from app.services.ad_platform_config_service import AdPlatformConfigService

        config_svc = AdPlatformConfigService(self.db)
        config = await config_svc.get_config()

        if config.get("require_profile_completion", True):
            vendor_doc = await self.db["users"].find_one({"_id": ObjectId(vendor_id)})
            if not vendor_doc:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Vendor account not found")
            completeness = check_profile_completeness(vendor_doc)
            if not completeness["is_complete"]:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "profile_incomplete",
                        "message": (
                            "Please complete your business profile before "
                            "creating campaigns."
                        ),
                        "missing_fields": completeness["missing_fields"],
                        "completion_percentage": completeness["completion_percentage"],
                    },
                )
        # ──────────────────────────────────────────────────────────

        now = datetime.now(timezone.utc)

        campaign = {
            "vendor_id": vendor_id,
            "vendor_email": vendor_email,
            "vendor_name": vendor_name,
            "campaign_name": data["campaign_name"],
            "campaign_description": data.get("campaign_description"),
            "goal": data.get("goal", "profile_visits"),
            "status": CampaignStatus.DRAFT.value,
            # Targeting
            "target_categories": data.get("target_categories", []),
            "target_wedding_stages": data.get("target_wedding_stages", []),
            "target_placements": data.get("target_placements", []),
            "target_regions": data.get("target_regions", []),
            "target_budget_min": data.get("target_budget_min"),
            "target_budget_max": data.get("target_budget_max"),
            # Budget
            "daily_budget": data.get("daily_budget", 0.0),
            "total_budget": data.get("total_budget", 0.0),
            "budget_consumed": 0.0,
            "pacing_strategy": data.get("pacing_strategy", "even"),
            # Schedule
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            # Bidding (placeholder for free tier)
            "bid_amount": 0.0,
            "bid_strategy": "fixed",
            # Performance counters
            "quality_score": 50,
            "impression_count": 0,
            "click_count": 0,
            "lead_count": 0,
            "conversion_count": 0,
            # Creatives
            "primary_creative_id": None,
            "creative_ids": [],
            # Review
            "submitted_at": None,
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
            # Vendor info for planner-facing cards
            "vendor_category": data.get("vendor_category"),
            "vendor_service_area": data.get("vendor_service_area"),
            "vendor_logo_url": data.get("vendor_logo_url"),
            # System
            "created_by": vendor_email,
            "metadata": data.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }

        result = await self.campaigns.insert_one(campaign)
        campaign["_id"] = str(result.inserted_id)

        logger.info(f"Created campaign {result.inserted_id} for vendor {vendor_id} ({vendor_name})")
        return campaign

    async def get_campaign(
        self,
        campaign_id: str,
        vendor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a single campaign. If vendor_id provided, enforces access control."""
        oid = _to_oid(campaign_id, "campaign_id")
        query: Dict[str, Any] = {"_id": oid}
        if vendor_id:
            query["vendor_id"] = vendor_id

        doc = await self.campaigns.find_one(query)
        if doc is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return _serialize(doc)

    async def list_campaigns(
        self,
        vendor_id: str,
        status_filter: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List a vendor's campaigns."""
        query: Dict[str, Any] = {"vendor_id": vendor_id}
        if status_filter:
            query["status"] = status_filter

        results = []
        async for doc in (
            self.campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
        ):
            results.append(_serialize(doc))
        return results

    async def update_campaign(
        self,
        campaign_id: str,
        vendor_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a draft campaign. Only allowed when status is 'draft'."""
        oid = _to_oid(campaign_id, "campaign_id")

        existing = await self.campaigns.find_one({"_id": oid, "vendor_id": vendor_id})
        if existing is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if existing.get("status") != CampaignStatus.DRAFT.value:
            raise HTTPException(status_code=400, detail="Only draft campaigns can be edited")

        # Strip immutable fields
        for key in ("_id", "vendor_id", "vendor_email", "vendor_name",
                     "created_by", "created_at", "status"):
            updates.pop(key, None)

        updates["updated_at"] = datetime.now(timezone.utc)

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "vendor_id": vendor_id},
            {"$set": updates},
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        logger.info(f"Updated campaign {campaign_id}")
        return _serialize(updated)

    async def delete_campaign(self, campaign_id: str, vendor_id: str) -> Dict[str, Any]:
        """Delete a draft campaign (hard delete, only drafts)."""
        oid = _to_oid(campaign_id, "campaign_id")

        existing = await self.campaigns.find_one({"_id": oid, "vendor_id": vendor_id})
        if existing is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if existing.get("status") != CampaignStatus.DRAFT.value:
            raise HTTPException(status_code=400, detail="Only draft campaigns can be deleted")

        await self.campaigns.delete_one({"_id": oid})
        logger.info(f"Deleted draft campaign {campaign_id}")
        return {"deleted": True, "campaign_id": campaign_id}

    # ─── Campaign Submission ─────────────────────────────────────────

    async def submit_for_review(self, campaign_id: str, vendor_id: str) -> Dict[str, Any]:
        """Submit a draft campaign for root admin review."""
        oid = _to_oid(campaign_id, "campaign_id")

        campaign = await self.campaigns.find_one({"_id": oid, "vendor_id": vendor_id})
        if campaign is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.get("status") != CampaignStatus.DRAFT.value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit campaign with status '{campaign.get('status')}'"
            )

        # Validate readiness
        errors = self._validate_campaign_ready(campaign)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"Campaign not ready for review: {'; '.join(errors)}"
            )

        now = datetime.now(timezone.utc)
        updated = await self.campaigns.find_one_and_update(
            {"_id": oid},
            {"$set": {
                "status": CampaignStatus.PENDING_REVIEW.value,
                "submitted_at": now,
                "updated_at": now,
            }},
            return_document=True,
        )

        logger.info(f"Campaign {campaign_id} submitted for review by vendor {vendor_id}")
        return _serialize(updated)

    def _validate_campaign_ready(self, campaign: Dict[str, Any]) -> List[str]:
        """Check if campaign has everything needed for review submission."""
        errors = []
        if not campaign.get("campaign_name"):
            errors.append("Campaign name is required")
        if not campaign.get("primary_creative_id"):
            errors.append("At least one primary creative is required")
        if not campaign.get("vendor_category"):
            errors.append("Vendor category is required")
        if not campaign.get("target_regions"):
            errors.append("At least one target region is required")
        return errors

    async def pause_campaign(self, campaign_id: str, vendor_id: str) -> Dict[str, Any]:
        """Vendor pauses their active campaign."""
        oid = _to_oid(campaign_id, "campaign_id")

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "vendor_id": vendor_id, "status": CampaignStatus.ACTIVE.value},
            {"$set": {"status": CampaignStatus.PAUSED.value, "updated_at": datetime.now(timezone.utc)}},
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=400, detail="Campaign not found or not active")

        logger.info(f"Campaign {campaign_id} paused by vendor {vendor_id}")
        return _serialize(updated)

    # ─── Creative CRUD ───────────────────────────────────────────────

    async def create_creative(
        self,
        campaign_id: str,
        vendor_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create a new creative for a campaign.
        Images uploaded separately via AdUploadService to vendor-ad-assets R2 bucket.
        """
        # Verify campaign ownership
        campaign = await self.get_campaign(campaign_id, vendor_id)
        now = datetime.now(timezone.utc)

        creative = {
            "campaign_id": campaign_id,
            "vendor_id": vendor_id,
            "creative_type": data.get("creative_type", "image"),
            "image_url": data.get("image_url"),  # CDN URL from vendor-ad-assets R2 bucket
            "image_alt_text": data.get("image_alt_text"),
            "headline": data["headline"],
            "description": data["description"],
            "offer": data.get("offer"),
            "call_to_action": data.get("call_to_action", "View Portfolio"),
            "review_status": CreativeReviewStatus.PENDING.value,
            "submitted_at": now,
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
            "is_primary": data.get("is_primary", False),
            "metadata": data.get("metadata", {}),
            "created_at": now,
            "updated_at": now,
        }

        result = await self.creatives.insert_one(creative)
        creative_id = str(result.inserted_id)
        creative["_id"] = creative_id

        # Add to campaign's creative list
        update_fields: Dict[str, Any] = {
            "$addToSet": {"creative_ids": creative_id},
            "$set": {"updated_at": now},
        }
        # If this is the first or primary creative, set it as primary
        if data.get("is_primary", False) or not campaign.get("primary_creative_id"):
            update_fields["$set"]["primary_creative_id"] = creative_id

        await self.campaigns.update_one({"_id": ObjectId(campaign_id)}, update_fields)

        logger.info(f"Created creative {creative_id} for campaign {campaign_id}")
        return creative

    async def list_creatives(
        self, campaign_id: str, vendor_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List creatives for a campaign."""
        query: Dict[str, Any] = {"campaign_id": campaign_id}
        if vendor_id:
            query["vendor_id"] = vendor_id

        results = []
        async for doc in self.creatives.find(query).sort("created_at", -1):
            results.append(_serialize(doc))
        return results

    async def get_creative(
        self, creative_id: str, vendor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a single creative."""
        oid = _to_oid(creative_id, "creative_id")
        query: Dict[str, Any] = {"_id": oid}
        if vendor_id:
            query["vendor_id"] = vendor_id

        doc = await self.creatives.find_one(query)
        if doc is None:
            raise HTTPException(status_code=404, detail="Creative not found")
        return _serialize(doc)

    async def update_creative(
        self, creative_id: str, vendor_id: str, updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update a creative. If content changes on an approved creative,
        it goes back to pending review (creative freeze policy).
        """
        oid = _to_oid(creative_id, "creative_id")

        existing = await self.creatives.find_one({"_id": oid, "vendor_id": vendor_id})
        if existing is None:
            raise HTTPException(status_code=404, detail="Creative not found")

        for key in ("_id", "campaign_id", "vendor_id", "created_at"):
            updates.pop(key, None)

        updates["updated_at"] = datetime.now(timezone.utc)

        # If creative content changed and was approved, reset to pending review
        content_fields = {"headline", "description", "offer", "call_to_action", "image_url"}
        content_changed = any(k in updates for k in content_fields)
        if content_changed and existing.get("review_status") == CreativeReviewStatus.APPROVED.value:
            updates["review_status"] = CreativeReviewStatus.PENDING.value
            updates["submitted_at"] = datetime.now(timezone.utc)

        updated = await self.creatives.find_one_and_update(
            {"_id": oid, "vendor_id": vendor_id},
            {"$set": updates},
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Creative not found")

        logger.info(f"Updated creative {creative_id}")
        return _serialize(updated)

    async def set_primary_creative(
        self, campaign_id: str, creative_id: str, vendor_id: str,
    ) -> Dict[str, Any]:
        """Set a creative as the campaign's primary."""
        creative = await self.get_creative(creative_id, vendor_id)
        if creative["campaign_id"] != campaign_id:
            raise HTTPException(status_code=400, detail="Creative does not belong to this campaign")

        # Unset existing primary
        await self.creatives.update_many(
            {"campaign_id": campaign_id, "is_primary": True},
            {"$set": {"is_primary": False}},
        )

        # Set new primary
        await self.creatives.update_one(
            {"_id": ObjectId(creative_id)},
            {"$set": {"is_primary": True}},
        )

        # Update campaign
        updated = await self.campaigns.find_one_and_update(
            {"_id": ObjectId(campaign_id), "vendor_id": vendor_id},
            {"$set": {"primary_creative_id": creative_id, "updated_at": datetime.now(timezone.utc)}},
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        logger.info(f"Set creative {creative_id} as primary for campaign {campaign_id}")
        return _serialize(updated)

    # ─── Leads ───────────────────────────────────────────────────────

    async def get_vendor_leads(
        self,
        vendor_id: str,
        status_filter: Optional[str] = None,
        lead_type_filter: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get leads for all of a vendor's campaigns."""
        # Get all campaign IDs for this vendor
        campaign_ids = []
        async for campaign in self.campaigns.find({"vendor_id": vendor_id}, {"_id": 1}):
            campaign_ids.append(str(campaign["_id"]))

        if not campaign_ids:
            return []

        query: Dict[str, Any] = {"campaign_id": {"$in": campaign_ids}}
        if status_filter:
            query["status"] = status_filter
        if lead_type_filter:
            query["lead_type"] = lead_type_filter

        results = []
        async for doc in (
            self.ad_leads.find(query).sort("created_at", -1).skip(skip).limit(limit)
        ):
            results.append(_serialize(doc))
        return results

    # ─── Campaign Stats ──────────────────────────────────────────────

    async def get_campaign_stats(
        self, campaign_id: str, vendor_id: str, days: int = 30,
    ) -> Dict[str, Any]:
        """Get performance stats for a campaign from campaign_day_stats rollups."""
        campaign = await self.get_campaign(campaign_id, vendor_id)

        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        daily_stats = []
        async for doc in (
            self.db["campaign_day_stats"]
            .find({"campaign_id": campaign_id, "date": {"$gte": period_start}})
            .sort("date", -1)
        ):
            daily_stats.append(_serialize(doc))

        impressions = campaign.get("impression_count", 0)
        clicks = campaign.get("click_count", 0)
        return {
            "campaign_id": campaign_id,
            "period_days": days,
            "totals": {
                "impressions": impressions,
                "clicks": clicks,
                "leads": campaign.get("lead_count", 0),
                "conversions": campaign.get("conversion_count", 0),
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0.0,
            },
            "daily_series": daily_stats,
        }

    # ─── Ad Serving ──────────────────────────────────────────────────

    async def get_servable_campaigns(
        self,
        planner_location: Optional[str] = None,
        categories: Optional[List[str]] = None,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Get active campaigns eligible for the planner rail.

        Replaces the old get_sponsored_vendors() query.
        Filters by: active status, date range, location match.
        Deduplicates by vendor_id (one campaign per vendor).
        Sorted by quality_score descending.
        """
        now = datetime.now(timezone.utc)

        query: Dict[str, Any] = {
            "status": CampaignStatus.ACTIVE.value,
            "primary_creative_id": {"$ne": None},
            "$and": [
                {"$or": [
                    {"start_date": {"$lte": now}},
                    {"start_date": {"$in": [None]}},
                    {"start_date": {"$exists": False}},
                ]},
                {"$or": [
                    {"end_date": {"$gte": now}},
                    {"end_date": {"$in": [None]}},
                    {"end_date": {"$exists": False}},
                ]},
            ],
        }

        # Location targeting
        if planner_location:
            query["$and"].append({
                "$or": [
                    {"target_regions": {"$in": [planner_location]}},
                    {"target_regions": {"$size": 0}},  # Empty = all regions
                ]
            })

        # Category targeting
        if categories:
            query["$and"].append({
                "$or": [
                    {"target_categories": {"$in": categories}},
                    {"target_categories": {"$size": 0}},
                ]
            })

        # Fetch more than needed for deduplication, then deduplicate by vendor_id
        raw_results = []
        async for doc in (
            self.campaigns.find(query).sort("quality_score", -1).limit(limit * 3)
        ):
            raw_results.append(_serialize(doc))

        # Deduplicate: one campaign per vendor (highest quality_score wins)
        seen_vendors = set()
        deduped = []
        for campaign in raw_results:
            vid = campaign.get("vendor_id")
            if vid not in seen_vendors:
                seen_vendors.add(vid)
                # Enrich with primary creative
                creative_id = campaign.get("primary_creative_id")
                if creative_id:
                    try:
                        creative = await self.creatives.find_one(
                            {"_id": ObjectId(creative_id)},
                            {"headline": 1, "description": 1, "offer": 1,
                             "call_to_action": 1, "image_url": 1, "image_alt_text": 1}
                        )
                        if creative:
                            campaign["creative"] = _serialize(creative)
                    except Exception as e:
                        logger.warning(f"Failed to load creative {creative_id}: {e}")
                deduped.append(campaign)
                if len(deduped) >= limit:
                    break

        return deduped

    # ─── Campaign Expiration (called by nightly cron) ────────────────

    async def complete_expired_campaigns(self) -> int:
        """
        Auto-complete campaigns past their end_date.
        Called by the nightly rollup scheduler.
        Returns count of campaigns completed.
        """
        now = datetime.now(timezone.utc)

        result = await self.campaigns.update_many(
            {
                "status": CampaignStatus.ACTIVE.value,
                "end_date": {"$lt": now, "$ne": None},
            },
            {"$set": {
                "status": CampaignStatus.COMPLETED.value,
                "updated_at": now,
            }},
        )

        if result.modified_count > 0:
            logger.info(f"Auto-completed {result.modified_count} expired campaigns")

        return result.modified_count
