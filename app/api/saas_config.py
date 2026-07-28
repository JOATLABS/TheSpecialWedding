import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.constants.roles import ROLE_WEDDING_PLANNER, is_wedding_planner_role
from app.core.database import mongo
from app.dependencies.auth_extended import ExtendedAuthUser, require_root_admin
from app.models.subscription import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    normalize_subscription_status,
)
from app.services.planner_access_lifecycle_service import (
    planner_access_lifecycle_service,
)
from app.services.platform_metrics_service import PlatformMetricsService
from app.utils.pydantic_objectid import PyObjectId

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_datetime(value: Any) -> datetime | None:
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
    """Shared default configuration used by both admin and public endpoints.

    These defaults match the hardcoded content from app/page.tsx so the
    admin-configured SaaS content stays aligned with the live homepage.
    """
    return {
        # Hero fields - matches page.tsx hero section
        "hero_title": "The Special Wedding",
        "hero_subtitle": "A stage-set platform where every wedding feels like a cinematic premiere",
        "hero_description": "Sculpt invitations, RSVP journeys, wedding websites, seating, timelines, and on-site orchestration—woven together with romantic motion and intelligent automation.",
        # Modern hero fields (benefit-driven)
        "hero_headline": "A stage-set platform where every wedding feels like a cinematic premiere",
        "hero_subheadline": "The Special Wedding",
        "hero_problem_statement": "Stop juggling spreadsheets, email chains, and vendor chaos",
        "hero_solution_statement": "Sculpt invitations, RSVP journeys, wedding websites, seating, timelines, and on-site orchestration—woven together with romantic motion and intelligent automation.",
        # CTA buttons
        "hero_cta_primary": "Explore pricing",
        "hero_cta_secondary": "Launch console",
        "contact_cta_label": "Contact Sales",
        "contact_url": "mailto:sales@thespecialwedding.io",
        # Product showcase
        "hero_screenshot_primary": None,
        "hero_screenshot_secondary": None,
        "demo_video_url": None,
        "show_product_demo": False,
        # Layout settings
        "hero_layout": "split",
        "hero_image_position": "right",
        "show_decorative_logo": True,
        # Trust indicators - partners from page.tsx
        "trust_indicators": ["Stripe", "Mailgun", "Mapbox", "Slack", "Zoom"],
        # Statistics/metrics - from page.tsx metrics array
        "statistics": [
            {"label": "Guest records managed across active weddings", "value": "48k"},
            {"label": "Average RSVP window to reach 90% response", "value": "5 days"},
            {"label": "Median guest memory upload completion time", "value": "43s"},
            {"label": "Automation reliability across reminders", "value": "99.9%"},
        ],
        "statistics_enabled": True,
        # Modern impact metrics
        "impact_metrics": [
            {"metric": "48k", "label": "Guest records managed across active weddings"},
            {"metric": "5 days", "label": "Average RSVP window to reach 90% response"},
            {"metric": "43s", "label": "Median guest memory upload completion time"},
            {"metric": "99.9%", "label": "Automation reliability across reminders"},
        ],
        "show_impact_metrics": True,
        # Customer logos (social proof)
        "customer_logos": ["Stripe", "Mailgun", "Mapbox", "Slack", "Zoom"],
        "show_customer_logos": True,
        # Features - all 10 from page.tsx
        "features": [
            {
                "title": "Guest lists & households",
                "description": "Unify invites, plus-ones, and households with filters for VIPs, vendors, and families.",
                "category": "Planning",
                "status": "available",
                "order": 1,
            },
            {
                "title": "Signature invitations",
                "description": "Send branded email invitations, track bounces, and personalize every RSVP link.",
                "category": "Engagement",
                "status": "available",
                "order": 2,
            },
            {
                "title": "Wedding websites",
                "description": "Launch a stunning site for every celebration with schedules, travel details, and galleries.",
                "category": "Experience",
                "status": "available",
                "order": 3,
            },
            {
                "title": "RSVP & meal selections",
                "description": "Capture attendance, meal preferences, allergies, and notes in real time.",
                "category": "Engagement",
                "status": "available",
                "order": 4,
            },
            {
                "title": "Seating orchestration",
                "description": "Map the venue, place fixtures and tables, respect family groupings, and export final charts.",
                "category": "Planning",
                "status": "available",
                "order": 5,
            },
            {
                "title": "Ceremony & reception timeline",
                "description": "Build the planner timeline and present prepared event details in the couple and public schedules.",
                "category": "Execution",
                "status": "available",
                "order": 6,
            },
            {
                "title": "Moments gallery",
                "description": "Collect guest photos, curate galleries, and share highlights after the celebration.",
                "category": "Celebration",
                "status": "available",
                "order": 7,
            },
            {
                "title": "Smart reminders",
                "description": "Automate nudges for RSVP deadlines, travel updates, and day-of changes.",
                "category": "Communication",
                "status": "available",
                "order": 8,
            },
            {
                "title": "Guest memories uploads",
                "description": "Share a QR code so guests can upload photos and videos from their phones without an app.",
                "category": "Celebration",
                "status": "available",
                "order": 9,
            },
            {
                "title": "Maps & travel",
                "description": "Share venues, shuttles, and hotel blocks with smart directions for every guest.",
                "category": "Communication",
                "status": "available",
                "order": 10,
            },
        ],
        # Benefits/Suites - from page.tsx suites array
        "benefits": [
            {
                "title": "Multi-tenant oversight",
                "description": "Serve every planner, partner, or franchise in isolated workspaces with shared brand standards.",
                "stat": "Scale to 100+ concurrent weddings with centralized governance.",
                "order": 1,
            },
            {
                "title": "Planner vendor records",
                "description": "Keep vendor contacts, notes, files, agreements, and payment context inside the planner workspace.",
                "stat": "Planner-owned records keep vendor context attached to the wedding.",
                "order": 2,
            },
            {
                "title": "Insights & compliance",
                "description": "Audit-ready exports cover guest consent, messaging logs, and accessibility notes.",
                "stat": "SOC 2 aligned infrastructure keeps client data secure.",
                "order": 3,
            },
        ],
        # Testimonials - kept in sync with app/api/testimonials.py defaults
        "testimonials": [
            {
                "name": "Maya Glenn",
                "company": "Aurora Collective",
                "role": "Director of Events",
                "content": "I used to juggle Google Sheets for guests, QuickBooks for budgets, and DocuSign for contracts — all disconnected. Now my 240-person guest list, seating chart, and budget tracker live in one place. Last Saturday I reassigned three tables in the seating orchestrator ten minutes before doors opened and guest memories were already flowing into the couple portal before dinner.",
                "order": 1,
            },
            {
                "name": "Elias Romero",
                "company": "Harbor & Bloom",
                "role": "Lead Coordinator",
                "content": "Building a service package with AI-suggested pricing took me ten minutes instead of a full afternoon of market research. I sent the quote through the contract canvas with e-sign the same day, and the client's milestone payment hit my dashboard before dinner. The entire book-to-pay cycle that used to take me a week now happens in a single session.",
                "order": 2,
            },
            {
                "name": "Priya Chandran",
                "company": "Verdant Celebrations",
                "role": "Senior Planner",
                "content": "Coordinating twelve vendors across two venues was a nightmare of group texts and missed emails. Now each vendor's contact details, agreements, payment status, and internal notes stay attached to the wedding in the private planner workspace, alongside the timeline and reminders my team uses. One operating record keeps us from chasing scattered updates.",
                "order": 3,
            },
            {
                "name": "Tomás Vega",
                "company": "Día Perfecto Weddings",
                "role": "Founder",
                "content": "We run fifteen weddings a month and the planning calendar synced with Google Calendar keeps my team sane. I set up intake forms for new couples in the forms canvas, the RSVP reminders go out automatically by SMS and email, and every wedding has its own branded configuration so clients feel like they have a dedicated app. The knowledge base even onboards our junior planners faster than I can.",
                "order": 4,
            },
        ],
        # Workflow steps - from page.tsx workflow array
        "workflow_steps": [
            {
                "title": "Design the experience",
                "description": "Collaborative planning canvas",
                "badge": "Step 1",
                "bullets": [
                    "Launch weddings in minutes with reusable templates",
                    "Assign visibility by planner, couple, or vendor team",
                    "Model budgets, seating, and timelines side by side",
                ],
            },
            {
                "title": "Invite & delight",
                "description": "Intelligent guest journeys",
                "badge": "Step 2",
                "bullets": [
                    "Personalized wedding websites with per-wedding slugs",
                    "Automated reminders that adapt to RSVP behavior",
                    "Guest portal with travel guidance and gallery teasers",
                ],
            },
            {
                "title": "Execute flawlessly",
                "description": "Day-of command center",
                "badge": "Step 3",
                "bullets": [
                    "QR-powered guest memory uploads with instant photo and video delivery",
                    "Role-based run of show for coordinators and crew",
                    "Instant galleries and thank-you follow ups post event",
                ],
            },
        ],
        # FAQs - from page.tsx faqs array
        "faqs": [
            {
                "question": "Can I manage multiple weddings at once?",
                "answer": "Yes. Workspaces let you run simultaneous weddings, each with their own permissions, branding, and analytics while maintaining agency-wide oversight.",
            },
            {
                "question": "How do couples collaborate with planners?",
                "answer": "Invite couples to a curated dashboard where they approve guest lists, monitor RSVPs, and review timelines without seeing internal notes.",
            },
            {
                "question": "Is there support on the wedding day?",
                "answer": "Solo Founding and Solo Standard include email support. We do not currently advertise an on-call day-of service.",
            },
            {
                "question": "Do couples pay for The Special Wedding?",
                "answer": "Couples invited by a planner pay nothing — the couple portal is included in the planner's plan. Couples planning their own wedding can purchase the Couple Plan: a one-time $199 fee (not a subscription) covering one wedding workspace through 90 days after the wedding — export your data before the workspace closes.",
            },
            {
                "question": "What's next for messaging?",
                "answer": "We are crafting a dedicated messaging studio that centralizes vendor, couple, and planner conversations with payment, contract, and budget context—launching soon.",
            },
        ],
        # Section toggles
        "features_enabled": True,
        "benefits_enabled": True,
        "testimonials_enabled": True,
        # Theme configuration - matches page.tsx defaultTheme colors
        "theme": {
            "primary_color": "#D4A5A5",
            "secondary_color": "#E8C46A",
            "background_style": "gradient",
            "font_style": "elegant",
            "fallback_images": [
                "/wedding-images/wedding-ceremony.jpg",
                "/wedding-images/wedding-reception.jpg",
            ],
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
            "allow_multiple_trials": False,
        },
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
        raise HTTPException(
            status_code=500, detail=f"Error fetching SAAS config: {e!s}"
        )


@router.put("/saas-config", tags=["ROOT_ADMIN"])
async def update_saas_config(
    config_data: dict[str, Any],
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update SAAS configuration - ROOT_ADMIN only"""
    try:
        # Add metadata
        config_data["type"] = "main_config"
        config_data["updated_by"] = current_user.email
        config_data["updated_at"] = datetime.now(UTC)
        # Update or insert configuration
        await mongo.db["saas_config"].update_one(
            {"type": "main_config"}, {"$set": config_data}, upsert=True
        )

        return {"message": "SAAS configuration updated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating SAAS config: {e!s}"
        )


# ==================== CONTENT SECTIONS MANAGEMENT ====================


@router.get("/content-sections", tags=["ROOT_ADMIN"])
async def get_content_sections(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get all content sections - ROOT_ADMIN only"""
    try:
        # Safety cap: typically ~10-20 content sections
        MAX_SECTIONS = 100
        sections_cursor = mongo.db["content_sections"].find({})
        sections = await sections_cursor.to_list(length=MAX_SECTIONS)

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
                        "description": "The ultimate wedding planning platform...",
                    },
                    "is_active": True,
                    "display_order": 1,
                    "updated_by": "system",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
                {
                    "id": "features_section",
                    "section": "features",
                    "content": {
                        "title": "Powerful Features for Wedding Professionals",
                        "features": [],
                    },
                    "is_active": True,
                    "display_order": 2,
                    "updated_by": "system",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            ]

        return sections

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching content sections: {e!s}"
        )


