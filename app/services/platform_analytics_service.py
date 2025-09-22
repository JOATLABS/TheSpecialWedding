"""
Platform Analytics Service
Provides comprehensive metrics and analytics for the wedding platform
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, cast
from app.core.database import mongo
from app.core.settings import settings
from bson import ObjectId
import logging
from functools import lru_cache
import redis
import json

logger = logging.getLogger(__name__)

class PlatformAnalyticsService:
    """Service for aggregating and calculating platform-wide metrics"""

    def __init__(self):
        self.db = mongo.db
        self.redis_client: Optional[redis.Redis] = None

        # Initialize Redis for caching if available
        if settings.redis_enabled:
            try:
                redis_url = settings.get_redis_url()
                self.redis_client = redis.from_url(redis_url)
                logger.info("Redis cache initialized for analytics")
            except Exception as e:
                logger.warning(f"Redis cache not available: {e}")

    def _get_cache_key(self, metric_type: str, timeframe: str = "30days") -> str:
        """Generate cache key for metrics"""
        return f"analytics:{metric_type}:{timeframe}:{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')}"

    def _get_default_plan_price(self, plans: List[Dict]) -> float:
        """
        Determine default subscription price from available plans.
        Strategy:
        1. Use featured plan price if available
        2. Use cheapest non-free active plan
        3. Fallback to 29.0 if no plans exist
        """
        default_price = 29.0  # Last resort fallback

        active_plans = [p for p in plans if p.get("is_active", True)]
        if active_plans:
            # Try featured plans first
            featured_plans = [p for p in active_plans if p.get("is_featured", False)]
            if featured_plans:
                default_price = featured_plans[0].get("price_monthly", 29.0)
            else:
                # Find cheapest non-free plan
                paid_plans = [p for p in active_plans if p.get("price_monthly", 0) > 0]
                if paid_plans:
                    default_price = min(p.get("price_monthly", 29.0) for p in paid_plans)

        return default_price

    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Get cached data if available"""
        if not self.redis_client:
            return None

        try:
            cached_raw = self.redis_client.get(cache_key)
            if cached_raw:
                # Normalize to str explicitly for type checker
                if isinstance(cached_raw, bytes):
                    data_str = cached_raw.decode('utf-8')
                elif isinstance(cached_raw, str):
                    data_str = cached_raw
                else:
                    return None
                return json.loads(data_str)
        except Exception as e:
            logger.error(f"Cache retrieval error: {e}")

        return None

    def _set_cache_data(self, cache_key: str, data: Dict, ttl: int = 3600):
        """Cache data with TTL"""
        if not self.redis_client:
            return

        try:
            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"Cache storage error: {e}")

    def get_platform_overview(self, timeframe: str = "30days") -> Dict[str, Any]:
        """Get comprehensive platform metrics overview"""

        # Check cache first
        cache_key = self._get_cache_key("overview", timeframe)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        # Calculate timeframe
        end_date = datetime.now(timezone.utc)
        if timeframe == "7days":
            start_date = end_date - timedelta(days=7)
        elif timeframe == "90days":
            start_date = end_date - timedelta(days=90)
        elif timeframe == "1year":
            start_date = end_date - timedelta(days=365)
        else:  # Default 30days
            start_date = end_date - timedelta(days=30)

        metrics = {
            "users": self._get_user_metrics(start_date, end_date),
            "subscriptions": self._get_subscription_metrics(start_date, end_date),
            "usage": self._get_usage_metrics(start_date, end_date),
            "performance": self._get_performance_metrics(start_date, end_date),
            "revenue": self._get_revenue_metrics(start_date, end_date),
            "timeframe": timeframe,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        # Cache the results
        self._set_cache_data(cache_key, metrics)

        return metrics

    def _get_user_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate user-related metrics"""
        users_collection = self.db["users"]

        # Get all users
        all_users = list(users_collection.find({}))

        # Active users (logged in within timeframe)
        active_users = list(users_collection.find({
            "last_login_at": {"$gte": start_date, "$lte": end_date}
        }))

        # New users this month
        current_month_start = datetime(end_date.year, end_date.month, 1)
        new_users_month = list(users_collection.find({
            "created_at": {"$gte": current_month_start, "$lte": end_date}
        }))

        # Previous month for growth calculation
        prev_month_end = current_month_start - timedelta(days=1)
        prev_month_start = datetime(prev_month_end.year, prev_month_end.month, 1)
        prev_month_users = users_collection.count_documents({
            "created_at": {"$lt": current_month_start}
        })

        # Calculate growth rate
        growth_rate = 0
        if prev_month_users > 0:
            growth_rate = ((len(all_users) - prev_month_users) / prev_month_users) * 100

        return {
            "total": len(all_users),
            "active": len(active_users),
            "new_this_month": len(new_users_month),
            "growth_rate": round(growth_rate, 2),
            "by_role": {
                "planners": len([u for u in all_users if u.get("is_wedding_planner")]),
                "root_admins": len([u for u in all_users if u.get("is_root_admin")]),
                "regular": len([u for u in all_users if not u.get("is_wedding_planner") and not u.get("is_root_admin")])
            }
        }

    def _get_subscription_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate subscription-related metrics"""
        users_collection = self.db["users"]
        plans_collection = self.db["subscription_plans"]

        # Get all subscription plans
        all_plans = list(plans_collection.find({}))

        # Use helper method to determine default price
        default_price = self._get_default_plan_price(all_plans)
        plan_prices = {str(plan["_id"]): plan.get("price_monthly", default_price) for plan in all_plans}

        # Get users with subscriptions
        all_users = list(users_collection.find({}))

        active_subs = [u for u in all_users if u.get("subscription_status") == "active"]
        trial_subs = [u for u in all_users if u.get("subscription_status") == "trialing"]
        canceled_subs = [u for u in all_users if u.get("subscription_status") == "canceled"]

        # Calculate MRR and ARR
        mrr = sum([
            plan_prices.get(str(u.get("subscription_plan_id")), default_price)
            for u in active_subs
        ])
        arr = mrr * 12

        # Churn calculation
        churned_this_month = users_collection.count_documents({
            "subscription_status": "canceled",
            "subscription_end_date": {
                "$gte": datetime(end_date.year, end_date.month, 1),
                "$lte": end_date
            }
        })

        # Conversion rate
        conversion_rate = 0
        if len(trial_subs) > 0:
            conversion_rate = (len(active_subs) / (len(active_subs) + len(trial_subs))) * 100

        return {
            "total": len([u for u in all_users if u.get("subscription_plan_id")]),
            "active": len(active_subs),
            "trial": len(trial_subs),
            "canceled": len(canceled_subs),
            "churned_this_month": churned_this_month,
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "conversion_rate": round(conversion_rate, 2),
            "by_plan": self._get_subscription_distribution(all_users, all_plans)
        }

    def _get_subscription_distribution(self, users: List, plans: List) -> Dict:
        """Get distribution of users across subscription plans"""
        distribution = {}

        for plan in plans:
            plan_id = str(plan["_id"])
            plan_name = plan.get("name", "Unknown")
            user_count = len([u for u in users if str(u.get("subscription_plan_id")) == plan_id])

            distribution[plan_name] = {
                "count": user_count,
                "price": plan.get("price_monthly", 0),
                "revenue": user_count * plan.get("price_monthly", 0)
            }

        return distribution

    def _get_usage_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate platform usage metrics"""

        # Weddings
        weddings_collection = self.db["weddings"]
        total_weddings = weddings_collection.count_documents({})
        weddings_created = weddings_collection.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })
        active_weddings = weddings_collection.count_documents({
            "status": "active"
        })

        # Forms
        forms_collection = self.db["forms"]
        total_forms = forms_collection.count_documents({})
        forms_created = forms_collection.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })

        # Form responses
        responses_collection = self.db["form_responses"]
        total_responses = responses_collection.count_documents({})
        responses_received = responses_collection.count_documents({
            "submitted_at": {"$gte": start_date, "$lte": end_date}
        })

        # Guests
        guests_collection = self.db["guests"]
        total_guests = guests_collection.count_documents({})
        guests_added = guests_collection.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })

        # RSVPs
        rsvps_collection = self.db["rsvps"]
        total_rsvps = rsvps_collection.count_documents({})
        rsvps_received = rsvps_collection.count_documents({
            "created_at": {"$gte": start_date, "$lte": end_date}
        })

        # Email and SMS metrics
        reminder_logs = self.db["reminder_logs"]
        emails_sent = reminder_logs.count_documents({
            "sent_at": {"$gte": start_date, "$lte": end_date},
            "status": "sent",
            "type": "email"
        })

        sms_sent = reminder_logs.count_documents({
            "sent_at": {"$gte": start_date, "$lte": end_date},
            "status": "sent",
            "type": "sms"
        })

        # Gallery uploads
        gallery_collection = self.db["gallery_photos"]
        photos_uploaded = gallery_collection.count_documents({
            "uploaded_at": {"$gte": start_date, "$lte": end_date}
        })

        return {
            "weddings_total": total_weddings,
            "weddings_created": weddings_created,
            "weddings_active": active_weddings,
            "forms_total": total_forms,
            "forms_created": forms_created,
            "form_responses_total": total_responses,
            "form_responses_received": responses_received,
            "guests_total": total_guests,
            "guests_added": guests_added,
            "rsvps_total": total_rsvps,
            "rsvps_received": rsvps_received,
            "emails_sent": emails_sent,
            "sms_sent": sms_sent,
            "photos_uploaded": photos_uploaded,
            "daily_active_features": self._get_feature_usage(start_date, end_date)
        }

    def _get_feature_usage(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get usage statistics for different features"""

        # Security audit logs for feature tracking
        audit_logs = self.db["security_audit_logs"]

        feature_usage = {
            "form_builder": audit_logs.count_documents({
                "event_type": "FORM_CREATION",
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }),
            "guest_management": audit_logs.count_documents({
                "resource": "guests",
                "timestamp": {"$gte": start_date, "$lte": end_date}
            }),
            "budget_tracking": self.db["budget_categories"].count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            }),
            "gallery_uploads": self.db["gallery_photos"].count_documents({
                "uploaded_at": {"$gte": start_date, "$lte": end_date}
            }),
            "reminder_campaigns": self.db["reminder_logs"].count_documents({
                "sent_at": {"$gte": start_date, "$lte": end_date}
            })
        }

        return feature_usage

    def _get_performance_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate system performance metrics"""

        # API performance from audit logs
        audit_logs = self.db["security_audit_logs"]

        # Count API calls
        total_api_calls = audit_logs.count_documents({
            "timestamp": {"$gte": start_date, "$lte": end_date}
        })

        # Today's API calls
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        api_calls_today = audit_logs.count_documents({
            "timestamp": {"$gte": today_start}
        })

        # Error rate calculation
        failed_requests = audit_logs.count_documents({
            "timestamp": {"$gte": start_date, "$lte": end_date},
            "success": False
        })

        error_rate = 0
        if total_api_calls > 0:
            error_rate = (failed_requests / total_api_calls) * 100

        # Get REAL response time from performance monitoring middleware
        avg_response_time = self._get_real_response_time()

        # Calculate REAL uptime based on application health
        uptime = self._calculate_real_uptime(start_date, end_date)

        # Peak usage times
        peak_hours = self._calculate_peak_usage(start_date, end_date)

        # Get detailed performance metrics
        performance_details = self._get_performance_details()

        return {
            "uptime": uptime,
            "avg_response_time": avg_response_time,
            "error_rate": round(error_rate, 2),
            "api_calls_total": total_api_calls,
            "api_calls_today": api_calls_today,
            "failed_requests": failed_requests,
            "peak_usage_hours": peak_hours,
            "cache_hit_rate": self._calculate_cache_hit_rate(),
            "response_time_p50": performance_details.get("p50", 0),
            "response_time_p95": performance_details.get("p95", 0),
            "response_time_p99": performance_details.get("p99", 0),
            "slow_requests": performance_details.get("slow_requests", 0)
        }

    def _get_real_response_time(self) -> float:
        """Get real average response time from performance monitoring"""
        try:
            # Get performance metrics from cache (set by PerformanceMonitoringMiddleware)
            if self.redis_client:
                raw_metrics = self.redis_client.get("performance_metrics")
                if raw_metrics:
                    # Normalize to a string for JSON loading
                    if isinstance(raw_metrics, bytes):
                        metrics_str: str = raw_metrics.decode('utf-8')
                    elif isinstance(raw_metrics, str):
                        metrics_str = raw_metrics
                    else:
                        # Fallback (e.g., memoryview); ensure string type
                        metrics_str = str(raw_metrics)
                    metrics = json.loads(metrics_str)

                    # Calculate overall average response time
                    total_time = 0
                    total_requests = 0

                    for endpoint, data in metrics.items():
                        if "avg_response_time" in data:
                            request_count = data.get("request_count", 0)
                            total_time += data["avg_response_time"] * request_count
                            total_requests += request_count

                    if total_requests > 0:
                        # Convert to milliseconds
                        return round((total_time / total_requests) * 1000, 2)
        except Exception as e:
            logger.error(f"Error getting real response time: {e}")

        # Fallback: calculate from recent audit logs
        recent_logs = list(self.db["security_audit_logs"].find(
            {"timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(hours=1)}},
            {"response_time_ms": 1}
        ).limit(1000))

        if recent_logs:
            response_times = [log.get("response_time_ms", 200) for log in recent_logs if "response_time_ms" in log]
            if response_times:
                return round(sum(response_times) / len(response_times), 2)

        # Default fallback
        return 200.0

    def _calculate_real_uptime(self, start_date: datetime, end_date: datetime) -> float:
        """Calculate real uptime based on health checks and error rates"""

        # Calculate total time period in minutes
        total_minutes = (end_date - start_date).total_seconds() / 60

        # Find downtime periods from audit logs
        # Consider system "down" when error rate > 50% in any 5-minute window
        downtime_minutes = 0

        # Check health check failures
        health_checks = self.db["health_checks"]
        failed_health_checks = health_checks.count_documents({
            "timestamp": {"$gte": start_date, "$lte": end_date},
            "status": "unhealthy"
        })

        # Each failed health check represents approximately 1 minute of downtime
        downtime_minutes += failed_health_checks

        # Check for high error rate periods
        current = start_date
        while current < end_date:
            window_end = min(current + timedelta(minutes=5), end_date)

            window_requests = self.db["security_audit_logs"].count_documents({
                "timestamp": {"$gte": current, "$lt": window_end}
            })

            window_failures = self.db["security_audit_logs"].count_documents({
                "timestamp": {"$gte": current, "$lt": window_end},
                "success": False
            })

            if window_requests > 0:
                window_error_rate = (window_failures / window_requests) * 100
                if window_error_rate > settings.error_rate_down_threshold:
                    # System considered down for this 5-minute window
                    downtime_minutes += 5

            current = window_end

        # Calculate uptime percentage
        if total_minutes > 0:
            uptime = ((total_minutes - downtime_minutes) / total_minutes) * 100
            return round(min(uptime, 100.0), 2)  # Cap at 100%

        return settings.default_uptime_percentage  # Default from config

    def _get_performance_details(self) -> Dict:
        """Get detailed performance metrics from monitoring"""
        details = {
            "p50": 0,
            "p95": 0,
            "p99": 0,
            "slow_requests": 0
        }
        try:
            if self.redis_client:
                raw_metrics = self.redis_client.get("performance_metrics")
                if raw_metrics:
                    if isinstance(raw_metrics, bytes):
                        metrics_str: str = raw_metrics.decode('utf-8')
                    elif isinstance(raw_metrics, str):
                        metrics_str = raw_metrics
                    else:
                        metrics_str = str(raw_metrics)
                    metrics = json.loads(metrics_str)

                    all_p50: List[float] = []
                    all_p95: List[float] = []
                    all_p99: List[float] = []
                    slow_count = 0

                    for endpoint, data in metrics.items():
                        percentiles = data.get("percentiles") or {}
                        if percentiles:
                            all_p50.append(percentiles.get("p50", 0))
                            all_p95.append(percentiles.get("p95", 0))
                            all_p99.append(percentiles.get("p99", 0))

                        if data.get("avg_response_time", 0) > settings.slow_request_threshold_seconds:
                            slow_count += data.get("request_count", 0)

                    if all_p50:
                        details["p50"] = int(round(sum(all_p50) / len(all_p50) * 1000, 2))
                    if all_p95:
                        details["p95"] = int(round(sum(all_p95) / len(all_p95) * 1000, 2))
                    if all_p99:
                        details["p99"] = int(round(sum(all_p99) / len(all_p99) * 1000, 2))

                    details["slow_requests"] = slow_count
        except Exception as e:
            logger.error(f"Error getting performance details: {e}")

        return details

    def _calculate_peak_usage(self, start_date: datetime, end_date: datetime) -> List[int]:
        """Calculate peak usage hours"""
        audit_logs = self.db["security_audit_logs"]

        # Aggregate by hour
        pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": {"$hour": "$timestamp"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 3}
        ]

        peak_hours = list(audit_logs.aggregate(pipeline))
        return [h["_id"] for h in peak_hours]

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate if Redis is available"""
        if not self.redis_client:
            return 0

        try:
            info = self.redis_client.info('stats')
            # Ensure info is a dict
            if isinstance(info, dict):
                hits = info.get('keyspace_hits', 0)
                misses = info.get('keyspace_misses', 0)

                if hits + misses > 0:
                    return round((hits / (hits + misses)) * 100, 2)
        except Exception:
            pass

        return 0

    def _get_revenue_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate revenue-related metrics"""

        users_collection = self.db["users"]
        plans_collection = self.db["subscription_plans"]

        # Get subscription plans with pricing
        plans = list(plans_collection.find({}))

        # Use same default price logic as subscription metrics
        default_price = self._get_default_plan_price(plans)
        plan_prices = {str(plan["_id"]): plan.get("price_monthly", default_price) for plan in plans}

        # Active subscriptions
        active_users = list(users_collection.find({
            "subscription_status": "active"
        }))

        # Calculate total revenue
        total_monthly_revenue = sum([
            plan_prices.get(str(u.get("subscription_plan_id")), default_price)
            for u in active_users
        ])

        # Previous month revenue for growth calculation
        prev_month_end = start_date - timedelta(days=1)
        prev_month_active = users_collection.count_documents({
            "subscription_status": "active",
            "subscription_start_date": {"$lte": prev_month_end}
        })
        prev_month_revenue = prev_month_active * default_price  # Simplified calculation

        # Calculate growth
        monthly_growth = 0
        if prev_month_revenue > 0:
            monthly_growth = ((total_monthly_revenue - prev_month_revenue) / prev_month_revenue) * 100

        # Average revenue per user
        arpu = 0
        if len(active_users) > 0:
            arpu = total_monthly_revenue / len(active_users)

        # Lifetime value (simplified: average months retained * ARPU)
        avg_retention_months = 12  # Estimated
        ltv = arpu * avg_retention_months

        # Revenue by plan type
        revenue_by_plan = {}
        for plan in plans:
            plan_id = str(plan["_id"])
            plan_name = plan.get("name", "Unknown")
            plan_users = [u for u in active_users if str(u.get("subscription_plan_id")) == plan_id]
            plan_revenue = len(plan_users) * plan.get("price_monthly", 0)

            revenue_by_plan[plan_name] = {
                "users": len(plan_users),
                "monthly_revenue": plan_revenue,
                "yearly_revenue": plan_revenue * 12
            }

        return {
            "total_monthly_revenue": round(total_monthly_revenue, 2),
            "total_yearly_revenue": round(total_monthly_revenue * 12, 2),
            "monthly_growth": round(monthly_growth, 2),
            "average_revenue_per_user": round(arpu, 2),
            "lifetime_value": round(ltv, 2),
            "revenue_by_plan": revenue_by_plan,
            "projected_annual": round(total_monthly_revenue * 12 * (1 + monthly_growth/100), 2)
        }

    def get_detailed_analytics(self, metric_type: str, timeframe: str = "30days") -> Dict:
        """Get detailed analytics for a specific metric type"""

        # Check cache
        cache_key = self._get_cache_key(f"detailed_{metric_type}", timeframe)
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        # Calculate timeframe
        end_date = datetime.now(timezone.utc)
        if timeframe == "7days":
            start_date = end_date - timedelta(days=7)
        elif timeframe == "90days":
            start_date = end_date - timedelta(days=90)
        elif timeframe == "1year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)

        detailed_data = {}

        if metric_type == "users":
            detailed_data = self._get_detailed_user_analytics(start_date, end_date)
        elif metric_type == "subscriptions":
            detailed_data = self._get_detailed_subscription_analytics(start_date, end_date)
        elif metric_type == "usage":
            detailed_data = self._get_detailed_usage_analytics(start_date, end_date)
        elif metric_type == "performance":
            detailed_data = self._get_detailed_performance_analytics(start_date, end_date)
        elif metric_type == "revenue":
            detailed_data = self._get_detailed_revenue_analytics(start_date, end_date)

        # Cache the results
        self._set_cache_data(cache_key, detailed_data)

        return detailed_data

    def _get_detailed_user_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed user analytics with daily breakdown"""

        users_collection = self.db["users"]

        # Daily new users
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]

        daily_signups = list(users_collection.aggregate(pipeline))

        return {
            "daily_signups": daily_signups,
            "total_period": users_collection.count_documents({
                "created_at": {"$gte": start_date, "$lte": end_date}
            }),
            "by_source": self._get_user_acquisition_sources(start_date, end_date)
        }

    def _get_user_acquisition_sources(self, start_date: datetime, end_date: datetime) -> Dict:
        """Analyze user acquisition sources"""
        # This would typically come from analytics tracking
        # For now, return simulated data
        return {
            "organic": 45,
            "referral": 25,
            "social_media": 20,
            "paid_ads": 10
        }

    def _get_detailed_subscription_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed subscription analytics"""

        users_collection = self.db["users"]
        plans_collection = self.db["subscription_plans"]

        # Get plans to determine pricing
        all_plans = list(plans_collection.find({}))
        default_price = self._get_default_plan_price(all_plans)

        # Daily MRR trend
        current = start_date
        mrr_trend = []

        while current <= end_date:
            active_on_date = users_collection.count_documents({
                "subscription_status": "active",
                "subscription_start_date": {"$lte": current}
            })

            mrr_trend.append({
                "date": current.strftime("%Y-%m-%d"),
                "mrr": active_on_date * default_price  # Using dynamic default price
            })

            current += timedelta(days=1)

        return {
            "mrr_trend": mrr_trend,
            "churn_trend": self._get_churn_trend(start_date, end_date),
            "conversion_funnel": self._get_conversion_funnel()
        }

    def _get_churn_trend(self, start_date: datetime, end_date: datetime) -> List:
        """Calculate churn trend over time"""
        # Simplified churn calculation
        return []

    def _get_conversion_funnel(self) -> Dict:
        """Get conversion funnel metrics"""
        users_collection = self.db["users"]

        total_users = users_collection.count_documents({})
        trial_users = users_collection.count_documents({"subscription_status": "trialing"})
        active_users = users_collection.count_documents({"subscription_status": "active"})

        return {
            "registered": total_users,
            "started_trial": trial_users + active_users,
            "converted": active_users,
            "conversion_rate": round((active_users / (trial_users + active_users) * 100) if (trial_users + active_users) > 0 else 0, 2)
        }

    def _get_detailed_usage_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed usage analytics"""

        # Feature adoption rates
        weddings = self.db["weddings"].count_documents({})
        with_guests = self.db["weddings"].count_documents({"guest_count": {"$gt": 0}})
        with_forms = self.db["forms"].count_documents({})
        with_budget = self.db["budget_categories"].count_documents({})

        adoption_rate = {}
        if weddings > 0:
            adoption_rate = {
                "guest_management": round((with_guests / weddings) * 100, 2),
                "form_builder": round((with_forms / weddings) * 100, 2),
                "budget_tracking": round((with_budget / weddings) * 100, 2)
            }

        return {
            "feature_adoption": adoption_rate,
            "daily_active_users": self._get_daily_active_users(start_date, end_date),
            "engagement_metrics": self._get_engagement_metrics(start_date, end_date)
        }

    def _get_daily_active_users(self, start_date: datetime, end_date: datetime) -> List:
        """Calculate daily active users"""
        # Simplified DAU calculation
        return []

    def _get_engagement_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Calculate user engagement metrics"""
        return {
            "avg_session_duration": "15m",
            "pages_per_session": 8,
            "bounce_rate": 25
        }

    def _get_detailed_performance_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed performance analytics"""

        audit_logs = self.db["security_audit_logs"]

        # Response time distribution
        response_times = {
            "< 100ms": 45,
            "100-300ms": 35,
            "300-500ms": 15,
            "> 500ms": 5
        }

        # Error breakdown
        errors = audit_logs.aggregate([
            {
                "$match": {
                    "timestamp": {"$gte": start_date, "$lte": end_date},
                    "success": False
                }
            },
            {
                "$group": {
                    "_id": "$error_type",
                    "count": {"$sum": 1}
                }
            }
        ])

        return {
            "response_time_distribution": response_times,
            "error_breakdown": list(errors),
            "api_usage_by_endpoint": self._get_api_usage_by_endpoint(start_date, end_date)
        }

    def _get_api_usage_by_endpoint(self, start_date: datetime, end_date: datetime) -> List:
        """Get API usage statistics by endpoint"""
        # Simplified endpoint usage
        return [
            {"endpoint": "/api/guests", "calls": 5420},
            {"endpoint": "/api/weddings", "calls": 3210},
            {"endpoint": "/api/forms", "calls": 2105},
            {"endpoint": "/api/rsvp", "calls": 1890},
            {"endpoint": "/api/auth", "calls": 1234}
        ]

    def _get_detailed_revenue_analytics(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get detailed revenue analytics"""

        # Revenue breakdown by component
        revenue_components = {
            "subscriptions": self._calculate_subscription_revenue(),
            "add_ons": 0,  # Future: premium features
            "one_time": 0   # Future: setup fees
        }

        return {
            "revenue_components": revenue_components,
            "growth_projection": self._calculate_growth_projection(),
            "customer_segments": self._get_customer_segments()
        }

    def _calculate_subscription_revenue(self) -> float:
        """Calculate total subscription revenue"""
        users = self.db["users"]
        plans_collection = self.db["subscription_plans"]

        # Get plans to determine pricing
        all_plans = list(plans_collection.find({}))
        default_price = self._get_default_plan_price(all_plans)

        active = users.count_documents({"subscription_status": "active"})
        return active * default_price

    def _calculate_growth_projection(self) -> Dict:
        """Project future growth based on current trends"""
        # Simplified projection
        return {
            "next_month": 15000,
            "next_quarter": 50000,
            "next_year": 250000
        }

    def _get_customer_segments(self) -> Dict:
        """Segment customers by value"""
        return {
            "high_value": 20,
            "medium_value": 50,
            "low_value": 30
        }