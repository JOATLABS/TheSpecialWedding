"""
Package Service

CRUD operations for wedding service packages.
Handles package lifecycle from creation to sending to couples.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from bson import ObjectId

from app.core.database import mongo
from app.core.settings import settings
from app.models.autopilot import Contract, CoupleInfo, WeddingPackage
from app.utils.mongo_dates import to_mongo_datetime
from app.utils.payment_schedule import build_effective_payment_schedule

logger = logging.getLogger(__name__)

# Initialize Stripe
if settings.stripe_enabled and settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key
else:
    logger.warning("Stripe is not enabled or API key is missing")


class PackageService:
    """
    Service for managing wedding packages.

    Packages are reusable templates that define services and payment schedules.
    They can be sent to couples to create contracts.
    """

    def __init__(self):
        self.packages = mongo.db["packages"]
        self.contracts = mongo.db["contracts"]
        self.users = mongo.db["users"]
        self.weddings = mongo.db["weddings"]
        self.scheduled_payments = mongo.db["scheduled_payments"]

    @staticmethod
    def _build_planner_snapshot(
        planner: Optional[Dict[str, Any]],
    ) -> Dict[str, Optional[str]]:
        planner = planner or {}
        planner_name = (
            planner.get("company_name")
            or planner.get("business_name")
            or planner.get("name")
            or " ".join(
                part
                for part in [planner.get("first_name"), planner.get("last_name")]
                if part
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

    async def create_package(self, planner_id: str, package_data: Dict) -> Dict:
        """
        Create a new package for a planner.

        Args:
            planner_id: The planner's user ID
            package_data: Package details including name, services, total_amount, etc.

        Returns:
            Created package dict with ID
        """
        try:
            # Keep total_amount as float for MongoDB BSON compatibility
            # (BSON cannot encode Python Decimal, only float or Decimal128)
            if "total_amount" in package_data:
                package_data["total_amount"] = float(package_data["total_amount"])

            package = WeddingPackage(planner_id=planner_id, **package_data)

            package_dict = package.model_dump(by_alias=True)
            # Ensure total_amount is float for BSON serialization
            if "total_amount" in package_dict:
                package_dict["total_amount"] = float(package_dict["total_amount"])
            result = await self.packages.insert_one(package_dict)

            logger.info(f"Created package '{package.name}' for planner {planner_id}")

            # Return with string ID
            created = await self.packages.find_one({"_id": result.inserted_id})
            return self._serialize_package(created)

        except Exception as e:
            logger.error(f"Failed to create package: {str(e)}")
            raise

    async def get_package(
        self, package_id: str, planner_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get a package by ID.

        Args:
            package_id: The package ID
            planner_id: Optional planner ID to verify ownership

        Returns:
            Package dict or None if not found
        """
        try:
            query = {"_id": ObjectId(package_id)}
            if planner_id:
                query["planner_id"] = planner_id

            package = await self.packages.find_one(query)
            return self._serialize_package(package) if package else None

        except Exception as e:
            logger.error(f"Failed to get package: {str(e)}")
            raise

    async def list_packages(
        self,
        planner_id: str,
        include_templates: bool = False,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict]:
        """
        List packages for a planner.

        Args:
            planner_id: The planner's user ID
            include_templates: Include template packages
            status: Filter by status (draft, active, archived)
            limit: Maximum packages to return
            skip: Number of packages to skip

        Returns:
            List of package dicts
        """
        try:
            query = {"planner_id": planner_id}

            if not include_templates:
                query["is_template"] = {"$ne": True}

            if status:
                query["status"] = status

            cursor = (
                self.packages.find(query).sort("updated_at", -1).skip(skip).limit(limit)
            )
            packages = await cursor.to_list(length=limit)

            return [self._serialize_package(p) for p in packages]

        except Exception as e:
            logger.error(f"Failed to list packages: {str(e)}")
            raise

    async def update_package(
        self, package_id: str, planner_id: str, update_data: Dict
    ) -> Dict:
        """
        Update an existing package.

        Args:
            package_id: The package ID
            planner_id: The planner's ID (for ownership verification)
            update_data: Fields to update

        Returns:
            Updated package dict
        """
        try:
            # Verify ownership
            package = await self.packages.find_one(
                {"_id": ObjectId(package_id), "planner_id": planner_id}
            )

            if not package:
                raise ValueError("Package not found or access denied")

            # Restrict updates to non-draft packages
            if package.get("status") != "draft":
                allowed_fields = {
                    "status",
                    "description",
                    "custom_terms",
                    "cancellation_policy",
                }
                update_keys = set(update_data.keys())
                if not update_keys.issubset(allowed_fields):
                    raise ValueError(
                        f"Cannot modify active package structure. Allowed: {allowed_fields}"
                    )

            # Handle Decimal conversion
            if "total_amount" in update_data:
                update_data["total_amount"] = float(update_data["total_amount"])

            update_data["updated_at"] = datetime.now(timezone.utc)

            await self.packages.update_one(
                {"_id": ObjectId(package_id)}, {"$set": update_data}
            )

            updated = await self.packages.find_one({"_id": ObjectId(package_id)})
            logger.info(f"Updated package {package_id}")
            return self._serialize_package(updated)

        except Exception as e:
            logger.error(f"Failed to update package: {str(e)}")
            raise

    async def delete_package(self, package_id: str, planner_id: str) -> bool:
        """
        Delete a package (drafts only).

        Args:
            package_id: The package ID
            planner_id: The planner's ID

        Returns:
            True if deleted
        """
        try:
            package = await self.packages.find_one(
                {"_id": ObjectId(package_id), "planner_id": planner_id}
            )

            if not package:
                raise ValueError("Package not found or access denied")

            if package.get("status") != "draft":
                raise ValueError("Only draft packages can be deleted")

            # Check for associated contracts
            contract_count = await self.contracts.count_documents(
                {"package_id": package_id}
            )
            if contract_count > 0:
                raise ValueError(
                    f"Cannot delete package with {contract_count} associated contracts"
                )

            await self.packages.delete_one({"_id": ObjectId(package_id)})
            logger.info(f"Deleted package {package_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete package: {str(e)}")
            raise

    async def duplicate_package(
        self,
        package_id: str,
        planner_id: str,
        new_name: Optional[str] = None,
        as_template: bool = True,
    ) -> Dict:
        """
        Duplicate a package as a template.

        Args:
            package_id: Source package ID
            planner_id: The planner's ID
            new_name: Name for the new package
            as_template: Mark as template

        Returns:
            New package dict
        """
        try:
            package = await self.packages.find_one(
                {"_id": ObjectId(package_id), "planner_id": planner_id}
            )

            if not package:
                raise ValueError("Package not found or access denied")

            # Create new package data
            new_package_data = {
                k: v
                for k, v in package.items()
                if k not in ["_id", "created_at", "updated_at", "contracts_count"]
            }
            new_package_data["name"] = new_name or f"{package['name']} (Copy)"
            new_package_data["is_template"] = as_template
            new_package_data["status"] = "draft"
            new_package_data["contracts_count"] = 0

            return await self.create_package(planner_id, new_package_data)

        except Exception as e:
            logger.error(f"Failed to duplicate package: {str(e)}")
            raise

    async def send_to_couple(
        self,
        package_id: str,
        planner_id: str,
        couple_data: Dict,
        wedding_date: Optional[str] = None,
        wedding_id: Optional[str] = None,
    ) -> Dict:
        """
        Send a package to a couple, creating a contract.

        Args:
            package_id: The package ID
            planner_id: The planner's ID
            couple_data: Couple info (partner1_name, email, etc.)
            wedding_date: Optional wedding date
            wedding_id: Optional linked wedding ID

        Returns:
            Created contract dict
        """
        try:
            # Get package
            package = await self.packages.find_one(
                {"_id": ObjectId(package_id), "planner_id": planner_id}
            )

            if not package:
                raise ValueError("Package not found or access denied")

            if package.get("status") == "draft":
                raise ValueError("Cannot send draft package. Activate it first.")

            # Parse wedding date if provided
            from datetime import date as date_type

            parsed_wedding_date = None
            if wedding_date:
                if isinstance(wedding_date, str):
                    parsed_wedding_date = date_type.fromisoformat(wedding_date)
                else:
                    parsed_wedding_date = wedding_date

            wedding = None
            if wedding_id:
                wedding = await self.weddings.find_one({"_id": wedding_id})
                if wedding and not parsed_wedding_date and wedding.get("date"):
                    wedding_date_value = wedding.get("date")
                    if isinstance(wedding_date_value, str):
                        parsed_wedding_date = date_type.fromisoformat(
                            wedding_date_value
                        )
                    else:
                        parsed_wedding_date = wedding_date_value

            planner = None
            try:
                planner = await self.users.find_one({"_id": ObjectId(planner_id)})
            except Exception:
                planner = await self.users.find_one({"email": planner_id})

            planner_snapshot = self._build_planner_snapshot(planner)
            venue = None
            if wedding:
                venue = wedding.get("venue") or wedding.get("location")

            # Create couple info
            couple = CoupleInfo(**couple_data)

            # Generate secure token for public access
            token = secrets.token_urlsafe(32)

            # Create package snapshot
            package_snapshot = {
                "name": package["name"],
                "description": package.get("description"),
                "services": package.get("services", []),
                "total_amount": float(package["total_amount"]),
                "currency": package.get("currency", "usd"),
                "payment_schedule": build_effective_payment_schedule(package),
                "cancellation_policy": package.get("cancellation_policy", ""),
                "late_payment_policy": package.get("late_payment_policy"),
                "custom_terms": package.get("custom_terms"),
            }

            # Create contract
            contract = Contract(
                package_id=package_id,
                planner_id=planner_id,
                wedding_id=wedding_id,
                token=token,
                couple=couple,
                wedding_date=parsed_wedding_date,
                venue=venue,
                planner_name=planner_snapshot.get("planner_name"),
                planner_email=planner_snapshot.get("planner_email"),
                planner_phone=planner_snapshot.get("planner_phone"),
                planner_logo=planner_snapshot.get("planner_logo"),
                package_snapshot=package_snapshot,
                status="sent",
                sent_at=datetime.now(timezone.utc),
            )

            contract_dict = contract.model_dump(by_alias=True)
            contract_dict["wedding_date"] = to_mongo_datetime(contract.wedding_date)
            result = await self.contracts.insert_one(contract_dict)
            created = await self.contracts.find_one({"_id": result.inserted_id})
            serialized_contract = self._serialize_contract(created)
            if serialized_contract is None:
                raise ValueError("Failed to serialize created contract")

            from app.services.contract_email_service import contract_email_service

            email_sent = await contract_email_service.send_package_contract_email(
                serialized_contract
            )
            if not email_sent:
                await self.contracts.delete_one({"_id": result.inserted_id})
                raise RuntimeError("Failed to send contract email to the couple")

            # Increment package contracts count only after email succeeds
            await self.packages.update_one(
                {"_id": ObjectId(package_id)}, {"$inc": {"contracts_count": 1}}
            )

            logger.info(
                f"Created contract for package {package_id} sent to {couple.email}"
            )

            return serialized_contract

        except Exception as e:
            logger.error(f"Failed to send package: {str(e)}")
            raise

    async def get_package_stats(self, planner_id: str) -> Dict[str, Any]:
        """
        Get package statistics for a planner.

        Returns:
            Dict with package counts and stats
        """
        try:
            pipeline = [
                {"$match": {"planner_id": planner_id}},
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "total_contracts": {"$sum": "$contracts_count"},
                    }
                },
            ]

            stats = await self.packages.aggregate(pipeline).to_list(length=None)

            return {
                "by_status": {s["_id"]: s["count"] for s in stats},
                "total_packages": sum(s["count"] for s in stats),
                "total_contracts": sum(s["total_contracts"] for s in stats),
            }

        except Exception as e:
            logger.error(f"Failed to get package stats: {str(e)}")
            raise

    def _serialize_package(self, package: Dict) -> Optional[Dict]:
        """Serialize package for API response."""
        if not package:
            return None

        serialized = {**package}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            serialized["_id"] = str(serialized["_id"])

        # Convert Decimal to float for JSON
        if "total_amount" in serialized:
            serialized["total_amount"] = float(serialized["total_amount"])

        return serialized

    def _serialize_contract(self, contract: Dict) -> Optional[Dict]:
        """Serialize contract for API response."""
        if not contract:
            return None

        serialized = {**contract}
        if "_id" in serialized:
            serialized["id"] = str(serialized["_id"])
            serialized["_id"] = str(serialized["_id"])

        if (
            "wedding_date" in serialized
            and serialized["wedding_date"]
            and hasattr(serialized["wedding_date"], "isoformat")
        ):
            serialized["wedding_date"] = serialized["wedding_date"].isoformat()

        couple = serialized.get("couple")
        if isinstance(couple, dict):
            partner1 = (couple.get("partner1_name") or couple.get("name") or "").strip()
            partner2 = (
                couple.get("partner2_name") or couple.get("partner_name") or ""
            ).strip()
            display_name = f"{partner1} & {partner2}" if partner2 else partner1
            normalized_couple = {
                **couple,
                "partner1_name": partner1,
                "partner2_name": partner2 or None,
                "name": partner1,
                "partner_name": partner2 or None,
                "display_name": display_name,
            }
            serialized["couple"] = normalized_couple

        return serialized

    async def pause_planner_payment_links(
        self, planner_id: str, planner_email: str
    ) -> Dict[str, Any]:
        """
        Pause all active payment links AND scheduled payments for a planner
        when their subscription is cancelled.

        Targets two separate payment systems:
        1. `payment_links` collection — standalone Stripe Payment Links created via
           vendor_service (field: `stripe_payment_link_id`). Deactivated via Stripe API.
        2. `scheduled_payments` collection — autopilot contract payments (field:
           `stripe_payment_intent_id`). Marked as paused locally (no Stripe link to deactivate).

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with payment_links_deactivated, scheduled_payments_paused, contracts_paused, errors
        """
        from app.core.database import mongo

        try:
            now = datetime.now(timezone.utc)
            links_deactivated = 0
            scheduled_paused = 0
            contracts_paused = set()
            errors = []

            # ── Part 1: Deactivate Stripe Payment Links (payment_links collection) ──
            # These are standalone links created by the planner via vendor_service.
            # Model: PaymentLink (vendor.py) — has `stripe_payment_link_id`, `created_by`.
            payment_links_coll = mongo.db["payment_links"]
            active_links = await payment_links_coll.find(
                {
                    "created_by": planner_email,
                    "status": {"$in": ["draft", "sent", "viewed"]},
                    "stripe_payment_link_id": {"$exists": True, "$ne": None},
                }
            ).to_list(length=10000)

            for link in active_links:
                stripe_pl_id = link.get("stripe_payment_link_id")
                try:
                    # Retrieve current state to avoid modifying already-inactive links
                    # (Stripe best practice: check state before mutating)
                    try:
                        pl_obj = stripe.PaymentLink.retrieve(stripe_pl_id)
                        if (
                            not pl_obj.get("active", True)
                            if isinstance(pl_obj, dict)
                            else not getattr(pl_obj, "active", True)
                        ):
                            logger.info(
                                f"PaymentLink {stripe_pl_id} already inactive, skipping"
                            )
                            links_deactivated += 1
                            continue
                    except stripe.error.StripeError as retrieve_err:
                        logger.warning(
                            f"Could not retrieve PaymentLink {stripe_pl_id}, attempting modify anyway: {retrieve_err}"
                        )

                    stripe.PaymentLink.modify(stripe_pl_id, active=False)
                    links_deactivated += 1
                    logger.info(f"Deactivated Stripe PaymentLink {stripe_pl_id}")
                except stripe.error.InvalidRequestError as e:
                    # Link may already be inactive or deleted — log and continue
                    logger.warning(
                        f"Stripe InvalidRequestError deactivating PaymentLink {stripe_pl_id}: {e}"
                    )
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": True,
                        }
                    )
                except stripe.error.StripeError as e:
                    error_msg = f"Stripe API error deactivating PaymentLink {stripe_pl_id}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": False,
                        }
                    )
                except Exception as e:
                    error_msg = f"Unexpected error deactivating PaymentLink {stripe_pl_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": False,
                        }
                    )

            # Bulk-stamp all matched links as paused
            if active_links:
                link_ids = [link["_id"] for link in active_links]
                await payment_links_coll.update_many(
                    {"_id": {"$in": link_ids}},
                    {
                        "$set": {
                            "payment_paused_at": now,
                            "payment_paused_reason": "planner_subscription_cancelled",
                            "updated_at": now,
                        }
                    },
                )

            # ── Part 2: Pause scheduled payments (scheduled_payments collection) ──
            # These are autopilot contract payments (ScheduledPayment model in autopilot.py).
            # They use `stripe_payment_intent_id`, NOT payment links.
            # We mark them as paused locally so the autopilot cron skips them.
            scheduled_result = await self.scheduled_payments.update_many(
                {
                    "planner_id": planner_id,
                    "status": {"$in": ["scheduled", "processing"]},
                },
                {
                    "$set": {
                        "payment_paused_at": now,
                        "payment_paused_reason": "planner_subscription_cancelled",
                    }
                },
            )
            scheduled_paused = scheduled_result.modified_count

            # Gather affected contract IDs for reporting
            if scheduled_paused > 0:
                paused_docs = await self.scheduled_payments.find(
                    {
                        "planner_id": planner_id,
                        "payment_paused_reason": "planner_subscription_cancelled",
                    },
                    {"contract_id": 1},
                ).to_list(length=10000)
                contracts_paused = {
                    doc.get("contract_id")
                    for doc in paused_docs
                    if doc.get("contract_id")
                }

            logger.info(
                f"Paused payments for planner {planner_id}: "
                f"{links_deactivated} payment links, {scheduled_paused} scheduled payments, "
                f"{len(contracts_paused)} contracts affected"
            )

            return {
                "payment_links_deactivated": links_deactivated,
                "scheduled_payments_paused": scheduled_paused,
                "contracts_paused": len(contracts_paused),
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to pause planner payment links: {str(e)}")
            raise

    async def resume_planner_payment_links(
        self, planner_id: str, planner_email: str
    ) -> Dict[str, Any]:
        """
        Resume all paused payment links AND scheduled payments for a planner
        when their subscription is reactivated.

        Reverses the actions of `pause_planner_payment_links`.

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with payment_links_reactivated, scheduled_payments_resumed, contracts_resumed, errors
        """
        from app.core.database import mongo

        try:
            now = datetime.now(timezone.utc)
            links_reactivated = 0
            scheduled_resumed = 0
            errors = []

            # ── Part 1: Reactivate Stripe Payment Links ──
            payment_links_coll = mongo.db["payment_links"]
            paused_links = await payment_links_coll.find(
                {
                    "created_by": planner_email,
                    "payment_paused_reason": "planner_subscription_cancelled",
                    "stripe_payment_link_id": {"$exists": True, "$ne": None},
                }
            ).to_list(length=10000)

            for link in paused_links:
                stripe_pl_id = link.get("stripe_payment_link_id")
                try:
                    # Retrieve current state to avoid modifying already-active links
                    try:
                        pl_obj = stripe.PaymentLink.retrieve(stripe_pl_id)
                        if (
                            pl_obj.get("active", False)
                            if isinstance(pl_obj, dict)
                            else getattr(pl_obj, "active", False)
                        ):
                            logger.info(
                                f"PaymentLink {stripe_pl_id} already active, skipping"
                            )
                            links_reactivated += 1
                            continue
                    except stripe.error.StripeError as retrieve_err:
                        logger.warning(
                            f"Could not retrieve PaymentLink {stripe_pl_id}, attempting modify anyway: {retrieve_err}"
                        )

                    stripe.PaymentLink.modify(stripe_pl_id, active=True)
                    links_reactivated += 1
                    logger.info(f"Reactivated Stripe PaymentLink {stripe_pl_id}")
                except stripe.error.InvalidRequestError as e:
                    logger.warning(
                        f"Stripe InvalidRequestError reactivating PaymentLink {stripe_pl_id}: {e}"
                    )
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": True,
                        }
                    )
                except stripe.error.StripeError as e:
                    error_msg = f"Stripe API error reactivating PaymentLink {stripe_pl_id}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": False,
                        }
                    )
                except Exception as e:
                    error_msg = f"Unexpected error reactivating PaymentLink {stripe_pl_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(
                        {
                            "payment_link_id": stripe_pl_id,
                            "error": str(e),
                            "recoverable": False,
                        }
                    )

            # Clear pause fields from payment links
            if paused_links:
                link_ids = [link["_id"] for link in paused_links]
                await payment_links_coll.update_many(
                    {"_id": {"$in": link_ids}},
                    {
                        "$unset": {
                            "payment_paused_at": "",
                            "payment_paused_reason": "",
                        },
                        "$set": {"updated_at": now},
                    },
                )

            # ── Part 2: Resume scheduled payments ──
            scheduled_result = await self.scheduled_payments.update_many(
                {
                    "planner_id": planner_id,
                    "payment_paused_reason": "planner_subscription_cancelled",
                },
                {
                    "$unset": {"payment_paused_at": "", "payment_paused_reason": ""},
                },
            )
            scheduled_resumed = scheduled_result.modified_count

            logger.info(
                f"Resumed payments for planner {planner_id}: "
                f"{links_reactivated} payment links, {scheduled_resumed} scheduled payments"
            )

            return {
                "payment_links_reactivated": links_reactivated,
                "scheduled_payments_resumed": scheduled_resumed,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to resume planner payment links: {str(e)}")
            raise


# Singleton instance
package_service = PackageService()
