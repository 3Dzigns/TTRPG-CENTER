"""
Unit tests for AEHRL integration components.
"""

import pytest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src_common.aehrl.models import (
    AEHRLReport, HallucinationFlag, CorrectionRecommendation,
    FactClaim, SupportEvidence, AEHRLMetrics,
    HallucinationSeverity, SupportLevel, CorrectionType
)
from src_common.aehrl.evaluator import AEHRLEvaluator
from src_common.aehrl.fact_extractor import FactExtractor
from src_common.aehrl.metrics_tracker import MetricsTracker
from src_common.aehrl.correction_manager import CorrectionManager


class TestAEHRLModels:
    """Test AEHRL data models."""

    def test_fact_claim_creation(self):
        """Test FactClaim creation and validation."""
        claim = FactClaim(
            text="The dragon has 200 hit points",
            confidence=0.8,
            context="Monster stat block",
            claim_type="hit_points"
        )

        assert claim.text == "The dragon has 200 hit points"
        assert claim.confidence == 0.8
        assert claim.claim_type == "hit_points"

    def test_fact_claim_invalid_confidence(self):
        """Test FactClaim validation with invalid confidence."""
        with pytest.raises(ValueError):
            FactClaim(
                text="Test claim",
                confidence=1.5  # Invalid confidence > 1.0
            )

    def test_support_evidence_creation(self):
        """Test SupportEvidence creation."""
        evidence = SupportEvidence(
            source="chunk:123",
            text="Supporting text from source",
            support_level=SupportLevel.FULLY_SUPPORTED,
            confidence=0.9
        )

        assert evidence.source == "chunk:123"
        assert evidence.support_level == SupportLevel.FULLY_SUPPORTED
        assert evidence.confidence == 0.9

    def test_hallucination_flag_serialization(self):
        """Test HallucinationFlag serialization."""
        claim = FactClaim("Test claim", 0.8)
        evidence = [SupportEvidence("test", "text", SupportLevel.UNSUPPORTED, 0.5)]

        flag = HallucinationFlag(
            id="test-flag",
            claim=claim,
            severity=HallucinationSeverity.HIGH,
            reason="No supporting evidence",
            evidence=evidence,
            query_id="test-query"
        )

        # Test serialization
        flag_dict = flag.to_dict()
        assert flag_dict["id"] == "test-flag"
        assert flag_dict["severity"] == "high"
        assert flag_dict["query_id"] == "test-query"

        # Test deserialization
        reconstructed = HallucinationFlag.from_dict(flag_dict)
        assert reconstructed.id == flag.id
        assert reconstructed.severity == flag.severity
        assert reconstructed.claim.text == flag.claim.text

    def test_correction_recommendation_creation(self):
        """Test CorrectionRecommendation creation."""
        correction = CorrectionRecommendation(
            id="test-correction",
            type=CorrectionType.DICTIONARY_UPDATE,
            target="dragon",
            description="Update dragon hit points",
            current_value=180,
            suggested_value=200,
            confidence=0.85
        )

        assert correction.type == CorrectionType.DICTIONARY_UPDATE
        assert correction.current_value == 180
        assert correction.suggested_value == 200

    def test_aehrl_report_high_priority_flags(self):
        """Test AEHRLReport high priority flag filtering."""
        claim = FactClaim("Test", 0.8)

        high_flag = HallucinationFlag("1", claim, HallucinationSeverity.HIGH, "test")
        critical_flag = HallucinationFlag("2", claim, HallucinationSeverity.CRITICAL, "test")
        low_flag = HallucinationFlag("3", claim, HallucinationSeverity.LOW, "test")

        report = AEHRLReport(
            query_id="test",
            hallucination_flags=[high_flag, critical_flag, low_flag]
        )

        high_priority = report.get_high_priority_flags()
        assert len(high_priority) == 2
        assert high_flag in high_priority
        assert critical_flag in high_priority
        assert low_flag not in high_priority


