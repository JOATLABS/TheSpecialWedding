from fastapi import FastAPI, Depends
from fastapi.security import HTTPBasic
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies.auth import require_admin
import os
from app.api.health import router as health_router
from app.api.guest import router as guest_router
from app.api.admin_import import router as import_router
from app.api.rspv import router as rsvp_router
from app.api.plus_one import router as plus_one_router
from app.core.database import mongo
from app.utils.token_generator import generate_token
from app.api.admin_rsvp import router as admin_rsvp_router
from app.api.admin_auth import router as auth_router
from app.api.reminder import router as reminder_router
from app.api.reminder_telnyx import router as reminder_telnyx_router
from app.api.email_reminders import router as email_reminder_router
from app.api.checkin import router as checkin_router
from app.api.gallery_public import router as gallery_public_router
from app.api.gallery_admin import router as gallery_admin_router
from app.api.wedding import router as wedding_router
from app.api.reminder_utilities import router as reminder_utils_router
from app.api.user_management import router as user_management_router
from app.api.subscription_management import router as subscription_router
from app.api.saas_config import router as saas_config_router

app = FastAPI(
    title="Wedding WebApp API",
    version="0.2.0",
    # Define security scheme for OpenAPI docs
    openapi_tags=[
        {"name": "Admin", "description": "Admin operations requiring authentication"},
        {"name": "Auth", "description": "Authentication operations"},
        {"name": "Guest", "description": "Guest operations"},
        {"name": "RSVP", "description": "RSVP operations"},
        {"name": "Plus-Ones", "description": "Plus-one operations"},
        {"name": "Health", "description": "Health check operations"}
    ]
)

# Add CORS middleware
# Get allowed origins from environment variable
allowed_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.include_router(health_router, prefix="/health")
app.include_router(guest_router, prefix="/guest")  # Public guest endpoints (search, invite)
app.include_router(rsvp_router, prefix="/rsvp")
app.include_router(plus_one_router, prefix="/plus_one")
app.include_router(wedding_router)  # Public wedding endpoints (list, get by slug)
app.include_router(gallery_public_router)  # Public gallery endpoints (view, QR)
app.include_router(subscription_router)  # Public subscription plan endpoints
app.include_router(saas_config_router, prefix="/saas")  # Public SAAS config endpoints

# Admin routes - all under /admin prefix
app.include_router(auth_router, prefix="/admin")
app.include_router(import_router, prefix="/admin")
app.include_router(guest_router, prefix="/admin")  # Admin guest endpoints (list, delete)
app.include_router(admin_rsvp_router, prefix="/admin")
app.include_router(reminder_router, prefix="/admin")
app.include_router(reminder_telnyx_router, prefix="/admin")  # Telnyx SMS endpoints
app.include_router(email_reminder_router, prefix="/admin")  # Email endpoints
app.include_router(checkin_router, prefix="/admin")
app.include_router(gallery_admin_router, prefix="/admin")  # Admin gallery endpoints (upload, delete)
app.include_router(wedding_router, prefix="/admin")  # Admin wedding endpoints (create, update, delete)
app.include_router(reminder_utils_router, prefix="/admin")
app.include_router(user_management_router, prefix="/admin")  # ROOT_ADMIN user management
app.include_router(subscription_router, prefix="/admin")  # Subscription management
app.include_router(saas_config_router, prefix="/admin")  # SAAS configuration management