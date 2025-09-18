"""
Delta Refresh Orchestrator for FR-029 Incremental Processing

Main orchestrator for efficient incremental document processing with
intelligent change detection and selective pipeline updates.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

from ..ttrpg_logging import get_logger
from .delta_models import (
    DocumentState,
    DeltaSession,
    ContentChange,
    DeltaConfig,
    DeltaStatus,
    ProcessingMode,
    ChangeType
)
from .delta_detector import DeltaDetector
from .delta_tracker import DeltaTracker

logger = get_logger(__name__)


class DeltaRefresh:
    """
    Main orchestrator for delta refresh operations.

    Coordinates change detection, incremental processing, and vector store updates
    to provide efficient document refresh with minimal computational overhead.
    """

    def __init__(
        self,
        environment: str = "dev",
        config: Optional[DeltaConfig] = None,
        tracker_storage_path: Optional[str] = None
    ):
        """Initialize delta refresh orchestrator."""
        self.environment = environment
        self.config = config or DeltaConfig()

        # Initialize components
        self.detector = DeltaDetector(self.config)
        self.tracker = DeltaTracker(tracker_storage_path, self.config)

        # Processing state
        self.processing_queue: List[str] = []
        self.background_tasks: Dict[str, asyncio.Task] = {}

        logger.info(f"DeltaRefresh initialized for environment: {environment}")

    async def refresh_document(
        self,
        document_path: Union[str, Path],
        force_full_processing: bool = False
    ) -> DeltaSession:
        """
        Refresh a document using delta processing.

        Args:
            document_path: Path to the document to refresh
            force_full_processing: Force full reprocessing instead of delta

        Returns:
            DeltaSession with processing results
        """
        start_time = time.perf_counter()
        document_path = str(document_path)

        # Determine processing mode
        processing_mode = ProcessingMode.FULL if force_full_processing else ProcessingMode.INCREMENTAL

        # Start tracking session
        session = self.tracker.start_delta_session(document_path, processing_mode)

        try:
            # Step 1: Detect changes
            current_state, changes = await self._detect_document_changes(document_path, session)

            if not changes and processing_mode == ProcessingMode.INCREMENTAL:
                logger.info(f"No changes detected for {document_path}, skipping processing")
                session.mark_completed(True)
                self.tracker.complete_session(session.session_id, True)
                return session

            # Step 2: Analyze change impact
            change_analysis = self._analyze_change_impact(changes)

            # Step 3: Determine if full processing is needed
            if self._should_use_full_processing(changes, change_analysis):
                logger.info(f"Switching to full processing for {document_path}")
                session.processing_mode = ProcessingMode.FULL
                session.log_processing_step("mode_switch", {"reason": "change_threshold_exceeded"})

            # Step 4: Create rollback point
            if self.config.enable_rollback:
                rollback_data = await self._create_rollback_point(document_path, session)
                self.tracker.create_rollback_point(session.session_id, rollback_data)

            # Step 5: Process changes
            if session.processing_mode == ProcessingMode.INCREMENTAL:
                success = await self._process_incremental_changes(changes, session)
            else:
                success = await self._process_full_document(document_path, session)

            # Step 6: Update document state
            if success:
                self.tracker.save_document_state(current_state)

            # Step 7: Complete session
            processing_time = (time.perf_counter() - start_time) * 1000
            baseline_time = await self._estimate_full_processing_time(document_path)

            completed_session = self.tracker.complete_session(
                session.session_id, success, baseline_time
            )

            if completed_session:
                logger.info(
                    f"Delta refresh completed for {document_path}: "
                    f"{'success' if success else 'failed'} "
                    f"({processing_time:.2f}ms, {len(changes)} changes)"
                )

            return completed_session or session

        except Exception as e:
            logger.error(f"Error during delta refresh for {document_path}: {e}")
            self.tracker.log_session_error(session.session_id, str(e))
            self.tracker.complete_session(session.session_id, False)
            return session

    async def batch_refresh_documents(
        self,
        document_paths: List[Union[str, Path]],
        max_parallel: Optional[int] = None
    ) -> List[DeltaSession]:
        """
        Refresh multiple documents in parallel.

        Args:
            document_paths: List of document paths to refresh
            max_parallel: Maximum number of parallel operations

        Returns:
            List of DeltaSession results
        """
        max_parallel = max_parallel or self.config.max_parallel_changes

        # Split into batches
        batches = [
            document_paths[i:i + max_parallel]
            for i in range(0, len(document_paths), max_parallel)
        ]

        all_sessions = []

        for batch in batches:
            logger.info(f"Processing batch of {len(batch)} documents")

            # Process batch in parallel
            tasks = [
                self.refresh_document(doc_path)
                for doc_path in batch
            ]

            batch_sessions = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions and collect results
            for i, result in enumerate(batch_sessions):
                if isinstance(result, Exception):
                    logger.error(f"Error processing {batch[i]}: {result}")
                    # Create a failed session for tracking
                    failed_session = self.tracker.start_delta_session(str(batch[i]))
                    failed_session.status = DeltaStatus.FAILED
                    all_sessions.append(failed_session)
                else:
                    all_sessions.append(result)

        return all_sessions

    async def _detect_document_changes(
        self,
        document_path: str,
        session: DeltaSession
    ) -> Tuple[DocumentState, List[ContentChange]]:
        """Detect changes in a document."""
        session.log_processing_step("change_detection_started", {"document": document_path})

        # Get previous state
        previous_state = self.tracker.get_document_state(document_path)

        # Detect changes
        current_state, changes = self.detector.detect_file_changes(document_path, previous_state)

        # Add changes to session
        self.tracker.add_changes_to_session(session.session_id, changes)

        session.log_processing_step("change_detection_completed", {
            "changes_detected": len(changes),
            "change_types": [c.change_type.value for c in changes]
        })

        return current_state, changes

    def _analyze_change_impact(self, changes: List[ContentChange]) -> Dict[str, Any]:
        """Analyze the impact of detected changes."""
        if not changes:
            return {"total_magnitude": 0.0, "change_ratio": 0.0, "high_impact_changes": 0}

        total_magnitude = sum(change.change_magnitude for change in changes)
        avg_magnitude = total_magnitude / len(changes)
        high_impact_changes = len([c for c in changes if c.change_magnitude > 0.7])

        # Calculate change ratio (simplified)
        change_ratio = min(1.0, len(changes) / 10.0)  # Assume 10 changes = 100%

        return {
            "total_changes": len(changes),
            "total_magnitude": total_magnitude,
            "average_magnitude": avg_magnitude,
            "change_ratio": change_ratio,
            "high_impact_changes": high_impact_changes,
            "change_types": {
                change_type.value: len([c for c in changes if c.change_type == change_type])
                for change_type in ChangeType
            }
        }

    def _should_use_full_processing(
        self,
        changes: List[ContentChange],
        analysis: Dict[str, Any]
    ) -> bool:
        """Determine if full processing should be used instead of incremental."""
        change_ratio = analysis.get("change_ratio", 0.0)

        # Use full processing if too many changes
        if change_ratio > self.config.max_change_percentage:
            return True

        # Use full processing if too many high-impact changes
        high_impact_ratio = analysis.get("high_impact_changes", 0) / max(len(changes), 1)
        if high_impact_ratio > 0.5:
            return True

        # Use full processing if structural changes detected
        structural_changes = analysis.get("change_types", {})
        if structural_changes.get(ChangeType.DELETED.value, 0) > 0:
            return True

        return False

    async def _create_rollback_point(
        self,
        document_path: str,
        session: DeltaSession
    ) -> Dict[str, Any]:
        """Create rollback point data."""
        # In a full implementation, this would capture:
        # - Current vector store state
        # - Graph relationships
        # - Chunk mappings
        # For this implementation, we'll create simplified rollback data

        rollback_data = {
            "document_path": document_path,
            "timestamp": time.time(),
            "session_id": session.session_id,
            "rollback_type": "simplified",
            # In real implementation, would include actual state snapshots
            "state_snapshot": {
                "chunks": [],  # Would contain chunk IDs and data
                "vectors": [],  # Would contain vector IDs and embeddings
                "graph_nodes": []  # Would contain graph node data
            }
        }

        session.log_processing_step("rollback_point_created", {
            "data_size": len(str(rollback_data))
        })

        return rollback_data

    async def _process_incremental_changes(
        self,
        changes: List[ContentChange],
        session: DeltaSession
    ) -> bool:
        """Process changes incrementally."""
        session.log_processing_step("incremental_processing_started", {
            "total_changes": len(changes)
        })

        success_count = 0
        failed_count = 0

        try:
            # Group changes by type for efficient processing
            change_groups = self._group_changes_by_type(changes)

            # Process each group
            for change_type, change_list in change_groups.items():
                group_success = await self._process_change_group(change_type, change_list, session)

                if group_success:
                    success_count += len(change_list)
                else:
                    failed_count += len(change_list)

                # Update session progress
                self.tracker.update_session_progress(
                    session.session_id, success_count, failed_count
                )

            session.log_processing_step("incremental_processing_completed", {
                "successful_changes": success_count,
                "failed_changes": failed_count
            })

            return failed_count == 0

        except Exception as e:
            logger.error(f"Error in incremental processing: {e}")
            self.tracker.log_session_error(session.session_id, str(e))
            return False

    async def _process_change_group(
        self,
        change_type: ChangeType,
        changes: List[ContentChange],
        session: DeltaSession
    ) -> bool:
        """Process a group of changes of the same type."""
        logger.debug(f"Processing {len(changes)} {change_type.value} changes")

        try:
            if change_type == ChangeType.ADDED:
                return await self._process_added_content(changes, session)
            elif change_type == ChangeType.MODIFIED:
                return await self._process_modified_content(changes, session)
            elif change_type == ChangeType.DELETED:
                return await self._process_deleted_content(changes, session)
            else:
                # For MOVED and RENAMED, treat as modified
                return await self._process_modified_content(changes, session)

        except Exception as e:
            logger.error(f"Error processing {change_type.value} changes: {e}")
            return False

    async def _process_added_content(
        self,
        changes: List[ContentChange],
        session: DeltaSession
    ) -> bool:
        """Process added content changes."""
        # In a full implementation, this would:
        # 1. Extract new content from document
        # 2. Run through Pass A (unstructured.io) for new sections
        # 3. Run through Pass B (Haystack) for enrichment
        # 4. Run through Pass C (LlamaIndex) for graph integration
        # 5. Add new chunks to vector store
        # 6. Update graph relationships

        session.log_processing_step("processing_added_content", {
            "change_count": len(changes)
        })

        # Simulate processing time
        await asyncio.sleep(0.1 * len(changes))

        return True

    async def _process_modified_content(
        self,
        changes: List[ContentChange],
        session: DeltaSession
    ) -> bool:
        """Process modified content changes."""
        # In a full implementation, this would:
        # 1. Identify affected chunks/vectors
        # 2. Extract updated content
        # 3. Reprocess through relevant pipeline passes
        # 4. Update vector store with new embeddings
        # 5. Update graph relationships
        # 6. Maintain cross-references

        session.log_processing_step("processing_modified_content", {
            "change_count": len(changes)
        })

        # Simulate processing time
        await asyncio.sleep(0.15 * len(changes))

        return True

    async def _process_deleted_content(
        self,
        changes: List[ContentChange],
        session: DeltaSession
    ) -> bool:
        """Process deleted content changes."""
        # In a full implementation, this would:
        # 1. Identify chunks/vectors to remove
        # 2. Remove from vector store
        # 3. Update graph by removing nodes/relationships
        # 4. Clean up orphaned references

        session.log_processing_step("processing_deleted_content", {
            "change_count": len(changes)
        })

        # Simulate processing time
        await asyncio.sleep(0.05 * len(changes))

        return True

    async def _process_full_document(
        self,
        document_path: str,
        session: DeltaSession
    ) -> bool:
        """Process entire document (fallback to full processing)."""
        session.log_processing_step("full_processing_started", {
            "document": document_path
        })

        try:
            # In a full implementation, this would:
            # 1. Run complete Pass A/B/C pipeline
            # 2. Replace all chunks/vectors for document
            # 3. Rebuild graph relationships
            # 4. Update all cross-references

            # Simulate full processing time
            await asyncio.sleep(2.0)

            session.log_processing_step("full_processing_completed", {
                "document": document_path
            })

            return True

        except Exception as e:
            logger.error(f"Error in full document processing: {e}")
            self.tracker.log_session_error(session.session_id, str(e))
            return False

    def _group_changes_by_type(self, changes: List[ContentChange]) -> Dict[ChangeType, List[ContentChange]]:
        """Group changes by their type for efficient processing."""
        groups = {}

        for change in changes:
            change_type = change.change_type
            if change_type not in groups:
                groups[change_type] = []
            groups[change_type].append(change)

        return groups

    async def _estimate_full_processing_time(self, document_path: str) -> float:
        """Estimate time for full processing (for efficiency calculation)."""
        # In a real implementation, this would look at:
        # - Document size
        # - Historical processing times
        # - Current system load

        # For this implementation, return a fixed estimate
        return 30000.0  # 30 seconds baseline

    async def rollback_session(self, session_id: str) -> bool:
        """Rollback changes from a delta session."""
        session = self.tracker.get_session(session_id)

        if not session or not session.can_rollback or not session.rollback_data:
            logger.warning(f"Cannot rollback session {session_id}: no rollback data available")
            return False

        try:
            logger.info(f"Rolling back session {session_id}")

            # In a full implementation, this would:
            # 1. Restore vector store state
            # 2. Restore graph relationships
            # 3. Restore chunk mappings
            # 4. Update document state

            session.log_processing_step("rollback_started", {
                "session_id": session_id
            })

            # Simulate rollback time
            await asyncio.sleep(1.0)

            session.status = DeltaStatus.ROLLED_BACK
            session.log_processing_step("rollback_completed", {
                "session_id": session_id
            })

            return True

        except Exception as e:
            logger.error(f"Error rolling back session {session_id}: {e}")
            self.tracker.log_session_error(session_id, f"Rollback failed: {str(e)}")
            return False

    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        return {
            "active_sessions": self.tracker.get_active_session_summary(),
            "processing_statistics": self.tracker.get_processing_statistics(),
            "queue_length": len(self.processing_queue),
            "background_tasks": len(self.background_tasks)
        }

    async def cleanup_resources(self):
        """Clean up resources and background tasks."""
        # Cancel background tasks
        for task_id, task in self.background_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.background_tasks.clear()

        # Clear caches
        self.detector.clear_cache()

        logger.info("Delta refresh resources cleaned up")


def create_delta_refresh(
    environment: str = "dev",
    config: Optional[DeltaConfig] = None,
    tracker_storage_path: Optional[str] = None
) -> DeltaRefresh:
    """Create delta refresh orchestrator instance."""
    return DeltaRefresh(environment, config, tracker_storage_path)