@router.put("/content-sections/{section_id}", tags=["ROOT_ADMIN"])
async def update_content_section(
    section_id: str,
    section_data: dict[str, Any],
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Update a content section - ROOT_ADMIN only"""
    try:
        # Add metadata
        section_data["updated_by"] = current_user.email
        section_data["updated_at"] = datetime.now(UTC)
        # Update section
        await mongo.db["content_sections"].update_one(
            {"section": section_id}, {"$set": section_data}, upsert=True
        )

        return {"message": f"Content section '{section_id}' updated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating content section: {e!s}"
        )


# ==================== WEDDING PLANNERS MANAGEMENT ====================


@router.get("/wedding-planners", tags=["ROOT_ADMIN"])
async def get_wedding_planners(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get all wedding planners - ROOT_ADMIN only"""
    try:
        # Get users with wedding_planner role (async Motor query)
        # Safety cap: typically platforms have <5k planners
        MAX_PLANNERS = 5000
        planners_cursor = mongo.get_users_collection().find({"role": "wedding_planner"})
        planners = await planners_cursor.to_list(length=MAX_PLANNERS)
        # Convert ObjectId to string and format data
        formatted_planners = []
        for planner in planners:
            planner["_id"] = str(planner["_id"])
            # Get assigned weddings count (async count)
            weddings_count = await mongo.get_weddings_collection().count_documents(
                {"assigned_planner_email": planner["email"]}
            )
            formatted_planner = {
                "id": planner["_id"],
                "email": planner["email"],
                "company_name": planner.get("company_name", "Unknown Company"),
                "plan_id": planner.get("plan_id"),
                "subscription_status": planner.get("subscription_status", "inactive"),
                "max_weddings": planner.get("max_weddings", 0),
                "assigned_weddings_count": weddings_count,
                "is_active": planner.get("is_active", True),
                "created_at": planner.get("created_at", datetime.now(UTC)).isoformat(),
                "last_login": (
                    planner.get("last_login").isoformat()
                    if planner.get("last_login")
                    else None
                ),
            }
            formatted_planners.append(formatted_planner)

        return formatted_planners

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching wedding planners: {e!s}"
        )


