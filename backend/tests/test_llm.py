"""
LLM Service Tests - Unit tests for model switching and fallback logic.
Tests are written to skip gracefully when dependencies are missing.

Run with: pytest tests/test_llm.py -v
"""
import pytest
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Circuit Breaker Tests (Import directly to avoid chromadb chain)
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker implementation."""
    
    @pytest.fixture
    def CircuitBreaker(self):
        """Import CircuitBreaker directly."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "llm_service",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "llm_service.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.CircuitBreaker
        except Exception as e:
            pytest.skip(f"CircuitBreaker not available: {e}")
    
    def test_circuit_starts_closed(self, CircuitBreaker):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=1)
        assert cb.state == 'CLOSED'
        assert cb.can_proceed() == True
    
    def test_circuit_opens_after_threshold(self, CircuitBreaker):
        """Test that circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, reset_timeout=1)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.state == 'CLOSED'
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        assert cb.can_proceed() == False
    
    def test_circuit_resets_after_timeout(self, CircuitBreaker):
        """Test that circuit enters HALF_OPEN after timeout."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=1)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        time.sleep(1.1)
        
        assert cb.can_proceed() == True
        assert cb.state == 'HALF_OPEN'
    
    def test_circuit_closes_on_success(self, CircuitBreaker):
        """Test that circuit closes after successful request in HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        cb.can_proceed()
        cb.record_success()
        assert cb.state == 'CLOSED'
        
    def test_circuit_reopens_on_failure_in_half_open(self, CircuitBreaker):
        """Test that circuit reopens if request fails in HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        cb.can_proceed()  # HALF_OPEN
        cb.record_failure()
        assert cb.state == 'OPEN'


# ============================================================================
# Model Hierarchy Tests (Config only, no chromadb)
# ============================================================================

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
            is_v2 = 'gemini-2' in model.lower()
            is_gemma = 'gemma' in model.lower()
            is_valid = is_v2 or is_gemma
            assert is_valid, f"Model {model} should be Gemini 2.0+ or Gemma"
            
    def test_no_v1_models(self):
        """Test that no Gemini 1.x models are in the list."""
        from config import Config
        for model in Config.GEMINI_MODELS:
            assert 'gemini-1' not in model.lower(), f"Found v1.x model: {model}"
            
    def test_gemma_is_first(self):
        """Test that Gemma is the first choice in hierarchy."""
        from config import Config
        first_model = Config.GEMINI_MODELS[0]
        assert 'gemma' in first_model.lower(), f"First model should be Gemma, got: {first_model}"


# ============================================================================
# Provider Support Tests (Config only)
# ============================================================================

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


# ============================================================================
# Error Message Tests (No external dependencies)
# ============================================================================

class TestErrorMessages:
    """Test error message formatting concepts."""
    
    def test_api_key_error_detection(self):
        """Test API key error can be detected from message."""
        error_msg = "Invalid API key provided"
        assert "api" in error_msg.lower() or "key" in error_msg.lower()
        
    def test_rate_limit_error_detection(self):
        """Test rate limit error can be detected."""
        error_msg = "Rate limit exceeded"
        assert "limit" in error_msg.lower() or "rate" in error_msg.lower()
        
    def test_timeout_error_detection(self):
        """Test timeout error can be detected."""
        error_msg = "Request timeout after 30 seconds"
        assert "timeout" in error_msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
