"""
Cache Service - Thread-safe in-memory caching with LRU eviction and TTL.
Provides response caching for LLM, search, and other expensive operations.
"""
import time
import hashlib
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional, Dict
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: float
    created_at: float


class CacheService:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            max_size: Maximum number of entries (LRU eviction when exceeded)
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _evict_expired(self) -> int:
        """Remove expired entries. Returns count of evicted items."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if v.expires_at < now]
        for key in expired:
            del self._cache[key]
        return len(expired)
    
    def _evict_lru(self) -> None:
        """Remove least recently used entries if over max size."""
        while len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._misses += 1
                return None
            
            if entry.expires_at < time.time():
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (default 5 minutes)
        """
        with self._lock:
            now = time.time()
            
            # Evict expired and LRU if needed
            self._evict_expired()
            self._evict_lru()
            
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=now + ttl_seconds,
                created_at=now
            )
            self._cache.move_to_end(key)
    
    def invalidate(self, key: str) -> bool:
        """
        Remove specific key from cache.
        
        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_pattern(self, prefix: str) -> int:
        """
        Remove all keys matching prefix.
        
        Returns:
            Count of removed keys
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate, 2)
            }


# Singleton instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get singleton cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(max_size=1000)
    return _cache_service


# Cache decorator for functions
def cached(ttl_seconds: int = 300, prefix: str = ''):
    """
    Decorator to cache function results.
    
    Args:
        ttl_seconds: Cache TTL in seconds
        prefix: Key prefix for cache organization
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            # Generate cache key
            key_base = f"{prefix}:{func.__name__}" if prefix else func.__name__
            key = f"{key_base}:{cache._generate_key(*args, **kwargs)}"
            
            # Try cache first
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache.set(key, result, ttl_seconds)
            return result
        
        return wrapper
    return decorator


# Async-aware cache decorator
import asyncio
from functools import wraps

def async_cached(ttl_seconds: int = 300, prefix: str = ''):
    """
    Async-compatible cache decorator for both sync and async functions.
    
    Args:
        ttl_seconds: Cache TTL in seconds
        prefix: Key prefix for cache organization
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            # Generate cache key (exclude 'self' from key generation)
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_base = f"{prefix}:{func.__name__}" if prefix else func.__name__
            key = f"{key_base}:{cache._generate_key(*cache_args, **kwargs)}"
            
            # Try cache first
            result = cache.get(key)
            if result is not None:
                return result
            
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            # Cache result (don't cache None or empty results)
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
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator

