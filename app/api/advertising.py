"""
Advertising API

REST API for managing sponsored vendors and advertising features.
Endpoints for feature flag management, sponsored vendor CRUD, and ad event tracking.

All admin endpoints (PUT, POST, DELETE) require admin authentication.
Read endpoints (GET) are available to all authenticated users.
"""

import logging
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional
from datetime import datetime, timezone

from app.dependencies.auth_extended import (
    require_admin_or_planner,
    get_current_user_extended,
    ExtendedAuthUser,
)
from app.core.database import mongo
from app.services.advertising_service import AdvertisingService
from app.services.ad_rollup_service import AdRollupService
from app.models.advertising import (
    SponsoredVendor,
    AdEvent,
    AdvertisingFeatureFlag,
    AdPlacement,
    AdEventType,
    AdLead,
    AdLeadStatus,
    AdLeadType,
    PlannerAdPreference,
    CreateSponsoredVendorRequest,
    UpdateSponsoredVendorRequest,
    RecordAdEventRequest,
    AdStatsResponse,
    CreateAdLeadRequest,
    AdLeadResponse,
    UpdateAdLeadStatusRequest,
    PlannerAdPreferenceResponse,
)
from app.models.vendor import VendorCategory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ads", tags=["Advertising"])


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

async def get_advertising_service() -> AdvertisingService:
    """
    Get advertising service instance with database client.

    This is a FastAPI dependency that provides a fresh service instance
    with the current async database connection.
    """
    return AdvertisingService(mongo.db)


async def get_rollup_service() -> AdRollupService:
    """
    Get ad rollup service instance with database client.

    Provides access to pre-aggregated daily stats from ad_stats_daily.
    """
    return AdRollupService(mongo.db)


# =============================================================================
# FEATURE FLAG ENDPOINTS
# =============================================================================

@router.get(
    "/feature-flag",
    response_model=dict,
    summary="Get Advertising Feature Flag Status"
)
async def get_feature_flag(
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get the current status of the advertising feature flag.

    Returns whether sponsored vendors are enabled, configuration settings,
    and who last modified the flag.

    **Access:** Admin or Planner
    """
    flag = await service.get_feature_flag()
    return flag


@router.put(
    "/feature-flag",
    response_model=dict,
    summary="Toggle Advertising Feature Flag"
)
async def toggle_feature_flag(
    is_enabled: bool = Query(..., description="Enable or disable the feature"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Toggle the advertising feature flag on or off.

    Only admins can modify the feature flag.

    **Access:** Admin only

    **Parameters:**
    - is_enabled: Whether to enable or disable sponsored vendors
    """
    # Check if user is admin
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can modify the feature flag"
        )

    updated_flag = await service.toggle_feature_flag(
        is_enabled=is_enabled,
        admin_email=current_user.email
    )

    logger.info(
        f"Advertising feature flag toggled to {is_enabled} by {current_user.email}"
    )

    return updated_flag


# =============================================================================
# SPONSORED VENDORS ENDPOINTS
# =============================================================================

