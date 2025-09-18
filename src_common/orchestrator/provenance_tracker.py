"""
Answer Provenance Tracker

Main orchestrator for tracking complete answer provenance through all
pipeline stages. Provides transparent, auditable lineage from query
to final answer with detailed source attribution.

Integrates with QueryPlanner (FR-024), Graph Augmented Retrieval (FR-025),
and Hybrid Reranker (FR-026) to provide comprehensive tracking.
"""
from __future__ import annotations

import time
import hashlib
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager

from ..ttrpg_logging import get_logger
from .provenance_models import (
    ProvenanceBundle,
    ProvenanceConfig,
    QueryProvenance,
    RetrievalProvenance,
    RerankingProvenance,
    AnswerProvenance,
    QualityMetrics,
    SourceAttribution,
    ReasoningStep,
    ConfidenceLevel,
    create_confidence_level,
    calculate_source_diversity,
    aggregate_confidence_scores
)

logger = get_logger(__name__)


class ProvenanceTracker:
    """
    Main provenance tracking orchestrator.

    Tracks complete answer lineage through all pipeline stages,
    providing transparency and auditability for AI-generated responses.
    """

    def __init__(self, environment: str = "dev", config: Optional[ProvenanceConfig] = None):
        self.environment = environment
        self.config = config or ProvenanceConfig()
        self.active_bundles: Dict[str, ProvenanceBundle] = {}

        logger.info(f"ProvenanceTracker initialized for environment: {environment}")

    def start_tracking(self, query: str, session_id: Optional[str] = None) -> ProvenanceBundle:
        """
        Start tracking provenance for a new query.

        Args:
            query: The user query to track
            session_id: Optional existing session ID

        Returns:
            ProvenanceBundle for this query
        """
        if not self.config.enabled:
            return ProvenanceBundle(environment=self.environment)

        bundle = ProvenanceBundle(environment=self.environment)
        if session_id:
            bundle.session_id = session_id

        self.active_bundles[bundle.correlation_id] = bundle

        logger.debug(f"Started provenance tracking for query: {query[:50]}...")

        return bundle

    def track_query_processing(
        self,
        bundle: ProvenanceBundle,
        original_query: str,
        processed_query: str,
        classification: Any,
        strategy_info: Dict[str, Any],
        processing_time_ms: float
    ) -> None:
        """
        Track query processing and planning stage.

        Args:
            bundle: ProvenanceBundle to update
            original_query: Original user query
            processed_query: Processed/normalized query
            classification: Query classification result
            strategy_info: Strategy selection information
            processing_time_ms: Processing time
        """
        if not self.config.track_query_processing:
            return

        start_time = time.perf_counter()

        try:
            query_hash = hashlib.sha256(original_query.encode()).hexdigest()[:16]

            provenance = QueryProvenance(
                original_query=original_query,
                processed_query=processed_query,
                query_hash=query_hash,
                intent=getattr(classification, 'intent', 'unknown'),
                domain=getattr(classification, 'domain', 'general'),
                complexity=getattr(classification, 'complexity', 'medium'),
                classification_confidence=getattr(classification, 'confidence', 0.5),
                strategy_selected=strategy_info.get('selected', 'default'),
                strategy_reason=strategy_info.get('reason', 'default selection'),
                alternative_strategies=strategy_info.get('alternatives', []),
                processing_time_ms=processing_time_ms
            )

            bundle.query_provenance = provenance

            tracking_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Query provenance tracked in {tracking_time:.2f}ms")

        except Exception as e:
            logger.warning(f"Error tracking query provenance: {e}")

    def track_retrieval(
        self,
        bundle: ProvenanceBundle,
        strategy: str,
        search_params: Dict[str, Any],
        results: List[Dict[str, Any]],
        graph_data: Optional[Dict[str, Any]] = None,
        retrieval_time_ms: float = 0.0
    ) -> None:
        """
        Track retrieval stage provenance.

        Args:
            bundle: ProvenanceBundle to update
            strategy: Retrieval strategy used
            search_params: Search parameters and configuration
            results: Retrieved results
            graph_data: Graph augmentation data
            retrieval_time_ms: Retrieval time
        """
        if not self.config.track_retrieval:
            return

        start_time = time.perf_counter()

        try:
            # Extract source attributions from results
            sources = []
            for i, result in enumerate(results):
                source = SourceAttribution(
                    source_id=result.get('id', f'result_{i}'),
                    source_path=result.get('source', 'unknown'),
                    source_type=self._extract_source_type(result.get('source', '')),
                    page_number=result.get('metadata', {}).get('page'),
                    section=result.get('metadata', {}).get('section'),
                    relevance_score=result.get('score', 0.0),
                    confidence_score=result.get('confidence', result.get('score', 0.0)),
                    confidence_level=create_confidence_level(result.get('score', 0.0)),
                    excerpt=result.get('content', '')[:200] if self.config.max_source_excerpts > 0 else None,
                    excerpt_length=len(result.get('content', ''))
                )
                sources.append(source)

            # Create retrieval provenance
            provenance = RetrievalProvenance(
                strategy=strategy,
                top_k=search_params.get('top_k', 5),
                graph_expansion_enabled=search_params.get('graph_expansion', False),
                search_terms=search_params.get('search_terms', []),
                expanded_terms=search_params.get('expanded_terms', []),
                filters_applied=search_params.get('filters', []),
                total_candidates=search_params.get('total_candidates', len(results)),
                results_returned=len(results),
                sources_found=sources,
                retrieval_time_ms=retrieval_time_ms
            )

            # Add graph data if available
            if graph_data:
                provenance.graph_nodes_explored = graph_data.get('nodes_explored', 0)
                provenance.relationships_found = graph_data.get('relationships_found', 0)
                provenance.cross_references = graph_data.get('cross_references', [])

            bundle.retrieval_provenance = provenance
            bundle.all_sources.extend(sources)

            tracking_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Retrieval provenance tracked in {tracking_time:.2f}ms")

        except Exception as e:
            logger.warning(f"Error tracking retrieval provenance: {e}")

    def track_reranking(
        self,
        bundle: ProvenanceBundle,
        reranking_data: Dict[str, Any],
        original_results: List[str],
        reranked_results: List[str],
        reranking_time_ms: float = 0.0
    ) -> None:
        """
        Track reranking stage provenance.

        Args:
            bundle: ProvenanceBundle to update
            reranking_data: Reranking configuration and signal data
            original_results: Original result order (IDs)
            reranked_results: Reranked result order (IDs)
            reranking_time_ms: Reranking time
        """
        if not self.config.track_reranking:
            return

        start_time = time.perf_counter()

        try:
            # Calculate ranking changes
            ranking_changes = []
            for i, result_id in enumerate(reranked_results):
                original_rank = original_results.index(result_id) if result_id in original_results else -1
                if original_rank != i:
                    ranking_changes.append({
                        'result_id': result_id,
                        'original_rank': original_rank,
                        'new_rank': i,
                        'rank_change': original_rank - i if original_rank >= 0 else 0
                    })

            # Create reranking provenance
            provenance = RerankingProvenance(
                strategy=reranking_data.get('strategy', 'unknown'),
                signal_weights=reranking_data.get('weights', {}),
                original_ranking=original_results,
                final_ranking=reranked_results,
                ranking_changes=ranking_changes,
                ranking_confidence=reranking_data.get('confidence', 0.0),
                signal_agreement=reranking_data.get('signal_agreement', 0.0),
                reranking_time_ms=reranking_time_ms
            )

            # Add signal details if configured
            if self.config.include_signal_details:
                provenance.vector_signals = reranking_data.get('vector_signals', {})
                provenance.graph_signals = reranking_data.get('graph_signals', {})
                provenance.content_signals = reranking_data.get('content_signals', {})
                provenance.domain_signals = reranking_data.get('domain_signals', {})

            bundle.reranking_provenance = provenance

            tracking_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Reranking provenance tracked in {tracking_time:.2f}ms")

        except Exception as e:
            logger.warning(f"Error tracking reranking provenance: {e}")

    def track_answer_generation(
        self,
        bundle: ProvenanceBundle,
        generation_config: Dict[str, Any],
        reasoning_steps: List[Dict[str, Any]],
        source_usage: Dict[str, Any],
        answer_metrics: Dict[str, Any],
        generation_time_ms: float = 0.0
    ) -> None:
        """
        Track answer generation stage provenance.

        Args:
            bundle: ProvenanceBundle to update
            generation_config: Model and generation configuration
            reasoning_steps: Step-by-step reasoning process
            source_usage: How sources were used in generation
            answer_metrics: Quality metrics for the answer
            generation_time_ms: Generation time
        """
        if not self.config.track_answer_generation:
            return

        start_time = time.perf_counter()

        try:
            # Convert reasoning steps
            steps = []
            if self.config.include_reasoning_steps:
                for i, step_data in enumerate(reasoning_steps):
                    step = ReasoningStep(
                        step_id=f"step_{i}",
                        step_type=step_data.get('type', 'synthesis'),
                        description=step_data.get('description', ''),
                        input_sources=step_data.get('input_sources', []),
                        input_context=step_data.get('input_context', ''),
                        reasoning=step_data.get('reasoning', ''),
                        alternatives_considered=step_data.get('alternatives', []) if self.config.include_alternative_paths else [],
                        decision_rationale=step_data.get('rationale', ''),
                        output=step_data.get('output', ''),
                        confidence=step_data.get('confidence', 0.0)
                    )
                    steps.append(step)

            # Create answer provenance
            provenance = AnswerProvenance(
                model_used=generation_config.get('model', 'unknown'),
                generation_strategy=generation_config.get('strategy', 'default'),
                temperature=generation_config.get('temperature', 0.0),
                max_tokens=generation_config.get('max_tokens', 0),
                reasoning_steps=steps,
                synthesis_approach=generation_config.get('synthesis_approach', ''),
                fact_checking_applied=generation_config.get('fact_checking', False),
                primary_sources=source_usage.get('primary', []),
                supporting_sources=source_usage.get('supporting', []),
                contradictory_sources=source_usage.get('contradictory', []),
                answer_confidence=answer_metrics.get('confidence', 0.0),
                completeness_score=answer_metrics.get('completeness', 0.0),
                accuracy_indicators=answer_metrics.get('accuracy_indicators', []),
                answer_length=answer_metrics.get('length', 0),
                citation_count=answer_metrics.get('citations', 0),
                fact_density=answer_metrics.get('fact_density', 0.0),
                generation_time_ms=generation_time_ms
            )

            bundle.answer_provenance = provenance

            # Update source usage flags
            used_sources = set(source_usage.get('primary', []) + source_usage.get('supporting', []))
            for source in bundle.all_sources:
                if source.source_id in used_sources:
                    source.used_in_answer = True
                    source.contribution_weight = answer_metrics.get('source_weights', {}).get(source.source_id, 0.0)

            tracking_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Answer provenance tracked in {tracking_time:.2f}ms")

        except Exception as e:
            logger.warning(f"Error tracking answer provenance: {e}")

    def calculate_quality_metrics(self, bundle: ProvenanceBundle) -> QualityMetrics:
        """
        Calculate overall quality metrics for the answer.

        Args:
            bundle: ProvenanceBundle to analyze

        Returns:
            QualityMetrics with calculated scores
        """
        start_time = time.perf_counter()

        try:
            # Collect confidence scores
            confidence_scores = []

            if bundle.query_provenance:
                confidence_scores.append(bundle.query_provenance.classification_confidence)

            if bundle.reranking_provenance:
                confidence_scores.append(bundle.reranking_provenance.ranking_confidence)

            if bundle.answer_provenance:
                confidence_scores.append(bundle.answer_provenance.answer_confidence)

            # Calculate overall confidence
            overall_confidence = aggregate_confidence_scores(confidence_scores)

            # Calculate source reliability
            primary_sources = bundle.get_primary_sources()
            source_reliability = self._calculate_source_reliability(primary_sources)

            # Calculate reasoning soundness
            reasoning_soundness = self._calculate_reasoning_soundness(bundle.answer_provenance)

            # Calculate completeness
            completeness = bundle.answer_provenance.completeness_score if bundle.answer_provenance else 0.0

            # Trust indicators
            source_diversity = len(set(source.source_type for source in primary_sources))
            official_source_count = len([s for s in primary_sources if s.source_type in ['phb', 'dmg', 'mm']])
            cross_validation_score = calculate_source_diversity(primary_sources)

            # Risk factors
            potential_inconsistencies = self._identify_inconsistencies(bundle)
            missing_information = self._identify_missing_information(bundle)
            confidence_warnings = self._generate_confidence_warnings(bundle)

            metrics = QualityMetrics(
                overall_confidence=overall_confidence,
                source_reliability=source_reliability,
                reasoning_soundness=reasoning_soundness,
                completeness=completeness,
                source_diversity=source_diversity,
                official_source_count=official_source_count,
                cross_validation_score=cross_validation_score,
                potential_inconsistencies=potential_inconsistencies,
                missing_information=missing_information,
                confidence_warnings=confidence_warnings
            )

            bundle.quality_metrics = metrics

            tracking_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Quality metrics calculated in {tracking_time:.2f}ms")

            return metrics

        except Exception as e:
            logger.warning(f"Error calculating quality metrics: {e}")
            return QualityMetrics()

    def finalize_bundle(self, bundle: ProvenanceBundle) -> ProvenanceBundle:
        """
        Finalize a provenance bundle and mark it as completed.

        Args:
            bundle: ProvenanceBundle to finalize

        Returns:
            Finalized ProvenanceBundle
        """
        try:
            # Calculate quality metrics if not already done
            if not bundle.quality_metrics:
                self.calculate_quality_metrics(bundle)

            # Mark as completed
            bundle.mark_completed()

            # Remove from active bundles
            if bundle.correlation_id in self.active_bundles:
                del self.active_bundles[bundle.correlation_id]

            logger.info(f"Provenance bundle finalized: {bundle.total_time_ms:.2f}ms total")

            return bundle

        except Exception as e:
            logger.warning(f"Error finalizing provenance bundle: {e}")
            return bundle

    @contextmanager
    def track_stage(self, bundle: ProvenanceBundle, stage_name: str):
        """
        Context manager for tracking individual stages.

        Args:
            bundle: ProvenanceBundle to update
            stage_name: Name of the stage being tracked
        """
        start_time = time.perf_counter()
        try:
            logger.debug(f"Starting stage: {stage_name}")
            yield
        finally:
            duration = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Completed stage {stage_name} in {duration:.2f}ms")

    def _extract_source_type(self, source_path: str) -> str:
        """Extract source type from source path."""
        source_path_lower = source_path.lower()

        if 'phb' in source_path_lower:
            return 'phb'
        elif 'dmg' in source_path_lower:
            return 'dmg'
        elif 'mm' in source_path_lower:
            return 'mm'
        elif 'xgte' in source_path_lower:
            return 'xgte'
        elif 'tce' in source_path_lower:
            return 'tce'
        elif 'homebrew' in source_path_lower:
            return 'homebrew'
        else:
            return 'unknown'

    def _calculate_source_reliability(self, sources: List[SourceAttribution]) -> float:
        """Calculate reliability score based on source types and quality."""
        if not sources:
            return 0.0

        reliability_weights = {
            'phb': 1.0,
            'dmg': 0.95,
            'mm': 0.9,
            'xgte': 0.85,
            'tce': 0.85,
            'homebrew': 0.3,
            'unknown': 0.1
        }

        total_weight = 0.0
        weighted_reliability = 0.0

        for source in sources:
            weight = source.contribution_weight or 1.0
            reliability = reliability_weights.get(source.source_type, 0.5)

            total_weight += weight
            weighted_reliability += weight * reliability

        return weighted_reliability / total_weight if total_weight > 0 else 0.0

    def _calculate_reasoning_soundness(self, answer_provenance: Optional[AnswerProvenance]) -> float:
        """Calculate reasoning soundness based on reasoning steps."""
        if not answer_provenance or not answer_provenance.reasoning_steps:
            return 0.5  # Neutral score if no reasoning data

        step_confidences = [step.confidence for step in answer_provenance.reasoning_steps if step.confidence > 0]

        if not step_confidences:
            return 0.5

        # Use minimum confidence as bottleneck
        return min(step_confidences)

    def _identify_inconsistencies(self, bundle: ProvenanceBundle) -> List[str]:
        """Identify potential inconsistencies in the answer."""
        inconsistencies = []

        # Check for conflicting sources
        if bundle.answer_provenance and bundle.answer_provenance.contradictory_sources:
            inconsistencies.append("Contradictory sources found")

        # Check confidence mismatches
        confidence_summary = bundle.get_confidence_summary()
        if len(confidence_summary) > 1:
            scores = list(confidence_summary.values())
            if max(scores) - min(scores) > 0.5:
                inconsistencies.append("Large confidence variation across stages")

        return inconsistencies

    def _identify_missing_information(self, bundle: ProvenanceBundle) -> List[str]:
        """Identify missing information that could affect answer quality."""
        missing = []

        # Check stage completeness
        stage_status = bundle.get_stage_status()
        for stage, completed in stage_status.items():
            if not completed:
                missing.append(f"Missing {stage} provenance")

        # Check source diversity
        if len(bundle.all_sources) < 2:
            missing.append("Limited source diversity")

        return missing

    def _generate_confidence_warnings(self, bundle: ProvenanceBundle) -> List[str]:
        """Generate warnings based on confidence levels."""
        warnings = []

        confidence_summary = bundle.get_confidence_summary()

        for stage, confidence in confidence_summary.items():
            if confidence < 0.3:
                warnings.append(f"Very low confidence in {stage} ({confidence:.2f})")
            elif confidence < 0.5:
                warnings.append(f"Low confidence in {stage} ({confidence:.2f})")

        return warnings

    def get_active_bundles(self) -> Dict[str, ProvenanceBundle]:
        """Get all currently active provenance bundles."""
        return self.active_bundles.copy()

    def get_bundle_by_session(self, session_id: str) -> Optional[ProvenanceBundle]:
        """Get provenance bundle by session ID."""
        for bundle in self.active_bundles.values():
            if bundle.session_id == session_id:
                return bundle
        return None

    def clear_expired_bundles(self, max_age_hours: int = 24) -> int:
        """Clear expired bundles from active tracking."""
        current_time = time.time()
        expired_bundles = []

        for correlation_id, bundle in self.active_bundles.items():
            age_hours = (current_time - bundle.started_at) / 3600
            if age_hours > max_age_hours:
                expired_bundles.append(correlation_id)

        for correlation_id in expired_bundles:
            del self.active_bundles[correlation_id]

        if expired_bundles:
            logger.info(f"Cleared {len(expired_bundles)} expired provenance bundles")

        return len(expired_bundles)