from fastapi import APIRouter, HTTPException, Depends, Query
from app.dependencies.auth_extended import (
    get_current_user_extended, ExtendedAuthUser,
    enforce_team_permission, require_team_or_planner,
    get_accessible_wedding_ids
)
from app.core.cache import cache, CacheKeys
from app.core.database import mongo
from bson import ObjectId
from app.models.planner_metrics import (
    PlannerMetricsResponse,
    MetricsSummaryModel,
    WeddingMetricsModel,
    RSVPStatsModel,
    RevenueMetricsModel,
    ActivityLogResponse,
    ActivityItemModel,
    PlannerWeddingModel,
)
from datetime import datetime
from typing import Any, Optional, List
from math import ceil
import hashlib
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

PLANNER_WEDDINGS_CACHE_TTL_SECONDS = 15


def _safe_isoformat(value: Any) -> str:
    """Safely convert datetime to ISO format string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return ""


def _parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse a date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def _calculate_rsvp_status(rsvp: dict) -> str:
    """
    Determine RSVP status based on attending field.

    The 'attending' field is a List[str] of event names the guest is attending.
    - If list has items: guest is confirmed (attending at least one event)
    - If list is empty: guest declined all events
    - If field is missing/None: should not happen for submitted RSVPs
    """
    attending = rsvp.get("attending")

    # attending is a List[str] of event names
    if attending is None:
        return "pending"

    if isinstance(attending, list):
        if len(attending) > 0:
            return "confirmed"
        else:
            return "declined"

    # Legacy support: if attending was stored as dict (old format)
    if isinstance(attending, dict):
        if any(attending.values()):
            return "confirmed"
        elif all(not val for val in attending.values()):
            return "declined"

    return "pending"


def _planner_weddings_scope_key(
    current_user: ExtendedAuthUser,
    include_cancelled: bool,
    accessible_ids: Optional[List[str]],
) -> str:
    scope_parts = [
        current_user.email or "anonymous",
        "root" if current_user.is_root_admin else "scoped",
        "include_cancelled" if include_cancelled else "active_only",
    ]
    if accessible_ids is not None:
        digest = hashlib.sha256(",".join(sorted(accessible_ids)).encode("utf-8")).hexdigest()[:12]
        scope_parts.append(digest)
    return CacheKeys.planner_weddings(":".join(scope_parts), include_cancelled)


def _normalize_cached_planner_wedding(payload: dict[str, Any]) -> dict[str, Any]:
    if "id" in payload:
        return payload
    if "_id" in payload:
        normalized = dict(payload)
        normalized["id"] = str(normalized.pop("_id"))
        return normalized
    return payload


@router.get("/planner/metrics", tags=["Wedding Planner"], response_model=PlannerMetricsResponse)
async def get_planner_metrics(current_user: ExtendedAuthUser = Depends(require_team_or_planner)) -> PlannerMetricsResponse:
    """
    Get comprehensive metrics for wedding planner dashboard.

    ROOT_ADMIN sees all weddings, wedding planners see only their assigned weddings.
    Team members with "assigned" access see only their assigned weddings.
    """

    enforce_team_permission(current_user, "view_analytics")

    try:
        weddings_collection = mongo.get_weddings_collection()
        guests_collection = mongo.get_guest_collection()
        rsvps_collection = mongo.get_rsvps_collection()

        # Build query based on user role
        # ROOT_ADMIN can see all weddings, planners only see their assigned weddings
        # Team members use accessible_wedding_ids for filtering
        if current_user.is_root_admin:
            query: dict[str, Any] = {"status": {"$ne": "cancelled"}}
        else:
            query = {
                "assigned_planner_email": current_user.email,
                "status": {"$ne": "cancelled"}
            }
            # Apply team member wedding scope filter
            accessible_ids = get_accessible_wedding_ids(current_user)
            if accessible_ids is not None:
                query["_id"] = {"$in": [ObjectId(id) for id in accessible_ids]}

        # Safety cap: typical planner/admin has <5k weddings
        MAX_WEDDINGS = 5000
        weddings = await weddings_collection.find(query).to_list(length=MAX_WEDDINGS)
        current_date = datetime.now()

        # Activity query used for both recent activity and /planner/activity-log
        if current_user.is_root_admin:
            activity_query: dict[str, Any] = {}
        else:
            assigned_weddings = await weddings_collection.find(
                {"assigned_planner_email": current_user.email},
                {"_id": 1}
            ).to_list(length=MAX_WEDDINGS)

            wedding_id_values: list[Any] = []
            for wedding in assigned_weddings:
                wedding_id = wedding.get("_id")
                if wedding_id is None:
                    continue
                wedding_id_values.append(wedding_id)
                wedding_id_values.append(str(wedding_id))

            activity_query = {
                "$or": [
                    {"planner_email": current_user.email},
                    {"actor_email": current_user.email},
                    {"user_email": current_user.email},
                    {"assigned_planner_email": current_user.email},
                    {"wedding_id": {"$in": wedding_id_values}}
                ]
            }

        plus_ones_collection = mongo.get_plus_ones_collection()

        metrics: dict[str, Any] = {
            "summary": {
                "total_weddings": len(weddings),
                "active_weddings": 0,
                "upcoming_weddings": 0,
                "past_weddings": 0,
                "total_guests": 0,
                "total_plus_ones_allowed": 0,
                "total_plus_ones_submitted": 0,
                "confirmed_rsvps": 0,
                "confirmed_plus_ones_allowed": 0,
                "confirmed_plus_ones_submitted": 0,
                "pending_rsvps": 0,
                "pending_plus_ones_allowed": 0,
                "declined_rsvps": 0
            },
            "weddings": [],
            "recent_activity": [],
            "revenue_metrics": {
                "monthly_bookings": 0,
                "total_revenue": 0,
                "average_wedding_value": 0
            }
        }

        # Process each wedding
        for wedding in weddings:
            wedding_id = wedding["_id"]
            wedding_id_str = str(wedding_id)
            wedding_status = wedding.get("status", "active")

            # Parse wedding date
            wedding_date = _parse_date_safe(wedding.get("date"))
            days_until_wedding = 0

            if wedding_date:
                days_until_wedding = (wedding_date - current_date).days
                if wedding_date > current_date:
                    metrics["summary"]["upcoming_weddings"] += 1
                else:
                    metrics["summary"]["past_weddings"] += 1

            if wedding_status == "active":
                metrics["summary"]["active_weddings"] += 1

            # Get all guests for this wedding (need plus-one and invite_sent data)
            # Safety cap: large weddings may have up to 5000 guests
            MAX_WEDDING_GUESTS = 5000
            guest_docs = await guests_collection.find(
                {"wedding_id": wedding_id_str},
                {"_id": 1, "number_of_plus_ones_allowed": 1, "invite_sent": 1}
            ).to_list(length=MAX_WEDDING_GUESTS)
            guest_count = len(guest_docs)
            metrics["summary"]["total_guests"] += guest_count

            # Build guest lookup: guest_id -> {plus_ones_allowed, invite_sent}
            guest_plus_ones_map: dict[str, int] = {}
            guest_invite_sent: dict[str, bool] = {}
            total_plus_ones_allowed = 0
            for g in guest_docs:
                gid = str(g["_id"])
                allowed = g.get("number_of_plus_ones_allowed") or 0
                guest_plus_ones_map[gid] = allowed
                guest_invite_sent[gid] = bool(g.get("invite_sent"))
                total_plus_ones_allowed += allowed
            metrics["summary"]["total_plus_ones_allowed"] += total_plus_ones_allowed

            # Count actual submitted plus-ones for this wedding's guests
            guest_id_strs = list(guest_plus_ones_map.keys())
            submitted_plus_ones = 0
            confirmed_plus_ones_submitted = 0
            if guest_id_strs:
                submitted_plus_ones = await plus_ones_collection.count_documents(
                    {"guest_id": {"$in": guest_id_strs}}
                )
            metrics["summary"]["total_plus_ones_submitted"] += submitted_plus_ones

            # Get RSVP statistics - handle both ObjectId and string formats for wedding_id
            # Safety cap: max guest RSVPs (same as guest cap)
            rsvps = await rsvps_collection.find({
                "$or": [
                    {"wedding_id": wedding_id},
                    {"wedding_id": wedding_id_str}
                ]
            }).to_list(length=MAX_WEDDING_GUESTS)

            confirmed = 0
            declined = 0
            confirmed_plus_allowed = 0
            rsvp_guest_ids: set[str] = set()

            for rsvp in rsvps:
                rsvp_guest_id = str(rsvp.get("guest_id", ""))
                rsvp_guest_ids.add(rsvp_guest_id)
                status = _calculate_rsvp_status(rsvp)
                if status == "confirmed":
                    confirmed += 1
                    confirmed_plus_allowed += guest_plus_ones_map.get(rsvp_guest_id, 0)
                elif status == "declined":
                    declined += 1

            # Count submitted plus-ones for confirmed guests
            confirmed_guest_ids = [
                str(rsvp.get("guest_id", "")) for rsvp in rsvps
                if _calculate_rsvp_status(rsvp) == "confirmed"
            ]
            if confirmed_guest_ids:
                confirmed_plus_ones_submitted = await plus_ones_collection.count_documents(
                    {"guest_id": {"$in": confirmed_guest_ids}}
                )

            # Pending = guests who were INVITED but haven't submitted an RSVP
            # This matches the guests page "Awaiting Response" calculation
            pending = sum(
                1 for gid in guest_plus_ones_map
                if gid not in rsvp_guest_ids and guest_invite_sent.get(gid, False)
            )
            pending_plus_allowed = sum(
                guest_plus_ones_map.get(gid, 0)
                for gid in guest_plus_ones_map
                if gid not in rsvp_guest_ids and guest_invite_sent.get(gid, False)
            )

            metrics["summary"]["confirmed_rsvps"] += confirmed
            metrics["summary"]["confirmed_plus_ones_allowed"] += confirmed_plus_allowed
            metrics["summary"]["confirmed_plus_ones_submitted"] += confirmed_plus_ones_submitted
            metrics["summary"]["declined_rsvps"] += declined
            metrics["summary"]["pending_rsvps"] += pending
            metrics["summary"]["pending_plus_ones_allowed"] += pending_plus_allowed

            # Calculate progress percentage
            progress_score = 0.0
            if guest_count > 0:
                response_rate = len(rsvps) / guest_count
                progress_score += min(40, response_rate * 40)  # Up to 40% for RSVPs
                progress_score += 20  # 20% for having guests
            if wedding.get("events"):
                progress_score += 20  # 20% for having events configured
            if wedding.get("details") or wedding.get("venue"):
                progress_score += 20  # 20% for wedding details

            wedding_metrics = {
                "id": wedding_id_str,
                "couple_names": wedding.get("couple_names", ""),
                "date": wedding.get("date", ""),
                "slug": wedding.get("slug", ""),
                "status": wedding_status,
                "guest_count": guest_count,
                "rsvp_stats": {
                    "confirmed": confirmed,
                    "declined": declined,
                    "pending": pending,
                    "total_responses": len(rsvps),
                    "response_rate": round((len(rsvps) / guest_count * 100) if guest_count > 0 else 0, 1)
                },
                "progress_percentage": min(100, round(progress_score)),
                "days_until_wedding": days_until_wedding,
                "created_at": _safe_isoformat(wedding.get("created_at")),
                "assigned_planner_email": wedding.get("assigned_planner_email", "")
            }

            metrics["weddings"].append(wedding_metrics)

        # Sort weddings by date (upcoming first, then by date)
        metrics["weddings"].sort(key=lambda x: (x["date"] or "9999-12-31"))

        # Calculate revenue metrics from subscription data
        if metrics["weddings"]:
            current_month = current_date.month
            current_year = current_date.year

            monthly_bookings = 0
            for w in metrics["weddings"]:
                created_at = w.get("created_at")
                if created_at:
                    created_date = _parse_date_safe(created_at)
                    if created_date and created_date.month == current_month and created_date.year == current_year:
                        monthly_bookings += 1

            metrics["revenue_metrics"]["monthly_bookings"] = monthly_bookings
            subscriptions_collection = mongo.db.get_collection("user_subscriptions")
            plans_collection = mongo.get_subscription_plans_collection()
            users_collection = mongo.get_users_collection()

            # Limit revenue calculations to the current planner unless ROOT_ADMIN
            if current_user.is_root_admin:
                user_query: dict[str, Any] = {"role": "wedding_planner"}
            else:
                user_query = {"email": current_user.email}

            user_id_values: list[Any] = []
            # Safety cap: fetch revenue users (typically <10k)
            MAX_REVENUE_USERS = 10000
            users_for_revenue = await users_collection.find(user_query, {"_id": 1}).to_list(length=MAX_REVENUE_USERS)
            for user in users_for_revenue:
                user_id = user.get("_id")
                if user_id is None:
                    continue
                user_id_values.append(user_id)
                user_id_values.append(str(user_id))

            subscription_match: dict[str, Any] = {"status": "active"}
            if user_id_values:
                subscription_match["user_id"] = {"$in": user_id_values}
            elif not current_user.is_root_admin:
                subscription_match["user_id"] = "__none__"  # Prevent leaking other users' revenue

            revenue_pipeline = [
                {"$match": subscription_match},
                {"$lookup": {
                    "from": plans_collection.name if hasattr(plans_collection, "name") else "subscription_plans",
                    "localField": "plan_id",
                    "foreignField": "_id",
                    "as": "plan_doc"
                }},
                {"$unwind": {"path": "$plan_doc", "preserveNullAndEmptyArrays": True}},
                {"$project": {
                    "billing_interval": "$billing_interval",
                    "price_monthly": {"$ifNull": ["$plan_doc.price_monthly", 0]},
                    "price_yearly": {"$ifNull": ["$plan_doc.price_yearly", 0]}
                }},
                {"$project": {
                    "monthly_revenue": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {"$eq": ["$billing_interval", "yearly"]},
                                    "then": {
                                        "$cond": [
                                            {"$gt": ["$price_yearly", 0]},
                                            {"$divide": ["$price_yearly", 12]},
                                            "$price_monthly"
                                        ]
                                    }
                                },
                                {
                                    "case": {"$eq": ["$billing_interval", "monthly"]},
                                    "then": {
                                        "$cond": [
                                            {"$gt": ["$price_monthly", 0]},
                                            "$price_monthly",
                                            {"$divide": ["$price_yearly", 12]}
                                        ]
                                    }
                                }
                            ],
                            "default": {
                                "$cond": [
                                    {"$gt": ["$price_monthly", 0]},
                                    "$price_monthly",
                                    {"$divide": ["$price_yearly", 12]}
                                ]
                            }
                        }
                    },
                    "annual_revenue": {
                        "$cond": [
                            {"$gt": ["$price_yearly", 0]},
                            "$price_yearly",
                            {"$multiply": ["$price_monthly", 12]}
                        ]
                    }
                }},
                {"$group": {
                    "_id": None,
                    "monthly": {"$sum": "$monthly_revenue"},
                    "annual": {"$sum": "$annual_revenue"}
                }}
            ]

            monthly_revenue = 0.0

            try:
                # Aggregate result should be single doc, but cap at 10 for safety
                revenue_docs = await subscriptions_collection.aggregate(revenue_pipeline).to_list(length=10)
                if revenue_docs:
                    monthly_revenue = float(revenue_docs[0].get("monthly", 0) or 0)
            except Exception as exc:
                logger.debug(f"Revenue aggregation fallback: {exc}")
                plan_cache: dict[Any, dict[str, Any]] = {}
                async for plan in plans_collection.find({}, {"price_monthly": 1, "price_yearly": 1}):
                    plan_cache[plan.get("_id")] = plan

                async for sub in subscriptions_collection.find(subscription_match, {"plan_id": 1, "billing_interval": 1}):
                    plan = plan_cache.get(sub.get("plan_id"), {})
                    price_monthly = float(plan.get("price_monthly") or 0)
                    price_yearly = float(plan.get("price_yearly") or 0)
                    interval = sub.get("billing_interval")

                    if interval == "yearly":
                        monthly_revenue += price_yearly / 12 if price_yearly else price_monthly
                    else:
                        monthly_revenue += price_monthly or (price_yearly / 12 if price_yearly else 0)

            total_weddings = metrics["summary"]["total_weddings"] or 0
            metrics["revenue_metrics"]["total_revenue"] = round(monthly_revenue, 2)
            metrics["revenue_metrics"]["average_wedding_value"] = round(
                monthly_revenue / total_weddings, 2) if total_weddings > 0 else 0

        # Recent activity (latest 10)
        recent_activity: List[ActivityItemModel] = []
        try:
            activity_logs_collection = mongo.get_collection("activity_logs")
            cursor = activity_logs_collection.find(
                activity_query,
                {
                    "_id": 1,
                    "type": 1,
                    "message": 1,
                    "timestamp": 1,
                    "created_at": 1,
                    "wedding_id": 1,
                    "metadata": 1,
                }
            ).sort([("timestamp", -1), ("created_at", -1)]).limit(10)

            # Activity already limited by .limit(10) in cursor
            activity_docs = await cursor.to_list(length=10)
            for activity in activity_docs:
                recent_activity.append(ActivityItemModel(
                    id=str(activity.get("_id")),
                    type=activity.get("type", "info"),
                    message=activity.get("message", ""),
                    timestamp=_safe_isoformat(activity.get("timestamp") or activity.get("created_at")),
                    wedding_id=str(activity.get("wedding_id")) if activity.get("wedding_id") is not None else None,
                    metadata=activity.get("metadata", {}),
                ))
        except Exception as exc:
            logger.debug(f"Recent activity fetch skipped: {exc}")

        return PlannerMetricsResponse(
            summary=MetricsSummaryModel(**metrics["summary"]),
            weddings=[WeddingMetricsModel(
                id=w["id"],
                couple_names=w["couple_names"],
                date=w["date"],
                slug=w["slug"],
                status=w["status"],
                guest_count=w["guest_count"],
                rsvp_stats=RSVPStatsModel(**w["rsvp_stats"]),
                progress_percentage=w["progress_percentage"],
                days_until_wedding=w["days_until_wedding"],
                created_at=w["created_at"],
                assigned_planner_email=w["assigned_planner_email"]
            ) for w in metrics["weddings"]],
            recent_activity=recent_activity,
            revenue_metrics=RevenueMetricsModel(**metrics["revenue_metrics"])
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching planner metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch planner metrics")


@router.get("/planner/activity-log", tags=["Wedding Planner"], response_model=ActivityLogResponse)
async def get_activity_log(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    page: int = Query(default=1, ge=1, le=10000, description="Page number (1-indexed)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of activities to return per page")
) -> ActivityLogResponse:
    """
    Get detailed activity log for wedding planner.
    """

    enforce_team_permission(current_user, "view_analytics")

    try:
        activity_logs_collection = mongo.get_collection("activity_logs")

        # Restrict to the planner's weddings unless ROOT_ADMIN
        if current_user.is_root_admin:
            query: dict[str, Any] = {}
        else:
            weddings_collection = mongo.get_weddings_collection()
            # Safety cap: planner's assigned weddings (typically <1k)
            MAX_PLANNER_WEDDINGS = 1000
            assigned_weddings = await weddings_collection.find(
                {"assigned_planner_email": current_user.email},
                {"_id": 1}
            ).to_list(length=MAX_PLANNER_WEDDINGS)

            wedding_id_values: list[Any] = []
            for wedding in assigned_weddings:
                wedding_id = wedding.get("_id")
                if wedding_id is None:
                    continue
                wedding_id_values.append(wedding_id)
                wedding_id_values.append(str(wedding_id))

            query = {
                "$or": [
                    {"planner_email": current_user.email},
                    {"actor_email": current_user.email},
                    {"user_email": current_user.email},
                    {"assigned_planner_email": current_user.email},
                    {"wedding_id": {"$in": wedding_id_values}}
                ]
            }

        # Count total documents first for pagination metadata
        total = await activity_logs_collection.count_documents(query)

        # Calculate skip value for pagination
        skip = (page - 1) * limit

        cursor = activity_logs_collection.find(
            query,
            {
                "_id": 1,
                "type": 1,
                "message": 1,
                "timestamp": 1,
                "created_at": 1,
                "wedding_id": 1,
                "metadata": 1,
            }
        ).sort([("timestamp", -1), ("created_at", -1)]).skip(skip).limit(limit)

        # Activity results already bounded by .limit(limit) above
        activities_raw = await cursor.to_list(length=limit)

        activities: List[ActivityItemModel] = []
        for activity in activities_raw:
            activities.append(ActivityItemModel(
                id=str(activity.get("_id")),
                type=activity.get("type", "info"),
                message=activity.get("message", ""),
                timestamp=_safe_isoformat(activity.get("timestamp") or activity.get("created_at")),
                wedding_id=str(activity.get("wedding_id")) if activity.get("wedding_id") is not None else None,
                metadata=activity.get("metadata", {}),
            ))

        # Calculate total pages
        pages = ceil(total / limit) if total > 0 else 0

        return ActivityLogResponse(
            activities=activities,
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching activity log: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch activity log")


@router.get("/planner/weddings", tags=["Wedding Planner"], response_model=List[PlannerWeddingModel])
async def get_planner_weddings(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
    include_cancelled: bool = Query(default=False, description="Include cancelled weddings")
) -> List[PlannerWeddingModel]:
    """
    Get all weddings assigned to the current planner.

    ROOT_ADMIN sees all weddings, wedding planners see only their assigned weddings.
    Team members with "assigned" access see only their assigned weddings.
    """

    enforce_team_permission(current_user, "view_analytics")

    try:
        weddings_collection = mongo.get_weddings_collection()

        # Build query based on user role
        accessible_ids: Optional[List[str]] = None
        if current_user.is_root_admin:
            query: dict[str, Any] = {}
        else:
            query = {"assigned_planner_email": current_user.email}
            # Apply team member wedding scope filter
            accessible_ids = get_accessible_wedding_ids(current_user)
            if accessible_ids is not None:
                query["_id"] = {"$in": [ObjectId(id) for id in accessible_ids]}

        # Optionally exclude cancelled weddings
        if not include_cancelled:
            query["status"] = {"$ne": "cancelled"}

        cache_key = _planner_weddings_scope_key(current_user, include_cancelled, accessible_ids)
        cached_weddings = await cache.get(cache_key)
        if cached_weddings is not None:
            return [PlannerWeddingModel(**_normalize_cached_planner_wedding(wedding)) for wedding in cached_weddings]

        # Safety cap: typical planner has <5k weddings
        MAX_WEDDINGS_LIST = 5000
        weddings = await weddings_collection.find(
            query,
            {
                "couple_names": 1,
                "date": 1,
                "slug": 1,
                "assigned_planner_email": 1,
                "assigned_planner_id": 1,
                "status": 1,
                "venue": 1,
                "guest_count": 1,
                "created_at": 1,
                "updated_at": 1,
                "events": 1,
                "privacy_settings": 1,
                "rsvp_config": 1,
                "theme_config": 1,
                "registries": 1,
                "faqs": 1,
                "our_story": 1,
                "wedding_party": 1,
                "featured_image": 1,
            },
        ).to_list(length=MAX_WEDDINGS_LIST)

        # Convert ObjectId to string and format response
        wedding_list: List[PlannerWeddingModel] = []
        for wedding in weddings:
            wedding_list.append(PlannerWeddingModel(
                id=str(wedding["_id"]),
                couple_names=wedding.get("couple_names", ""),
                date=wedding.get("date", ""),
                slug=wedding.get("slug", ""),
                assigned_planner_email=wedding.get("assigned_planner_email"),
                assigned_planner_id=wedding.get("assigned_planner_id"),
                status=wedding.get("status", "active"),
                venue=wedding.get("venue"),
                guest_count=wedding.get("guest_count", 0),
                created_at=_safe_isoformat(wedding.get("created_at")),
                updated_at=_safe_isoformat(wedding.get("updated_at")),
                events=wedding.get("events", []),
                privacy_settings=wedding.get("privacy_settings"),
                rsvp_config=wedding.get("rsvp_config"),
                theme_config=wedding.get("theme_config"),
                registries=wedding.get("registries", []),
                faqs=wedding.get("faqs", []),
                our_story=wedding.get("our_story"),
                wedding_party=wedding.get("wedding_party", []),
                featured_image=wedding.get("featured_image")
            ))

        # Sort by date (upcoming first)
        wedding_list.sort(key=lambda x: x.date or "9999-12-31")

        await cache.set(
            cache_key,
            [wedding.model_dump(by_alias=False) for wedding in wedding_list],
            expire=PLANNER_WEDDINGS_CACHE_TTL_SECONDS,
        )

        return wedding_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching planner weddings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch weddings")
