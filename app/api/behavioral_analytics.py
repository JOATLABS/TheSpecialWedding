"""API endpoints for behavioral product analytics.

Provides WAU, activation funnels, retention cohorts, engagement
signals, MRR movement, and per-wedding engagement data.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth_extended import require_root_admin, get_current_active_user
from app.models.user_extended import ExtendedAuthUser
from app.services.behavioral_analytics_service import service as analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────────
#  ROOT ADMIN: Full behavioral analytics dashboard
# ──────────────────────────────────────────────────

@router.get(
    "/behavioral-analytics",
    tags=["Behavioral Analytics"],
    summary="Get behavioral product metrics (WAU, funnels, retention, MRR movement)",
)
async def get_behavioral_analytics(
    timeframe: str = Query(default="30d", regex="^(7d|30d|90d|1y)$"),
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
    current_user: ExtendedAuthUser = Depends(get_current_active_user),
):
    """Return engagement signals for each wedding assigned to the current planner.

    Includes: last activity date, RSVP velocity, form completion,
    and needs-attention flags.
    """
    if current_user.role not in ("wedding_planner", "ROOT_ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        signals = await analytics_service.get_planner_engagement_signals(
            current_user.email
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
    current_user: ExtendedAuthUser = Depends(get_current_active_user),
):
    """Return invited guests who haven't submitted an RSVP,
    sorted by days since invitation was sent (longest first).
    """
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
    current_user: ExtendedAuthUser = Depends(get_current_active_user),
):
    """Return budget categories with allocation, spend, and percentage data
    for rendering a budget distribution chart.
    """
    try:
        breakdown = await analytics_service.get_budget_breakdown(wedding_id)
        return {"wedding_id": wedding_id, **breakdown}
    except Exception as exc:
        logger.error("Failed to get budget breakdown: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get budget breakdown")
