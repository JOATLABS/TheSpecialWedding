from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, model_validator
from app.services.budget_service import BudgetService
from app.dependencies.auth_extended import (
    get_current_user_extended,
    ExtendedAuthUser,
    check_wedding_access,
    require_wedding_planner,
    require_admin_or_planner,
    enforce_team_permission,
)
from app.models.budget import BudgetCategory, VendorQuote, BudgetTemplate, PaymentRecord
from app.utils.response import success_response, error_response, dict_response
from app.utils.query_validation import (
    validated_string_filter,
    validated_boolean_filter
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
budget_service = BudgetService()

# ===== REQUEST MODELS =====

class CreateBudgetCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    budgeted_amount: float = Field(..., ge=0)
    priority: int = Field(default=3, ge=1, le=5)
    percentage_of_total: Optional[float] = Field(None, ge=0, le=100)

class UpdateBudgetCategoryRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    budgeted_amount: Optional[float] = Field(None, ge=0)
    actual_spent: Optional[float] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=1, le=5)
    payment_status: Optional[str] = Field(None, pattern="^(pending|partial|paid|overdue)$")

class CreateVendorQuoteRequest(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=200)
    vendor_email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    vendor_phone: Optional[str] = Field(None)
    service_category: str = Field(..., min_length=1)
    quote_amount: float = Field(..., ge=0)
    quote_details: Dict = Field(default_factory=dict)
    includes: List[str] = Field(default_factory=list)
    excludes: List[str] = Field(default_factory=list)
    terms_conditions: Optional[str] = Field(None)
    valid_until: Optional[str] = Field(None)  # ISO datetime string
    notes: Optional[str] = Field(None, max_length=1000)

class SetTotalBudgetRequest(BaseModel):
    total_budget: float = Field(..., ge=0)

class ApplyBudgetTemplateRequest(BaseModel):
    template_id: str = Field(..., min_length=1)
    total_budget: float = Field(..., gt=0)

class TemplateCategoryInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    percentage: float = Field(..., gt=0, le=100)
    priority: int = Field(default=3, ge=1, le=5)

class GuestCountRangeInput(BaseModel):
    min: int = Field(..., ge=0, le=2000)
    max: int = Field(..., ge=0, le=5000)

    @model_validator(mode="after")
    def validate_range(self) -> "GuestCountRangeInput":
        if self.max < self.min:
            raise ValueError("Guest count max must be greater than or equal to min")
        return self

class CreateBudgetTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    wedding_type: str = Field(..., min_length=1, max_length=50)
    target_budget_min: float = Field(..., ge=0)
    target_budget_max: float = Field(..., ge=0)
    guest_count_range: GuestCountRangeInput
    categories: List[TemplateCategoryInput] = Field(..., min_length=1)
    is_public: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_budget_and_percentages(self) -> "CreateBudgetTemplateRequest":
        if self.target_budget_max < self.target_budget_min:
            raise ValueError("Maximum budget must be greater than or equal to minimum budget")

        total_percentage = sum(category.percentage for category in self.categories)
        if abs(total_percentage - 100) > 0.5:
            raise ValueError("Category percentages must total 100%")

        seen_names = set()
        for category in self.categories:
            normalized = category.name.strip().lower()
            if normalized in seen_names:
                raise ValueError("Category names must be unique within a template")
            seen_names.add(normalized)

        return self

class RecordPaymentRequest(BaseModel):
    vendor_name: Optional[str] = Field(None)
    amount: float = Field(..., gt=0)
    payment_method: str = Field(..., min_length=1)
    payment_date: str = Field(...)  # ISO datetime string
    description: Optional[str] = Field(None)
    receipt_url: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)

class CostEstimationRequest(BaseModel):
    guest_count: int = Field(..., gt=0, le=1000)
    wedding_type: str = Field(default="traditional")
    region: str = Field(default="national")

# ===== BUDGET CATEGORY ENDPOINTS =====

