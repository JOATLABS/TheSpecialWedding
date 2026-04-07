from fastapi import APIRouter, Path, HTTPException, Request
from app.services.rsvp_service import RSVPService
from app.models.rsvp import RSVPModel
from fastapi import Body
from app.dependencies.guest_access import get_guest_access_session
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

rsvp_service = RSVPService()


@router.post("/invite/{token}/rsvp", tags=["RSVP"])
async def submit_rsvp(
    request: Request, token: str = Path(...), rsvp: RSVPModel = Body(...)
):
    try:
        return await rsvp_service.submit_rsvp(token, rsvp)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected RSVP error for token {token[:8]}...: {str(e)}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Unexpected error occurred")


@router.post("/session/{slug}/rsvp", tags=["RSVP"])
async def submit_rsvp_from_guest_session(
    request: Request,
    slug: str = Path(...),
    rsvp: RSVPModel = Body(...),
):
    try:
        session = get_guest_access_session(
            request,
            slug=slug,
            require_guest=True,
            require_otp_verified=True,
        )
        return await rsvp_service.submit_rsvp_for_guest(session.guest_id, rsvp)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected session RSVP error for slug {slug}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Unexpected error occurred")
