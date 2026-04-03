"""API endpoints for behavioral product analytics.

Provides WAU, activation funnels, retention cohorts, engagement
signals, MRR movement, and per-wedding engagement data.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    get_accessible_wedding_ids,
    require_root_admin,
    require_team_or_planner,
)
from app.dependencies.couple_auth import require_couple_auth
from app.services.behavioral_analytics_service import service as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_planner_scope_email(current_user: ExtendedAuthUser) -> Optional[str]:
    """Map admin/team auth to the planner owner scope used by wedding records."""
    if current_user.is_root_admin:
        return None
    if current_user.is_team_member:
        return current_user.team_owner_email
    return current_user.email


# ──────────────────────────────────────────────────
#  ROOT ADMIN: Full behavioral analytics dashboard
# ──────────────────────────────────────────────────

@router.get(
    "/behavioral-analytics",
    tags=["Behavioral Analytics"],
    summary="Get behavioral product metrics (WAU, funnels, retention, MRR movement)",
)
async def get_behavioral_analytics(
    timeframe: str = Query(default="30d", pattern="^(7d|30d|90d|1y)$"),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Return the full behavioral analytics payload for the root admin dashboard.

    Includes: WAU, activation funnel, retention cohorts,
    engagement signals, MRR movement, and week-over-week changes.
    """
    try:
        return await analytics_service.compile_behavioral_metrics(timeframe)
    except Exception as exc:
        logger.error("Failed to compile behavioral metrics: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to compile behavioral metrics")


# ──────────────────────────────────────────────────
#  PLANNER: Per-wedding engagement signals
# ──────────────────────────────────────────────────

@router.get(
    "/engagement-signals",
    tags=["Behavioral Analytics"],
    summary="Get per-wedding engagement signals for the current planner",
)
async def get_engagement_signals(
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Return engagement signals for each wedding assigned to the current planner.

    Includes: last activity date, RSVP velocity, form completion,
    and needs-attention flags.
    """
    enforce_team_permission(current_user, "view_analytics")

    planner_scope_email = _resolve_planner_scope_email(current_user)
    if current_user.is_team_member and not planner_scope_email:
        raise HTTPException(status_code=403, detail="Team member is not linked to a planner")

    try:
        signals = await analytics_service.get_planner_engagement_signals(
            planner_email=planner_scope_email,
            accessible_wedding_ids=get_accessible_wedding_ids(current_user),
        )
        return {"signals": signals, "count": len(signals)}
    except Exception as exc:
        logger.error("Failed to get engagement signals: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get engagement signals")


# ──────────────────────────────────────────────────
#  COUPLE PORTAL: Non-responders list
# ──────────────────────────────────────────────────

@router.get(
    "/weddings/{wedding_id}/non-responders",
    tags=["Behavioral Analytics"],
    summary="Get guests who haven't RSVP'd, sorted by wait time",
)
async def get_non_responders(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Return invited guests who haven't submitted an RSVP,
    sorted by days since invitation was sent (longest first).
    """
    enforce_team_permission(current_user, "view_analytics")
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        non_responders = await analytics_service.get_non_responders(wedding_id)
        return {
            "wedding_id": wedding_id,
            "non_responders": non_responders,
            "count": len(non_responders),
        }
    except Exception as exc:
        logger.error("Failed to get non-responders: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get non-responders")


# ──────────────────────────────────────────────────
#  COUPLE PORTAL: Budget category breakdown
# ──────────────────────────────────────────────────

@router.get(
    "/weddings/{wedding_id}/budget-breakdown",
    tags=["Behavioral Analytics"],
    summary="Get per-category budget allocation and spend",
)
async def get_budget_breakdown(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_team_or_planner),
):
    """Return budget categories with allocation, spend, and percentage data
    for rendering a budget distribution chart.
    """
    enforce_team_permission(current_user, "view_analytics")
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        breakdown = await analytics_service.get_budget_breakdown(wedding_id)
        return {"wedding_id": wedding_id, **breakdown}
    except Exception as exc:
        logger.error("Failed to get budget breakdown: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get budget breakdown")


# ──────────────────────────────────────────────────
#  COUPLE-AUTH ENDPOINTS
#  These mirror the admin endpoints but use couple auth
#  and restrict access to the couple's own wedding.
# ──────────────────────────────────────────────────

couple_router = APIRouter()


@couple_router.get(
    "/portal/non-responders",
    tags=["Couple Portal Analytics"],
    summary="Get guests who haven't RSVP'd for the couple's wedding",
)
async def couple_get_non_responders(
    couple: dict = Depends(require_couple_auth),
):
    """Return non-responding guests for the authenticated couple's wedding."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=400, detail="No wedding associated with this account")

    try:
        non_responders = await analytics_service.get_non_responders(str(wedding_id))
        return {
            "wedding_id": str(wedding_id),
            "non_responders": non_responders,
            "count": len(non_responders),
        }
    except Exception as exc:
        logger.error("Failed to get non-responders: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get non-responders")


@couple_router.get(
    "/portal/budget-breakdown",
    tags=["Couple Portal Analytics"],
    summary="Get budget category breakdown for the couple's wedding",
)
async def couple_get_budget_breakdown(
    couple: dict = Depends(require_couple_auth),
):
    """Return budget category breakdown for the authenticated couple's wedding."""
    wedding_id = couple.get("wedding_id")
    if not wedding_id:
        raise HTTPException(status_code=400, detail="No wedding associated with this account")

    try:
        breakdown = await analytics_service.get_budget_breakdown(str(wedding_id))
        return {"wedding_id": str(wedding_id), **breakdown}
    except Exception as exc:
        logger.error("Failed to get budget breakdown: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get budget breakdown")
