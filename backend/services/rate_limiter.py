"""
Rate Limiter Service - In-memory rate limiting for API endpoints.
Uses sliding window algorithm for accurate rate limiting.
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Tuple, Optional
from functools import wraps
from flask import request, jsonify


class RateLimiter:
    """Thread-safe sliding window rate limiter."""
    
    def __init__(self, default_limit: int = 60, default_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            default_limit: Default requests per window
            default_window: Default window size in seconds
        """
        self.default_limit = default_limit
        self.default_window = default_window
        self._requests = defaultdict(list)
        self._lock = Lock()
        
        # Endpoint-specific limits
        self._limits = {
            '/api/chat/message': (30, 60),     # 30 requests per minute
            '/api/upload/': (10, 60),          # 10 uploads per minute
            '/api/training/': (60, 60),        # 60 training ops per minute
        }
    
    def _get_client_id(self) -> str:
        """Get unique identifier for the client."""
        # Use IP + User-Agent for identification
        ip = request.remote_addr or '127.0.0.1'
        ua = request.user_agent.string[:100] if request.user_agent else ''
        return f"{ip}:{hash(ua) % 10000}"
    
    def _get_limit_for_path(self, path: str) -> Tuple[int, int]:
        """Get rate limit for a specific path."""
        for prefix, limits in self._limits.items():
            if path.startswith(prefix):
                return limits
        return (self.default_limit, self.default_window)
    
    def _clean_old_requests(self, client_id: str, path: str, window: int) -> None:
        """Remove expired request timestamps."""
        key = f"{client_id}:{path}"
        cutoff = time.time() - window
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]
    
    def is_allowed(self, path: Optional[str] = None) -> Tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, rate_limit_info dict)
        """
        if path is None:
            path = request.path
        
        client_id = self._get_client_id()
        limit, window = self._get_limit_for_path(path)
        key = f"{client_id}:{path}"
        
        with self._lock:
            self._clean_old_requests(client_id, path, window)
            current_count = len(self._requests[key])
            
            if current_count >= limit:
                # Calculate reset time
                oldest = self._requests[key][0] if self._requests[key] else time.time()
                reset_in = int(oldest + window - time.time())
                
                return False, {
                    'limit': limit,
                    'remaining': 0,
                    'reset': reset_in,
                    'window': window
                }
            
            # Record this request
            self._requests[key].append(time.time())
            
            return True, {
                'limit': limit,
                'remaining': limit - current_count - 1,
                'reset': window,
                'window': window
            }
    
    def get_headers(self, rate_info: dict) -> dict:
        """Generate rate limit headers for response."""
        return {
            'X-RateLimit-Limit': str(rate_info['limit']),
            'X-RateLimit-Remaining': str(rate_info['remaining']),
            'X-RateLimit-Reset': str(rate_info['reset'])
        }


# Singleton instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def rate_limit(f):
    """Decorator to apply rate limiting to a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        limiter = get_rate_limiter()
        allowed, rate_info = limiter.is_allowed()
        
        if not allowed:
            response = jsonify({
                'error': 'Rate limit exceeded. Please try again later.',
                'retry_after': rate_info['reset']
            })
            response.status_code = 429
            for header, value in limiter.get_headers(rate_info).items():
                response.headers[header] = value
            return response
        
        # Execute the route
        response = f(*args, **kwargs)
        
        # Add rate limit headers to successful responses
        if hasattr(response, 'headers'):
            for header, value in limiter.get_headers(rate_info).items():
                response.headers[header] = value
        
        return response
    
    return decorated_function
