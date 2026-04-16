import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.services.media_storage import MediaStorage, StorageTarget

ALLOWED_BLOG_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_BLOG_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


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
