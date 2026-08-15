"""
LLM Service Tests - Unit tests for LM Studio local LLM and fallback logic.

Run with: pytest tests/test_llm.py -v
"""
import pytest
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Circuit Breaker Tests
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


# ============================================================================
# Local Provider Tests (Config only)
# ============================================================================

class TestProviderSupport:
    """Test local LLM provider configuration."""
    
    def test_lmstudio_provider_supported(self):
        """Test LM Studio provider settings exist in config."""
        from config import Config
        assert hasattr(Config, 'LMSTUDIO_BASE_URL')
        assert hasattr(Config, 'LMSTUDIO_MODEL')
        assert Config.LLM_PROVIDER == 'lmstudio'
        
    def test_no_cloud_keys_required(self):
        """Test no cloud API keys exist in config."""
        from config import Config
        assert not hasattr(Config, 'GEMINI_API_KEY')
        assert not hasattr(Config, 'OPENAI_API_KEY')
        assert not hasattr(Config, 'ANTHROPIC_API_KEY')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
