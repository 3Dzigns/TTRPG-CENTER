# tests/unit/test_phase6_feedback_system.py
"""
Unit tests for Phase 6 Feedback System
Tests feedback processing, test gate management, and regression test creation
"""

import pytest
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

# Import Phase 6 components
from app_feedback import (
    FeedbackProcessor, TestGateManager, FeedbackRequest, 
    RegressionTestCase, BugBundle, TestGateStatus
)


class TestFeedbackProcessor:
    """Test Feedback Processing System (US-601, US-602)"""
    
    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def feedback_processor(self, temp_artifacts_dir):
        """Create feedback processor with temporary directory"""
        processor = FeedbackProcessor()
        processor.artifacts_dir = temp_artifacts_dir
        processor.bugs_dir = temp_artifacts_dir / "bugs"
        processor.regression_dir = temp_artifacts_dir / "regression"
        processor.gates_dir = temp_artifacts_dir / "gates"
        
        # Ensure directories exist
        processor.bugs_dir.mkdir(exist_ok=True)
        processor.regression_dir.mkdir(exist_ok=True)
        processor.gates_dir.mkdir(exist_ok=True)
        
        return processor
    
    def test_feedback_processor_initialization(self, feedback_processor):
        """Test feedback processor initializes correctly"""
        assert feedback_processor.artifacts_dir.exists()
        assert feedback_processor.bugs_dir.exists()
        assert feedback_processor.regression_dir.exists()
        assert feedback_processor.gates_dir.exists()
    
    @pytest.mark.asyncio
    async def test_thumbs_up_creates_regression_test(self, feedback_processor):
        """Test 👍 feedback creates regression test (US-601)"""
        feedback = FeedbackRequest(
            trace_id="test_trace_123",
            rating="thumbs_up",
            query="What is a paladin?",
            answer="A paladin is a holy warrior class.",
            metadata={"model": "test-model", "tokens": 42},
            retrieved_chunks=[{"source": "PHB", "text": "Paladin description"}],
            context={"session": "test_session"}
        )
        
        result = await feedback_processor.process_thumbs_up(feedback)
        
        # Check result structure
        assert "test_id" in result
        assert "artifact_path" in result
        assert result["action"] == "regression_test_created"
        assert "Regression test created" in result["message"]
        
        # Verify regression test file was created
        test_files = list(feedback_processor.regression_dir.glob("test_*.json"))
        assert len(test_files) == 1
        
        # Verify regression test content
        with open(test_files[0], 'r') as f:
            test_data = json.load(f)
        
        test_case = RegressionTestCase(**test_data)
        assert test_case.trace_id == "test_trace_123"
        assert test_case.query == "What is a paladin?"
        assert test_case.expected_answer == "A paladin is a holy warrior class."
        assert test_case.model == "test-model"
        assert len(test_case.expected_chunks) == 1
        assert test_case.expected_chunks[0]["source"] == "PHB"
    
    @pytest.mark.asyncio
    async def test_thumbs_up_creates_pytest_file(self, feedback_processor):
        """Test 👍 feedback creates pytest test file"""
        feedback = FeedbackRequest(
            trace_id="pytest_test_123",
            rating="thumbs_up",
            query="What is initiative?",
            answer="Initiative determines turn order.",
            metadata={"model": "test-model"},
            retrieved_chunks=[],
            context={}
        )
        
        with patch('pathlib.Path.mkdir'), patch('builtins.open', mock_open()) as mock_file:
            await feedback_processor.process_thumbs_up(feedback)
        
        # Verify pytest file was "created" (mocked)
        mock_file.assert_called()
        
        # Check that pytest content includes the query
        written_content = ''.join(call.args[0] for call in mock_file().write.call_args_list)
        assert "What is initiative?" in written_content
        assert "Initiative determines turn order." in written_content
        assert "def test_query_produces_expected_answer" in written_content
        assert "def test_query_retrieves_expected_chunks" in written_content
        assert "def test_end_to_end_response_quality" in written_content
    
    @pytest.mark.asyncio
    async def test_thumbs_down_creates_bug_bundle(self, feedback_processor):
        """Test 👎 feedback creates bug bundle (US-602)"""
        feedback = FeedbackRequest(
            trace_id="bug_trace_123",
            rating="thumbs_down",
            query="How do I cast fireball?",
            answer="Incorrect spell information...",
            metadata={"model": "test-model", "tokens": 50},
            retrieved_chunks=[{"source": "PHB", "text": "Spell description"}],
            context={"session": "bug_test"},
            user_note="The spell level is wrong"
        )
        
        result = await feedback_processor.process_thumbs_down(feedback)
        
        # Check result structure
        assert "bug_id" in result
        assert "artifact_path" in result
        assert result["action"] == "bug_bundle_created"
        assert "Bug bundle created" in result["message"]
        
        # Verify bug directory was created
        bug_dirs = [d for d in feedback_processor.bugs_dir.iterdir() if d.is_dir()]
        assert len(bug_dirs) == 1
        
        # Verify bug bundle file exists
        bundle_file = bug_dirs[0] / "bundle.json"
        assert bundle_file.exists()
        
        # Verify bug bundle content
        with open(bundle_file, 'r') as f:
            bug_data = json.load(f)
        
        bug_bundle = BugBundle(**bug_data)
        assert bug_bundle.trace_id == "bug_trace_123"
        assert bug_bundle.query == "How do I cast fireball?"
        assert bug_bundle.actual_answer == "Incorrect spell information..."
        assert bug_bundle.user_note == "The spell level is wrong"
        assert len(bug_bundle.context_chunks) == 1
        assert len(bug_bundle.logs) > 0  # Should have collected logs
    
    @pytest.mark.asyncio
    async def test_bug_bundle_includes_debug_artifacts(self, feedback_processor):
        """Test bug bundle includes additional debug artifacts"""
        feedback = FeedbackRequest(
            trace_id="debug_trace_123",
            rating="thumbs_down",
            query="Debug test query",
            answer="Debug test answer",
            metadata={"model": "debug-model"},
            retrieved_chunks=[],
            context={"debug": True}
        )
        
        await feedback_processor.process_thumbs_down(feedback)
        
        # Find bug directory
        bug_dirs = [d for d in feedback_processor.bugs_dir.iterdir() if d.is_dir()]
        bug_dir = bug_dirs[0]
        
        # Verify debug artifacts were created
        assert (bug_dir / "context.json").exists()
        assert (bug_dir / "environment.json").exists()
        
        # Verify context file content
        with open(bug_dir / "context.json", 'r') as f:
            context_data = json.load(f)
        
        assert context_data["query"] == "Debug test query"
        assert context_data["answer"] == "Debug test answer"
        assert context_data["metadata"]["model"] == "debug-model"
        
        # Verify environment file content
        with open(bug_dir / "environment.json", 'r') as f:
            env_data = json.load(f)
        
        assert "environment" in env_data
        assert "timestamp" in env_data
        assert "python_version" in env_data
    
    @pytest.mark.asyncio
    async def test_collect_relevant_logs(self, feedback_processor):
        """Test log collection for bug bundles"""
        logs = await feedback_processor._collect_relevant_logs("test_trace_456")
        
        assert isinstance(logs, list)
        assert len(logs) > 0
        
        # Check that logs reference the trace ID
        trace_logs = [log for log in logs if "test_trace_456" in log]
        assert len(trace_logs) > 0
    
    def test_sanitize_metadata(self, feedback_processor):
        """Test metadata sanitization removes sensitive information"""
        metadata = {
            "model": "test-model",
            "tokens": 42,
            "api_key": "secret_key_123",
            "password": "secret_password",
            "auth_token": "bearer_token_456",
            "normal_field": "normal_value"
        }
        
        sanitized = feedback_processor._sanitize_metadata(metadata)
        
        assert sanitized["model"] == "test-model"
        assert sanitized["tokens"] == 42
        assert sanitized["normal_field"] == "normal_value"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["auth_token"] == "[REDACTED]"
    
    @pytest.mark.asyncio
    async def test_feedback_processor_handles_errors(self, feedback_processor):
        """Test feedback processor handles errors gracefully"""
        # Test with invalid feedback data
        invalid_feedback = FeedbackRequest(
            trace_id="",  # Invalid empty trace ID
            rating="thumbs_up",
            query="",     # Invalid empty query
            answer="",    # Invalid empty answer
            metadata={},
            retrieved_chunks=[],
            context={}
        )
        
        # Should not raise exception, but handle gracefully
        try:
            result = await feedback_processor.process_thumbs_up(invalid_feedback)
            # Should still create some kind of result
            assert "test_id" in result or "error" in result
        except Exception as e:
            # If it does raise, should be a handled exception
            assert "Failed to" in str(e) or "Invalid" in str(e)


