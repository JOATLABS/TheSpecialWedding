"""Read-only storefront entitlement resolution.

Boolean storefront capabilities intentionally come from the current plan
catalog. Subscription snapshots remain historical records for grandfathered
limits and are never read or rewritten here.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.constants.roles import is_wedding_planner_user
from app.constants.storefront import CUSTOM_DOMAIN_FEATURE, STOREFRONT_FEATURE
from app.core.database import mongo
from app.models.subscription import ACTIVE_SUBSCRIPTION_STATUSES
from app.utils.planner_ownership import normalize_planner_id, normalize_query_id

logger = logging.getLogger(__name__)


class StorefrontEntitlementResolutionError(RuntimeError):
    """The entitlement source could not be read reliably."""


@dataclass(frozen=True, slots=True)
class StorefrontEntitlements:
    owner_id: str
    plan_id: str | None
    storefront_enabled: bool
    custom_domain_enabled: bool


class StorefrontEntitlementService:
    """Resolve independent storefront capabilities for a planner owner."""

    def __init__(self, mongo_client: Any | None = None):
        self._mongo = mongo_client or mongo

    @staticmethod
    def _disabled(
        owner_id: str | None, plan_id: str | None = None
    ) -> StorefrontEntitlements:
        return StorefrontEntitlements(
            owner_id=owner_id or "",
            plan_id=plan_id,
            storefront_enabled=False,
            custom_domain_enabled=False,
        )

    async def resolve_for_owner(self, user_data: dict) -> StorefrontEntitlements:
        owner_id = normalize_planner_id(user_data.get("_id"))
        if not owner_id or not is_wedding_planner_user(user_data):
            return self._disabled(owner_id)

        try:
            active_subscriptions = await (
                self._mongo.db["user_subscriptions"]
                .find(
                    {
                        "user_id": owner_id,
                        "status": {"$in": sorted(ACTIVE_SUBSCRIPTION_STATUSES)},
                    },
                    {"plan_id": 1, "status": 1},
                )
                .limit(2)
                .to_list(length=2)
            )
        except Exception as exc:
            logger.exception(
                "Failed to read storefront subscription for owner %s", owner_id
            )
            raise StorefrontEntitlementResolutionError(
                "Storefront eligibility could not be resolved"
            ) from exc

        # There is no unique-active-subscription index. Ambiguity must never
        # grant a capability based on whichever record Mongo happens to return.
        if len(active_subscriptions) != 1:
            return self._disabled(owner_id)

        plan_id = normalize_planner_id(active_subscriptions[0].get("plan_id"))
        if not plan_id:
            return self._disabled(owner_id)

        try:
            plan = await self._mongo.get_subscription_plans_collection().find_one(
                {"_id": plan_id}, {"features": 1}
            )
        except Exception as exc:
            logger.exception(
                "Failed to read storefront plan %s for owner %s", plan_id, owner_id
            )
            raise StorefrontEntitlementResolutionError(
                "Storefront eligibility could not be resolved"
            ) from exc

        if not plan or not isinstance(plan.get("features"), dict):
            return self._disabled(owner_id, plan_id)

        features = plan["features"]
        return StorefrontEntitlements(
            owner_id=owner_id,
            plan_id=plan_id,
            # Literal True is required. Values such as "true" and 1 signal a
            # malformed catalog and must not accidentally grant access.
            storefront_enabled=features.get(STOREFRONT_FEATURE) is True,
            custom_domain_enabled=features.get(CUSTOM_DOMAIN_FEATURE) is True,
        )

    async def resolve_for_planner_id(self, planner_id: str) -> StorefrontEntitlements:
        owner_id = normalize_planner_id(planner_id)
        if not owner_id:
            return self._disabled(None)

        try:
            owner = await self._mongo.get_users_collection().find_one(
                {"_id": normalize_query_id(owner_id)},
                {"_id": 1, "role": 1, "is_active": 1},
            )
        except Exception as exc:
            logger.exception("Failed to read storefront owner %s", owner_id)
            raise StorefrontEntitlementResolutionError(
                "Storefront eligibility could not be resolved"
            ) from exc

        if (
            not owner
            or owner.get("is_active") is not True
            or not is_wedding_planner_user(owner)
        ):
            return self._disabled(owner_id)

        return await self.resolve_for_owner(owner)


storefront_entitlement_service = StorefrontEntitlementService()
