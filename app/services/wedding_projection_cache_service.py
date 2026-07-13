"""Best-effort invalidation for the public privacy projection of a wedding."""

from __future__ import annotations

import logging
from typing import Optional

from app.core.cache import CacheKeys, cache
from app.core.database import mongo
from app.utils.planner_ownership import normalize_query_id

logger = logging.getLogger(__name__)


def _normalized_slug(slug: Optional[str]) -> Optional[str]:
    if not isinstance(slug, str):
        return None
    normalized = slug.strip()
    return normalized or None


async def invalidate_wedding_projection_caches(
    wedding_id: str,
    *,
    previous_slug: Optional[str] = None,
) -> None:
    """Clear public privacy data after one durable wedding write.

    Planner and couple aggregate reads deliberately bypass short-lived caches so
    tenant transfers and dashboard writes are immediately consistent. This one
    remaining public projection is deliberately best-effort: a Redis or follow-up
    Mongo failure must not turn a successful wedding mutation into an API error.
    """
    normalized_wedding_id = str(wedding_id).strip()
    if not normalized_wedding_id:
        return

    current_slug: Optional[str] = None
    try:
        wedding = await mongo.db["weddings"].find_one(
            {"_id": normalize_query_id(normalized_wedding_id)},
            {"slug": 1},
        )
        current_slug = _normalized_slug(wedding.get("slug") if wedding else None)
    except Exception as exc:  # pragma: no cover - exercised through behavior test
        logger.warning(
            "Failed to resolve current slug while invalidating wedding %s: %s",
            normalized_wedding_id,
            exc,
        )

    slugs: list[str] = []
    for slug in (_normalized_slug(previous_slug), current_slug):
        if slug and slug not in slugs:
            slugs.append(slug)

    for slug in slugs:
        cache_key = CacheKeys.wedding_privacy_info(slug)
        try:
            await cache.delete(cache_key)
        except Exception as exc:  # pragma: no cover - cache normally fails soft
            logger.warning(
                "Failed to clear wedding projection cache key %s: %s",
                cache_key,
                exc,
            )
