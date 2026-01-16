"""
HTTP Client Pool - Optimized aiohttp session management with connection pooling.
Provides reusable HTTP sessions with automatic retry, timeouts, and cleanup.
"""
import asyncio
import aiohttp
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from services.logger import get_logger

logger = get_logger(__name__)


class HTTPClientPool:
    """
    Singleton HTTP client pool with connection reuse.
    
    Features:
    - Connection pooling (reuses TCP connections)
    - Automatic retry with exponential backoff
    - Request timeouts
    - Graceful cleanup on shutdown
    """
    
    _instance: Optional['HTTPClientPool'] = None
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create the shared aiohttp session."""
        async with self._lock:
            if self._session is None or self._session.closed:
                # Connection pool settings
                connector = aiohttp.TCPConnector(
                    limit=100,              # Max connections total
                    limit_per_host=20,      # Max per host
                    ttl_dns_cache=300,      # DNS cache TTL (5 min)
                    enable_cleanup_closed=True
                )
                
                # Default timeout configuration
                timeout = aiohttp.ClientTimeout(
                    total=30,       # Total request timeout
                    connect=10,     # Connection establish timeout
                    sock_read=10    # Socket read timeout
                )
                
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers={
                        "User-Agent": "ChiragClone/2.3 (Brain Station)"
                    }
                )
                logger.info("Created new HTTP connection pool")
            
            return self._session
    
    async def close(self):
        """Close the session and release connections."""
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                logger.info("Closed HTTP connection pool")
                self._session = None
    
    async def request(
        self,
        method: str,
        url: str,
        retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make an HTTP request with automatic retry.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            retries: Number of retry attempts
            retry_delay: Initial delay between retries (doubles each attempt)
            **kwargs: Additional aiohttp request arguments
            
        Returns:
            aiohttp.ClientResponse
            
        Raises:
            aiohttp.ClientError after all retries exhausted
        """
        session = await self.get_session()
        last_error = None
        
        for attempt in range(retries + 1):
            try:
                response = await session.request(method, url, **kwargs)
                
                # Retry on server errors (5xx)
                if response.status >= 500 and attempt < retries:
                    logger.warning(f"Server error {response.status}, retrying ({attempt + 1}/{retries})")
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                
                return response
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < retries:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"Request failed: {e}, retrying in {delay}s ({attempt + 1}/{retries})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Request failed after {retries + 1} attempts: {e}")
        
        raise last_error
    
    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Convenience method for GET requests."""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Convenience method for POST requests."""
        return await self.request("POST", url, **kwargs)
    
    async def fetch_json(self, url: str, **kwargs) -> Dict[str, Any]:
        """Fetch URL and parse JSON response."""
        response = await self.get(url, **kwargs)
        async with response:
            return await response.json()
    
    async def fetch_text(self, url: str, **kwargs) -> str:
        """Fetch URL and return text content."""
        response = await self.get(url, **kwargs)
        async with response:
            return await response.text()


# Singleton accessor
_http_pool: Optional[HTTPClientPool] = None


def get_http_pool() -> HTTPClientPool:
    """Get the singleton HTTP client pool."""
    global _http_pool
    if _http_pool is None:
        _http_pool = HTTPClientPool()
    return _http_pool


async def cleanup_http_pool():
    """Cleanup function to be called on app shutdown."""
    global _http_pool
    if _http_pool:
        await _http_pool.close()
        _http_pool = None


@asynccontextmanager
async def http_session():
    """
    Context manager for one-off HTTP sessions.
    Use this for isolated requests that shouldn't share the pool.
    """
    session = aiohttp.ClientSession()
    try:
        yield session
    finally:
        await session.close()
