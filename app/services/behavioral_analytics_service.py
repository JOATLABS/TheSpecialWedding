"""Behavioral analytics service for product metrics.

Provides WAU tracking, activation funnels, retention cohorts,
engagement signals, and MRR movement — the product analytics layer
that complements the existing operational metrics.

All calculations are derived from existing data (users, weddings,
guests, rsvps, activity_logs, user_subscriptions) — no new
collections are required for the core metrics.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from bson import ObjectId

from app.core.cache import cache
from app.core.database import mongo

logger = logging.getLogger(__name__)

BEHAVIORAL_METRICS_CACHE_TTL = timedelta(minutes=5)
PLANNER_ENGAGEMENT_CACHE_TTL = timedelta(minutes=1)


class BehavioralAnalyticsService:
    """Compute product-level metrics from existing platform data."""

    def __init__(self, mongo_connector: Any) -> None:
        self._mongo = mongo_connector

    # ──────────────────────────────────────────────
    #  PUBLIC: Full behavioral dashboard payload
    # ──────────────────────────────────────────────

    async def compile_behavioral_metrics(
        self, timeframe: str = "30d"
    ) -> Dict[str, Any]:
        """Return the full behavioral analytics payload."""
        cache_key = self._behavioral_metrics_cache_key(timeframe)
        cached_payload = await cache.get(cache_key)
        if isinstance(cached_payload, dict):
            return cached_payload

        period_days = self._resolve_timeframe(timeframe)
        now = datetime.now(timezone.utc)

        # Run all analyses concurrently
        wau_task = asyncio.create_task(self._compute_wau(now))
        activation_task = asyncio.create_task(self._compute_activation_funnel(now))
        retention_task = asyncio.create_task(self._compute_retention_cohorts(now))
        engagement_task = asyncio.create_task(self._compute_engagement_signals(now))
        mrr_movement_task = asyncio.create_task(self._compute_mrr_movement(now))
        wow_task = asyncio.create_task(self._compute_wow_changes(now, period_days))

        (
            wau,
            activation,
            retention,
            engagement,
            mrr_movement,
            wow,
        ) = await asyncio.gather(
            wau_task,
            activation_task,
            retention_task,
            engagement_task,
            mrr_movement_task,
            wow_task,
        )

        payload = {
            "generated_at": self._serialize_datetime(now),
            "timeframe": timeframe,
            "weekly_active_users": wau,
            "activation_funnel": activation,
            "retention_cohorts": retention,
            "engagement_signals": engagement,
            "mrr_movement": mrr_movement,
            "week_over_week": wow,
        }
        await cache.set(cache_key, payload, expire=BEHAVIORAL_METRICS_CACHE_TTL)
        return payload

    # ──────────────────────────────────────────────
    #  WAU: Weekly Active Users
    # ──────────────────────────────────────────────
    #
    #  Definition: Unique users (planners + team members) who
    #  performed at least one core action in the past 7 days.
    #
    #  "Core actions" are derived from the activity_logs collection,
    #  which tracks: RSVP management, guest management, email/SMS
    #  sends, wedding updates, and form interactions.
    #
    #  We also check last_login from the users collection as a
    #  secondary signal.

    async def _compute_wau(self, now: datetime) -> Dict[str, Any]:
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)

        users_col = self._mongo.get_users_collection()
        activity_col = self._mongo.db.get_collection("activity_logs")

        # Current WAU: unique actor_emails in activity_logs last 7 days
        current_wau_pipeline = [
            {"$match": {"timestamp": {"$gte": seven_days_ago}}},
            {"$group": {"_id": "$actor_email"}},
            {"$count": "count"},
        ]

        # Previous WAU: 7-14 days ago (for comparison)
        previous_wau_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": fourteen_days_ago, "$lt": seven_days_ago}
                }
            },
            {"$group": {"_id": "$actor_email"}},
            {"$count": "count"},
        ]

        # Also count users with last_login in the past 7 days as a floor
        login_wau_task = asyncio.create_task(
            self._count_documents(
                users_col,
                {
                    "last_login": {"$gte": seven_days_ago},
                    "role": {"$in": ["wedding_planner", "team_member"]},
                },
            )
        )

        current_docs = await self._safe_aggregate(activity_col, current_wau_pipeline)
        previous_docs = await self._safe_aggregate(activity_col, previous_wau_pipeline)
        login_wau = await login_wau_task

        current_wau = current_docs[0]["count"] if current_docs else 0
        previous_wau = previous_docs[0]["count"] if previous_docs else 0

        # Use the higher of activity-based or login-based WAU
        current_wau = max(current_wau, login_wau)

        change = current_wau - previous_wau
        change_pct = (change / previous_wau * 100) if previous_wau > 0 else 0.0

        # WAU/MAU ratio (stickiness)
        thirty_days_ago = now - timedelta(days=30)
        mau_pipeline = [
            {"$match": {"timestamp": {"$gte": thirty_days_ago}}},
            {"$group": {"_id": "$actor_email"}},
            {"$count": "count"},
        ]
        mau_docs = await self._safe_aggregate(activity_col, mau_pipeline)
        mau = mau_docs[0]["count"] if mau_docs else 0
        stickiness = (current_wau / mau * 100) if mau > 0 else 0.0

        return {
            "current": current_wau,
            "previous_week": previous_wau,
            "change": change,
            "change_percent": round(change_pct, 1),
            "mau": mau,
            "stickiness_ratio": round(stickiness, 1),
        }

    # ──────────────────────────────────────────────
    #  ACTIVATION FUNNEL
    # ──────────────────────────────────────────────
    #
    #  Tracks the critical path from signup to value delivery:
    #
    #  Step 1: Signed up (user created)
    #  Step 2: Onboarding completed (onboarding_completed == True)
    #  Step 3: First wedding created (at least 1 wedding assigned)
    #  Step 4: First guest invited (at least 1 guest with invite_sent)
    #  Step 5: First RSVP received (at least 1 RSVP in their wedding)
    #
    #  We measure: last 30 days of signups and how far they've progressed.
    #  This uses actual data relationships, not synthetic events.

    async def _compute_activation_funnel(self, now: datetime) -> Dict[str, Any]:
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        users_col = self._mongo.get_users_collection()
        weddings_col = self._mongo.get_weddings_collection()
        guests_col = self._mongo.get_guest_collection()
        rsvps_col = self._mongo.get_rsvps_collection()

        # Step 1: New planner signups (last 30d)
        total_signups = 0
        onboarded = 0
        planner_emails: List[str] = []
        async for planner in users_col.find(
            {
                "created_at": {"$gte": thirty_days_ago},
                "role": "wedding_planner",
            },
            {"email": 1, "onboarding_completed": 1},
        ):
            total_signups += 1
            if planner.get("onboarding_completed") is True:
                onboarded += 1
            email = planner.get("email")
            if email:
                planner_emails.append(email)

        if total_signups == 0:
            return self._empty_funnel()

        # Step 3: First wedding created
        # Find which of these planners have at least 1 wedding
        wedding_pipeline = [
            {"$match": {"assigned_planner_email": {"$in": planner_emails}}},
            {"$group": {"_id": "$assigned_planner_email"}},
        ]
        planners_with_weddings_docs = await self._safe_aggregate(
            weddings_col, wedding_pipeline
        )
        planners_with_weddings = {doc["_id"] for doc in planners_with_weddings_docs}
        created_wedding = len(planners_with_weddings)

        # Step 4: First guest invited
        # Find wedding_ids for these planners, then check for invited guests
        if planners_with_weddings:
            wedding_ids_pipeline = [
                {
                    "$match": {
                        "assigned_planner_email": {"$in": list(planners_with_weddings)}
                    }
                },
                {"$project": {"_id": 1, "assigned_planner_email": 1}},
            ]
            wedding_docs = await self._safe_aggregate(
                weddings_col, wedding_ids_pipeline
            )

            # Map wedding_id -> planner_email
            wedding_to_planner: Dict[str, str] = {}
            for doc in wedding_docs:
                wid = str(doc["_id"])
                wedding_to_planner[wid] = doc["assigned_planner_email"]

            wedding_ids = list(wedding_to_planner.keys())

            # Guests with invite_sent == True in those weddings
            invited_pipeline = [
                {"$match": {"wedding_id": {"$in": wedding_ids}, "invite_sent": True}},
                {"$group": {"_id": "$wedding_id"}},
            ]
            weddings_with_invites_docs = await self._safe_aggregate(
                guests_col, invited_pipeline
            )
            planners_with_invites = {
                wedding_to_planner[doc["_id"]]
                for doc in weddings_with_invites_docs
                if doc["_id"] in wedding_to_planner
            }
            invited_guests = len(planners_with_invites)

            # Step 5: First RSVP received
            # RSVPs in those weddings where attending is a non-empty list
            rsvp_pipeline = [
                {
                    "$match": {
                        "wedding_id": {"$in": wedding_ids},
                        "attending": {"$exists": True, "$type": "array", "$ne": []},
                    }
                },
                {"$group": {"_id": "$wedding_id"}},
            ]
            weddings_with_rsvps_docs = await self._safe_aggregate(
                rsvps_col, rsvp_pipeline
            )
            planners_with_rsvps = {
                wedding_to_planner[doc["_id"]]
                for doc in weddings_with_rsvps_docs
                if doc["_id"] in wedding_to_planner
            }
            received_rsvp = len(planners_with_rsvps)
        else:
            invited_guests = 0
            received_rsvp = 0

        # Also compute all-time funnel for the 90-day window
        all_time_signups = await self._count_documents(
            users_col,
            {"created_at": {"$gte": ninety_days_ago}, "role": "wedding_planner"},
        )

        return {
            "period": "last_30_days",
            "steps": [
                {
                    "name": "Signed Up",
                    "count": total_signups,
                    "rate": 100.0,
                },
                {
                    "name": "Completed Onboarding",
                    "count": onboarded,
                    "rate": (
                        round(onboarded / total_signups * 100, 1)
                        if total_signups
                        else 0.0
                    ),
                },
                {
                    "name": "Created First Wedding",
                    "count": created_wedding,
                    "rate": (
                        round(created_wedding / total_signups * 100, 1)
                        if total_signups
                        else 0.0
                    ),
                },
                {
                    "name": "Invited First Guest",
                    "count": invited_guests,
                    "rate": (
                        round(invited_guests / total_signups * 100, 1)
                        if total_signups
                        else 0.0
                    ),
                },
                {
                    "name": "Received First RSVP",
                    "count": received_rsvp,
                    "rate": (
                        round(received_rsvp / total_signups * 100, 1)
                        if total_signups
                        else 0.0
                    ),
                },
            ],
            "conversion_rate": (
                round(received_rsvp / total_signups * 100, 1) if total_signups else 0.0
            ),
            "signups_90d": all_time_signups,
        }

    # ──────────────────────────────────────────────
    #  RETENTION COHORTS
    # ──────────────────────────────────────────────
    #
    #  Monthly signup cohorts tracked at D7, D30, D60, D90.
    #
    #  "Retained" = user logged in (last_login) OR performed
    #  an activity (activity_logs) after the threshold date.
    #
    #  We generate cohorts for the last 4 months of signups.

    async def _compute_retention_cohorts(self, now: datetime) -> Dict[str, Any]:
        users_col = self._mongo.get_users_collection()
        activity_col = self._mongo.db.get_collection("activity_logs")

        cohorts = []
        cohort_anchor = self._month_floor(now)

        for months_ago in range(4):
            # Define cohort month boundaries
            cohort_start = self._add_months(cohort_anchor, -months_ago)
            cohort_end = self._add_months(cohort_start, 1)

            # Get planners who signed up in this month
            cohort_size = 0
            cohort_emails: List[str] = []
            async for user in users_col.find(
                {
                    "created_at": {"$gte": cohort_start, "$lt": cohort_end},
                    "role": "wedding_planner",
                },
                {"email": 1},
            ):
                cohort_size += 1
                email = user.get("email")
                if email:
                    cohort_emails.append(email)

            if cohort_size == 0:
                cohorts.append(
                    {
                        "month": cohort_start.strftime("%Y-%m"),
                        "cohort_size": 0,
                        "d7": None,
                        "d30": None,
                        "d60": None,
                        "d90": None,
                    }
                )
                continue

            # For each retention window, check if user was active after that threshold
            retention_windows = {"d7": 7, "d30": 30, "d60": 60, "d90": 90}
            retention_data: Dict[str, Optional[float]] = {}

            for label, days in retention_windows.items():
                threshold = cohort_start + timedelta(days=days)

                # If the threshold hasn't passed yet, we can't measure this window
                if threshold > now:
                    retention_data[label] = None
                    continue

                # Count users who logged in after the threshold
                login_emails = {
                    doc.get("email")
                    async for doc in users_col.find(
                        {
                            "email": {"$in": cohort_emails},
                            "last_login": {"$gte": threshold},
                        },
                        {"email": 1},
                    )
                    if doc.get("email")
                }

                # Also count users active in activity_logs after threshold
                activity_pipeline = [
                    {
                        "$match": {
                            "actor_email": {"$in": cohort_emails},
                            "timestamp": {"$gte": threshold},
                        }
                    },
                    {"$group": {"_id": "$actor_email"}},
                ]
                activity_docs = await self._safe_aggregate(
                    activity_col, activity_pipeline
                )
                activity_emails = {
                    doc["_id"] for doc in activity_docs if doc.get("_id")
                }

                # Retained = union of login-based and activity-based
                retained = len(login_emails | activity_emails)

                retention_data[label] = round(retained / cohort_size * 100, 1)

            cohorts.append(
                {
                    "month": cohort_start.strftime("%Y-%m"),
                    "cohort_size": cohort_size,
                    **retention_data,
                }
            )

        return {"cohorts": cohorts}

    # ──────────────────────────────────────────────
    #  ENGAGEMENT SIGNALS (for planner dashboard)
    # ──────────────────────────────────────────────
    #
    #  Per-planner signals that help identify which couples/
    #  weddings need attention:
    #  - Couple last portal access
    #  - Form completion rates
    #  - Average message response time
    #  - RSVP velocity (RSVPs per day, last 7 days)

    async def _compute_engagement_signals(self, now: datetime) -> Dict[str, Any]:
        seven_days_ago = now - timedelta(days=7)
        fourteen_days_ago = now - timedelta(days=14)

        activity_col = self._mongo.db.get_collection("activity_logs")
        rsvps_col = self._mongo.get_rsvps_collection()

        # RSVP velocity: RSVPs in last 7 days vs previous 7 days
        current_rsvps = await self._count_documents(
            activity_col,
            {"type": "rsvp_received", "timestamp": {"$gte": seven_days_ago}},
        )
        previous_rsvps = await self._count_documents(
            activity_col,
            {
                "type": "rsvp_received",
                "timestamp": {"$gte": fourteen_days_ago, "$lt": seven_days_ago},
            },
        )

        rsvp_velocity_change = current_rsvps - previous_rsvps

        # Platform-wide response rate
        total_rsvps = await self._count_documents(rsvps_col, {})
        total_guests_invited = await self._count_documents(
            self._mongo.get_guest_collection(),
            {"invite_sent": True},
        )
        platform_response_rate = (
            round(total_rsvps / total_guests_invited * 100, 1)
            if total_guests_invited > 0
            else 0.0
        )

        # Active weddings with guest engagement (North Star metric)
        # Weddings where at least 1 RSVP, form submission, or media upload
        # occurred in the past 7 days
        active_engagement_pipeline = [
            {"$match": {"timestamp": {"$gte": seven_days_ago}}},
            {
                "$match": {
                    "type": {
                        "$in": [
                            "rsvp_received",
                            "rsvp_updated",
                            "guest_added",
                            "guest_imported",
                            "email_sent",
                            "sms_sent",
                            "reminder_sent",
                        ]
                    }
                }
            },
            {"$group": {"_id": "$wedding_id"}},
            {"$match": {"_id": {"$ne": None}}},
            {"$count": "count"},
        ]
        engagement_docs = await self._safe_aggregate(
            activity_col, active_engagement_pipeline
        )
        active_engaged_weddings = engagement_docs[0]["count"] if engagement_docs else 0

        return {
            "rsvp_velocity": {
                "current_7d": current_rsvps,
                "previous_7d": previous_rsvps,
                "change": rsvp_velocity_change,
                "trend": (
                    "up"
                    if rsvp_velocity_change > 0
                    else ("down" if rsvp_velocity_change < 0 else "flat")
                ),
            },
            "platform_response_rate": platform_response_rate,
            "active_engaged_weddings": active_engaged_weddings,
            "north_star_metric": active_engaged_weddings,
        }

    # ──────────────────────────────────────────────
    #  MRR MOVEMENT
    # ──────────────────────────────────────────────
    #
    #  Decomposes MRR changes into:
    #  - New MRR (from new subscriptions this period)
    #  - Expansion/contraction tracking is deferred until plan-change events
    #    are recorded reliably in subscription history.
    #  - Churned MRR (cancellations)
    #
    #  Trial conversion is derived from subscriptions whose trial_end_date
    #  falls inside the reporting window and whose current status is active.

    async def _compute_mrr_movement(self, now: datetime) -> Dict[str, Any]:
        thirty_days_ago = now - timedelta(days=30)

        subs_col = self._mongo.db.get_collection("user_subscriptions")
        plans_col = self._mongo.get_subscription_plans_collection()

        # Build plan price lookup
        plans_lookup: Dict[str, Dict[str, float]] = {}
        plans_cursor = plans_col.find(
            {}, {"_id": 1, "price_monthly": 1, "price_yearly": 1}
        )
        async for plan in plans_cursor:
            pid = str(plan["_id"])
            plans_lookup[pid] = {
                "monthly": float(plan.get("price_monthly") or 0),
                "yearly": float(plan.get("price_yearly") or 0),
            }

        # New MRR: subscriptions created in the last 30 days with active status
        new_mrr = 0.0
        async for sub in subs_col.find(
            {
                "start_date": {"$gte": thirty_days_ago},
                "status": {"$in": ["active", "trial"]},
            },
            {"plan_id": 1, "billing_interval": 1, "status": 1},
        ):
            if sub.get("status") == "active":
                plan = plans_lookup.get(str(sub.get("plan_id", "")), {})
                new_mrr += self._monthly_value(plan, sub.get("billing_interval"))

        # Churned MRR: subscriptions cancelled in the last 30 days
        churned_mrr = 0.0
        async for sub in subs_col.find(
            {
                "cancelled_at": {"$gte": thirty_days_ago},
                "status": "cancelled",
            },
            {"plan_id": 1, "billing_interval": 1},
        ):
            plan = plans_lookup.get(str(sub.get("plan_id", "")), {})
            churned_mrr += self._monthly_value(plan, sub.get("billing_interval"))

        # Current total MRR (for context)
        current_mrr = 0.0
        async for sub in subs_col.find(
            {"status": "active"},
            {"plan_id": 1, "billing_interval": 1},
        ):
            plan = plans_lookup.get(str(sub.get("plan_id", "")), {})
            current_mrr += self._monthly_value(plan, sub.get("billing_interval"))

        # Trial-to-paid conversion in the period
        conversion_query, total_trials_query = self._trial_conversion_queries(
            thirty_days_ago,
            now,
        )
        trial_conversions = await self._count_documents(subs_col, conversion_query)
        total_trials_in_period = await self._count_documents(
            subs_col, total_trials_query
        )
        trial_conversion_rate = (
            round(trial_conversions / total_trials_in_period * 100, 1)
            if total_trials_in_period > 0
            else 0.0
        )

        net_mrr_change = new_mrr - churned_mrr

        return {
            "current_mrr": round(current_mrr, 2),
            "new_mrr": round(new_mrr, 2),
            "churned_mrr": round(churned_mrr, 2),
            "net_change": round(net_mrr_change, 2),
            "net_change_percent": (
                round(net_mrr_change / (current_mrr - net_mrr_change) * 100, 1)
                if (current_mrr - net_mrr_change) > 0
                else 0.0
            ),
            "trial_conversions": trial_conversions,
            "trial_conversion_rate": trial_conversion_rate,
        }

    # ──────────────────────────────────────────────
    #  WEEK-OVER-WEEK CHANGE INDICATORS
    # ──────────────────────────────────────────────
    #
    #  Computes current vs previous period for key metrics
    #  to power ↑/↓ indicators on metric cards.

    async def _compute_wow_changes(
        self, now: datetime, period_days: int
    ) -> Dict[str, Any]:
        current_start = now - timedelta(days=period_days)
        previous_start = now - timedelta(days=period_days * 2)

        users_col = self._mongo.get_users_collection()
        # New users: current period vs previous period
        current_new_users = await self._count_documents(
            users_col, {"created_at": {"$gte": current_start}}
        )
        previous_new_users = await self._count_documents(
            users_col, {"created_at": {"$gte": previous_start, "$lt": current_start}}
        )

        # New weddings
        # Wedding created_at can be datetime or string, use a safe approach
        activity_col = self._mongo.db.get_collection("activity_logs")
        current_weddings = await self._count_documents(
            activity_col,
            {"type": "wedding_created", "timestamp": {"$gte": current_start}},
        )
        previous_weddings = await self._count_documents(
            activity_col,
            {
                "type": "wedding_created",
                "timestamp": {"$gte": previous_start, "$lt": current_start},
            },
        )

        # New RSVPs
        current_rsvps = await self._count_documents(
            activity_col,
            {"type": "rsvp_received", "timestamp": {"$gte": current_start}},
        )
        previous_rsvps = await self._count_documents(
            activity_col,
            {
                "type": "rsvp_received",
                "timestamp": {"$gte": previous_start, "$lt": current_start},
            },
        )

        # Active users (last_login in period)
        current_active = await self._count_documents(
            users_col, {"is_active": True, "last_login": {"$gte": current_start}}
        )
        previous_active = await self._count_documents(
            users_col,
            {
                "is_active": True,
                "last_login": {"$gte": previous_start, "$lt": current_start},
            },
        )

        def _change(current: int, previous: int) -> Dict[str, Any]:
            delta = current - previous
            pct = round(delta / previous * 100, 1) if previous > 0 else 0.0
            trend = "up" if delta > 0 else ("down" if delta < 0 else "flat")
            return {
                "current": current,
                "previous": previous,
                "change": delta,
                "change_percent": pct,
                "trend": trend,
            }

        return {
            "new_users": _change(current_new_users, previous_new_users),
            "new_weddings": _change(current_weddings, previous_weddings),
            "new_rsvps": _change(current_rsvps, previous_rsvps),
            "active_users": _change(current_active, previous_active),
        }

    # ──────────────────────────────────────────────
    #  PLANNER-SPECIFIC ENGAGEMENT (per wedding)
    # ──────────────────────────────────────────────

    async def get_planner_engagement_signals(
        self,
        planner_email: Optional[str] = None,
        accessible_wedding_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Return per-wedding engagement signals for a specific planner.

        Includes: couple last activity, form completion status,
        RSVP velocity per wedding, and needs-attention flags.
        """
        cache_key = self._planner_engagement_cache_key(
            planner_email, accessible_wedding_ids
        )
        cached_signals = await cache.get(cache_key)
        if isinstance(cached_signals, list):
            return cached_signals

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        weddings_col = self._mongo.get_weddings_collection()
        activity_col = self._mongo.db.get_collection("activity_logs")
        guests_col = self._mongo.get_guest_collection()
        rsvps_col = self._mongo.get_rsvps_collection()
        forms_col = self._mongo.get_forms_collection()
        form_responses_col = self._mongo.get_form_responses_collection()

        wedding_query: Dict[str, Any] = {"status": {"$ne": "deleted"}}
        if planner_email:
            wedding_query["assigned_planner_email"] = planner_email

        if accessible_wedding_ids is not None:
            normalized_ids = self._normalize_wedding_ids(accessible_wedding_ids)
            if not normalized_ids:
                return []
            wedding_query["_id"] = {"$in": normalized_ids}

        weddings = await weddings_col.find(
            wedding_query,
            {"_id": 1, "couple_names": 1, "date": 1},
        ).to_list(length=5000)

        if not weddings:
            return []

        wedding_ids = [str(wedding["_id"]) for wedding in weddings]

        last_activity_docs = await self._safe_aggregate(
            activity_col,
            [
                {"$match": {"wedding_id": {"$in": wedding_ids}}},
                {"$sort": {"timestamp": -1}},
                {
                    "$group": {
                        "_id": "$wedding_id",
                        "last_activity_at": {"$first": "$timestamp"},
                    }
                },
            ],
        )
        last_activity_map = {
            str(doc["_id"]): doc.get("last_activity_at")
            for doc in last_activity_docs
            if doc.get("_id") is not None
        }

        guest_stats_docs = await self._safe_aggregate(
            guests_col,
            [
                {"$match": {"wedding_id": {"$in": wedding_ids}}},
                {
                    "$group": {
                        "_id": "$wedding_id",
                        "guest_count": {"$sum": 1},
                        "invited_count": {
                            "$sum": {"$cond": [{"$eq": ["$invite_sent", True]}, 1, 0]}
                        },
                    }
                },
            ],
        )
        guest_stats_map = {
            str(doc["_id"]): {
                "guest_count": int(doc.get("guest_count", 0) or 0),
                "invited_count": int(doc.get("invited_count", 0) or 0),
            }
            for doc in guest_stats_docs
            if doc.get("_id") is not None
        }

        rsvp_counts = self._count_map(
            await self._safe_aggregate(
                rsvps_col,
                [
                    {"$match": {"wedding_id": {"$in": wedding_ids}}},
                    {"$group": {"_id": "$wedding_id", "count": {"$sum": 1}}},
                ],
            )
        )
        recent_rsvp_counts = self._count_map(
            await self._safe_aggregate(
                activity_col,
                [
                    {
                        "$match": {
                            "wedding_id": {"$in": wedding_ids},
                            "type": "rsvp_received",
                            "timestamp": {"$gte": seven_days_ago},
                        }
                    },
                    {"$group": {"_id": "$wedding_id", "count": {"$sum": 1}}},
                ],
            )
        )
        form_counts = self._count_map(
            await self._safe_aggregate(
                forms_col,
                [
                    {"$match": {"wedding_id": {"$in": wedding_ids}, "is_active": True}},
                    {"$group": {"_id": "$wedding_id", "count": {"$sum": 1}}},
                ],
            )
        )
        form_submission_counts = self._count_map(
            await self._safe_aggregate(
                form_responses_col,
                [
                    {"$match": {"wedding_id": {"$in": wedding_ids}}},
                    {"$group": {"_id": "$wedding_id", "count": {"$sum": 1}}},
                ],
            )
        )

        signals = []
        for wedding in weddings:
            wid = str(wedding["_id"])
            last_activity_at = self._as_datetime(last_activity_map.get(wid))
            guest_stats = guest_stats_map.get(
                wid,
                {"guest_count": 0, "invited_count": 0},
            )
            guest_count = guest_stats["guest_count"]
            invited_count = guest_stats["invited_count"]
            rsvp_count = rsvp_counts.get(wid, 0)
            recent_rsvps = recent_rsvp_counts.get(wid, 0)
            form_count = form_counts.get(wid, 0)
            form_submissions = form_submission_counts.get(wid, 0)

            # Determine needs-attention flags
            needs_attention = []
            if last_activity_at and (now - last_activity_at).days > 14:
                needs_attention.append("inactive_14d")
            if invited_count > 0 and rsvp_count == 0:
                needs_attention.append("no_rsvps_yet")
            if invited_count > 0:
                response_rate = rsvp_count / invited_count * 100
                if response_rate < 30:
                    needs_attention.append("low_response_rate")
            if form_count > 0 and form_submissions < form_count:
                needs_attention.append("pending_forms")

            signals.append(
                {
                    "wedding_id": wid,
                    "couple_names": wedding.get("couple_names", ""),
                    "wedding_date": wedding.get("date", ""),
                    "last_activity_at": self._serialize_datetime(last_activity_at),
                    "days_since_activity": (
                        (now - last_activity_at).days if last_activity_at else None
                    ),
                    "guest_count": guest_count,
                    "invited_count": invited_count,
                    "rsvp_count": rsvp_count,
                    "response_rate": (
                        round(rsvp_count / invited_count * 100, 1)
                        if invited_count > 0
                        else 0.0
                    ),
                    "rsvps_last_7d": recent_rsvps,
                    "forms_total": form_count,
                    "forms_completed": min(form_submissions, form_count),
                    "needs_attention": needs_attention,
                }
            )

        await cache.set(cache_key, signals, expire=PLANNER_ENGAGEMENT_CACHE_TTL)
        return signals

    # ──────────────────────────────────────────────
    #  COUPLE PORTAL: Non-responders list
    # ──────────────────────────────────────────────

    async def get_non_responders(self, wedding_id: str) -> List[Dict[str, Any]]:
        """Return guests who haven't RSVP'd, sorted by days since invite sent."""
        now = datetime.now(timezone.utc)
        guests_col = self._mongo.get_guest_collection()
        rsvps_col = self._mongo.get_rsvps_collection()

        # Get all invited guests
        invited_guests = [
            doc
            async for doc in guests_col.find(
                {"wedding_id": wedding_id, "invite_sent": True},
                {
                    "_id": 1,
                    "name": 1,
                    "email": 1,
                    "phone": 1,
                    "invite_sent_date": 1,
                    "group_id": 1,
                },
            )
        ]

        if not invited_guests:
            return []

        # Get all guest_ids that have submitted RSVPs
        guest_ids = [str(g["_id"]) for g in invited_guests]
        rsvps = [
            doc
            async for doc in rsvps_col.find(
                {"wedding_id": wedding_id, "guest_id": {"$in": guest_ids}},
                {"guest_id": 1},
            )
        ]

        responded_ids = {r["guest_id"] for r in rsvps}

        # Filter to non-responders
        non_responders = []
        for guest in invited_guests:
            gid = str(guest["_id"])
            if gid not in responded_ids:
                invite_date = self._as_datetime(guest.get("invite_sent_date"))
                days_since = (now - invite_date).days if invite_date else None

                non_responders.append(
                    {
                        "guest_id": gid,
                        "name": guest.get("name", ""),
                        "email": guest.get("email"),
                        "phone": guest.get("phone"),
                        "invite_sent_date": self._serialize_datetime(invite_date),
                        "days_since_invite": days_since,
                        "group_id": guest.get("group_id"),
                    }
                )

        # Sort by days_since_invite descending (longest waiters first)
        non_responders.sort(
            key=lambda x: (
                x["days_since_invite"] if x["days_since_invite"] is not None else -1
            ),
            reverse=True,
        )

        return non_responders

    # ──────────────────────────────────────────────
    #  COUPLE PORTAL: Budget category breakdown
    # ──────────────────────────────────────────────

    async def get_budget_breakdown(self, wedding_id: str) -> Dict[str, Any]:
        """Return per-category budget allocation and spend."""
        budget_col = self._mongo.db.get_collection("budget_categories")

        categories = [
            doc
            async for doc in budget_col.find(
                {"wedding_id": wedding_id},
                {
                    "name": 1,
                    "budgeted_amount": 1,
                    "actual_spent": 1,
                    "payment_status": 1,
                    "priority": 1,
                },
            )
        ]

        total_budgeted = sum(c.get("budgeted_amount", 0) for c in categories)
        total_spent = sum(c.get("actual_spent", 0) for c in categories)

        breakdown = []
        for cat in categories:
            budgeted = float(cat.get("budgeted_amount", 0))
            spent = float(cat.get("actual_spent", 0))
            pct_of_budget = (
                round(budgeted / total_budgeted * 100, 1) if total_budgeted > 0 else 0.0
            )
            pct_spent = round(spent / budgeted * 100, 1) if budgeted > 0 else 0.0

            breakdown.append(
                {
                    "category_id": str(cat.get("_id", "")),
                    "name": cat.get("name", ""),
                    "budgeted": budgeted,
                    "spent": spent,
                    "remaining": round(budgeted - spent, 2),
                    "percent_of_total_budget": pct_of_budget,
                    "percent_spent": pct_spent,
                    "payment_status": cat.get("payment_status", "pending"),
                    "priority": cat.get("priority", 1),
                }
            )

        # Sort by budgeted amount descending
        breakdown.sort(key=lambda x: x["budgeted"], reverse=True)

        return {
            "total_budgeted": round(total_budgeted, 2),
            "total_spent": round(total_spent, 2),
            "total_remaining": round(total_budgeted - total_spent, 2),
            "percent_spent": (
                round(total_spent / total_budgeted * 100, 1)
                if total_budgeted > 0
                else 0.0
            ),
            "categories": breakdown,
            "category_count": len(breakdown),
        }

    # ──────────────────────────────────────────────
    #  HELPERS
    # ──────────────────────────────────────────────

    def _empty_funnel(self) -> Dict[str, Any]:
        return {
            "period": "last_30_days",
            "steps": [
                {"name": "Signed Up", "count": 0, "rate": 0.0},
                {"name": "Completed Onboarding", "count": 0, "rate": 0.0},
                {"name": "Created First Wedding", "count": 0, "rate": 0.0},
                {"name": "Invited First Guest", "count": 0, "rate": 0.0},
                {"name": "Received First RSVP", "count": 0, "rate": 0.0},
            ],
            "conversion_rate": 0.0,
            "signups_90d": 0,
        }

    @staticmethod
    def _monthly_value(plan_prices: Dict[str, float], interval: Optional[str]) -> float:
        """Calculate monthly equivalent revenue from plan prices and billing interval."""
        interval_norm = (interval or "").lower()
        monthly = plan_prices.get("monthly", 0)
        yearly = plan_prices.get("yearly", 0)

        if interval_norm == "yearly":
            return yearly / 12 if yearly else monthly
        return monthly if monthly else yearly / 12

    @staticmethod
    def _month_floor(value: datetime) -> datetime:
        return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _behavioral_metrics_cache_key(timeframe: str) -> str:
        return f"behavioral_analytics:v1:dashboard:{timeframe.lower()}"

    @staticmethod
    def _planner_engagement_cache_key(
        planner_email: Optional[str],
        accessible_wedding_ids: Optional[Sequence[str]],
    ) -> str:
        scope_email = planner_email or "root_admin"
        if accessible_wedding_ids is None:
            scope = "all"
        else:
            digest_source = "|".join(sorted(accessible_wedding_ids))
            scope = (
                hashlib.sha1(
                    digest_source.encode("utf-8"), usedforsecurity=False
                ).hexdigest()
                if digest_source
                else "none"
            )
        return f"behavioral_analytics:v1:planner_signals:{scope_email}:{scope}"

    @classmethod
    def _add_months(cls, value: datetime, months: int) -> datetime:
        base = cls._month_floor(value)
        month_index = base.year * 12 + (base.month - 1) + months
        year = month_index // 12
        month = month_index % 12 + 1
        return base.replace(year=year, month=month)

    @staticmethod
    def _trial_conversion_queries(
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        base_query = {
            "trial_end_date": {"$gte": period_start, "$lte": period_end},
        }
        return {**base_query, "status": "active"}, base_query

    @staticmethod
    def _normalize_wedding_ids(wedding_ids: Sequence[str]) -> List[Any]:
        normalized: List[Any] = []
        for wedding_id in wedding_ids:
            if not wedding_id:
                continue
            if ObjectId.is_valid(wedding_id):
                normalized.append(ObjectId(wedding_id))
            normalized.append(wedding_id)
        return normalized

    @staticmethod
    def _count_map(
        docs: Sequence[Dict[str, Any]],
        value_key: str = "count",
    ) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for doc in docs:
            doc_id = doc.get("_id")
            if doc_id is None:
                continue
            result[str(doc_id)] = int(doc.get(value_key, 0) or 0)
        return result

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        return None

    @classmethod
    def _serialize_datetime(cls, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value
        dt = cls._as_datetime(value)
        if not dt:
            return None
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _resolve_timeframe(timeframe: str) -> int:
        mapping = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
        return mapping.get(timeframe.lower(), 30)

    async def _count_documents(self, collection: Any, query: Dict[str, Any]) -> int:
        try:
            return await collection.count_documents(query)
        except Exception as exc:
            logger.warning("count_documents failed: %s", exc)
            return 0

    async def _safe_aggregate(
        self, collection: Any, pipeline: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        try:
            cursor = collection.aggregate(pipeline)
            return [doc async for doc in cursor]
        except Exception as exc:
            logger.warning("Aggregate failed: %s", exc)
            return []


# Module-level singleton
service = BehavioralAnalyticsService(mongo)
