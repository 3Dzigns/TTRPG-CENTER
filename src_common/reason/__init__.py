# src_common/reason/__init__.py
"""
Phase 3 Graph-Based Reasoning
Multi-hop QA and procedural execution with graph guidance
"""

from .graphwalk import GraphGuidedReasoner, graph_guided_answer
from .executors import ChecklistExecutor, ComputeDCExecutor, RulesVerifier

__all__ = [
    'GraphGuidedReasoner', 'graph_guided_answer',
    'ChecklistExecutor', 'ComputeDCExecutor', 'RulesVerifier'
]