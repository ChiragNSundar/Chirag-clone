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
    def app_context(self):
        """Create Flask app context for testing."""
        from app import app
        with app.test_request_context('/api/test'):
            yield
    
    def test_allows_requests_under_limit(self, app_context):
        """Test that requests under limit are allowed."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter(default_limit=5, default_window=60)
        
        for _ in range(5):
            allowed, _ = limiter.is_allowed('/api/test')
            assert allowed == True
    
    def test_blocks_requests_over_limit(self, app_context):
        """Test that requests over limit are blocked."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter(default_limit=3, default_window=60)
        
        for _ in range(3):
            limiter.is_allowed('/api/test')
        
        allowed, info = limiter.is_allowed('/api/test')
        assert allowed == False
        assert info['remaining'] == 0
    
    def test_headers_returned(self, app_context):
        """Test that rate limit headers are returned."""
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter(default_limit=10, default_window=60)
        
        _, info = limiter.is_allowed('/api/test')
        headers = limiter.get_headers(info)
        
        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers


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
    
    def test_sanitize_message_removes_control_chars(self):
        """Test that control characters are removed."""
        from routes.chat_routes import sanitize_message
        
        # Normal text should pass through
        assert sanitize_message("Hello World") == "Hello World"
        
        # Newlines should be preserved
        assert sanitize_message("Hello\nWorld") == "Hello\nWorld"
        
        # Null bytes should be removed
        assert sanitize_message("Hello\x00World") == "HelloWorld"
    
    def test_validate_session_id_format(self):
        """Test session ID validation."""
        from routes.chat_routes import validate_session_id
        
        # Valid session IDs
        assert validate_session_id("abc-123")[0] == True
        assert validate_session_id("test_session")[0] == True
        
        # Invalid session IDs
        assert validate_session_id("a" * 200)[0] == False  # Too long
        assert validate_session_id("test;DROP TABLE")[0] == False  # Invalid chars


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
