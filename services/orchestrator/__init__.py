"""
Orchestrator Service package exports.
"""

__version__ = "2.0.0"
__service__ = "orchestrator"

from .engine import OrchestratorEngine

__all__ = ["OrchestratorEngine", "__version__", "__service__"]
