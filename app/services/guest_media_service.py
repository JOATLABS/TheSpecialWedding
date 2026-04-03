import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.database import mongo
from app.core.settings import settings
from app.utils.serializers import serialize_mongo_doc

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
}
ALLOWED_MEDIA_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES

MAX_FILES_PER_BATCH = 25
MAX_IMAGE_SIZE_BYTES = 25 * 1024 * 1024
MAX_VIDEO_SIZE_BYTES = 200 * 1024 * 1024
MAX_BATCH_SIZE_BYTES = 500 * 1024 * 1024
DEFAULT_UPLOAD_WINDOW_DAYS = 30
REOPEN_WINDOW_DAYS = 7
UPLOAD_URL_EXPIRES_IN = 15 * 60
DOWNLOAD_URL_EXPIRES_IN = 10 * 60
PREVIEW_URL_EXPIRES_IN = 5 * 60
STREAM_SOURCE_URL_EXPIRES_IN = 60 * 60
STREAM_TOKEN_EXPIRES_IN = 10 * 60
STREAM_TOKEN_REUSE_BUFFER_SECONDS = 30
STREAM_SOURCE_VALIDATION_TIMEOUT_SECONDS = 15
STREAM_JOB_STALE_MINUTES = 5
STREAM_POLL_INTERVAL_SECONDS = 20
EXPORT_JOB_STALE_MINUTES = 30
NOT_SURE_EVENT = "not_sure"
REVIEW_STATUSES = {"pending", "kept", "rejected"}
UPLOAD_STATUSES = {"reserved", "uploaded", "failed"}
STREAM_STATUSES = {"queued", "ingesting", "processing", "ready", "failed", "unconfigured"}


def _safe_filename(filename: str) -> str:
    base_name = os.path.basename(filename or "upload")
    name, extension = os.path.splitext(base_name)
    normalized_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._") or "upload"
    normalized_extension = re.sub(r"[^A-Za-z0-9.]+", "", extension)[:16]
    return f"{normalized_name}{normalized_extension}"[:180]


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


