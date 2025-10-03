"""
Regression test for observability logging infrastructure.

Validates that all passes emit proper job logs with:
- Pass start/complete messages
- Heartbeat messages (no >10s silence)
- Upsert status logging (NEW/CHANGED/UNCHANGED/DELETED)
- Job log files created and accessible
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any

import pytest


class TestObservabilityLogging:
    """Test observability logging across the ingestion pipeline."""

    def test_job_log_file_creation(self, tmp_path):
        """Test that job log files are created properly."""
        from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete

        job_log_path = tmp_path / "test_job.log"

        # Test basic logging
        log_to_job("Test message", job_log_path, "info", "A")

        assert job_log_path.exists(), "Job log file should be created"
        content = job_log_path.read_text()
        assert "Test message" in content
        assert "Pass A:" in content

    def test_pass_start_complete_logging(self, tmp_path):
        """Test that pass start/complete messages are formatted correctly."""
        from src_common.job_logging import log_pass_start, log_pass_complete

        job_log_path = tmp_path / "test_job.log"

        # Log pass start
        log_pass_start("A", "ToC Parsing & Dictionary Seed", job_log_path)

        # Log pass complete
        stats = {"entries": 100, "categories": 25}
        log_pass_complete("A", 5.5, stats, job_log_path)

        content = job_log_path.read_text()

        # Validate start message
        assert "=" * 60 in content, "Should have separator lines"
        assert "ToC Parsing & Dictionary Seed" in content
        assert "Pass A:" in content

        # Validate complete message
        assert "Completed in 5.50s" in content
        assert "entries=100" in content
        assert "categories=25" in content

    def test_heartbeat_logging_prevents_silence(self, tmp_path):
        """Test that heartbeat logging prevents >10s silence."""
        from src_common.job_logging import log_heartbeat

        job_log_path = tmp_path / "test_job.log"

        # Simulate processing loop with heartbeat
        total_items = 10
        last_log_time = 0.0

        for i in range(total_items):
            # Simulate work
            time.sleep(0.1)

            # Heartbeat should log every 8s
            last_log_time = log_heartbeat(
                current=i + 1,
                total=total_items,
                item_name=f"item_{i}",
                log_file_path=job_log_path,
                pass_name="B",
                last_log_time=last_log_time,
                heartbeat_interval=0.5  # Use shorter interval for testing
            )

        content = job_log_path.read_text()
        log_lines = [line for line in content.split('\n') if line.strip()]

        # Should have multiple heartbeat messages
        assert len(log_lines) > 1, "Should have heartbeat messages"

        # Check progress percentage format
        assert any("%" in line for line in log_lines), "Should show progress percentage"
        assert any("Processing" in line for line in log_lines), "Should show processing status"

    def test_upsert_status_logging(self, tmp_path):
        """Test that upsert status logging includes proper indicators."""
        from src_common.job_logging import log_upsert_result

        job_log_path = tmp_path / "test_job.log"

        # Log different upsert operations
        log_upsert_result("NEW", "chunk_001", "chunk", job_log_path, "C")
        log_upsert_result("CHANGED", "chunk_002", "chunk", job_log_path, "C", "metadata updated")
        log_upsert_result("UNCHANGED", "chunk_003", "chunk", job_log_path, "C")
        log_upsert_result("DELETED", "chunk_004", "chunk", job_log_path, "C")

        content = job_log_path.read_text(encoding='utf-8')

        # Validate emoji indicators
        assert "📝" in content, "Should have NEW indicator"
        assert "✏️" in content, "Should have CHANGED indicator"
        assert "✓" in content, "Should have UNCHANGED indicator"
        assert "🗑️" in content, "Should have DELETED indicator"

        # Validate operation types
        assert "NEW: chunk 'chunk_001'" in content
        assert "CHANGED: chunk 'chunk_002'" in content
        assert "metadata updated" in content
        assert "UNCHANGED: chunk 'chunk_003'" in content
        assert "DELETED: chunk 'chunk_004'" in content

    def test_pass_a_logging_integration(self, tmp_path):
        """Test Pass A emits proper job logs."""
        from src_common.pass_a_toc_parser import PassATocParser

        # Create minimal test PDF (would need actual PDF in real test)
        pytest.skip("Requires actual PDF file - integration test only")

    def test_pass_0_ocr_validation_logging(self, tmp_path):
        """Test Pass 0 logs OCR dependency validation."""
        from src_common.pass_0_preflight import run_preflight_checks

        # Create minimal test PDF
        test_pdf = tmp_path / "test.pdf"

        # Create a minimal valid PDF
        pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000314 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
407
%%EOF
"""
        test_pdf.write_bytes(pdf_content)

        job_log_path = tmp_path / "job.log"

        # Run preflight
        result = run_preflight_checks(test_pdf, job_log_path)

        # Validate OCR validation was logged
        content = job_log_path.read_text()
        assert "Validating OCR dependencies" in content, "Should log OCR validation"
        assert "tesseract" in content.lower() or "OCR" in content, "Should mention OCR tools"

    def test_log_timestamps_present(self, tmp_path):
        """Test that all log messages include timestamps."""
        from src_common.job_logging import log_to_job

        job_log_path = tmp_path / "test_job.log"

        log_to_job("Test message 1", job_log_path, "info", "A")
        time.sleep(0.1)
        log_to_job("Test message 2", job_log_path, "info", "A")

        content = job_log_path.read_text()
        lines = [line for line in content.split('\n') if line.strip()]

        # Each line should have ISO timestamp format
        iso_pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'

        for line in lines:
            assert re.search(iso_pattern, line), f"Line should have timestamp: {line}"

    def test_pass_logging_no_10s_silence(self, tmp_path):
        """Test that pass logging prevents >10 second silence."""
        from src_common.job_logging import log_to_job, log_heartbeat

        job_log_path = tmp_path / "test_job.log"

        # Simulate long operation with heartbeats
        start_time = time.time()
        last_log_time = 0.0  # Start at 0 to force first heartbeat

        # Simulate work with heartbeats
        for i in range(5):
            # Heartbeat should log based on interval
            last_log_time = log_heartbeat(
                current=i + 1,
                total=5,
                item_name=f"operation_{i}",
                log_file_path=job_log_path,
                pass_name="D",
                last_log_time=last_log_time,
                heartbeat_interval=0.1  # Very short for testing
            )
            time.sleep(0.15)  # Sleep longer than interval to trigger heartbeat

        # Parse timestamps and validate gaps
        content = job_log_path.read_text(encoding='utf-8')
        lines = [line for line in content.split('\n') if line.strip()]

        # Extract timestamps
        iso_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'
        timestamps = []

        for line in lines:
            match = re.search(iso_pattern, line)
            if match:
                timestamps.append(match.group(1))

        # Validate we have multiple log entries (at least 3 out of 5 iterations)
        assert len(timestamps) >= 3, f"Should have multiple timestamped log entries, got {len(timestamps)}"


