from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.guest import router as guest_router
from app.api.admin_import import router as import_router
from app.api.rspv import router as rsvp_router
from app.core.database import mongo
from app.utils.token_generator import generate_token

app = FastAPI(title="Wedding WebApp API", version="0.1.0")

app.include_router(health_router, prefix="/health")

app.include_router(guest_router)

app.include_router(import_router)

app.include_router(rsvp_router)
