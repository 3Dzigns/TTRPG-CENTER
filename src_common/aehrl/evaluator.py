"""
AEHRL Evaluator

Main evaluation engine for automated hallucination detection and correction.
Coordinates fact extraction, evidence gathering, and flag generation.
"""

import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .models import (
    AEHRLReport, HallucinationFlag, FactClaim, SupportEvidence,
    HallucinationSeverity, SupportLevel, AEHRLMetrics
)
from .fact_extractor import FactExtractor
from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


class AEHRLEvaluator:
    """
    Main AEHRL evaluation engine.

    Evaluates model outputs against retrieved sources and knowledge base
    to detect hallucinations and generate correction recommendations.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        hallucination_threshold: float = 0.3,
        environment: str = "dev"
    ):
        """
        Initialize AEHRL evaluator.

        Args:
            confidence_threshold: Minimum confidence for extracted facts
            hallucination_threshold: Maximum support level before flagging as hallucination
            environment: Environment name for configuration
        """
        self.confidence_threshold = confidence_threshold
        self.hallucination_threshold = hallucination_threshold
        self.environment = environment

        # Initialize components
        self.fact_extractor = FactExtractor(confidence_threshold=confidence_threshold)

        logger.info(f"AEHRL Evaluator initialized for {environment} environment")

    def evaluate_query_response(
        self,
        query_id: str,
        model_response: str,
        retrieved_chunks: List[Dict[str, Any]],
        graph_context: Optional[Dict[str, Any]] = None,
        dictionary_entries: Optional[List[Dict[str, Any]]] = None,
        persona_context: Optional[Any] = None
    ) -> AEHRLReport:
        """
        Evaluate a query response for hallucinations.

        Args:
            query_id: Unique query identifier
            model_response: The model's response text
            retrieved_chunks: Retrieved source chunks
            graph_context: Graph context information
            dictionary_entries: Relevant dictionary entries

        Returns:
            AEHRL evaluation report
        """
        start_time = time.time()

        try:
            logger.info(f"Starting query-time evaluation for query {query_id}")

            # Extract factual claims from response
            claims = self.fact_extractor.extract_facts(
                text=model_response,
                context=f"Query response for {query_id}"
            )

            logger.debug(f"Extracted {len(claims)} fact claims from response")

            # Gather evidence for each claim
            hallucination_flags = []
            total_support_score = 0.0

            for claim in claims:
                evidence = self._gather_evidence(
                    claim=claim,
                    retrieved_chunks=retrieved_chunks,
                    graph_context=graph_context,
                    dictionary_entries=dictionary_entries
                )

                # Evaluate claim support
                support_score = self._calculate_support_score(evidence)
                total_support_score += support_score

                # Flag if insufficient support
                if support_score < self.hallucination_threshold:
                    flag = self._create_hallucination_flag(
                        claim=claim,
                        evidence=evidence,
                        support_score=support_score,
                        query_id=query_id
                    )
                    hallucination_flags.append(flag)

            # Calculate metrics
            processing_time_ms = (time.time() - start_time) * 1000
            metrics = self._calculate_metrics(
                query_id=query_id,
                claims=claims,
                flags=hallucination_flags,
                total_support_score=total_support_score,
                processing_time_ms=processing_time_ms
            )

            # Create report
            report = AEHRLReport(
                query_id=query_id,
                environment=self.environment,
                evaluation_type="query_time",
                status="completed",
                hallucination_flags=hallucination_flags,
                metrics=metrics,
                processing_time_ms=processing_time_ms
            )

            logger.info(
                f"Query evaluation completed for {query_id}. "
                f"Flagged {len(hallucination_flags)}/{len(claims)} claims"
            )

            return report

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error evaluating query {query_id}: {str(e)}")

            return AEHRLReport(
                query_id=query_id,
                environment=self.environment,
                evaluation_type="query_time",
                status="failed",
                processing_time_ms=processing_time_ms,
                error_message=str(e)
            )

    def evaluate_ingestion_artifacts(
        self,
        job_id: str,
        artifacts_path: Path,
        hgrn_report: Optional[Dict[str, Any]] = None
    ) -> AEHRLReport:
        """
        Evaluate ingestion artifacts for quality issues.

        Args:
            job_id: Ingestion job identifier
            artifacts_path: Path to job artifacts
            hgrn_report: Existing HGRN report data

        Returns:
            AEHRL evaluation report with correction recommendations
        """
        start_time = time.time()

        try:
            logger.info(f"Starting ingestion evaluation for job {job_id}")

            # Load ingestion artifacts
            artifacts = self._load_ingestion_artifacts(artifacts_path)

            # Generate correction recommendations
            corrections = []

            # Check for dictionary inconsistencies
            dict_corrections = self._evaluate_dictionary_consistency(
                artifacts.get("dictionary", {}),
                job_id
            )
            corrections.extend(dict_corrections)

            # Check for graph integrity issues
            graph_corrections = self._evaluate_graph_integrity(
                artifacts.get("graph", {}),
                job_id
            )
            corrections.extend(graph_corrections)

            # Check chunk quality
            chunk_corrections = self._evaluate_chunk_quality(
                artifacts.get("chunks", []),
                job_id
            )
            corrections.extend(chunk_corrections)

            # Process HGRN report if available
            if hgrn_report:
                hgrn_corrections = self._process_hgrn_recommendations(
                    hgrn_report,
                    job_id
                )
                corrections.extend(hgrn_corrections)

            processing_time_ms = (time.time() - start_time) * 1000

            report = AEHRLReport(
                job_id=job_id,
                environment=self.environment,
                evaluation_type="ingestion_time",
                status="completed",
                correction_recommendations=corrections,
                processing_time_ms=processing_time_ms
            )

            logger.info(
                f"Ingestion evaluation completed for {job_id}. "
                f"Generated {len(corrections)} correction recommendations"
            )

            return report

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            logger.error(f"Error evaluating ingestion {job_id}: {str(e)}")

            return AEHRLReport(
                job_id=job_id,
                environment=self.environment,
                evaluation_type="ingestion_time",
                status="failed",
                processing_time_ms=processing_time_ms,
                error_message=str(e)
            )

    def _gather_evidence(
        self,
        claim: FactClaim,
        retrieved_chunks: List[Dict[str, Any]],
        graph_context: Optional[Dict[str, Any]] = None,
        dictionary_entries: Optional[List[Dict[str, Any]]] = None
    ) -> List[SupportEvidence]:
        """Gather supporting or contradicting evidence for a claim."""
        evidence = []

        try:
            # Search retrieved chunks
            for chunk in retrieved_chunks:
                chunk_evidence = self._search_chunk_for_evidence(claim, chunk)
                if chunk_evidence:
                    evidence.append(chunk_evidence)

            # Search graph context
            if graph_context:
                graph_evidence = self._search_graph_for_evidence(claim, graph_context)
                if graph_evidence:
                    evidence.append(graph_evidence)

            # Search dictionary entries
            if dictionary_entries:
                for entry in dictionary_entries:
                    dict_evidence = self._search_dictionary_for_evidence(claim, entry)
                    if dict_evidence:
                        evidence.append(dict_evidence)

        except Exception as e:
            logger.warning(f"Error gathering evidence for claim: {str(e)}")

        return evidence

    def _search_chunk_for_evidence(
        self,
        claim: FactClaim,
        chunk: Dict[str, Any]
    ) -> Optional[SupportEvidence]:
        """Search a chunk for evidence supporting/contradicting a claim."""
        try:
            chunk_text = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "unknown")

            # Simple text similarity and keyword matching
            claim_keywords = self._extract_keywords(claim.text)
            chunk_keywords = self._extract_keywords(chunk_text)

            # Calculate keyword overlap
            overlap = len(set(claim_keywords) & set(chunk_keywords))
            similarity = overlap / max(len(claim_keywords), 1)

            if similarity > 0.3:  # Threshold for relevance
                # Determine support level based on content analysis
                support_level = self._determine_support_level(claim.text, chunk_text)

                return SupportEvidence(
                    source=f"chunk:{chunk_id}",
                    text=chunk_text[:500],  # Truncate for storage
                    support_level=support_level,
                    confidence=min(0.9, similarity + 0.3),
                    citation_info={
                        "chunk_id": chunk_id,
                        "page_number": chunk.get("page_number"),
                        "source_file": chunk.get("source_file")
                    },
                    metadata={
                        "similarity_score": similarity,
                        "keyword_overlap": overlap
                    }
                )

        except Exception as e:
            logger.warning(f"Error searching chunk for evidence: {str(e)}")

        return None

    def _search_graph_for_evidence(
        self,
        claim: FactClaim,
        graph_context: Dict[str, Any]
    ) -> Optional[SupportEvidence]:
        """Search graph context for evidence."""
        try:
            # Extract entities from claim
            entities = self.fact_extractor.extract_entities(claim.text)

            # Search for relevant nodes/edges in graph
            nodes = graph_context.get("nodes", [])
            edges = graph_context.get("edges", [])

            relevant_info = []

            # Check nodes
            for node in nodes:
                node_name = node.get("name", "").lower()
                if any(entity.lower() in node_name for entity_list in entities.values() for entity in entity_list):
                    relevant_info.append(f"Node: {node}")

            # Check edges
            for edge in edges:
                edge_desc = f"{edge.get('source', '')} -> {edge.get('target', '')}"
                if any(entity.lower() in edge_desc.lower() for entity_list in entities.values() for entity in entity_list):
                    relevant_info.append(f"Edge: {edge}")

            if relevant_info:
                graph_text = "; ".join(relevant_info)
                support_level = self._determine_support_level(claim.text, graph_text)

                return SupportEvidence(
                    source="graph:context",
                    text=graph_text[:500],
                    support_level=support_level,
                    confidence=0.8,
                    citation_info={"source_type": "graph"},
                    metadata={"relevant_elements": len(relevant_info)}
                )

        except Exception as e:
            logger.warning(f"Error searching graph for evidence: {str(e)}")

        return None

    def _search_dictionary_for_evidence(
        self,
        claim: FactClaim,
        entry: Dict[str, Any]
    ) -> Optional[SupportEvidence]:
        """Search dictionary entry for evidence."""
        try:
            term = entry.get("term", "")
            definition = entry.get("definition", "")
            full_text = f"{term}: {definition}"

            # Check if claim relates to this dictionary entry
            claim_keywords = self._extract_keywords(claim.text)
            entry_keywords = self._extract_keywords(full_text)

            overlap = len(set(claim_keywords) & set(entry_keywords))
            if overlap > 0:
                support_level = self._determine_support_level(claim.text, full_text)

                return SupportEvidence(
                    source=f"dictionary:{term}",
                    text=full_text,
                    support_level=support_level,
                    confidence=0.85,
                    citation_info={
                        "term": term,
                        "source": entry.get("source", "unknown")
                    },
                    metadata={"keyword_overlap": overlap}
                )

        except Exception as e:
            logger.warning(f"Error searching dictionary for evidence: {str(e)}")

        return None

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract important keywords from text."""
        import re

        # Remove common words and extract meaningful terms
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter out common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'may', 'might', 'can', 'this', 'that', 'these', 'those'
        }

        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        return keywords

    def _determine_support_level(self, claim: str, evidence_text: str) -> SupportLevel:
        """Determine how well evidence supports a claim."""
        claim_lower = claim.lower()
        evidence_lower = evidence_text.lower()

        # Simple heuristic-based support determination
        if claim_lower in evidence_lower:
            return SupportLevel.FULLY_SUPPORTED

        # Check for contradictory language
        contradictory_patterns = [
            r'\bnot\s+' + re.escape(claim_lower),
            r'\bno\s+' + re.escape(claim_lower),
            r'\bnever\s+' + re.escape(claim_lower)
        ]

        for pattern in contradictory_patterns:
            if re.search(pattern, evidence_lower):
                return SupportLevel.CONTRADICTED

        # Check for partial support through keyword overlap
        claim_keywords = set(self._extract_keywords(claim))
        evidence_keywords = set(self._extract_keywords(evidence_text))

        overlap_ratio = len(claim_keywords & evidence_keywords) / max(len(claim_keywords), 1)

        if overlap_ratio > 0.7:
            return SupportLevel.PARTIALLY_SUPPORTED
        elif overlap_ratio > 0.3:
            return SupportLevel.PARTIALLY_SUPPORTED
        else:
            return SupportLevel.UNSUPPORTED

    def _calculate_support_score(self, evidence: List[SupportEvidence]) -> float:
        """Calculate overall support score for a claim."""
        if not evidence:
            return 0.0

        # Weight evidence by support level and confidence
        support_weights = {
            SupportLevel.FULLY_SUPPORTED: 1.0,
            SupportLevel.PARTIALLY_SUPPORTED: 0.6,
            SupportLevel.UNSUPPORTED: 0.0,
            SupportLevel.CONTRADICTED: -0.5
        }

        total_weight = 0.0
        total_score = 0.0

        for ev in evidence:
            weight = ev.confidence
            score = support_weights[ev.support_level] * weight
            total_weight += weight
            total_score += score

        if total_weight == 0:
            return 0.0

        return max(0.0, total_score / total_weight)

    def _create_hallucination_flag(
        self,
        claim: FactClaim,
        evidence: List[SupportEvidence],
        support_score: float,
        query_id: str
    ) -> HallucinationFlag:
        """Create a hallucination flag for an unsupported claim."""
        # Determine severity
        if support_score < 0.1:
            severity = HallucinationSeverity.CRITICAL
        elif support_score < 0.2:
            severity = HallucinationSeverity.HIGH
        elif support_score < 0.3:
            severity = HallucinationSeverity.MEDIUM
        else:
            severity = HallucinationSeverity.LOW

        # Generate reason
        if not evidence:
            reason = "No supporting evidence found in retrieved sources"
        elif any(ev.support_level == SupportLevel.CONTRADICTED for ev in evidence):
            reason = "Claim contradicted by source material"
        else:
            reason = f"Insufficient evidence support (score: {support_score:.2f})"

        # Generate recommended action
        if severity in [HallucinationSeverity.CRITICAL, HallucinationSeverity.HIGH]:
            action = "Remove or significantly revise this claim"
        else:
            action = "Add citation or qualifying language"

        return HallucinationFlag(
            id="",  # Will be generated in __post_init__
            claim=claim,
            severity=severity,
            reason=reason,
            evidence=evidence,
            recommended_action=action,
            query_id=query_id,
            metadata={
                "support_score": support_score,
                "evidence_count": len(evidence)
            }
        )

    def _calculate_metrics(
        self,
        query_id: str,
        claims: List[FactClaim],
        flags: List[HallucinationFlag],
        total_support_score: float,
        processing_time_ms: float
    ) -> AEHRLMetrics:
        """Calculate evaluation metrics."""
        total_claims = len(claims)
        flagged_claims = len(flags)

        if total_claims == 0:
            support_rate = 1.0
            hallucination_rate = 0.0
        else:
            support_rate = max(0.0, total_support_score / total_claims)
            hallucination_rate = flagged_claims / total_claims

        # Calculate citation accuracy (simplified)
        citation_accuracy = 0.9  # Placeholder - would need more sophisticated calculation

        return AEHRLMetrics(
            query_id=query_id,
            support_rate=support_rate,
            hallucination_rate=hallucination_rate,
            citation_accuracy=citation_accuracy,
            total_claims=total_claims,
            flagged_claims=flagged_claims,
            processing_time_ms=processing_time_ms,
            confidence_threshold=self.confidence_threshold
        )

    def _load_ingestion_artifacts(self, artifacts_path: Path) -> Dict[str, Any]:
        """Load ingestion artifacts for evaluation."""
        artifacts = {}

        try:
            # Load dictionary artifacts
            dict_file = artifacts_path / "dictionary.json"
            if dict_file.exists():
                import json
                with open(dict_file, 'r') as f:
                    artifacts["dictionary"] = json.load(f)

            # Load graph artifacts
            graph_file = artifacts_path / "graph.json"
            if graph_file.exists():
                import json
                with open(graph_file, 'r') as f:
                    artifacts["graph"] = json.load(f)

            # Load chunk artifacts
            chunks_file = artifacts_path / "chunks.json"
            if chunks_file.exists():
                import json
                with open(chunks_file, 'r') as f:
                    artifacts["chunks"] = json.load(f)

        except Exception as e:
            logger.warning(f"Error loading artifacts: {str(e)}")

        return artifacts

    def _evaluate_dictionary_consistency(
        self,
        dictionary_data: Dict[str, Any],
        job_id: str
    ) -> List['CorrectionRecommendation']:
        """Evaluate dictionary for consistency issues."""
        # Placeholder - would implement actual dictionary validation
        return []

    def _evaluate_graph_integrity(
        self,
        graph_data: Dict[str, Any],
        job_id: str
    ) -> List['CorrectionRecommendation']:
        """Evaluate graph for integrity issues."""
        # Placeholder - would implement actual graph validation
        return []

    def _evaluate_chunk_quality(
        self,
        chunks_data: List[Dict[str, Any]],
        job_id: str
    ) -> List['CorrectionRecommendation']:
        """Evaluate chunks for quality issues."""
        # Placeholder - would implement actual chunk quality validation
        return []

    def _process_hgrn_recommendations(
        self,
        hgrn_report: Dict[str, Any],
        job_id: str
    ) -> List['CorrectionRecommendation']:
        """Process HGRN recommendations into AEHRL corrections."""
        # Placeholder - would convert HGRN recommendations
        return []