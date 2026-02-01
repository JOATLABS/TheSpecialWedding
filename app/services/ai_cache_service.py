"""
AI Cache Service

Content-addressed caching for AI responses with TTL support.
Reduces costs by avoiding redundant AI calls for identical inputs.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import json
import logging
from app.core.database import mongo

logger = logging.getLogger(__name__)


class AICacheService:
    """
    Manages AI response caching with smart invalidation.
    Uses MongoDB for persistence with TTL index support.
    """

    def __init__(self):
        self.cache = mongo.db["ai_cache"]

    def _generate_cache_key(self, feature: str, tenant_id: str, context: Dict) -> str:
        """Generate content-addressed cache key from input data."""
        # Create stable hash from context
        context_str = json.dumps(context, sort_keys=True, default=str)
        context_hash = hashlib.sha256(context_str.encode()).hexdigest()[:16]
        return f"ai:{feature}:{tenant_id}:{context_hash}"

    async def get_cached_response(
        self,
        feature: str,
        tenant_id: str,
        context: Dict
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
            cache_key = self._generate_cache_key(feature, tenant_id, context)

            cached = await self.cache.find_one({
                "_id": cache_key,
                "expires_at": {"$gt": datetime.utcnow()}
            })

            if cached:
                # Increment hit count for analytics
                await self.cache.update_one(
                    {"_id": cache_key},
                    {"$inc": {"hit_count": 1}}
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
        ttl_hours: int
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
            cache_key = self._generate_cache_key(feature, tenant_id, context)

            cache_entry = {
                "_id": cache_key,
                "feature": feature,
                "tenant_id": tenant_id,
                "context_hash": hashlib.sha256(
                    json.dumps(context, sort_keys=True, default=str).encode()
                ).hexdigest(),
                "response": response,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(hours=ttl_hours),
                "hit_count": 0
            }

            await self.cache.replace_one(
                {"_id": cache_key},
                cache_entry,
                upsert=True
            )

            logger.debug(f"Cached response for {feature}/{tenant_id} (TTL: {ttl_hours}h)")
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
            result = await self.cache.delete_many({
                "feature": feature,
                "tenant_id": tenant_id
            })

            if result.deleted_count > 0:
                logger.info(f"Invalidated {result.deleted_count} cache entries for {feature}/{tenant_id}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    async def invalidate_by_features(self, features: list[str], tenant_id: str) -> int:
        """
        Invalidate cache entries for multiple features for a tenant in one query.

        Args:
            features: List of feature names to invalidate
            tenant_id: Tenant ID

        Returns:
            Number of entries deleted
        """
        try:
            result = await self.cache.delete_many({
                "feature": {"$in": features},
                "tenant_id": tenant_id
            })

            if result.deleted_count > 0:
                logger.info(f"Invalidated {result.deleted_count} cache entries for features {features}/{tenant_id}")
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
                logger.info(f"Invalidated all {result.deleted_count} cache entries for tenant {tenant_id}")
            return result.deleted_count

        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        Note: MongoDB TTL index handles this automatically, but this can be
        called for immediate cleanup if needed.

        Returns:
            Number of entries deleted
        """
        try:
            result = await self.cache.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })

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
                        "total_hits": {"$sum": "$hit_count"}
                    }
                }
            ]

            stats = await self.cache.aggregate(pipeline).to_list(length=None)

            return {
                "by_feature": {s["_id"]: {"count": s["count"], "hits": s["total_hits"]} for s in stats},
                "total_entries": sum(s["count"] for s in stats),
                "total_hits": sum(s["total_hits"] for s in stats)
            }

        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}


# Singleton instance
ai_cache_service = AICacheService()
