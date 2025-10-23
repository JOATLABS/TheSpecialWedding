from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException
from pymongo import ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from app.core.database import mongo


def _ensure_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        for candidate in (value, value.replace("Z", "+00:00")):
            try:
                parsed = datetime.fromisoformat(candidate)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                continue
    return datetime.now(timezone.utc)


def _serialize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    serialized = {**document}
    doc_id = serialized.pop("_id", None)
    if doc_id is not None:
        serialized["id"] = str(doc_id)
    for key in ("snapshot_time", "ingested_at"):
        value = serialized.get(key)
        if isinstance(value, datetime):
            serialized[key] = value.astimezone(timezone.utc)
    return serialized


class PlatformMetricsService:
    def __init__(self) -> None:
        self.collection: Collection = mongo.get_platform_metrics_collection()
        self.collection.create_index([("snapshot_time", DESCENDING)])

    def save_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Snapshot payload must be an object")

        snapshot_time = _ensure_datetime(payload.get("snapshot_time") or payload.get("timestamp"))
        document = {
            "snapshot_time": snapshot_time,
            "timestamp": payload.get("timestamp"),
            "metrics": payload,
            "ingested_at": datetime.now(timezone.utc),
        }

        try:
            result = self.collection.insert_one(document)
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to persist metrics snapshot: {exc}") from exc

        document["_id"] = result.inserted_id
        return _serialize_document(document)

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        try:
            document = self.collection.find_one(sort=[("snapshot_time", DESCENDING)])
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve latest snapshot: {exc}") from exc

        if not document:
            return None
        return _serialize_document(document)

    def get_history(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {}
        if since is not None:
            query["snapshot_time"] = {"$gte": since}

        try:
            cursor: Iterable[Dict[str, Any]] = self.collection.find(query).sort("snapshot_time", ASCENDING)
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics history: {exc}") from exc

        return [_serialize_document(document) for document in cursor]


service = PlatformMetricsService()
