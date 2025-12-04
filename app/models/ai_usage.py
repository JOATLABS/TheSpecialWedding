from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AIFeature(str, Enum):
    SEATING_OPTIMIZATION = "seating_optimization"
    BUDGET_ADVICE = "budget_advice"
    REPORT_GENERATION = "report_generation"
    OTHER = "other"

class AIUsageLog(BaseModel):
    """Logs every AI interaction for billing and analytics"""
    id: str = Field(..., alias="_id")
    tenant_id: str = Field(..., description="Wedding/Tenant ID")
    feature: AIFeature = Field(..., description="Which feature was used")
    prompt_tokens: int = Field(0, description="Tokens used for input")
    completion_tokens: int = Field(0, description="Tokens used for output")
    total_tokens: int = Field(0, description="Total tokens")
    credits_cost: int = Field(..., description="Credits deducted")

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