@router.post("/wedding-planners", tags=["ROOT_ADMIN"])
async def create_wedding_planner(
    planner_data: dict[str, Any],
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Create a new wedding planner - ROOT_ADMIN only"""
    try:
        # Validate required fields
        if not planner_data.get("email"):
            raise HTTPException(status_code=400, detail="Email is required")
        # Check if user already exists
        existing_user = await mongo.get_users_collection().find_one(
            {"email": planner_data["email"]}
        )
        if existing_user:
            raise HTTPException(
                status_code=400, detail="User with this email already exists"
            )
        # Create user document
        user_doc = {
            "email": planner_data["email"],
            "role": ROLE_WEDDING_PLANNER,
            "company_name": planner_data.get("company_name", ""),
            "plan_id": planner_data.get("plan_id"),
            "subscription_status": "inactive",
            "is_active": True,
            "created_by": current_user.email,
            "created_at": datetime.now(UTC),
        }

        # Insert user
        result = await mongo.get_users_collection().insert_one(user_doc)

        # Phase D parity: admin-bulk-onboarded planners never go through
        # the verify_email flow that normally triggers the catalog seed,
        # so they would otherwise see an empty Forms tab on first login.
        # Seed when the inserted role IS the planner role — guards against
        # a future caller passing role=ROOT_ADMIN through the same endpoint.
        if not is_wedding_planner_role(user_doc["role"]):
            return {
                "message": "Wedding planner created successfully",
                "user_id": str(result.inserted_id),
            }
        try:
            from app.services.form_service import FormService

            seed_result = await FormService().seed_catalog_templates_for_planner(
                planner_data["email"]
            )
            logger.info(
                "Catalog seed for admin-created planner %s: %s",
                planner_data["email"],
                seed_result,
            )
        except Exception as seed_exc:
            logger.warning(
                "Catalog seed failed for admin-created planner %s "
                "(account creation still succeeded): %s",
                planner_data["email"],
                seed_exc,
            )

        return {
            "message": "Wedding planner created successfully",
            "user_id": str(result.inserted_id),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error creating wedding planner: {e!s}"
        )


@router.put("/wedding-planners/{planner_id}/status", tags=["ROOT_ADMIN"])
async def toggle_planner_status(
    planner_id: str, current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """Toggle wedding planner active status - ROOT_ADMIN only"""
    try:
        # Get current status
        planner = await mongo.get_users_collection().find_one(
            {"_id": PyObjectId(planner_id)}
        )
        if not planner:
            raise HTTPException(status_code=404, detail="Wedding planner not found")

        new_status = not planner.get("is_active", True)
        planner_email = planner.get("email", "")
        now = datetime.now(UTC)

        # Update status
        await mongo.get_users_collection().update_one(
            {"_id": PyObjectId(planner_id)},
            {
                "$set": {
                    "is_active": new_status,
                    "updated_by": current_user.email,
                    "updated_at": now,
                }
            },
        )

        subscription_status = normalize_subscription_status(
            planner.get("subscription_status")
        )

        if new_status and subscription_status in ACTIVE_SUBSCRIPTION_STATUSES:
            lifecycle_sync = await (
                planner_access_lifecycle_service.restore_planner_access(
                    planner_id=planner_id,
                    planner_email=planner_email,
                )
            )
        elif new_status:
            lifecycle_sync = {
                "skipped": True,
                "reason": "planner_subscription_not_restored",
                "detail": "Planner account was activated, but downstream access remains suspended until the subscription is restored.",
            }
        else:
            lifecycle_sync = (
                await planner_access_lifecycle_service.suspend_planner_access(
                    planner_id=planner_id,
                    planner_email=planner_email,
                    team_reason="root_admin_deactivated",
                )
            )

        return {
            "message": f"Planner {'activated' if new_status else 'deactivated'} successfully",
            "new_status": new_status,
            "lifecycle_sync": lifecycle_sync,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error updating planner status: {e!s}"
        )


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
        raise HTTPException(
            status_code=500, detail=f"Error fetching public SAAS config: {e!s}"
        )


@router.get("/analytics/overview", tags=["ROOT_ADMIN"])
async def get_overview_analytics(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get overview analytics for dashboard - ROOT_ADMIN only"""
    try:
        # Get counts (all async operations)
        total_planners = await mongo.get_users_collection().count_documents(
            {"role": "wedding_planner"}
        )
        active_planners = await mongo.get_users_collection().count_documents(
            {"role": "wedding_planner", "is_active": True}
        )
        total_weddings = await mongo.get_weddings_collection().count_documents({})
        active_plans = await mongo.get_subscription_plans_collection().count_documents(
            {"is_active": True}
        )

        # Calculate revenue based on active subscriptions
        monthly_revenue = 0
        yearly_revenue = 0

        # Get all users with active subscriptions (async cursor)
        # Safety cap: iterate through batches to avoid memory overload
        MAX_ACTIVE_USERS = 10000
        active_users_cursor = mongo.get_users_collection().find(
            {
                "subscription_status": {"$in": list(ACTIVE_SUBSCRIPTION_STATUSES)},
                "is_active": True,
            }
        )
        active_users = await active_users_cursor.to_list(length=MAX_ACTIVE_USERS)
        for user in active_users:
            # Skip trial users for revenue calculation
            if user.get("subscription_status") in {"trial", "trial_expiring"}:
                continue
            plan_id = user.get("plan_id")
            if plan_id:
                # Get the subscription plan (async find_one)
                plan = await mongo.get_subscription_plans_collection().find_one(
                    {"_id": plan_id}
                )
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
            "projected_annual_revenue": projected_annual_revenue,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching overview analytics: {e!s}"
        )


