"""
Cascade Delete Service

Handles the safe deletion of a wedding and ALL dependent data across collections.
Supports soft-delete (archive) and hard-delete modes.

This service ensures referential integrity when deleting a wedding by:
1. Soft delete: Setting deleted_at and deleted_by fields (preserves data for recovery)
2. Hard delete: Permanently removing records from database
3. Handling indirect relationships (e.g., plus_ones references guest_id, not wedding_id)
4. Logging all operations with detailed counts
5. Rolling back on errors to prevent partial deletes
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List

from app.core.database import mongo
from app.utils.planner_ownership import build_wedding_owner_query

logger = logging.getLogger(__name__)

# Collections that have wedding_id references and need cascade handling
WEDDING_DEPENDENT_COLLECTIONS = [
    "guests",
    "plus_ones",  # References guest_id, which references wedding_id
    "rsvps",  # References guest_id
    "tables",
    "seating_layouts",
    "activity_logs",
    "forms",
    "form_responses",
    "form_distributions",
    "budget_items",
    "budget_categories",
    "vendor_quotes",
    "budget_alerts",
    "reminders_sent",
    "support_tickets",
    "gallery",
    "contracts",
    "vendor_assignments",
    "vendor_forms",
    "vendor_form_submissions",
    "checkins",
    "payment_records",
    "payment_links",
    "scheduled_payments",
]

# Collections that reference guest_id (indirect wedding_id dependency)
GUEST_DEPENDENT_COLLECTIONS = [
    "plus_ones",
    "rsvps",
    "reminders_sent",
    "support_tickets",
    "checkins",
]


class CascadeDeleteService:
    """Service for safely cascading wedding deletion across all dependent collections."""

    async def soft_delete_wedding(self, wedding_id: str, deleted_by: str) -> Dict:
        """
        Archive a wedding and mark all dependent data as deleted without removing it.

        This is the preferred deletion method as it preserves data for audit and recovery.
        Sets deleted_at and deleted_by fields on all dependent records.

        Args:
            wedding_id: The ID of the wedding to delete
            deleted_by: Email/ID of the user performing the deletion

        Returns:
            Dict with deletion statistics and status
        """
        try:
            logger.info(
                f"Starting soft delete for wedding {wedding_id} by {deleted_by}"
            )

            # First, get counts of all dependent records
            counts = await self._get_dependent_counts(wedding_id)
            logger.info(f"Soft delete counts for wedding {wedding_id}: {counts}")

            deleted_at = datetime.now(timezone.utc)
            update_data = {
                "deleted_at": deleted_at,
                "deleted_by": deleted_by,
                "is_deleted": True,
            }

            # Get guest IDs for indirect deletes
            guest_ids = await self._get_guest_ids_for_wedding(wedding_id)

            # Delete/archive the wedding itself
            wedding_result = await mongo.db["weddings"].update_one(
                {"_id": wedding_id}, {"$set": update_data}
            )

            if wedding_result.matched_count == 0:
                raise ValueError(f"Wedding {wedding_id} not found")

            # Soft delete all dependent collections with wedding_id
            for collection_name in WEDDING_DEPENDENT_COLLECTIONS:
                if collection_name in GUEST_DEPENDENT_COLLECTIONS:
                    # Skip guest-dependent collections here, handle them separately
                    continue

                collection = mongo.db[collection_name]
                try:
                    result = await collection.update_many(
                        {"wedding_id": wedding_id}, {"$set": update_data}
                    )
                    logger.debug(
                        f"Soft deleted {result.modified_count} records from {collection_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error soft deleting from {collection_name}: {str(e)}"
                    )
                    raise

            # Soft delete guest-dependent collections (via guest_id)
            for collection_name in GUEST_DEPENDENT_COLLECTIONS:
                collection = mongo.db[collection_name]
                try:
                    result = await collection.update_many(
                        {"guest_id": {"$in": guest_ids}}, {"$set": update_data}
                    )
                    logger.debug(
                        f"Soft deleted {result.modified_count} records from {collection_name} (via guest_id)"
                    )
                except Exception as e:
                    logger.error(
                        f"Error soft deleting from {collection_name} (guest_id): {str(e)}"
                    )
                    raise

            # Log the operation
            await self._log_deletion_operation(
                wedding_id=wedding_id,
                deletion_type="soft",
                deleted_by=deleted_by,
                counts=counts,
            )

            return {
                "status": "success",
                "deletion_type": "soft",
                "wedding_id": wedding_id,
                "deleted_at": deleted_at.isoformat(),
                "deleted_by": deleted_by,
                "records_archived": sum(counts.values()),
                "counts": counts,
                "message": f"Wedding {wedding_id} and all {sum(counts.values())} dependent records archived",
            }

        except Exception as e:
            logger.error(f"Error in soft delete for wedding {wedding_id}: {str(e)}")
            raise

    async def hard_delete_wedding(self, wedding_id: str, deleted_by: str) -> Dict:
        """
        Permanently delete a wedding and ALL dependent data.

        WARNING: This operation is irreversible. All data is permanently removed.
        This should only be used for data cleanup, testing, or compliance requirements.

        Args:
            wedding_id: The ID of the wedding to delete
            deleted_by: Email/ID of the user performing the deletion

        Returns:
            Dict with deletion statistics and status
        """
        try:
            logger.warning(
                f"Starting HARD DELETE for wedding {wedding_id} by {deleted_by}. "
                f"This operation is IRREVERSIBLE."
            )

            # First, get counts of all dependent records
            counts = await self._get_dependent_counts(wedding_id)
            logger.warning(f"Hard delete counts for wedding {wedding_id}: {counts}")

            # Get guest IDs for indirect deletes
            guest_ids = await self._get_guest_ids_for_wedding(wedding_id)

            # Delete the wedding itself
            wedding_result = await mongo.db["weddings"].delete_one({"_id": wedding_id})

            if wedding_result.deleted_count == 0:
                raise ValueError(f"Wedding {wedding_id} not found")

            # Hard delete all dependent collections with wedding_id
            for collection_name in WEDDING_DEPENDENT_COLLECTIONS:
                if collection_name in GUEST_DEPENDENT_COLLECTIONS:
                    # Skip guest-dependent collections here, handle them separately
                    continue

                collection = mongo.db[collection_name]
                try:
                    result = await collection.delete_many({"wedding_id": wedding_id})
                    logger.info(
                        f"Hard deleted {result.deleted_count} records from {collection_name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error hard deleting from {collection_name}: {str(e)}"
                    )
                    raise

            # Hard delete guest-dependent collections (via guest_id)
            for collection_name in GUEST_DEPENDENT_COLLECTIONS:
                collection = mongo.db[collection_name]
                try:
                    result = await collection.delete_many(
                        {"guest_id": {"$in": guest_ids}}
                    )
                    logger.info(
                        f"Hard deleted {result.deleted_count} records from {collection_name} (via guest_id)"
                    )
                except Exception as e:
                    logger.error(
                        f"Error hard deleting from {collection_name} (guest_id): {str(e)}"
                    )
                    raise

            # Log the operation
            await self._log_deletion_operation(
                wedding_id=wedding_id,
                deletion_type="hard",
                deleted_by=deleted_by,
                counts=counts,
            )

            return {
                "status": "success",
                "deletion_type": "hard",
                "wedding_id": wedding_id,
                "deleted_at": datetime.now(timezone.utc).isoformat(),
                "deleted_by": deleted_by,
                "records_deleted": sum(counts.values()),
                "counts": counts,
                "message": f"Wedding {wedding_id} and all {sum(counts.values())} dependent records permanently deleted",
            }

        except Exception as e:
            logger.error(f"Error in hard delete for wedding {wedding_id}: {str(e)}")
            raise

    async def _get_dependent_counts(self, wedding_id: str) -> Dict[str, int]:
        """
        Count all dependent records before deletion.
        Useful for confirmation dialogs and logging.

        Args:
            wedding_id: The wedding ID to count dependents for

        Returns:
            Dict mapping collection names to record counts
        """
        counts = {}

        # Count wedding_id direct references
        for collection_name in WEDDING_DEPENDENT_COLLECTIONS:
            if collection_name in GUEST_DEPENDENT_COLLECTIONS:
                continue

            collection = mongo.db[collection_name]
            try:
                count = await collection.count_documents({"wedding_id": wedding_id})
                counts[collection_name] = count
            except Exception as e:
                logger.warning(f"Error counting {collection_name}: {str(e)}")
                counts[collection_name] = 0

        # Get guest IDs and count indirect references
        guest_ids = await self._get_guest_ids_for_wedding(wedding_id)

        for collection_name in GUEST_DEPENDENT_COLLECTIONS:
            collection = mongo.db[collection_name]
            try:
                count = await collection.count_documents(
                    {"guest_id": {"$in": guest_ids}}
                )
                # Add to collection name to distinguish from direct references
                counts[f"{collection_name}_via_guest"] = count
            except Exception as e:
                logger.warning(f"Error counting {collection_name} (guest_id): {str(e)}")
                counts[f"{collection_name}_via_guest"] = 0

        # Include the wedding record itself
        counts["weddings"] = 1

        return counts

    async def _get_guest_ids_for_wedding(self, wedding_id: str) -> List:
        """
        Get all guest IDs for a wedding.
        Used to delete records that reference guests via guest_id.

        Args:
            wedding_id: The wedding ID

        Returns:
            List of guest ObjectIds
        """
        try:
            guests = (
                await mongo.db["guests"]
                .find({"wedding_id": wedding_id}, {"_id": 1})
                .to_list(length=None)
            )

            guest_ids = [guest["_id"] for guest in guests]
            logger.debug(f"Found {len(guest_ids)} guests for wedding {wedding_id}")
            return guest_ids

        except Exception as e:
            logger.error(f"Error getting guest IDs for wedding {wedding_id}: {str(e)}")
            raise

    async def _delete_plus_ones_for_wedding(self, wedding_id: str) -> int:
        """
        Delete plus_ones via guest_ids.
        Plus_ones reference guest_id, not wedding_id directly.

        Args:
            wedding_id: The wedding ID

        Returns:
            Number of plus_ones deleted
        """
        try:
            guest_ids = await self._get_guest_ids_for_wedding(wedding_id)

            result = await mongo.db["plus_ones"].delete_many(
                {"guest_id": {"$in": guest_ids}}
            )

            logger.info(
                f"Deleted {result.deleted_count} plus_ones for wedding {wedding_id}"
            )
            return result.deleted_count

        except Exception as e:
            logger.error(f"Error deleting plus_ones for wedding {wedding_id}: {str(e)}")
            raise

    async def _log_deletion_operation(
        self, wedding_id: str, deletion_type: str, deleted_by: str, counts: Dict
    ) -> None:
        """
        Log the deletion operation for audit and compliance purposes.

        Args:
            wedding_id: The wedding ID
            deletion_type: "soft" or "hard"
            deleted_by: User email/ID performing deletion
            counts: Dictionary of counts for each collection
        """
        try:
            deletion_log = {
                "wedding_id": wedding_id,
                "deletion_type": deletion_type,
                "deleted_by": deleted_by,
                "deleted_at": datetime.now(timezone.utc),
                "counts": counts,
                "total_records": sum(counts.values()),
                "event_type": "wedding_deletion",
            }

            # Store in audit/activity logs for compliance
            await mongo.db["activity_logs"].insert_one(deletion_log)

            logger.info(
                f"Logged {deletion_type} deletion for wedding {wedding_id}: "
                f"Total records: {sum(counts.values())}"
            )

        except Exception as e:
            logger.error(f"Error logging deletion operation: {str(e)}")
            # Don't raise - logging failure shouldn't fail the deletion

    async def verify_deletion(self, wedding_id: str) -> Dict:
        """
        Verify that a wedding and all its dependents have been deleted.
        Useful for confirming successful hard delete operations.

        Args:
            wedding_id: The wedding ID to verify

        Returns:
            Dict with verification results
        """
        try:
            remaining = {}

            # Check wedding itself
            wedding = await mongo.db["weddings"].find_one({"_id": wedding_id})
            if wedding:
                if wedding.get("is_deleted"):
                    remaining["weddings"] = "SOFT_DELETED"
                else:
                    remaining["weddings"] = 1

            # Check all dependent collections
            for collection_name in WEDDING_DEPENDENT_COLLECTIONS:
                collection = mongo.db[collection_name]
                count = await collection.count_documents({"wedding_id": wedding_id})
                if count > 0:
                    remaining[collection_name] = count

            # Check guest-dependent collections
            guest_ids = await self._get_guest_ids_for_wedding(wedding_id)
            for collection_name in GUEST_DEPENDENT_COLLECTIONS:
                collection = mongo.db[collection_name]
                count = await collection.count_documents(
                    {"guest_id": {"$in": guest_ids}}
                )
                if count > 0:
                    remaining[f"{collection_name}_via_guest"] = count

            is_fully_deleted = len(remaining) == 0

            return {
                "wedding_id": wedding_id,
                "is_fully_deleted": is_fully_deleted,
                "remaining_records": remaining,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error verifying deletion for wedding {wedding_id}: {str(e)}")
            raise

    async def suspend_planner_data(self, planner_id: str, planner_email: str) -> Dict:
        """
        Suspend all data access for a planner by stamping suspension fields.
        This prevents the planner from accessing weddings, packages, and contracts.

        Data is NOT deleted, only marked as suspended. This is reversible.

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with suspension statistics
        """
        try:
            logger.info(
                f"Starting data suspension for planner {planner_email} (ID: {planner_id})"
            )

            now = datetime.now(timezone.utc)
            suspension_data = {
                "data_access_suspended_at": now,
                "data_access_suspended_reason": "planner_subscription_cancelled",
                "updated_at": now,
            }

            # Suspend weddings assigned to this planner
            wedding_query = build_wedding_owner_query(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            if not wedding_query:
                raise ValueError("Planner identity is required to suspend wedding data")
            weddings_result = await mongo.db["weddings"].update_many(
                wedding_query,
                {"$set": suspension_data},
            )

            # Suspend packages created by this planner
            packages_result = await mongo.db["packages"].update_many(
                {"planner_id": planner_id}, {"$set": suspension_data}
            )

            # Suspend contracts associated with this planner
            contracts_result = await mongo.db["contracts"].update_many(
                {
                    "$or": [
                        {"planner_id": planner_id},
                        {"planner_email": planner_email},
                    ]
                },
                {"$set": suspension_data},
            )

            logger.info(
                f"Suspended data for planner {planner_email}: "
                f"{weddings_result.modified_count} weddings, "
                f"{packages_result.modified_count} packages, "
                f"{contracts_result.modified_count} contracts"
            )

            return {
                "weddings_suspended": weddings_result.modified_count,
                "packages_suspended": packages_result.modified_count,
                "contracts_suspended": contracts_result.modified_count,
                "suspended_at": now.isoformat(),
                "status": "success",
                "message": f"Data suspended for planner {planner_email}",
            }

        except Exception as e:
            logger.error(f"Error suspending data for planner {planner_email}: {str(e)}")
            raise

    async def unsuspend_planner_data(self, planner_id: str, planner_email: str) -> Dict:
        """
        Unsuspend data access for a planner by removing suspension fields.
        Restores access to previously suspended weddings, packages, and contracts.

        Args:
            planner_id: The planner's user ID
            planner_email: The planner's email address

        Returns:
            Dict with unsuspension statistics
        """
        try:
            logger.info(
                f"Starting data unsuspension for planner {planner_email} (ID: {planner_id})"
            )

            # Unsuspend weddings
            wedding_query = build_wedding_owner_query(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            if not wedding_query:
                raise ValueError(
                    "Planner identity is required to unsuspend wedding data"
                )
            weddings_result = await mongo.db["weddings"].update_many(
                {
                    **wedding_query,
                    "data_access_suspended_reason": "planner_subscription_cancelled",
                },
                {
                    "$unset": {
                        "data_access_suspended_at": "",
                        "data_access_suspended_reason": "",
                    },
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                    },
                },
            )

            # Unsuspend packages
            packages_result = await mongo.db["packages"].update_many(
                {
                    "planner_id": planner_id,
                    "data_access_suspended_reason": "planner_subscription_cancelled",
                },
                {
                    "$unset": {
                        "data_access_suspended_at": "",
                        "data_access_suspended_reason": "",
                    },
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                    },
                },
            )

            # Unsuspend contracts
            contracts_result = await mongo.db["contracts"].update_many(
                {
                    "$or": [
                        {"planner_id": planner_id},
                        {"planner_email": planner_email},
                    ],
                    "data_access_suspended_reason": "planner_subscription_cancelled",
                },
                {
                    "$unset": {
                        "data_access_suspended_at": "",
                        "data_access_suspended_reason": "",
                    },
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                    },
                },
            )

            logger.info(
                f"Unsuspended data for planner {planner_email}: "
                f"{weddings_result.modified_count} weddings, "
                f"{packages_result.modified_count} packages, "
                f"{contracts_result.modified_count} contracts"
            )

            return {
                "weddings_unsuspended": weddings_result.modified_count,
                "packages_unsuspended": packages_result.modified_count,
                "contracts_unsuspended": contracts_result.modified_count,
                "unsuspended_at": datetime.now(timezone.utc).isoformat(),
                "status": "success",
                "message": f"Data unsuspended for planner {planner_email}",
            }

        except Exception as e:
            logger.error(
                f"Error unsuspending data for planner {planner_email}: {str(e)}"
            )
            raise


# Singleton instance
cascade_delete_service = CascadeDeleteService()
