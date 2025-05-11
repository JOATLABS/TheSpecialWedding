from fastapi import APIRouter, Path, HTTPException
from app.services.rsvp_service import RSVPService
from app.models.rsvp import RSVPModel

router = APIRouter()

rsvp_service = RSVPService()

@router.post("/invite/{token}/rsvp", tags=["RSVP"])
def submit_rsvp(token: str = Path(...), rsvp: RSVPModel = None):
    try:
        return rsvp_service.submit_rsvp(token, rsvp)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")