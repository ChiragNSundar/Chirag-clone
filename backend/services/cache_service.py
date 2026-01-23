"""
Cache Service - Persistent disk-backed cache using diskcache.
Replaces in-memory dictionary with SQLite-based storage for robustness across restarts.
"""
import os
import hashlib
from typing import Any, Optional, Dict
from functools import wraps
import asyncio
from config import Config
from services.logger import get_logger

# Import diskcache
try:
    from diskcache import Cache
    DISK_CACHE_AVAILABLE = True
except ImportError:
    DISK_CACHE_AVAILABLE = False
    print("[WARN] diskcache not installed, falling back to dict")

logger = get_logger(__name__)

class CacheService:
    """Persistent cache service."""
    
    def __init__(self):
        """Initialize disk cache."""
        self.cache_dir = os.path.join(Config.DATA_DIR, 'cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if DISK_CACHE_AVAILABLE:
            # 1GB size limit, generic eviction
            self._cache = Cache(self.cache_dir, size_limit=1024 * 1024 * 1024)
            logger.info(f"💾 Persistent cache initialized at {self.cache_dir}")
        else:
            self._cache = {}
            logger.warning("⚠️ Using in-memory cache (not persistent)")
            
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if DISK_CACHE_AVAILABLE:
            return self._cache.get(key)
        else:
            return self._cache.get(key)
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache with TTL."""
        if DISK_CACHE_AVAILABLE:
            self._cache.set(key, value, expire=ttl_seconds)
        else:
            self._cache[key] = value
            # Note: In-memory fallback doesn't implement TTL without extra logic
            # Use diskcache for proper TTL support
            
    def invalidate(self, key: str) -> bool:
        """Remove specific key."""
        if DISK_CACHE_AVAILABLE:
            return self._cache.delete(key)
        else:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
            
    def clear(self) -> None:
        """Clear all cache."""
        self._cache.clear()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if DISK_CACHE_AVAILABLE:
            # diskcache specific stats
            return {
                'size_bytes': self._cache.volume(),
                'count': len(self._cache),
                'backend': 'diskcache'
            }
        else:
            return {
                'count': len(self._cache),
                'backend': 'memory'
            }

# Singleton
_cache_service = None

def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service

# Async-aware Decorator
def async_cached(ttl_seconds: int = 300, prefix: str = ''):
    """Async-compatible cache decorator."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            # Key generation
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_base = f"{prefix}:{func.__name__}" if prefix else func.__name__
            key = f"{key_base}:{cache._generate_key(*cache_args, **kwargs)}"
            
            # Check cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            # Store
            if result is not None:
                cache.set(key, result, ttl_seconds)
            return result
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cache = get_cache_service()
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_base = f"{prefix}:{func.__name__}" if prefix else func.__name__
            key = f"{key_base}:{cache._generate_key(*cache_args, **kwargs)}"
            
            result = cache.get(key)
            if result is not None:
                return result
                
            result = func(*args, **kwargs)
            
            if result is not None:
                cache.set(key, result, ttl_seconds)
            return result
            
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
