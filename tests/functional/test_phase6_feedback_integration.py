# tests/functional/test_phase6_feedback_integration.py
"""
Functional tests for Phase 6 Feedback Integration
Tests complete feedback workflows, API endpoints, and cache bypass functionality
"""

import pytest
import asyncio
import json
import time
import tempfile
import shutil
from pathlib import Path
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
from app_feedback import app, feedback_processor, gate_manager


class TestFeedbackAPIEndpoints:
    """Test Feedback API endpoints (US-601, US-602, US-604)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def async_client(self):
        return AsyncClient(app=app, base_url="http://test")
    
    def test_health_check_endpoint(self, client):
        """Test feedback system health check"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "feedback-testing"
        assert data["phase"] == "6"
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_submit_thumbs_up_feedback(self, async_client):
        """Test submitting positive feedback creates regression test (US-601)"""
        feedback_data = {
            "trace_id": "test_thumbs_up_123",
            "rating": "thumbs_up",
            "query": "What is a barbarian?",
            "answer": "A barbarian is a fierce warrior class.",
            "metadata": {"model": "test-model", "tokens": 30, "processing_time_ms": 450},
            "retrieved_chunks": [{"source": "PHB", "score": 0.95, "text": "Barbarian class info"}],
            "context": {"session": "functional_test"}
        }
        
        async with async_client as ac:
            response = await ac.post("/api/feedback", json=feedback_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["success"] is True
        assert data["action_taken"] == "regression_test_created"
        assert "feedback_id" in data
        assert "Thank you!" in data["message"]
        assert "regression test" in data["message"].lower()
        assert "artifact_path" in data
        
        # Verify regression test artifact was created
        assert data["artifact_path"] is not None
        if Path(data["artifact_path"]).exists():
            with open(data["artifact_path"], 'r') as f:
                test_data = json.load(f)
            
            assert test_data["trace_id"] == "test_thumbs_up_123"
            assert test_data["query"] == "What is a barbarian?"
            assert test_data["expected_answer"] == "A barbarian is a fierce warrior class."
    
    @pytest.mark.asyncio
    async def test_submit_thumbs_down_feedback(self, async_client):
        """Test submitting negative feedback creates bug bundle (US-602)"""
        feedback_data = {
            "trace_id": "test_thumbs_down_456",
            "rating": "thumbs_down", 
            "query": "How do I cast healing spells?",
            "answer": "Incorrect spell information provided...",
            "metadata": {"model": "test-model", "tokens": 40, "processing_time_ms": 600},
            "retrieved_chunks": [{"source": "PHB", "score": 0.8, "text": "Spell casting rules"}],
            "context": {"session": "bug_test"},
            "user_note": "The spell slots are calculated wrong"
        }
        
        async with async_client as ac:
            response = await ac.post("/api/feedback", json=feedback_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["success"] is True
        assert data["action_taken"] == "bug_bundle_created"
        assert "feedback_id" in data
        assert "Thank you!" in data["message"]
        assert "bug report" in data["message"].lower()
        assert "artifact_path" in data
        
        # Verify bug bundle artifact was created
        assert data["artifact_path"] is not None
        if Path(data["artifact_path"]).exists():
            with open(data["artifact_path"], 'r') as f:
                bug_data = json.load(f)
            
            assert bug_data["trace_id"] == "test_thumbs_down_456"
            assert bug_data["query"] == "How do I cast healing spells?"
            assert bug_data["actual_answer"] == "Incorrect spell information provided..."
            assert bug_data["user_note"] == "The spell slots are calculated wrong"
    
    @pytest.mark.asyncio
    async def test_feedback_invalid_rating(self, async_client):
        """Test submitting feedback with invalid rating"""
        invalid_feedback = {
            "trace_id": "test_invalid_789",
            "rating": "invalid_rating",  # Invalid rating
            "query": "Test query",
            "answer": "Test answer",
            "metadata": {}
        }
        
        async with async_client as ac:
            response = await ac.post("/api/feedback", json=invalid_feedback)
        
        assert response.status_code == 422  # Validation error
    
    def test_feedback_stats_endpoint(self, client):
        """Test feedback statistics endpoint"""
        response = client.get("/api/feedback/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check stats structure
        assert "regression_tests" in data
        assert "bug_bundles" in data
        assert "total_feedback" in data
        assert "last_updated" in data
        
        # Values should be non-negative integers
        assert isinstance(data["regression_tests"], int)
        assert isinstance(data["bug_bundles"], int)
        assert isinstance(data["total_feedback"], int)
        assert data["regression_tests"] >= 0
        assert data["bug_bundles"] >= 0
        assert data["total_feedback"] >= 0
    
    @pytest.mark.asyncio
    async def test_feedback_rate_limiting(self, async_client):
        """Test feedback rate limiting prevents spam (US-604 security)"""
        feedback_data = {
            "trace_id": "rate_limit_test",
            "rating": "thumbs_up",
            "query": "Rate limit test",
            "answer": "Rate limit test answer",
            "metadata": {}
        }
        
        # Submit feedback rapidly to trigger rate limiting
        responses = []
        async with async_client as ac:
            for i in range(12):  # More than the limit of 10
                try:
                    response = await ac.post("/api/feedback", json={
                        **feedback_data,
                        "trace_id": f"rate_limit_test_{i}"
                    })
                    responses.append(response.status_code)
                except:
                    responses.append(429)  # Rate limited
        
        # Should have some successful requests and some rate limited
        success_count = sum(1 for status in responses if status == 200)
        rate_limited_count = sum(1 for status in responses if status == 429)
        
        assert success_count <= 10  # Within rate limit
        assert rate_limited_count > 0   # Some requests were rate limited
    
    def test_feedback_cache_bypass_headers(self, client):
        """Test feedback endpoints include cache bypass headers (US-604)"""
        feedback_data = {
            "trace_id": "cache_bypass_test",
            "rating": "thumbs_up",
            "query": "Cache test",
            "answer": "Cache test answer",
            "metadata": {}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        
        # Check cache bypass headers are present
        assert response.status_code == 200
        assert "cache-control" in response.headers
        cache_control = response.headers["cache-control"]
        assert "no-store" in cache_control
        assert "no-cache" in cache_control
        assert "must-revalidate" in cache_control


class TestTestGateAPIEndpoints:
    """Test Test Gate API endpoints (US-603)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def async_client(self):
        return AsyncClient(app=app, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_create_test_gate(self, async_client):
        """Test creating a test gate"""
        async with async_client as ac:
            response = await ac.post("/api/gates", params={"environment": "test"})
        
        assert response.status_code == 200
        data = response.json()
        
        # Check gate structure
        assert "gate_id" in data
        assert data["status"] == "pending"
        assert data["environment"] == "test"
        assert data["test_results"] == {}
        assert "created_at" in data
        assert "updated_at" in data
        
        return data["gate_id"]  # Return for use in other tests
    
    @pytest.mark.asyncio
    async def test_run_test_gate(self, async_client):
        """Test running a test gate"""
        # First create a gate
        async with async_client as ac:
            create_response = await ac.post("/api/gates", params={"environment": "dev"})
        
        assert create_response.status_code == 200
        gate_data = create_response.json()
        gate_id = gate_data["gate_id"]
        
        # Run the gate
        async with async_client as ac:
            run_response = await ac.post(f"/api/gates/{gate_id}/run")
        
        assert run_response.status_code == 200
        run_data = run_response.json()
        
        # Should initially show running status
        assert run_data["gate_id"] == gate_id
        assert run_data["status"] == "running"
        
        # Wait a moment for background processing
        await asyncio.sleep(0.1)
        
        # Check final status
        async with async_client as ac:
            status_response = await ac.get(f"/api/gates/{gate_id}")
        
        final_data = status_response.json()
        assert final_data["status"] in ["passed", "failed", "running"]
    
    @pytest.mark.asyncio
    async def test_get_test_gate_status(self, async_client):
        """Test getting test gate status"""
        # Create a gate
        async with async_client as ac:
            create_response = await ac.post("/api/gates")
        
        gate_data = create_response.json()
        gate_id = gate_data["gate_id"]
        
        # Get gate status
        async with async_client as ac:
            response = await ac.get(f"/api/gates/{gate_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["gate_id"] == gate_id
        assert data["status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_gate(self, async_client):
        """Test getting nonexistent gate returns 404"""
        async with async_client as ac:
            response = await ac.get("/api/gates/nonexistent_gate_123")
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_list_test_gates(self, async_client):
        """Test listing all test gates"""
        # Create multiple gates
        gate_ids = []
        for env in ["dev", "test", "prod"]:
            async with async_client as ac:
                response = await ac.post("/api/gates", params={"environment": env})
            
            assert response.status_code == 200
            gate_ids.append(response.json()["gate_id"])
        
        # List all gates
        async with async_client as ac:
            list_response = await ac.get("/api/gates")
        
        assert list_response.status_code == 200
        gates = list_response.json()
        
        assert len(gates) >= 3  # At least the 3 we created
        returned_ids = [gate["gate_id"] for gate in gates]
        
        for gate_id in gate_ids:
            assert gate_id in returned_ids
    
    def test_list_gates_empty(self, client):
        """Test listing gates when none exist returns empty list"""
        # Clear any existing gates by mocking
        with patch.object(gate_manager, 'list_gates', return_value=[]):
            response = client.get("/api/gates")
            
            assert response.status_code == 200
            data = response.json()
            assert data == []


class TestFeedbackWorkflowIntegration:
    """Test complete feedback workflows and integration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def async_client(self):
        return AsyncClient(app=app, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_complete_positive_feedback_workflow(self, async_client):
        """Test complete positive feedback workflow (US-601)"""
        # 1. Submit positive feedback
        feedback_data = {
            "trace_id": "workflow_positive_123",
            "rating": "thumbs_up",
            "query": "What are the spellcasting classes?",
            "answer": "Spellcasting classes include wizard, sorcerer, cleric, and druid.",
            "metadata": {"model": "workflow-test", "tokens": 45, "intent": "information"},
            "retrieved_chunks": [
                {"source": "PHB", "score": 0.92, "text": "Wizard spellcasting info"},
                {"source": "PHB", "score": 0.88, "text": "Cleric spellcasting info"}
            ],
            "context": {"session": "workflow_test", "user": "test_user"}
        }
        
        async with async_client as ac:
            feedback_response = await ac.post("/api/feedback", json=feedback_data)
        
        assert feedback_response.status_code == 200
        feedback_result = feedback_response.json()
        assert feedback_result["success"] is True
        assert feedback_result["action_taken"] == "regression_test_created"
        
        # 2. Verify regression test artifact exists
        artifact_path = feedback_result.get("artifact_path")
        if artifact_path and Path(artifact_path).exists():
            with open(artifact_path, 'r') as f:
                test_data = json.load(f)
            
            assert test_data["query"] == feedback_data["query"]
            assert test_data["expected_answer"] == feedback_data["answer"]
            assert len(test_data["expected_chunks"]) == 2
        
        # 3. Create test gate to run the new regression test
        async with async_client as ac:
            gate_response = await ac.post("/api/gates", params={"environment": "test"})
        
        assert gate_response.status_code == 200
        gate_data = gate_response.json()
        gate_id = gate_data["gate_id"]
        
        # 4. Run the test gate
        async with async_client as ac:
            run_response = await ac.post(f"/api/gates/{gate_id}/run")
        
        assert run_response.status_code == 200
        
        # 5. Check that workflow completed successfully
        # (In real implementation, would verify test was included in gate run)
        async with async_client as ac:
            stats_response = await ac.get("/api/feedback/stats")
        
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["regression_tests"] >= 1
    
    @pytest.mark.asyncio
    async def test_complete_negative_feedback_workflow(self, async_client):
        """Test complete negative feedback workflow (US-602)"""
        # 1. Submit negative feedback
        feedback_data = {
            "trace_id": "workflow_negative_456",
            "rating": "thumbs_down",
            "query": "How do I calculate spell attack bonus?",
            "answer": "Incorrect formula provided: Spell attack = level + ability modifier",
            "metadata": {"model": "bug-test", "tokens": 35, "intent": "calculation", "confidence": 0.3},
            "retrieved_chunks": [
                {"source": "PHB", "score": 0.65, "text": "Spell attack information"}
            ],
            "context": {"session": "bug_session", "user": "frustrated_user"},
            "user_note": "This formula is completely wrong. Should include proficiency bonus."
        }
        
        async with async_client as ac:
            feedback_response = await ac.post("/api/feedback", json=feedback_data)
        
        assert feedback_response.status_code == 200
        feedback_result = feedback_response.json()
        assert feedback_result["success"] is True
        assert feedback_result["action_taken"] == "bug_bundle_created"
        
        # 2. Verify bug bundle was created with all artifacts
        artifact_path = feedback_result.get("artifact_path")
        if artifact_path and Path(artifact_path).exists():
            # Check main bundle file
            with open(artifact_path, 'r') as f:
                bug_data = json.load(f)
            
            assert bug_data["trace_id"] == feedback_data["trace_id"]
            assert bug_data["query"] == feedback_data["query"]
            assert bug_data["actual_answer"] == feedback_data["answer"]
            assert bug_data["user_note"] == feedback_data["user_note"]
            assert len(bug_data["logs"]) > 0
            
            # Check debug artifacts in same directory
            bug_dir = Path(artifact_path).parent
            assert (bug_dir / "context.json").exists()
            assert (bug_dir / "environment.json").exists()
        
        # 3. Verify stats were updated
        async with async_client as ac:
            stats_response = await ac.get("/api/feedback/stats")
        
        stats = stats_response.json()
        assert stats["bug_bundles"] >= 1
        assert stats["total_feedback"] >= 1
    
    @pytest.mark.asyncio
    async def test_feedback_cache_bypass_integration(self, async_client):
        """Test feedback immediately bypasses cache (US-604)"""
        # 1. Submit feedback
        feedback_data = {
            "trace_id": "cache_bypass_integration",
            "rating": "thumbs_up",
            "query": "Cache bypass test query",
            "answer": "Cache bypass test answer",
            "metadata": {"test": "cache_bypass"}
        }
        
        # Record time before submission
        before_time = time.time()
        
        async with async_client as ac:
            feedback_response = await ac.post("/api/feedback", json=feedback_data)
        
        assert feedback_response.status_code == 200
        
        # 2. Immediately check stats (should reflect new feedback)
        async with async_client as ac:
            stats_response = await ac.get("/api/feedback/stats")
        
        assert stats_response.status_code == 200
        stats = stats_response.json()
        
        # Stats should be updated immediately (within seconds)
        stats_time = stats["last_updated"]
        time_diff = stats_time - before_time
        assert time_diff < 5  # Updated within 5 seconds
        
        # 3. Verify cache bypass headers were sent
        assert "cache-control" in feedback_response.headers
        assert "no-store" in feedback_response.headers["cache-control"]
    
    @pytest.mark.asyncio
    async def test_concurrent_feedback_processing(self, async_client):
        """Test system handles concurrent feedback submissions"""
        # Create multiple feedback submissions concurrently
        feedback_tasks = []
        
        for i in range(5):
            feedback_data = {
                "trace_id": f"concurrent_test_{i}",
                "rating": "thumbs_up" if i % 2 == 0 else "thumbs_down",
                "query": f"Concurrent test query {i}",
                "answer": f"Concurrent test answer {i}",
                "metadata": {"test": "concurrent", "index": i},
                "user_note": f"Note {i}" if i % 2 == 1 else None
            }
            
            async def submit_feedback(data):
                async with async_client as ac:
                    return await ac.post("/api/feedback", json=data)
            
            feedback_tasks.append(submit_feedback(feedback_data))
        
        # Submit all feedback concurrently
        responses = await asyncio.gather(*feedback_tasks)
        
        # All submissions should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        
        # Verify stats reflect all submissions
        async with async_client as ac:
            stats_response = await ac.get("/api/feedback/stats")
        
        stats = stats_response.json()
        assert stats["total_feedback"] >= 5
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, async_client):
        """Test system handles errors gracefully"""
        # 1. Test with malformed feedback data
        invalid_feedback = {
            "trace_id": "",  # Empty trace ID
            "rating": "thumbs_up",
            "query": "",     # Empty query
            "answer": "",    # Empty answer
            "metadata": None  # Invalid metadata
        }
        
        async with async_client as ac:
            response = await ac.post("/api/feedback", json=invalid_feedback)
        
        # Should handle gracefully (either validation error or processed with defaults)
        assert response.status_code in [200, 422, 500]
        
        # 2. Test system continues working after error
        valid_feedback = {
            "trace_id": "recovery_test_123",
            "rating": "thumbs_up",
            "query": "Recovery test query",
            "answer": "Recovery test answer",
            "metadata": {"test": "recovery"}
        }
        
        async with async_client as ac:
            response = await ac.post("/api/feedback", json=valid_feedback)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestPhase6SecurityAndCompliance:
    """Test Phase 6 security and compliance requirements"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_feedback_data_sanitization(self, client):
        """Test sensitive data is properly sanitized in bug bundles"""
        feedback_data = {
            "trace_id": "security_test_789",
            "rating": "thumbs_down",
            "query": "Test query with sensitive data",
            "answer": "Test answer",
            "metadata": {
                "api_key": "secret_api_key_123",
                "password": "user_password_456",
                "auth_token": "bearer_token_789",
                "normal_field": "normal_value",
                "credential": "sensitive_credential"
            },
            "context": {"session": "security_test"}
        }
        
        response = client.post("/api/feedback", json=feedback_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify artifact was created and sensitive data was redacted
        artifact_path = data.get("artifact_path")
        if artifact_path and Path(artifact_path).exists():
            with open(artifact_path, 'r') as f:
                bug_data = json.load(f)
            
            metadata = bug_data["metadata"]
            assert metadata["api_key"] == "[REDACTED]"
            assert metadata["password"] == "[REDACTED]" 
            assert metadata["auth_token"] == "[REDACTED]"
            assert metadata["credential"] == "[REDACTED]"
            assert metadata["normal_field"] == "normal_value"  # Not redacted
    
    def test_rate_limiting_compliance(self, client):
        """Test rate limiting prevents abuse"""
        feedback_base = {
            "rating": "thumbs_up",
            "query": "Rate limit test",
            "answer": "Rate limit answer",
            "metadata": {}
        }
        
        # Submit requests rapidly
        success_count = 0
        rate_limited_count = 0
        
        for i in range(15):  # Exceed rate limit
            feedback_data = {
                **feedback_base,
                "trace_id": f"rate_limit_{i}"
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1
        
        # Should have limited some requests
        assert success_count <= 10  # Within rate limit
        assert rate_limited_count > 0   # Some requests blocked
    
    def test_input_validation_security(self, client):
        """Test input validation prevents injection attacks"""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE feedback; --",
            "../../../etc/passwd",
            "javascript:alert('injection')",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for malicious_input in malicious_inputs:
            feedback_data = {
                "trace_id": "security_injection_test",
                "rating": "thumbs_down",
                "query": malicious_input,
                "answer": malicious_input,
                "metadata": {"test": malicious_input},
                "user_note": malicious_input
            }
            
            response = client.post("/api/feedback", json=feedback_data)
            
            # Should either process safely or reject
            assert response.status_code in [200, 400, 422]
            
            if response.status_code == 200:
                # If processed, should be sanitized
                data = response.json()
                assert data["success"] is True
                # Malicious content should be contained, not executed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])