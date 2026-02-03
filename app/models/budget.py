from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List, Dict, Optional
from datetime import datetime
from bson import ObjectId
from app.utils.pydantic_objectid import PyObjectId, generate_object_id

class BudgetSubcategory(BaseModel):
    """Subcategory within a budget category"""
    id: PyObjectId = Field(default_factory=generate_object_id, description="Unique subcategory ID")
    name: str = Field(..., min_length=1, max_length=100, description="Subcategory name")
    budgeted_amount: float = Field(ge=0, description="Budgeted amount for this subcategory")
    actual_spent: float = Field(default=0.0, ge=0, description="Actual amount spent")
    notes: Optional[str] = Field(None, max_length=500, description="Notes about this subcategory")

class BudgetCategory(BaseModel):
    """Main budget category for a wedding"""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    wedding_id: str = Field(..., description="ID of the wedding this budget belongs to")
    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, max_length=500, description="Category description")
    budgeted_amount: float = Field(ge=0, description="Total budgeted amount for this category")
    actual_spent: float = Field(default=0.0, ge=0, description="Total actual amount spent")
    payment_status: str = Field(default="pending", description="Payment status: pending, partial, paid, overdue")
    priority: int = Field(default=1, ge=1, le=5, description="Priority level (1=highest, 5=lowest)")
    percentage_of_total: Optional[float] = Field(None, ge=0, le=100, description="Percentage of total wedding budget")
    subcategories: List[BudgetSubcategory] = Field(default_factory=list, description="Subcategories within this category")
    vendor_quotes: List[str] = Field(default_factory=list, description="List of vendor quote IDs for this category")
    payments: List[Dict] = Field(default_factory=list, description="List of payments made for this category")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )
    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        """Serialize ObjectId to string for JSON output."""
        return str(value) if value else None

    @classmethod
    def model_json_schema(cls, by_alias: bool = True) -> dict:
        """Generate JSON schema with example."""
        schema = super().model_json_schema(by_alias=by_alias)
        schema["example"] = {
            "_id": "60c7d3e9e1b1fdbb4f12d9aa",
            "wedding_id": "60c7d3e9e1b1fdbb4f12d9bb",
            "name": "Venue & Catering",
            "description": "Reception venue and catering costs",
            "budgeted_amount": 25000.00,
            "actual_spent": 22500.00,
            "payment_status": "partial",
            "priority": 1,
            "percentage_of_total": 50.0,
            "subcategories": [
                {
                    "name": "Venue Rental",
                    "budgeted_amount": 15000.00,
                    "actual_spent": 15000.00
                }
            ]
        }
        return schema

class VendorQuote(BaseModel):
    """Vendor quote for budget comparison"""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    wedding_id: str = Field(..., description="ID of the wedding")
    vendor_id: Optional[str] = Field(None, description="ID of the vendor (if registered)")
    vendor_name: str = Field(..., min_length=1, max_length=200, description="Vendor name")
    vendor_email: Optional[str] = Field(None, description="Vendor email")
    vendor_phone: Optional[str] = Field(None, description="Vendor phone")
    service_category: str = Field(..., description="Service category (photography, catering, etc.)")
    quote_amount: float = Field(ge=0, description="Total quote amount")
    quote_details: Dict = Field(default_factory=dict, description="Detailed quote breakdown")
    includes: List[str] = Field(default_factory=list, description="What's included in the quote")
    excludes: List[str] = Field(default_factory=list, description="What's excluded from the quote")
    terms_conditions: Optional[str] = Field(None, description="Terms and conditions")
    status: str = Field(default="pending", description="Quote status: pending, accepted, rejected, expired")
    valid_until: Optional[datetime] = Field(None, description="Quote expiration date")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Quality/value rating (1-5)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )
    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        """Serialize ObjectId to string for JSON output."""
        return str(value) if value else None

    @classmethod
    def model_json_schema(cls, by_alias: bool = True) -> dict:
        """Generate JSON schema with example."""
        schema = super().model_json_schema(by_alias=by_alias)
        schema["example"] = {
            "vendor_name": "Perfect Photos Studio",
            "vendor_email": "info@perfectphotos.com",
            "service_category": "photography",
            "quote_amount": 3500.00,
            "quote_details": {
                "hours": 8,
                "photographers": 2,
                "edited_photos": 500,
                "prints": "100 4x6 prints included"
            },
            "includes": ["8 hours coverage", "2 photographers", "500 edited photos", "online gallery"],
            "excludes": ["Video", "Albums", "Engagement session"],
            "valid_until": "2024-02-01T00:00:00Z",
            "status": "pending"
        }
        return schema

