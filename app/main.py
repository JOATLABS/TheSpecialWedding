from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.guest import router as guest_router
from app.api.admin_import import router as import_router
from app.api.rspv import router as rsvp_router
from app.api.plus_one import router as plus_one_router
from app.core.database import mongo
from app.utils.token_generator import generate_token
from app.api.admin_rsvp import router as admin_rsvp_router
from app.api.admin_auth import router as auth_router


app = FastAPI(title="Wedding WebApp API", version="0.2.0")

app.include_router(health_router, prefix="/health")
app.include_router(guest_router, prefix="/guest")
app.include_router(rsvp_router, prefix="/rsvp")
app.include_router(plus_one_router, prefix="/plus_one")

# Admin routes - all under /admin prefix
app.include_router(auth_router, prefix="/admin")
app.include_router(import_router, prefix="/admin")
app.include_router(admin_rsvp_router, prefix="/admin")

