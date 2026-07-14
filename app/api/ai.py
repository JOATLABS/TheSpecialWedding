"""
AI Feature API Endpoints

Provides endpoints for AI-powered features:
- Budget insights
- Seating optimization
- Communication copilot
- Progress reports
- Package pricing suggestions
"""

import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import mongo
from app.core.settings import settings
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    require_admin_or_planner,
)
from app.services.ai_service import (
    MODEL_ECONOMY,
    MODEL_PRIMARY,
    AIContentBlockedError,
    AIGenerationError,
    AIInvalidResponseError,
    AIQuotaExceededError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AITimeoutError,
    InsufficientCreditsError,
    ai_service,
)
from google.genai import types
from app.services.ai_cache_service import ai_cache_service
from app.utils.rsvp_status import (
    RSVP_STATUS_CONFIRMED,
    RSVP_STATUS_DECLINED,
    get_rsvp_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


def handle_ai_error(e: Exception):
    """
    Convert AI service errors to appropriate HTTP responses.

    Error types and their HTTP status codes:
    - InsufficientCreditsError → 402 (Payment Required)
    - AIRateLimitError → 429 (Too Many Requests)
    - AIQuotaExceededError → 429 (Too Many Requests)
    - AIServiceUnavailableError → 503 (Service Unavailable)
    - AITimeoutError → 504 (Gateway Timeout)
    - AIContentBlockedError → 400 (Bad Request)
    - AIInvalidResponseError → 502 (Bad Gateway)
    - AIGenerationError → 500 (Internal Server Error)
    """
    if isinstance(e, InsufficientCreditsError):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "message": e.message,
                "required": e.required,
                "available": e.available,
            },
        )
    elif isinstance(e, AIRateLimitError):
        raise HTTPException(
            status_code=429,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after,
            },
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None,
        )
    elif isinstance(e, AIQuotaExceededError):
        raise HTTPException(
            status_code=429, detail={"error": e.error_code, "message": e.message}
        )
    elif isinstance(e, AIServiceUnavailableError):
        raise HTTPException(
            status_code=503,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after,
            },
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None,
        )
    elif isinstance(e, AITimeoutError):
        raise HTTPException(
            status_code=504,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after,
            },
        )
    elif isinstance(e, AIContentBlockedError):
        raise HTTPException(
            status_code=400, detail={"error": e.error_code, "message": e.message}
        )
    elif isinstance(e, AIInvalidResponseError):
        raise HTTPException(
            status_code=502, detail={"error": e.error_code, "message": e.message}
        )
    elif isinstance(e, AIGenerationError):
        raise HTTPException(
            status_code=500, detail={"error": e.error_code, "message": e.message}
        )
    else:
        # Unknown error
        logger.error(f"Unexpected AI error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "unknown_error",
                "message": "An unexpected error occurred. Please try again.",
            },
        )


# =========================================================================
# VALIDATION HELPERS
# =========================================================================


def _extract_guest_id(guest: Any) -> Optional[str]:
    """
    Extract guest ID from various formats AI might return.
    Handles: string IDs, objects with id/guest_id/_id fields.
    """
    if guest is None:
        return None
    # AI might return plain string IDs (seating_small format)
    if isinstance(guest, str):
        return guest if guest and guest != "None" else None
    # AI might return objects with various ID fields
    if isinstance(guest, dict):
        guest_id = guest.get("id") or guest.get("guest_id") or guest.get("_id")
        if guest_id and str(guest_id) != "None":
            return str(guest_id)
    return None


