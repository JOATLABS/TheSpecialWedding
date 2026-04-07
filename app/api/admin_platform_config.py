"""
Admin Platform Config API Router

REST API for root admin to manage advertising platform settings,
view data pipeline status, and export advertising data.

All endpoints require ROOT_ADMIN auth.

PRD Reference: Mockup Platform Config tab
Routes: /admin/ads/config/*
"""

import logging
from fastapi import APIRouter, Depends, Query

from app.dependencies.auth_extended import (
    require_root_admin,
    ExtendedAuthUser,
)
from app.core.database import mongo
from app.services.ad_platform_config_service import AdPlatformConfigService
from app.models.advertising_campaign import UpdatePlatformConfigRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ads/config", tags=["Admin Platform Config"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================


async def get_config_service() -> AdPlatformConfigService:
    """Get platform config service instance."""
    return AdPlatformConfigService(mongo.db)


# =============================================================================
# SETTINGS
# =============================================================================


@router.get(
    "",
    summary="Get platform config",
    description="Returns current advertising platform configuration (feature flags, limits, thresholds).",
)
async def get_platform_config(
    admin: ExtendedAuthUser = Depends(require_root_admin),
    service: AdPlatformConfigService = Depends(get_config_service),
):
    return await service.get_config()


@router.put(
    "",
    summary="Update platform config",
    description="Partially update platform config. Only provided fields are updated.",
)
async def update_platform_config(
    body: UpdatePlatformConfigRequest,
    admin: ExtendedAuthUser = Depends(require_root_admin),
    service: AdPlatformConfigService = Depends(get_config_service),
):
    updates = body.model_dump(exclude_none=True)
    return await service.update_config(updates, admin.email)


# =============================================================================
# DATA PIPELINE
# =============================================================================


@router.get(
    "/pipeline",
    summary="Get data pipeline status",
    description="Returns rollup health, collection stats, TTL info.",
)
async def get_pipeline_status(
    admin: ExtendedAuthUser = Depends(require_root_admin),
    service: AdPlatformConfigService = Depends(get_config_service),
):
    return await service.get_pipeline_status()


# =============================================================================
# DATA EXPORT
# =============================================================================


@router.get(
    "/export",
    summary="Export advertising data",
    description="Export data from any advertising collection as JSON.",
)
async def export_data(
    dataset: str = Query(
        ...,
        description="Dataset to export: vendor_accounts, active_campaigns, all_campaigns, "
        "campaign_performance, ad_events, ad_leads, planner_feedback, "
        "campaign_daily_stats, placement_daily_stats, fraud_signals",
    ),
    date_range: str = Query(
        "last_30_days",
        description="Date range: last_7_days, last_30_days, last_90_days, all_time",
    ),
    format: str = Query("json", description="Export format: json or csv"),
    limit: int = Query(1000, ge=1, le=10000, description="Max rows to return"),
    admin: ExtendedAuthUser = Depends(require_root_admin),
    service: AdPlatformConfigService = Depends(get_config_service),
):
    return await service.export_data(dataset, date_range, format, limit)
