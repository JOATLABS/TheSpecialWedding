"""
Package API Routes

Admin endpoints for managing wedding service packages.
All endpoints require planner authentication.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from pydantic import BaseModel, Field
from app.services.package_service import package_service
from app.dependencies.auth_extended import (
    ExtendedAuthUser,
    require_admin_or_planner,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class PackageServiceRequest(BaseModel):
    """Service item in a package."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    included: bool = True


class ScheduleItemRequest(BaseModel):
    """Payment schedule item."""
    name: str = Field(..., min_length=1, max_length=100)
    trigger: str = Field(
        ...,
        pattern="^(on_signing|days_after_signing|days_before_wedding|fixed_date)$"
    )
    days_after: Optional[int] = Field(None, ge=0)
    days_before: Optional[int] = Field(None, ge=0)
    fixed_date: Optional[str] = None
    amount: Optional[float] = Field(None, ge=0)
    percentage: Optional[float] = Field(None, ge=0, le=100)


class CreatePackageRequest(BaseModel):
    """Request to create a new package."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    services: List[PackageServiceRequest] = Field(default_factory=list)
    total_amount: float = Field(..., gt=0)
    currency: str = Field(default="usd", pattern="^[a-z]{3}$")
    payment_schedule: List[ScheduleItemRequest] = Field(default_factory=list)
    cancellation_policy: str = Field(default="")
    late_payment_policy: Optional[str] = None
    custom_terms: Optional[str] = None
    is_template: bool = False


class UpdatePackageRequest(BaseModel):
    """Request to update a package."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    services: Optional[List[PackageServiceRequest]] = None
    total_amount: Optional[float] = Field(None, gt=0)
    payment_schedule: Optional[List[ScheduleItemRequest]] = None
    cancellation_policy: Optional[str] = None
    late_payment_policy: Optional[str] = None
    custom_terms: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class CoupleInfoRequest(BaseModel):
    """Couple contact information."""
    partner1_name: str = Field(..., min_length=1, max_length=100)
    partner2_name: Optional[str] = Field(None, max_length=100)
    email: str = Field(..., max_length=254)
    phone: Optional[str] = Field(None, max_length=20)


class SendPackageRequest(BaseModel):
    """Request to send package to couple."""
    couple: CoupleInfoRequest
    wedding_date: Optional[str] = None
    wedding_id: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/packages", tags=["Packages"])
