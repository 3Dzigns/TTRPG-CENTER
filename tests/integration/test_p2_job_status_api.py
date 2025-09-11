"""
P2.1 Integration Tests: Job Status API
Tests for FastAPI job status endpoints and WebSocket functionality.
"""

import asyncio
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src_common.job_status_api import create_job_status_api, websocket_manager, JobStatusProgressCallback
from src_common.job_status_store import JobStatusStore, JobStatusRecord
from src_common.progress_callback import JobProgress, PassProgress, PassType, PassStatus
from src_common.job_dashboard import create_dashboard_routes


@pytest.fixture
def mock_job_store():
    """Create mock job store for testing"""
    store = MagicMock(spec=JobStatusStore)
    
    # Mock some sample data
    active_job = JobStatusRecord(
        job_id="api_test_job_1",
        source_path="/test/api_test.pdf",
        environment="test",
        status="running",
        queued_time=1234567890.0,
        start_time=1234567900.0,
        current_pass="pass_b_logical_split",
        progress_percentage=35.0,
        passes={
            "pass_a_toc_parse": {
                "status": "completed",
                "toc_entries": 5
            },
            "pass_b_logical_split": {
                "status": "in_progress",
                "chunks_processed": 12
            }
        }
    )
    
    completed_job = JobStatusRecord(
        job_id="api_test_job_2",
        source_path="/test/completed.pdf", 
        environment="test",
        status="completed",
        queued_time=1234567800.0,
        start_time=1234567810.0,
        end_time=1234567850.0,
        processing_time=40.0,
        wait_time=2.5
    )
    
    store.get_job_status.side_effect = lambda job_id: {
        "api_test_job_1": active_job,
        "api_test_job_2": completed_job
    }.get(job_id)
    
    store.get_active_jobs.return_value = [active_job]
    store.get_job_history.return_value = [completed_job]
    store.get_job_statistics.return_value = {
        "active_jobs": 1,
        "total_completed": 1,
        "successful": 1,
        "failed": 0,
        "success_rate": 100.0,
        "average_processing_time": 40.0
    }
    
    return store


@pytest.fixture
def simple_client():
    """Create test client for basic functionality testing"""
    app = FastAPI()
    create_job_status_api(app)
    create_dashboard_routes(app)
    return TestClient(app)


