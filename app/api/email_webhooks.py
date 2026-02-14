"""
Email webhook handlers for tracking email delivery events from Resend.

Resend uses Svix for webhook delivery with automatic retries and signature verification.
This module processes email events for audit trail and delivery monitoring.

Event Types: email.sent, email.delivered, email.bounced, email.delivery_delayed,
             email.complained, email.opened, email.clicked
"""

from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
from app.core.database import mongo
from bson import ObjectId
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhook/resend", tags=["Webhooks"])
async def verify_resend_webhook():
    """
    Webhook verification endpoint for Resend.
    Returns 200 OK to confirm the endpoint is active.
    """
    return {"status": "ok", "message": "Resend webhook endpoint active"}


@router.post("/webhook/resend", tags=["Webhooks"])
async def handle_resend_webhook(
    request: Request,
    svix_id: Optional[str] = Header(None, alias="svix-id"),
    svix_timestamp: Optional[str] = Header(None, alias="svix-timestamp"),
    svix_signature: Optional[str] = Header(None, alias="svix-signature")
):
    """
    Handle incoming webhook events from Resend.

    Resend uses Svix for secure webhook delivery with:
    - Automatic retries: 5s, 5m, 30m, 2h, 5h, 10h
    - HMAC-SHA256 signature verification
    - Event deduplication via svix-id

    Supported Events:
    - email.sent: Accepted by mail server
    - email.delivered: Successfully delivered to inbox
    - email.delivery_delayed: Temporary delivery delay
    - email.bounced: Permanently rejected (hard/soft bounce)
    - email.complained: Marked as spam
    - email.opened: Recipient opened email
    - email.clicked: Recipient clicked link

    Payload Structure:
    {
      "type": "email.delivered",
      "created_at": "2024-02-22T23:41:12.126Z",
      "data": {
        "email_id": "uuid",
        "from": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Email subject"
      }
    }
    """
    try:
        # Get raw body for signature verification (MUST be raw, not parsed JSON)
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')

        # Verify webhook signature using Resend's Svix implementation
        webhook_secret = os.getenv("RESEND_WEBHOOK_SECRET")
        if webhook_secret:
            # Verify using Resend's built-in method
            verified_payload = _verify_resend_webhook(
                body_str,
                svix_id,
                svix_timestamp,
                svix_signature,
                webhook_secret
            )
            if not verified_payload:
                logger.warning(f"Invalid webhook signature. ID: {svix_id}")
                raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            logger.warning("RESEND_WEBHOOK_SECRET not configured - skipping signature verification")
            import json
            verified_payload = json.loads(body_str)

        if not isinstance(verified_payload, dict):
            raise HTTPException(status_code=400, detail="Invalid payload format")

        # Extract event data
        event_type = verified_payload.get("type")
        event_data = verified_payload.get("data", {})
        created_at_str = verified_payload.get("created_at")

        # Parse timestamp
        created_at = datetime.now(timezone.utc)
        if created_at_str and isinstance(created_at_str, str):
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                logger.warning(f"Could not parse timestamp from webhook: {created_at_str}")
                # Fallback to utcnow() is already set

        # Store raw event in database for audit trail
        email_events_collection = mongo.db["email_events"]
        event_record = {
            "svix_id": svix_id,  # Unique ID for deduplication
            "event_type": event_type,
            "email_id": event_data.get("email_id"),
            "to": event_data.get("to", []),
            "from": event_data.get("from"),
            "subject": event_data.get("subject"),
            "created_at": created_at,
            "received_at": datetime.now(timezone.utc),
            "raw_payload": verified_payload,
            "processed": False
        }

        # Add event-specific metadata
        if event_type == "email.bounced":
            # Bounced emails include bounce type and reason
            event_record["bounce_type"] = event_data.get("bounce_type")  # "hard" or "soft"
            event_record["bounce_reason"] = event_data.get("reason")
        elif event_type == "email.complained":
            # Spam complaints include feedback type
            event_record["complaint_feedback_type"] = event_data.get("feedback_type")
        elif event_type in ["email.opened", "email.clicked"]:
            # Opens and clicks include user agent and IP for analytics
            event_record["user_agent"] = event_data.get("user_agent")
            event_record["ip_address"] = event_data.get("ip_address")
            if event_type == "email.clicked":
                event_record["link"] = event_data.get("link")
        elif event_type == "email.delivery_delayed":
            # Delayed deliveries include attempt count and reason
            event_record["attempt"] = event_data.get("attempt")
            event_record["delay_reason"] = event_data.get("reason")

        # Check for duplicate events (Resend may retry)
        existing = await email_events_collection.find_one({"svix_id": svix_id})
        if existing:
            logger.info(f"Duplicate event {svix_id} - already processed")
            return {"status": "duplicate", "event_id": str(existing["_id"])}

        # Insert event record
        result = await email_events_collection.insert_one(event_record)
        event_id = str(result.inserted_id)

        # Update notification delivery status
        if event_type:
            await _update_notification_status(event_type, event_data, event_id)

        # Mark event as processed
        await email_events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"processed": True, "processed_at": datetime.now(timezone.utc)}}
        )

        logger.info(f"✅ Processed {event_type} for {event_data.get('to')} (ID: {event_id})")

        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error processing Resend webhook: {str(e)}")
        # Still return 200 to prevent retries for unrecoverable errors
        return {"status": "error", "message": str(e)}


