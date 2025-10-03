"""
Regression tests for TOC heuristics parser.

Tests compliance with AI prompt spec:
- Pattern matching for various TOC formats
- Hierarchical structure detection
- Section ID generation (sha1-based)
- End page inference
- Parent-child relationships
"""

import pytest


class TestTocLinePatterns:
    """Test TOC line pattern matching."""

    def test_decimal_numbering_pattern(self):
        """Test decimal numbering pattern (1.2.3 Title ... 45)."""
        from src_common.toc_heuristics import TocHeuristicParser

        parser = TocHeuristicParser()

        # Test simple decimal numbering
        line = "1.2 Character Creation ........ 15"
        toc_line = parser._parse_line(line)

        assert toc_line is not None
        assert toc_line.title == "Character Creation"
        assert toc_line.page_number == 15
        assert toc_line.numbering == "1.2"

    def test_roman_numeral_pattern(self):
        """Test Roman numeral pattern (I. Title ... 45)."""
        from src_common.toc_heuristics import TocHeuristicParser

        parser = TocHeuristicParser()

        line = "I. Introduction ........... 5"
        toc_line = parser._parse_line(line)

        assert toc_line is not None
        assert toc_line.title == "Introduction"
        assert toc_line.page_number == 5
        assert toc_line.numbering == "I"

    def test_alphabetic_pattern(self):
        """Test alphabetic pattern (A. Title ... 45)."""
        from src_common.toc_heuristics import TocHeuristicParser

        parser = TocHeuristicParser()

        line = "A. Appendix .............. 100"
        toc_line = parser._parse_line(line)

        assert toc_line is not None
        assert toc_line.title == "Appendix"
        assert toc_line.page_number == 100
        assert toc_line.numbering == "A"

    def test_simple_pattern_with_dots(self):
        """Test simple pattern with dot leaders."""
        from src_common.toc_heuristics import TocHeuristicParser

        parser = TocHeuristicParser()

        line = "Equipment ................. 25"
        toc_line = parser._parse_line(line)

        assert toc_line is not None
        assert toc_line.title == "Equipment"
        assert toc_line.page_number == 25
        assert toc_line.numbering is None

    def test_simple_pattern_with_spaces(self):
        """Test simple pattern with space leaders."""
        from src_common.toc_heuristics import TocHeuristicParser

        parser = TocHeuristicParser()

        line = "Chapter 3          50"
        toc_line = parser._parse_line(line)

        assert toc_line is not None
        assert toc_line.title == "Chapter 3"
        assert toc_line.page_number == 50


class TestHierarchyDetection:
    """Test hierarchical structure detection."""

    def test_decimal_hierarchy_levels(self):
        """Test hierarchy levels from decimal numbering."""
        from src_common.toc_heuristics import TocHeuristicParser, TocLine

        parser = TocHeuristicParser()

        lines = [
            TocLine("1 Chapter One .... 1", "Chapter One", 1, "1"),
            TocLine("1.1 Section 1.1 .. 5", "Section 1.1", 5, "1.1"),
            TocLine("1.1.1 Subsection . 8", "Subsection", 8, "1.1.1"),
            TocLine("2 Chapter Two .... 10", "Chapter Two", 10, "2"),
        ]

        lines = parser._determine_hierarchy(lines)

        assert lines[0].indentation_level == 1  # "1"
        assert lines[1].indentation_level == 2  # "1.1"
        assert lines[2].indentation_level == 3  # "1.1.1"
        assert lines[3].indentation_level == 1  # "2"

    def test_roman_numeral_hierarchy(self):
        """Test Roman numeral hierarchy."""
        from src_common.toc_heuristics import TocHeuristicParser, TocLine

        parser = TocHeuristicParser()

        lines = [
            TocLine("I. Part One .... 1", "Part One", 1, "I"),
            TocLine("II. Part Two ... 50", "Part Two", 50, "II"),
        ]

        lines = parser._determine_hierarchy(lines)

        assert lines[0].indentation_level == 1
        assert lines[1].indentation_level == 1


