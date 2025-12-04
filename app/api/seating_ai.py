from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Dict, Any
from app.core.database import mongo
from app.dependencies.auth import get_current_user
from app.services.ai_service import AIService, AIFeature
from app.models.table import TableModel
import json

router = APIRouter()

@router.post("/seating/optimize", response_model=Dict[str, Any])
async def optimize_seating(
    request: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Optimizes seating arrangements using AI.
    Body: { "wedding_id": "...", "constraints": "..." }
    """
    wedding_id = request.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=400, detail="Missing wedding_id")

    # Fetch Data
    guests = await mongo.db.guests.find({"wedding_id": wedding_id, "rsvp_status": "accepted"}).to_list(length=1000)
    tables = await mongo.db.tables.find({"wedding_id": wedding_id}).to_list(length=100)

    if not guests:
        raise HTTPException(status_code=400, detail="No confirmed guests found")
    if not tables:
        raise HTTPException(status_code=400, detail="No tables found")

    # Format data for AI
    guest_list = []
    for g in guests:
        guest_list.append({
            "id": str(g["_id"]),
            "name": f"{g.get('first_name', '')} {g.get('last_name', '')}",
            "group": g.get("group", "General"), # Assuming group/relationship field exists
            "plus_ones": len(g.get("plus_ones", []))
        })

    table_list = []
    for t in tables:
        table_list.append({
            "id": str(t["_id"]),
            "name": t.get("name"),
            "capacity": t.get("capacity", 10)
        })

    # Construct Prompt
    prompt = f"""
    Optimize the seating arrangement for a wedding.

    Guests: {json.dumps(guest_list)}
    Tables: {json.dumps(table_list)}

    Rules:
    1. Do not exceed table capacity.
    2. Try to seat guests with the same 'group' together.
    3. Plus ones must be seated with the main guest.

    Return ONLY a JSON object mapping Table IDs to lists of Guest IDs.
    Format:
    {{
      "assignments": [
        {{ "table_id": "...", "guest_ids": ["...", "..."] }},
        ...
      ]
    }}
    """

    try:
        # Call AI Service
        ai_response = await AIService.generate_content(
            tenant_id=wedding_id,
            prompt=prompt,
            feature=AIFeature.SEATING_OPTIMIZATION,
            system_instruction="You are a helpful wedding planner assistant optimized for logistics."
        )

        # Clean response (remove markdown if present)
        clean_response = ai_response.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_response)

        return result

    except ValueError as e:
        raise HTTPException(status_code=402, detail=str(e)) # 402 Payment Required for insufficient credits
    except Exception as e:
        print(f"Seating Optimization Error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")