class BudgetTemplate(BaseModel):
    """Pre-built budget template for different wedding types"""
    id: PyObjectId = Field(default_factory=generate_object_id, alias="_id")
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, max_length=500, description="Template description")
    wedding_type: str = Field(..., description="Type of wedding: traditional, modern, destination, intimate, etc.")
    target_budget_min: float = Field(ge=0, description="Minimum recommended budget")
    target_budget_max: float = Field(ge=0, description="Maximum recommended budget")
    guest_count_range: Dict = Field(default_factory=dict, description="Recommended guest count range")
    categories: List[Dict] = Field(default_factory=list, description="Default categories with percentages")
    created_by: Optional[str] = Field(None, description="Created by user email")
    is_public: bool = Field(default=True, description="Whether template is available to all planners")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True
    )
    @field_serializer('id', when_used='json')
    def serialize_id(self, value) -> str:
        """Serialize ObjectId to string for JSON output."""
        return str(value) if value else None

    @classmethod
    def model_json_schema(cls, by_alias: bool = True) -> dict:
        """Generate JSON schema with example."""
        schema = super().model_json_schema(by_alias=by_alias)
        schema["example"] = {
            "name": "Traditional Wedding Template",
            "description": "Standard template for traditional weddings with 100-150 guests",
            "wedding_type": "traditional",
            "target_budget_min": 25000.00,
            "target_budget_max": 50000.00,
            "guest_count_range": {"min": 100, "max": 150},
            "categories": [
                {"name": "Venue & Catering", "percentage": 45.0, "priority": 1},
                {"name": "Photography & Videography", "percentage": 12.0, "priority": 2},
                {"name": "Music & Entertainment", "percentage": 10.0, "priority": 3},
                {"name": "Flowers & Decorations", "percentage": 8.0, "priority": 4}
            ]
        }
        return schema

class BudgetSummary(BaseModel):
    """Budget summary for reporting"""
    wedding_id: str = Field(..., description="Wedding ID")
    total_budget: float = Field(ge=0, description="Total allocated budget")
    total_spent: float = Field(default=0.0, ge=0, description="Total amount spent")
    total_committed: float = Field(default=0.0, ge=0, description="Total committed (contracts signed)")
    remaining_budget: float = Field(description="Remaining budget available (can be negative if overspent)")
    budget_variance: float = Field(description="Variance from budget (+ over, - under)")
    variance_percentage: float = Field(description="Variance as percentage")
    categories_count: int = Field(ge=0, description="Number of budget categories")
    paid_categories: int = Field(default=0, ge=0, description="Number of fully paid categories")
    overdue_categories: int = Field(default=0, ge=0, description="Number of overdue categories")
    vendor_quotes_count: int = Field(default=0, ge=0, description="Total vendor quotes collected")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class PaymentRecord(BaseModel):
    """Individual payment record"""
    id: PyObjectId = Field(default_factory=generate_object_id)
    category_id: str = Field(..., description="Budget category this payment belongs to")
    vendor_name: Optional[str] = Field(None, description="Vendor who received payment")
    amount: float = Field(gt=0, description="Payment amount")
    payment_method: str = Field(..., description="Payment method: cash, check, card, transfer")
    payment_date: datetime = Field(..., description="Date payment was made")
    description: Optional[str] = Field(None, description="Payment description")
    receipt_url: Optional[str] = Field(None, description="URL to receipt/invoice")
    status: str = Field(default="completed", description="Payment status: pending, completed, failed")
    notes: Optional[str] = Field(None, description="Additional notes")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BudgetAlert(BaseModel):
    """Budget alerts and notifications"""
    id: PyObjectId = Field(default_factory=generate_object_id)
    wedding_id: str = Field(..., description="Wedding ID")
    category_id: Optional[str] = Field(default=None, description="Specific category if applicable")
    alert_type: str = Field(..., description="Alert type: over_budget, payment_due, quote_expired")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    amount: Optional[float] = Field(default=None, description="Amount related to alert")
    threshold: Optional[float] = Field(default=None, description="Threshold that triggered alert")
    is_read: bool = Field(default=False, description="Whether alert has been read")
    is_resolved: bool = Field(default=False, description="Whether alert has been resolved")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(default=None, description="When alert was resolved")