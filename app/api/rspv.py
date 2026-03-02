from fastapi import APIRouter, Path, HTTPException, Request
from app.services.rsvp_service import RSVPService
from app.models.rsvp import RSVPModel
from fastapi import Body
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

rsvp_service = RSVPService()


@router.post("/invite/{token}/rsvp", tags=["RSVP"])
async def submit_rsvp(
    request: Request,
    token: str = Path(...),
    rsvp: RSVPModel = Body(...)
):
    try:
        return await rsvp_service.submit_rsvp(token, rsvp)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected RSVP error for token {token[:8]}...: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unexpected error occurred")