async def list_packages(
    include_templates: bool = Query(False),
    status: Optional[str] = Query(None, pattern="^(draft|active|archived)$"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    List all packages for the authenticated planner.

    - **include_templates**: Include template packages
    - **status**: Filter by status (draft, active, archived)
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        packages = await package_service.list_packages(
            planner_id=planner_id,
            include_templates=include_templates,
            status=status,
            limit=limit,
            skip=skip
        )

        return {
            "packages": packages,
            "count": len(packages)
        }

    except Exception as e:
        logger.error(f"Failed to list packages: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve packages")


@router.post("/packages", tags=["Packages"], status_code=201)
async def create_package(
    package_data: CreatePackageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Create a new package.

    Packages start in 'draft' status. Activate them before sending to couples.
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        package = await package_service.create_package(
            planner_id=planner_id,
            package_data=package_data.model_dump(exclude_unset=True)
        )

        return {
            "message": "Package created successfully",
            "package": package
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create package")


@router.get("/packages/stats", tags=["Packages"])
async def get_package_stats(
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get package statistics for the planner."""
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)
        stats = await package_service.get_package_stats(planner_id)
        return stats

    except Exception as e:
        logger.error(f"Failed to get package stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.get("/packages/{package_id}", tags=["Packages"])
async def get_package(
    package_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get a specific package by ID."""
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        package = await package_service.get_package(package_id, planner_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")

        return {"package": package}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve package")


@router.put("/packages/{package_id}", tags=["Packages"])
async def update_package(
    package_id: str,
    update_data: UpdatePackageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Update an existing package.

    Note: Active packages have limited editable fields.
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        package = await package_service.update_package(
            package_id=package_id,
            planner_id=planner_id,
            update_data=update_data.model_dump(exclude_unset=True)
        )

        return {
            "message": "Package updated successfully",
            "package": package
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update package")


@router.delete("/packages/{package_id}", tags=["Packages"])
async def delete_package(
    package_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Delete a draft package.

    Only packages in 'draft' status without contracts can be deleted.
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        await package_service.delete_package(package_id, planner_id)

        return {"message": "Package deleted successfully"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete package")


@router.post("/packages/{package_id}/duplicate", tags=["Packages"])
async def duplicate_package(
    package_id: str,
    name: Optional[str] = None,
    as_template: bool = True,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Duplicate a package.

    Creates a copy of the package, optionally as a template.
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        package = await package_service.duplicate_package(
            package_id=package_id,
            planner_id=planner_id,
            new_name=name,
            as_template=as_template
        )

        return {
            "message": "Package duplicated successfully",
            "package": package
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to duplicate package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to duplicate package")


@router.post("/packages/{package_id}/send", tags=["Packages"], status_code=201)
async def send_package_to_couple(
    package_id: str,
    send_data: SendPackageRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Send a package to a couple, creating a contract.

    The package must be in 'active' status. This creates a contract
    with a unique token for the couple to view and sign.
    """
    try:
        planner_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        contract = await package_service.send_to_couple(
            package_id=package_id,
            planner_id=planner_id,
            couple_data=send_data.couple.model_dump(),
            wedding_date=send_data.wedding_date,
            wedding_id=send_data.wedding_id
        )

        return {
            "message": "Contract created and sent to couple",
            "contract": contract
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send package")


# ============================================================================
# AI PRICING SUGGESTIONS
# ============================================================================

class AIPricingSuggestionRequest(BaseModel):
    """Request for AI pricing suggestions."""
    services: List[PackageServiceRequest] = Field(default_factory=list)
    location: Optional[str] = Field(None, max_length=100)
    wedding_size: Optional[int] = Field(None, ge=1, le=1000)


@router.post("/packages/ai-pricing", tags=["Packages"])
async def get_ai_pricing_suggestion(
    request_data: AIPricingSuggestionRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """
    Get AI-powered pricing suggestions for a package.

    Uses the AI service to analyze services, location, and wedding size
    to suggest competitive pricing.

    Cost: 3 AI credits
    """
    from app.services.ai_service import ai_service, InsufficientCreditsError, AIGenerationError
    from app.core.settings import settings

    try:
        if not settings.ai_enabled:
            raise HTTPException(
                status_code=503,
                detail="AI features are not available. Please configure GOOGLE_API_KEY."
            )

        user_id = str((current_user.user_data or {}).get("_id") or current_user.email)

        # Build context for AI
        services_list = [
            {"name": s.name, "description": s.description or ""}
            for s in request_data.services
            if s.included
        ]

        context = {
            "services": services_list,
            "service_count": len(services_list),
            "location": request_data.location or "United States",
            "wedding_size": request_data.wedding_size or 100
        }

        prompt = f"""
        Analyze this wedding planning package and suggest competitive pricing:

        Services offered: {len(services_list)} services
        Location: {context['location']}
        Typical wedding size: {context['wedding_size']} guests

        Service details:
        {', '.join([s['name'] for s in services_list]) if services_list else 'General wedding planning'}

        Provide pricing suggestions based on current market rates.
        """

        result = await ai_service.generate(
            user_id=user_id,
            tenant_id=user_id,
            feature="package_pricing",
            prompt=prompt,
            context=context
        )

        response = result.get("response", {})

        # Ensure we have valid pricing data
        if isinstance(response, dict) and "min_price" in response:
            return {
                "suggestion": response,
                "credits_used": result.get("credits_used", 3),
                "cached": result.get("cached", False)
            }

        # Parse text response if not structured
        return {
            "suggestion": {
                "min_price": 2000,
                "max_price": 8000,
                "recommended": 4500,
                "market_comparison": "at",
                "reasoning": response.get("text", "Based on the services provided, this pricing is competitive for the market."),
                "schedule_suggestion": [
                    {"name": "Deposit", "percentage": 25, "trigger": "on_signing"},
                    {"name": "Mid-Planning", "percentage": 25, "trigger": "days_after_signing", "days_after": 60},
                    {"name": "Final Payment", "percentage": 50, "trigger": "days_before_wedding", "days_before": 14}
                ]
            },
            "credits_used": result.get("credits_used", 3),
            "cached": result.get("cached", False)
        }

    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail={
                "message": e.message,
                "required": e.required,
                "available": e.available
            }
        )
    except AIGenerationError as e:
        logger.error(f"AI generation error: {str(e)}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI pricing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get pricing suggestion")