class TestEndPageInference:
    """Test end page inference logic."""

    def test_end_page_inference(self):
        """Test end page is inferred from next section's start."""
        from src_common.toc_heuristics import TocHeuristicParser, TocLine

        parser = TocHeuristicParser()

        lines = [
            TocLine("Chapter 1", "Chapter 1", 5, None),
            TocLine("Chapter 2", "Chapter 2", 20, None),
            TocLine("Chapter 3", "Chapter 3", 35, None),
        ]

        lines = parser._infer_end_pages(lines)

        assert lines[0].end_page == 19  # 20 - 1
        assert lines[1].end_page == 34  # 35 - 1
        assert lines[2].end_page == 35  # Last section, same as start


class TestSectionCreation:
    """Test TocSection creation with stable IDs."""

    def test_section_id_generation(self):
        """Test section ID is stable (sha1-based)."""
        from src_common.toc_heuristics import TocHeuristicParser, TocLine

        parser = TocHeuristicParser()

        line = TocLine("Chapter 1", "Chapter 1", 5, None)
        line.end_page = 19
        line.indentation_level = 1

        sections = parser._create_sections([line])

        assert len(sections) == 1
        assert len(sections[0].section_id) == 12  # SHA1 truncated to 12 chars
        assert sections[0].title == "Chapter 1"
        assert sections[0].start_page == 5
        assert sections[0].end_page == 19

        # Test stability - same input should produce same ID
        sections2 = parser._create_sections([line])
        assert sections[0].section_id == sections2[0].section_id


class TestParentChildRelationships:
    """Test parent-child hierarchy establishment."""

    def test_establish_hierarchy(self):
        """Test parent-child relationships are established correctly."""
        from src_common.toc_heuristics import TocHeuristicParser
        from src_common.pass_a_toc_extraction import TocSection

        parser = TocHeuristicParser()

        sections = [
            TocSection("A", "Chapter 1", 1, 20, 1),
            TocSection("B", "Section 1.1", 5, 10, 2),
            TocSection("C", "Section 1.2", 11, 19, 2),
            TocSection("D", "Chapter 2", 20, 30, 1),
        ]

        sections = parser._establish_hierarchy(sections)

        assert sections[0].parent_id is None  # Level 1, no parent
        assert sections[1].parent_id == "A"   # Level 2, parent is Chapter 1
        assert sections[2].parent_id == "A"   # Level 2, parent is Chapter 1
        assert sections[3].parent_id is None  # Level 1, no parent


class TestFullParsing:
    """Test complete TOC parsing workflow."""

    def test_parse_mixed_toc(self):
        """Test parsing TOC with mixed numbering styles."""
        from src_common.toc_heuristics import parse_toc_with_heuristics

        toc_lines = [
            "1. Introduction .............. 1",
            "2. Character Creation ........ 5",
            "2.1 Races .................... 7",
            "2.2 Classes .................. 15",
            "3. Equipment ................. 25",
            "A. Appendix A ................ 100",
        ]

        sections = parse_toc_with_heuristics(toc_lines)

        # Should parse all 6 sections
        assert len(sections) == 6

        # Check first section
        assert sections[0].title == "Introduction"
        assert sections[0].start_page == 1
        assert sections[0].level == 1

        # Check hierarchical section
        assert sections[2].title == "Races"
        assert sections[2].start_page == 7
        assert sections[2].level == 2
        assert sections[2].parent_id == sections[1].section_id  # Parent is "Character Creation"

    def test_parse_simple_toc(self):
        """Test parsing simple TOC without numbering."""
        from src_common.toc_heuristics import parse_toc_with_heuristics

        toc_lines = [
            "Chapter One .............. 1",
            "Chapter Two .............. 20",
            "Chapter Three ............ 40",
        ]

        sections = parse_toc_with_heuristics(toc_lines)

        assert len(sections) == 3
        assert sections[0].title == "Chapter One"
        assert sections[0].end_page == 19  # Inferred from next section
        assert sections[1].end_page == 39
        assert sections[2].end_page == 40  # Last section

    def test_parse_empty_lines(self):
        """Test parsing handles empty/invalid lines."""
        from src_common.toc_heuristics import parse_toc_with_heuristics

        toc_lines = [
            "",
            "Chapter 1 .............. 1",
            "   ",
            "Chapter 2 .............. 20",
            "X",  # Too short
        ]

        sections = parse_toc_with_heuristics(toc_lines)

        # Should only parse the 2 valid chapters
        assert len(sections) == 2
        assert sections[0].title == "Chapter 1"
        assert sections[1].title == "Chapter 2"
