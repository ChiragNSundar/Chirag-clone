"""
Circuit Breaker Tests - Fault tolerance patterns.

Run with: pytest tests/test_circuit_breaker.py -v
"""
import pytest
import os
import sys
import time
from unittest.mock import MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCircuitBreaker:
    """Test circuit breaker pattern implementation."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create CircuitBreaker for testing."""
        try:
            from services.circuit_breaker import CircuitBreaker, CircuitConfig
            config = CircuitConfig(failure_threshold=3, timeout_seconds=0.2)
            return CircuitBreaker("test-circuit", config=config)
        except ImportError:
            pytest.skip("CircuitBreaker service not found")
    
    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit starts in CLOSED state."""
        from services.circuit_breaker import CircuitState
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._should_allow_request() == True
    
    def test_stays_closed_under_threshold(self, circuit_breaker):
        """Test circuit stays closed below failure threshold."""
        from services.circuit_breaker import CircuitState
        circuit_breaker._record_failure(Exception("test"))
        assert circuit_breaker.state == CircuitState.CLOSED
        
        circuit_breaker._record_failure(Exception("test"))
        assert circuit_breaker.state == CircuitState.CLOSED
    
    def test_opens_at_threshold(self, circuit_breaker):
        """Test circuit opens at failure threshold."""
        from services.circuit_breaker import CircuitState
        for _ in range(3):
            circuit_breaker._record_failure(Exception("test"))
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker._should_allow_request() == False
    
    def test_blocks_requests_when_open(self, circuit_breaker):
        """Test that open circuit blocks requests."""
        for _ in range(3):
            circuit_breaker._record_failure(Exception("test"))
        
        # Should block
        assert circuit_breaker._should_allow_request() == False
    
    def test_half_open_after_timeout(self):
        """Test circuit enters HALF_OPEN after timeout."""
        from services.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
        config = CircuitConfig(failure_threshold=1, timeout_seconds=0.5)
        cb = CircuitBreaker("test", config)
        
        cb._record_failure(Exception("test"))
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.6)
        
        # Should now allow a test request (transitions to HALF_OPEN)
        assert cb._should_allow_request() == True
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_closes_on_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN."""
        from services.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
        config = CircuitConfig(failure_threshold=1, timeout_seconds=0, success_threshold=1)
        cb = CircuitBreaker("test", config)
        
        cb._record_failure(Exception("test"))
        cb._should_allow_request()  # Trigger potential transition if timeout passed
        # Since timeout is 0, it might transition immediately if logic checks time
        
        # Force HALF_OPEN for test if needed, or rely on logic
        cb.state = CircuitState.HALF_OPEN
        
        cb._record_success()
        
        assert cb.state == CircuitState.CLOSED
    
    def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens after failure in HALF_OPEN."""
        from services.circuit_breaker import CircuitBreaker, CircuitConfig, CircuitState
        config = CircuitConfig(failure_threshold=1, timeout_seconds=0)
        cb = CircuitBreaker("test", config)
        
        cb.state = CircuitState.HALF_OPEN
        cb._record_failure(Exception("test"))
        
        assert cb.state == CircuitState.OPEN
    
    def test_success_resets_failure_count(self, circuit_breaker):
        """Test success resets failure counter."""
        from services.circuit_breaker import CircuitState
        circuit_breaker._record_failure(Exception("test"))
        circuit_breaker._record_failure(Exception("test"))
        circuit_breaker._record_success()
        
        # Should reset, so one more failure shouldn't open (threshold 3)
        circuit_breaker._record_failure(Exception("test"))
        assert circuit_breaker.state == CircuitState.CLOSED


class TestCircuitBreakerStats:
    """Test circuit breaker statistics."""
    
    @pytest.fixture
    def circuit_breaker(self):
        from services.circuit_breaker import CircuitBreaker
        return CircuitBreaker("stats-test")
    
    def test_failure_count(self, circuit_breaker):
        """Test failure count tracking."""
        circuit_breaker._record_failure(Exception("test"))
        circuit_breaker._record_failure(Exception("test"))
        
        assert circuit_breaker.stats.failed_calls == 2
    
    def test_success_count(self, circuit_breaker):
        """Test success count tracking."""
        circuit_breaker._record_success()
        circuit_breaker._record_success()
        
        assert circuit_breaker.stats.successful_calls == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