class GuestMediaStorage:
    def __init__(self):
        self.bucket_name = os.getenv("S3_GUEST_MEDIA_BUCKET_NAME") or os.getenv("S3_BUCKET_NAME")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.bucket_name and os.getenv("S3_ENDPOINT_URL") and os.getenv("S3_ACCESS_KEY_ID") and os.getenv("S3_SECRET_ACCESS_KEY"))

    def build_key(self, wedding_slug: str, upload_batch_id: str, asset_id: str, filename: str) -> str:
        now = datetime.now(timezone.utc)
        return (
            f"guest-media/{wedding_slug}/{now.strftime('%Y')}/{now.strftime('%m')}/"
            f"{upload_batch_id}/{asset_id}-{_safe_filename(filename)}"
        )

    def build_export_key(self, wedding_slug: str, export_id: str) -> str:
        now = datetime.now(timezone.utc)
        return (
            f"guest-media-exports/{wedding_slug}/{now.strftime('%Y')}/{now.strftime('%m')}/"
            f"{export_id}.zip"
        )

    def create_presigned_upload_url(self, key: str, content_type: str, expires_in: int = UPLOAD_URL_EXPIRES_IN) -> str:
        if not self.bucket_name:
            raise HTTPException(status_code=503, detail="Guest media storage bucket is not configured")
        return self.s3.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def create_presigned_download_url(self, key: str, expires_in: int = DOWNLOAD_URL_EXPIRES_IN, filename: Optional[str] = None) -> str:
        if not self.bucket_name:
            raise HTTPException(status_code=503, detail="Guest media storage bucket is not configured")

        params: dict[str, Any] = {"Bucket": self.bucket_name, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{_safe_filename(filename)}"'

        return self.s3.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def head_object(self, key: str) -> dict[str, Any]:
        if not self.bucket_name:
            raise HTTPException(status_code=503, detail="Guest media storage bucket is not configured")
        return self.s3.head_object(Bucket=self.bucket_name, Key=key)

    def upload_file(self, local_path: str, key: str, content_type: str) -> None:
        if not self.bucket_name:
            raise HTTPException(status_code=503, detail="Guest media storage bucket is not configured")
        with open(local_path, "rb") as file_handle:
            self.s3.upload_fileobj(
                file_handle,
                self.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )

    def get_object_bytes(self, key: str) -> bytes:
        if not self.bucket_name:
            raise HTTPException(status_code=503, detail="Guest media storage bucket is not configured")
        response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()


class GuestMediaService:
    def __init__(self):
        self.weddings = mongo.db["weddings"]
        self.assets = mongo.db["guest_media_assets"]
        self.exports = mongo.db["guest_media_exports"]
        self.storage = GuestMediaStorage()

        self.cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.cloudflare_api_token = os.getenv("CLOUDFLARE_STREAM_API_TOKEN")
        self.stream_api_base = (
            f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/stream"
            if self.cloudflare_account_id else None
        )

    @property
    def stream_is_configured(self) -> bool:
        return bool(self.stream_api_base and self.cloudflare_api_token)

    def hash_upload_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _build_upload_token(self, wedding_id: str, wedding_slug: str, rotated_at: datetime) -> str:
        payload = f"{wedding_id}:{wedding_slug}:{rotated_at.astimezone(timezone.utc).isoformat()}"
        digest = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")

    def _serialize_datetime(self, value: Any) -> Optional[str]:
        serialized = _coerce_datetime(value)
        return serialized.isoformat() if serialized else None

    def _wedding_id_query(self, wedding_id: Any) -> dict[str, Any]:
        query_variants = [{"_id": wedding_id}]
        if isinstance(wedding_id, str) and len(wedding_id) == 24:
            try:
                from bson import ObjectId

                query_variants.append({"_id": ObjectId(wedding_id)})
            except Exception:
                pass

        if len(query_variants) == 1:
            return query_variants[0]
        return {"$or": query_variants}

    async def _get_wedding_by_slug(self, slug: str) -> dict[str, Any]:
        wedding = await self.weddings.find_one({"slug": slug})
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")
        return wedding

    async def _get_wedding_by_id(self, wedding_id: Any) -> dict[str, Any]:
        wedding = await self.weddings.find_one(self._wedding_id_query(wedding_id))
        if not wedding:
            raise HTTPException(status_code=404, detail="Wedding not found")
        return wedding

    def _default_upload_close_at(self, wedding: dict[str, Any]) -> datetime:
        raw_date = wedding.get("date")
        if isinstance(raw_date, str):
            try:
                parsed = datetime.fromisoformat(f"{raw_date}T00:00:00+00:00")
                return parsed + timedelta(days=DEFAULT_UPLOAD_WINDOW_DAYS)
            except ValueError:
                pass
        return datetime.now(timezone.utc) + timedelta(days=DEFAULT_UPLOAD_WINDOW_DAYS)

    async def ensure_guest_media_config(self, wedding: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        guest_media = dict(wedding.get("guest_media") or {})
        changed = False

        last_rotated_at = _coerce_datetime(guest_media.get("last_rotated_at"))
        if not last_rotated_at:
            last_rotated_at = now
            guest_media["last_rotated_at"] = last_rotated_at
            changed = True

        upload_closes_at = _coerce_datetime(guest_media.get("upload_closes_at"))
        if not upload_closes_at:
            upload_closes_at = self._default_upload_close_at(wedding)
            guest_media["upload_closes_at"] = upload_closes_at
            changed = True

        if "enabled" not in guest_media:
            guest_media["enabled"] = True
            changed = True

        wedding_id = str(wedding.get("_id"))
        upload_token = self._build_upload_token(wedding_id, wedding.get("slug", ""), last_rotated_at)
        token_hash = self.hash_upload_token(upload_token)

        if guest_media.get("upload_token_hash") != token_hash:
            guest_media["upload_token_hash"] = token_hash
            changed = True

        if changed:
            await self.weddings.update_one(
                {"_id": wedding["_id"]},
                {
                    "$set": {
                        "guest_media": guest_media,
                        "updated_at": now,
                    }
                },
            )
            wedding["guest_media"] = guest_media

        return {
            "config": guest_media,
            "upload_token": upload_token,
        }

    def _build_upload_link(self, wedding_slug: str, upload_token: str) -> str:
        base = settings.frontend_url or ""
        if base:
            return f"{base.rstrip('/')}/{wedding_slug}/upload/{upload_token}"
        return f"/{wedding_slug}/upload/{upload_token}"

    def _event_options(self, wedding: dict[str, Any]) -> list[dict[str, Any]]:
        options = [{"value": NOT_SURE_EVENT, "label": "Not sure", "date": None}]
        for event in wedding.get("events", []) or []:
            event_type = event.get("type")
            if not event_type:
                continue

            custom_label = event.get("custom_type_label")
            label = custom_label or str(event_type).replace("_", " ").title()
            options.append({
                "value": event_type,
                "label": label,
                "date": event.get("date"),
            })
        return options

    def _normalize_event_type(self, event_type: Optional[str], wedding: dict[str, Any]) -> Optional[str]:
        if not event_type or event_type == NOT_SURE_EVENT:
            return None

        allowed = {event.get("type") for event in wedding.get("events", []) if event.get("type")}
        if event_type not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported event type: {event_type}")
        return event_type

    def _validate_uploaded_object_constraints(
        self,
        reserved_asset: dict[str, Any],
        *,
        actual_size: int,
        actual_content_type: str,
    ) -> None:
        if actual_size <= 0:
            raise ValueError("Uploaded object is empty")

        reserved_size = int(reserved_asset.get("size_bytes") or 0)
        reserved_content_type = str(reserved_asset.get("mime_type") or "").lower()
        actual_content_type = actual_content_type.lower()

        if actual_content_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError("Uploaded object uses an unsupported media type")
        if reserved_content_type and actual_content_type != reserved_content_type:
            raise ValueError("Uploaded object content type does not match the reserved upload")
        if reserved_size and actual_size != reserved_size:
            raise ValueError("Uploaded object size does not match the reserved upload")
        if actual_size > MAX_BATCH_SIZE_BYTES:
            raise ValueError("Uploaded object is unexpectedly large")

        media_type = reserved_asset.get("media_type")
        if media_type == "image":
            if actual_content_type not in ALLOWED_IMAGE_TYPES:
                raise ValueError("Uploaded object is not a supported image type")
            if actual_size > MAX_IMAGE_SIZE_BYTES:
                raise ValueError("Images must be 25 MB or smaller")
        elif media_type == "video":
            if actual_content_type not in ALLOWED_VIDEO_TYPES:
                raise ValueError("Uploaded object is not a supported video type")
            if actual_size > MAX_VIDEO_SIZE_BYTES:
                raise ValueError("Videos must be 200 MB or smaller")
        else:
            raise ValueError("Reserved upload has an unknown media type")

    def _asset_api_path(self, asset_id: str, variant: str) -> str:
        return f"/couple/portal/memories/{asset_id}/{variant}"

    def _stream_allowed_origins(self) -> list[str]:
        raw_candidates = [settings.frontend_url, *(settings.cors_origins or [])]
        allowed_origins: list[str] = []

        for raw_value in raw_candidates:
            if not raw_value:
                continue

            candidate = str(raw_value).strip()
            if not candidate or candidate == "*":
                continue

            parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
            hostname = (parsed.hostname or parsed.path.split("/")[0]).strip().lower()
            if not hostname or hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
                continue

            allowed_origins.append(hostname)

        return sorted(set(allowed_origins))

    def _stream_security_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"requireSignedURLs": True}
        allowed_origins = self._stream_allowed_origins()
        if allowed_origins:
            payload["allowedOrigins"] = allowed_origins
        return payload

    def _stream_security_signature(self) -> str:
        payload = self._stream_security_payload()
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _stream_result_needs_security_update(self, stream_result: dict[str, Any]) -> bool:
        if not stream_result.get("requireSignedURLs"):
            return True

        required_origins = self._stream_allowed_origins()
        if not required_origins:
            return False

        current_origins = sorted({
            str(origin).strip().lower()
            for origin in (stream_result.get("allowedOrigins") or [])
            if str(origin).strip()
        })
        return current_origins != required_origins

    def _build_stream_copy_payload(self, source_url: str, asset: dict[str, Any], asset_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "url": source_url,
            "meta": {
                "asset_id": asset_id,
                "wedding_id": asset.get("wedding_id"),
                "filename": asset.get("original_filename"),
            },
            **self._stream_security_payload(),
        }
        return payload

    async def _validate_stream_source_url(self, source_url: str) -> None:
        timeout = aiohttp.ClientTimeout(total=STREAM_SOURCE_VALIDATION_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.head(source_url, allow_redirects=True) as response:
                if response.status >= 400:
                    raise RuntimeError(
                        f"Guest media source URL rejected HEAD requests with status {response.status}"
                    )

            async with session.get(
                source_url,
                allow_redirects=True,
                headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"},
            ) as response:
                if response.status not in {200, 206}:
                    raise RuntimeError(
                        f"Guest media source URL rejected ranged GET requests with status {response.status}"
                    )

                supports_range = (
                    response.status == 206
                    or "bytes" in (response.headers.get("Accept-Ranges") or "").lower()
                    or bool(response.headers.get("Content-Range"))
                )
                if not supports_range:
                    raise RuntimeError(
                        "Guest media source URL must support ranged GET requests for Cloudflare Stream ingestion"
                    )

                await response.content.read(1)

    def _stream_base_url_from_result(self, stream_result: dict[str, Any]) -> Optional[str]:
        candidates = [
            stream_result.get("preview"),
            stream_result.get("thumbnail"),
            ((stream_result.get("playback") or {}).get("hls")),
            ((stream_result.get("playback") or {}).get("dash")),
        ]

        for candidate in candidates:
            if not candidate:
                continue
            parsed = urlparse(candidate)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return None

    def _require_upload_window_open(self, guest_media_config: dict[str, Any]) -> None:
        upload_closes_at = _coerce_datetime(guest_media_config.get("upload_closes_at"))
        if guest_media_config.get("enabled") is False:
            raise HTTPException(status_code=403, detail="Guest uploads are currently closed")
        if upload_closes_at and upload_closes_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=403, detail="Guest uploads are closed for this wedding")

    async def validate_public_upload_access(self, slug: str, upload_token: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_slug(slug)
        ensured = await self.ensure_guest_media_config(wedding)
        guest_media = ensured["config"]
        token_hash = self.hash_upload_token(upload_token)
        if not hmac.compare_digest(guest_media.get("upload_token_hash", ""), token_hash):
            raise HTTPException(status_code=404, detail="Upload link is invalid")
        self._require_upload_window_open(guest_media)
        return {
            "wedding": wedding,
            "guest_media": guest_media,
        }

    def _validate_file_descriptor(self, file_data: dict[str, Any]) -> dict[str, Any]:
        filename = str(file_data.get("filename") or "").strip()
        content_type = str(file_data.get("content_type") or "").strip().lower()
        size_bytes = int(file_data.get("size_bytes") or 0)

        if not filename:
            raise HTTPException(status_code=400, detail="Each file must include a filename")
        if content_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(status_code=400, detail=f"File type '{content_type}' is not allowed")
        if size_bytes <= 0:
            raise HTTPException(status_code=400, detail="Each file must include a positive file size")

        is_image = content_type in ALLOWED_IMAGE_TYPES
        max_allowed = MAX_IMAGE_SIZE_BYTES if is_image else MAX_VIDEO_SIZE_BYTES
        if size_bytes > max_allowed:
            if is_image:
                raise HTTPException(status_code=400, detail="Images must be 25 MB or smaller")
            raise HTTPException(status_code=400, detail="Videos must be 200 MB or smaller")

        return {
            "filename": _safe_filename(filename),
            "content_type": content_type,
            "size_bytes": size_bytes,
            "media_type": "image" if is_image else "video",
        }

    async def get_public_upload_context(self, slug: str, upload_token: str) -> dict[str, Any]:
        if not self.storage.is_configured:
            raise HTTPException(status_code=503, detail="Guest media uploads are not configured")

        validated = await self.validate_public_upload_access(slug, upload_token)
        wedding = validated["wedding"]
        guest_media = validated["guest_media"]

        return {
            "wedding": {
                "slug": wedding.get("slug"),
                "couple_names": wedding.get("couple_names"),
                "date": wedding.get("date"),
            },
            "guest_media": {
                "enabled": guest_media.get("enabled", True),
                "upload_closes_at": self._serialize_datetime(guest_media.get("upload_closes_at")),
                "link_status": "open",
                "storage_ready": self.storage.is_configured,
                "stream_configured": self.stream_is_configured,
            },
            "events": self._event_options(wedding),
            "limits": {
                "max_files_per_batch": MAX_FILES_PER_BATCH,
                "max_image_size_bytes": MAX_IMAGE_SIZE_BYTES,
                "max_video_size_bytes": MAX_VIDEO_SIZE_BYTES,
                "max_batch_size_bytes": MAX_BATCH_SIZE_BYTES,
                "accepted_types": sorted(ALLOWED_MEDIA_TYPES),
                "not_sure_value": NOT_SURE_EVENT,
            },
        }

    async def create_upload_plan(
        self,
        slug: str,
        upload_token: str,
        uploader_name: str,
        batch_event_type: Optional[str],
        files: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.storage.is_configured:
            raise HTTPException(status_code=503, detail="Guest media uploads are not configured")

        validated = await self.validate_public_upload_access(slug, upload_token)
        wedding = validated["wedding"]

        cleaned_name = uploader_name.strip()
        if not cleaned_name:
            raise HTTPException(status_code=400, detail="Guest name is required")
        if len(cleaned_name) > 120:
            raise HTTPException(status_code=400, detail="Guest name must be 120 characters or fewer")

        if not files:
            raise HTTPException(status_code=400, detail="Select at least one file to upload")
        if len(files) > MAX_FILES_PER_BATCH:
            raise HTTPException(status_code=400, detail=f"You can upload up to {MAX_FILES_PER_BATCH} files at a time")

        normalized_batch_event = self._normalize_event_type(batch_event_type, wedding)
        normalized_files: list[dict[str, Any]] = []
        total_size_bytes = 0

        for file_data in files:
            validated_file = self._validate_file_descriptor(file_data)
            validated_file["event_type"] = self._normalize_event_type(file_data.get("event_type"), wedding) or normalized_batch_event
            total_size_bytes += validated_file["size_bytes"]
            normalized_files.append(validated_file)

        if total_size_bytes > MAX_BATCH_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Batch uploads must be 500 MB or smaller")

        upload_batch_id = hashlib.sha1(
            f"{slug}:{cleaned_name}:{datetime.now(timezone.utc).isoformat()}".encode("utf-8")
        ).hexdigest()[:20]
        created_at = datetime.now(timezone.utc)
        wedding_id = str(wedding.get("_id"))

        asset_docs = []
        upload_entries = []

        for index, file_data in enumerate(normalized_files):
            asset_id = hashlib.sha1(
                f"{upload_batch_id}:{index}:{file_data['filename']}:{created_at.isoformat()}".encode("utf-8")
            ).hexdigest()[:24]
            key = self.storage.build_key(slug, upload_batch_id, asset_id, file_data["filename"])
            upload_url = self.storage.create_presigned_upload_url(key, file_data["content_type"])

            asset_docs.append({
                "_id": asset_id,
                "wedding_id": wedding_id,
                "wedding_slug": slug,
                "upload_batch_id": upload_batch_id,
                "uploader_name": cleaned_name,
                "event_type": file_data["event_type"],
                "media_type": file_data["media_type"],
                "mime_type": file_data["content_type"],
                "size_bytes": file_data["size_bytes"],
                "original_filename": file_data["filename"],
                "original_bucket": self.storage.bucket_name,
                "original_key": key,
                "stream_uid": None,
                "stream_status": None,
                "stream_playback_base_url": None,
                "review_status": "pending",
                "visibility": "couple_only",
                "upload_status": "reserved",
                "uploaded_at": None,
                "reviewed_at": None,
                "created_at": created_at,
                "updated_at": created_at,
            })

            upload_entries.append({
                "asset_id": asset_id,
                "upload_url": upload_url,
                "key": key,
                "content_type": file_data["content_type"],
                "media_type": file_data["media_type"],
                "event_type": file_data["event_type"] or NOT_SURE_EVENT,
                "filename": file_data["filename"],
            })

        try:
            await self.assets.insert_many(asset_docs, ordered=True)
        except Exception as exc:
            logger.error("Failed to reserve guest media assets: %s", exc)
            raise HTTPException(status_code=500, detail="Could not prepare upload plan")

        return {
            "upload_batch_id": upload_batch_id,
            "assets": upload_entries,
        }

    async def finalize_upload_batch(
        self,
        slug: str,
        upload_token: str,
        upload_batch_id: str,
        asset_ids: list[str],
    ) -> dict[str, Any]:
        validated = await self.validate_public_upload_access(slug, upload_token)
        wedding = validated["wedding"]
        wedding_id = str(wedding.get("_id"))

        if not upload_batch_id:
            raise HTTPException(status_code=400, detail="Upload batch ID is required")
        if not asset_ids:
            raise HTTPException(status_code=400, detail="At least one uploaded asset is required")

        docs = await self.assets.find({
            "_id": {"$in": asset_ids},
            "wedding_id": wedding_id,
            "wedding_slug": slug,
            "upload_batch_id": upload_batch_id,
        }).to_list(length=len(asset_ids))

        if not docs:
            raise HTTPException(status_code=404, detail="Reserved uploads were not found")

        finalized_ids: list[str] = []
        failed_assets: list[dict[str, str]] = []
        now = datetime.now(timezone.utc)

        for doc in docs:
            try:
                head = self.storage.head_object(doc["original_key"])
                actual_size = int(head.get("ContentLength") or 0)
                actual_content_type = str(head.get("ContentType") or doc.get("mime_type") or "").lower()

                self._validate_uploaded_object_constraints(
                    doc,
                    actual_size=actual_size,
                    actual_content_type=actual_content_type,
                )

                update_data = {
                    "upload_status": "uploaded",
                    "uploaded_at": now,
                    "updated_at": now,
                    "size_bytes": actual_size,
                    "mime_type": actual_content_type or doc.get("mime_type"),
                }

                if doc.get("media_type") == "video":
                    update_data["stream_status"] = "queued" if self.stream_is_configured else "unconfigured"

                await self.assets.update_one({"_id": doc["_id"]}, {"$set": update_data})
                finalized_ids.append(str(doc["_id"]))
            except Exception as exc:
                logger.warning("Guest media finalize failed for %s: %s", doc.get("_id"), exc)
                await self.assets.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "upload_status": "failed",
                            "updated_at": now,
                            "failure_reason": str(exc),
                        }
                    },
                )
                failed_assets.append({
                    "asset_id": str(doc["_id"]),
                    "reason": str(exc),
                })

        if not finalized_ids:
            raise HTTPException(status_code=400, detail="No files finished uploading successfully")

        return {
            "uploaded_count": len(finalized_ids),
            "failed_count": len(failed_assets),
            "assets": finalized_ids,
            "failed_assets": failed_assets,
        }

    async def _stream_request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self.stream_api_base or not self.cloudflare_api_token:
            raise RuntimeError("Cloudflare Stream is not configured")

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                method,
                f"{self.stream_api_base}{path}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.cloudflare_api_token}",
                    "Content-Type": "application/json",
                },
            ) as response:
                data = await response.json(content_type=None)
                if response.status >= 400 or not data.get("success", False):
                    raise RuntimeError(f"Cloudflare Stream error: {data}")
                return data.get("result") or {}

    async def _create_stream_signed_token(self, stream_uid: str) -> tuple[str, datetime]:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        result = await self._stream_request(
            "POST",
            f"/{stream_uid}/token",
            payload={
                "exp": now_ts + STREAM_TOKEN_EXPIRES_IN,
                "nbf": now_ts - 30,
            },
        )
        token = result.get("token")
        if not token:
            raise RuntimeError("Cloudflare Stream did not return a signed playback token")
        expires_at = datetime.fromtimestamp(now_ts + STREAM_TOKEN_EXPIRES_IN, tz=timezone.utc)
        return token, expires_at

    async def _enforce_stream_security(self, stream_uid: str) -> None:
        await self._stream_request(
            "POST",
            f"/{stream_uid}",
            payload=self._stream_security_payload(),
        )

    async def _delete_stream_video(self, stream_uid: str) -> None:
        await self._stream_request("DELETE", f"/{stream_uid}")

    async def _ingest_video_into_stream(self, asset_id: str) -> None:
        asset = await self.assets.find_one({"_id": asset_id, "upload_status": "uploaded"})
        if not asset or asset.get("media_type") != "video":
            return

        if not self.stream_is_configured:
            await self.assets.update_one(
                {"_id": asset_id},
                {
                    "$set": {
                        "stream_status": "unconfigured",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            return

        stream_uid: Optional[str] = None
        try:
            source_url = self.storage.create_presigned_download_url(
                asset["original_key"],
                expires_in=STREAM_SOURCE_URL_EXPIRES_IN,
            )
            await self._validate_stream_source_url(source_url)
            result = await self._stream_request(
                "POST",
                "/copy",
                payload=self._build_stream_copy_payload(source_url, asset, asset_id),
            )
            stream_uid = result.get("uid")
            if not stream_uid:
                raise RuntimeError("Cloudflare Stream did not return a stream UID")

            await self.assets.update_one(
                {"_id": asset_id},
                {
                    "$set": {
                        "stream_uid": stream_uid,
                        "stream_status": "processing",
                        "stream_playback_base_url": self._stream_base_url_from_result(result),
                        "stream_security_signature": self._stream_security_signature(),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as exc:
            logger.error("Video ingest failed for asset %s: %s", asset_id, exc)
            if stream_uid:
                try:
                    await self._delete_stream_video(stream_uid)
                except Exception as cleanup_exc:
                    logger.warning("Failed to clean up orphaned Cloudflare Stream video %s: %s", stream_uid, cleanup_exc)
            await self.assets.update_one(
                {"_id": asset_id},
                {
                    "$set": {
                        "stream_status": "failed",
                        "stream_error": str(exc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

    async def _poll_stream_ready_once(self, asset_id: str, stream_uid: str) -> None:
        try:
            result = await self._stream_request("GET", f"/{stream_uid}")
            if self._stream_result_needs_security_update(result):
                await self._enforce_stream_security(stream_uid)
                result = await self._stream_request("GET", f"/{stream_uid}")

            status = result.get("status") or {}
            state = str(status.get("state") or "").lower()
            ready = bool(result.get("readyToStream") or state == "ready")

            update_data: dict[str, Any]
            if state == "error":
                error_reason = status.get("errorReasonText") or status.get("errorReasonCode") or "Cloudflare Stream processing failed"
                update_data = {
                    "stream_status": "failed",
                    "stream_error": error_reason,
                    "updated_at": datetime.now(timezone.utc),
                }
            else:
                update_data = {
                    "stream_status": "ready" if ready else "processing",
                    "stream_playback_base_url": self._stream_base_url_from_result(result),
                    "stream_security_signature": self._stream_security_signature(),
                    "updated_at": datetime.now(timezone.utc),
                }
                ready_at = _coerce_datetime(result.get("readyToStreamAt"))
                if ready:
                    update_data["stream_ready_at"] = ready_at or datetime.now(timezone.utc)
            await self.assets.update_one({"_id": asset_id}, {"$set": update_data})
        except Exception as exc:
            logger.warning("Stream readiness poll failed for %s: %s", asset_id, exc)

    async def process_pending_video_jobs(self, *, limit: int = 6) -> int:
        from pymongo import ReturnDocument

        processed = 0
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(minutes=STREAM_JOB_STALE_MINUTES)
        poll_cutoff = now - timedelta(seconds=STREAM_POLL_INTERVAL_SECONDS)

        while processed < limit:
            claimed_asset = await self.assets.find_one_and_update(
                {
                    "media_type": "video",
                    "upload_status": "uploaded",
                    "stream_uid": None,
                    "$or": [
                        {"stream_status": "queued"},
                        {"stream_status": "ingesting", "updated_at": {"$lte": stale_cutoff}},
                    ],
                },
                {
                    "$set": {
                        "stream_status": "ingesting",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                sort=[("uploaded_at", 1)],
                return_document=ReturnDocument.AFTER,
            )

            if not claimed_asset:
                break

            await self._ingest_video_into_stream(str(claimed_asset["_id"]))
            processed += 1

        if processed >= limit:
            return processed

        pending_polls = await self.assets.find(
            {
                "media_type": "video",
                "upload_status": "uploaded",
                "stream_uid": {"$ne": None},
                "stream_status": "processing",
                "updated_at": {"$lte": poll_cutoff},
            }
        ).sort("updated_at", 1).limit(limit - processed).to_list(length=limit - processed)

        for asset in pending_polls:
            await self._poll_stream_ready_once(str(asset["_id"]), asset["stream_uid"])
            processed += 1

        return processed

    async def _count_assets(self, wedding_id: str, **filters: Any) -> int:
        query: dict[str, Any] = {"wedding_id": wedding_id, "upload_status": "uploaded"}
        query.update(filters)
        return await self.assets.count_documents(query)

    async def get_dashboard_summary(self, wedding_id: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        ensured = await self.ensure_guest_media_config(wedding)
        guest_media = ensured["config"]

        normalized_wedding_id = str(wedding.get("_id"))
        pending = await self._count_assets(normalized_wedding_id, review_status="pending")
        kept = await self._count_assets(normalized_wedding_id, review_status="kept")
        rejected = await self._count_assets(normalized_wedding_id, review_status="rejected")
        processing_videos = await self._count_assets(
            normalized_wedding_id,
            media_type="video",
            stream_status={"$in": ["queued", "ingesting", "processing"]},
        )

        upload_closes_at = _coerce_datetime(guest_media.get("upload_closes_at"))
        is_open = guest_media.get("enabled", True) and (not upload_closes_at or upload_closes_at >= datetime.now(timezone.utc))

        return {
            "pending_count": pending,
            "kept_count": kept,
            "rejected_count": rejected,
            "processing_videos": processing_videos,
            "enabled": guest_media.get("enabled", True),
            "link_status": "open" if is_open else "closed",
            "upload_closes_at": self._serialize_datetime(upload_closes_at),
            "storage_ready": self.storage.is_configured,
            "stream_configured": self.stream_is_configured,
        }

    async def get_couple_settings(self, wedding_id: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        ensured = await self.ensure_guest_media_config(wedding)
        guest_media = ensured["config"]
        upload_token = ensured["upload_token"]

        summary = await self.get_dashboard_summary(str(wedding.get("_id")))

        return {
            **summary,
            "upload_url": self._build_upload_link(wedding.get("slug", ""), upload_token),
            "upload_token_last_rotated_at": self._serialize_datetime(guest_media.get("last_rotated_at")),
            "event_options": self._event_options(wedding),
            "wedding": {
                "slug": wedding.get("slug"),
                "couple_names": wedding.get("couple_names"),
            },
        }

    async def update_couple_settings(
        self,
        wedding_id: str,
        *,
        enabled: Optional[bool] = None,
        upload_closes_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        ensured = await self.ensure_guest_media_config(wedding)
        guest_media = dict(ensured["config"])
        now = datetime.now(timezone.utc)

        if enabled is not None:
            guest_media["enabled"] = enabled
            if enabled:
                current_close = _coerce_datetime(guest_media.get("upload_closes_at"))
                if not current_close or current_close < now:
                    guest_media["upload_closes_at"] = now + timedelta(days=REOPEN_WINDOW_DAYS)

        if upload_closes_at is not None:
            normalized_close = upload_closes_at if upload_closes_at.tzinfo else upload_closes_at.replace(tzinfo=timezone.utc)
            guest_media["upload_closes_at"] = normalized_close

        await self.weddings.update_one(
            {"_id": wedding["_id"]},
            {
                "$set": {
                    "guest_media": guest_media,
                    "updated_at": now,
                }
            },
        )

        return await self.get_couple_settings(str(wedding.get("_id")))

    async def rotate_upload_link(self, wedding_id: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        guest_media = dict(wedding.get("guest_media") or {})
        now = datetime.now(timezone.utc)
        guest_media["last_rotated_at"] = now
        upload_token = self._build_upload_token(str(wedding.get("_id")), wedding.get("slug", ""), now)
        guest_media["upload_token_hash"] = self.hash_upload_token(upload_token)
        if "enabled" not in guest_media:
            guest_media["enabled"] = True
        if not _coerce_datetime(guest_media.get("upload_closes_at")):
            guest_media["upload_closes_at"] = self._default_upload_close_at(wedding)

        await self.weddings.update_one(
            {"_id": wedding["_id"]},
            {
                "$set": {
                    "guest_media": guest_media,
                    "updated_at": now,
                }
            },
        )

        return await self.get_couple_settings(str(wedding.get("_id")))

    def _image_preview_url(self, asset: dict[str, Any]) -> str:
        return self.storage.create_presigned_download_url(
            asset["original_key"],
            expires_in=PREVIEW_URL_EXPIRES_IN,
        )

    async def _get_stream_base_url(self, asset: dict[str, Any]) -> str:
        base_url = asset.get("stream_playback_base_url")
        stream_uid = asset.get("stream_uid")
        if base_url and stream_uid and asset.get("stream_security_signature") == self._stream_security_signature():
            return base_url
        if not stream_uid:
            raise HTTPException(status_code=409, detail="Video playback is not ready yet")

        result = await self._stream_request("GET", f"/{stream_uid}")
        if self._stream_result_needs_security_update(result):
            await self._enforce_stream_security(stream_uid)
            result = await self._stream_request("GET", f"/{stream_uid}")

        status = result.get("status") or {}
        if str(status.get("state") or "").lower() == "error":
            error_reason = status.get("errorReasonText") or status.get("errorReasonCode") or "Cloudflare Stream processing failed"
            await self.assets.update_one(
                {"_id": asset["_id"]},
                {
                    "$set": {
                        "stream_status": "failed",
                        "stream_error": error_reason,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            raise HTTPException(status_code=409, detail="Video processing failed")

        base_url = self._stream_base_url_from_result(result)
        if not base_url:
            raise HTTPException(status_code=503, detail="Video playback domain is unavailable")

        await self.assets.update_one(
            {"_id": asset["_id"]},
            {
                "$set": {
                    "stream_playback_base_url": base_url,
                    "stream_security_signature": self._stream_security_signature(),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        return base_url

    def _get_cached_stream_token(self, asset: dict[str, Any]) -> Optional[str]:
        token = asset.get("stream_token")
        expires_at = _coerce_datetime(asset.get("stream_token_expires_at"))
        if not token or not expires_at:
            return None

        reuse_buffer = timedelta(seconds=STREAM_TOKEN_REUSE_BUFFER_SECONDS)
        if expires_at <= datetime.now(timezone.utc) + reuse_buffer:
            return None
        return str(token)

    async def _get_stream_player_token(self, asset: dict[str, Any]) -> str:
        cached_token = self._get_cached_stream_token(asset)
        if cached_token:
            return cached_token

        token, expires_at = await self._create_stream_signed_token(asset["stream_uid"])
        await self.assets.update_one(
            {"_id": asset["_id"]},
            {
                "$set": {
                    "stream_token": token,
                    "stream_token_expires_at": expires_at,
                }
            },
        )
        return token

    async def _build_signed_stream_player_url(self, asset: dict[str, Any]) -> str:
        stream_uid = asset.get("stream_uid")
        if not stream_uid or asset.get("stream_status") not in {"processing", "ready"}:
            raise HTTPException(status_code=409, detail="Video playback is not ready yet")

        stream_token = await self._get_stream_player_token(asset)
        base_url = await self._get_stream_base_url(asset)
        return f"{base_url}/{stream_token}/iframe"

    async def _build_signed_stream_thumbnail_url(self, asset: dict[str, Any]) -> str:
        stream_uid = asset.get("stream_uid")
        if not stream_uid or asset.get("stream_status") not in {"processing", "ready"}:
            raise HTTPException(status_code=409, detail="Video thumbnail is not ready yet")

        stream_token = await self._get_stream_player_token(asset)
        base_url = await self._get_stream_base_url(asset)
        return f"{base_url}/{stream_token}/thumbnails/thumbnail.jpg?time=2s&height=480"

    def _serialize_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        serialized = serialize_mongo_doc(asset)
        serialized["id"] = serialized.pop("_id", serialized.get("id"))
        asset_id = serialized["id"]

        if serialized.get("media_type") == "image":
            serialized["preview_path"] = self._asset_api_path(asset_id, "preview")
        else:
            if asset.get("stream_uid"):
                serialized["player_path"] = self._asset_api_path(asset_id, "player")
                serialized["thumbnail_path"] = self._asset_api_path(asset_id, "thumbnail")

        serialized["event_type"] = serialized.get("event_type") or NOT_SURE_EVENT
        serialized["download_ready"] = serialized.get("upload_status") == "uploaded"
        serialized.pop("original_bucket", None)
        serialized.pop("original_key", None)
        serialized.pop("stream_uid", None)
        serialized.pop("stream_playback_base_url", None)
        serialized.pop("stream_security_signature", None)
        serialized.pop("stream_token", None)
        serialized.pop("stream_token_expires_at", None)
        return serialized

    async def list_couple_assets(
        self,
        wedding_id: str,
        *,
        review_status: str = "all",
        media_type: str = "all",
        event_type: str = "all",
        uploader_query: Optional[str] = None,
        page: int = 1,
        limit: int = 24,
    ) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        query: dict[str, Any] = {
            "wedding_id": str(wedding.get("_id")),
            "upload_status": "uploaded",
        }

        if review_status != "all":
            if review_status not in REVIEW_STATUSES:
                raise HTTPException(status_code=400, detail="Invalid review status filter")
            query["review_status"] = review_status

        if media_type != "all":
            if media_type not in {"image", "video"}:
                raise HTTPException(status_code=400, detail="Invalid media type filter")
            query["media_type"] = media_type

        if event_type != "all":
            if event_type == NOT_SURE_EVENT:
                query["event_type"] = None
            else:
                query["event_type"] = self._normalize_event_type(event_type, wedding)

        if uploader_query:
            query["uploader_name"] = {"$regex": re.escape(uploader_query.strip()), "$options": "i"}

        total = await self.assets.count_documents(query)
        skip = max(0, page - 1) * limit
        cursor = self.assets.find(query).sort("uploaded_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        return {
            "items": [self._serialize_asset(doc) for doc in docs],
            "page": page,
            "limit": limit,
            "total": total,
            "pages": max(1, (total + limit - 1) // limit),
            "summary": await self.get_dashboard_summary(str(wedding.get("_id"))),
        }

    async def update_review_status(self, wedding_id: str, asset_id: str, review_status: str) -> dict[str, Any]:
        if review_status not in REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Unsupported review status")

        wedding = await self._get_wedding_by_id(wedding_id)
        result = await self.assets.update_one(
            {
                "_id": asset_id,
                "wedding_id": str(wedding.get("_id")),
                "upload_status": "uploaded",
            },
            {
                "$set": {
                    "review_status": review_status,
                    "reviewed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Memory item not found")

        updated_doc = await self.assets.find_one({"_id": asset_id})
        return self._serialize_asset(updated_doc)

    async def get_asset_download(self, wedding_id: str, asset_id: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        asset = await self.assets.find_one({
            "_id": asset_id,
            "wedding_id": str(wedding.get("_id")),
            "upload_status": "uploaded",
        })
        if not asset:
            raise HTTPException(status_code=404, detail="Memory item not found")

        download_url = self.storage.create_presigned_download_url(
            asset["original_key"],
            filename=asset.get("original_filename"),
        )

        return {
            "download_url": download_url,
            "filename": asset.get("original_filename"),
        }

    async def get_asset_redirect_url(self, wedding_id: str, asset_id: str, variant: str) -> str:
        wedding = await self._get_wedding_by_id(wedding_id)
        asset = await self.assets.find_one({
            "_id": asset_id,
            "wedding_id": str(wedding.get("_id")),
            "upload_status": "uploaded",
        })
        if not asset:
            raise HTTPException(status_code=404, detail="Memory item not found")

        try:
            if variant == "preview":
                if asset.get("media_type") == "image":
                    return self._image_preview_url(asset)
                return await self._build_signed_stream_player_url(asset)

            if variant == "player":
                if asset.get("media_type") != "video":
                    raise HTTPException(status_code=400, detail="Only video memories support player playback")
                return await self._build_signed_stream_player_url(asset)

            if variant == "thumbnail":
                if asset.get("media_type") != "video":
                    raise HTTPException(status_code=400, detail="Only video memories have thumbnails")
                return await self._build_signed_stream_thumbnail_url(asset)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Failed to build guest media redirect URL for %s (%s): %s", asset_id, variant, exc)
            raise HTTPException(status_code=503, detail="Media playback is temporarily unavailable")

        raise HTTPException(status_code=400, detail="Unsupported memory asset variant")

    async def create_export_job(
        self,
        wedding_id: str,
        requested_by: str,
        *,
        asset_ids: Optional[list[str]] = None,
        review_status: str = "kept",
    ) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        normalized_wedding_id = str(wedding.get("_id"))

        query: dict[str, Any] = {
            "wedding_id": normalized_wedding_id,
            "upload_status": "uploaded",
        }
        if asset_ids:
            query["_id"] = {"$in": asset_ids}
        if review_status != "all":
            if review_status not in REVIEW_STATUSES:
                raise HTTPException(status_code=400, detail="Unsupported export status filter")
            query["review_status"] = review_status

        assets = await self.assets.find(query).sort("uploaded_at", 1).to_list(length=5000)
        if not assets:
            raise HTTPException(status_code=404, detail="No memories matched this export request")

        export_id = hashlib.sha1(
            f"{normalized_wedding_id}:{requested_by}:{datetime.now(timezone.utc).isoformat()}".encode("utf-8")
        ).hexdigest()[:24]
        now = datetime.now(timezone.utc)
        export_key = self.storage.build_export_key(wedding.get("slug", "wedding"), export_id)

        document = {
            "_id": export_id,
            "wedding_id": normalized_wedding_id,
            "wedding_slug": wedding.get("slug"),
            "requested_by": requested_by,
            "asset_ids": [str(asset["_id"]) for asset in assets],
            "asset_count": len(assets),
            "status": "queued",
            "review_status": review_status,
            "export_bucket": self.storage.bucket_name,
            "export_key": export_key,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "error": None,
        }

        await self.exports.insert_one(document)
        return {
            "export_id": export_id,
            "status": "queued",
            "asset_count": len(assets),
        }

    def _write_export_archive_sync(self, export_key: str, asset_docs: list[dict[str, Any]]) -> None:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for index, asset in enumerate(asset_docs, start=1):
                    file_ext = os.path.splitext(asset.get("original_filename") or "")[1]
                    sanitized_name = _safe_filename(asset.get("original_filename") or f"memory-{index}{file_ext}")
                    archive_name = f"{index:03d}-{asset.get('uploader_name', 'guest')}-{sanitized_name}"
                    object_bytes = self.storage.get_object_bytes(asset["original_key"])
                    zip_file.writestr(archive_name, object_bytes)

            self.storage.upload_file(temp_path, export_key, "application/zip")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def process_export_job(self, export_id: str) -> None:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=EXPORT_JOB_STALE_MINUTES)
        export_doc = await self.exports.find_one_and_update(
            {
                "_id": export_id,
                "$or": [
                    {"status": "queued"},
                    {"status": "processing", "updated_at": {"$lte": stale_cutoff}},
                ],
            },
            {
                "$set": {
                    "status": "processing",
                    "updated_at": datetime.now(timezone.utc),
                    "processing_started_at": datetime.now(timezone.utc),
                }
            },
        )
        if not export_doc:
            return

        try:
            assets = await self.assets.find({
                "_id": {"$in": export_doc.get("asset_ids", [])},
                "upload_status": "uploaded",
            }).sort("uploaded_at", 1).to_list(length=5000)

            if not assets:
                raise RuntimeError("No uploaded assets were available for export")

            await asyncio.to_thread(
                self._write_export_archive_sync,
                export_doc["export_key"],
                assets,
            )

            await self.exports.update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as exc:
            logger.error("Guest media export %s failed: %s", export_id, exc)
            await self.exports.update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": "failed",
                        "error": str(exc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

    async def process_pending_export_jobs(self, *, limit: int = 1) -> int:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=EXPORT_JOB_STALE_MINUTES)
        export_docs = await self.exports.find(
            {
                "$or": [
                    {"status": "queued"},
                    {"status": "processing", "updated_at": {"$lte": stale_cutoff}},
                ]
            }
        ).sort("created_at", 1).limit(limit).to_list(length=limit)

        processed = 0
        for export_doc in export_docs:
            await self.process_export_job(str(export_doc["_id"]))
            processed += 1
        return processed

    async def get_export_job(self, wedding_id: str, export_id: str) -> dict[str, Any]:
        wedding = await self._get_wedding_by_id(wedding_id)
        export_doc = await self.exports.find_one({
            "_id": export_id,
            "wedding_id": str(wedding.get("_id")),
        })
        if not export_doc:
            raise HTTPException(status_code=404, detail="Export job not found")

        serialized = serialize_mongo_doc(export_doc)
        serialized["id"] = serialized.pop("_id", serialized.get("id"))
        if export_doc.get("status") == "completed":
            serialized["download_url"] = self.storage.create_presigned_download_url(
                export_doc["export_key"],
                filename=f"{wedding.get('slug', 'wedding')}-guest-memories.zip",
            )
        return serialized


guest_media_service = GuestMediaService()
