# app/tasks/email_tasks.py

import os
import logging
from typing import Dict, Any, Optional
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from app.core.celery_app import celery_app
from app.services.email_service_resend import ResendEmailService
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailTask(Task):
    """Base task with email service initialization"""
    _email_service = None

    @property
    def email_service(self):
        if self._email_service is None:
            self._email_service = ResendEmailService()
        return self._email_service


@celery_app.task(
    base=EmailTask,
    bind=True,
    name="app.tasks.email_tasks.send_email_notification",
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    retry_backoff=True,
    retry_backoff_max=600,  # 10 minutes max
    retry_jitter=True
)
def send_email_notification(
    self,
    to_email: str,
    subject: str,
    html_content: str,
    notification_type: str = "general",
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    template_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send email notification with retry logic

    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content
        notification_type: Type of notification for tracking
        from_email: Sender email (optional, uses default if not provided)
        from_name: Sender name (optional)
        metadata: Additional metadata for logging

    Returns:
        Dict with success status and email ID
    """
    try:
        logger.info(f"Attempting to send {notification_type} email to {to_email}")

        # Send email using ResendEmailService
        result = self.email_service.send_email(
            to_email=to_email,
            subject=subject,
            html_content=html_content,
            from_email=from_email,
            from_name=from_name,
            email_type=notification_type,
            template_id=template_id
        )

        if result.get("success"):
            logger.info(f"Successfully sent {notification_type} email to {to_email}, ID: {result.get('id')}")
            return result
        else:
            # Email failed, retry
            error_msg = result.get("error", "Unknown error")
            logger.warning(f"Failed to send email to {to_email}: {error_msg}, retrying...")
            raise self.retry(exc=Exception(error_msg))

    except MaxRetriesExceededError:
        # Max retries exceeded, log as critical failure
        logger.error(f"Max retries exceeded for email to {to_email}, notification type: {notification_type}")

        # Log failure to database for manual review
        from app.core.database import mongo
        failure_log = {
            "to_email": to_email,
            "subject": subject,
            "notification_type": notification_type,
            "from_email": from_email,
            "from_name": from_name,
            "metadata": metadata,
            "status": "max_retries_exceeded",
            "retries": self.request.retries,
            "failed_at": datetime.utcnow()
        }
        mongo.db["email_failures"].insert_one(failure_log)

        return {
            "success": False,
            "error": "Max retries exceeded, logged for manual review",
            "failure_id": str(failure_log.get("_id"))
        }

    except Exception as e:
        # Unexpected error, retry with exponential backoff
        logger.error(f"Unexpected error sending email to {to_email}: {str(e)}")

        # Calculate exponential backoff
        countdown = min(60 * (2 ** self.request.retries), 600)  # Max 10 minutes

        raise self.retry(exc=e, countdown=countdown)


@celery_app.task(
    base=EmailTask,
    bind=True,
    name="app.tasks.email_tasks.send_admin_notification",
    max_retries=3,
    default_retry_delay=30
)
def send_admin_notification(
    self,
    subject: str,
    content: str,
    notification_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    include_link: bool = True
) -> Dict[str, Any]:
    """
    Send notification email to root admin using database templates

    Args:
        subject: Email subject (fallback if no template)
        content: Main content of the notification
        notification_type: Type of notification (contact_form, new_user, payment, etc.)
        metadata: Additional data to include in email
        include_link: Whether to include admin panel link

    Returns:
        Dict with success status
    """
    try:
        # Get root admin email from environment
        root_admin_email = os.getenv("ROOT_ADMIN_EMAIL", "thedeveloper@thespecialwedding.com")
        base_url = os.getenv("FRONTEND_URL", "https://www.thespecialwedding.com")

        # Try to get template from database
        from app.services.email_template_service import EmailTemplateService
        from app.models.email_template import TemplateType

        template_service = EmailTemplateService()

        # Map notification types to template types
        type_mapping = {
            "contact_form": TemplateType.CONTACT_FORM,
            "new_user": TemplateType.NEW_USER,
            "payment": TemplateType.PAYMENT,
            "system_alert": TemplateType.SYSTEM_ALERT,
            "general": TemplateType.GENERAL
        }

        template_type = type_mapping.get(notification_type, TemplateType.GENERAL)

        # Get template synchronously (Celery tasks can't be async)
        from app.core.database import mongo
        template_query = {"type": template_type.value, "status": "active"}
        template_doc = mongo.db["email_templates"].find_one({**template_query, "is_default": True})
        if not template_doc:
            template_doc = mongo.db["email_templates"].find_one(template_query)

        template = None
        if template_doc:
            template = {
                "id": str(template_doc["_id"]),
                "name": template_doc["name"],
                "subject": template_doc["subject"],
                "html_content": template_doc["html_content"]
            }

        if template:
            # Use database template
            template_data = metadata or {}
            template_data.update({
                "admin_link": f"{base_url}/admin",
                "content": content,
                "subject": subject
            })

            # Render template
            html_content = template_service._render_template(template["html_content"], template_data)
            final_subject = template_service._render_template(template["subject"], template_data)

            logger.info(f"Using database template for {notification_type}: {template['name']}")
        else:
            # Fallback to hardcoded templates
            logger.warning(f"No database template found for {notification_type}, using fallback")
            final_subject = subject

            if notification_type == "contact_form":
                html_content = _generate_contact_form_email(content, metadata or {}, base_url, include_link)
            elif notification_type == "new_user":
                html_content = _generate_new_user_email(content, metadata or {}, base_url, include_link)
            elif notification_type == "payment":
                html_content = _generate_payment_email(content, metadata or {}, base_url, include_link)
            elif notification_type == "system_alert":
                html_content = _generate_system_alert_email(content, metadata or {}, base_url, include_link)
            else:
                html_content = _generate_general_admin_email(subject, content, metadata or {}, base_url, include_link)

        # Send email with template tracking
        result = send_email_notification.apply_async(
            args=[
                root_admin_email,
                final_subject,
                html_content,
                f"admin_{notification_type}",
                os.getenv("RESEND_FROM_EMAIL", "noreply@thespecialwedding.com"),
                "TheSpecialWedding Platform"
            ],
            kwargs={
                "metadata": metadata,
                "template_id": template["id"] if template else None
            }
        )

        logger.info(f"Queued admin notification email for {notification_type}, task ID: {result.id}")
        return {"success": True, "task_id": result.id}

    except Exception as e:
        logger.error(f"Error queuing admin notification: {str(e)}")
        return {"success": False, "error": str(e)}


def _generate_contact_form_email(content: str, metadata: Dict, base_url: str, include_link: bool) -> str:
    """Generate HTML email for contact form submission"""
    name = metadata.get("name", "Unknown")
    email = metadata.get("email", "Unknown")
    company = metadata.get("company", "Not provided")
    phone = metadata.get("phone", "Not provided")
    message = metadata.get("message", content)
    submission_id = metadata.get("submission_id", "")

    admin_link = f"{base_url}/admin/notifications" if include_link else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
            .header p {{ margin: 5px 0 0; opacity: 0.9; font-size: 14px; }}
            .content {{ padding: 30px; }}
            .info-grid {{ background: #f9fafb; border-radius: 6px; padding: 20px; margin: 20px 0; }}
            .info-row {{ display: flex; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }}
            .info-row:last-child {{ border-bottom: none; }}
            .info-label {{ font-weight: 600; color: #6b7280; min-width: 120px; }}
            .info-value {{ color: #111827; flex: 1; }}
            .message-box {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 15px; margin: 20px 0; }}
            .message-box h3 {{ margin: 0 0 10px 0; color: #374151; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
            .button-container {{ text-align: center; margin: 30px 0; }}
            .button {{ display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 6px; font-weight: 500; }}
            .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 12px; background: #f9fafb; }}
            .badge {{ display: inline-block; padding: 4px 8px; background: #10b981; color: white; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔔 New Contact Form Submission</h1>
                <p>JOAT Labs - TheSpecialWedding Platform</p>
            </div>
            <div class="content">
                <p>Hello Admin,</p>
                <p>A new contact form has been submitted on the platform. Here are the details:</p>

                <div class="info-grid">
                    <div class="info-row">
                        <div class="info-label">Name:</div>
                        <div class="info-value"><strong>{name}</strong></div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Email:</div>
                        <div class="info-value"><a href="mailto:{email}" style="color: #667eea;">{email}</a></div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Company:</div>
                        <div class="info-value">{company}</div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Phone:</div>
                        <div class="info-value">{phone}</div>
                    </div>
                    {f'''<div class="info-row">
                        <div class="info-label">Submission ID:</div>
                        <div class="info-value"><code>{submission_id}</code></div>
                    </div>''' if submission_id else ''}
                </div>

                <div class="message-box">
                    <h3>Message</h3>
                    <p>{message}</p>
                </div>

                {f'''<div class="button-container">
                    <a href="{admin_link}" class="button">View in Admin Panel</a>
                </div>
                <p style="text-align: center; color: #6b7280; font-size: 13px;">
                    You'll need to log in to access the admin panel
                </p>''' if include_link else ''}

                <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">
                    <strong>Response Time:</strong> Please respond within 24 hours<br>
                    <span class="badge">Priority: High</span>
                </p>
            </div>
            <div class="footer">
                <p>© {datetime.now().year} JOAT Labs - TheSpecialWedding Platform</p>
                <p>This is an automated notification. Do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """


def _generate_new_user_email(content: str, metadata: Dict, base_url: str, include_link: bool) -> str:
    """Generate HTML email for new user registration"""
    user_email = metadata.get("email", "Unknown")
    company = metadata.get("company_name", "Not provided")
    plan = metadata.get("subscription_plan", "Free Trial")

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
            .info-box {{ background: #f9fafb; border-radius: 6px; padding: 20px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>👤 New User Registration</h1>
                <p>JOAT Labs - TheSpecialWedding Platform</p>
            </div>
            <div class="content">
                <p>A new wedding planner has registered on the platform:</p>
                <div class="info-box">
                    <p><strong>Email:</strong> {user_email}</p>
                    <p><strong>Company:</strong> {company}</p>
                    <p><strong>Plan:</strong> {plan}</p>
                </div>
                {f'<p><a href="{base_url}/admin/saas" style="color: #667eea;">View in Admin Panel</a></p>' if include_link else ''}
            </div>
        </div>
    </body>
    </html>
    """


def _generate_payment_email(content: str, metadata: Dict, base_url: str, include_link: bool) -> str:
    """Generate HTML email for payment events"""
    return _generate_general_admin_email("💳 Payment Event", content, metadata, base_url, include_link)


def _generate_system_alert_email(content: str, metadata: Dict, base_url: str, include_link: bool) -> str:
    """Generate HTML email for system alerts"""
    return _generate_general_admin_email("⚠️ System Alert", content, metadata, base_url, include_link)


def _generate_general_admin_email(subject: str, content: str, metadata: Dict, base_url: str, include_link: bool) -> str:
    """Generate generic admin notification email"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
            .content {{ padding: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{subject}</h1>
                <p>JOAT Labs - TheSpecialWedding Platform</p>
            </div>
            <div class="content">
                <p>{content}</p>
                {f'<p><a href="{base_url}/admin" style="color: #667eea;">Go to Admin Panel</a></p>' if include_link else ''}
            </div>
        </div>
    </body>
    </html>
    """