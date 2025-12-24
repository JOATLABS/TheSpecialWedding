"""
AI Service

Centralized AI gateway with credit management, caching, and logging.
Uses Google Gemini 2.0 Flash for all AI generation.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
import logging
from app.core.settings import settings
from app.core.database import mongo
from app.services.ai_cache_service import ai_cache_service
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


# ============================================================================
# AI FEATURE DEFINITIONS
# ============================================================================

AI_FEATURES = {
    "budget_insights": {
        "credits": 3,
        "ttl_hours": 48,
        "cacheable": True,
        "description": "Generate budget insights and recommendations",
        "system_prompt": """You are a wedding budget advisor. Analyze the budget data
and provide 3 specific, actionable insights. Focus on:
1. Categories that are over/under typical amounts for this wedding size
2. Potential savings opportunities
3. Allocation recommendations

Return JSON: {"insights": [{"type": "warning|tip|success", "title": "...", "detail": "..."}]}"""
    },
    "seating_small": {
        "credits": 2,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for small weddings (<=50 guests)",
        "system_prompt": """You are a wedding seating optimizer. Given guests and tables,
create an optimal seating arrangement that:
1. Keeps family groups together
2. Respects "keep apart" constraints
3. Balances table sizes

Return JSON: {"tables": [{"table_id": "...", "guests": ["guest_id", ...]}]}"""
    },
    "seating_medium": {
        "credits": 5,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for medium weddings (51-150 guests)"
    },
    "seating_large": {
        "credits": 10,
        "ttl_hours": 72,
        "cacheable": True,
        "description": "Seating optimization for large weddings (150+ guests)"
    },
    "email_draft": {
        "credits": 1,
        "ttl_hours": 0,
        "cacheable": False,
        "description": "Draft communication emails",
        "system_prompt": """You are a professional wedding planner writing to clients.
Draft a warm, professional message based on the context provided.
Match the tone to the situation (reminder, thank you, follow-up, etc.).
Keep it concise (2-3 short paragraphs max)."""
    },
    "progress_report": {
        "credits": 2,
        "ttl_hours": 6,
        "cacheable": True,
        "description": "Generate wedding progress report",
        "system_prompt": """Generate a wedding progress summary for the couple.
Include:
1. RSVP status (accepted, pending, declined)
2. Budget status (spent vs remaining)
3. Upcoming milestones
4. Action items for the couple

Return a warm, encouraging summary."""
    },
    "package_pricing": {
        "credits": 3,
        "ttl_hours": 24,
        "cacheable": True,
        "description": "Suggest package pricing based on market data",
        "system_prompt": """You are a wedding industry pricing consultant.
Based on the services, location, and market data, suggest:
1. A competitive price range
2. Recommended payment schedule
3. How this compares to market average

Return JSON: {"min_price": X, "max_price": Y, "recommended": Z,
"market_comparison": "above|at|below", "schedule_suggestion": [...]}"""
    }
}


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough AI credits."""
    def __init__(self, message: str, required: int, available: int):
        self.message = message
        self.required = required
        self.available = available
        super().__init__(message)


class AIGenerationError(Exception):
    """Raised when AI generation fails."""
    pass


