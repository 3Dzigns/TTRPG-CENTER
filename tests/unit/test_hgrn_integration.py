#!/usr/bin/env python3
"""
Unit tests for HGRN integration in TTRPG Center.

Tests the HGRN models, validator, runner, and adapter components
with comprehensive coverage of Pass D validation functionality.
"""

import os
import sys
import json
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import pytest
import tempfile

# Add src_common to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src_common"))

from hgrn.models import (
    HGRNReport, HGRNRecommendation, HGRNValidationStats,
    RecommendationType, ValidationSeverity
)
from hgrn.validator import HGRNValidator
from hgrn.runner import HGRNRunner
from hgrn.adapter import HGRNAdapter


class TestHGRNModels:
    """Test HGRN data models and validation."""

    def test_hgrn_recommendation_creation(self):
        """Test creating valid HGRN recommendations."""
        rec = HGRNRecommendation(
            id="test_rec_001",
            type=RecommendationType.DICTIONARY,
            severity=ValidationSeverity.HIGH,
            confidence=0.85,
            title="Test Dictionary Issue",
            description="Test recommendation description",
            evidence={"test_data": "example"},
            suggested_action="Review dictionary extraction"
        )

        assert rec.id == "test_rec_001"
        assert rec.type == RecommendationType.DICTIONARY
        assert rec.severity == ValidationSeverity.HIGH
        assert rec.confidence == 0.85
        assert not rec.accepted
        assert not rec.rejected

    def test_hgrn_recommendation_validation(self):
        """Test HGRN recommendation validation."""
        # Test invalid confidence range
        with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
            HGRNRecommendation(
                id="test",
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.HIGH,
                confidence=1.5,  # Invalid
                title="Test",
                description="Test",
                evidence={},
                suggested_action="Test"
            )

        # Test empty ID
        with pytest.raises(ValueError, match="Recommendation ID cannot be empty"):
            HGRNRecommendation(
                id="",  # Invalid
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.HIGH,
                confidence=0.8,
                title="Test",
                description="Test",
                evidence={},
                suggested_action="Test"
            )

    def test_hgrn_report_creation_and_methods(self):
        """Test HGRN report creation and utility methods."""
        report = HGRNReport(
            job_id="test_job_001",
            environment="test",
            status="success"
        )

        # Test adding recommendations
        rec1 = HGRNRecommendation(
            id="rec1",
            type=RecommendationType.DICTIONARY,
            severity=ValidationSeverity.CRITICAL,
            confidence=0.9,
            title="Critical Issue",
            description="Test",
            evidence={},
            suggested_action="Fix immediately"
        )

        rec2 = HGRNRecommendation(
            id="rec2",
            type=RecommendationType.GRAPH,
            severity=ValidationSeverity.LOW,
            confidence=0.7,
            title="Minor Issue",
            description="Test",
            evidence={},
            suggested_action="Consider fixing"
        )

        report.add_recommendation(rec1)
        report.add_recommendation(rec2)

        # Test filtering methods
        dict_recs = report.get_recommendations_by_type(RecommendationType.DICTIONARY)
        assert len(dict_recs) == 1
        assert dict_recs[0].id == "rec1"

        high_priority = report.get_high_priority_recommendations()
        assert len(high_priority) == 1
        assert high_priority[0].severity == ValidationSeverity.CRITICAL

        unprocessed = report.get_unprocessed_recommendations()
        assert len(unprocessed) == 2  # Neither accepted nor rejected

    def test_hgrn_report_serialization(self):
        """Test HGRN report to/from dictionary conversion."""
        stats = HGRNValidationStats(
            total_chunks_analyzed=100,
            dictionary_terms_validated=25,
            graph_nodes_validated=50,
            ocr_fallback_triggered=False,
            processing_time_seconds=45.2,
            confidence_threshold_used=0.7,
            package_version="1.2.3"
        )

        rec = HGRNRecommendation(
            id="test_rec",
            type=RecommendationType.CHUNK,
            severity=ValidationSeverity.MEDIUM,
            confidence=0.75,
            title="Test Recommendation",
            description="Test description",
            evidence={"chunks": 42},
            suggested_action="Review chunks",
            page_refs=[1, 2, 3],
            chunk_ids=["chunk1", "chunk2"]
        )

        report = HGRNReport(
            job_id="test_job",
            environment="test",
            status="success",
            recommendations=[rec],
            stats=stats
        )

        # Test serialization
        report_dict = report.to_dict()
        assert report_dict["job_id"] == "test_job"
        assert report_dict["environment"] == "test"
        assert len(report_dict["recommendations"]) == 1
        assert report_dict["stats"]["total_chunks_analyzed"] == 100

        # Test deserialization
        restored_report = HGRNReport.from_dict(report_dict)
        assert restored_report.job_id == "test_job"
        assert len(restored_report.recommendations) == 1
        assert restored_report.recommendations[0].type == RecommendationType.CHUNK
        assert restored_report.stats.total_chunks_analyzed == 100


