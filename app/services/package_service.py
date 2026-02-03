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
from app.core.database import mongo
from app.models.autopilot import WeddingPackage, Contract, CoupleInfo

logger = logging.getLogger(__name__)


class PackageService:
    """
    Service for managing wedding packages.

    Packages are reusable templates that define services and payment schedules.
    They can be sent to couples to create contracts.
    """

    def __init__(self):
        self.packages = mongo.db["packages"]
        self.contracts = mongo.db["contracts"]

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
            # Convert total_amount to Decimal if needed
            if "total_amount" in package_data:
                package_data["total_amount"] = Decimal(str(package_data["total_amount"]))

            package = WeddingPackage(
                planner_id=planner_id,
                **package_data
            )

            package_dict = package.model_dump(by_alias=True)
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
                "payment_schedule": package.get("payment_schedule", []),
                "cancellation_policy": package.get("cancellation_policy", ""),
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
                package_snapshot=package_snapshot,
                status="sent",
                sent_at=datetime.now(timezone.utc)
            )

            contract_dict = contract.model_dump(by_alias=True)
            result = await self.contracts.insert_one(contract_dict)

            # Increment package contracts count
            await self.packages.update_one(
                {"_id": ObjectId(package_id)},
                {"$inc": {"contracts_count": 1}}
            )

            logger.info(f"Created contract for package {package_id} sent to {couple.email}")

            # Return created contract
            created = await self.contracts.find_one({"_id": result.inserted_id})
            return self._serialize_contract(created)

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

        return serialized


# Singleton instance
package_service = PackageService()
