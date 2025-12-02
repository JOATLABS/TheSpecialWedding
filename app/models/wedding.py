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

class PrivacySettingsModel(BaseModel):
    privacy_mode: str = Field(default="private", description="Privacy mode: private, password, public")
    guest_auth_required: bool = Field(default=True, description="Whether guest authentication is required")
    password_protection: Optional[str] = Field(None, description="Password for password-protected weddings")
    allow_guest_sharing: bool = Field(default=False, description="Whether guests can share wedding links")
    require_phone_verification: bool = Field(default=True, description="Require phone number for guest verification")
    require_name_verification: bool = Field(default=True, description="Require name for guest verification")

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

class OurStoryModel(BaseModel):
    text: str = Field(..., description="Our story text/paragraph")
    image_url: Optional[str] = Field(None, description="S3 key for couple photo")
    image_shape: str = Field(default="circle", description="Image shape: circle, heart, square, or hexagon")

class WeddingPartyMemberModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the wedding party member")
    name: str = Field(..., description="Full name of the wedding party member")
    role: str = Field(..., description="Role: maid_of_honor, bridesmaid, best_man, groomsman, or custom")
    image_url: Optional[str] = Field(None, description="S3 key for member photo")
    display_order: Optional[int] = Field(default=0, description="Display order within their role group")
    side: str = Field(..., description="bride or groom")
    linked_guest_id: Optional[str] = Field(None, description="ID of linked guest if applicable")
    linked_guest_email: Optional[str] = Field(None, description="Email of linked guest for matching")

class WeddingModel(BaseModel):
    id: str = Field(..., alias="_id")
    couple_names: str = Field(..., min_length=3, max_length=200)
    date: str = Field(..., description="Main wedding date in YYYY-MM-DD format")
    slug: str = Field(..., description="URL-friendly slug for the wedding")
    events: List[EventModel] = Field(default_factory=list)
    rsvp_config: Optional[RSVPConfigModel] = Field(default_factory=RSVPConfigModel)
    privacy_settings: Optional[PrivacySettingsModel] = Field(default_factory=PrivacySettingsModel)
    registries: List[RegistryItemModel] = Field(default_factory=list)
    faqs: List[FAQItemModel] = Field(default_factory=list)
    theme_config: Optional[ThemeConfigModel] = Field(default_factory=ThemeConfigModel)
    featured_image: Optional[str] = Field(None, description="S3 key for the featured background image")
    our_story: Optional[OurStoryModel] = Field(None, description="Our story content and image")
    wedding_party: List[WeddingPartyMemberModel] = Field(default_factory=list, description="Wedding party members")
    reminder_from_email: Optional[str] = Field(None, description="Custom from email for reminders (e.g., couple@example.com)")
    # SAAS Multi-tenancy fields (backward compatible - won't break existing weddings)
    assigned_planner_email: Optional[str] = Field(None, description="Wedding planner responsible for this wedding")
    created_by: Optional[str] = Field(None, description="ROOT_ADMIN email (always thedeveloper@thespecialwedding.com)")
    status: str = Field(default="active", description="Wedding status: active, inactive, deleted")
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