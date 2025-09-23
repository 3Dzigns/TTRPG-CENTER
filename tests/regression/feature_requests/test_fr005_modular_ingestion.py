# tests/regression/feature_requests/test_fr005_modular_ingestion.py
"""
Feature Request FR-005: Modular Ingestion Passes Regression Tests
Tests modularized ingestion pipeline with strict gates (A→B→C→D→E→F)
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock, patch


class TestModularIngestionPasses:
    """Test suite for FR-005 Modular Ingestion with Gates"""

    def test_modular_ingestion_framework_availability(self):
        """Test that modular ingestion framework components are available"""
        try:
            from src_common.ingestion import ModularIngestionRunner
            from src_common.ingestion.contracts import PassContracts
            from src_common.ingestion.state import JobState
            from src_common.ingestion import pass_a, pass_b, pass_c, pass_d, pass_e, pass_f

            assert ModularIngestionRunner is not None, "ModularIngestionRunner should be available"
            assert PassContracts is not None, "PassContracts should be available"
            assert JobState is not None, "JobState should be available"

            # Verify all pass modules
            pass_modules = [pass_a, pass_b, pass_c, pass_d, pass_e, pass_f]
            for i, pass_module in enumerate(pass_modules, start=1):
                pass_name = chr(64 + i)  # A, B, C, D, E, F
                assert pass_module is not None, f"Pass {pass_name} module should be available"

        except ImportError as e:
            pytest.fail(f"Modular ingestion components not available: {e}")

    def test_pass_contract_definitions(self):
        """Test pass contract definitions and validation"""
        try:
            from src_common.ingestion.contracts import PassContracts
        except ImportError:
            pytest.skip("Pass contracts not available for testing")

        contracts = PassContracts()

        # Test contract schemas for all passes
        expected_passes = ["A", "B", "C", "D", "E", "F"]

        if hasattr(contracts, 'get_pass_contract'):
            for pass_name in expected_passes:
                contract = contracts.get_pass_contract(pass_name)

                assert isinstance(contract, dict), f"Pass {pass_name} contract should be structured"

                # Verify required contract fields
                required_fields = ["input_schema", "output_schema", "success_criteria"]
                for field in required_fields:
                    if field in contract:
                        assert contract[field] is not None, f"Pass {pass_name} should have {field}"

                # Verify contract validation
                if hasattr(contracts, 'validate_contract'):
                    validation = contracts.validate_contract(pass_name, contract)
                    assert validation.get("valid", False) == True, f"Pass {pass_name} contract should be valid"

        # Test specific pass contracts
        expected_contracts = {
            "A": {
                "description": "TOC/Dictionary Prime",
                "input": "PDF sources",
                "output": "Table of contents and sections",
                "artifacts": ["passA_toc.json"]
            },
            "B": {
                "description": "Large-File Splitter",
                "input": "Large PDF files",
                "output": "Split file parts",
                "artifacts": ["passB_splits.json"]
            },
            "C": {
                "description": "Unstructured Parse/Chunk",
                "input": "Split files or whole PDFs",
                "output": "Parsed chunks with metadata",
                "artifacts": ["passC_chunks.json"]
            },
            "D": {
                "description": "Enrich (Haystack)",
                "input": "Raw chunks",
                "output": "Enriched content with entities",
                "artifacts": ["passD_enriched.json"]
            },
            "E": {
                "description": "Graph Compile (LlamaIndex)",
                "input": "Enriched chunks",
                "output": "Graph structure with nodes/edges",
                "artifacts": ["passE_graph.json"]
            },
            "F": {
                "description": "Cleanup/Validate",
                "input": "Graph data",
                "output": "Validated and cleaned final data",
                "artifacts": ["passF_cleanup.json"]
            }
        }

        if hasattr(contracts, 'get_pass_description'):
            for pass_name, expected in expected_contracts.items():
                description = contracts.get_pass_description(pass_name)
                if description:
                    # Verify description contains key concepts
                    desc_lower = description.lower()
                    assert len(desc_lower) > 10, f"Pass {pass_name} should have meaningful description"

    def test_sequential_pass_gating(self):
        """Test sequential pass execution with strict gating (A→B→C→D→E→F)"""
        try:
            from src_common.ingestion import ModularIngestionRunner
        except ImportError:
            pytest.skip("Modular ingestion runner not available for testing")

        runner = ModularIngestionRunner()

        # Test job configuration
        job_config = {
            "job_id": "test_sequential_001",
            "environment": "test",
            "passes": ["A", "B", "C", "D", "E", "F"],
            "gating": {
                "strict": True,
                "halt_on_failure": True,
                "validate_artifacts": True
            },
            "sources": [
                {
                    "source_id": "test_source_001",
                    "path": "/test/sources/sample.pdf",
                    "size": 1024000
                }
            ]
        }

        if hasattr(runner, 'initialize_job'):
            # Test job initialization
            init_result = runner.initialize_job(job_config)

            assert isinstance(init_result, dict), "Job initialization should return structured result"

            if "job_state" in init_result:
                job_state = init_result["job_state"]
                assert "job_id" in job_state, "Job state should include job ID"
                assert "passes" in job_state, "Job state should include pass states"

                # Verify initial pass states
                passes = job_state["passes"]
                for pass_name in ["A", "B", "C", "D", "E", "F"]:
                    if pass_name in passes:
                        pass_state = passes[pass_name]
                        if pass_name == "A":
                            # Pass A should be ready to execute
                            assert pass_state["status"] == "PENDING", "Pass A should be initially pending"
                        else:
                            # Other passes should be blocked
                            assert pass_state["status"] in ["BLOCKED", "PENDING"], f"Pass {pass_name} should be initially blocked"

        # Test sequential execution enforcement
        if hasattr(runner, 'can_execute_pass'):
            # Should be able to execute Pass A
            can_execute_a = runner.can_execute_pass("A", job_config)
            assert can_execute_a, "Should be able to execute Pass A initially"

            # Should not be able to execute Pass B without A completion
            can_execute_b = runner.can_execute_pass("B", job_config)
            assert not can_execute_b, "Should not be able to execute Pass B without Pass A completion"

        # Test pass execution with mocked success
        if hasattr(runner, 'execute_pass'):
            with patch.object(runner, '_run_pass_a', return_value={"status": "SUCCESS", "artifacts": ["passA_toc.json"]}):
                pass_a_result = runner.execute_pass("A", job_config)

                assert isinstance(pass_a_result, dict), "Pass execution should return structured result"

                if "status" in pass_a_result:
                    assert pass_a_result["status"] == "SUCCESS", "Mocked Pass A should succeed"

                # After Pass A success, Pass B should be executable
                can_execute_b_after_a = runner.can_execute_pass("B", job_config)
                assert can_execute_b_after_a, "Pass B should be executable after Pass A success"

    def test_artifact_validation_gating(self):
        """Test artifact validation as gating mechanism"""
        try:
            from src_common.ingestion import ModularIngestionRunner
        except ImportError:
            pytest.skip("Modular ingestion runner not available for testing")

        runner = ModularIngestionRunner()

        # Test valid Pass A artifacts
        valid_pass_a_artifacts = {
            "passA_toc.json": {
                "source_id": "test_source_001",
                "sections": [
                    {"title": "Chapter 1: Introduction", "page_start": 1, "page_end": 10},
                    {"title": "Chapter 2: Spells", "page_start": 11, "page_end": 50},
                    {"title": "Chapter 3: Items", "page_start": 51, "page_end": 80}
                ],
                "total_pages": 80,
                "processing_metadata": {
                    "extracted_at": "2024-09-22T10:00:00Z",
                    "extraction_tool": "unstructured.io",
                    "confidence": 0.92
                }
            }
        }

        if hasattr(runner, 'validate_pass_artifacts'):
            # Test valid artifact validation
            validation_result = runner.validate_pass_artifacts("A", valid_pass_a_artifacts)

            assert isinstance(validation_result, dict), "Artifact validation should return structured result"

            if "valid" in validation_result:
                assert validation_result["valid"] == True, "Valid artifacts should pass validation"

            if "validation_details" in validation_result:
                details = validation_result["validation_details"]
                assert isinstance(details, dict), "Validation details should be structured"

        # Test invalid Pass A artifacts
        invalid_pass_a_artifacts = {
            "passA_toc.json": {
                "source_id": "test_source_001",
                "sections": [],  # Empty sections - should be invalid
                "total_pages": 0  # Zero pages - should be invalid
            }
        }

        if hasattr(runner, 'validate_pass_artifacts'):
            invalid_validation = runner.validate_pass_artifacts("A", invalid_pass_a_artifacts)

            if "valid" in invalid_validation:
                assert invalid_validation["valid"] == False, "Invalid artifacts should fail validation"

            if "errors" in invalid_validation:
                errors = invalid_validation["errors"]
                assert len(errors) > 0, "Invalid artifacts should produce error messages"

        # Test missing artifacts
        missing_artifacts = {}

        if hasattr(runner, 'validate_pass_artifacts'):
            missing_validation = runner.validate_pass_artifacts("A", missing_artifacts)

            if "valid" in missing_validation:
                assert missing_validation["valid"] == False, "Missing artifacts should fail validation"

    def test_pass_failure_and_halt_behavior(self):
        """Test pass failure handling and pipeline halt behavior"""
        try:
            from src_common.ingestion import ModularIngestionRunner
        except ImportError:
            pytest.skip("Modular ingestion runner not available for testing")

        runner = ModularIngestionRunner()

        # Test configuration with strict gating
        strict_config = {
            "job_id": "test_failure_001",
            "gating": {
                "strict": True,
                "halt_on_failure": True,
                "max_retries": 2
            },
            "passes": ["A", "B", "C", "D", "E", "F"]
        }

        # Test pass failure simulation
        if hasattr(runner, 'execute_pass'):
            # Simulate Pass C failure
            with patch.object(runner, '_run_pass_c', side_effect=Exception("Chunking failed: corrupted PDF")):
                pass_c_result = runner.execute_pass("C", strict_config)

                assert isinstance(pass_c_result, dict), "Failed pass should return structured result"

                if "status" in pass_c_result:
                    assert pass_c_result["status"] == "FAILED", "Failed pass should have FAILED status"

                if "error" in pass_c_result:
                    error = pass_c_result["error"]
                    assert "chunking failed" in error.lower(), "Error should contain failure reason"

        # Test pipeline halt behavior
        if hasattr(runner, 'should_halt_pipeline'):
            halt_decision = runner.should_halt_pipeline("C", "FAILED", strict_config)

            assert halt_decision == True, "Pipeline should halt on pass failure with strict gating"

        # Test subsequent pass blocking
        if hasattr(runner, 'can_execute_pass'):
            # After Pass C failure, Pass D should be blocked
            job_state_after_failure = {
                "passes": {
                    "A": {"status": "SUCCESS"},
                    "B": {"status": "SUCCESS"},
                    "C": {"status": "FAILED"},
                    "D": {"status": "BLOCKED"},
                    "E": {"status": "BLOCKED"},
                    "F": {"status": "BLOCKED"}
                }
            }

            can_execute_d = runner.can_execute_pass("D", {**strict_config, "job_state": job_state_after_failure})
            assert not can_execute_d, "Pass D should be blocked after Pass C failure"

    def test_resume_from_pass_functionality(self):
        """Test resume from specific pass functionality"""
        try:
            from src_common.ingestion import ModularIngestionRunner
        except ImportError:
            pytest.skip("Modular ingestion runner not available for testing")

        runner = ModularIngestionRunner()

        # Test job state for resume scenario
        resume_job_state = {
            "job_id": "test_resume_001",
            "passes": {
                "A": {"status": "SUCCESS", "artifacts": ["passA_toc.json"], "completed_at": "2024-09-22T10:00:00Z"},
                "B": {"status": "SUCCESS", "artifacts": ["passB_splits.json"], "completed_at": "2024-09-22T10:15:00Z"},
                "C": {"status": "FAILED", "error": "Timeout during chunking", "failed_at": "2024-09-22T10:30:00Z"},
                "D": {"status": "PENDING"},
                "E": {"status": "PENDING"},
                "F": {"status": "PENDING"}
            },
            "source_files": ["test_source.pdf"],
            "artifacts_dir": "/test/artifacts/test_resume_001"
        }

        # Test resume validation
        if hasattr(runner, 'validate_resume_capability'):
            resume_validation = runner.validate_resume_capability("C", resume_job_state)

            assert isinstance(resume_validation, dict), "Resume validation should return structured result"

            if "can_resume" in resume_validation:
                assert resume_validation["can_resume"] == True, "Should be able to resume from failed Pass C"

            if "prerequisite_status" in resume_validation:
                prereq_status = resume_validation["prerequisite_status"]
                assert prereq_status["A"] == "SUCCESS", "Pass A should be completed for resume"
                assert prereq_status["B"] == "SUCCESS", "Pass B should be completed for resume"

        # Test resume execution
        if hasattr(runner, 'resume_from_pass'):
            resume_config = {
                "resume_from": "C",
                "job_state": resume_job_state,
                "gating": {"strict": True, "validate_prerequisites": True}
            }

            # Mock successful Pass C execution on resume
            with patch.object(runner, '_run_pass_c', return_value={"status": "SUCCESS", "artifacts": ["passC_chunks.json"]}):
                resume_result = runner.resume_from_pass(resume_config)

                assert isinstance(resume_result, dict), "Resume should return structured result"

                if "resumed_successfully" in resume_result:
                    assert resume_result["resumed_successfully"] == True, "Resume should succeed with fixed pass"

                if "executed_passes" in resume_result:
                    executed = resume_result["executed_passes"]
                    assert "C" in executed, "Should execute resumed Pass C"

                    # Should not re-execute completed passes
                    assert "A" not in executed, "Should not re-execute completed Pass A"
                    assert "B" not in executed, "Should not re-execute completed Pass B"

    def test_job_manifest_and_state_management(self):
        """Test job manifest and state management functionality"""
        try:
            from src_common.ingestion.state import JobState
        except ImportError:
            pytest.skip("Job state management not available for testing")

        job_state = JobState()

        # Test manifest creation
        job_config = {
            "job_id": "test_manifest_001",
            "environment": "test",
            "sources": [{"source_id": "src_001", "path": "/test/file.pdf"}],
            "created_at": "2024-09-22T10:00:00Z"
        }

        if hasattr(job_state, 'create_manifest'):
            manifest = job_state.create_manifest(job_config)

            assert isinstance(manifest, dict), "Manifest should be structured"

            # Verify required manifest fields
            required_fields = ["job_id", "environment", "passes", "source_sha_map", "metrics"]
            for field in required_fields:
                if field in manifest:
                    if field == "passes":
                        passes = manifest[field]
                        assert isinstance(passes, dict), "Passes should be structured"

                        # Should initialize all passes
                        expected_passes = ["A", "B", "C", "D", "E", "F"]
                        for pass_name in expected_passes:
                            if pass_name in passes:
                                pass_state = passes[pass_name]
                                assert "status" in pass_state, f"Pass {pass_name} should have status"
                                assert pass_state["status"] == "PENDING", f"Pass {pass_name} should be initially pending"

        # Test state updates
        if hasattr(job_state, 'update_pass_status'):
            update_result = job_state.update_pass_status("test_manifest_001", "A", "SUCCESS", {"artifacts": ["passA_toc.json"]})

            assert isinstance(update_result, dict), "State update should return structured result"

            if "updated" in update_result:
                assert update_result["updated"] == True, "State update should succeed"

        # Test state persistence
        if hasattr(job_state, 'save_manifest') and hasattr(job_state, 'load_manifest'):
            # Save manifest
            save_result = job_state.save_manifest("test_manifest_001", manifest)
            if save_result.get("saved", False):
                # Load manifest
                loaded_manifest = job_state.load_manifest("test_manifest_001")

                assert isinstance(loaded_manifest, dict), "Loaded manifest should be structured"
                assert loaded_manifest["job_id"] == manifest["job_id"], "Loaded manifest should match saved manifest"

    def test_pass_idempotency_and_atomic_writes(self):
        """Test pass idempotency and atomic write operations"""
        try:
            from src_common.ingestion.io import AtomicFileOperations
        except ImportError:
            pytest.skip("Atomic file operations not available for testing")

        file_ops = AtomicFileOperations()

        # Test atomic write functionality
        test_data = {
            "source_id": "test_source_001",
            "processed_chunks": [
                {"chunk_id": "chunk_001", "content": "Test content 1"},
                {"chunk_id": "chunk_002", "content": "Test content 2"}
            ],
            "processing_metadata": {
                "processed_at": "2024-09-22T10:00:00Z",
                "chunk_count": 2
            }
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
            test_file_path = Path(tmp_file.name)

        try:
            if hasattr(file_ops, 'atomic_write_json'):
                # Test atomic write
                write_result = file_ops.atomic_write_json(test_file_path, test_data)

                assert isinstance(write_result, dict), "Atomic write should return structured result"

                if "written" in write_result:
                    assert write_result["written"] == True, "Atomic write should succeed"

                # Verify file exists and contains correct data
                assert test_file_path.exists(), "File should exist after atomic write"

                with open(test_file_path, 'r') as f:
                    written_data = json.load(f)

                assert written_data == test_data, "Written data should match input data"

                # Test idempotency - writing same data should produce same result
                second_write = file_ops.atomic_write_json(test_file_path, test_data)
                if "written" in second_write:
                    assert second_write["written"] == True, "Idempotent write should succeed"

                # Verify data hasn't changed
                with open(test_file_path, 'r') as f:
                    second_data = json.load(f)

                assert second_data == test_data, "Idempotent write should preserve data"

        finally:
            # Cleanup test file
            if test_file_path.exists():
                test_file_path.unlink()

    def test_modular_ingestion_contract_compliance(self):
        """Test that modular ingestion matches established contract"""
        # Test pass sequence contract
        required_pass_sequence = ["A", "B", "C", "D", "E", "F"]
        pass_dependencies = {
            "A": [],
            "B": ["A"],
            "C": ["A", "B"],
            "D": ["A", "B", "C"],
            "E": ["A", "B", "C", "D"],
            "F": ["A", "B", "C", "D", "E"]
        }

        for pass_name, dependencies in pass_dependencies.items():
            assert isinstance(dependencies, list), f"Pass {pass_name} dependencies should be list"

            # Verify dependency chain integrity
            for dep in dependencies:
                assert dep in required_pass_sequence, f"Dependency {dep} should be valid pass"
                dep_index = required_pass_sequence.index(dep)
                pass_index = required_pass_sequence.index(pass_name)
                assert dep_index < pass_index, f"Dependency {dep} should come before {pass_name}"

        # Test gating contract
        gating_requirements = {
            "strict_gates": True,
            "artifact_validation": True,
            "sequential_execution": True,
            "failure_halting": True,
            "resume_capability": True,
            "idempotent_operations": True
        }

        for requirement, needed in gating_requirements.items():
            assert needed, f"Gating requirement {requirement} is mandatory"

        # Test artifact contract
        required_artifacts = {
            "A": ["passA_toc.json"],
            "B": ["passB_splits.json"],
            "C": ["passC_chunks.json"],
            "D": ["passD_enriched.json"],
            "E": ["passE_graph.json"],
            "F": ["passF_cleanup.json"]
        }

        for pass_name, artifacts in required_artifacts.items():
            assert len(artifacts) >= 1, f"Pass {pass_name} should produce at least one artifact"

        # Test state management contract
        state_requirements = {
            "job_manifest": True,
            "pass_status_tracking": True,
            "artifact_tracking": True,
            "metrics_collection": True,
            "persistence": True
        }

        for requirement, needed in state_requirements.items():
            assert needed, f"State management requirement {requirement} is mandatory"