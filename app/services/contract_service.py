"""
Contract Service

Manages contract lifecycle from creation to completion.
Handles signing, payment method capture, and status transitions.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import logging
from bson import ObjectId
from app.core.database import mongo
from app.models.autopilot import Contract, ContractSignature, ScheduledPayment

logger = logging.getLogger(__name__)


class ContractService:
    """
    Service for managing contract lifecycle.

    Contracts track the signing process, payment method,
    and scheduled payments between planners and couples.
    """

    def __init__(self):
        self.contracts = mongo.db["contracts"]
        self.scheduled_payments = mongo.db["scheduled_payments"]
        self.packages = mongo.db["packages"]

    async def get_contract(
        self,
        contract_id: str,
        planner_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get a contract by ID.

        Args:
            contract_id: The contract ID
            planner_id: Optional planner ID to verify ownership

        Returns:
            Contract dict or None
        """
        try:
            query: Dict[str, Any] = {"_id": ObjectId(contract_id)}
            if planner_id:
                query["planner_id"] = planner_id

            contract = await self.contracts.find_one(query)
            return self._serialize_contract(contract) if contract else None

        except Exception as e:
            logger.error(f"Failed to get contract: {str(e)}")
            raise

    async def get_contract_by_token(self, token: str) -> Optional[Dict]:
        """
        Get a contract by public token.
        Used for public contract viewing/signing.

        Args:
            token: The contract access token

        Returns:
            Contract dict or None
        """
        try:
            contract = await self.contracts.find_one({"token": token})
            return self._serialize_contract(contract) if contract else None

        except Exception as e:
            logger.error(f"Failed to get contract by token: {str(e)}")
            raise

    async def list_contracts(
        self,
        planner_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict]:
        """
        List contracts for a planner.

        Args:
            planner_id: The planner's user ID
            status: Filter by status
            limit: Maximum contracts to return
            skip: Number to skip

        Returns:
            List of contract dicts
        """
        try:
            query = {"planner_id": planner_id}
            if status:
                query["status"] = status

            cursor = self.contracts.find(query).sort("updated_at", -1).skip(skip).limit(limit)
            contracts = await cursor.to_list(length=limit)

            serialized_contracts: List[Dict] = []
            for c in contracts:
                serialized = self._serialize_contract(c)
                if serialized is not None:
                    serialized_contracts.append(serialized)

            return serialized_contracts

        except Exception as e:
            logger.error(f"Failed to list contracts: {str(e)}")
            raise

    async def mark_viewed(self, token: str, ip_address: str) -> Dict:
        """
        Mark a contract as viewed by the couple.

        Args:
            token: Contract access token
            ip_address: Viewer's IP address

        Returns:
            Updated contract dict
        """
        try:
            contract = await self.contracts.find_one({"token": token})

            if not contract:
                raise ValueError("Contract not found")

            # Only mark as viewed if it's in 'sent' status
            if contract.get("status") == "sent":
                await self.contracts.update_one(
                    {"token": token},
                    {
                        "$set": {
                            "status": "viewed",
                            "viewed_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                logger.info(f"Contract {contract['_id']} marked as viewed")

            updated = await self.contracts.find_one({"token": token})
            serialized = self._serialize_contract(updated)
            if serialized is None:
                raise ValueError("Failed to serialize updated contract")
            return serialized

        except Exception as e:
            logger.error(f"Failed to mark contract as viewed: {str(e)}")
            raise

    async def sign_contract(
        self,
        token: str,
        signature_name: str,
        ip_address: str,
        user_agent: str,
        stripe_customer_id: str,
        stripe_payment_method_id: str,
        payment_method_last4: Optional[str] = None,
        payment_method_brand: Optional[str] = None
    ) -> Dict:
        """
        Sign a contract and capture payment method.

        Args:
            token: Contract access token
            signature_name: Name typed as signature
            ip_address: Signer's IP address
            user_agent: Signer's browser user agent
            stripe_customer_id: Stripe customer ID
            stripe_payment_method_id: Stripe payment method ID
            payment_method_last4: Last 4 digits of card
            payment_method_brand: Card brand (visa, mastercard, etc.)

        Returns:
            Updated contract with scheduled payments
        """
        try:
            contract = await self.contracts.find_one({"token": token})

            if not contract:
                raise ValueError("Contract not found")

            if contract.get("status") in ["signed", "active", "completed", "cancelled"]:
                raise ValueError(f"Contract already in status: {contract['status']}")

            # Create signature
            signature = ContractSignature(
                signed_by=signature_name,
                signed_at=datetime.now(timezone.utc),
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else ""
            )

            # Update contract
            await self.contracts.update_one(
                {"token": token},
                {
                    "$set": {
                        "status": "signed",
                        "signature": signature.model_dump(),
                        "signed_at": datetime.now(timezone.utc),
                        "stripe_customer_id": stripe_customer_id,
                        "stripe_payment_method_id": stripe_payment_method_id,
                        "payment_method_last4": payment_method_last4,
                        "payment_method_brand": payment_method_brand,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            logger.info(f"Contract {contract['_id']} signed by {signature_name}")

            # Create scheduled payments
            await self._create_scheduled_payments(contract)

            # Process first payment (deposit) if due on signing
            deposit_result = await self._process_deposit_payment(
                contract_id=str(contract["_id"]),
                customer_id=stripe_customer_id,
                payment_method_id=stripe_payment_method_id
            )

            # Generate PDF snapshot (async, don't block signing)
            try:
                from app.services.contract_pdf_service import contract_pdf_service
                pdf_url = await contract_pdf_service.generate_pdf(str(contract["_id"]))
            except Exception as e:
                logger.warning(f"PDF generation failed (non-blocking): {str(e)}")
                pdf_url = None

            # Get updated contract with payments
            updated = await self.contracts.find_one({"token": token})
            payments = await self.get_contract_payments(str(contract["_id"]))

            result = self._serialize_contract(updated)
            if result is None:
                raise ValueError("Failed to serialize updated contract")
            result["scheduled_payments"] = payments
            result["deposit_processed"] = deposit_result.get("success", False) if deposit_result else False

            # Send confirmation emails (async, don't block signing)
            try:
                from app.services.contract_email_service import contract_email_service
                await contract_email_service.send_signed_confirmation(result, pdf_url)

                # Get planner email and notify
                planner_id = contract.get("planner_id")
                if planner_id:
                    from bson import ObjectId
                    planner = await mongo.db["users"].find_one({"_id": ObjectId(planner_id)})
                    if planner and planner.get("email"):
                        await contract_email_service.send_planner_notification(
                            result,
                            planner.get("email")
                        )

                        # Send activity notification to planner's bell
                        try:
                            from app.services.planner_notification_service import planner_notification_service
                            await planner_notification_service.notify_contract_signed(
                                planner_id=planner.get("email"),
                                wedding_id=contract.get("wedding_id", ""),
                                signer_name=signature_name,
                                contract_id=str(contract.get("_id", ""))
                            )
                        except Exception as notif_err:
                            logger.warning(f"Activity notification failed: {str(notif_err)}")
            except Exception as e:
                logger.warning(f"Email notification failed (non-blocking): {str(e)}")

            return result

        except Exception as e:
            logger.error(f"Failed to sign contract: {str(e)}")
            raise

    async def _create_scheduled_payments(self, contract: Dict) -> List[Dict]:
        """
        Create scheduled payments from contract's payment schedule.

        Args:
            contract: The signed contract

        Returns:
            List of created scheduled payment dicts
        """
        try:
            package_snapshot = contract.get("package_snapshot", {})
            payment_schedule = package_snapshot.get("payment_schedule", [])
            total_amount = Decimal(str(package_snapshot.get("total_amount", 0)))
            currency = package_snapshot.get("currency", "usd")

            wedding_date = contract.get("wedding_date")
            signed_at = contract.get("signed_at") or datetime.now(timezone.utc)

            created_payments = []

            for schedule_item in payment_schedule:
                # Calculate amount
                if schedule_item.get("amount"):
                    amount = Decimal(str(schedule_item["amount"]))
                elif schedule_item.get("percentage"):
                    amount = total_amount * Decimal(str(schedule_item["percentage"])) / 100
                else:
                    continue  # Skip if no amount specified

                # Calculate due date
                trigger = schedule_item.get("trigger", "on_signing")
                due_date = self._calculate_due_date(
                    trigger=trigger,
                    signed_at=signed_at,
                    wedding_date=wedding_date,
                    days_after=schedule_item.get("days_after"),
                    days_before=schedule_item.get("days_before"),
                    fixed_date=schedule_item.get("fixed_date")
                )

                if not due_date:
                    logger.warning(f"Could not calculate due date for {schedule_item}")
                    continue

                # Create scheduled payment
                payment = ScheduledPayment(
                    contract_id=str(contract["_id"]),
                    planner_id=contract["planner_id"],
                    name=schedule_item.get("name", "Payment"),
                    amount=amount,
                    currency=currency,
                    due_date=due_date,
                    status="scheduled"
                )

                payment_dict = payment.model_dump(by_alias=True)
                result = await self.scheduled_payments.insert_one(payment_dict)
                payment_dict["_id"] = result.inserted_id

                serialized_payment = self._serialize_payment(payment_dict)
                if serialized_payment is not None:
                    created_payments.append(serialized_payment)

            logger.info(f"Created {len(created_payments)} scheduled payments for contract {contract['_id']}")
            return created_payments

        except Exception as e:
            logger.error(f"Failed to create scheduled payments: {str(e)}")
            raise

    def _calculate_due_date(
        self,
        trigger: str,
        signed_at: datetime,
        wedding_date: Optional[date],
        days_after: Optional[int],
        days_before: Optional[int],
        fixed_date: Optional[date]
    ) -> Optional[date]:
        """Calculate payment due date based on trigger type."""

        if trigger == "on_signing":
            return signed_at.date()

        elif trigger == "days_after_signing" and days_after is not None:
            return (signed_at + timedelta(days=days_after)).date()

        elif trigger == "days_before_wedding" and days_before is not None:
            if wedding_date:
                return wedding_date - timedelta(days=days_before)
            else:
                # If no wedding date, fallback to 90 days from signing
                logger.warning("No wedding date for days_before_wedding trigger, using 90 days from signing")
                return (signed_at + timedelta(days=90)).date()

        elif trigger == "fixed_date" and fixed_date:
            if isinstance(fixed_date, str):
                return date.fromisoformat(fixed_date)
            return fixed_date

        return None

    async def _process_deposit_payment(
        self,
        contract_id: str,
        customer_id: str,
        payment_method_id: str
    ) -> Dict[str, Any]:
        """
        Process the first payment (deposit) if due on signing.

        Args:
            contract_id: The contract ID
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID

        Returns:
            Dict with success status and payment details
        """
        try:
            import stripe
            from app.core.settings import settings

            if not settings.stripe_secret_key:
                logger.warning("Stripe not configured, skipping deposit processing")
                return {"success": False, "error": "Stripe not configured"}

            stripe.api_key = settings.stripe_secret_key

            # Find the on_signing payment
            payment = await self.scheduled_payments.find_one({
                "contract_id": contract_id,
                "status": "scheduled"
            })

            if not payment:
                logger.info(f"No scheduled payments found for contract {contract_id}")
                return {"success": True, "message": "No deposit required"}

            # Check if this payment's trigger is "on_signing" (due date = today)
            due_date = payment.get("due_date")
            if due_date and hasattr(due_date, 'date'):
                due_date = due_date.date()

            if due_date and due_date > datetime.now(timezone.utc).date():
                logger.info(f"First payment not due yet (due: {due_date})")
                return {"success": True, "message": "First payment not due yet"}

            # Get contract to check planner's connect account
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                return {"success": False, "error": "Contract not found"}

            planner_id = contract.get("planner_id")
            destination_account = None

            if planner_id:
                planner = await mongo.db["users"].find_one({"_id": ObjectId(planner_id)})
                if planner and planner.get("stripe_connect_id"):
                    destination_account = planner.get("stripe_connect_id")

            amount_cents = int(float(payment.get("amount", 0)) * 100)
            currency = payment.get("currency", "usd")

            if amount_cents <= 0:
                return {"success": False, "error": "Invalid payment amount"}

            # Create PaymentIntent and charge immediately
            # Use idempotency key to prevent double-charging on retries/duplicate requests
            idempotency_key = f"deposit_{contract_id}_{str(payment['_id'])}"

            payment_intent_params = {
                "amount": amount_cents,
                "currency": currency,
                "customer": customer_id,
                "payment_method": payment_method_id,
                "confirm": True,
                "off_session": True,
                "description": f"Deposit for contract {contract_id}",
                "metadata": {
                    "contract_id": contract_id,
                    "payment_id": str(payment["_id"]),
                    "payment_type": "deposit"
                },
                "idempotency_key": idempotency_key
            }

            # Add destination for Connect if planner has account
            if destination_account:
                payment_intent_params["transfer_data"] = {
                    "destination": destination_account
                }

            payment_intent = stripe.PaymentIntent.create(**payment_intent_params)

            if payment_intent.status == "succeeded":
                # Update scheduled payment status
                await self.scheduled_payments.update_one(
                    {"_id": payment["_id"]},
                    {
                        "$set": {
                            "status": "succeeded",
                            "paid_at": datetime.now(timezone.utc),
                            "stripe_payment_intent_id": payment_intent.id,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                logger.info(f"Deposit processed for contract {contract_id}: {payment_intent.id}")
                return {
                    "success": True,
                    "payment_intent_id": payment_intent.id,
                    "amount": amount_cents / 100,
                    "currency": currency
                }
            else:
                # Payment requires action or failed
                await self.scheduled_payments.update_one(
                    {"_id": payment["_id"]},
                    {
                        "$set": {
                            "status": "failed" if payment_intent.status == "canceled" else "processing",
                            "stripe_payment_intent_id": payment_intent.id,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                return {
                    "success": False,
                    "status": payment_intent.status,
                    "payment_intent_id": payment_intent.id
                }

        except stripe.error.CardError as e:
            logger.error(f"Card error processing deposit: {str(e)}")
            return {"success": False, "error": str(e.user_message)}
        except Exception as e:
            logger.error(f"Failed to process deposit: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_contract_payments(
        self,
        contract_id: str,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Get scheduled payments for a contract.

        Args:
            contract_id: The contract ID
            status: Optional status filter

        Returns:
            List of scheduled payment dicts
        """
        try:
            query = {"contract_id": contract_id}
            if status:
                query["status"] = status

            cursor = self.scheduled_payments.find(query).sort("due_date", 1)
            payments = await cursor.to_list(length=None)

            serialized_payments: List[Dict] = []
            for payment in payments:
                serialized = self._serialize_payment(payment)
                if serialized is not None:
                    serialized_payments.append(serialized)

            return serialized_payments

        except Exception as e:
            logger.error(f"Failed to get contract payments: {str(e)}")
            raise

    async def update_wedding_date(
        self,
        contract_id: str,
        planner_id: str,
        new_wedding_date: date
    ) -> Dict:
        """
        Update wedding date and recalculate payment schedules.

        Args:
            contract_id: The contract ID
            planner_id: The planner's ID
            new_wedding_date: New wedding date

        Returns:
            Updated contract dict
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found or access denied")

            old_date = contract.get("wedding_date")
            if isinstance(old_date, str):
                old_date = date.fromisoformat(old_date)

            # If the date didn't change, avoid unnecessary writes/recalculation
            if old_date == new_wedding_date:
                serialized = self._serialize_contract(contract)
                if serialized is None:
                    raise ValueError("Failed to serialize contract")
                return serialized

            # Update contract
            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "wedding_date": new_wedding_date,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            # Recalculate days_before_wedding payments
            await self._recalculate_payment_dates(contract, new_wedding_date)
            updated = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            serialized = self._serialize_contract(updated)
            if serialized is None:
                raise ValueError("Failed to serialize updated contract")
            return serialized

        except Exception as e:
            logger.error(f"Failed to update wedding date: {str(e)}")
            raise

    async def _recalculate_payment_dates(self, contract: Dict, new_wedding_date: date):
        """Recalculate due dates for payments with days_before_wedding trigger."""
        try:
            package_snapshot = contract.get("package_snapshot", {})
            payment_schedule = package_snapshot.get("payment_schedule", [])

            # Find payments that need recalculation
            for schedule_item in payment_schedule:
                if schedule_item.get("trigger") == "days_before_wedding":
                    days_before = schedule_item.get("days_before", 0)
                    new_due_date = new_wedding_date - timedelta(days=days_before)

                    # Update matching scheduled payment
                    await self.scheduled_payments.update_many(
                        {
                            "contract_id": str(contract["_id"]),
                            "name": schedule_item.get("name"),
                            "status": "scheduled"
                        },
                        {"$set": {"due_date": new_due_date, "updated_at": datetime.now(timezone.utc)}}
                    )

        except Exception as e:
            logger.error(f"Failed to recalculate payment dates: {str(e)}")

    async def cancel_contract(
        self,
        contract_id: str,
        planner_id: str,
        reason: str
    ) -> Dict:
        """
        Cancel a contract and all pending payments.

        Args:
            contract_id: The contract ID
            planner_id: The planner's ID
            reason: Cancellation reason

        Returns:
            Updated contract dict
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found or access denied")

            if contract.get("status") in ["completed", "cancelled"]:
                raise ValueError(f"Cannot cancel contract in status: {contract['status']}")

            now = datetime.now(timezone.utc)

            # Cancel contract
            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": now,
                        "cancellation_reason": reason,
                        "updated_at": now
                    }
                }
            )

            # Cancel all pending payments
            await self.scheduled_payments.update_many(
                {
                    "contract_id": contract_id,
                    "status": "scheduled"
                },
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": now,
                        "updated_at": now
                    }
                }
            )

            updated = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            serialized = self._serialize_contract(updated)
            if serialized is None:
                raise ValueError("Failed to serialize updated contract")
            return serialized

        except Exception as e:
            logger.error(f"Failed to cancel contract: {str(e)}")
            raise

    async def mark_payment_paid_externally(
        self,
        payment_id: str,
        planner_id: str,
        payment_method: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict:
        """
        Mark a scheduled payment as paid externally (cash, check, wire, etc.)

        Args:
            payment_id: The scheduled payment ID
            planner_id: The planner's ID (for verification)
            payment_method: How the payment was received (cash, check, wire, etc.)
            note: Optional note about the external payment

        Returns:
            Updated payment dict
        """
        try:
            # Find the payment and verify ownership
            payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

            if not payment:
                raise ValueError("Payment not found")

            # Verify the planner owns this payment's contract
            if payment.get("planner_id") != planner_id:
                raise ValueError("Payment not found or access denied")

            # Can only mark scheduled or failed payments as paid externally
            if payment.get("status") not in ["scheduled", "failed"]:
                raise ValueError(f"Cannot mark payment with status '{payment.get('status')}' as paid externally")

            now = datetime.now(timezone.utc)

            # Update the payment
            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "status": "paid_externally",
                        "paid_externally": True,
                        "external_payment_method": payment_method,
                        "external_payment_note": note,
                        "paid_at": now,
                        "updated_at": now
                    }
                }
            )

            logger.info(f"Payment {payment_id} marked as paid externally via {payment_method}")

            # Return updated payment
            updated = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})
            return self._serialize_payment(updated)

        except Exception as e:
            logger.error(f"Failed to mark payment as paid externally: {str(e)}")
            raise

    async def process_refund(
        self,
        payment_id: str,
        planner_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Process a refund for a succeeded payment.

        Args:
            payment_id: The scheduled payment ID
            planner_id: The planner's ID (for verification)
            amount: Optional refund amount (partial refund). If None, full refund.
            reason: Optional refund reason

        Returns:
            Updated payment dict with refund info
        """
        try:
            import stripe
            from app.core.settings import settings

            stripe.api_key = settings.stripe_secret_key

            # Find the payment and verify ownership
            payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

            if not payment:
                raise ValueError("Payment not found")

            if payment.get("planner_id") != planner_id:
                raise ValueError("Payment not found or access denied")

            # Can only refund succeeded payments
            if payment.get("status") != "succeeded":
                raise ValueError(f"Cannot refund payment with status '{payment.get('status')}'")

            payment_intent_id = payment.get("stripe_payment_intent_id")
            if not payment_intent_id:
                raise ValueError("No Stripe payment intent found for this payment")

            payment_amount = float(payment.get("amount", 0))

            # Validate refund amount
            if amount is not None:
                if amount <= 0:
                    raise ValueError("Refund amount must be positive")
                if amount > payment_amount:
                    raise ValueError(f"Refund amount cannot exceed payment amount (${payment_amount})")
                refund_amount_cents = int(amount * 100)
                is_partial = amount < payment_amount
            else:
                refund_amount_cents = int(payment_amount * 100)
                amount = payment_amount
                is_partial = False

            # Create refund in Stripe
            refund_params = {
                "payment_intent": payment_intent_id,
                "amount": refund_amount_cents,
            }
            if reason:
                refund_params["reason"] = "requested_by_customer"

            refund = stripe.Refund.create(**refund_params)

            now = datetime.now(timezone.utc)

            # Update payment record
            update_data = {
                "refund_id": refund.id,
                "refund_amount": amount,
                "refund_reason": reason,
                "refunded_at": now,
                "updated_at": now
            }

            # Update status based on refund type
            if is_partial:
                update_data["status"] = "partially_refunded"
            else:
                update_data["status"] = "refunded"

            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment_id)},
                {"$set": update_data}
            )

            logger.info(f"Processed {'partial' if is_partial else 'full'} refund of ${amount} for payment {payment_id}")

            # Return updated payment
            updated = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})
            return self._serialize_payment(updated)

        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            raise ValueError(f"Stripe refund failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to process refund: {str(e)}")
            raise

    async def retry_payment(
        self,
        payment_id: str,
        planner_id: str
    ) -> Dict:
        """
        Retry a failed scheduled payment.

        Args:
            payment_id: The scheduled payment ID
            planner_id: The planner's ID (for verification)

        Returns:
            Updated payment dict with retry result
        """
        try:
            from app.services.autopilot_service import autopilot_service

            # Find the payment and verify ownership
            payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

            if not payment:
                raise ValueError("Payment not found")

            if payment.get("planner_id") != planner_id:
                raise ValueError("Payment not found or access denied")

            # Can only retry failed payments
            if payment.get("status") != "failed":
                raise ValueError(f"Cannot retry payment with status '{payment.get('status')}'. Only failed payments can be retried.")

            # Reset status to scheduled for retry (atomic - only if still failed)
            # This prevents race conditions if multiple retry requests come in
            update_result = await self.scheduled_payments.update_one(
                {
                    "_id": ObjectId(payment_id),
                    "status": "failed"  # Only update if still in failed state
                },
                {"$set": {"status": "scheduled", "updated_at": datetime.now(timezone.utc)}}
            )

            # Check if another process already started retrying
            if update_result.modified_count == 0:
                raise ValueError("Payment is already being retried by another process")

            # Process the payment immediately
            payment_dict = self._serialize_payment(payment)
            result = await autopilot_service._process_single_payment(payment_dict)

            # Get updated payment
            updated = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

            if result.get("success"):
                logger.info(f"Payment {payment_id} retry succeeded")
            else:
                logger.warning(f"Payment {payment_id} retry failed: {result.get('error')}")

            return self._serialize_payment(updated)

        except Exception as e:
            logger.error(f"Failed to retry payment: {str(e)}")
            raise

    async def cancel_payment(
        self,
        payment_id: str,
        planner_id: str,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Cancel a scheduled payment.

        Args:
            payment_id: The scheduled payment ID
            planner_id: The planner's ID (for verification)
            reason: Optional cancellation reason

        Returns:
            Updated payment dict
        """
        try:
            # Find the payment and verify ownership
            payment = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})

            if not payment:
                raise ValueError("Payment not found")

            if payment.get("planner_id") != planner_id:
                raise ValueError("Payment not found or access denied")

            # Can only cancel scheduled or failed payments
            if payment.get("status") not in ["scheduled", "failed"]:
                raise ValueError(f"Cannot cancel payment with status '{payment.get('status')}'. Only scheduled or failed payments can be cancelled.")

            now = datetime.now(timezone.utc)

            await self.scheduled_payments.update_one(
                {"_id": ObjectId(payment_id)},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": now,
                        "cancellation_reason": reason,
                        "updated_at": now
                    }
                }
            )

            logger.info(f"Payment {payment_id} cancelled by planner {planner_id}")

            # Return updated payment
            updated = await self.scheduled_payments.find_one({"_id": ObjectId(payment_id)})
            return self._serialize_payment(updated)

        except Exception as e:
            logger.error(f"Failed to cancel payment: {str(e)}")
            raise

    async def get_contract_stats(self, planner_id: str) -> Dict[str, Any]:
        """
        Get contract statistics for a planner.

        Args:
            planner_id: The planner's user ID

        Returns:
            Dict with contract counts by status
        """
        try:
            pipeline = [
                {"$match": {"planner_id": planner_id}},
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                }
            ]

            stats = await self.contracts.aggregate(pipeline).to_list(length=None)

            return {
                "by_status": {s["_id"]: s["count"] for s in stats},
                "total_contracts": sum(s["count"] for s in stats)
            }

        except Exception as e:
            logger.error(f"Failed to get contract stats: {str(e)}")
            raise

    def _serialize_contract(self, contract: Optional[Dict]) -> Optional[Dict]:
        """Serialize contract for API response."""
        if not contract:
            return None

        serialized = {**contract}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            serialized["_id"] = str(serialized["_id"])

        # Convert dates to ISO format
        for date_field in ["wedding_date", "sent_at", "viewed_at", "signed_at",
                           "completed_at", "cancelled_at", "created_at", "updated_at"]:
            if date_field in serialized and serialized[date_field]:
                if hasattr(serialized[date_field], "isoformat"):
                    serialized[date_field] = serialized[date_field].isoformat()

        return serialized

    def _serialize_payment(self, payment: Dict) -> Optional[Dict]:
        """Serialize scheduled payment for API response."""
        if not payment:
            return None

        serialized = {**payment}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            serialized["_id"] = str(serialized["_id"])

        if "amount" in serialized:
            serialized["amount"] = float(serialized["amount"])

        if "due_date" in serialized and hasattr(serialized["due_date"], "isoformat"):
            serialized["due_date"] = serialized["due_date"].isoformat()

        return serialized


# Singleton instance
contract_service = ContractService()
