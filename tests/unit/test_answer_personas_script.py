"""
Tests for scripts/answer_personas.py ensuring it produces reports (BP005 US-BP005-1)
"""

import os
import json
import tempfile
from pathlib import Path


def test_answer_personas_main_writes_reports(monkeypatch):
    import importlib

    # Arrange a temporary repo structure
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        personas_dir = repo / "Personas"
        personas_dir.mkdir(parents=True, exist_ok=True)
        artifacts_reports = repo / "artifacts" / "reports"
        artifacts_reports.mkdir(parents=True, exist_ok=True)

        # Minimal persona file in legacy EN Q/A format
        md = (
            "# Test Persona\n\n"
            "- **English Q:** What is a test question?\n\n"
            "- **English A:** This is an expected answer.\n"
        )
        (personas_dir / "Test_Persona.md").write_text(md, encoding="utf-8")

        # Import module fresh and override REPO_ROOT
        mod = importlib.import_module("scripts.answer_personas")
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "")  # ensure local path
        monkeypatch.setenv("ASTRA_DB_APPLICATION_TOKEN", "")
        mod.REPO_ROOT = repo

        # Act
        mod.main()

        # Assert outputs exist
        md_out = artifacts_reports / "persona_answers_dev.md"
        json_out = artifacts_reports / "persona_answers_dev.json"
        assert md_out.exists(), "Markdown report not written"
        assert json_out.exists(), "JSON report not written"

        # Validate JSON structure contains at least one entry with question
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert any("question" in r for r in data)

