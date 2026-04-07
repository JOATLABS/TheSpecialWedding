"""
Inbound Email Service

Handles processing of inbound emails from Resend webhooks,
content fetching from Resend API, threading, and planner inbox operations.

Flow:
1. Webhook fires email.received → handle_email_received_webhook()
2. Metadata stored immediately, content fetched async via Resend API
3. Reply-to address decoded to link email to wedding/planner/guest
4. Planner notified via existing notification system
5. Planner views inbox, reads emails, sends replies
"""

import asyncio
import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any

import aiohttp
import bleach
from bson import ObjectId
from fastapi import HTTPException

from app.core.database import mongo
from app.models.inbound_email import create_inbound_email_document

logger = logging.getLogger(__name__)

EMAIL_ALLOWED_TAGS = [
    "a",
    "b",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
]
EMAIL_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
EMAIL_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


class InboundEmailService:
    """Service for managing inbound emails and planner inbox"""

    def __init__(self):
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.resend_api_base = "https://api.resend.com"

    @property
    def collection(self):
        return mongo.db["inbound_emails"]

    @property
    def email_logs_collection(self):
        return mongo.db["email_logs"]

    @property
    def weddings_collection(self):
        return mongo.db["weddings"]

    @property
    def guests_collection(self):
        return mongo.get_guest_collection()

    # ==================== WEBHOOK HANDLING ====================

    async def handle_email_received_webhook(
        self, payload: dict, svix_id: Optional[str] = None
    ) -> dict:
        """
        Handle email.received webhook from Resend.

        Stores metadata immediately, then kicks off async tasks to:
        1. Fetch full email content from Resend API
        2. Notify the planner of the new message

        Returns result dict with status and email ID.
        """
        try:
            event_data = payload.get("data", {})
            resend_email_id = event_data.get("email_id")

            if not resend_email_id:
                logger.warning("email.received webhook missing email_id")
                return {"status": "error", "message": "Missing email_id"}

            # Check for duplicate via svix_id
            if svix_id:
                existing = await self.collection.find_one({"svix_id": svix_id})
                if existing:
                    logger.info(f"Duplicate email.received webhook: {svix_id}")
                    return {"status": "duplicate", "id": str(existing["_id"])}

            # Also check by resend_email_id
            existing_by_resend = await self.collection.find_one(
                {"resend_email_id": resend_email_id}
            )
            if existing_by_resend:
                logger.info(f"Duplicate email by resend_email_id: {resend_email_id}")
                return {"status": "duplicate", "id": str(existing_by_resend["_id"])}

            # Extract data from webhook
            from_address = event_data.get("from", "")
            from_name = event_data.get("from_name")
            to_list = event_data.get("to", [])
            to_address = to_list[0] if to_list else ""
            subject = event_data.get("subject", "(No subject)")
            attachments_raw = event_data.get("attachments", [])

            # Parse attachments metadata
            attachments_metadata = [
                {
                    "filename": att.get("filename", "unknown"),
                    "content_type": att.get("content_type", "application/octet-stream"),
                    "size": att.get("size"),
                    "content_disposition": att.get("content_disposition"),
                }
                for att in attachments_raw
            ]

            # Decode reply-to address to extract thread context
            thread_context = await self._decode_reply_to_and_resolve(
                to_address, from_address
            )

            # Create document
            doc = create_inbound_email_document(
                resend_email_id=resend_email_id,
                from_address=from_address,
                to_address=to_address,
                subject=subject,
                from_name=from_name,
                attachments_metadata=attachments_metadata,
                thread_context=thread_context,
                svix_id=svix_id,
            )

            # Insert
            result = await self.collection.insert_one(doc)
            email_id = str(result.inserted_id)

            logger.info(
                f"✅ Inbound email stored: {email_id} from {from_address} "
                f"(wedding: {thread_context.get('wedding_slug', 'unknown')})"
            )

            # Async: fetch full content from Resend API
            asyncio.create_task(
                self._fetch_and_store_content(email_id, resend_email_id)
            )

            # Async: notify planner
            planner_id = thread_context.get("planner_id")
            if planner_id:
                asyncio.create_task(
                    self._notify_planner(
                        planner_id=planner_id,
                        wedding_id=thread_context.get("wedding_id"),
                        guest_name=thread_context.get("guest_name")
                        or from_name
                        or from_address,
                        subject=subject,
                        email_id=email_id,
                    )
                )

            return {
                "status": "success",
                "id": email_id,
                "thread_id": thread_context.get("thread_id"),
            }

        except Exception as e:
            logger.error(f"❌ Error handling email.received: {str(e)}")
            return {"status": "error", "message": str(e)}

    # ==================== CONTENT FETCHING ====================

    async def _fetch_and_store_content(
        self, email_id: str, resend_email_id: str, max_retries: int = 3
    ) -> None:
        """
        Fetch full email content from Resend API and update the document.

        The webhook only provides metadata; the actual email body, headers,
        and attachment content must be retrieved via a separate API call.
        """
        if not self.resend_api_key:
            logger.warning(
                "RESEND_API_KEY not set — cannot fetch inbound email content"
            )
            return

        for attempt in range(max_retries):
            try:
                url = f"{self.resend_api_base}/emails/receiving/{resend_email_id}"
                headers = {
                    "Authorization": f"Bearer {self.resend_api_key}",
                    "Accept": "application/json",
                }

                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()

                            content = {
                                "html_body": data.get("html"),
                                "text_body": data.get("text"),
                                "headers": data.get("headers", {}),
                                "reply_to": data.get("reply_to"),
                                "cc": data.get("cc", []),
                                "bcc": data.get("bcc", []),
                                "attachments": data.get("attachments", []),
                                "message_id": data.get("message_id"),
                                "raw_download_url": (data.get("raw") or {}).get(
                                    "download_url"
                                ),
                            }

                            await self.collection.update_one(
                                {"_id": ObjectId(email_id)},
                                {
                                    "$set": {
                                        "content": content,
                                        "status": "content_fetched",
                                        "content_fetched_at": datetime.now(
                                            timezone.utc
                                        ),
                                        "updated_at": datetime.now(timezone.utc),
                                    }
                                },
                            )
                            logger.info(
                                f"📧 Fetched content for inbound email {email_id}"
                            )
                            return

                        elif response.status == 404:
                            logger.warning(
                                f"Inbound email {resend_email_id} not found in Resend API (404)"
                            )
                            break  # Don't retry 404s

                        else:
                            error_text = await response.text()
                            logger.warning(
                                f"Failed to fetch email content (attempt {attempt + 1}): "
                                f"HTTP {response.status} - {error_text}"
                            )

            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout fetching email content (attempt {attempt + 1})"
                )
            except Exception as e:
                logger.error(
                    f"Error fetching email content (attempt {attempt + 1}): {str(e)}"
                )

            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)

        # All retries exhausted
        await self.collection.update_one(
            {"_id": ObjectId(email_id)},
            {
                "$inc": {"content_fetch_attempts": max_retries},
                "$set": {
                    "content_fetch_last_error": "Max retries exhausted",
                    "status": "error",
                    "updated_at": datetime.now(timezone.utc),
                },
            },
        )

    # ==================== REPLY-TO DECODING ====================

    def _decode_reply_to(self, to_address: str) -> dict:
        """
        Decode the reply-to address to extract wedding context.

        Formats:
          reply+wedding-slug@thespecialwedding.io          → wedding only
          reply+wedding-slug--guestObjectId@thespecialwedding.io → wedding + guest

        Returns dict with wedding_slug, guest_id, thread_id.
        """
        try:
            match = re.match(r"reply\+([^@]+)@", to_address)
            if match:
                context_str = match.group(1)
                parts = context_str.split("--", 1)
                wedding_slug = parts[0]
                guest_id = parts[1] if len(parts) > 1 else None

                return {
                    "wedding_slug": wedding_slug,
                    "guest_id": guest_id,
                    "thread_id": f"wedding-{wedding_slug}",
                }
        except Exception as e:
            logger.warning(f"Could not decode reply-to '{to_address}': {e}")

        return {"wedding_slug": None, "guest_id": None, "thread_id": None}

    async def _decode_reply_to_and_resolve(
        self, to_address: str, from_address: str
    ) -> dict:
        """
        Decode reply-to address AND resolve wedding/planner/guest from DB.

        Returns full thread_context dict ready for storage.
        """
        decoded = self._decode_reply_to(to_address)
        context = {
            "wedding_slug": decoded.get("wedding_slug"),
            "thread_id": decoded.get("thread_id"),
            "guest_id": decoded.get("guest_id"),
            "wedding_id": None,
            "planner_id": None,
            "guest_name": None,
        }

        wedding_slug = decoded.get("wedding_slug")
        if not wedding_slug:
            return context

        try:
            # Resolve wedding
            wedding = await self.weddings_collection.find_one(
                {"slug": wedding_slug},
                {"_id": 1, "planner_id": 1, "planner_email": 1, "couple_names": 1},
            )

            if wedding:
                context["wedding_id"] = str(wedding["_id"])
                context["planner_id"] = wedding.get("planner_email") or wedding.get(
                    "planner_id"
                )

            # Resolve guest
            guest_id = decoded.get("guest_id")
            if guest_id and ObjectId.is_valid(guest_id):
                guest = await self.guests_collection.find_one(
                    {"_id": ObjectId(guest_id)}, {"name": 1}
                )
                if guest:
                    context["guest_name"] = guest.get("name")
            elif from_address:
                # Try to find guest by email
                guest = await self.guests_collection.find_one(
                    {
                        "email": from_address,
                        "wedding_id": wedding["_id"] if wedding else None,
                    },
                    {"_id": 1, "name": 1},
                )
                if guest:
                    context["guest_id"] = str(guest["_id"])
                    context["guest_name"] = guest.get("name")

        except Exception as e:
            logger.error(f"Error resolving thread context: {e}")

        return context

    # ==================== PLANNER NOTIFICATION ====================

    async def _notify_planner(
        self,
        planner_id: str,
        wedding_id: Optional[str],
        guest_name: str,
        subject: str,
        email_id: str,
    ) -> None:
        """Trigger planner notification for new inbound email"""
        try:
            from app.services.planner_notification_service import (
                planner_notification_service,
            )

            await planner_notification_service.notify_guest_message(
                planner_id=planner_id,
                wedding_id=wedding_id or "",
                guest_name=guest_name,
                message_preview=subject,
                guest_id=None,
            )
            logger.info(
                f"🔔 Notified planner {planner_id} of inbound email from {guest_name}"
            )

        except Exception as e:
            logger.error(f"Error notifying planner of inbound email: {e}")

    # ==================== INBOX READ OPERATIONS ====================

    async def get_inbox(
        self,
        planner_id: str,
        wedding_id: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> dict:
        """Get paginated inbox for a planner"""
        query: Dict[str, Any] = {"thread_context.planner_id": planner_id}
        if wedding_id:
            query["thread_context.wedding_id"] = wedding_id
        if unread_only:
            query["is_read"] = False

        total = await self.collection.count_documents(query)
        skip = (page - 1) * limit
        pages = (total + limit - 1) // limit if total > 0 else 0

        cursor = (
            self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        )
        emails = []
        async for doc in cursor:
            emails.append(self._format_list_response(doc))

        unread_count = await self.collection.count_documents(
            {"thread_context.planner_id": planner_id, "is_read": False}
        )

        return {
            "emails": emails,
            "total": total,
            "page": page,
            "pages": pages,
            "unread_count": unread_count,
        }

    async def get_unread_count(self, planner_id: str) -> dict:
        """Get unread email count for badge display"""
        count = await self.collection.count_documents(
            {"thread_context.planner_id": planner_id, "is_read": False}
        )
        return {"unread_count": count}

    async def get_email(self, email_id: str, planner_id: str) -> dict:
        """Get single email with full content, auto-marks as read"""
        doc = await self.collection.find_one(
            {"_id": ObjectId(email_id), "thread_context.planner_id": planner_id}
        )

        if not doc:
            raise HTTPException(status_code=404, detail="Email not found")

        # Auto-mark as read
        if not doc.get("is_read"):
            await self.collection.update_one(
                {"_id": ObjectId(email_id)},
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        return self._format_detail_response(doc)

    async def get_thread(self, thread_id: str, planner_id: str) -> dict:
        """
        Get full conversation thread — both inbound and outbound emails.

        Merges inbound emails from inbound_emails collection with
        outbound emails from email_logs collection, sorted chronologically.
        """
        # Inbound emails
        inbound_cursor = self.collection.find(
            {
                "thread_context.thread_id": thread_id,
                "thread_context.planner_id": planner_id,
            }
        ).sort("created_at", 1)

        thread_emails = []
        async for doc in inbound_cursor:
            email_data = self._format_detail_response(doc)
            email_data["direction"] = "inbound"
            thread_emails.append(email_data)

        # Outbound emails (from email_logs)
        outbound_cursor = self.email_logs_collection.find(
            {"thread_id": thread_id}
        ).sort("sent_at", 1)

        async for doc in outbound_cursor:
            thread_emails.append(
                {
                    "id": str(doc.get("_id")),
                    "direction": "outbound",
                    "from_address": doc.get("from_email"),
                    "from_name": doc.get("from_name"),
                    "to_address": doc.get("to"),
                    "subject": doc.get("subject"),
                    "html_body": doc.get("html_content"),
                    "text_body": None,
                    "status": doc.get("status"),
                    "created_at": doc["sent_at"].isoformat()
                    if doc.get("sent_at")
                    else None,
                    "is_read": True,
                    "has_attachments": False,
                }
            )

        # Sort merged list
        thread_emails.sort(key=lambda x: x.get("created_at") or "")

        return {
            "thread_id": thread_id,
            "emails": thread_emails,
            "total": len(thread_emails),
        }

    # ==================== INBOX WRITE OPERATIONS ====================

    async def mark_as_read(self, email_id: str, planner_id: str) -> dict:
        """Mark a single email as read"""
        result = await self.collection.update_one(
            {"_id": ObjectId(email_id), "thread_context.planner_id": planner_id},
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Email not found")
        return {"message": "Marked as read"}

    async def mark_all_as_read(self, planner_id: str) -> dict:
        """Mark all emails as read for a planner"""
        now = datetime.now(timezone.utc)
        result = await self.collection.update_many(
            {"thread_context.planner_id": planner_id, "is_read": False},
            {"$set": {"is_read": True, "read_at": now, "updated_at": now}},
        )
        return {"marked_count": result.modified_count}

    async def send_reply(
        self,
        email_id: str,
        planner_id: str,
        reply_html: str,
        reply_text: Optional[str] = None,
    ) -> dict:
        """Send a reply to an inbound email via Resend"""
        # Get original email
        original = await self.collection.find_one(
            {"_id": ObjectId(email_id), "thread_context.planner_id": planner_id}
        )

        if not original:
            raise HTTPException(status_code=404, detail="Email not found")

        thread_context = original.get("thread_context", {})
        wedding_slug = thread_context.get("wedding_slug")
        guest_id = thread_context.get("guest_id")

        # Get wedding details for from_name
        from_name = "TheSpecialWedding"
        from_email = None
        if thread_context.get("wedding_id"):
            wedding = await self.weddings_collection.find_one(
                {"_id": ObjectId(thread_context["wedding_id"])},
                {"couple_names": 1, "reminder_from_email": 1},
            )
            if wedding:
                from_name = wedding.get("couple_names", from_name)
                from_email = wedding.get("reminder_from_email")

        # Build reply subject
        original_subject = original.get("subject", "")
        subject = (
            original_subject
            if original_subject.startswith("Re:")
            else f"Re: {original_subject}"
        )

        # Build reply-to address to maintain thread
        reply_to_addr = original.get("to_address")

        # Send via existing email service
        from app.services.email_service_resend import ResendEmailService

        email_service = ResendEmailService()

        result = await email_service.send_email(
            to_email=original["from_address"],
            subject=subject,
            html_content=reply_html,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to_addr,
            wedding_id=thread_context.get("wedding_id"),
            email_type="inbound_reply",
            wedding_slug=wedding_slug,
            guest_id=guest_id,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=f"Failed to send reply: {result.get('error')}"
            )

        # Mark original as replied
        await self.collection.update_one(
            {"_id": ObjectId(email_id)},
            {
                "$set": {
                    "planner_response_sent": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        return {
            "status": "success",
            "reply_resend_id": result.get("id"),
            "sent_to": original["from_address"],
        }

    # ==================== RESPONSE FORMATTERS ====================

    def _format_list_response(self, doc: dict) -> dict:
        """Format document for inbox listing (no content body)"""
        content = doc.get("content") or {}
        text_body = content.get("text_body") or ""
        if not text_body and content.get("html_body"):
            # Strip HTML tags for preview
            text_body = re.sub(r"<[^>]+>", "", content.get("html_body", ""))
        preview = (text_body[:200] + "...") if len(text_body) > 200 else text_body

        thread_ctx = doc.get("thread_context", {})

        return {
            "id": str(doc["_id"]),
            "from_address": doc.get("from_address"),
            "from_name": doc.get("from_name"),
            "subject": doc.get("subject"),
            "preview": preview.strip(),
            "thread_id": thread_ctx.get("thread_id"),
            "guest_name": thread_ctx.get("guest_name"),
            "wedding_slug": thread_ctx.get("wedding_slug"),
            "wedding_id": thread_ctx.get("wedding_id"),
            "is_read": doc.get("is_read", False),
            "planner_response_sent": doc.get("planner_response_sent", False),
            "created_at": doc["created_at"].isoformat()
            if doc.get("created_at")
            else None,
            "has_attachments": len(doc.get("attachments_metadata", [])) > 0,
            "status": doc.get("status", "received"),
        }

    def _format_detail_response(self, doc: dict) -> dict:
        """Format document for single email view (with content)"""
        base = self._format_list_response(doc)
        content = doc.get("content") or {}

        raw_html_body = content.get("html_body")
        base["html_body"] = (
            bleach.clean(
                raw_html_body,
                tags=EMAIL_ALLOWED_TAGS,
                attributes=EMAIL_ALLOWED_ATTRIBUTES,
                protocols=EMAIL_ALLOWED_PROTOCOLS,
                strip=True,
                strip_comments=True,
            )
            if raw_html_body
            else None
        )
        base["text_body"] = content.get("text_body")
        base["attachments"] = content.get("attachments", [])

        return base


# Singleton
inbound_email_service = InboundEmailService()
