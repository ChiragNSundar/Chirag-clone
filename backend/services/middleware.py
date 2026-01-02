"""
Middleware Service - Request processing middleware for Flask.
Includes timeout handling, request tracking, and memory limits.
"""
import time
import signal
import threading
from functools import wraps
from typing import Dict, Set, Callable
from flask import request, g, jsonify
from services.logger import get_logger

logger = get_logger(__name__)


class RequestTracker:
    """Track in-flight requests for graceful shutdown."""
    
    def __init__(self):
        self._active_requests: Set[str] = set()
        self._lock = threading.Lock()
        self._shutting_down = False
    
    def add(self, request_id: str) -> None:
        """Add request to active set."""
        with self._lock:
            self._active_requests.add(request_id)
    
    def remove(self, request_id: str) -> None:
        """Remove request from active set."""
        with self._lock:
            self._active_requests.discard(request_id)
    
    def count(self) -> int:
        """Get count of active requests."""
        with self._lock:
            return len(self._active_requests)
    
    def is_shutting_down(self) -> bool:
        """Check if server is shutting down."""
        return self._shutting_down
    
    def start_shutdown(self) -> None:
        """Mark server as shutting down."""
        self._shutting_down = True
    
    def wait_for_requests(self, timeout: int = 30) -> bool:
        """
        Wait for active requests to complete.
        
        Args:
            timeout: Max seconds to wait
            
        Returns:
            True if all requests completed, False if timed out
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.count() == 0:
                return True
            time.sleep(0.1)
        return False


# Global request tracker
_request_tracker = RequestTracker()


def get_request_tracker() -> RequestTracker:
    """Get global request tracker."""
    return _request_tracker


class TimeoutError(Exception):
    """Request timeout exception."""
    pass


def request_tracking_middleware(app):
    """
    Add request tracking middleware for graceful shutdown support.
    """
    @app.before_request
    def track_request_start():
        if hasattr(g, 'request_id'):
            _request_tracker.add(g.request_id)
        
        # Reject new requests during shutdown
        if _request_tracker.is_shutting_down():
            return jsonify({
                'error': 'Server is shutting down',
                'retry_after': 30
            }), 503
    
    @app.after_request
    def track_request_end(response):
        if hasattr(g, 'request_id'):
            _request_tracker.remove(g.request_id)
        return response
    
    return app


def timeout_handler(signum, frame):
    """Signal handler for request timeout."""
    raise TimeoutError("Request timed out")


def with_timeout(seconds: int):
    """
    Decorator to add timeout to a function.
    Note: Only works on Unix-like systems with SIGALRM.
    On Windows, uses a threading-based approach.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import platform
            
            if platform.system() != 'Windows':
                # Unix: Use signal-based timeout
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                return result
            else:
                # Windows: Use threading-based timeout (less reliable)
                result = [None]
                exception = [None]
                
                def target():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=target)
                thread.start()
                thread.join(timeout=seconds)
                
                if thread.is_alive():
                    logger.warning(f"Function {func.__name__} timed out after {seconds}s")
                    raise TimeoutError(f"Request timed out after {seconds} seconds")
                
                if exception[0]:
                    raise exception[0]
                
                return result[0]
        
        return wrapper
    return decorator


# Route-specific timeout configuration
ROUTE_TIMEOUTS: Dict[str, int] = {
    '/api/chat/message': 30,
    '/api/upload/': 120,
    '/api/training/': 30,
    '/api/knowledge/': 60,
}


def get_timeout_for_route(path: str) -> int:
    """Get timeout in seconds for a specific route."""
    for prefix, timeout in ROUTE_TIMEOUTS.items():
        if path.startswith(prefix):
            return timeout
    return 30  # Default 30 seconds


def memory_limit_check(max_content_length: int = 10 * 1024 * 1024):
    """
    Middleware to check request content length.
    
    Args:
        max_content_length: Maximum allowed content length in bytes
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.content_length and request.content_length > max_content_length:
                return jsonify({
                    'error': 'Request too large',
                    'max_size_mb': max_content_length / (1024 * 1024)
                }), 413
            return func(*args, **kwargs)
        return wrapper
    return decorator
