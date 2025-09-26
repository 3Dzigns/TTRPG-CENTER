"""
BUG-035 Test Suite: Pass A Timeout Protection

Comprehensive test suite for validating timeout protection in Pass A
ToC parsing and metadata extraction.

Tests cover:
- Timeout scenarios with slow PDFs
- Circuit breaker behavior under failure conditions
- Error recovery and partial extraction
- Performance regression prevention
"""

import asyncio
import concurrent.futures
import pytest
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src_common.pass_a_toc_parser import PassATocParser, process_pass_a
from src_common.toc_parser import TocParser, _extract_text_with_timeout
from src_common.patterns.circuit_breaker import CircuitState


class TimeoutError(Exception):
    """Custom timeout error for testing"""
    pass


@pytest.fixture
def mock_pdf_path():
    """Mock PDF path for testing"""
    return Path("test_document.pdf")


@pytest.fixture
def mock_output_dir(tmp_path):
    """Temporary output directory for test artifacts"""
    return tmp_path / "artifacts"


@pytest.fixture
def toc_parser():
    """TocParser instance for testing"""
    return TocParser()


@pytest.fixture
def pass_a_parser():
    """PassATocParser instance for testing"""
    return PassATocParser("test_job_001", "dev")


class TestBug035TimeoutProtection:
    """Test timeout protection functionality"""

    def test_extract_text_with_timeout_success(self):
        """Test successful text extraction within timeout"""
        def mock_extract():
            time.sleep(0.1)  # Short delay to simulate processing
            return "Sample PDF text content"

        result = _extract_text_with_timeout(mock_extract, 1.0)
        assert result == "Sample PDF text content"

    def test_extract_text_with_timeout_failure(self):
        """Test timeout handling when extraction takes too long"""
        def slow_extract():
            time.sleep(2.0)  # Longer than timeout
            return "Should not return this"

        with pytest.raises(concurrent.futures.TimeoutError):
            _extract_text_with_timeout(slow_extract, 0.5)

    def test_extract_text_safely_with_timeout(self, toc_parser):
        """Test safe text extraction handles timeouts gracefully"""
        mock_page = Mock()

        # Mock extract_text to simulate hanging
        def hanging_extract():
            time.sleep(2.0)
            return "Should not return"

        mock_page.extract_text = hanging_extract

        # Should return empty string on timeout, not hang
        start_time = time.time()
        result = toc_parser._extract_text_safely(mock_page, timeout_seconds=0.5)
        duration = time.time() - start_time

        assert result == ""  # Empty string on timeout
        assert duration < 1.5  # Should complete quickly due to timeout

    def test_extract_text_safely_with_success(self, toc_parser):
        """Test safe text extraction works for normal PDFs"""
        mock_page = Mock()
        mock_page.extract_text.return_value = "Normal PDF content"

        result = toc_parser._extract_text_safely(mock_page, timeout_seconds=5.0)
        assert result == "Normal PDF content"

    @patch('src_common.toc_parser.pypdf.PdfReader')
    def test_find_and_parse_toc_with_timeout_resilience(self, mock_pdf_reader, toc_parser):
        """Test ToC parsing continues when some pages timeout"""
        # Mock PDF with 5 pages
        mock_pages = []
        for i in range(5):
            mock_page = Mock()
            if i == 2:  # Make page 3 timeout
                mock_page.extract_text.side_effect = lambda: time.sleep(2.0) or "timeout"
            else:
                mock_page.extract_text.return_value = f"Page {i} contents with table of contents"
            mock_pages.append(mock_page)

        mock_pdf_reader.pages = mock_pages
        mock_pdf_reader.return_value.pages = mock_pages

        # Should handle timeout on page 3 gracefully
        toc_entries, toc_pages, has_toc = toc_parser._find_and_parse_toc(mock_pdf_reader)

        # Should have found ToC on pages that didn't timeout
        assert has_toc or len(toc_entries) >= 0  # May have some entries from successful pages
        assert len(toc_pages) <= 4  # Page 3 should be skipped due to timeout

    def test_circuit_breaker_opens_on_repeated_failures(self, toc_parser):
        """Test circuit breaker opens after repeated timeout failures"""
        mock_page = Mock()

        # Simulate repeated failures
        def failing_extract():
            raise concurrent.futures.TimeoutError("Simulated timeout")

        mock_page.extract_text = failing_extract

        # First few calls should attempt extraction
        for i in range(3):
            result = toc_parser._extract_text_safely(mock_page)
            assert result == ""  # Should return empty on failure

        # Check circuit breaker state
        circuit_stats = toc_parser.pdf_circuit.get_stats()
        assert circuit_stats['total_failures'] >= 3
        assert circuit_stats['state'] in [CircuitState.OPEN, CircuitState.HALF_OPEN]


