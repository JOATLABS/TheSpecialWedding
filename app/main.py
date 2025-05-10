from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.guest import router as guest_router

app = FastAPI(title="Wedding WebApp API", version="0.1.0")

app.include_router(health_router, prefix="/health")

app.include_router(guest_router)