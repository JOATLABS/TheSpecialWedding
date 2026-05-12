"""Storage and validation for FILE_UPLOAD form-field attachments.

Public form respondents who hit a per-recipient link with a FILE_UPLOAD
field upload through the dedicated S3 bucket
(``StorageTarget.FORM_UPLOADS``) so a public form can never write into
the planner's primary media surfaces. Each upload is verified against
the same ``(distribution_id, access_token)`` pair used by the
submission flow — anonymous uploads are not allowed.

The submit_form_response path validates that any FILE_UPLOAD field value
refers to an upload row scoped to that form + distribution before
persisting the response, so a forged file_id in the submission body
cannot smuggle in a file from another form / another guest's session.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.core.database import mongo
from app.services.media_storage import MediaStorage, StorageTarget

logger = logging.getLogger(__name__)


# 10 MB cap mirrors the average wedding-vendor PDF / scanned-doc size and
# keeps memory pressure on the API process bounded.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Per-distribution aggregate upload cap. Stops a single recipient from
# DoS'ing the bucket by hammering the 10 MB-per-file limit thirty times
# an hour. 50 MB total comfortably accommodates legitimate vendor doc
# packets while bounding worst-case abuse.
MAX_UPLOAD_BYTES_PER_DISTRIBUTION = 50 * 1024 * 1024

# Hard cap on the number of upload rows per distribution so a recipient
# can't flood the form_uploads collection with 1KB files.
MAX_UPLOADS_PER_DISTRIBUTION = 25

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        # Images
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
        "image/heif",
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
    }
)


_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: Optional[str]) -> str:
    """Reduce arbitrary uploaded filenames to a safe S3-key suffix.

    Strips path separators and unusual characters, caps the length, and
    falls back to ``upload`` when the input is empty or all-stripped.
    """
    if not filename:
        return "upload"
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = _FILENAME_SANITIZE_RE.sub("_", base).strip("._")
    if not cleaned:
        cleaned = "upload"
    if len(cleaned) > 100:
        # Preserve extension if possible.
        head, _, ext = cleaned.rpartition(".")
        if ext and len(ext) <= 8:
            head = head[: 100 - len(ext) - 1] or "upload"
            cleaned = f"{head}.{ext}"
        else:
            cleaned = cleaned[:100]
    return cleaned


class FormUploadService:
    def __init__(self, storage: Optional[MediaStorage] = None) -> None:
        self.uploads_collection = mongo.db["form_uploads"]
        self._storage = storage

    @property
    def storage(self) -> MediaStorage:
        # Lazy-init so test harnesses that monkeypatch ``MediaStorage`` can
        # do so before the service touches it.
        if self._storage is None:
            self._storage = MediaStorage()
        return self._storage

    @staticmethod
    def _validate_field_is_file_upload(form: Dict[str, Any], field_id: str) -> None:
        for field in form.get("fields", []):
            if field.get("id") == field_id:
                if field.get("type") != "file_upload":
                    raise HTTPException(
                        status_code=400,
                        detail="Target field does not accept uploads",
                    )
                return
        raise HTTPException(status_code=400, detail="Unknown field")

    async def store_upload(
        self,
        *,
        form: Dict[str, Any],
        distribution: Dict[str, Any],
        field_id: str,
        filename: Optional[str],
        content_type: Optional[str],
        contents: bytes,
    ) -> Dict[str, Any]:
        """Persist an uploaded file to the form-uploads bucket and Mongo.

        Caller is responsible for verifying (form_id, distribution_id,
        access_token) before invoking — this method enforces only the
        size/MIME/field-type contract and writes the artifact.
        """
        self._validate_field_is_file_upload(form, field_id)

        if content_type is None or content_type.lower() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Unsupported file type for upload",
            )
        if not contents:
            raise HTTPException(status_code=400, detail="Empty upload")
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."),
            )

        # Per-distribution aggregate quota. Counted from existing
        # form_uploads rows for this distribution; rejecting up-front
        # avoids partial writes (we'd otherwise put_object into S3 and
        # discover the quota miss only after spending bandwidth).
        existing = await self.uploads_collection.find(
            {"form_id": form["_id"], "distribution_id": distribution["_id"]}
        ).to_list(length=MAX_UPLOADS_PER_DISTRIBUTION + 1)
        if len(existing) >= MAX_UPLOADS_PER_DISTRIBUTION:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Upload limit reached "
                    f"({MAX_UPLOADS_PER_DISTRIBUTION} files per recipient)."
                ),
            )
        existing_bytes = sum(int(row.get("size_bytes") or 0) for row in existing)
        if existing_bytes + len(contents) > MAX_UPLOAD_BYTES_PER_DISTRIBUTION:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Upload would exceed per-recipient quota "
                    f"({MAX_UPLOAD_BYTES_PER_DISTRIBUTION // (1024 * 1024)} MB total)."
                ),
            )

        # MediaStorage.require_target raises RuntimeError when the
        # target health is not ready (no bucket, missing creds, etc).
        # Translate that into the documented 503 so the public upload
        # endpoint surfaces a clean "uploads are not configured" path
        # instead of bubbling a generic 500.
        try:
            target = self.storage.require_target(StorageTarget.FORM_UPLOADS)
        except RuntimeError as exc:
            logger.warning("Form uploads target not ready: %s", exc)
            raise HTTPException(
                status_code=503, detail="Form uploads are not configured"
            ) from exc
        if not target.bucket_name:
            raise HTTPException(
                status_code=503, detail="Form uploads are not configured"
            )

        safe_filename = sanitize_filename(filename)
        file_id = str(uuid.uuid4())
        key = f"forms/{form['_id']}/{distribution['_id']}/{file_id}-{safe_filename}"

        try:
            self.storage.client.put_object(
                Bucket=target.bucket_name,
                Key=key,
                Body=contents,
                ContentType=content_type,
                Metadata={
                    "form_id": str(form["_id"]),
                    "distribution_id": str(distribution["_id"]),
                    "field_id": field_id,
                },
            )
        except Exception as exc:  # pragma: no cover - boto error surface
            logger.error(
                "Failed to upload form attachment for form=%s dist=%s: %s",
                form.get("_id"),
                distribution.get("_id"),
                exc,
            )
            raise HTTPException(status_code=502, detail="Upload failed")

        public_url = self.storage.build_public_url(StorageTarget.FORM_UPLOADS, key)

        record = {
            "_id": file_id,
            "form_id": form["_id"],
            "distribution_id": distribution["_id"],
            "field_id": field_id,
            "filename": safe_filename,
            "original_filename": filename,
            "content_type": content_type,
            "size_bytes": len(contents),
            "s3_bucket": target.bucket_name,
            "s3_key": key,
            "url": public_url,
            "uploaded_at": datetime.now(timezone.utc),
        }
        await self.uploads_collection.insert_one(record)

        return {
            "file_id": file_id,
            "url": public_url,
            "filename": safe_filename,
            "content_type": content_type,
            "size_bytes": len(contents),
            "field_id": field_id,
        }

    async def get_upload_for_form_distribution(
        self,
        *,
        file_id: str,
        form_id: str,
        distribution_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the upload row iff it exists AND is scoped to the form+distribution.

        Used by submit_form_response to verify that any FILE_UPLOAD value
        in the submission body legitimately came from this respondent's
        own upload session.
        """
        if not (file_id and form_id and distribution_id):
            return None
        return await self.uploads_collection.find_one(
            {
                "_id": file_id,
                "form_id": form_id,
                "distribution_id": distribution_id,
            }
        )


__all__ = [
    "ALLOWED_MIME_TYPES",
    "FormUploadService",
    "MAX_UPLOAD_BYTES",
    "MAX_UPLOAD_BYTES_PER_DISTRIBUTION",
    "MAX_UPLOADS_PER_DISTRIBUTION",
    "sanitize_filename",
]
