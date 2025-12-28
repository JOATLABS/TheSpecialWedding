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
from app.dependencies.auth_extended import require_admin_or_planner
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
        guests = await mongo.db["guests"].find({"wedding_id": wedding_id}).to_list(length=500)

        accepted = sum(1 for g in guests if g.get("rsvp_status") == "accepted")
        declined = sum(1 for g in guests if g.get("rsvp_status") == "declined")
        pending = sum(1 for g in guests if g.get("rsvp_status") in ["pending", None])

        return {
            "total_guests": len(guests),
            "accepted": accepted,
            "declined": declined,
            "pending": pending,
            "response_rate": round((accepted + declined) / len(guests) * 100, 1) if guests else 0
        }
    except Exception as e:
        logger.error(f"Error fetching RSVP data: {str(e)}")
        return {"total_guests": 0, "accepted": 0, "declined": 0, "pending": 0}


# =========================================================================
# BUDGET INSIGHTS (WFA-701)
# =========================================================================

@router.get("/weddings/{wedding_id}/budget-insights")
async def get_budget_insights(
    wedding_id: str,
    force_refresh: bool = False,
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Get AI-powered budget insights for a wedding.

    Returns 3 actionable insights about the budget allocation.
    Cost: 3 credits
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

        # Verify wedding exists and user has access
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
# SEATING OPTIMIZATION (WFA-702, WFA-703, WFA-704)
# =========================================================================

@router.post("/weddings/{wedding_id}/seating-optimize")
async def optimize_seating(
    wedding_id: str,
    request: SeatingOptimizeRequest,
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    AI-powered seating optimization.

    Cost varies by guest count:
    - ≤50 guests: 2 credits
    - 51-150 guests: 5 credits
    - 150+ guests: 10 credits
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

        # Verify wedding exists
        wedding = await get_wedding_by_id(wedding_id)
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        guest_count = len(request.guests)

        # Determine feature based on guest count
        if guest_count <= 50:
            feature = "seating_small"
        elif guest_count <= 150:
            feature = "seating_medium"
        else:
            feature = "seating_large"

        # Build context
        context = {
            "wedding_id": wedding_id,
            "guest_count": guest_count,
            "table_count": len(request.tables),
            "guests": request.guests,
            "tables": request.tables,
            "constraints": request.constraints or {}
        }

        # Generate seating arrangement
        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=wedding_id,
            feature=feature,
            prompt="Create an optimal seating arrangement for this wedding.",
            context=context,
            force_refresh=request.force_refresh
        )

        return {
            "tables": result["response"].get("tables", []),
            "guest_count": guest_count,
            "feature_used": feature,
            "cached": result["cached"],
            "credits_used": result["credits_used"]
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
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    AI-powered email/message drafting.

    Supports types: follow_up, reminder, thank_you, progress_update
    Cost: 1 credit (not cached - context-dependent)
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

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
            "planner_name": current_user.get("first_name") or current_user.get("company_name")
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
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Generate a wedding progress report for the couple.

    Cost: 2 credits
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

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
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    AI-powered pricing suggestions for service packages.

    Cost: 3 credits
    """
    try:
        user_id = str(current_user.user_data.get("_id", ""))

        if not request.services:
            raise HTTPException(status_code=400, detail="At least one service is required")

        # Build context
        context = {
            "services": request.services,
            "location": request.location or "USA",
            "wedding_size": request.wedding_size or 100,
            "planner_experience": current_user.get("years_experience", "unknown")
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
# UTILITY ENDPOINTS
# =========================================================================

@router.get("/features")
async def list_ai_features(
    current_user: dict = Depends(require_admin_or_planner)
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
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Check AI credit balance and feature availability.
    """
    user_id = str(current_user.user_data.get("_id", ""))

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
    current_user: dict = Depends(require_admin_or_planner)
):
    """
    Get AI usage metrics for the current user.
    """
    user_id = str(current_user.user_data.get("_id", ""))

    metrics = await ai_service.get_usage_metrics(
        period_days=period_days,
        tenant_id=user_id
    )

    return metrics


# =========================================================================
# INTERACTIVE AI CHAT (Conversational Assistant)
# =========================================================================

class ChatMessageRequest(BaseModel):
    message: str
    wedding_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None  # [{role: "user"/"assistant", content: "..."}]


class ChatResponse(BaseModel):
    response: str
    credits_used: int
    credits_remaining: Optional[int] = None
    warning: Optional[str] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    request: ChatMessageRequest,
    current_user: dict = Depends(require_admin_or_planner)
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
        user_id = str(current_user.user_data.get("_id", ""))

        # Build context with wedding data if provided
        context = {
            "user_message": request.message,
            "planner_email": current_user.email
        }

        # Add conversation history for context
        if request.conversation_history:
            # Only include last 10 messages to avoid token limits
            context["conversation_history"] = request.conversation_history[-10:]

        # If wedding_id provided, add wedding context
        if request.wedding_id:
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

        # Build the prompt with conversation context
        prompt = request.message
        if request.conversation_history:
            history_text = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in request.conversation_history[-10:]
            ])
            prompt = f"Previous conversation:\n{history_text}\n\nUser's new message: {request.message}"

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
