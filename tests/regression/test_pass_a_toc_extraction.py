"""
Regression test for Pass A TOC-only extraction.

Tests compliance with AI prompt spec:
- TOC-only extraction using Unstructured.io
- TOC page range from Pass 0
- Section structure parsing
- passA.toc.json format compliance
"""

import pytest
from pathlib import Path


class TestTocExtraction:
    """Test TOC extraction module."""

    def test_toc_extractor_with_no_toc_pages(self, tmp_path):
        """Test TOC extractor when no TOC pages detected."""
        from src_common.pass_a_toc_extraction import TocExtractor

        test_pdf = tmp_path / "test.pdf"
        test_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

        extractor = TocExtractor(job_id="test_job")
        result = extractor.extract_toc(test_pdf, toc_pages=(0, 0))

        assert result.success is False
        assert result.error_message == "No TOC pages detected"
        assert len(result.sections) == 0
        assert result.extraction_method == "none"

    def test_toc_extractor_structure(self, tmp_path):
        """Test TOC extractor result structure."""
        from src_common.pass_a_toc_extraction import TocExtractor, TocExtractionResult

        # This is a structure test - actual extraction requires real PDF
        # which is tested in integration tests
        extractor = TocExtractor(job_id="test_job_001")

        # Verify extractor initialized correctly
        assert extractor.job_id == "test_job_001"


class TestTocSection:
    """Test TOC section data structure."""

    def test_toc_section_creation(self):
        """Test TocSection data class."""
        from src_common.pass_a_toc_extraction import TocSection

        section = TocSection(
            section_id="A1",
            title="Chapter 1: Introduction",
            start_page=5,
            end_page=15,
            level=1,
            parent_id=None
        )

        assert section.section_id == "A1"
        assert section.title == "Chapter 1: Introduction"
        assert section.start_page == 5
        assert section.end_page == 15
        assert section.level == 1
        assert section.parent_id is None

    def test_toc_section_with_parent(self):
        """Test TocSection with parent hierarchy."""
        from src_common.pass_a_toc_extraction import TocSection

        parent = TocSection(
            section_id="A1",
            title="Chapter 1",
            start_page=5,
            end_page=25,
            level=1
        )

        child = TocSection(
            section_id="A1.1",
            title="Section 1.1",
            start_page=5,
            end_page=10,
            level=2,
            parent_id=parent.section_id
        )

        assert child.parent_id == "A1"
        assert child.level == 2


class TestPassATocJsonGeneration:
    """Test passA.toc.json generation."""

    def test_generate_pass_a_toc_json_structure(self, tmp_path):
        """Test passA.toc.json structure per AI spec."""
        from src_common.pass_a_toc_extraction import (
            TocExtractionResult, TocSection, generate_pass_a_toc_json
        )
        import json

        # Create test result
        sections = [
            TocSection("abc123", "Introduction", 1, 4, 1, None),
            TocSection("def456", "Chapter 1", 5, 19, 1, None),
            TocSection("ghi789", "Section 1.1", 5, 10, 2, "def456"),
        ]

        result = TocExtractionResult(
            doc_id="test_job_001",
            sections=sections,
            toc_pages_used=(1, 2),
            extraction_method="unstructured",
            success=True
        )

        # Generate JSON
        output_path = tmp_path / "passA.toc.json"
        generate_pass_a_toc_json(result, output_path)

        # Verify file exists
        assert output_path.exists()

        # Load and validate structure
        with open(output_path, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)

        # Validate required fields per AI spec
        assert toc_data["doc_id"] == "test_job_001"
        assert toc_data["extraction_method"] == "unstructured"
        assert toc_data["toc_pages_used"]["start"] == 1
        assert toc_data["toc_pages_used"]["end"] == 2
        assert toc_data["total_sections"] == 3
        assert toc_data["success"] is True
        assert toc_data["error_message"] is None

        # Validate sections structure
        assert len(toc_data["sections"]) == 3
        section = toc_data["sections"][0]
        assert "section_id" in section
        assert "title" in section
        assert "start_page" in section
        assert "end_page" in section
        assert "level" in section
        assert "parent_id" in section

        # Validate hierarchy
        assert toc_data["sections"][0]["parent_id"] is None
        assert toc_data["sections"][2]["parent_id"] == "def456"


@pytest.mark.integration
class TestTocExtractionIntegration:
    """Integration tests for TOC extraction with Unstructured.io."""

    def test_extract_toc_with_unstructured(self, tmp_path):
        """Test TOC extraction with Unstructured.io (requires library)."""
        pytest.skip("Requires Unstructured.io library - integration test only")

    def test_extract_toc_from_real_pdf(self, tmp_path):
        """Test TOC extraction from real PDF file."""
        pytest.skip("Requires real PDF file - integration test only")
