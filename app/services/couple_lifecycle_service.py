from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pymongo import UpdateOne

from app.core.database import mongo
from app.models.subscription import (
    PLANNER_BLOCKED_SUBSCRIPTION_STATUSES,
    normalize_subscription_status,
)
from app.utils.planner_ownership import (
    build_wedding_owner_query,
    extract_wedding_owner_identity,
    normalize_planner_email,
    normalize_planner_id,
    normalize_query_id,
    resolve_planner_identity,
)

COUPLE_PORTAL_STATE_PENDING_SETUP = "pending_setup"
COUPLE_PORTAL_STATE_ACTIVE = "active"
COUPLE_PORTAL_STATE_REVOKED = "revoked_by_planner"
COUPLE_PORTAL_STATE_OWNER_CANCELLED = "owner_cancelled"
COUPLE_PORTAL_STATE_ARCHIVED = "archived_readonly"

COUPLE_PORTAL_MUTABLE_STATES = {
    COUPLE_PORTAL_STATE_PENDING_SETUP,
    COUPLE_PORTAL_STATE_ACTIVE,
    COUPLE_PORTAL_STATE_REVOKED,
    COUPLE_PORTAL_STATE_OWNER_CANCELLED,
}

logger = logging.getLogger(__name__)


class CoupleLifecycleService:
    def __init__(self):
        self.couples_collection = mongo.db["couple_users"]
        self.weddings_collection = mongo.get_weddings_collection()
        self.users_collection = mongo.get_users_collection()
        self.subscriptions_collection = mongo.db["user_subscriptions"]

    def infer_stored_state(self, couple: Optional[dict]) -> str:
        """Infer the persisted couple-access state from explicit or legacy fields."""
        if not couple:
            return COUPLE_PORTAL_STATE_PENDING_SETUP

        explicit_state = couple.get("access_state")
        if explicit_state in COUPLE_PORTAL_MUTABLE_STATES:
            return explicit_state
        if couple.get("revoked_at") or couple.get("revoked_by"):
            return COUPLE_PORTAL_STATE_REVOKED
        if couple.get("owner_cancelled_at"):
            return COUPLE_PORTAL_STATE_OWNER_CANCELLED
        if not couple.get("setup_completed", False):
            return COUPLE_PORTAL_STATE_PENDING_SETUP
        if couple.get("is_active", False):
            return COUPLE_PORTAL_STATE_ACTIVE
        return COUPLE_PORTAL_STATE_REVOKED

    def restore_state_for_couple(self, couple: dict) -> tuple[str, bool]:
        """Return the correct restored mutable state for a couple record."""
        if couple.get("setup_completed", False):
            return COUPLE_PORTAL_STATE_ACTIVE, True
        return COUPLE_PORTAL_STATE_PENDING_SETUP, False

    async def _resolve_owner_identity(
        self, couple: dict, wedding: Optional[dict] = None
    ) -> dict:
        if wedding is None and couple.get("wedding_id"):
            wedding = await self.weddings_collection.find_one(
                {"_id": normalize_query_id(couple["wedding_id"])},
                {"assigned_planner_id": 1, "assigned_planner_email": 1},
            )

        owner_id, owner_email = extract_wedding_owner_identity(wedding)
        return await resolve_planner_identity(owner_id, owner_email)

    async def _owner_is_blocked(
        self, couple: dict, wedding: Optional[dict] = None
    ) -> bool:
        suspended_reason = (
            wedding.get("data_access_suspended_reason") if wedding else None
        )

        owner_identity = await self._resolve_owner_identity(couple, wedding=wedding)
        planner_id = owner_identity.get("planner_id")
        planner_email = owner_identity.get("planner_email")

        if planner_id:
            planner = await self.users_collection.find_one(
                {"_id": normalize_query_id(planner_id)},
                {"_id": 1, "email": 1, "is_active": 1, "subscription_status": 1},
            )
        elif planner_email:
            planner = await self.users_collection.find_one(
                {"email": planner_email},
                {"_id": 1, "email": 1, "is_active": 1, "subscription_status": 1},
            )
        else:
            planner = None

        if not planner:
            return True

        if not planner.get("is_active", True):
            return True

        sub_status = normalize_subscription_status(planner.get("subscription_status"))
        if sub_status in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES:
            return True

        planner_user_id = normalize_planner_id(planner.get("_id"))
        if planner_user_id:
            subscription_record = await self.subscriptions_collection.find_one(
                {"user_id": planner_user_id},
                {"status": 1},
            )
        if (
            subscription_record
            and normalize_subscription_status(subscription_record.get("status"))
            in PLANNER_BLOCKED_SUBSCRIPTION_STATUSES
        ):
            return True

        if suspended_reason == "planner_subscription_cancelled":
            logger.warning(
                "Ignoring stale wedding suspension flag for active planner %s on wedding %s",
                planner_user_id or planner.get("email"),
                couple.get("wedding_id"),
            )

        return False

    async def resolve_effective_state(
        self, couple: dict, wedding: Optional[dict] = None
    ) -> dict:
        """Resolve the effective portal state combining stored state and owner lifecycle."""
        stored_state = self.infer_stored_state(couple)

        if stored_state == COUPLE_PORTAL_STATE_REVOKED:
            return {
                "state": COUPLE_PORTAL_STATE_REVOKED,
                "stored_state": stored_state,
                "blocked": True,
                "detail": "Your planner has revoked access to this wedding portal. Please contact your planner.",
            }

        if stored_state == COUPLE_PORTAL_STATE_OWNER_CANCELLED:
            return {
                "state": COUPLE_PORTAL_STATE_OWNER_CANCELLED,
                "stored_state": stored_state,
                "blocked": True,
                "detail": "This wedding portal is unavailable because your planner's account is inactive. Please contact your planner.",
            }

        if await self._owner_is_blocked(couple, wedding=wedding):
            return {
                "state": COUPLE_PORTAL_STATE_OWNER_CANCELLED,
                "stored_state": stored_state,
                "blocked": True,
                "detail": "This wedding portal is unavailable because your planner's account is inactive. Please contact your planner.",
            }

        if couple.get("wedding_archived"):
            return {
                "state": COUPLE_PORTAL_STATE_ARCHIVED,
                "stored_state": stored_state,
                "blocked": False,
                "read_only": True,
                "detail": "This wedding has been archived. You can still view your wedding details.",
            }

        if stored_state == COUPLE_PORTAL_STATE_PENDING_SETUP:
            return {
                "state": COUPLE_PORTAL_STATE_PENDING_SETUP,
                "stored_state": stored_state,
                "blocked": True,
                "detail": "Please complete your account setup using the invitation link from your planner.",
            }

        return {
            "state": COUPLE_PORTAL_STATE_ACTIVE,
            "stored_state": stored_state,
            "blocked": False,
            "detail": None,
        }

    def build_setup_completed_update(self) -> dict[str, Any]:
        """State fields for a successfully set-up couple account."""
        now = datetime.now(timezone.utc)
        return {
            "is_active": True,
            "access_state": COUPLE_PORTAL_STATE_ACTIVE,
            "setup_completed": True,
            "setup_completed_at": now,
            "invite_token": None,
            "invite_token_expires": None,
            "updated_at": now,
            "revoked_at": None,
            "revoked_by": None,
            "owner_cancelled_at": None,
            "owner_cancelled_by_planner_id": None,
            "owner_cancelled_by_planner_email": None,
        }

    def build_revoke_update(self, actor_email: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "is_active": False,
            "access_state": COUPLE_PORTAL_STATE_REVOKED,
            "revoked_at": now,
            "revoked_by": actor_email,
            "owner_cancelled_at": None,
            "owner_cancelled_by_planner_id": None,
            "owner_cancelled_by_planner_email": None,
            "updated_at": now,
        }

    def build_manual_restore_update(self, couple: dict) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        restored_state, is_active = self.restore_state_for_couple(couple)
        return {
            "is_active": is_active,
            "access_state": restored_state,
            "revoked_at": None,
            "revoked_by": None,
            "owner_cancelled_at": None,
            "owner_cancelled_by_planner_id": None,
            "owner_cancelled_by_planner_email": None,
            "updated_at": now,
        }

    def build_owner_cancelled_update(
        self,
        couple: dict,
        planner_id: Optional[str],
        planner_email: Optional[str],
    ) -> Optional[dict[str, Any]]:
        stored_state = self.infer_stored_state(couple)
        if stored_state == COUPLE_PORTAL_STATE_REVOKED:
            return None

        now = datetime.now(timezone.utc)
        return {
            "is_active": False,
            "access_state": COUPLE_PORTAL_STATE_OWNER_CANCELLED,
            "owner_cancelled_at": now,
            "owner_cancelled_by_planner_id": normalize_planner_id(planner_id),
            "owner_cancelled_by_planner_email": normalize_planner_email(planner_email),
            "updated_at": now,
        }

    def build_owner_restore_update(self, couple: dict) -> Optional[dict[str, Any]]:
        if self.infer_stored_state(couple) != COUPLE_PORTAL_STATE_OWNER_CANCELLED:
            return None

        now = datetime.now(timezone.utc)
        restored_state, is_active = self.restore_state_for_couple(couple)
        return {
            "is_active": is_active,
            "access_state": restored_state,
            "owner_cancelled_at": None,
            "owner_cancelled_by_planner_id": None,
            "owner_cancelled_by_planner_email": None,
            "updated_at": now,
        }

    async def _owned_wedding_ids(
        self, planner_id: Optional[str], planner_email: Optional[str]
    ) -> list[str]:
        owner_query = build_wedding_owner_query(planner_id, planner_email)
        if not owner_query:
            return []
        weddings = await self.weddings_collection.find(owner_query, {"_id": 1}).to_list(
            length=None
        )
        return [str(wedding["_id"]) for wedding in weddings]

    async def bulk_mark_owner_cancelled(
        self, planner_id: Optional[str], planner_email: Optional[str]
    ) -> dict[str, Any]:
        wedding_ids = await self._owned_wedding_ids(planner_id, planner_email)
        if not wedding_ids:
            return {"updated_count": 0, "wedding_ids": []}

        couples = await self.couples_collection.find(
            {"wedding_id": {"$in": wedding_ids}}
        ).to_list(length=None)
        operations: list[UpdateOne] = []

        for couple in couples:
            set_fields = self.build_owner_cancelled_update(
                couple, planner_id=planner_id, planner_email=planner_email
            )
            if set_fields:
                operations.append(
                    UpdateOne({"_id": couple["_id"]}, {"$set": set_fields})
                )

        updated_count = 0
        if operations:
            result = await self.couples_collection.bulk_write(operations)
            updated_count = result.modified_count

        return {
            "updated_count": updated_count,
            "wedding_ids": wedding_ids,
            "couple_count": len(couples),
        }

    async def bulk_restore_owner_cancelled(
        self, planner_id: Optional[str], planner_email: Optional[str]
    ) -> dict[str, Any]:
        wedding_ids = await self._owned_wedding_ids(planner_id, planner_email)
        if not wedding_ids:
            return {"updated_count": 0, "wedding_ids": []}

        couples = await self.couples_collection.find(
            {"wedding_id": {"$in": wedding_ids}}
        ).to_list(length=None)
        operations: list[UpdateOne] = []

        for couple in couples:
            set_fields = self.build_owner_restore_update(couple)
            if set_fields:
                operations.append(
                    UpdateOne({"_id": couple["_id"]}, {"$set": set_fields})
                )

        updated_count = 0
        if operations:
            result = await self.couples_collection.bulk_write(operations)
            updated_count = result.modified_count

        return {
            "updated_count": updated_count,
            "wedding_ids": wedding_ids,
            "couple_count": len(couples),
        }


couple_lifecycle_service = CoupleLifecycleService()
