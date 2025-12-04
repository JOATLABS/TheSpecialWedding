from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.checklist_service import ChecklistService
from app.services.auth_service import require_admin_auth
from typing import List
import logging

router = APIRouter(prefix="/admin/weddings/{wedding_id}/checklist", tags=["Admin"])
checklist_service = ChecklistService()

@router.get("", dependencies=[Depends(require_admin_auth)])
def get_checklist(wedding_id: str):
    try:
        checklist = checklist_service.get_checklist_for_wedding(wedding_id)
        if checklist is None:
            raise HTTPException(status_code=404, detail="Checklist not found")
        return checklist
    except (ValueError, KeyError) as e:
        logging.warning(f"Checklist not found for wedding {wedding_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error fetching checklist for wedding {wedding_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")

@router.put("/{item_id}", dependencies=[Depends(require_admin_auth)])
def update_checklist_item(wedding_id: str, item_id: str, completed: bool = Query(...)):
    try:
        updated_item = checklist_service.update_checklist_item(item_id, completed)
        if updated_item is None:
            raise HTTPException(status_code=404, detail="Checklist item not found")
        return updated_item
    except (ValueError, KeyError) as e:
        logging.warning(f"Checklist item not found {item_id} for wedding {wedding_id}: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logging.error(f"Error updating checklist item {item_id} for wedding {wedding_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.")