@router.get("/weddings/{wedding_id}/budget", tags=["Budget"])
async def get_wedding_budget(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get complete budget information for a wedding"""
    try:
        # Check if user has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        budget_data = await budget_service.get_wedding_budget(wedding_id)
        return budget_data

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get wedding budget: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve budget information")

@router.post("/weddings/{wedding_id}/budget/category", tags=["Budget"])
async def create_budget_category(
    wedding_id: str,
    category_data: CreateBudgetCategoryRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Create a new budget category for a wedding"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        # Check if user has access to this wedding
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        category = await budget_service.create_budget_category(
            wedding_id,
            category_data.dict(exclude_unset=True)
        )
        return dict_response(data={"category": category}, message="Budget category created successfully")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create budget category: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create budget category")

@router.put("/budget/category/{category_id}", tags=["Budget"])
async def update_budget_category(
    category_id: str,
    update_data: UpdateBudgetCategoryRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Update an existing budget category"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        # Verify wedding access via category lookup
        category = await budget_service.get_budget_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Budget category not found")
        if not await check_wedding_access(current_user, category["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        updated_category = await budget_service.update_budget_category(
            category_id,
            update_data.dict(exclude_unset=True)
        )
        return dict_response(data={"category": updated_category}, message="Budget category updated successfully")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update budget category: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update budget category")

@router.delete("/budget/category/{category_id}", tags=["Budget"])
async def delete_budget_category(
    category_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Delete a budget category"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        # Verify wedding access via category lookup
        category = await budget_service.get_budget_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Budget category not found")
        if not await check_wedding_access(current_user, category["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        success = await budget_service.delete_budget_category(category_id)
        if success:
            return dict_response(message="Budget category deleted successfully")
        else:
            raise HTTPException(status_code=400, detail="Failed to delete budget category")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete budget category: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete budget category")

# ===== VENDOR QUOTE ENDPOINTS =====

@router.get("/weddings/{wedding_id}/quotes", tags=["Budget", "Vendors"])
async def get_vendor_quotes(
    wedding_id: str,
    service_category: Optional[str] = Query(None, description="Filter by service category"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get vendor quotes for a wedding, optionally filtered by service category"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        # Validate filter parameter
        service_category = validated_string_filter(service_category, max_length=100)

        quotes = await budget_service.get_vendor_quotes(wedding_id, service_category)
        return dict_response(data={"quotes": quotes}, meta={"count": len(quotes)})

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get vendor quotes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve vendor quotes")

@router.post("/weddings/{wedding_id}/quotes", tags=["Budget", "Vendors"])
async def create_vendor_quote(
    wedding_id: str,
    quote_data: CreateVendorQuoteRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Create a new vendor quote"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")
        quote = await budget_service.create_vendor_quote(
            wedding_id,
            quote_data.dict(exclude_unset=True)
        )
        return dict_response(data={"quote": quote}, message="Vendor quote created successfully")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create vendor quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create vendor quote")

@router.get("/weddings/{wedding_id}/quotes/compare/{service_category}", tags=["Budget", "Vendors"])
async def compare_vendor_quotes(
    wedding_id: str,
    service_category: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Compare vendor quotes for a specific service category"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        comparison = await budget_service.compare_vendor_quotes(wedding_id, service_category)
        return comparison

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to compare vendor quotes: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to compare vendor quotes")

@router.put("/quotes/{quote_id}/status", tags=["Budget", "Vendors"])
async def update_quote_status(
    quote_id: str,
    status: str = Body(..., embed=True),
    notes: Optional[str] = Body(None, embed=True),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Update vendor quote status (accept/reject/pending)"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        if status not in ["pending", "accepted", "rejected", "expired"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        # Verify wedding access via quote lookup
        quote = await budget_service.get_vendor_quote(quote_id)
        if not quote:
            raise HTTPException(status_code=404, detail="Vendor quote not found")
        if not await check_wedding_access(current_user, quote["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        updated_quote = await budget_service.update_quote_status(quote_id, status, notes)
        return dict_response(data={"quote": updated_quote}, message=f"Quote status updated to {status}")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update quote status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update quote status")

@router.put("/quotes/{quote_id}/rating", tags=["Budget", "Vendors"])
async def rate_vendor_quote(
    quote_id: str,
    rating: int = Body(..., embed=True, ge=1, le=5),
    notes: Optional[str] = Body(None, embed=True),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Rate a vendor quote (1-5 stars)"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        # Verify wedding access via quote lookup
        quote = await budget_service.get_vendor_quote(quote_id)
        if not quote:
            raise HTTPException(status_code=404, detail="Vendor quote not found")
        if not await check_wedding_access(current_user, quote["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        updated_quote = await budget_service.rate_vendor_quote(quote_id, rating, notes)
        return dict_response(data={"quote": updated_quote}, message="Quote rated successfully")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to rate vendor quote: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to rate vendor quote")

# ===== BUDGET TEMPLATE ENDPOINTS =====

@router.get("/budget/templates", tags=["Budget"])
async def get_budget_templates(
    wedding_type: Optional[str] = Query(None, description="Filter by wedding type"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get available budget templates"""
    try:
        # Validate filter parameter
        wedding_type = validated_string_filter(wedding_type, max_length=50)

        templates = await budget_service.get_budget_templates(wedding_type)
        return dict_response(data={"templates": templates}, meta={"count": len(templates)})

    except Exception as e:
        logger.error(f"Failed to get budget templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve budget templates")

@router.post("/budget/templates", tags=["Budget"], status_code=201)
async def create_budget_template(
    request_data: CreateBudgetTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_wedding_planner)
):
    """Create a custom budget template for planners"""
    try:
        template = await budget_service.create_budget_template(
            request_data.model_dump(),
            created_by=current_user.email,
        )
        return dict_response(data={"template": template}, message="Budget template created successfully")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create budget template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create budget template")

