"""
AI Cache Service

Content-addressed caching for AI responses with TTL support.
Reduces costs by avoiding redundant AI calls for identical inputs.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.database import mongo

logger = logging.getLogger(__name__)


class AICacheService:
    """
    Manages AI response caching with smart invalidation.
    Uses MongoDB for persistence with TTL index support.

    Cache keys are discriminated by ``subscription_plan`` so a free-plan
    user cannot read a paid-tier user's cached output for the same
    wedding. The plan label is bucketed (e.g. ``free`` / ``trial`` /
    ``active`` / ``metered``) — not per-user — so legitimate sharing
    across team members on the same plan still yields cache hits.
    """

    # Sentinel used when the caller can't resolve a plan; callers should
    # avoid this in production but it's safer than a hard failure for
    # internal scripts and root-admin tooling.
    UNKNOWN_PLAN = "unknown"

    def __init__(self):
        self.cache = mongo.db["ai_cache"]

    @staticmethod
    def _normalize_plan(plan: Optional[str]) -> str:
        if not plan:
            return AICacheService.UNKNOWN_PLAN
        normalized = plan.strip().lower()
        return normalized or AICacheService.UNKNOWN_PLAN

    def _generate_cache_key(
        self,
        feature: str,
        tenant_id: str,
        context: Dict,
        *,
        subscription_plan: Optional[str] = None,
    ) -> str:
        """Generate content-addressed cache key from input data.

        ``subscription_plan`` is mixed into the key so a downgrade does
        not let the planner keep reading paid-tier outputs from the
        previous plan, and an upgrade does not let two users on
        different plans accidentally share a tenant-scoped entry.
        """
        plan = self._normalize_plan(subscription_plan)
        context_str = json.dumps(context, sort_keys=True, default=str)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
        return f"ai:{feature}:{tenant_id}:{plan}:{context_hash}"

    async def get_cached_response(
        self,
        feature: str,
        tenant_id: str,
        context: Dict,
        *,
        subscription_plan: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get cached AI response if valid.

        Args:
            feature: AI feature name (e.g., "budget_insights")
            tenant_id: Wedding or Planner ID
            context: Input context data

        Returns:
            Cached response dict or None if not found/expired
        """
        try:
            cache_key = self._generate_cache_key(
                feature, tenant_id, context, subscription_plan=subscription_plan
            )

            cached = await self.cache.find_one(
                {"_id": cache_key, "expires_at": {"$gt": datetime.now(timezone.utc)}}
            )

            if cached:
                # Increment hit count for analytics
                await self.cache.update_one(
                    {"_id": cache_key}, {"$inc": {"hit_count": 1}}
                )
                logger.debug(f"Cache hit for {feature}/{tenant_id}")
                return cached

            return None

        except Exception as e:
            logger.error(f"Cache get error: {str(e)}")
            return None

    async def cache_response(
        self,
        feature: str,
        tenant_id: str,
        context: Dict,
        response: Dict,
        ttl_hours: int,
        *,
        subscription_plan: Optional[str] = None,
    ) -> bool:
        """
        Cache AI response with TTL.

        Args:
            feature: AI feature name
            tenant_id: Wedding or Planner ID
            context: Input context data (used for cache key)
            response: AI response to cache
            ttl_hours: Time-to-live in hours

        Returns:
            True if cached successfully
        """
        try:
            plan = self._normalize_plan(subscription_plan)
            cache_key = self._generate_cache_key(
                feature, tenant_id, context, subscription_plan=plan
            )

            cache_entry = {
                "_id": cache_key,
                "feature": feature,
                "tenant_id": tenant_id,
                "subscription_plan": plan,
                "context_hash": hashlib.sha256(
                    json.dumps(context, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "response": response,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
                "hit_count": 0,
            }

            await self.cache.replace_one({"_id": cache_key}, cache_entry, upsert=True)

            logger.debug(
                f"Cached response for {feature}/{tenant_id} (TTL: {ttl_hours}h)"
            )
            return True

        except Exception as e:
            logger.error(f"Cache set error: {str(e)}")
            return False

    async def invalidate_by_feature(self, feature: str, tenant_id: str) -> int:
        """
        Invalidate all cache entries for a feature and tenant.
        Called when source data changes (e.g., budget updated).

        Returns:
            Number of entries deleted
        """
        try:
            result = await self.cache.delete_many(
                {"feature": feature, "tenant_id": tenant_id}
            )

            if result.deleted_count > 0:
                logger.info(
                    f"Invalidated {result.deleted_count} cache entries for {feature}/{tenant_id}"
                )
            return result.deleted_count

        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    async def invalidate_by_tenant(self, tenant_id: str) -> int:
        """
        Invalidate all cache entries for a tenant.
        Use sparingly - this is the "nuclear option".

        Returns:
            Number of entries deleted
        """
        try:
            result = await self.cache.delete_many({"tenant_id": tenant_id})

            if result.deleted_count > 0:
                logger.info(
                    f"Invalidated all {result.deleted_count} cache entries for tenant {tenant_id}"
                )
            return result.deleted_count

        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    async def get_latest_cached_response(
        self,
        feature: str,
        tenant_id: str,
        *,
        subscription_plan: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get the most recent cached response for a feature+tenant regardless of context hash.

        This is used as a fallback when a fresh AI call fails — we return the most recent
        cached response rather than showing an error. This provides a much better UX since
        slightly stale insights are better than no insights.

        Args:
            feature: AI feature name (e.g., "budget_insights")
            tenant_id: Wedding or Planner ID
            subscription_plan: Optional plan tier. When supplied the lookup
                is plan-scoped so a downgraded caller can't read a paid-
                tier response. When omitted (Codex P2 review fix) the
                gate falls back to tenant_id only — the AI error /
                insufficient-credit code paths in ``AIService.generate_response``
                don't have a resolved plan handy, and a plan-scoped query
                would otherwise miss every entry written under the real
                plan tier and starve the fallback path entirely.

        Returns:
            Most recent cached response dict or None if nothing cached
        """
        try:
            base_query: Dict[str, Any] = {
                "feature": feature,
                "tenant_id": tenant_id,
            }
            plan_label: str
            if subscription_plan is not None:
                # Caller threaded the plan through — keep the scope
                # tight so the fallback can't leak paid-tier cache.
                plan_label = self._normalize_plan(subscription_plan)
                base_query["subscription_plan"] = plan_label
            else:
                plan_label = "any"
            cached = await self.cache.find_one(
                {**base_query, "expires_at": {"$gt": datetime.now(timezone.utc)}},
                sort=[("created_at", -1)],
            )

            if cached:
                logger.debug(
                    f"Fallback cache hit for {feature}/{tenant_id}/{plan_label}"
                )
                return cached

            # Fall back to expired entries (stale insights > no insights),
            # honouring the same plan scope choice as the fresh lookup.
            cached = await self.cache.find_one(base_query, sort=[("created_at", -1)])

            if cached:
                logger.info(
                    f"Returning expired fallback cache for {feature}/{tenant_id}/{plan_label}"
                )
                return cached

            return None

        except Exception as e:
            logger.error(f"Fallback cache get error: {str(e)}")
            return None

    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        Note: MongoDB TTL index handles this automatically, but this can be
        called for immediate cleanup if needed.

        Returns:
            Number of entries deleted
        """
        try:
            result = await self.cache.delete_many(
                {"expires_at": {"$lt": datetime.now(timezone.utc)}}
            )

            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} expired cache entries")
            return result.deleted_count

        except Exception as e:
            logger.error(f"Cache cleanup error: {str(e)}")
            return 0

    async def get_cache_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache statistics
        """
        try:
            query = {}
            if tenant_id:
                query["tenant_id"] = tenant_id

            # Count by feature
            pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": "$feature",
                        "count": {"$sum": 1},
                        "total_hits": {"$sum": "$hit_count"},
                    }
                },
            ]

            stats = await self.cache.aggregate(pipeline).to_list(length=None)

            return {
                "by_feature": {
                    s["_id"]: {"count": s["count"], "hits": s["total_hits"]}
                    for s in stats
                },
                "total_entries": sum(s["count"] for s in stats),
                "total_hits": sum(s["total_hits"] for s in stats),
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}


# Singleton instance
ai_cache_service = AICacheService()
