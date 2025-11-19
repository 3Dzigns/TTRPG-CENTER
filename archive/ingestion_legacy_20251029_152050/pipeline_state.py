"""Pipeline state management for checkpoint/resume capability."""
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import hashlib

from time_utils import utc_now, utc_now_isoformat

DEFAULT_PASS_ORDER = ["pass_a", "pass_b", "pass_c", "pass_d", "pass_e"]


class PipelineState:
    """
    Manage pipeline execution state for resume capability.

    Tracks:
    - Which passes have completed for each document
    - Pass metadata (timing, success, errors)
    - Document processing status
    """

    def __init__(
        self,
        state_dir: Path = Path("ingestion/state"),
        pass_order: Optional[List[str]] = None
    ):
        """
        Initialize pipeline state manager.

        Args:
            state_dir: Directory to store state files
            pass_order: Ordered list of pipeline passes for resume logic
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.pass_order = pass_order or DEFAULT_PASS_ORDER

    def _get_state_file(self, document_id: str) -> Path:
        """Get state file path for document."""
        return self.state_dir / f"{document_id}_state.json"

    def _document_id_from_path(self, document_path: Path) -> str:
        """Generate stable document ID from path."""
        # Use hash of absolute path for stable ID
        return hashlib.md5(str(document_path.absolute()).encode()).hexdigest()[:16]

    def load_state(self, document_id: str) -> Dict[str, Any]:
        """
        Load pipeline state for document.

        Returns:
            State dict with passes_completed, metadata, etc.
        """
        state_file = self._get_state_file(document_id)

        if not state_file.exists():
            return {
                "document_id": document_id,
                "passes_completed": [],
                "created_at": utc_now_isoformat(),
                "updated_at": utc_now_isoformat(),
                "status": "pending"
            }

        with open(state_file, 'r') as f:
            return json.load(f)

    def save_state(self, document_id: str, state: Dict[str, Any]):
        """Save pipeline state for document."""
        state["updated_at"] = utc_now_isoformat()
        state_file = self._get_state_file(document_id)

        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def mark_pass_started(self, document_id: str, pass_name: str):
        """Mark a pass as started."""
        state = self.load_state(document_id)
        state["status"] = "in_progress"
        state["current_pass"] = pass_name
        state["current_pass_started"] = utc_now_isoformat()
        self.save_state(document_id, state)

    def mark_pass_completed(
        self,
        document_id: str,
        pass_name: str,
        metadata: Optional[Dict] = None
    ):
        """
        Mark a pass as successfully completed.

        Args:
            document_id: Document identifier
            pass_name: Name of completed pass (e.g., 'pass_a', 'pass_b')
            metadata: Optional metadata about the pass execution
        """
        state = self.load_state(document_id)

        pass_record = {
            "pass": pass_name,
            "completed_at": utc_now_isoformat(),
            "status": "success",
            "metadata": metadata or {}
        }

        if "current_pass_started" in state:
            start_time = datetime.fromisoformat(state["current_pass_started"])
            duration = (utc_now() - start_time).total_seconds()
            pass_record["duration_seconds"] = duration

        state["passes_completed"].append(pass_record)

        if "current_pass" in state:
            del state["current_pass"]
        if "current_pass_started" in state:
            del state["current_pass_started"]

        self.save_state(document_id, state)
        print(f"✅ Checkpoint: {pass_name} completed for {document_id}")

    def mark_pass_failed(
        self,
        document_id: str,
        pass_name: str,
        error: str,
        metadata: Optional[Dict] = None
    ):
        """Mark a pass as failed with error details."""
        state = self.load_state(document_id)

        pass_record = {
            "pass": pass_name,
            "failed_at": utc_now_isoformat(),
            "status": "failed",
            "error": error,
            "metadata": metadata or {}
        }

        if "current_pass_started" in state:
            start_time = datetime.fromisoformat(state["current_pass_started"])
            duration = (utc_now() - start_time).total_seconds()
            pass_record["duration_seconds"] = duration

        state["passes_completed"].append(pass_record)
        state["status"] = "failed"

        self.save_state(document_id, state)
        print(f"❌ Checkpoint: {pass_name} failed for {document_id}")

    def is_pass_completed(self, document_id: str, pass_name: str) -> bool:
        """Check if a specific pass has been completed."""
        state = self.load_state(document_id)

        for pass_record in state["passes_completed"]:
            if pass_record["pass"] == pass_name and pass_record["status"] == "success":
                return True

        return False

    def get_completed_passes(self, document_id: str) -> List[str]:
        """Get list of successfully completed pass names."""
        state = self.load_state(document_id)

        return [
            record["pass"]
            for record in state["passes_completed"]
            if record["status"] == "success"
        ]

    def mark_pipeline_complete(self, document_id: str):
        """Mark entire pipeline as completed."""
        state = self.load_state(document_id)
        state["status"] = "completed"
        state["completed_at"] = utc_now_isoformat()
        self.save_state(document_id, state)
        print(f"✅ Pipeline completed for {document_id}")

    def can_resume(self, document_id: str) -> bool:
        """Check if pipeline can be resumed for document."""
        state = self.load_state(document_id)
        return (
            state["status"] in ["in_progress", "failed"] and
            len(state["passes_completed"]) > 0
        )

    def get_resume_point(self, document_id: str) -> Optional[str]:
        """Get the next pass to execute when resuming."""
        if not self.can_resume(document_id):
            return None

        completed = self.get_completed_passes(document_id)

        for pass_name in self.pass_order:
            if pass_name not in completed:
                return pass_name

        return None

    def clear_state(self, document_id: str):
        """Clear state for document (for reprocessing)."""
        state_file = self._get_state_file(document_id)
        if state_file.exists():
            state_file.unlink()
            print(f"🗑️  Cleared state for {document_id}")
