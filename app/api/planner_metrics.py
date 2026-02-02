from fastapi import APIRouter, HTTPException, Depends, Query
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.core.database import mongo
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
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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


@router.get("/planner/metrics", tags=["Wedding Planner"], response_model=PlannerMetricsResponse)
async def get_planner_metrics(current_user: ExtendedAuthUser = Depends(get_current_user_extended)) -> PlannerMetricsResponse:
    """
    Get comprehensive metrics for wedding planner dashboard.

    ROOT_ADMIN sees all weddings, wedding planners see only their assigned weddings.
    """

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        weddings_collection = mongo.get_weddings_collection()
        guests_collection = mongo.get_guest_collection()
        rsvps_collection = mongo.get_rsvps_collection()

        # Build query based on user role
        # ROOT_ADMIN can see all weddings, planners only see their assigned weddings
        if current_user.is_root_admin:
            query: dict[str, Any] = {"status": {"$ne": "cancelled"}}
        else:
            query = {
                "assigned_planner_email": current_user.email,
                "status": {"$ne": "cancelled"}
            }

        weddings = await weddings_collection.find(query).to_list(length=None)
        current_date = datetime.now()

        # Activity query used for both recent activity and /planner/activity-log
        if current_user.is_root_admin:
            activity_query: dict[str, Any] = {}
        else:
            assigned_weddings = await weddings_collection.find(
                {"assigned_planner_email": current_user.email},
                {"_id": 1}
            ).to_list(length=None)

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

        metrics: dict[str, Any] = {
            "summary": {
                "total_weddings": len(weddings),
                "active_weddings": 0,
                "upcoming_weddings": 0,
                "past_weddings": 0,
                "total_guests": 0,
                "confirmed_rsvps": 0,
                "pending_rsvps": 0,
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

            # Get guest count - wedding_id in guests collection is stored as string
            guest_count = await guests_collection.count_documents({"wedding_id": wedding_id_str})
            metrics["summary"]["total_guests"] += guest_count

            # Get RSVP statistics - handle both ObjectId and string formats for wedding_id
            rsvps = await rsvps_collection.find({
                "$or": [
                    {"wedding_id": wedding_id},
                    {"wedding_id": wedding_id_str}
                ]
            }).to_list(length=None)

            confirmed = 0
            declined = 0

            for rsvp in rsvps:
                status = _calculate_rsvp_status(rsvp)
                if status == "confirmed":
                    confirmed += 1
                elif status == "declined":
                    declined += 1

            # Pending = guests who haven't submitted an RSVP at all
            pending = max(0, guest_count - len(rsvps))

            metrics["summary"]["confirmed_rsvps"] += confirmed
            metrics["summary"]["declined_rsvps"] += declined
            metrics["summary"]["pending_rsvps"] += pending

            # Calculate progress percentage
            progress_score = 0
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
            users_for_revenue = await users_collection.find(user_query, {"_id": 1}).to_list(length=None)
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
                revenue_docs = await subscriptions_collection.aggregate(revenue_pipeline).to_list(length=None)
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

            activity_docs = await cursor.to_list(length=None)
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
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of activities to return")
) -> ActivityLogResponse:
    """
    Get detailed activity log for wedding planner.
    """

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        activity_logs_collection = mongo.get_collection("activity_logs")

        # Restrict to the planner's weddings unless ROOT_ADMIN
        if current_user.is_root_admin:
            query: dict[str, Any] = {}
        else:
            weddings_collection = mongo.get_weddings_collection()
            assigned_weddings = await weddings_collection.find(
                {"assigned_planner_email": current_user.email},
                {"_id": 1}
            ).to_list(length=None)

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
        ).sort([("timestamp", -1), ("created_at", -1)]).limit(limit)

        activities_raw = await cursor.to_list(length=None)
        total = await activity_logs_collection.count_documents(query)

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

        return ActivityLogResponse(
            activities=activities,
            total=total
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching activity log: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch activity log")


@router.get("/planner/weddings", tags=["Wedding Planner"], response_model=List[PlannerWeddingModel])
async def get_planner_weddings(
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
    include_cancelled: bool = Query(default=False, description="Include cancelled weddings")
) -> List[PlannerWeddingModel]:
    """
    Get all weddings assigned to the current planner.

    ROOT_ADMIN sees all weddings, wedding planners see only their assigned weddings.
    """

    if not (current_user.is_wedding_planner or current_user.is_root_admin):
        raise HTTPException(status_code=403, detail="Access denied. Wedding planner or ROOT_ADMIN role required.")

    try:
        weddings_collection = mongo.get_weddings_collection()

        # Build query based on user role
        if current_user.is_root_admin:
            query: dict[str, Any] = {}
        else:
            query = {"assigned_planner_email": current_user.email}

        # Optionally exclude cancelled weddings
        if not include_cancelled:
            query["status"] = {"$ne": "cancelled"}

        weddings = await weddings_collection.find(query).to_list(length=None)

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

        return wedding_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching planner weddings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch weddings")
