# app/api/email_templates.py

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any
import logging

from app.models.email_template import (
    EmailTemplate, EmailTemplateCreate, EmailTemplateUpdate,
    EmailTemplatePreview, TemplateType, TemplateStatus
)
from app.services.email_template_service import EmailTemplateService
from app.dependencies.auth import require_admin, AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Email Templates"])

@router.get("/email-templates", summary="List email templates")
async def get_templates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    template_type: Optional[TemplateType] = None,
    status: Optional[TemplateStatus] = None,
    current_admin: AuthUser = Depends(require_admin)
):
    """Get list of email templates with pagination and filtering"""
    service = EmailTemplateService()
    return await service.get_templates(
        page=page,
        limit=limit,
        template_type=template_type,
        status=status
    )

@router.post("/email-templates", summary="Create email template")
async def create_template(
    template_data: EmailTemplateCreate,
    current_admin: AuthUser = Depends(require_admin)
):
    """Create a new email template"""
    service = EmailTemplateService()
    return await service.create_template(
        template_data,
        created_by=current_admin.email
    )

@router.get("/email-templates/{template_id}", summary="Get email template")
async def get_template(
    template_id: str,
    current_admin: AuthUser = Depends(require_admin)
):
    """Get specific email template by ID"""
    service = EmailTemplateService()
    return await service.get_template(template_id)

@router.put("/email-templates/{template_id}", summary="Update email template")
async def update_template(
    template_id: str,
    update_data: EmailTemplateUpdate,
    current_admin: AuthUser = Depends(require_admin)
):
    """Update an email template"""
    service = EmailTemplateService()
    return await service.update_template(
        template_id,
        update_data,
        updated_by=current_admin.email
    )

@router.delete("/email-templates/{template_id}", summary="Delete email template")
async def delete_template(
    template_id: str,
    current_admin: AuthUser = Depends(require_admin)
):
    """Archive an email template"""
    service = EmailTemplateService()
    return await service.delete_template(template_id)

@router.post("/email-templates/{template_id}/activate", summary="Activate email template")
async def activate_template(
    template_id: str,
    current_admin: AuthUser = Depends(require_admin)
):
    """Activate an email template"""
    service = EmailTemplateService()
    return await service.activate_template(
        template_id,
        activated_by=current_admin.email
    )

@router.post("/email-templates/{template_id}/preview", summary="Preview email template")
async def preview_template(
    template_id: str,
    preview_data: EmailTemplatePreview,
    current_admin: AuthUser = Depends(require_admin)
):
    """Preview email template with sample data"""
    service = EmailTemplateService()
    return await service.preview_template(
        template_id,
        preview_data.sample_data
    )

@router.get("/email-templates/{template_id}/versions", summary="Get template version history")
async def get_template_versions(
    template_id: str,
    current_admin: AuthUser = Depends(require_admin)
):
    """Get version history for a template"""
    service = EmailTemplateService()
    template = await service.get_template(template_id)
    return {
        "current_version": template.get("version", 1),
        "versions": template.get("version_history", [])
    }

@router.get("/email-templates/types/{template_type}/default", summary="Get default template for type")
async def get_default_template(
    template_type: TemplateType,
    current_admin: AuthUser = Depends(require_admin)
):
    """Get the default template for a specific type"""
    service = EmailTemplateService()
    template = await service.get_template_by_type(template_type)

    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"No active template found for type: {template_type.value}"
        )

    return template

@router.get("/email-templates/analytics/overview", summary="Get email analytics overview")
async def get_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    current_admin: AuthUser = Depends(require_admin)
):
    """Get email analytics overview for all templates"""
    service = EmailTemplateService()
    return await service.get_analytics(days=days)

@router.get("/email-templates/{template_id}/analytics", summary="Get template analytics")
async def get_template_analytics(
    template_id: str,
    days: int = Query(30, ge=1, le=365),
    current_admin: AuthUser = Depends(require_admin)
):
    """Get analytics for a specific template"""
    service = EmailTemplateService()
    return await service.get_analytics(template_id=template_id, days=days)

@router.post("/email-templates/bulk-action", summary="Perform bulk actions on templates")
async def bulk_template_action(
    action_data: Dict[str, Any],
    current_admin: AuthUser = Depends(require_admin)
):
    """Perform bulk actions on multiple templates"""
    try:
        action = action_data.get("action")
        template_ids = action_data.get("template_ids", [])

        if not action or not template_ids:
            raise HTTPException(
                status_code=400,
                detail="Action and template_ids are required"
            )

        service = EmailTemplateService()
        results = []

        for template_id in template_ids:
            try:
                if action == "activate":
                    result = await service.activate_template(
                        template_id,
                        activated_by=current_admin.email
                    )
                elif action == "archive":
                    result = await service.delete_template(template_id)
                elif action == "draft":
                    result = await service.update_template(
                        template_id,
                        EmailTemplateUpdate(status=TemplateStatus.DRAFT),
                        updated_by=current_admin.email
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid action: {action}"
                    )

                results.append({
                    "template_id": template_id,
                    "success": True,
                    "message": result.get("message", "Action completed")
                })

            except Exception as e:
                results.append({
                    "template_id": template_id,
                    "success": False,
                    "error": str(e)
                })

        success_count = sum(1 for r in results if r["success"])

        return {
            "action": action,
            "total_attempted": len(template_ids),
            "successful": success_count,
            "failed": len(template_ids) - success_count,
            "results": results
        }

    except Exception as e:
        logger.error(f"Error performing bulk template action: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error performing bulk action: {str(e)}"
        )

