from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class TableModel(BaseModel):
    wedding_id: str = Field(...)
    name: str = Field(..., description="Table name or number")
    capacity: int = Field(default=10, description="Number of seats")
    shape: str = Field(default="circle", description="Shape: circle, rectangle")
    x: float = Field(default=0, description="X coordinate on canvas")
    y: float = Field(default=0, description="Y coordinate on canvas")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "wedding_id": "wedding_001",
                "name": "Table 1",
                "capacity": 8,
                "shape": "circle",
                "x": 100,
                "y": 100
            }
        }
