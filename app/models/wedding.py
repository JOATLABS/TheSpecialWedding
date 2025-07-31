from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class EventDetailsModel(BaseModel):
    venue_name: Optional[str] = Field(None, description="Name of the venue")
    location: Optional[str] = Field(None, description="Address or location of the venue")
    time: Optional[str] = Field(None, description="Event time (e.g., '3:00 PM')")
    attire: Optional[str] = Field(None, description="Dress code/attire details")

class EventModel(BaseModel):
    type: str = Field(..., description="Event type: traditional, white_wedding, reception")
    date: str = Field(..., description="Event date in YYYY-MM-DD format")
    details: Optional[EventDetailsModel] = Field(default=None, description="Additional event details")

class RegistryItemModel(BaseModel):
    name: str = Field(..., description="Registry name (e.g., 'Target', 'Amazon')")
    url: str = Field(..., description="Registry URL")
    color: Optional[str] = Field(default="bg-gray-600", description="Button color class")

class FAQItemModel(BaseModel):
    question: str = Field(..., description="FAQ question")
    answer: str = Field(..., description="FAQ answer")

class RSVPConfigModel(BaseModel):
    greeting: str = Field(default="Join us in celebrating our special day! Please let us know if you'll be attending.", 
                         description="RSVP greeting message")
    help_text: str = Field(default="Check your phone for your personal invitation link, or contact us directly.",
                          description="RSVP help text")
    phone_numbers: List[str] = Field(default_factory=lambda: ["(319) 529-6088", "(405) 708-1076"],
                                    description="Contact phone numbers")

class ThemeConfigModel(BaseModel):
    primary_color: str = Field(default="#1e3a5f", description="Primary color (wedding-navy)")
    secondary_color: str = Field(default="#d4af37", description="Secondary color (wedding-gold)")
    accent_color: str = Field(default="#c8847e", description="Accent color (wedding-rose)")
    background_style: str = Field(default="gradient", description="Background style: gradient, solid, or image")
    font_style: str = Field(default="elegant", description="Font style: elegant, modern, classic, or playful")

class WeddingModel(BaseModel):
    id: str = Field(..., alias="_id")
    couple_names: str = Field(..., min_length=3, max_length=200)
    date: str = Field(..., description="Main wedding date in YYYY-MM-DD format")
    slug: str = Field(..., description="URL-friendly slug for the wedding")
    events: List[EventModel] = Field(default_factory=list)
    rsvp_config: Optional[RSVPConfigModel] = Field(default_factory=RSVPConfigModel)
    registries: List[RegistryItemModel] = Field(default_factory=list)
    faqs: List[FAQItemModel] = Field(default_factory=list)
    theme_config: Optional[ThemeConfigModel] = Field(default_factory=ThemeConfigModel)
    featured_image: Optional[str] = Field(None, description="S3 key for the featured background image")
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
                    {
                        "type": "traditional", 
                        "date": "2026-05-29",
                        "details": {
                            "venue_name": "Family Home",
                            "location": "123 Main Street, Lagos",
                            "time": "10:00 AM",
                            "attire": "Traditional Nigerian attire"
                        }
                    },
                    {
                        "type": "white_wedding", 
                        "date": "2026-05-30",
                        "details": {
                            "venue_name": "St. Mary's Church",
                            "location": "456 Church Road, Lagos",
                            "time": "2:00 PM",
                            "attire": "Formal attire"
                        }
                    },
                    {
                        "type": "reception", 
                        "date": "2026-05-31",
                        "details": {
                            "venue_name": "Grand Ballroom",
                            "location": "789 Event Center, Lagos",
                            "time": "6:00 PM",
                            "attire": "Cocktail attire"
                        }
                    }
                ],
                "rsvp_config": {
                    "greeting": "Join us in celebrating our special day!",
                    "help_text": "Contact us if you need help",
                    "phone_numbers": ["(319) 529-6088", "(405) 708-1076"]
                },
                "registries": [
                    {"name": "Target", "url": "https://target.com/registry/123", "color": "bg-red-600"},
                    {"name": "Amazon", "url": "https://amazon.com/registry/456", "color": "bg-orange-500"}
                ],
                "faqs": [
                    {"question": "What should I wear?", "answer": "Semi-formal attire"},
                    {"question": "Is parking available?", "answer": "Yes, free parking at the venue"}
                ]
            }
        }