"""
Ad Stats Rollup Service

Computes pre-aggregated daily rollups from raw ad_events into ad_stats_daily.
Designed to run as a nightly cron job or on-demand for backfill.

The rollup pipeline:
1. $match — Filter events for a specific date (UTC day boundaries)
2. $group — Aggregate by (sponsored_vendor_id, placement, day)
3. $project — Shape counts, compute CTR, format hourly clicks
4. $merge — Upsert into ad_stats_daily (idempotent, safe to re-run)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.database import mongo

logger = logging.getLogger(__name__)


class AdRollupService:
    """
    Service for computing and managing pre-aggregated daily ad stats.

    Reads from: ad_events, ad_leads
    Writes to: ad_stats_daily
    """

    def __init__(self, db):
        """
        Initialize the rollup service.

        Args:
            db: Motor async database client
        """
        self.db = db
        self.ad_events = db["ad_events"]
        self.ad_leads = db["ad_leads"]
        self.ad_stats_daily = db["ad_stats_daily"]

    async def compute_daily_rollup(
        self,
        target_date: Optional[datetime] = None
    ) -> int:
        """
        Compute the daily rollup for a specific date.

        If no date is provided, defaults to yesterday (UTC).
        Idempotent: safe to re-run for the same date (upserts via $merge).

        Args:
            target_date: Date to compute rollup for (defaults to yesterday UTC)

        Returns:
            Number of rollup documents created/updated
        """
        if target_date is None:
            # Default to yesterday UTC
            now = datetime.now(timezone.utc)
            target_date = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            # Normalize to midnight UTC
            target_date = target_date.replace(
                hour=0, minute=0, second=0, microsecond=0,
                tzinfo=timezone.utc
            )

        day_start = target_date
        day_end = target_date + timedelta(days=1)

        logger.info(
            f"Computing ad stats rollup for {day_start.strftime('%Y-%m-%d')}"
        )

        # =====================================================================
        # Stage 1: Aggregate ad_events
        # =====================================================================
        events_pipeline = [
            # Match events for the target day
            {
                "$match": {
                    "created_at": {
                        "$gte": day_start,
                        "$lt": day_end,
                    }
                }
            },
            # Group by vendor + placement + day
            {
                "$group": {
                    "_id": {
                        "sponsored_vendor_id": "$sponsored_vendor_id",
                        "vendor_profile_id": "$vendor_profile_id",
                        "placement": "$placement",
                    },
                    # Count each event type
                    "impression_served": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_served"]},
                                1, 0,
                            ]
                        }
                    },
                    "impression_viewable": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "impression_viewable"]},
                                1, 0,
                            ]
                        }
                    },
                    "click": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "click"]},
                                1, 0,
                            ]
                        }
                    },
                    "vendor_profile_view": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_profile_view"]},
                                1, 0,
                            ]
                        }
                    },
                    "vendor_added_to_wedding": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_added_to_wedding"]},
                                1, 0,
                            ]
                        }
                    },
                    "lead_created": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "lead_created"]},
                                1, 0,
                            ]
                        }
                    },
                    "vendor_invited": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_invited"]},
                                1, 0,
                            ]
                        }
                    },
                    "lead_accepted": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "lead_accepted"]},
                                1, 0,
                            ]
                        }
                    },
                    "vendor_responded": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "vendor_responded"]},
                                1, 0,
                            ]
                        }
                    },
                    "dismiss": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "dismiss"]},
                                1, 0,
                            ]
                        }
                    },
                    "hover": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "hover"]},
                                1, 0,
                            ]
                        }
                    },
                    "contact_click": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$event_type", "contact_click"]},
                                1, 0,
                            ]
                        }
                    },
                    # Unique reach
                    "unique_planners_set": {"$addToSet": "$planner_id"},
                    "unique_weddings_set": {"$addToSet": "$wedding_id"},
                    # Hourly click distribution
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

        # Execute the events aggregation
        event_rollups = {}
        async for doc in self.ad_events.aggregate(events_pipeline):
            key = (
                doc["_id"]["sponsored_vendor_id"],
                doc["_id"]["placement"],
            )

            # Build hourly clicks array (24 hours)
            hourly = [0] * 24
            for hour in doc.get("hourly_clicks_raw", []):
                if isinstance(hour, int) and 0 <= hour < 24:
                    hourly[hour] += 1

            # Compute total impressions and CTR
            total_impressions = (
                doc.get("impression_served", 0) +
                doc.get("impression_viewable", 0)
            )
            total_clicks = doc.get("click", 0)
            ctr = (
                (total_clicks / total_impressions * 100)
                if total_impressions > 0 else 0.0
            )

            # Filter None from unique sets
            unique_planners = [
                p for p in doc.get("unique_planners_set", []) if p
            ]
            unique_weddings = [
                w for w in doc.get("unique_weddings_set", []) if w
            ]

            event_rollups[key] = {
                "date": day_start,
                "sponsored_vendor_id": doc["_id"]["sponsored_vendor_id"],
                "vendor_profile_id": doc["_id"]["vendor_profile_id"],
                "placement": doc["_id"]["placement"],
                "counts": {
                    "impression_served": doc.get("impression_served", 0),
                    "impression_viewable": doc.get("impression_viewable", 0),
                    "click": doc.get("click", 0),
                    "vendor_profile_view": doc.get("vendor_profile_view", 0),
                    "vendor_added_to_wedding": doc.get("vendor_added_to_wedding", 0),
                    "lead_created": doc.get("lead_created", 0),
                    "vendor_invited": doc.get("vendor_invited", 0),
                    "lead_accepted": doc.get("lead_accepted", 0),
                    "vendor_responded": doc.get("vendor_responded", 0),
                    "dismiss": doc.get("dismiss", 0),
                    "hover": doc.get("hover", 0),
                    "contact_click": doc.get("contact_click", 0),
                },
                "unique_planners": len(unique_planners),
                "unique_weddings": len(unique_weddings),
                "hourly_clicks": hourly,
                "ctr": round(ctr, 2),
                "leads_by_type": {},
                "leads_by_status": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

        # =====================================================================
        # Stage 2: Aggregate ad_leads for the same day
        # =====================================================================
        leads_pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": day_start,
                        "$lt": day_end,
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "sponsored_vendor_id": "$sponsored_vendor_id",
                        "placement": "$placement",
                    },
                    # Leads by type
                    "quote_request": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$lead_type", "quote_request"]},
                                1, 0,
                            ]
                        }
                    },
                    "message": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$lead_type", "message"]},
                                1, 0,
                            ]
                        }
                    },
                    "add_to_wedding": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$lead_type", "add_to_wedding"]},
                                1, 0,
                            ]
                        }
                    },
                    "vendor_invite": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$lead_type", "vendor_invite"]},
                                1, 0,
                            ]
                        }
                    },
                    # Leads by status
                    "status_pending": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "pending"]},
                                1, 0,
                            ]
                        }
                    },
                    "status_contacted": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "contacted"]},
                                1, 0,
                            ]
                        }
                    },
                    "status_responded": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "responded"]},
                                1, 0,
                            ]
                        }
                    },
                    "status_converted": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "converted"]},
                                1, 0,
                            ]
                        }
                    },
                    "status_closed": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$status", "closed"]},
                                1, 0,
                            ]
                        }
                    },
                }
            },
        ]

        async for doc in self.ad_leads.aggregate(leads_pipeline):
            key = (
                doc["_id"]["sponsored_vendor_id"],
                doc["_id"].get("placement", "vendor_rail"),
            )

            leads_by_type = {
                "quote_request": doc.get("quote_request", 0),
                "message": doc.get("message", 0),
                "add_to_wedding": doc.get("add_to_wedding", 0),
                "vendor_invite": doc.get("vendor_invite", 0),
            }
            leads_by_status = {
                "pending": doc.get("status_pending", 0),
                "contacted": doc.get("status_contacted", 0),
                "responded": doc.get("status_responded", 0),
                "converted": doc.get("status_converted", 0),
                "closed": doc.get("status_closed", 0),
            }

            if key in event_rollups:
                event_rollups[key]["leads_by_type"] = leads_by_type
                event_rollups[key]["leads_by_status"] = leads_by_status

        # =====================================================================
        # Stage 3: Upsert into ad_stats_daily
        # =====================================================================
        upserted_count = 0
        for key, rollup in event_rollups.items():
            await self.ad_stats_daily.update_one(
                {
                    "date": rollup["date"],
                    "sponsored_vendor_id": rollup["sponsored_vendor_id"],
                    "placement": rollup["placement"],
                },
                {"$set": rollup},
                upsert=True,
            )
            upserted_count += 1

        logger.info(
            f"Completed rollup for {day_start.strftime('%Y-%m-%d')}: "
            f"{upserted_count} stats documents upserted"
        )

        return upserted_count

    async def backfill_rollups(
        self,
        days_back: int = 90
    ) -> int:
        """
        Backfill rollups for the last N days.

        Useful for initial setup or recovering from missed cron runs.

        Args:
            days_back: Number of days to backfill (default 90)

        Returns:
            Total number of rollup documents created/updated
        """
        now = datetime.now(timezone.utc)
        total = 0

        for i in range(days_back, 0, -1):
            target_date = (now - timedelta(days=i)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            count = await self.compute_daily_rollup(target_date)
            total += count

        logger.info(f"Backfill complete: {total} rollup documents over {days_back} days")
        return total

    async def get_dashboard_stats(
        self,
        days: int = 30,
        sponsored_vendor_id: Optional[str] = None,
        placement: Optional[str] = None,
    ) -> list:
        """
        Query pre-aggregated stats for the dashboard.

        Returns daily rollup documents for the specified period,
        optionally filtered by vendor and/or placement.

        Args:
            days: Number of days to look back
            sponsored_vendor_id: Filter by specific vendor (optional)
            placement: Filter by specific placement (optional)

        Returns:
            List of daily rollup documents sorted by date descending
        """
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        query = {"date": {"$gte": period_start}}

        if sponsored_vendor_id:
            query["sponsored_vendor_id"] = sponsored_vendor_id
        if placement:
            query["placement"] = placement

        results = []
        async for doc in (
            self.ad_stats_daily
            .find(query)
            .sort("date", -1)
        ):
            results.append(doc)

        return results

    async def get_vendor_leaderboard(
        self,
        days: int = 30,
        limit: int = 20,
    ) -> list:
        """
        Get vendor performance leaderboard from rollup data.

        Aggregates daily stats per vendor, sorted by total clicks.

        Args:
            days: Number of days to look back
            limit: Maximum vendors to return

        Returns:
            List of vendor summaries with total impressions, clicks, CTR, leads
        """
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        pipeline = [
            {"$match": {"date": {"$gte": period_start}}},
            {
                "$group": {
                    "_id": {
                        "sponsored_vendor_id": "$sponsored_vendor_id",
                        "vendor_profile_id": "$vendor_profile_id",
                    },
                    "total_impressions": {
                        "$sum": {
                            "$add": [
                                {"$ifNull": ["$counts.impression_served", 0]},
                                {"$ifNull": ["$counts.impression_viewable", 0]},
                            ]
                        }
                    },
                    "total_clicks": {"$sum": {"$ifNull": ["$counts.click", 0]}},
                    "total_leads": {"$sum": {"$ifNull": ["$counts.lead_created", 0]}},
                    "total_conversions": {
                        "$sum": {"$ifNull": ["$leads_by_status.converted", 0]}
                    },
                    "unique_planners": {"$sum": "$unique_planners"},
                    "days_active": {"$sum": 1},
                }
            },
            {
                "$project": {
                    "sponsored_vendor_id": "$_id.sponsored_vendor_id",
                    "vendor_profile_id": "$_id.vendor_profile_id",
                    "total_impressions": 1,
                    "total_clicks": 1,
                    "total_leads": 1,
                    "total_conversions": 1,
                    "unique_planners": 1,
                    "days_active": 1,
                    "ctr": {
                        "$cond": [
                            {"$gt": ["$total_impressions", 0]},
                            {
                                "$multiply": [
                                    {"$divide": ["$total_clicks", "$total_impressions"]},
                                    100,
                                ]
                            },
                            0,
                        ]
                    },
                }
            },
            {"$sort": {"total_clicks": -1}},
            {"$limit": limit},
        ]

        results = []
        async for doc in self.ad_stats_daily.aggregate(pipeline):
            results.append(doc)

        return results