class TestJobStatusAPI:
    """Test job status API endpoints"""
    
    @patch('src_common.job_status_api.get_job_store')
    def test_get_job_status_found(self, mock_get_store):
        """Test retrieving existing job status"""
        # Setup mock
        mock_store = MagicMock()
        mock_job = JobStatusRecord(
            job_id="api_test_job_1",
            source_path="/test/api_test.pdf",
            environment="test",
            status="running",
            queued_time=1234567890.0,
            start_time=1234567900.0,
            current_pass="pass_b_logical_split",
            progress_percentage=35.0,
            passes={
                "pass_a_toc_parse": {
                    "status": "completed",
                    "toc_entries": 5
                }
            }
        )
        mock_store.get_job_status.return_value = mock_job
        mock_get_store.return_value = mock_store
        
        # Create app and client
        app = FastAPI()
        create_job_status_api(app)
        client = TestClient(app)
        
        # Test request
        response = client.get("/api/jobs/status/api_test_job_1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "api_test_job_1"
        assert data["status"] == "running"
        assert data["progress_percentage"] == 35.0
        assert data["current_pass"] == "pass_b_logical_split"
    
    def test_get_job_status_not_found(self, client):
        """Test retrieving non-existent job status"""
        response = client.get("/api/jobs/status/nonexistent_job")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    
    def test_get_active_jobs(self, client):
        """Test retrieving active jobs"""
        response = client.get("/api/jobs/active")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["job_id"] == "api_test_job_1"
        assert data[0]["status"] == "running"
    
    def test_get_active_jobs_with_environment_filter(self, client, mock_job_store):
        """Test retrieving active jobs filtered by environment"""
        response = client.get("/api/jobs/active?environment=test")
        
        assert response.status_code == 200
        data = response.json()
        
        # Mock should filter by environment
        mock_job_store.get_active_jobs.assert_called_once()
        assert len(data) == 1
    
    def test_get_job_history(self, client):
        """Test retrieving job history"""
        response = client.get("/api/jobs/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["job_id"] == "api_test_job_2"
        assert data[0]["status"] == "completed"
        assert data[0]["processing_time"] == 40.0
    
    def test_get_job_history_with_limit(self, client, mock_job_store):
        """Test job history with custom limit"""
        response = client.get("/api/jobs/history?limit=10")
        
        assert response.status_code == 200
        
        # Verify limit was passed to store
        mock_job_store.get_job_history.assert_called_once_with(limit=10, environment=None)
    
    def test_get_job_history_with_environment(self, client, mock_job_store):
        """Test job history with environment filter"""
        response = client.get("/api/jobs/history?environment=prod&limit=20")
        
        assert response.status_code == 200
        
        # Verify parameters were passed correctly
        mock_job_store.get_job_history.assert_called_once_with(limit=20, environment="prod")
    
    def test_get_job_statistics(self, client):
        """Test retrieving job statistics"""
        response = client.get("/api/jobs/statistics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["active_jobs"] == 1
        assert data["total_completed"] == 1
        assert data["success_rate"] == 100.0
        assert data["average_processing_time"] == 40.0
    
    def test_get_job_statistics_with_environment(self, client, mock_job_store):
        """Test job statistics with environment filter"""
        response = client.get("/api/jobs/statistics?environment=dev")
        
        assert response.status_code == 200
        
        # Verify environment filter was passed
        mock_job_store.get_job_statistics.assert_called_once_with(environment="dev")


class TestWebSocketManager:
    """Test WebSocket manager functionality"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection_management(self):
        """Test WebSocket connection and disconnection"""
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        
        manager = websocket_manager
        initial_connections = len(manager.active_connections)
        
        # Test connection
        await manager.connect(mock_websocket)
        assert len(manager.active_connections) == initial_connections + 1
        
        # Test disconnection
        manager.disconnect(mock_websocket)
        assert len(manager.active_connections) == initial_connections
    
    @pytest.mark.asyncio
    async def test_broadcast_job_update(self):
        """Test broadcasting job updates via WebSocket"""
        mock_websocket = MagicMock()
        mock_websocket.send_text = AsyncMock()
        
        manager = websocket_manager
        manager.active_connections = [mock_websocket]
        
        # Create test job status
        job_status = JobStatusRecord(
            job_id="broadcast_test",
            source_path="/test/broadcast.pdf",
            environment="test",
            status="running",
            queued_time=1234567890.0,
            progress_percentage=50.0,
            current_pass="pass_c_unstructured"
        )
        
        # Broadcast update
        await manager.broadcast_job_update(job_status)
        
        # Verify WebSocket was called
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        assert sent_data["type"] == "job_update"
        assert sent_data["data"]["job_id"] == "broadcast_test"
        assert sent_data["data"]["status"] == "running"
        assert sent_data["data"]["progress_percentage"] == 50.0
    
    @pytest.mark.asyncio
    async def test_broadcast_statistics_update(self):
        """Test broadcasting statistics updates"""
        mock_websocket = MagicMock()
        mock_websocket.send_text = AsyncMock()
        
        manager = websocket_manager
        manager.active_connections = [mock_websocket]
        
        stats = {
            "active_jobs": 3,
            "total_completed": 15,
            "success_rate": 87.5
        }
        
        await manager.broadcast_statistics_update(stats)
        
        mock_websocket.send_text.assert_called_once()
        sent_data = json.loads(mock_websocket.send_text.call_args[0][0])
        
        assert sent_data["type"] == "statistics_update"
        assert sent_data["data"]["active_jobs"] == 3
        assert sent_data["data"]["success_rate"] == 87.5
    
    @pytest.mark.asyncio
    async def test_failed_websocket_cleanup(self):
        """Test cleanup of failed WebSocket connections"""
        working_websocket = MagicMock()
        working_websocket.send_text = AsyncMock()
        
        failing_websocket = MagicMock()
        failing_websocket.send_text = AsyncMock(side_effect=Exception("Connection failed"))
        
        manager = websocket_manager
        manager.active_connections = [working_websocket, failing_websocket]
        
        job_status = JobStatusRecord(
            job_id="cleanup_test",
            source_path="/test/cleanup.pdf", 
            environment="test",
            status="running",
            queued_time=1234567890.0
        )
        
        await manager.broadcast_job_update(job_status)
        
        # Working connection should still be active
        assert working_websocket in manager.active_connections
        # Failed connection should be removed
        assert failing_websocket not in manager.active_connections


class TestJobStatusProgressCallback:
    """Test JobStatusProgressCallback integration"""
    
    @pytest.mark.asyncio
    async def test_progress_callback_job_lifecycle(self):
        """Test progress callback through complete job lifecycle"""
        mock_store = MagicMock(spec=JobStatusStore)
        mock_store.get_job_status.return_value = JobStatusRecord(
            job_id="callback_test",
            source_path="/test/callback.pdf",
            environment="test", 
            status="running",
            queued_time=1234567890.0
        )
        
        callback = JobStatusProgressCallback(mock_store)
        
        # Create job progress
        job_progress = JobProgress(
            job_id="callback_test",
            source_path="/test/callback.pdf",
            environment="test",
            start_time=1234567900.0
        )
        
        # Test job start
        await callback.on_job_start(job_progress)
        mock_store.update_job_from_progress.assert_called_with(job_progress)
        
        # Test pass start
        pass_progress = PassProgress(
            pass_type=PassType.PASS_A,
            status=PassStatus.STARTING,
            start_time=1234567905.0
        )
        
        job_progress.current_pass = PassType.PASS_A
        job_progress.passes[PassType.PASS_A] = pass_progress
        
        await callback.on_pass_start(job_progress, pass_progress)
        assert mock_store.update_job_from_progress.call_count == 2
        
        # Test pass progress
        pass_progress.status = PassStatus.IN_PROGRESS
        await callback.on_pass_progress(job_progress, pass_progress, toc_entries=8)
        assert mock_store.update_job_from_progress.call_count == 3
        
        # Test pass completion
        pass_progress.complete(toc_entries=8)
        await callback.on_pass_complete(job_progress, pass_progress)
        assert mock_store.update_job_from_progress.call_count == 4
        
        # Test job completion
        job_progress.overall_status = "completed"
        await callback.on_job_complete(job_progress)
        assert mock_store.update_job_from_progress.call_count == 5
    
    @pytest.mark.asyncio
    async def test_progress_callback_error_handling(self):
        """Test progress callback error handling"""
        failing_store = MagicMock(spec=JobStatusStore)
        failing_store.update_job_from_progress.side_effect = Exception("Store error")
        failing_store.get_job_status.return_value = None
        
        callback = JobStatusProgressCallback(failing_store)
        
        job_progress = JobProgress(
            job_id="error_test",
            source_path="/test/error.pdf",
            environment="test",
            start_time=1234567890.0
        )
        
        # Should not raise exception even if store fails
        try:
            await callback.on_job_start(job_progress)
        except Exception as e:
            pytest.fail(f"Progress callback should handle store errors gracefully: {e}")


class TestDashboardIntegration:
    """Test dashboard integration with job status API"""
    
    def test_dashboard_endpoint(self, client):
        """Test dashboard HTML endpoint"""
        response = client.get("/dashboard")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "TTRPG CENTER JOB DASHBOARD" in response.text
    
    def test_dashboard_data_endpoint(self, client):
        """Test dashboard data endpoint"""
        response = client.get("/dashboard/data")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "active_jobs" in data
        assert "recent_jobs" in data
        assert "statistics" in data
        assert "timestamp" in data
        
        # Verify data structure
        assert isinstance(data["active_jobs"], list)
        assert isinstance(data["recent_jobs"], list)
        assert isinstance(data["statistics"], dict)
    
    @pytest.mark.asyncio
    async def test_dashboard_websocket_integration(self, test_app):
        """Test dashboard WebSocket endpoint"""
        client = TestClient(test_app)
        
        # Test WebSocket connection
        with client.websocket_connect("/ws/jobs") as websocket:
            # Should receive initial data
            data = websocket.receive_text()
            message = json.loads(data)
            
            assert message["type"] == "initial_data"
            assert "active_jobs" in message["data"]
            assert "statistics" in message["data"]


class TestAPIErrorHandling:
    """Test API error handling scenarios"""
    
    def test_api_with_store_errors(self):
        """Test API behavior when store operations fail"""
        app = FastAPI()
        
        # Mock store that raises exceptions
        failing_store = MagicMock(spec=JobStatusStore)
        failing_store.get_job_status.side_effect = Exception("Store failure")
        failing_store.get_active_jobs.side_effect = Exception("Store failure")
        
        async def mock_get_failing_store():
            return failing_store
        
        with patch('src_common.job_status_api.get_job_store', mock_get_failing_store):
            create_job_status_api(app)
            client = TestClient(app)
            
            # Should handle store errors gracefully
            response = client.get("/api/jobs/status/test_job")
            assert response.status_code in [404, 500]  # Depends on error handling implementation
    
    def test_api_parameter_validation(self, client):
        """Test API parameter validation"""
        # Test invalid limit values
        response = client.get("/api/jobs/history?limit=0")
        assert response.status_code == 422  # Validation error
        
        response = client.get("/api/jobs/history?limit=300")
        assert response.status_code == 422  # Exceeds maximum
        
        # Valid parameters should work
        response = client.get("/api/jobs/history?limit=50")
        assert response.status_code == 200
    
    def test_malformed_requests(self, client):
        """Test handling of malformed requests"""
        # Non-existent endpoints
        response = client.get("/api/jobs/invalid_endpoint")
        assert response.status_code == 404
        
        # Wrong HTTP methods
        response = client.post("/api/jobs/active")
        assert response.status_code == 405  # Method not allowed


if __name__ == "__main__":
    pytest.main([__file__])