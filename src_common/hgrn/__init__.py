"""
HGRN (Hierarchical Graph Recurrent Network) Integration Module

Provides validation and sanity checking capabilities for TTRPG Center ingestion pipeline.
Implements Pass D processing for dictionary metadata validation, graph integrity checks,
and chunk artifact comparison with automated recommendations.
"""

from .models import HGRNReport, HGRNRecommendation, RecommendationType
from .runner import HGRNRunner
from .adapter import HGRNAdapter
from .validator import HGRNValidator

__all__ = [
    'HGRNReport',
    'HGRNRecommendation',
    'RecommendationType',
    'HGRNRunner',
    'HGRNAdapter',
    'HGRNValidator'
]

__version__ = '1.0.0'