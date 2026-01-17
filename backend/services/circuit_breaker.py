"""
Circuit Breaker - Prevent cascading failures when external services are down.
Implements the circuit breaker pattern with states: CLOSED, OPEN, HALF_OPEN.
"""
import asyncio
import time
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock

from services.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for a circuit."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    last_failure_time: float = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    timeout_seconds: float = 30.0       # Time before trying again
    half_open_max_calls: int = 3        # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(self, name: str, config: Optional[CircuitConfig] = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._lock = Lock()
        self._half_open_calls = 0
    
    def _should_allow_request(self) -> bool:
        """Check if the request should be allowed based on current state."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.stats.last_failure_time >= self.config.timeout_seconds:
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open
            return self._half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def _transition_to_half_open(self):
        """Transition to half-open state."""
        with self._lock:
            self.state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            self.stats.consecutive_successes = 0
            logger.info(f"Circuit '{self.name}' transitioning to HALF_OPEN")
    
    def _record_success(self):
        """Record a successful call."""
        with self._lock:
            self.stats.total_calls += 1
            self.stats.successful_calls += 1
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes += 1
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    logger.info(f"Circuit '{self.name}' CLOSED - service recovered")
    
    def _record_failure(self, error: Exception):
        """Record a failed call."""
        with self._lock:
            self.stats.total_calls += 1
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens the circuit
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit '{self.name}' OPEN - failure in half-open state: {error}")
            
            elif self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(f"Circuit '{self.name}' OPEN - threshold reached: {error}")
    
    async def call_async(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute an async function through the circuit breaker."""
        if not self._should_allow_request():
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise
    
    def call_sync(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a sync function through the circuit breaker."""
        if not self._should_allow_request():
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            raise
    
    def get_status(self) -> dict:
        """Get current circuit status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "consecutive_failures": self.stats.consecutive_failures,
                "failure_rate": round(
                    self.stats.failed_calls / max(self.stats.total_calls, 1) * 100, 2
                )
            }
        }
    
    def reset(self):
        """Manually reset the circuit to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self._half_open_calls = 0
            logger.info(f"Circuit '{self.name}' manually reset")


class CircuitOpenError(Exception):
    """Raised when a circuit is open and rejecting requests."""
    pass


# ============= Circuit Registry =============

class CircuitRegistry:
    """Manage multiple circuit breakers."""
    
    def __init__(self):
        self._circuits: dict[str, CircuitBreaker] = {}
        self._lock = Lock()
    
    def get_or_create(self, name: str, config: Optional[CircuitConfig] = None) -> CircuitBreaker:
        """Get existing circuit or create a new one."""
        with self._lock:
            if name not in self._circuits:
                self._circuits[name] = CircuitBreaker(name, config)
            return self._circuits[name]
    
    def get_all_status(self) -> dict:
        """Get status of all circuits."""
        return {
            name: circuit.get_status()
            for name, circuit in self._circuits.items()
        }
    
    def reset_all(self):
        """Reset all circuits."""
        for circuit in self._circuits.values():
            circuit.reset()


# Singleton
_registry: Optional[CircuitRegistry] = None


def get_circuit_registry() -> CircuitRegistry:
    global _registry
    if _registry is None:
        _registry = CircuitRegistry()
    return _registry


# ============= Decorator =============

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    timeout_seconds: float = 30.0,
    fallback: Optional[Callable] = None
):
    """
    Decorator to wrap a function with a circuit breaker.
    
    Usage:
        @circuit_breaker("openai", failure_threshold=3, fallback=lambda: "default")
        async def call_openai(prompt: str):
            ...
    """
    config = CircuitConfig(
        failure_threshold=failure_threshold,
        timeout_seconds=timeout_seconds
    )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        circuit = get_circuit_registry().get_or_create(name, config)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                try:
                    return await circuit.call_async(func, *args, **kwargs)
                except CircuitOpenError:
                    if fallback:
                        return fallback(*args, **kwargs) if not asyncio.iscoroutinefunction(fallback) else await fallback(*args, **kwargs)
                    raise
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                try:
                    return circuit.call_sync(func, *args, **kwargs)
                except CircuitOpenError:
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise
            return sync_wrapper
    
    return decorator
