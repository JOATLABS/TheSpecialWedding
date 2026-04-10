"""
Logo Uploader

Downloads vendor photos from Google Places and uploads them to the
R2 ad-assets bucket (S3_AD_BUCKET_NAME) under the scraped-vendors/ prefix.
Returns the CDN URL to use as logo_url.
"""

import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO

import boto3
import httpx
from botocore.config import Config as BotoConfig

from app.jobs.vendor_scraper.config import R2_LOGO_PREFIX

logger = logging.getLogger(__name__)

# ─── R2 / S3 config from env (same creds as AdUploadService) ─────────────────
_S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
_S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
_S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
_AD_BUCKET_NAME = os.getenv("S3_AD_BUCKET_NAME")

# Build AD_MEDIA_DOMAIN the same way gallery_upload_service.py does
_raw_ad_media_domain = os.getenv("AD_MEDIA_DOMAIN")
if _raw_ad_media_domain:
    if _raw_ad_media_domain.startswith(("http://", "https://")):
        AD_MEDIA_DOMAIN = _raw_ad_media_domain.rstrip("/")
    else:
        AD_MEDIA_DOMAIN = f"https://{_raw_ad_media_domain}".rstrip("/")
else:
    AD_MEDIA_DOMAIN = None


def _slugify(text: str) -> str:
    """Simple slugify: lowercase, replace non-alnum with hyphens, collapse."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:80]


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_S3_ENDPOINT_URL,
        aws_access_key_id=_S3_ACCESS_KEY_ID,
        aws_secret_access_key=_S3_SECRET_ACCESS_KEY,
        config=BotoConfig(signature_version="s3v4"),
    )


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
    if not _AD_BUCKET_NAME:
        logger.warning("S3_AD_BUCKET_NAME not set — skipping logo upload")
        return None
    if not AD_MEDIA_DOMAIN:
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
        s3 = _get_s3_client()
        s3.upload_fileobj(
            BytesIO(image_bytes),
            _AD_BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": content_type},
        )

        cdn_url = f"{AD_MEDIA_DOMAIN}/{key}"
        logger.info(f"Uploaded logo for '{business_name}' → {cdn_url}")
        return cdn_url

    except httpx.HTTPError as e:
        logger.warning(f"Failed to download logo for '{business_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to upload logo for '{business_name}': {e}")
        return None
