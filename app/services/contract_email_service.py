"""
Contract Email Service

Sends confirmation emails when contracts are signed.
Uses Resend for email delivery.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from app.core.settings import settings
from app.core.database import mongo

logger = logging.getLogger(__name__)


class ContractEmailService:
    """
    Service for sending contract-related emails.

    Handles:
    - Signed contract confirmation to couple
    - Notification to planner
    - Payment reminders
    """

    def __init__(self):
        self.contracts = mongo.db["contracts"]
        self._resend = None

    def _get_resend(self):
        """Get or create Resend client."""
        if self._resend is None:
            try:
                import resend
                resend.api_key = settings.resend_api_key
                self._resend = resend
            except Exception as e:
                logger.error(f"Failed to initialize Resend: {str(e)}")
                raise
        return self._resend

    async def send_signed_confirmation(
        self,
        contract: Dict,
        pdf_url: Optional[str] = None
    ) -> bool:
        """
        Send confirmation email to couple after signing.

        Args:
            contract: The signed contract data
            pdf_url: Optional URL to the signed PDF

        Returns:
            True if email sent successfully
        """
        try:
            resend = self._get_resend()

            couple = contract.get("couple", {})
            package = contract.get("package_snapshot", {})
            signature = contract.get("signature", {})

            couple_email = couple.get("email")
            if not couple_email:
                logger.error("No couple email found for contract")
                return False

            couple_name = couple.get("name", "")
            partner_name = couple.get("partner_name")
            greeting_name = f"{couple_name} & {partner_name}" if partner_name else couple_name

            # Format currency
            total = package.get("total_amount", 0)
            currency = package.get("currency", "usd").upper()

            # Format payment schedule
            schedule_rows = ""
            for i, payment in enumerate(package.get("payment_schedule", []), 1):
                amount = payment.get("amount") or (total * payment.get("percentage", 0) / 100)
                trigger = payment.get("trigger", "")
                trigger_label = {
                    "on_signing": "Due on signing",
                    "days_after_signing": f"{payment.get('days_after', 0)} days after signing",
                    "days_before_wedding": f"{payment.get('days_before', 0)} days before wedding",
                    "fixed_date": "Fixed date"
                }.get(trigger, trigger)

                schedule_rows += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{payment.get('name', f'Payment {i}')}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{trigger_label}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">${amount:,.2f}</td>
                </tr>
                """

            # Build services list
            services_list = ""
            for service in package.get("services", []):
                if service.get("included"):
                    services_list += f'<li style="margin-bottom: 8px;">✓ {service.get("name", "Service")}</li>'

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; padding: 30px 0; border-bottom: 2px solid #6366f1;">
                    <h1 style="color: #6366f1; margin: 0 0 10px 0;">Contract Signed! 🎉</h1>
                    <p style="color: #64748b; margin: 0;">Your wedding planning journey begins</p>
                </div>

                <div style="padding: 30px 0;">
                    <p>Dear {greeting_name},</p>

                    <p>Thank you for signing your wedding planning agreement! We're thrilled to be part of your special journey.</p>

                    <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #334155; margin: 0 0 15px 0; font-size: 16px;">Agreement Summary</h2>
                        <p style="margin: 0;"><strong>Package:</strong> {package.get('name', 'Wedding Package')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Total Investment:</strong> ${total:,.2f} {currency}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Signed by:</strong> {signature.get('signed_by', 'N/A')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Signed on:</strong> {contract.get('signed_at', 'N/A')}</p>
                    </div>

                    {f'''
                    <h3 style="color: #334155; margin: 25px 0 15px 0;">Services Included</h3>
                    <ul style="margin: 0; padding-left: 0; list-style: none;">
                        {services_list}
                    </ul>
                    ''' if services_list else ''}

                    <h3 style="color: #334155; margin: 25px 0 15px 0;">Payment Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: #f8fafc; border-radius: 8px; overflow: hidden;">
                        <thead>
                            <tr style="background: #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-weight: 600;">Payment</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600;">Due</th>
                                <th style="padding: 12px; text-align: right; font-weight: 600;">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_rows}
                        </tbody>
                    </table>

                    {f'''
                    <div style="margin: 30px 0; text-align: center;">
                        <a href="{pdf_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500;">
                            Download Signed Contract (PDF)
                        </a>
                    </div>
                    ''' if pdf_url else ''}

                    <h3 style="color: #334155; margin: 25px 0 15px 0;">What Happens Next?</h3>
                    <ol style="margin: 0; padding-left: 20px; color: #64748b;">
                        <li style="margin-bottom: 10px;">Your payment method has been securely saved for scheduled payments</li>
                        <li style="margin-bottom: 10px;">You'll receive reminders before each payment is processed</li>
                        <li style="margin-bottom: 10px;">Your wedding planner will be in touch to begin planning!</li>
                    </ol>

                    <p style="margin-top: 30px;">If you have any questions, please don't hesitate to reach out.</p>

                    <p style="margin-top: 20px;">With love,<br>The Special Wedding Team</p>
                </div>

                <div style="border-top: 1px solid #e2e8f0; padding-top: 20px; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>Contract ID: {contract.get('id', 'N/A')}</p>
                    <p>This email confirms your digitally signed agreement.</p>
                </div>
            </body>
            </html>
            """

            # Send email
            response = resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [couple_email],
                "subject": f"🎉 Contract Signed - {package.get('name', 'Wedding Package')}",
                "html": html_content
            })

            logger.info(f"Sent confirmation email to {couple_email}: {response}")
            return True

        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")
            return False

    async def send_planner_notification(
        self,
        contract: Dict,
        planner_email: str
    ) -> bool:
        """
        Send notification to planner when contract is signed.

        Args:
            contract: The signed contract data
            planner_email: The planner's email address

        Returns:
            True if email sent successfully
        """
        try:
            resend = self._get_resend()

            couple = contract.get("couple", {})
            package = contract.get("package_snapshot", {})

            couple_name = couple.get("name", "")
            partner_name = couple.get("partner_name")
            full_name = f"{couple_name} & {partner_name}" if partner_name else couple_name

            total = package.get("total_amount", 0)

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; padding: 20px; background: #f0fdf4; border-radius: 12px; margin-bottom: 20px;">
                    <h1 style="color: #166534; margin: 0;">New Contract Signed! 🎉</h1>
                </div>

                <p>Great news! A new contract has been signed.</p>

                <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                    <h3 style="color: #334155; margin: 0 0 15px 0;">Contract Details</h3>
                    <p style="margin: 0;"><strong>Couple:</strong> {full_name}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Email:</strong> {couple.get('email', 'N/A')}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Package:</strong> {package.get('name', 'Wedding Package')}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Total:</strong> ${total:,.2f}</p>
                    <p style="margin: 10px 0 0 0;"><strong>Wedding Date:</strong> {contract.get('wedding_date', 'TBD')}</p>
                </div>

                <p>The first payment (deposit) has been processed. Login to your dashboard to view the full contract details.</p>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{settings.frontend_url}/admin/contracts" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500;">
                        View Contract
                    </a>
                </div>
            </body>
            </html>
            """

            response = resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [planner_email],
                "subject": f"🎉 New Contract Signed - {full_name}",
                "html": html_content
            })

            logger.info(f"Sent planner notification to {planner_email}: {response}")
            return True

        except Exception as e:
            logger.error(f"Failed to send planner notification: {str(e)}")
            return False


# Singleton instance
contract_email_service = ContractEmailService()
