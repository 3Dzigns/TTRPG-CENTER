from src_common.pass_c_extraction import PassCResult


def test_pass_c_result_defaults_chunks_loaded_to_zero():
    result = PassCResult(
        job_id="job-123",
        parts_processed=1,
        chunks_extracted=4,
        chunks_written=4,
        used_unstructured=True,
        fallback_used=False,
        processing_time_ms=1200,
        artifacts=["chunks.jsonl"],
    )

    assert hasattr(result, "chunks_loaded")
    assert result.chunks_loaded == 0


def test_pass_c_result_can_record_loaded_chunks():
    result = PassCResult(
        job_id="job-456",
        parts_processed=1,
        chunks_extracted=7,
        chunks_written=7,
        used_unstructured=False,
        fallback_used=True,
        processing_time_ms=980,
        artifacts=["chunks.jsonl"],
        chunks_loaded=7,
    )

    assert result.chunks_loaded == 7
