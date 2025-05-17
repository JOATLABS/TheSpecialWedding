from fastapi import APIRouter, Response, Depends, Header, HTTPException
from app.services.admin_rsvp_service import AdminRSVPService

router = APIRouter()

admin_service = AdminRSVPService()

API_KEY = "secureadminkey123"  # In real setup, use env var or JWT auth

def verify_admin(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.get("/admin/rsvps", tags=["Admin"], dependencies=[Depends(verify_admin)])
def get_rsvps():
    return admin_service.get_all_rsvps()

@router.get("/admin/rsvps/export", tags=["Admin"], dependencies=[Depends(verify_admin)])
def export_rsvps():
    csv_data = admin_service.export_rsvps_to_csv()
    return Response(content=csv_data, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=rsvps.csv"
    })