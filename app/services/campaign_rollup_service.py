"""
Campaign Rollup Service

Computes pre-aggregated daily rollups from raw ad_events into:
- campaign_day_stats: Per-campaign daily metrics (replaces vendor-centric ad_stats_daily)
- placement_day_stats: Per-placement daily metrics (new)

This is the NEW campaign-centric rollup service. The OLD ad_rollup_service.py
rolls up by sponsored_vendor_id into ad_stats_daily and will be deprecated
once the campaign platform is fully live (Phase 5).

Key difference from old service:
- Groups by campaign_id (not sponsored_vendor_id)
- Writes to campaign_day_stats (not ad_stats_daily)
- Also writes placement_day_stats (new collection)
- Handles both legacy events (with sponsored_vendor_id) and new events (with campaign_id)

Designed to run as a nightly cron job or on-demand via admin button.

PRD Reference: Section 3.5 (Updated Rollup Service)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from bson import ObjectId

logger = logging.getLogger(__name__)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId _id to string for JSON serialization."""
    if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


class CampaignRollupService:
    """
    Service for computing campaign-centric daily rollups.

    Reads from: ad_events (filtered to events with campaign_id)
    Writes to: campaign_day_stats, placement_day_stats
    """

    def __init__(self, db):
        self.db = db
        self.ad_events = db["ad_events"]
        self.ad_leads = db["ad_leads"]
        self.campaign_day_stats = db["campaign_day_stats"]
        self.placement_day_stats = db["placement_day_stats"]

    # ─── Campaign Day Stats Rollup ────────────────────────────────

    async def compute_campaign_rollup(
        self,
        target_date: Optional[datetime] = None,
    ) -> int:
        """
        Compute daily rollup per campaign from ad_events with campaign_id.

        Only processes events that have a campaign_id field (new platform events).
        Legacy events without campaign_id are handled by the old ad_rollup_service.

        Idempotent: safe to re-run (upserts by date + campaign_id).

        Args:
            target_date: Date to compute (defaults to yesterday UTC)

        Returns:
            Number of campaign_day_stats documents upserted
        """
        day_start, day_end = self._get_day_boundaries(target_date)

        logger.info(f"Computing campaign rollup for {day_start.strftime('%Y-%m-%d')}")

        # ── Stage 1: Aggregate ad_events by campaign_id ──
        events_pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": day_start, "$lt": day_end},
                    "campaign_id": {"$ne": None, "$exists": True},
                }
            },
            {
                "$group": {
                    "_id": "$campaign_id",
                    # Event counts
                    "impression_served": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_served"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "click": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "click"]}, 1, 0]}
                    },
                    "lead_created": {
                        "$sum": {
                            "$cond": [{"$eq": ["$event_type", "lead_created"]}, 1, 0]
                        }
                    },
                    "vendor_profile_view": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_profile_view"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "vendor_added_to_directory": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_added_to_directory"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "vendor_added_to_wedding": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_added_to_wedding"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "dismiss": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", "dismiss"]}, 1, 0]}
                    },
                    "contact_click": {
                        "$sum": {
                            "$cond": [{"$eq": ["$event_type", "contact_click"]}, 1, 0]
                        }
                    },
                    # Unique reach
                    "unique_planners_set": {"$addToSet": "$planner_id"},
                    "unique_weddings_set": {"$addToSet": "$wedding_id"},
                    # Hourly distributions
                    "hourly_impressions_raw": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_served"]},
                                {"$hour": "$created_at"},
                                "$$REMOVE",
                            ]
                        }
                    },
                    "hourly_clicks_raw": {
                        "$push": {
                            "$cond": [
                                {"$eq": ["$event_type", "click"]},
                                {"$hour": "$created_at"},
                                "$$REMOVE",
                            ]
                        }
                    },
                }
            },
        ]

        campaign_rollups: Dict[str, Dict[str, Any]] = {}

        async for doc in self.ad_events.aggregate(events_pipeline):
            campaign_id = doc["_id"]

            hourly_impressions = self._build_hourly_array(
                doc.get("hourly_impressions_raw", [])
            )
            hourly_clicks = self._build_hourly_array(doc.get("hourly_clicks_raw", []))

            impressions = doc.get("impression_served", 0)
            clicks = doc.get("click", 0)

            unique_planners = [p for p in doc.get("unique_planners_set", []) if p]
            unique_weddings = [w for w in doc.get("unique_weddings_set", []) if w]

            campaign_rollups[campaign_id] = {
                "date": day_start,
                "campaign_id": campaign_id,
                "vendor_id": "",  # Will be enriched below
                "events": {
                    "impression_served": impressions,
                    "click": clicks,
                    "lead_created": doc.get("lead_created", 0),
                    "vendor_profile_view": doc.get("vendor_profile_view", 0),
                    "vendor_added_to_directory": doc.get(
                        "vendor_added_to_directory", 0
                    ),
                    "vendor_added_to_wedding": doc.get("vendor_added_to_wedding", 0),
                    "dismiss": doc.get("dismiss", 0),
                    "contact_click": doc.get("contact_click", 0),
                },
                "unique_planners": len(unique_planners),
                "unique_weddings": len(unique_weddings),
                "hourly_impressions": hourly_impressions,
                "hourly_clicks": hourly_clicks,
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0.0,
                "conversion_rate": 0.0,
                "spend": 0.0,  # Free tier
                "leads_by_type": {},
                "leads_by_status": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

        # ── Enrich with vendor_id from campaigns collection ──
        if campaign_rollups:
            campaigns_coll = self.db["ad_campaigns"]
            campaign_ids = list(campaign_rollups.keys())

            try:
                oid_list = [ObjectId(cid) for cid in campaign_ids]
                async for campaign in campaigns_coll.find(
                    {"_id": {"$in": oid_list}},
                    {"_id": 1, "vendor_id": 1},
                ):
                    cid = str(campaign["_id"])
                    if cid in campaign_rollups:
                        campaign_rollups[cid]["vendor_id"] = campaign.get(
                            "vendor_id", ""
                        )
            except Exception as e:
                logger.warning(f"Failed to enrich vendor_id for campaign rollups: {e}")

        # ── Stage 2: Aggregate ad_leads by campaign_id ──
        leads_pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": day_start, "$lt": day_end},
                    "campaign_id": {"$ne": None, "$exists": True},
                }
            },
            {
                "$group": {
                    "_id": "$campaign_id",
                    "quote_request": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "quote_request"]}, 1, 0]
                        }
                    },
                    "message": {
                        "$sum": {"$cond": [{"$eq": ["$lead_type", "message"]}, 1, 0]}
                    },
                    "add_to_directory": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "add_to_directory"]}, 1, 0]
                        }
                    },
                    "add_to_wedding": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "add_to_wedding"]}, 1, 0]
                        }
                    },
                    "vendor_invite": {
                        "$sum": {
                            "$cond": [{"$eq": ["$lead_type", "vendor_invite"]}, 1, 0]
                        }
                    },
                    "status_pending": {
                        "$sum": {"$cond": [{"$eq": ["$status", "pending"]}, 1, 0]}
                    },
                    "status_contacted": {
                        "$sum": {"$cond": [{"$eq": ["$status", "contacted"]}, 1, 0]}
                    },
                    "status_responded": {
                        "$sum": {"$cond": [{"$eq": ["$status", "responded"]}, 1, 0]}
                    },
                    "status_converted": {
                        "$sum": {"$cond": [{"$eq": ["$status", "converted"]}, 1, 0]}
                    },
                    "status_closed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "closed"]}, 1, 0]}
                    },
                }
            },
        ]

        async for doc in self.ad_leads.aggregate(leads_pipeline):
            campaign_id = doc["_id"]
            if campaign_id in campaign_rollups:
                campaign_rollups[campaign_id]["leads_by_type"] = {
                    "quote_request": doc.get("quote_request", 0),
                    "message": doc.get("message", 0),
                    "add_to_directory": doc.get("add_to_directory", 0),
                    "add_to_wedding": doc.get("add_to_wedding", 0),
                    "vendor_invite": doc.get("vendor_invite", 0),
                }
                campaign_rollups[campaign_id]["leads_by_status"] = {
                    "pending": doc.get("status_pending", 0),
                    "contacted": doc.get("status_contacted", 0),
                    "responded": doc.get("status_responded", 0),
                    "converted": doc.get("status_converted", 0),
                    "closed": doc.get("status_closed", 0),
                }

        # ── Stage 3: Upsert into campaign_day_stats ──
        upserted = 0
        for campaign_id, rollup in campaign_rollups.items():
            await self.campaign_day_stats.update_one(
                {"date": rollup["date"], "campaign_id": campaign_id},
                {"$set": rollup},
                upsert=True,
            )
            upserted += 1

        logger.info(
            f"Campaign rollup for {day_start.strftime('%Y-%m-%d')}: "
            f"{upserted} campaign_day_stats upserted"
        )

        return upserted

    # ─── Placement Day Stats Rollup ───────────────────────────────

    async def compute_placement_rollup(
        self,
        target_date: Optional[datetime] = None,
    ) -> int:
        """
        Compute daily rollup per placement type from ad_events with campaign_id.

        Writes to placement_day_stats. Platform-level reporting:
        which placements perform best?

        Idempotent: upserts by date + placement.

        Returns:
            Number of placement_day_stats documents upserted
        """
        day_start, day_end = self._get_day_boundaries(target_date)

        logger.info(f"Computing placement rollup for {day_start.strftime('%Y-%m-%d')}")

        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": day_start, "$lt": day_end},
                    "campaign_id": {"$ne": None, "$exists": True},
                }
            },
            {
                "$group": {
                    "_id": "$placement",
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
                            "$cond": [{"$eq": ["$event_type", "lead_created"]}, 1, 0]
                        }
                    },
                    "unique_planners_set": {"$addToSet": "$planner_id"},
                    "unique_campaigns_set": {"$addToSet": "$campaign_id"},
                }
            },
        ]

        upserted = 0
        async for doc in self.ad_events.aggregate(pipeline):
            placement = doc["_id"] or "unknown"
            impressions = doc.get("impressions", 0)
            clicks = doc.get("clicks", 0)

            unique_planners = [p for p in doc.get("unique_planners_set", []) if p]
            unique_campaigns = [c for c in doc.get("unique_campaigns_set", []) if c]

            rollup = {
                "date": day_start,
                "placement": placement,
                "impressions": impressions,
                "clicks": clicks,
                "leads": doc.get("leads", 0),
                "ctr": round(clicks / impressions * 100, 2) if impressions > 0 else 0.0,
                "unique_planners": len(unique_planners),
                "unique_campaigns": len(unique_campaigns),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await self.placement_day_stats.update_one(
                {"date": day_start, "placement": placement},
                {"$set": rollup},
                upsert=True,
            )
            upserted += 1

        logger.info(
            f"Placement rollup for {day_start.strftime('%Y-%m-%d')}: "
            f"{upserted} placement_day_stats upserted"
        )

        return upserted

    # ─── Combined Nightly Rollup ──────────────────────────────────

    async def compute_daily_rollup(
        self,
        target_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Run both campaign and placement rollups for a date.

        This is the entry point called by the nightly cron scheduler.

        Returns:
            {"campaign_stats": N, "placement_stats": M}
        """
        campaign_count = await self.compute_campaign_rollup(target_date)
        placement_count = await self.compute_placement_rollup(target_date)

        return {
            "campaign_stats": campaign_count,
            "placement_stats": placement_count,
        }

    async def backfill_rollups(self, days_back: int = 90) -> Dict[str, int]:
        """
        Backfill rollups for the last N days.

        Useful for initial setup or recovering from missed cron runs.
        """
        now = datetime.now(timezone.utc)
        total_campaigns = 0
        total_placements = 0

        for i in range(days_back, 0, -1):
            target_date = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            result = await self.compute_daily_rollup(target_date)
            total_campaigns += result["campaign_stats"]
            total_placements += result["placement_stats"]

        logger.info(
            f"Backfill complete: {total_campaigns} campaign_day_stats + "
            f"{total_placements} placement_day_stats over {days_back} days"
        )

        return {
            "campaign_stats": total_campaigns,
            "placement_stats": total_placements,
            "days_processed": days_back,
        }

    # ─── Dashboard Queries ────────────────────────────────────────

    async def get_campaign_daily_stats(
        self,
        campaign_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily stats for a specific campaign."""
        period_start = self._get_period_start(days)

        results = []
        async for doc in self.campaign_day_stats.find(
            {"campaign_id": campaign_id, "date": {"$gte": period_start}}
        ).sort("date", -1):
            results.append(_serialize(doc))
        return results

    async def get_placement_daily_stats(
        self,
        days: int = 30,
        placement: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get daily stats per placement type."""
        period_start = self._get_period_start(days)

        query: Dict[str, Any] = {"date": {"$gte": period_start}}
        if placement:
            query["placement"] = placement

        results = []
        async for doc in (
            self.placement_day_stats.find(query).sort("date", -1).limit(5000)
        ):
            results.append(_serialize(doc))
        return results

    # ─── Helpers ──────────────────────────────────────────────────

    def _get_day_boundaries(
        self,
        target_date: Optional[datetime] = None,
    ) -> tuple:
        """Get UTC midnight boundaries for a date."""
        if target_date is None:
            now = datetime.now(timezone.utc)
            target_date = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            target_date = target_date.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=timezone.utc,
            )

        return target_date, target_date + timedelta(days=1)

    def _get_period_start(self, days: int) -> datetime:
        """Get the start of a lookback period."""
        now = datetime.now(timezone.utc)
        return (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    @staticmethod
    def _build_hourly_array(raw_hours: list) -> List[int]:
        """Convert a list of hour values into a 24-element array."""
        hourly = [0] * 24
        for hour in raw_hours:
            if isinstance(hour, int) and 0 <= hour < 24:
                hourly[hour] += 1
        return hourly
