#!/usr/bin/env python3
"""
test_gate0_cleanup.py
=====================

Quick harness to validate Gate 0 deferred cleanup behaviour.

Steps performed:
1. Create a temporary Gate 0 marker with a custom rebuild scope.
2. Run `_cleanup_existing_document_data` to verify pending cleanup is recorded.
3. Execute `_ensure_store_cleanup` for each store and confirm the correct
   `clear_document` invocations are staged with per-store targets.

Run with: `python test_gate0_cleanup.py`
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ingestion_wrapper import IngestionPipeline, ProcessingMode


class _TestPipeline(IngestionPipeline):
    """In-memory test harness that avoids external side effects."""

    def __init__(self) -> None:
        super().__init__(mode=ProcessingMode.AD_HOC, log_level="warning")
        self.commands: List[Tuple[str, Optional[List[str]]]] = []
        self.saved_state: Optional[Dict] = None
        self.purged: Optional[Tuple[str, Optional[str]]] = None

    def _run_command(self, command: List[str], step: str) -> Dict[str, object]:
        # Record the command but simulate success.
        self.commands.append((step, command))
        return {"exit_code": 0, "stdout": "", "stderr": ""}

    def _purge_document_artifacts(self, document_id: str, sha256_hash: Optional[str]) -> None:
        # Skip filesystem removal during tests; record invocation only.
        self.purged = (document_id, sha256_hash)

    def _reset_pipeline_steps(
        self,
        state: Dict,
        steps: List[str],
        last_checkpoint: Optional[str] = None
    ) -> None:
        # No-op for tests.
        state['pipeline'] = {}
        state['last_checkpoint'] = last_checkpoint or ""

    def _save_state(self, state: Dict) -> None:
        # Capture the most recent state snapshot for assertions.
        self.saved_state = json.loads(json.dumps(state))

    def _invoke_clear_document(self, document_id: str, targets: Optional[List[str]] = None) -> bool:
        # Record cleanup requests without touching external services.
        self.commands.append(("clear_document", targets))
        return True


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        marker_path = Path(tmpdir) / "doc_marker.json"
        marker_data = {
            "document_id": "test_doc",
            "sha256_hash": "abc123",
            "rebuild_mode": True,
            "rebuild_scope": {
                "mongodb": True,
                "cassandra": False,
                "neo4j": True
            }
        }
        marker_path.write_text(json.dumps(marker_data, indent=2), encoding="utf-8")

        state: Dict[str, object] = {
            "document_id": "test_doc",
            "source_sha256": "abc123",
            "gate_0_marker": str(marker_path),
            "gate_0_validation": {},
            "gate_0_cleanup": {},
            "pipeline": {},
            "status": "pending"
        }

        pipeline = _TestPipeline()

        assert pipeline._cleanup_existing_document_data(state), "cleanup scheduling failed"
        pending = state.get("pending_cleanup")
        assert pending == {"mongodb": True, "cassandra": False, "neo4j": True}, pending

        # MongoDB cleanup should execute once.
        assert pipeline._ensure_store_cleanup(state, "mongodb") is True
        assert state["pending_cleanup"]["mongodb"] is False

        # Cassandra was not scheduled; no new command expected.
        before = len(pipeline.commands)
        assert pipeline._ensure_store_cleanup(state, "cassandra") is True
        assert len(pipeline.commands) == before

        # Neo4j cleanup should execute once.
        assert pipeline._ensure_store_cleanup(state, "neo4j") is True
        assert state["pending_cleanup"]["neo4j"] is False

        print("Gate 0 cleanup test passed.\nLogged commands:")
        for entry in pipeline.commands:
            print("  ", entry)


if __name__ == "__main__":
    main()
