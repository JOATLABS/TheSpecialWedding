"""
Advertising API

REST API for managing sponsored vendors and advertising features.
Endpoints for feature flag management, sponsored vendor CRUD, and ad event tracking.

All admin endpoints (PUT, POST, DELETE) require admin authentication.
Read endpoints (GET) are available to all authenticated users.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from app.dependencies.auth_extended import require_admin_or_planner, ExtendedAuthUser
from app.core.database import mongo
from app.services.advertising_service import AdvertisingService
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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

    if planner_id and current_user.is_root_admin:
        filters["planner_id"] = planner_id
    elif not current_user.is_root_admin:
        # Non-admins only see their own leads
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
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get details of a specific ad lead.

    **Access:** Admin, lead creator, or involved vendor

    **Parameters:**
    - lead_id: ID of the ad lead
    """
    lead = await service.get_lead(lead_id=lead_id)

    # Authorization check
    if not current_user.is_root_admin and lead.get("planner_id") != current_user.email:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this lead"
        )

    return lead


@router.put(
    "/leads/{lead_id}/status",
    response_model=dict,
    summary="Update Ad Lead Status"
)
async def update_ad_lead_status(
    lead_id: str,
    request: UpdateAdLeadStatusRequest,
    service: AdvertisingService = Depends(get_advertising_service),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
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
