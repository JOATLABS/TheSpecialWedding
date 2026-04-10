"""Audit logging helpers for shared calendar actions."""

from __future__ import annotations

from typing import Any, Optional

from app.services.activity_log_service import activity_log_service


class CalendarAuditService:
    """Record calendar actions in the planner activity log."""

    async def log(
        self,
        *,
        action: str,
        message: str,
        owner_planner_email: Optional[str],
        actor_email: Optional[str],
        actor_role: Optional[str] = None,
        wedding_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
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
