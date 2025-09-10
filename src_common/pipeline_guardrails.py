# src_common/pipeline_guardrails.py
"""
Pipeline Guardrails System for TTRPG Center Ingestion Pipeline

Implements fail-fast validation to prevent wasted compute when passes produce
zero output. Provides configurable thresholds and clear failure categorization.

Key Features:
- Configurable output thresholds for each pass
- Clear failure reason categorization  
- Integration with existing pass result structures
- Detailed logging for operational debugging
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
import logging as _logging

from .pass_c_extraction import PassCResult
from .pass_d_vector_enrichment import PassDResult

logger = _logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """Result of a guardrail validation check"""
    passed: bool
    pass_name: str
    threshold_name: str
    actual_value: Union[int, float]
    threshold_value: Union[int, float]
    failure_reason: Optional[str] = None
    
    @property
    def failure_message(self) -> str:
        """Generate a descriptive failure message"""
        if self.passed:
            return ""
        return (
            f"Pass {self.pass_name} failed guardrail: {self.threshold_name} "
            f"(actual: {self.actual_value}, required: >{self.threshold_value})"
        )


class GuardrailPolicy:
    """
    Configurable guardrail policy for pipeline passes.
    
    Validates output counts and quality metrics to determine if pipeline
    should continue or abort processing for a given source.
    """
    
    def __init__(self, env: str = "dev"):
        self.env = env
        self._configure_thresholds()
    
    def _configure_thresholds(self) -> None:
        """Configure pass output thresholds based on environment"""
        # Critical thresholds that cause hard stops
        self.critical_thresholds = {
            "C": {
                "chunks_extracted": 0,  # Must produce at least 1 chunk
                "description": "Raw chunk extraction from PDF content"
            },
            "D": {
                "chunks_vectorized": 0,  # Must vectorize at least 1 chunk
                "description": "Vector embeddings for semantic search"
            }
        }
        
        # Warning thresholds that log but don't stop processing
        self.warning_thresholds = {
            "A": {
                "toc_entries": -1,  # Negative means no minimum (flexible)
                "description": "Table of contents parsing"
            },
            "E": {
                "graph_nodes": -1,  # Graphs are optional for some documents
                "description": "Knowledge graph construction"
            }
        }
        
        # Environment-specific adjustments
        if self.env == "test":
            # More lenient thresholds for testing
            self.critical_thresholds["C"]["chunks_extracted"] = 0
            self.critical_thresholds["D"]["chunks_vectorized"] = 0
        elif self.env == "prod":
            # Stricter thresholds for production
            self.critical_thresholds["C"]["chunks_extracted"] = 1
            self.critical_thresholds["D"]["chunks_vectorized"] = 1
    
    def validate_pass_output(self, pass_name: str, pass_result: Any) -> GuardrailResult:
        """
        Validate a pass result against configured thresholds.
        
        Args:
            pass_name: Pass identifier (A, B, C, D, E, F)
            pass_result: Result object from the pass
            
        Returns:
            GuardrailResult indicating whether validation passed
        """
        # Handle skipped passes (from resume operations)
        if isinstance(pass_result, dict) and pass_result.get("skipped"):
            logger.debug(f"Pass {pass_name} was skipped (resume mode)")
            return GuardrailResult(
                passed=True,
                pass_name=pass_name,
                threshold_name="skipped",
                actual_value=0,
                threshold_value=0
            )
        
        # Validate critical thresholds
        if pass_name in self.critical_thresholds:
            return self._validate_critical_threshold(pass_name, pass_result)
        
        # Check warning thresholds (don't cause failures)
        if pass_name in self.warning_thresholds:
            warning_result = self._validate_warning_threshold(pass_name, pass_result)
            if not warning_result.passed:
                logger.warning(warning_result.failure_message)
        
        # Default: allow pass to succeed
        return GuardrailResult(
            passed=True,
            pass_name=pass_name,
            threshold_name="default",
            actual_value=1,
            threshold_value=0
        )
    
    def _validate_critical_threshold(self, pass_name: str, pass_result: Any) -> GuardrailResult:
        """Validate critical thresholds that cause hard stops"""
        thresholds = self.critical_thresholds[pass_name]
        
        if pass_name == "C":
            return self._validate_pass_c(pass_result, thresholds)
        elif pass_name == "D":
            return self._validate_pass_d(pass_result, thresholds)
        
        # Unknown critical pass
        logger.warning(f"Unknown critical pass: {pass_name}")
        return GuardrailResult(
            passed=True,
            pass_name=pass_name,
            threshold_name="unknown",
            actual_value=1,
            threshold_value=0
        )
    
    def _validate_pass_c(self, pass_result: Any, thresholds: Dict) -> GuardrailResult:
        """Validate Pass C (extraction) output"""
        # Extract chunks_extracted from PassCResult or dict
        if isinstance(pass_result, PassCResult):
            chunks_extracted = pass_result.chunks_extracted
        elif isinstance(pass_result, dict):
            chunks_extracted = pass_result.get("chunks_extracted", 0)
        else:
            logger.error(f"Invalid Pass C result type: {type(pass_result)}")
            chunks_extracted = 0
        
        threshold = thresholds["chunks_extracted"]
        passed = chunks_extracted > threshold
        
        failure_reason = None
        if not passed:
            failure_reason = f"Zero output at Pass C"
            logger.error(f"CRITICAL: Pass C produced {chunks_extracted} chunks (required: >{threshold})")
        
        return GuardrailResult(
            passed=passed,
            pass_name="C",
            threshold_name="chunks_extracted",
            actual_value=chunks_extracted,
            threshold_value=threshold,
            failure_reason=failure_reason
        )
    
    def _validate_pass_d(self, pass_result: Any, thresholds: Dict) -> GuardrailResult:
        """Validate Pass D (vectorization) output"""
        # Extract chunks_vectorized from PassDResult or dict
        if isinstance(pass_result, PassDResult):
            chunks_vectorized = pass_result.chunks_vectorized
        elif isinstance(pass_result, dict):
            chunks_vectorized = pass_result.get("chunks_vectorized", 0)
        else:
            logger.error(f"Invalid Pass D result type: {type(pass_result)}")
            chunks_vectorized = 0
        
        threshold = thresholds["chunks_vectorized"]
        passed = chunks_vectorized > threshold
        
        failure_reason = None
        if not passed:
            failure_reason = f"Zero output at Pass D"
            logger.error(f"CRITICAL: Pass D vectorized {chunks_vectorized} chunks (required: >{threshold})")
        
        return GuardrailResult(
            passed=passed,
            pass_name="D",
            threshold_name="chunks_vectorized",
            actual_value=chunks_vectorized,
            threshold_value=threshold,
            failure_reason=failure_reason
        )
    
    def _validate_warning_threshold(self, pass_name: str, pass_result: Any) -> GuardrailResult:
        """Validate warning thresholds (log but don't fail)"""
        thresholds = self.warning_thresholds[pass_name]
        
        # For now, just return success for warning thresholds
        # Future enhancement: implement specific validation logic
        return GuardrailResult(
            passed=True,
            pass_name=pass_name,
            threshold_name="warning",
            actual_value=1,
            threshold_value=0
        )
    
    def should_abort_source(self, pass_name: str, pass_result: Any) -> bool:
        """
        Determine if source processing should be aborted after this pass.
        
        Args:
            pass_name: Pass identifier (A, B, C, D, E, F)
            pass_result: Result object from the pass
            
        Returns:
            True if processing should be aborted, False to continue
        """
        validation_result = self.validate_pass_output(pass_name, pass_result)
        
        # Only abort on critical threshold failures
        if not validation_result.passed and pass_name in self.critical_thresholds:
            logger.error(f"[FATAL] Pass {pass_name} guardrail failure — aborting source processing")
            logger.error(f"[FATAL] Reason: {validation_result.failure_reason}")
            return True
        
        return False
    
    def get_failure_summary(self, pass_name: str, pass_result: Any) -> Dict[str, Any]:
        """
        Get detailed failure summary for reporting.
        
        Returns:
            Dictionary with failure details for job summaries
        """
        validation_result = self.validate_pass_output(pass_name, pass_result)
        
        return {
            "failed": not validation_result.passed,
            "failed_pass": pass_name if not validation_result.passed else None,
            "failure_reason": validation_result.failure_reason,
            "threshold_name": validation_result.threshold_name,
            "actual_value": validation_result.actual_value,
            "threshold_value": validation_result.threshold_value,
            "description": self.critical_thresholds.get(pass_name, {}).get("description", "Unknown pass")
        }


# Global policy instance - can be configured per environment
def get_guardrail_policy(env: str = "dev") -> GuardrailPolicy:
    """Get or create guardrail policy instance for environment"""
    return GuardrailPolicy(env=env)