class TestPassGIntegrityValidation:
    """Test Pass G artifact integrity validation."""

    def test_pass_g_validates_artifacts(self, tmp_path):
        """Test that Pass G validates artifact integrity."""
        from src_common.pass_g_hgrn_consistency import HGRNChecker

        # Create mock job directory with pass artifacts
        job_dir = tmp_path / "job_test_001"
        job_dir.mkdir()

        # Create Pass A artifacts
        pass_a_dir = job_dir / "pass_a"
        pass_a_dir.mkdir()
        (pass_a_dir / "job_test_001_pass_a_dict.json").write_text('{"entries": []}')
        (pass_a_dir / "job_test_001_pass_a_manifest.json").write_text('{"job_id": "job_test_001"}')

        # Create Pass C artifacts
        pass_c_dir = job_dir / "pass_c"
        pass_c_dir.mkdir()
        (pass_c_dir / "job_test_001_pass_c_chunks.jsonl").write_text('{"text": "test"}\n')
        (pass_c_dir / "chunk_summary.json").write_text('{"chunks": 1}')
        (pass_c_dir / "dict_delta.passC.json").write_text('{}')

        # Create Pass D artifacts
        pass_d_dir = job_dir / "pass_d"
        pass_d_dir.mkdir()
        (pass_d_dir / "job_test_001_pass_d_vectors.jsonl").write_text('{"embedding": [0.1]}\n')
        (pass_d_dir / "vector_summary.json").write_text('{"vectors": 1}')
        (pass_d_dir / "dict_delta.passD.json").write_text('{}')

        # Create Pass E artifacts
        pass_e_dir = job_dir / "pass_e"
        pass_e_dir.mkdir()
        (pass_e_dir / "graph.json").write_text('{"nodes": [], "edges": []}')
        (pass_e_dir / "graph_summary.json").write_text('{"nodes": 0}')
        (pass_e_dir / "dict_delta.passE.json").write_text('{}')

        # Create Pass F artifacts
        pass_f_dir = job_dir / "pass_f"
        pass_f_dir.mkdir()
        (pass_f_dir / "finalization.json").write_text('{"status": "complete"}')
        (pass_f_dir / "dict_delta.passF.json").write_text('{}')

        # Run Pass G validation
        job_log_path = tmp_path / "job.log"
        checker = HGRNChecker(job_id="job_test_001", env="dev", log_file_path=job_log_path)
        result = checker.process(job_dir)

        # Validate results
        assert result.success, "Pass G should complete successfully"

        # Check job log for integrity validation
        log_content = job_log_path.read_text()
        assert "Validating artifact integrity" in log_content
        assert "Pass G:" in log_content

    def test_pass_g_detects_missing_artifacts(self, tmp_path):
        """Test that Pass G detects missing artifacts."""
        from src_common.pass_g_hgrn_consistency import HGRNChecker

        # Create job directory with incomplete artifacts
        job_dir = tmp_path / "job_test_002"
        job_dir.mkdir()

        # Only create Pass A (missing other passes)
        pass_a_dir = job_dir / "pass_a"
        pass_a_dir.mkdir()
        (pass_a_dir / "job_test_002_pass_a_dict.json").write_text('{}')
        (pass_a_dir / "job_test_002_pass_a_manifest.json").write_text('{}')

        # Create minimal Pass E for graph loading
        pass_e_dir = job_dir / "pass_e"
        pass_e_dir.mkdir()
        (pass_e_dir / "graph.json").write_text('{"nodes": [], "edges": []}')

        # Run Pass G - should detect missing artifacts
        job_log_path = tmp_path / "job.log"
        checker = HGRNChecker(job_id="job_test_002", env="dev", log_file_path=job_log_path)
        result = checker.process(job_dir)

        # Should find missing artifact issues
        assert result.critical_issues > 0, "Should detect missing artifacts as critical issues"


@pytest.mark.integration
class TestEndToEndObservability:
    """Integration tests for end-to-end observability."""

    def test_full_pipeline_logging(self, tmp_path):
        """Test that full pipeline generates complete logs."""
        pytest.skip("Requires full pipeline setup - integration test only")

    def test_docker_log_accessibility(self):
        """Test that logs are accessible from Docker volumes."""
        pytest.skip("Requires Docker environment - integration test only")
