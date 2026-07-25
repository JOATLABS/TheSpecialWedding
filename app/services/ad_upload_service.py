import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from urllib.parse import unquote, urlparse

from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.services.media_storage import MediaStorage, StorageTarget

ALLOWED_AD_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_AD_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


class VendorMediaAssetKind(str, Enum):
    CREATIVE = "creative"
    VENDOR_LOGO = "vendor_logo"


@dataclass(frozen=True)
class ManagedAdAsset:
    asset_kind: VendorMediaAssetKind
    key: str
    cdn_url: str


class AdUploadService:
    """
    Handles file uploads for vendor ad creative assets.
    Uses a dedicated ad-assets bucket while sharing the common S3/R2 credentials.
    """

    def __init__(self):
        self.storage = MediaStorage()
        self.bucket_name = self.storage.target(StorageTarget.AD_ASSETS).bucket_name

    def _normalize_asset_kind(
        self, asset_kind: VendorMediaAssetKind | str
    ) -> VendorMediaAssetKind:
        return VendorMediaAssetKind(asset_kind)

    def _asset_prefix(
        self, vendor_id: str, asset_kind: VendorMediaAssetKind | str
    ) -> str:
        normalized_kind = self._normalize_asset_kind(asset_kind)
        if normalized_kind == VendorMediaAssetKind.CREATIVE:
            return f"ads/{vendor_id}"
        return f"vendor-profiles/{vendor_id}/logo"

    def build_public_url(self, key: str) -> str:
        return self.storage.build_public_url(StorageTarget.AD_ASSETS, key)

    def resolve_managed_asset(
        self,
        url: str | None,
        vendor_id: str,
        asset_kind: VendorMediaAssetKind | str,
    ) -> ManagedAdAsset | None:
        if not url:
            return None

        candidate = str(url).strip()
        if not candidate:
            return None

        normalized_kind = self._normalize_asset_kind(asset_kind)
        expected_prefix = f"{self._asset_prefix(vendor_id, normalized_kind)}/"
        target_config = self.storage.target(StorageTarget.AD_ASSETS)

        if candidate.startswith(expected_prefix):
            key = candidate
        else:
            parsed = urlparse(candidate)
            if not parsed.path:
                return None

            if parsed.scheme:
                if not target_config.public_domain:
                    return None
                expected_host = urlparse(target_config.public_domain).netloc
                if parsed.netloc != expected_host:
                    return None

            key = unquote(parsed.path.lstrip("/"))

        if not key.startswith(expected_prefix):
            return None

        return ManagedAdAsset(
            asset_kind=normalized_kind,
            key=key,
            cdn_url=self.build_public_url(key),
        )

    def ensure_vendor_asset_url(
        self,
        url: str | None,
        vendor_id: str,
        asset_kind: VendorMediaAssetKind | str,
        *,
        field_name: str,
    ) -> str | None:
        if url is None:
            return None

        asset = self.resolve_managed_asset(url, vendor_id, asset_kind)
        if asset is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{field_name} must reference a vendor-owned uploaded asset for "
                    f"'{self._normalize_asset_kind(asset_kind).value}'."
                ),
            )
        return asset.cdn_url

    def create_presigned_upload_url(
        self,
        filename: str,
        vendor_id: str,
        content_type: str,
        asset_kind: VendorMediaAssetKind | str = VendorMediaAssetKind.CREATIVE,
        expires_in: int = 300,
        replace_url: str | None = None,
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
            normalized_kind = self._normalize_asset_kind(asset_kind)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            safe_filename = os.path.basename(filename)
            key = (
                f"{self._asset_prefix(vendor_id, normalized_kind)}/"
                f"{timestamp}_{safe_filename}"
            )
            url = self.storage.generate_presigned_put_url(
                StorageTarget.AD_ASSETS,
                key=key,
                expires_in=expires_in,
                content_type=content_type,
            )
            payload = {
                "upload_url": url,
                "key": key,
                "cdn_url": self.build_public_url(key),
                "asset_kind": normalized_kind.value,
                "max_size_bytes": MAX_AD_IMAGE_SIZE_BYTES,
                "allowed_content_types": sorted(ALLOWED_AD_TYPES),
            }
            replaced_asset = self.resolve_managed_asset(
                replace_url, vendor_id, normalized_kind
            )
            if replaced_asset:
                payload["replaced_asset"] = {
                    "key": replaced_asset.key,
                    "cdn_url": replaced_asset.cdn_url,
                    "asset_kind": replaced_asset.asset_kind.value,
                }
            return payload
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            raise HTTPException(
                status_code=500, detail=f"Error creating ad upload URL: {exc!s}"
            )

    def delete_asset_url(
        self,
        url: str | None,
        vendor_id: str,
        asset_kind: VendorMediaAssetKind | str,
    ) -> bool:
        asset = self.resolve_managed_asset(url, vendor_id, asset_kind)
        if asset is None:
            return False

        try:
            self.storage.delete_object(StorageTarget.AD_ASSETS, asset.key)
            return True
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")
            raise HTTPException(
                status_code=500,
                detail=f"Error deleting ad file ({error_code}): {exc!s}",
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
                detail=f"Error deleting ad file ({error_code}): {exc!s}",
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
                detail=f"Error listing ad files ({error_code}): {exc!s}",
            )