@router.get("/analytics/revenue", tags=["ROOT_ADMIN"])
async def get_revenue_analytics(
    current_user: ExtendedAuthUser = Depends(require_root_admin),
):
    """Get detailed revenue analytics for ROOT_ADMIN"""
    try:
        # Revenue by subscription plan
        plan_revenue = []
        # Safety cap: typically <100 subscription plans
        MAX_PLANS = 500
        plans_cursor = mongo.get_subscription_plans_collection().find(
            {"is_active": True}
        )
        plans = await plans_cursor.to_list(length=MAX_PLANS)

        for plan in plans:
            plan_id = plan["_id"]

            # Count active users on this plan
            active_users_count = await mongo.get_users_collection().count_documents(
                {"plan_id": plan_id, "subscription_status": "active", "is_active": True}
            )
            # Count trial users on this plan
            trial_users_count = await mongo.get_users_collection().count_documents(
                {
                    "plan_id": plan_id,
                    "subscription_status": {"$in": ["trial", "trial_expiring"]},
                    "is_active": True,
                }
            )

            plan_monthly_revenue = active_users_count * plan.get("price_monthly", 0)
            plan_yearly_revenue = active_users_count * plan.get("price_yearly", 0)

            plan_revenue.append(
                {
                    "plan_name": plan.get("name"),
                    "plan_id": str(plan_id),
                    "active_users": active_users_count,
                    "trial_users": trial_users_count,
                    "monthly_revenue": plan_monthly_revenue,
                    "yearly_revenue": plan_yearly_revenue,
                    "price_monthly": plan.get("price_monthly", 0),
                    "price_yearly": plan.get("price_yearly", 0),
                }
            )
        # Calculate totals
        total_monthly_revenue = sum(plan["monthly_revenue"] for plan in plan_revenue)
        total_yearly_revenue = sum(plan["yearly_revenue"] for plan in plan_revenue)
        total_active_users = sum(plan["active_users"] for plan in plan_revenue)
        total_trial_users = sum(plan["trial_users"] for plan in plan_revenue)

        # Average revenue per user
        arpu_monthly = (
            total_monthly_revenue / total_active_users if total_active_users > 0 else 0
        )
        arpu_yearly = (
            total_yearly_revenue / total_active_users if total_active_users > 0 else 0
        )

        return {
            "summary": {
                "total_monthly_revenue": total_monthly_revenue,
                "total_yearly_revenue": total_yearly_revenue,
                "projected_annual_revenue": total_monthly_revenue * 12,
                "total_active_users": total_active_users,
                "total_trial_users": total_trial_users,
                "arpu_monthly": arpu_monthly,
                "arpu_yearly": arpu_yearly,
            },
            "plan_breakdown": plan_revenue,
            "generated_at": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching revenue analytics: {e!s}"
        )


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
            detail=f"Error compiling platform metrics: {exc!s}",
        )


@router.get("/trial-settings", tags=["ROOT_ADMIN", "Public"])
async def get_trial_settings():
    """Get trial settings from SAAS config - Can be used by both admin and registration"""
    try:
        config = await mongo.db["saas_config"].find_one({"type": "main_config"})

        if config and "trial_settings" in config:
            return config["trial_settings"]

        # Return default trial settings if none configured
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False,
        }
    except Exception:
        # Return defaults on error to prevent registration failures
        return {
            "default_trial_days": 30,
            "trial_warning_days": 7,
            "auto_expire_trials": True,
            "allow_multiple_trials": False,
        }
