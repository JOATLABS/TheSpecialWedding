import logging
from typing import List

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from app.core.database import mongo
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    check_wedding_access,
    enforce_team_permission,
    require_admin_or_planner,
)
from app.models.table import AssignGuestsRequest, TableModel, UpdateTableRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tables/{wedding_id}", tags=["Seating"])
async def list_tables(
    wedding_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Fetch all tables for a wedding"""
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Safety cap for seating tables (typical weddings have <500 tables)
    MAX_TABLES = 1000
    tables_cursor = mongo.db["tables"].find({"wedding_id": wedding_id})
    tables = await tables_cursor.to_list(length=MAX_TABLES)

    # Convert ObjectIds to strings
    for table in tables:
        if "_id" in table:
            table["id"] = str(table["_id"])
            del table["_id"]

    return tables


@router.post("/tables", tags=["Seating"])
async def create_table(
    table: TableModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Create a new table"""
    enforce_team_permission(current_user, "manage_seating")
    if not await check_wedding_access(current_user, table.wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    table_data = table.dict()
    result = await mongo.db["tables"].insert_one(table_data)

    # Clean up response
    response_data = table_data.copy()
    if "_id" in response_data:
        response_data["id"] = str(response_data["_id"])
        del response_data["_id"]
    else:
        response_data["id"] = str(result.inserted_id)

    # Ensure no ObjectId remains in values
    for k, v in response_data.items():
        if isinstance(v, ObjectId):
            response_data[k] = str(v)

    return response_data


@router.put("/tables/{table_id}", tags=["Seating"])
async def update_table(
    table_id: str,
    update_data: UpdateTableRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Update table properties"""
    enforce_team_permission(current_user, "manage_seating")
    try:
        oid = ObjectId(table_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid table ID")

    # First get the table to check wedding_id access
    table = await mongo.db["tables"].find_one({"_id": oid})
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if not await check_wedding_access(current_user, table["wedding_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

    if update_dict:
        await mongo.db["tables"].update_one({"_id": oid}, {"$set": update_dict})

    return {"message": "Table updated successfully"}


@router.delete("/tables/{table_id}", tags=["Seating"])
async def delete_table(
    table_id: str, current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Delete a table and unassign its guests"""
    enforce_team_permission(current_user, "manage_seating")
    try:
        oid = ObjectId(table_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid table ID")

    # First get the table to check wedding_id access
    table = await mongo.db["tables"].find_one({"_id": oid})
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if not await check_wedding_access(current_user, table["wedding_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Unassign guests assigned to this table (scoped to wedding for security)
    await mongo.db["guests"].update_many(
        {"table_id": table_id, "wedding_id": table["wedding_id"]},
        {"$set": {"table_id": None}},
    )

    # Delete the table
    await mongo.db["tables"].delete_one({"_id": oid})

    return {"message": "Table deleted and guests unassigned"}


@router.post("/tables/assign", tags=["Seating"])
async def assign_guests(
    request: AssignGuestsRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Bulk assign guests to a table"""
    enforce_team_permission(current_user, "manage_seating")
    try:
        table_oid = ObjectId(request.table_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid table ID")

    # Validate table exists and check access
    table = await mongo.db["tables"].find_one({"_id": table_oid})
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if not await check_wedding_access(current_user, table["wedding_id"]):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    # Validate guest IDs — report invalid ones instead of silently skipping
    guest_object_ids = []
    invalid_ids = []
    for gid in request.guest_ids:
        try:
            guest_object_ids.append(ObjectId(gid))
        except InvalidId:
            invalid_ids.append(gid)

    if invalid_ids:
        raise HTTPException(
            status_code=400, detail=f"Invalid guest IDs: {', '.join(invalid_ids)}"
        )

    if not guest_object_ids:
        return {"message": "No guest IDs provided", "assigned": 0}

    # Check capacity: count current guests at table + new guests (excluding those already at table)
    current_guests_count = await mongo.db["guests"].count_documents(
        {"table_id": request.table_id, "wedding_id": table["wedding_id"]}
    )

    # Count how many of the requested guests are NOT already at this table
    guests_already_at_table = await mongo.db["guests"].count_documents(
        {
            "_id": {"$in": guest_object_ids},
            "table_id": request.table_id,
            "wedding_id": table["wedding_id"],
        }
    )

    new_guests_count = len(guest_object_ids) - guests_already_at_table
    total_after_assign = current_guests_count + new_guests_count

    if total_after_assign > table.get("capacity", 10):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot assign guests: table capacity is {table.get('capacity', 10)}, "
            f"would have {total_after_assign} guests after assignment",
        )

    # Bulk update guests
    if guest_object_ids:
        result = await mongo.db["guests"].update_many(
            {"_id": {"$in": guest_object_ids}, "wedding_id": table["wedding_id"]},
            {"$set": {"table_id": request.table_id}},
        )

        # Post-update capacity check for concurrent assignment safety (T8)
        post_count = await mongo.db["guests"].count_documents(
            {"table_id": request.table_id, "wedding_id": table["wedding_id"]}
        )
        if post_count > table.get("capacity", 10):
            # Rollback: unassign the guests we just assigned
            logger.warning(
                f"Concurrent assignment exceeded capacity on table {request.table_id}: "
                f"{post_count}/{table.get('capacity', 10)}. Rolling back."
            )
            await mongo.db["guests"].update_many(
                {"_id": {"$in": guest_object_ids}, "wedding_id": table["wedding_id"]},
                {"$set": {"table_id": None}},
            )
            raise HTTPException(
                status_code=409,
                detail=f"Table capacity exceeded due to concurrent assignment. "
                f"Please retry. Capacity: {table.get('capacity', 10)}",
            )

        actually_modified = result.modified_count
    else:
        actually_modified = 0

    return {
        "message": f"Assigned {actually_modified} guests to table",
        "assigned": actually_modified,
    }


@router.post("/tables/unassign", tags=["Seating"])
async def unassign_guests(
    guest_ids: List[str] = Body(...),
    wedding_id: str = Body(...),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Bulk unassign guests"""
    enforce_team_permission(current_user, "manage_seating")
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    guest_object_ids = []
    for gid in guest_ids:
        try:
            guest_object_ids.append(ObjectId(gid))
        except InvalidId:
            continue

    if guest_object_ids:
        await mongo.db["guests"].update_many(
            {"_id": {"$in": guest_object_ids}, "wedding_id": wedding_id},
            {"$set": {"table_id": None}},
        )

    return {"message": f"Unassigned {len(guest_object_ids)} guests"}


@router.get("/tables/{wedding_id}/export/pdf", tags=["Seating"])
async def export_seating_chart_pdf(
    wedding_id: str,
    layout: str = Query(
        "visual",
        description="Layout style: visual (floor plan) or list (table-by-table)",
    ),
    size: str = Query(
        "poster",
        description="Paper size: poster (24x18 inches) or tabloid (11x17 inches)",
    ),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """
    Export seating chart as a printable PDF.

    Layout options:
    - **visual**: Floor plan layout with positioned tables (best for venue display)
    - **list**: Table-by-table guest list format (best for printing/reference)

    Size options:
    - **poster**: 24x18 inches (large venue display)
    - **tabloid**: 11x17 inches (standard print shop)
    """
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        # Import service here to avoid circular imports and handle missing dependency
        from app.services.seating_export_service import seating_export_service

        # Get wedding name for PDF header (handle both string and ObjectId formats)
        wedding_oid = (
            ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id
        )
        wedding = await mongo.db["weddings"].find_one({"_id": wedding_oid})
        wedding_name = wedding.get("couple_names", "Wedding") if wedding else "Wedding"

        # Validate parameters
        if layout not in ("visual", "list"):
            layout = "visual"
        if size not in ("poster", "tabloid"):
            size = "poster"

        # Generate PDF
        pdf_bytes = await seating_export_service.generate_seating_chart_pdf(
            wedding_id=wedding_id,
            wedding_name=wedding_name,
            layout_style=layout,
            paper_size=size,
        )

        # Create safe filename
        safe_name = "".join(
            c if c.isalnum() or c in " -_" else "_" for c in wedding_name
        )
        filename = f"{safe_name}_seating_chart_{size}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ImportError as e:
        logger.error(f"PDF generation dependency missing: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="PDF generation not available. WeasyPrint may not be installed.",
        )
    except Exception as e:
        logger.error(f"Failed to generate seating chart PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")
