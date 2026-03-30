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
from app.utils.mongo_dates import to_mongo_datetime
from app.utils.payment_schedule import build_effective_payment_schedule

logger = logging.getLogger(__name__)


# C17: Documented contract status constants — single source of truth
CONTRACT_STATUS_DRAFT = "draft"
CONTRACT_STATUS_PENDING_REVIEW = "pending_review"
CONTRACT_STATUS_SENT = "sent"
CONTRACT_STATUS_VIEWED = "viewed"
CONTRACT_STATUS_SIGNED = "signed"
CONTRACT_STATUS_ACTIVE = "active"
CONTRACT_STATUS_COMPLETED = "completed"
CONTRACT_STATUS_CANCELLED = "cancelled"

# Statuses that allow editing
EDITABLE_STATUSES = {CONTRACT_STATUS_DRAFT, CONTRACT_STATUS_PENDING_REVIEW}

# Statuses that allow sending
SENDABLE_STATUSES = {CONTRACT_STATUS_DRAFT, CONTRACT_STATUS_PENDING_REVIEW}

# Statuses that mean the contract is no longer actionable
TERMINAL_STATUSES = {CONTRACT_STATUS_COMPLETED, CONTRACT_STATUS_CANCELLED}

# Payment milestone statuses
MILESTONE_STATUS_PENDING = "pending"
MILESTONE_STATUS_PARTIAL = "partial"
MILESTONE_STATUS_PAID = "paid"
MILESTONE_STATUS_OVERDUE = "overdue"


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
        self.users = mongo.db["users"]
        self.weddings = mongo.db["weddings"]
        self.max_money_overview_contracts = 5000
        self.max_money_overview_payments = 20000

    @staticmethod
    def _normalize_couple(couple: Any) -> Dict[str, Any]:
        if not isinstance(couple, dict):
            return {}

        partner1 = (couple.get("partner1_name") or couple.get("name") or "").strip()
        partner2 = (couple.get("partner2_name") or couple.get("partner_name") or "").strip()
        display_name = f"{partner1} & {partner2}" if partner2 else partner1

        return {
            **couple,
            "partner1_name": partner1,
            "partner2_name": partner2 or None,
            "name": partner1,
            "partner_name": partner2 or None,
            "display_name": display_name,
        }

    @staticmethod
    def _build_planner_snapshot(planner: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
        planner = planner or {}
        planner_name = (
            planner.get("company_name")
            or planner.get("business_name")
            or planner.get("name")
            or " ".join(
                part for part in [planner.get("first_name"), planner.get("last_name")] if part
            ).strip()
            or planner.get("email")
            or "Your Wedding Planner"
        )
        return {
            "planner_name": planner_name,
            "planner_email": planner.get("email"),
            "planner_phone": planner.get("phone") or planner.get("support_phone"),
            "planner_logo": planner.get("logo_url")
            or planner.get("profile_image_url")
            or planner.get("profile_image")
            or planner.get("avatar_url"),
        }

    async def _get_planner_record(self, planner_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not planner_id:
            return None

        try:
            if ObjectId.is_valid(str(planner_id)):
                planner = await self.users.find_one({"_id": ObjectId(str(planner_id))})
                if planner:
                    return planner
        except Exception:
            pass

        return await self.users.find_one({"email": planner_id})

    async def _get_wedding_record(self, wedding_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not wedding_id:
            return None

        wedding = await self.weddings.find_one({"_id": wedding_id})
        if wedding:
            return wedding

        if ObjectId.is_valid(str(wedding_id)):
            return await self.weddings.find_one({"_id": ObjectId(str(wedding_id))})

        return None

    async def _serialize_contract_response(self, contract: Optional[Dict]) -> Optional[Dict]:
        if not contract:
            return None

        hydrated = {**contract}
        updates: Dict[str, Any] = {}
        package_snapshot = dict(hydrated.get("package_snapshot") or {})
        effective_schedule = build_effective_payment_schedule(package_snapshot)
        if package_snapshot.get("payment_schedule") != effective_schedule:
            package_snapshot["payment_schedule"] = effective_schedule
            updates["package_snapshot"] = package_snapshot
            hydrated["package_snapshot"] = package_snapshot

        couple = self._normalize_couple(hydrated.get("couple"))
        if couple:
            hydrated["couple"] = couple

        wedding = None
        if not hydrated.get("venue") or not hydrated.get("wedding_date"):
            wedding = await self._get_wedding_record(hydrated.get("wedding_id"))
            if wedding:
                venue = wedding.get("venue") or wedding.get("location")
                if venue and not hydrated.get("venue"):
                    updates["venue"] = venue

                wedding_date = wedding.get("date")
                if wedding_date and not hydrated.get("wedding_date"):
                    updates["wedding_date"] = to_mongo_datetime(
                        date.fromisoformat(wedding_date) if isinstance(wedding_date, str) else wedding_date
                    )

        planner_fields = ["planner_name", "planner_email", "planner_phone", "planner_logo"]
        if any(not hydrated.get(field) for field in planner_fields):
            planner = await self._get_planner_record(hydrated.get("planner_id"))
            if planner:
                planner_snapshot = self._build_planner_snapshot(planner)
                for field, value in planner_snapshot.items():
                    if value and not hydrated.get(field):
                        updates[field] = value

        if "late_payment_policy" not in package_snapshot and hydrated.get("package_id"):
            package = None
            try:
                if ObjectId.is_valid(str(hydrated.get("package_id"))):
                    package = await self.packages.find_one({"_id": ObjectId(str(hydrated.get("package_id")))})
            except Exception:
                package = None

            if package and package.get("late_payment_policy") is not None:
                package_snapshot["late_payment_policy"] = package.get("late_payment_policy")
                updates["package_snapshot"] = package_snapshot
                hydrated["package_snapshot"] = package_snapshot

        if updates and hydrated.get("_id"):
            await self.contracts.update_one({"_id": hydrated["_id"]}, {"$set": updates})
            hydrated.update(updates)

        return self._serialize_contract(hydrated)

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
            return await self._serialize_contract_response(contract)

        except Exception as e:
            logger.error(f"Failed to get contract: {str(e)}")
            raise

    async def get_contract_by_token(self, token: str) -> Optional[Dict]:
        """
        Get a contract by public token.
        Used for public contract viewing/signing.

        Includes token expiration check (C11):
        - Tokens expire 30 days after the contract is sent.
        - Cancelled/completed contracts have expired tokens.

        Args:
            token: The contract access token

        Returns:
            Contract dict or None

        Raises:
            ValueError: If token is expired
        """
        try:
            contract = await self.contracts.find_one({"token": token})
            if not contract:
                return None

            # Token expiration check (C11)
            status = contract.get("status", "")
            if status in ("cancelled", "completed"):
                raise ValueError("This contract link has expired. The contract has been " + status + ".")

            sent_at = contract.get("sent_at")
            if sent_at and isinstance(sent_at, datetime):
                expiry = sent_at + timedelta(days=30)
                if datetime.now(timezone.utc) > expiry:
                    raise ValueError(
                        "This contract link has expired. Please contact the planner for a new link."
                    )

            return await self._serialize_contract_response(contract)

        except ValueError:
            raise
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
                serialized = await self._serialize_contract_response(c)
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
            serialized = await self._serialize_contract_response(updated)
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

            result = await self._serialize_contract_response(updated)
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
            payment_schedule = build_effective_payment_schedule(package_snapshot)
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
                payment_dict["due_date"] = to_mongo_datetime(payment.due_date)
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
                    "scheduled_payment_id": str(payment["_id"]),
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
                from app.services.autopilot_service import autopilot_service

                receipt_url = None
                if payment_intent.charges and payment_intent.charges.data:
                    receipt_url = payment_intent.charges.data[0].receipt_url

                await autopilot_service.record_payment_success(
                    payment_id=str(payment["_id"]),
                    payment_intent_id=payment_intent.id,
                    receipt_url=receipt_url,
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

    async def get_planner_payment_overview(
        self,
        planner_id: str,
        contract_statuses: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Get scheduled payments across a planner's contracts in one query set.

        Used by the admin money dashboard to avoid N+1 contract payment fetches.
        """
        try:
            contract_query: Dict[str, Any] = {"planner_id": planner_id}
            if contract_statuses:
                contract_query["status"] = {"$in": contract_statuses}

            contract_cursor = self.contracts.find(
                contract_query,
                {
                    "couple": 1,
                    "package_snapshot": 1,
                    "contract_title": 1,
                    "status": 1,
                },
            )
            contracts = await contract_cursor.to_list(length=self.max_money_overview_contracts)
            if not contracts:
                return []

            contract_lookup: Dict[str, Dict[str, Any]] = {}
            contract_ids: List[str] = []
            for contract in contracts:
                contract_id = str(contract["_id"])
                couple = self._normalize_couple(contract.get("couple"))
                contract_lookup[contract_id] = {
                    "couple_name": couple.get("display_name") or "A couple",
                    "wedding_title": (
                        (contract.get("package_snapshot") or {}).get("name")
                        or contract.get("contract_title")
                        or "Wedding"
                    ),
                    "contract_status": contract.get("status"),
                }
                contract_ids.append(contract_id)

            payments_cursor = self.scheduled_payments.find(
                {"contract_id": {"$in": contract_ids}}
            ).sort("due_date", 1)
            payments = await payments_cursor.to_list(length=self.max_money_overview_payments)

            overview: List[Dict[str, Any]] = []
            for payment in payments:
                serialized = self._serialize_payment(payment)
                if serialized is None:
                    continue

                contract_meta = contract_lookup.get(str(serialized.get("contract_id")), {})
                overview.append({
                    **serialized,
                    "name": serialized.get("name") or serialized.get("description") or "Scheduled payment",
                    "couple_name": contract_meta.get("couple_name", "A couple"),
                    "wedding_title": contract_meta.get("wedding_title", "Wedding"),
                    "contract_status": contract_meta.get("contract_status"),
                })

            return overview

        except Exception as e:
            logger.error(f"Failed to get planner payment overview: {str(e)}")
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
                serialized = await self._serialize_contract_response(contract)
                if serialized is None:
                    raise ValueError("Failed to serialize contract")
                return serialized

            # Update contract
            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "wedding_date": to_mongo_datetime(new_wedding_date),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            # Recalculate days_before_wedding payments
            await self._recalculate_payment_dates(contract, new_wedding_date)
            updated = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            serialized = await self._serialize_contract_response(updated)
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
            payment_schedule = build_effective_payment_schedule(package_snapshot)

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
                        {
                            "$set": {
                                "due_date": to_mongo_datetime(new_due_date),
                                "updated_at": datetime.now(timezone.utc),
                            }
                        }
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
            serialized = await self._serialize_contract_response(updated)
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

    # ========================================================================
    # CONTRACT CREATION, UPDATE, SEND (C3, C4 — missing endpoints)
    # ========================================================================

    async def _generate_contract_number(self) -> str:
        """
        Auto-generate a unique contract number (C5).
        Format: CON-YYYYMMDD-XXXX where XXXX is a sequential counter.
        """
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"CON-{today}-"

        # Find the latest contract number with today's prefix
        latest = await self.contracts.find_one(
            {"contract_number": {"$regex": f"^{prefix}"}},
            sort=[("contract_number", -1)]
        )

        if latest and latest.get("contract_number"):
            try:
                last_num = int(latest["contract_number"].split("-")[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1

        return f"{prefix}{next_num:04d}"

    async def create_contract(
        self,
        planner_id: str,
        wedding_id: str,
        vendor_profile_id: str,
        total_amount: float,
        template_id: Optional[str] = None,
        deposit_percentage: float = 50.0,
        service_date: Optional[str] = None,
        service_location: Optional[str] = None,
        custom_sections: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Create a new vendor contract (C3).

        Args:
            planner_id: ID of the planner creating the contract
            wedding_id: Wedding this contract belongs to
            vendor_profile_id: Vendor profile ID
            total_amount: Total contract amount
            template_id: Optional template ID to base contract on
            deposit_percentage: Deposit percentage (default 50%)
            service_date: Optional service date
            service_location: Optional service location
            custom_sections: Optional custom contract sections

        Returns:
            Created contract dict
        """
        import secrets

        try:
            # Look up vendor profile
            vendor_profiles = mongo.db["vendor_profiles"]
            vendor = await vendor_profiles.find_one({"_id": ObjectId(vendor_profile_id)})
            if not vendor:
                raise ValueError("Vendor profile not found")

            # Look up wedding for context
            weddings = mongo.db["weddings"]
            wedding = await weddings.find_one({"_id": ObjectId(wedding_id)})

            # Auto-generate contract number (C5)
            contract_number = await self._generate_contract_number()

            # Generate secure access token
            access_token = secrets.token_urlsafe(32)

            # Calculate deposit
            deposit_amount = round(total_amount * (deposit_percentage / 100), 2)

            # Build sections
            sections = custom_sections or []

            # Load template sections if template_id provided
            if template_id:
                templates = mongo.db["contract_templates"]
                template = await templates.find_one({"_id": ObjectId(template_id)})
                if template and not custom_sections:
                    sections = template.get("sections", [])

            contract_title = f"Contract - {vendor.get('business_name', 'Vendor')}"
            if wedding:
                couple = wedding.get("couple_names") or wedding.get("partner1_name", "")
                if couple:
                    contract_title = f"{couple} - {vendor.get('business_name', 'Vendor')} Contract"

            now = datetime.now(timezone.utc)

            doc = {
                "planner_id": planner_id,
                "wedding_id": wedding_id,
                "vendor_profile_id": vendor_profile_id,
                "vendor_name": vendor.get("business_name", ""),
                "vendor_email": vendor.get("email", ""),
                "vendor_phone": vendor.get("phone", ""),
                "service_category": vendor.get("service_category", "other"),
                "contract_title": contract_title,
                "contract_number": contract_number,
                "total_amount": total_amount,
                "deposit_amount": deposit_amount,
                "deposit_percentage": deposit_percentage,
                "service_date": service_date,
                "service_location": service_location or "",
                "template_id": template_id,
                "sections": sections,
                "terms_and_conditions": "",
                "cancellation_policy": "",
                "custom_clauses": "",
                "token": access_token,
                "status": "draft",
                "created_at": now,
                "updated_at": now,
                "sent_at": None,
                "viewed_at": None,
                "signed_at": None,
                "completed_at": None,
                "cancelled_at": None,
            }

            result = await self.contracts.insert_one(doc)
            doc["_id"] = result.inserted_id
            return await self._serialize_contract_response(doc)

        except Exception as e:
            logger.error(f"Failed to create contract: {str(e)}")
            raise

    async def update_contract(
        self,
        contract_id: str,
        planner_id: str,
        update_data: Dict
    ) -> Optional[Dict]:
        """
        Update a contract (only allowed in draft/pending_review status).

        Args:
            contract_id: Contract ID
            planner_id: Planner ID for ownership verification
            update_data: Fields to update

        Returns:
            Updated contract dict
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found")

            # Status transition validation (C13)
            if contract.get("status") not in ("draft", "pending_review"):
                raise ValueError(
                    f"Cannot edit contract in '{contract.get('status')}' status. "
                    "Only draft and pending_review contracts can be edited."
                )

            # Remove fields that shouldn't be updated directly
            safe_fields = {
                "contract_title", "total_amount", "deposit_amount", "deposit_percentage",
                "service_date", "service_location", "sections",
                "terms_and_conditions", "cancellation_policy", "custom_clauses",
            }

            filtered = {k: v for k, v in update_data.items() if k in safe_fields}
            filtered["updated_at"] = datetime.now(timezone.utc)

            # Recalculate deposit if total_amount or deposit_percentage changed
            if "total_amount" in filtered or "deposit_percentage" in filtered:
                total = filtered.get("total_amount", contract.get("total_amount", 0))
                pct = filtered.get("deposit_percentage", contract.get("deposit_percentage", 50))
                filtered["deposit_amount"] = round(total * (pct / 100), 2)

            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": filtered}
            )

            updated = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            return await self._serialize_contract_response(updated)

        except Exception as e:
            logger.error(f"Failed to update contract: {str(e)}")
            raise

    async def update_contract_sections(
        self,
        contract_id: str,
        planner_id: str,
        sections: List[Dict],
        terms_and_conditions: Optional[str] = None,
        cancellation_policy: Optional[str] = None,
        custom_clauses: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Update contract sections (C4).

        Args:
            contract_id: Contract ID
            planner_id: Planner ID for ownership verification
            sections: List of section dicts with id, title, content, order
            terms_and_conditions: Optional terms text
            cancellation_policy: Optional cancellation policy text
            custom_clauses: Optional custom clauses text

        Returns:
            Updated contract dict
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found")

            if contract.get("status") not in ("draft", "pending_review"):
                raise ValueError("Cannot update sections on a non-draft contract")

            update: Dict[str, Any] = {
                "sections": sections,
                "updated_at": datetime.now(timezone.utc),
            }
            if terms_and_conditions is not None:
                update["terms_and_conditions"] = terms_and_conditions
            if cancellation_policy is not None:
                update["cancellation_policy"] = cancellation_policy
            if custom_clauses is not None:
                update["custom_clauses"] = custom_clauses

            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": update}
            )

            updated = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            return await self._serialize_contract_response(updated)

        except Exception as e:
            logger.error(f"Failed to update contract sections: {str(e)}")
            raise

    async def send_contract(
        self,
        contract_id: str,
        planner_id: str,
        message: Optional[str] = None,
    ) -> Dict:
        """
        Send a contract to the vendor for review/signing.

        Updates status to 'sent' and records sent_at timestamp.
        Triggers email notification via contract_email_service.

        Args:
            contract_id: Contract ID
            planner_id: Planner ID for ownership verification
            message: Optional personal message to include

        Returns:
            Dict with message and sent_to fields
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found")

            # Status validation (C13)
            allowed_send_statuses = ("draft", "pending_review")
            if contract.get("status") not in allowed_send_statuses:
                raise ValueError(
                    f"Cannot send contract in '{contract.get('status')}' status. "
                    f"Only {', '.join(allowed_send_statuses)} contracts can be sent."
                )

            vendor_email = contract.get("vendor_email", "")
            if not vendor_email:
                raise ValueError("Contract has no vendor email address")

            now = datetime.now(timezone.utc)
            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {"$set": {
                    "status": "sent",
                    "sent_at": now,
                    "updated_at": now,
                }}
            )

            # Send email notification
            try:
                from app.services.contract_email_service import contract_email_service
                await contract_email_service.send_contract_email(
                    contract_id=contract_id,
                    token=contract.get("token", ""),
                    vendor_email=vendor_email,
                    vendor_name=contract.get("vendor_name", ""),
                    contract_title=contract.get("contract_title", ""),
                    planner_message=message,
                )
            except Exception as email_err:
                logger.warning(f"Failed to send contract email (contract still marked sent): {email_err}")

            return {
                "message": "Contract sent successfully",
                "sent_to": vendor_email,
            }

        except Exception as e:
            logger.error(f"Failed to send contract: {str(e)}")
            raise

    async def create_payment_milestones(
        self,
        contract_id: str,
        planner_id: str,
        milestones: List[Dict],
    ) -> List[Dict]:
        """
        Create payment milestones for a contract.

        Args:
            contract_id: Contract ID
            planner_id: Planner ID for ownership verification
            milestones: List of milestone dicts with description, amount, due_date

        Returns:
            List of created milestone dicts
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })

            if not contract:
                raise ValueError("Contract not found")

            created = []
            now = datetime.now(timezone.utc)

            for m in milestones:
                doc = {
                    "contract_id": contract_id,
                    "wedding_id": contract.get("wedding_id", ""),
                    "vendor_name": contract.get("vendor_name", ""),
                    "vendor_email": contract.get("vendor_email", ""),
                    "description": m.get("description", ""),
                    "amount": float(m.get("amount", 0)),
                    "paid_amount": 0.0,
                    "due_date": m.get("due_date", ""),
                    "percentage_of_total": m.get("percentage_of_total", 0),
                    "status": "pending",
                    "payment_history": [],
                    "created_at": now,
                    "updated_at": now,
                }

                result = await self.scheduled_payments.insert_one(doc)
                doc["_id"] = result.inserted_id
                created.append(self._serialize_payment(doc))

            return created

        except Exception as e:
            logger.error(f"Failed to create payment milestones: {str(e)}")
            raise

    async def get_milestones(
        self,
        planner_id: str,
        contract_id: Optional[str] = None,
        wedding_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get payment milestones filtered by contract, wedding, or status.

        Args:
            planner_id: Planner ID for ownership verification
            contract_id: Optional contract ID filter
            wedding_id: Optional wedding ID filter
            status: Optional status filter

        Returns:
            List of milestone dicts
        """
        try:
            query: Dict[str, Any] = {}

            if contract_id:
                # Verify planner owns this contract
                contract = await self.contracts.find_one({
                    "_id": ObjectId(contract_id),
                    "planner_id": planner_id
                })
                if not contract:
                    raise ValueError("Contract not found")
                query["contract_id"] = contract_id

            if wedding_id:
                query["wedding_id"] = wedding_id

            if status:
                query["status"] = status

            milestones = await self.scheduled_payments.find(query).sort("due_date", 1).to_list(length=None)
            return [self._serialize_payment(m) for m in milestones if m]

        except Exception as e:
            logger.error(f"Failed to get milestones: {str(e)}")
            raise

    async def record_milestone_payment(
        self,
        milestone_id: str,
        planner_id: str,
        amount: float,
        payment_method: str = "manual",
        payment_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Record a payment against a milestone (C2).

        Args:
            milestone_id: Milestone ID
            planner_id: Planner ID for ownership verification
            amount: Payment amount
            payment_method: How payment was made
            payment_date: When payment was made
            notes: Optional notes

        Returns:
            Updated milestone dict
        """
        try:
            milestone = await self.scheduled_payments.find_one({"_id": ObjectId(milestone_id)})
            if not milestone:
                raise ValueError("Milestone not found")

            # Verify ownership via contract
            if milestone.get("contract_id"):
                contract = await self.contracts.find_one({
                    "_id": ObjectId(milestone["contract_id"]),
                    "planner_id": planner_id
                })
                if not contract:
                    raise ValueError("Milestone's contract not found or not owned by planner")

            now = datetime.now(timezone.utc)
            new_paid = milestone.get("paid_amount", 0) + amount

            # Determine new status
            if new_paid >= milestone.get("amount", 0):
                new_status = "paid"
            elif new_paid > 0:
                new_status = "partial"
            else:
                new_status = milestone.get("status", "pending")

            payment_record = {
                "amount": amount,
                "payment_method": payment_method,
                "payment_date": payment_date or now.isoformat(),
                "notes": notes or "",
                "recorded_at": now,
            }

            await self.scheduled_payments.update_one(
                {"_id": ObjectId(milestone_id)},
                {
                    "$set": {
                        "paid_amount": new_paid,
                        "status": new_status,
                        "updated_at": now,
                    },
                    "$push": {"payment_history": payment_record},
                }
            )

            updated = await self.scheduled_payments.find_one({"_id": ObjectId(milestone_id)})
            return self._serialize_payment(updated)

        except Exception as e:
            logger.error(f"Failed to record milestone payment: {str(e)}")
            raise

    async def get_contract_form_data(
        self,
        contract_id: str,
        planner_id: str,
    ) -> Dict:
        """
        Get form data submissions for a contract's vendor.

        Returns vendor form submissions that can be applied to the contract.
        """
        try:
            contract = await self.contracts.find_one({
                "_id": ObjectId(contract_id),
                "planner_id": planner_id
            })
            if not contract:
                raise ValueError("Contract not found")

            vendor_profile_id = contract.get("vendor_profile_id")
            if not vendor_profile_id:
                return {"vendor_submissions": [], "available_fields": {}, "suggested_contract_fields": {}}

            # Look up vendor form submissions
            submissions_collection = mongo.db["vendor_form_submissions"]
            submissions = await submissions_collection.find({
                "vendor_profile_id": vendor_profile_id
            }).to_list(length=None)

            # Serialize
            serialized_submissions = []
            for sub in submissions:
                sub["_id"] = str(sub["_id"])
                serialized_submissions.append(sub)

            return {
                "vendor_submissions": serialized_submissions,
                "available_fields": {},
                "suggested_contract_fields": {},
            }

        except Exception as e:
            logger.error(f"Failed to get contract form data: {str(e)}")
            raise

    def _serialize_contract(self, contract: Optional[Dict]) -> Optional[Dict]:
        """Serialize contract for API response."""
        if not contract:
            return None

        serialized = {**contract}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            serialized["_id"] = str(serialized["_id"])

        if "couple" in serialized:
            serialized["couple"] = self._normalize_couple(serialized.get("couple"))

        # Convert dates to ISO format
        for date_field in ["wedding_date", "sent_at", "viewed_at", "signed_at",
                           "completed_at", "cancelled_at", "created_at", "updated_at"]:
            if date_field in serialized and serialized[date_field]:
                if hasattr(serialized[date_field], "isoformat"):
                    serialized[date_field] = serialized[date_field].isoformat()

        # Serialize nested datetime fields in sections
        if "sections" in serialized and isinstance(serialized["sections"], list):
            for section in serialized["sections"]:
                if isinstance(section, dict):
                    for date_field in ["created_at", "updated_at"]:
                        if date_field in section and section[date_field]:
                            if hasattr(section[date_field], "isoformat"):
                                section[date_field] = section[date_field].isoformat()

        # Serialize nested datetime fields in scheduled payments/milestones
        if "scheduled_payments" in serialized and isinstance(serialized["scheduled_payments"], list):
            for payment in serialized["scheduled_payments"]:
                if isinstance(payment, dict):
                    for date_field in ["due_date", "last_attempt_at", "next_retry_at",
                                     "paid_at", "reminder_sent_at", "created_at", "updated_at"]:
                        if date_field in payment and payment[date_field]:
                            if hasattr(payment[date_field], "isoformat"):
                                payment[date_field] = payment[date_field].isoformat()

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
