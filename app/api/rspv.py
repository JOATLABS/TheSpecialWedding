from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Path

from app.models.rsvp import RSVPModel
from app.services.rsvp_service import RSVPService

router = APIRouter()

rsvp_service = RSVPService()


@router.post("/invite/{token}/rsvp", tags=["RSVP"])
async def submit_rsvp(
    background_tasks: BackgroundTasks,
    token: str = Path(...),
    rsvp: RSVPModel = Body(...),
):
    try:
        return await rsvp_service.submit_rsvp(token, rsvp, background_tasks)
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")
