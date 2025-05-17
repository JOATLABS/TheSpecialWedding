from fastapi import APIRouter, Response, Depends
from app.services.admin_rsvp_service import AdminRSVPService
from app.dependencies.auth import require_admin

router = APIRouter()

admin_service = AdminRSVPService()

@router.get("/rsvps", tags=["Admin"], dependencies=[Depends(require_admin)])
def get_rsvps():
    return admin_service.get_all_rsvps()

@router.get("/rsvps/export", tags=["Admin"], dependencies=[Depends(require_admin)])
def export_rsvps():
    csv_data = admin_service.export_rsvps_to_csv()
    return Response(content=csv_data, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=rsvps.csv"
    })