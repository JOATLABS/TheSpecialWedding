#!/usr/bin/env python3
"""
One-Time Migration: Move Existing Blog + KB Images Onto Our R2/CDN
==================================================================

Scans `blog_articles` and `kb_articles` for `og_image` / `card_image`
fields that point at an external host (anything NOT under our
BLOG_MEDIA_DOMAIN). For each such image, downloads via
BlogUploadService.upload_from_url and rewrites the field to the R2
cdn_url.

Rationale
---------
Today: admin-authored articles go through the presigned-PUT path so
images land on R2 from the start. BabyLoveGrowth-synced articles go
through upload_from_url. But any article whose `og_image` was pasted
in by hand, copied from a Figma export, or seeded from a legacy
CMS, may still point at a third-party host. Those break two ways:

  1. If the host goes down or rotates URLs, our blog cards 404.
  2. Third-party CDNs are credit-card-revealing surfaces; the
     image's HTTP referer leaks the visitor's IP to that vendor.

This driver eliminates both classes by hauling every image into our
own bucket.

Idempotency
-----------
Already-on-R2 URLs are recognised by host-match against
BLOG_MEDIA_DOMAIN and skipped. Re-running this driver does nothing
once everything is migrated.

Strategy
--------
SCAN PHASE (read-only):
    - Iterate blog_articles + kb_articles
    - Classify each (og_image, card_image) pair: null / on-r2 /
      external / bad-url
    - Print a count summary; ENTER-gate before mutating

MIGRATE PHASE:
    - For each external URL, call upload_from_url
    - On success: $set the field to the new R2 cdn_url
    - On failure: log + skip (diagnostic-first — surface the exact
      BlogUploadFromUrlError reason so we can see what the host is
      serving)

VERIFY:
    - Print final summary: counts of migrated / skipped / failed
    - Idempotency hint: re-run should show zero migrated, all
      already-r2

This file uses the harness pattern from
testbed/_form_lifecycle_common.py: imports lazy, no banner-less
output, ENTER-gates between phases, BLG_NO_INPUT=1 for CI.

No paired cleanup script — this driver is non-destructive; it only
updates field values to the R2 equivalent.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from testbed._blg_sync_common import (  # noqa: E402
    banner,
    checkpoint_pause,
    get_async_mongo,
    now_utc,
)


COLLECTIONS = ["blog_articles", "kb_articles"]
IMAGE_FIELDS = ["og_image", "card_image"]


def _classify(url: Optional[str], r2_host: Optional[str]) -> str:
    """Sort an image-field value into one of four buckets."""
    if not url:
        return "null"
    try:
        parsed = urlparse(url)
    except Exception:
        return "bad-url"
    if not parsed.scheme or not parsed.netloc:
        # Relative or malformed — treat as bad-url so the operator
        # sees it instead of silently leaving in place.
        return "bad-url"
    if r2_host and parsed.netloc == r2_host:
        return "already-r2"
    return "external"


async def _scan(r2_host: Optional[str]) -> dict[str, Any]:
    """Read-only pass: count what we'd touch, group by collection."""
    mongo = get_async_mongo()
    report: dict[str, Any] = {}
    targets: list[dict] = []
    for coll_name in COLLECTIONS:
        coll = mongo.db[coll_name]
        breakdown = {"null": 0, "already-r2": 0, "external": 0, "bad-url": 0}
        cursor = coll.find(
            {},
            {"_id": 1, "slug": 1, "title": 1, "og_image": 1, "card_image": 1},
        )
        async for doc in cursor:
            external_fields = []
            for field in IMAGE_FIELDS:
                bucket = _classify(doc.get(field), r2_host)
                breakdown[bucket] += 1
                if bucket == "external":
                    external_fields.append(field)
            if external_fields:
                targets.append(
                    {
                        "collection": coll_name,
                        "_id": doc["_id"],
                        "slug": doc.get("slug"),
                        "title": doc.get("title"),
                        "fields": external_fields,
                        "values": {f: doc.get(f) for f in external_fields},
                    }
                )
        report[coll_name] = breakdown
    return {"counts": report, "targets": targets}


