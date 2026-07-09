import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser, require_admin_or_planner
from app.services.cloudflare_service import CloudflareService, CloudflareServiceError

logger = logging.getLogger(__name__)
router = APIRouter()
public_router = APIRouter()

class StorefrontSettingsModel(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    hero_image_url: Optional[str] = None
    about_image_url: Optional[str] = None
    theme_color: Optional[str] = Field(None, max_length=20)
    packages_enabled: bool = True
    reviews_enabled: bool = True
    custom_domain: Optional[str] = None

class CustomDomainRequest(BaseModel):
    domain: str

@router.post("/storefront/custom-domain")
async def add_custom_domain(
    req: CustomDomainRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Add a custom domain and configure Cloudflare for SaaS."""
    user_id = str((current_user.user_data or {}).get("_id", ""))
    
    try:
        cf_response = await CloudflareService.add_custom_hostname(req.domain)
    except CloudflareServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    update_data = {
        "custom_domain": req.domain,
        "cloudflare_hostname_id": cf_response.get("id"),
        "cloudflare_hostname_status": cf_response.get("status"),
        "ownership_verification": cf_response.get("ownership_verification")
    }
    
    await mongo.db["storefront_settings"].update_one(
        {"planner_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return {"status": "success", "data": update_data}

@router.get("/storefront/custom-domain/status")
async def get_custom_domain_status(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get the current DNS verification status of the custom domain."""
    user_id = str((current_user.user_data or {}).get("_id", ""))
    settings = await mongo.db["storefront_settings"].find_one({"planner_id": user_id})
    
    if not settings or not settings.get("cloudflare_hostname_id"):
        return {"status": "none"}
        
    hostname_id = settings["cloudflare_hostname_id"]
    try:
        cf_response = await CloudflareService.get_custom_hostname_status(hostname_id)
        if cf_response:
            # Update DB with latest status
            await mongo.db["storefront_settings"].update_one(
                {"planner_id": user_id},
                {"$set": {"cloudflare_hostname_status": cf_response.get("status")}}
            )
            return {"status": "success", "data": cf_response}
    except CloudflareServiceError:
        pass
        
    # Fallback to cached data
    return {
        "status": "success", 
        "data": {
            "status": settings.get("cloudflare_hostname_status", "pending"), 
            "ownership_verification": settings.get("ownership_verification")
        }
    }

@router.delete("/storefront/custom-domain")
async def remove_custom_domain(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Remove the custom domain configuration."""
    user_id = str((current_user.user_data or {}).get("_id", ""))
    settings = await mongo.db["storefront_settings"].find_one({"planner_id": user_id})
    
    if settings and settings.get("cloudflare_hostname_id"):
        hostname_id = settings["cloudflare_hostname_id"]
        try:
            await CloudflareService.delete_custom_hostname(hostname_id)
        except CloudflareServiceError:
            pass # Ignore deletion errors to allow users to force-remove from their DB
            
    await mongo.db["storefront_settings"].update_one(
        {"planner_id": user_id},
        {"$unset": {
            "custom_domain": "", 
            "cloudflare_hostname_id": "", 
            "cloudflare_hostname_status": "", 
            "ownership_verification": ""
        }}
    )
    
    return {"status": "success"}

@router.get("/storefront/settings")
async def get_storefront_settings(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get the planner's storefront settings."""
    user_id = str((current_user.user_data or {}).get("_id", ""))
    
    settings = await mongo.db["storefront_settings"].find_one({"planner_id": user_id})
    if not settings:
        return {"settings": None}
    
    # Exclude _id
    settings.pop("_id", None)
    return {"settings": settings}

@router.post("/storefront/settings")
async def update_storefront_settings(
    settings: StorefrontSettingsModel,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Update the planner's storefront settings."""
    user_id = str((current_user.user_data or {}).get("_id", ""))
    
    update_data = settings.dict(exclude_unset=True)
    update_data["planner_id"] = user_id
    
    result = await mongo.db["storefront_settings"].update_one(
        {"planner_id": user_id},
        {"$set": update_data},
        upsert=True
    )
    
    return {"status": "success", "settings": update_data}


@router.get("/storefront/upload-url")
async def get_storefront_upload_url(
    filename: str = Query(..., min_length=1),
    content_type: str = Query(default="image/jpeg"),
    folder: str = Query(default="storefront"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner),
):
    """Get a presigned URL to upload a storefront image directly to R2.

    Uses the same BLOG_ASSETS bucket and BlogUploadService as the blog
    image upload flow, but under a ``storefront/`` key prefix so files
    are logically separated.
    """
    from app.services.blog_upload_service import BlogUploadService

    blog_upload = BlogUploadService()
    return blog_upload.create_presigned_upload_url(
        filename=filename,
        folder=folder,
        content_type=content_type,
    )

@public_router.get("/storefront/{domain_or_planner_id}")
async def get_public_storefront(domain_or_planner_id: str):
    """Public endpoint to fetch storefront data by custom domain or planner ID."""
    # First try to find by custom domain
    settings = await mongo.db["storefront_settings"].find_one({"custom_domain": domain_or_planner_id})
    
    if not settings:
        # Fallback to planner ID
        settings = await mongo.db["storefront_settings"].find_one({"planner_id": domain_or_planner_id})
        
    if not settings:
        # Check if the domain_or_planner_id is actually a valid user ID (for a preview before saving)
        try:
            planner_check = await mongo.get_users_collection().find_one({"_id": ObjectId(domain_or_planner_id)})
            if planner_check:
                settings = {
                    "planner_id": domain_or_planner_id,
                    "title": None,
                    "description": None,
                    "hero_image_url": None,
                    "about_image_url": None,
                    "theme_color": "#0f172a",
                    "packages_enabled": True,
                    "reviews_enabled": True,
                    "custom_domain": None,
                }
        except Exception:
            pass

    if not settings:
        # If it's literally "preview", maybe just 404 or provide dummy. We'll raise 404.
        raise HTTPException(status_code=404, detail="Storefront not found")
        
    planner_id = settings["planner_id"]
    
    # Fetch planner details
    planner = await mongo.get_users_collection().find_one({"_id": ObjectId(planner_id)})
    if not planner:
        raise HTTPException(status_code=404, detail="Planner not found")
        
    # Fetch packages
    packages_cursor = mongo.db["packages"].find({"user_id": planner_id})
    packages = await packages_cursor.to_list(length=50)
    
    # Fetch reviews (from external integrations or manual entry)
    # For now, we mock or fetch from a 'planner_reviews' collection
    reviews_cursor = mongo.db["planner_reviews"].find({"planner_id": planner_id, "is_published": True})
    reviews = await reviews_cursor.to_list(length=20)
    
    settings.pop("_id", None)
    
    # Format packages and reviews to remove ObjectId
    for p in packages:
        p["_id"] = str(p["_id"])
    for r in reviews:
        r["_id"] = str(r["_id"])
        
    return {
        "storefront": settings,
        "planner": {
            "company_name": planner.get("company_name"),
            "first_name": planner.get("first_name"),
            "last_name": planner.get("last_name"),
            "profile_image_url": planner.get("profile_image_url"),
            "support_phone": planner.get("support_phone"),
            "email": planner.get("email"),
        },
        "packages": packages if settings.get("packages_enabled", True) else [],
        "reviews": reviews if settings.get("reviews_enabled", True) else []
    }
