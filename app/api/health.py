import logging
from datetime import UTC, datetime

from fastapi import APIRouter

from app.utils.response import dict_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/livez", tags=["Health"])
async def liveness():
    """
    Lightweight liveness probe for Kubernetes.
    Returns 200 if the process is alive — no dependency checks.
    K8s restarts the pod if this fails.
    """
    return dict_response(data={"status": "alive"})


@router.get("/readyz", tags=["Health"])
async def readiness():
    """
    Readiness probe for Kubernetes.
    Returns 200 only if all dependencies (DB, Redis) are reachable.
    K8s removes the pod from the Service if this fails (no traffic routed).
    """
    from fastapi.responses import JSONResponse

    checks = {"database": "unknown", "redis": "unknown"}
    ready = True

    # Check MongoDB
    try:
        from app.core.database import mongo

        await mongo.client.server_info()
        checks["database"] = "connected"
    except Exception as e:
        logger.warning(f"Readiness: MongoDB unreachable: {e}")
        checks["database"] = "unreachable"
        ready = False

    # Check Redis (non-fatal if not configured)
    try:
        from app.core.cache import cache

        if cache.redis_client:
            await cache.redis_client.ping()
            checks["redis"] = "connected"
        else:
            checks["redis"] = "not_configured"
    except Exception as e:
        logger.warning(f"Readiness: Redis unreachable: {e}")
        checks["redis"] = "unreachable"
        ready = False

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "checks": checks,
        },
    )


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
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "checks": checks,
        },
    )


@router.get("", tags=["Health"], include_in_schema=False)
async def health_check_no_slash():
    """Alias for platform probes that call /health without following redirects."""

    return await health_check()
