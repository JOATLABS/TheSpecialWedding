import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, Optional
from urllib.parse import urlparse

import boto3
import qrcode
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# Allowed MIME types for gallery uploads
ALLOWED_GALLERY_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "video/mp4",
    "video/quicktime",
}

# Get MEDIA_DOMAIN from environment - no fallback
_raw_media_domain = os.getenv("MEDIA_DOMAIN")
if not _raw_media_domain:
    logger.warning("MEDIA_DOMAIN environment variable is not set")
    MEDIA_DOMAIN = None
else:
    # Ensure MEDIA_DOMAIN has https:// protocol
    if _raw_media_domain.startswith(("http://", "https://")):
        MEDIA_DOMAIN = _raw_media_domain.rstrip("/")
    else:
        MEDIA_DOMAIN = f"https://{_raw_media_domain}".rstrip("/")


class GalleryUploadService:
    def __init__(self):
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

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
        """Legacy method - creates presigned URL without wedding_slug (deprecated)"""
        try:
            key = f"gallery/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{filename}"
            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return {"upload_url": url, "key": key}
        except ClientError as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating upload URL: {str(e)}"
            )

    def create_presigned_url_with_wedding(
        self,
        filename: str,
        wedding_slug: str,
        folder: str = "gallery",
        expires_in: int = 300,
        planner_scope: Optional[str] = None,
    ):
        """Creates presigned URL with wedding_slug in the key for proper authorization"""
        try:
            key = self.build_wedding_storage_key(
                folder=folder,
                wedding_slug=wedding_slug,
                filename=filename,
                planner_scope=planner_scope,
            )
            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
            return {"upload_url": url, "key": key}
        except ClientError as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating upload URL: {str(e)}"
            )

    def get_file_url(self, key: str):
        try:
            url = self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=3600,
            )
            return {"file_url": url}
        except ClientError as e:
            raise HTTPException(
                status_code=500, detail=f"Error generating file URL: {str(e)}"
            )

    def delete_file(self, key: str):
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return {"message": "File deleted successfully"}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 delete error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting file: {str(e)}"
            )

    def _format_listed_objects(self, objects):
        return [
            {
                "key": obj["Key"],
                "url": f"{MEDIA_DOMAIN}/{obj['Key']}" if MEDIA_DOMAIN else obj["Key"],
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
            request = {
                "Bucket": self.bucket_name,
                "Prefix": prefix,
                "MaxKeys": limit,
            }
            if cursor:
                request["ContinuationToken"] = cursor

            response = self.s3.list_objects_v2(**request)
            contents = response.get("Contents", [])

            return {
                "items": self._format_listed_objects(contents),
                "next_cursor": response.get("NextContinuationToken"),
                "has_more": response.get("IsTruncated", False),
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 list error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error listing files: {str(e)}"
            )

    def list_uploaded_files(self, prefix: str = "gallery/"):
        try:
            files = []
            continuation_token = None

            while True:
                request = {
                    "Bucket": self.bucket_name,
                    "Prefix": prefix,
                    "MaxKeys": 1000,
                }
                if continuation_token:
                    request["ContinuationToken"] = continuation_token

                response = self.s3.list_objects_v2(**request)
                files.extend(self._format_listed_objects(response.get("Contents", [])))

                if not response.get("IsTruncated"):
                    break

                continuation_token = response.get("NextContinuationToken")

            return sorted(files, key=lambda x: x["key"], reverse=True)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 list error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error listing files: {str(e)}"
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
            # Security: Validate scheme and that the URL belongs to our domain
            parsed_url = urlparse(url)
            if parsed_url.scheme.lower() not in ("http", "https"):
                raise HTTPException(status_code=400, detail="Invalid URL scheme")
            allowed_domains = []

            frontend_url = os.getenv("FRONTEND_URL")
            if frontend_url:
                allowed_domains.append(urlparse(frontend_url).netloc)

            if MEDIA_DOMAIN:
                # MEDIA_DOMAIN might contain protocol
                if "://" in MEDIA_DOMAIN:
                    allowed_domains.append(urlparse(MEDIA_DOMAIN).netloc)
                else:
                    allowed_domains.append(MEDIA_DOMAIN)

            # Check if domain is allowed (reject external domains)
            if not parsed_url.netloc or parsed_url.netloc not in allowed_domains:
                raise HTTPException(status_code=400, detail="Invalid URL domain")

            qr = qrcode.make(url)
            buffer = BytesIO()
            qr.save(buffer)
            buffer.seek(0)
            return StreamingResponse(buffer, media_type="image/png")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error generating QR code: {str(e)}"
            )

    def upload_file_direct(
        self,
        file: UploadFile,
        wedding_slug: str,
        folder: str = "gallery",
        planner_scope: Optional[str] = None,
    ):
        try:
            # Validate MIME type
            if file.content_type not in ALLOWED_GALLERY_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file.content_type}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_GALLERY_TYPES))}",
                )

            key = self.build_wedding_storage_key(
                folder=folder,
                wedding_slug=wedding_slug,
                filename=str(file.filename),
                planner_scope=planner_scope,
            )

            self.s3.upload_fileobj(file.file, self.bucket_name, key)
            return {"message": "File uploaded successfully", "key": key}
        except HTTPException:
            raise
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"S3 upload error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error uploading file: {str(e)}"
            )


