"""
Search Service - Web search integration for real-time information.
Uses DuckDuckGo for free web search with caching support.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
from services.cache_service import get_cache_service


class SearchService:
    """Service for web search to provide real-time information."""
    
    # Keywords that suggest a query needs web search
    SEARCH_TRIGGER_KEYWORDS = [
        'latest', 'news', 'current', 'today', 'yesterday', 'recent',
        'weather', 'stock', 'price', 'score', 'result', 'update',
        'what happened', 'who won', 'when is', 'where is',
        'how much', 'trending', '2024', '2025', 'now'
    ]
    
    # Topics that don't need web search (personal/general knowledge)
    PERSONAL_TOPICS = [
        'you', 'your', 'yourself', 'i ', 'me ', 'my ', 'myself',
        'favorite', 'like', 'love', 'hate', 'think', 'feel', 'opinion'
    ]
    
    def __init__(self):
        self._ddg_available = None
        self._init_error = None
    
    def _check_ddg(self) -> bool:
        """Check if DuckDuckGo search is available."""
        if self._ddg_available is not None:
            return self._ddg_available
        
        try:
            from duckduckgo_search import DDGS
            self._ddg_available = True
        except ImportError:
            self._ddg_available = False
            self._init_error = "duckduckgo-search not installed"
            print("Web search disabled. Install with: pip install duckduckgo-search")
        
        return self._ddg_available
    
    def should_search(self, query: str) -> bool:
        """
        Determine if a query needs web search.
        
        Args:
            query: The user's message
            
        Returns:
            True if web search would be helpful
        """
        query_lower = query.lower()
        
        # Skip if it's a personal question
        if any(topic in query_lower for topic in self.PERSONAL_TOPICS):
            return False
        
        # Check for search trigger keywords
        for keyword in self.SEARCH_TRIGGER_KEYWORDS:
            if keyword in query_lower:
                return True
        
        # Check for question patterns about facts
        fact_patterns = [
            r'^who (is|was|are|were)\b',
            r'^what (is|are|was|were)\b',
            r'^when (did|does|will|is)\b',
            r'^where (is|are|did)\b',
            r'^how (many|much|old|long)\b',
        ]
        
        for pattern in fact_patterns:
            if re.match(pattern, query_lower):
                # But skip personal questions
                if 'you' in query_lower or 'your' in query_lower:
                    return False
                return True
        
        return False
    
    def search(
        self,
        query: str,
        max_results: int = 3,
        region: str = "wt-wt"
    ) -> List[Dict]:
        """
        Perform a web search with caching.
        
        Args:
            query: The search query
            max_results: Maximum number of results
            region: Region code (wt-wt = worldwide)
            
        Returns:
            List of search results with title, snippet, url
        """
        if not self._check_ddg():
            return []
        
        # Check cache first (10 minute TTL for search results)
        cache = get_cache_service()
        cache_key = f"search:{query}:{max_results}:{region}"
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            return cached_results
        
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for result in ddgs.text(query, region=region, max_results=max_results):
                    results.append({
                        'title': result.get('title', ''),
                        'snippet': result.get('body', ''),
                        'url': result.get('href', ''),
                        'source': self._extract_domain(result.get('href', ''))
                    })
            
            # Cache results for 10 minutes
            if results:
                cache.set(cache_key, results, ttl_seconds=600)
            
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def search_news(
        self,
        query: str,
        max_results: int = 3
    ) -> List[Dict]:
        """
        Search for news specifically.
        
        Args:
            query: The search query
            max_results: Maximum number of results
            
        Returns:
            List of news results
        """
        if not self._check_ddg():
            return []
        
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for result in ddgs.news(query, max_results=max_results):
                    results.append({
                        'title': result.get('title', ''),
                        'snippet': result.get('body', ''),
                        'url': result.get('url', ''),
                        'source': result.get('source', ''),
                        'date': result.get('date', '')
                    })
            
            return results
            
        except Exception as e:
            print(f"News search error: {e}")
            return []
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return url[:30] if url else ''
    
    def format_for_llm(self, results: List[Dict], query: str) -> str:
        """
        Format search results for injection into LLM prompt.
        
        Args:
            results: List of search result dictionaries
            query: Original search query
            
        Returns:
            Formatted string for system prompt
        """
        if not results:
            return ""
        
        formatted = f"WEB SEARCH RESULTS for '{query}':\n"
        formatted += "-" * 40 + "\n"
        
        for i, result in enumerate(results, 1):
            formatted += f"{i}. [{result.get('source', 'Source')}] {result['title']}\n"
            formatted += f"   {result['snippet'][:200]}...\n"
            formatted += f"   URL: {result['url']}\n\n"
        
        formatted += "-" * 40 + "\n"
        formatted += "Use this information to answer the question. Cite sources when using specific facts.\n"
        
        return formatted
    
    def format_citations(self, results: List[Dict]) -> List[Dict]:
        """
        Format results as citations for frontend display.
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            List of citation dictionaries
        """
        citations = []
        for result in results:
            citations.append({
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'source': result.get('source', '')
            })
        return citations
    
    def is_available(self) -> bool:
        """Check if search service is available."""
        return self._check_ddg()


# Singleton instance
_search_service = None

def get_search_service() -> SearchService:
    """Get the singleton search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
