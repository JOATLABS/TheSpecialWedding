"""
Package Service

CRUD operations for wedding service packages.
Handles package lifecycle from creation to sending to couples.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal
import secrets
import logging
from bson import ObjectId
import stripe
from app.core.database import mongo
from app.core.settings import settings
from app.models.autopilot import WeddingPackage, Contract, CoupleInfo
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

            package = WeddingPackage(
                planner_id=planner_id,
                **package_data
            )

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
        self,
        package_id: str,
        planner_id: Optional[str] = None
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
        skip: int = 0
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

            cursor = self.packages.find(query).sort("updated_at", -1).skip(skip).limit(limit)
            packages = await cursor.to_list(length=limit)

            return [self._serialize_package(p) for p in packages]

        except Exception as e:
            logger.error(f"Failed to list packages: {str(e)}")
            raise

    async def update_package(
        self,
        package_id: str,
        planner_id: str,
        update_data: Dict
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
            package = await self.packages.find_one({
                "_id": ObjectId(package_id),
                "planner_id": planner_id
            })

            if not package:
                raise ValueError("Package not found or access denied")

            # Restrict updates to non-draft packages
            if package.get("status") != "draft":
                allowed_fields = {"status", "description", "custom_terms", "cancellation_policy"}
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
                {"_id": ObjectId(package_id)},
                {"$set": update_data}
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
            package = await self.packages.find_one({
                "_id": ObjectId(package_id),
                "planner_id": planner_id
            })

            if not package:
                raise ValueError("Package not found or access denied")

            if package.get("status") != "draft":
                raise ValueError("Only draft packages can be deleted")

            # Check for associated contracts
            contract_count = await self.contracts.count_documents({"package_id": package_id})
            if contract_count > 0:
                raise ValueError(f"Cannot delete package with {contract_count} associated contracts")

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
        as_template: bool = True
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
            package = await self.packages.find_one({
                "_id": ObjectId(package_id),
                "planner_id": planner_id
            })

            if not package:
                raise ValueError("Package not found or access denied")

            # Create new package data
            new_package_data = {
                k: v for k, v in package.items()
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
        wedding_id: Optional[str] = None
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
            package = await self.packages.find_one({
                "_id": ObjectId(package_id),
                "planner_id": planner_id
            })

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
                        parsed_wedding_date = date_type.fromisoformat(wedding_date_value)
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
                "custom_terms": package.get("custom_terms")
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
                sent_at=datetime.now(timezone.utc)
            )

            contract_dict = contract.model_dump(by_alias=True)
            contract_dict["wedding_date"] = to_mongo_datetime(contract.wedding_date)
            result = await self.contracts.insert_one(contract_dict)
            created = await self.contracts.find_one({"_id": result.inserted_id})
            serialized_contract = self._serialize_contract(created)
            if serialized_contract is None:
                raise ValueError("Failed to serialize created contract")

            from app.services.contract_email_service import contract_email_service

            email_sent = await contract_email_service.send_package_contract_email(serialized_contract)
            if not email_sent:
                await self.contracts.delete_one({"_id": result.inserted_id})
                raise RuntimeError("Failed to send contract email to the couple")

            # Increment package contracts count only after email succeeds
            await self.packages.update_one(
                {"_id": ObjectId(package_id)},
                {"$inc": {"contracts_count": 1}}
            )

            logger.info(f"Created contract for package {package_id} sent to {couple.email}")

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
                        "total_contracts": {"$sum": "$contracts_count"}
                    }
                }
            ]

            stats = await self.packages.aggregate(pipeline).to_list(length=None)

            return {
                "by_status": {s["_id"]: s["count"] for s in stats},
                "total_packages": sum(s["count"] for s in stats),
                "total_contracts": sum(s["total_contracts"] for s in stats)
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

        if "wedding_date" in serialized and serialized["wedding_date"] and hasattr(serialized["wedding_date"], "isoformat"):
            serialized["wedding_date"] = serialized["wedding_date"].isoformat()

        couple = serialized.get("couple")
        if isinstance(couple, dict):
            partner1 = (couple.get("partner1_name") or couple.get("name") or "").strip()
            partner2 = (couple.get("partner2_name") or couple.get("partner_name") or "").strip()
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

    async def pause_planner_payment_links(self, planner_id: str, planner_email: str) -> Dict[str, Any]:
        """
        Pause all active payment links for a planner when their subscription is cancelled.

        Finds all active contracts/packages for this planner that have pending payment schedule items,
        deactivates their Stripe payment links, and updates local records with pause metadata.

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with keys:
                - payment_links_deactivated: Number of payment links successfully deactivated
                - contracts_paused: Number of contracts affected
                - errors: List of error details for failed operations
        """
        try:
            deactivated_count = 0
            contracts_paused = set()
            errors = []

            # Find all active contracts for this planner
            active_contracts = await self.contracts.find(
                {
                    "planner_id": planner_id,
                    "status": {"$in": ["active", "signed", "viewed"]}
                }
            ).to_list(length=None)

            if not active_contracts:
                logger.info(f"No active contracts found for planner {planner_id}")
                return {
                    "payment_links_deactivated": 0,
                    "contracts_paused": 0,
                    "errors": []
                }

            # TODO: Confirm exact field name for Stripe payment link ID in scheduled_payments collection
            # Currently searching for stripe_payment_link_id or similar fields.
            # Payment link IDs may be stored in scheduled_payments documents linked via contract_id.

            for contract in active_contracts:
                contract_id = str(contract.get("_id"))

                # Find scheduled payments for this contract that have payment links
                scheduled_payments = await self.scheduled_payments.find(
                    {
                        "contract_id": contract_id,
                        "status": {"$in": ["scheduled", "processing"]}
                    }
                ).to_list(length=None)

                if not scheduled_payments:
                    continue

                for payment in scheduled_payments:
                    # TODO: Update field name based on actual schema for stripe payment link ID
                    payment_link_id = payment.get("stripe_payment_link_id")

                    if not payment_link_id:
                        continue

                    # Attempt to deactivate the payment link in Stripe
                    try:
                        stripe.PaymentLink.modify(payment_link_id, active=False)
                        deactivated_count += 1
                        logger.info(
                            f"Deactivated payment link {payment_link_id} for contract {contract_id}"
                        )
                    except stripe.error.StripeError as e:
                        error_msg = f"Failed to deactivate payment link {payment_link_id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({
                            "payment_link_id": payment_link_id,
                            "contract_id": contract_id,
                            "error": str(e)
                        })
                        continue

                    # Update local record to mark payment as paused
                    try:
                        await self.scheduled_payments.update_one(
                            {"_id": payment.get("_id")},
                            {
                                "$set": {
                                    "payment_paused_at": datetime.now(timezone.utc),
                                    "payment_paused_reason": "planner_subscription_cancelled"
                                }
                            }
                        )
                    except Exception as e:
                        error_msg = f"Failed to update payment record {payment.get('_id')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({
                            "payment_id": str(payment.get("_id")),
                            "contract_id": contract_id,
                            "error": str(e)
                        })

                contracts_paused.add(contract_id)

            logger.info(
                f"Paused {deactivated_count} payment links across {len(contracts_paused)} contracts for planner {planner_id}"
            )

            return {
                "payment_links_deactivated": deactivated_count,
                "contracts_paused": len(contracts_paused),
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Failed to pause planner payment links: {str(e)}")
            raise

    async def resume_planner_payment_links(self, planner_id: str, planner_email: str) -> Dict[str, Any]:
        """
        Resume all paused payment links for a planner when their subscription is reactivated.

        Finds all paused contracts/payments for this planner, reactivates their Stripe payment links,
        and clears pause metadata.

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with keys:
                - payment_links_reactivated: Number of payment links successfully reactivated
                - contracts_resumed: Number of contracts affected
                - errors: List of error details for failed operations
        """
        try:
            reactivated_count = 0
            contracts_resumed = set()
            errors = []

            # Find all contracts with paused payments for this planner
            paused_contracts = await self.contracts.find(
                {
                    "planner_id": planner_id,
                    "status": {"$in": ["active", "signed", "viewed"]}
                }
            ).to_list(length=None)

            if not paused_contracts:
                logger.info(f"No contracts found for planner {planner_id}")
                return {
                    "payment_links_reactivated": 0,
                    "contracts_resumed": 0,
                    "errors": []
                }

            # TODO: Confirm exact field name for Stripe payment link ID in scheduled_payments collection
            # Currently searching for stripe_payment_link_id or similar fields.
            # Payment link IDs may be stored in scheduled_payments documents linked via contract_id.

            for contract in paused_contracts:
                contract_id = str(contract.get("_id"))

                # Find paused scheduled payments for this contract
                paused_payments = await self.scheduled_payments.find(
                    {
                        "contract_id": contract_id,
                        "payment_paused_reason": "planner_subscription_cancelled",
                        "payment_paused_at": {"$exists": True}
                    }
                ).to_list(length=None)

                if not paused_payments:
                    continue

                for payment in paused_payments:
                    # TODO: Update field name based on actual schema for stripe payment link ID
                    payment_link_id = payment.get("stripe_payment_link_id")

                    if not payment_link_id:
                        continue

                    # Attempt to reactivate the payment link in Stripe
                    try:
                        stripe.PaymentLink.modify(payment_link_id, active=True)
                        reactivated_count += 1
                        logger.info(
                            f"Reactivated payment link {payment_link_id} for contract {contract_id}"
                        )
                    except stripe.error.StripeError as e:
                        error_msg = f"Failed to reactivate payment link {payment_link_id}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({
                            "payment_link_id": payment_link_id,
                            "contract_id": contract_id,
                            "error": str(e)
                        })
                        continue

                    # Clear pause fields from local record
                    try:
                        await self.scheduled_payments.update_one(
                            {"_id": payment.get("_id")},
                            {
                                "$unset": {
                                    "payment_paused_at": "",
                                    "payment_paused_reason": ""
                                }
                            }
                        )
                    except Exception as e:
                        error_msg = f"Failed to update payment record {payment.get('_id')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append({
                            "payment_id": str(payment.get("_id")),
                            "contract_id": contract_id,
                            "error": str(e)
                        })

                contracts_resumed.add(contract_id)

            logger.info(
                f"Resumed {reactivated_count} payment links across {len(contracts_resumed)} contracts for planner {planner_id}"
            )

            return {
                "payment_links_reactivated": reactivated_count,
                "contracts_resumed": len(contracts_resumed),
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Failed to resume planner payment links: {str(e)}")
            raise


# Singleton instance
package_service = PackageService()
