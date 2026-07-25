import logging
import os
from html import escape

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.services.email_service_resend import ResendEmailService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/saas", tags=["Sales"])

email_service = ResendEmailService()
notification_service = NotificationService()


class ContactSalesRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    company: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=50)
    message: str = Field(..., min_length=10, max_length=2000)


class ContactSalesResponse(BaseModel):
    message: str
    notification_id: str | None
    email_sent: bool


@router.post(
    "/contact", response_model=ContactSalesResponse, status_code=status.HTTP_201_CREATED
)
async def submit_contact_request(
    payload: ContactSalesRequest, background_tasks: BackgroundTasks
) -> ContactSalesResponse:
    """Capture a sales inquiry, notify the root admin, and queue an email."""

    root_admin_email = os.getenv(
        "ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.io"
    )
    if not root_admin_email:
        logger.error("ROOT_ADMIN_EMAIL is not configured; cannot route sales inquiry.")
        raise HTTPException(status_code=500, detail="Sales contact is not configured.")

    # Prepare notification body with escaped values to prevent HTML injection
    details = [
        f"Name: {escape(payload.name)}",
        f"Email: {escape(payload.email)}",
    ]

    if payload.company:
        details.append(f"Company: {escape(payload.company)}")

    if payload.phone:
        details.append(f"Phone: {escape(payload.phone)}")

    details.append(f"Message: {escape(payload.message)}")

    notification_message = "\n".join(details)

    notification_data = {
        "title": f"New sales inquiry from {payload.name}",
        "message": notification_message,
        "type": "sales_contact",
        "target_audience": "root_admin",
        "user_id": root_admin_email,
        "is_dismissible": True,
        "priority": "high",
    }

    notification_result = await notification_service.create_notification(
        notification_data, created_by="saas_contact_form"
    )

    email_sent = False
    if getattr(email_service, "configured", False):
        subject = f"Sales inquiry · {payload.name}"
        company_line = (
            f"<p><strong>Company:</strong> {escape(payload.company)} </p>"
            if payload.company
            else ""
        )
        phone_line = (
            f"<p><strong>Phone:</strong> {escape(payload.phone)} </p>"
            if payload.phone
            else ""
        )
        html_content = (
            "<div style=\"font-family: 'Inter', sans-serif; color:#0f172a; line-height:1.6;\">"
            f'<h2 style="margin:0 0 12px;">New sales inquiry from {escape(payload.name)}</h2>'
            f"<p><strong>Email:</strong> {escape(payload.email)}</p>"
            f"{company_line}"
            f"{phone_line}"
            f"<p><strong>Message</strong></p>"
            f'<p style="white-space:pre-line; background:#f8fafc; padding:12px; border-radius:12px; border:1px solid #e2e8f0;">{escape(payload.message)}</p>'
            '<p style="margin-top:20px; font-size:13px; color:#475569;">You can reply directly to this email to continue the conversation.</p>'
            "</div>"
        )

        background_tasks.add_task(
            email_service.send_email,
            to_email=root_admin_email,
            subject=subject,
            html_content=html_content,
            reply_to=payload.email,
            from_name=payload.name,
            email_type="sales_contact",
        )
        email_sent = True
    else:
        logger.warning(
            "Resend email service not configured; skipping sales inquiry email dispatch."
        )

    return ContactSalesResponse(
        message="Thanks! We received your request.",
        notification_id=(
            notification_result.get("id")
            if isinstance(notification_result, dict)
            else None
        ),
        email_sent=email_sent,
    )
