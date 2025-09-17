"""
AEHRL (Automated Evaluation & Hallucination Reduction Layer) Module

Provides automated evaluation and self-checking capabilities for TTRPG Center.
Leverages HGRN infrastructure to validate model outputs against ingested sources,
dictionary entries, and graph nodes for continuous quality assurance.
"""

from .models import AEHRLReport, HallucinationFlag, CorrectionRecommendation
from .evaluator import AEHRLEvaluator
from .fact_extractor import FactExtractor
from .metrics_tracker import MetricsTracker
from .correction_manager import CorrectionManager

__all__ = [
    'AEHRLReport',
    'HallucinationFlag',
    'CorrectionRecommendation',
    'AEHRLEvaluator',
    'FactExtractor',
    'MetricsTracker',
    'CorrectionManager'
]

__version__ = '1.0.0'