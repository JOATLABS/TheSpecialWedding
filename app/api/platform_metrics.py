from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.config import settings
from app.dependencies.auth_extended import require_root_admin, ExtendedAuthUser
from app.services.platform_metrics_service import service as metrics_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_metrics_token(authorization: Optional[str] = Header(None)) -> None:
    if not settings.PLATFORM_METRICS_TOKEN:
        logger.error("PLATFORM_METRICS_TOKEN is not configured in settings")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Metrics token not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing metrics token")

    token = authorization.split(" ", 1)[1].strip()
    if token != settings.PLATFORM_METRICS_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid metrics token")


def _serialize_snapshot_response(document: Dict[str, Any]) -> Dict[str, Any]:
    snapshot_time = document.get("snapshot_time")
    ingested_at = document.get("ingested_at")
    return {
        "id": document.get("id"),
        "timestamp": document.get("timestamp"),
        "snapshot_time": snapshot_time.isoformat() if isinstance(snapshot_time, datetime) else snapshot_time,
        "ingested_at": ingested_at.isoformat() if isinstance(ingested_at, datetime) else ingested_at,
        "metrics": document.get("metrics", {}),
    }


@router.get("/metrics/snapshot", tags=["Metrics"], dependencies=[Depends(_require_metrics_token)])
async def get_metrics_snapshot():
    snapshot = await metrics_service.get_latest_snapshot()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No metrics snapshots available")
    return _serialize_snapshot_response(snapshot)


@router.post("/metrics/snapshot", tags=["Metrics"], dependencies=[Depends(_require_metrics_token)])
async def ingest_metrics_snapshot(payload: Dict[str, Any]):
    document = await metrics_service.save_snapshot(payload)
    return _serialize_snapshot_response(document)


@router.get("/admin/platform/metrics", tags=["Admin"])
async def get_admin_metrics_overview(
    current_user: ExtendedAuthUser = Depends(require_root_admin)
):
    """
    Get platform metrics for the admin dashboard.

    Returns stored snapshot if available, otherwise generates live health data.
    """
    # Try to get a stored snapshot first
    snapshot = await metrics_service.get_latest_snapshot()

    if snapshot:
        return _serialize_snapshot_response(snapshot)

    # No snapshot exists - generate live health data
    logger.info("No metrics snapshots found, generating live health data")

    try:
        # Import here to avoid circular imports
        from app.api.admin_platform_metrics import get_platform_health

        # Get live health data from the comprehensive health endpoint
        live_health = await get_platform_health(current_user=current_user)

        # Format as a snapshot response for dashboard compatibility
        now = datetime.now(timezone.utc)
        return {
            "id": None,
            "timestamp": now.isoformat(),
            "snapshot_time": now.isoformat(),
            "ingested_at": now.isoformat(),
            "metrics": live_health,
        }
    except Exception as e:
        logger.error(f"Failed to generate live health data: {e}")
        raise HTTPException(
            status_code=500,
            detail="No metrics snapshots available and failed to generate live data"
        )


@router.get("/admin/platform/metrics/history", tags=["Admin"], dependencies=[Depends(require_root_admin)])
async def get_metrics_history(start_date: Optional[str] = Query(None, description="ISO-8601 timestamp inclusive")):
    since: Optional[datetime] = None
    if start_date:
        try:
            since = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            if since.tzinfo is None:
                since = since.replace(tzinfo=timezone.utc)
            else:
                since = since.astimezone(timezone.utc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="start_date must be an ISO-8601 datetime") from exc

    snapshots = await metrics_service.get_history(since)
    return [_serialize_snapshot_response(snapshot) for snapshot in snapshots]