class AIService:
    """
    Centralized AI service with:
    - Credit validation and deduction
    - Response caching
    - Usage logging
    - Error handling
    """

    def __init__(self):
        self.usage_log = mongo.db["ai_usage_log"]
        self.subscription_service = SubscriptionService()
        self._model = None

        # Initialize Gemini if API key is available
        if settings.ai_enabled:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.ai_api_key)
                self._model = genai.GenerativeModel('gemini-2.0-flash-exp')
                logger.info("Gemini AI initialized successfully with gemini-2.0-flash-exp")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {str(e)}")
        else:
            logger.warning("AI service disabled - GOOGLE_API_KEY or GEMINI_API_KEY not configured")

    def _ensure_initialized(self):
        """Verify AI service is properly configured."""
        if not self._model:
            raise AIGenerationError(
                "AI service not initialized. Check GOOGLE_API_KEY configuration."
            )

    def get_feature_info(self, feature: str) -> Optional[Dict]:
        """Get feature configuration."""
        return AI_FEATURES.get(feature)

    def list_features(self) -> Dict[str, Dict]:
        """List all available AI features with their costs."""
        return {
            name: {
                "credits": config["credits"],
                "description": config["description"],
                "cacheable": config["cacheable"]
            }
            for name, config in AI_FEATURES.items()
        }

    async def check_credits(self, user_id: str, feature: str) -> Dict[str, Any]:
        """
        Check if user has enough AI credits for a feature.

        Returns:
            Dict with allowed status, credits info, and message
        """
        if feature not in AI_FEATURES:
            raise ValueError(f"Unknown AI feature: {feature}")

        credits_needed = AI_FEATURES[feature]["credits"]

        # Use existing subscription service to check limits
        result = await self.subscription_service.check_usage_limits(
            user_id=user_id,
            resource_type="ai_credits",
            requested_amount=credits_needed
        )

        return {
            "allowed": result.get("allowed", False),
            "credits_needed": credits_needed,
            "credits_remaining": result.get("remaining", 0),
            "message": result.get("message", "")
        }

    async def generate(
        self,
        user_id: str,
        tenant_id: str,
        feature: str,
        prompt: str,
        context: Dict[str, Any],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Generate AI response with caching and credit tracking.

        Args:
            user_id: The user's ID for credit tracking
            tenant_id: The wedding or planner ID for cache scoping
            feature: The AI feature being used (e.g., "budget_insights")
            prompt: The prompt to send to the AI
            context: Context data for cache key generation
            force_refresh: Bypass cache if True

        Returns:
            Dict with response, cached status, and credits_used
        """
        self._ensure_initialized()

        if feature not in AI_FEATURES:
            raise ValueError(f"Unknown AI feature: {feature}")

        feature_config = AI_FEATURES[feature]
        start_time = datetime.utcnow()

        # Check cache first if feature is cacheable
        if feature_config["cacheable"] and not force_refresh:
            cached = await ai_cache_service.get_cached_response(
                feature=feature,
                tenant_id=tenant_id,
                context=context
            )
            if cached:
                # Log cache hit (no credits charged)
                await self._log_usage(
                    user_id=user_id,
                    tenant_id=tenant_id,
                    feature=feature,
                    credits_used=0,
                    latency_ms=0,
                    status="cached"
                )
                return {
                    "response": cached["response"],
                    "cached": True,
                    "credits_used": 0
                }

        # Check credits before making API call
        credits_check = await self.check_credits(user_id, feature)
        if not credits_check["allowed"]:
            raise InsufficientCreditsError(
                message=credits_check["message"] or "Insufficient AI credits",
                required=credits_check["credits_needed"],
                available=credits_check["credits_remaining"]
            )

        # Make AI API call
        try:
            response = await self._call_gemini(feature, prompt, context)
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Deduct credits
            await self.subscription_service.increment_usage(
                user_id=user_id,
                resource_type="ai_credits",
                amount=feature_config["credits"]
            )

            # Cache response if cacheable
            if feature_config["cacheable"] and feature_config["ttl_hours"] > 0:
                await ai_cache_service.cache_response(
                    feature=feature,
                    tenant_id=tenant_id,
                    context=context,
                    response=response,
                    ttl_hours=feature_config["ttl_hours"]
                )

            # Log successful usage
            await self._log_usage(
                user_id=user_id,
                tenant_id=tenant_id,
                feature=feature,
                credits_used=feature_config["credits"],
                latency_ms=latency_ms,
                status="success"
            )

            return {
                "response": response,
                "cached": False,
                "credits_used": feature_config["credits"]
            }

        except InsufficientCreditsError:
            raise
        except Exception as e:
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Log error (no credits charged)
            await self._log_usage(
                user_id=user_id,
                tenant_id=tenant_id,
                feature=feature,
                credits_used=0,
                latency_ms=latency_ms,
                status="error",
                error=str(e)
            )

            logger.error(f"AI generation error for {feature}: {str(e)}")
            raise AIGenerationError(f"AI generation failed: {str(e)}")

    async def _call_gemini(
        self,
        feature: str,
        prompt: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the actual Gemini API call."""
        try:
            feature_config = AI_FEATURES.get(feature, {})
            system_prompt = feature_config.get("system_prompt", "")

            # Format context into prompt
            context_str = json.dumps(context, indent=2, default=str)
            full_prompt = f"{system_prompt}\n\nContext:\n{context_str}\n\nRequest:\n{prompt}"

            # Generate response (sync call wrapped for async)
            response = self._model.generate_content(full_prompt)

            # Try to parse as JSON if expected
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # Return as text if not valid JSON
                return {"text": response.text, "raw": True}

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise

    async def _log_usage(
        self,
        user_id: str,
        tenant_id: str,
        feature: str,
        credits_used: int,
        latency_ms: float,
        status: str,
        error: Optional[str] = None
    ):
        """Log AI usage for analytics and auditing."""
        try:
            log_entry = {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "feature": feature,
                "credits_used": credits_used,
                "latency_ms": latency_ms,
                "status": status,
                "error": error,
                "created_at": datetime.utcnow()
            }
            await self.usage_log.insert_one(log_entry)
        except Exception as e:
            logger.error(f"Failed to log AI usage: {str(e)}")

    async def get_usage_metrics(
        self,
        period_days: int = 7,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get AI usage metrics for admin dashboard.

        Args:
            period_days: Number of days to look back
            tenant_id: Optional tenant filter

        Returns:
            Dict with usage metrics and breakdowns
        """
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=period_days)

        query = {"created_at": {"$gte": start_date}}
        if tenant_id:
            query["tenant_id"] = tenant_id

        # Aggregate daily usage
        daily_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "feature": "$feature"
                    },
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1},
                    "cached_requests": {
                        "$sum": {"$cond": [{"$eq": ["$status", "cached"]}, 1, 0]}
                    },
                    "avg_latency": {"$avg": "$latency_ms"}
                }
            },
            {"$sort": {"_id.date": -1}}
        ]

        daily_usage = await self.usage_log.aggregate(daily_pipeline).to_list(length=None)

        # Top users by credits
        user_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$tenant_id",
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1}
                }
            },
            {"$sort": {"total_credits": -1}},
            {"$limit": 10}
        ]

        top_tenants = await self.usage_log.aggregate(user_pipeline).to_list(length=None)

        # Feature breakdown
        feature_pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$feature",
                    "total_credits": {"$sum": "$credits_used"},
                    "total_requests": {"$sum": 1},
                    "cache_hit_rate": {
                        "$avg": {"$cond": [{"$eq": ["$status", "cached"]}, 1, 0]}
                    },
                    "error_rate": {
                        "$avg": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}
                    }
                }
            }
        ]

        feature_breakdown = await self.usage_log.aggregate(feature_pipeline).to_list(length=None)

        # Total summary
        total_credits = sum(f.get("total_credits", 0) for f in feature_breakdown)
        total_requests = sum(f.get("total_requests", 0) for f in feature_breakdown)

        return {
            "period_days": period_days,
            "summary": {
                "total_credits_used": total_credits,
                "total_requests": total_requests,
                "unique_features": len(feature_breakdown)
            },
            "daily_usage": daily_usage,
            "top_tenants": top_tenants,
            "feature_breakdown": feature_breakdown,
            "generated_at": datetime.utcnow().isoformat()
        }


# Singleton instance
ai_service = AIService()
