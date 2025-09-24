# tests/regression/phase1/test_rag001c_extraction.py
"""
Phase 1 - US RAG-001C: Pass C Content Extraction Regression Tests (HARD GATE)
Tests content extraction functionality using unstructured.io for chunking and enrichment
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassCExtraction:
    """Test suite for Pass C content extraction functionality (HARD GATE)"""

    def test_unstructured_tool_availability(self):
        """HARD GATE: Verify unstructured.io tool is available and functional"""
        try:
            # Test that unstructured can be imported
            import unstructured

            # Verify core partition functions are available
            from unstructured.partition.auto import partition
            assert callable(partition), "partition function should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: unstructured.io not available: {e}")

    def test_pass_c_module_integration(self):
        """HARD GATE: Test that Pass C module exists and integrates with unstructured.io"""
        try:
            # Import the Pass C module
            from src_common.pass_c_extraction import process_pass_c, PassCExtractor

            # Verify functions are available
            assert callable(process_pass_c), "process_pass_c function should be available"
            assert PassCExtractor is not None, "PassCExtractor class should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass C module not available: {e}")

    def test_pass_c_contract_compliance(self):
        """HARD GATE: Test that Pass C produces contract-compliant output structure"""
        try:
            from src_common.pass_c_extraction import process_pass_c
        except ImportError:
            pytest.skip("Pass C module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF file
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                # Write minimal PDF content
                f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF")

            # Create mock manifest from previous passes
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Chapter 1", "page_start": 1, "page_end": 5}
                    ]
                },
                "pass_b_output": {
                    "split_performed": False,
                    "split_index": {"no_split_reason": "file_under_threshold"}
                },
                "completed_passes": ["A", "B"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Test process_pass_c function
            result = process_pass_c(str(artifacts_dir))

            # Verify result structure
            assert isinstance(result, dict), "Process result should be a dictionary"
            assert "extraction_performed" in result, "Result should indicate if extraction was performed"
            assert "chunk_count" in result, "Result should contain chunk count"
            assert "updated_manifest" in result, "Result should contain updated manifest"

            # Verify manifest was updated
            updated_manifest = result["updated_manifest"]
            assert "pass_c_output" in updated_manifest, "Manifest should contain Pass C output"
            assert "completed_passes" in updated_manifest, "Manifest should track completed passes"
            assert "C" in updated_manifest["completed_passes"], "Pass C should be marked as completed"

    def test_pass_c_chunk_extraction(self):
        """HARD GATE: Test chunk extraction functionality with mock PDF"""
        try:
            from src_common.pass_c_extraction import process_pass_c
        except ImportError:
            pytest.skip("Pass C module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF file
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nTest PDF content\n%%EOF")

            # Mock unstructured.io partition function
            with patch('unstructured.partition.auto.partition') as mock_partition:
                # Configure mock to return sample elements
                mock_element = MagicMock()
                mock_element.text = "Sample extracted text content"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_partition.return_value = [mock_element]

                # Test chunk extraction
                chunks = process_pass_c(test_pdf_path)

                # Verify chunks structure
                assert isinstance(chunks, list), "Chunks should be a list"
                assert len(chunks) > 0, "Should extract at least one chunk"

                # Verify chunk structure
                chunk = chunks[0]
                assert "text" in chunk, "Chunk should contain text"
                assert "page" in chunk, "Chunk should contain page number"
                assert "type" in chunk, "Chunk should contain element type"

                # Verify unstructured.io was called
                mock_partition.assert_called_once()

    def test_pass_c_chunk_schema_validation(self):
        """HARD GATE: Test that extracted chunks follow required schema"""
        try:
            from src_common.pass_c_extraction import process_pass_c
        except ImportError:
            pytest.skip("Pass C module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nContent\n%%EOF")

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},
                "completed_passes": ["A", "B"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock unstructured.io
            with patch('unstructured.partition.auto.partition') as mock_partition:
                mock_element = MagicMock()
                mock_element.text = "Test chunk content"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_partition.return_value = [mock_element]

                # Test extraction
                result = process_pass_c(str(artifacts_dir))

                # Verify Pass C output structure
                pass_c_output = result["updated_manifest"]["pass_c_output"]

                # Check required fields
                assert "extraction_method" in pass_c_output, "Should document extraction method"
                assert "chunk_count" in pass_c_output, "Should document chunk count"
                assert "chunks_file" in pass_c_output, "Should reference chunks file"

                # Verify chunks were written to file
                chunks_file = artifacts_dir / pass_c_output["chunks_file"]
                assert chunks_file.exists(), "Chunks file should be created"

                # Verify chunks content
                with open(chunks_file, 'r') as f:
                    chunks = json.load(f)

                assert isinstance(chunks, list), "Chunks should be a list"
                for chunk in chunks:
                    assert "text" in chunk, "Each chunk should have text"
                    assert "page" in chunk, "Each chunk should have page number"
                    assert "type" in chunk, "Each chunk should have type"

    def test_pass_c_unstructured_version_tracking(self):
        """HARD GATE: Test that unstructured.io version can be tracked for manifest"""
        try:
            import unstructured

            # Should be able to get version information
            version = getattr(unstructured, '__version__', None)

            # Version should be available for tracking
            if version is not None:
                assert isinstance(version, str), "Version should be a string"
                assert len(version) > 0, "Version should not be empty"
            else:
                # Some packages store version differently
                try:
                    from importlib.metadata import version as get_version
                    version = get_version('unstructured')
                    assert isinstance(version, str), "Version should be a string"
                    assert len(version) > 0, "Version should not be empty"
                except:
                    pytest.skip("unstructured version not accessible through standard methods")

        except ImportError:
            pytest.skip("unstructured not available for version checking")

    def test_pass_c_error_handling(self):
        """HARD GATE: Test that Pass C handles errors gracefully"""
        try:
            from src_common.pass_c_extraction import process_pass_c
        except ImportError:
            pytest.skip("Pass C module not available for testing")

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            process_pass_c("/nonexistent/artifacts")

        # Test with invalid manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create invalid manifest
            manifest_path = artifacts_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                f.write("invalid json content")

            with pytest.raises(json.JSONDecodeError):
                process_pass_c(str(artifacts_dir))

    def test_pass_c_performance_baseline(self):
        """HARD GATE: Test that Pass C meets performance requirements"""
        try:
            from src_common.pass_c_extraction import process_pass_c
        except ImportError:
            pytest.skip("Pass C module not available for testing")

        import time

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},
                "completed_passes": ["A", "B"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Create minimal PDF
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nContent\n%%EOF")

            # Mock unstructured.io for performance test
            with patch('unstructured.partition.auto.partition') as mock_partition:
                mock_element = MagicMock()
                mock_element.text = "Test content"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_partition.return_value = [mock_element]

                # Measure processing time
                start_time = time.time()
                result = process_pass_c(str(artifacts_dir))
                end_time = time.time()

                processing_time = end_time - start_time

                # Should complete within reasonable time (15 seconds for test data)
                assert processing_time < 15.0, f"Pass C took {processing_time:.2f}s, should be < 15s for test data"
                assert isinstance(result, dict), "Should produce valid result"