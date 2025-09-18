"""
Delta Tracking System for FR-029 Incremental Processing

Provides change tracking, audit trail, and state management
for delta refresh operations.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from ..ttrpg_logging import get_logger
from .delta_models import (
    DocumentState,
    DeltaSession,
    ContentChange,
    DeltaConfig,
    DeltaStatus,
    ProcessingMode
)

logger = get_logger(__name__)


class DeltaTracker:
    """
    System for tracking document states and delta refresh sessions.

    Maintains persistent state information for change detection and
    provides audit trail for all delta operations.
    """

    def __init__(self, storage_path: Optional[Union[str, Path]] = None, config: Optional[DeltaConfig] = None):
        """Initialize delta tracker with storage location."""
        self.config = config or DeltaConfig()
        self.storage_path = Path(storage_path) if storage_path else Path("artifacts/delta_tracking")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory caches
        self.document_states: Dict[str, DocumentState] = {}
        self.active_sessions: Dict[str, DeltaSession] = {}

        # Load existing states
        self._load_stored_states()

        logger.info(f"DeltaTracker initialized with storage: {self.storage_path}")

    def get_document_state(self, document_path: str) -> Optional[DocumentState]:
        """Get current state for a document."""
        return self.document_states.get(document_path)

    def save_document_state(self, state: DocumentState):
        """Save document state to storage."""
        self.document_states[state.document_path] = state

        # Persist to storage
        if self.config.enable_caching:
            self._persist_document_state(state)

        logger.debug(f"Saved document state for: {state.document_path}")

    def start_delta_session(
        self,
        document_path: str,
        processing_mode: ProcessingMode = ProcessingMode.INCREMENTAL
    ) -> DeltaSession:
        """Start a new delta refresh session."""
        session = DeltaSession(
            document_path=document_path,
            processing_mode=processing_mode
        )

        self.active_sessions[session.session_id] = session

        session.log_processing_step("session_started", {
            "document": document_path,
            "mode": processing_mode.value,
            "session_id": session.session_id
        })

        logger.info(f"Started delta session {session.session_id} for {document_path}")

        return session

    def update_session_progress(
        self,
        session_id: str,
        processed_changes: int,
        failed_changes: int = 0
    ):
        """Update session progress."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.processed_changes = processed_changes
            session.failed_changes = failed_changes

            session.log_processing_step("progress_update", {
                "processed": processed_changes,
                "failed": failed_changes,
                "total": session.total_changes
            })

    def complete_session(
        self,
        session_id: str,
        success: bool = True,
        baseline_time_ms: Optional[float] = None
    ) -> Optional[DeltaSession]:
        """Complete a delta refresh session."""
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found in active sessions")
            return None

        session = self.active_sessions[session_id]
        session.mark_completed(success)

        if baseline_time_ms:
            session.calculate_efficiency(baseline_time_ms)

        # Move from active to completed
        del self.active_sessions[session_id]

        # Persist session data
        self._persist_session(session)

        session.log_processing_step("session_completed", {
            "success": success,
            "processing_time_ms": session.processing_time_ms,
            "efficiency_ratio": session.efficiency_ratio
        })

        logger.info(f"Completed delta session {session_id}: {'success' if success else 'failed'}")

        return session

    def get_session(self, session_id: str) -> Optional[DeltaSession]:
        """Get session by ID."""
        return self.active_sessions.get(session_id)

    def add_changes_to_session(self, session_id: str, changes: List[ContentChange]):
        """Add detected changes to a session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]

            for change in changes:
                session.add_change(change)

            session.log_processing_step("changes_detected", {
                "new_changes": len(changes),
                "total_changes": session.total_changes
            })

            logger.debug(f"Added {len(changes)} changes to session {session_id}")

    def log_session_error(self, session_id: str, error: str, details: Optional[Dict[str, Any]] = None):
        """Log an error for a session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.log_error(error, details)

            logger.error(f"Session {session_id} error: {error}")

    def create_rollback_point(self, session_id: str, rollback_data: Dict[str, Any]):
        """Create a rollback point for a session."""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.rollback_data = rollback_data
            session.can_rollback = True

            session.log_processing_step("rollback_point_created", {
                "data_size": len(str(rollback_data))
            })

    def get_document_history(self, document_path: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get processing history for a document."""
        history = []

        # Search through completed sessions
        completed_sessions_path = self.storage_path / "completed_sessions"
        if completed_sessions_path.exists():
            for session_file in completed_sessions_path.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)

                    if session_data.get('document_path') == document_path:
                        history.append({
                            'session_id': session_data.get('session_id'),
                            'completed_at': session_data.get('completed_at'),
                            'status': session_data.get('status'),
                            'total_changes': session_data.get('total_changes', 0),
                            'processing_time_ms': session_data.get('processing_time_ms', 0),
                            'efficiency_ratio': session_data.get('efficiency_ratio', 0)
                        })
                except Exception as e:
                    logger.warning(f"Error reading session file {session_file}: {e}")

        # Sort by completion time and limit
        history.sort(key=lambda x: x.get('completed_at', 0), reverse=True)
        return history[:limit]

    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get overall processing statistics."""
        stats = {
            'active_sessions': len(self.active_sessions),
            'tracked_documents': len(self.document_states),
            'total_processed_sessions': 0,
            'average_processing_time_ms': 0.0,
            'average_efficiency_ratio': 0.0,
            'total_time_saved_ms': 0.0
        }

        # Calculate statistics from completed sessions
        completed_sessions_path = self.storage_path / "completed_sessions"
        if completed_sessions_path.exists():
            total_time = 0.0
            total_efficiency = 0.0
            total_time_saved = 0.0
            session_count = 0

            for session_file in completed_sessions_path.glob("*.json"):
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)

                    if session_data.get('status') == DeltaStatus.COMPLETED.value:
                        total_time += session_data.get('processing_time_ms', 0)
                        total_efficiency += session_data.get('efficiency_ratio', 0)
                        total_time_saved += session_data.get('time_saved_ms', 0)
                        session_count += 1

                except Exception as e:
                    logger.warning(f"Error reading session statistics from {session_file}: {e}")

            if session_count > 0:
                stats['total_processed_sessions'] = session_count
                stats['average_processing_time_ms'] = total_time / session_count
                stats['average_efficiency_ratio'] = total_efficiency / session_count
                stats['total_time_saved_ms'] = total_time_saved

        return stats

    def cleanup_old_sessions(self, max_age_days: int = 30):
        """Clean up old session data."""
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0

        completed_sessions_path = self.storage_path / "completed_sessions"
        if completed_sessions_path.exists():
            for session_file in completed_sessions_path.glob("*.json"):
                try:
                    if session_file.stat().st_mtime < cutoff_time:
                        session_file.unlink()
                        cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Error cleaning up session file {session_file}: {e}")

        logger.info(f"Cleaned up {cleaned_count} old session files")

    def export_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export session data for analysis."""
        # Check active sessions first
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            return self._session_to_dict(session)

        # Check completed sessions
        completed_sessions_path = self.storage_path / "completed_sessions"
        session_file = completed_sessions_path / f"{session_id}.json"

        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading session file {session_file}: {e}")

        return None

    def _load_stored_states(self):
        """Load stored document states from disk."""
        states_path = self.storage_path / "document_states"
        if not states_path.exists():
            return

        for state_file in states_path.glob("*.json"):
            try:
                with open(state_file, 'r') as f:
                    state_data = json.load(f)

                # Convert back to DocumentState object
                state = self._dict_to_document_state(state_data)
                self.document_states[state.document_path] = state

            except Exception as e:
                logger.warning(f"Error loading document state from {state_file}: {e}")

        logger.debug(f"Loaded {len(self.document_states)} document states from storage")

    def _persist_document_state(self, state: DocumentState):
        """Persist document state to disk."""
        states_path = self.storage_path / "document_states"
        states_path.mkdir(exist_ok=True)

        # Create safe filename from document path
        safe_filename = state.document_path.replace('/', '_').replace('\\', '_').replace(':', '_')
        state_file = states_path / f"{safe_filename}.json"

        try:
            with open(state_file, 'w') as f:
                json.dump(self._document_state_to_dict(state), f, indent=2)
        except Exception as e:
            logger.error(f"Error persisting document state to {state_file}: {e}")

    def _persist_session(self, session: DeltaSession):
        """Persist completed session to disk."""
        completed_sessions_path = self.storage_path / "completed_sessions"
        completed_sessions_path.mkdir(exist_ok=True)

        session_file = completed_sessions_path / f"{session.session_id}.json"

        try:
            with open(session_file, 'w') as f:
                json.dump(self._session_to_dict(session), f, indent=2)
        except Exception as e:
            logger.error(f"Error persisting session to {session_file}: {e}")

    def _document_state_to_dict(self, state: DocumentState) -> Dict[str, Any]:
        """Convert DocumentState to dictionary for JSON serialization."""
        return {
            'document_path': state.document_path,
            'last_modified': state.last_modified,
            'file_size': state.file_size,
            'document_hash': state.document_hash,
            'last_processed': state.last_processed,
            'processing_version': state.processing_version,
            'created_at': state.created_at,
            'updated_at': state.updated_at,
            # Note: Fingerprints and mappings would need more complex serialization
            # For this implementation, we'll store basic info only
            'page_count': len(state.page_fingerprints),
            'section_count': len(state.section_fingerprints)
        }

    def _dict_to_document_state(self, data: Dict[str, Any]) -> DocumentState:
        """Convert dictionary back to DocumentState."""
        return DocumentState(
            document_path=data['document_path'],
            last_modified=data['last_modified'],
            file_size=data['file_size'],
            document_hash=data['document_hash'],
            last_processed=data.get('last_processed', 0.0),
            processing_version=data.get('processing_version', '1.0'),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time())
        )

    def _session_to_dict(self, session: DeltaSession) -> Dict[str, Any]:
        """Convert DeltaSession to dictionary for JSON serialization."""
        return {
            'session_id': session.session_id,
            'document_path': session.document_path,
            'processing_mode': session.processing_mode.value,
            'started_at': session.started_at,
            'completed_at': session.completed_at,
            'status': session.status.value,
            'total_changes': session.total_changes,
            'processed_changes': session.processed_changes,
            'failed_changes': session.failed_changes,
            'processing_time_ms': session.processing_time_ms,
            'time_saved_ms': session.time_saved_ms,
            'efficiency_ratio': session.efficiency_ratio,
            'can_rollback': session.can_rollback,
            'processing_log': session.processing_log,
            'error_log': session.error_log,
            # Changes would need more complex serialization
            'change_count': len(session.detected_changes)
        }

    def get_active_session_summary(self) -> Dict[str, Any]:
        """Get summary of all active sessions."""
        return {
            'total_active': len(self.active_sessions),
            'sessions': [
                {
                    'session_id': session.session_id,
                    'document': session.document_path,
                    'mode': session.processing_mode.value,
                    'status': session.status.value,
                    'started_at': session.started_at,
                    'total_changes': session.total_changes,
                    'processed_changes': session.processed_changes
                }
                for session in self.active_sessions.values()
            ]
        }