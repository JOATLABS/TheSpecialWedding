"""
Vendor Notification Service

Thin orchestration layer for advertising-platform notifications.
Does NOT duplicate in-portal or push — those are handled by
NotificationService.create_notification() which already:
  - Inserts the in-portal (bell icon) record
  - Fires SSE for real-time UI update
  - Fires WebPush to the targeted user or root admin

This service adds only:
  - Email delivery for vendor-facing events (via ResendEmailService)
  - Convenience methods that pair the correct NotificationService call
    with the correct email template in a single await

Phase 10+ — Notification Wiring.
"""

import asyncio
import logging

from app.core.settings import settings as app_settings

logger = logging.getLogger(__name__)

_PORTAL_URL = (
    f"{app_settings.frontend_url}/portal/ads"
    if app_settings.frontend_url
    else "https://thespecialwedding.io/portal/ads"
)


class VendorNotificationService:
    """
    Orchestrates notification delivery for the advertising platform.

    Each method calls:
      1. NotificationService.create_notification()  → in-portal + push + SSE
      2. ResendEmailService.send_email()             → email (where appropriate)
    """

    def __init__(self):
        self._notification_service = None
        self._email_service = None

    @property
    def notification_service(self):
        if self._notification_service is None:
            from app.services.notification_service import NotificationService

            self._notification_service = NotificationService()
        return self._notification_service

    @property
    def email_service(self):
        if self._email_service is None:
            from app.services.email_service_resend import ResendEmailService

            self._email_service = ResendEmailService()
        return self._email_service

    # ─── Helpers ────────────────────────────────────────────────────

    async def _create_notification(
        self,
        title: str,
        message: str,
        notification_type: str,
        target_audience: str,
        priority: str = "medium",
        user_id: str | None = None,
    ) -> None:
        """Delegate to NotificationService (handles in-portal + push + SSE)."""
        try:
            await self.notification_service.create_notification(
                notification_data={
                    "title": title,
                    "message": message,
                    "type": notification_type,
                    "target_audience": target_audience,
                    "user_id": user_id,
                    "is_dismissible": True,
                    "priority": priority,
                },
                created_by="system",
            )
        except Exception as e:
            logger.warning("NotificationService.create_notification failed: %s", e)

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        email_type: str = "vendor_notification",
    ) -> None:
        """Send email (non-blocking, never raises)."""
        try:
            await self.email_service.send_email(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
                from_name="The Special Wedding",
                email_type=email_type,
            )
        except Exception as e:
            logger.warning("Email send failed for %s: %s", to_email, e)

    # ─── Email Template ─────────────────────────────────────────────

    @staticmethod
    def _render_vendor_email(
        title: str,
        body_html: str,
        cta_url: str = "",
        cta_text: str = "",
    ) -> str:
        """Dark-theme email matching the vendor portal style."""
        cta_block = ""
        if cta_url and cta_text:
            cta_block = f"""
                    <div style="text-align: center; margin-top: 24px;">
                        <a href="{cta_url}" style="display: inline-block; padding: 12px 28px; background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #ffffff; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 600;">{cta_text}</a>
                    </div>"""

        return f"""<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0f172a;">
    <div style="max-width: 560px; margin: 40px auto; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; border: 1px solid #334155; overflow: hidden;">
        <div style="padding: 32px 24px; text-align: center; border-bottom: 1px solid #334155;">
            <h1 style="margin: 0; color: #f1f5f9; font-size: 22px;">The Special Wedding</h1>
            <p style="margin: 8px 0 0; color: #94a3b8; font-size: 13px;">Vendor Advertising Platform</p>
        </div>
        <div style="padding: 32px 24px;">
            <h2 style="color: #f1f5f9; font-size: 18px; margin: 0 0 16px;">{title}</h2>
            <div style="color: #cbd5e1; font-size: 14px; line-height: 1.6;">{body_html}</div>
            {cta_block}
        </div>
        <div style="padding: 16px 24px; border-top: 1px solid #334155; text-align: center;">
            <p style="color: #64748b; font-size: 11px; margin: 0;">
                &copy; The Special Wedding &mdash; Professional Wedding Planning Platform
            </p>
        </div>
    </div>
</body>
</html>"""

    # ═══════════════════════════════════════════════════════════════════
    # VENDOR-FACING EVENTS
    # ═══════════════════════════════════════════════════════════════════

    async def notify_vendor_campaign_approved(
        self,
        vendor_email: str,
        campaign_name: str,
    ) -> None:
        title = "Campaign Approved"
        message = f'Your campaign "{campaign_name}" has been approved and is now live!'

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="campaign_approved",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="high",
            ),
            self._send_email(
                to_email=vendor_email,
                subject=f"Campaign Approved — {campaign_name}",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f"<p>{message}</p><p>Your ads are now visible to wedding planners.</p>",
                    cta_url=f"{_PORTAL_URL}/campaigns",
                    cta_text="View Campaign",
                ),
                email_type="vendor_campaign_approved",
            ),
        )

    async def notify_vendor_campaign_rejected(
        self,
        vendor_email: str,
        campaign_name: str,
        reason: str | None = None,
    ) -> None:
        title = "Campaign Rejected"
        message = f'Your campaign "{campaign_name}" was not approved.'
        if reason:
            message += f" Reason: {reason}"
        reason_html = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="campaign_rejected",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="high",
            ),
            self._send_email(
                to_email=vendor_email,
                subject=f"Campaign Not Approved — {campaign_name}",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f'<p>Your campaign "{campaign_name}" was not approved.</p>{reason_html}<p>You can update and resubmit for review.</p>',
                    cta_url=f"{_PORTAL_URL}/campaigns",
                    cta_text="Edit Campaign",
                ),
                email_type="vendor_campaign_rejected",
            ),
        )

    async def notify_vendor_campaign_changes_requested(
        self,
        vendor_email: str,
        campaign_name: str,
        notes: str | None = None,
    ) -> None:
        title = "Changes Requested"
        message = f'Changes requested for your campaign "{campaign_name}".'
        if notes:
            message += f" Notes: {notes}"
        notes_html = f"<p><strong>Reviewer notes:</strong> {notes}</p>" if notes else ""

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="campaign_changes_requested",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="high",
            ),
            self._send_email(
                to_email=vendor_email,
                subject=f"Changes Requested — {campaign_name}",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f'<p>Your campaign "{campaign_name}" needs changes before going live.</p>{notes_html}',
                    cta_url=f"{_PORTAL_URL}/campaigns",
                    cta_text="Update Campaign",
                ),
                email_type="vendor_campaign_changes_requested",
            ),
        )

    async def notify_vendor_new_lead(
        self,
        vendor_email: str,
        planner_name: str,
        lead_type: str,
        campaign_name: str = "",
    ) -> None:
        if lead_type == "quote_request":
            title = "New Quote Request"
            msg = f"{planner_name} sent you a quote request"
        else:
            title = "Added to Directory"
            msg = f"{planner_name} added you to their vendor directory"
        if campaign_name:
            msg += f' via "{campaign_name}"'

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=msg,
                notification_type=f"lead_{lead_type}",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="medium",
            ),
            self._send_email(
                to_email=vendor_email,
                subject=f"{title} — The Special Wedding",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f"<p>{msg}.</p><p>Check your portal for details.</p>",
                    cta_url=f"{_PORTAL_URL}/analytics",
                    cta_text="View Leads",
                ),
                email_type=f"vendor_lead_{lead_type}",
            ),
        )

    async def notify_vendor_suspended(
        self,
        vendor_email: str,
        reason: str = "",
    ) -> None:
        title = "Account Suspended"
        message = "Your vendor account has been suspended."
        if reason:
            message += f" Reason: {reason}"
        reason_html = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="vendor_suspended",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="urgent",
            ),
            self._send_email(
                to_email=vendor_email,
                subject="Account Suspended — The Special Wedding",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f"<p>Your vendor advertising account has been suspended and your active campaigns have been paused.</p>{reason_html}<p>If you believe this is an error, please contact support.</p>",
                ),
                email_type="vendor_account_suspended",
            ),
        )

    async def notify_vendor_reactivated(self, vendor_email: str) -> None:
        title = "Account Reactivated"
        message = "Your vendor account has been reactivated. Your campaigns remain paused — resume them from your portal."

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="vendor_reactivated",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="high",
            ),
            self._send_email(
                to_email=vendor_email,
                subject="Account Reactivated — The Special Wedding",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html="<p>Your vendor advertising account has been reactivated.</p><p>Your campaigns remain paused — sign in to resume them.</p>",
                    cta_url=f"{_PORTAL_URL}/campaigns",
                    cta_text="Go to Portal",
                ),
                email_type="vendor_account_reactivated",
            ),
        )

    async def notify_vendor_budget_exhausted(
        self,
        vendor_email: str,
        campaign_name: str,
        budget_consumed: float,
        total_budget: float,
    ) -> None:
        title = "Campaign Budget Exhausted"
        message = f'Your campaign "{campaign_name}" has been auto-paused — budget ${budget_consumed:.2f} of ${total_budget:.2f} consumed.'

        await asyncio.gather(
            self._create_notification(
                title=title,
                message=message,
                notification_type="budget_exhausted",
                target_audience="advertising_vendors",
                user_id=vendor_email,
                priority="high",
            ),
            self._send_email(
                to_email=vendor_email,
                subject=f"Budget Exhausted — {campaign_name}",
                html_content=self._render_vendor_email(
                    title=title,
                    body_html=f'<p>Your campaign "{campaign_name}" reached its budget cap and was auto-paused.</p><p><strong>Budget:</strong> ${budget_consumed:.2f} / ${total_budget:.2f}</p><p>Increase your budget or create a new campaign to continue.</p>',
                    cta_url=f"{_PORTAL_URL}/campaigns",
                    cta_text="Manage Campaign",
                ),
                email_type="vendor_budget_exhausted",
            ),
        )

    # ═══════════════════════════════════════════════════════════════════
    # ADMIN-FACING EVENTS (ad platform)
    # ═══════════════════════════════════════════════════════════════════

    async def notify_admin_new_vendor_signup(
        self,
        business_name: str,
        vendor_email: str,
    ) -> None:
        """New vendor signup — in-portal + push already handled by
        vendor_signup_service._notify_admin_new_signup() via NotificationService.
        This is a no-op kept for backward compat with existing callers."""
        # NotificationService.create_notification with target_audience="root_admin"
        # already fires in-portal + push. Nothing extra needed here.

    async def notify_admin_campaign_submitted(
        self,
        vendor_name: str,
        campaign_name: str,
        campaign_id: str,
    ) -> None:
        """Campaign submitted for review → admin in-portal + push."""
        await self._create_notification(
            title="Campaign Pending Review",
            message=f'{vendor_name} submitted campaign "{campaign_name}" for review.',
            notification_type="campaign_submitted",
            target_audience="root_admin",
            priority="high",
        )

    async def notify_admin_fraud_detected(
        self,
        signal_type: str,
        planner_id: str,
        campaign_id: str,
    ) -> None:
        """Fraud detected → admin in-portal + push."""
        await self._create_notification(
            title="Fraud Alert",
            message=f"Fraud signal ({signal_type}) detected — planner={planner_id}, campaign={campaign_id}",
            notification_type="fraud_alert",
            target_audience="root_admin",
            priority="urgent",
        )
