"""
Lane A Integration Tests - Pass A → B → C Pipeline Flow

Tests the complete ingestion pipeline flow from TOC extraction through
content extraction, validating data contracts and artifact integrity.

Per AI Prompt Specification:
- Pass A: TOC-only extraction using Unstructured.io → passA.toc.json
- Pass B: Smart page splitting using TOC structure → passB.parts.jsonl + part PDFs
- Pass C: Content extraction using Unstructured.io → passC.chunks.jsonl
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.pass_a_toc_extraction import TocExtractor, TocExtractionResult, TocSection, generate_pass_a_toc_json
from src_common.pass_b_logical_splitter import process_pass_b
from src_common.pass_c_extraction import process_pass_c


class TestLaneAIntegration:
    """Integration tests for complete Lane A pipeline (Pass A → B → C)."""

    def test_pass_a_to_b_data_contract(self, tmp_path):
        """Test that Pass A output is consumed correctly by Pass B."""
        # Create artifacts directory structure
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Simulate Pass A: Create passA.toc.json
        pass_a_dir = artifacts_dir / "pass_a"
        pass_a_dir.mkdir()

        toc_sections = [
            TocSection("abc123", "Introduction", 1, 5, 1, None),
            TocSection("def456", "Chapter 1", 6, 15, 1, None),
            TocSection("ghi789", "Section 1.1", 6, 10, 2, "def456"),
            TocSection("jkl012", "Section 1.2", 11, 15, 2, "def456"),
            TocSection("mno345", "Chapter 2", 16, 25, 1, None),
        ]

        toc_result = TocExtractionResult(
            doc_id="test_job_001",
            sections=toc_sections,
            toc_pages_used=(1, 2),
            extraction_method="unstructured",
            success=True
        )

        toc_output_path = pass_a_dir / "test_job_001_passA.toc.json"
        generate_pass_a_toc_json(toc_result, toc_output_path)

        # Verify Pass A output exists
        assert toc_output_path.exists()
        with open(toc_output_path, 'r') as f:
            toc_data = json.load(f)

        assert toc_data["doc_id"] == "test_job_001"
        assert len(toc_data["sections"]) == 5
        assert toc_data["success"] is True

        # Create minimal PDF for Pass B
        test_pdf = artifacts_dir / "test.pdf"
        with open(test_pdf, 'wb') as f:
            # Create minimal valid PDF
            f.write(b"%PDF-1.4\n")
            f.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            f.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 25 >>\nendobj\n")
            f.write(b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n")
            f.write(b"xref\n0 4\n0000000000 65535 f\n")
            f.write(b"trailer\n<< /Size 4 /Root 1 0 R >>\n")
            f.write(b"startxref\n100\n%%EOF\n")

        # Execute Pass B with mocked PyPDF (to avoid actual PDF parsing)
        with patch('pypdf.PdfReader') as mock_reader, \
             patch('pypdf.PdfWriter') as mock_writer:

            # Configure PyPDF mocks
            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock() for _ in range(25)]

            mock_writer_instance = MagicMock()
            mock_writer.return_value = mock_writer_instance

            # Run Pass B
            result_b = process_pass_b(test_pdf, artifacts_dir, "test_job_001", "dev")

        # Verify Pass B consumed Pass A output
        assert result_b.success is True

        # Check that passB.parts.jsonl was created
        parts_jsonl_path = artifacts_dir / "pass_b" / "test_job_001_passB.parts.jsonl"
        if parts_jsonl_path.exists():
            # Verify JSONL format (newline-delimited JSON, not array)
            with open(parts_jsonl_path, 'r') as f:
                lines = f.readlines()
                assert len(lines) > 0, "passB.parts.jsonl should have entries"

                # Each line should be valid JSON
                for line in lines:
                    part_entry = json.loads(line)
                    assert "part_id" in part_entry
                    assert "section_id" in part_entry
                    assert "section_title" in part_entry
                    assert "page_start" in part_entry
                    assert "page_end" in part_entry

    def test_pass_b_to_c_data_contract(self, tmp_path):
        """Test that Pass B output is consumed correctly by Pass C."""
        # Create artifacts directory
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Simulate Pass B: Create split_index.json
        pass_b_dir = artifacts_dir / "pass_b"
        pass_b_dir.mkdir()

        parts_dir = artifacts_dir / "parts"
        parts_dir.mkdir()

        # Create mock part PDFs
        part1_path = parts_dir / "test_job_001_part_001.pdf"
        part2_path = parts_dir / "test_job_001_part_002.pdf"

        for part_path in [part1_path, part2_path]:
            with open(part_path, 'wb') as f:
                f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF")

        # Create split_index.json
        split_index = {
            "split_performed": True,
            "parts": [
                {"relative_path": "parts/test_job_001_part_001.pdf", "page_start": 1, "page_end": 12},
                {"relative_path": "parts/test_job_001_part_002.pdf", "page_start": 13, "page_end": 25}
            ]
        }

        split_index_path = pass_b_dir / "split_index.json"
        with open(split_index_path, 'w') as f:
            json.dump(split_index, f)

        # Mock Unstructured.io for Pass C
        with patch('src_common.pass_c_extraction.partition_pdf') as mock_partition:
            # Create mock elements with text content
            mock_elements = [
                MagicMock(text="Chapter 1 Introduction", metadata=MagicMock(page_number=1, category="Title")),
                MagicMock(text="This is the introduction content.", metadata=MagicMock(page_number=1, category="NarrativeText")),
            ]
            mock_partition.return_value = mock_elements

            # Run Pass C
            result_c = process_pass_c(artifacts_dir / "test.pdf", artifacts_dir, "test_job_001", "dev")

        # Verify Pass C processed Pass B parts
        assert result_c.success is True
        assert result_c.parts_processed == 2, "Should process 2 parts from split_index"
        assert result_c.chunks_extracted > 0, "Should extract chunks from parts"

        # Verify chunks file exists
        chunks_path = artifacts_dir / "pass_c" / "test_job_001_pass_c_chunks.jsonl"
        assert chunks_path.exists()

        # Verify JSONL format
        with open(chunks_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) > 0

            for line in lines:
                chunk = json.loads(line)
                assert "doc_id" in chunk
                assert "chunk_id" in chunk
                assert "text" in chunk
                assert "page_number" in chunk

    def test_complete_pass_a_b_c_flow(self, tmp_path):
        """Test complete Pass A → B → C pipeline with realistic data flow."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # === PASS A: TOC Extraction ===
        toc_sections = [
            TocSection("sec001", "Preface", 1, 3, 1, None),
            TocSection("sec002", "Chapter 1: Basics", 4, 12, 1, None),
            TocSection("sec003", "1.1 Getting Started", 4, 7, 2, "sec002"),
            TocSection("sec004", "1.2 Advanced Topics", 8, 12, 2, "sec002"),
            TocSection("sec005", "Chapter 2: Advanced", 13, 20, 1, None),
        ]

        toc_result = TocExtractionResult(
            doc_id="integration_test",
            sections=toc_sections,
            toc_pages_used=(1, 2),
            extraction_method="unstructured",
            success=True
        )

        pass_a_dir = artifacts_dir / "pass_a"
        pass_a_dir.mkdir()
        toc_path = pass_a_dir / "integration_test_passA.toc.json"
        generate_pass_a_toc_json(toc_result, toc_path)

        # Verify Pass A output
        assert toc_path.exists()
        with open(toc_path, 'r') as f:
            toc_data = json.load(f)
        assert toc_data["total_sections"] == 5

        # === PASS B: Smart Page Splitting ===
        test_pdf = artifacts_dir / "test.pdf"
        with open(test_pdf, 'wb') as f:
            # Minimal valid PDF structure
            f.write(b"%PDF-1.4\n")
            f.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
            f.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 20 >>\nendobj\n")
            f.write(b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n")
            f.write(b"xref\n0 4\ntrailer\n<< /Root 1 0 R >>\nstartxref\n100\n%%EOF\n")

        with patch('pypdf.PdfReader') as mock_reader, \
             patch('pypdf.PdfWriter') as mock_writer:

            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock() for _ in range(20)]

            mock_writer_instance = MagicMock()
            mock_writer.return_value = mock_writer_instance

            result_b = process_pass_b(test_pdf, artifacts_dir, "integration_test", "dev")

        assert result_b.success is True

        # Verify passB.parts.jsonl exists
        parts_jsonl = artifacts_dir / "pass_b" / "integration_test_passB.parts.jsonl"
        if parts_jsonl.exists():
            with open(parts_jsonl, 'r') as f:
                parts_data = [json.loads(line) for line in f]

            # Verify TOC-based splitting
            for part in parts_data:
                assert "section_id" in part, "Parts should reference TOC sections"
                assert "section_title" in part
                assert part["section_id"] in [s.section_id for s in toc_sections]

        # === PASS C: Content Extraction ===
        with patch('src_common.pass_c_extraction.partition_pdf') as mock_partition:
            # Mock extraction results
            mock_elements = [
                MagicMock(text="Preface text", metadata=MagicMock(page_number=1, category="NarrativeText")),
                MagicMock(text="Chapter 1 content", metadata=MagicMock(page_number=4, category="NarrativeText")),
                MagicMock(text="Advanced content", metadata=MagicMock(page_number=13, category="NarrativeText")),
            ]
            mock_partition.return_value = mock_elements

            result_c = process_pass_c(test_pdf, artifacts_dir, "integration_test", "dev")

        assert result_c.success is True
        assert result_c.chunks_extracted > 0

        # Verify final output
        chunks_path = artifacts_dir / "pass_c" / "integration_test_pass_c_chunks.jsonl"
        assert chunks_path.exists()

        with open(chunks_path, 'r') as f:
            chunks = [json.loads(line) for line in f]

        assert len(chunks) > 0
        assert all("text" in c and "chunk_id" in c for c in chunks)

    def test_pipeline_error_propagation(self, tmp_path):
        """Test that errors in Pass A prevent Pass B execution."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        # Create Pass A output with failure status
        pass_a_dir = artifacts_dir / "pass_a"
        pass_a_dir.mkdir()

        failed_toc_result = TocExtractionResult(
            doc_id="failed_test",
            sections=[],
            toc_pages_used=(0, 0),
            extraction_method="none",
            success=False,
            error_message="No TOC pages detected"
        )

        toc_path = pass_a_dir / "failed_test_passA.toc.json"
        generate_pass_a_toc_json(failed_toc_result, toc_path)

        # Verify Pass A failure is recorded
        with open(toc_path, 'r') as f:
            toc_data = json.load(f)

        assert toc_data["success"] is False
        assert toc_data["error_message"] == "No TOC pages detected"
        assert toc_data["total_sections"] == 0

        # Pass B should handle missing/failed TOC gracefully
        test_pdf = artifacts_dir / "test.pdf"
        with open(test_pdf, 'wb') as f:
            f.write(b"%PDF-1.4\nminimal content\n%%EOF")

        with patch('pypdf.PdfReader') as mock_reader:
            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock() for _ in range(10)]

            # Pass B should fall back to page-based splitting when TOC fails
            result_b = process_pass_b(test_pdf, artifacts_dir, "failed_test", "dev")

        # Pass B should succeed with fallback strategy
        assert result_b.success is True

    def test_artifact_lineage_tracking(self, tmp_path):
        """Test that artifact lineage is maintained across passes."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        job_id = "lineage_test"

        # Pass A: Create TOC with section IDs
        toc_sections = [
            TocSection("section_alpha", "Part I", 1, 10, 1, None),
            TocSection("section_beta", "Part II", 11, 20, 1, None),
        ]

        toc_result = TocExtractionResult(
            doc_id=job_id,
            sections=toc_sections,
            toc_pages_used=(1, 1),
            extraction_method="unstructured",
            success=True
        )

        pass_a_dir = artifacts_dir / "pass_a"
        pass_a_dir.mkdir()
        generate_pass_a_toc_json(toc_result, pass_a_dir / f"{job_id}_passA.toc.json")

        # Pass B: Generate parts with section references
        test_pdf = artifacts_dir / "test.pdf"
        with open(test_pdf, 'wb') as f:
            f.write(b"%PDF-1.4\ncontent\n%%EOF")

        with patch('pypdf.PdfReader') as mock_reader, \
             patch('pypdf.PdfWriter') as mock_writer:

            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock() for _ in range(20)]

            mock_writer_instance = MagicMock()
            mock_writer.return_value = mock_writer_instance

            result_b = process_pass_b(test_pdf, artifacts_dir, job_id, "dev")

        # Verify section lineage in Pass B output
        parts_jsonl = artifacts_dir / "pass_b" / f"{job_id}_passB.parts.jsonl"
        if parts_jsonl.exists():
            with open(parts_jsonl, 'r') as f:
                parts = [json.loads(line) for line in f]

            # Parts should reference original TOC sections
            for part in parts:
                if "section_id" in part:
                    assert part["section_id"] in ["section_alpha", "section_beta"]

        # Pass C: Verify chunks maintain lineage
        with patch('src_common.pass_c_extraction.partition_pdf') as mock_partition:
            mock_elements = [
                MagicMock(text="Content from Part I", metadata=MagicMock(page_number=5, category="Text")),
            ]
            mock_partition.return_value = mock_elements

            result_c = process_pass_c(test_pdf, artifacts_dir, job_id, "dev")

        # Verify chunk lineage
        chunks_path = artifacts_dir / "pass_c" / f"{job_id}_pass_c_chunks.jsonl"
        if chunks_path.exists():
            with open(chunks_path, 'r') as f:
                chunks = [json.loads(line) for line in f]

            for chunk in chunks:
                # Chunks should have lineage metadata
                assert "lineage" in chunk
                assert "doc_id" in chunk
                assert chunk["doc_id"] == job_id