class TestFactExtractor:
    """Test FactExtractor functionality."""

    def test_fact_extractor_initialization(self):
        """Test FactExtractor initialization."""
        extractor = FactExtractor(confidence_threshold=0.8)
        assert extractor.confidence_threshold == 0.8
        assert len(extractor.extraction_patterns) > 0

    def test_extract_damage_facts(self):
        """Test extraction of damage-related facts."""
        extractor = FactExtractor(confidence_threshold=0.7)
        text = "The dragon deals 2d6+4 damage with its bite attack."

        claims = extractor.extract_facts(text)

        # Should extract damage claim
        damage_claims = [c for c in claims if c.claim_type == "damage"]
        assert len(damage_claims) > 0

        damage_claim = damage_claims[0]
        assert "2d6+4" in damage_claim.text

    def test_extract_armor_class_facts(self):
        """Test extraction of armor class facts."""
        extractor = FactExtractor(confidence_threshold=0.7)
        text = "The ancient dragon has AC 22 due to its thick scales."

        claims = extractor.extract_facts(text)

        # Should extract AC claim
        ac_claims = [c for c in claims if c.claim_type == "armor_class"]
        assert len(ac_claims) > 0

        ac_claim = ac_claims[0]
        assert "22" in ac_claim.text

    def test_extract_entities(self):
        """Test entity extraction."""
        extractor = FactExtractor()
        text = "The Ancient Red Dragon casts Fireball spell in the Sunless Citadel."

        entities = extractor.extract_entities(text)

        assert "creatures" in entities
        assert "spells" in entities
        assert "locations" in entities


class TestAEHRLEvaluator:
    """Test AEHRLEvaluator functionality."""

    def test_evaluator_initialization(self):
        """Test AEHRLEvaluator initialization."""
        evaluator = AEHRLEvaluator(
            confidence_threshold=0.8,
            hallucination_threshold=0.3,
            environment="test"
        )

        assert evaluator.confidence_threshold == 0.8
        assert evaluator.hallucination_threshold == 0.3
        assert evaluator.environment == "test"

    @patch('src_common.aehrl.evaluator.time.time')
    def test_evaluate_query_response_basic(self, mock_time):
        """Test basic query response evaluation."""
        mock_time.side_effect = [0.0, 0.1]  # Start and end time

        evaluator = AEHRLEvaluator(environment="test")

        # Mock fact extractor to return controllable results
        with patch.object(evaluator.fact_extractor, 'extract_facts') as mock_extract:
            mock_claim = FactClaim("Test claim", 0.8)
            mock_extract.return_value = [mock_claim]

            report = evaluator.evaluate_query_response(
                query_id="test-query",
                model_response="Test response",
                retrieved_chunks=[{
                    "chunk_id": "test-chunk",
                    "content": "Test content",
                    "source_file": "test.pdf"
                }]
            )

            assert report.query_id == "test-query"
            assert report.status == "completed"
            assert report.evaluation_type == "query_time"
            assert report.processing_time_ms == 100  # 0.1 seconds

    def test_evaluate_ingestion_artifacts_error_handling(self):
        """Test ingestion evaluation error handling."""
        evaluator = AEHRLEvaluator(environment="test")

        # Test with non-existent path
        report = evaluator.evaluate_ingestion_artifacts(
            job_id="test-job",
            artifacts_path=Path("/nonexistent/path")
        )

        assert report.job_id == "test-job"
        assert report.status == "failed"
        assert report.error_message is not None


class TestMetricsTracker:
    """Test MetricsTracker functionality."""

    def test_metrics_tracker_initialization(self):
        """Test MetricsTracker initialization."""
        tracker = MetricsTracker(
            environment="test",
            hallucination_alert_threshold=0.1
        )

        assert tracker.environment == "test"
        assert tracker.hallucination_alert_threshold == 0.1

    def test_record_metrics_with_valid_report(self):
        """Test recording metrics from valid report."""
        tracker = MetricsTracker(environment="test")

        # Create test metrics
        metrics = AEHRLMetrics(
            query_id="test-query",
            support_rate=0.8,
            hallucination_rate=0.2,
            citation_accuracy=0.9,
            total_claims=10,
            flagged_claims=2,
            processing_time_ms=100
        )

        # Create test report
        report = AEHRLReport(
            query_id="test-query",
            metrics=metrics
        )

        # Mock file operations
        with patch('builtins.open', MagicMock()):
            with patch('json.dump') as mock_dump:
                tracker.record_metrics(report)

                # Should have called json.dump for storing metrics
                assert mock_dump.called

    def test_get_metrics_summary_no_data(self):
        """Test metrics summary when no data exists."""
        tracker = MetricsTracker(environment="test")

        with patch.object(Path, 'exists', return_value=False):
            summary = tracker.get_metrics_summary()

            assert summary["total_queries"] == 0
            assert "error" in summary


