"""
Contract Email Service

Sends contract lifecycle emails using Resend.
"""
from typing import Dict, Any, Optional, List
from datetime import date, datetime
import logging
from bson import ObjectId
from app.core.settings import settings
from app.core.database import mongo
from app.utils.payment_schedule import build_effective_payment_schedule

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

    @staticmethod
    def _format_calendar_date(value: Any) -> str:
        if not value:
            return "TBD"

        if isinstance(value, datetime):
            return value.strftime("%B %d, %Y")

        if isinstance(value, date):
            return value.strftime("%B %d, %Y")

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return "TBD"
            try:
                return datetime.fromisoformat(normalized.replace("Z", "+00:00")).strftime("%B %d, %Y")
            except ValueError:
                try:
                    return date.fromisoformat(normalized).strftime("%B %d, %Y")
                except ValueError:
                    return normalized

        return str(value)

    @staticmethod
    def _resolve_couple_names(couple: Dict[str, Any]) -> tuple[str, Optional[str], str]:
        primary = (couple.get("partner1_name") or couple.get("name") or "").strip()
        secondary = (couple.get("partner2_name") or couple.get("partner_name") or "").strip() or None
        display = f"{primary} & {secondary}" if secondary else primary
        return primary, secondary, display

    @staticmethod
    def _format_currency(amount: float, currency: Optional[str] = "USD") -> str:
        normalized = (currency or "USD").upper()
        return f"${amount:,.2f} {normalized}"

    @staticmethod
    def _is_completed_payment(status: Optional[str]) -> bool:
        return status in {"succeeded", "paid_externally"}

    @staticmethod
    def _payment_status_label(status: Optional[str]) -> str:
        labels = {
            "scheduled": "Scheduled",
            "processing": "Processing",
            "succeeded": "Paid",
            "paid_externally": "Paid",
            "failed": "Failed",
            "cancelled": "Cancelled",
        }
        return labels.get(status or "", status or "Unknown")

    @staticmethod
    def _payment_id(payment: Dict[str, Any]) -> Optional[str]:
        value = payment.get("id") or payment.get("_id")
        return str(value) if value is not None else None

    async def _load_contract_payment_schedule(self, contract_id: str) -> List[Dict[str, Any]]:
        if not contract_id:
            return []

        payments = await mongo.db["scheduled_payments"].find(
            {"contract_id": contract_id}
        ).sort("due_date", 1).to_list(length=None)

        serialized: List[Dict[str, Any]] = []
        for payment in payments:
            amount = float(payment.get("amount", 0) or 0)
            serialized.append({
                "id": self._payment_id(payment),
                "name": payment.get("name") or "Scheduled Payment",
                "amount": amount,
                "currency": payment.get("currency", "usd"),
                "status": payment.get("status", "scheduled"),
                "due_date": payment.get("due_date"),
                "paid_at": payment.get("paid_at"),
                "receipt_url": payment.get("receipt_url"),
            })

        return serialized

    def _render_payment_schedule_rows(self, payments: List[Dict[str, Any]]) -> str:
        rows = ""
        for payment in payments:
            rows += f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{payment.get('name', 'Payment')}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{self._format_calendar_date(payment.get('due_date'))}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{self._payment_status_label(payment.get('status'))}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: right;">{self._format_currency(float(payment.get('amount', 0) or 0), payment.get('currency', 'usd'))}</td>
                </tr>
            """
        return rows

    async def send_contract_email(
        self,
        contract_id: str,
        token: str,
        vendor_email: str,
        vendor_name: str,
        contract_title: str,
        planner_message: Optional[str] = None,
    ) -> bool:
        """
        Send contract to vendor for review and signing.

        Args:
            contract_id: Contract ID
            token: Secure access token for the contract
            vendor_email: Vendor's email address
            vendor_name: Vendor's name
            contract_title: Contract title
            planner_message: Optional personal message from planner

        Returns:
            True if email sent successfully
        """
        try:
            resend = self._get_resend()

            from_domain = getattr(settings, "from_email_domain", "thespecialwedding.io")
            from_email = f"contracts@{from_domain}"

            contract_url = f"{getattr(settings, 'frontend_url', 'https://thespecialwedding.io')}/contracts/{token}"

            message_section = ""
            if planner_message:
                message_section = f"""
                <div style="background-color: #f8f9fa; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <p style="margin: 0; color: #495057; font-style: italic;">"{planner_message}"</p>
                </div>
                """

            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 32px; border-radius: 12px 12px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 24px;">Contract Ready for Review</h1>
                </div>
                <div style="padding: 32px; background: white; border: 1px solid #e9ecef; border-top: none; border-radius: 0 0 12px 12px;">
                    <p>Hi {vendor_name},</p>
                    <p>You have a new contract ready for your review:</p>
                    <p style="font-size: 18px; font-weight: 600; color: #333;">{contract_title}</p>
                    {message_section}
                    <div style="text-align: center; margin: 32px 0;">
                        <a href="{contract_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
                            View & Sign Contract
                        </a>
                    </div>
                    <p style="color: #6c757d; font-size: 14px;">If you have any questions, please reach out to your wedding planner directly.</p>
                </div>
            </div>
            """

            resend.Emails.send({
                "from": from_email,
                "to": [vendor_email],
                "subject": f"Contract Ready: {contract_title}",
                "html": html_content,
            })

            logger.info(f"Contract email sent to {vendor_email} for contract {contract_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send contract email to {vendor_email}: {str(e)}")
            raise

    async def send_package_contract_email(self, contract: Dict[str, Any]) -> bool:
        """
        Send a package contract invitation to the couple for review/signing.

        This uses the shared ResendEmailService so the send is recorded in
        email_logs for operational verification.
        """
        try:
            from app.services.email_service_resend import ResendEmailService

            couple = contract.get("couple", {}) or {}
            package = contract.get("package_snapshot", {}) or {}
            planner_id = contract.get("planner_id")
            wedding_id = contract.get("wedding_id")

            couple_email = couple.get("email")
            if not couple_email:
                logger.error("Package contract email skipped: couple email missing")
                return False

            planner = None
            if planner_id:
                planner = await mongo.db["users"].find_one({"_id": planner_id}) or await mongo.db["users"].find_one({"_id": str(planner_id)})

            wedding = None
            if wedding_id:
                wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})

            partner1 = couple.get("partner1_name", "").strip()
            partner2 = (couple.get("partner2_name") or "").strip()
            couple_display = f"{partner1} & {partner2}" if partner2 else partner1 or "there"

            planner_company = (
                (planner or {}).get("company_name")
                or (planner or {}).get("business_name")
                or (planner or {}).get("name")
                or settings.resend_from_name
            )
            planner_email = (planner or {}).get("email")
            wedding_date = self._format_calendar_date(contract.get("wedding_date") or (wedding or {}).get("date"))
            venue = (wedding or {}).get("venue") or contract.get("venue") or "TBD"

            total = float(package.get("total_amount", 0) or 0)
            currency = str(package.get("currency", "usd")).upper()
            contract_url = f"{settings.frontend_url or 'https://thespecialwedding.io'}/contracts/{contract.get('token', '')}"

            services_html = ""
            for service in package.get("services", []):
                if service.get("included"):
                    services_html += f"<li style=\"margin-bottom: 8px;\">{service.get('name', 'Service')}</li>"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; padding: 30px 0; border-bottom: 2px solid #6366f1;">
                    <h1 style="color: #6366f1; margin: 0 0 10px 0;">Your wedding planning proposal is ready</h1>
                    <p style="color: #64748b; margin: 0;">Review the package and sign online to get started</p>
                </div>

                <div style="padding: 30px 0;">
                    <p>Hi {couple_display},</p>
                    <p>{planner_company} shared a wedding planning package with you. You can review the details and sign your agreement online using the secure link below.</p>

                    <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #334155; margin: 0 0 15px 0; font-size: 16px;">Package Summary</h2>
                        <p style="margin: 0;"><strong>Package:</strong> {package.get('name', 'Wedding Package')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Investment:</strong> ${total:,.2f} {currency}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Wedding date:</strong> {wedding_date}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Venue:</strong> {venue}</p>
                    </div>

                    {f'''
                    <h3 style="color: #334155; margin: 25px 0 15px 0;">Included Services</h3>
                    <ul style="margin: 0; padding-left: 20px; color: #475569;">
                        {services_html}
                    </ul>
                    ''' if services_html else ''}

                    <div style="text-align: center; margin: 32px 0;">
                        <a href="{contract_url}" style="display: inline-block; background: #6366f1; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: 600;">
                            Review & Sign Contract
                        </a>
                    </div>

                    <p style="color: #64748b;">If you have questions before signing, reply to this email or contact {planner_company}{f' at {planner_email}' if planner_email else ''}.</p>
                    <p style="margin-top: 20px;">Warmly,<br>{planner_company}</p>
                </div>
            </body>
            </html>
            """

            email_service = ResendEmailService()
            result = await email_service.send_email(
                to_email=couple_email,
                subject=f"Review Your Wedding Planning Package - {package.get('name', 'Wedding Package')}",
                html_content=html_content,
                from_email=settings.resend_from_email,
                from_name=planner_company,
                wedding_id=str(wedding_id) if wedding_id else None,
                email_type="package_contract_invitation",
                wedding_slug=(wedding or {}).get("slug"),
            )
            if result.get("success"):
                logger.info(
                    "Package contract email sent to %s for contract %s",
                    couple_email,
                    contract.get("id") or contract.get("_id"),
                )
                return True

            logger.error(
                "Package contract email failed for %s: %s",
                couple_email,
                result.get("error", "unknown error"),
            )
            return False

        except Exception as e:
            logger.error(f"Failed to send package contract email: {str(e)}")
            return False

    async def send_contract_payment_receipt(
        self,
        contract: Dict[str, Any],
        payment: Dict[str, Any],
        receipt_url: Optional[str] = None,
    ) -> bool:
        """Send a payment receipt with remaining balance/schedule details to the couple."""
        try:
            from app.services.email_service_resend import ResendEmailService

            couple = contract.get("couple", {}) or {}
            couple_email = couple.get("email")
            if not couple_email:
                logger.error("Contract payment receipt skipped: couple email missing")
                return False

            contract_id = str(contract.get("_id") or contract.get("id") or "")
            schedule = await self._load_contract_payment_schedule(contract_id)
            current_payment_id = self._payment_id(payment)
            current_payment = next((item for item in schedule if item.get("id") == current_payment_id), None) or {
                "id": current_payment_id,
                "name": payment.get("name") or "Scheduled Payment",
                "amount": float(payment.get("amount", 0) or 0),
                "currency": payment.get("currency", "usd"),
                "status": payment.get("status", "succeeded"),
                "due_date": payment.get("due_date"),
                "paid_at": payment.get("paid_at"),
                "receipt_url": receipt_url or payment.get("receipt_url"),
            }

            total_amount = float(contract.get("package_snapshot", {}).get("total_amount", 0) or 0)
            if total_amount <= 0:
                total_amount = sum(float(item.get("amount", 0) or 0) for item in schedule)

            paid_amount = sum(
                float(item.get("amount", 0) or 0)
                for item in schedule
                if self._is_completed_payment(item.get("status"))
            )
            remaining_amount = max(total_amount - paid_amount, 0)
            remaining_payments = [
                item for item in schedule
                if item.get("status") not in {"succeeded", "paid_externally", "cancelled"}
            ]

            _, _, couple_display = self._resolve_couple_names(couple)
            couple_display = couple_display or "there"
            planner_name = contract.get("planner_name") or settings.resend_from_name
            planner_email = contract.get("planner_email")
            wedding_id = contract.get("wedding_id")
            wedding = None
            if wedding_id:
                wedding = await mongo.db["weddings"].find_one({"_id": wedding_id}) or await mongo.db["weddings"].find_one({"_id": str(wedding_id)})
            wedding_slug = (wedding or {}).get("slug")
            portal_url = f"{settings.frontend_url or 'https://thespecialwedding.io'}/portal/{contract.get('token', '')}"
            schedule_rows = self._render_payment_schedule_rows(remaining_payments)
            receipt_link = receipt_url or current_payment.get("receipt_url")

            paid_in_full_html = ""
            remaining_schedule_html = ""
            if remaining_payments:
                remaining_schedule_html = f"""
                    <h3 style="color: #334155; margin: 25px 0 15px 0;">Remaining Payment Schedule</h3>
                    <table style="width: 100%; border-collapse: collapse; background: #f8fafc; border-radius: 8px; overflow: hidden;">
                        <thead>
                            <tr style="background: #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-weight: 600;">Payment</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600;">Due</th>
                                <th style="padding: 12px; text-align: left; font-weight: 600;">Status</th>
                                <th style="padding: 12px; text-align: right; font-weight: 600;">Amount</th>
                            </tr>
                        </thead>
                        <tbody>
                            {schedule_rows}
                        </tbody>
                    </table>
                """
            else:
                paid_in_full_html = """
                    <div style="background: #ecfdf5; border: 1px solid #86efac; border-radius: 12px; padding: 20px; margin-top: 24px;">
                        <p style="margin: 0; color: #166534; font-weight: 600;">Your package is now paid in full.</p>
                    </div>
                """

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; padding: 30px 0; border-bottom: 2px solid #16a34a;">
                    <h1 style="color: #166534; margin: 0 0 10px 0;">Payment Received</h1>
                    <p style="color: #64748b; margin: 0;">Here&apos;s your updated payment summary</p>
                </div>

                <div style="padding: 30px 0;">
                    <p>Hi {couple_display},</p>
                    <p>We successfully processed <strong>{current_payment.get('name', 'your payment')}</strong> for your wedding planning package.</p>

                    <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #334155; margin: 0 0 15px 0; font-size: 16px;">Payment Receipt</h2>
                        <p style="margin: 0;"><strong>Package:</strong> {contract.get('package_snapshot', {}).get('name', 'Wedding Package')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Payment:</strong> {current_payment.get('name', 'Scheduled Payment')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Paid:</strong> {self._format_currency(float(current_payment.get('amount', 0) or 0), current_payment.get('currency', 'usd'))}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Processed on:</strong> {self._format_calendar_date(current_payment.get('paid_at') or datetime.now())}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Total paid to date:</strong> {self._format_currency(paid_amount, contract.get('package_snapshot', {}).get('currency', 'usd'))}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Remaining balance:</strong> {self._format_currency(remaining_amount, contract.get('package_snapshot', {}).get('currency', 'usd'))}</p>
                    </div>

                    {remaining_schedule_html}
                    {paid_in_full_html}

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{portal_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500; margin-right: 12px;">
                            View Payment Portal
                        </a>
                        {f'<a href="{receipt_link}" style="display: inline-block; background: #0f172a; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500;">View Stripe Receipt</a>' if receipt_link else ''}
                    </div>

                    <p style="color: #64748b;">Questions about your plan or payment schedule? Contact {planner_name}{f' at {planner_email}' if planner_email else ''}.</p>
                </div>
            </body>
            </html>
            """

            email_service = ResendEmailService()
            result = await email_service.send_email(
                to_email=couple_email,
                subject=f"Payment Received - {contract.get('package_snapshot', {}).get('name', 'Wedding Package')}",
                html_content=html_content,
                from_email=settings.resend_from_email,
                from_name=planner_name,
                wedding_id=str(wedding_id) if wedding_id else None,
                wedding_slug=wedding_slug,
                email_type="contract_payment_receipt",
            )

            if result.get("success"):
                logger.info("Contract payment receipt sent to %s for contract %s", couple_email, contract_id)
                return True

            logger.error("Contract payment receipt failed for %s: %s", couple_email, result.get("error", "unknown error"))
            return False
        except Exception as e:
            logger.error(f"Failed to send contract payment receipt: {str(e)}")
            return False

    async def send_planner_payment_notification(
        self,
        contract: Dict[str, Any],
        payment: Dict[str, Any],
    ) -> bool:
        """Send a payment-received notification email to the planner."""
        try:
            from app.services.email_service_resend import ResendEmailService

            planner_email = contract.get("planner_email")
            if not planner_email:
                logger.warning("Planner payment notification skipped: planner email missing")
                return False

            contract_id = str(contract.get("_id") or contract.get("id") or "")
            schedule = await self._load_contract_payment_schedule(contract_id)
            total_amount = float(contract.get("package_snapshot", {}).get("total_amount", 0) or 0)
            if total_amount <= 0:
                total_amount = sum(float(item.get("amount", 0) or 0) for item in schedule)

            paid_amount = sum(
                float(item.get("amount", 0) or 0)
                for item in schedule
                if self._is_completed_payment(item.get("status"))
            )
            remaining_amount = max(total_amount - paid_amount, 0)

            couple = contract.get("couple", {}) or {}
            _, _, couple_display = self._resolve_couple_names(couple)
            couple_display = couple_display or "Your couple"
            planner_name = contract.get("planner_name") or settings.resend_from_name
            payment_amount = float(payment.get("amount", 0) or 0)
            payment_currency = payment.get("currency", contract.get("package_snapshot", {}).get("currency", "usd"))
            wedding_id = contract.get("wedding_id")
            contract_url = f"{settings.frontend_url or 'https://thespecialwedding.io'}/admin/weddings/{wedding_id}" if wedding_id else f"{settings.frontend_url or 'https://thespecialwedding.io'}/admin/money"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1e293b; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; padding: 24px 0; border-bottom: 2px solid #16a34a;">
                    <h1 style="color: #166534; margin: 0 0 10px 0;">Contract Payment Received</h1>
                    <p style="color: #64748b; margin: 0;">A couple payment was processed successfully</p>
                </div>

                <div style="padding: 30px 0;">
                    <p>Hi {planner_name},</p>
                    <p>{couple_display} completed <strong>{payment.get('name', 'a scheduled payment')}</strong>.</p>

                    <div style="background: #f8fafc; border-radius: 12px; padding: 20px; margin: 20px 0;">
                        <h2 style="color: #334155; margin: 0 0 15px 0; font-size: 16px;">Payment Summary</h2>
                        <p style="margin: 0;"><strong>Package:</strong> {contract.get('package_snapshot', {}).get('name', 'Wedding Package')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Couple:</strong> {couple_display}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Payment:</strong> {payment.get('name', 'Scheduled Payment')}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Amount received:</strong> {self._format_currency(payment_amount, payment_currency)}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Total paid to date:</strong> {self._format_currency(paid_amount, payment_currency)}</p>
                        <p style="margin: 10px 0 0 0;"><strong>Remaining balance:</strong> {self._format_currency(remaining_amount, payment_currency)}</p>
                    </div>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{contract_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500;">
                            Open Planner Dashboard
                        </a>
                    </div>
                </div>
            </body>
            </html>
            """

            email_service = ResendEmailService()
            result = await email_service.send_email(
                to_email=planner_email,
                subject=f"Payment Received - {couple_display}",
                html_content=html_content,
                from_email=settings.resend_from_email,
                from_name=settings.resend_from_name,
                wedding_id=str(wedding_id) if wedding_id else None,
                email_type="planner_payment_received",
            )

            if result.get("success"):
                logger.info("Planner payment notification sent to %s for contract %s", planner_email, contract_id)
                return True

            logger.error("Planner payment notification failed for %s: %s", planner_email, result.get("error", "unknown error"))
            return False
        except Exception as e:
            logger.error(f"Failed to send planner payment notification: {str(e)}")
            return False

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

            # C12: Resolve recipient — vendor contracts use vendor_email, couple contracts use couple email
            couple_email = (
                contract.get("vendor_email")
                or couple.get("email")
                or contract.get("signer_email")
            )
            if not couple_email:
                logger.error("No recipient email found for contract confirmation")
                return False

            couple_name, partner_name, display_name = self._resolve_couple_names(couple)
            # For vendor contracts, use vendor_name if couple name is missing
            if not couple_name and contract.get("vendor_name"):
                greeting_name = contract.get("vendor_name", "")
            else:
                greeting_name = display_name

            # Format currency
            total = package.get("total_amount", 0)
            currency = package.get("currency", "usd").upper()

            # Format payment schedule
            schedule_rows = ""
            for i, payment in enumerate(build_effective_payment_schedule(package), 1):
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

            _, _, full_name = self._resolve_couple_names(couple)

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
                    <p style="margin: 10px 0 0 0;"><strong>Wedding Date:</strong> {self._format_calendar_date(contract.get('wedding_date'))}</p>
                </div>

                <p>{'The first payment has been processed successfully.' if contract.get('deposit_processed') else 'The contract is signed and the payment method is now saved for the upcoming schedule.'} Login to your dashboard to view the full contract details.</p>

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
