"""
Admin Campaign Service

Root admin operations for the advertising campaign platform.
Handles campaign/creative review workflow, campaign monitoring,
revenue tracking, vendor account management, and fraud signals.

This is the admin side of the campaign platform. The vendor side
is in vendor_campaign_service.py.

PRD Reference: Section 6.8 (Admin Moderation Console)
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


class AdminCampaignService:
    """
    Service for root-admin campaign operations.

    Reads/writes: ad_campaigns, ad_creatives, ad_fraud_signals,
                  vendor_ad_billing, ad_events, ad_leads, users
    """

    def __init__(self, db):
        self.db = db
        self.campaigns = db["ad_campaigns"]
        self.creatives = db["ad_creatives"]
        self.fraud_signals = db["ad_fraud_signals"]
        self.billing = db["vendor_ad_billing"]
        self.ad_events = db["ad_events"]
        self.ad_leads = db["ad_leads"]
        self.users = db["users"]

    # ─── Review Queue ─────────────────────────────────────────────

    async def get_review_queue(
        self,
        status_filter: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get campaigns pending review, with their primary creative inlined.

        Default: pending_review campaigns sorted by submitted_at ascending
        (oldest first, FIFO review).
        """
        query: Dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter
        else:
            query["status"] = CampaignStatus.PENDING_REVIEW.value

        results = []
        async for doc in (
            self.campaigns.find(query)
            .sort("submitted_at", 1)  # FIFO: oldest submissions first
            .skip(skip)
            .limit(limit)
        ):
            campaign = _serialize(doc)

            # Inline primary creative for review card display
            creative_id = campaign.get("primary_creative_id")
            if creative_id:
                try:
                    creative = await self.creatives.find_one(
                        {"_id": ObjectId(creative_id)}
                    )
                    if creative:
                        campaign["primary_creative"] = _serialize(creative)
                except Exception as e:
                    logger.warning(f"Failed to load creative {creative_id}: {e}")

            results.append(campaign)

        return results

    async def get_review_counts(self) -> Dict[str, int]:
        """
        Get status counts for the review dashboard.

        Returns counts for: pending_review, active, paused, rejected, draft, completed.
        """
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]

        counts: Dict[str, int] = {
            "pending_review": 0,
            "active": 0,
            "paused": 0,
            "rejected": 0,
            "draft": 0,
            "completed": 0,
        }

        async for doc in self.campaigns.aggregate(pipeline):
            status_val = doc["_id"]
            if status_val in counts:
                counts[status_val] = doc["count"]

        counts["total"] = sum(counts.values())
        return counts

    # ─── Campaign Review Actions ──────────────────────────────────

    async def approve_campaign(
        self,
        campaign_id: str,
        admin_email: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending_review campaign. Sets status to active.

        Also auto-approves all pending creatives for this campaign.
        """
        oid = _to_oid(campaign_id, "campaign_id")
        now = datetime.now(timezone.utc)

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "status": CampaignStatus.PENDING_REVIEW.value},
            {
                "$set": {
                    "status": CampaignStatus.ACTIVE.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": review_notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400,
                detail="Campaign not found or not in pending_review status",
            )

        # Auto-approve all pending creatives for this campaign
        await self.creatives.update_many(
            {
                "campaign_id": campaign_id,
                "review_status": CreativeReviewStatus.PENDING.value,
            },
            {
                "$set": {
                    "review_status": CreativeReviewStatus.APPROVED.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "updated_at": now,
                }
            },
        )

        logger.info(f"Campaign {campaign_id} approved by {admin_email}")

        # Push notification to vendor
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_campaign_approved(
                vendor_email=updated.get("vendor_email", ""),
                campaign_name=updated.get("campaign_name", campaign_id),
            )
        except Exception as e:
            logger.warning(f"Failed to push-notify vendor on campaign approval: {e}")

        return _serialize(updated)

    async def reject_campaign(
        self,
        campaign_id: str,
        admin_email: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a pending_review campaign."""
        oid = _to_oid(campaign_id, "campaign_id")
        now = datetime.now(timezone.utc)

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "status": CampaignStatus.PENDING_REVIEW.value},
            {
                "$set": {
                    "status": CampaignStatus.REJECTED.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": review_notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400,
                detail="Campaign not found or not in pending_review status",
            )

        logger.info(f"Campaign {campaign_id} rejected by {admin_email}")

        # Push notification to vendor
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_campaign_rejected(
                vendor_email=updated.get("vendor_email", ""),
                campaign_name=updated.get("campaign_name", campaign_id),
                reason=review_notes,
            )
        except Exception as e:
            logger.warning(f"Failed to push-notify vendor on campaign rejection: {e}")

        return _serialize(updated)

    async def request_changes(
        self,
        campaign_id: str,
        admin_email: str,
        review_notes: str,
    ) -> Dict[str, Any]:
        """
        Return a pending_review campaign to the vendor for changes.
        Sets status back to draft so vendor can edit and resubmit.
        """
        if not review_notes or not review_notes.strip():
            raise HTTPException(
                status_code=400,
                detail="Review notes are required when requesting changes",
            )

        oid = _to_oid(campaign_id, "campaign_id")
        now = datetime.now(timezone.utc)

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "status": CampaignStatus.PENDING_REVIEW.value},
            {
                "$set": {
                    "status": CampaignStatus.DRAFT.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": review_notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400,
                detail="Campaign not found or not in pending_review status",
            )

        logger.info(
            f"Campaign {campaign_id} returned to vendor with change requests by {admin_email}"
        )

        # Push notification to vendor
        try:
            from app.services.vendor_notification_service import (
                VendorNotificationService,
            )

            vns = VendorNotificationService()
            await vns.notify_vendor_campaign_changes_requested(
                vendor_email=updated.get("vendor_email", ""),
                campaign_name=updated.get("campaign_name", campaign_id),
                notes=review_notes,
            )
        except Exception as e:
            logger.warning(f"Failed to push-notify vendor on change request: {e}")

        return _serialize(updated)

    # ─── Creative Review ──────────────────────────────────────────

    async def get_creative_review_queue(
        self,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get creatives pending review."""
        results = []
        async for doc in (
            self.creatives.find({"review_status": CreativeReviewStatus.PENDING.value})
            .sort("submitted_at", 1)
            .skip(skip)
            .limit(limit)
        ):
            results.append(_serialize(doc))
        return results

    async def approve_creative(
        self,
        creative_id: str,
        admin_email: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve a pending creative."""
        oid = _to_oid(creative_id, "creative_id")
        now = datetime.now(timezone.utc)

        updated = await self.creatives.find_one_and_update(
            {"_id": oid, "review_status": CreativeReviewStatus.PENDING.value},
            {
                "$set": {
                    "review_status": CreativeReviewStatus.APPROVED.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": review_notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400, detail="Creative not found or not pending review"
            )

        logger.info(f"Creative {creative_id} approved by {admin_email}")
        return _serialize(updated)

    async def reject_creative(
        self,
        creative_id: str,
        admin_email: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reject a pending creative."""
        oid = _to_oid(creative_id, "creative_id")
        now = datetime.now(timezone.utc)

        updated = await self.creatives.find_one_and_update(
            {"_id": oid, "review_status": CreativeReviewStatus.PENDING.value},
            {
                "$set": {
                    "review_status": CreativeReviewStatus.REJECTED.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": review_notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400, detail="Creative not found or not pending review"
            )

        logger.info(f"Creative {creative_id} rejected by {admin_email}")
        return _serialize(updated)

    # ─── Campaign Monitoring (Admin View) ─────────────────────────

    async def list_all_campaigns(
        self,
        status_filter: Optional[str] = None,
        vendor_id: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """List all campaigns across all vendors (admin view)."""
        query: Dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter
        if vendor_id:
            query["vendor_id"] = vendor_id

        results = []
        async for doc in (
            self.campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)
        ):
            results.append(_serialize(doc))
        return results

    async def admin_pause_campaign(
        self,
        campaign_id: str,
        admin_email: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Admin forcibly pauses an active campaign."""
        oid = _to_oid(campaign_id, "campaign_id")
        now = datetime.now(timezone.utc)

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid, "status": CampaignStatus.ACTIVE.value},
            {
                "$set": {
                    "status": CampaignStatus.PAUSED.value,
                    "review_notes": f"[Admin pause by {admin_email}] {reason or ''}".strip(),
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(
                status_code=400, detail="Campaign not found or not currently active"
            )

        logger.info(f"Campaign {campaign_id} admin-paused by {admin_email}: {reason}")
        return _serialize(updated)

    async def admin_deactivate_campaign(
        self,
        campaign_id: str,
        admin_email: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Admin kills a campaign (sets to rejected regardless of current status).
        Use for policy violations or emergency takedowns.
        """
        oid = _to_oid(campaign_id, "campaign_id")
        now = datetime.now(timezone.utc)

        # Allow deactivation from any non-terminal status
        existing = await self.campaigns.find_one({"_id": oid})
        if existing is None:
            raise HTTPException(status_code=404, detail="Campaign not found")

        terminal_statuses = {
            CampaignStatus.COMPLETED.value,
            CampaignStatus.REJECTED.value,
        }
        if existing.get("status") in terminal_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Campaign already in terminal status: {existing.get('status')}",
            )

        updated = await self.campaigns.find_one_and_update(
            {"_id": oid},
            {
                "$set": {
                    "status": CampaignStatus.REJECTED.value,
                    "reviewed_at": now,
                    "reviewed_by": admin_email,
                    "review_notes": f"[Admin deactivation by {admin_email}] {reason or ''}".strip(),
                    "updated_at": now,
                }
            },
            return_document=True,
        )

        logger.info(f"Campaign {campaign_id} deactivated by {admin_email}: {reason}")
        return _serialize(updated)

    # ─── Revenue & Engagement Dashboard ───────────────────────────

    async def get_revenue_summary(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Revenue summary for the admin dashboard.
        For free tier, this tracks engagement metrics (not actual revenue).
        All spend values are $0.
        """
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Count campaigns by status
        status_counts = await self.get_review_counts()

        # Aggregate engagement from ad_events in the period
        events_pipeline = [
            {"$match": {"created_at": {"$gte": period_start}}},
            {
                "$group": {
                    "_id": None,
                    "total_impressions": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_served"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "total_clicks": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "click"]}, 1, 0]}
                    },
                    "total_leads": {
                        "$sum": {
                            "$cond": [{"$eq": ["$event_type", "lead_created"]}, 1, 0]
                        }
                    },
                    "unique_planners": {"$addToSet": "$planner_id"},
                }
            },
        ]

        engagement = {
            "total_impressions": 0,
            "total_clicks": 0,
            "total_leads": 0,
            "unique_planners": 0,
            "ctr": 0.0,
        }

        async for doc in self.ad_events.aggregate(events_pipeline):
            planners = [p for p in doc.get("unique_planners", []) if p]
            impressions = doc.get("total_impressions", 0)
            clicks = doc.get("total_clicks", 0)
            engagement = {
                "total_impressions": impressions,
                "total_clicks": clicks,
                "total_leads": doc.get("total_leads", 0),
                "unique_planners": len(planners),
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0.0,
            }

        # Count active vendors (distinct vendor_id with at least one active campaign)
        active_vendor_ids = await self.campaigns.distinct(
            "vendor_id",
            {"status": CampaignStatus.ACTIVE.value},
        )

        return {
            "period_days": days,
            "period_start": period_start.isoformat(),
            "campaign_counts": status_counts,
            "engagement": engagement,
            "active_vendors": len(active_vendor_ids),
            "total_revenue": 0.0,  # Free tier — always $0
            "currency": "USD",
        }

    # ─── Planner Feedback ─────────────────────────────────────────

    async def get_planner_feedback(
        self,
        limit: int = 50,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """
        Get planner ad feedback: hidden vendors, suppressed categories,
        reduced frequency requests. Helps admin understand planner sentiment.
        """
        prefs_collection = self.db["planner_ad_preferences"]

        # Planners who have hidden vendors or reduced frequency
        query = {
            "$or": [
                {"hidden_vendor_ids": {"$ne": []}},
                {"hidden_categories": {"$ne": []}},
                {"reduced_frequency": True},
            ]
        }

        results = []
        async for doc in (
            prefs_collection.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        ):
            results.append(_serialize(doc))

        # Summary stats
        total_with_prefs = await prefs_collection.count_documents(query)
        total_hidden = await prefs_collection.count_documents(
            {"hidden_vendor_ids": {"$ne": []}}
        )
        total_reduced = await prefs_collection.count_documents(
            {"reduced_frequency": True}
        )

        return {
            "feedback": results,
            "summary": {
                "planners_with_feedback": total_with_prefs,
                "planners_hiding_vendors": total_hidden,
                "planners_reduced_frequency": total_reduced,
            },
        }

    # ─── Fraud Signals ────────────────────────────────────────────

    async def get_fraud_signals(
        self,
        status_filter: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get fraud/anomaly signals from ad_fraud_signals (7-day TTL)."""
        query: Dict[str, Any] = {}
        if status_filter:
            query["status"] = status_filter

        results = []
        async for doc in (
            self.fraud_signals.find(query)
            .sort("flagged_at", -1)
            .skip(skip)
            .limit(limit)
        ):
            results.append(_serialize(doc))
        return results

    async def update_fraud_signal(
        self,
        signal_id: str,
        admin_email: str,
        status: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update the investigation status of a fraud signal."""
        oid = _to_oid(signal_id, "signal_id")
        now = datetime.now(timezone.utc)

        updated = await self.fraud_signals.find_one_and_update(
            {"_id": oid},
            {
                "$set": {
                    "status": status,
                    "notes": notes,
                    "updated_at": now,
                }
            },
            return_document=True,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Fraud signal not found")

        logger.info(f"Fraud signal {signal_id} updated to {status} by {admin_email}")
        return _serialize(updated)

    # ─── Vendor Account Management ────────────────────────────────

    async def list_vendor_accounts(
        self,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        location_filter: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
        limit: int = 50,
        skip: int = 0,
    ) -> Dict[str, Any]:
        """
        List advertising vendor accounts with advanced filtering.

        Filters:
          - status: account status (pending_approval, active, suspended)
          - category: vendor category (photographer, florist, etc.)
          - location: text search on vendor_location
          - date_from/date_to: created_at range (ISO date strings)
          - search: text search on email or business_name
        """
        query: Dict[str, Any] = {"role": "advertising_vendor"}

        if status_filter:
            query["vendor_account_status"] = status_filter
        if category_filter:
            query["vendor_category"] = category_filter
        if location_filter:
            query["vendor_location"] = {"$regex": location_filter, "$options": "i"}
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"business_name": {"$regex": search, "$options": "i"}},
            ]
        if date_from or date_to:
            date_range_q: Dict[str, Any] = {}
            if date_from:
                try:
                    date_range_q["$gte"] = datetime.fromisoformat(
                        date_from.replace("Z", "+00:00")
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid date_from format: {date_from}. Use ISO 8601 (e.g. 2026-01-01)",
                    )
            if date_to:
                try:
                    date_range_q["$lte"] = datetime.fromisoformat(
                        date_to.replace("Z", "+00:00")
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid date_to format: {date_to}. Use ISO 8601 (e.g. 2026-12-31)",
                    )
            if date_range_q:
                query["created_at"] = date_range_q

        # Validate sort field
        valid_sorts = {
            "created_at",
            "business_name",
            "total_impressions",
            "total_clicks",
            "total_leads",
        }
        if sort_by not in valid_sorts:
            sort_by = "created_at"

        total = await self.users.count_documents(query)

        results = []
        async for doc in (
            self.users.find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        ):
            results.append(_serialize(doc))

        return {
            "items": results,
            "total": total,
            "limit": limit,
            "skip": skip,
        }

    # ─── Batch Vendor Stats (pipeline optimization) ──────────────

    async def get_vendor_stats_batch(
        self,
        vendor_ids: List[str],
        days: int = 30,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute stats for multiple vendors in a single aggregation pipeline
        instead of N+1 individual queries.

        Returns: { vendor_id: { impressions, clicks, leads, ctr, campaigns } }
        """
        if not vendor_ids:
            return {}

        period_start = datetime.now(timezone.utc) - timedelta(days=days)

        # ── 1. Aggregate events by vendor_id ──
        events_pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": period_start},
                    "vendor_id": {"$in": vendor_ids},
                }
            },
            {
                "$group": {
                    "_id": "$vendor_id",
                    "impressions": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_served"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "clicks": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "click"]}, 1, 0]}
                    },
                    "leads": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$in": [
                                        "$event_type",
                                        ["lead_created", "quote_requested"],
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]

        stats: Dict[str, Dict[str, Any]] = {}
        async for doc in self.ad_events.aggregate(events_pipeline):
            vid = doc["_id"]
            impressions = doc.get("impressions", 0)
            clicks = doc.get("clicks", 0)
            stats[vid] = {
                "impressions": impressions,
                "clicks": clicks,
                "leads": doc.get("leads", 0),
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0.0,
            }

        # ── 2. Count campaigns per vendor ──
        campaign_pipeline = [
            {
                "$match": {
                    "vendor_id": {"$in": vendor_ids},
                }
            },
            {
                "$group": {
                    "_id": "$vendor_id",
                    "total_campaigns": {"$sum": 1},
                    "active_campaigns": {
                        "$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}
                    },
                }
            },
        ]

        async for doc in self.campaigns.aggregate(campaign_pipeline):
            vid = doc["_id"]
            if vid not in stats:
                stats[vid] = {"impressions": 0, "clicks": 0, "leads": 0, "ctr": 0.0}
            stats[vid]["total_campaigns"] = doc.get("total_campaigns", 0)
            stats[vid]["active_campaigns"] = doc.get("active_campaigns", 0)

        # Fill in defaults for vendors with no activity
        for vid in vendor_ids:
            if vid not in stats:
                stats[vid] = {
                    "impressions": 0,
                    "clicks": 0,
                    "leads": 0,
                    "ctr": 0.0,
                    "total_campaigns": 0,
                    "active_campaigns": 0,
                }

        return stats

    # ─── Event Query Engine (Elasticsearch-style) ────────────────

    async def query_events(
        self,
        event_types: Optional[List[str]] = None,
        campaign_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        planner_id: Optional[str] = None,
        session_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
        limit: int = 100,
        skip: int = 0,
        aggregate_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Flexible event search with filtering, sorting, pagination, and optional aggregation.

        Supports Elasticsearch-style queries over the ad_events collection:
        - Filter by event_type, campaign_id, vendor_id, planner_id, session_id
        - Date range filtering
        - Sorting by any field
        - Pagination with total count
        - Optional aggregation by a field (returns counts instead of raw docs)

        Returns: { items: [...], total: int, aggregations?: {...} }
        """
        query: Dict[str, Any] = {}

        if event_types:
            query["event_type"] = {"$in": event_types}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if vendor_id:
            query["vendor_id"] = vendor_id
        if planner_id:
            query["planner_id"] = planner_id
        if session_id:
            query["session_id"] = session_id

        # Date range
        if date_from or date_to:
            date_range_q: Dict[str, Any] = {}
            if date_from:
                try:
                    date_range_q["$gte"] = datetime.fromisoformat(
                        date_from.replace("Z", "+00:00")
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid date_from format: {date_from}. Use ISO 8601 (e.g. 2026-01-01)",
                    )
            if date_to:
                try:
                    date_range_q["$lte"] = datetime.fromisoformat(
                        date_to.replace("Z", "+00:00")
                    )
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid date_to format: {date_to}. Use ISO 8601 (e.g. 2026-12-31)",
                    )
            if date_range_q:
                query["created_at"] = date_range_q

        # If aggregation requested, return grouped counts
        if aggregate_by and aggregate_by in {
            "event_type",
            "campaign_id",
            "vendor_id",
            "planner_id",
            "placement",
        }:
            agg_pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": f"${aggregate_by}",
                        "count": {"$sum": 1},
                        "first_event": {"$min": "$created_at"},
                        "last_event": {"$max": "$created_at"},
                    }
                },
                {"$sort": {"count": -1}},
                {"$limit": limit},
            ]
            aggregations = []
            async for doc in self.ad_events.aggregate(agg_pipeline):
                aggregations.append(
                    {
                        "key": doc["_id"],
                        "count": doc["count"],
                        "first_event": doc.get("first_event", "").isoformat()
                        if doc.get("first_event")
                        else None,
                        "last_event": doc.get("last_event", "").isoformat()
                        if doc.get("last_event")
                        else None,
                    }
                )

            return {
                "aggregations": aggregations,
                "aggregate_by": aggregate_by,
                "total_buckets": len(aggregations),
            }

        # Standard query with pagination
        total = await self.ad_events.count_documents(query)

        # Validate sort field
        valid_sorts = {
            "created_at",
            "event_type",
            "campaign_id",
            "vendor_id",
            "planner_id",
        }
        if sort_by not in valid_sorts:
            sort_by = "created_at"

        items = []
        async for doc in (
            self.ad_events.find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        ):
            items.append(_serialize(doc))

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "skip": skip,
        }

    # ─── Bulk Vendor Operations ──────────────────────────────────

    async def bulk_create_vendor_accounts(
        self,
        vendors: List[Dict[str, Any]],
        admin_email: str,
    ) -> Dict[str, Any]:
        """
        Create multiple advertising vendor accounts in one operation.

        Each vendor dict should have at minimum:
            - email: str (unique, required)
            - business_name: str (required)
            - category: str (optional)
            - location: str (optional)

        Returns summary with created/failed/skipped counts and details.
        """
        now = datetime.now(timezone.utc)
        created = []
        failed = []
        skipped = []

        for i, vendor_data in enumerate(vendors):
            email = vendor_data.get("email", "").strip().lower()
            business_name = vendor_data.get("business_name", "").strip()

            if not email or not business_name:
                failed.append(
                    {
                        "index": i,
                        "email": email or "(missing)",
                        "reason": "Missing required fields: email and business_name",
                    }
                )
                continue

            # Check if vendor already exists
            existing = await self.users.find_one({"email": email})
            if existing:
                skipped.append(
                    {
                        "index": i,
                        "email": email,
                        "reason": "Vendor account already exists",
                    }
                )
                continue

            try:
                vendor_doc = {
                    "email": email,
                    "business_name": business_name,
                    "role": "advertising_vendor",
                    "vendor_account_status": "pending_approval",
                    "vendor_category": vendor_data.get("category", ""),
                    "vendor_location": vendor_data.get("location", ""),
                    "vendor_phone": vendor_data.get("phone", ""),
                    "vendor_website": vendor_data.get("website", ""),
                    "created_at": now,
                    "updated_at": now,
                    "created_by": admin_email,
                    "is_free_tier": vendor_data.get("is_free_tier", False),
                    "total_campaigns": 0,
                    "total_impressions": 0,
                    "total_clicks": 0,
                    "total_leads": 0,
                }
                result = await self.users.insert_one(vendor_doc)
                vendor_doc["_id"] = str(result.inserted_id)
                created.append(
                    {
                        "index": i,
                        "email": email,
                        "business_name": business_name,
                        "_id": vendor_doc["_id"],
                    }
                )
            except Exception as e:
                failed.append(
                    {
                        "index": i,
                        "email": email,
                        "reason": str(e),
                    }
                )

        logger.info(
            f"Bulk vendor create by {admin_email}: "
            f"{len(created)} created, {len(skipped)} skipped, {len(failed)} failed"
        )
        return {
            "total_submitted": len(vendors),
            "created": len(created),
            "skipped": len(skipped),
            "failed": len(failed),
            "details": {
                "created": created,
                "skipped": skipped,
                "failed": failed,
            },
        }

    # ─── Platform Config ──────────────────────────────────────────

    async def get_platform_config(self) -> Dict[str, Any]:
        """Get the advertising platform feature flag / config."""
        config = await self.db["ad_feature_flags"].find_one(
            {"feature_key": "sponsored_vendors"}
        )
        if config is None:
            # Return defaults if no config doc exists
            return {
                "feature_key": "sponsored_vendors",
                "is_enabled": False,
                "config": {
                    "max_sponsored_per_page": 3,
                    "show_sponsored_badge": True,
                    "show_sponsored_label": True,
                    "enable_tracking": True,
                    "min_priority_threshold": 1,
                    "impressions_per_session_limit": 5,
                    "require_review": True,
                    "auto_approve_returning_vendors": False,
                    "review_sla_hours": 48,
                },
            }
        return _serialize(config)

    async def update_platform_config(
        self,
        admin_email: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update advertising platform configuration."""
        now = datetime.now(timezone.utc)

        updated = await self.db["ad_feature_flags"].find_one_and_update(
            {"feature_key": "sponsored_vendors"},
            {
                "$set": {
                    **updates,
                    "enabled_by": admin_email,
                    "enabled_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
            return_document=True,
        )

        logger.info(f"Platform config updated by {admin_email}")
        return _serialize(updated)