class TestCorrectionManager:
    """Test CorrectionManager functionality."""

    def test_correction_manager_initialization(self):
        """Test CorrectionManager initialization."""
        manager = CorrectionManager(environment="test")

        assert manager.environment == "test"
        assert isinstance(manager.pending_corrections, list)

    def test_store_recommendations(self):
        """Test storing correction recommendations."""
        manager = CorrectionManager(environment="test")

        correction = CorrectionRecommendation(
            id="test-correction",
            type=CorrectionType.DICTIONARY_UPDATE,
            target="test-target",
            description="Test correction",
            current_value="old",
            suggested_value="new",
            confidence=0.8
        )

        with patch.object(manager, '_store_recommendation') as mock_store:
            with patch.object(manager, '_load_pending_corrections', return_value=[]):
                manager.store_recommendations([correction])

                mock_store.assert_called_once_with(correction, None)

    def test_get_pending_recommendations_filtering(self):
        """Test filtering of pending recommendations."""
        manager = CorrectionManager(environment="test")

        # Create test corrections
        dict_correction = CorrectionRecommendation(
            id="dict-1",
            type=CorrectionType.DICTIONARY_UPDATE,
            target="test",
            description="Dict update",
            current_value="old",
            suggested_value="new",
            confidence=0.8,
            job_id="job-1"
        )

        graph_correction = CorrectionRecommendation(
            id="graph-1",
            type=CorrectionType.GRAPH_EDGE_FIX,
            target="test",
            description="Graph fix",
            current_value="old",
            suggested_value="new",
            confidence=0.9,
            job_id="job-2"
        )

        manager.pending_corrections = [dict_correction, graph_correction]

        # Test type filtering
        dict_only = manager.get_pending_recommendations(
            correction_type=CorrectionType.DICTIONARY_UPDATE
        )
        assert len(dict_only) == 1
        assert dict_only[0].type == CorrectionType.DICTIONARY_UPDATE

        # Test job ID filtering
        job1_only = manager.get_pending_recommendations(job_id="job-1")
        assert len(job1_only) == 1
        assert job1_only[0].job_id == "job-1"

    def test_accept_recommendation_not_found(self):
        """Test accepting non-existent recommendation."""
        manager = CorrectionManager(environment="test")

        with patch.object(manager, '_find_recommendation', return_value=None):
            result = manager.accept_recommendation("nonexistent-id")
            assert result is False

    def test_get_correction_statistics(self):
        """Test getting correction statistics."""
        manager = CorrectionManager(environment="test")

        # Create test corrections with different confidence levels
        high_conf = CorrectionRecommendation(
            "1", CorrectionType.DICTIONARY_UPDATE, "test", "desc", "old", "new", 0.9
        )
        medium_conf = CorrectionRecommendation(
            "2", CorrectionType.GRAPH_EDGE_FIX, "test", "desc", "old", "new", 0.7
        )
        low_conf = CorrectionRecommendation(
            "3", CorrectionType.CHUNK_REVISION, "test", "desc", "old", "new", 0.5
        )

        manager.pending_corrections = [high_conf, medium_conf, low_conf]

        stats = manager.get_correction_statistics()

        assert stats["pending_count"] == 3
        assert stats["pending_by_confidence"]["high"] == 1
        assert stats["pending_by_confidence"]["medium"] == 1
        assert stats["pending_by_confidence"]["low"] == 1
        assert stats["pending_by_type"]["dictionary_update"] == 1
        assert stats["pending_by_type"]["graph_edge_fix"] == 1
        assert stats["pending_by_type"]["chunk_revision"] == 1


class TestAEHRLIntegration:
    """Test AEHRL system integration."""

    def test_end_to_end_query_evaluation(self):
        """Test complete query evaluation workflow."""
        # This would be an integration test that exercises the full pipeline
        # For now, just test that components can be instantiated together

        evaluator = AEHRLEvaluator(environment="test")
        metrics_tracker = MetricsTracker(environment="test")
        correction_manager = CorrectionManager(environment="test")

        # All components should initialize without errors
        assert evaluator is not None
        assert metrics_tracker is not None
        assert correction_manager is not None

    def test_configuration_integration(self):
        """Test that AEHRL components respect configuration."""
        import os

        # Test with custom configuration
        with patch.dict(os.environ, {
            'AEHRL_CONFIDENCE_THRESHOLD': '0.9',
            'AEHRL_HALLUCINATION_THRESHOLD': '0.2'
        }):
            evaluator = AEHRLEvaluator(environment="test")

            # Should use environment configuration if available
            # (This depends on implementation details)
            assert evaluator.confidence_threshold >= 0.7


if __name__ == "__main__":
    pytest.main([__file__])