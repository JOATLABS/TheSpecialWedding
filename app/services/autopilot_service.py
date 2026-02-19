"""
Autopilot Payment Service

Handles automatic payment processing, scheduling, retries, and notifications.
This is the core engine for the Wedding Finance Autopilot feature.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import logging
from bson import ObjectId
from app.core.database import mongo
from app.core.settings import settings

logger = logging.getLogger(__name__)


# Retry schedule: exponential backoff in days
RETRY_SCHEDULE = [1, 2, 4, 7]  # Days between retries
MAX_RETRY_ATTEMPTS = 4


class AutopilotService:
    """
    Service for automatic payment processing.

    Handles:
    - Payment schedule calculation
    - Due payment processing
    - Payment reminders
    - Failed payment retries with exponential backoff
    - Webhook handling for payment outcomes
    """

    def __init__(self):
        self.contracts = mongo.db["contracts"]
        self.scheduled_payments = mongo.db["scheduled_payments"]
        self.payment_logs = mongo.db["autopilot_payment_logs"]
        self.users = mongo.db["users"]

    # =========================================================================
    # PAYMENT SCHEDULE CALCULATOR (WFA-501)
    # =========================================================================

    def calculate_payment_schedule(
        self,
        payment_schedule: List[Dict],
        total_amount: Decimal,
        signing_date: datetime,
        wedding_date: Optional[date] = None
    ) -> List[Dict]:
        """
        Calculate concrete payment due dates from schedule configuration.

        Args:
            payment_schedule: List of schedule items from package
            total_amount: Total contract amount
            signing_date: When the contract was signed
            wedding_date: Wedding date (optional, needed for days_before_wedding)

        Returns:
            List of dicts with (name, amount, due_date, trigger)
        """
        calculated = []

        for item in payment_schedule:
            # Calculate amount
            if item.get("amount"):
                amount = Decimal(str(item["amount"]))
            elif item.get("percentage"):
                amount = total_amount * Decimal(str(item["percentage"])) / 100
            else:
                continue  # Skip if no amount specified

            # Calculate due date based on trigger
            trigger = item.get("trigger", "on_signing")
            due_date = self._calculate_due_date(
                trigger=trigger,
                signing_date=signing_date,
                wedding_date=wedding_date,
                days_after=item.get("days_after"),
                days_before=item.get("days_before"),
                fixed_date=item.get("fixed_date")
            )

            if due_date:
                calculated.append({
                    "name": item.get("name", "Payment"),
                    "amount": float(amount),
                    "due_date": due_date,
                    "trigger": trigger,
                    "percentage": item.get("percentage")
                })

        # Sort by due date
        calculated.sort(key=lambda x: x["due_date"])
        return calculated

    def _calculate_due_date(
        self,
        trigger: str,
        signing_date: datetime,
        wedding_date: Optional[date],
        days_after: Optional[int],
        days_before: Optional[int],
        fixed_date: Optional[str]
    ) -> Optional[date]:
        """Calculate payment due date based on trigger type."""

        if trigger == "on_signing":
            return signing_date.date() if isinstance(signing_date, datetime) else signing_date

        elif trigger == "days_after_signing" and days_after is not None:
            base = signing_date.date() if isinstance(signing_date, datetime) else signing_date
            return base + timedelta(days=days_after)

        elif trigger == "days_before_wedding" and days_before is not None:
            if wedding_date:
                if isinstance(wedding_date, str):
                    wedding_date = date.fromisoformat(wedding_date)
                return wedding_date - timedelta(days=days_before)
            else:
                # Fallback: 90 days from signing
                base = signing_date.date() if isinstance(signing_date, datetime) else signing_date
                return base + timedelta(days=90)

        elif trigger == "fixed_date" and fixed_date:
            if isinstance(fixed_date, str):
                return date.fromisoformat(fixed_date)
            return fixed_date

        return None

    # =========================================================================
    # DUE PAYMENT PROCESSING (WFA-502)
    # =========================================================================

    async def get_due_payments(self, as_of_date: Optional[date] = None) -> List[Dict]:
        """
        Find all scheduled payments that are due.

        Args:
            as_of_date: Date to check against (defaults to today)

        Returns:
            List of due payment records
        """
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc).date()

        # Convert to datetime for MongoDB query
        as_of_datetime = datetime.combine(as_of_date, datetime.max.time())

        query = {
            "status": "scheduled",
            "due_date": {"$lte": as_of_datetime}
        }

        cursor = self.scheduled_payments.find(query).sort("due_date", 1)
        payments = await cursor.to_list(length=100)

        return [self._serialize_payment(p) for p in payments]

    async def process_due_payments(self) -> Dict[str, Any]:
        """
        Process all due payments.

        Returns:
            Summary of processing results
        """
        import stripe
        stripe.api_key = settings.stripe_secret_key

        due_payments = await self.get_due_payments()

        results = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

        for payment in due_payments:
            try:
                result = await self._process_single_payment(payment)

                results["processed"] += 1
                if result.get("success"):
                    results["succeeded"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                results["errors"].append({
                    "payment_id": payment.get("id"),
                    "error": str(e)
                })
                logger.error(f"Error processing payment {payment.get('id')}: {str(e)}")

        logger.info(f"Payment processing complete: {results}")
        return results

    async def _process_single_payment(self, payment: Dict) -> Dict[str, Any]:
        """Process a single scheduled payment."""
        import stripe
        stripe.api_key = settings.stripe_secret_key

        payment_id = payment.get("id")
        contract_id = payment.get("contract_id")

        # Get contract for payment method
        contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
        if not contract:
            return {"success": False, "error": "Contract not found"}

        customer_id = contract.get("stripe_customer_id")
        payment_method_id = contract.get("stripe_payment_method_id")

        if not customer_id or not payment_method_id:
            return {"success": False, "error": "Missing payment credentials"}

        amount_cents = int(float(payment.get("amount", 0)) * 100)
        currency = payment.get("currency", "usd")

        if amount_cents <= 0:
            return {"success": False, "error": "Invalid amount"}

        # Check for planner's connect account
        planner_id = contract.get("planner_id")
        destination_account = None

        if planner_id:
            planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            if planner and planner.get("stripe_connect_id"):
                destination_account = planner.get("stripe_connect_id")

        try:
            # Update status to processing (atomic - only if still scheduled)
            # This prevents race conditions if another cron instance picks up the same payment
            update_result = await self.scheduled_payments.update_one(
                {
                    "_id": ObjectId(payment_id),
                    "status": "scheduled"  # Only process if still in scheduled state
                },
                {"$set": {"status": "processing", "updated_at": datetime.now(timezone.utc)}}
            )

            # Skip if another process already grabbed this payment
            if update_result.modified_count == 0:
                logger.info(f"Payment {payment_id} already being processed, skipping")
                return {"success": False, "error": "Payment already being processed"}

            # Create and confirm PaymentIntent
            # Use idempotency key to prevent double-charging on retries/duplicate requests
            attempt_count = payment.get("attempt_count", 0)
            idempotency_key = f"autopilot_{payment_id}_attempt_{attempt_count}"

            payment_intent_params = {
                "amount": amount_cents,
                "currency": currency,
                "customer": customer_id,
                "payment_method": payment_method_id,
                "confirm": True,
                "off_session": True,
                "description": f"Scheduled payment: {payment.get('name')}",
                "metadata": {
                    "contract_id": contract_id,
                    "scheduled_payment_id": payment_id,
                    "payment_type": "scheduled",
                    "attempt_count": str(attempt_count)
                },
                "idempotency_key": idempotency_key
            }

            if destination_account:
                payment_intent_params["transfer_data"] = {
                    "destination": destination_account
                }

            payment_intent = stripe.PaymentIntent.create(**payment_intent_params)

            if payment_intent.status == "succeeded":
                await self._mark_payment_succeeded(
                    payment_id=payment_id,
                    payment_intent_id=payment_intent.id,
                    receipt_url=payment_intent.charges.data[0].receipt_url if payment_intent.charges.data else None
                )
                return {"success": True, "payment_intent_id": payment_intent.id}

            else:
                # Payment requires action or is processing
                await self.scheduled_payments.update_one(
                    {"_id": ObjectId(payment_id)},
                    {
                        "$set": {
                            "status": "processing",
                            "stripe_payment_intent_id": payment_intent.id,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                return {"success": False, "status": payment_intent.status}

        except stripe.error.CardError as e:
            await self._handle_payment_failure(
                payment_id=payment_id,
                error_code=e.code,
                error_message=e.user_message
            )
            return {"success": False, "error": e.user_message}

        except Exception as e:
            await self._handle_payment_failure(
                payment_id=payment_id,
                error_code="unknown",
                error_message=str(e)
            )
            return {"success": False, "error": str(e)}

    async def _mark_payment_succeeded(
        self,
        payment_id: str,
        payment_intent_id: str,
        receipt_url: Optional[str] = None
    ):
        """Mark a payment as succeeded."""
        # Get payment first for budget sync
        payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

        await self.scheduled_payments.update_one(
            {"_id": ObjectId(payment_id)},
            {
                "$set": {
                    "status": "succeeded",
                    "paid_at": datetime.now(timezone.utc),
                    "stripe_payment_intent_id": payment_intent_id,
                    "receipt_url": receipt_url,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        # Log success
        await self._log_payment_event(
            payment_id=payment_id,
            event_type="payment_succeeded",
            details={"payment_intent_id": payment_intent_id}
        )

        logger.info(f"Payment {payment_id} succeeded: {payment_intent_id}")

        # Sync to budget module (WFA-901)
        if payment:
            await self._sync_payment_to_budget(payment)

    async def _sync_payment_to_budget(self, payment: Dict):
        """Sync a successful payment to the budget module."""
        try:
            contract_id = payment.get("contract_id")
            if not contract_id:
                return

            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                return

            wedding_id = contract.get("wedding_id")
            if not wedding_id:
                logger.info(f"Contract {contract_id} not linked to a wedding, skipping budget sync")
                return

            # Import budget service
            from app.services.budget_service import BudgetService
            budget_service = BudgetService()

            await budget_service.record_contract_payment(
                wedding_id=wedding_id,
                contract_id=contract_id,
                payment_name=payment.get("name", "Contract Payment"),
                amount=float(payment.get("amount", 0)),
                category_name="Wedding Planner",
                payment_method="card"
            )

            logger.info(f"Synced payment to budget for wedding {wedding_id}")

        except Exception as e:
            # Don't fail the payment if budget sync fails
            logger.error(f"Failed to sync payment to budget: {str(e)}")

    # =========================================================================
    # PAYMENT REMINDERS (WFA-503)
    # =========================================================================

    async def get_upcoming_payments(self, days_ahead: int = 3) -> List[Dict]:
        """
        Find payments due in the specified number of days.

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming payment records
        """
        target_date = datetime.now(timezone.utc).date() + timedelta(days=days_ahead)
        start = datetime.combine(target_date, datetime.min.time())
        end = datetime.combine(target_date, datetime.max.time())

        query = {
            "status": "scheduled",
            "due_date": {"$gte": start, "$lte": end},
            "reminder_sent_at": {"$exists": False}  # Haven't sent reminder yet
        }

        cursor = self.scheduled_payments.find(query)
        payments = await cursor.to_list(length=100)

        return [self._serialize_payment(p) for p in payments]

    async def send_payment_reminders(self, days_ahead: int = 3) -> Dict[str, Any]:
        """
        Send reminders for upcoming payments.

        Args:
            days_ahead: Days before due date to send reminder

        Returns:
            Summary of reminders sent
        """
        upcoming = await self.get_upcoming_payments(days_ahead)

        results = {
            "total_found": len(upcoming),
            "reminders_sent": 0,
            "errors": 0,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

        for payment in upcoming:
            try:
                success = await self._send_payment_reminder(payment)
                if success:
                    results["reminders_sent"] += 1
            except Exception as e:
                results["errors"] += 1
                logger.error(f"Failed to send reminder for payment {payment.get('id')}: {str(e)}")

        logger.info(f"Payment reminders complete: {results}")
        return results

    async def _send_payment_reminder(self, payment: Dict) -> bool:
        """Send a single payment reminder."""
        try:
            import resend
            resend.api_key = settings.resend_api_key

            contract_id = payment.get("contract_id")
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})

            if not contract:
                return False

            couple = contract.get("couple", {})
            couple_email = couple.get("email")

            if not couple_email:
                return False

            amount = payment.get("amount", 0)
            due_date = payment.get("due_date")
            if isinstance(due_date, str):
                due_date = datetime.fromisoformat(due_date)

            formatted_date = due_date.strftime("%B %d, %Y") if due_date else "soon"

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #6366f1;">Payment Reminder</h2>
                <p>Hi {couple.get('name', 'there')},</p>
                <p>This is a friendly reminder that your scheduled payment is coming up:</p>
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Payment:</strong> {payment.get('name', 'Scheduled Payment')}</p>
                    <p style="margin: 10px 0 0;"><strong>Amount:</strong> ${amount:,.2f}</p>
                    <p style="margin: 10px 0 0;"><strong>Due Date:</strong> {formatted_date}</p>
                </div>
                <p>Your payment will be automatically processed on the due date using your saved payment method.</p>
                <p>If you have any questions, please contact your wedding planner.</p>
                <p style="color: #64748b; font-size: 12px; margin-top: 30px;">
                    This is an automated reminder from The Special Wedding.
                </p>
            </body>
            </html>
            """

            resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [couple_email],
                "subject": f"Payment Reminder: ${amount:,.2f} due {formatted_date}",
                "html": html_content
            })

            # Mark reminder as sent
            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment.get("id"))},
                {"$set": {"reminder_sent_at": datetime.now(timezone.utc)}}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to send reminder: {str(e)}")
            return False

    # =========================================================================
    # RETRY LOGIC (WFA-504)
    # =========================================================================

    async def _handle_payment_failure(
        self,
        payment_id: str,
        error_code: str,
        error_message: str
    ):
        """Handle a failed payment with retry scheduling."""
        payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})
        if not payment:
            return

        attempt_count = payment.get("attempt_count", 0)
        new_attempt_count = attempt_count + 1

        # Calculate next retry date using exponential backoff (1, 2, 4, 7 days)
        if new_attempt_count <= MAX_RETRY_ATTEMPTS:
            retry_days = RETRY_SCHEDULE[min(attempt_count, len(RETRY_SCHEDULE) - 1)]
            next_retry = datetime.now(timezone.utc) + timedelta(days=retry_days)

            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "status": "failed",
                        "attempt_count": new_attempt_count,
                        "failure_reason": error_message,
                        "failure_code": error_code,
                        "next_retry_at": next_retry,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            logger.info(f"Payment {payment_id} failed (attempt {attempt_count}), retry scheduled for {next_retry}")
        else:
            # Max retries reached - mark as failed permanently
            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "status": "failed",
                        "attempt_count": new_attempt_count,
                        "failure_reason": error_message,
                        "failure_code": error_code,
                        "max_retries_reached": True,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            # Notify planner of manual intervention needed
            await self._notify_planner_of_failure(payment)

            logger.warning(f"Payment {payment_id} failed after {MAX_RETRY_ATTEMPTS} attempts")

        # Log failure
        await self._log_payment_event(
            payment_id=payment_id,
            event_type="payment_failed",
            details={
                "error_code": error_code,
                "error_message": error_message,
                "attempt_count": new_attempt_count
            }
        )

    async def get_payments_for_retry(self) -> List[Dict]:
        """Get failed payments that are due for retry."""
        now = datetime.now(timezone.utc)

        query = {
            "status": "failed",
            "next_retry_at": {"$lte": now},
            "max_retries_reached": {"$ne": True}
        }

        cursor = self.scheduled_payments.find(query)
        payments = await cursor.to_list(length=50)

        return [self._serialize_payment(p) for p in payments]

    async def retry_failed_payments(self) -> Dict[str, Any]:
        """Retry all payments that are due for retry."""
        payments_to_retry = await self.get_payments_for_retry()

        results = {
            "total_found": len(payments_to_retry),
            "retried": 0,
            "succeeded": 0,
            "failed": 0,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

        for payment in payments_to_retry:
            # Reset status to scheduled for retry (atomic - only if still failed)
            # This prevents race conditions if another cron instance is processing
            update_result = await self.scheduled_payments.update_one(
                {
                    "_id": ObjectId(payment.get("id")),
                    "status": "failed"  # Only update if still in failed state
                },
                {"$set": {"status": "scheduled", "updated_at": datetime.now(timezone.utc)}}
            )

            # Skip if another process already grabbed this payment
            if update_result.modified_count == 0:
                logger.info(f"Payment {payment.get('id')} already being processed, skipping")
                continue

            result = await self._process_single_payment(payment)
            results["retried"] += 1

            if result.get("success"):
                results["succeeded"] += 1
            else:
                results["failed"] += 1

        logger.info(f"Payment retry complete: {results}")
        return results

    async def _notify_planner_of_failure(self, payment: Dict):
        """Notify planner when payment fails after max retries."""
        try:
            import resend
            resend.api_key = settings.resend_api_key

            contract_id = payment.get("contract_id")
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})

            if not contract:
                return

            planner_id = contract.get("planner_id")
            if not planner_id:
                return

            planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            if not planner or not planner.get("email"):
                return

            couple = contract.get("couple", {})
            amount = payment.get("amount", 0)

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ef4444;">⚠️ Payment Requires Attention</h2>
                <p>A scheduled payment has failed after multiple retry attempts and requires manual intervention.</p>
                <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ef4444;">
                    <p style="margin: 0;"><strong>Couple:</strong> {couple.get('name', 'Unknown')}</p>
                    <p style="margin: 10px 0 0;"><strong>Payment:</strong> {payment.get('name', 'Scheduled Payment')}</p>
                    <p style="margin: 10px 0 0;"><strong>Amount:</strong> ${amount:,.2f}</p>
                    <p style="margin: 10px 0 0;"><strong>Failure Reason:</strong> {payment.get('failure_reason', 'Unknown')}</p>
                </div>
                <p>Please contact the couple to resolve the payment issue.</p>
                <a href="{settings.frontend_url}/admin/contracts" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin-top: 10px;">
                    View Contract
                </a>
            </body>
            </html>
            """

            resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [planner.get("email")],
                "subject": f"⚠️ Payment Failed - {couple.get('name', 'Unknown')}",
                "html": html_content
            })

        except Exception as e:
            logger.error(f"Failed to notify planner: {str(e)}")

    # =========================================================================
    # WEBHOOK HANDLERS (WFA-505, WFA-506)
    # =========================================================================

    async def handle_payment_succeeded(
        self,
        payment_intent_id: str,
        receipt_url: Optional[str] = None
    ) -> bool:
        """
        Handle payment_intent.succeeded webhook.

        Args:
            payment_intent_id: Stripe PaymentIntent ID
            receipt_url: URL to payment receipt

        Returns:
            True if handled successfully
        """
        try:
            # Find the scheduled payment
            payment = await self.scheduled_payments.find_one({
                "stripe_payment_intent_id": payment_intent_id
            })

            if not payment:
                # Try metadata lookup
                import stripe
                stripe.api_key = settings.stripe_secret_key

                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                scheduled_payment_id = pi.metadata.get("scheduled_payment_id")

                if scheduled_payment_id:
                    payment = await self.scheduled_payments.find_one({
                        "_id": ObjectId(scheduled_payment_id)
                    })

            if not payment:
                logger.warning(f"No scheduled payment found for PI: {payment_intent_id}")
                return False

            await self._mark_payment_succeeded(
                payment_id=str(payment["_id"]),
                payment_intent_id=payment_intent_id,
                receipt_url=receipt_url
            )

            # Send receipt email
            await self._send_payment_receipt(payment, receipt_url)

            return True

        except Exception as e:
            logger.error(f"Error handling payment succeeded: {str(e)}")
            return False

    async def handle_payment_failed(
        self,
        payment_intent_id: str,
        error_code: str,
        error_message: str
    ) -> bool:
        """
        Handle payment_intent.payment_failed webhook.

        Args:
            payment_intent_id: Stripe PaymentIntent ID
            error_code: Stripe error code
            error_message: Human-readable error message

        Returns:
            True if handled successfully
        """
        try:
            import stripe
            stripe.api_key = settings.stripe_secret_key

            # Find the scheduled payment
            payment = await self.scheduled_payments.find_one({
                "stripe_payment_intent_id": payment_intent_id
            })

            if not payment:
                pi = stripe.PaymentIntent.retrieve(payment_intent_id)
                scheduled_payment_id = pi.metadata.get("scheduled_payment_id")

                if scheduled_payment_id:
                    payment = await self.scheduled_payments.find_one({
                        "_id": ObjectId(scheduled_payment_id)
                    })

            if not payment:
                logger.warning(f"No scheduled payment found for failed PI: {payment_intent_id}")
                return False

            await self._handle_payment_failure(
                payment_id=str(payment["_id"]),
                error_code=error_code,
                error_message=error_message
            )

            # Send failure notification to couple
            await self._send_payment_failure_notification(payment, error_message)

            return True

        except Exception as e:
            logger.error(f"Error handling payment failed: {str(e)}")
            return False

    async def _send_payment_receipt(self, payment: Dict, receipt_url: Optional[str]):
        """Send payment receipt email."""
        try:
            import resend
            resend.api_key = settings.resend_api_key

            contract_id = payment.get("contract_id")
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})

            if not contract:
                return

            couple = contract.get("couple", {})
            couple_email = couple.get("email")

            if not couple_email:
                return

            amount = payment.get("amount", 0)

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #22c55e;">✓ Payment Received</h2>
                <p>Hi {couple.get('name', 'there')},</p>
                <p>Thank you! Your payment has been successfully processed.</p>
                <div style="background: #f0fdf4; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Payment:</strong> {payment.get('name', 'Scheduled Payment')}</p>
                    <p style="margin: 10px 0 0;"><strong>Amount:</strong> ${amount:,.2f}</p>
                    <p style="margin: 10px 0 0;"><strong>Date:</strong> {datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
                </div>
                {f'<a href="{receipt_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px;">View Receipt</a>' if receipt_url else ''}
            </body>
            </html>
            """

            resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [couple_email],
                "subject": f"✓ Payment Received - ${amount:,.2f}",
                "html": html_content
            })

        except Exception as e:
            logger.error(f"Failed to send receipt: {str(e)}")

    async def _send_payment_failure_notification(self, payment: Dict, error_message: str):
        """Send payment failure notification to couple."""
        try:
            import resend
            resend.api_key = settings.resend_api_key

            contract_id = payment.get("contract_id")
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})

            if not contract:
                return

            couple = contract.get("couple", {})
            couple_email = couple.get("email")

            if not couple_email:
                return

            amount = payment.get("amount", 0)

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #ef4444;">Payment Issue</h2>
                <p>Hi {couple.get('name', 'there')},</p>
                <p>We were unable to process your scheduled payment.</p>
                <div style="background: #fef2f2; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Payment:</strong> {payment.get('name', 'Scheduled Payment')}</p>
                    <p style="margin: 10px 0 0;"><strong>Amount:</strong> ${amount:,.2f}</p>
                    <p style="margin: 10px 0 0;"><strong>Reason:</strong> {error_message}</p>
                </div>
                <p>We'll automatically retry this payment. If the issue persists, please update your payment method or contact your wedding planner.</p>
            </body>
            </html>
            """

            resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [couple_email],
                "subject": "Payment Issue - Action Required",
                "html": html_content
            })

        except Exception as e:
            logger.error(f"Failed to send failure notification: {str(e)}")

    # =========================================================================
    # SCHEDULE RECALCULATION (WFA-507)
    # =========================================================================

    async def recalculate_payment_schedule(self, contract_id: str) -> Dict[str, Any]:
        """
        Recalculate payment due dates when wedding date changes.

        Args:
            contract_id: The contract ID to recalculate

        Returns:
            Summary of recalculated payments
        """
        try:
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                return {"success": False, "error": "Contract not found"}

            wedding_date = contract.get("wedding_date")
            if not wedding_date:
                return {"success": False, "error": "No wedding date set"}

            if isinstance(wedding_date, str):
                wedding_date = date.fromisoformat(wedding_date)
            elif isinstance(wedding_date, datetime):
                wedding_date = wedding_date.date()

            # Find all scheduled payments with days_before_wedding trigger
            query = {
                "contract_id": contract_id,
                "trigger": "days_before_wedding",
                "status": {"$in": ["scheduled", "pending"]}
            }

            cursor = self.scheduled_payments.find(query)
            payments = await cursor.to_list(length=100)

            updated_count = 0
            past_due_count = 0

            for payment in payments:
                days_before = payment.get("days_before")
                if days_before is None:
                    continue

                new_due_date = wedding_date - timedelta(days=days_before)

                # Check if new due date is in the past
                if new_due_date < datetime.now(timezone.utc).date():
                    past_due_count += 1
                    logger.warning(
                        f"Payment {payment['_id']} new due date {new_due_date} is in the past"
                    )

                # Update the payment
                await self.scheduled_payments.update_one(
                    {"_id": payment["_id"]},
                    {
                        "$set": {
                            "due_date": datetime.combine(new_due_date, datetime.min.time()),
                            "updated_at": datetime.now(timezone.utc),
                            "recalculated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                updated_count += 1

            results = {
                "success": True,
                "contract_id": contract_id,
                "wedding_date": str(wedding_date),
                "payments_updated": updated_count,
                "past_due_warnings": past_due_count
            }

            # If any payments are now past due, notify planner
            if past_due_count > 0:
                await self._notify_planner_of_schedule_change(contract, past_due_count)

            logger.info(f"Recalculated schedule for contract {contract_id}: {results}")
            return results

        except Exception as e:
            logger.error(f"Error recalculating schedule: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _notify_planner_of_schedule_change(self, contract: Dict, past_due_count: int):
        """Notify planner when schedule recalculation results in past-due payments."""
        try:
            import resend
            resend.api_key = settings.resend_api_key

            planner_id = contract.get("planner_id")
            if not planner_id:
                return

            planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            if not planner or not planner.get("email"):
                return

            couple = contract.get("couple", {})

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #f59e0b;">⚠️ Payment Schedule Updated</h2>
                <p>The wedding date for {couple.get('name', 'a client')} has been changed, and the payment schedule has been recalculated.</p>
                <div style="background: #fffbeb; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                    <p style="margin: 0;"><strong>Attention:</strong> {past_due_count} payment(s) now have due dates in the past.</p>
                    <p style="margin: 10px 0 0;">Please review the payment schedule and take appropriate action.</p>
                </div>
                <a href="{settings.frontend_url}/admin/contracts" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; margin-top: 10px;">
                    View Contract
                </a>
            </body>
            </html>
            """

            resend.Emails.send({
                "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
                "to": [planner.get("email")],
                "subject": f"⚠️ Payment Schedule Updated - {couple.get('name', 'Client')}",
                "html": html_content
            })

        except Exception as e:
            logger.error(f"Failed to notify planner of schedule change: {str(e)}")

    # =========================================================================
    # AI FEATURES (WFA-508, WFA-509)
    # =========================================================================

    async def get_optimal_retry_timing(self, payment: Dict) -> Dict[str, Any]:
        """
        Use AI to suggest optimal retry timing for a failed payment.

        Args:
            payment: The failed payment record

        Returns:
            AI suggestion with optimal retry timing
        """
        try:
            from app.services.ai_service import ai_service

            # Build context for AI
            contract_id = payment.get("contract_id")

            # Get payment history for this contract
            history = []
            if contract_id:
                cursor = self.scheduled_payments.find({
                    "contract_id": contract_id,
                    "status": {"$in": ["succeeded", "failed"]}
                }).sort("updated_at", -1).limit(10)
                history = await cursor.to_list(length=10)

            context = {
                "payment": {
                    "amount": payment.get("amount"),
                    "due_date": str(payment.get("due_date")),
                    "failure_code": payment.get("failure_code"),
                    "failure_reason": payment.get("failure_reason"),
                    "attempt_count": payment.get("attempt_count", 1),
                    "last_attempt": str(payment.get("updated_at"))
                },
                "history": [
                    {
                        "status": p.get("status"),
                        "amount": p.get("amount"),
                        "date": str(p.get("paid_at") or p.get("updated_at"))
                    }
                    for p in history
                ],
                "current_date": datetime.now(timezone.utc).isoformat()
            }

            # Call AI service (no credits - internal feature)
            result = await ai_service.generate(
                feature_name="payment_retry_timing",
                context=context,
                user_id="system",  # Internal system call
                skip_credit_check=True
            )

            return result

        except Exception as e:
            logger.error(f"Error getting AI retry timing: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "using_default_backoff"
            }

    async def predict_payment_success(self, payment: Dict) -> Dict[str, Any]:
        """
        Use AI to predict likelihood of payment success.

        Args:
            payment: The scheduled payment record

        Returns:
            AI prediction with success probability and risk factors
        """
        try:
            from app.services.ai_service import ai_service

            contract_id = payment.get("contract_id")
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)}) if contract_id else None

            # Get payment method age
            card_added = contract.get("card_added_at") if contract else None
            days_since_card_added = None
            if card_added:
                if isinstance(card_added, str):
                    card_added = datetime.fromisoformat(card_added)
                days_since_card_added = (datetime.now(timezone.utc) - card_added).days

            # Get payment history
            history = []
            if contract_id:
                cursor = self.scheduled_payments.find({
                    "contract_id": contract_id,
                    "status": {"$in": ["succeeded", "failed"]}
                }).sort("updated_at", -1).limit(10)
                history = await cursor.to_list(length=10)

            successful = len([p for p in history if p.get("status") == "succeeded"])
            failed = len([p for p in history if p.get("status") == "failed"])

            context = {
                "payment": {
                    "amount": payment.get("amount"),
                    "due_date": str(payment.get("due_date")),
                    "name": payment.get("name")
                },
                "card_info": {
                    "days_since_added": days_since_card_added,
                    "card_brand": contract.get("card_brand") if contract else None,
                    "card_last4": contract.get("card_last4") if contract else None
                },
                "history_summary": {
                    "successful_payments": successful,
                    "failed_payments": failed,
                    "success_rate": round(successful / max(successful + failed, 1) * 100, 1)
                },
                "current_date": datetime.now(timezone.utc).isoformat()
            }

            # Call AI service (no credits - internal feature)
            result = await ai_service.generate(
                feature_name="payment_success_prediction",
                context=context,
                user_id="system",
                skip_credit_check=True
            )

            return result

        except Exception as e:
            logger.error(f"Error predicting payment success: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "fallback": "assuming_medium_risk"
            }

    async def get_payment_risk_assessment(self, payment_id: str) -> Dict[str, Any]:
        """
        Get comprehensive risk assessment for a payment.

        Combines AI prediction with historical analysis.
        """
        try:
            payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})
            if not payment:
                return {"success": False, "error": "Payment not found"}

            prediction = await self.predict_payment_success(payment)

            # Add to payment record for dashboard display
            if prediction.get("success_probability"):
                await self.scheduled_payments.update_one(
                    {"_id": ObjectId(payment_id)},
                    {
                        "$set": {
                            "ai_risk_assessment": {
                                "probability": prediction.get("success_probability"),
                                "risk_level": prediction.get("risk_level"),
                                "assessed_at": datetime.now(timezone.utc)
                            }
                        }
                    }
                )

            return {
                "success": True,
                "payment_id": payment_id,
                "prediction": prediction
            }

        except Exception as e:
            logger.error(f"Error getting risk assessment: {str(e)}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def _log_payment_event(
        self,
        payment_id: str,
        event_type: str,
        details: Dict
    ):
        """Log a payment event for auditing."""
        try:
            await self.payment_logs.insert_one({
                "payment_id": payment_id,
                "event_type": event_type,
                "details": details,
                "created_at": datetime.now(timezone.utc)
            })
        except Exception as e:
            logger.error(f"Failed to log payment event: {str(e)}")

    def _serialize_payment(self, payment: Dict) -> Dict:
        """Serialize a payment record for API response."""
        if not payment:
            return {}

        serialized = {**payment}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            del serialized["_id"]

        if "amount" in serialized:
            serialized["amount"] = float(serialized["amount"])

        for date_field in ["due_date", "paid_at", "reminder_sent_at", "next_retry_at", "created_at", "updated_at"]:
            if date_field in serialized and serialized[date_field]:
                if hasattr(serialized[date_field], "isoformat"):
                    serialized[date_field] = serialized[date_field].isoformat()

        return serialized


# Singleton instance
autopilot_service = AutopilotService()