class TestHGRNValidator:
    """Test HGRN validation engine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.validator = HGRNValidator(confidence_threshold=0.7)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_test_artifacts(self, scenario: str = "normal"):
        """Create test artifacts for different scenarios."""
        # Create artifact directory structure
        pass_a_dir = self.test_dir / "pass_a"
        pass_b_dir = self.test_dir / "pass_b"
        pass_c_dir = self.test_dir / "pass_c"

        for dir_path in [pass_a_dir, pass_b_dir, pass_c_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        if scenario == "normal":
            # Normal artifacts with good data
            pass_a_dir.joinpath("initial_chunks.json").write_text(json.dumps([
                {"id": "chunk1", "text": "Test chunk 1", "page": 1},
                {"id": "chunk2", "text": "Test chunk 2", "page": 2}
            ]))

            pass_b_dir.joinpath("dictionary_updates.json").write_text(json.dumps({
                "terms": [
                    {"term": "Fireball", "definition": "A spell that creates a fiery explosion"},
                    {"term": "Wizard", "definition": "A spellcaster who studies arcane magic"}
                ]
            }))

            pass_c_dir.joinpath("graph_data.json").write_text(json.dumps({
                "nodes": [
                    {"id": "node1", "type": "spell", "name": "Fireball"},
                    {"id": "node2", "type": "class", "name": "Wizard"}
                ],
                "edges": [
                    {"source": "node2", "target": "node1", "relationship": "can_cast"}
                ]
            }))

        elif scenario == "missing_dictionary":
            # Missing dictionary data
            pass_a_dir.joinpath("initial_chunks.json").write_text(json.dumps([
                {"id": "chunk1", "text": "Test chunk 1"}
            ]))

            pass_c_dir.joinpath("graph_data.json").write_text(json.dumps({
                "nodes": [{"id": "node1", "type": "spell"}],
                "edges": []
            }))

        elif scenario == "malformed_dictionary":
            # Malformed dictionary entries
            pass_a_dir.joinpath("initial_chunks.json").write_text(json.dumps([
                {"id": "chunk1", "text": "Test chunk 1"}
            ]))

            pass_b_dir.joinpath("dictionary_updates.json").write_text(json.dumps({
                "terms": [
                    "invalid_entry",  # Should be dict
                    {"term": "Fireball"},  # Missing definition
                    {"definition": "Missing term"}  # Missing term
                ]
            }))

        elif scenario == "empty_graph":
            # Empty graph structure
            pass_a_dir.joinpath("initial_chunks.json").write_text(json.dumps([
                {"id": "chunk1", "text": "Test chunk 1"}
            ]))

            pass_c_dir.joinpath("graph_data.json").write_text(json.dumps({
                "nodes": [],
                "edges": []
            }))

        elif scenario == "chunk_loss":
            # Significant chunk loss between passes
            pass_a_dir.joinpath("initial_chunks.json").write_text(json.dumps([
                {"id": f"chunk{i}", "text": f"Test chunk {i}"} for i in range(100)
            ]))

            pass_c_dir.joinpath("final_chunks.json").write_text(json.dumps([
                {"id": "chunk1", "text": "Only one chunk remains"}
            ]))

    def test_normal_validation_scenario(self):
        """Test validation with normal, healthy artifacts."""
        self.create_test_artifacts("normal")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        assert report.job_id == "test_job"
        assert report.environment == "test"
        assert report.status == "success"
        assert len(report.recommendations) == 0  # No issues found

    def test_missing_dictionary_validation(self):
        """Test validation when dictionary updates are missing."""
        self.create_test_artifacts("missing_dictionary")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        assert report.status in ["recommendations", "critical"]
        dict_recs = report.get_recommendations_by_type(RecommendationType.DICTIONARY)
        assert len(dict_recs) > 0
        assert any("Missing Dictionary Updates" in rec.title for rec in dict_recs)

    def test_malformed_dictionary_validation(self):
        """Test validation with malformed dictionary entries."""
        self.create_test_artifacts("malformed_dictionary")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        dict_recs = report.get_recommendations_by_type(RecommendationType.DICTIONARY)
        malformed_recs = [rec for rec in dict_recs if "Malformed" in rec.title]
        assert len(malformed_recs) > 0
        assert malformed_recs[0].severity == ValidationSeverity.HIGH

    def test_empty_graph_validation(self):
        """Test validation with empty graph structure."""
        self.create_test_artifacts("empty_graph")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        graph_recs = report.get_recommendations_by_type(RecommendationType.GRAPH)
        empty_recs = [rec for rec in graph_recs if "Empty Graph" in rec.title]
        assert len(empty_recs) > 0
        assert empty_recs[0].severity == ValidationSeverity.CRITICAL

    def test_chunk_loss_validation(self):
        """Test validation detecting significant chunk loss."""
        self.create_test_artifacts("chunk_loss")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        chunk_recs = report.get_recommendations_by_type(RecommendationType.CHUNK)
        loss_recs = [rec for rec in chunk_recs if "Chunk Loss" in rec.title]
        assert len(loss_recs) > 0
        assert loss_recs[0].severity == ValidationSeverity.HIGH

    def test_validation_statistics_generation(self):
        """Test validation statistics generation."""
        self.create_test_artifacts("normal")

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=self.test_dir
        )

        assert report.stats is not None
        assert report.stats.total_chunks_analyzed >= 0
        assert report.stats.dictionary_terms_validated >= 0
        assert report.stats.processing_time_seconds > 0
        assert report.stats.confidence_threshold_used == 0.7
        assert report.stats.package_version == "1.2.3"

    def test_validation_error_handling(self):
        """Test validation error handling for missing artifacts."""
        # Try to validate non-existent directory
        non_existent_path = self.test_dir / "does_not_exist"

        report = self.validator.validate_artifacts(
            job_id="test_job",
            environment="test",
            artifacts_path=non_existent_path
        )

        assert report.status == "failed"
        assert report.error_message is not None


class TestHGRNRunner:
    """Test HGRN runner functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_hgrn_runner_initialization(self):
        """Test HGRN runner initialization with different configurations."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "HGRN_CONFIDENCE_THRESHOLD": "0.8"}):
            runner = HGRNRunner(environment="test")
            assert runner.environment == "test"
            assert runner.hgrn_enabled is True
            assert runner.confidence_threshold == 0.8

        with patch.dict(os.environ, {"HGRN_ENABLED": "false"}):
            runner = HGRNRunner(environment="test")
            assert runner.hgrn_enabled is False

    def test_hgrn_disabled_scenario(self):
        """Test HGRN runner when HGRN is disabled."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "false"}):
            runner = HGRNRunner(environment="test")

            report = runner.run_pass_d_validation(
                job_id="test_job",
                artifacts_path=self.test_dir
            )

            assert report.status == "disabled"
            assert report.hgrn_enabled is False
            assert "disabled" in report.error_message.lower()

    @patch('src_common.hgrn.validator.HGRNValidator.validate_artifacts')
    def test_hgrn_enabled_scenario(self, mock_validate):
        """Test HGRN runner when HGRN is enabled."""
        # Mock validator response
        mock_report = HGRNReport(
            job_id="test_job",
            environment="test",
            status="success"
        )
        mock_validate.return_value = mock_report

        with patch.dict(os.environ, {"HGRN_ENABLED": "true"}):
            runner = HGRNRunner(environment="test")

            # Create test artifacts directory
            self.test_dir.mkdir(exist_ok=True)

            report = runner.run_pass_d_validation(
                job_id="test_job",
                artifacts_path=self.test_dir
            )

            assert report.status == "success"
            assert mock_validate.called

            # Check that report was saved
            report_file = self.test_dir / "hgrn_report.json"
            assert report_file.exists()

    def test_report_loading_and_saving(self):
        """Test HGRN report loading and saving."""
        runner = HGRNRunner(environment="test")

        # Create a test report
        test_report = HGRNReport(
            job_id="test_job",
            environment="test",
            status="success"
        )
        test_report.add_recommendation(HGRNRecommendation(
            id="test_rec",
            type=RecommendationType.DICTIONARY,
            severity=ValidationSeverity.MEDIUM,
            confidence=0.8,
            title="Test Recommendation",
            description="Test",
            evidence={},
            suggested_action="Test action"
        ))

        # Save report
        report_file = self.test_dir / "hgrn_report.json"
        runner._save_report(test_report, report_file)

        # Load report
        loaded_report = runner.load_report(report_file)

        assert loaded_report is not None
        assert loaded_report.job_id == "test_job"
        assert len(loaded_report.recommendations) == 1

    def test_recommendation_status_update(self):
        """Test updating recommendation status."""
        runner = HGRNRunner(environment="test")

        # Create and save test report
        test_report = HGRNReport(
            job_id="test_job",
            environment="test",
            status="success"
        )
        test_rec = HGRNRecommendation(
            id="test_rec_123",
            type=RecommendationType.DICTIONARY,
            severity=ValidationSeverity.MEDIUM,
            confidence=0.8,
            title="Test Recommendation",
            description="Test",
            evidence={},
            suggested_action="Test action"
        )
        test_report.add_recommendation(test_rec)

        report_file = self.test_dir / "hgrn_report.json"
        runner._save_report(test_report, report_file)

        # Update recommendation status
        success = runner.update_recommendation_status(
            job_id="test_job",
            artifacts_path=self.test_dir,
            recommendation_id="test_rec_123",
            accepted=True,
            rejected=False
        )

        assert success is True

        # Verify update
        updated_report = runner.load_report(report_file)
        assert updated_report.recommendations[0].accepted is True
        assert updated_report.recommendations[0].rejected is False

    def test_environment_stats(self):
        """Test environment statistics retrieval."""
        with patch.dict(os.environ, {
            "HGRN_ENABLED": "true",
            "HGRN_CONFIDENCE_THRESHOLD": "0.75",
            "HGRN_TIMEOUT_SECONDS": "180"
        }):
            runner = HGRNRunner(environment="test")
            stats = runner.get_environment_stats()

            assert stats["environment"] == "test"
            assert stats["hgrn_enabled"] is True
            assert stats["confidence_threshold"] == 0.75
            assert stats["timeout_seconds"] == 180
            assert "config_source" in stats


