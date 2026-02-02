"""
Guest Export API

Endpoints for exporting guest data:
- Single guest QR code (PNG)
- Guest list PDF
- Bulk QR codes (ZIP)
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import StreamingResponse
from app.dependencies.auth_extended import require_wedding_planner_only, ExtendedAuthUser, check_wedding_access
from app.services.guest_export_service import guest_export_service
from app.core.database import mongo
from bson import ObjectId
from pydantic import BaseModel
from typing import List, Optional
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class QRExportRequest(BaseModel):
    """Request model for bulk QR export"""
    guest_ids: List[str] = []  # Empty list means all guests
    wedding_id: str


@router.get("/guests/{guest_id}/qr", tags=["Guest Export"])
async def get_guest_qr(
    guest_id: str,
    wedding_id: str = Query(..., description="Wedding ID for verification"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Get QR code PNG for a single guest.

    The QR code links to the guest's RSVP page.
    """
    # Check wedding access
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    result = await guest_export_service.get_single_guest_qr(guest_id, wedding_id)

    if not result:
        raise HTTPException(status_code=404, detail="Guest not found or missing token")

    qr_bytes, filename = result

    return Response(
        content=qr_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename={filename}",
            "Cache-Control": "private, max-age=3600"
        }
    )


@router.get("/guests/{guest_id}/qr/download", tags=["Guest Export"])
async def download_guest_qr(
    guest_id: str,
    wedding_id: str = Query(..., description="Wedding ID for verification"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Download QR code PNG for a single guest.

    Same as /qr but with attachment header for download.
    """
    # Check wedding access
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    result = await guest_export_service.get_single_guest_qr(guest_id, wedding_id)

    if not result:
        raise HTTPException(status_code=404, detail="Guest not found or missing token")

    qr_bytes, filename = result

    return Response(
        content=qr_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/guests/export/pdf", tags=["Guest Export"])
async def export_guest_list_pdf(
    wedding_id: str = Query(..., description="Wedding ID"),
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Export guest list as a printable PDF.

    Includes columns: Name, Phone, Email, Group, RSVP Status, Dietary
    Footer shows summary statistics.
    """
    # Check wedding access
    if not await check_wedding_access(current_user, wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        # Get wedding name for the PDF header (handle both string and ObjectId formats)
        wedding_oid = ObjectId(wedding_id) if ObjectId.is_valid(wedding_id) else wedding_id
        wedding = await mongo.db["weddings"].find_one({"_id": wedding_oid})
        wedding_name = wedding.get("couple_names", "Wedding") if wedding else "Wedding"

        pdf_bytes = await guest_export_service.generate_guest_list_pdf(
            wedding_id=wedding_id,
            wedding_name=wedding_name
        )

        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in wedding_name)
        filename = f"{safe_name}_guest_list.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except ImportError as e:
        logger.error(f"PDF generation dependency missing: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="PDF generation not available. WeasyPrint may not be installed."
        )
    except Exception as e:
        logger.error(f"Failed to generate guest list PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.post("/guests/export/qr-zip", tags=["Guest Export"])
async def export_qr_codes_zip(
    request: QRExportRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner_only)
):
    """
    Export QR codes as a ZIP file.

    If guest_ids is empty, exports all guests for the wedding.
    Each QR code is named: GuestName_token.png
    """
    # Check wedding access
    if not await check_wedding_access(current_user, request.wedding_id):
        raise HTTPException(status_code=403, detail="Access to this wedding denied")

    try:
        from bson import ObjectId

        guest_collection = mongo.get_guest_collection()
        wedding_collection = mongo.db["weddings"]

        # Get wedding slug
        wedding = await wedding_collection.find_one({"_id": request.wedding_id})
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")

        slug = wedding.get("slug", "")
        if not slug:
            raise HTTPException(status_code=400, detail="Wedding has no slug configured")

        # Get guests
        if request.guest_ids:
            # Specific guests
            guest_object_ids = [ObjectId(gid) for gid in request.guest_ids]
            guests = await guest_collection.find({
                "_id": {"$in": guest_object_ids},
                "wedding_id": request.wedding_id
            }).to_list(length=None)
        else:
            # All guests for the wedding
            guests = await guest_collection.find({
                "wedding_id": request.wedding_id
            }).to_list(length=None)

        if not guests:
            raise HTTPException(status_code=404, detail="No guests found")

        # Convert guests to dict format expected by service
        guests_list = []
        for guest in guests:
            guests_list.append({
                "id": str(guest["_id"]),
                "name": guest.get("name", "Unknown"),
                "token": guest.get("token", "")
            })

        # Generate ZIP
        zip_bytes = await guest_export_service.generate_guests_qr_zip(guests_list, slug)

        # Create filename
        wedding_name = wedding.get("couple_names", "Wedding")
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in wedding_name)
        filename = f"{safe_name}_qr_codes.zip"

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate QR ZIP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate ZIP: {str(e)}")