@router.post("/email-templates/seed-defaults", summary="Seed default templates")
async def seed_default_templates(
    current_admin: AuthUser = Depends(require_admin)
):
    """Seed the database with default email templates"""
    try:
        service = EmailTemplateService()
        created_templates = []

        # Default contact form template
        contact_template = EmailTemplateCreate(
            name="Default Contact Form Notification",
            type=TemplateType.CONTACT_FORM,
            subject="🔔 New Contact Form Submission from {name}",
            html_content="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5; }
                    .container { max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                    .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
                    .header h1 { margin: 0; font-size: 24px; font-weight: 600; }
                    .content { padding: 30px; }
                    .info-grid { background: #f9fafb; border-radius: 6px; padding: 20px; margin: 20px 0; }
                    .info-row { display: flex; padding: 10px 0; border-bottom: 1px solid #e5e7eb; }
                    .info-row:last-child { border-bottom: none; }
                    .info-label { font-weight: 600; color: #6b7280; min-width: 120px; }
                    .info-value { color: #111827; flex: 1; }
                    .message-box { background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 15px; margin: 20px 0; }
                    .footer { text-align: center; padding: 20px; color: #6b7280; font-size: 12px; background: #f9fafb; }
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
                        <p>A new contact form has been submitted on the platform:</p>

                        <div class="info-grid">
                            <div class="info-row">
                                <div class="info-label">Name:</div>
                                <div class="info-value"><strong>{name}</strong></div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Email:</div>
                                <div class="info-value"><a href="mailto:{email}">{email}</a></div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Company:</div>
                                <div class="info-value">{company}</div>
                            </div>
                            <div class="info-row">
                                <div class="info-label">Phone:</div>
                                <div class="info-value">{phone}</div>
                            </div>
                        </div>

                        <div class="message-box">
                            <h3>Message</h3>
                            <p>{message}</p>
                        </div>

                        <p><a href="{admin_link}" style="color: #667eea;">View in Admin Panel</a></p>
                    </div>
                    <div class="footer">
                        <p>© JOAT Labs - TheSpecialWedding Platform</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            variables=["name", "email", "company", "phone", "message", "admin_link"],
            is_default=True
        )

        result = await service.create_template(
            contact_template,
            created_by=current_admin.email
        )
        created_templates.append({"type": "contact_form", "id": result["id"]})

        # Default new user template
        user_template = EmailTemplateCreate(
            name="Default New User Notification",
            type=TemplateType.NEW_USER,
            subject="👤 New User Registration - {email}",
            html_content="""
            <!DOCTYPE html>
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center;">
                        <h1 style="margin: 0;">👤 New User Registration</h1>
                        <p style="margin: 5px 0 0;">JOAT Labs - TheSpecialWedding Platform</p>
                    </div>
                    <div style="padding: 30px;">
                        <p>A new wedding planner has registered on the platform:</p>
                        <div style="background: #f9fafb; border-radius: 6px; padding: 20px; margin: 20px 0;">
                            <p><strong>Email:</strong> {email}</p>
                            <p><strong>Company:</strong> {company}</p>
                            <p><strong>Plan:</strong> {plan}</p>
                        </div>
                        <p><a href="{admin_link}" style="color: #667eea;">View in Admin Panel</a></p>
                    </div>
                    <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px; background: #f9fafb;">
                        <p>© JOAT Labs - TheSpecialWedding Platform</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            variables=["email", "company", "plan", "admin_link"],
            is_default=True
        )

        result = await service.create_template(
            user_template,
            created_by=current_admin.email
        )
        created_templates.append({"type": "new_user", "id": result["id"]})

        # Default system alert template
        alert_template = EmailTemplateCreate(
            name="Default System Alert",
            type=TemplateType.SYSTEM_ALERT,
            subject="⚠️ System Alert: {alert_type}",
            html_content="""
            <!DOCTYPE html>
            <html>
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 40px auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: white; padding: 30px; text-align: center;">
                        <h1 style="margin: 0;">⚠️ System Alert</h1>
                        <p style="margin: 5px 0 0;">JOAT Labs - TheSpecialWedding Platform</p>
                    </div>
                    <div style="padding: 30px;">
                        <h2 style="color: #ef4444;">{alert_type}</h2>
                        <p>{message}</p>
                        <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 15px; margin: 20px 0;">
                            <p><strong>Timestamp:</strong> {timestamp}</p>
                            <p><strong>Severity:</strong> {severity}</p>
                        </div>
                        <p><a href="{admin_link}" style="color: #ef4444;">Go to Admin Panel</a></p>
                    </div>
                    <div style="text-align: center; padding: 20px; color: #6b7280; font-size: 12px; background: #f9fafb;">
                        <p>© JOAT Labs - TheSpecialWedding Platform</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            variables=["alert_type", "message", "timestamp", "severity", "admin_link"],
            is_default=True
        )

        result = await service.create_template(
            alert_template,
            created_by=current_admin.email
        )
        created_templates.append({"type": "system_alert", "id": result["id"]})

        logger.info(f"Seeded {len(created_templates)} default email templates")

        return {
            "message": f"Successfully created {len(created_templates)} default templates",
            "templates": created_templates
        }

    except Exception as e:
        logger.error(f"Error seeding default templates: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error seeding templates: {str(e)}"
        )