"""Vendor dashboard API endpoints."""

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    enforce_team_permission,
    require_vendor,
)
from app.services.vendor_dashboard_service import VendorDashboardService

router = APIRouter()
service = VendorDashboardService()


@router.get("/dashboard", tags=["Vendor Dashboard"])
def get_vendor_dashboard(
    current_user: ExtendedAuthUser = Depends(require_vendor),
):
    """Return the aggregated dashboard data for the current vendor."""

    assigned_weddings = (
        current_user.user_data.get("assigned_wedding_ids", [])
        if current_user.user_data
        else []
    )

    return service.get_dashboard(
        vendor_email=current_user.email,
        assigned_wedding_ids=assigned_weddings,
    )


@router.patch("/tasks/{task_id}", tags=["Vendor Dashboard"])
def update_vendor_task_status(
    task_id: str,
    status: str = Query(..., description="New status for the task"),
    current_user: ExtendedAuthUser = Depends(require_vendor),
):
    """Update a vendor task status while enforcing ownership."""
    enforce_team_permission(current_user, "manage_vendors")

    user_data = current_user.user_data or {}
    assigned_weddings = user_data.get("assigned_wedding_ids", [])

    vendor_records = service.resolve_vendor_scope(
        vendor_email=current_user.email,
        assigned_wedding_ids=assigned_weddings,
    )

    bypass = current_user.is_root_admin or current_user.is_wedding_planner

    return service.update_task_status(
        task_id=task_id,
        new_status=status,
        actor_email=current_user.email,
        allowed_vendor_ids=vendor_records["vendor_ids"],
        allowed_wedding_ids=vendor_records["wedding_ids"],
        bypass_permission=bypass,
    )
