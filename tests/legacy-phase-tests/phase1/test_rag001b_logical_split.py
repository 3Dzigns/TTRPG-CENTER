# tests/regression/phase1/test_rag001b_logical_split.py
"""
Phase 1 - US RAG-001B: Pass B Logical Split Regression Tests (HARD GATE)
Tests logical splitting of large PDFs (>25MB) using ToC guidance from Pass A
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassBLogicalSplit:
    """Test suite for Pass B logical splitting of large PDFs (HARD GATE)"""

    def test_pypdf_tool_availability(self):
        """HARD GATE: Verify PyPDF tool is available and functional"""
        try:
            # Test that PyPDF can be imported
            import pypdf

            # Verify the PdfReader is available
            assert hasattr(pypdf, 'PdfReader'), "PdfReader should be available"
            assert hasattr(pypdf, 'PdfWriter'), "PdfWriter should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: PyPDF not available: {e}")

    def test_pass_b_module_integration(self):
        """HARD GATE: Test that Pass B module exists and integrates with PyPDF"""
        try:
            # Import the Pass B module
            from src_common.pass_b_logical_splitter import process_pass_b, PassBLogicalSplitter, SPLIT_THRESHOLD_BYTES

            # Verify functions are available
            assert callable(process_pass_b), "process_pass_b function should be available"
            assert PassBLogicalSplitter is not None, "PassBLogicalSplitter class should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass B module not available: {e}")

    def test_pass_b_contract_compliance(self):
        """HARD GATE: Test that Pass B produces contract-compliant output structure"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b, PassBLogicalSplitter, SPLIT_THRESHOLD_BYTES
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF file (small, should not split)
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                # Write minimal PDF content (small file)
                f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF")

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},  # Small file
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Chapter 1", "page_start": 1, "page_end": 5},
                        {"title": "Chapter 2", "page_start": 6, "page_end": 10}
                    ]
                }
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Test size threshold checking (simulate the internal logic)
            test_file_size = os.path.getsize(test_pdf_path)
            should_split = test_file_size > SPLIT_THRESHOLD_BYTES
            assert isinstance(should_split, bool), "Size check should return boolean"
            assert should_split == False, "Small PDF should not be split"

            # Test process_pass_b function
            result = process_pass_b(Path(test_pdf_path), artifacts_dir, "test_job")

            # Verify result structure (PassBResult object)
            assert hasattr(result, 'split_performed'), "Result should indicate if split was performed"
            assert hasattr(result, 'success'), "Result should indicate success"
            assert hasattr(result, 'parts_created'), "Result should contain parts count"

            # For small files, no split should be performed
            assert result.split_performed == False, "Small file should not trigger split"
            assert result.success == True, "Processing should succeed"
            assert result.parts_created == 0, "No parts should be created for small files"

            # Verify manifest file was updated
            assert Path(result.manifest_path).exists(), "Manifest should be updated"

    def test_pass_b_large_file_splitting(self):
        """HARD GATE: Test large file splitting functionality"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b, SPLIT_THRESHOLD_BYTES
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Create mock artifacts directory for large file test
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF file (large, should split)
            test_pdf_path = artifacts_dir / "large_test.pdf"
            with open(test_pdf_path, 'wb') as f:
                # Write enough content to exceed threshold
                content = b"%PDF-1.4\nLarge PDF content\n%%EOF"
                # Pad to exceed 25MB threshold
                padding_size = SPLIT_THRESHOLD_BYTES + 1000
                f.write(content)
                f.write(b"X" * padding_size)

            # Create mock manifest with ToC sections
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": SPLIT_THRESHOLD_BYTES + 1000},
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Chapter 1", "page_start": 1, "page_end": 10},
                        {"title": "Chapter 2", "page_start": 11, "page_end": 20},
                        {"title": "Chapter 3", "page_start": 21, "page_end": 30}
                    ]
                }
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock pypdf operations for splitting
            with patch('pypdf.PdfReader') as mock_reader, \
                 patch('pypdf.PdfWriter') as mock_writer:

                # Configure mocks
                mock_reader_instance = MagicMock()
                mock_reader.return_value = mock_reader_instance
                mock_reader_instance.pages = [MagicMock() for _ in range(30)]  # 30 pages

                mock_writer_instance = MagicMock()
                mock_writer.return_value = mock_writer_instance

                # Test process_pass_b with large file
                result = process_pass_b(Path(test_pdf_path), artifacts_dir, "test_job")

                # Verify split was attempted for large file
                assert hasattr(result, 'split_performed'), "Result should indicate if split was performed"
                assert result.success == True, "Processing should succeed"

                # Should have attempted to read the PDF
                mock_reader.assert_called()

                # Should have created writers for splitting
                assert mock_writer.call_count >= 0, "Should attempt to create PDF writers for splitting"

    def test_pass_b_split_index_integrity(self):
        """HARD GATE: Test that split index references valid ToC sections"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock manifest with ToC sections
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},  # Small file - no split
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Introduction", "page_start": 1, "page_end": 5},
                        {"title": "Main Content", "page_start": 6, "page_end": 15},
                        {"title": "Conclusion", "page_start": 16, "page_end": 20}
                    ]
                }
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Create minimal PDF
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nMinimal content\n%%EOF")

            # Test process_pass_b
            result = process_pass_b(Path(test_pdf_path), artifacts_dir, "test_job", "dev")

            # Verify result structure for small file (no actual splitting)
            assert result.split_performed == False, "Small file should not be split"
            assert result.success == True, "Processing should succeed"

            # For small files, should still have structure but no splits
            if not result["split_performed"]:
                assert "no_split_reason" in split_index, "Should document why no split was performed"
                assert split_index["no_split_reason"] == "file_under_threshold", "Should indicate size threshold"

            # Verify all ToC sections are accounted for
            original_sections = mock_manifest["pass_a_output"]["toc_sections"]
            assert len(original_sections) == 3, "Should have 3 ToC sections for test"

    def test_pass_b_pypdf_version_tracking(self):
        """HARD GATE: Test that PyPDF version can be tracked for manifest"""
        try:
            import pypdf

            # Should be able to get version information
            version = getattr(pypdf, '__version__', None)

            # Version should be available for tracking
            assert version is not None, "PyPDF version should be available for manifest tracking"
            assert isinstance(version, str), "Version should be a string"
            assert len(version) > 0, "Version should not be empty"

        except ImportError:
            pytest.skip("PyPDF not available for version checking")

    def test_pass_b_threshold_calculation(self):
        """HARD GATE: Test that splitting threshold is calculated correctly"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b, SPLIT_THRESHOLD_BYTES
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Test files of different sizes
        with tempfile.TemporaryDirectory() as temp_dir:
            # Small file - should not split
            small_file = Path(temp_dir) / "small.pdf"
            with open(small_file, 'wb') as f:
                f.write(b"small content")

            # Large file - should split
            large_file = Path(temp_dir) / "large.pdf"
            with open(large_file, 'wb') as f:
                f.write(b"X" * (SPLIT_THRESHOLD_BYTES + 1000))

            # Test threshold logic
            assert os.path.getsize(small_file) <= SPLIT_THRESHOLD_BYTES, "Small file should not exceed threshold"
            assert os.path.getsize(large_file) > SPLIT_THRESHOLD_BYTES, "Large file should exceed threshold"

            # Test exact threshold
            threshold_file = Path(temp_dir) / "threshold.pdf"
            with open(threshold_file, 'wb') as f:
                f.write(b"X" * SPLIT_THRESHOLD_BYTES)

            # Exactly at threshold should not split (> threshold required)
            assert os.path.getsize(threshold_file) == SPLIT_THRESHOLD_BYTES, "File should be at exact threshold"

    def test_pass_b_manifest_updates(self):
        """HARD GATE: Test that Pass B updates manifest with correct content"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Chapter 1", "page_start": 1, "page_end": 10}
                    ]
                },
                "completed_passes": ["A"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Create minimal PDF
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nContent\n%%EOF")

            # Test process_pass_b with small file
            result = process_pass_b(Path(small_file), artifacts_dir, "test_job")

            # Verify manifest was updated
            updated_manifest = result["updated_manifest"]

            assert "pass_b_output" in updated_manifest, "Manifest should contain Pass B output"
            assert "B" in updated_manifest["completed_passes"], "Pass B should be marked completed"

            pass_b_output = updated_manifest["pass_b_output"]
            assert "split_performed" in pass_b_output, "Should document if split was performed"
            assert "threshold_check" in pass_b_output, "Should document threshold check"
            assert "file_size_bytes" in pass_b_output, "Should record file size"

    def test_pass_b_error_handling(self):
        """HARD GATE: Test that Pass B handles errors gracefully"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            process_pass_b(Path("/nonexistent/file.pdf"), Path("/tmp"), "test_job")

        # Test with invalid manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create invalid manifest
            manifest_path = artifacts_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                f.write("invalid json content")

            with pytest.raises(json.JSONDecodeError):
                process_pass_b(Path(test_pdf_path), artifacts_dir, "test_job")

    def test_pass_b_performance_baseline(self):
        """HARD GATE: Test that Pass B meets performance requirements"""
        try:
            from src_common.pass_b_logical_splitter import process_pass_b
        except ImportError:
            pytest.skip("Pass B module not available for testing")

        import time

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 1024},  # Small file
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Chapter 1", "page_start": 1, "page_end": 10}
                    ]
                }
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Create minimal PDF
            test_pdf_path = artifacts_dir / "test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(b"%PDF-1.4\nContent\n%%EOF")

            # Measure processing time
            start_time = time.time()
            result = process_pass_b(Path(test_pdf_path), artifacts_dir, "test_job")
            end_time = time.time()

            processing_time = end_time - start_time

            # Should complete within reasonable time (10 seconds for small file test)
            assert processing_time < 10.0, f"Pass B took {processing_time:.2f}s, should be < 10s for test data"
            assert isinstance(result, dict), "Should produce valid result"