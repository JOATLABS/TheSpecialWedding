from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.core.database import mongo
from app.utils.pydantic_objectid import PyObjectId
from app.services.platform_metrics_service import PlatformMetricsService

router = APIRouter()

def _normalize_datetime(value: Any) -> Optional[datetime]:
    """Convert supported datetime representations to datetime objects."""
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                return datetime.strptime(normalized, "%Y-%m-%d")
            except ValueError:
                return None

    return None


def _is_within_period(value: Any, lower_bound: datetime) -> bool:
    parsed = _normalize_datetime(value)
    return bool(parsed and parsed >= lower_bound)


def _is_upcoming(date_value: Any, reference: datetime) -> bool:
    if isinstance(date_value, str):
        try:
            event_date = datetime.strptime(date_value, "%Y-%m-%d")
            return event_date.date() >= reference.date()
        except ValueError:
            pass

    parsed = _normalize_datetime(date_value)
    return bool(parsed and parsed.date() >= reference.date())

# ==================== SAAS CONFIGURATION MANAGEMENT ====================

def _get_default_saas_config():
    """Shared default configuration used by both admin and public endpoints"""
    return {
        # Legacy hero fields (backward compatibility)
        "hero_title": "Welcome to Special Wedding",
        "hero_subtitle": "Wedding Planning Made Simple",
        "hero_description": "The ultimate wedding planning platform for professional wedding planners. Manage multiple weddings, coordinate with vendors, and create beautiful wedding websites with AI-powered tools.",

        # Modern hero fields (benefit-driven)
        "hero_headline": "Manage 10+ Weddings Simultaneously",
        "hero_subheadline": "For Professional Wedding Planners",
        "hero_problem_statement": "Stop juggling spreadsheets, email chains, and vendor chaos",
        "hero_solution_statement": "One platform to manage guests, vendors, timelines, and budgets—all in sync",

        # CTA buttons
        "hero_cta_primary": "Start Free Trial",
        "hero_cta_secondary": "Watch Demo",
        "contact_cta_label": "Contact Sales",
        "contact_url": "mailto:sales@specialwedding.com",

        # Product showcase
        "hero_screenshot_primary": None,
        "hero_screenshot_secondary": None,
        "demo_video_url": None,
        "show_product_demo": False,

        # Layout settings
        "hero_layout": "split",
        "hero_image_position": "right",
        "show_decorative_logo": True,  # Keep legacy design by default

        # Trust indicators
        "trust_indicators": ["Free 30-day trial", "No setup fees", "Cancel anytime"],

        # Legacy statistics (generic)
        "statistics": [
            {"label": "Wedding Planners Trust Us", "value": "500+"},
            {"label": "Weddings Managed", "value": "10K+"},
            {"label": "Uptime Guarantee", "value": "99.9%"}
        ],
        "statistics_enabled": True,

        # Modern impact metrics (specific, measurable)
        "impact_metrics": [
            {"metric": "15 hours/week", "label": "Average time saved per planner"},
            {"metric": "80%", "label": "Reduction in vendor miscommunication"},
            {"metric": "2.5x", "label": "Increase in weddings managed per year"}
        ],
        "show_impact_metrics": False,  # Disabled by default, admin can enable

        # Customer logos (social proof)
        "customer_logos": [],
        "show_customer_logos": False,

        # Content sections
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

        # Section toggles
        "features_enabled": True,
        "benefits_enabled": True,
        "testimonials_enabled": True,

        # Theme configuration
        "theme": {
            "primary_color": "#1e3a5f",
            "secondary_color": "#d4af37",
            "fallback_images": [
                "/wedding-images/wedding-ceremony.jpg",
                "/wedding-images/wedding-reception.jpg"
            ]
        },

        # Animation settings
        "animations_enabled": True,
        "scroll_animations": True,
        "animation_speed": "medium",

        # Trial settings
        "trial_settings": {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }
    }

