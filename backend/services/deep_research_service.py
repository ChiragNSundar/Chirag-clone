"""
Deep Research Service - Agentic multi-step web research with source synthesis.
Recursively searches the web, scrapes pages, and generates comprehensive answers with citations.
"""
import asyncio
import re
import hashlib
from typing import Optional, Dict, List, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin

from services.logger import get_logger
from services.search_service import get_search_service
from services.llm_service import get_llm_service
from services.cache_service import get_cache_service

logger = get_logger(__name__)

# ============= Dependencies =============

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    logger.warning("aiohttp not installed. Deep research will be slower.")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.warning("beautifulsoup4 not installed. Page scraping disabled.")


@dataclass
class ResearchSource:
    """A source document used in research."""
    url: str
    title: str
    content: str
    relevance_score: float = 0.0
    scraped_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'title': self.title,
            'content_preview': self.content[:500] + '...' if len(self.content) > 500 else self.content,
            'relevance_score': self.relevance_score,
            'scraped_at': self.scraped_at.isoformat()
        }


@dataclass  
class ResearchResult:
    """Complete research result with answer and sources."""
    query: str
    answer: str
    sources: List[ResearchSource]
    follow_up_queries: List[str]
    total_sources_checked: int
    research_time_seconds: float
    
    def to_dict(self) -> Dict:
        return {
            'query': self.query,
            'answer': self.answer,
            'sources': [s.to_dict() for s in self.sources],
            'follow_up_queries': self.follow_up_queries,
            'total_sources_checked': self.total_sources_checked,
            'research_time_seconds': self.research_time_seconds
        }