@router.post("/weddings/{wedding_id}/budget/apply-template", tags=["Budget"])
async def apply_budget_template(
    wedding_id: str,
    request_data: ApplyBudgetTemplateRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Apply a budget template to a wedding"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")
        result = await budget_service.apply_budget_template(
            wedding_id,
            request_data.template_id,
            request_data.total_budget
        )
        return dict_response(data={"result": result}, message="Budget template applied successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to apply budget template: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to apply budget template")

# ===== PAYMENT TRACKING ENDPOINTS =====

@router.post("/budget/category/{category_id}/payment", tags=["Budget"])
async def record_payment(
    category_id: str,
    payment_data: RecordPaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Record a payment for a budget category"""
    enforce_team_permission(current_user, "manage_budget")
    try:
        category = await budget_service.get_budget_category(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Budget category not found")

        if not await check_wedding_access(current_user, category["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        payment = await budget_service.record_payment(
            category_id,
            payment_data.dict(exclude_unset=True)
        )
        return dict_response(data={"payment": payment}, message="Payment recorded successfully")

    except HTTPException:
        raise
    except ValueError as e:
        detail = str(e)
        if "not found" in detail.lower():
            raise HTTPException(status_code=404, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    except Exception as e:
        logger.error(f"Failed to record payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record payment")


@router.put("/budget/payment/{payment_id}", tags=["Budget"])
async def update_payment(
    payment_id: str,
    payment_data: RecordPaymentRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Update an existing payment record"""
    try:
        # Verify wedding access via payment lookup
        payment = await budget_service.get_payment(payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        category = await budget_service.get_budget_category(payment["category_id"])
        if not category:
            raise HTTPException(status_code=404, detail="Budget category not found")
        if not await check_wedding_access(current_user, category["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        result = await budget_service.update_payment(
            payment_id,
            payment_data.dict(exclude_unset=True)
        )
        return dict_response(data={"payment": result}, message="Payment updated successfully")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update payment")

@router.delete("/budget/payment/{payment_id}", tags=["Budget"])
async def delete_payment(
    payment_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Delete a payment record"""
    try:
        # Verify wedding access via payment lookup
        payment = await budget_service.get_payment(payment_id)
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")

        category = await budget_service.get_budget_category(payment["category_id"])
        if not category:
            raise HTTPException(status_code=404, detail="Budget category not found")
        if not await check_wedding_access(current_user, category["wedding_id"]):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        success = await budget_service.delete_payment(payment_id)
        if success:
            return dict_response(message="Payment deleted successfully")
        raise HTTPException(status_code=400, detail="Failed to delete payment")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete payment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete payment")

@router.get("/weddings/{wedding_id}/payments", tags=["Budget"])
async def get_payment_history(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get payment history for a wedding"""
    from fastapi.responses import JSONResponse
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        payments = await budget_service.get_payment_history(wedding_id)
        return dict_response(data={"payments": payments}, meta={"count": len(payments)})

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment history: {type(e).__name__}: {str(e)}", exc_info=True)
        # Return JSONResponse directly to avoid middleware converting the error
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to retrieve payment history"}
        )

# ===== TOTAL BUDGET =====

@router.put("/weddings/{wedding_id}/budget/total", tags=["Budget"])
async def set_total_budget(
    wedding_id: str,
    request_data: SetTotalBudgetRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Set or update the overall total budget for a wedding"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        await budget_service.weddings.update_one(
            {"_id": wedding_id},
            {"$set": {"total_budget": request_data.total_budget}}
        )
        logger.info(f"Updated total budget for wedding {wedding_id} to ${request_data.total_budget:,.2f}")
        return dict_response(data={"total_budget": request_data.total_budget}, message="Total budget updated")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set total budget: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update total budget")


# ===== REPORTING ENDPOINTS =====

@router.get("/weddings/{wedding_id}/budget/report", tags=["Budget", "Reports"])
async def generate_financial_report(
    wedding_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Generate comprehensive financial report for a wedding"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        report = await budget_service.generate_financial_report(wedding_id)
        return report

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate financial report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate financial report")

# ===== COST ESTIMATION ENDPOINTS =====

@router.post("/budget/estimate", tags=["Budget"])
def estimate_wedding_costs(
    estimation_request: CostEstimationRequest,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Estimate wedding costs based on guest count, type, and region"""
    try:
        estimation = budget_service.estimate_costs(
            guest_count=estimation_request.guest_count,
            wedding_type=estimation_request.wedding_type,
            region=estimation_request.region
        )
        return estimation
    except Exception as e:
        logger.error(f"Failed to estimate costs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to estimate wedding costs")

# ===== UTILITY ENDPOINTS =====

@router.get("/budget/categories/suggestions", tags=["Budget"])
def get_category_suggestions(
    wedding_type: str = Query(default="traditional", description="Wedding type for category suggestions"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get suggested budget categories for a wedding type"""
    try:
        # Validate wedding type parameter
        wedding_type = validated_string_filter(wedding_type, max_length=50) or "traditional"
        # Standard category suggestions
        category_suggestions = {
            "traditional": [
                {"name": "Venue & Catering", "percentage": 45.0, "priority": 1},
                {"name": "Photography & Videography", "percentage": 12.0, "priority": 2},
                {"name": "Music & Entertainment", "percentage": 10.0, "priority": 3},
                {"name": "Flowers & Decorations", "percentage": 8.0, "priority": 4},
                {"name": "Attire & Beauty", "percentage": 8.0, "priority": 4},
                {"name": "Transportation", "percentage": 5.0, "priority": 5},
                {"name": "Invitations & Stationery", "percentage": 3.0, "priority": 5},
                {"name": "Favors & Gifts", "percentage": 2.0, "priority": 5},
                {"name": "Miscellaneous", "percentage": 7.0, "priority": 5}
            ],
            "modern": [
                {"name": "Venue & Experience", "percentage": 40.0, "priority": 1},
                {"name": "Photography & Videography", "percentage": 15.0, "priority": 2},
                {"name": "Entertainment & DJ", "percentage": 12.0, "priority": 3},
                {"name": "Catering & Bar", "percentage": 15.0, "priority": 2},
                {"name": "Attire & Styling", "percentage": 8.0, "priority": 4},
                {"name": "Digital Invitations", "percentage": 2.0, "priority": 5},
                {"name": "Technology & Lighting", "percentage": 5.0, "priority": 4},
                {"name": "Miscellaneous", "percentage": 3.0, "priority": 5}
            ],
            "intimate": [
                {"name": "Venue & Catering", "percentage": 50.0, "priority": 1},
                {"name": "Photography", "percentage": 15.0, "priority": 2},
                {"name": "Flowers & Decor", "percentage": 12.0, "priority": 3},
                {"name": "Attire & Beauty", "percentage": 10.0, "priority": 3},
                {"name": "Music", "percentage": 5.0, "priority": 4},
                {"name": "Transportation", "percentage": 3.0, "priority": 5},
                {"name": "Special Touches", "percentage": 5.0, "priority": 4}
            ]
        }

        suggestions = category_suggestions.get(wedding_type, category_suggestions["traditional"])
        return {"wedding_type": wedding_type, "suggestions": suggestions}

    except Exception as e:
        logger.error(f"Failed to get category suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get category suggestions")

@router.get("/budget/alerts/{wedding_id}", tags=["Budget"])
async def get_budget_alerts(
    wedding_id: str,
    include_resolved: bool = Query(default=False, description="Include resolved alerts"),
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Get budget alerts for a wedding"""
    try:
        if not await check_wedding_access(current_user, wedding_id):
            raise HTTPException(status_code=403, detail="Access to this wedding denied")

        # Validate filter parameter
        include_resolved = validated_boolean_filter(include_resolved) or False

        alerts = await budget_service.get_budget_alerts(wedding_id, include_resolved)
        return {"alerts": alerts}

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get budget alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve budget alerts")


@router.put("/budget/alerts/{alert_id}/read", tags=["Budget"])
async def mark_alert_as_read(
    alert_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Mark a budget alert as read"""
    try:
        return await budget_service.mark_alert_as_read(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to mark alert as read: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to mark alert as read")


@router.put("/budget/alerts/{alert_id}/resolve", tags=["Budget"])
async def resolve_alert(
    alert_id: str,
    current_user: ExtendedAuthUser = Depends(require_admin_or_planner)
):
    """Resolve a budget alert"""
    try:
        return await budget_service.resolve_alert(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resolve alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")