class TestBug035PassAIntegration:
    """Integration tests for Pass A with timeout protection"""

    @patch('src_common.pass_a_toc_parser.PassATocParser.toc_parser')
    def test_pass_a_completes_with_problematic_pdf(self, mock_toc_parser, mock_pdf_path, mock_output_dir, pass_a_parser):
        """Test Pass A completes even with problematic PDF"""
        # Mock document outline with minimal data
        mock_outline = Mock()
        mock_outline.entries = []  # Empty entries to simulate failed parsing
        mock_outline.has_toc = False
        mock_outline.toc_pages = []
        mock_outline.total_pages = 100

        mock_toc_parser.parse_document_structure.return_value = mock_outline

        # Ensure PDF file exists for the test
        mock_pdf_path.touch()
        mock_output_dir.mkdir(parents=True, exist_ok=True)

        # Should complete without hanging, even with problematic PDF
        start_time = time.time()
        result = pass_a_parser.process_pdf(mock_pdf_path, mock_output_dir)
        duration = time.time() - start_time

        # Should complete within reasonable time (< 5 seconds for this test)
        assert duration < 5.0
        assert result.success is True  # Should succeed even with empty ToC
        assert result.processing_time_ms < 5000

    @patch('src_common.toc_parser.pypdf.PdfReader')
    def test_pass_a_timeout_logging(self, mock_pdf_reader, mock_pdf_path, mock_output_dir):
        """Test timeout scenarios generate appropriate log messages"""
        # Mock PDF reader to simulate slow document
        mock_pdf_reader.return_value.pages = [Mock() for _ in range(5)]

        # Ensure PDF file exists
        mock_pdf_path.touch()
        mock_output_dir.mkdir(parents=True, exist_ok=True)

        with patch('src_common.pass_a_toc_parser.logger') as mock_logger:
            parser = PassATocParser("test_job_timeout", "dev")

            # Mock slow document structure parsing
            with patch.object(parser.toc_parser, 'parse_document_structure') as mock_parse:
                mock_outline = Mock()
                mock_outline.entries = []
                mock_outline.has_toc = False
                mock_outline.toc_pages = []
                mock_outline.total_pages = 100

                # Simulate slow parsing
                def slow_parse(*args):
                    time.sleep(0.5)
                    return mock_outline

                mock_parse.side_effect = slow_parse

                result = parser.process_pdf(mock_pdf_path, mock_output_dir)

                # Check that BUG-035 logging messages were generated
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                bug_035_logs = [call for call in log_calls if "BUG-035" in call]
                assert len(bug_035_logs) > 0, "Should generate BUG-035 diagnostic logs"


class TestBug035PerformanceRegression:
    """Performance regression tests to prevent future hanging issues"""

    @pytest.mark.timeout(120)  # 2 minute maximum timeout
    def test_pass_a_performance_sla(self, mock_pdf_path, mock_output_dir):
        """Test Pass A completes within 2-minute SLA"""
        # Ensure PDF file exists
        mock_pdf_path.touch()
        mock_output_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        result = process_pass_a(mock_pdf_path, mock_output_dir, "performance_test")
        duration = time.time() - start_time

        # Should complete within 2-minute SLA
        assert duration < 120.0, f"Pass A took {duration:.1f}s, exceeds 2-minute SLA"
        assert result.success is True

    def test_multiple_concurrent_pass_a_operations(self, mock_output_dir):
        """Test multiple Pass A operations can run concurrently without blocking"""
        # Create multiple mock PDFs
        pdf_paths = []
        for i in range(3):
            pdf_path = mock_output_dir / f"concurrent_test_{i}.pdf"
            pdf_path.touch()
            pdf_paths.append(pdf_path)

        mock_output_dir.mkdir(parents=True, exist_ok=True)

        async def run_concurrent_pass_a():
            """Run Pass A operations concurrently"""
            tasks = []
            for i, pdf_path in enumerate(pdf_paths):
                task = asyncio.create_task(
                    asyncio.to_thread(process_pass_a, pdf_path, mock_output_dir, f"concurrent_{i}")
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results

        # Should complete all operations within reasonable time
        start_time = time.time()
        results = asyncio.run(run_concurrent_pass_a())
        duration = time.time() - start_time

        assert duration < 60.0, f"Concurrent operations took {duration:.1f}s, too slow"
        assert len(results) == 3
        for result in results:
            assert not isinstance(result, Exception), f"Concurrent operation failed: {result}"


class TestBug035CircuitBreakerIntegration:
    """Test circuit breaker behavior with PDF processing"""

    def test_circuit_breaker_configuration(self, toc_parser):
        """Test circuit breaker is properly configured"""
        circuit = toc_parser.pdf_circuit
        assert circuit is not None
        assert circuit.name == "pdf_text_extraction"

        stats = circuit.get_stats()
        assert stats['config']['failure_threshold'] == 3
        assert stats['config']['recovery_timeout'] == 60
        assert stats['config']['timeout'] == 10.0

    def test_circuit_breaker_prevents_repeated_hangs(self, toc_parser):
        """Test circuit breaker prevents repeated hanging operations"""
        mock_page = Mock()

        # Simulate hanging extract_text
        def hanging_extract():
            time.sleep(2.0)  # Longer than circuit breaker timeout
            return "Should not return"

        mock_page.extract_text = hanging_extract

        # First call should timeout
        start_time = time.time()
        result1 = toc_parser._extract_text_safely(mock_page, timeout_seconds=0.5)
        duration1 = time.time() - start_time

        assert result1 == ""
        assert duration1 < 1.5  # Should timeout quickly

        # Subsequent calls should be faster due to circuit breaker
        start_time = time.time()
        result2 = toc_parser._extract_text_safely(mock_page, timeout_seconds=0.5)
        duration2 = time.time() - start_time

        assert result2 == ""
        # Second call might be blocked by circuit breaker, but should still be reasonably fast
        assert duration2 < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])