def validate_seating_suggestions(
    ai_tables: List[Dict[str, Any]],
    original_guests: Optional[List[Dict[str, Any]]],
    original_tables: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Validate AI-generated seating suggestions for correctness.

    Checks:
    1. All guest IDs in suggestions exist in the original request
    2. Table assignments don't exceed capacity
    3. Tracks unassigned guests

    Returns:
        Dict with validated tables, warnings, and any corrections made
    """
    # Handle null/empty inputs
    if not original_guests or not original_tables:
        return {
            "tables": [],
            "warnings": [
                {
                    "type": "invalid_input",
                    "message": "No guests or tables provided for validation",
                }
            ],
            "stats": {
                "total_guests": 0,
                "assigned_guests": 0,
                "unassigned_guests": 0,
                "tables_over_capacity": 0,
            },
        }

    if not ai_tables:
        return {
            "tables": [],
            "warnings": [
                {
                    "type": "empty_response",
                    "message": "AI returned no seating suggestions",
                }
            ],
            "stats": {
                "total_guests": len(original_guests),
                "assigned_guests": 0,
                "unassigned_guests": len(original_guests),
                "tables_over_capacity": 0,
            },
        }

    # Build lookup maps - filter out guests without valid IDs
    valid_guest_ids = set()
    guest_id_to_name = {}
    for g in original_guests:
        gid = g.get("id") or g.get("_id")
        if gid and str(gid) != "None":
            valid_guest_ids.add(str(gid))
            guest_id_to_name[str(gid)] = g.get("name", "Unknown")

    table_capacities = {}
    table_names = {}
    for i, t in enumerate(original_tables):
        tid = t.get("id") or t.get("_id")
        if tid and str(tid) != "None":
            table_capacities[str(tid)] = t.get("capacity", 10)
            table_names[str(tid)] = t.get("name", f"Table {i + 1}")

    validated_tables = []
    warnings = []
    assigned_guest_ids = set()

    for table in ai_tables:
        table_id = str(table.get("id") or table.get("table_id", ""))
        table_guests = table.get("guests", [])
        capacity = table_capacities.get(table_id, 10)

        # Filter out invalid guest IDs - handle both string and object formats
        valid_guests = []
        invalid_guests = []

        for guest in table_guests:
            guest_id = _extract_guest_id(guest)
            if guest_id and guest_id in valid_guest_ids:
                # Normalize to object format for consistent output
                if isinstance(guest, str):
                    valid_guests.append(
                        {
                            "id": guest_id,
                            "name": guest_id_to_name.get(guest_id, "Unknown"),
                        }
                    )
                else:
                    valid_guests.append(guest)
                assigned_guest_ids.add(guest_id)
            elif guest_id:
                invalid_guests.append(guest_id)
            # Skip None/invalid entries silently

        if invalid_guests:
            warnings.append(
                {
                    "type": "invalid_guest_ids",
                    "table": table_names.get(table_id, table_id),
                    "invalid_ids": invalid_guests,
                    "message": f"Removed {len(invalid_guests)} invalid guest ID(s) from {table_names.get(table_id, table_id)}",
                }
            )

        # Check capacity (account for party sizes if available)
        total_seats_used = 0
        for guest in valid_guests:
            if isinstance(guest, dict):
                party_size = guest.get("party_size", 1)
            else:
                party_size = 1
            total_seats_used += party_size

        if total_seats_used > capacity:
            warnings.append(
                {
                    "type": "over_capacity",
                    "table": table_names.get(table_id, table_id),
                    "capacity": capacity,
                    "assigned": total_seats_used,
                    "message": f"{table_names.get(table_id, table_id)} is over capacity ({total_seats_used}/{capacity})",
                }
            )

        validated_tables.append(
            {
                **table,
                "guests": valid_guests,
                "capacity": capacity,
                "seats_used": total_seats_used,
            }
        )

    # Find unassigned guests
    unassigned = valid_guest_ids - assigned_guest_ids
    unassigned_count = len(unassigned)
    if unassigned:
        unassigned_names = [
            guest_id_to_name.get(gid, "Unknown")
            for gid in list(unassigned)[:10]  # Limit to first 10
        ]
        warnings.append(
            {
                "type": "unassigned_guests",
                "count": unassigned_count,
                "guest_ids": list(unassigned)[:50],  # Limit stored IDs
                "guest_names": unassigned_names,
                "message": f"{unassigned_count} guest(s) not assigned to any table",
            }
        )

    return {
        "tables": validated_tables,
        "warnings": warnings,
        "stats": {
            "total_guests": len(valid_guest_ids),
            "assigned_guests": len(assigned_guest_ids),
            "unassigned_guests": unassigned_count,
            "tables_over_capacity": sum(
                1 for w in warnings if w.get("type") == "over_capacity"
            ),
        },
    }


# =========================================================================
# REQUEST/RESPONSE MODELS
# =========================================================================


class BudgetInsightsRequest(BaseModel):
    force_refresh: bool = False


class SeatingOptimizeRequest(BaseModel):
    guests: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    constraints: Optional[Dict[str, Any]] = None
    force_refresh: bool = False


class DraftCommunicationRequest(BaseModel):
    communication_type: str = Field(
        ..., max_length=50
    )  # follow_up, reminder, thank_you, progress_update
    couple_name: str = Field(..., min_length=1, max_length=200)
    wedding_date: Optional[str] = None
    context: Optional[str] = Field(None, max_length=2000)
    custom_instructions: Optional[str] = Field(None, max_length=2000)


class ProgressReportRequest(BaseModel):
    include_budget: bool = True
    include_rsvp: bool = True
    include_timeline: bool = True
    force_refresh: bool = False


class PricingSuggestionRequest(BaseModel):
    services: List[Dict[str, str]]
    location: Optional[str] = None
    wedding_size: Optional[int] = None
    force_refresh: bool = False


# =========================================================================
# UTILITY FUNCTIONS
# =========================================================================


def get_season_from_date(date_str: Optional[str]) -> Optional[str]:
    """
    Derive the wedding season from the date string.
    Returns: 'peak', 'off_peak', or None
    """
    if not date_str:
        return None
    try:
        from datetime import datetime as dt

        # Parse YYYY-MM-DD format
        wedding_date = dt.strptime(date_str, "%Y-%m-%d")
        month = wedding_date.month

        # Peak season: May-October plus December holidays
        if month in [5, 6, 7, 8, 9, 10, 12]:
            return "peak"
        # Off-peak: January-April, November
        else:
            return "off_peak"
    except Exception:
        return None


def detect_cultural_style_from_events(events: List[Dict]) -> Optional[str]:
    """
    Try to infer cultural style from event types if not explicitly set.
    """
    if not events:
        return None

    event_types = [e.get("type", "").lower() for e in events]

    # Nigerian weddings often have "traditional" ceremony
    if "traditional" in event_types and "white_wedding" in event_types:
        return "nigerian"

    # Could add more detection logic for other cultures
    return None


async def get_wedding_by_id(wedding_id: str) -> Optional[Dict]:
    """Get wedding data by ID. Handles both ObjectId and string IDs."""
    try:
        # Try finding by string _id first (e.g., "wedding_1765336536839")
        wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
        if not wedding:
            # Try ObjectId if string lookup failed
            try:
                wedding = await mongo.db["weddings"].find_one(
                    {"_id": ObjectId(wedding_id)}
                )
            except Exception:
                pass
        if wedding:
            wedding["id"] = str(wedding["_id"])
        return wedding
    except Exception:
        return None


async def get_budget_data(wedding_id: str) -> Dict[str, Any]:
    """Get budget data for a wedding from budget_categories collection."""
    try:
        # Get budget categories from the budget_categories collection
        categories_cursor = mongo.db["budget_categories"].find(
            {"wedding_id": wedding_id}
        )
        categories_list = await categories_cursor.to_list(length=100)

        if not categories_list:
            return {"categories": [], "total_budget": 0, "total_spent": 0}

        # Format categories for AI consumption
        categories = []
        for cat in categories_list:
            categories.append(
                {
                    "name": cat.get("name", "Unknown"),
                    "budget": cat.get("budgeted_amount", 0),
                    "spent": cat.get("actual_spent", 0),
                    "status": cat.get("payment_status", "pending"),
                    "priority": cat.get("priority", 3),
                    "percentage": cat.get("percentage_of_total", 0),
                }
            )

        total_budget = sum(c.get("budget", 0) for c in categories)
        total_spent = sum(c.get("spent", 0) for c in categories)

        return {
            "categories": categories,
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining": total_budget - total_spent,
        }
    except Exception as e:
        logger.error(f"Error fetching budget: {str(e)}")
        return {"categories": [], "total_budget": 0, "total_spent": 0}


async def get_rsvp_data(wedding_id: str) -> Dict[str, Any]:
    """Get RSVP summary for a wedding."""
    try:
        guest_count = await mongo.db["guests"].count_documents(
            {"wedding_id": wedding_id}
        )

        if guest_count == 0:
            return {
                "total_guests": 0,
                "accepted": 0,
                "declined": 0,
                "pending": 0,
                "response_rate": 0,
            }

        rsvps_cursor = mongo.db["rsvps"].find({"wedding_id": wedding_id})
        rsvps = await rsvps_cursor.to_list(length=None)

        accepted = 0
        declined = 0

        for rsvp in rsvps:
            status = get_rsvp_status(rsvp)
            if status == RSVP_STATUS_CONFIRMED:
                accepted += 1
            elif status == RSVP_STATUS_DECLINED:
                declined += 1

        pending = guest_count - len(rsvps)

        return {
            "total_guests": guest_count,
            "accepted": accepted,
            "declined": declined,
            "pending": pending,
            "response_rate": (
                round((len(rsvps) / guest_count * 100), 1) if guest_count > 0 else 0
            ),
        }
    except Exception as e:
        logger.error(f"Error fetching RSVP data for wedding {wedding_id}: {str(e)}")
        return {
            "total_guests": 0,
            "accepted": 0,
            "declined": 0,
            "pending": 0,
            "response_rate": 0,
        }


# =========================================================================
# BUDGET INSIGHTS (WFA-701)
# =========================================================================


@router.get("/weddings/{wedding_id}/budget-insights")
async def get_budget_insights(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI-powered budget insights for a wedding.

    Returns 3 actionable insights about the budget allocation.
    Cost: 3 credits
    """
    # Check if AI service is properly initialized
    if not ai_service._client:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ai_not_configured",
                "message": "AI service is not configured. Please contact the administrator.",
                "hint": "GEMINI_API_KEY environment variable may be missing.",
            },
        )

    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Get budget data
        budget_data = await get_budget_data(wedding_id)

        if not budget_data["categories"]:
            return {
                "insights": [],
                "message": "No budget data available. Add budget categories first.",
                "credits_used": 0,
            }

        # Build context with cultural and regional awareness
        venue = wedding.get("venue")
        location = None
        if isinstance(venue, dict):
            location = venue.get("city")
        elif isinstance(venue, str):
            location = venue
        location = (
            location
            or wedding.get("region")
            or wedding.get("city")
            or wedding.get("location")
        )

        # Get cultural style - explicit or inferred from events
        cultural_style = wedding.get("cultural_style")
        if not cultural_style:
            events = wedding.get("events", [])
            cultural_style = detect_cultural_style_from_events(events)

        # Get season from wedding date
        wedding_date = wedding.get("date")
        season = get_season_from_date(wedding_date)

        context = {
            "wedding_id": wedding_id,
            "wedding_date": wedding_date,
            "guest_count": wedding.get("guest_count", 100),
            "location": location,
            "cultural_style": cultural_style
            or "western",  # Default to western if not specified
            "season": season or "unknown",
            "total_budget": wedding.get("total_budget"),
            "budget": budget_data,
        }

        # Stable cache key — uses budget totals rather than full category details
        # to prevent cache misses when minor budget changes occur.
        # Full budget data is still sent to the AI for analysis.
        cache_context = {
            "wedding_id": wedding_id,
            "cultural_style": cultural_style or "western",
            "location": location,
            "season": season or "unknown",
            "total_budget": wedding.get("total_budget"),
            "budget_total": budget_data.get("total_budget", 0),
            "budget_spent": budget_data.get("total_spent", 0),
            "categories_count": len(budget_data.get("categories", [])),
        }

        # Generate insights with cultural context in prompt
        cultural_prompt = f"Analyze this {cultural_style or 'wedding'} budget"
        if location:
            cultural_prompt += f" for a wedding in {location}"
        if season:
            cultural_prompt += f" ({season.replace('_', '-')} season)"
        cultural_prompt += ". Provide culturally-aware insights considering typical costs and traditions for this wedding style."

        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="budget_insights",
            prompt=cultural_prompt,
            context=context,
            force_refresh=force_refresh,
            cache_context=cache_context,
        )

        return {
            "insights": result["response"].get("insights", []),
            "cached": result["cached"],
            "credits_used": result["credits_used"],
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating budget insights: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate budget insights"
        )


# =========================================================================
# DASHBOARD INSIGHTS (AI-002)
# =========================================================================


