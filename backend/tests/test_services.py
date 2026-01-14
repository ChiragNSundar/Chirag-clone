"""
Service Tests - Unit tests for service layer error handling and edge cases.
Run with: python -m pytest tests/test_services.py -v
"""
import pytest
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCircuitBreaker:
    """Test circuit breaker implementation."""
    
    def test_circuit_starts_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=1)
        assert cb.state == 'CLOSED'
        assert cb.can_proceed() == True
    
    def test_circuit_opens_after_threshold(self):
        """Test that circuit opens after reaching failure threshold."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=1)
        
        # Record failures
        cb.record_failure()
        cb.record_failure()
        assert cb.state == 'CLOSED'
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        assert cb.can_proceed() == False
    
    def test_circuit_resets_after_timeout(self):
        """Test that circuit enters HALF_OPEN after timeout."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=1)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        # Wait for reset timeout
        time.sleep(1.1)
        
        # Should be able to proceed (enters HALF_OPEN)
        assert cb.can_proceed() == True
        assert cb.state == 'HALF_OPEN'
    
    def test_circuit_closes_on_success(self):
        """Test that circuit closes after successful request in HALF_OPEN."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        cb.can_proceed()  # Transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == 'CLOSED'


class TestRateLimiter:
    """Test rate limiter implementation."""
    
    @pytest.fixture
    def mock_request(self):
        """Create mock request context for testing."""
        from unittest.mock import MagicMock, patch
        mock_req = MagicMock()
        mock_req.path = '/api/test'
        mock_req.remote_addr = '127.0.0.1'
        mock_req.user_agent.string = 'TestAgent'
        return mock_req
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter can be initialized."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter(default_limit=5, default_window=60)
        assert limiter.default_limit == 5
        assert limiter.default_window == 60
    
    def test_rate_limiter_has_limits_dict(self):
        """Test rate limiter has endpoint-specific limits."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter()
        assert hasattr(limiter, '_limits')
        assert isinstance(limiter._limits, dict)
        
    def test_headers_generation(self):
        """Test that rate limit headers are generated correctly."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter(default_limit=10, default_window=60)
        
        rate_info = {'limit': 10, 'remaining': 5, 'reset': 30, 'window': 60}
        headers = limiter.get_headers(rate_info)
        
        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers
        assert headers['X-RateLimit-Limit'] == '10'


class TestMemoryServiceResilience:
    """Test memory service error handling."""
    
    def test_find_similar_handles_errors(self):
        """Test that find_similar_examples returns empty list on error."""
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        
        # Should not crash, should return empty list
        result = memory.find_similar_examples("")
        assert isinstance(result, list)
    
    def test_get_training_stats_handles_errors(self):
        """Test that get_training_stats returns default values on error."""
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        
        stats = memory.get_training_stats()
        assert 'total_examples' in stats
        assert 'sources' in stats
    
    def test_get_conversation_history_empty(self):
        """Test getting history for non-existent session."""
        from services.memory_service import get_memory_service
        memory = get_memory_service()
        
        history = memory.get_conversation_history('non_existent_session_12345')
        assert isinstance(history, list)


class TestPersonalityServiceResilience:
    """Test personality service error handling."""
    
    def test_service_loads(self):
        """Test that personality service loads without crashing."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        assert service is not None
    
    def test_get_profile_returns_defaults(self):
        """Test that get_profile returns valid profile."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        profile = service.get_profile()
        
        assert profile is not None
        assert hasattr(profile, 'name')
        assert hasattr(profile, 'facts')
    
    def test_system_prompt_generation(self):
        """Test that system prompt is generated."""
        from services.personality_service import get_personality_service
        service = get_personality_service()
        prompt = service.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestSearchServiceResilience:
    """Test search service error handling."""
    
    def test_should_search_personal_questions(self):
        """Test that personal questions don't trigger search."""
        from services.search_service import get_search_service
        search = get_search_service()
        
        assert search.should_search("What is your favorite color?") == False
        assert search.should_search("Tell me about yourself") == False
    
    def test_should_search_factual_questions(self):
        """Test that factual questions trigger search."""
        from services.search_service import get_search_service
        search = get_search_service()
        
        assert search.should_search("What is the latest news today?") == True
        assert search.should_search("What is the current stock price?") == True
    
    def test_search_handles_errors(self):
        """Test that search returns empty list on error."""
        from services.search_service import get_search_service
        search = get_search_service()
        
        # Should return empty list if DDG is unavailable
        result = search.search("")
        assert isinstance(result, list)


class TestInputValidation:
    """Test input validation utilities."""
    
    def test_message_sanitization_concept(self):
        """Test basic string sanitization concept."""
        # Basic sanitization test without Flask dependency
        test_input = "Hello World"
        assert len(test_input.strip()) > 0
        
    def test_session_id_length_validation(self):
        """Test session ID length validation concept."""
        # Valid session IDs should be reasonable length
        valid_id = "abc-123"
        too_long = "a" * 200
        
        assert len(valid_id) < 100
        assert len(too_long) > 100  # Would be rejected


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_validate_config_returns_list(self):
        """Test that validate_config returns a list."""
        from config import validate_config
        warnings = validate_config()
        assert isinstance(warnings, list)
    
    def test_config_has_required_attrs(self):
        """Test that Config has required attributes."""
        from config import Config
        
        # Required attributes
        assert hasattr(Config, 'GEMINI_API_KEY')
        assert hasattr(Config, 'LLM_PROVIDER')
        assert hasattr(Config, 'DATA_DIR')
        assert hasattr(Config, 'MAX_MESSAGE_LENGTH')
        assert hasattr(Config, 'LLM_RETRY_COUNT')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
