"""
Robustness Middleware for FastAPI.
Includes request validation, timeout handling, error recovery, and health monitoring.
"""
import time
import asyncio
import traceback
from typing import Callable, Set, Dict, Any, Optional
from threading import Lock
from functools import wraps
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from services.logger import get_logger

logger = get_logger(__name__)


class ServiceHealthMonitor:
    """
    Monitor health status of dependent services.
    Provides degraded mode information for graceful fallback.
    """
    
    def __init__(self):
        self._status: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def update_status(self, service_name: str, healthy: bool, message: str = "", latency_ms: float = 0):
        """Update service health status."""
        with self._lock:
            self._status[service_name] = {
                "healthy": healthy,
                "message": message,
                "latency_ms": latency_ms,
                "last_check": time.time()
            }
    
    def get_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific service."""
        with self._lock:
            return self._status.get(service_name)
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all services."""
        with self._lock:
            return dict(self._status)
    
    def is_service_healthy(self, service_name: str) -> bool:
        """Check if a specific service is healthy."""
        status = self.get_status(service_name)
        return status.get("healthy", False) if status else False
    
    def get_overall_health(self) -> tuple:
        """
        Get overall system health.
        Returns: (is_healthy, degraded_services, message)
        """
        with self._lock:
            if not self._status:
                return True, [], "No services registered"
            
            degraded = []
            for name, status in self._status.items():
                if not status.get("healthy", False):
                    degraded.append(name)
            
            if not degraded:
                return True, [], "All services healthy"
            
            # Critical services that must be up
            critical = {"llm", "memory"}
            critical_down = set(degraded) & critical
            
            if critical_down:
                return False, degraded, f"Critical services down: {', '.join(critical_down)}"
            
            return True, degraded, f"Degraded mode: {', '.join(degraded)} unavailable"


# Global health monitor instance
_health_monitor = ServiceHealthMonitor()


def get_health_monitor() -> ServiceHealthMonitor:
    """Get global health monitor."""
    return _health_monitor


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for request validation and sanitization.
    """
    
    def __init__(self, app: ASGIApp, max_body_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error": "Request too large",
                    "max_size_mb": self.max_body_size / (1024 * 1024)
                }
            )
        
        # Add request timing
        start_time = time.time()
        request.state.start_time = start_time
        
        response = await call_next(request)
        
        # Add timing header
        duration = time.time() - start_time
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        
        return response


class GlobalExceptionMiddleware(BaseHTTPMiddleware):
    """
    Global exception handler to ensure graceful error responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            raise  # Let FastAPI handle HTTP exceptions
        except asyncio.TimeoutError:
            logger.error(f"Request timeout: {request.url.path}")
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Request timed out",
                    "message": "The request took too long to process. Please try again."
                }
            )
        except Exception as e:
            logger.error(f"Unhandled exception: {e}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later."
                }
            )


async def check_service_health(service_name: str, check_func: Callable) -> bool:
    """
    Helper to check service health and update monitor.
    
    Args:
        service_name: Name of the service
        check_func: Async or sync function that returns True if healthy
        
    Returns:
        True if service is healthy
    """
    start = time.time()
    try:
        if asyncio.iscoroutinefunction(check_func):
            result = await check_func()
        else:
            result = await asyncio.to_thread(check_func)
        
        latency = (time.time() - start) * 1000
        _health_monitor.update_status(service_name, bool(result), "OK", latency)
        return bool(result)
    except Exception as e:
        latency = (time.time() - start) * 1000
        _health_monitor.update_status(service_name, False, str(e), latency)
        return False


def safe_service_call(default_value=None, log_error: bool = True):
    """
    Decorator for graceful degradation of service calls.
    Returns default_value if service fails.
    
    Usage:
        @safe_service_call(default_value=[])
        def get_suggestions():
            return some_service.get_suggestions()
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return await asyncio.to_thread(func, *args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.warning(f"Service call failed (using default): {func.__name__} - {e}")
                return default_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.warning(f"Service call failed (using default): {func.__name__} - {e}")
                return default_value
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class GracefulDegradation:
    """
    Context manager for graceful degradation.
    Allows code to fail gracefully and return a default.
    
    Usage:
        async with GracefulDegradation(default=[]) as ctx:
            result = await some_risky_call()
            ctx.set_result(result)
        return ctx.result
    """
    
    def __init__(self, default=None, service_name: str = "unknown"):
        self.default = default
        self.service_name = service_name
        self._result = default
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger.warning(f"Graceful degradation for {self.service_name}: {exc_val}")
            _health_monitor.update_status(self.service_name, False, str(exc_val))
            return True  # Suppress exception
        return False
    
    def set_result(self, value):
        self._result = value
    
    @property
    def result(self):
        return self._result


def validate_input_length(text: str, max_length: int = 10000, field_name: str = "input") -> str:
    """
    Validate and truncate input text if needed.
    
    Args:
        text: Input text to validate
        max_length: Maximum allowed length
        field_name: Name of field for error messages
        
    Returns:
        Validated (possibly truncated) text
        
    Raises:
        HTTPException if input is invalid
    """
    if not text:
        raise HTTPException(status_code=422, detail=f"{field_name} cannot be empty")
    
    if len(text) > max_length:
        logger.warning(f"Input truncated: {field_name} was {len(text)} chars, max is {max_length}")
        return text[:max_length]
    
    return text


def create_robust_response(
    data: Any = None,
    success: bool = True,
    error: str = None,
    message: str = None,
    degraded: bool = False,
    degraded_services: list = None
) -> dict:
    """
    Create a standardized API response with robustness metadata.
    """
    response = {
        "success": success,
        "timestamp": time.time()
    }
    
    if data is not None:
        response["data"] = data
    
    if error:
        response["error"] = error
        response["success"] = False
    
    if message:
        response["message"] = message
    
    if degraded:
        response["degraded"] = True
        response["degraded_services"] = degraded_services or []
    
    return response
