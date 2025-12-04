from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any
from app.dependencies.auth_extended import get_current_user_extended, ExtendedAuthUser
from app.services.budget_service import BudgetService
from app.services.ai_service import AIService, AIFeature
import json

router = APIRouter()
budget_service = BudgetService()

@router.post("/budget/ai-analyze", response_model=Dict[str, Any])
async def analyze_budget(
    request: Dict[str, Any] = Body(...),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Analyzes the wedding budget using AI to find savings and optimize allocation.
    Body: { "wedding_id": "..." }
    """
    wedding_id = request.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=400, detail="Missing wedding_id")

    # Fetch budget data
    try:
        budget_data = budget_service.get_wedding_budget(wedding_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Budget not found")

    # Construct Prompt
    categories = budget_data.get("categories", [])
    total_budget = budget_data.get("total_budget", 0)
    total_spent = budget_data.get("total_spent", 0)

    # Simplify data for AI
    summary_list = []
    for c in categories:
        summary_list.append({
            "name": c.get("name"),
            "budgeted": c.get("budgeted_amount"),
            "spent": c.get("actual_spent"),
            "status": "Over Budget" if c.get("actual_spent", 0) > c.get("budgeted_amount", 0) else "Under Budget"
        })

    prompt = f"""
    Analyze this wedding budget.
    Total Budget: ${total_budget}
    Total Spent: ${total_spent}

    Categories: {json.dumps(summary_list)}

    Provide a helpful analysis in markdown format.
    1. Identify any categories that are over budget.
    2. Suggest 3 specific ways to save money based on standard wedding costs.
    3. Provide a reassuring closing statement.
    """

    try:
        # Call AI Service
        ai_response = await AIService.generate_content(
            tenant_id=wedding_id,
            prompt=prompt,
            feature=AIFeature.BUDGET_ADVICE,
            system_instruction="You are a financial advisor for weddings. Be encouraging but practical."
        )

        return {"analysis": ai_response}

    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e))
    except Exception as e:
        print(f"Budget Analysis Error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")