async def _migrate(targets: list[dict]) -> dict[str, Any]:
    """Mutate phase: download each external URL → R2; update the field."""
    from app.services.blog_upload_service import (
        BlogUploadFromUrlError,
        BlogUploadService,
    )

    mongo = get_async_mongo()
    upload = BlogUploadService()

    migrated = 0
    failed = 0
    results: list[dict] = []

    for target in targets:
        coll = mongo.db[target["collection"]]
        per_field_updates: dict[str, str] = {}
        per_field_errors: dict[str, str] = {}

        for field in target["fields"]:
            remote_url = target["values"][field]
            try:
                push = await upload.upload_from_url(
                    remote_url,
                    folder=f"migrated/{target['collection']}/{target['_id']}",
                )
                per_field_updates[field] = push["cdn_url"]
            except BlogUploadFromUrlError as exc:
                per_field_errors[field] = str(exc)

        if per_field_updates:
            await coll.update_one(
                {"_id": target["_id"]},
                {
                    "$set": {
                        **per_field_updates,
                        "updated_at": now_utc(),
                    }
                },
            )
            migrated += 1
        if per_field_errors:
            failed += 1

        results.append(
            {
                "collection": target["collection"],
                "slug": target["slug"],
                "title": target["title"],
                "migrated_fields": list(per_field_updates.keys()),
                "errors": per_field_errors,
            }
        )

    return {"migrated": migrated, "failed": failed, "results": results}


async def main() -> None:
    banner("migrate_existing_images_to_r2")

    from app.core.settings import settings

    r2_domain = settings.normalized_blog_media_domain
    r2_host = None
    if r2_domain:
        r2_host = urlparse(r2_domain).netloc or r2_domain
    print(f"  BLOG_MEDIA_DOMAIN: {r2_domain or '<UNSET>'}")
    print(f"  R2 host for match: {r2_host or '<UNSET>'}")
    print()

    if not r2_host:
        print("  ⚠  BLOG_MEDIA_DOMAIN is unset. Cannot distinguish R2 URLs")
        print("     from external URLs — aborting before any mutation.")
        print("     Set S3_BLOG_BUCKET_NAME + BLOG_MEDIA_DOMAIN in .env first.")
        return

    print("  SCAN")
    scan = await _scan(r2_host)
    for coll_name, breakdown in scan["counts"].items():
        print(f"    • {coll_name}:")
        for bucket, count in breakdown.items():
            print(f"        {bucket}: {count}")

    targets = scan["targets"]
    if not targets:
        print()
        print("  ✅ Nothing to migrate. All image fields are null or already on R2.")
        return

    print()
    print(f"  Found {len(targets)} article(s) with external image URLs.")
    print("  Preview (first 10):")
    for target in targets[:10]:
        for field in target["fields"]:
            print(
                f"    • [{target['collection']}] {target['slug']!r}: "
                f"{field} = {target['values'][field]}"
            )

    checkpoint_pause(
        "Confirm migration",
        [
            f"About to download {sum(len(t['fields']) for t in targets)} image(s)",
            f"From {len(targets)} article(s) across {len(COLLECTIONS)} collections",
            "Each will be re-hosted under r2://<bucket>/migrated/<collection>/<_id>/",
            "Existing blog_articles + kb_articles docs will be updated in place",
            "Press ENTER to proceed; Ctrl-C to abort",
        ],
    )

    print()
    print("  MIGRATE")
    result = await _migrate(targets)
    print(f"    • articles migrated: {result['migrated']}")
    print(f"    • articles with errors: {result['failed']}")

    failures = [r for r in result["results"] if r["errors"]]
    if failures:
        print()
        print("  ⚠  Per-article errors:")
        for entry in failures:
            print(f"    • [{entry['collection']}] {entry['slug']!r}")
            for field, err in entry["errors"].items():
                print(f"        {field}: {err}")

    print()
    print("  ✅ Migration pass complete.")
    print(
        "  Re-run this driver to confirm idempotency — second pass should "
        "show zero migrations and zero external URLs in the scan."
    )


if __name__ == "__main__":
    asyncio.run(main())
