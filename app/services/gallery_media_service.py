import hashlib
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, Optional
from urllib.parse import urlparse

import qrcode
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.core.settings import settings
from app.services.media_storage import MediaStorage, StorageTarget

# Allowed MIME types for gallery uploads
ALLOWED_GALLERY_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/quicktime",
}


class GalleryUploadService:
    def __init__(self):
        self.storage = MediaStorage()
        primary_target = self.storage.target(StorageTarget.PRIMARY)
        self.bucket_name = primary_target.bucket_name
        self.frontend_url = settings.frontend_url

    @property
    def s3(self):
        return self.storage.client

    @staticmethod
    def _strip_storage_part(value: str) -> str:
        return value.strip("/") if isinstance(value, str) else ""

    @staticmethod
    def _normalize_storage_part(value: str, fallback: str = "unknown") -> str:
        normalized = re.sub(r"[^a-z0-9_-]+", "-", str(value or "").strip().lower())
        normalized = normalized.strip("-")
        return normalized or fallback

    @classmethod
    def get_planner_scope_from_wedding(cls, wedding: Optional[dict]) -> Optional[str]:
        if not wedding:
            return None

        planner_id = str(wedding.get("assigned_planner_id") or "").strip()
        if planner_id:
            return f"planner-{cls._normalize_storage_part(planner_id)}"

        planner_email = str(wedding.get("assigned_planner_email") or "").strip().lower()
        if planner_email:
            digest = hashlib.sha256(planner_email.encode("utf-8")).hexdigest()[:16]
            return f"planner-{digest}"

        return "planner-unassigned"

    @classmethod
    def build_wedding_storage_prefix(
        cls,
        folder: str,
        wedding_slug: str,
        planner_scope: Optional[str] = None,
    ) -> str:
        normalized_folder = cls._strip_storage_part(folder)
        normalized_slug = cls._strip_storage_part(wedding_slug)

        if planner_scope:
            normalized_scope = cls._strip_storage_part(planner_scope)
            return f"{normalized_folder}/{normalized_scope}/{normalized_slug}/"

        return f"{normalized_folder}/{normalized_slug}/"

    @classmethod
    def build_wedding_storage_prefixes(
        cls,
        folder: str,
        wedding_slug: str,
        planner_scope: Optional[str] = None,
    ) -> list[str]:
        prefixes: list[str] = []
        if planner_scope:
            prefixes.append(
                cls.build_wedding_storage_prefix(folder, wedding_slug, planner_scope)
            )
        prefixes.append(cls.build_wedding_storage_prefix(folder, wedding_slug))
        return prefixes

    @classmethod
    def build_wedding_storage_key(
        cls,
        folder: str,
        wedding_slug: str,
        filename: str,
        planner_scope: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> str:
        safe_filename = os.path.basename(str(filename))
        safe_timestamp = timestamp or datetime.now(timezone.utc).strftime(
            "%Y%m%d_%H%M%S"
        )
        prefix = cls.build_wedding_storage_prefix(
            folder, wedding_slug, planner_scope
        ).rstrip("/")
        return f"{prefix}/{safe_timestamp}_{safe_filename}"

    @classmethod
    def parse_wedding_storage_key(cls, key: str) -> Optional[dict]:
        parts = cls._strip_storage_part(key).split("/")
        if len(parts) < 3:
            return None

        folder = parts[0]
        planner_scope = None
        if len(parts) >= 4 and parts[1].startswith("planner-"):
            planner_scope = parts[1]
            wedding_slug = parts[2]
            remainder = "/".join(parts[3:])
        else:
            wedding_slug = parts[1]
            remainder = "/".join(parts[2:])

        if not folder or not wedding_slug or not remainder:
            return None

        return {
            "folder": folder,
            "planner_scope": planner_scope,
            "wedding_slug": wedding_slug,
            "remainder": remainder,
        }

    @classmethod
    def parse_wedding_storage_prefix(cls, prefix: str) -> Optional[dict]:
        parts = cls._strip_storage_part(prefix).split("/")
        if len(parts) < 2:
            return None

        folder = parts[0]
        planner_scope = None
        if len(parts) >= 3 and parts[1].startswith("planner-"):
            planner_scope = parts[1]
            wedding_slug = parts[2]
        else:
            wedding_slug = parts[1]

        if not folder or not wedding_slug:
            return None

        return {
            "folder": folder,
            "planner_scope": planner_scope,
            "wedding_slug": wedding_slug,
        }

    @classmethod
    def build_legacy_storage_identity(cls, key: str) -> Optional[str]:
        parsed = cls.parse_wedding_storage_key(key)
        if not parsed:
            return None
        return f"{parsed['folder']}/{parsed['wedding_slug']}/{parsed['remainder']}"

    def build_public_url(self, key: str) -> str:
        return self.storage.build_public_url(StorageTarget.PRIMARY, key)

    def _merge_file_entries(self, file_groups: Iterable[list[dict]]) -> list[dict]:
        seen: set[str] = set()
        merged: list[dict] = []

        for group in file_groups:
            for entry in group:
                identity = (
                    self.build_legacy_storage_identity(entry["key"]) or entry["key"]
                )
                if identity in seen:
                    continue
                seen.add(identity)
                merged.append(entry)

        return sorted(
            merged,
            key=lambda item: (
                self.build_legacy_storage_identity(item["key"]) or item["key"]
            ),
            reverse=True,
        )

    @staticmethod
    def _encode_scoped_cursor(scope: str, cursor: Optional[str]) -> Optional[str]:
        if scope == "legacy" and cursor is None:
            return "legacy::"
        if not cursor:
            return None
        return f"{scope}::{cursor}"

    @staticmethod
    def _decode_scoped_cursor(cursor: Optional[str]) -> tuple[str, Optional[str]]:
        if not cursor:
            return ("primary", None)
        if "::" in cursor:
            scope, raw_cursor = cursor.split("::", 1)
            if scope in {"primary", "legacy"}:
                return (scope, raw_cursor or None)
        return ("primary", cursor)

    def create_presigned_url(self, filename: str, expires_in: int = 300):
        """Legacy method - creates presigned URL without wedding_slug (deprecated)."""
        try:
            key = f"gallery/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{filename}"
            url = self.storage.generate_presigned_put_url(
                StorageTarget.PRIMARY,
                key=key,
                expires_in=expires_in,
            )
            return {"upload_url": url, "key": key}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            raise HTTPException(
                status_code=500, detail=f"Error creating upload URL: {str(exc)}"
            )

    def create_presigned_url_with_wedding(
        self,
        filename: str,
        wedding_slug: str,
        folder: str = "gallery",
        expires_in: int = 300,
        planner_scope: Optional[str] = None,
    ):
        """Create a presigned URL with wedding-aware storage keys."""
        try:
            key = self.build_wedding_storage_key(
                folder=folder,
                wedding_slug=wedding_slug,
                filename=filename,
                planner_scope=planner_scope,
            )
            url = self.storage.generate_presigned_put_url(
                StorageTarget.PRIMARY,
                key=key,
                expires_in=expires_in,
            )
            return {"upload_url": url, "key": key}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            raise HTTPException(
                status_code=500, detail=f"Error creating upload URL: {str(exc)}"
            )

    def get_file_url(self, key: str):
        try:
            url = self.storage.generate_presigned_get_url(
                StorageTarget.PRIMARY,
                key=key,
                expires_in=3600,
            )
            return {"file_url": url}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            raise HTTPException(
                status_code=500, detail=f"Error generating file URL: {str(exc)}"
            )

    def delete_file(self, key: str):
        try:
            self.storage.delete_object(StorageTarget.PRIMARY, key)
            return {"message": "File deleted successfully"}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting file ({error_code}): {str(exc)}",
            )

    def _format_listed_objects(self, objects: list[dict]) -> list[dict]:
        return [
            {
                "key": obj["Key"],
                "url": self.build_public_url(obj["Key"]),
                "size": obj.get("Size", 0),
            }
            for obj in objects
        ]

    def list_uploaded_files_page(
        self,
        prefix: str = "gallery/",
        limit: int = 60,
        cursor: Optional[str] = None,
    ):
        try:
            response = self.storage.list_objects_page(
                StorageTarget.PRIMARY,
                prefix=prefix,
                limit=limit,
                cursor=cursor,
            )
            contents = response.get("Contents", [])

            return {
                "items": self._format_listed_objects(contents),
                "next_cursor": response.get("NextContinuationToken"),
                "has_more": response.get("IsTruncated", False),
            }
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error listing files ({error_code}): {str(exc)}",
            )

    def list_uploaded_files(self, prefix: str = "gallery/"):
        try:
            files = []
            continuation_token = None

            while True:
                response = self.storage.list_objects_page(
                    StorageTarget.PRIMARY,
                    prefix=prefix,
                    limit=1000,
                    cursor=continuation_token,
                )
                files.extend(self._format_listed_objects(response.get("Contents", [])))

                if not response.get("IsTruncated"):
                    break

                continuation_token = response.get("NextContinuationToken")

            return sorted(files, key=lambda item: item["key"], reverse=True)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error listing files ({error_code}): {str(exc)}",
            )

    def list_wedding_files(
        self,
        folder: str,
        wedding_slug: str,
        planner_scope: Optional[str] = None,
    ):
        prefixes = self.build_wedding_storage_prefixes(
            folder=folder,
            wedding_slug=wedding_slug,
            planner_scope=planner_scope,
        )
        file_groups = [self.list_uploaded_files(prefix=prefix) for prefix in prefixes]
        return self._merge_file_entries(file_groups)

    def list_wedding_files_page(
        self,
        folder: str,
        wedding_slug: str,
        planner_scope: Optional[str] = None,
        limit: int = 60,
        cursor: Optional[str] = None,
    ):
        prefixes = self.build_wedding_storage_prefixes(
            folder=folder,
            wedding_slug=wedding_slug,
            planner_scope=planner_scope,
        )
        primary_prefix = prefixes[0]
        fallback_prefix = prefixes[1] if len(prefixes) > 1 else None

        cursor_scope, raw_cursor = self._decode_scoped_cursor(cursor)
        if cursor_scope == "legacy" and fallback_prefix:
            legacy_page = self.list_uploaded_files_page(
                prefix=fallback_prefix,
                limit=limit,
                cursor=raw_cursor,
            )
            legacy_page["next_cursor"] = self._encode_scoped_cursor(
                "legacy", legacy_page.get("next_cursor")
            )
            return legacy_page

        primary_page = self.list_uploaded_files_page(
            prefix=primary_prefix,
            limit=limit,
            cursor=raw_cursor,
        )
        primary_page["next_cursor"] = self._encode_scoped_cursor(
            "primary", primary_page.get("next_cursor")
        )

        if primary_page["has_more"] or not fallback_prefix:
            return primary_page

        seen = {
            self.build_legacy_storage_identity(item["key"]) or item["key"]
            for item in primary_page["items"]
        }
        combined_items = list(primary_page["items"])
        legacy_cursor = None
        legacy_has_more = False

        while len(combined_items) < limit and fallback_prefix:
            legacy_page = self.list_uploaded_files_page(
                prefix=fallback_prefix,
                limit=max(1, limit - len(combined_items)),
                cursor=legacy_cursor,
            )

            for item in legacy_page["items"]:
                identity = (
                    self.build_legacy_storage_identity(item["key"]) or item["key"]
                )
                if identity in seen:
                    continue
                seen.add(identity)
                combined_items.append(item)
                if len(combined_items) >= limit:
                    break

            legacy_cursor = legacy_page.get("next_cursor")
            legacy_has_more = legacy_page.get("has_more", False)
            if not legacy_has_more:
                break

        return {
            "items": combined_items,
            "next_cursor": (
                self._encode_scoped_cursor("legacy", legacy_cursor)
                if legacy_has_more
                else None
            ),
            "has_more": legacy_has_more,
        }

    def generate_qr_code(self, url: str):
        try:
            parsed_url = urlparse(url)
            if parsed_url.scheme.lower() not in ("http", "https"):
                raise HTTPException(status_code=400, detail="Invalid URL scheme")

            allowed_domains = self.storage.allowed_public_hosts(StorageTarget.PRIMARY)
            if self.frontend_url:
                frontend_host = urlparse(self.frontend_url).netloc
                if frontend_host and frontend_host not in allowed_domains:
                    allowed_domains.append(frontend_host)

            if not parsed_url.netloc or parsed_url.netloc not in allowed_domains:
                raise HTTPException(status_code=400, detail="Invalid URL domain")

            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)
            return StreamingResponse(buffer, media_type="image/png")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Error generating QR code: {str(exc)}"
            )

    def upload_file_direct(
        self,
        file: UploadFile,
        wedding_slug: str,
        folder: str = "gallery",
        planner_scope: Optional[str] = None,
    ):
        try:
            if file.content_type not in ALLOWED_GALLERY_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File type '{file.content_type}' not allowed. Allowed types: "
                        f"{', '.join(sorted(ALLOWED_GALLERY_TYPES))}"
                    ),
                )

            key = self.build_wedding_storage_key(
                folder=folder,
                wedding_slug=wedding_slug,
                filename=str(file.filename),
                planner_scope=planner_scope,
            )

            self.storage.upload_fileobj(file.file, StorageTarget.PRIMARY, key)
            return {"message": "File uploaded successfully", "key": key}
        except HTTPException:
            raise
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading file ({error_code}): {str(exc)}",
            )
