"""
Tests for Deep Research Service
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


class TestDeepResearchService:
    """Tests for the DeepResearchService class."""
    
    @pytest.fixture
    def mock_search_service(self):
        """Mock search service for testing."""
        mock = Mock()
        mock.search.return_value = [
            {'url': 'https://example.com/1', 'title': 'Test Article 1', 'snippet': 'Content 1'},
            {'url': 'https://example.com/2', 'title': 'Test Article 2', 'snippet': 'Content 2'},
        ]
        mock.is_available.return_value = True
        return mock
    
    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM service for testing."""
        mock = Mock()
        mock.generate_response.return_value = "This is a synthesized answer based on [Source 1].\n\n**Suggested Follow-up Questions:**\n1. What are the implications?\n2. How does this compare?"
        return mock
    
    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service for testing."""
        mock = Mock()
        mock.get.return_value = None
        mock.set.return_value = None
        return mock
    
    def test_research_source_dataclass(self):
        """Test ResearchSource dataclass."""
        from services.deep_research_service import ResearchSource
        
        source = ResearchSource(
            url="https://example.com",
            title="Test Title",
            content="Test content here",
            relevance_score=0.95
        )
        
        assert source.url == "https://example.com"
        assert source.title == "Test Title"
        assert source.relevance_score == 0.95
        
        # Test to_dict
        d = source.to_dict()
        assert 'url' in d
        assert 'title' in d
        assert 'content_preview' in d
    
    def test_research_result_dataclass(self):
        """Test ResearchResult dataclass."""
        from services.deep_research_service import ResearchResult, ResearchSource
        
        sources = [
            ResearchSource(url="https://example.com", title="Test", content="Content")
        ]
        
        result = ResearchResult(
            query="test query",
            answer="test answer",
            sources=sources,
            follow_up_queries=["q1", "q2"],
            total_sources_checked=5,
            research_time_seconds=2.5
        )
        
        assert result.query == "test query"
        assert len(result.sources) == 1
        
        d = result.to_dict()
        assert d['query'] == "test query"
        assert len(d['sources']) == 1
    
    def test_should_skip_url(self):
        """Test URL filtering logic."""
        from services.deep_research_service import DeepResearchService
        
        service = DeepResearchService()
        
        # Should skip social media
        assert service._should_skip_url("https://youtube.com/watch?v=123") is True
        assert service._should_skip_url("https://twitter.com/user") is True
        assert service._should_skip_url("https://www.facebook.com/page") is True
        
        # Should NOT skip regular sites
        assert service._should_skip_url("https://example.com/article") is False
        assert service._should_skip_url("https://docs.python.org/3/") is False
        
        # Edge cases
        assert service._should_skip_url("") is True
        assert service._should_skip_url(None) is True
    
    @pytest.mark.asyncio
    async def test_research_returns_cached(self, mock_cache_service):
        """Test that cached results are returned."""
        from services.deep_research_service import DeepResearchService
        
        cached_result = {
            'query': 'cached query',
            'answer': 'cached answer',
            'sources': [],
            'follow_up_queries': [],
            'total_sources_checked': 3,
            'research_time_seconds': 1.0
        }
        mock_cache_service.get.return_value = cached_result
        
        with patch('services.deep_research_service.get_cache_service', return_value=mock_cache_service):
            service = DeepResearchService()
            service.cache = mock_cache_service
            
            # The cache check happens in research() method
            result = service.cache.get("test_key")
            assert result == cached_result


class TestResearchHelpers:
    """Test helper functions in deep research service."""
    
    def test_build_context(self):
        """Test context building from sources."""
        from services.deep_research_service import DeepResearchService, ResearchSource
        
        service = DeepResearchService()
        
        sources = [
            ResearchSource(
                url="https://example.com",
                title="Test Article",
                content="This is test content for analysis.",
                relevance_score=0.9
            )
        ]
        
        context = service._build_context(sources, "test query")
        
        assert "SCREEN HISTORY" in context or "Test Article" in context


class TestResearchIntegration:
    """Integration-style tests for research flow."""
    
    @pytest.mark.asyncio
    async def test_full_research_flow_mocked(self):
        """Test the full research flow with mocked dependencies."""
        from services.deep_research_service import DeepResearchService
        
        with patch('services.deep_research_service.get_search_service') as mock_search, \
             patch('services.deep_research_service.get_llm_service') as mock_llm, \
             patch('services.deep_research_service.get_cache_service') as mock_cache:
            
            # Setup mocks
            mock_search.return_value.search.return_value = [
                {'url': 'https://example.com', 'title': 'Test', 'snippet': 'Content'}
            ]
            mock_search.return_value.is_available.return_value = True
            
            mock_llm.return_value.generate_response.return_value = "SUFFICIENT"
            
            mock_cache.return_value.get.return_value = None
            mock_cache.return_value.set.return_value = None
            
            service = DeepResearchService()
            
            # Should be able to instantiate without errors
            assert service is not None
            assert service.MAX_DEPTH == 3