# =============================================================================
# AD ASSET UPLOAD SERVICE — Separate bucket for vendor ad creative
# =============================================================================

# Allowed MIME types for ad creative uploads (images only, no video)
ALLOWED_AD_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_AD_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Allowed types for blog images (same as ads)
ALLOWED_BLOG_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_BLOG_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Get BLOG_MEDIA_DOMAIN from environment
_raw_blog_media_domain = os.getenv("BLOG_MEDIA_DOMAIN")
if not _raw_blog_media_domain:
    logger.warning(
        "BLOG_MEDIA_DOMAIN environment variable is not set — falling back to AD_MEDIA_DOMAIN for blog assets"
    )
    BLOG_MEDIA_DOMAIN = None  # Will be set after AD_MEDIA_DOMAIN is resolved
else:
    if _raw_blog_media_domain.startswith(("http://", "https://")):
        BLOG_MEDIA_DOMAIN = _raw_blog_media_domain.rstrip("/")
    else:
        BLOG_MEDIA_DOMAIN = f"https://{_raw_blog_media_domain}".rstrip("/")

# Get AD_MEDIA_DOMAIN from environment
_raw_ad_media_domain = os.getenv("AD_MEDIA_DOMAIN")
if not _raw_ad_media_domain:
    logger.warning(
        "AD_MEDIA_DOMAIN environment variable is not set — falling back to MEDIA_DOMAIN for ad assets"
    )
    AD_MEDIA_DOMAIN = MEDIA_DOMAIN
else:
    if _raw_ad_media_domain.startswith(("http://", "https://")):
        AD_MEDIA_DOMAIN = _raw_ad_media_domain.rstrip("/")
    else:
        AD_MEDIA_DOMAIN = f"https://{_raw_ad_media_domain}".rstrip("/")


