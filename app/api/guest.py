from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.guest_service import GuestService

router = APIRouter()

guest_service = GuestService()

@router.get("/invite/{token}", tags=["Guest"])
def get_guest(token: str, wedding_id: str = Query(...)):
    try:
        return guest_service.get_guest_by_token(token, wedding_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")

@router.get("/invite/search", tags=["Guest"])
def search_guest(phone: str = Query(None), name: str = Query(None)):
    try:
        return guest_service.get_guest_by_phone_or_name(phone=phone, name=name)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unexpected error occurred")



# from fastapi import APIRouter, Depends, HTTPException, Query
# from app.services.guest_service import GuestService

# router = APIRouter()

# guest_service = GuestService()

# @router.get("/invite/{token}", tags=["Guest"])
# def get_guest(token: str):
#     try:
#         return guest_service.get_guest_by_token(token)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Unexpected error occurred")

# @router.get("/invite/search", tags=["Guest"])
# def search_guest(phone: str = Query(None), name: str = Query(None)):
#     try:
#         return guest_service.get_guest_by_phone_or_name(phone=phone, name=name)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail="Unexpected error occurred")
# # Defines a FastAPI router for handling guest-related API endpoints.