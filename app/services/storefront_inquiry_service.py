"""Durable public storefront inquiry capture and best-effort notification."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import logging
from typing import Any

from fastapi import HTTPException, status

from app.core.database import mongo
from app.models.storefront import StorefrontInquiryRequest, StorefrontInquiryResponse
from app.services.email_service_resend import ResendEmailService
from app.services.storefront_service import (
    StorefrontService,
    storefront_service as default_storefront_service,
)
from app.utils.planner_ownership import normalize_query_id
from app.utils.rate_limiter import RateLimiter, create_rate_limiter


logger = logging.getLogger(__name__)

STOREFRONT_INQUIRY_RATE_LIMIT = 5
STOREFRONT_INQUIRY_MESSAGE = "Thanks — your inquiry was sent to the wedding planner."


class StorefrontInquiryService:
    """Persist an inquiry before attempting any external notification."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        storefront_service: StorefrontService | Any | None = None,
        rate_limiter: RateLimiter | Any | None = None,
        email_service: ResendEmailService | Any | None = None,
    ) -> None:
        self._mongo = mongo_client or mongo
        self._storefront = storefront_service or default_storefront_service
        self._rate_limiter = rate_limiter or create_rate_limiter(
            "storefront_inquiry",
            requests_per_minute=STOREFRONT_INQUIRY_RATE_LIMIT,
        )
        self._email = email_service or ResendEmailService()

    async def capture(
        self,
        identifier: str,
        payload: StorefrontInquiryRequest,
        *,
        client_ip: str,
        user_agent: str | None,
    ) -> dict:
        # This is deliberately the same resolver used by public rendering. It
        # keeps draft, ineligible, and unverified-domain storefronts uniformly
        # non-enumerable and prevents a second publication policy from drifting.
        context = await self._storefront.resolve_public_context(identifier)
        owner_id = str(context["owner_id"])
        slug = str(context["slug"])

        rate_subject = f"{client_ip or 'unknown'}:{slug}"
        is_allowed, _remaining, reset_time = await self._rate_limiter.is_allowed(
            rate_subject,
            requests_per_minute=STOREFRONT_INQUIRY_RATE_LIMIT,
        )
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "Too many inquiries. Please try again later.",
                    "reset_time": reset_time,
                },
            )

        planner = await self._mongo.get_users_collection().find_one(
            {"_id": normalize_query_id(owner_id)},
            {"email": 1, "company_name": 1, "first_name": 1},
        )
        if not planner:
            # The public resolver should already have verified the owner. Fail
            # closed if that invariant changes between reads.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Storefront not found",
            )

        now = datetime.now(timezone.utc)
        inquiry = {
            "planner_id": owner_id,
            "storefront_slug": slug,
            "source_identifier": identifier.strip().lower(),
            "name": payload.name,
            "email": str(payload.email),
            "phone": payload.phone,
            "wedding_date": (
                payload.wedding_date.isoformat() if payload.wedding_date else None
            ),
            "message": payload.message,
            "client_ip": client_ip or "unknown",
            "user_agent": (user_agent or "")[:500] or None,
            "status": "new",
            "notification": {"status": "pending"},
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = await self._mongo.db["storefront_inquiries"].insert_one(inquiry)
        except Exception as exc:
            logger.exception("Failed to persist storefront inquiry")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inquiry could not be saved. Please try again.",
            ) from exc

        inquiry_id = result.inserted_id
        notification = await self._notify_planner(
            planner=planner,
            slug=slug,
            payload=payload,
        )
        try:
            await self._mongo.db["storefront_inquiries"].update_one(
                {"_id": inquiry_id, "planner_id": owner_id},
                {
                    "$set": {
                        "notification.status": notification["status"],
                        "notification.error": notification.get("error"),
                        "notification.provider_id": notification.get("provider_id"),
                        "notification.attempted_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception:
            # Lead durability is the primary contract. A failed bookkeeping
            # update cannot erase or make the accepted inquiry appear rejected.
            logger.exception(
                "Failed to record storefront inquiry notification outcome",
                extra={"inquiry_id": str(inquiry_id)},
            )

        return StorefrontInquiryResponse(
            success=True,
            inquiry_id=str(inquiry_id),
            message=STOREFRONT_INQUIRY_MESSAGE,
        ).model_dump()

    async def _notify_planner(
        self,
        *,
        planner: dict,
        slug: str,
        payload: StorefrontInquiryRequest,
    ) -> dict[str, str | None]:
        recipient = planner.get("email")
        if not recipient:
            return {"status": "failed", "error": "Planner email is unavailable"}

        planner_name = (
            planner.get("company_name") or planner.get("first_name") or "Planner"
        )
        wedding_date = (
            payload.wedding_date.isoformat() if payload.wedding_date else "Not provided"
        )
        html_content = (
            f"<p>Hello {escape(str(planner_name))},</p>"
            f"<p>You received a storefront inquiry from <strong>{escape(payload.name)}</strong>.</p>"
            f"<p><strong>Email:</strong> {escape(str(payload.email))}<br>"
            f"<strong>Phone:</strong> {escape(payload.phone or 'Not provided')}<br>"
            f"<strong>Wedding date:</strong> {escape(wedding_date)}</p>"
            f"<p><strong>Message:</strong><br>{escape(payload.message)}</p>"
            f"<p>Storefront: {escape(slug)}</p>"
        )
        try:
            result = await self._email.send_email(
                to_email=recipient,
                subject="New storefront inquiry",
                html_content=html_content,
                from_name="The Special Wedding",
                email_type="storefront_inquiry",
            )
        except Exception as exc:
            logger.exception("Storefront inquiry notification raised")
            return {"status": "failed", "error": str(exc)[:500]}

        if not result.get("success"):
            return {
                "status": "failed",
                "error": str(result.get("error") or "Email delivery failed")[:500],
            }
        return {
            "status": "sent",
            "provider_id": str(result.get("id") or "") or None,
        }


storefront_inquiry_service = StorefrontInquiryService()
