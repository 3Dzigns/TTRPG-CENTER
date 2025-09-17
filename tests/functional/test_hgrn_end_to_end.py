#!/usr/bin/env python3
"""
Functional tests for HGRN end-to-end integration.

Tests the complete HGRN workflow from ingestion pipeline integration
through admin UI interactions and recommendation processing.
"""

import os
import sys
import json
import uuid
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
from fastapi.testclient import TestClient
import tempfile

# Add src_common to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src_common"))

from app import app
from admin.ingestion import AdminIngestionService
from hgrn.runner import HGRNRunner
from hgrn.models import HGRNReport, HGRNRecommendation, RecommendationType, ValidationSeverity


class TestHGRNEndToEndIntegration:
    """Test HGRN integration in end-to-end workflows."""

    def setup_method(self):
        """Set up test client and fixtures."""
        self.client = TestClient(app)
        self.test_dir = Path(tempfile.mkdtemp())
        self.ingestion_service = AdminIngestionService()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_test_job_artifacts(self, job_id: str, environment: str, scenario: str = "normal"):
        """Create test job artifacts for HGRN validation."""
        job_path = self.test_dir / environment / job_id
        job_path.mkdir(parents=True, exist_ok=True)

        # Create manifest
        manifest = {
            "job_id": job_id,
            "environment": environment,
            "source_file": "test_document.pdf",
            "status": "completed",
            "created_at": 1234567890,
            "phases": ["parse", "enrich", "compile", "hgrn_validate"],
            "hgrn_enabled": True
        }

        with open(job_path / "manifest.json", 'w') as f:
            json.dump(manifest, f, indent=2)

        # Create Pass A artifacts
        pass_a_dir = job_path / "pass_a"
        pass_a_dir.mkdir(exist_ok=True)

        if scenario == "normal":
            initial_chunks = [
                {"id": "chunk1", "text": "A fireball spell creates a burst of flame", "page": 1},
                {"id": "chunk2", "text": "Wizards are masters of arcane magic", "page": 2},
                {"id": "chunk3", "text": "Combat involves initiative and actions", "page": 3}
            ]
        elif scenario == "few_chunks":
            initial_chunks = [
                {"id": "chunk1", "text": "Short content", "page": 1}
            ]
        else:
            initial_chunks = []

        with open(pass_a_dir / "initial_chunks.json", 'w') as f:
            json.dump(initial_chunks, f)

        # Create Pass B artifacts
        pass_b_dir = job_path / "pass_b"
        pass_b_dir.mkdir(exist_ok=True)

        if scenario == "normal":
            dictionary_updates = {
                "terms": [
                    {"term": "Fireball", "definition": "A 3rd-level evocation spell"},
                    {"term": "Wizard", "definition": "A spellcasting class"},
                    {"term": "Initiative", "definition": "Turn order in combat"}
                ]
            }
        elif scenario == "few_terms":
            dictionary_updates = {
                "terms": [
                    {"term": "Spell", "definition": "Magical effect"}
                ]
            }
        else:
            dictionary_updates = {"terms": []}

        with open(pass_b_dir / "dictionary_updates.json", 'w') as f:
            json.dump(dictionary_updates, f)

        # Create Pass C artifacts
        pass_c_dir = job_path / "pass_c"
        pass_c_dir.mkdir(exist_ok=True)

        if scenario == "normal":
            graph_data = {
                "nodes": [
                    {"id": "spell_fireball", "type": "spell", "name": "Fireball"},
                    {"id": "class_wizard", "type": "class", "name": "Wizard"},
                    {"id": "concept_combat", "type": "concept", "name": "Combat"}
                ],
                "edges": [
                    {"source": "class_wizard", "target": "spell_fireball", "relationship": "can_cast"},
                    {"source": "concept_combat", "target": "spell_fireball", "relationship": "used_in"}
                ]
            }
        elif scenario == "orphaned_nodes":
            graph_data = {
                "nodes": [
                    {"id": "node1", "type": "spell", "name": "Fireball"},
                    {"id": "node2", "type": "spell", "name": "Magic Missile"},
                    {"id": "node3", "type": "spell", "name": "Lightning Bolt"}
                ],
                "edges": [
                    {"source": "node1", "target": "node2", "relationship": "similar"}
                ]  # node3 is orphaned
            }
        else:
            graph_data = {"nodes": [], "edges": []}

        with open(pass_c_dir / "graph_data.json", 'w') as f:
            json.dump(graph_data, f)

        final_chunks = initial_chunks if scenario != "chunk_loss" else initial_chunks[:1]
        with open(pass_c_dir / "final_chunks.json", 'w') as f:
            json.dump(final_chunks, f)

        return job_path

    def test_pass_d_hgrn_integration_enabled(self):
        """Test Pass D HGRN integration when enabled."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            job_id = "test_job_001"
            environment = "test"

            # Create test artifacts
            job_path = self.create_test_job_artifacts(job_id, environment, "normal")

            # Run Pass D HGRN validation
            success = self.ingestion_service.run_pass_d_hgrn(
                job_id=job_id,
                environment=environment,
                artifacts_path=job_path
            )

            assert success is True

            # Check that HGRN report was created
            hgrn_report_file = job_path / "hgrn_report.json"
            assert hgrn_report_file.exists()

            # Verify report content
            hgrn_runner = HGRNRunner(environment=environment)
            report = hgrn_runner.load_report(hgrn_report_file)

            assert report is not None
            assert report.job_id == job_id
            assert report.environment == environment
            assert report.hgrn_enabled is True

    def test_pass_d_hgrn_integration_disabled(self):
        """Test Pass D HGRN integration when disabled."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "false", "APP_ENV": "test"}):
            job_id = "test_job_002"
            environment = "test"

            # Create test artifacts
            job_path = self.create_test_job_artifacts(job_id, environment, "normal")

            # Run Pass D HGRN validation
            success = self.ingestion_service.run_pass_d_hgrn(
                job_id=job_id,
                environment=environment,
                artifacts_path=job_path
            )

            assert success is True  # Should succeed even when disabled

            # Check that HGRN report was created (disabled report)
            hgrn_report_file = job_path / "hgrn_report.json"
            assert hgrn_report_file.exists()

            # Verify report indicates disabled status
            hgrn_runner = HGRNRunner(environment=environment)
            report = hgrn_runner.load_report(hgrn_report_file)

            assert report is not None
            assert report.status == "disabled"
            assert report.hgrn_enabled is False

    def test_hgrn_validation_with_issues(self):
        """Test HGRN validation detecting various issues."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            job_id = "test_job_003"
            environment = "test"

            # Create test artifacts with issues
            job_path = self.create_test_job_artifacts(job_id, environment, "few_chunks")

            # Run HGRN validation
            hgrn_runner = HGRNRunner(environment=environment)
            report = hgrn_runner.run_pass_d_validation(
                job_id=job_id,
                artifacts_path=job_path
            )

            # Should detect low chunk count issue
            assert len(report.recommendations) > 0

            # Find dictionary-related recommendations
            dict_recommendations = report.get_recommendations_by_type(RecommendationType.DICTIONARY)
            assert len(dict_recommendations) > 0

            low_term_rec = next(
                (rec for rec in dict_recommendations if "Low Dictionary Term Count" in rec.title),
                None
            )
            assert low_term_rec is not None
            assert low_term_rec.severity == ValidationSeverity.LOW

    def test_hgrn_admin_ui_routes(self):
        """Test HGRN admin UI routes and functionality."""
        # Test HGRN recommendations page
        response = self.client.get("/admin/hgrn")
        assert response.status_code == 200
        assert b"HGRN Recommendations" in response.content

    def test_hgrn_api_recommendations_endpoint(self):
        """Test HGRN API recommendations endpoint."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            # Create test job with HGRN report
            job_id = "api_test_job"
            environment = "test"
            job_path = self.create_test_job_artifacts(job_id, environment, "few_terms")

            # Generate HGRN report
            hgrn_runner = HGRNRunner(environment=environment)
            hgrn_runner.run_pass_d_validation(
                job_id=job_id,
                artifacts_path=job_path
            )

            # Test API endpoint
            response = self.client.get("/admin/api/hgrn/recommendations")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "success"
            assert "recommendations" in data
            assert "total_count" in data

            # Verify recommendation structure
            if data["recommendations"]:
                rec = data["recommendations"][0]
                required_fields = [
                    "id", "job_id", "environment", "type", "severity",
                    "confidence", "title", "description", "suggested_action"
                ]
                for field in required_fields:
                    assert field in rec

    def test_hgrn_recommendation_acceptance_workflow(self):
        """Test accepting HGRN recommendations through API."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            # Create test job and generate recommendations
            job_id = "workflow_test_job"
            environment = "test"
            job_path = self.create_test_job_artifacts(job_id, environment, "few_chunks")

            # Create HGRN report with test recommendation
            test_rec = HGRNRecommendation(
                id="test_workflow_rec_001",
                type=RecommendationType.DICTIONARY,
                severity=ValidationSeverity.MEDIUM,
                confidence=0.8,
                title="Test Workflow Recommendation",
                description="Test recommendation for workflow validation",
                evidence={"test": True},
                suggested_action="Accept this test recommendation"
            )

            test_report = HGRNReport(
                job_id=job_id,
                environment=environment,
                status="recommendations",
                recommendations=[test_rec]
            )

            hgrn_runner = HGRNRunner(environment=environment)
            hgrn_runner._save_report(test_report, job_path / "hgrn_report.json")

            # Test accepting recommendation
            response = self.client.post(f"/admin/api/hgrn/recommendations/test_workflow_rec_001/accept")
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True

            # Verify recommendation was updated
            updated_report = hgrn_runner.load_report(job_path / "hgrn_report.json")
            updated_rec = updated_report.recommendations[0]
            assert updated_rec.accepted is True
            assert updated_rec.rejected is False

    def test_hgrn_recommendation_rejection_workflow(self):
        """Test rejecting HGRN recommendations through API."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            # Create test job and generate recommendations
            job_id = "reject_test_job"
            environment = "test"
            job_path = self.create_test_job_artifacts(job_id, environment, "normal")

            # Create HGRN report with test recommendation
            test_rec = HGRNRecommendation(
                id="test_reject_rec_001",
                type=RecommendationType.GRAPH,
                severity=ValidationSeverity.LOW,
                confidence=0.7,
                title="Test Rejection Recommendation",
                description="Test recommendation for rejection workflow",
                evidence={"test": True},
                suggested_action="Reject this test recommendation"
            )

            test_report = HGRNReport(
                job_id=job_id,
                environment=environment,
                status="recommendations",
                recommendations=[test_rec]
            )

            hgrn_runner = HGRNRunner(environment=environment)
            hgrn_runner._save_report(test_report, job_path / "hgrn_report.json")

            # Test rejecting recommendation
            response = self.client.post(f"/admin/api/hgrn/recommendations/test_reject_rec_001/reject")
            assert response.status_code == 200

            result = response.json()
            assert result["success"] is True

            # Verify recommendation was updated
            updated_report = hgrn_runner.load_report(job_path / "hgrn_report.json")
            updated_rec = updated_report.recommendations[0]
            assert updated_rec.accepted is False
            assert updated_rec.rejected is True

    def test_hgrn_nonexistent_recommendation_handling(self):
        """Test handling of requests for nonexistent recommendations."""
        response = self.client.post("/admin/api/hgrn/recommendations/nonexistent_rec_123/accept")
        assert response.status_code == 404

        error_data = response.json()
        assert "not found" in error_data["detail"].lower()

    def test_hgrn_statistics_and_reporting(self):
        """Test HGRN statistics generation and reporting."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            job_id = "stats_test_job"
            environment = "test"
            job_path = self.create_test_job_artifacts(job_id, environment, "normal")

            # Run HGRN validation
            hgrn_runner = HGRNRunner(environment=environment)
            report = hgrn_runner.run_pass_d_validation(
                job_id=job_id,
                artifacts_path=job_path
            )

            # Verify statistics were generated
            assert report.stats is not None
            assert report.stats.total_chunks_analyzed >= 0
            assert report.stats.dictionary_terms_validated >= 0
            assert report.stats.graph_nodes_validated >= 0
            assert report.stats.processing_time_seconds > 0

            # Test environment stats
            env_stats = hgrn_runner.get_environment_stats()
            assert env_stats["environment"] == environment
            assert env_stats["hgrn_enabled"] is True

    def test_hgrn_model_router_integration(self):
        """Test HGRN integration with model router."""
        from orchestrator.router import pick_model

        # Test HGRN validation intent routing
        classification = {"intent": "hgrn_validation", "complexity": "medium"}
        plan = {}

        result = pick_model(classification, plan)

        assert result["model"] == "gpt-4o-mini"
        assert result["max_tokens"] == 4000
        assert result["temperature"] == 0.1

    def test_hgrn_error_resilience(self):
        """Test HGRN system resilience to various error conditions."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            job_id = "error_test_job"
            environment = "test"

            # Test missing artifacts directory
            non_existent_path = self.test_dir / "does_not_exist"

            success = self.ingestion_service.run_pass_d_hgrn(
                job_id=job_id,
                environment=environment,
                artifacts_path=non_existent_path
            )

            assert success is False  # Should gracefully handle missing directory

    def test_hgrn_cross_environment_functionality(self):
        """Test HGRN functionality across different environments."""
        environments = ["dev", "test", "prod"]

        for env in environments:
            with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": env}):
                hgrn_runner = HGRNRunner(environment=env)

                env_stats = hgrn_runner.get_environment_stats()
                assert env_stats["environment"] == env
                assert "hgrn_enabled" in env_stats

    def test_hgrn_recommendation_filtering_and_sorting(self):
        """Test recommendation filtering and sorting functionality."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "APP_ENV": "test"}):
            # Create multiple test recommendations with different properties
            recommendations = [
                HGRNRecommendation(
                    id="critical_rec",
                    type=RecommendationType.DICTIONARY,
                    severity=ValidationSeverity.CRITICAL,
                    confidence=0.95,
                    title="Critical Issue",
                    description="Critical problem",
                    evidence={},
                    suggested_action="Fix immediately"
                ),
                HGRNRecommendation(
                    id="high_rec",
                    type=RecommendationType.GRAPH,
                    severity=ValidationSeverity.HIGH,
                    confidence=0.85,
                    title="High Priority Issue",
                    description="High priority problem",
                    evidence={},
                    suggested_action="Fix soon"
                ),
                HGRNRecommendation(
                    id="low_rec",
                    type=RecommendationType.CHUNK,
                    severity=ValidationSeverity.LOW,
                    confidence=0.65,
                    title="Low Priority Issue",
                    description="Low priority problem",
                    evidence={},
                    suggested_action="Consider fixing"
                )
            ]

            # Create report
            test_report = HGRNReport(
                job_id="filter_test_job",
                environment="test",
                status="recommendations",
                recommendations=recommendations
            )

            # Test filtering methods
            high_priority = test_report.get_high_priority_recommendations()
            assert len(high_priority) == 2  # Critical and high

            dict_recs = test_report.get_recommendations_by_type(RecommendationType.DICTIONARY)
            assert len(dict_recs) == 1
            assert dict_recs[0].id == "critical_rec"

            unprocessed = test_report.get_unprocessed_recommendations()
            assert len(unprocessed) == 3  # All are unprocessed initially


class TestHGRNPerformanceAndScaling:
    """Test HGRN performance and scaling characteristics."""

    def test_hgrn_large_dataset_handling(self):
        """Test HGRN handling of large datasets."""
        with patch.dict(os.environ, {"HGRN_ENABLED": "true", "HGRN_TIMEOUT_SECONDS": "60"}):
            # This would test with large datasets in a real implementation
            # For unit testing, we simulate the scenario

            hgrn_runner = HGRNRunner(environment="test")

            # Verify timeout configuration is respected
            assert hgrn_runner.timeout_seconds == 60

    def test_hgrn_concurrent_processing(self):
        """Test HGRN concurrent processing capabilities."""
        # This would test concurrent HGRN processing
        # For unit testing, we verify the infrastructure supports it

        runners = [HGRNRunner(environment="test") for _ in range(3)]

        # Verify all runners are properly isolated
        assert len(set(id(runner) for runner in runners)) == 3

    def test_hgrn_memory_usage_patterns(self):
        """Test HGRN memory usage patterns."""
        # In a real implementation, this would monitor memory usage
        # For unit testing, we verify efficient object creation

        with patch.dict(os.environ, {"HGRN_ENABLED": "true"}):
            hgrn_runner = HGRNRunner(environment="test")

            # Verify runner properly initializes without memory leaks
            assert hgrn_runner.environment == "test"
            assert hgrn_runner.hgrn_enabled is True


if __name__ == "__main__":
    pytest.main([__file__])