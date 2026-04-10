from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TableShape(str, Enum):
    ROUND = "round"
    RECTANGLE = "rectangle"


class TableModel(BaseModel):
    wedding_id: str = Field(...)
    name: str = Field(..., min_length=1, max_length=50)
    shape: TableShape = Field(default=TableShape.ROUND)
    capacity: int = Field(..., ge=1, le=50)
    x: float = Field(default=0.0)
    y: float = Field(default=0.0)

    model_config = {
        "json_schema_extra": {
            "example": {
                "wedding_id": "wedding_001",
                "name": "Table 1",
                "shape": "round",
                "capacity": 8,
                "x": 100.5,
                "y": 200.0,
            }
        }
    }


class UpdateTableRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    shape: Optional[TableShape] = None
    capacity: Optional[int] = Field(None, ge=1, le=50)
    x: Optional[float] = None
    y: Optional[float] = None


class AssignGuestsRequest(BaseModel):
    guest_ids: list[str] = Field(...)
    table_id: str = Field(...)
