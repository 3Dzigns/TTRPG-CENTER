# src_common/patterns/__init__.py
"""
Design patterns for TTRPG Center
"""

from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
    get_all_circuit_breakers,
    reset_all_circuit_breakers
)

__all__ = [
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerError',
    'CircuitState',
    'circuit_breaker',
    'get_circuit_breaker',
    'get_all_circuit_breakers',
    'reset_all_circuit_breakers'
]