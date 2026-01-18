from fastapi import APIRouter, HTTPException, Depends, Request
from app.services.reminder_service import ReminderService
from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
from app.core.config import settings
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

reminder_service = ReminderService()

@router.post("/reminders/send", tags=["Admin"])
def send_reminder(event_type: str, message: str, target_group: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return reminder_service.send_reminders(event_type, message, target_group)

@router.get("/reminders/logs", tags=["Admin"])
async def get_logs(current_user: ExtendedAuthUser = Depends(require_admin_or_planner)):
    return await reminder_service.get_logs()

@router.get("/reminders/sms-callback", tags=["Webhooks"])
async def verify_sms_callback():
    """
    Handle GET requests for webhook verification
    Returns 200 OK to confirm the endpoint is active
    """
    return {"status": "ok", "message": "SMS webhook endpoint active"}

@router.post("/reminders/sms-callback", tags=["Webhooks"])
async def handle_sms_callback(request: Request):
    """
    Handle SMS webhooks for STOP, HELP, and START messages
    Works with both Telnyx and Twilio webhook formats
    Compliant with toll-free SMS requirements
    """
    try:
        data = await request.json()
        guest_collection = mongo.get_guest_collection()
        wedding_collection = mongo.db["weddings"]
        
        # Import SMS service to send responses
        from app.services.reminder_service_telnyx import TelnyxReminderService
        sms_service = TelnyxReminderService()
        
        # Handle Telnyx format
        if "data" in data and "event_type" in data.get("data", {}):
            event_type = data.get("data", {}).get("event_type", "")
            payload = data.get("data", {}).get("payload", {})
            
            if event_type == "message.received":
                from_number = payload.get("from", {}).get("phone_number", "")
                to_number = payload.get("to", [{}])[0].get("phone_number", "")
                text = payload.get("text", "").strip().upper()
                
                normalized_number = from_number.replace("+1", "").replace("+", "")
                
                # Find guest and their associated wedding
                guest = await guest_collection.find_one({
                    "$or": [
                        {"phone": from_number},
                        {"phone": normalized_number},
                        {"phone": f"1{normalized_number}"}
                    ]
                })

                wedding_name = "the wedding"
                if guest and guest.get("wedding_id"):
                    wedding = await wedding_collection.find_one({"_id": guest["wedding_id"]})
                    if wedding:
                        wedding_name = wedding.get("couple_names", "the wedding")
                
                # Handle STOP messages
                if text in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                    result = await guest_collection.update_many(
                        {
                            "$or": [
                                {"phone": from_number},
                                {"phone": normalized_number},
                                {"phone": f"1{normalized_number}"}
                            ]
                        },
                        {
                            "$set": {
                                "sms_opt_in": False,
                                "sms_opt_out_date": datetime.now(timezone.utc)
                            }
                        }
                    )
                    logger.info(f"Opted out {result.modified_count} guests with phone {from_number}")
                    
                    # Send confirmation
                    confirmation_msg = f"You have been unsubscribed from {wedding_name} SMS notifications. Reply START to resubscribe."
                    sms_service._send_sms(from_number, confirmation_msg)
                
                # Handle HELP messages
                elif text in ["HELP", "INFO"]:
                    help_msg = f"Wedding reminders from {wedding_name}. Reply STOP to unsubscribe. For support, visit thespecialwedding.com/support or call (319) 529-6088. Msg&data rates may apply."
                    sms_service._send_sms(from_number, help_msg)
                
                # Handle START/UNSTOP messages
                elif text in ["START", "UNSTOP", "YES", "SUBSCRIBE"]:
                    result = await guest_collection.update_many(
                        {
                            "$or": [
                                {"phone": from_number},
                                {"phone": normalized_number},
                                {"phone": f"1{normalized_number}"}
                            ]
                        },
                        {
                            "$set": {
                                "sms_opt_in": True,
                                "sms_opt_in_date": datetime.now(timezone.utc)
                            },
                            "$unset": {
                                "sms_opt_out_date": ""
                            }
                        }
                    )
                    logger.info(f"Re-subscribed {result.modified_count} guests with phone {from_number}")

                    # Send welcome message
                    welcome_msg = f"Welcome back! You're subscribed to reminders for {wedding_name}. Reply STOP to opt out. Msg&data rates may apply."
                    sms_service._send_sms(from_number, welcome_msg)

                # Handle any other messages (customer support)
                else:
                    # Get wedding planner info for routing
                    assigned_planner_email = None
                    planner_name = None
                    if guest and guest.get("wedding_id"):
                        wedding_doc = await wedding_collection.find_one({"_id": guest["wedding_id"]})
                        if wedding_doc:
                            assigned_planner_email = wedding_doc.get("assigned_planner_email")
                            # Get planner name for better notifications
                            if assigned_planner_email:
                                planner = await mongo.get_users_collection().find_one({"email": assigned_planner_email})
                                if planner:
                                    planner_name = planner.get("company_name") or planner.get("email")

                    # Store as support ticket with proper routing
                    support_ticket = {
                        "phone": from_number,
                        "message": payload.get("text", ""),
                        "guest_id": str(guest["_id"]) if guest else None,
                        "wedding_id": str(guest["wedding_id"]) if guest and guest.get("wedding_id") else None,
                        "wedding_name": wedding_name,
                        "assigned_to": assigned_planner_email,  # ← Route to responsible planner
                        "planner_name": planner_name,
                        "status": "new",
                        "created_at": datetime.now(timezone.utc),
                        "source": "sms",
                        "provider": "telnyx",
                        "is_read": False,
                        "priority": "normal"
                    }
                    await mongo.db["support_tickets"].insert_one(support_ticket)
                    logger.info(f"Support ticket created from {from_number} for planner {assigned_planner_email}: {text}")

                    # Send acknowledgment to guest
                    contact_info = f"your wedding planner at {planner_name}" if planner_name else "us"
                    support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon. For urgent matters, call (319) 529-6088."
                    sms_service._send_sms(from_number, support_msg)

                    # Notify the responsible wedding planner
                    if assigned_planner_email:
                        await _notify_planner_support_ticket(support_ticket, assigned_planner_email)
                    else:
                        # Fallback: notify ROOT_ADMIN if no planner assigned
                        await _notify_root_admin_support_ticket(support_ticket)
        
        # Handle Twilio format (for backward compatibility)
        elif "MessageStatus" in data or "Body" in data:
            from_number = data.get("From", "")
            to_number = data.get("To", "")
            body = data.get("Body", "").strip().upper()
            
            normalized_number = from_number.replace("+1", "").replace("+", "")
            
            # Find guest and their associated wedding
            guest = await guest_collection.find_one({
                "$or": [
                    {"phone": from_number},
                    {"phone": normalized_number},
                    {"phone": f"1{normalized_number}"}
                ]
            })

            wedding_name = "the wedding"
            if guest and guest.get("wedding_id"):
                wedding = await wedding_collection.find_one({"_id": guest["wedding_id"]})
                if wedding:
                    wedding_name = wedding.get("couple_names", "the wedding")
            
            if body in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                result = await guest_collection.update_many(
                    {
                        "$or": [
                            {"phone": from_number},
                            {"phone": normalized_number},
                            {"phone": f"1{normalized_number}"}
                        ]
                    },
                    {
                        "$set": {
                            "sms_opt_in": False,
                            "sms_opt_out_date": datetime.now(timezone.utc)
                        }
                    }
                )
                logger.info(f"Opted out {result.modified_count} guests with phone {from_number}")
            
            elif body in ["HELP", "INFO"]:
                # Note: Twilio auto-responds to HELP, so we may not need to send a response
                logger.info(f"HELP request from {from_number}")
            
            elif body in ["START", "UNSTOP", "YES", "SUBSCRIBE"]:
                result = await guest_collection.update_many(
                    {
                        "$or": [
                            {"phone": from_number},
                            {"phone": normalized_number},
                            {"phone": f"1{normalized_number}"}
                        ]
                    },
                    {
                        "$set": {
                            "sms_opt_in": True,
                            "sms_opt_in_date": datetime.now(timezone.utc)
                        },
                        "$unset": {
                            "sms_opt_out_date": ""
                        }
                    }
                )
                logger.info(f"Re-subscribed {result.modified_count} guests with phone {from_number}")

            # Handle any other messages (customer support) - Twilio format
            elif body and body not in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "HELP", "INFO", "START", "UNSTOP", "YES", "SUBSCRIBE"]:
                # Get wedding planner info for routing
                assigned_planner_email = None
                planner_name = None
                if guest and guest.get("wedding_id"):
                    wedding_doc = await wedding_collection.find_one({"_id": guest["wedding_id"]})
                    if wedding_doc:
                        assigned_planner_email = wedding_doc.get("assigned_planner_email")
                        # Get planner name for better notifications
                        if assigned_planner_email:
                            planner = await mongo.get_users_collection().find_one({"email": assigned_planner_email})
                            if planner:
                                planner_name = planner.get("company_name") or planner.get("email")

                # Store as support ticket with proper routing
                support_ticket = {
                    "phone": from_number,
                    "message": data.get("Body", ""),
                    "guest_id": str(guest["_id"]) if guest else None,
                    "wedding_id": str(guest["wedding_id"]) if guest and guest.get("wedding_id") else None,
                    "wedding_name": wedding_name,
                    "assigned_to": assigned_planner_email,  # ← Route to responsible planner
                    "planner_name": planner_name,
                    "status": "new",
                    "created_at": datetime.now(timezone.utc),
                    "source": "sms",
                    "provider": "twilio",
                    "message_sid": data.get("MessageSid"),
                    "is_read": False,
                    "priority": "normal"
                }
                await mongo.db["support_tickets"].insert_one(support_ticket)
                logger.info(f"Support ticket created from {from_number} for planner {assigned_planner_email}: {body}")

                # Send acknowledgment to guest
                from app.services.sms_service import SMSService
                twilio_sms_service = SMSService()
                contact_info = f"your wedding planner at {planner_name}" if planner_name else "us"
                support_msg = f"Thanks for your message! {contact_info.capitalize()} will respond soon. For urgent matters, call (319) 529-6088."
                twilio_sms_service.send_sms(from_number, support_msg)

                # Notify the responsible wedding planner
                if assigned_planner_email:
                    await _notify_planner_support_ticket(support_ticket, assigned_planner_email)
                else:
                    # Fallback: notify ROOT_ADMIN if no planner assigned
                    await _notify_root_admin_support_ticket(support_ticket)
        
        return {"status": "ok"}
        
    except Exception as e:
        import traceback
        logger.error(f"Error processing SMS webhook: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions for notifications
async def _notify_planner_support_ticket(ticket: dict, planner_email: str):
    """Send email notification to wedding planner about new support ticket"""
    try:
        from app.services.email_service_resend import ResendEmailService
        email_service = ResendEmailService()

        frontend_url = settings.get_required_url("FRONTEND_URL")
        subject = f"New Guest Message: {ticket['wedding_name']}"

        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2c3e50;">📱 New Message from Guest</h2>

            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Wedding:</strong> {ticket['wedding_name']}</p>
                <p><strong>From:</strong> {ticket['phone']}</p>
                <p><strong>Received:</strong> {ticket['created_at'].strftime('%B %d, %Y at %I:%M %p UTC')}</p>
            </div>

            <div style="background-color: #fff; padding: 20px; border-left: 4px solid #2c3e50; margin: 20px 0;">
                <p style="margin: 0;"><em>"{ticket['message']}"</em></p>
            </div>

            <p>Please respond to your guest as soon as possible.</p>

            <div style="margin: 30px 0;">
                <a href="{frontend_url}/admin/support?ticket={str(ticket.get('_id', ''))}"
                   style="background-color: #2c3e50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block;">
                    View & Respond in Dashboard
                </a>
            </div>

            <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">

            <p style="color: #666; font-size: 12px;">
                This notification was sent because you are the wedding planner for {ticket['wedding_name']}.
                Manage your notification preferences in your dashboard settings.
            </p>
        </div>
        """

        await email_service.send_email(
            to_email=planner_email,
            subject=subject,
            html_content=html_content,
            wedding_id=ticket.get('wedding_id'),
            email_type="support_notification"
        )
        logger.info(f"Email notification sent to planner {planner_email} for ticket {ticket.get('_id')}")
    except Exception as e:
        logger.error(f"Failed to send email notification to planner: {str(e)}")

async def _notify_root_admin_support_ticket(ticket: dict):
    """Send notification to ROOT_ADMIN for tickets without assigned planner"""
    try:
        import os
        import requests

        # Send Slack notification if webhook configured
        slack_webhook = os.getenv("SLACK_WEBHOOK")
        if slack_webhook:
            message = {
                "text": "🚨 Unassigned Support Ticket",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 Support Ticket - No Planner Assigned"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*From:*\n{ticket['phone']}"},
                            {"type": "mrkdwn", "text": f"*Wedding:*\n{ticket.get('wedding_name', 'Unknown')}"},
                            {"type": "mrkdwn", "text": f"*Message:*\n{ticket['message']}"},
                            {"type": "mrkdwn", "text": f"*Status:*\nNeeds Planner Assignment"}
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"⚠️ This wedding has no assigned planner. Please assign a planner to route future tickets correctly."
                            }
                        ]
                    }
                ]
            }

            requests.post(slack_webhook, json=message, timeout=5)
            logger.info(f"Slack notification sent to ROOT_ADMIN for unassigned ticket")

        # Also send email to ROOT_ADMIN
        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
        await _notify_planner_support_ticket(ticket, root_admin_email)

    except Exception as e:
        logger.error(f"Failed to send ROOT_ADMIN notification: {str(e)}")