@router.get(
    "/sponsored-vendors",
    response_model=List[dict],
    summary="List Sponsored Vendors"
)
async def list_sponsored_vendors(
    placement: Optional[str] = Query(None, description="Filter by ad placement"),
    category: Optional[str] = Query(None, description="Filter by vendor category"),
    wedding_stage: Optional[str] = Query(None, description="Filter by wedding stage"),
    limit: int = Query(10, ge=1, le=100, description="Max results"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get sponsored vendors for the given filters.

    Returns active sponsored vendors sorted by priority (highest first).
    Only returns results if the feature flag is enabled.

    **Access:** Any authenticated user

    **Query Parameters:**
    - placement: Optional ad placement (vendor_rail, vendor_detail, etc.)
    - category: Optional vendor category filter
    - wedding_stage: Optional wedding stage filter
    - limit: Maximum results to return (1-100, default 10)
    """
    # Convert string enums to enum types
    placement_enum = None
    if placement:
        try:
            placement_enum = AdPlacement(placement)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid placement: {placement}"
            )

    category_enum = None
    if category:
        try:
            category_enum = VendorCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}"
            )

    vendors = await service.get_sponsored_vendors(
        placement=placement_enum,
        category_filter=category_enum,
        wedding_stage=wedding_stage,
        limit=limit
    )

    return vendors


@router.post(
    "/sponsored-vendors",
    response_model=dict,
    summary="Create Sponsored Vendor",
    status_code=201
)
async def create_sponsored_vendor(
    request: CreateSponsoredVendorRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a new sponsored vendor entry.

    Assigns a vendor to a specific placement with optional time period
    and targeting criteria.

    **Access:** Admin only

    **Request Body:**
    - vendor_profile_id: Reference to VendorProfile._id (required)
    - placement: Ad placement (required)
    - priority: Display priority 1-100 (default 50)
    - headline: Custom ad headline (optional, max 100 chars)
    - description: Custom ad description (optional, max 300 chars)
    - start_date: When sponsorship begins (optional)
    - end_date: When sponsorship ends (optional)
    - target_categories: Categories to target (optional, empty = all)
    - target_wedding_stages: Wedding stages to target (optional)
    """
    # Check if user is admin
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can create sponsored vendors"
        )

    data = request.model_dump(exclude_unset=True)

    sponsored = await service.create_sponsored_vendor(
        data=data,
        admin_email=current_user.email
    )

    logger.info(
        f"Sponsored vendor created: {sponsored['_id']} by {current_user.email}"
    )

    return sponsored


@router.put(
    "/sponsored-vendors/{sponsored_id}",
    response_model=dict,
    summary="Update Sponsored Vendor"
)
async def update_sponsored_vendor(
    sponsored_id: str,
    request: UpdateSponsoredVendorRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update an existing sponsored vendor.

    Only admins can modify sponsored vendors.

    **Access:** Admin only

    **Parameters:**
    - sponsored_id: ID of the sponsored vendor to update

    **Request Body:**
    All fields are optional. Only include fields to update:
    - priority: Display priority 1-100
    - headline: Custom ad headline
    - description: Custom ad description
    - is_active: Active status
    - start_date: Sponsorship start date
    - end_date: Sponsorship end date
    - target_categories: Categories to target
    - target_wedding_stages: Wedding stages to target
    """
    # Check if user is admin
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can update sponsored vendors"
        )

    updates = request.model_dump(exclude_unset=True)

    updated = await service.update_sponsored_vendor(
        sponsored_id=sponsored_id,
        updates=updates
    )

    logger.info(
        f"Sponsored vendor {sponsored_id} updated by {current_user.email}"
    )

    return updated


@router.delete(
    "/sponsored-vendors/{sponsored_id}",
    response_model=dict,
    summary="Delete Sponsored Vendor"
)
async def delete_sponsored_vendor(
    sponsored_id: str,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Soft delete a sponsored vendor (deactivates it).

    The record is not permanently deleted but marked as inactive.

    **Access:** Admin only

    **Parameters:**
    - sponsored_id: ID of the sponsored vendor to delete
    """
    # Check if user is admin
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete sponsored vendors"
        )

    deleted = await service.delete_sponsored_vendor(sponsored_id=sponsored_id)

    logger.info(
        f"Sponsored vendor {sponsored_id} deleted by {current_user.email}"
    )

    return deleted


# =============================================================================
# AD EVENT ENDPOINTS
# =============================================================================

@router.post(
    "/events",
    response_model=dict,
    summary="Record Ad Event",
    status_code=201
)
async def record_ad_event(
    request: RecordAdEventRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Record an ad event (impression, click, dismiss, etc).

    This endpoint is used by the frontend to track user interactions
    with sponsored vendors.

    **Access:** Any authenticated user

    **Request Body:**
    - event_type: Type of event (impression, click, dismiss, etc.) (required)
    - sponsored_vendor_id: Sponsored vendor ID (required)
    - vendor_profile_id: Vendor profile ID (required)
    - placement: Ad placement (required)
    - wedding_id: Current wedding ID (optional)
    - planner_id: Planner email (optional)
    - session_id: Session identifier (optional)
    - click_id: Click attribution ID (optional)
    - metadata: Additional event context (optional)
    """
    # Check if advertising feature is enabled before recording events
    flag = await service.get_feature_flag()
    if flag and not flag.get("is_enabled", True):
        return {"status": "skipped", "reason": "advertising_disabled"}

    event_data = request.model_dump(exclude_unset=True)

    # Add planner info if not provided
    if not event_data.get("planner_id"):
        event_data["planner_id"] = current_user.email

    ad_event = await service.record_ad_event(event_data=event_data)

    logger.debug(
        f"Ad event recorded: {ad_event['event_type']} "
        f"for {ad_event['vendor_profile_id']}"
    )

    return ad_event


# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@router.get(
    "/sponsored-vendors/{sponsored_id}/stats",
    response_model=dict,
    summary="Get Sponsored Vendor Stats"
)
async def get_sponsored_vendor_stats(
    sponsored_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get analytics stats for a sponsored vendor.

    Returns impressions, clicks, CTR, and recent event counts.

    **Access:** Admin only

    **Parameters:**
    - sponsored_id: ID of the sponsored vendor
    - days: Number of days to look back (1-90, default 7)
    """
    # Check if user is admin
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can view advertising stats"
        )

    stats = await service.get_ad_stats(
        sponsored_vendor_id=sponsored_id,
        days=days
    )

    return stats


# =============================================================================
# AD LEAD ENDPOINTS
# =============================================================================

@router.post(
    "/leads",
    response_model=dict,
    summary="Create Ad Lead",
    status_code=201
)
async def create_ad_lead(
    request: CreateAdLeadRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a new ad lead from planner interest in a sponsored vendor.

    Records when a planner expresses interest in a sponsored vendor through
    a quote request, message, add-to-wedding, or vendor invite.

    **Access:** Any authenticated user

    **Request Body:**
    - sponsored_vendor_id: Sponsored vendor ID (required)
    - vendor_profile_id: Vendor profile ID (required)
    - wedding_id: Wedding ID (optional)
    - lead_type: Type of lead interaction (required)
    - message: Planner message (optional, max 2000 chars)
    - quote_amount: Quote amount for QUOTE_REQUEST type (optional)
    - click_id: UUID linking to originating ad click (optional)
    - placement: Ad placement (default: vendor_rail)
    - metadata: Additional context (optional)
    """
    lead_data = request.model_dump(exclude_unset=True)
    lead_data["planner_id"] = current_user.email

    lead = await service.create_lead(data=lead_data)

    logger.info(
        f"Ad lead created by {current_user.email}: "
        f"{lead['lead_type']} for vendor {lead['vendor_profile_id']}"
    )

    return lead


@router.get(
    "/leads",
    response_model=List[dict],
    summary="List Ad Leads"
)
async def list_ad_leads(
    vendor_id: Optional[str] = Query(None, description="Filter by vendor ID"),
    planner_id: Optional[str] = Query(None, description="Filter by planner email"),
    status: Optional[str] = Query(None, description="Filter by lead status"),
    lead_type: Optional[str] = Query(None, description="Filter by lead type"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    skip: int = Query(0, ge=0, description="Skip results"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    List ad leads with optional filters.

    Admins can view all leads. Planners can only view their own leads.
    Vendors can view leads for their sponsored placements.

    **Access:** Admin, Planner, or Vendor

    **Query Parameters:**
    - vendor_id: Filter by vendor profile ID
    - planner_id: Filter by planner email
    - status: Filter by lead status
    - lead_type: Filter by lead type
    - limit: Maximum results (1-500, default 50)
    - skip: Skip N results for pagination
    """
    filters = {}

    if vendor_id:
        filters["vendor_profile_id"] = vendor_id

    # Role-based scoping:
    # - Admins: can view all leads, optionally filter by planner
    # - Vendors: can only see leads for vendor profiles matching their email
    # - Planners: can only see their own leads
    if current_user.is_root_admin:
        if planner_id:
            filters["planner_id"] = planner_id
    elif current_user.is_vendor:
        # Vendor users: scope to leads for their vendor profiles
        # Look up vendor profiles matching this vendor's email
        db = service.db
        vendor_profiles = []
        async for vp in db.vendor_profiles.find(
            {"email": current_user.email},
            {"_id": 1}
        ):
            vendor_profiles.append(str(vp["_id"]))
        if vendor_profiles:
            filters["vendor_profile_id"] = {"$in": vendor_profiles}
        else:
            # Vendor has no profiles — return empty
            return []
    else:
        # Planners and team members: only see their own leads
        filters["planner_id"] = current_user.email

    if status:
        filters["status"] = status

    if lead_type:
        filters["lead_type"] = lead_type

    leads = await service.get_leads(
        filters=filters,
        limit=limit,
        skip=skip
    )

    logger.debug(f"Listed {len(leads)} ad leads for {current_user.email}")

    return leads


@router.get(
    "/leads/{lead_id}",
    response_model=dict,
    summary="Get Ad Lead Details"
)
async def get_ad_lead(
    lead_id: str,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Get details of a specific ad lead.

    **Access:** Admin, lead creator, or involved vendor

    **Parameters:**
    - lead_id: ID of the ad lead
    """
    lead = await service.get_lead(lead_id=lead_id)

    # Authorization check — admin sees all, planner sees own, vendor sees own
    if current_user.is_root_admin:
        return lead
    elif current_user.is_vendor:
        # Vendor can see leads for their vendor profiles
        db = service.db
        vendor_profile_id = lead.get("vendor_profile_id")
        vendor_profile = await db.vendor_profiles.find_one(
            {"email": current_user.email, "_id": ObjectId(vendor_profile_id)}
        ) if vendor_profile_id else None
        if not vendor_profile:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to view this lead"
            )
        return lead
    elif lead.get("planner_id") == current_user.email:
        return lead
    else:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this lead"
        )


@router.put(
    "/leads/{lead_id}/status",
    response_model=dict,
    summary="Update Ad Lead Status"
)
async def update_ad_lead_status(
    lead_id: str,
    request: UpdateAdLeadStatusRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended)
):
    """
    Update the status of an ad lead.

    Vendors use this to mark leads as contacted, responded, or converted.

    **Access:** Admin or involved vendor

    **Parameters:**
    - lead_id: ID of the ad lead

    **Request Body:**
    - status: New status (pending, contacted, responded, converted, closed)
    - responded_at: When vendor responded (optional)
    - converted_at: When lead was converted (optional)
    """
    # Authorization: only admin or involved vendor can update lead status
    if not current_user.is_root_admin:
        lead = await service.get_lead(lead_id=lead_id)
        if current_user.is_vendor:
            db = service.db
            vendor_profile_id = lead.get("vendor_profile_id")
            vendor_profile = await db.vendor_profiles.find_one(
                {"email": current_user.email, "_id": ObjectId(vendor_profile_id)}
            ) if vendor_profile_id else None
            if not vendor_profile:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to update this lead"
                )
        elif lead.get("planner_id") != current_user.email:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to update this lead"
            )

    status_data = request.model_dump(exclude_unset=True)

    updated = await service.update_lead_status(
        lead_id=lead_id,
        status_data=status_data
    )

    logger.info(
        f"Ad lead {lead_id} status updated to {status_data.get('status')} "
        f"by {current_user.email}"
    )

    return updated


# =============================================================================
# PLANNER AD PREFERENCE ENDPOINTS
# =============================================================================

@router.get(
    "/preferences",
    response_model=dict,
    summary="Get Planner Ad Preferences"
)
async def get_ad_preferences(
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get ad display preferences for the current planner.

    Returns hidden vendors, hidden categories, and frequency settings.

    **Access:** Any authenticated planner
    """
    prefs = await service.get_planner_preferences(planner_id=current_user.email)

    return prefs


@router.put(
    "/preferences/hide-vendor",
    response_model=dict,
    summary="Hide Vendor from Planner"
)
async def hide_vendor_for_planner(
    vendor_id: str = Query(..., description="Sponsored vendor ID to hide"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Hide a sponsored vendor from the current planner's ad feed.

    **Access:** Any authenticated planner

    **Query Parameters:**
    - vendor_id: ID of the sponsored vendor to hide
    """
    updated = await service.hide_vendor(
        planner_id=current_user.email,
        vendor_id=vendor_id
    )

    logger.info(
        f"Vendor {vendor_id} hidden for planner {current_user.email}"
    )

    return updated


@router.put(
    "/preferences/hide-category",
    response_model=dict,
    summary="Hide Category from Planner"
)
async def hide_category_for_planner(
    category: str = Query(..., description="Vendor category to hide"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Hide a vendor category from the current planner's ad feed.

    **Access:** Any authenticated planner

    **Query Parameters:**
    - category: VendorCategory value to hide
    """
    updated = await service.hide_category(
        planner_id=current_user.email,
        category=category
    )

    logger.info(
        f"Category {category} hidden for planner {current_user.email}"
    )

    return updated


@router.put(
    "/preferences/reduce-frequency",
    response_model=dict,
    summary="Toggle Reduced Ad Frequency"
)
async def toggle_reduced_frequency(
    reduce: bool = Query(..., description="Enable or disable reduced frequency"),
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Toggle reduced ad frequency for the current planner.

    When enabled, fewer ads will be shown to the planner.

    **Access:** Any authenticated planner

    **Query Parameters:**
    - reduce: Whether to enable reduced frequency
    """
    updated = await service.toggle_reduced_frequency(
        planner_id=current_user.email,
        reduced=reduce
    )

    logger.info(
        f"Reduced frequency {'enabled' if reduce else 'disabled'} "
        f"for planner {current_user.email}"
    )

    return updated


@router.delete(
    "/preferences/unhide-vendor/{vendor_id}",
    response_model=dict,
    summary="Unhide Vendor for Planner"
)
async def unhide_vendor_for_planner(
    vendor_id: str,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Unhide a previously hidden sponsored vendor for the current planner.

    **Access:** Any authenticated planner

    **Parameters:**
    - vendor_id: ID of the sponsored vendor to unhide
    """
    updated = await service.unhide_vendor(
        planner_id=current_user.email,
        vendor_id=vendor_id
    )

    logger.info(
        f"Vendor {vendor_id} unhidden for planner {current_user.email}"
    )

    return updated


# =============================================================================
# ROLLUP DASHBOARD ENDPOINTS
# =============================================================================

@router.get(
    "/dashboard/stats",
    response_model=dict,
    summary="Get Dashboard Stats from Rollups"
)
async def get_dashboard_stats(
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    sponsored_vendor_id: Optional[str] = Query(None, description="Filter by vendor"),
    placement: Optional[str] = Query(None, description="Filter by placement"),
    rollup_service: AdRollupService = Depends(get_rollup_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get pre-aggregated daily stats for the analytics dashboard.

    Reads from the ad_stats_daily rollup collection for fast, indexed queries.
    Returns daily breakdowns with event counts, CTR, lead funnels, and hourly patterns.

    **Access:** Admin only

    **Query Parameters:**
    - days: Lookback period (1-365, default 30)
    - sponsored_vendor_id: Filter by specific vendor (optional)
    - placement: Filter by ad placement (optional)
    """
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can view dashboard stats"
        )

    daily_stats = await rollup_service.get_dashboard_stats(
        days=days,
        sponsored_vendor_id=sponsored_vendor_id,
        placement=placement,
    )

    # Aggregate totals across all days
    totals = {
        "impressions": 0,
        "clicks": 0,
        "leads": 0,
        "conversions": 0,
        "unique_planners": 0,
        "unique_weddings": 0,
    }
    leads_by_type_totals = {}
    leads_by_status_totals = {}
    hourly_clicks_totals = [0] * 24
    daily_series = []

    for doc in daily_stats:
        counts = doc.get("counts", {})
        # Use impression_served only — impression_viewable is a subset, not additive
        impressions = counts.get("impression_served", 0)
        clicks = counts.get("click", 0)
        leads = counts.get("lead_created", 0)

        totals["impressions"] += impressions
        totals["clicks"] += clicks
        totals["leads"] += leads
        totals["conversions"] += doc.get("leads_by_status", {}).get("converted", 0)
        totals["unique_planners"] += doc.get("unique_planners", 0)
        totals["unique_weddings"] += doc.get("unique_weddings", 0)

        # Accumulate leads by type
        for lt, count in doc.get("leads_by_type", {}).items():
            leads_by_type_totals[lt] = leads_by_type_totals.get(lt, 0) + count

        # Accumulate leads by status
        for ls, count in doc.get("leads_by_status", {}).items():
            leads_by_status_totals[ls] = leads_by_status_totals.get(ls, 0) + count

        # Accumulate hourly clicks
        for i, h in enumerate(doc.get("hourly_clicks", [0] * 24)):
            hourly_clicks_totals[i] += h

        # Build daily time series
        date_str = doc["date"].strftime("%Y-%m-%d") if hasattr(doc["date"], "strftime") else str(doc["date"])
        daily_series.append({
            "date": date_str,
            "impressions": impressions,
            "clicks": clicks,
            "leads": leads,
            "ctr": doc.get("ctr", 0),
            "vendor_profile_views": counts.get("vendor_profile_view", 0),
            "vendor_added_to_wedding": counts.get("vendor_added_to_wedding", 0),
        })

    # Sort daily series by date ascending
    daily_series.sort(key=lambda x: x["date"])

    # Compute overall CTR
    overall_ctr = (
        round((totals["clicks"] / totals["impressions"]) * 100, 2)
        if totals["impressions"] > 0 else 0.0
    )

    return {
        "period_days": days,
        "totals": {
            **totals,
            "ctr": overall_ctr,
        },
        "leads_by_type": leads_by_type_totals,
        "leads_by_status": leads_by_status_totals,
        "hourly_clicks": hourly_clicks_totals,
        "daily_series": daily_series,
    }


@router.get(
    "/dashboard/leaderboard",
    response_model=list,
    summary="Get Vendor Performance Leaderboard"
)
async def get_vendor_leaderboard(
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(20, ge=1, le=100, description="Max vendors to return"),
    rollup_service: AdRollupService = Depends(get_rollup_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get vendor performance leaderboard ranked by total clicks.

    Returns aggregated vendor stats from the rollup collection,
    including impressions, clicks, CTR, leads, and conversion counts.

    **Access:** Admin only

    **Query Parameters:**
    - days: Lookback period (1-365, default 30)
    - limit: Maximum vendors to return (1-100, default 20)
    """
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can view the vendor leaderboard"
        )

    leaderboard = await rollup_service.get_vendor_leaderboard(
        days=days,
        limit=limit,
    )

    # Clean up MongoDB _id fields for JSON response
    results = []
    for doc in leaderboard:
        doc.pop("_id", None)
        results.append(doc)

    return results


@router.post(
    "/dashboard/rollup",
    response_model=dict,
    summary="Trigger Daily Rollup Computation"
)
async def trigger_rollup(
    target_date: Optional[str] = Query(
        None,
        description="Date to compute rollup for (YYYY-MM-DD, defaults to yesterday)"
    ),
    rollup_service: AdRollupService = Depends(get_rollup_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Manually trigger a daily rollup computation.

    Computes or recomputes the ad_stats_daily rollup for a specific date.
    Idempotent: safe to re-run for the same date.

    **Access:** Admin only

    **Query Parameters:**
    - target_date: Date in YYYY-MM-DD format (defaults to yesterday UTC)
    """
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can trigger rollup computation"
        )

    date_obj = None
    if target_date:
        try:
            date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD."
            )

    count = await rollup_service.compute_daily_rollup(target_date=date_obj)

    logger.info(
        f"Rollup triggered by {current_user.email}: "
        f"{count} documents for {target_date or 'yesterday'}"
    )

    return {
        "status": "completed",
        "documents_upserted": count,
        "target_date": target_date or "yesterday",
    }


@router.post(
    "/dashboard/backfill",
    response_model=dict,
    summary="Backfill Rollup Data"
)
async def backfill_rollups(
    days_back: int = Query(90, ge=1, le=365, description="Days to backfill"),
    rollup_service: AdRollupService = Depends(get_rollup_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Backfill rollup data for the specified number of past days.

    Useful for initial setup or recovering from missed nightly runs.

    **Access:** Admin only

    **Query Parameters:**
    - days_back: Number of days to backfill (1-365, default 90)
    """
    if not current_user.is_root_admin:
        raise HTTPException(
            status_code=403,
            detail="Only admins can trigger backfill"
        )

    total = await rollup_service.backfill_rollups(days_back=days_back)

    logger.info(
        f"Backfill completed by {current_user.email}: "
        f"{total} documents over {days_back} days"
    )

    return {
        "status": "completed",
        "total_documents": total,
        "days_backfilled": days_back,
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get(
    "/health",
    summary="Advertising Service Health Check"
)
async def health_check(
    service: AdvertisingService = Depends(get_advertising_service)
):
    """
    Check if the advertising service is healthy.

    **Access:** Public (no authentication required)
    """
    is_healthy = await service.health_check()

    if not is_healthy:
        raise HTTPException(
            status_code=503,
            detail="Advertising service is unavailable"
        )

    return {
        "status": "healthy",
        "service": "advertising"
    }


# =============================================================================
# AD CREATIVE IMAGE UPLOAD
# =============================================================================

from app.services.gallery_upload_service import AdUploadService

_ad_upload_service = AdUploadService()


@router.get(
    "/upload-url",
    summary="Get Presigned URL for Ad Image Upload",
)
async def get_ad_upload_url(
    filename: str = Query(..., description="Original filename of the image"),
    content_type: str = Query(..., description="MIME type (image/jpeg, image/png, image/webp)"),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """
    Generate a presigned PUT URL for uploading ad creative images
    to the dedicated ad-assets S3 bucket.

    The vendor must be the owner of the ad campaign.
    Returns upload_url (presigned PUT), key, and cdn_url.

    **Access:** Authenticated vendors or root admins.
    """
    if not current_user.is_root_admin and not current_user.is_vendor:
        raise HTTPException(status_code=403, detail="Only vendors or admins can upload ad images")

    # Resolve vendor_id: vendors use their own ID, admins must pass it
    vendor_id = None
    if current_user.is_vendor and hasattr(current_user, 'user_data'):
        vendor_id = getattr(current_user.user_data, 'vendor_id', None) if hasattr(current_user.user_data, 'vendor_id') else current_user.user_data.get('vendor_id') if isinstance(current_user.user_data, dict) else None

    if not vendor_id and current_user.is_root_admin:
        # Root admin can upload for any vendor — use a generic key
        vendor_id = "admin"
    elif not vendor_id:
        raise HTTPException(status_code=400, detail="Could not resolve vendor ID from your profile")

    result = _ad_upload_service.create_presigned_upload_url(
        filename=filename,
        vendor_id=vendor_id,
        content_type=content_type,
    )
    return result


@router.post(
    "/update-logo",
    summary="Update Vendor Profile Logo URL after Ad Image Upload",
)
async def update_vendor_logo(
    logo_url: str = Body(..., embed=True, description="CDN URL of the uploaded image"),
    current_user: ExtendedAuthUser = Depends(get_current_user_extended),
):
    """
    After a successful image upload to the ad bucket, call this endpoint
    to persist the CDN URL on the vendor's profile as logo_url.

    **Access:** Authenticated vendors or root admins.
    """
    if not current_user.is_root_admin and not current_user.is_vendor:
        raise HTTPException(status_code=403, detail="Only vendors or admins can update vendor logos")

    vendor_id = None
    if current_user.is_vendor and hasattr(current_user, 'user_data'):
        vendor_id = getattr(current_user.user_data, 'vendor_id', None) if hasattr(current_user.user_data, 'vendor_id') else current_user.user_data.get('vendor_id') if isinstance(current_user.user_data, dict) else None

    if not vendor_id and current_user.is_root_admin:
        raise HTTPException(status_code=400, detail="Admin must specify a vendor_id via query param")
    elif not vendor_id:
        raise HTTPException(status_code=400, detail="Could not resolve vendor ID from your profile")

    # Update logo_url on vendor profile
    result = await mongo.db.vendor_profiles.find_one_and_update(
        {"_id": ObjectId(vendor_id)},
        {"$set": {"logo_url": logo_url, "updated_at": datetime.now(timezone.utc)}},
        return_document=True,
    )

    if not result:
        raise HTTPException(status_code=404, detail="Vendor profile not found")

    return {"message": "Logo updated successfully", "logo_url": logo_url}