def _verify_resend_webhook(
    payload: str,
    svix_id: Optional[str],
    svix_timestamp: Optional[str],
    svix_signature: Optional[str],
    secret: str
) -> Optional[dict]:
    """
    Verify webhook signature using Resend's verification method.

    Resend provides resend.webhooks.verify() which uses Svix under the hood.
    The signature is created by: HMAC-SHA256(svix_id.svix_timestamp.payload, secret)

    Returns the verified payload dict if valid, None if invalid.
    """
    try:
        from svix.webhooks import Webhook

        # Prepare headers dict for verification
        headers = {
            "svix-id": svix_id or "",
            "svix-timestamp": svix_timestamp or "",
            "svix-signature": svix_signature or ""
        }

        # Use Svix for webhook verification (Resend uses Svix under the hood)
        wh = Webhook(secret)
        verified = wh.verify(payload, headers)

        # Return the parsed payload if verification succeeded
        return verified

    except Exception as e:
        logger.error(f"Webhook verification failed: {str(e)}")
        return None


async def _update_notification_status(event_type: str, event_data: dict, event_id: str):
    """
    Update notification delivery status based on email events.

    Links email events to their originating notifications for:
    - Delivery rate tracking
    - Bounce monitoring
    - Engagement metrics (opens/clicks)
    - Audit trail compliance
    """
    try:
        notifications_collection = mongo.db["notifications"]
        recipient_email = event_data.get("to", [])[0] if event_data.get("to") else None

        if not recipient_email:
            return

        # Map event types to counter updates and delivery event logs
        event_mapping = {
            "email.sent": {
                "counter": "sent_count",
                "event_data": {
                    "type": "sent",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.delivered": {
                "counter": "delivered_count",
                "event_data": {
                    "type": "delivered",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.bounced": {
                "counter": "bounced_count",
                "event_data": {
                    "type": "bounced",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "bounce_type": event_data.get("bounce_type"),
                    "reason": event_data.get("reason"),
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.delivery_delayed": {
                "counter": "delayed_count",
                "event_data": {
                    "type": "delayed",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "attempt": event_data.get("attempt"),
                    "reason": event_data.get("reason"),
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.opened": {
                "counter": "opened_count",
                "event_data": {
                    "type": "opened",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.clicked": {
                "counter": "clicked_count",
                "event_data": {
                    "type": "clicked",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "link": event_data.get("link"),
                    "timestamp": datetime.now(timezone.utc)
                }
            },
            "email.complained": {
                "counter": "complained_count",
                "event_data": {
                    "type": "complained",
                    "recipient": recipient_email,
                    "email_id": event_data.get("email_id"),
                    "event_id": event_id,
                    "feedback_type": event_data.get("feedback_type"),
                    "timestamp": datetime.now(timezone.utc)
                }
            }
        }

        mapping = event_mapping.get(event_type)
        if not mapping:
            return  # Event type we don't track

        # Update notification records that sent to this recipient
        # We track in delivery_summary for aggregate stats
        update_operation = {
            "$inc": {f"delivery_summary.{mapping['counter']}": 1},
            "$push": {"delivery_events": mapping['event_data']},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }

        # Update all notifications that were sent to this recipient
        # Match by email in delivery logs or sent status
        result = await notifications_collection.update_many(
            {
                "status": "sent",  # Only update sent notifications
                "$or": [
                    {"delivery_summary.last_recipient": recipient_email},
                    {"delivery_logs.sent_to": {"$in": [recipient_email]}}
                ]
            },
            update_operation
        )

        if result.modified_count > 0:
            logger.info(f"📊 Updated {result.modified_count} notifications with {event_type}")

    except Exception as e:
        logger.error(f"Error updating notification status: {str(e)}")
        # Don't raise - webhook should succeed even if status update fails
