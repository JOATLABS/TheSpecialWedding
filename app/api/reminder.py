from fastapi import APIRouter, HTTPException, Depends
from app.services.reminder_service import ReminderService
from app.dependencies.auth import require_admin

router = APIRouter()

reminder_service = ReminderService()

@router.post("/reminders/send", tags=["Admin"], dependencies=[Depends(require_admin)])
def send_reminder(event_type: str, message: str, target_group: str):
    return reminder_service.send_reminders(event_type, message, target_group)

@router.get("/reminders/logs", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_logs():
    return reminder_service.get_logs()