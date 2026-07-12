"""Durable public storefront inquiry capture and best-effort notification."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from html import escape
import json
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

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

    @staticmethod
    def _request_hash(payload: StorefrontInquiryRequest) -> str:
        canonical_payload = payload.model_dump(
            mode="json",
            exclude={"idempotency_key"},
        )
        serialized = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _replay_or_conflict(inquiry: dict, request_hash: str) -> dict:
        if inquiry.get("request_hash") != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This inquiry key was already used with different details",
            )
        inquiry_id = inquiry.get("_id")
        if inquiry_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Inquiry confirmation is temporarily unavailable",
            )
        return StorefrontInquiryResponse(
            success=True,
            inquiry_id=str(inquiry_id),
            message=str(inquiry.get("response_message") or STOREFRONT_INQUIRY_MESSAGE),
        ).model_dump()

    async def _require_same_public_context(
        self,
        identifier: str,
        *,
        owner_id: str,
        slug: str,
    ) -> None:
        current = await self._storefront.resolve_public_context(identifier)
        if str(current.get("owner_id")) != owner_id or str(current.get("slug")) != slug:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Storefront not found",
            )

    @staticmethod
    def _notification_is_pending(inquiry: dict) -> bool:
        notification = inquiry.get("notification")
        return (
            isinstance(notification, dict) and notification.get("status") == "pending"
        )

    async def _reconcile_insert_receipt(
        self,
        inquiries: Any,
        *,
        idempotency_query: dict,
        request_hash: str,
    ) -> dict | None:
        exact_query = {**idempotency_query, "request_hash": request_hash}
        exact = await inquiries.find_one(exact_query)
        if exact:
            return exact
        conflicting = await inquiries.find_one(idempotency_query)
        if conflicting:
            self._replay_or_conflict(conflicting, request_hash)
            return conflicting
        return None

    async def _claim_notification(
        self,
        inquiries: Any,
        *,
        inquiry_id: Any,
        owner_id: str,
        request_hash: str,
    ) -> str | None:
        claim_token = uuid4().hex
        now = datetime.now(timezone.utc)
        claim_query = {
            "_id": inquiry_id,
            "planner_id": owner_id,
            "request_hash": request_hash,
            "notification.status": "pending",
        }
        claim_update = {
            "$set": {
                "notification.status": "sending",
                "notification.claim_token": claim_token,
                "notification.claimed_at": now,
                "updated_at": now,
            }
        }
        try:
            claimed = await inquiries.update_one(claim_query, claim_update)
        except Exception:
            logger.exception(
                "Storefront inquiry notification claim acknowledgement was lost",
                extra={"inquiry_id": str(inquiry_id)},
            )
            try:
                reconciled = await inquiries.find_one(
                    {
                        "_id": inquiry_id,
                        "planner_id": owner_id,
                        "request_hash": request_hash,
                        "notification.status": "sending",
                        "notification.claim_token": claim_token,
                    }
                )
            except Exception:
                logger.exception(
                    "Failed to reconcile storefront inquiry notification claim",
                    extra={"inquiry_id": str(inquiry_id)},
                )
                return None
            return claim_token if reconciled else None
        if getattr(claimed, "modified_count", 0) != 1:
            return None
        return claim_token

    async def _deliver_notification_if_claimed(
        self,
        inquiries: Any,
        inquiry: dict,
        *,
        owner_id: str,
        request_hash: str,
        slug: str,
        payload: StorefrontInquiryRequest,
        planner: dict | None = None,
    ) -> None:
        inquiry_id = inquiry.get("_id")
        if inquiry_id is None:
            return
        claim_token = await self._claim_notification(
            inquiries,
            inquiry_id=inquiry_id,
            owner_id=owner_id,
            request_hash=request_hash,
        )
        if not claim_token:
            return

        if planner is None:
            try:
                planner = await self._mongo.get_users_collection().find_one(
                    {"_id": normalize_query_id(owner_id)},
                    {"email": 1, "company_name": 1, "first_name": 1},
                )
            except Exception as exc:
                logger.exception(
                    "Failed to load planner for storefront inquiry notification",
                    extra={"inquiry_id": str(inquiry_id)},
                )
                notification = {"status": "failed", "error": str(exc)[:500]}
            else:
                notification = (
                    await self._notify_planner(
                        planner=planner,
                        slug=slug,
                        payload=payload,
                    )
                    if planner
                    else {"status": "failed", "error": "Planner is unavailable"}
                )
        else:
            notification = await self._notify_planner(
                planner=planner,
                slug=slug,
                payload=payload,
            )

        attempted_at = datetime.now(timezone.utc)
        try:
            outcome = await inquiries.update_one(
                {
                    "_id": inquiry_id,
                    "planner_id": owner_id,
                    "request_hash": request_hash,
                    "notification.status": "sending",
                    "notification.claim_token": claim_token,
                },
                {
                    "$set": {
                        "notification.status": notification["status"],
                        "notification.error": notification.get("error"),
                        "notification.provider_id": notification.get("provider_id"),
                        "notification.attempted_at": attempted_at,
                        "updated_at": attempted_at,
                    },
                    "$unset": {"notification.claim_token": ""},
                },
            )
            if getattr(outcome, "matched_count", 0) != 1:
                logger.error(
                    "Storefront inquiry notification outcome lost its claim fence",
                    extra={"inquiry_id": str(inquiry_id)},
                )
        except Exception:
            # Lead durability is the primary contract. A failed bookkeeping
            # update cannot erase or make the accepted inquiry appear rejected.
            logger.exception(
                "Failed to record storefront inquiry notification outcome",
                extra={"inquiry_id": str(inquiry_id)},
            )

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
        inquiries = self._mongo.db["storefront_inquiries"]
        request_hash = self._request_hash(payload)
        idempotency_key = payload.idempotency_key or f"legacy-{uuid4().hex}"
        idempotency_query = {
            "planner_id": owner_id,
            "idempotency_key": idempotency_key,
        }
        existing = await inquiries.find_one(idempotency_query)
        if existing:
            response = self._replay_or_conflict(existing, request_hash)
            if self._notification_is_pending(existing):
                await self._require_same_public_context(
                    identifier,
                    owner_id=owner_id,
                    slug=slug,
                )
                await self._deliver_notification_if_claimed(
                    inquiries,
                    existing,
                    owner_id=owner_id,
                    request_hash=request_hash,
                    slug=slug,
                    payload=payload,
                )
            return response

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

        # The rate-limit and planner reads above are await points where an owner
        # can unpublish, lose entitlement, or revoke a custom hostname. Recheck
        # the exact same public owner/slug immediately before any durable write.
        await self._require_same_public_context(
            identifier,
            owner_id=owner_id,
            slug=slug,
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
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "response_message": STOREFRONT_INQUIRY_MESSAGE,
            "client_ip": client_ip or "unknown",
            "user_agent": (user_agent or "")[:500] or None,
            "status": "new",
            "notification": {"status": "pending"},
            "created_at": now,
            "updated_at": now,
        }
        try:
            result = await inquiries.insert_one(inquiry)
        except Exception as exc:
            try:
                receipt = await self._reconcile_insert_receipt(
                    inquiries,
                    idempotency_query=idempotency_query,
                    request_hash=request_hash,
                )
            except HTTPException:
                raise
            except Exception:
                logger.exception(
                    "Failed to reconcile storefront inquiry insert",
                    extra={"idempotency_key": idempotency_key},
                )
                receipt = None
            if not receipt:
                if isinstance(exc, DuplicateKeyError):
                    logger.exception(
                        "Storefront inquiry collided with an unrelated unique constraint"
                    )
                else:
                    logger.exception("Failed to persist storefront inquiry")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Inquiry could not be saved. Please try again.",
                ) from exc
            if not isinstance(exc, DuplicateKeyError):
                logger.warning(
                    "Reconciled ambiguous storefront inquiry insert acknowledgement",
                    extra={"inquiry_id": str(receipt.get("_id"))},
                )
        else:
            receipt = {**inquiry, "_id": result.inserted_id}

        response = self._replay_or_conflict(receipt, request_hash)
        await self._deliver_notification_if_claimed(
            inquiries,
            receipt,
            owner_id=owner_id,
            request_hash=request_hash,
            slug=slug,
            payload=payload,
            planner=planner,
        )
        return response

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
