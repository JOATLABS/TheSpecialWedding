from fastapi import APIRouter
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", tags=["Health"])
async def health_check():
    """
    Health check endpoint that validates database connectivity.
    Returns 200 if the app and database are reachable, 503 otherwise.
    """
    from fastapi.responses import JSONResponse

    checks = {
        "database": "unknown",
    }
    overall_status = "ok"

    # Check MongoDB connectivity
    try:
        from app.core.database import mongo
        await mongo.client.server_info()
        checks["database"] = "connected"
    except Exception as e:
        logger.error(f"Health check: MongoDB unreachable: {e}")
        checks["database"] = "unreachable"
        overall_status = "degraded"

    status_code = 200 if overall_status == "ok" else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "checks": checks,
        },
    )