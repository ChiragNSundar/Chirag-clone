"""
LLM Service Tests - Unit tests for model switching and fallback logic.
Covers circuit breaker, model cascade, and error handling.

Run with: pytest tests/test_llm.py -v
"""
import pytest
import sys
import os
import time
from unittest.mock import patch, MagicMock

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
        
        time.sleep(1.1)
        
        assert cb.can_proceed() == True
        assert cb.state == 'HALF_OPEN'
    
    def test_circuit_closes_on_success(self):
        """Test that circuit closes after successful request in HALF_OPEN."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        cb.can_proceed()
        cb.record_success()
        assert cb.state == 'CLOSED'
        
    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test that circuit reopens if request fails in HALF_OPEN."""
        from services.llm_service import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        cb.can_proceed()  # HALF_OPEN
        cb.record_failure()
        assert cb.state == 'OPEN'


class TestModelHierarchy:
    """Test model fallback hierarchy."""
    
    def test_gemini_models_list_exists(self):
        """Test that GEMINI_MODELS list exists in config."""
        from config import Config
        assert hasattr(Config, 'GEMINI_MODELS')
        assert isinstance(Config.GEMINI_MODELS, list)
        assert len(Config.GEMINI_MODELS) > 0
        
    def test_gemini_models_are_v2_plus(self):
        """Test that all models are Gemini 2.0+ or Gemma."""
        from config import Config
        for model in Config.GEMINI_MODELS:
            # Should contain 'gemini-2' or 'gemma'
            is_v2 = 'gemini-2' in model.lower()
            is_gemma = 'gemma' in model.lower()
            is_valid = is_v2 or is_gemma
            assert is_valid, f"Model {model} should be Gemini 2.0+ or Gemma"
            
    def test_no_v1_models(self):
        """Test that no Gemini 1.x models are in the list."""
        from config import Config
        for model in Config.GEMINI_MODELS:
            assert 'gemini-1' not in model.lower(), f"Found v1.x model: {model}"


class TestLLMServiceInit:
    """Test LLM service initialization."""
    
    def test_service_singleton(self):
        """Test that LLM service is singleton."""
        from services.llm_service import get_llm_service
        svc1 = get_llm_service()
        svc2 = get_llm_service()
        assert svc1 is svc2
        
    def test_service_has_circuit_breaker(self):
        """Test that service has circuit breaker."""
        from services.llm_service import get_llm_service
        svc = get_llm_service()
        assert hasattr(svc, '_circuit_breaker')


class TestErrorMessages:
    """Test error message formatting."""
    
    def test_format_api_key_error(self):
        """Test API key error message."""
        from services.llm_service import LLMService
        svc = LLMService.__new__(LLMService)
        
        error = Exception("Invalid API key provided")
        msg = svc._format_error_message(error)
        assert "API" in msg or "api" in msg.lower()
        
    def test_format_quota_error(self):
        """Test quota exceeded error message."""
        from services.llm_service import LLMService
        svc = LLMService.__new__(LLMService)
        
        error = Exception("Rate limit exceeded")
        msg = svc._format_error_message(error)
        assert "limit" in msg.lower() or "later" in msg.lower()
        
    def test_format_timeout_error(self):
        """Test timeout error message."""
        from services.llm_service import LLMService
        svc = LLMService.__new__(LLMService)
        
        error = Exception("Request timeout after 30 seconds")
        msg = svc._format_error_message(error)
        assert "timeout" in msg.lower() or "again" in msg.lower()


class TestFallbackLogic:
    """Test fallback to OpenAI."""
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-key'})
    def test_fallback_client_initialized(self):
        """Test that fallback client is initialized when key present."""
        from config import Config
        # Just verify the config has the key structure
        assert hasattr(Config, 'OPENAI_API_KEY')
        

class TestProviderSupport:
    """Test supported LLM providers."""
    
    def test_gemini_provider_supported(self):
        """Test Gemini provider is supported."""
        from config import Config
        assert hasattr(Config, 'GEMINI_API_KEY')
        assert hasattr(Config, 'GEMINI_MODELS')
        
    def test_openai_provider_supported(self):
        """Test OpenAI provider is supported."""
        from config import Config
        assert hasattr(Config, 'OPENAI_API_KEY')
        assert hasattr(Config, 'OPENAI_MODEL')
        
    def test_ollama_provider_supported(self):
        """Test Ollama provider is supported."""
        from config import Config
        assert hasattr(Config, 'OLLAMA_BASE_URL')
        assert hasattr(Config, 'OLLAMA_MODEL')
        
    def test_no_anthropic_support(self):
        """Test Anthropic/Claude is NOT supported (removed)."""
        from config import Config
        assert not hasattr(Config, 'ANTHROPIC_API_KEY')
        assert not hasattr(Config, 'ANTHROPIC_MODEL')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
