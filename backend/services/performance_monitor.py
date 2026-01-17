"""
Performance Monitoring Middleware - Track request latency, errors, and resource usage.
"""
import time
import asyncio
import traceback
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock

from services.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EndpointMetrics:
    """Metrics for a single endpoint."""
    total_requests: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    status_codes: dict = field(default_factory=lambda: defaultdict(int))
    
    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0
        return self.total_latency_ms / self.total_requests
    
    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0
        return self.total_errors / self.total_requests * 100


class PerformanceMonitor:
    """Collects and aggregates performance metrics."""
    
    def __init__(self):
        self._metrics: dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self._lock = Lock()
        self._start_time = time.time()
    
    def record(
        self,
        endpoint: str,
        latency_ms: float,
        status_code: int,
        is_error: bool = False
    ):
        """Record a request's metrics."""
        with self._lock:
            m = self._metrics[endpoint]
            m.total_requests += 1
            m.total_latency_ms += latency_ms
            m.min_latency_ms = min(m.min_latency_ms, latency_ms)
            m.max_latency_ms = max(m.max_latency_ms, latency_ms)
            m.status_codes[status_code] += 1
            if is_error:
                m.total_errors += 1
    
    def get_metrics(self) -> dict:
        """Get all metrics."""
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                'uptime_seconds': round(uptime, 2),
                'endpoints': {
                    path: {
                        'total_requests': m.total_requests,
                        'total_errors': m.total_errors,
                        'error_rate_percent': round(m.error_rate, 2),
                        'avg_latency_ms': round(m.avg_latency_ms, 2),
                        'min_latency_ms': round(m.min_latency_ms, 2) if m.min_latency_ms != float('inf') else 0,
                        'max_latency_ms': round(m.max_latency_ms, 2),
                        'status_codes': dict(m.status_codes)
                    }
                    for path, m in self._metrics.items()
                },
                'summary': self._get_summary()
            }
    
    def _get_summary(self) -> dict:
        """Get summary metrics."""
        total_requests = sum(m.total_requests for m in self._metrics.values())
        total_errors = sum(m.total_errors for m in self._metrics.values())
        total_latency = sum(m.total_latency_ms for m in self._metrics.values())
        
        return {
            'total_requests': total_requests,
            'total_errors': total_errors,
            'overall_error_rate': round(total_errors / max(total_requests, 1) * 100, 2),
            'avg_latency_ms': round(total_latency / max(total_requests, 1), 2)
        }
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._start_time = time.time()


# Singleton
_monitor: PerformanceMonitor | None = None


def get_performance_monitor() -> PerformanceMonitor:
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track request performance."""
    
    def __init__(self, app: ASGIApp, exclude_paths: set[str] | None = None):
        super().__init__(app)
        self.monitor = get_performance_monitor()
        self.exclude_paths = exclude_paths or {'/api/health', '/api/system/metrics'}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        start_time = time.perf_counter()
        is_error = False
        status_code = 500
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            is_error = status_code >= 400
            return response
            
        except Exception as e:
            is_error = True
            logger.error(f"Request error: {request.url.path} - {e}")
            raise
            
        finally:
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Log slow requests
            if latency_ms > 1000:
                logger.warning(f"Slow request: {request.method} {request.url.path} took {latency_ms:.0f}ms")
            
            # Record metrics
            self.monitor.record(
                endpoint=f"{request.method} {request.url.path}",
                latency_ms=latency_ms,
                status_code=status_code,
                is_error=is_error
            )


class RequestLogger(BaseHTTPMiddleware):
    """Middleware to log all requests."""
    
    def __init__(self, app: ASGIApp, log_body: bool = False):
        super().__init__(app)
        self.log_body = log_body
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Log request
        logger.info(f"→ {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Log response
            logger.info(f"← {request.method} {request.url.path} [{response.status_code}]")
            
            return response
            
        except Exception as e:
            logger.error(f"✗ {request.method} {request.url.path} - {type(e).__name__}: {e}")
            raise
