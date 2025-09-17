"""
Functional tests for AEHRL end-to-end workflows.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


class TestAEHRLQueryEvaluation:
    """Test AEHRL query-time evaluation workflows."""

    def test_query_with_aehrl_enabled(self, test_client):
        """Test query processing with AEHRL evaluation enabled."""
        with patch.dict('os.environ', {'AEHRL_ENABLED': 'true'}):
            response = test_client.post('/rag/ask', json={
                'query': 'What is the armor class of an ancient red dragon?'
            })

            assert response.status_code == 200
            data = response.json()

            # Should include AEHRL section in response
            assert 'aehrl' in data
            assert data['aehrl']['enabled'] is True
            assert 'warnings' in data['aehrl']
            assert 'metrics' in data['aehrl']
            assert 'query_id' in data['aehrl']

    def test_query_with_aehrl_disabled(self, test_client):
        """Test query processing with AEHRL evaluation disabled."""
        with patch.dict('os.environ', {'AEHRL_ENABLED': 'false'}):
            response = test_client.post('/rag/ask', json={
                'query': 'What is the armor class of an ancient red dragon?'
            })

            assert response.status_code == 200
            data = response.json()

            # Should include AEHRL section but disabled
            assert 'aehrl' in data
            assert data['aehrl']['enabled'] is False

    def test_query_with_hallucination_warnings(self, test_client):
        """Test query that should trigger hallucination warnings."""
        # Mock the AEHRL evaluator to return high-priority flags
        with patch('src_common.orchestrator.service.AEHRLEvaluator') as mock_evaluator_class:
            mock_evaluator = MagicMock()
            mock_evaluator_class.return_value = mock_evaluator

            # Create mock report with high-priority flags
            from src_common.aehrl.models import (
                AEHRLReport, HallucinationFlag, FactClaim,
                HallucinationSeverity, AEHRLMetrics
            )

            mock_claim = FactClaim("Dragon has 999 hit points", 0.9)
            mock_flag = HallucinationFlag(
                "test-flag",
                mock_claim,
                HallucinationSeverity.HIGH,
                "No supporting evidence"
            )
            mock_metrics = AEHRLMetrics(
                "test-query", 0.3, 0.7, 0.8, 5, 3, 100
            )
            mock_report = AEHRLReport(
                query_id="test-query",
                hallucination_flags=[mock_flag],
                metrics=mock_metrics
            )

            mock_evaluator.evaluate_query_response.return_value = mock_report

            with patch.dict('os.environ', {'AEHRL_ENABLED': 'true'}):
                response = test_client.post('/rag/ask', json={
                    'query': 'How many hit points does a dragon have?'
                })

                assert response.status_code == 200
                data = response.json()

                # Should include warnings
                assert len(data['aehrl']['warnings']) > 0
                warning = data['aehrl']['warnings'][0]
                assert '⚠️' in warning['message']
                assert 'severity' in warning


class TestAEHRLAdminInterface:
    """Test AEHRL admin interface functionality."""

    def test_aehrl_management_page_loads(self, test_client):
        """Test that AEHRL management page loads successfully."""
        response = test_client.get('/admin/aehrl')

        assert response.status_code == 200
        assert 'AEHRL Management' in response.text
        assert 'Correction Recommendations' in response.text

    def test_get_aehrl_corrections_empty(self, test_client):
        """Test getting AEHRL corrections when none exist."""
        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.get_pending_recommendations.return_value = []

            response = test_client.get('/admin/api/aehrl/corrections')

            assert response.status_code == 200
            data = response.json()

            assert data['status'] == 'success'
            assert data['corrections'] == []
            assert data['total_count'] == 0

    def test_get_aehrl_corrections_with_data(self, test_client):
        """Test getting AEHRL corrections with sample data."""
        from src_common.aehrl.models import CorrectionRecommendation, CorrectionType

        mock_correction = CorrectionRecommendation(
            id="test-correction",
            type=CorrectionType.DICTIONARY_UPDATE,
            target="dragon",
            description="Update dragon stats",
            current_value={"hp": 180},
            suggested_value={"hp": 200},
            confidence=0.85,
            job_id="test-job"
        )

        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.get_pending_recommendations.return_value = [mock_correction]

            response = test_client.get('/admin/api/aehrl/corrections')

            assert response.status_code == 200
            data = response.json()

            assert data['status'] == 'success'
            assert len(data['corrections']) == 1

            correction_data = data['corrections'][0]
            assert correction_data['id'] == 'test-correction'
            assert correction_data['type'] == 'dictionary_update'
            assert correction_data['confidence'] == 0.85

    def test_accept_aehrl_correction_success(self, test_client):
        """Test successfully accepting an AEHRL correction."""
        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.accept_recommendation.return_value = True

            response = test_client.post('/admin/api/aehrl/corrections/test-id/accept')

            assert response.status_code == 200
            data = response.json()

            assert data['success'] is True
            assert 'accepted successfully' in data['message']

    def test_accept_aehrl_correction_not_found(self, test_client):
        """Test accepting non-existent AEHRL correction."""
        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.accept_recommendation.return_value = False

            response = test_client.post('/admin/api/aehrl/corrections/nonexistent/accept')

            assert response.status_code == 404

    def test_reject_aehrl_correction_with_reason(self, test_client):
        """Test rejecting an AEHRL correction with reason."""
        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.reject_recommendation.return_value = True

            response = test_client.post('/admin/api/aehrl/corrections/test-id/reject', json={
                'reason': 'Incorrect suggestion'
            })

            assert response.status_code == 200
            data = response.json()

            assert data['success'] is True
            assert 'rejected successfully' in data['message']

            # Verify reason was passed to manager
            mock_manager.reject_recommendation.assert_called_with(
                recommendation_id='test-id',
                reason='Incorrect suggestion',
                admin_user='admin'
            )

    def test_get_aehrl_metrics(self, test_client):
        """Test getting AEHRL metrics."""
        mock_metrics_summary = {
            'total_queries': 100,
            'avg_hallucination_rate': 0.05,
            'avg_support_rate': 0.92
        }

        mock_correction_stats = {
            'pending_count': 5,
            'pending_by_type': {'dictionary_update': 3, 'graph_edge_fix': 2}
        }

        with patch('src_common.admin_routes.MetricsTracker') as mock_tracker_class:
            with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
                mock_tracker = MagicMock()
                mock_manager = MagicMock()
                mock_tracker_class.return_value = mock_tracker
                mock_manager_class.return_value = mock_manager

                mock_tracker.get_metrics_summary.return_value = mock_metrics_summary
                mock_tracker.get_recent_alerts.return_value = []
                mock_manager.get_correction_statistics.return_value = mock_correction_stats

                response = test_client.get('/admin/api/aehrl/metrics')

                assert response.status_code == 200
                data = response.json()

                assert data['status'] == 'success'
                assert data['metrics']['total_queries'] == 100
                assert data['corrections']['pending_count'] == 5


class TestAEHRLIngestionIntegration:
    """Test AEHRL integration with ingestion pipeline."""

    def test_hgrn_integration_with_aehrl(self):
        """Test that HGRN runner integrates with AEHRL evaluation."""
        from src_common.hgrn.runner import HGRNRunner

        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_path = Path(temp_dir)

            # Create mock artifacts
            (artifacts_path / "pass_a").mkdir()
            (artifacts_path / "pass_b").mkdir()
            (artifacts_path / "pass_c").mkdir()

            # Mock the HGRN validator and AEHRL evaluator
            with patch('src_common.hgrn.runner.HGRNValidator') as mock_validator_class:
                with patch('src_common.hgrn.runner.AEHRLEvaluator') as mock_evaluator_class:
                    with patch('src_common.hgrn.runner.CorrectionManager') as mock_manager_class:
                        # Setup mocks
                        mock_validator = MagicMock()
                        mock_evaluator = MagicMock()
                        mock_manager = MagicMock()

                        mock_validator_class.return_value = mock_validator
                        mock_evaluator_class.return_value = mock_evaluator
                        mock_manager_class.return_value = mock_manager

                        # Mock HGRN report
                        from src_common.hgrn.models import HGRNReport
                        mock_hgrn_report = HGRNReport(
                            job_id="test-job",
                            environment="test",
                            status="completed"
                        )
                        mock_validator.validate_artifacts.return_value = mock_hgrn_report

                        # Mock AEHRL report
                        from src_common.aehrl.models import AEHRLReport
                        mock_aehrl_report = AEHRLReport(
                            job_id="test-job",
                            environment="test",
                            evaluation_type="ingestion_time",
                            status="completed"
                        )
                        mock_evaluator.evaluate_ingestion_artifacts.return_value = mock_aehrl_report

                        # Test integration
                        with patch.dict('os.environ', {'AEHRL_ENABLED': 'true'}):
                            runner = HGRNRunner(environment="test")
                            runner.hgrn_enabled = True

                            report = runner.run_pass_d_validation(
                                job_id="test-job",
                                artifacts_path=artifacts_path
                            )

                            # Verify HGRN validation was called
                            mock_validator.validate_artifacts.assert_called_once()

                            # Verify AEHRL evaluation was called
                            mock_evaluator.evaluate_ingestion_artifacts.assert_called_once()

                            # Verify correction manager was used
                            mock_manager.store_recommendations.assert_called_once()

                            assert report.job_id == "test-job"


class TestAEHRLErrorHandling:
    """Test AEHRL error handling and graceful degradation."""

    def test_query_evaluation_with_aehrl_failure(self, test_client):
        """Test query processing when AEHRL evaluation fails."""
        with patch('src_common.orchestrator.service.AEHRLEvaluator') as mock_evaluator_class:
            # Make AEHRL evaluator raise an exception
            mock_evaluator_class.side_effect = Exception("AEHRL service unavailable")

            with patch.dict('os.environ', {'AEHRL_ENABLED': 'true'}):
                response = test_client.post('/rag/ask', json={
                    'query': 'Test query'
                })

                # Query should still succeed despite AEHRL failure
                assert response.status_code == 200
                data = response.json()

                # Should still have basic response structure
                assert 'query' in data
                assert 'answers' in data

                # AEHRL section should indicate failure gracefully
                assert 'aehrl' in data
                assert data['aehrl']['enabled'] is True

    def test_admin_interface_with_missing_data(self, test_client):
        """Test admin interface when AEHRL data is missing."""
        with patch('src_common.admin_routes.CorrectionManager') as mock_manager_class:
            # Make correction manager raise an exception
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.get_pending_recommendations.side_effect = Exception("Storage error")

            response = test_client.get('/admin/api/aehrl/corrections')

            # Should return error response
            assert response.status_code == 500

    def test_metrics_with_corrupted_data(self, test_client):
        """Test metrics endpoint with corrupted data."""
        with patch('src_common.admin_routes.MetricsTracker') as mock_tracker_class:
            mock_tracker = MagicMock()
            mock_tracker_class.return_value = mock_tracker
            mock_tracker.get_metrics_summary.return_value = {"error": "Corrupted data"}

            response = test_client.get('/admin/api/aehrl/metrics')

            assert response.status_code == 200
            data = response.json()

            # Should handle corrupted data gracefully
            assert data['status'] == 'success'
            assert 'error' in data['metrics']


@pytest.fixture
def test_client():
    """Create test client for API testing."""
    from src_common.app import app
    return TestClient(app)


if __name__ == "__main__":
    pytest.main([__file__])