class TestHGRNAdapter:
    """Test HGRN adapter functionality."""

    def test_adapter_initialization_without_package(self):
        """Test adapter initialization when HGRN package is not available."""
        adapter = HGRNAdapter()
        assert adapter.is_available() is False

    def test_mock_validation_results(self):
        """Test mock validation results generation."""
        adapter = HGRNAdapter()

        # Create test artifacts directory
        test_dir = Path(tempfile.mkdtemp())
        try:
            (test_dir / "pass_b").mkdir()
            (test_dir / "pass_c").mkdir()

            results = adapter._mock_validation_results("test_job", test_dir)

            assert results["status"] == "mock_success"
            assert results["job_id"] == "test_job"
            assert "mock_data" in results
            assert len(results["recommendations"]) > 0

            # Verify mock recommendations structure
            rec = results["recommendations"][0]
            assert "id" in rec
            assert "type" in rec
            assert "confidence" in rec

        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_results_translation(self):
        """Test translation of external results to internal format."""
        adapter = HGRNAdapter()

        # Mock external results
        external_results = {
            "status": "success",
            "job_id": "test_job",
            "processing_time": 30.5,
            "recommendations": [
                {
                    "id": "ext_rec_001",
                    "type": "dictionary",
                    "severity": "high",
                    "confidence": 0.9,
                    "title": "External Dictionary Issue",
                    "description": "External description",
                    "evidence": {"external": True},
                    "suggested_action": "External action",
                    "page_refs": [1, 2],
                    "chunk_ids": ["chunk1"]
                }
            ],
            "stats": {
                "total_chunks_analyzed": 50,
                "dictionary_terms_validated": 10,
                "graph_nodes_validated": 25,
                "ocr_fallback_triggered": False
            }
        }

        report = adapter.translate_results_to_report(
            external_results,
            job_id="test_job",
            environment="test"
        )

        assert report.job_id == "test_job"
        assert report.environment == "test"
        assert report.status == "success"
        assert len(report.recommendations) == 1

        rec = report.recommendations[0]
        assert rec.type == RecommendationType.DICTIONARY
        assert rec.severity == ValidationSeverity.HIGH
        assert rec.confidence == 0.9

        assert report.stats is not None
        assert report.stats.total_chunks_analyzed == 50

    def test_type_and_severity_mapping(self):
        """Test external type and severity mapping."""
        adapter = HGRNAdapter()

        # Test type mapping
        assert adapter._map_recommendation_type("dictionary") == RecommendationType.DICTIONARY
        assert adapter._map_recommendation_type("graph") == RecommendationType.GRAPH
        assert adapter._map_recommendation_type("chunk") == RecommendationType.CHUNK
        assert adapter._map_recommendation_type("unknown") == RecommendationType.CHUNK

        # Test severity mapping
        assert adapter._map_severity("critical") == ValidationSeverity.CRITICAL
        assert adapter._map_severity("high") == ValidationSeverity.HIGH
        assert adapter._map_severity("medium") == ValidationSeverity.MEDIUM
        assert adapter._map_severity("low") == ValidationSeverity.LOW
        assert adapter._map_severity("unknown") == ValidationSeverity.MEDIUM

    def test_package_info(self):
        """Test package information retrieval."""
        adapter = HGRNAdapter()
        info = adapter.get_package_info()

        assert "package_available" in info
        assert "expected_version" in info
        assert "package_path" in info
        assert info["package_available"] is False  # No real package in test


if __name__ == "__main__":
    pytest.main([__file__])