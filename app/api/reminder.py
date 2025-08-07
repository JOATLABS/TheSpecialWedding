from fastapi import APIRouter, HTTPException, Depends, Request
from app.services.reminder_service import ReminderService
from app.dependencies.auth import require_admin
from app.core.database import mongo
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

reminder_service = ReminderService()

@router.post("/reminders/send", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_reminder(event_type: str, message: str, target_group: str):
    return reminder_service.send_reminders(event_type, message, target_group)

@router.get("/reminders/logs", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_logs():
    return reminder_service.get_logs()

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
                guest = guest_collection.find_one({
                    "$or": [
                        {"phone": from_number},
                        {"phone": normalized_number},
                        {"phone": f"1{normalized_number}"}
                    ]
                })
                
                wedding_name = "the wedding"
                if guest and guest.get("wedding_id"):
                    wedding = wedding_collection.find_one({"_id": guest["wedding_id"]})
                    if wedding:
                        wedding_name = wedding.get("couple_names", "the wedding")
                
                # Handle STOP messages
                if text in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                    result = guest_collection.update_many(
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
                    result = guest_collection.update_many(
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
        
        # Handle Twilio format (for backward compatibility)
        elif "MessageStatus" in data or "Body" in data:
            from_number = data.get("From", "")
            to_number = data.get("To", "")
            body = data.get("Body", "").strip().upper()
            
            normalized_number = from_number.replace("+1", "").replace("+", "")
            
            # Find guest and their associated wedding
            guest = guest_collection.find_one({
                "$or": [
                    {"phone": from_number},
                    {"phone": normalized_number},
                    {"phone": f"1{normalized_number}"}
                ]
            })
            
            wedding_name = "the wedding"
            if guest and guest.get("wedding_id"):
                wedding = wedding_collection.find_one({"_id": guest["wedding_id"]})
                if wedding:
                    wedding_name = wedding.get("couple_names", "the wedding")
            
            if body in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                result = guest_collection.update_many(
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
                result = guest_collection.update_many(
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
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))