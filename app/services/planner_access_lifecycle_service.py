import logging
from typing import Any


logger = logging.getLogger(__name__)


class PlannerAccessLifecycleService:
    """Coordinate planner-owned access suspension/restoration across modules."""

    async def suspend_planner_access(
        self,
        planner_id: str,
        planner_email: str,
        *,
        team_reason: str = "owner_subscription_cancelled",
    ) -> dict[str, Any]:
        results: dict[str, Any] = {
            "team_members_deactivated": 0,
            "couples_blocked": 0,
            "data_suspended": {},
            "payments_paused": {},
            "errors": [],
        }

        try:
            from app.services.team_management_service import TeamManagementService

            team_service = TeamManagementService()
            team_result = await team_service.bulk_deactivate_by_owner(
                planner_id, team_reason
            )
            results["team_members_deactivated"] = team_result.get(
                "deactivated_count", 0
            )
        except Exception as exc:
            logger.warning(
                "Failed to deactivate team members for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "team_members_deactivated",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.couple_lifecycle_service import couple_lifecycle_service

            couple_result = await couple_lifecycle_service.bulk_mark_owner_cancelled(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            results["couples_blocked"] = couple_result.get("updated_count", 0)
        except Exception as exc:
            logger.warning(
                "Failed to block couple portal access for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "couples_blocked",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.cascade_delete_service import cascade_delete_service

            suspend_result = await cascade_delete_service.suspend_planner_data(
                planner_id, planner_email
            )
            results["data_suspended"] = suspend_result
        except Exception as exc:
            logger.warning(
                "Failed to suspend planner-owned data for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "data_suspended",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.package_service import package_service

            payments_result = await package_service.pause_planner_payment_links(
                planner_id, planner_email
            )
            results["payments_paused"] = payments_result
        except Exception as exc:
            logger.warning(
                "Failed to pause planner payments for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "payments_paused",
                    "detail": str(exc),
                }
            )

        return results

    async def restore_planner_access(
        self,
        planner_id: str,
        planner_email: str,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {
            "team_members_reactivated": 0,
            "couples_restored": 0,
            "data_unsuspended": {},
            "payments_resumed": {},
            "errors": [],
        }

        try:
            from app.services.team_management_service import TeamManagementService

            team_service = TeamManagementService()
            team_result = await team_service.bulk_reactivate_by_owner(
                owner_id=planner_id
            )
            results["team_members_reactivated"] = team_result.get(
                "reactivated_count", 0
            )
        except Exception as exc:
            logger.error(
                "Failed to reactivate team members for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "team_members_reactivated",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.couple_lifecycle_service import couple_lifecycle_service

            couple_result = await couple_lifecycle_service.bulk_restore_owner_cancelled(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            results["couples_restored"] = couple_result.get("updated_count", 0)
        except Exception as exc:
            logger.error(
                "Failed to restore couple portal access for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "couples_restored",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.cascade_delete_service import cascade_delete_service

            data_result = await cascade_delete_service.unsuspend_planner_data(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            results["data_unsuspended"] = data_result
        except Exception as exc:
            logger.error(
                "Failed to unsuspend planner-owned data for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "data_unsuspended",
                    "detail": str(exc),
                }
            )

        try:
            from app.services.package_service import package_service

            payment_result = await package_service.resume_planner_payment_links(
                planner_id=planner_id,
                planner_email=planner_email,
            )
            results["payments_resumed"] = payment_result
        except Exception as exc:
            logger.error(
                "Failed to resume planner payments for planner %s: %s",
                planner_id,
                str(exc),
            )
            results["errors"].append(
                {
                    "phase": "payments_resumed",
                    "detail": str(exc),
                }
            )

        return results


planner_access_lifecycle_service = PlannerAccessLifecycleService()