@router.get("/weddings/{wedding_id}/insights")
async def get_dashboard_insights(
    wedding_id: str,
    force_refresh: bool = False,
    cache_only: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI-powered actionable insights for a wedding dashboard.

    Returns 3-5 prioritized insights about:
    - RSVP status and follow-ups needed
    - Budget health and spending patterns
    - Upcoming deadlines and tasks
    - Vendor payments due
    - Timeline concerns

    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if cache_only:
            subscription_plan = await ai_service._resolve_subscription_plan(user_id)
            cached = await ai_cache_service.get_latest_cached_response(
                feature="dashboard_insights",
                tenant_id=wedding_id,
                subscription_plan=subscription_plan,
            )
            if cached:
                response = cached.get("response", {})
                insights = (
                    response.get("insights", []) if isinstance(response, dict) else []
                )
                return {
                    "insights": insights,
                    "wedding_id": wedding_id,
                    "cached": True,
                    "credits_used": 0,
                    "cache_only": True,
                }
            return {
                "insights": [],
                "wedding_id": wedding_id,
                "cached": False,
                "credits_used": 0,
                "cache_only": True,
                "requires_generation": True,
            }

        # Check if AI service is properly initialized only when generation is allowed.
        if not ai_service._client:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "ai_not_configured",
                    "message": "AI service is not configured. Please contact the administrator.",
                    "hint": "GEMINI_API_KEY environment variable may be missing.",
                },
            )

        # Gather comprehensive wedding data for analysis
        budget_data = await get_budget_data(wedding_id)
        rsvp_data = await get_rsvp_data(wedding_id)

        # Get upcoming tasks
        tasks = (
            await mongo.db["tasks"]
            .find({"wedding_id": wedding_id, "status": {"$ne": "completed"}})
            .sort("due_date", 1)
            .limit(10)
            .to_list(length=10)
        )

        upcoming_tasks = [
            {
                "title": t.get("title"),
                "due_date": str(t.get("due_date")) if t.get("due_date") else None,
                "priority": t.get("priority", "medium"),
                "category": t.get("category"),
            }
            for t in tasks
        ]

        # Get upcoming vendor payments
        from datetime import datetime, timedelta, timezone

        upcoming_deadline = datetime.now(timezone.utc) + timedelta(days=30)

        scheduled_payments = (
            await mongo.db["scheduled_payments"]
            .find(
                {
                    "wedding_id": wedding_id,
                    "status": {"$in": ["scheduled", "pending"]},
                    "due_date": {"$lte": upcoming_deadline},
                }
            )
            .sort("due_date", 1)
            .limit(5)
            .to_list(length=5)
        )

        vendor_payments = [
            {
                "vendor": p.get("vendor_name", "Unknown Vendor"),
                "amount": p.get("amount", 0),
                "due_date": str(p.get("due_date")) if p.get("due_date") else None,
                "status": p.get("status"),
            }
            for p in scheduled_payments
        ]

        # Calculate days until wedding
        days_until_wedding = None
        wedding_date_str = wedding.get("date")
        if wedding_date_str and isinstance(wedding_date_str, str):
            try:
                from datetime import datetime as dt
                from datetime import timezone

                wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                days_until_wedding = (wedding_date - dt.now(timezone.utc)).days
            except (ValueError, TypeError):
                # Ignore if date format is wrong
                pass

        # Build context for AI (full data for the AI model)
        context = {
            "wedding_id": wedding_id,
            "couple_names": wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "days_until_wedding": days_until_wedding,
            "guest_count": wedding.get("guest_count"),
            "cultural_style": wedding.get("cultural_style", "western"),
            "total_budget": wedding.get("total_budget"),
            "budget": budget_data,
            "rsvp": rsvp_data,
            "upcoming_tasks": upcoming_tasks,
            "vendor_payments": vendor_payments,
        }

        # Stable cache key context — excludes volatile data like upcoming_tasks,
        # vendor_payments, and computed days_until_wedding to prevent unnecessary
        # cache misses on page reload. The TTL handles staleness.
        cache_context = {
            "wedding_id": wedding_id,
            "wedding_date": wedding.get("date"),
            "guest_count": wedding.get("guest_count"),
            "cultural_style": wedding.get("cultural_style", "western"),
            "total_budget": wedding.get("total_budget"),
            "budget_total": budget_data.get("total_budget", 0),
            "budget_spent": budget_data.get("total_spent", 0),
            "rsvp_total": rsvp_data.get("total_guests", 0),
            "rsvp_confirmed": rsvp_data.get("accepted", 0),
        }

        # Generate insights
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="dashboard_insights",
            prompt="Analyze this wedding's current status and generate actionable insights for the planner.",
            context=context,
            force_refresh=force_refresh,
            cache_context=cache_context,
        )

        response = result["response"]
        insights = response.get("insights", []) if isinstance(response, dict) else []

        return {
            "insights": insights,
            "wedding_id": wedding_id,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating dashboard insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate insights")


# =========================================================================
# SEATING OPTIMIZATION (WFA-702, WFA-703, WFA-704)
# =========================================================================


@router.post("/weddings/{wedding_id}/seating-optimize")
async def optimize_seating(
    wedding_id: str,
    request: SeatingOptimizeRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    AI-powered seating optimization.

    Cost varies by guest count:
    - ≤50 guests: 2 credits
    - 51-150 guests: 5 credits
    - 150+ guests: 10 credits
    """
    # Check if AI service is properly initialized
    if not ai_service._client:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ai_not_configured",
                "message": "AI service is not configured. Please contact the administrator.",
                "hint": "GEMINI_API_KEY environment variable may be missing.",
            },
        )

    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if not request.guests or not request.tables:
            raise HTTPException(
                status_code=400,
                detail="Guests and tables are required for optimization",
            )

        guest_count = len(request.guests)

        # Determine feature based on guest count
        if guest_count <= 50:
            feature = "seating_small"
        elif guest_count <= 150:
            feature = "seating_medium"
        else:
            feature = "seating_large"

        # Fetch RSVP data to get dietary restrictions
        guest_ids = [g.get("id") or g.get("_id") for g in request.guests]
        rsvp_cursor = mongo.db["rsvps"].find(
            {"wedding_id": wedding_id, "guest_id": {"$in": guest_ids}}
        )
        rsvps = await rsvp_cursor.to_list(length=None)

        # Create lookup map for dietary info
        dietary_map: dict[str, str] = {}
        for rsvp in rsvps:
            rsvp_guest_id = rsvp.get("guest_id")
            dietary = rsvp.get("dietary")
            if rsvp_guest_id and dietary:
                dietary_map[rsvp_guest_id] = dietary

        # Sanitize guest data with enhanced seating fields
        # Include dietary, accessibility, relationships, and preferences
        sanitized_guests: list[dict] = []
        relationship_constraints: dict[str, list] = {
            "must_sit_together": [],  # Pairs of guest IDs
            "must_sit_apart": [],  # Pairs of guest IDs to separate
        }

        for g in request.guests:
            guest_id: str = g.get("id") or g.get("_id") or ""

            guest_data = {
                "id": guest_id,
                "name": g.get("name"),
                "group": g.get("group_id"),
                "role": g.get("role"),
                "plus_one": g.get("plus_one_allowed"),
                "party_size": 1
                + (
                    g.get("number_of_plus_ones_allowed", 0)
                    if g.get("plus_one_allowed")
                    else 0
                ),
                # Enhanced fields for smarter seating
                "dietary": dietary_map.get(guest_id) if guest_id else None,
                "accessibility": g.get("accessibility_needs"),
                "age_group": g.get("age_group"),
                "language": g.get("language_preference"),
                "seating_pref": g.get("seating_preference"),
            }
            sanitized_guests.append(guest_data)

            # Collect relationship constraints
            must_sit_with: list[str] = g.get("must_sit_with") or []
            must_sit_apart_list: list[str] = g.get("must_sit_apart") or []

            for partner_id in must_sit_with:
                if partner_id:  # Ensure partner_id is not None
                    pair = tuple(sorted([guest_id, str(partner_id)]))
                    if pair not in relationship_constraints["must_sit_together"]:
                        relationship_constraints["must_sit_together"].append(pair)

            for conflict_id in must_sit_apart_list:
                if conflict_id:  # Ensure conflict_id is not None
                    pair = tuple(sorted([guest_id, str(conflict_id)]))
                    if pair not in relationship_constraints["must_sit_apart"]:
                        relationship_constraints["must_sit_apart"].append(pair)

        # Convert tuples to lists for JSON serialization
        relationship_constraints["must_sit_together"] = [
            list(p) for p in relationship_constraints["must_sit_together"]
        ]
        relationship_constraints["must_sit_apart"] = [
            list(p) for p in relationship_constraints["must_sit_apart"]
        ]

        # Count special needs for context
        dietary_count = sum(1 for g in sanitized_guests if g.get("dietary"))
        accessibility_count = sum(1 for g in sanitized_guests if g.get("accessibility"))

        # Build context
        context = {
            "wedding_id": wedding_id,
            "guest_count": guest_count,
            "table_count": len(request.tables),
            "guests": sanitized_guests,
            "tables": request.tables,
            "constraints": request.constraints or {},
            "relationship_constraints": relationship_constraints,
            "special_needs_summary": {
                "guests_with_dietary_restrictions": dietary_count,
                "guests_with_accessibility_needs": accessibility_count,
                "total_must_sit_together_pairs": len(
                    relationship_constraints["must_sit_together"]
                ),
                "total_must_sit_apart_pairs": len(
                    relationship_constraints["must_sit_apart"]
                ),
            },
        }

        # Enhanced prompt with comprehensive constraints
        system_prompt = (
            "Create an optimal seating arrangement. CRITICAL RULES (in priority order): "
            "1. MUST respect 'must_sit_together' pairs - these guests MUST be at the same table. "
            "2. MUST respect 'must_sit_apart' pairs - these guests must be at DIFFERENT tables. "
            "3. Guests with accessibility needs should be placed at accessible tables (near exits, ground level). "
            "4. Keep guests with the same 'group' together where possible. "
            "5. Ensure VIPs/Family are at appropriate tables. "
            "6. Consider grouping guests with similar dietary restrictions for easier serving. "
            "7. Strictly respect table capacity limits. "
            "8. Keep plus-ones with their primary guest. "
            "9. Consider age groups - seat children near family, elders in quieter areas. "
            "10. Group guests by language preference for multilingual weddings."
        )

        # Generate seating arrangement
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature=feature,
            prompt=system_prompt,
            context=context,
            force_refresh=request.force_refresh,
        )

        # Validate AI response
        ai_tables = result["response"].get("tables", [])
        validation = validate_seating_suggestions(
            ai_tables=ai_tables,
            original_guests=request.guests,
            original_tables=request.tables,
        )

        # Log any warnings for monitoring
        if validation["warnings"]:
            logger.warning(
                f"Seating validation warnings for wedding {wedding_id}: "
                f"{len(validation['warnings'])} issue(s) found"
            )
            for warning in validation["warnings"]:
                logger.warning(f"  - {warning['message']}")

        return {
            "tables": validation["tables"],
            "guest_count": guest_count,
            "feature_used": feature,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "validation": {
                "warnings": validation["warnings"],
                "stats": validation["stats"],
            },
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error optimizing seating: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to optimize seating")


# =========================================================================
# COMMUNICATION COPILOT (WFA-705)
# =========================================================================


@router.post("/draft-communication")
async def draft_communication(
    request: DraftCommunicationRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    AI-powered email/message drafting.

    Supports types: follow_up, reminder, thank_you, progress_update
    Cost: 1 credit (not cached - context-dependent)
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))
        user_data = current_user.user_data or {}

        valid_types = ["follow_up", "reminder", "thank_you", "progress_update"]
        if request.communication_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid communication type. Must be one of: {valid_types}",
            )

        # Build context
        context = {
            "type": request.communication_type,
            "couple_name": request.couple_name,
            "wedding_date": request.wedding_date,
            "additional_context": request.context,
            "planner_name": user_data.get("first_name")
            or user_data.get("company_name"),
        }

        prompt = (
            request.custom_instructions
            or f"Draft a {request.communication_type.replace('_', ' ')} message."
        )

        # Generate draft (not cached)
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=user_id,  # Use user as tenant since this isn't wedding-specific
            feature="email_draft",
            prompt=prompt,
            context=context,
            force_refresh=True,  # Never cache drafts
        )

        # Extract text from response
        response_text = result["response"]
        if isinstance(response_text, dict):
            draft = response_text.get("text", str(response_text))
        else:
            draft = str(response_text)

        return {
            "draft": draft,
            "communication_type": request.communication_type,
            "credits_used": result["credits_used"],
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error drafting communication: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to draft communication")


# =========================================================================
# PROGRESS REPORT (WFA-706)
# =========================================================================


@router.get("/weddings/{wedding_id}/progress-report")
async def generate_progress_report(
    wedding_id: str,
    include_budget: bool = True,
    include_rsvp: bool = True,
    include_timeline: bool = True,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Generate a wedding progress report for the couple.

    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Gather data
        context = {
            "wedding_id": wedding_id,
            "wedding_title": wedding.get("title") or wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "couple_names": wedding.get("couple_names"),
        }

        if include_budget:
            context["budget"] = await get_budget_data(wedding_id)

        if include_rsvp:
            context["rsvp"] = await get_rsvp_data(wedding_id)

        if include_timeline:
            # Get upcoming tasks
            tasks = (
                await mongo.db["tasks"]
                .find({"wedding_id": wedding_id, "status": {"$ne": "completed"}})
                .sort("due_date", 1)
                .limit(5)
                .to_list(length=5)
            )

            context["upcoming_tasks"] = [
                {"title": t.get("title"), "due_date": t.get("due_date")} for t in tasks
            ]

        # Generate report
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="progress_report",
            prompt="Generate a progress report for this wedding.",
            context=context,
            force_refresh=force_refresh,
        )

        # Extract report text
        response = result["response"]
        if isinstance(response, dict):
            report = response.get("text", str(response))
        else:
            report = str(response)

        return {
            "report": report,
            "data_included": {
                "budget": include_budget,
                "rsvp": include_rsvp,
                "timeline": include_timeline,
            },
            "cached": result["cached"],
            "credits_used": result["credits_used"],
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating progress report: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate progress report"
        )


# =========================================================================
# PACKAGE PRICING SUGGESTIONS (WFA-707)
# =========================================================================


@router.post("/suggest-pricing")
async def suggest_pricing(
    request: PricingSuggestionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    AI-powered pricing suggestions for service packages.

    Cost: 3 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))
        user_data = current_user.user_data or {}

        if not request.services:
            raise HTTPException(
                status_code=400, detail="At least one service is required"
            )

        # Build context
        context = {
            "services": request.services,
            "location": request.location or "USA",
            "wedding_size": request.wedding_size or 100,
            "planner_experience": user_data.get("years_experience", "unknown"),
        }

        # Generate pricing suggestion
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=user_id,
            feature="package_pricing",
            prompt="Suggest pricing for this wedding package.",
            context=context,
            force_refresh=request.force_refresh,
        )

        response = result["response"]

        return {
            "pricing": {
                "min_price": response.get("min_price"),
                "max_price": response.get("max_price"),
                "recommended": response.get("recommended"),
                "market_comparison": response.get("market_comparison", "at"),
                "schedule_suggestion": response.get("schedule_suggestion", []),
            },
            "cached": result["cached"],
            "credits_used": result["credits_used"],
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error suggesting pricing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to suggest pricing")


# =========================================================================
# CONTRACT SECTION GENERATION (AI-005)
# =========================================================================


class ContractSectionRequest(BaseModel):
    section_type: str = Field(
        ..., max_length=50
    )  # payment_terms, cancellation_policy, scope_of_work, liability, force_majeure, custom
    vendor_type: Optional[str] = Field(
        None, max_length=100
    )  # photographer, caterer, florist, dj, venue, etc.
    wedding_id: Optional[str] = None
    custom_prompt: Optional[str] = Field(None, max_length=3000)


@router.post("/generate-contract-section")
async def generate_contract_section(
    request: ContractSectionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Generate contract clause content using AI.

    Section types:
    - payment_terms: Payment schedule, methods, late fees
    - cancellation_policy: Cancellation terms, refunds, notice periods
    - scope_of_work: Detailed deliverables and services
    - liability: Liability limitations, insurance
    - force_majeure: Force majeure clauses
    - custom: Based on custom_prompt

    Cost: 1 credit per generation
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # A8: Pre-check AI credits before expensive contract generation
        try:
            credit_check = await ai_service.check_credits(user_id, "contract_section")
            if not credit_check.get("allowed", True):
                raise InsufficientCreditsError(
                    message=credit_check.get("message", "Insufficient AI credits"),
                    required=credit_check.get("credits_needed", 1),
                    available=credit_check.get("credits_remaining", 0),
                )
        except InsufficientCreditsError:
            raise
        except Exception:
            pass  # Allow through if credit check itself fails — generate() will re-check

        valid_sections = [
            "payment_terms",
            "cancellation_policy",
            "scope_of_work",
            "liability",
            "force_majeure",
            "custom",
        ]
        if request.section_type not in valid_sections:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section_type. Must be one of: {valid_sections}",
            )

        # If custom section, require custom_prompt
        if request.section_type == "custom" and not request.custom_prompt:
            raise HTTPException(
                status_code=400,
                detail="custom_prompt is required when section_type is 'custom'",
            )

        # Build context
        context = {
            "section_type": request.section_type,
            "vendor_type": request.vendor_type or "general vendor",
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403, detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                context["wedding_couple_names"] = wedding.get("couple_names", "")
                context["wedding_date"] = wedding.get("date", "")
                context["wedding_cultural_style"] = wedding.get("cultural_style", "")
                context["wedding_region"] = wedding.get("region", "")

        # Build prompt based on section type
        section_prompts = {
            "payment_terms": f"Generate payment terms for a {request.vendor_type or 'wedding vendor'} contract. Include payment schedule, accepted methods, deposit requirements, and late payment policies.",
            "cancellation_policy": f"Generate a cancellation policy for a {request.vendor_type or 'wedding vendor'} contract. Include cancellation windows, refund schedules, and notice requirements.",
            "scope_of_work": f"Generate a scope of work section for a {request.vendor_type or 'wedding vendor'} contract. Detail the services, deliverables, timeline, and what is/isn't included.",
            "liability": f"Generate a liability clause for a {request.vendor_type or 'wedding vendor'} contract. Include limitation of liability, insurance requirements, and indemnification.",
            "force_majeure": f"Generate a force majeure clause for a {request.vendor_type or 'wedding vendor'} contract. Include covered events, notification requirements, and remedies.",
            "custom": request.custom_prompt,
        }

        prompt = section_prompts[request.section_type]

        # Ensure prompt is not None (should not happen due to earlier validation, but for type safety)
        if prompt is None:
            raise HTTPException(
                status_code=400,
                detail="Unable to generate prompt for the specified section type",
            )

        # Add custom instructions if provided for non-custom sections
        if request.custom_prompt and request.section_type != "custom":
            prompt += f"\n\nAdditional requirements: {request.custom_prompt}"

        # Generate content
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id or user_id,
            feature="contract_section",
            prompt=prompt,
            context=context,
            force_refresh=True,  # Never cache - each generation is unique
        )

        # Extract text from response
        response = result["response"]
        if isinstance(response, dict):
            content = response.get("text", str(response))
        else:
            content = str(response)

        return {
            "content": content,
            "section_type": request.section_type,
            "vendor_type": request.vendor_type,
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating contract section: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate contract section"
        )


# =========================================================================
# VENDOR RECOMMENDATIONS (AI-011)
# =========================================================================


class VendorRecommendationRequest(BaseModel):
    vendor_type: str  # photographer, caterer, florist, dj, venue, etc.
    budget_range: Optional[Dict[str, float]] = None  # {"min": 0, "max": 0}
    wedding_style: Optional[str] = None  # western, nigerian, indian, jewish, etc.
    region: Optional[str] = None  # City, State or Country
    guest_count: Optional[int] = None
    wedding_id: Optional[str] = None  # For more context


@router.post("/vendor-recommendations")
async def get_vendor_recommendations(
    request: VendorRecommendationRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI-powered vendor selection criteria and recommendations.

    Returns:
    - Selection criteria for the vendor type
    - Questions to ask during consultations
    - Red flags to watch for
    - Budget assessment for the region
    - Pro tips

    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Build context
        context = {
            "vendor_type": request.vendor_type,
            "budget_range": request.budget_range or {"min": 0.0, "max": 0.0},
            "wedding_style": request.wedding_style or "western",
            "region": request.region or "USA",
            "guest_count": request.guest_count or 100,
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403, detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                # Override with wedding data if not explicitly provided
                context["wedding_style"] = request.wedding_style or wedding.get(
                    "cultural_style", "western"
                )
                context["region"] = (
                    request.region or wedding.get("region") or wedding.get("venue")
                )
                context["guest_count"] = request.guest_count or wedding.get(
                    "guest_count", 100
                )
                context["wedding_date"] = wedding.get("date")

        prompt = f"Provide vendor selection guidance for hiring a {request.vendor_type} for a {context['wedding_style']} wedding in {context['region']} with approximately {context['guest_count']} guests."

        if request.budget_range:
            if request.budget_range.get("min") and request.budget_range.get("max"):
                prompt += f" The budget range is ${request.budget_range['min']:,.0f} - ${request.budget_range['max']:,.0f}."
            elif request.budget_range.get("max"):
                prompt += f" The budget is up to ${request.budget_range['max']:,.0f}."

        # Generate recommendations
        # Use wedding_id as tenant for caching — if no wedding context,
        # use a unique key to prevent cache pollution across weddings
        if request.wedding_id:
            rec_tenant_id = request.wedding_id
            rec_force_refresh = False
        else:
            rec_tenant_id = f"user_{user_id}_no_wedding"
            rec_force_refresh = True  # No caching without wedding context

        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=rec_tenant_id,
            feature="vendor_recommendations",
            prompt=prompt,
            context=context,
            force_refresh=rec_force_refresh,
        )

        response = result["response"]

        return {
            "recommendations": (
                response if isinstance(response, dict) else {"raw": response}
            ),
            "vendor_type": request.vendor_type,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating vendor recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate vendor recommendations"
        )


# =========================================================================
# TASK PRIORITIZATION (AI-013)
# =========================================================================


@router.post("/weddings/{wedding_id}/prioritize-tasks")
async def prioritize_tasks(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI-powered task prioritization for a wedding.

    Analyzes:
    - Wedding date and time remaining
    - Pending tasks
    - Vendor deadlines
    - Cultural considerations

    Returns prioritized task list with urgency levels.
    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Calculate days until wedding
        from datetime import datetime as dt
        from datetime import timedelta, timezone

        days_until_wedding = None
        wedding_date_str = wedding.get("date")
        if wedding_date_str and isinstance(wedding_date_str, str):
            try:
                wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                days_until_wedding = (wedding_date - dt.now(timezone.utc)).days
            except Exception:
                pass

        # Get all pending tasks
        tasks = (
            await mongo.db["tasks"]
            .find({"wedding_id": wedding_id, "status": {"$ne": "completed"}})
            .sort("due_date", 1)
            .to_list(length=50)
        )

        pending_tasks = [
            {
                "title": t.get("title"),
                "description": t.get("description"),
                "due_date": str(t.get("due_date")) if t.get("due_date") else None,
                "priority": t.get("priority", "medium"),
                "category": t.get("category"),
                "status": t.get("status", "pending"),
            }
            for t in tasks
        ]

        # Get upcoming vendor payments/deadlines
        upcoming_deadline = dt.now(timezone.utc) + timedelta(days=60)
        vendor_deadlines = (
            await mongo.db["scheduled_payments"]
            .find(
                {
                    "wedding_id": wedding_id,
                    "status": {"$in": ["scheduled", "pending"]},
                    "due_date": {"$lte": upcoming_deadline},
                }
            )
            .sort("due_date", 1)
            .limit(10)
            .to_list(length=10)
        )

        deadlines = [
            {
                "vendor": p.get("vendor_name", "Vendor"),
                "type": "payment",
                "amount": p.get("amount", 0),
                "due_date": str(p.get("due_date")) if p.get("due_date") else None,
            }
            for p in vendor_deadlines
        ]

        # Build context
        context = {
            "wedding_id": wedding_id,
            "couple_names": wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "days_until_wedding": days_until_wedding,
            "cultural_style": wedding.get("cultural_style", "western"),
            "guest_count": wedding.get("guest_count"),
            "current_date": dt.now(timezone.utc).strftime("%Y-%m-%d"),
            "pending_tasks": pending_tasks,
            "vendor_deadlines": deadlines,
        }

        prompt = "Analyze these wedding planning tasks and vendor deadlines. Prioritize them based on the wedding date, dependencies, and urgency. Identify what should be done this week."

        # Generate prioritization
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="task_prioritization",
            prompt=prompt,
            context=context,
            force_refresh=force_refresh,
        )

        response = result["response"]

        return {
            "prioritization": (
                response if isinstance(response, dict) else {"raw": response}
            ),
            "wedding_id": wedding_id,
            "days_until_wedding": days_until_wedding,
            "tasks_analyzed": len(pending_tasks),
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error prioritizing tasks: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to prioritize tasks")


# =========================================================================
# TIMELINE GENERATOR (AI-015)
# =========================================================================


class TimelineGeneratorRequest(BaseModel):
    wedding_id: str
    force_refresh: bool = False


@router.post("/generate-timeline")
async def generate_timeline(
    request: TimelineGeneratorRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Generate a comprehensive wedding planning timeline.

    Creates milestone-based timeline from now to the wedding date.
    Considers cultural style, guest count, and budget.

    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, request.wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(request.wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        wedding_date_str = wedding.get("date")
        if not wedding_date_str:
            raise HTTPException(
                status_code=400,
                detail="Wedding date is required to generate a timeline",
            )

        # Calculate timeline parameters
        from datetime import datetime as dt
        from datetime import timezone

        wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        current_date = dt.now(timezone.utc)
        days_until_wedding = (wedding_date - current_date).days
        months_until_wedding = days_until_wedding / 30

        # Get existing tasks to avoid duplicates in suggestions
        existing_tasks = (
            await mongo.db["tasks"]
            .find({"wedding_id": request.wedding_id})
            .to_list(length=100)
        )

        existing_task_titles = [t.get("title", "").lower() for t in existing_tasks]

        # Build context
        context = {
            "wedding_id": request.wedding_id,
            "couple_names": wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "current_date": current_date.strftime("%Y-%m-%d"),
            "days_until_wedding": days_until_wedding,
            "months_until_wedding": round(months_until_wedding, 1),
            "cultural_style": wedding.get("cultural_style", "western"),
            "guest_count": wedding.get("guest_count", 100),
            "total_budget": wedding.get("total_budget"),
            "region": wedding.get("region") or wedding.get("venue"),
            "existing_tasks_count": len(existing_tasks),
            "existing_task_samples": existing_task_titles[:10],  # First 10 for context
        }

        prompt = f"Generate a wedding planning timeline for a {context['cultural_style']} wedding with {context['guest_count']} guests. The wedding is on {wedding.get('date')}, which is {days_until_wedding} days ({round(months_until_wedding, 1)} months) away. Create realistic milestones starting from today ({current_date.strftime('%Y-%m-%d')})."

        # Generate timeline
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id,
            feature="timeline_generator",
            prompt=prompt,
            context=context,
            force_refresh=request.force_refresh,
        )

        response = result["response"]

        return {
            "timeline": response if isinstance(response, dict) else {"raw": response},
            "wedding_id": request.wedding_id,
            "wedding_date": wedding.get("date"),
            "days_until_wedding": days_until_wedding,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating timeline: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate timeline")


# =========================================================================
# PAYMENT FORECAST (AI-016)
# =========================================================================


@router.get("/weddings/{wedding_id}/payment-forecast")
async def get_payment_forecast(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI-powered payment forecast and cash flow analysis.

    Analyzes scheduled payments and provides:
    - 30/60/90 day forecast
    - Peak payment dates
    - Cash flow warnings
    - Recommendations

    Cost: 2 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        from datetime import datetime as dt
        from datetime import timezone

        # Get all scheduled payments
        scheduled_payments = (
            await mongo.db["scheduled_payments"]
            .find({"wedding_id": wedding_id})
            .sort("due_date", 1)
            .to_list(length=100)
        )

        # Get paid payments for historical context
        paid_payments = (
            await mongo.db["payment_records"]
            .find({"wedding_id": wedding_id, "status": "succeeded"})
            .to_list(length=100)
        )

        # Format payments data
        now = dt.now(timezone.utc)
        payments_data = []
        for p in scheduled_payments:
            due_date = p.get("due_date")
            status = p.get("status", "scheduled")

            # Calculate if overdue
            if due_date and due_date < now and status not in ["paid", "completed"]:
                status = "overdue"

            payments_data.append(
                {
                    "vendor": p.get("vendor_name", "Unknown Vendor"),
                    "amount": p.get("amount", 0),
                    "due_date": str(due_date) if due_date else None,
                    "status": status,
                    "description": p.get("description", ""),
                }
            )

        # Calculate totals
        total_due = sum(
            p.get("amount", 0)
            for p in scheduled_payments
            if p.get("status") not in ["paid", "completed"]
        )
        total_paid = sum(p.get("amount", 0) for p in paid_payments)

        # Build context
        context = {
            "wedding_id": wedding_id,
            "couple_names": wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "total_budget": wedding.get("total_budget"),
            "current_date": now.strftime("%Y-%m-%d"),
            "scheduled_payments": payments_data,
            "total_due": total_due,
            "total_paid": total_paid,
            "payment_count": len(payments_data),
        }

        if not payments_data:
            return {
                "forecast": {
                    "forecast_periods": [],
                    "cash_flow_warning": None,
                    "peak_payment_dates": [],
                    "recommendations": [],
                    "summary": {
                        "total_remaining": 0,
                        "total_paid": total_paid,
                        "next_payment_date": None,
                        "largest_upcoming": None,
                    },
                },
                "wedding_id": wedding_id,
                "message": "No scheduled payments found",
                "cached": False,
                "credits_used": 0,
            }

        prompt = "Analyze this wedding's payment schedule and provide a cash flow forecast. Identify any concerns, peak payment periods, and recommendations for managing payments."

        # Generate forecast
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="payment_forecast",
            prompt=prompt,
            context=context,
            force_refresh=force_refresh,
        )

        response = result["response"]

        return {
            "forecast": response if isinstance(response, dict) else {"raw": response},
            "wedding_id": wedding_id,
            "total_payments": len(payments_data),
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating payment forecast: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to generate payment forecast"
        )


# =========================================================================
# VENDOR PRICE ANALYSIS (AI-018)
# =========================================================================


class VendorPriceAnalysisRequest(BaseModel):
    vendor_type: str  # photographer, caterer, florist, dj, venue, etc.
    quoted_price: float
    region: Optional[str] = None
    wedding_style: Optional[str] = None
    guest_count: Optional[int] = None
    service_description: Optional[str] = None  # What's included in the quote
    wedding_id: Optional[str] = None


@router.post("/analyze-vendor-price")
async def analyze_vendor_price(
    request: VendorPriceAnalysisRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Analyze if a vendor quote is fair for the region and service type.

    Returns:
    - Market comparison verdict
    - Typical price range for the region
    - Factors affecting the price
    - Negotiation recommendations

    Cost: 1 credit
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Build context
        context = {
            "vendor_type": request.vendor_type,
            "quoted_price": request.quoted_price,
            "region": request.region or "USA",
            "wedding_style": request.wedding_style or "western",
            "guest_count": request.guest_count or 100,
            "service_description": request.service_description,
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403, detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                context["wedding_style"] = request.wedding_style or wedding.get(
                    "cultural_style", "western"
                )
                context["region"] = (
                    request.region or wedding.get("region") or wedding.get("venue")
                )
                context["guest_count"] = request.guest_count or wedding.get(
                    "guest_count", 100
                )

        prompt = f"Analyze this vendor quote: A {request.vendor_type} in {context['region']} is quoting ${request.quoted_price:,.2f} for a {context['wedding_style']} wedding with {context['guest_count']} guests."

        if request.service_description:
            prompt += f" The quote includes: {request.service_description}"

        prompt += " Is this a fair price? How does it compare to market rates?"

        # Generate analysis
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id or user_id,
            feature="vendor_price_analysis",
            prompt=prompt,
            context=context,
            force_refresh=False,
        )

        response = result["response"]

        return {
            "analysis": response if isinstance(response, dict) else {"raw": response},
            "vendor_type": request.vendor_type,
            "quoted_price": request.quoted_price,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error analyzing vendor price: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze vendor price")


# =========================================================================
# UTILITY ENDPOINTS
# =========================================================================


@router.get("/features")
async def list_ai_features(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    List all available AI features with their credit costs.
    """
    return {"features": ai_service.list_features()}


@router.get("/credits")
async def check_ai_credits(
    feature: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Check AI credit balance and feature availability.
    """
    user_id = str((current_user.user_data or {}).get("_id", ""))

    if feature:
        try:
            check = await ai_service.check_credits(user_id, feature)
            return check
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        # Return general credit info. AI credits are now soft-capped with
        # metered overage billing — pass the overage fields through so the
        # planner billing UI can render the overage banner and running cost.
        # See SubscriptionService.check_usage_limits() ai_credits branch.
        from app.services.subscription_service import SubscriptionService

        sub_service = SubscriptionService()
        result = await sub_service.check_usage_limits(
            user_id=user_id, resource_type="ai_credits", requested_amount=0
        )
        return {
            "credits_remaining": result.get("remaining", 0),
            "credits_limit": result.get("limit", 0),
            # The ai_credits branch in check_usage_limits returns
            # ``current_usage``; ``used`` is a legacy alias other branches
            # don't emit. Fall back to ``used`` only if ``current_usage`` is
            # missing so we stay forward-compatible.
            "credits_used": result.get("current_usage", result.get("used", 0)),
            "overage": result.get("overage", False),
            "overage_credits": result.get("overage_credits", 0),
            "overage_price_per_credit_usd": result.get(
                "overage_price_per_credit_usd", 0.0
            ),
            "overage_cost_cents": result.get("overage_cost_cents", 0),
        }


@router.get("/usage")
async def get_ai_usage(
    period_days: int = 7,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Get AI usage metrics for the current user.
    """
    user_id = str((current_user.user_data or {}).get("_id", ""))

    metrics = await ai_service.get_usage_metrics(
        period_days=period_days, tenant_id=user_id
    )

    return metrics


# =========================================================================
# INTERACTIVE AI CHAT (Conversational Assistant)
# =========================================================================


class PageContextModel(BaseModel):
    """Page context for enhanced AI responses based on current page."""

    page: str  # e.g., "contract_canvas", "budget", "guests"
    hint: str  # System hint for AI context


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    wedding_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = (
        None  # [{role: "user"/"assistant", content: "..."}]
    )
    page_context: Optional[PageContextModel] = (
        None  # Current page context for enhanced responses
    )


class ChatResponse(BaseModel):
    response: str
    credits_used: int
    credits_remaining: Optional[int] = None
    warning: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatMessageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Interactive chat with the AI wedding planning assistant.

    Features:
    - Maintains conversation context via conversation_history
    - Optionally scoped to a specific wedding for contextual answers
    - 1 credit per message
    - Culturally-aware responses when wedding context is provided
    """
    # Check if AI service is properly initialized
    if not ai_service._client:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "ai_not_configured",
                "message": "AI service is not configured. Please contact the administrator.",
                "hint": "GEMINI_API_KEY environment variable may be missing.",
            },
        )

    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Build context with wedding data if provided
        context: Dict[str, Any] = {
            "user_message": request.message,
            "planner_email": current_user.email,
        }

        # Add page context for enhanced responses
        if request.page_context:
            context["page_context"] = {
                "page": request.page_context.page,
                "hint": request.page_context.hint,
            }

        # Add conversation history for context
        if request.conversation_history:
            # Only include last 10 messages to avoid token limits
            context["conversation_history"] = request.conversation_history[-10:]

        # If wedding_id provided, verify access and add wedding context
        if request.wedding_id:
            # Verify planner has access to this wedding
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403, detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                # Get budget data for context
                budget_data = await get_budget_data(request.wedding_id)

                context["wedding"] = {
                    "couple_names": wedding.get("couple_names"),
                    "date": wedding.get("date"),
                    "guest_count": wedding.get("guest_count"),
                    "cultural_style": wedding.get("cultural_style", "western"),
                    "region": wedding.get("region") or wedding.get("venue"),
                    "total_budget": wedding.get("total_budget"),
                    "budget_summary": {
                        "total_budgeted": budget_data.get("total_budget", 0),
                        "total_spent": budget_data.get("total_spent", 0),
                        "remaining": budget_data.get("remaining", 0),
                        "categories_count": len(budget_data.get("categories", [])),
                    },
                }

        # Build the prompt with conversation context and page hint
        prompt_parts = []

        # Add page context hint as system guidance
        if request.page_context and request.page_context.hint:
            prompt_parts.append(f"[Context: {request.page_context.hint}]")

        # Add conversation history
        if request.conversation_history:
            history_text = "\n".join(
                [
                    f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                    for msg in request.conversation_history[-10:]
                ]
            )
            prompt_parts.append(f"Previous conversation:\n{history_text}")

        # Add the user's message
        prompt_parts.append(f"User's message: {request.message}")

        prompt = "\n\n".join(prompt_parts)

        # Generate response
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id or user_id,
            feature="chat",
            prompt=prompt,
            context=context,
            force_refresh=True,  # Chat is never cached
        )

        # Extract response text
        response_content = result["response"]
        if isinstance(response_content, dict):
            response_text = response_content.get("text", str(response_content))
        else:
            response_text = str(response_content)

        return ChatResponse(
            response=response_text,
            credits_used=result["credits_used"],
            credits_remaining=result.get("credits_remaining"),
            warning=result.get("warning"),
        )

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


# =========================================================================
# COMMAND CENTER ORCHESTRATOR
# =========================================================================


class CommandCenterRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    wedding_id: str
    execute_actions: bool = (
        False  # False for Freemium preview (dry run), True for paid execution
    )


command_center_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_wedding_budget",
                description="Fetch the current budget categories, totals, and remaining budget.",
            ),
            types.FunctionDeclaration(
                name="get_guest_list",
                description="Fetch the guest list and RSVP status.",
            ),
            types.FunctionDeclaration(
                name="add_task_to_checklist",
                description="Add a new task to the wedding planning checklist.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "title": types.Schema(
                            type=types.Type.STRING, description="The title of the task"
                        ),
                        "due_date": types.Schema(
                            type=types.Type.STRING,
                            description="The due date of the task in YYYY-MM-DD format (optional)",
                        ),
                    },
                    required=["title"],
                ),
            ),
            types.FunctionDeclaration(
                name="update_budget_item",
                description="Update or add a budget item's cost (e.g. Catering, Venue).",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="The budget category name (e.g. Catering, Venue, Photography)",
                        ),
                        "amount": types.Schema(
                            type=types.Type.NUMBER,
                            description="The new estimated or actual cost",
                        ),
                    },
                    required=["category", "amount"],
                ),
            ),
            types.FunctionDeclaration(
                name="add_guest",
                description="Add a new guest to the guest list.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "name": types.Schema(
                            type=types.Type.STRING, description="The guest's full name"
                        ),
                        "email": types.Schema(
                            type=types.Type.STRING,
                            description="The guest's email address (optional)",
                        ),
                        "group": types.Schema(
                            type=types.Type.STRING,
                            description="The guest's group (e.g. Family, Friends) (optional)",
                        ),
                    },
                    required=["name"],
                ),
            ),
            types.FunctionDeclaration(
                name="draft_email",
                description="Draft an email to a vendor or guest.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "recipient_type": types.Schema(
                            type=types.Type.STRING, description="'guest' or 'vendor'"
                        ),
                        "subject": types.Schema(
                            type=types.Type.STRING, description="The email subject"
                        ),
                        "body": types.Schema(
                            type=types.Type.STRING, description="The email body content"
                        ),
                    },
                    required=["recipient_type", "subject", "body"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_hired_vendors",
                description="Fetch the list of hired vendors for the wedding.",
            ),
        ]
    )
]


@router.post("/weddings/{wedding_id}/command-center")
async def ai_command_center(
    wedding_id: str,
    request: CommandCenterRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Full AI Command Center endpoint.
    Orchestrates the execution of platform tools on behalf of the user.
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Build context
        context = {
            "user_message": request.message,
            "wedding_id": wedding_id,
            "couple_names": wedding.get("couple_names"),
            "wedding_date": wedding.get("date"),
            "execute_actions": request.execute_actions,  # For Freemium logic
        }

        system_prompt = f"User's request: {request.message}\n\nYou are an autonomous Expert Wedding Planner Copilot. You have access to several tools to read and modify data. Think step-by-step. If asked to do something complex, break it down. For example, to follow up on a budget, first get the budget, then draft an email. If you decide to modify data (add task, update budget, draft email) just call the function. We will handle showing the user a preview if they are on a free tier."

        # Step 1: Let the AI decide what tools to call
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="command_center",
            prompt=system_prompt,
            context=context,
            force_refresh=True,
            tools=command_center_tools,
        )

        response_content = result["response"]
        credits_used = result["credits_used"]

        # Step 2: Check if AI decided to call functions
        executed_actions = []
        function_calls = []

        if isinstance(response_content, dict) and "function_calls" in response_content:
            function_calls = response_content["function_calls"]

            # Step 3: Execute local platform functions
            for fc in function_calls:
                func_name = fc["name"]
                func_args = fc.get("args", {})

                action_result = None

                # Execute matching tool
                if func_name == "get_wedding_budget":
                    budget_data = await get_budget_data(wedding_id)
                    action_result = {"budget_data": budget_data}
                elif func_name == "get_guest_list":
                    # Simple guest count and RSVP summary for now
                    guests_cursor = mongo.db["guests"].find({"wedding_id": wedding_id})
                    guests = await guests_cursor.to_list(length=100)
                    action_result = {
                        "guest_count": len(guests),
                        "guests": [
                            {"name": g.get("name"), "status": g.get("rsvp_status")}
                            for g in guests
                        ],
                    }
                elif func_name == "get_hired_vendors":
                    vendors_cursor = mongo.db["vendors"].find(
                        {"wedding_id": wedding_id, "status": "hired"}
                    )
                    vendors = await vendors_cursor.to_list(length=100)
                    action_result = {
                        "vendor_count": len(vendors),
                        "vendors": [
                            {
                                "name": v.get("name"),
                                "category": v.get("category"),
                                "email": v.get("email"),
                            }
                            for v in vendors
                        ],
                    }
                elif func_name in [
                    "add_task_to_checklist",
                    "update_budget_item",
                    "add_guest",
                    "draft_email",
                ]:
                    if not request.execute_actions:
                        # Freemium Preview: Tell the frontend what WOULD have happened
                        preview_msg = f"Would {func_name.replace('_', ' ')} with args: {func_args}"
                        action_result = {
                            "preview_only": True,
                            "message": preview_msg,
                            "upgrade_required": True,
                            "drafted_args": func_args,
                        }
                    else:
                        # Paid Tier: Execute
                        if func_name == "add_task_to_checklist":
                            from datetime import datetime, timezone

                            new_task = {
                                "wedding_id": wedding_id,
                                "title": func_args.get("title"),
                                "status": "pending",
                                "created_at": datetime.now(timezone.utc),
                            }
                            if "due_date" in func_args:
                                try:
                                    new_task["due_date"] = datetime.strptime(
                                        func_args["due_date"], "%Y-%m-%d"
                                    ).replace(tzinfo=timezone.utc)
                                except ValueError:
                                    pass
                            insert_res = await mongo.db["tasks"].insert_one(new_task)
                            action_result = {
                                "status": "success",
                                "task_id": str(insert_res.inserted_id),
                                "task": new_task["title"],
                            }

                        elif func_name == "update_budget_item":
                            # Simplistic update for demonstration
                            await mongo.db["budget_items"].update_one(
                                {
                                    "wedding_id": wedding_id,
                                    "category": func_args.get("category"),
                                },
                                {"$set": {"amount": func_args.get("amount")}},
                                upsert=True,
                            )
                            action_result = {
                                "status": "success",
                                "message": f"Updated {func_args.get('category')} budget to ${func_args.get('amount')}",
                            }

                        elif func_name == "add_guest":
                            new_guest = {
                                "wedding_id": wedding_id,
                                "name": func_args.get("name"),
                                "email": func_args.get("email"),
                                "group": func_args.get("group"),
                                "rsvp_status": "pending",
                            }
                            insert_res = await mongo.db["guests"].insert_one(new_guest)
                            action_result = {
                                "status": "success",
                                "guest_id": str(insert_res.inserted_id),
                                "name": new_guest["name"],
                            }

                        elif func_name == "draft_email":
                            new_draft = {
                                "wedding_id": wedding_id,
                                "recipient_type": func_args.get("recipient_type"),
                                "subject": func_args.get("subject"),
                                "body": func_args.get("body"),
                                "status": "draft",
                            }
                            insert_res = await mongo.db["communications"].insert_one(
                                new_draft
                            )
                            action_result = {
                                "status": "success",
                                "draft_id": str(insert_res.inserted_id),
                                "message": "Email drafted successfully",
                            }
                else:
                    action_result = {"error": f"Unknown function {func_name}"}

                executed_actions.append(
                    {"name": func_name, "args": func_args, "result": action_result}
                )

            # Step 4: Send results back to AI for final synthesis
            # Note: A fully robust implementation would map function_responses into the conversational history.
            # For simplicity, we just send a second generation request with the tool outputs.
            synthesis_prompt = f"User's request: {request.message}\n\nYou executed the following tools and got these results:\n{executed_actions}\n\nPlease provide a final human-readable response to the user summarizing what you found or what you did."

            final_result = await ai_service.generate(
                user_id=user_id,
                tenant_id=wedding_id,
                feature="command_center",
                prompt=synthesis_prompt,
                context=context,
                force_refresh=True,
            )

            response_content = final_result["response"]
            credits_used += final_result["credits_used"]

        # Parse text from final response
        if isinstance(response_content, dict):
            response_text = response_content.get("text", str(response_content))
        else:
            response_text = str(response_content)

        return {
            "response": response_text,
            "actions_executed": executed_actions,
            "credits_used": credits_used,
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error in AI command center: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to process command center request"
        )


# =========================================================================
# MESSAGE GENERATOR (JOA-151 / AI-008)
# =========================================================================


class GenerateMessageRequest(BaseModel):
    message_type: str = Field(
        ..., max_length=50
    )  # rsvp_reminder, save_the_date, thank_you, vendor_reminder, event_reminder, custom
    wedding_id: str
    tone: str = Field("friendly", max_length=20)  # formal, friendly, casual
    recipient_context: Optional[str] = Field(
        None, max_length=200
    )  # family, friend, vendor, etc.
    custom_instructions: Optional[str] = Field(None, max_length=2000)
    couple_names: Optional[str] = Field(None, max_length=200)
    wedding_date: Optional[str] = None
    event_name: Optional[str] = Field(None, max_length=200)


@router.post("/generate-message")
async def generate_message(
    request: GenerateMessageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Generate a personalized wedding communication message.

    Cost: 1 credit
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, request.wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Get wedding details for context
        wedding = await get_wedding_by_id(request.wedding_id)

        context = {
            "message_type": request.message_type,
            "tone": request.tone,
            "recipient_context": request.recipient_context,
            "couple_names": request.couple_names
            or (wedding.get("couple_names") if wedding else None),
            "wedding_date": request.wedding_date
            or (wedding.get("date") if wedding else None),
            "event_name": request.event_name,
            "custom_instructions": request.custom_instructions,
        }

        prompt = f"Generate a {request.tone} {request.message_type} message"
        if request.recipient_context:
            prompt += f" for a {request.recipient_context}"
        if request.custom_instructions:
            prompt += f". Special instructions: {request.custom_instructions}"

        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id,
            feature="message_generator",
            prompt=prompt,
            context=context,
            force_refresh=True,  # Messages should always be fresh
        )

        response = result["response"]

        return {
            "message": (
                response if isinstance(response, dict) else {"body": str(response)}
            ),
            "message_type": request.message_type,
            "tone": request.tone,
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate message")


# =========================================================================
# FORM QUESTIONS GENERATOR (JOA-153 / AI-010)
# =========================================================================


class GenerateFormQuestionsRequest(BaseModel):
    form_type: str = Field(
        ..., max_length=50
    )  # rsvp, dietary, song_requests, accommodation, transportation, custom
    wedding_id: str
    cultural_style: Optional[str] = Field(
        None, max_length=100
    )  # nigerian, indian, jewish, western, etc.
    custom_context: Optional[str] = Field(None, max_length=2000)
    existing_questions: Optional[List[str]] = None  # To avoid duplicates


@router.post("/generate-form-questions")
async def generate_form_questions(
    request: GenerateFormQuestionsRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Generate smart form questions based on form type and wedding context.

    Cost: 1 credit
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, request.wedding_id):
            raise HTTPException(
                status_code=403, detail="You don't have access to this wedding"
            )

        # Get wedding details for context
        wedding = await get_wedding_by_id(request.wedding_id)

        context = {
            "form_type": request.form_type,
            "cultural_style": request.cultural_style
            or (wedding.get("cultural_style") if wedding else "western"),
            "couple_names": wedding.get("couple_names") if wedding else None,
            "wedding_date": wedding.get("date") if wedding else None,
            "guest_count": wedding.get("guest_count") if wedding else None,
            "custom_context": request.custom_context,
            "existing_questions": request.existing_questions,
        }

        prompt = f"Generate {request.form_type} form questions"
        if request.cultural_style:
            prompt += f" for a {request.cultural_style} wedding"
        if request.custom_context:
            prompt += f". Additional context: {request.custom_context}"
        if request.existing_questions:
            prompt += f". Avoid duplicating these existing questions: {', '.join(request.existing_questions)}"

        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id,
            feature="form_questions",
            prompt=prompt,
            context=context,
            force_refresh=False,  # Can cache form questions
        )

        response = result["response"]

        return {
            "questions": (
                response.get("questions", []) if isinstance(response, dict) else []
            ),
            "form_title": (
                response.get("form_title") if isinstance(response, dict) else None
            ),
            "form_intro": (
                response.get("form_intro") if isinstance(response, dict) else None
            ),
            "form_type": request.form_type,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining"),
        }

    except (
        InsufficientCreditsError,
        AIGenerationError,
        AIRateLimitError,
        AIContentBlockedError,
        AIServiceUnavailableError,
        AIQuotaExceededError,
        AITimeoutError,
        AIInvalidResponseError,
    ) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating form questions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate form questions")


# =========================================================================
# AI HEALTH CHECK (Diagnostic Endpoint)
# =========================================================================


@router.get("/health")
async def ai_health_check(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Check AI service health and configuration status (A7).

    Returns diagnostic information about the AI service:
    - Whether AI is enabled (API key configured)
    - Whether the Gemini client initialized successfully
    - API connection status with response time (if client is initialized)
    - Recent error rate from usage logs

    Cost: 0 credits (diagnostic only)
    """
    import time

    status = {
        "ai_enabled": settings.ai_enabled,
        "api_key_configured": bool(settings.ai_api_key),
        "client_initialized": ai_service._client is not None,
        "primary_model": MODEL_PRIMARY,
        "economy_model": MODEL_ECONOMY,
    }

    # Try a lightweight async API test if client is initialized
    if ai_service._client:
        try:
            start_time = time.monotonic()
            # Use the async client to avoid blocking the event loop
            models_response = await ai_service._client.aio.models.list()
            models = (
                [m async for m in models_response]
                if hasattr(models_response, "__aiter__")
                else list(models_response)
            )
            elapsed_ms = round((time.monotonic() - start_time) * 1000)
            status["api_connection"] = "ok"
            status["available_models"] = len(models)
            status["response_time_ms"] = elapsed_ms
        except Exception as e:
            status["api_connection"] = "error"
            status["api_error"] = str(e)
            logger.error(f"AI health check - API connection error: {str(e)}")
    else:
        status["api_connection"] = "not_initialized"
        status["api_error"] = (
            "Gemini client not initialized. Check GEMINI_API_KEY environment variable."
        )

    # Recent error metrics (A7 — health monitoring)
    try:
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        total_recent = await mongo.db["ai_usage_log"].count_documents(
            {"created_at": {"$gte": cutoff}}
        )
        errors_recent = await mongo.db["ai_usage_log"].count_documents(
            {"created_at": {"$gte": cutoff}, "error": {"$exists": True, "$ne": None}}
        )
        status["last_24h"] = {
            "total_requests": total_recent,
            "errors": errors_recent,
            "error_rate": (
                round(errors_recent / total_recent * 100, 1) if total_recent > 0 else 0
            ),
        }
    except Exception:
        # ai_usage_log may not exist yet — non-critical
        status["last_24h"] = {"total_requests": 0, "errors": 0, "error_rate": 0}

    return status
