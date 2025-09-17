"""
Persona testing framework for TTRPG Center.

This module provides persona-aware testing capabilities that evaluate system responses
based on user types, experience levels, and context. It integrates with existing
AEHRL and HGRN quality systems to ensure responses are appropriate for specific personas.
"""

from .models import (
    PersonaProfile, PersonaContext, PersonaMetrics,
    PersonaType, ExperienceLevel, UserRole, SessionContext
)
from .manager import PersonaManager
from .validator import PersonaResponseValidator
from .metrics import PersonaMetricsTracker

__all__ = [
    'PersonaProfile',
    'PersonaContext',
    'PersonaMetrics',
    'PersonaType',
    'ExperienceLevel',
    'UserRole',
    'SessionContext',
    'PersonaManager',
    'PersonaResponseValidator',
    'PersonaMetricsTracker'
]