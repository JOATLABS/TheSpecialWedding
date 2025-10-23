"""
Performance monitoring middleware
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time
import logging
from typing import Dict, List
from collections import defaultdict, deque
import asyncio
from datetime import datetime, timedelta
from app.core.cache import cache

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Monitor API performance and track metrics
    """
    
    def __init__(
        self,
        app,
        slow_request_threshold: float = 1.0,  # seconds
        metrics_window_size: int = 1000,
        enable_detailed_logging: bool = False
    ):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.metrics_window_size = metrics_window_size
        self.enable_detailed_logging = enable_detailed_logging
        
        # In-memory metrics storage
        self.request_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=metrics_window_size))
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
        # Background task for metrics aggregation
        self._metrics_task = None
    
    def _get_endpoint_key(self, path: str, method: str) -> str:
        """Generate endpoint key for metrics"""
        # Normalize path to remove IDs and dynamic segments
        normalized_path = path
        
        # Replace common ID patterns
        import re
        normalized_path = re.sub(r'/\d+', '/{id}', normalized_path)
        normalized_path = re.sub(r'/[a-f0-9-]{36}', '/{uuid}', normalized_path)
        normalized_path = re.sub(r'/[a-f0-9]{24}', '/{objectid}', normalized_path)
        
        return f"{method}:{normalized_path}"
    
    def _record_request_time(self, endpoint_key: str, duration: float):
        """Record request duration for metrics"""
        self.request_times[endpoint_key].append(duration)
        self.request_counts[endpoint_key] += 1
    
    def _record_error(self, endpoint_key: str):
        """Record error for metrics"""
        self.error_counts[endpoint_key] += 1
    
    def _calculate_percentiles(self, times: List[float]) -> Dict[str, float]:
        """Calculate response time percentiles"""
        if not times:
            return {"p50": 0, "p95": 0, "p99": 0}
        
        sorted_times = sorted(times)
        n = len(sorted_times)
        
        return {
            "p50": sorted_times[int(n * 0.5)],
            "p95": sorted_times[int(n * 0.95)],
            "p99": sorted_times[int(n * 0.99)]
        }
    
    async def _cache_metrics(self):
        """Cache current metrics to Redis"""
        try:
            metrics = {}
            
            for endpoint_key, times in self.request_times.items():
                if times:
                    percentiles = self._calculate_percentiles(list(times))
                    avg_time = sum(times) / len(times)
                    
                    metrics[endpoint_key] = {
                        "request_count": self.request_counts[endpoint_key],
                        "error_count": self.error_counts[endpoint_key],
                        "avg_response_time": round(avg_time, 3),
                        "percentiles": percentiles,
                        "error_rate": (
                            self.error_counts[endpoint_key] / self.request_counts[endpoint_key]
                            if self.request_counts[endpoint_key] > 0 else 0
                        )
                    }
            
            # Cache metrics for 5 minutes
            await cache.set("performance_metrics", metrics, expire=300)
            
        except Exception as e:
            logger.error(f"Failed to cache performance metrics: {str(e)}")
    
    async def _start_metrics_task(self):
        """Start background metrics aggregation task"""
        if self._metrics_task is None:
            self._metrics_task = asyncio.create_task(self._metrics_loop())
    
    async def _metrics_loop(self):
        """Background loop for metrics aggregation"""
        while True:
            try:
                await asyncio.sleep(60)  # Update metrics every minute
                await self._cache_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics loop error: {str(e)}")
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Monitor request performance"""
        
        # Start metrics task if not running
        await self._start_metrics_task()
        
        # Record start time
        start_time = time.time()
        endpoint_key = self._get_endpoint_key(request.url.path, request.method)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            duration = time.time() - start_time
            
            # Record metrics
            self._record_request_time(endpoint_key, duration)
            
            # Check for errors
            if response.status_code >= 400:
                self._record_error(endpoint_key)
            
            # Log slow requests
            if duration > self.slow_request_threshold:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration:.3f}s (status: {response.status_code})"
                )
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            
            # Detailed logging if enabled
            if self.enable_detailed_logging:
                logger.info(
                    f"{request.method} {request.url.path} "
                    f"- {response.status_code} - {duration:.3f}s"
                )
            
            return response
            
        except Exception as e:
            # Record error and duration
            duration = time.time() - start_time
            self._record_request_time(endpoint_key, duration)
            self._record_error(endpoint_key)
            
            logger.error(
                f"Request error: {request.method} {request.url.path} "
                f"after {duration:.3f}s - {str(e)}"
            )
            
            # Re-raise the exception
            raise
    
    async def get_metrics(self) -> Dict:
        """Get current performance metrics"""
        # Try to get from cache first
        cached_metrics = await cache.get("performance_metrics")
        if cached_metrics:
            return cached_metrics
        
        # Calculate metrics on demand
        metrics = {}
        
        for endpoint_key, times in self.request_times.items():
            if times:
                percentiles = self._calculate_percentiles(list(times))
                avg_time = sum(times) / len(times)
                
                metrics[endpoint_key] = {
                    "request_count": self.request_counts[endpoint_key],
                    "error_count": self.error_counts[endpoint_key],
                    "avg_response_time": round(avg_time, 3),
                    "percentiles": percentiles,
                    "error_rate": (
                        self.error_counts[endpoint_key] / self.request_counts[endpoint_key]
                        if self.request_counts[endpoint_key] > 0 else 0
                    )
                }
        
        return metrics


# Database query performance monitor
class DatabaseQueryMonitor:
    """Monitor database query performance"""
    
    def __init__(self):
        self.query_times = defaultdict(list)
        self.slow_query_threshold = 0.5  # 500ms
    
    async def monitor_query(self, collection_name: str, operation: str, query_func, *args, **kwargs):
        """Monitor a database query"""
        start_time = time.time()
        
        try:
            result = await query_func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Record query time
            query_key = f"{collection_name}.{operation}"
            self.query_times[query_key].append(duration)
            
            # Log slow queries
            if duration > self.slow_query_threshold:
                logger.warning(
                    f"Slow database query: {query_key} took {duration:.3f}s"
                )
            
            # Cache metrics
            await cache.set(
                f"db_query_time:{query_key}",
                duration,
                expire=300  # 5 minutes
            )
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Database query error: {collection_name}.{operation} "
                f"after {duration:.3f}s - {str(e)}"
            )
            raise


# Global instances
performance_monitor = PerformanceMonitoringMiddleware(
    app=None,  # Will be set when added to app
    slow_request_threshold=1.0,
    enable_detailed_logging=True
)

db_monitor = DatabaseQueryMonitor()


# Decorator for monitoring database operations
def monitor_db_operation(collection_name: str, operation: str):
    """Decorator for monitoring database operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await db_monitor.monitor_query(
                collection_name,
                operation,
                func,
                *args,
                **kwargs
            )
        return wrapper
    return decorator