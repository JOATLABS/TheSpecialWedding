from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.guest_help_service import GuestHelpRequestService

router = APIRouter()
guest_help_service = GuestHelpRequestService()
logger = logging.getLogger(__name__)


class GuestHelpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=30)
    relationship_to_couple: str = Field(..., min_length=2, max_length=120)

    @field_validator("slug", "full_name", "phone", "relationship_to_couple")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


@router.post("/guests/help-request", tags=["Guest"])
async def create_guest_help_request(request_data: GuestHelpRequest):
    """Create a planner-visible SMS support ticket from the public wedding page."""
    try:
        return await guest_help_service.create_help_request(
            slug=request_data.slug,
            full_name=request_data.full_name,
            phone=request_data.phone,
            relationship_to_couple=request_data.relationship_to_couple,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected public guest help request failure: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to send the help request right now.",
        )
