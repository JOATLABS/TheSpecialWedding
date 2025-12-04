from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.services.budget_service import BudgetService
from app.services.ai_service import AIService, AIFeature
from app.core.database import mongo
from datetime import datetime
import json

router = APIRouter()
budget_service = BudgetService()

@router.post("/reports/ai-update", response_model=Dict[str, Any])
async def generate_ai_update_report(
    request: Dict[str, Any] = Body(...),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Generates a professional weekly update report for the couple using AI.
    Body: { "wedding_id": "..." }
    """
    wedding_id = request.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=400, detail="Missing wedding_id")

    # 1. Fetch RSVP Stats
    # Count guests by rsvp_status (assuming 'rsvp_status' field exists or we join with RSVPs)
    # Using simple aggregation for now based on Guest collection or RSVP collection

    total_guests = await mongo.db.guests.count_documents({"wedding_id": wedding_id})
    accepted = await mongo.db.guests.count_documents({"wedding_id": wedding_id, "rsvp_status": "accepted"})
    declined = await mongo.db.guests.count_documents({"wedding_id": wedding_id, "rsvp_status": "declined"})
    pending = total_guests - accepted - declined

    # 2. Fetch Budget Stats
    try:
        budget_data = budget_service.get_wedding_budget(wedding_id)
        budget_total = budget_data.get("total_budget", 0)
        budget_spent = budget_data.get("total_spent", 0)
        remaining = budget_total - budget_spent
    except Exception:
        budget_total = 0
        budget_spent = 0
        remaining = 0

    # 3. Construct Prompt
    stats = f"""
    - Total Guests Invited: {total_guests}
    - Confirmed: {accepted}
    - Declined: {declined}
    - Waiting for Reply: {pending}

    - Total Budget: ${budget_total}
    - Amount Spent: ${budget_spent}
    - Remaining: ${remaining}
    """

    prompt = f"""
    Write a professional and encouraging weekly update email to the couple (Bride & Groom) from their Wedding Planner.

    Current Statistics:
    {stats}

    The email should:
    1. Summarize the RSVP progress.
    2. Give a quick financial snapshot.
    3. Encourage them to complete any pending tasks (keep this generic, like "reviewing vendor contracts" or "finalizing playlist").
    4. Maintain a warm, excited tone.
    """

    try:
        # Call AI Service
        ai_response = await AIService.generate_content(
            tenant_id=wedding_id,
            prompt=prompt,
            feature=AIFeature.REPORT_GENERATION,
            system_instruction="You are a professional Wedding Planner writing an update email."
        )

        return {"report_text": ai_response}

    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except Exception as e:
        print(f"Report Generation Error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")
