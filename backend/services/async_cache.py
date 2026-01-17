"""
Async Cache Decorator - High-performance async caching with request coalescing.
Prevents thundering herd problem when multiple requests for same data arrive simultaneously.
"""
import asyncio
import hashlib
import time
from functools import wraps
from typing import Any, Optional, Dict, Callable, TypeVar
from dataclasses import dataclass, field

from services.cache_service import get_cache_service
from services.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class CacheOptions:
    """Options for async caching."""
    ttl_seconds: int = 300
    prefix: str = ''
    skip_none: bool = True  # Don't cache None results
    stale_while_revalidate: int = 0  # Serve stale while refreshing


class AsyncCacheManager:
    """
    Manages async caching with request coalescing.
    When multiple requests arrive for the same key, only one fetch happens.
    """
    
    def __init__(self):
        self._pending: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_fetch(
        self,
        key: str,
        fetcher: Callable[[], Any],
        options: CacheOptions
    ) -> Any:
        """
        Get from cache or fetch with coalescing.
        
        If a request for this key is already in-flight, wait for it.
        Otherwise, fetch and cache the result.
        """
        cache = get_cache_service()
        full_key = f"{options.prefix}:{key}" if options.prefix else key
        
        # Check cache first
        cached = cache.get(full_key)
        if cached is not None:
            return cached
        
        async with self._lock:
            # Check if request is already pending
            if full_key in self._pending:
                # Wait for the pending request
                return await self._pending[full_key]
            
            # Create a future for this request
            future = asyncio.get_event_loop().create_future()
            self._pending[full_key] = future
        
        try:
            # Execute the fetcher
            if asyncio.iscoroutinefunction(fetcher):
                result = await fetcher()
            else:
                result = await asyncio.to_thread(fetcher)
            
            # Cache the result
            if result is not None or not options.skip_none:
                cache.set(full_key, result, options.ttl_seconds)
            
            # Resolve the future
            future.set_result(result)
            return result
            
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._pending.pop(full_key, None)


# Singleton instance
_cache_manager: Optional[AsyncCacheManager] = None


def get_async_cache_manager() -> AsyncCacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = AsyncCacheManager()
    return _cache_manager


def async_cache(
    ttl_seconds: int = 300,
    prefix: str = '',
    skip_none: bool = True
):
    """
    Async cache decorator with request coalescing.
    
    Usage:
        @async_cache(ttl_seconds=60, prefix='user')
        async def get_user(user_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Generate cache key from function name and arguments
            key_data = f"{func.__module__}.{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            key = hashlib.md5(key_data.encode()).hexdigest()
            
            options = CacheOptions(
                ttl_seconds=ttl_seconds,
                prefix=prefix,
                skip_none=skip_none
            )
            
            manager = get_async_cache_manager()
            return await manager.get_or_fetch(key, lambda: func(*args, **kwargs), options)
        
        return wrapper
    return decorator


def timed_cache(ttl_seconds: int = 60):
    """
    Simple time-based cache decorator for sync functions.
    Uses in-memory dict with expiration checking.
    """
    cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = f"{str(args)}:{str(sorted(kwargs.items()))}"
            
            # Check cache
            if key in cache:
                value, expiry = cache[key]
                if time.time() < expiry:
                    return value
                del cache[key]
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache[key] = (result, time.time() + ttl_seconds)
            return result
        
        # Add cache control methods
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_info = lambda: {'size': len(cache)}
        
        return wrapper
    return decorator


def invalidate_cache(prefix: str = '', pattern: str = ''):
    """
    Invalidate cache entries matching prefix or pattern.
    
    Usage:
        invalidate_cache(prefix='user')  # Clear all user-related cache
    """
    cache = get_cache_service()
    
    if prefix:
        count = cache.invalidate_pattern(prefix)
        logger.info(f"Invalidated {count} cache entries with prefix '{prefix}'")
        return count
    
    return 0
