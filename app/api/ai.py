"""
AI Feature API Endpoints

Provides endpoints for AI-powered features:
- Budget insights
- Seating optimization
- Communication copilot
- Progress reports
- Package pricing suggestions
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from app.services.ai_service import (
    ai_service,
    InsufficientCreditsError,
    AIGenerationError,
    AIRateLimitError,
    AIContentBlockedError,
    AIServiceUnavailableError,
    AIQuotaExceededError,
    AITimeoutError,
    AIInvalidResponseError
)
from app.dependencies.auth_extended import require_admin_or_planner, check_wedding_access, ExtendedAuthUser
from app.core.database import mongo
from bson import ObjectId

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
                "available": e.available
            }
        )
    elif isinstance(e, AIRateLimitError):
        raise HTTPException(
            status_code=429,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after
            },
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None
        )
    elif isinstance(e, AIQuotaExceededError):
        raise HTTPException(
            status_code=429,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    elif isinstance(e, AIServiceUnavailableError):
        raise HTTPException(
            status_code=503,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after
            },
            headers={"Retry-After": str(e.retry_after)} if e.retry_after else None
        )
    elif isinstance(e, AITimeoutError):
        raise HTTPException(
            status_code=504,
            detail={
                "error": e.error_code,
                "message": e.message,
                "retry_after": e.retry_after
            }
        )
    elif isinstance(e, AIContentBlockedError):
        raise HTTPException(
            status_code=400,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    elif isinstance(e, AIInvalidResponseError):
        raise HTTPException(
            status_code=502,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    elif isinstance(e, AIGenerationError):
        raise HTTPException(
            status_code=500,
            detail={
                "error": e.error_code,
                "message": e.message
            }
        )
    else:
        # Unknown error
        logger.error(f"Unexpected AI error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "unknown_error",
                "message": "An unexpected error occurred. Please try again."
            }
        )


# =========================================================================
# VALIDATION HELPERS
# =========================================================================

def validate_seating_suggestions(
    ai_tables: List[Dict[str, Any]],
    original_guests: List[Dict[str, Any]],
    original_tables: List[Dict[str, Any]]
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
    # Build lookup maps
    valid_guest_ids = {
        str(g.get("id") or g.get("_id")) for g in original_guests
    }
    table_capacities = {
        str(t.get("id") or t.get("_id")): t.get("capacity", 10)
        for t in original_tables
    }
    table_names = {
        str(t.get("id") or t.get("_id")): t.get("name", f"Table {i+1}")
        for i, t in enumerate(original_tables)
    }

    validated_tables = []
    warnings = []
    assigned_guest_ids = set()

    for table in ai_tables:
        table_id = str(table.get("id") or table.get("table_id", ""))
        table_guests = table.get("guests", [])
        capacity = table_capacities.get(table_id, 10)

        # Filter out invalid guest IDs
        valid_guests = []
        invalid_guests = []

        for guest in table_guests:
            guest_id = str(guest.get("id") or guest.get("guest_id", ""))
            if guest_id in valid_guest_ids:
                valid_guests.append(guest)
                assigned_guest_ids.add(guest_id)
            else:
                invalid_guests.append(guest_id)

        if invalid_guests:
            warnings.append({
                "type": "invalid_guest_ids",
                "table": table_names.get(table_id, table_id),
                "invalid_ids": invalid_guests,
                "message": f"Removed {len(invalid_guests)} invalid guest ID(s) from {table_names.get(table_id, table_id)}"
            })

        # Check capacity (account for party sizes if available)
        total_seats_used = 0
        for guest in valid_guests:
            party_size = guest.get("party_size", 1)
            total_seats_used += party_size

        if total_seats_used > capacity:
            warnings.append({
                "type": "over_capacity",
                "table": table_names.get(table_id, table_id),
                "capacity": capacity,
                "assigned": total_seats_used,
                "message": f"{table_names.get(table_id, table_id)} is over capacity ({total_seats_used}/{capacity})"
            })

        validated_tables.append({
            **table,
            "guests": valid_guests,
            "capacity": capacity,
            "seats_used": total_seats_used
        })

    # Find unassigned guests
    unassigned = valid_guest_ids - assigned_guest_ids
    if unassigned:
        # Get names of unassigned guests
        unassigned_names = [
            g.get("name", "Unknown")
            for g in original_guests
            if str(g.get("id") or g.get("_id")) in unassigned
        ]
        warnings.append({
            "type": "unassigned_guests",
            "count": len(unassigned),
            "guest_ids": list(unassigned),
            "guest_names": unassigned_names[:10],  # Limit to first 10 names
            "message": f"{len(unassigned)} guest(s) not assigned to any table"
        })

    return {
        "tables": validated_tables,
        "warnings": warnings,
        "stats": {
            "total_guests": len(valid_guest_ids),
            "assigned_guests": len(assigned_guest_ids),
            "unassigned_guests": len(unassigned),
            "tables_over_capacity": sum(1 for w in warnings if w.get("type") == "over_capacity")
        }
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
    communication_type: str  # follow_up, reminder, thank_you, progress_update
    couple_name: str
    wedding_date: Optional[str] = None
    context: Optional[str] = None
    custom_instructions: Optional[str] = None


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


def _calculate_rsvp_status(rsvp: dict) -> str:
    """
    Determine RSVP status based on attending field.

    The 'attending' field is a List[str] of event names the guest is attending.
    - If list has items: guest is confirmed (attending at least one event)
    - If list is empty: guest declined all events
    - If field is missing/None: should not happen for submitted RSVPs
    """
    attending = rsvp.get("attending")

    if attending is None:
        return "pending"

    if isinstance(attending, list):
        return "confirmed" if len(attending) > 0 else "declined"

    if isinstance(attending, dict):
        return "confirmed" if any(attending.values()) else "declined"

    return "pending"


async def get_wedding_by_id(wedding_id: str) -> Optional[Dict]:
    """Get wedding data by ID. Handles both ObjectId and string IDs."""
    try:
        # Try finding by string _id first (e.g., "wedding_1765336536839")
        wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
        if not wedding:
            # Try ObjectId if string lookup failed
            try:
                wedding = await mongo.db["weddings"].find_one({"_id": ObjectId(wedding_id)})
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
        categories_cursor = mongo.db["budget_categories"].find({"wedding_id": wedding_id})
        categories_list = await categories_cursor.to_list(length=100)

        if not categories_list:
            return {"categories": [], "total_budget": 0, "total_spent": 0}

        # Format categories for AI consumption
        categories = []
        for cat in categories_list:
            categories.append({
                "name": cat.get("name", "Unknown"),
                "budget": cat.get("budgeted_amount", 0),
                "spent": cat.get("actual_spent", 0),
                "status": cat.get("payment_status", "pending"),
                "priority": cat.get("priority", 3),
                "percentage": cat.get("percentage_of_total", 0)
            })

        total_budget = sum(c.get("budget", 0) for c in categories)
        total_spent = sum(c.get("spent", 0) for c in categories)

        return {
            "categories": categories,
            "total_budget": total_budget,
            "total_spent": total_spent,
            "remaining": total_budget - total_spent
        }
    except Exception as e:
        logger.error(f"Error fetching budget: {str(e)}")
        return {"categories": [], "total_budget": 0, "total_spent": 0}


async def get_rsvp_data(wedding_id: str) -> Dict[str, Any]:
    """Get RSVP summary for a wedding."""
    try:
        guest_count = await mongo.db["guests"].count_documents({"wedding_id": wedding_id})

        if guest_count == 0:
            return {"total_guests": 0, "accepted": 0, "declined": 0, "pending": 0, "response_rate": 0}

        rsvps_cursor = mongo.db["rsvps"].find({"wedding_id": wedding_id})
        rsvps = await rsvps_cursor.to_list(length=None)

        accepted = 0
        declined = 0

        for rsvp in rsvps:
            status = _calculate_rsvp_status(rsvp)
            if status == "confirmed":
                accepted += 1
            elif status == "declined":
                declined += 1

        pending = guest_count - len(rsvps)

        return {
            "total_guests": guest_count,
            "accepted": accepted,
            "declined": declined,
            "pending": pending,
            "response_rate": round((len(rsvps) / guest_count * 100), 1) if guest_count > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error fetching RSVP data for wedding {wedding_id}: {str(e)}")
        return {"total_guests": 0, "accepted": 0, "declined": 0, "pending": 0, "response_rate": 0}


# =========================================================================
# BUDGET INSIGHTS (WFA-701)
# =========================================================================

@router.get("/weddings/{wedding_id}/budget-insights")
async def get_budget_insights(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get AI-powered budget insights for a wedding.

    Returns 3 actionable insights about the budget allocation.
    Cost: 3 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this wedding"
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
                "credits_used": 0
            }

        # Build context with cultural and regional awareness
        venue = wedding.get("venue")
        location = None
        if isinstance(venue, dict):
            location = venue.get("city")
        elif isinstance(venue, str):
            location = venue
        location = location or wedding.get("region") or wedding.get("city") or wedding.get("location")

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
            "cultural_style": cultural_style or "western",  # Default to western if not specified
            "season": season or "unknown",
            "total_budget": wedding.get("total_budget"),
            "budget": budget_data
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
            force_refresh=force_refresh
        )

        return {
            "insights": result["response"].get("insights", []),
            "cached": result["cached"],
            "credits_used": result["credits_used"]
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating budget insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate budget insights")


# =========================================================================
# DASHBOARD INSIGHTS (AI-002)
# =========================================================================

@router.get("/weddings/{wedding_id}/insights")
async def get_dashboard_insights(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Gather comprehensive wedding data for analysis
        budget_data = await get_budget_data(wedding_id)
        rsvp_data = await get_rsvp_data(wedding_id)

        # Get upcoming tasks
        tasks = await mongo.db["tasks"].find({
            "wedding_id": wedding_id,
            "status": {"$ne": "completed"}
        }).sort("due_date", 1).limit(10).to_list(length=10)

        upcoming_tasks = [
            {
                "title": t.get("title"),
                "due_date": str(t.get("due_date")) if t.get("due_date") else None,
                "priority": t.get("priority", "medium"),
                "category": t.get("category")
            }
            for t in tasks
        ]

        # Get upcoming vendor payments
        from datetime import datetime, timedelta
        upcoming_deadline = datetime.utcnow() + timedelta(days=30)

        scheduled_payments = await mongo.db["scheduled_payments"].find({
            "wedding_id": wedding_id,
            "status": {"$in": ["scheduled", "pending"]},
            "due_date": {"$lte": upcoming_deadline}
        }).sort("due_date", 1).limit(5).to_list(length=5)

        vendor_payments = [
            {
                "vendor": p.get("vendor_name", "Unknown Vendor"),
                "amount": p.get("amount", 0),
                "due_date": str(p.get("due_date")) if p.get("due_date") else None,
                "status": p.get("status")
            }
            for p in scheduled_payments
        ]

        # Calculate days until wedding
        days_until_wedding = None
        wedding_date_str = wedding.get("date")
        if wedding_date_str and isinstance(wedding_date_str, str):
            try:
                from datetime import datetime as dt
                wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d")
                days_until_wedding = (wedding_date - dt.utcnow()).days
            except (ValueError, TypeError):
                # Ignore if date format is wrong
                pass

        # Build context for AI
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
            "vendor_payments": vendor_payments
        }

        # Generate insights
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="dashboard_insights",
            prompt="Analyze this wedding's current status and generate actionable insights for the planner.",
            context=context,
            force_refresh=force_refresh
        )

        response = result["response"]
        insights = response.get("insights", []) if isinstance(response, dict) else []

        return {
            "insights": insights,
            "wedding_id": wedding_id,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    AI-powered seating optimization.

    Cost varies by guest count:
    - ≤50 guests: 2 credits
    - 51-150 guests: 5 credits
    - 150+ guests: 10 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        if not request.guests or not request.tables:
            raise HTTPException(
                status_code=400, 
                detail="Guests and tables are required for optimization"
            )

        guest_count = len(request.guests)

        # Determine feature based on guest count
        if guest_count <= 50:
            feature = "seating_small"
        elif guest_count <= 150:
            feature = "seating_medium"
        else:
            feature = "seating_large"

        # Sanitize guest data to remove PII (email, phone) and reduce token usage
        # Only send fields relevant to seating logic
        sanitized_guests = [
            {
                "id": g.get("id") or g.get("_id"),
                "name": g.get("name"),
                "group": g.get("group_id"),
                "role": g.get("role"),
                "plus_one": g.get("plus_one_allowed"),
                "party_size": 1 + (g.get("number_of_plus_ones_allowed", 0) if g.get("plus_one_allowed") else 0)
            }
            for g in request.guests
        ]

        # Build context
        context = {
            "wedding_id": wedding_id,
            "guest_count": guest_count,
            "table_count": len(request.tables),
            "guests": sanitized_guests,
            "tables": request.tables,
            "constraints": request.constraints or {}
        }

        # Enhanced prompt with explicit constraints
        system_prompt = (
            "Create an optimal seating arrangement. Rules: 1. Keep guests with the same 'group' together where possible. "
            "2. Ensure VIPs/Family are at appropriate tables. 3. Strictly respect table capacity limits. "
            "4. Keep plus-ones with their primary guest."
        )

        # Generate seating arrangement
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature=feature,
            prompt=system_prompt,
            context=context,
            force_refresh=request.force_refresh
        )

        # Validate AI response
        ai_tables = result["response"].get("tables", [])
        validation = validate_seating_suggestions(
            ai_tables=ai_tables,
            original_guests=request.guests,
            original_tables=request.tables
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
                "stats": validation["stats"]
            }
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                detail=f"Invalid communication type. Must be one of: {valid_types}"
            )

        # Build context
        context = {
            "type": request.communication_type,
            "couple_name": request.couple_name,
            "wedding_date": request.wedding_date,
            "additional_context": request.context,
            "planner_name": user_data.get("first_name") or user_data.get("company_name")
        }

        prompt = request.custom_instructions or f"Draft a {request.communication_type.replace('_', ' ')} message."

        # Generate draft (not cached)
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=user_id,  # Use user as tenant since this isn't wedding-specific
            feature="email_draft",
            prompt=prompt,
            context=context,
            force_refresh=True  # Never cache drafts
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
            "credits_used": result["credits_used"]
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                status_code=403,
                detail="You don't have access to this wedding"
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
            tasks = await mongo.db["tasks"].find({
                "wedding_id": wedding_id,
                "status": {"$ne": "completed"}
            }).sort("due_date", 1).limit(5).to_list(length=5)

            context["upcoming_tasks"] = [
                {"title": t.get("title"), "due_date": t.get("due_date")}
                for t in tasks
            ]

        # Generate report
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="progress_report",
            prompt="Generate a progress report for this wedding.",
            context=context,
            force_refresh=force_refresh
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
                "timeline": include_timeline
            },
            "cached": result["cached"],
            "credits_used": result["credits_used"]
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating progress report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate progress report")


# =========================================================================
# PACKAGE PRICING SUGGESTIONS (WFA-707)
# =========================================================================

@router.post("/suggest-pricing")
async def suggest_pricing(
    request: PricingSuggestionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    AI-powered pricing suggestions for service packages.

    Cost: 3 credits
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))
        user_data = current_user.user_data or {}

        if not request.services:
            raise HTTPException(status_code=400, detail="At least one service is required")

        # Build context
        context = {
            "services": request.services,
            "location": request.location or "USA",
            "wedding_size": request.wedding_size or 100,
            "planner_experience": user_data.get("years_experience", "unknown")
        }

        # Generate pricing suggestion
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=user_id,
            feature="package_pricing",
            prompt="Suggest pricing for this wedding package.",
            context=context,
            force_refresh=request.force_refresh
        )

        response = result["response"]

        return {
            "pricing": {
                "min_price": response.get("min_price"),
                "max_price": response.get("max_price"),
                "recommended": response.get("recommended"),
                "market_comparison": response.get("market_comparison", "at"),
                "schedule_suggestion": response.get("schedule_suggestion", [])
            },
            "cached": result["cached"],
            "credits_used": result["credits_used"]
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error suggesting pricing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to suggest pricing")


# =========================================================================
# CONTRACT SECTION GENERATION (AI-005)
# =========================================================================

class ContractSectionRequest(BaseModel):
    section_type: str  # payment_terms, cancellation_policy, scope_of_work, liability, force_majeure, custom
    vendor_type: Optional[str] = None  # photographer, caterer, florist, dj, venue, etc.
    wedding_id: Optional[str] = None
    custom_prompt: Optional[str] = None


@router.post("/generate-contract-section")
async def generate_contract_section(
    request: ContractSectionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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

        valid_sections = ["payment_terms", "cancellation_policy", "scope_of_work", "liability", "force_majeure", "custom"]
        if request.section_type not in valid_sections:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section_type. Must be one of: {valid_sections}"
            )

        # If custom section, require custom_prompt
        if request.section_type == "custom" and not request.custom_prompt:
            raise HTTPException(
                status_code=400,
                detail="custom_prompt is required when section_type is 'custom'"
            )

        # Build context
        context = {
            "section_type": request.section_type,
            "vendor_type": request.vendor_type or "general vendor"
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this wedding"
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
            "custom": request.custom_prompt
        }

        prompt = section_prompts[request.section_type]

        # Ensure prompt is not None (should not happen due to earlier validation, but for type safety)
        if prompt is None:
            raise HTTPException(
                status_code=400,
                detail="Unable to generate prompt for the specified section type"
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
            force_refresh=True  # Never cache - each generation is unique
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
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating contract section: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate contract section")


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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
            "guest_count": request.guest_count or 100
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                # Override with wedding data if not explicitly provided
                context["wedding_style"] = request.wedding_style or wedding.get("cultural_style", "western")
                context["region"] = request.region or wedding.get("region") or wedding.get("venue")
                context["guest_count"] = request.guest_count or wedding.get("guest_count", 100)
                context["wedding_date"] = wedding.get("date")

        prompt = f"Provide vendor selection guidance for hiring a {request.vendor_type} for a {context['wedding_style']} wedding in {context['region']} with approximately {context['guest_count']} guests."

        if request.budget_range:
            if request.budget_range.get("min") and request.budget_range.get("max"):
                prompt += f" The budget range is ${request.budget_range['min']:,.0f} - ${request.budget_range['max']:,.0f}."
            elif request.budget_range.get("max"):
                prompt += f" The budget is up to ${request.budget_range['max']:,.0f}."

        # Generate recommendations
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id or user_id,
            feature="vendor_recommendations",
            prompt=prompt,
            context=context,
            force_refresh=False
        )

        response = result["response"]

        return {
            "recommendations": response if isinstance(response, dict) else {"raw": response},
            "vendor_type": request.vendor_type,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating vendor recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate vendor recommendations")


# =========================================================================
# TASK PRIORITIZATION (AI-013)
# =========================================================================

@router.post("/weddings/{wedding_id}/prioritize-tasks")
async def prioritize_tasks(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        # Calculate days until wedding
        from datetime import datetime as dt, timedelta
        days_until_wedding = None
        wedding_date_str = wedding.get("date")
        if wedding_date_str and isinstance(wedding_date_str, str):
            try:
                wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d")
                days_until_wedding = (wedding_date - dt.utcnow()).days
            except Exception:
                pass

        # Get all pending tasks
        tasks = await mongo.db["tasks"].find({
            "wedding_id": wedding_id,
            "status": {"$ne": "completed"}
        }).sort("due_date", 1).to_list(length=50)

        pending_tasks = [
            {
                "title": t.get("title"),
                "description": t.get("description"),
                "due_date": str(t.get("due_date")) if t.get("due_date") else None,
                "priority": t.get("priority", "medium"),
                "category": t.get("category"),
                "status": t.get("status", "pending")
            }
            for t in tasks
        ]

        # Get upcoming vendor payments/deadlines
        upcoming_deadline = dt.utcnow() + timedelta(days=60)
        vendor_deadlines = await mongo.db["scheduled_payments"].find({
            "wedding_id": wedding_id,
            "status": {"$in": ["scheduled", "pending"]},
            "due_date": {"$lte": upcoming_deadline}
        }).sort("due_date", 1).limit(10).to_list(length=10)

        deadlines = [
            {
                "vendor": p.get("vendor_name", "Vendor"),
                "type": "payment",
                "amount": p.get("amount", 0),
                "due_date": str(p.get("due_date")) if p.get("due_date") else None
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
            "current_date": dt.utcnow().strftime("%Y-%m-%d"),
            "pending_tasks": pending_tasks,
            "vendor_deadlines": deadlines
        }

        prompt = "Analyze these wedding planning tasks and vendor deadlines. Prioritize them based on the wedding date, dependencies, and urgency. Identify what should be done this week."

        # Generate prioritization
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="task_prioritization",
            prompt=prompt,
            context=context,
            force_refresh=force_refresh
        )

        response = result["response"]

        return {
            "prioritization": response if isinstance(response, dict) else {"raw": response},
            "wedding_id": wedding_id,
            "days_until_wedding": days_until_wedding,
            "tasks_analyzed": len(pending_tasks),
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(request.wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        wedding_date_str = wedding.get("date")
        if not wedding_date_str:
            raise HTTPException(
                status_code=400,
                detail="Wedding date is required to generate a timeline"
            )

        # Calculate timeline parameters
        from datetime import datetime as dt
        wedding_date = dt.strptime(wedding_date_str, "%Y-%m-%d")
        current_date = dt.utcnow()
        days_until_wedding = (wedding_date - current_date).days
        months_until_wedding = days_until_wedding / 30

        # Get existing tasks to avoid duplicates in suggestions
        existing_tasks = await mongo.db["tasks"].find({
            "wedding_id": request.wedding_id
        }).to_list(length=100)

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
            "existing_task_samples": existing_task_titles[:10]  # First 10 for context
        }

        prompt = f"Generate a wedding planning timeline for a {context['cultural_style']} wedding with {context['guest_count']} guests. The wedding is on {wedding.get('date')}, which is {days_until_wedding} days ({round(months_until_wedding, 1)} months) away. Create realistic milestones starting from today ({current_date.strftime('%Y-%m-%d')})."

        # Generate timeline
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=request.wedding_id,
            feature="timeline_generator",
            prompt=prompt,
            context=context,
            force_refresh=request.force_refresh
        )

        response = result["response"]

        return {
            "timeline": response if isinstance(response, dict) else {"raw": response},
            "wedding_id": request.wedding_id,
            "wedding_date": wedding.get("date"),
            "days_until_wedding": days_until_wedding,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        from datetime import datetime as dt

        # Get all scheduled payments
        scheduled_payments = await mongo.db["scheduled_payments"].find({
            "wedding_id": wedding_id
        }).sort("due_date", 1).to_list(length=100)

        # Get paid payments for historical context
        paid_payments = await mongo.db["payment_records"].find({
            "wedding_id": wedding_id,
            "status": "succeeded"
        }).to_list(length=100)

        # Format payments data
        now = dt.utcnow()
        payments_data = []
        for p in scheduled_payments:
            due_date = p.get("due_date")
            status = p.get("status", "scheduled")

            # Calculate if overdue
            if due_date and due_date < now and status not in ["paid", "completed"]:
                status = "overdue"

            payments_data.append({
                "vendor": p.get("vendor_name", "Unknown Vendor"),
                "amount": p.get("amount", 0),
                "due_date": str(due_date) if due_date else None,
                "status": status,
                "description": p.get("description", "")
            })

        # Calculate totals
        total_due = sum(p.get("amount", 0) for p in scheduled_payments if p.get("status") not in ["paid", "completed"])
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
            "payment_count": len(payments_data)
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
                        "largest_upcoming": None
                    }
                },
                "wedding_id": wedding_id,
                "message": "No scheduled payments found",
                "cached": False,
                "credits_used": 0
            }

        prompt = "Analyze this wedding's payment schedule and provide a cash flow forecast. Identify any concerns, peak payment periods, and recommendations for managing payments."

        # Generate forecast
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature="payment_forecast",
            prompt=prompt,
            context=context,
            force_refresh=force_refresh
        )

        response = result["response"]

        return {
            "forecast": response if isinstance(response, dict) else {"raw": response},
            "wedding_id": wedding_id,
            "total_payments": len(payments_data),
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating payment forecast: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate payment forecast")


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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
            "service_description": request.service_description
        }

        # Add wedding context if provided
        if request.wedding_id:
            if not await check_wedding_access(current_user, request.wedding_id):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have access to this wedding"
                )

            wedding = await get_wedding_by_id(request.wedding_id)
            if wedding:
                context["wedding_style"] = request.wedding_style or wedding.get("cultural_style", "western")
                context["region"] = request.region or wedding.get("region") or wedding.get("venue")
                context["guest_count"] = request.guest_count or wedding.get("guest_count", 100)

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
            force_refresh=False
        )

        response = result["response"]

        return {
            "analysis": response if isinstance(response, dict) else {"raw": response},
            "vendor_type": request.vendor_type,
            "quoted_price": request.quoted_price,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error analyzing vendor price: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze vendor price")


# =========================================================================
# UTILITY ENDPOINTS
# =========================================================================

@router.get("/features")
async def list_ai_features(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    List all available AI features with their credit costs.
    """
    return {
        "features": ai_service.list_features()
    }


@router.get("/credits")
async def check_ai_credits(
    feature: Optional[str] = None,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
        # Return general credit info
        from app.services.subscription_service import SubscriptionService
        sub_service = SubscriptionService()
        result = await sub_service.check_usage_limits(
            user_id=user_id,
            resource_type="ai_credits",
            requested_amount=0
        )
        return {
            "credits_remaining": result.get("remaining", 0),
            "credits_limit": result.get("limit", 0)
        }


@router.get("/usage")
async def get_ai_usage(
    period_days: int = 7,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get AI usage metrics for the current user.
    """
    user_id = str((current_user.user_data or {}).get("_id", ""))

    metrics = await ai_service.get_usage_metrics(
        period_days=period_days,
        tenant_id=user_id
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
    message: str
    wedding_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None  # [{role: "user"/"assistant", content: "..."}]
    page_context: Optional[PageContextModel] = None  # Current page context for enhanced responses


class ChatResponse(BaseModel):
    response: str
    credits_used: int
    credits_remaining: Optional[int] = None
    warning: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatMessageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Interactive chat with the AI wedding planning assistant.

    Features:
    - Maintains conversation context via conversation_history
    - Optionally scoped to a specific wedding for contextual answers
    - 1 credit per message
    - Culturally-aware responses when wedding context is provided
    """
    try:
        user_id = str((current_user.user_data or {}).get("_id", ""))

        # Build context with wedding data if provided
        context: Dict[str, Any] = {
            "user_message": request.message,
            "planner_email": current_user.email
        }

        # Add page context for enhanced responses
        if request.page_context:
            context["page_context"] = {
                "page": request.page_context.page,
                "hint": request.page_context.hint
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
                    status_code=403,
                    detail="You don't have access to this wedding"
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
                        "categories_count": len(budget_data.get("categories", []))
                    }
                }

        # Build the prompt with conversation context and page hint
        prompt_parts = []

        # Add page context hint as system guidance
        if request.page_context and request.page_context.hint:
            prompt_parts.append(f"[Context: {request.page_context.hint}]")

        # Add conversation history
        if request.conversation_history:
            history_text = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in request.conversation_history[-10:]
            ])
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
            force_refresh=True  # Chat is never cached
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
            warning=result.get("warning")
        )

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


