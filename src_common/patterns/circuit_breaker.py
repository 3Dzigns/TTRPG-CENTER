# src_common/patterns/circuit_breaker.py
"""
Circuit Breaker Pattern Implementation - FR-015

Provides resilient error handling for MongoDB connections with automatic
recovery and graceful degradation when the database is unavailable.
"""

import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict, TypeVar, Generic
from functools import wraps
import logging

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5      # Failures before opening circuit
    recovery_timeout: int = 60      # Seconds before attempting recovery
    expected_failure_rate: float = 0.5  # Expected failure rate threshold
    max_retry_attempts: int = 3     # Max retries in half-open state
    health_check_interval: int = 30  # Seconds between health checks
    timeout: float = 5.0            # Operation timeout in seconds


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation for MongoDB operations

    Provides automatic failure detection, recovery attempts, and graceful degradation
    when the MongoDB backend becomes unavailable.
    """

    def __init__(self,
                 name: str,
                 config: Optional[CircuitBreakerConfig] = None,
                 fallback_handler: Optional[Callable[..., T]] = None):
        """
        Initialize circuit breaker

        Args:
            name: Identifier for this circuit breaker
            config: Configuration parameters
            fallback_handler: Function to call when circuit is open
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback_handler = fallback_handler

        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_success_time = 0

        # Thread safety
        self._lock = threading.RLock()

        # Health monitoring
        self.last_health_check = 0
        self.consecutive_health_failures = 0

        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_timeouts = 0
        self.state_changes = []

        logger.info(f"Circuit breaker '{name}' initialized")

    def _get_current_time(self) -> float:
        """Get current timestamp (mockable for testing)"""
        return time.time()

    def _should_attempt_recovery(self) -> bool:
        """Check if circuit should attempt recovery"""
        if self.state != CircuitState.OPEN:
            return False

        time_since_failure = self._get_current_time() - self.last_failure_time
        return time_since_failure >= self.config.recovery_timeout

    def _record_success(self):
        """Record a successful operation"""
        with self._lock:
            self.success_count += 1
            self.last_success_time = self._get_current_time()

            # Reset failure count on success
            if self.state == CircuitState.HALF_OPEN:
                if self.success_count >= self.config.max_retry_attempts:
                    self._transition_to_closed()
            elif self.state == CircuitState.OPEN:
                # Shouldn't happen, but handle gracefully
                self._transition_to_half_open()

    def _record_failure(self, error: Exception):
        """Record a failed operation"""
        with self._lock:
            self.failure_count += 1
            self.total_failures += 1
            self.last_failure_time = self._get_current_time()

            logger.warning(f"Circuit breaker '{self.name}' recorded failure: {error}")

            # Check if we should open the circuit
            if self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    self._transition_to_open()
            elif self.state == CircuitState.HALF_OPEN:
                # Failed during recovery attempt
                self._transition_to_open()

    def _transition_to_open(self):
        """Transition circuit to OPEN state"""
        self.state = CircuitState.OPEN
        self.state_changes.append({
            'state': CircuitState.OPEN,
            'timestamp': self._get_current_time(),
            'failure_count': self.failure_count,
            'reason': 'failure_threshold_exceeded'
        })
        logger.warning(f"Circuit breaker '{self.name}' opened after {self.failure_count} failures")

    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0  # Reset success count for recovery attempt
        self.state_changes.append({
            'state': CircuitState.HALF_OPEN,
            'timestamp': self._get_current_time(),
            'reason': 'recovery_attempt'
        })
        logger.info(f"Circuit breaker '{self.name}' attempting recovery (HALF_OPEN)")

    def _transition_to_closed(self):
        """Transition circuit to CLOSED state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0  # Reset failure count
        self.state_changes.append({
            'state': CircuitState.CLOSED,
            'timestamp': self._get_current_time(),
            'success_count': self.success_count,
            'reason': 'recovery_successful'
        })
        logger.info(f"Circuit breaker '{self.name}' closed after successful recovery")

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerError: When circuit is open
            Original exception: When function fails and circuit allows it
        """
        with self._lock:
            self.total_calls += 1

            # Check if we should attempt recovery
            if self._should_attempt_recovery():
                self._transition_to_half_open()

            # Block calls if circuit is open
            if self.state == CircuitState.OPEN:
                if self.fallback_handler:
                    logger.info(f"Circuit breaker '{self.name}' executing fallback")
                    return self.fallback_handler(*args, **kwargs)
                else:
                    raise CircuitBreakerError(f"Circuit breaker '{self.name}' is OPEN")

        # Execute the function
        try:
            start_time = self._get_current_time()
            result = func(*args, **kwargs)
            execution_time = self._get_current_time() - start_time

            # Check for slow operations (potential timeout)
            if execution_time > self.config.timeout:
                self.total_timeouts += 1
                logger.warning(f"Circuit breaker '{self.name}' detected slow operation: {execution_time:.2f}s")

            self._record_success()
            return result

        except Exception as e:
            self._record_failure(e)
            raise

    def health_check(self, health_func: Callable[[], bool]) -> bool:
        """
        Perform health check and update circuit state accordingly

        Args:
            health_func: Function that returns True if service is healthy

        Returns:
            True if healthy, False otherwise
        """
        current_time = self._get_current_time()

        # Skip if we recently performed a health check
        if current_time - self.last_health_check < self.config.health_check_interval:
            return self.state == CircuitState.CLOSED

        self.last_health_check = current_time

        try:
            is_healthy = health_func()

            if is_healthy:
                self.consecutive_health_failures = 0
                # If we're open due to health failures, attempt recovery
                if self.state == CircuitState.OPEN:
                    self._transition_to_half_open()
                return True
            else:
                self.consecutive_health_failures += 1
                # Open circuit if repeated health check failures
                if (self.consecutive_health_failures >= self.config.failure_threshold
                    and self.state == CircuitState.CLOSED):
                    self._transition_to_open()
                return False

        except Exception as e:
            logger.error(f"Health check failed for circuit breaker '{self.name}': {e}")
            self.consecutive_health_failures += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        with self._lock:
            current_time = self._get_current_time()
            uptime = current_time - self.state_changes[0]['timestamp'] if self.state_changes else 0

            # Calculate failure rate
            failure_rate = (self.total_failures / self.total_calls) if self.total_calls > 0 else 0

            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_calls': self.total_calls,
                'total_failures': self.total_failures,
                'total_timeouts': self.total_timeouts,
                'failure_rate': failure_rate,
                'last_failure_time': self.last_failure_time,
                'last_success_time': self.last_success_time,
                'last_health_check': self.last_health_check,
                'consecutive_health_failures': self.consecutive_health_failures,
                'uptime': uptime,
                'state_changes': len(self.state_changes),
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'timeout': self.config.timeout
                }
            }

    def reset(self):
        """Reset circuit breaker to initial state"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.consecutive_health_failures = 0
            self.total_calls = 0
            self.total_failures = 0
            self.total_timeouts = 0
            self.state_changes = []

            logger.info(f"Circuit breaker '{self.name}' reset to initial state")


def circuit_breaker(name: str,
                   config: Optional[CircuitBreakerConfig] = None,
                   fallback_handler: Optional[Callable] = None):
    """
    Decorator for applying circuit breaker pattern to functions

    Args:
        name: Circuit breaker identifier
        config: Configuration parameters
        fallback_handler: Fallback function when circuit is open
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = CircuitBreaker(name, config, fallback_handler)

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        # Attach circuit breaker to function for external access
        wrapper._circuit_breaker = breaker
        return wrapper

    return decorator


# Global circuit breakers registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(name: str,
                       config: Optional[CircuitBreakerConfig] = None,
                       fallback_handler: Optional[Callable] = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name"""
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, config, fallback_handler)
        return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, CircuitBreaker]:
    """Get all registered circuit breakers"""
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_all_circuit_breakers():
    """Reset all registered circuit breakers"""
    with _registry_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")