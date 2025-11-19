from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "ingestion"))

from ingestion.pipeline_state import PipelineState
from ingestion import checkpoint_wrapper


def test_mark_pass_completed_and_loaded(tmp_path):
    state = PipelineState(state_dir=tmp_path)
    document_id = "doc123"

    state.mark_pass_started(document_id, "pass_a")
    state.mark_pass_completed(document_id, "pass_a", metadata={"chunks": 3})

    loaded = state.load_state(document_id)
    assert loaded["passes_completed"][0]["pass"] == "pass_a"
    assert loaded["passes_completed"][0]["metadata"]["chunks"] == 3
    assert loaded["status"] == "in_progress"


def test_mark_pass_failed_sets_status(tmp_path):
    state = PipelineState(state_dir=tmp_path)
    document_id = "doc123"

    state.mark_pass_started(document_id, "pass_a")
    state.mark_pass_failed(document_id, "pass_a", error="boom")
    loaded = state.load_state(document_id)

    assert loaded["status"] == "failed"
    assert loaded["passes_completed"][0]["status"] == "failed"
    assert state.can_resume(document_id)


def test_get_resume_point_respects_pass_order(tmp_path):
    state = PipelineState(state_dir=tmp_path, pass_order=["pass_a", "pass_b", "pass_c"])
    document_id = "doc123"

    state.mark_pass_started(document_id, "pass_a")
    state.mark_pass_completed(document_id, "pass_a")

    assert state.can_resume(document_id)
    assert state.get_resume_point(document_id) == "pass_b"

    state.mark_pass_started(document_id, "pass_b")
    state.mark_pass_completed(document_id, "pass_b")
    assert state.get_resume_point(document_id) == "pass_c"


def test_clear_state_removes_file(tmp_path):
    state = PipelineState(state_dir=tmp_path)
    document_id = "doc123"

    state.mark_pass_started(document_id, "pass_a")
    state.mark_pass_completed(document_id, "pass_a")
    state_file = tmp_path / f"{document_id}_state.json"
    assert state_file.exists()

    state.clear_state(document_id)
    assert not state_file.exists()


def test_with_checkpoint_skips_completed(tmp_path, monkeypatch):
    state = PipelineState(state_dir=tmp_path)

    def state_factory():
        return state

    monkeypatch.setattr(checkpoint_wrapper, "PipelineState", state_factory)

    @checkpoint_wrapper.with_checkpoint("pass_a")
    def demo_pass(document_path: Path):
        return {"output": document_path.name}

    doc_path = tmp_path / "doc.pdf"
    doc_path.write_text("content")

    first_result = demo_pass(doc_path)
    assert first_result["output"] == "doc.pdf"

    second_result = demo_pass(doc_path)
    assert second_result["skipped"]
    assert second_result["reason"] == "already_completed"
