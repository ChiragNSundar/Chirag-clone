"""
Circuit Breaker Tests - Fault tolerance patterns.

Run with: pytest tests/test_circuit_breaker.py -v
"""
import pytest
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCircuitBreaker:
    """Test circuit breaker pattern implementation."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create CircuitBreaker for testing."""
        try:
            from services.circuit_breaker import CircuitBreaker
            return CircuitBreaker(failure_threshold=3, reset_timeout=1)
        except ImportError:
            try:
                from services.llm_service import CircuitBreaker
                return CircuitBreaker(failure_threshold=3, reset_timeout=1)
            except ImportError as e:
                pytest.skip(f"CircuitBreaker not available: {e}")
    
    def test_initial_state_closed(self, circuit_breaker):
        """Test circuit starts in CLOSED state."""
        assert circuit_breaker.state == 'CLOSED'
        assert circuit_breaker.can_proceed() == True
    
    def test_stays_closed_under_threshold(self, circuit_breaker):
        """Test circuit stays closed below failure threshold."""
        circuit_breaker.record_failure()
        assert circuit_breaker.state == 'CLOSED'
        
        circuit_breaker.record_failure()
        assert circuit_breaker.state == 'CLOSED'
    
    def test_opens_at_threshold(self, circuit_breaker):
        """Test circuit opens at failure threshold."""
        for _ in range(3):
            circuit_breaker.record_failure()
        
        assert circuit_breaker.state == 'OPEN'
        assert circuit_breaker.can_proceed() == False
    
    def test_blocks_requests_when_open(self, circuit_breaker):
        """Test that open circuit blocks requests."""
        for _ in range(3):
            circuit_breaker.record_failure()
        
        # Should block
        assert circuit_breaker.can_proceed() == False
    
    def test_half_open_after_timeout(self):
        """Test circuit enters HALF_OPEN after timeout."""
        try:
            from services.circuit_breaker import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.5)
        except ImportError:
            from services.llm_service import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0.5)
        
        cb.record_failure()
        assert cb.state == 'OPEN'
        
        time.sleep(0.6)
        
        # Should now allow a test request
        assert cb.can_proceed() == True
        assert cb.state == 'HALF_OPEN'
    
    def test_closes_on_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN."""
        try:
            from services.circuit_breaker import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        except ImportError:
            from services.llm_service import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        cb.can_proceed()  # Enter HALF_OPEN
        cb.record_success()
        
        assert cb.state == 'CLOSED'
    
    def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens after failure in HALF_OPEN."""
        try:
            from services.circuit_breaker import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        except ImportError:
            from services.llm_service import CircuitBreaker
            cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
        
        cb.record_failure()
        cb.can_proceed()  # Enter HALF_OPEN
        cb.record_failure()
        
        assert cb.state == 'OPEN'
    
    def test_success_resets_failure_count(self, circuit_breaker):
        """Test success resets failure counter."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        circuit_breaker.record_success()
        
        # Should reset, so one more failure shouldn't open
        circuit_breaker.record_failure()
        assert circuit_breaker.state == 'CLOSED'


class TestCircuitBreakerStats:
    """Test circuit breaker statistics."""
    
    @pytest.fixture
    def circuit_breaker(self):
        try:
            from services.circuit_breaker import CircuitBreaker
            return CircuitBreaker()
        except ImportError:
            from services.llm_service import CircuitBreaker
            return CircuitBreaker()
    
    def test_failure_count(self, circuit_breaker):
        """Test failure count tracking."""
        circuit_breaker.record_failure()
        circuit_breaker.record_failure()
        
        if hasattr(circuit_breaker, 'failure_count'):
            assert circuit_breaker.failure_count == 2
    
    def test_success_count(self, circuit_breaker):
        """Test success count tracking."""
        circuit_breaker.record_success()
        circuit_breaker.record_success()
        
        if hasattr(circuit_breaker, 'success_count'):
            assert circuit_breaker.success_count >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