# =========================================================================
# MESSAGE GENERATOR (JOA-151 / AI-008)
# =========================================================================

class GenerateMessageRequest(BaseModel):
    message_type: str  # rsvp_reminder, save_the_date, thank_you, vendor_reminder, event_reminder, custom
    wedding_id: str
    tone: str = "friendly"  # formal, friendly, casual
    recipient_context: Optional[str] = None  # family, friend, vendor, etc.
    custom_instructions: Optional[str] = None
    couple_names: Optional[str] = None
    wedding_date: Optional[str] = None
    event_name: Optional[str] = None


@router.post("/generate-message")
async def generate_message(
    request: GenerateMessageRequest,
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Generate a personalized wedding communication message.

    Cost: 1 credit
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, request.wedding_id):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Get wedding details for context
        wedding = await get_wedding_by_id(request.wedding_id)

        context = {
            "message_type": request.message_type,
            "tone": request.tone,
            "recipient_context": request.recipient_context,
            "couple_names": request.couple_names or (wedding.get("couple_names") if wedding else None),
            "wedding_date": request.wedding_date or (wedding.get("date") if wedding else None),
            "event_name": request.event_name,
            "custom_instructions": request.custom_instructions
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
            force_refresh=True  # Messages should always be fresh
        )

        response = result["response"]

        return {
            "message": response if isinstance(response, dict) else {"body": str(response)},
            "message_type": request.message_type,
            "tone": request.tone,
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating message: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate message")


# =========================================================================
# FORM QUESTIONS GENERATOR (JOA-153 / AI-010)
# =========================================================================

class GenerateFormQuestionsRequest(BaseModel):
    form_type: str  # rsvp, dietary, song_requests, accommodation, transportation, custom
    wedding_id: str
    cultural_style: Optional[str] = None  # nigerian, indian, jewish, western, etc.
    custom_context: Optional[str] = None
    existing_questions: Optional[List[str]] = None  # To avoid duplicates


@router.post("/generate-form-questions")
async def generate_form_questions(
    request: GenerateFormQuestionsRequest,
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Generate smart form questions based on form type and wedding context.

    Cost: 1 credit
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

        # Verify planner has access to this wedding
        if not await check_wedding_access(current_user, request.wedding_id):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this wedding"
            )

        # Get wedding details for context
        wedding = await get_wedding_by_id(request.wedding_id)

        context = {
            "form_type": request.form_type,
            "cultural_style": request.cultural_style or (wedding.get("cultural_style") if wedding else "western"),
            "couple_names": wedding.get("couple_names") if wedding else None,
            "wedding_date": wedding.get("date") if wedding else None,
            "guest_count": wedding.get("guest_count") if wedding else None,
            "custom_context": request.custom_context,
            "existing_questions": request.existing_questions
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
            force_refresh=False  # Can cache form questions
        )

        response = result["response"]

        return {
            "questions": response.get("questions", []) if isinstance(response, dict) else [],
            "form_title": response.get("form_title") if isinstance(response, dict) else None,
            "form_intro": response.get("form_intro") if isinstance(response, dict) else None,
            "form_type": request.form_type,
            "cached": result["cached"],
            "credits_used": result["credits_used"],
            "credits_remaining": result.get("credits_remaining")
        }

    except (InsufficientCreditsError, AIGenerationError, AIRateLimitError,
            AIContentBlockedError, AIServiceUnavailableError, AIQuotaExceededError,
            AITimeoutError, AIInvalidResponseError) as e:
        handle_ai_error(e)
    except Exception as e:
        logger.error(f"Error generating form questions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate form questions")
