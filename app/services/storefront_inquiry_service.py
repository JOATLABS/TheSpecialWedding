"""Durable public storefront inquiry capture and best-effort notification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
STOREFRONT_NOTIFICATION_LEASE = timedelta(minutes=5)
STOREFRONT_NOTIFICATION_RETRY_DELAY = timedelta(minutes=1)
# Resend retains idempotency keys for 24 hours. Keep a one-hour safety margin
# so an ambiguous request is never retried after the provider may forget it.
STOREFRONT_NOTIFICATION_SAFE_RETRY_WINDOW = timedelta(hours=23)


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
    def _notification_is_recoverable(
        inquiry: dict,
        *,
        now: datetime | None = None,
    ) -> bool:
        notification = inquiry.get("notification")
        if not isinstance(notification, dict):
            return False
        current_time = now or datetime.now(timezone.utc)
        notification_status = notification.get("status")
        if notification_status == "pending":
            return True
        if notification_status == "retry_pending":
            next_attempt_at = notification.get("next_attempt_at")
            return not isinstance(next_attempt_at, datetime) or (
                next_attempt_at <= current_time
            )
        if notification_status == "sending":
            lease_expires_at = notification.get("lease_expires_at")
            return not isinstance(lease_expires_at, datetime) or (
                lease_expires_at <= current_time
            )
        return False

    @staticmethod
    def _notification_snapshot_query(inquiry: dict) -> dict:
        notification = inquiry.get("notification")
        if not isinstance(notification, dict):
            return {"notification.status": {"$exists": False}}
        notification_status = notification.get("status")
        query: dict[str, Any] = {"notification.status": notification_status}
        if notification_status == "sending":
            for field in ("claim_token", "lease_expires_at"):
                value = notification.get(field)
                query[f"notification.{field}"] = (
                    value if value is not None else {"$exists": False}
                )
        elif notification_status == "retry_pending":
            next_attempt_at = notification.get("next_attempt_at")
            query["notification.next_attempt_at"] = (
                next_attempt_at if next_attempt_at is not None else {"$exists": False}
            )
        return query

    @staticmethod
    def _provider_idempotency_key(inquiry_id: Any) -> str:
        return f"storefront-inquiry/{inquiry_id}"

    @staticmethod
    def _ambiguous_retry_is_unsafe(inquiry: dict, now: datetime) -> bool:
        notification = inquiry.get("notification")
        if not isinstance(notification, dict) or notification.get("status") not in {
            "sending",
            "retry_pending",
        }:
            return False
        provider_key = notification.get("provider_idempotency_key")
        retry_until = notification.get("retry_until")
        return (
            not isinstance(provider_key, str)
            or not provider_key
            or not isinstance(retry_until, datetime)
            or retry_until <= now
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
        inquiry: dict,
        owner_id: str,
        request_hash: str,
    ) -> tuple[str, str] | None:
        inquiry_id = inquiry.get("_id")
        if inquiry_id is None:
            return None
        claim_token = uuid4().hex
        now = datetime.now(timezone.utc)
        notification = inquiry.get("notification")
        if not isinstance(notification, dict):
            return None
        provider_idempotency_key = notification.get("provider_idempotency_key")
        if (
            not isinstance(provider_idempotency_key, str)
            or not provider_idempotency_key
        ):
            provider_idempotency_key = self._provider_idempotency_key(inquiry_id)
        retry_until = notification.get("retry_until")
        if not isinstance(retry_until, datetime):
            retry_until = now + STOREFRONT_NOTIFICATION_SAFE_RETRY_WINDOW
        claim_query = {
            "_id": inquiry_id,
            "planner_id": owner_id,
            "request_hash": request_hash,
            **self._notification_snapshot_query(inquiry),
        }
        claim_update = {
            "$set": {
                "notification.status": "sending",
                "notification.delivery_outcome": "unknown",
                "notification.claim_token": claim_token,
                "notification.claimed_at": now,
                "notification.lease_expires_at": (now + STOREFRONT_NOTIFICATION_LEASE),
                "notification.provider_idempotency_key": (provider_idempotency_key),
                "notification.retry_until": retry_until,
                "updated_at": now,
            },
            "$inc": {"notification.attempt_count": 1},
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
            return (claim_token, provider_idempotency_key) if reconciled else None
        if getattr(claimed, "modified_count", 0) != 1:
            return None
        return claim_token, provider_idempotency_key

    async def _mark_delivery_unknown(
        self,
        inquiries: Any,
        inquiry: dict,
        *,
        owner_id: str,
        request_hash: str,
    ) -> bool:
        inquiry_id = inquiry.get("_id")
        if inquiry_id is None:
            return False
        now = datetime.now(timezone.utc)
        outcome = await inquiries.update_one(
            {
                "_id": inquiry_id,
                "planner_id": owner_id,
                "request_hash": request_hash,
                **self._notification_snapshot_query(inquiry),
            },
            {
                "$set": {
                    "notification.status": "delivery_unknown",
                    "notification.delivery_outcome": "unknown",
                    "notification.error": (
                        "Provider acknowledgement could not be reconciled "
                        "inside the safe idempotency window"
                    ),
                    "notification.attempted_at": now,
                    "updated_at": now,
                },
                "$unset": {
                    "notification.claim_token": "",
                    "notification.lease_expires_at": "",
                    "notification.next_attempt_at": "",
                },
            },
        )
        return getattr(outcome, "matched_count", 0) == 1

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
    ) -> bool:
        inquiry_id = inquiry.get("_id")
        if inquiry_id is None:
            return False
        now = datetime.now(timezone.utc)
        if self._ambiguous_retry_is_unsafe(inquiry, now):
            return await self._mark_delivery_unknown(
                inquiries,
                inquiry,
                owner_id=owner_id,
                request_hash=request_hash,
            )
        claim = await self._claim_notification(
            inquiries,
            inquiry=inquiry,
            owner_id=owner_id,
            request_hash=request_hash,
        )
        if not claim:
            return False
        claim_token, provider_idempotency_key = claim

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
                        provider_idempotency_key=provider_idempotency_key,
                    )
                    if planner
                    else {"status": "failed", "error": "Planner is unavailable"}
                )
        else:
            notification = await self._notify_planner(
                planner=planner,
                slug=slug,
                payload=payload,
                provider_idempotency_key=provider_idempotency_key,
            )

        attempted_at = datetime.now(timezone.utc)
        notification_status = str(notification["status"])
        outcome_set = {
            "notification.status": notification_status,
            "notification.delivery_outcome": (
                "confirmed"
                if notification_status == "sent"
                else "unknown"
                if notification_status == "retry_pending"
                else "not_sent"
            ),
            "notification.error": notification.get("error"),
            "notification.provider_id": notification.get("provider_id"),
            "notification.attempted_at": attempted_at,
            "updated_at": attempted_at,
        }
        outcome_unset = {
            "notification.claim_token": "",
            "notification.lease_expires_at": "",
        }
        if notification_status == "retry_pending":
            outcome_set["notification.next_attempt_at"] = (
                attempted_at + STOREFRONT_NOTIFICATION_RETRY_DELAY
            )
        else:
            outcome_unset["notification.next_attempt_at"] = ""
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
                    "$set": outcome_set,
                    "$unset": outcome_unset,
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
        return True

    async def process_pending_notifications(self, *, limit: int = 10) -> int:
        """Recover pending or abandoned inquiry notifications without double-send."""
        bounded_limit = max(1, min(int(limit), 50))
        now = datetime.now(timezone.utc)
        inquiries = self._mongo.db["storefront_inquiries"]
        cursor = (
            inquiries.find(
                {
                    "$or": [
                        {"notification.status": "pending"},
                        {
                            "notification.status": "retry_pending",
                            "notification.next_attempt_at": {"$lte": now},
                        },
                        {
                            "notification.status": "retry_pending",
                            "notification.next_attempt_at": {"$exists": False},
                        },
                        {
                            "notification.status": "sending",
                            "notification.lease_expires_at": {"$lte": now},
                        },
                        {
                            "notification.status": "sending",
                            "notification.lease_expires_at": {"$exists": False},
                        },
                    ]
                }
            )
            .sort([("created_at", 1), ("_id", 1)])
            .limit(bounded_limit)
        )
        processed = 0
        async for inquiry in cursor:
            owner_id = inquiry.get("planner_id")
            request_hash = inquiry.get("request_hash")
            slug = inquiry.get("storefront_slug")
            if not all(
                isinstance(value, str) and value
                for value in (owner_id, request_hash, slug)
            ):
                logger.error(
                    "Storefront inquiry notification has invalid ownership metadata",
                    extra={"inquiry_id": str(inquiry.get("_id"))},
                )
                continue
            try:
                payload = StorefrontInquiryRequest.model_validate(
                    {
                        "name": inquiry.get("name"),
                        "email": inquiry.get("email"),
                        "phone": inquiry.get("phone"),
                        "wedding_date": inquiry.get("wedding_date"),
                        "message": inquiry.get("message"),
                        "idempotency_key": inquiry.get("idempotency_key"),
                    }
                )
            except Exception:
                logger.exception(
                    "Storefront inquiry notification payload is invalid",
                    extra={"inquiry_id": str(inquiry.get("_id"))},
                )
                continue
            if await self._deliver_notification_if_claimed(
                inquiries,
                inquiry,
                owner_id=owner_id,
                request_hash=request_hash,
                slug=slug,
                payload=payload,
            ):
                processed += 1
        return processed

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
            if self._notification_is_recoverable(existing):
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
        provider_idempotency_key: str,
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
                idempotency_key=provider_idempotency_key,
            )
        except Exception as exc:
            logger.exception("Storefront inquiry notification raised")
            return {"status": "retry_pending", "error": str(exc)[:500]}

        if not result.get("success"):
            return {
                "status": (
                    "retry_pending" if result.get("delivery_unknown") else "failed"
                ),
                "error": str(result.get("error") or "Email delivery failed")[:500],
            }
        return {
            "status": "sent",
            "provider_id": str(result.get("id") or "") or None,
        }


storefront_inquiry_service = StorefrontInquiryService()
