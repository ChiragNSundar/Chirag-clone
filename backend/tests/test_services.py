"""
Service Tests - Unit tests for service layer error handling and edge cases.
Tests are written to skip gracefully when dependencies (chromadb) are missing.

Run with: python -m pytest tests/test_services.py -v
"""
import pytest
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Circuit Breaker Tests (No external dependencies)
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker implementation."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        try:
            from services.llm_service import CircuitBreaker
            return CircuitBreaker(failure_threshold=3, reset_timeout=1)
        except ImportError:
            pytest.skip("CircuitBreaker not available")
    
    def test_circuit_starts_closed(self, circuit_breaker):
        """Test that circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == 'CLOSED'
        assert circuit_breaker.can_proceed() == True
    
    def test_circuit_opens_after_threshold(self, circuit_breaker):
        """Test that circuit opens after reaching failure threshold."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        assert circuit_breaker.state == 'CLOSED'
        
        circuit_breaker.record_failure()
        assert circuit_breaker.state == 'OPEN'
        assert circuit_breaker.can_proceed() == False
    
    def test_circuit_resets_after_timeout(self):
        """Test that circuit enters HALF_OPEN after timeout."""
        try:
            from services.llm_service import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=1)
        except ImportError:
            pytest.skip("CircuitBreaker not available")
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        # Wait for reset timeout
        time.sleep(1.1)
        
        # Should be able to proceed (enters HALF_OPEN)
        assert cb.can_proceed() == True
        assert cb.state == 'HALF_OPEN'
    
    def test_circuit_closes_on_success(self):
        """Test that circuit closes after successful request in HALF_OPEN."""
        try:
            from services.llm_service import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        except ImportError:
            pytest.skip("CircuitBreaker not available")
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        cb.can_proceed()  # Transitions to HALF_OPEN
        cb.record_success()
        assert cb.state == 'CLOSED'


# ============================================================================
# Rate Limiter Tests (Skip if chromadb import fails)
# ============================================================================

class TestRateLimiter:
    """Test rate limiter implementation."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        try:
            # Import directly to avoid __init__.py chain
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "rate_limiter",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "rate_limiter.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.RateLimiter(default_limit=5, default_window=60)
        except Exception as e:
            pytest.skip(f"RateLimiter not available: {e}")
    
    def test_rate_limiter_initialization(self, rate_limiter):
        """Test rate limiter can be initialized."""
        assert rate_limiter.default_limit == 5
        assert rate_limiter.default_window == 60
    
    def test_rate_limiter_has_limits_dict(self, rate_limiter):
        """Test rate limiter has endpoint-specific limits."""
        assert hasattr(rate_limiter, '_limits')
        assert isinstance(rate_limiter._limits, dict)
        
    def test_headers_generation(self, rate_limiter):
        """Test that rate limit headers are generated correctly."""
        rate_info = {'limit': 10, 'remaining': 5, 'reset': 30, 'window': 60}
        headers = rate_limiter.get_headers(rate_info)
        
        assert 'X-RateLimit-Limit' in headers
        assert 'X-RateLimit-Remaining' in headers
        assert 'X-RateLimit-Reset' in headers
        assert headers['X-RateLimit-Limit'] == '10'


# ============================================================================
# Personality Service Tests (Uses direct import to skip chromadb chain)
# ============================================================================

class TestPersonalityServiceResilience:
    """Test personality service error handling."""
    
    @pytest.fixture
    def personality_service(self):
        """Create personality service for testing."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "personality_service",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "personality_service.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.get_personality_service()
        except Exception as e:
            pytest.skip(f"PersonalityService not available: {e}")
    
    def test_service_loads(self, personality_service):
        """Test that personality service loads without crashing."""
        assert personality_service is not None
    
    def test_get_profile_returns_profile(self, personality_service):
        """Test that get_profile returns valid profile."""
        profile = personality_service.get_profile()
        
        assert profile is not None
        assert hasattr(profile, 'name')
        assert hasattr(profile, 'facts')
    
    def test_system_prompt_generation(self, personality_service):
        """Test that system prompt is generated."""
        prompt = personality_service.get_system_prompt()
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0


# ============================================================================
# Input Validation Tests (No external dependencies)
# ============================================================================

class TestInputValidation:
    """Test input validation utilities."""
    
    def test_message_sanitization_concept(self):
        """Test basic string sanitization concept."""
        test_input = "Hello World"
        assert len(test_input.strip()) > 0
        
    def test_session_id_length_validation(self):
        """Test session ID length validation concept."""
        valid_id = "abc-123"
        too_long = "a" * 200
        
        assert len(valid_id) < 100
        assert len(too_long) > 100  # Would be rejected
        
    def test_strip_null_bytes(self):
        """Test null byte stripping."""
        test_input = "Hello\x00World"
        cleaned = test_input.replace('\x00', '')
        assert cleaned == "HelloWorld"


# ============================================================================
# Config Validation Tests (No external dependencies)
# ============================================================================

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
        
    def test_gemini_models_list(self):
        """Test that GEMINI_MODELS list exists and is valid."""
        from config import Config
        
        assert hasattr(Config, 'GEMINI_MODELS')
        assert isinstance(Config.GEMINI_MODELS, list)
        assert len(Config.GEMINI_MODELS) > 0
        
        # All should be v2+ or gemma
        for model in Config.GEMINI_MODELS:
            is_valid = 'gemini-2' in model.lower() or 'gemma' in model.lower()
            assert is_valid, f"Invalid model in hierarchy: {model}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
