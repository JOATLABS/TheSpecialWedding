from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class UserModel(BaseModel):
    """Extended user model supporting multiple roles"""
    id: str = Field(..., alias="_id")
    email: str = Field(..., description="User email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(default="wedding_planner", description="User role: ROOT_ADMIN, wedding_planner, vendor")
    # Wedding planner specific fields
    company_name: Optional[str] = Field(None, description="Wedding planning company name")
    subscription_plan_id: Optional[str] = Field(None, description="Current subscription plan")
    subscription_status: str = Field(default="trial", description="Subscription status: trial, active, cancelled")
    trial_end_date: Optional[datetime] = Field(None, description="Trial expiration date")

    # Billing information
    stripe_customer_id: Optional[str] = Field(None, description="Stripe customer ID")
    stripe_subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    stripe_connect_id: Optional[str] = Field(None, description="Stripe Connect Account ID for receiving payments")

    # Wedding planner permissions and limits
    max_weddings: int = Field(default=1, description="Maximum weddings allowed")
    ai_credits_remaining: int = Field(default=10, description="Remaining AI credits this month")
    ai_credits_reset_date: Optional[datetime] = Field(None, description="When AI credits reset")
    # Vendor specific fields (if role is vendor)
    assigned_wedding_ids: List[str] = Field(default_factory=list, description="Weddings this vendor has access to")
    service_type: Optional[str] = Field(None, description="Type of service for vendors")
    created_by: Optional[str] = Field(None, description="Wedding planner who created this vendor")
    # Profile
    first_name: Optional[str] = Field(None, description="User's first name")
    last_name: Optional[str] = Field(None, description="User's last name")
    profile_image_url: Optional[str] = Field(None, description="S3/R2 URL for profile image")

    # System fields
    is_active: bool = Field(default=True, description="Whether account is active")
    email_verified: bool = Field(default=False, description="Whether email is verified")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "_id": "user_001",
                "email": "planner@example.com",
                "role": "wedding_planner",
                "company_name": "Dream Weddings LLC",
                "subscription_plan_id": "plan_basic",
                "subscription_status": "active",
                "max_weddings": 5,
                "ai_credits_remaining": 50
            }
        }

# Migration compatible: This extends functionality without breaking existing admin_users collection
class AdminUserModel(BaseModel):
    """Legacy admin user model - keeping for backward compatibility"""
    email: str = Field(..., description="Admin email")
    password_hash: str = Field(..., description="Hashed password")
    role: str = Field(default="admin", description="Always 'admin' for backward compatibility")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    class Config:
        schema_extra = {
            "example": {
                "email": "thedeveloper@thespecialwedding.com",
                "password_hash": "hashed_password_here",
                "role": "admin"
            }
        }