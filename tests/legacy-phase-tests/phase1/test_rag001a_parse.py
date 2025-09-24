# tests/regression/phase1/test_rag001a_parse.py
"""
Phase 1 - US RAG-001A: Pass A Parse/Chunk Regression Tests (HARD GATE)
Tests PDF parsing and chunking using unstructured.io with real tool integration
"""

import json
import pytest
import hashlib
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


class TestPassAParseChunk:
    """Test suite for Pass A PDF parsing and chunking with unstructured.io (HARD GATE)"""

    def test_unstructured_tool_availability(self):
        """HARD GATE: Verify unstructured.io tool is available and functional"""
        try:
            # Test that unstructured can be imported
            from unstructured.partition.pdf import partition_pdf

            # Verify the function is callable
            assert callable(partition_pdf), "partition_pdf should be callable"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: unstructured.io not available: {e}")

    def test_pass_a_module_integration(self):
        """HARD GATE: Test that Pass A module exists and integrates with unstructured.io"""
        try:
            # Import the Pass A module
            from src_common.pass_a_toc_parser import process_pass_a, PassATocParser

            # Verify functions are available
            assert callable(process_pass_a), "process_pass_a function should be available"
            assert PassATocParser is not None, "PassATocParser class should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass A module not available: {e}")

    def test_pass_a_contract_compliance_with_mock_pdf(self):
        """HARD GATE: Test that Pass A produces contract-compliant output structure"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        # Create a minimal test PDF content using a mock
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            # Create minimal PDF content (this would normally be a real PDF)
            temp_pdf.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Test Content) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000062 00000 n \n0000000120 00000 n \n0000000202 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n295\n%%EOF")
            temp_pdf_path = temp_pdf.name

        with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as temp_output:
            temp_output_path = temp_output.name

        try:
            # Mock the unstructured call to return expected structure
            with patch('unstructured.partition.pdf.partition_pdf') as mock_partition:
                # Create mock elements that match unstructured.io output
                class MockElement:
                    def __init__(self, text, page_number=1, category="Text", section=None):
                        self.text = text
                        self.metadata = type('obj', (object,), {
                            'page_number': page_number,
                            'section': section
                        })()
                        self.category = category

                mock_elements = [
                    MockElement("Test Content", 1, "Text", "Introduction"),
                    MockElement("Sample text for testing", 1, "Text", "Body"),
                    MockElement("", 1, "Text"),  # Empty element (should be filtered)
                    MockElement("Page 2 content", 2, "Title", "Chapter 1"),
                ]

                mock_partition.return_value = mock_elements

                # Setup artifacts directory for process_pass_a
                artifacts_dir = Path(temp_output_path).parent / "artifacts"
                artifacts_dir.mkdir(exist_ok=True)

                # Copy PDF to artifacts directory
                import shutil
                temp_pdf_in_artifacts = artifacts_dir / "test.pdf"
                shutil.copy2(temp_pdf_path, temp_pdf_in_artifacts)

                # Create manifest for process_pass_a
                manifest = {
                    "job_id": "test_job",
                    "pdf_file": "test.pdf",
                    "completed_passes": []
                }
                manifest_path = artifacts_dir / "manifest.json"
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f)

                # Call process_pass_a with real tool integration (mocked for testing)
                result = process_pass_a(str(artifacts_dir))

                # Extract chunks from result
                chunks = result.get('pass_a_output', {}).get('toc_entries', [])
                if not chunks:
                    # Fallback: read chunks from file if available
                    toc_file = artifacts_dir / result.get('pass_a_output', {}).get('toc_file', 'toc.jsonl')
                    if toc_file.exists():
                        chunks = []
                        with open(toc_file, 'r') as f:
                            for line in f:
                                if line.strip():
                                    chunks.append(json.loads(line))

                # Verify contract compliance
                assert isinstance(chunks, list), "process_pass_a should return chunks as a list"
                assert len(chunks) > 0, "Should produce at least one chunk"

                # Verify each chunk has required fields
                required_fields = {"text", "page", "section", "type"}
                for i, chunk in enumerate(chunks):
                    assert isinstance(chunk, dict), f"Chunk {i} should be a dictionary"
                    assert required_fields.issubset(chunk.keys()), f"Chunk {i} missing required fields: {chunk.keys()}"

                    # Verify field types and constraints
                    assert isinstance(chunk["text"], str), f"Chunk {i} text should be string"
                    assert len(chunk["text"].strip()) > 0, f"Chunk {i} should not have empty text"
                    assert isinstance(chunk["page"], (int, type(None))), f"Chunk {i} page should be int or None"
                    assert isinstance(chunk["section"], str), f"Chunk {i} section should be string"
                    assert isinstance(chunk["type"], str), f"Chunk {i} type should be string"

                # Verify manifest was updated
                updated_manifest_path = artifacts_dir / "manifest.json"
                assert updated_manifest_path.exists(), "Manifest should be updated"

                with open(updated_manifest_path, 'r') as f:
                    updated_manifest = json.load(f)

                assert "pass_a_output" in updated_manifest, "Manifest should contain pass_a_output"
                assert "A" in updated_manifest.get("completed_passes", []), "Pass A should be marked complete"

        finally:
            # Cleanup
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)

    def test_pass_a_deterministic_output(self):
        """HARD GATE: Test that Pass A produces deterministic output for same input"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        # Test with mock chunks
        test_chunks = [
            {"text": "First chunk of text", "page": 1, "section": "intro", "type": "Text"},
            {"text": "Second chunk of text", "page": 1, "section": "body", "type": "Text"},
            {"text": "Third chunk on page 2", "page": 2, "section": "conclusion", "type": "Text"},
        ]

        # Test that process_pass_a produces deterministic results by running twice
        with tempfile.TemporaryDirectory() as temp_dir1, tempfile.TemporaryDirectory() as temp_dir2:
            # Setup identical test environments
            for temp_dir in [temp_dir1, temp_dir2]:
                artifacts_dir = Path(temp_dir) / "artifacts"
                artifacts_dir.mkdir()

                # Create test PDF
                test_pdf = artifacts_dir / "test.pdf"
                test_pdf.write_bytes(b"%PDF-1.4 minimal test content")

                # Create manifest
                manifest = {"job_id": "test_job", "pdf_file": "test.pdf", "completed_passes": []}
                with open(artifacts_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)

            # Mock to ensure deterministic output
            with patch('unstructured.partition.pdf.partition_pdf') as mock_partition:
                mock_partition.return_value = []

                result1 = process_pass_a(str(Path(temp_dir1) / "artifacts"))
                result2 = process_pass_a(str(Path(temp_dir2) / "artifacts"))

                # Results should be structurally identical
                assert type(result1) == type(result2), "Results should have same type"
                assert result1.keys() == result2.keys(), "Results should have same keys"

    def test_pass_a_coverage_validation(self):
        """HARD GATE: Test that Pass A achieves proper page coverage"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(b"mock pdf content")
            temp_pdf_path = temp_pdf.name

        with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as temp_output:
            temp_output_path = temp_output.name

        try:
            # Mock multi-page PDF processing
            with patch('unstructured.partition.pdf.partition_pdf') as mock_partition:
                class MockElement:
                    def __init__(self, text, page_number, category="Text"):
                        self.text = text
                        self.metadata = type('obj', (object,), {
                            'page_number': page_number,
                            'section': None
                        })()
                        self.category = category

                # Simulate a 3-page document
                mock_elements = [
                    MockElement("Content on page 1", 1),
                    MockElement("More content on page 1", 1),
                    MockElement("Content on page 2", 2),
                    MockElement("Content on page 3", 3),
                    MockElement("Final content on page 3", 3),
                ]

                mock_partition.return_value = mock_elements

                # Setup artifacts directory
                artifacts_dir = Path(temp_output_path).parent / "artifacts"
                artifacts_dir.mkdir(exist_ok=True)

                # Copy PDF and create manifest
                import shutil
                temp_pdf_in_artifacts = artifacts_dir / "test.pdf"
                shutil.copy2(temp_pdf_path, temp_pdf_in_artifacts)

                manifest = {"job_id": "test_job", "pdf_file": "test.pdf", "completed_passes": []}
                with open(artifacts_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)

                result = process_pass_a(str(artifacts_dir))
                chunks = result.get('pass_a_output', {}).get('toc_entries', [])

                # Verify page coverage
                pages_found = set()
                for chunk in chunks:
                    if chunk["page"] is not None:
                        pages_found.add(chunk["page"])

                # Should have content from all 3 pages
                expected_pages = {1, 2, 3}
                assert pages_found == expected_pages, f"Expected pages {expected_pages}, found {pages_found}"

                # Verify no chunks have null/empty text
                for chunk in chunks:
                    assert chunk["text"].strip(), "No chunks should have empty text"

        finally:
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)

    def test_pass_a_tool_version_tracking(self):
        """HARD GATE: Test that unstructured.io version can be tracked for manifest"""
        try:
            import importlib.metadata

            # Should be able to get version information
            version = importlib.metadata.version('unstructured')

            # Version should be available for tracking
            assert version is not None, "unstructured.io version should be available for manifest tracking"
            assert isinstance(version, str), "Version should be a string"
            assert len(version) > 0, "Version should not be empty"

            # Version should follow semantic versioning pattern (basic check)
            version_parts = version.split('.')
            assert len(version_parts) >= 2, f"Version '{version}' should have at least major.minor format"

        except ImportError:
            pytest.skip("unstructured.io not available for version checking")

    def test_pass_a_schema_validation(self):
        """HARD GATE: Test that Pass A output matches exact schema requirements"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        # Create expected schema
        expected_schema = {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "page", "section", "type"],
                "properties": {
                    "text": {"type": "string", "minLength": 1},
                    "page": {"type": ["integer", "null"], "minimum": 1},
                    "section": {"type": "string"},
                    "type": {"type": "string"}
                }
            }
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(b"mock pdf content")
            temp_pdf_path = temp_pdf.name

        with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as temp_output:
            temp_output_path = temp_output.name

        try:
            with patch('unstructured.partition.pdf.partition_pdf') as mock_partition:
                class MockElement:
                    def __init__(self, text, page_number=1, category="Text", section="default"):
                        self.text = text
                        self.metadata = type('obj', (object,), {
                            'page_number': page_number,
                            'section': section
                        })()
                        self.category = category

                mock_elements = [
                    MockElement("Valid chunk text", 1, "Text", "section1"),
                ]

                mock_partition.return_value = mock_elements

                # Setup artifacts directory
                artifacts_dir = Path(temp_output_path).parent / "artifacts"
                artifacts_dir.mkdir(exist_ok=True)

                # Copy PDF and create manifest
                import shutil
                temp_pdf_in_artifacts = artifacts_dir / "test.pdf"
                shutil.copy2(temp_pdf_path, temp_pdf_in_artifacts)

                manifest = {"job_id": "test_job", "pdf_file": "test.pdf", "completed_passes": []}
                with open(artifacts_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)

                result = process_pass_a(str(artifacts_dir))
                chunks = result.get('pass_a_output', {}).get('toc_entries', [])

                # Validate against schema (basic validation)
                assert isinstance(chunks, list), "Output should be an array"

                for chunk in chunks:
                    # Required fields
                    assert "text" in chunk and isinstance(chunk["text"], str) and len(chunk["text"]) > 0
                    assert "page" in chunk and (isinstance(chunk["page"], int) or chunk["page"] is None)
                    assert "section" in chunk and isinstance(chunk["section"], str)
                    assert "type" in chunk and isinstance(chunk["type"], str)

                    # Constraints
                    if chunk["page"] is not None:
                        assert chunk["page"] >= 1, "Page numbers should be >= 1"

        finally:
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)

    def test_pass_a_error_handling(self):
        """HARD GATE: Test that Pass A handles errors gracefully"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        # Test with non-existent PDF in manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create manifest with non-existent PDF
            manifest = {"job_id": "test_job", "pdf_file": "nonexistent.pdf", "completed_passes": []}
            with open(artifacts_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)

            with pytest.raises((FileNotFoundError, OSError)):
                process_pass_a(str(artifacts_dir))

        # Test with invalid output path
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(b"mock content")
            temp_pdf_path = temp_pdf.name

        try:
            # Test with invalid artifacts directory
            with pytest.raises((PermissionError, OSError, FileNotFoundError)):
                process_pass_a("/nonexistent/artifacts")  # Should fail due to missing directory

        finally:
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)

    def test_pass_a_performance_baseline(self):
        """HARD GATE: Test that Pass A meets performance requirements"""
        try:
            from src_common.pass_a_toc_parser import process_pass_a
        except ImportError:
            pytest.skip("Pass A module not available for testing")

        import time

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_pdf:
            temp_pdf.write(b"mock pdf content")
            temp_pdf_path = temp_pdf.name

        with tempfile.NamedTemporaryFile(mode='w', suffix=".json", delete=False) as temp_output:
            temp_output_path = temp_output.name

        try:
            with patch('unstructured.partition.pdf.partition_pdf') as mock_partition:
                # Simulate reasonable processing time
                def slow_partition(*args, **kwargs):
                    time.sleep(0.01)  # Simulate some processing time
                    class MockElement:
                        def __init__(self, text, page_number=1):
                            self.text = text
                            self.metadata = type('obj', (object,), {'page_number': page_number, 'section': None})()
                            self.category = "Text"
                    return [MockElement("Test content")]

                mock_partition.side_effect = slow_partition

                start_time = time.time()
                # Setup artifacts directory
                artifacts_dir = Path(temp_output_path).parent / "artifacts"
                artifacts_dir.mkdir(exist_ok=True)

                # Copy PDF and create manifest
                import shutil
                temp_pdf_in_artifacts = artifacts_dir / "test.pdf"
                shutil.copy2(temp_pdf_path, temp_pdf_in_artifacts)

                manifest = {"job_id": "test_job", "pdf_file": "test.pdf", "completed_passes": []}
                with open(artifacts_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)

                result = process_pass_a(str(artifacts_dir))
                chunks = result.get('pass_a_output', {}).get('toc_entries', [])
                end_time = time.time()

                processing_time = end_time - start_time

                # Should complete within reasonable time (5 seconds for test)
                assert processing_time < 5.0, f"Pass A took {processing_time:.2f}s, should be < 5s for test data"
                assert result is not None, "Should produce output"

        finally:
            if os.path.exists(temp_pdf_path):
                os.unlink(temp_pdf_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)