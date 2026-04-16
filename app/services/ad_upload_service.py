import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.services.media_storage import MediaStorage, StorageTarget

ALLOWED_AD_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_AD_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class AdUploadService:
    """
    Handles file uploads for vendor ad creative assets.
    Uses a dedicated ad-assets bucket while sharing the common S3/R2 credentials.
    """

    def __init__(self):
        self.storage = MediaStorage()
        self.bucket_name = self.storage.target(StorageTarget.AD_ASSETS).bucket_name

    def build_public_url(self, key: str) -> str:
        return self.storage.build_public_url(StorageTarget.AD_ASSETS, key)

    def create_presigned_upload_url(
        self, filename: str, vendor_id: str, content_type: str, expires_in: int = 300
    ) -> dict:
        """Generate a presigned PUT URL for ad creative assets."""
        if content_type not in ALLOWED_AD_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File type '{content_type}' not allowed for ad images. "
                    f"Allowed: {', '.join(sorted(ALLOWED_AD_TYPES))}"
                ),
            )

        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_filename = os.path.basename(filename)
            key = f"ads/{vendor_id}/{timestamp}_{safe_filename}"
            url = self.storage.generate_presigned_put_url(
                StorageTarget.AD_ASSETS,
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
                status_code=500, detail=f"Error creating ad upload URL: {str(exc)}"
            )

    def delete_ad_file(self, key: str):
        try:
            self.storage.delete_object(StorageTarget.AD_ASSETS, key)
            return {"message": "Ad file deleted successfully"}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting ad file ({error_code}): {str(exc)}",
            )

    def list_vendor_ad_files(self, vendor_id: str) -> list[dict]:
        try:
            prefix = f"ads/{vendor_id}/"
            response = self.storage.list_objects_page(
                StorageTarget.AD_ASSETS,
                prefix=prefix,
                limit=1000,
            )
            contents = response.get("Contents", [])
            files = [
                {
                    "key": obj["Key"],
                    "url": self.build_public_url(obj["Key"]),
                    "size": obj.get("Size", 0),
                }
                for obj in contents
            ]
            return sorted(files, key=lambda item: item["key"], reverse=True)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error listing ad files ({error_code}): {str(exc)}",
            )