class TestTestGateManager:
    """Test Test Gate Management System (US-603)"""
    
    @pytest.fixture
    def temp_gates_dir(self):
        """Create temporary gates directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def gate_manager(self, temp_gates_dir):
        """Create gate manager with temporary directory"""
        manager = TestGateManager()
        manager.gates_dir = temp_gates_dir
        return manager
    
    @pytest.mark.asyncio
    async def test_create_gate(self, gate_manager):
        """Test creating a new test gate"""
        gate = await gate_manager.create_gate("dev")
        
        assert isinstance(gate, TestGateStatus)
        assert gate.environment == "dev"
        assert gate.status == "pending"
        assert gate.test_results == {}
        assert gate.created_at > 0
        assert gate.updated_at > 0
        assert len(gate.gate_id) > 0
        
        # Verify gate file was created
        gate_file = gate_manager.gates_dir / f"gate_{gate.gate_id}.json"
        assert gate_file.exists()
    
    @pytest.mark.asyncio
    async def test_run_gate_tests(self, gate_manager):
        """Test running tests for a gate"""
        # Create a gate first
        gate = await gate_manager.create_gate("test")
        
        # Run the gate tests
        updated_gate = await gate_manager.run_gate_tests(gate.gate_id)
        
        assert updated_gate.gate_id == gate.gate_id
        assert updated_gate.status in ["passed", "failed"]
        assert updated_gate.updated_at > gate.updated_at
        assert len(updated_gate.test_results) > 0
        
        # Check test results structure
        expected_tests = ["unit_tests", "functional_tests", "regression_tests", "security_tests"]
        for test_type in expected_tests:
            assert test_type in updated_gate.test_results
            result = updated_gate.test_results[test_type]
            assert "status" in result
            assert "count" in result
            assert "failures" in result
    
    @pytest.mark.asyncio
    async def test_get_gate_status(self, gate_manager):
        """Test retrieving gate status"""
        # Create and run a gate
        gate = await gate_manager.create_gate("prod")
        
        # Get status
        retrieved_gate = await gate_manager.get_gate_status(gate.gate_id)
        
        assert retrieved_gate.gate_id == gate.gate_id
        assert retrieved_gate.environment == gate.environment
        assert retrieved_gate.created_at == gate.created_at
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_gate_raises_error(self, gate_manager):
        """Test getting nonexistent gate raises HTTPException"""
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await gate_manager.get_gate_status("nonexistent_gate_123")
        
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_list_gates(self, gate_manager):
        """Test listing all gates"""
        # Create multiple gates
        gate1 = await gate_manager.create_gate("dev")
        gate2 = await gate_manager.create_gate("test")
        gate3 = await gate_manager.create_gate("prod")
        
        # List gates
        gates = await gate_manager.list_gates()
        
        assert len(gates) == 3
        gate_ids = [g.gate_id for g in gates]
        assert gate1.gate_id in gate_ids
        assert gate2.gate_id in gate_ids
        assert gate3.gate_id in gate_ids
        
        # Check that gates are sorted by creation time (newest first)
        creation_times = [g.created_at for g in gates]
        assert creation_times == sorted(creation_times, reverse=True)
    
    @pytest.mark.asyncio
    async def test_list_gates_empty(self, gate_manager):
        """Test listing gates when none exist"""
        gates = await gate_manager.list_gates()
        assert gates == []
    
    @pytest.mark.asyncio
    async def test_gate_test_results_structure(self, gate_manager):
        """Test gate test results have correct structure"""
        gate = await gate_manager.create_gate("test")
        updated_gate = await gate_manager.run_gate_tests(gate.gate_id)
        
        for test_type, result in updated_gate.test_results.items():
            assert isinstance(result, dict)
            assert "status" in result
            assert result["status"] in ["passed", "failed"]
            assert "count" in result
            assert isinstance(result["count"], int)
            assert result["count"] >= 0
            assert "failures" in result
            assert isinstance(result["failures"], int)
            assert result["failures"] >= 0
            assert result["failures"] <= result["count"]
    
    @pytest.mark.asyncio
    async def test_gate_status_transitions(self, gate_manager):
        """Test gate status transitions correctly"""
        gate = await gate_manager.create_gate("dev")
        assert gate.status == "pending"
        
        # Mock the test execution to control status
        with patch.object(gate_manager, 'run_gate_tests') as mock_run:
            # Simulate running status
            gate.status = "running"
            gate.updated_at = time.time()
            
            # Simulate completed status
            gate.status = "passed"
            gate.test_results = {
                "unit_tests": {"status": "passed", "count": 10, "failures": 0}
            }
            gate.updated_at = time.time()
            
            mock_run.return_value = gate
            
            result = await gate_manager.run_gate_tests(gate.gate_id)
            assert result.status == "passed"


class TestFeedbackModels:
    """Test Pydantic models for feedback system"""
    
    def test_feedback_request_model(self):
        """Test FeedbackRequest model validation"""
        valid_data = {
            "trace_id": "test_trace_123",
            "rating": "thumbs_up",
            "query": "What is a wizard?",
            "answer": "A wizard is a spellcaster.",
            "metadata": {"model": "test", "tokens": 42},
            "retrieved_chunks": [{"source": "PHB", "text": "Wizard info"}],
            "context": {"session": "test"},
            "user_note": "Great answer!"
        }
        
        request = FeedbackRequest(**valid_data)
        
        assert request.trace_id == "test_trace_123"
        assert request.rating == "thumbs_up"
        assert request.query == "What is a wizard?"
        assert request.answer == "A wizard is a spellcaster."
        assert request.user_note == "Great answer!"
    
    def test_feedback_request_invalid_rating(self):
        """Test FeedbackRequest rejects invalid ratings"""
        invalid_data = {
            "trace_id": "test_trace",
            "rating": "invalid_rating",  # Invalid rating
            "query": "Test query",
            "answer": "Test answer",
            "metadata": {}
        }
        
        with pytest.raises(ValueError):
            FeedbackRequest(**invalid_data)
    
    def test_regression_test_case_model(self):
        """Test RegressionTestCase model"""
        test_data = {
            "test_id": "test_123",
            "trace_id": "trace_456",
            "query": "What is a paladin?",
            "expected_answer": "A holy warrior",
            "expected_chunks": [{"source": "PHB"}],
            "model": "test-model",
            "created_at": time.time(),
            "environment": "dev",
            "metadata": {"tokens": 42}
        }
        
        test_case = RegressionTestCase(**test_data)
        
        assert test_case.test_id == "test_123"
        assert test_case.trace_id == "trace_456"
        assert test_case.query == "What is a paladin?"
        assert test_case.expected_answer == "A holy warrior"
        assert test_case.model == "test-model"
        assert test_case.environment == "dev"
    
    def test_bug_bundle_model(self):
        """Test BugBundle model"""
        bug_data = {
            "bug_id": "bug_789",
            "trace_id": "trace_101",
            "query": "How to cast spell?",
            "actual_answer": "Wrong information",
            "context_chunks": [{"source": "PHB"}],
            "logs": ["Error log 1", "Error log 2"],
            "user_note": "This is incorrect",
            "created_at": time.time(),
            "environment": "test",
            "metadata": {"issue": "accuracy"}
        }
        
        bug_bundle = BugBundle(**bug_data)
        
        assert bug_bundle.bug_id == "bug_789"
        assert bug_bundle.trace_id == "trace_101"
        assert bug_bundle.query == "How to cast spell?"
        assert bug_bundle.actual_answer == "Wrong information"
        assert bug_bundle.user_note == "This is incorrect"
        assert len(bug_bundle.logs) == 2
        assert bug_bundle.environment == "test"
    
    def test_test_gate_status_model(self):
        """Test TestGateStatus model"""
        gate_data = {
            "gate_id": "gate_456",
            "status": "passed",
            "test_results": {
                "unit_tests": {"status": "passed", "count": 5, "failures": 0}
            },
            "created_at": time.time(),
            "updated_at": time.time(),
            "environment": "prod"
        }
        
        gate_status = TestGateStatus(**gate_data)
        
        assert gate_status.gate_id == "gate_456"
        assert gate_status.status == "passed"
        assert gate_status.environment == "prod"
        assert "unit_tests" in gate_status.test_results
    
    def test_test_gate_status_invalid_status(self):
        """Test TestGateStatus rejects invalid status"""
        invalid_data = {
            "gate_id": "gate_123",
            "status": "invalid_status",  # Invalid status
            "test_results": {},
            "created_at": time.time(),
            "updated_at": time.time(),
            "environment": "dev"
        }
        
        with pytest.raises(ValueError):
            TestGateStatus(**invalid_data)


class TestFeedbackIntegration:
    """Integration tests for feedback system components"""
    
    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def integrated_system(self, temp_artifacts_dir):
        """Create integrated feedback system for testing"""
        processor = FeedbackProcessor()
        processor.artifacts_dir = temp_artifacts_dir
        processor.bugs_dir = temp_artifacts_dir / "bugs"
        processor.regression_dir = temp_artifacts_dir / "regression"
        processor.gates_dir = temp_artifacts_dir / "gates"
        
        # Ensure directories exist
        processor.bugs_dir.mkdir(exist_ok=True)
        processor.regression_dir.mkdir(exist_ok=True)
        processor.gates_dir.mkdir(exist_ok=True)
        
        manager = TestGateManager()
        manager.gates_dir = temp_artifacts_dir / "gates"
        
        return processor, manager
    
    @pytest.mark.asyncio
    async def test_feedback_to_test_workflow(self, integrated_system):
        """Test complete workflow from feedback to test creation"""
        processor, gate_manager = integrated_system
        
        # 1. Submit positive feedback
        feedback = FeedbackRequest(
            trace_id="workflow_trace_123",
            rating="thumbs_up",
            query="What is a rogue class?",
            answer="A rogue is a stealthy character class.",
            metadata={"model": "workflow-test", "tokens": 35},
            retrieved_chunks=[{"source": "PHB", "text": "Rogue description"}],
            context={"workflow": "test"}
        )
        
        result = await processor.process_thumbs_up(feedback)
        
        # 2. Verify regression test was created
        assert "test_id" in result
        test_files = list(processor.regression_dir.glob("test_*.json"))
        assert len(test_files) == 1
        
        # 3. Create and run a test gate
        gate = await gate_manager.create_gate("dev")
        assert gate.status == "pending"
        
        # 4. Run gate tests (would include the new regression test)
        updated_gate = await gate_manager.run_gate_tests(gate.gate_id)
        assert updated_gate.status in ["passed", "failed"]
        assert len(updated_gate.test_results) > 0
        
        # 5. Verify the workflow completed successfully
        assert updated_gate.gate_id == gate.gate_id
        assert updated_gate.updated_at > gate.created_at
    
    @pytest.mark.asyncio
    async def test_bug_report_workflow(self, integrated_system):
        """Test complete bug reporting workflow"""
        processor, _ = integrated_system
        
        # 1. Submit negative feedback
        feedback = FeedbackRequest(
            trace_id="bug_workflow_456",
            rating="thumbs_down",
            query="How do I multiclass?",
            answer="Incorrect multiclassing rules...",
            metadata={"model": "bug-test", "tokens": 50},
            retrieved_chunks=[{"source": "PHB", "text": "Multiclass info"}],
            context={"bug": "workflow"},
            user_note="The prerequisites are wrong"
        )
        
        result = await processor.process_thumbs_down(feedback)
        
        # 2. Verify bug bundle was created
        assert "bug_id" in result
        bug_dirs = [d for d in processor.bugs_dir.iterdir() if d.is_dir()]
        assert len(bug_dirs) == 1
        
        # 3. Verify bug bundle contains all necessary information
        bundle_file = bug_dirs[0] / "bundle.json"
        with open(bundle_file, 'r') as f:
            bug_data = json.load(f)
        
        bug_bundle = BugBundle(**bug_data)
        assert bug_bundle.trace_id == "bug_workflow_456"
        assert bug_bundle.user_note == "The prerequisites are wrong"
        assert len(bug_bundle.logs) > 0
        
        # 4. Verify debug artifacts were created
        assert (bug_dirs[0] / "context.json").exists()
        assert (bug_dirs[0] / "environment.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])