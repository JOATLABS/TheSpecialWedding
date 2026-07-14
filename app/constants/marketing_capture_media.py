"""Approved repository media used only by isolated local product demos."""

from __future__ import annotations

import os
from typing import Any

from app.constants.seed_sources import (
    is_exact_marketing_capture_seed,
)

NON_PRODUCTION_ENVIRONMENTS = {
    "development",
    "dev",
    "local",
    "test",
    "testing",
    "ci",
}

MARKETING_CAPTURE_GALLERY_ITEMS = [
    {
        "key": "gallery/sofia-and-daniel/20270125-terrace-portrait.webp",
        "url": "/demo-gallery/sofia-daniel-terrace.webp",
        "content_type": "image/webp",
        "display_name": "Garden terrace portrait",
        "alt": "Fictional newlyweds on the glasshouse garden terrace",
        "credit": "Fictional capture fixture generated for The Special Wedding",
    },
    {
        "key": "gallery/sofia-and-daniel/20270125-ceremony-aisle.webp",
        "url": "/demo-gallery/sofia-daniel-ceremony.webp",
        "content_type": "image/webp",
        "display_name": "Glasshouse ceremony aisle",
        "alt": "Fictional garden ceremony aisle at the glasshouse",
        "credit": "Fictional capture fixture generated for The Special Wedding",
    },
    {
        "key": "gallery/sofia-and-daniel/20270125-reception-table.webp",
        "url": "/demo-gallery/sofia-daniel-reception.webp",
        "content_type": "image/webp",
        "display_name": "Candlelit reception table",
        "alt": "Fictional candlelit reception table inside the glasshouse",
        "credit": "Fictional capture fixture generated for The Special Wedding",
    },
]

MARKETING_CAPTURE_GALLERY_URLS = frozenset(
    item["url"] for item in MARKETING_CAPTURE_GALLERY_ITEMS
)


def allow_local_demo_gallery_fallback(wedding: Any) -> bool:
    environment = (
        os.getenv("ENVIRONMENT", os.getenv("NODE_ENV", "development")).strip().lower()
    )
    return (
        environment in NON_PRODUCTION_ENVIRONMENTS
        and isinstance(wedding, dict)
        and is_exact_marketing_capture_seed(
            wedding.get("seed_source"),
            wedding.get("seed_scope"),
        )
    )


def gallery_fallback_items_for_wedding(wedding: Any) -> list[dict[str, str]]:
    if isinstance(wedding, dict) and is_exact_marketing_capture_seed(
        wedding.get("seed_source"),
        wedding.get("seed_scope"),
    ):
        return [dict(item) for item in MARKETING_CAPTURE_GALLERY_ITEMS]
    return []
