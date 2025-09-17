"""
HGRN Adapter

Integration adapter for HGRN package compatibility and API abstraction.
Provides a clean interface between TTRPG Center and external HGRN libraries.
"""

import os
import sys
import logging
import importlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .models import HGRNReport, HGRNRecommendation, RecommendationType, ValidationSeverity
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class HGRNAdapter:
    """
    Adapter for external HGRN package integration.

    Provides abstraction layer for HGRN library interactions,
    handling package detection, version compatibility, and API translation.
    """

    def __init__(self, package_version: str = "1.2.3"):
        """
        Initialize HGRN adapter.

        Args:
            package_version: Expected HGRN package version
        """
        self.package_version = package_version
        self.hgrn_package = None
        self.package_available = False

        # Attempt to load HGRN package
        self._initialize_package()

    def _initialize_package(self) -> None:
        """Initialize HGRN package if available."""
        try:
            # Check if HGRN package path is configured
            hgrn_path = os.getenv("HGRN_PACKAGE_PATH", "/opt/hgrn")
            if Path(hgrn_path).exists():
                sys.path.insert(0, str(hgrn_path))

            # Attempt to import HGRN package
            import hgrn  # type: ignore
            self.hgrn_package = hgrn
            self.package_available = True

            package_version = getattr(hgrn, "__version__", "unknown")
            logger.info(f"HGRN package loaded successfully. Version: {package_version}")

            # Version compatibility check
            if package_version != self.package_version:
                logger.warning(
                    f"HGRN package version mismatch. "
                    f"Expected: {self.package_version}, "
                    f"Found: {package_version}"
                )

        except ImportError:
            logger.info("HGRN package not available. Using mock implementation.")
            self.package_available = False
        except Exception as e:
            logger.error(f"Failed to initialize HGRN package: {str(e)}")
            self.package_available = False

    def is_available(self) -> bool:
        """Check if HGRN package is available."""
        return self.package_available

    def run_validation(
        self,
        job_id: str,
        artifacts_path: Path,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run HGRN validation using external package.

        Args:
            job_id: Ingestion job identifier
            artifacts_path: Path to artifacts directory
            config: Optional configuration overrides

        Returns:
            Raw HGRN validation results
        """
        if not self.package_available:
            return self._mock_validation_results(job_id, artifacts_path)

        try:
            # Configure HGRN package
            hgrn_config = self._build_hgrn_config(config)

            # Run HGRN validation
            logger.info(f"Running external HGRN validation for job {job_id}")
            results = self.hgrn_package.validate_ingestion(
                job_id=job_id,
                artifacts_path=str(artifacts_path),
                config=hgrn_config
            )

            logger.info(f"External HGRN validation completed for job {job_id}")
            return results

        except Exception as e:
            logger.error(f"External HGRN validation failed for job {job_id}: {str(e)}")
            # Fallback to mock results
            return self._mock_validation_results(job_id, artifacts_path, error=str(e))

    def _build_hgrn_config(self, config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build HGRN package configuration."""
        base_config = {
            "confidence_threshold": float(os.getenv("HGRN_CONFIDENCE_THRESHOLD", "0.7")),
            "timeout_seconds": int(os.getenv("HGRN_TIMEOUT_SECONDS", "300")),
            "enable_ocr_fallback": True,
            "max_chunk_analysis": 1000,
            "validate_dictionary": True,
            "validate_graph": True,
            "validate_chunks": True
        }

        if config_override:
            base_config.update(config_override)

        return base_config

    def _mock_validation_results(
        self,
        job_id: str,
        artifacts_path: Path,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate mock HGRN validation results for testing.

        Used when HGRN package is not available or fails.
        """
        logger.info(f"Generating mock HGRN validation results for job {job_id}")

        # Simulate validation findings
        mock_recommendations = []

        # Mock dictionary validation issue
        if (artifacts_path / "pass_b").exists():
            mock_recommendations.append({
                "id": f"mock_dict_{job_id}_001",
                "type": "dictionary",
                "severity": "medium",
                "confidence": 0.8,
                "title": "Mock Dictionary Issue",
                "description": "This is a mock recommendation generated when HGRN package is unavailable",
                "evidence": {"mock": True, "job_id": job_id},
                "suggested_action": "This is a demonstration recommendation - install HGRN package for real validation",
                "page_refs": [1, 2],
                "chunk_ids": ["mock_chunk_1", "mock_chunk_2"]
            })

        # Mock graph validation issue
        if (artifacts_path / "pass_c").exists():
            mock_recommendations.append({
                "id": f"mock_graph_{job_id}_001",
                "type": "graph",
                "severity": "low",
                "confidence": 0.7,
                "title": "Mock Graph Connectivity Issue",
                "description": "Mock graph validation finding - install HGRN package for real analysis",
                "evidence": {"mock": True, "node_count": 42, "edge_count": 38},
                "suggested_action": "Install and configure HGRN package for actual graph validation",
                "page_refs": [3, 4, 5],
                "chunk_ids": ["mock_chunk_3", "mock_chunk_4"]
            })

        mock_results = {
            "status": "mock_success" if not error else "mock_error",
            "job_id": job_id,
            "package_version": "mock-1.2.3",
            "processing_time": 1.5,
            "recommendations": mock_recommendations,
            "stats": {
                "total_chunks_analyzed": 25,
                "dictionary_terms_validated": 15,
                "graph_nodes_validated": 42,
                "ocr_fallback_triggered": False
            },
            "error_message": error,
            "mock_data": True
        }

        return mock_results

    def translate_results_to_report(
        self,
        raw_results: Dict[str, Any],
        job_id: str,
        environment: str
    ) -> HGRNReport:
        """
        Translate raw HGRN package results to internal report format.

        Args:
            raw_results: Raw results from HGRN package
            job_id: Job identifier
            environment: Environment name

        Returns:
            Translated HGRN report
        """
        try:
            # Create base report
            report = HGRNReport(
                job_id=job_id,
                environment=environment,
                status=raw_results.get("status", "unknown")
            )

            # Translate recommendations
            recommendations = []
            for rec_data in raw_results.get("recommendations", []):
                try:
                    # Map external recommendation format to internal format
                    rec = HGRNRecommendation(
                        id=rec_data.get("id", f"ext_{job_id}_{len(recommendations)}"),
                        type=self._map_recommendation_type(rec_data.get("type", "unknown")),
                        severity=self._map_severity(rec_data.get("severity", "medium")),
                        confidence=float(rec_data.get("confidence", 0.5)),
                        title=rec_data.get("title", "External Recommendation"),
                        description=rec_data.get("description", ""),
                        evidence=rec_data.get("evidence", {}),
                        suggested_action=rec_data.get("suggested_action", "Review manually"),
                        page_refs=rec_data.get("page_refs", []),
                        chunk_ids=rec_data.get("chunk_ids", [])
                    )
                    recommendations.append(rec)

                except Exception as e:
                    logger.warning(f"Failed to translate recommendation: {str(e)}")
                    continue

            report.recommendations = recommendations

            # Translate statistics if available
            stats_data = raw_results.get("stats")
            if stats_data:
                from .models import HGRNValidationStats
                report.stats = HGRNValidationStats(
                    total_chunks_analyzed=stats_data.get("total_chunks_analyzed", 0),
                    dictionary_terms_validated=stats_data.get("dictionary_terms_validated", 0),
                    graph_nodes_validated=stats_data.get("graph_nodes_validated", 0),
                    ocr_fallback_triggered=stats_data.get("ocr_fallback_triggered", False),
                    processing_time_seconds=raw_results.get("processing_time", 0.0),
                    confidence_threshold_used=float(os.getenv("HGRN_CONFIDENCE_THRESHOLD", "0.7")),
                    package_version=raw_results.get("package_version", "unknown")
                )

            # Set error message if present
            if raw_results.get("error_message"):
                report.error_message = raw_results["error_message"]

            # Mark as mock data if applicable
            if raw_results.get("mock_data"):
                report.status = "mock_" + report.status
                for rec in report.recommendations:
                    rec.metadata["mock_data"] = True

            return report

        except Exception as e:
            logger.error(f"Failed to translate HGRN results: {str(e)}")
            return HGRNReport(
                job_id=job_id,
                environment=environment,
                status="translation_failed",
                error_message=f"Failed to translate external HGRN results: {str(e)}"
            )

    def _map_recommendation_type(self, external_type: str) -> RecommendationType:
        """Map external recommendation type to internal enum."""
        type_mapping = {
            "dictionary": RecommendationType.DICTIONARY,
            "dict": RecommendationType.DICTIONARY,
            "graph": RecommendationType.GRAPH,
            "chunk": RecommendationType.CHUNK,
            "chunks": RecommendationType.CHUNK,
            "ocr": RecommendationType.OCR
        }

        return type_mapping.get(external_type.lower(), RecommendationType.CHUNK)

    def _map_severity(self, external_severity: str) -> ValidationSeverity:
        """Map external severity to internal enum."""
        severity_mapping = {
            "low": ValidationSeverity.LOW,
            "medium": ValidationSeverity.MEDIUM,
            "high": ValidationSeverity.HIGH,
            "critical": ValidationSeverity.CRITICAL
        }

        return severity_mapping.get(external_severity.lower(), ValidationSeverity.MEDIUM)

    def get_package_info(self) -> Dict[str, Any]:
        """Get information about the HGRN package."""
        info = {
            "package_available": self.package_available,
            "expected_version": self.package_version,
            "package_path": os.getenv("HGRN_PACKAGE_PATH", "/opt/hgrn")
        }

        if self.package_available and self.hgrn_package:
            info.update({
                "actual_version": getattr(self.hgrn_package, "__version__", "unknown"),
                "capabilities": getattr(self.hgrn_package, "__capabilities__", []),
                "package_name": getattr(self.hgrn_package, "__name__", "hgrn")
            })

        return info