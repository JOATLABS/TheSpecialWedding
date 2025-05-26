from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

class EventModel(BaseModel):
    type: str = Field(..., description="Event type: traditional, white_wedding, reception")
    date: str = Field(..., description="Event date in YYYY-MM-DD format")

class WeddingModel(BaseModel):
    id: str = Field(..., alias="_id")
    couple_names: str = Field(..., min_length=3, max_length=200)
    date: str = Field(..., description="Main wedding date in YYYY-MM-DD format")
    slug: str = Field(..., description="URL-friendly slug for the wedding")
    events: List[EventModel] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        schema_extra = {
            "example": {
                "_id": "wedding_001",
                "couple_names": "Tolu & Peace",
                "date": "2026-05-29",
                "slug": "tolu-peace-wedding",
                "events": [
                    {"type": "traditional", "date": "2026-05-29"},
                    {"type": "white_wedding", "date": "2026-05-30"},
                    {"type": "reception", "date": "2026-05-31"}
                ]
            }
        }