class AdUploadService:
    """
    Handles file uploads for vendor ad creative assets.
    Uses a separate S3/R2 bucket (S3_AD_BUCKET_NAME) so wedding gallery
    content and ad assets are fully isolated.

    Shares the same R2 credentials (S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY)
    since both buckets live under the same Cloudflare account.
    """

    def __init__(self):
        self.bucket_name = os.getenv("S3_AD_BUCKET_NAME")
        if not self.bucket_name:
            logger.warning("S3_AD_BUCKET_NAME not set — ad uploads will fail")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

    def create_presigned_upload_url(
        self, filename: str, vendor_id: str, content_type: str, expires_in: int = 300
    ) -> dict:
        """
        Generate a presigned PUT URL for the ad assets bucket.
        Key format: ads/{vendor_id}/{timestamp}_{filename}
        Returns: { upload_url, key, cdn_url }
        """
        if content_type not in ALLOWED_AD_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{content_type}' not allowed for ad images. Allowed: {', '.join(sorted(ALLOWED_AD_TYPES))}",
            )

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_filename = os.path.basename(filename)
            key = f"ads/{vendor_id}/{timestamp}_{safe_filename}"

            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )

            cdn_url = f"{AD_MEDIA_DOMAIN}/{key}" if AD_MEDIA_DOMAIN else key

            return {"upload_url": url, "key": key, "cdn_url": cdn_url}
        except ClientError as e:
            logger.error(f"Ad presigned URL error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating ad upload URL: {str(e)}"
            )

    def delete_ad_file(self, key: str):
        """Delete an ad creative file from the ad bucket."""
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return {"message": "Ad file deleted successfully"}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Ad S3 delete error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting ad file: {str(e)}"
            )

    def list_vendor_ad_files(self, vendor_id: str) -> list:
        """List all ad creative files for a specific vendor."""
        try:
            prefix = f"ads/{vendor_id}/"
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            if "Contents" not in response:
                return []

            files = [
                {
                    "key": obj["Key"],
                    "url": (
                        f"{AD_MEDIA_DOMAIN}/{obj['Key']}"
                        if AD_MEDIA_DOMAIN
                        else obj["Key"]
                    ),
                    "size": obj.get("Size", 0),
                }
                for obj in response["Contents"]
            ]
            return sorted(files, key=lambda x: x["key"], reverse=True)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Ad S3 list error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error listing ad files: {str(e)}"
            )


class BlogUploadService:
    """
    Handles file uploads for blog images (card images, og images, inline content images).
    Uses S3_BLOG_BUCKET_NAME — shared R2 credentials, separate bucket.
    Serves via BLOG_MEDIA_DOMAIN.
    """

    def __init__(self):
        self.bucket_name = os.getenv("S3_BLOG_BUCKET_NAME")
        if not self.bucket_name:
            logger.warning("S3_BLOG_BUCKET_NAME not set — blog uploads will fail")
        self.s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
        )

    def _get_cdn_domain(self):
        """Resolve the CDN domain for blog assets."""
        if BLOG_MEDIA_DOMAIN:
            return BLOG_MEDIA_DOMAIN
        if AD_MEDIA_DOMAIN:
            logger.warning(
                "BLOG_MEDIA_DOMAIN not set — falling back to AD_MEDIA_DOMAIN for blog assets"
            )
            return AD_MEDIA_DOMAIN
        if MEDIA_DOMAIN:
            logger.warning(
                "BLOG_MEDIA_DOMAIN not set — falling back to MEDIA_DOMAIN for blog assets"
            )
            return MEDIA_DOMAIN
        logger.warning(
            "No CDN domain configured for blog assets — URLs will use raw keys instead"
        )
        return None

    def create_presigned_upload_url(
        self,
        filename: str,
        folder: str = "blog",
        content_type: str = "image/jpeg",
        expires_in: int = 300,
    ) -> dict:
        """
        Generate a presigned PUT URL for the blog bucket.
        Key format: {folder}/{timestamp}_{filename}
        Returns: { upload_url, key, cdn_url }
        """
        if content_type not in ALLOWED_BLOG_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{content_type}' not allowed. Allowed: {', '.join(sorted(ALLOWED_BLOG_IMAGE_TYPES))}",
            )

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_filename = os.path.basename(filename)
            key = f"{folder}/{timestamp}_{safe_filename}"

            url = self.s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in,
            )

            cdn_domain = self._get_cdn_domain()
            cdn_url = f"{cdn_domain}/{key}" if cdn_domain else key

            return {"upload_url": url, "key": key, "cdn_url": cdn_url}
        except ClientError as e:
            logger.error(f"Blog presigned URL error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating blog upload URL: {str(e)}"
            )

    def delete_blog_file(self, key: str):
        """Delete a blog image from the blog bucket."""
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return {"message": "Blog file deleted successfully"}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Blog S3 delete error ({error_code}): {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting blog file: {str(e)}"
            )
