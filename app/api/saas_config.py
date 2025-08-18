from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database import mongo
from bson import ObjectId
from datetime import datetime

router = APIRouter()

# ==================== SAAS CONFIGURATION MANAGEMENT ====================

@router.get("/saas-config", tags=["ROOT_ADMIN"])
def get_saas_config(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get current SAAS configuration - ROOT_ADMIN only"""
    try:
        config = mongo.db["saas_config"].find_one({"type": "main_config"})
        if not config:
            # Return default config if none exists
            return {
                "hero_title": "Welcome to Special Wedding",
                "hero_subtitle": "Wedding Planning Made Simple",
                "hero_description": "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
                "hero_cta_primary": "Start Free Trial",
                "hero_cta_secondary": "Watch Demo",
                "trust_indicators": ["Free 30-day trial", "No setup fees", "Cancel anytime"],
                "statistics": [
                    {"label": "Wedding Planners Trust Us", "value": "500+"},
                    {"label": "Weddings Managed", "value": "10K+"},
                    {"label": "Uptime Guarantee", "value": "99.9%"}
                ],
                "features": [
                    {
                        "title": "Complete Wedding Management",
                        "description": "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
                        "status": "available",
                        "order": 1
                    },
                    {
                        "title": "AI Presentation Generator",
                        "description": "Create stunning wedding presentations in minutes with our AI-powered design tools.",
                        "status": "coming_soon",
                        "order": 5
                    }
                ],
                "benefits": [
                    {
                        "title": "Save Time",
                        "description": "Automate repetitive tasks and streamline wedding planning operations",
                        "order": 1
                    },
                    {
                        "title": "Scale Your Business",
                        "description": "Manage multiple weddings efficiently and grow your planning business",
                        "order": 2
                    }
                ],
                "testimonials": [
                    {
                        "name": "Sarah Johnson",
                        "company": "Elegant Events Planning",
                        "role": "Senior Wedding Planner",
                        "content": "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
                        "order": 1
                    }
                ],
                "features_enabled": True,
                "benefits_enabled": True,
                "testimonials_enabled": True,
                "statistics_enabled": True,
                "theme": {
                    "primary_color": "#1e3a5f",
                    "secondary_color": "#d4af37",
                    "fallback_images": [
                        "/wedding-images/wedding-ceremony.jpg",
                        "/wedding-images/wedding-reception.jpg"
                    ]
                }
            }
        
        # Convert ObjectId to string for JSON serialization
        config["_id"] = str(config["_id"])
        return config
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching SAAS config: {str(e)}")

@router.put("/saas-config", tags=["ROOT_ADMIN"])
def update_saas_config(
    config_data: Dict[str, Any], 
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update SAAS configuration - ROOT_ADMIN only"""
    try:
        # Add metadata
        config_data["type"] = "main_config"
        config_data["updated_by"] = current_user.email
        config_data["updated_at"] = datetime.utcnow()
        
        # Update or insert configuration
        result = mongo.db["saas_config"].update_one(
            {"type": "main_config"},
            {"$set": config_data},
            upsert=True
        )
        
        return {"message": "SAAS configuration updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating SAAS config: {str(e)}")

# ==================== CONTENT SECTIONS MANAGEMENT ====================

@router.get("/content-sections", tags=["ROOT_ADMIN"])
def get_content_sections(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get all content sections - ROOT_ADMIN only"""
    try:
        sections = list(mongo.db["content_sections"].find({}))
        
        # Convert ObjectId to string for JSON serialization
        for section in sections:
            section["_id"] = str(section["_id"])
        
        # Return default sections if none exist
        if not sections:
            return [
                {
                    "id": "hero_section",
                    "section": "hero",
                    "content": {
                        "title": "Welcome to Special Wedding",
                        "subtitle": "Wedding Planning Made Simple",
                        "description": "The ultimate wedding planning platform..."
                    },
                    "is_active": True,
                    "display_order": 1,
                    "updated_by": "system",
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "id": "features_section",
                    "section": "features",
                    "content": {
                        "title": "Powerful Features for Wedding Professionals",
                        "features": []
                    },
                    "is_active": True,
                    "display_order": 2,
                    "updated_by": "system",
                    "updated_at": datetime.utcnow().isoformat()
                }
            ]
        
        return sections
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching content sections: {str(e)}")

@router.put("/content-sections/{section_id}", tags=["ROOT_ADMIN"])
def update_content_section(
    section_id: str,
    section_data: Dict[str, Any],
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Update a content section - ROOT_ADMIN only"""
    try:
        # Add metadata
        section_data["updated_by"] = current_user.email
        section_data["updated_at"] = datetime.utcnow()
        
        # Update section
        result = mongo.db["content_sections"].update_one(
            {"section": section_id},
            {"$set": section_data},
            upsert=True
        )
        
        return {"message": f"Content section '{section_id}' updated successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating content section: {str(e)}")

# ==================== WEDDING PLANNERS MANAGEMENT ====================

@router.get("/wedding-planners", tags=["ROOT_ADMIN"])
def get_wedding_planners(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get all wedding planners - ROOT_ADMIN only"""
    try:
        # Get users with wedding_planner role
        planners = list(mongo.get_users_collection().find({"role": "wedding_planner"}))
        
        # Convert ObjectId to string and format data
        formatted_planners = []
        for planner in planners:
            planner["_id"] = str(planner["_id"])
            
            # Get assigned weddings count
            weddings_count = mongo.get_weddings_collection().count_documents({
                "assigned_planner_email": planner["email"]
            })
            
            formatted_planner = {
                "id": planner["_id"],
                "email": planner["email"],
                "company_name": planner.get("company_name", "Unknown Company"),
                "subscription_plan_id": planner.get("subscription_plan_id"),
                "subscription_status": planner.get("subscription_status", "inactive"),
                "max_weddings": planner.get("max_weddings", 0),
                "assigned_weddings_count": weddings_count,
                "is_active": planner.get("is_active", True),
                "created_at": planner.get("created_at", datetime.utcnow()).isoformat(),
                "last_login": planner.get("last_login", {}).get("$date") if planner.get("last_login") else None
            }
            formatted_planners.append(formatted_planner)
        
        return formatted_planners
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching wedding planners: {str(e)}")

@router.post("/wedding-planners", tags=["ROOT_ADMIN"])
def create_wedding_planner(
    planner_data: Dict[str, Any],
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Create a new wedding planner - ROOT_ADMIN only"""
    try:
        # Validate required fields
        if not planner_data.get("email"):
            raise HTTPException(status_code=400, detail="Email is required")
        
        # Check if user already exists
        existing_user = mongo.get_users_collection().find_one({"email": planner_data["email"]})
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Create user document
        user_doc = {
            "email": planner_data["email"],
            "role": "wedding_planner",
            "company_name": planner_data.get("company_name", ""),
            "subscription_plan_id": planner_data.get("subscription_plan_id"),
            "subscription_status": "inactive",
            "is_active": True,
            "created_by": current_user.email,
            "created_at": datetime.utcnow()
        }
        
        # Insert user
        result = mongo.get_users_collection().insert_one(user_doc)
        
        return {
            "message": "Wedding planner created successfully",
            "user_id": str(result.inserted_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating wedding planner: {str(e)}")

@router.put("/wedding-planners/{planner_id}/status", tags=["ROOT_ADMIN"])
def toggle_planner_status(
    planner_id: str,
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Toggle wedding planner active status - ROOT_ADMIN only"""
    try:
        # Get current status
        planner = mongo.get_users_collection().find_one({"_id": ObjectId(planner_id)})
        if not planner:
            raise HTTPException(status_code=404, detail="Wedding planner not found")
        
        new_status = not planner.get("is_active", True)
        
        # Update status
        mongo.get_users_collection().update_one(
            {"_id": ObjectId(planner_id)},
            {
                "$set": {
                    "is_active": new_status,
                    "updated_by": current_user.email,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "message": f"Planner {'activated' if new_status else 'deactivated'} successfully",
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating planner status: {str(e)}")

# ==================== PUBLIC SAAS CONFIGURATION ====================

@router.get("/config", tags=["Public"])
def get_public_saas_config():
    """Get SAAS configuration for public landing page - No auth required"""
    try:
        config = mongo.db["saas_config"].find_one({"type": "main_config"})
        if not config:
            # Return default config if none exists
            return {
                "hero_title": "Welcome to Special Wedding",
                "hero_subtitle": "Wedding Planning Made Simple",
                "hero_description": "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",
                "hero_cta_primary": "Start Free Trial",
                "hero_cta_secondary": "Watch Demo",
                "trust_indicators": ["Free 30-day trial", "No setup fees", "Cancel anytime"],
                "statistics": [
                    {"label": "Wedding Planners Trust Us", "value": "500+"},
                    {"label": "Weddings Managed", "value": "10K+"},
                    {"label": "Uptime Guarantee", "value": "99.9%"}
                ],
                "features": [
                    {
                        "title": "Complete Wedding Management",
                        "description": "Manage multiple weddings with ease. Track guests, RSVPs, vendors, and timelines all in one place.",
                        "status": "available",
                        "order": 1
                    },
                    {
                        "title": "AI Presentation Generator",
                        "description": "Create stunning wedding presentations in minutes with our AI-powered design tools.",
                        "status": "coming_soon",
                        "order": 5
                    }
                ],
                "benefits": [
                    {
                        "title": "Save Time",
                        "description": "Automate repetitive tasks and streamline wedding planning operations",
                        "order": 1
                    },
                    {
                        "title": "Scale Your Business",
                        "description": "Manage multiple weddings efficiently and grow your planning business",
                        "order": 2
                    }
                ],
                "testimonials": [
                    {
                        "name": "Sarah Johnson",
                        "company": "Elegant Events Planning",
                        "role": "Senior Wedding Planner",
                        "content": "Special Wedding has revolutionized how I manage my clients' weddings. The AI tools save me hours every week!",
                        "order": 1
                    }
                ],
                "features_enabled": True,
                "benefits_enabled": True,
                "testimonials_enabled": True,
                "statistics_enabled": True,
                "primary_color": "#1e3a5f",
                "secondary_color": "#d4af37",
                "fallback_images": [
                    "/wedding-images/wedding-ceremony.jpg",
                    "/wedding-images/wedding-reception.jpg"
                ]
            }
        
        # Remove private fields and prepare for public consumption
        public_config = {
            "hero_title": config.get("hero_title", "Welcome to Special Wedding"),
            "hero_subtitle": config.get("hero_subtitle", "Wedding Planning Made Simple"),
            "hero_description": config.get("hero_description", "The ultimate wedding planning platform for professional wedding planners."),
            "hero_cta_primary": config.get("hero_cta_primary", "Start Free Trial"),
            "hero_cta_secondary": config.get("hero_cta_secondary", "Watch Demo"),
            "trust_indicators": config.get("trust_indicators", ["Free 30-day trial", "No setup fees", "Cancel anytime"]),
            "statistics": config.get("statistics", []),
            "features": config.get("features", []),
            "benefits": config.get("benefits", []),
            "testimonials": config.get("testimonials", []),
            "features_enabled": config.get("features_enabled", True),
            "benefits_enabled": config.get("benefits_enabled", True),
            "testimonials_enabled": config.get("testimonials_enabled", True),
            "statistics_enabled": config.get("statistics_enabled", True),
            "primary_color": config.get("theme", {}).get("primary_color", "#1e3a5f"),
            "secondary_color": config.get("theme", {}).get("secondary_color", "#d4af37"),
            "fallback_images": config.get("theme", {}).get("fallback_images", [
                "/wedding-images/wedding-ceremony.jpg",
                "/wedding-images/wedding-reception.jpg"
            ])
        }
        
        return public_config
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching public SAAS config: {str(e)}")

@router.get("/analytics/overview", tags=["ROOT_ADMIN"])
def get_overview_analytics(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get overview analytics for dashboard - ROOT_ADMIN only"""
    try:
        # Get counts
        total_planners = mongo.get_users_collection().count_documents({"role": "wedding_planner"})
        active_planners = mongo.get_users_collection().count_documents({
            "role": "wedding_planner", 
            "is_active": True
        })
        total_weddings = mongo.get_weddings_collection().count_documents({})
        active_plans = mongo.get_subscription_plans_collection().count_documents({"is_active": True})
        
        # Calculate revenue (mock for now - would need subscription data)
        monthly_revenue = 0  # TODO: Calculate based on active subscriptions
        
        return {
            "total_planners": total_planners,
            "active_planners": active_planners,
            "total_weddings": total_weddings,
            "active_plans": active_plans,
            "monthly_revenue": monthly_revenue
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching overview analytics: {str(e)}")