@router.get("/saas-config", tags=["ROOT_ADMIN"])
async def get_saas_config(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get current SAAS configuration - ROOT_ADMIN only"""
    try:
        config = await mongo.db["saas_config"].find_one({"type": "main_config"})
        if not config:
            # Return default config if none exists
            return _get_default_saas_config()

        # Convert ObjectId to string for JSON serialization
        config["_id"] = str(config["_id"])

        # Ensure all new fields have defaults if missing
        default_config = _get_default_saas_config()
        for key, value in default_config.items():
            if key not in config:
                config[key] = value

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
                "last_login": planner.get("last_login").isoformat() if planner.get("last_login") else None
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
        planner = mongo.get_users_collection().find_one({"_id": PyObjectId(planner_id)})
        if not planner:
            raise HTTPException(status_code=404, detail="Wedding planner not found")

        new_status = not planner.get("is_active", True)

        # Update status
        mongo.get_users_collection().update_one(
            {"_id": PyObjectId(planner_id)},
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
async def get_public_saas_config():
    """Get SAAS configuration for public landing page - No auth required"""
    try:
        config = await mongo.db["saas_config"].find_one({"type": "main_config"})
        if not config:
            # Return default config if none exists
            return _get_default_saas_config()

        # Return all config fields (no need to filter for public use)
        # Remove only MongoDB internal fields
        if "_id" in config:
            del config["_id"]

        # Ensure all new fields have defaults if missing
        default_config = _get_default_saas_config()
        for key, value in default_config.items():
            if key not in config:
                config[key] = value

        return config

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

        # Calculate revenue based on active subscriptions
        monthly_revenue = 0
        yearly_revenue = 0

        # Get all users with active subscriptions
        active_users = mongo.get_users_collection().find({
            "subscription_status": {"$in": ["trial", "active"]},
            "is_active": True
        })

        for user in active_users:
            # Skip trial users for revenue calculation
            if user.get("subscription_status") == "trial":
                continue

            plan_id = user.get("subscription_plan_id")
            if plan_id:
                # Get the subscription plan
                plan = mongo.get_subscription_plans_collection().find_one({"_id": plan_id})
                if plan:
                    monthly_revenue += plan.get("price_monthly", 0)
                    yearly_revenue += plan.get("price_yearly", 0)

        # Calculate projected annual revenue from current monthly subscriptions
        projected_annual_revenue = monthly_revenue * 12

        return {
            "total_planners": total_planners,
            "active_planners": active_planners,
            "total_weddings": total_weddings,
            "active_plans": active_plans,
            "monthly_revenue": monthly_revenue,
            "yearly_revenue": yearly_revenue,
            "projected_annual_revenue": projected_annual_revenue
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching overview analytics: {str(e)}")

@router.get("/analytics/revenue", tags=["ROOT_ADMIN"])
def get_revenue_analytics(current_user: ExtendedAuthUser = Depends(require_root_admin)):
    """Get detailed revenue analytics for ROOT_ADMIN"""
    try:
        # Revenue by subscription plan
        plan_revenue = []
        plans = mongo.get_subscription_plans_collection().find({"is_active": True})

        for plan in plans:
            plan_id = plan["_id"]

            # Count active users on this plan
            active_users_count = mongo.get_users_collection().count_documents({
                "subscription_plan_id": plan_id,
                "subscription_status": "active",
                "is_active": True
            })

            # Count trial users on this plan
            trial_users_count = mongo.get_users_collection().count_documents({
                "subscription_plan_id": plan_id,
                "subscription_status": "trial",
                "is_active": True
            })

            plan_monthly_revenue = active_users_count * plan.get("price_monthly", 0)
            plan_yearly_revenue = active_users_count * plan.get("price_yearly", 0)

            plan_revenue.append({
                "plan_name": plan.get("name"),
                "plan_id": str(plan_id),
                "active_users": active_users_count,
                "trial_users": trial_users_count,
                "monthly_revenue": plan_monthly_revenue,
                "yearly_revenue": plan_yearly_revenue,
                "price_monthly": plan.get("price_monthly", 0),
                "price_yearly": plan.get("price_yearly", 0)
            })

        # Calculate totals
        total_monthly_revenue = sum(plan["monthly_revenue"] for plan in plan_revenue)
        total_yearly_revenue = sum(plan["yearly_revenue"] for plan in plan_revenue)
        total_active_users = sum(plan["active_users"] for plan in plan_revenue)
        total_trial_users = sum(plan["trial_users"] for plan in plan_revenue)

        # Average revenue per user
        arpu_monthly = total_monthly_revenue / total_active_users if total_active_users > 0 else 0
        arpu_yearly = total_yearly_revenue / total_active_users if total_active_users > 0 else 0

        return {
            "summary": {
                "total_monthly_revenue": total_monthly_revenue,
                "total_yearly_revenue": total_yearly_revenue,
                "projected_annual_revenue": total_monthly_revenue * 12,
                "total_active_users": total_active_users,
                "total_trial_users": total_trial_users,
                "arpu_monthly": arpu_monthly,
                "arpu_yearly": arpu_yearly
            },
            "plan_breakdown": plan_revenue,
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching revenue analytics: {str(e)}")



@router.get("/analytics/platform", tags=["ROOT_ADMIN"])
async def get_platform_metrics(
    timeframe: str = Query(
        "30d",
        description="Timeframe window for growth metrics (supported: 7d, 30d, 90d, 1y)",
    ),
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Aggregate platform-level metrics for the admin analytics dashboard."""
    service = PlatformMetricsService(mongo)

    try:
        return await service.compile_metrics(timeframe.lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error compiling platform metrics: {str(exc)}",
        )

@router.get("/trial-settings", tags=["ROOT_ADMIN", "Public"])
def get_trial_settings():
    """Get trial settings from SAAS config - Can be used by both admin and registration"""
    try:
        config = mongo.db["saas_config"].find_one({"type": "main_config"})

        if config and "trial_settings" in config:
            return config["trial_settings"]

        # Return default trial settings if none configured
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }

    except Exception as e:
        # Return defaults on error to prevent registration failures
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False
        }