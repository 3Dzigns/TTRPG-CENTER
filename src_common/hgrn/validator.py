"""
HGRN Validator

Core validation logic for HGRN sanity checking. Implements validation algorithms
for dictionary metadata, graph integrity, and chunk artifact comparison.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid

from .models import (
    HGRNReport, HGRNRecommendation, HGRNValidationStats,
    RecommendationType, ValidationSeverity
)

logger = logging.getLogger(__name__)


class HGRNValidator:
    """
    Core HGRN validation engine.

    Performs dictionary metadata validation, graph integrity checks,
    and chunk artifact comparison with automated recommendation generation.
    """

    def __init__(self, confidence_threshold: float = 0.7, timeout_seconds: int = 300):
        """
        Initialize HGRN validator.

        Args:
            confidence_threshold: Minimum confidence for recommendations
            timeout_seconds: Maximum processing time
        """
        self.confidence_threshold = confidence_threshold
        self.timeout_seconds = timeout_seconds
        self.start_time: Optional[datetime] = None

    def validate_artifacts(
        self,
        job_id: str,
        environment: str,
        artifacts_path: Path
    ) -> HGRNReport:
        """
        Run complete HGRN validation on ingestion artifacts.

        Args:
            job_id: Ingestion job identifier
            environment: Environment (dev/test/prod)
            artifacts_path: Path to job artifacts directory

        Returns:
            Complete HGRN validation report
        """
        self.start_time = datetime.now()
        logger.info(f"Starting HGRN validation for job {job_id} in {environment}")

        try:
            # Initialize report
            report = HGRNReport(
                job_id=job_id,
                environment=environment,
                status="in_progress"
            )

            # Load and analyze artifacts
            artifacts = self._load_artifacts(artifacts_path)
            report.artifacts_analyzed = list(artifacts.keys())

            # Perform validation checks
            recommendations = []

            # Dictionary validation
            dict_recommendations = self._validate_dictionary_metadata(
                artifacts, artifacts_path
            )
            recommendations.extend(dict_recommendations)

            # Graph integrity validation
            graph_recommendations = self._validate_graph_integrity(
                artifacts, artifacts_path
            )
            recommendations.extend(graph_recommendations)

            # Chunk comparison validation
            chunk_recommendations = self._compare_chunk_artifacts(
                artifacts, artifacts_path
            )
            recommendations.extend(chunk_recommendations)

            # Filter by confidence threshold
            high_confidence_recommendations = [
                rec for rec in recommendations
                if rec.confidence >= self.confidence_threshold
            ]

            report.recommendations = high_confidence_recommendations

            # Generate statistics
            report.stats = self._generate_stats(artifacts, recommendations)

            # Set final status
            if high_confidence_recommendations:
                critical_issues = [
                    rec for rec in high_confidence_recommendations
                    if rec.severity == ValidationSeverity.CRITICAL
                ]
                report.status = "critical" if critical_issues else "recommendations"
            else:
                report.status = "success"

            processing_time = (datetime.now() - self.start_time).total_seconds()
            logger.info(
                f"HGRN validation completed for job {job_id} in {processing_time:.2f}s. "
                f"Generated {len(high_confidence_recommendations)} recommendations."
            )

            return report

        except Exception as e:
            logger.error(f"HGRN validation failed for job {job_id}: {str(e)}")
            return HGRNReport(
                job_id=job_id,
                environment=environment,
                status="failed",
                error_message=str(e)
            )

    def _load_artifacts(self, artifacts_path: Path) -> Dict[str, Any]:
        """Load all relevant artifacts from the job directory."""
        artifacts = {}

        # Load Pass A artifacts (TOC and chunks)
        pass_a_path = artifacts_path / "pass_a"
        if pass_a_path.exists():
            artifacts["pass_a"] = self._load_pass_a_artifacts(pass_a_path)

        # Load Pass B artifacts (logical splits and dictionary)
        pass_b_path = artifacts_path / "pass_b"
        if pass_b_path.exists():
            artifacts["pass_b"] = self._load_pass_b_artifacts(pass_b_path)

        # Load Pass C artifacts (graph and final output)
        pass_c_path = artifacts_path / "pass_c"
        if pass_c_path.exists():
            artifacts["pass_c"] = self._load_pass_c_artifacts(pass_c_path)

        return artifacts

    def _load_pass_a_artifacts(self, pass_a_path: Path) -> Dict[str, Any]:
        """Load Pass A artifacts (TOC parsing and initial chunks)."""
        artifacts = {}

        # Load TOC data
        toc_file = pass_a_path / "toc_data.json"
        if toc_file.exists():
            with open(toc_file, 'r', encoding='utf-8') as f:
                artifacts["toc_data"] = json.load(f)

        # Load initial chunks
        chunks_file = pass_a_path / "initial_chunks.json"
        if chunks_file.exists():
            with open(chunks_file, 'r', encoding='utf-8') as f:
                artifacts["initial_chunks"] = json.load(f)

        return artifacts

    def _load_pass_b_artifacts(self, pass_b_path: Path) -> Dict[str, Any]:
        """Load Pass B artifacts (logical splitting and dictionary updates)."""
        artifacts = {}

        # Load logical splits
        splits_file = pass_b_path / "logical_splits.json"
        if splits_file.exists():
            with open(splits_file, 'r', encoding='utf-8') as f:
                artifacts["logical_splits"] = json.load(f)

        # Load dictionary updates
        dict_file = pass_b_path / "dictionary_updates.json"
        if dict_file.exists():
            with open(dict_file, 'r', encoding='utf-8') as f:
                artifacts["dictionary_updates"] = json.load(f)

        return artifacts

    def _load_pass_c_artifacts(self, pass_c_path: Path) -> Dict[str, Any]:
        """Load Pass C artifacts (graph compilation and final chunks)."""
        artifacts = {}

        # Load graph data
        graph_file = pass_c_path / "graph_data.json"
        if graph_file.exists():
            with open(graph_file, 'r', encoding='utf-8') as f:
                artifacts["graph_data"] = json.load(f)

        # Load final chunks
        final_chunks_file = pass_c_path / "final_chunks.json"
        if final_chunks_file.exists():
            with open(final_chunks_file, 'r', encoding='utf-8') as f:
                artifacts["final_chunks"] = json.load(f)

        return artifacts

    def _validate_dictionary_metadata(
        self,
        artifacts: Dict[str, Any],
        artifacts_path: Path
    ) -> List[HGRNRecommendation]:
        """Validate dictionary metadata consistency and completeness."""
        recommendations = []

        # Check if dictionary updates exist
        dict_updates = artifacts.get("pass_b", {}).get("dictionary_updates")
        if not dict_updates:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.MEDIUM,
                confidence=0.9,
                title="Missing Dictionary Updates",
                description="No dictionary updates found in Pass B artifacts",
                evidence={"pass_b_path": str(artifacts_path / "pass_b")},
                suggested_action="Verify Pass B completed successfully and dictionary updates were generated"
            )
            recommendations.append(rec)
            return recommendations

        # Validate dictionary term consistency
        term_count = len(dict_updates.get("terms", []))
        if term_count < 10:  # Heuristic threshold
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.LOW,
                confidence=0.8,
                title="Low Dictionary Term Count",
                description=f"Only {term_count} dictionary terms found, which may indicate incomplete extraction",
                evidence={"term_count": term_count, "terms": dict_updates.get("terms", [])[:5]},
                suggested_action="Review source document for missed terminology or adjust extraction parameters"
            )
            recommendations.append(rec)

        # Check for malformed dictionary entries
        malformed_terms = []
        for term in dict_updates.get("terms", []):
            if not isinstance(term, dict) or "term" not in term or "definition" not in term:
                malformed_terms.append(term)

        if malformed_terms:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.HIGH,
                confidence=0.95,
                title="Malformed Dictionary Entries",
                description=f"Found {len(malformed_terms)} malformed dictionary entries",
                evidence={"malformed_count": len(malformed_terms), "examples": malformed_terms[:3]},
                suggested_action="Review and fix dictionary extraction logic to ensure proper term/definition structure"
            )
            recommendations.append(rec)

        return recommendations

    def _validate_graph_integrity(
        self,
        artifacts: Dict[str, Any],
        artifacts_path: Path
    ) -> List[HGRNRecommendation]:
        """Validate graph structure integrity and relationships."""
        recommendations = []

        # Check if graph data exists
        graph_data = artifacts.get("pass_c", {}).get("graph_data")
        if not graph_data:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.GRAPH,
                severity=ValidationSeverity.CRITICAL,
                confidence=0.95,
                title="Missing Graph Data",
                description="No graph data found in Pass C artifacts",
                evidence={"pass_c_path": str(artifacts_path / "pass_c")},
                suggested_action="Verify Pass C graph compilation completed successfully"
            )
            recommendations.append(rec)
            return recommendations

        # Validate graph structure
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        if len(nodes) == 0:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.GRAPH,
                severity=ValidationSeverity.CRITICAL,
                confidence=0.9,
                title="Empty Graph Structure",
                description="Graph contains no nodes",
                evidence={"node_count": 0, "edge_count": len(edges)},
                suggested_action="Investigate graph compilation process for failures or configuration issues"
            )
            recommendations.append(rec)

        # Check for orphaned nodes
        node_ids = {node.get("id") for node in nodes if "id" in node}
        connected_nodes = set()
        for edge in edges:
            if "source" in edge and "target" in edge:
                connected_nodes.add(edge["source"])
                connected_nodes.add(edge["target"])

        orphaned_nodes = node_ids - connected_nodes
        if len(orphaned_nodes) > len(node_ids) * 0.3:  # >30% orphaned is suspicious
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.GRAPH,
                severity=ValidationSeverity.MEDIUM,
                confidence=0.8,
                title="High Orphaned Node Count",
                description=f"Found {len(orphaned_nodes)} orphaned nodes out of {len(node_ids)} total",
                evidence={
                    "orphaned_count": len(orphaned_nodes),
                    "total_nodes": len(node_ids),
                    "orphaned_percentage": round(len(orphaned_nodes) / len(node_ids) * 100, 1)
                },
                suggested_action="Review graph relationship extraction to improve node connectivity"
            )
            recommendations.append(rec)

        return recommendations

    def _compare_chunk_artifacts(
        self,
        artifacts: Dict[str, Any],
        artifacts_path: Path
    ) -> List[HGRNRecommendation]:
        """Compare chunk artifacts between passes for consistency."""
        recommendations = []

        initial_chunks = artifacts.get("pass_a", {}).get("initial_chunks", [])
        final_chunks = artifacts.get("pass_c", {}).get("final_chunks", [])

        if not initial_chunks:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.CHUNK,
                severity=ValidationSeverity.HIGH,
                confidence=0.9,
                title="Missing Initial Chunks",
                description="No initial chunks found from Pass A",
                evidence={"pass_a_chunks": len(initial_chunks)},
                suggested_action="Verify Pass A chunk extraction completed successfully"
            )
            recommendations.append(rec)

        if not final_chunks:
            rec = HGRNRecommendation(
                id=str(uuid.uuid4()),
                type=RecommendationType.CHUNK,
                severity=ValidationSeverity.HIGH,
                confidence=0.9,
                title="Missing Final Chunks",
                description="No final chunks found from Pass C",
                evidence={"pass_c_chunks": len(final_chunks)},
                suggested_action="Verify Pass C chunk finalization completed successfully"
            )
            recommendations.append(rec)

        if initial_chunks and final_chunks:
            # Check for significant chunk count changes
            chunk_loss_ratio = 1 - (len(final_chunks) / len(initial_chunks))
            if chunk_loss_ratio > 0.5:  # >50% chunk loss
                rec = HGRNRecommendation(
                    id=str(uuid.uuid4()),
                    type=RecommendationType.CHUNK,
                    severity=ValidationSeverity.HIGH,
                    confidence=0.85,
                    title="Significant Chunk Loss",
                    description=f"Lost {chunk_loss_ratio:.1%} of chunks from initial to final processing",
                    evidence={
                        "initial_count": len(initial_chunks),
                        "final_count": len(final_chunks),
                        "loss_percentage": round(chunk_loss_ratio * 100, 1)
                    },
                    suggested_action="Review chunk processing pipeline for excessive filtering or failures"
                )
                recommendations.append(rec)

            # Check for truncated chunks
            truncated_count = 0
            for chunk in final_chunks:
                text = chunk.get("text", "")
                if text.endswith("…") or text.endswith("...") or len(text) == 1500:
                    truncated_count += 1

            if truncated_count > len(final_chunks) * 0.2:  # >20% truncated
                rec = HGRNRecommendation(
                    id=str(uuid.uuid4()),
                    type=RecommendationType.CHUNK,
                    severity=ValidationSeverity.MEDIUM,
                    confidence=0.8,
                    title="High Chunk Truncation Rate",
                    description=f"Found {truncated_count} truncated chunks out of {len(final_chunks)} total",
                    evidence={
                        "truncated_count": truncated_count,
                        "total_chunks": len(final_chunks),
                        "truncation_percentage": round(truncated_count / len(final_chunks) * 100, 1)
                    },
                    suggested_action="Consider increasing chunk size limits or review text extraction quality"
                )
                recommendations.append(rec)

        return recommendations

    def _generate_stats(
        self,
        artifacts: Dict[str, Any],
        all_recommendations: List[HGRNRecommendation]
    ) -> HGRNValidationStats:
        """Generate validation statistics."""
        processing_time = (datetime.now() - self.start_time).total_seconds()

        # Count analyzed elements
        total_chunks = 0
        dict_terms = 0
        graph_nodes = 0

        if "pass_a" in artifacts:
            initial_chunks = artifacts["pass_a"].get("initial_chunks", [])
            total_chunks += len(initial_chunks)

        if "pass_c" in artifacts:
            final_chunks = artifacts["pass_c"].get("final_chunks", [])
            total_chunks += len(final_chunks)

        if "pass_b" in artifacts:
            dict_updates = artifacts["pass_b"].get("dictionary_updates", {})
            dict_terms = len(dict_updates.get("terms", []))

        if "pass_c" in artifacts:
            graph_data = artifacts["pass_c"].get("graph_data", {})
            graph_nodes = len(graph_data.get("nodes", []))

        # Check if OCR fallback was triggered (heuristic)
        ocr_fallback = any(
            rec.type == RecommendationType.OCR for rec in all_recommendations
        )

        return HGRNValidationStats(
            total_chunks_analyzed=total_chunks,
            dictionary_terms_validated=dict_terms,
            graph_nodes_validated=graph_nodes,
            ocr_fallback_triggered=ocr_fallback,
            processing_time_seconds=processing_time,
            confidence_threshold_used=self.confidence_threshold,
            package_version="1.2.3"  # This would come from actual HGRN package
        )