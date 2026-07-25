"""Audit logging helpers for shared calendar actions."""

from __future__ import annotations

from typing import Any

from app.services.activity_log_service import activity_log_service


class CalendarAuditService:
    """Record calendar actions in the planner activity log."""

    async def log(
        self,
        *,
        action: str,
        message: str,
        owner_planner_email: str | None,
        actor_email: str | None,
        actor_role: str | None = None,
        wedding_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        await activity_log_service.log_activity(
            activity_type=action,
            message=message,
            wedding_id=wedding_id,
            planner_email=owner_planner_email,
            actor_email=actor_email,
            actor_role=actor_role,
            metadata=metadata or {},
        )


calendar_audit_service = CalendarAuditService()
