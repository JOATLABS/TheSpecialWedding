from enum import Enum
from typing import Literal

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
    name: str | None = Field(None, min_length=1, max_length=50)
    shape: TableShape | None = None
    capacity: int | None = Field(None, ge=1, le=50)
    x: float | None = None
    y: float | None = None


class AssignGuestsRequest(BaseModel):
    guest_ids: list[str] = Field(...)
    table_id: str = Field(...)


class SeatingLayoutPoint(BaseModel):
    x: float = Field(..., ge=0, le=5000)
    y: float = Field(..., ge=0, le=5000)


class SeatingLayoutFixture(BaseModel):
    id: str = Field(..., min_length=1, max_length=80)
    type: Literal[
        "dance_floor",
        "bar",
        "stage",
        "entrance",
        "restrooms",
        "kitchen",
        "vendor_path",
    ]
    label: str = Field(..., min_length=1, max_length=80)
    x: float = Field(..., ge=0, le=5000)
    y: float = Field(..., ge=0, le=5000)
    width: float = Field(default=180, ge=24, le=2000)
    height: float = Field(default=120, ge=24, le=2000)
    rotation: float | None = Field(default=0, ge=-360, le=360)


class SeatingLayoutRequest(BaseModel):
    canvas_width: float = Field(default=1600, ge=600, le=5000)
    canvas_height: float = Field(default=1000, ge=400, le=5000)
    outline: list[SeatingLayoutPoint] = Field(default_factory=list, max_length=80)
    background_image_data_url: str | None = Field(default=None, max_length=1_800_000)
    background_image_name: str | None = Field(default=None, max_length=160)
    background_locked: bool = True
    scale_pixels: float | None = Field(default=None, ge=1, le=5000)
    scale_distance: float | None = Field(default=None, ge=0.1, le=10000)
    scale_unit: Literal["ft", "m"] = "ft"
    fixtures: list[SeatingLayoutFixture] = Field(default_factory=list, max_length=80)
