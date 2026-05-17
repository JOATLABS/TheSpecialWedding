import asyncio
import io
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.services.media_storage import MediaStorage, StorageTarget

logger = logging.getLogger(__name__)

ALLOWED_BLOG_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_BLOG_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

_CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class BlogUploadFromUrlError(Exception):
    """Raised when a server-side image ingestion cannot be completed.

    Distinct from FastAPI's HTTPException because callers of
    BlogUploadService.upload_from_url are services (not route
    handlers); they decide whether to log + continue, count toward a
    failure threshold, or surface to the user. Translating to
    HTTPException at this layer would force a route-handler-shaped
    error contract on every consumer.
    """


class BlogUploadService:
    """
    Handles file uploads for blog and knowledge-base images in the dedicated blog bucket.
    """

    def __init__(self):
        self.storage = MediaStorage()
        self.bucket_name = self.storage.target(StorageTarget.BLOG_ASSETS).bucket_name

    def build_public_url(self, key: str) -> str:
        return self.storage.build_public_url(StorageTarget.BLOG_ASSETS, key)

    def create_presigned_upload_url(
        self,
        filename: str,
        folder: str = "blog",
        content_type: str = "image/jpeg",
        expires_in: int = 300,
    ) -> dict:
        if content_type not in ALLOWED_BLOG_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File type '{content_type}' not allowed. "
                    f"Allowed: {', '.join(sorted(ALLOWED_BLOG_IMAGE_TYPES))}"
                ),
            )

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_filename = os.path.basename(filename)
            key = f"{folder}/{timestamp}_{safe_filename}"
            url = self.storage.generate_presigned_put_url(
                StorageTarget.BLOG_ASSETS,
                key=key,
                expires_in=expires_in,
                content_type=content_type,
            )
            return {
                "upload_url": url,
                "key": key,
                "cdn_url": self.build_public_url(key),
            }
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            raise HTTPException(
                status_code=500, detail=f"Error creating blog upload URL: {str(exc)}"
            )

    def delete_blog_file(self, key: str):
        try:
            self.storage.delete_object(StorageTarget.BLOG_ASSETS, key)
            return {"message": "Blog file deleted successfully"}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting blog file ({error_code}): {str(exc)}",
            )

    async def upload_from_url(
        self,
        remote_url: str,
        folder: str = "blog/synced",
        *,
        max_bytes: int = MAX_BLOG_IMAGE_SIZE_BYTES,
        timeout_seconds: float = 15.0,
    ) -> dict:
        """Server-side: stream a remote image into R2 under BLOG_ASSETS.

        Used by the BabyLoveGrowth sync service to re-host hero images
        on our CDN rather than depending on third-party hosts at render
        time. Mirrors the browser-side presigned-PUT flow for the same
        bucket: same allowlist, same 5 MB cap, same key shape.

        Args:
            remote_url: Source image URL (must be reachable from our backend).
            folder: R2 key prefix. Defaults to ``blog/synced``.
            max_bytes: Reject downloads exceeding this size. Defaults to
                ``MAX_BLOG_IMAGE_SIZE_BYTES`` (5 MB).
            timeout_seconds: httpx total request timeout.

        Returns:
            ``{"key": ..., "cdn_url": ...}`` matching
            ``create_presigned_upload_url``'s shape.

        Raises:
            BlogUploadFromUrlError: For any non-recoverable failure
                — non-200 source, content-type not in allowlist,
                oversized body, httpx errors, R2 not configured, R2
                put_object failure.
        """
        content_type, body_bytes = await self._fetch_to_memory(
            remote_url, max_bytes=max_bytes, timeout_seconds=timeout_seconds
        )
        key = self._build_synced_key(folder, remote_url, content_type)

        # boto3 is sync — wrap upload_fileobj in a thread so we don't
        # block the event loop on the R2 PUT. MediaStorage.upload_fileobj
        # internally calls require_target, which raises RuntimeError if
        # BLOG_ASSETS isn't configured (missing S3_BLOG_BUCKET_NAME or
        # credentials health-check failed).
        try:
            await asyncio.to_thread(
                self.storage.upload_fileobj,
                io.BytesIO(body_bytes),
                StorageTarget.BLOG_ASSETS,
                key,
                {"ContentType": content_type},
            )
        except RuntimeError as exc:
            raise BlogUploadFromUrlError(
                f"R2 BLOG_ASSETS not configured: {exc}"
            ) from exc
        except ClientError as exc:
            raise BlogUploadFromUrlError(
                f"R2 put_object failed for {key}: {exc}"
            ) from exc

        return {"key": key, "cdn_url": self.build_public_url(key)}

    async def _fetch_to_memory(
        self,
        remote_url: str,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> tuple[str, bytes]:
        """Stream a URL into memory, enforcing content-type + size caps.

        Two enforcement layers:
          1. ``Content-Type`` response header must match
             ``ALLOWED_BLOG_IMAGE_TYPES``. URL extension is NOT trusted
             (BLG's CDN may serve images without extensions in the URL).
          2. Size cap is checked twice: once against the declared
             ``Content-Length`` header (early reject), and again as a
             running tally while streaming (catches lying or chunked
             responses).
        """
        timeout = httpx.Timeout(timeout_seconds)
        try:
            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True
            ) as client:
                async with client.stream("GET", remote_url) as response:
                    if response.status_code != 200:
                        raise BlogUploadFromUrlError(
                            f"Source returned HTTP {response.status_code} "
                            f"for {remote_url}"
                        )

                    content_type = (
                        (response.headers.get("content-type") or "")
                        .split(";")[0]
                        .strip()
                        .lower()
                    )
                    if content_type not in ALLOWED_BLOG_IMAGE_TYPES:
                        raise BlogUploadFromUrlError(
                            f"Content-type {content_type!r} not in allowlist "
                            f"for {remote_url}"
                        )

                    declared = response.headers.get("content-length")
                    if declared:
                        try:
                            declared_int = int(declared)
                        except ValueError:
                            declared_int = 0
                        if declared_int > max_bytes:
                            raise BlogUploadFromUrlError(
                                f"Declared content-length {declared_int} "
                                f"exceeds cap {max_bytes} for {remote_url}"
                            )

                    buffer = bytearray()
                    async for chunk in response.aiter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > max_bytes:
                            raise BlogUploadFromUrlError(
                                f"Streamed size exceeded cap {max_bytes} "
                                f"for {remote_url}"
                            )

                    return content_type, bytes(buffer)
        except BlogUploadFromUrlError:
            raise
        except httpx.HTTPError as exc:
            raise BlogUploadFromUrlError(
                f"HTTP error fetching {remote_url}: {exc}"
            ) from exc

    @staticmethod
    def _build_synced_key(folder: str, remote_url: str, content_type: str) -> str:
        """Build an R2 object key for a synced image.

        Pattern: ``{folder}/{timestamp}_{safe_basename}``. Timestamp
        ensures uniqueness across reruns (we don't dedupe by content
        hash — caller handles idempotency upstream via babylovegrowth_id).
        Basename is sanitized to ASCII-safe to avoid signed-URL
        encoding surprises. If the URL has no extension, append one
        derived from the content-type.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        extension = _CONTENT_TYPE_TO_EXTENSION.get(content_type, "")
        raw_basename = os.path.basename(remote_url.split("?")[0]) or f"image{extension}"
        safe_basename = re.sub(r"[^A-Za-z0-9._-]", "_", raw_basename)
        if extension and not safe_basename.lower().endswith(extension):
            safe_basename = f"{safe_basename}{extension}"
        return f"{folder}/{timestamp}_{safe_basename}"