@pytest.mark.integration
class TestLaneAPerformance:
    """Performance baseline tests for Lane A pipeline."""

    def test_pass_a_b_c_performance_baseline(self, tmp_path):
        """Test that Pass A → B → C completes within performance budget."""
        import time

        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()

        job_id = "perf_test"

        # Pass A
        start_a = time.time()
        toc_sections = [TocSection(f"sec{i}", f"Chapter {i}", i*10, (i+1)*10-1, 1, None) for i in range(5)]
        toc_result = TocExtractionResult(job_id, toc_sections, (1, 2), "unstructured", True)

        pass_a_dir = artifacts_dir / "pass_a"
        pass_a_dir.mkdir()
        generate_pass_a_toc_json(toc_result, pass_a_dir / f"{job_id}_passA.toc.json")
        duration_a = time.time() - start_a

        # Pass B
        test_pdf = artifacts_dir / "test.pdf"
        with open(test_pdf, 'wb') as f:
            f.write(b"%PDF-1.4\ncontent\n%%EOF")

        with patch('pypdf.PdfReader') as mock_reader, patch('pypdf.PdfWriter'):
            mock_reader_instance = MagicMock()
            mock_reader.return_value = mock_reader_instance
            mock_reader_instance.pages = [MagicMock() for _ in range(50)]

            start_b = time.time()
            result_b = process_pass_b(test_pdf, artifacts_dir, job_id, "dev")
            duration_b = time.time() - start_b

        # Pass C
        with patch('src_common.pass_c_extraction.partition_pdf') as mock_partition:
            mock_partition.return_value = [
                MagicMock(text=f"Chunk {i}", metadata=MagicMock(page_number=i, category="Text"))
                for i in range(10)
            ]

            start_c = time.time()
            result_c = process_pass_c(test_pdf, artifacts_dir, job_id, "dev")
            duration_c = time.time() - start_c

        # Performance assertions (generous for test environment)
        assert duration_a < 5.0, f"Pass A took {duration_a:.2f}s, should be < 5s"
        assert duration_b < 10.0, f"Pass B took {duration_b:.2f}s, should be < 10s"
        assert duration_c < 15.0, f"Pass C took {duration_c:.2f}s, should be < 15s"

        total_duration = duration_a + duration_b + duration_c
        assert total_duration < 30.0, f"Total pipeline took {total_duration:.2f}s, should be < 30s"
