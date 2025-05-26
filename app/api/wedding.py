from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.wedding import WeddingModel
from app.services.wedding_service import WeddingService
from app.dependencies.auth import require_admin

router = APIRouter()
wedding_service = WeddingService()

@router.post("/weddings", dependencies=[Depends(require_admin)], tags=["Admin"])
def create_wedding(wedding: WeddingModel):
    """Create a new wedding"""
    return wedding_service.create_wedding(wedding)

@router.get("/weddings", tags=["Wedding"])
def list_weddings():
    """List all weddings"""
    return wedding_service.list_weddings()

@router.get("/weddings/{wedding_id}", tags=["Wedding"])
def get_wedding(wedding_id: str):
    """Get a wedding by ID"""
    return wedding_service.get_wedding(wedding_id)

@router.get("/weddings/slug/{slug}", tags=["Wedding"])
def get_wedding_by_slug(slug: str):
    """Get a wedding by slug"""
    return wedding_service.get_wedding_by_slug(slug)

@router.put("/weddings/{wedding_id}", dependencies=[Depends(require_admin)], tags=["Admin"])
def update_wedding(wedding_id: str, wedding: dict):
    """Update a wedding"""
    return wedding_service.update_wedding(wedding_id, wedding)

@router.delete("/weddings/{wedding_id}", dependencies=[Depends(require_admin)], tags=["Admin"])
def delete_wedding(wedding_id: str):
    """Delete a wedding"""
    return wedding_service.delete_wedding(wedding_id)