class DeepResearchService:
    """
    Agentic deep research service that:
    1. Searches the web for relevant sources
    2. Scrapes and extracts content from top results
    3. Generates follow-up queries if needed
    4. Synthesizes a comprehensive answer with citations
    """
    
    # Configuration
    MAX_DEPTH = 3  # Maximum recursive search depth
    MAX_SOURCES_PER_QUERY = 5  # Sources to scrape per search
    MAX_CONTENT_LENGTH = 8000  # Max chars per source
    REQUEST_TIMEOUT = 10  # Seconds
    
    # Domains to skip (ads, paywalls, etc.)
    SKIP_DOMAINS = {
        'youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
        'tiktok.com', 'pinterest.com', 'linkedin.com', 'reddit.com'
    }
    
    def __init__(self):
        self.search_service = get_search_service()
        self.llm_service = get_llm_service()
        self.cache = get_cache_service()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> 'aiohttp.ClientSession':
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.REQUEST_TIMEOUT)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; ChiragClone/2.4)'}
            )
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # ============= Core Research Flow =============
    
    async def research(
        self,
        query: str,
        max_depth: int = None,
        progress_callback: Optional[callable] = None
    ) -> ResearchResult:
        """
        Perform deep research on a query.
        
        Args:
            query: The research question
            max_depth: Maximum recursion depth (default: 3)
            progress_callback: Optional async callback for progress updates
            
        Returns:
            ResearchResult with answer and sources
        """
        start_time = datetime.now()
        max_depth = max_depth or self.MAX_DEPTH
        
        # Check cache
        cache_key = f"research:{hashlib.md5(query.encode()).hexdigest()}"
        cached = self.cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached research for: {query[:50]}...")
            return ResearchResult(**cached)
        
        if progress_callback:
            await progress_callback({'stage': 'starting', 'query': query})
        
        all_sources: List[ResearchSource] = []
        queries_searched = [query]
        
        # Recursive research loop
        for depth in range(max_depth):
            current_query = queries_searched[-1] if queries_searched else query
            
            if progress_callback:
                await progress_callback({
                    'stage': 'searching',
                    'depth': depth + 1,
                    'query': current_query
                })
            
            # Step 1: Search
            search_results = self.search_service.search(current_query, max_results=self.MAX_SOURCES_PER_QUERY)
            
            if not search_results:
                logger.warning(f"No search results for: {current_query}")
                break
            
            # Step 2: Scrape top results
            for result in search_results:
                url = result.get('url', '')
                if self._should_skip_url(url):
                    continue
                
                if progress_callback:
                    await progress_callback({
                        'stage': 'scraping',
                        'url': url,
                        'title': result.get('title', '')
                    })
                
                content = await self._scrape_page(url)
                if content:
                    source = ResearchSource(
                        url=url,
                        title=result.get('title', ''),
                        content=content[:self.MAX_CONTENT_LENGTH]
                    )
                    all_sources.append(source)
            
            # Step 3: Check if we have enough information
            if len(all_sources) >= 5:
                # Generate follow-up query if needed
                follow_up = await self._generate_follow_up_query(query, all_sources)
                if follow_up and follow_up not in queries_searched:
                    queries_searched.append(follow_up)
                else:
                    break  # No more follow-ups needed
            
            if depth >= max_depth - 1:
                break
        
        if progress_callback:
            await progress_callback({'stage': 'synthesizing', 'sources_count': len(all_sources)})
        
        # Step 4: Synthesize answer
        answer, follow_ups = await self._synthesize_answer(query, all_sources)
        
        research_time = (datetime.now() - start_time).total_seconds()
        
        result = ResearchResult(
            query=query,
            answer=answer,
            sources=all_sources[:10],  # Top 10 sources
            follow_up_queries=follow_ups,
            total_sources_checked=len(all_sources),
            research_time_seconds=research_time
        )
        
        # Cache for 1 hour
        self.cache.set(cache_key, result.to_dict(), ttl_seconds=3600)
        
        if progress_callback:
            await progress_callback({'stage': 'complete', 'result': result.to_dict()})
        
        return result
    
    async def research_stream(
        self,
        query: str,
        max_depth: int = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Stream research progress as events.
        
        Yields:
            Dict events with 'stage' and relevant data
        """
        events = []
        
        async def collect_events(event):
            events.append(event)
        
        # Run research with progress collection
        result = await self.research(query, max_depth, collect_events)
        
        # Yield all collected events
        for event in events:
            yield event
        
        # Final result
        yield {'stage': 'result', 'data': result.to_dict()}
    
    # ============= Page Scraping =============
    
    async def _scrape_page(self, url: str) -> Optional[str]:
        """
        Scrape and extract main content from a URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            Extracted text content or None
        """
        if not HAS_BS4:
            return None
        
        # Check cache first
        cache_key = f"page:{hashlib.md5(url.encode()).hexdigest()}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            if HAS_AIOHTTP:
                content = await self._fetch_async(url)
            else:
                content = self._fetch_sync(url)
            
            if not content:
                return None
            
            # Parse HTML
            soup = BeautifulSoup(content, 'lxml' if 'lxml' in str(type(BeautifulSoup)) else 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                element.decompose()
            
            # Try to find main content
            main_content = (
                soup.find('article') or 
                soup.find('main') or 
                soup.find(class_=re.compile(r'content|article|post|entry')) or
                soup.find('div', class_=re.compile(r'content|article|post|entry')) or
                soup.body
            )
            
            if main_content:
                text = main_content.get_text(separator='\n', strip=True)
                # Clean up whitespace
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r' {2,}', ' ', text)
                
                # Cache for 30 minutes
                self.cache.set(cache_key, text, ttl_seconds=1800)
                return text
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return None
    
    async def _fetch_async(self, url: str) -> Optional[str]:
        """Fetch URL content asynchronously."""
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
        except Exception as e:
            logger.debug(f"Async fetch failed for {url}: {e}")
        return None
    
    def _fetch_sync(self, url: str) -> Optional[str]:
        """Fetch URL content synchronously (fallback)."""
        try:
            import requests
            response = requests.get(url, timeout=self.REQUEST_TIMEOUT, 
                                    headers={'User-Agent': 'Mozilla/5.0 (compatible; ChiragClone/2.4)'})
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.debug(f"Sync fetch failed for {url}: {e}")
        return None
    
    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped."""
        if not url:
            return True
        try:
            domain = urlparse(url).netloc.lower()
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain in self.SKIP_DOMAINS
        except:
            return True
    
    # ============= LLM Integration =============
    
    async def _generate_follow_up_query(
        self,
        original_query: str,
        sources: List[ResearchSource]
    ) -> Optional[str]:
        """
        Generate a follow-up query to fill knowledge gaps.
        
        Args:
            original_query: The original research question
            sources: Sources collected so far
            
        Returns:
            Follow-up query or None if sufficient info
        """
        if not sources:
            return None
        
        source_summaries = "\n".join([
            f"- {s.title}: {s.content[:200]}..." 
            for s in sources[:5]
        ])
        
        prompt = f"""Based on the original question and sources found so far, determine if more research is needed.

ORIGINAL QUESTION: {original_query}

SOURCES FOUND:
{source_summaries}

If the sources adequately answer the question, respond with: SUFFICIENT

If more research is needed, respond with a single follow-up search query that would help fill the gaps.
Only output the follow-up query or SUFFICIENT, nothing else."""

        try:
            response = self.llm_service.generate_response(
                system_prompt="You are a research assistant that determines if more information is needed.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            response = response.strip()
            if response.upper() == "SUFFICIENT":
                return None
            return response
            
        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}")
            return None
    
    async def _synthesize_answer(
        self,
        query: str,
        sources: List[ResearchSource]
    ) -> tuple[str, List[str]]:
        """
        Synthesize a comprehensive answer from sources.
        
        Args:
            query: The research question
            sources: All collected sources
            
        Returns:
            Tuple of (answer, follow_up_questions)
        """
        if not sources:
            return "I couldn't find enough information to answer this question.", []
        
        # Prepare source context
        source_text = ""
        for i, source in enumerate(sources[:8], 1):  # Top 8 sources
            source_text += f"\n[Source {i}] {source.title}\nURL: {source.url}\n{source.content[:1500]}\n---\n"
        
        prompt = f"""You are a research assistant synthesizing information from multiple sources.

RESEARCH QUESTION: {query}

SOURCES:
{source_text}

INSTRUCTIONS:
1. Provide a comprehensive answer to the research question
2. Cite sources using [Source N] notation where relevant
3. Be objective and note any conflicting information
4. At the end, suggest 2-3 follow-up questions the user might want to explore

FORMAT:
Start with your synthesized answer, then add:

**Suggested Follow-up Questions:**
1. [question 1]
2. [question 2]
3. [question 3]"""

        try:
            response = self.llm_service.generate_response(
                system_prompt="You are a thorough research assistant that synthesizes information from multiple sources with proper citations.",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=2000
            )
            
            # Parse follow-up questions
            follow_ups = []
            if "**Suggested Follow-up Questions:**" in response:
                parts = response.split("**Suggested Follow-up Questions:**")
                answer = parts[0].strip()
                if len(parts) > 1:
                    follow_up_section = parts[1]
                    # Extract numbered questions
                    matches = re.findall(r'\d\.\s*(.+?)(?:\n|$)', follow_up_section)
                    follow_ups = [m.strip() for m in matches[:3]]
            else:
                answer = response
            
            return answer, follow_ups
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Research found {len(sources)} sources but synthesis failed.", []


# ============= Singleton =============

_deep_research_service: Optional[DeepResearchService] = None


def get_deep_research_service() -> DeepResearchService:
    """Get the singleton deep research service instance."""
    global _deep_research_service
    if _deep_research_service is None:
        _deep_research_service = DeepResearchService()
    return _deep_research_service
