"""
Comprehensive observability system with metrics, tracing, and health checks
"""
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import time
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
import psutil
import platform
from app.core.settings import settings
from app.core.cache import cache
from app.core.database_async import async_mongo

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheck:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricData:
    """Metric data point"""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram


class MetricsCollector:
    """Collect and manage application metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[MetricData]] = {}
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
        self.max_data_points = 1000
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        if name not in self.counters:
            self.counters[name] = 0
        
        self.counters[name] += value
        
        metric = MetricData(
            name=name,
            value=self.counters[name],
            tags=tags or {},
            metric_type="counter"
        )
        
        self._store_metric(metric)
    
    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric value"""
        self.gauges[name] = value
        
        metric = MetricData(
            name=name,
            value=value,
            tags=tags or {},
            metric_type="gauge"
        )
        
        self._store_metric(metric)
    
    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value"""
        if name not in self.histograms:
            self.histograms[name] = []
        
        self.histograms[name].append(value)
        
        # Keep only recent values
        if len(self.histograms[name]) > self.max_data_points:
            self.histograms[name] = self.histograms[name][-self.max_data_points:]
        
        metric = MetricData(
            name=name,
            value=value,
            tags=tags or {},
            metric_type="histogram"
        )
        
        self._store_metric(metric)
    
    def _store_metric(self, metric: MetricData):
        """Store metric data point"""
        if metric.name not in self.metrics:
            self.metrics[metric.name] = []
        
        self.metrics[metric.name].append(metric)
        
        # Keep only recent data points
        if len(self.metrics[metric.name]) > self.max_data_points:
            self.metrics[metric.name] = self.metrics[metric.name][-self.max_data_points:]
    
    def get_counter_value(self, name: str) -> float:
        """Get current counter value"""
        return self.counters.get(name, 0)
    
    def get_gauge_value(self, name: str) -> float:
        """Get current gauge value"""
        return self.gauges.get(name, 0)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics"""
        if name not in self.histograms or not self.histograms[name]:
            return {}
        
        values = self.histograms[name]
        values.sort()
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "p50": values[int(len(values) * 0.5)],
            "p95": values[int(len(values) * 0.95)],
            "p99": values[int(len(values) * 0.99)]
        }
    
    async def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics"""
        return {
            "counters": self.counters,
            "gauges": self.gauges,
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self.histograms.keys()
            },
            "timestamp": datetime.utcnow().isoformat()
        }


class HealthMonitor:
    """Monitor system health"""
    
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, HealthCheck] = {}
    
    def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func
        logger.info(f"Registered health check: {name}")
    
    async def run_health_check(self, name: str) -> HealthCheck:
        """Run a specific health check"""
        if name not in self.health_checks:
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check '{name}' not found"
            )
        
        start_time = time.time()
        
        try:
            check_func = self.health_checks[name]
            
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            
            response_time = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheck):
                result.response_time_ms = response_time
                return result
            elif isinstance(result, bool):
                return HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                    message="OK" if result else "Check failed",
                    response_time_ms=response_time
                )
            else:
                return HealthCheck(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=str(result),
                    response_time_ms=response_time
                )
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheck(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def run_all_health_checks(self) -> Dict[str, HealthCheck]:
        """Run all registered health checks"""
        results = {}
        
        tasks = []
        for name in self.health_checks.keys():
            tasks.append(self.run_health_check(name))
        
        if tasks:
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(check_results):
                name = list(self.health_checks.keys())[i]
                if isinstance(result, Exception):
                    results[name] = HealthCheck(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Health check error: {str(result)}"
                    )
                else:
                    results[name] = result
        
        self.last_check_results = results
        return results
    
    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status"""
        if not self.last_check_results:
            return HealthStatus.UNHEALTHY
        
        statuses = [check.status for check in self.last_check_results.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED


class SystemMonitor:
    """Monitor system resources"""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system resource metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics (if available)
            try:
                network = psutil.net_io_counters()
                network_stats = {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            except:
                network_stats = {}
            
            # Process info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            return {
                "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": (disk.used / disk.total) * 100
                },
                "network": network_stats,
                "process": {
                    "memory_rss": process_memory.rss,
                    "memory_vms": process_memory.vms,
                    "pid": process.pid,
                    "threads": process.num_threads()
                },
                "platform": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "python_version": platform.python_version()
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            return {"error": str(e)}


class ObservabilityManager:
    """Main observability manager"""
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.health_monitor = HealthMonitor()
        self.system_monitor = SystemMonitor()
        self._setup_default_health_checks()
        self._start_background_tasks()
    
    def _setup_default_health_checks(self):
        """Setup default health checks"""
        
        async def database_health():
            """Check database connectivity"""
            try:
                # Simple ping to database
                await async_mongo.client.server_info()
                return HealthCheck(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection OK"
                )
            except Exception as e:
                return HealthCheck(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database connection failed: {str(e)}"
                )
        
        async def cache_health():
            """Check cache connectivity"""
            if not cache.enabled:
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    message="Cache disabled"
                )
            
            try:
                await cache.redis_client.ping()
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    message="Cache connection OK"
                )
            except Exception as e:
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.DEGRADED,
                    message=f"Cache connection failed: {str(e)}"
                )
        
        def memory_health():
            """Check memory usage"""
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.UNHEALTHY,
                    message=f"High memory usage: {memory.percent}%",
                    details={"memory_percent": memory.percent}
                )
            elif memory.percent > 80:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.DEGRADED,
                    message=f"Elevated memory usage: {memory.percent}%",
                    details={"memory_percent": memory.percent}
                )
            else:
                return HealthCheck(
                    name="memory",
                    status=HealthStatus.HEALTHY,
                    message=f"Memory usage OK: {memory.percent}%",
                    details={"memory_percent": memory.percent}
                )
        
        def disk_health():
            """Check disk usage"""
            disk = psutil.disk_usage('/')
            percent = (disk.used / disk.total) * 100
            
            if percent > 95:
                return HealthCheck(
                    name="disk",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Critical disk usage: {percent:.1f}%",
                    details={"disk_percent": percent}
                )
            elif percent > 85:
                return HealthCheck(
                    name="disk",
                    status=HealthStatus.DEGRADED,
                    message=f"High disk usage: {percent:.1f}%",
                    details={"disk_percent": percent}
                )
            else:
                return HealthCheck(
                    name="disk",
                    status=HealthStatus.HEALTHY,
                    message=f"Disk usage OK: {percent:.1f}%",
                    details={"disk_percent": percent}
                )
        
        # Register health checks
        self.health_monitor.register_health_check("database", database_health)
        self.health_monitor.register_health_check("cache", cache_health)
        self.health_monitor.register_health_check("memory", memory_health)
        self.health_monitor.register_health_check("disk", disk_health)
    
    def _start_background_tasks(self):
        """Start background monitoring tasks"""
        async def collect_system_metrics():
            """Background task to collect system metrics"""
            while True:
                try:
                    system_metrics = await self.system_monitor.get_system_metrics()
                    
                    # Record key metrics
                    if "cpu" in system_metrics:
                        self.metrics.set_gauge("system.cpu.percent", system_metrics["cpu"]["percent"])
                    
                    if "memory" in system_metrics:
                        self.metrics.set_gauge("system.memory.percent", system_metrics["memory"]["percent"])
                        self.metrics.set_gauge("system.memory.used", system_metrics["memory"]["used"])
                    
                    if "process" in system_metrics:
                        self.metrics.set_gauge("process.memory.rss", system_metrics["process"]["memory_rss"])
                        self.metrics.set_gauge("process.threads", system_metrics["process"]["threads"])
                    
                    # Cache metrics for later retrieval
                    await cache.set("system_metrics", system_metrics, expire=300)
                    
                except Exception as e:
                    logger.error(f"Error collecting system metrics: {str(e)}")
                
                await asyncio.sleep(60)  # Collect every minute
        
        # Start the background task
        asyncio.create_task(collect_system_metrics())
    
    async def get_full_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report"""
        health_checks = await self.health_monitor.run_all_health_checks()
        overall_status = self.health_monitor.get_overall_health()
        system_metrics = await self.system_monitor.get_system_metrics()
        app_metrics = await self.metrics.export_metrics()
        
        return {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "health_checks": {
                name: {
                    "status": check.status.value,
                    "message": check.message,
                    "response_time_ms": check.response_time_ms,
                    "details": check.details
                }
                for name, check in health_checks.items()
            },
            "system_metrics": system_metrics,
            "application_metrics": app_metrics,
            "version": settings.app_version,
            "environment": settings.environment
        }


# Global observability manager
observability = ObservabilityManager()


# Convenience functions
def increment_counter(name: str, value: float = 1.0, **tags):
    """Increment a counter metric"""
    observability.metrics.increment_counter(name, value, tags)


def set_gauge(name: str, value: float, **tags):
    """Set a gauge metric"""
    observability.metrics.set_gauge(name, value, tags)


def record_histogram(name: str, value: float, **tags):
    """Record a histogram value"""
    observability.metrics.record_histogram(name, value, tags)


# Decorator for timing function execution
def timed(metric_name: str):
    """Decorator to time function execution"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                record_histogram(f"{metric_name}.duration", duration * 1000)  # milliseconds
                increment_counter(f"{metric_name}.success")
                return result
            except Exception as e:
                duration = time.time() - start_time
                record_histogram(f"{metric_name}.duration", duration * 1000)
                increment_counter(f"{metric_name}.error")
                raise
        
        return wrapper
    return decorator