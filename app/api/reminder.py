from fastapi import APIRouter, HTTPException, Depends, Request
from app.services.reminder_service import ReminderService
from app.dependencies.auth import require_admin
from app.core.database import mongo
from datetime import datetime
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
    Handle SMS webhooks for opt-outs (STOP messages)
    Works with both Telnyx and Twilio webhook formats
    """
    try:
        data = await request.json()
        guest_collection = mongo.get_guest_collection()
        
        # Handle Telnyx format
        if "data" in data and "event_type" in data.get("data", {}):
            event_type = data.get("data", {}).get("event_type", "")
            payload = data.get("data", {}).get("payload", {})
            
            if event_type == "message.received":
                from_number = payload.get("from", {}).get("phone_number", "")
                text = payload.get("text", "").strip().upper()
                
                if text in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                    # Update guest opt-out status
                    normalized_number = from_number.replace("+1", "").replace("+", "")
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
                                "sms_opt_out_date": datetime.utcnow()
                            }
                        }
                    )
                    logger.info(f"Opted out {result.modified_count} guests with phone {from_number}")
        
        # Handle Twilio format (for backward compatibility)
        elif "MessageStatus" in data or "Body" in data:
            from_number = data.get("From", "")
            body = data.get("Body", "").strip().upper()
            
            if body in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"]:
                normalized_number = from_number.replace("+1", "").replace("+", "")
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
                            "sms_opt_out_date": datetime.utcnow()
                        }
                    }
                )
                logger.info(f"Opted out {result.modified_count} guests with phone {from_number}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing SMS webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))