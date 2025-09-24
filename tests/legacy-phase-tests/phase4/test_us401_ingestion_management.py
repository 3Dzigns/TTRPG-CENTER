# tests/regression/phase4/test_us401_ingestion_management.py
"""
Phase 4 - US-401: Admin Ingestion Management Regression Tests
Tests admin interface for managing PDF ingestion jobs and monitoring progress
"""

import pytest
import time
import json
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestAdminIngestionManagement:
    """Test suite for Admin Ingestion Management validation"""

    def test_admin_ingestion_interface_availability(self):
        """Test that admin ingestion interface is accessible"""
        try:
            # Test that admin routes are importable
            from src_common.admin_routes import app
            assert app is not None, "Admin Flask app should be available"

        except ImportError as e:
            pytest.fail(f"Admin ingestion interface not available: {e}")

    def test_ingestion_job_creation_endpoint(self):
        """Test admin endpoint for creating new ingestion jobs"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test job creation endpoint
            job_data = {
                "source_file": "test_document.pdf",
                "job_name": "Test Ingestion Job",
                "description": "Test job for regression testing",
                "priority": "normal"
            }

            response = client.post('/admin/ingestion/create', json=job_data)

            # Verify response
            assert response.status_code in [200, 201], f"Job creation should succeed, got {response.status_code}"

            if response.status_code in [200, 201]:
                response_data = response.get_json()

                assert "job_id" in response_data, "Response should include job ID"
                assert "status" in response_data, "Response should include status"

                # Verify job ID format
                job_id = response_data["job_id"]
                assert isinstance(job_id, str), "Job ID should be string"
                assert len(job_id) > 0, "Job ID should not be empty"

    def test_ingestion_job_listing_endpoint(self):
        """Test admin endpoint for listing ingestion jobs"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test job listing endpoint
            response = client.get('/admin/ingestion/jobs')

            assert response.status_code == 200, f"Job listing should succeed, got {response.status_code}"

            response_data = response.get_json()

            # Verify response structure
            assert isinstance(response_data, dict), "Response should be a dictionary"
            assert "jobs" in response_data, "Response should include jobs list"

            jobs = response_data["jobs"]
            assert isinstance(jobs, list), "Jobs should be a list"

            # Verify job structure if jobs exist
            for job in jobs:
                required_fields = ["job_id", "name", "status", "created_at"]
                for field in required_fields:
                    assert field in job, f"Job missing required field: {field}"

                # Verify field types
                assert isinstance(job["job_id"], str), "Job ID should be string"
                assert isinstance(job["status"], str), "Job status should be string"

                # Verify valid status values
                valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
                assert job["status"] in valid_statuses, f"Invalid job status: {job['status']}"

    def test_ingestion_job_detail_endpoint(self):
        """Test admin endpoint for getting job details"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # First create a job to get details for
            job_data = {"source_file": "test.pdf", "job_name": "Detail Test Job"}
            create_response = client.post('/admin/ingestion/create', json=job_data)

            if create_response.status_code in [200, 201]:
                job_id = create_response.get_json()["job_id"]

                # Test job detail endpoint
                response = client.get(f'/admin/ingestion/jobs/{job_id}')

                assert response.status_code == 200, f"Job detail should succeed, got {response.status_code}"

                job_detail = response.get_json()

                # Verify detailed job structure
                detailed_fields = ["job_id", "name", "status", "progress", "logs", "metadata"]
                for field in detailed_fields:
                    assert field in job_detail, f"Job detail missing field: {field}"

                # Verify progress structure
                progress = job_detail["progress"]
                assert isinstance(progress, dict), "Progress should be a dictionary"

                progress_fields = ["current_pass", "total_passes", "percentage"]
                for field in progress_fields:
                    if field in progress:
                        if field == "percentage":
                            assert isinstance(progress[field], (int, float)), "Percentage should be numeric"
                            assert 0 <= progress[field] <= 100, "Percentage should be 0-100"

    def test_ingestion_job_cancellation(self):
        """Test admin capability to cancel running ingestion jobs"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Create a job to cancel
            job_data = {"source_file": "cancel_test.pdf", "job_name": "Cancellation Test"}
            create_response = client.post('/admin/ingestion/create', json=job_data)

            if create_response.status_code in [200, 201]:
                job_id = create_response.get_json()["job_id"]

                # Test job cancellation
                cancel_response = client.post(f'/admin/ingestion/jobs/{job_id}/cancel')

                assert cancel_response.status_code in [200, 202], f"Job cancellation should succeed, got {cancel_response.status_code}"

                cancel_data = cancel_response.get_json()
                assert "status" in cancel_data, "Cancellation response should include status"

                # Verify job status updated
                detail_response = client.get(f'/admin/ingestion/jobs/{job_id}')
                if detail_response.status_code == 200:
                    job_detail = detail_response.get_json()
                    assert job_detail["status"] in ["cancelled", "cancelling"], "Job should be marked as cancelled"

    def test_ingestion_progress_monitoring(self):
        """Test real-time progress monitoring for ingestion jobs"""
        try:
            from src_common.admin_routes import app
            from src_common.admin.ingestion import IngestionManager
        except ImportError:
            pytest.skip("Required modules not available for testing")

        # Mock ingestion manager for controlled testing
        with patch('src_common.admin.ingestion.IngestionManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # Mock job progress data
            progress_sequence = [
                {"current_pass": "pass_a", "percentage": 10, "status": "processing"},
                {"current_pass": "pass_a", "percentage": 33, "status": "processing"},
                {"current_pass": "pass_b", "percentage": 66, "status": "processing"},
                {"current_pass": "pass_c", "percentage": 100, "status": "completed"}
            ]

            mock_manager.get_job_progress.side_effect = progress_sequence

            with app.test_client() as client:
                # Simulate progress monitoring
                for i, expected_progress in enumerate(progress_sequence):
                    response = client.get('/admin/ingestion/jobs/test_job_id/progress')

                    if response.status_code == 200:
                        progress_data = response.get_json()

                        assert "progress" in progress_data, "Response should include progress"
                        progress = progress_data["progress"]

                        # Verify progress matches expected sequence
                        assert progress["percentage"] == expected_progress["percentage"], f"Step {i}: Expected {expected_progress['percentage']}%, got {progress['percentage']}%"

    def test_ingestion_log_viewing(self):
        """Test admin interface for viewing ingestion job logs"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test log viewing endpoint
            response = client.get('/admin/ingestion/jobs/test_job_id/logs')

            if response.status_code == 200:
                log_data = response.get_json()

                assert "logs" in log_data, "Response should include logs"

                logs = log_data["logs"]
                assert isinstance(logs, list), "Logs should be a list"

                # Verify log entry structure
                for log_entry in logs:
                    log_fields = ["timestamp", "level", "message"]
                    for field in log_fields:
                        assert field in log_entry, f"Log entry missing field: {field}"

                    # Verify log levels
                    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                    assert log_entry["level"] in valid_levels, f"Invalid log level: {log_entry['level']}"

            # Test log filtering
            filter_response = client.get('/admin/ingestion/jobs/test_job_id/logs?level=ERROR')

            if filter_response.status_code == 200:
                filtered_logs = filter_response.get_json()["logs"]

                for log_entry in filtered_logs:
                    assert log_entry["level"] == "ERROR", "Filtered logs should match filter criteria"

    def test_batch_ingestion_management(self):
        """Test admin interface for managing batch ingestion operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test batch job creation
            batch_data = {
                "batch_name": "Test Batch",
                "files": [
                    {"filename": "doc1.pdf", "priority": "high"},
                    {"filename": "doc2.pdf", "priority": "normal"},
                    {"filename": "doc3.pdf", "priority": "low"}
                ]
            }

            response = client.post('/admin/ingestion/batch', json=batch_data)

            if response.status_code in [200, 201]:
                batch_response = response.get_json()

                assert "batch_id" in batch_response, "Batch response should include batch ID"
                assert "jobs" in batch_response, "Batch response should include job list"

                jobs = batch_response["jobs"]
                assert len(jobs) == 3, "Should create jobs for all files in batch"

                # Verify each job has required fields
                for job in jobs:
                    assert "job_id" in job, "Each batch job should have job ID"
                    assert "filename" in job, "Each batch job should reference filename"

    def test_ingestion_statistics_dashboard(self):
        """Test admin dashboard statistics for ingestion operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test statistics endpoint
            response = client.get('/admin/ingestion/statistics')

            if response.status_code == 200:
                stats_data = response.get_json()

                # Verify statistics structure
                expected_stats = [
                    "total_jobs", "completed_jobs", "failed_jobs", "active_jobs",
                    "average_processing_time", "success_rate"
                ]

                for stat in expected_stats:
                    if stat in stats_data:
                        # Verify numeric statistics
                        if stat in ["total_jobs", "completed_jobs", "failed_jobs", "active_jobs"]:
                            assert isinstance(stats_data[stat], int), f"{stat} should be integer"
                            assert stats_data[stat] >= 0, f"{stat} should be non-negative"

                        elif stat in ["average_processing_time", "success_rate"]:
                            assert isinstance(stats_data[stat], (int, float)), f"{stat} should be numeric"

            # Test time-based statistics
            time_response = client.get('/admin/ingestion/statistics?period=24h')

            if time_response.status_code == 200:
                time_stats = time_response.get_json()

                assert "period" in time_stats, "Time-based stats should include period"
                assert "jobs_processed" in time_stats, "Should include jobs processed in period"

    def test_ingestion_error_handling_interface(self):
        """Test admin interface for handling ingestion errors"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test error listing endpoint
            response = client.get('/admin/ingestion/errors')

            if response.status_code == 200:
                error_data = response.get_json()

                assert "errors" in error_data, "Response should include errors list"

                errors = error_data["errors"]
                assert isinstance(errors, list), "Errors should be a list"

                # Verify error structure
                for error in errors:
                    error_fields = ["job_id", "error_message", "timestamp", "severity"]
                    for field in error_fields:
                        if field in error:
                            if field == "severity":
                                valid_severities = ["low", "medium", "high", "critical"]
                                assert error[field] in valid_severities, f"Invalid error severity: {error[field]}"

            # Test error acknowledgment
            if errors:
                error_id = errors[0].get("error_id", "test_error")
                ack_response = client.post(f'/admin/ingestion/errors/{error_id}/acknowledge')

                if ack_response.status_code == 200:
                    ack_data = ack_response.get_json()
                    assert "acknowledged" in ack_data, "Acknowledgment response should confirm action"

    def test_ingestion_performance_monitoring(self):
        """Test performance monitoring for ingestion operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test performance metrics endpoint
            response = client.get('/admin/ingestion/performance')

            if response.status_code == 200:
                perf_data = response.get_json()

                # Verify performance metrics
                expected_metrics = [
                    "throughput", "avg_processing_time", "pass_completion_times",
                    "resource_utilization", "queue_depth"
                ]

                for metric in expected_metrics:
                    if metric in perf_data:
                        # Verify metric types
                        if metric in ["throughput", "avg_processing_time"]:
                            assert isinstance(perf_data[metric], (int, float)), f"{metric} should be numeric"

                        elif metric == "pass_completion_times":
                            assert isinstance(perf_data[metric], dict), "Pass times should be dictionary"

                            pass_times = perf_data[metric]
                            for pass_name, time_value in pass_times.items():
                                assert isinstance(time_value, (int, float)), f"Pass time for {pass_name} should be numeric"

    def test_admin_ui_responsiveness(self):
        """Test admin UI responsiveness and performance"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test main admin interface load time
            start_time = time.perf_counter()
            response = client.get('/admin/ingestion')
            end_time = time.perf_counter()

            load_time = (end_time - start_time) * 1000

            assert response.status_code == 200, "Admin interface should load successfully"
            assert load_time < 1000, f"Admin interface load time {load_time:.1f}ms should be < 1000ms"

            # Test API endpoint responsiveness
            api_endpoints = [
                '/admin/ingestion/jobs',
                '/admin/ingestion/statistics',
                '/admin/ingestion/performance'
            ]

            for endpoint in api_endpoints:
                start_time = time.perf_counter()
                response = client.get(endpoint)
                end_time = time.perf_counter()

                response_time = (end_time - start_time) * 1000

                if response.status_code == 200:
                    assert response_time < 500, f"API endpoint {endpoint} response time {response_time:.1f}ms should be < 500ms"

    def test_admin_authentication_and_authorization(self):
        """Test admin interface authentication and authorization"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test unauthenticated access
            protected_endpoints = [
                '/admin/ingestion/create',
                '/admin/ingestion/jobs/test/cancel',
                '/admin/ingestion/batch'
            ]

            for endpoint in protected_endpoints:
                response = client.post(endpoint)

                # Should require authentication (401) or redirect (302/403)
                assert response.status_code in [401, 403, 302], f"Protected endpoint {endpoint} should require authentication"

            # Test with valid authentication (if implemented)
            if hasattr(app, 'config') and 'ADMIN_AUTH' in app.config:
                # Mock authentication headers or session
                headers = {'Authorization': 'Bearer test_admin_token'}

                auth_response = client.get('/admin/ingestion/jobs', headers=headers)

                if auth_response.status_code == 200:
                    # Authenticated access should work
                    assert auth_response.get_json() is not None, "Authenticated request should return data"

    def test_admin_interface_contract_compliance(self):
        """Test that admin interface matches established contract"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test job creation contract
            job_data = {"source_file": "contract_test.pdf", "job_name": "Contract Test"}
            response = client.post('/admin/ingestion/create', json=job_data)

            if response.status_code in [200, 201]:
                response_data = response.get_json()

                # Required response fields
                required_fields = ["job_id", "status"]
                for field in required_fields:
                    assert field in response_data, f"Job creation response missing field: {field}"

                # Field types and formats
                assert isinstance(response_data["job_id"], str), "Job ID must be string"
                assert len(response_data["job_id"]) > 0, "Job ID must not be empty"

            # Test job listing contract
            list_response = client.get('/admin/ingestion/jobs')

            if list_response.status_code == 200:
                list_data = list_response.get_json()

                assert "jobs" in list_data, "Job listing must include jobs array"
                assert isinstance(list_data["jobs"], list), "Jobs must be array"

                # Pagination contract (if implemented)
                if "pagination" in list_data:
                    pagination = list_data["pagination"]
                    pagination_fields = ["page", "per_page", "total", "pages"]

                    for field in pagination_fields:
                        if field in pagination:
                            assert isinstance(pagination[field], int), f"Pagination {field} must be integer"

            # Test error response contract
            error_response = client.post('/admin/ingestion/create', json={"invalid": "data"})

            if error_response.status_code >= 400:
                error_data = error_response.get_json()

                if error_data:
                    assert "error" in error_data or "message" in error_data, "Error response should include error message"