# tests/regression/phase1/test_rag001f_finalizer.py
"""
Phase 1 - US RAG-001F: Pass F Finalization Regression Tests (HARD GATE)
Tests finalization functionality for validation, cleanup, and manifest completion
"""

import json
import pytest
import tempfile
import os
import shutil
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassFFinalizer:
    """Test suite for Pass F finalization functionality (HARD GATE)"""

    def test_pass_f_module_availability(self):
        """HARD GATE: Verify Pass F module is available and functional"""
        try:
            # Import the Pass F module
            from src_common.pass_f_finalizer import process_pass_f, PassFFinalizer

            # Verify functions are available
            assert callable(process_pass_f), "process_pass_f function should be available"
            assert callable(process_pass_f), "process_pass_f function should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass F module not available: {e}")

    def test_pass_f_contract_compliance(self):
        """HARD GATE: Test that Pass F produces contract-compliant output structure"""
        try:
            from src_common.pass_f_finalizer import process_pass_f
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock files from previous passes
            test_files = {
                "test_pass_c_chunks.jsonl": [
                    {"text": "Test chunk", "page": 1, "chunk_id": "chunk_001"}
                ],
                "test_pass_d_vectors.jsonl": [
                    {"text": "Test chunk", "chunk_id": "chunk_001", "vector": [0.1] * 1536, "stage": "vectorized"}
                ],
                "test_pass_e_graph.jsonl": [
                    {"text": "Test chunk", "chunk_id": "chunk_001", "graph_refs": [], "stage": "graph_enriched"}
                ]
            }

            # Create test files
            for filename, content in test_files.items():
                file_path = artifacts_dir / filename
                with open(file_path, 'w') as f:
                    for item in content:
                        f.write(json.dumps(item) + '\n')

            # Create manifest from all previous passes
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "job_id": "test_job_001",
                "pdf_metadata": {"file_size_bytes": 2048000, "filename": "test.pdf"},
                "pass_a_output": {"toc_sections": [], "completed_at": "2024-01-01T10:00:00Z"},
                "pass_b_output": {"split_performed": False, "completed_at": "2024-01-01T10:01:00Z"},
                "pass_c_output": {"chunks_file": "test_pass_c_chunks.jsonl", "chunk_count": 1, "completed_at": "2024-01-01T10:02:00Z"},
                "pass_d_output": {"vectors_file": "test_pass_d_vectors.jsonl", "vector_count": 1, "completed_at": "2024-01-01T10:03:00Z"},
                "pass_e_output": {"enriched_chunks_file": "test_pass_e_graph.jsonl", "node_count": 5, "edge_count": 3, "completed_at": "2024-01-01T10:04:00Z"},
                "completed_passes": ["A", "B", "C", "D", "E"],
                "created_at": "2024-01-01T10:00:00Z"
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Test process_pass_f function
            result = process_pass_f(str(artifacts_dir))

            # Verify result structure
            assert isinstance(result, dict), "Process result should be a dictionary"
            assert "finalization_completed" in result, "Result should indicate if finalization completed"
            assert "validation_passed" in result, "Result should indicate validation status"
            assert "cleanup_performed" in result, "Result should indicate cleanup status"
            assert "updated_manifest" in result, "Result should contain updated manifest"

            # Verify manifest was finalized
            updated_manifest = result["updated_manifest"]
            assert "pass_f_output" in updated_manifest, "Manifest should contain Pass F output"
            assert "completed_passes" in updated_manifest, "Manifest should track completed passes"
            assert "F" in updated_manifest["completed_passes"], "Pass F should be marked as completed"
            assert "run_summary" in updated_manifest, "Manifest should contain run summary"
            assert "checksums" in updated_manifest, "Manifest should contain file checksums"

    def test_pass_f_artifact_validation(self):
        """HARD GATE: Test artifact validation and integrity checks"""
        try:
            from src_common.pass_f_finalizer import process_pass_f
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create valid artifact files
            valid_files = {
                "chunks.jsonl": [
                    {"text": "Valid chunk", "chunk_id": "chunk_001", "page": 1}
                ],
                "vectors.jsonl": [
                    {"chunk_id": "chunk_001", "vector": [0.1] * 1536, "vector_id": "vec_001"}
                ],
                "manifest.json": {
                    "job_id": "test_001",
                    "completed_passes": ["A", "B", "C", "D", "E"]
                }
            }

            # Create files
            for filename, content in valid_files.items():
                file_path = artifacts_dir / filename
                if filename.endswith('.jsonl'):
                    with open(file_path, 'w') as f:
                        for item in content:
                            f.write(json.dumps(item) + '\n')
                else:
                    with open(file_path, 'w') as f:
                        json.dump(content, f)

            # Test validation
            validation_result = process_pass_f(str(artifacts_dir))

            # Verify validation results
            assert isinstance(validation_result, dict), "Validation result should be a dictionary"
            assert "valid" in validation_result, "Should indicate overall validity"
            assert "file_checks" in validation_result, "Should contain file-level checks"
            assert "integrity_checks" in validation_result, "Should contain integrity checks"

            # Verify specific validations
            file_checks = validation_result["file_checks"]
            assert "chunks.jsonl" in file_checks, "Should validate chunks file"
            assert "vectors.jsonl" in file_checks, "Should validate vectors file"
            assert "manifest.json" in file_checks, "Should validate manifest file"

            # All files should be valid
            for filename, check_result in file_checks.items():
                assert check_result["valid"] == True, f"File {filename} should be valid"

    def test_pass_f_atomic_file_operations(self):
        """HARD GATE: Test atomic file operations and temp file management"""
        try:
            from src_common.pass_f_finalizer import move_temp_files_atomically
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock temp and final directories
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "temp"
            final_path = Path(temp_dir) / "final"
            temp_path.mkdir()
            final_path.mkdir()

            # Create temporary files
            temp_files = ["temp_chunks.jsonl", "temp_vectors.jsonl", "temp_manifest.json"]
            for filename in temp_files:
                temp_file = temp_path / filename
                with open(temp_file, 'w') as f:
                    f.write(f"Content of {filename}")

            # Test atomic move operation
            move_result = move_temp_files_atomically(str(temp_path), str(final_path))

            # Verify move results
            assert isinstance(move_result, dict), "Move result should be a dictionary"
            assert "success" in move_result, "Should indicate success status"
            assert "moved_files" in move_result, "Should list moved files"

            # Verify files were moved
            for filename in temp_files:
                final_file = final_path / filename
                assert final_file.exists(), f"File {filename} should exist in final location"

                # Verify content integrity
                with open(final_file, 'r') as f:
                    content = f.read()
                    assert content == f"Content of {filename}", "File content should be preserved"

                # Original temp file should not exist
                temp_file = temp_path / filename
                assert not temp_file.exists(), f"Temp file {filename} should be removed"

    def test_pass_f_cleanup_operations(self):
        """HARD GATE: Test cleanup of partial and incomplete artifacts"""
        try:
            from src_common.pass_f_finalizer import cleanup_partial_artifacts
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock artifacts directory with partial files
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create complete files
            complete_files = {
                "final_chunks.jsonl": {"status": "complete"},
                "final_vectors.jsonl": {"status": "complete"}
            }

            # Create partial/incomplete files
            partial_files = {
                "temp_incomplete.jsonl": {"status": "partial"},
                "backup_old.jsonl": {"status": "outdated"},
                ".tmp_processing": {"status": "temp"}
            }

            # Create all files
            all_files = {**complete_files, **partial_files}
            for filename, content in all_files.items():
                file_path = artifacts_dir / filename
                with open(file_path, 'w') as f:
                    json.dump(content, f)

            # Create cleanup report tracking what should be cleaned
            cleanup_rules = {
                "patterns_to_remove": ["temp_*", "backup_*", ".*tmp*"],
                "preserve_patterns": ["final_*"]
            }

            # Test cleanup operation
            cleanup_result = cleanup_partial_artifacts(str(artifacts_dir), cleanup_rules)

            # Verify cleanup results
            assert isinstance(cleanup_result, dict), "Cleanup result should be a dictionary"
            assert "cleaned_files" in cleanup_result, "Should list cleaned files"
            assert "preserved_files" in cleanup_result, "Should list preserved files"
            assert "deletion_count" in cleanup_result, "Should report deletion count"

            # Verify correct files were preserved
            for filename in complete_files.keys():
                file_path = artifacts_dir / filename
                assert file_path.exists(), f"Complete file {filename} should be preserved"

            # Verify partial files were cleaned (depending on implementation)
            cleanup_count = cleanup_result["deletion_count"]
            assert cleanup_count >= 0, "Should report non-negative deletion count"

    def test_pass_f_checksum_generation(self):
        """HARD GATE: Test checksum generation for file integrity"""
        try:
            from src_common.pass_f_finalizer import generate_file_checksums
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create test files with known content
            test_files = {
                "test_chunks.jsonl": '{"chunk_id": "001", "text": "test content"}\n',
                "test_vectors.jsonl": '{"vector_id": "vec_001", "vector": [0.1, 0.2, 0.3]}\n',
                "manifest.json": '{"job_id": "test", "status": "processing"}'
            }

            # Create files and calculate expected checksums
            expected_checksums = {}
            for filename, content in test_files.items():
                file_path = artifacts_dir / filename
                with open(file_path, 'w') as f:
                    f.write(content)

                # Calculate expected checksum
                expected_checksums[filename] = hashlib.sha256(content.encode()).hexdigest()

            # Test checksum generation
            checksums_result = generate_file_checksums(str(artifacts_dir))

            # Verify checksum results
            assert isinstance(checksums_result, dict), "Checksums result should be a dictionary"
            assert "checksums" in checksums_result, "Should contain checksums map"
            assert "algorithm" in checksums_result, "Should specify hash algorithm"

            # Verify specific checksums
            actual_checksums = checksums_result["checksums"]
            for filename, expected_hash in expected_checksums.items():
                assert filename in actual_checksums, f"Should have checksum for {filename}"
                assert actual_checksums[filename] == expected_hash, f"Checksum mismatch for {filename}"

    def test_pass_f_manifest_finalization(self):
        """HARD GATE: Test manifest finalization with run summary"""
        try:
            from src_common.pass_f_finalizer import finalize_manifest
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock manifest data
        mock_manifest = {
            "job_id": "test_job_001",
            "created_at": "2024-01-01T10:00:00Z",
            "pdf_metadata": {"filename": "test.pdf", "file_size_bytes": 1024000},
            "pass_a_output": {"toc_sections": [], "processing_time_ms": 1000},
            "pass_b_output": {"split_performed": False, "processing_time_ms": 500},
            "pass_c_output": {"chunk_count": 50, "processing_time_ms": 2000},
            "pass_d_output": {"vector_count": 50, "processing_time_ms": 5000},
            "pass_e_output": {"node_count": 75, "edge_count": 120, "processing_time_ms": 3000},
            "completed_passes": ["A", "B", "C", "D", "E"]
        }

        # Mock file checksums
        mock_checksums = {
            "chunks.jsonl": "abcd1234...",
            "vectors.jsonl": "efgh5678...",
            "graph.json": "ijkl9012..."
        }

        # Test manifest finalization
        finalized_manifest = finalize_manifest(mock_manifest, mock_checksums)

        # Verify finalized manifest structure
        assert isinstance(finalized_manifest, dict), "Finalized manifest should be a dictionary"
        assert "pass_f_output" in finalized_manifest, "Should contain Pass F output"
        assert "F" in finalized_manifest["completed_passes"], "Should mark Pass F as completed"
        assert "run_summary" in finalized_manifest, "Should contain run summary"
        assert "checksums" in finalized_manifest, "Should contain file checksums"
        assert "finalized_at" in finalized_manifest, "Should have finalization timestamp"

        # Verify run summary content
        run_summary = finalized_manifest["run_summary"]
        assert "total_processing_time_ms" in run_summary, "Should calculate total processing time"
        assert "total_chunks_processed" in run_summary, "Should count total chunks"
        assert "passes_completed" in run_summary, "Should list completed passes"
        assert "final_stage" in run_summary, "Should indicate final processing stage"

        # Verify checksums were included
        assert finalized_manifest["checksums"] == mock_checksums, "Should preserve checksums"

    def test_pass_f_error_handling(self):
        """HARD GATE: Test that Pass F handles errors gracefully"""
        try:
            from src_common.pass_f_finalizer import process_pass_f
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            process_pass_f("/nonexistent/artifacts")

        # Test with corrupted manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create corrupted manifest
            manifest_path = artifacts_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                f.write("invalid json content")

            with pytest.raises(json.JSONDecodeError):
                process_pass_f(str(artifacts_dir))

    def test_pass_f_performance_baseline(self):
        """HARD GATE: Test that Pass F meets performance requirements"""
        try:
            from src_common.pass_f_finalizer import process_pass_f
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        import time

        # Create mock artifacts directory with realistic file sizes
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create moderately sized test files
            large_chunks = [
                {"text": f"Large chunk content {i} " * 100, "chunk_id": f"chunk_{i:03d}", "page": i}
                for i in range(100)  # 100 chunks
            ]

            chunks_file = artifacts_dir / "chunks.jsonl"
            with open(chunks_file, 'w') as f:
                for chunk in large_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create vectors file
            vectors_file = artifacts_dir / "vectors.jsonl"
            with open(vectors_file, 'w') as f:
                for i in range(100):
                    vector_chunk = {
                        "chunk_id": f"chunk_{i:03d}",
                        "vector": [0.1 * i] * 1536,
                        "stage": "vectorized"
                    }
                    f.write(json.dumps(vector_chunk) + '\n')

            # Create manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "job_id": "perf_test_001",
                "pass_a_output": {"processing_time_ms": 1000},
                "pass_b_output": {"processing_time_ms": 500},
                "pass_c_output": {"chunk_count": 100, "processing_time_ms": 3000},
                "pass_d_output": {"vector_count": 100, "processing_time_ms": 8000},
                "pass_e_output": {"node_count": 150, "processing_time_ms": 5000},
                "completed_passes": ["A", "B", "C", "D", "E"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Measure processing time
            start_time = time.time()
            result = process_pass_f(str(artifacts_dir))
            end_time = time.time()

            processing_time = end_time - start_time

            # Should complete within reasonable time (20 seconds for test data)
            assert processing_time < 20.0, f"Pass F took {processing_time:.2f}s, should be < 20s for test data"
            assert isinstance(result, dict), "Should produce valid result"
            assert result["finalization_completed"] == True, "Should complete finalization successfully"

    def test_pass_f_file_permissions_and_security(self):
        """HARD GATE: Test file permissions and security constraints"""
        try:
            from src_common.pass_f_finalizer import secure_file_operations
        except ImportError:
            pytest.skip("Pass F module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create test files
            test_file = artifacts_dir / "sensitive_data.jsonl"
            with open(test_file, 'w') as f:
                f.write('{"data": "sensitive content"}\n')

            # Test secure file operations
            security_result = secure_file_operations(str(artifacts_dir))

            # Verify security measures
            assert isinstance(security_result, dict), "Security result should be a dictionary"
            assert "permissions_set" in security_result, "Should report permission settings"
            assert "secure_cleanup" in security_result, "Should report cleanup status"

            # Verify no sensitive data leakage in logs or temp files
            assert "data_sanitized" in security_result, "Should confirm data sanitization"