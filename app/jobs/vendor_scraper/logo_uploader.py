"""
Logo Uploader

Downloads vendor photos from Google Places and uploads them to the
R2 ad-assets bucket (S3_AD_BUCKET_NAME) under the scraped-vendors/ prefix.
Returns the CDN URL to use as logo_url.
"""

import logging
import re
from datetime import datetime, timezone
from io import BytesIO

import httpx

from app.jobs.vendor_scraper.config import R2_LOGO_PREFIX
from app.services.media_storage import MediaStorage, StorageTarget

logger = logging.getLogger(__name__)

_media_storage = MediaStorage()


def _slugify(text: str) -> str:
    """Simple slugify: lowercase, replace non-alnum with hyphens, collapse."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:80]


async def download_and_upload_logo(
    photo_url: str,
    business_name: str,
    city: str | None = None,
    state: str | None = None,
) -> str | None:
    """
    Download an image from photo_url and upload it to R2.

    Returns the public CDN URL, or None on failure.
    Key format: scraped-vendors/{location_slug}/{timestamp}_{business_slug}.jpg
    Uses city when available, falls back to state for the directory slug.
    """
    ad_target = _media_storage.target(StorageTarget.AD_ASSETS)
    if not ad_target.bucket_name:
        logger.warning("S3_AD_BUCKET_NAME not set — skipping logo upload")
        return None
    if not ad_target.public_domain:
        logger.warning("AD_MEDIA_DOMAIN not set — skipping logo upload")
        return None

    try:
        # Download the image
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(photo_url)
            resp.raise_for_status()
            image_bytes = resp.content
            content_type = resp.headers.get("content-type", "image/jpeg")

        # Determine extension from content-type
        ext_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), "jpg")

        # Build R2 key — prefer city, fall back to state
        location = city or state or "unknown"
        location_slug = _slugify(location)
        name_slug = _slugify(business_name)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        key = f"{R2_LOGO_PREFIX}/{location_slug}/{timestamp}_{name_slug}.{ext}"

        # Upload to R2
        _media_storage.upload_fileobj(
            BytesIO(image_bytes),
            StorageTarget.AD_ASSETS,
            key,
            extra_args={"ContentType": content_type},
        )

        cdn_url = _media_storage.build_public_url(StorageTarget.AD_ASSETS, key)
        logger.info(f"Uploaded logo for '{business_name}' → {cdn_url}")
        return cdn_url

    except httpx.HTTPError as e:
        logger.warning(f"Failed to download logo for '{business_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to upload logo for '{business_name}': {e}")
        return None
