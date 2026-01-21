"""
Rate Limiter Service - In-memory rate limiting for API endpoints.
Uses sliding window algorithm for accurate rate limiting.
Adapted for FastAPI.
"""
import time
from collections import defaultdict
from threading import Lock
from typing import Tuple, Optional, Callable
from functools import wraps
from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

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
    
    def _get_client_id(self, request: Request) -> str:
        """Get unique identifier for the client."""
        # Use IP + User-Agent for identification
        ip = request.client.host if request.client else '127.0.0.1'
        ua = request.headers.get('user-agent', '')[:100]
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
    
    def check_rate_limit(self, request: Request) -> Tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        
        Returns:
            Tuple of (is_allowed, rate_limit_info dict)
        """
        path = request.url.path
        
        client_id = self._get_client_id(request)
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
        """Generate headers dict from rate info."""
        return {
            'X-RateLimit-Limit': str(rate_info.get('limit', 0)),
            'X-RateLimit-Remaining': str(rate_info.get('remaining', 0)),
            'X-RateLimit-Reset': str(rate_info.get('reset', 0))
        }

# Singleton instance
_rate_limiter = RateLimiter()

def get_rate_limiter() -> RateLimiter:
    return _rate_limiter

FILTERED_PATHS = ["/health", "/docs", "/openapi.json", "/favicon.ico"]

async def rate_limit(request: Request, call_next):
    """
    Middleware for rate limiting.
    """
    path = request.url.path
    
    # Skip rate limiting for health checks and docs
    if any(path.startswith(p) for p in FILTERED_PATHS) or request.method == "OPTIONS":
        return await call_next(request)

    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit(request)
    
    if not allowed:
        response = Response(
            content=f'{{"error": "Rate limit exceeded. Try again in {rate_info["reset"]} seconds."}}', 
            status_code=429,
            media_type="application/json"
        )
        response.headers['X-RateLimit-Limit'] = str(rate_info['limit'])
        response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
        response.headers['X-RateLimit-Reset'] = str(rate_info['reset'])
        return response
    
    response = await call_next(request)
    
    # Add rate limit headers
    response.headers['X-RateLimit-Limit'] = str(rate_info['limit'])
    response.headers['X-RateLimit-Remaining'] = str(rate_info['remaining'])
    response.headers['X-RateLimit-Reset'] = str(rate_info['reset'])
    
    return response

# Legacy decorator support removed as it's not compatible with FastAPI async routes easily
# Use middleware instead
