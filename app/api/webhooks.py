# app/api/webhooks.py

from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional, Dict, Any
import logging
import hashlib
import hmac
import json
from datetime import datetime

from app.core.database import mongo
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

settings = get_settings()

@router.post("/resend", summary="Handle Resend email delivery events")
async def handle_resend_webhook(
    request: Request,
    resend_signature: Optional[str] = Header(None, alias="resend-signature")
):
    """
    Handle webhook events from Resend for email delivery tracking

    Supported events:
    - email.sent: Email was accepted by Resend
    - email.delivered: Email was delivered to recipient's mailbox
    - email.delivery_delayed: Email delivery was delayed
    - email.complained: Recipient marked email as spam
    - email.bounced: Email bounced (hard or soft bounce)
    - email.opened: Recipient opened the email
    - email.clicked: Recipient clicked a link in the email
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify webhook signature if configured
        secret = getattr(settings, "RESEND_WEBHOOK_SECRET", None)
        if secret and resend_signature:
            if not _verify_resend_signature(body, resend_signature, secret):
                logger.warning("Invalid Resend webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse the webhook payload
        try:
            payload = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook payload")
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Extract event data
        event_type = payload.get("type")
        event_data = payload.get("data", {})
        created_at = payload.get("created_at")

        if not event_type or not event_data:
            logger.error("Missing required fields in webhook payload")
            raise HTTPException(status_code=400, detail="Missing required fields")

        # Process the event
        await _process_resend_event(event_type, event_data, created_at)

        logger.info(f"Processed Resend webhook event: {event_type}")

        return {"status": "success", "message": "Webhook processed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Resend webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing webhook")

@router.post("/test", summary="Test webhook endpoint")
async def test_webhook(payload: Dict[str, Any]):
    """Test webhook endpoint for development"""
    try:
        logger.info(f"Test webhook received: {payload}")

        # Simulate processing
        event_type = payload.get("type", "test.event")
        await _process_resend_event(event_type, payload.get("data", {}), datetime.utcnow().isoformat())

        return {"status": "success", "message": "Test webhook processed"}

    except Exception as e:
        logger.error(f"Error in test webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _process_resend_event(event_type: str, event_data: Dict[str, Any], created_at: str):
    """Process a Resend webhook event and update our tracking data"""
    try:
        # Extract common fields
        email_id = event_data.get("email_id")
        to_email: Optional[str] = event_data.get("to")
        from_email = event_data.get("from")
        subject = event_data.get("subject")

        if not email_id:
            logger.warning(f"No email_id in event data for {event_type}")
            return

        # Parse timestamp (defensive: fall back to current UTC on any parse issue)
        try:
            timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00')) if created_at else datetime.utcnow()
        except Exception:
            timestamp = datetime.utcnow()

        # Create delivery event record
        delivery_event = {
            "event_id": f"{email_id}_{event_type}_{int(timestamp.timestamp())}",
            "email_id": email_id,
            "event_type": _normalize_event_type(event_type),
            "timestamp": timestamp,
            "recipient": to_email,
            "sender": from_email,
            "subject": subject,
            "metadata": {
                "raw_event_type": event_type,
                "event_data": event_data
            },
            "created_at": datetime.utcnow()
        }

        # Store the delivery event
        mongo.db["email_delivery_events"].insert_one(delivery_event)

        # Update the corresponding email log if it exists
        await _update_email_log(email_id, event_type, event_data, timestamp)

        # Handle specific event types
        if event_type in ["email.bounced", "email.complained"] and to_email:
            await _handle_negative_event(email_id, event_type, event_data, to_email)

        logger.debug(f"Stored delivery event: {event_type} for email {email_id}")

    except Exception as e:
        logger.error(f"Error processing event {event_type}: {str(e)}")
        raise

async def _update_email_log(email_id: str, event_type: str, event_data: Dict[str, Any], timestamp: datetime):
    """Update the email log with delivery status"""
    try:
        update_data = {
            "last_event": event_type,
            "last_event_at": timestamp
        }

        # Update specific fields based on event type
        if event_type == "email.delivered":
            update_data["delivered_at"] = timestamp
            update_data["delivery_status"] = "delivered"
        elif event_type == "email.bounced":
            update_data["bounced_at"] = timestamp
            update_data["delivery_status"] = "bounced"
            update_data["bounce_reason"] = event_data.get("bounce_reason")
        elif event_type == "email.complained":
            update_data["complained_at"] = timestamp
            update_data["delivery_status"] = "complained"
        elif event_type == "email.opened":
            # Track first open time
            existing = mongo.db["email_logs"].find_one({"resend_id": email_id, "opened_at": {"$exists": True}})
            if not existing:
                update_data["opened_at"] = timestamp
                update_data["open_count"] = 1
            else:
                # Increment open count
                mongo.db["email_logs"].update_one(
                    {"resend_id": email_id},
                    {"$inc": {"open_count": 1}}
                )
                return
        elif event_type == "email.clicked":
            # Track click data
            click_data = {
                "clicked_at": timestamp,
                "url": event_data.get("click", {}).get("url"),
                "link_id": event_data.get("click", {}).get("link_id")
            }

            mongo.db["email_logs"].update_one(
                {"resend_id": email_id},
                {
                    "$inc": {"click_count": 1},
                    "$push": {"clicks": click_data},
                    "$set": {"last_clicked_at": timestamp}
                }
            )
            return

        # Update the email log
        result = mongo.db["email_logs"].update_one(
            {"resend_id": email_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            logger.warning(f"No email log found for Resend ID: {email_id}")

    except Exception as e:
        logger.error(f"Error updating email log for {email_id}: {str(e)}")

async def _handle_negative_event(email_id: str, event_type: str, event_data: Dict[str, Any], to_email: str):
    """Handle bounces and complaints"""
    try:
        # Log the negative event for further analysis
        negative_event = {
            "email_id": email_id,
            "recipient": to_email,
            "event_type": event_type,
            "reason": event_data.get("bounce_reason") or event_data.get("complaint_reason"),
            "details": event_data,
            "created_at": datetime.utcnow()
        }

        mongo.db["email_negative_events"].insert_one(negative_event)

        # For hard bounces or complaints, consider adding to suppression list
        if event_type == "email.bounced":
            bounce_type = event_data.get("bounce_type", "").lower()
            if bounce_type == "hard":
                bounce_reason = event_data.get("bounce_reason") or ""
                await _add_to_suppression_list(to_email, "hard_bounce", str(bounce_reason))
        elif event_type == "email.complained":
            await _add_to_suppression_list(to_email, "complaint", "User marked email as spam")

        logger.info(f"Handled negative event {event_type} for {to_email}")

    except Exception as e:
        logger.error(f"Error handling negative event: {str(e)}")

async def _add_to_suppression_list(email: str, reason: str, details: str):
    """Add email to suppression list to prevent future sends"""
    try:
        suppression_entry = {
            "email": email.lower(),
            "reason": reason,
            "details": details,
            "suppressed_at": datetime.utcnow(),
            "status": "active"
        }

        # Use upsert to avoid duplicates
        mongo.db["email_suppressions"].update_one(
            {"email": email.lower()},
            {"$set": suppression_entry},
            upsert=True
        )

        logger.info(f"Added {email} to suppression list: {reason}")

    except Exception as e:
        logger.error(f"Error adding {email} to suppression list: {str(e)}")

def _normalize_event_type(event_type: str) -> str:
    """Normalize Resend event types to our internal format"""
    mapping = {
        "email.sent": "sent",
        "email.delivered": "delivered",
        "email.delivery_delayed": "delayed",
        "email.bounced": "bounced",
        "email.complained": "complained",
        "email.opened": "opened",
        "email.clicked": "clicked"
    }
    return mapping.get(event_type, event_type)

def _verify_resend_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Resend webhook signature"""
    try:
        # Resend uses HMAC-SHA256
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Remove 'sha256=' prefix if present
        if signature.startswith('sha256='):
            signature = signature[7:]

        return hmac.compare_digest(expected, signature)

    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False

@router.get("/delivery-stats", summary="Get delivery statistics")
async def get_delivery_stats(
    days: int = 30,
    template_id: Optional[str] = None
):
    """Get email delivery statistics for monitoring"""
    try:
        from datetime import timedelta
        from_date = datetime.utcnow() - timedelta(days=days)

        # Build aggregation pipeline
        match_filter = {"timestamp": {"$gte": from_date}}
        if template_id:
            # We'll need to join with email_logs to filter by template
            pass

        pipeline = [
            {"$match": match_filter},
            {
                "$group": {
                    "_id": "$event_type",
                    "count": {"$sum": 1},
                    "latest": {"$max": "$timestamp"}
                }
            }
        ]

        stats = list(mongo.db["email_delivery_events"].aggregate(pipeline))

        # Format the results
        delivery_stats = {
            "total_events": sum(stat["count"] for stat in stats),
            "events_by_type": {stat["_id"]: stat["count"] for stat in stats},
            "date_range": {
                "from": from_date,
                "to": datetime.utcnow(),
                "days": days
            }
        }

        return delivery_stats

    except Exception as e:
        logger.error(f"Error getting delivery stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving delivery statistics")