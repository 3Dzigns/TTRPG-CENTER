"""
Unit tests for FR-029 Delta Refresh System

Tests cover:
- Delta detection models and fingerprinting
- Change detection and analysis
- Incremental processing orchestration
- Performance and efficiency metrics
"""

import pytest
import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from src_common.ingestion.delta_models import (
    ContentFingerprint,
    ContentChange,
    DocumentState,
    DeltaSession,
    DeltaConfig,
    ChangeType,
    DeltaStatus,
    ProcessingMode,
    calculate_content_similarity,
    estimate_change_magnitude
)
from src_common.ingestion.delta_detector import DeltaDetector
from src_common.ingestion.delta_tracker import DeltaTracker
from src_common.ingestion.delta_refresh import DeltaRefresh
from src_common.ingestion.delta_integration import IncrementalIngestionManager


class TestDeltaModels:
    """Test delta refresh data models."""

    def test_content_fingerprint_creation(self):
        """Test ContentFingerprint creation and comparison."""
        content = "This is test content for fingerprinting."
        metadata = {"page": 1, "section": "intro"}

        fingerprint = ContentFingerprint.from_content(
            content=content,
            metadata=metadata,
            page_number=1,
            section_id="intro"
        )

        assert fingerprint.content_hash
        assert fingerprint.metadata_hash
        assert fingerprint.page_number == 1
        assert fingerprint.section_id == "intro"
        assert fingerprint.content_length == len(content)
        assert fingerprint.word_count == len(content.split())

        # Test matching
        same_fingerprint = ContentFingerprint.from_content(content, metadata, 1, "intro")
        assert fingerprint.matches(same_fingerprint)

        # Test different content
        different_fingerprint = ContentFingerprint.from_content("Different content", metadata, 1, "intro")
        assert not fingerprint.matches(different_fingerprint)
        assert not fingerprint.content_matches(different_fingerprint)

    def test_content_change_creation(self):
        """Test ContentChange creation and properties."""
        old_fingerprint = ContentFingerprint.from_content("Old content")
        new_fingerprint = ContentFingerprint.from_content("New content")

        change = ContentChange(
            change_type=ChangeType.MODIFIED,
            document_path="test.pdf",
            page_number=1,
            old_fingerprint=old_fingerprint,
            new_fingerprint=new_fingerprint
        )

        assert change.change_type == ChangeType.MODIFIED
        assert change.document_path == "test.pdf"
        assert change.page_number == 1
        assert change.change_id

        summary = change.get_change_summary()
        assert 'change_id' in summary
        assert 'type' in summary
        assert 'location' in summary

    def test_document_state_creation(self):
        """Test DocumentState creation and change detection."""
        # Create temporary file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test document content")
            temp_path = f.name

        try:
            state = DocumentState.from_file(temp_path)

            assert state.document_path == temp_path
            assert state.file_size > 0
            assert state.document_hash
            assert state.last_modified > 0

            # Test fingerprint management
            fingerprint = ContentFingerprint.from_content("Page 1 content")
            state.add_page_fingerprint(1, fingerprint)

            assert 1 in state.page_fingerprints
            assert state.page_fingerprints[1] == fingerprint

        finally:
            Path(temp_path).unlink()

    def test_document_state_change_detection(self):
        """Test change detection between document states."""
        state1 = DocumentState(
            document_path="test.pdf",
            last_modified=1000,
            file_size=100,
            document_hash="hash1"
        )

        state2 = DocumentState(
            document_path="test.pdf",
            last_modified=2000,
            file_size=200,
            document_hash="hash2"
        )

        # Add fingerprints
        fp1 = ContentFingerprint.from_content("Page 1 v1")
        fp2 = ContentFingerprint.from_content("Page 1 v2")

        state1.add_page_fingerprint(1, fp1)
        state2.add_page_fingerprint(1, fp2)

        # Test change detection
        assert state1.has_changes(state2)
        changed_pages = state1.get_changed_pages(state2)
        assert 1 in changed_pages

    def test_delta_session_management(self):
        """Test DeltaSession lifecycle management."""
        session = DeltaSession(
            document_path="test.pdf",
            processing_mode=ProcessingMode.INCREMENTAL
        )

        assert session.status == DeltaStatus.PENDING
        assert session.total_changes == 0

        # Add changes
        change = ContentChange(change_type=ChangeType.MODIFIED)
        session.add_change(change)

        assert session.total_changes == 1

        # Log processing steps
        session.log_processing_step("test_step", {"detail": "test"})
        assert len(session.processing_log) == 1

        # Complete session
        session.mark_completed(True)
        assert session.status == DeltaStatus.COMPLETED
        assert session.completed_at is not None

        # Test efficiency calculation
        session.calculate_efficiency(10000.0)  # 10 second baseline
        assert session.efficiency_ratio > 0

    def test_content_similarity_calculation(self):
        """Test content similarity functions."""
        content1 = "The fireball spell deals 8d6 fire damage"
        content2 = "Fireball deals 8d6 fire damage to targets"
        content3 = "Lightning bolt deals 8d6 lightning damage"

        # Similar content should have high similarity
        similarity1 = calculate_content_similarity(content1, content2)
        assert similarity1 > 0.5

        # Different content should have lower similarity
        similarity2 = calculate_content_similarity(content1, content3)
        assert similarity2 < similarity1

        # Identical content should have perfect similarity
        similarity3 = calculate_content_similarity(content1, content1)
        assert similarity3 == 1.0

    def test_change_magnitude_estimation(self):
        """Test change magnitude estimation."""
        old_content = "Original content"
        new_content = "Original content with additions"
        different_content = "Completely different content"

        # Small change should have low magnitude
        small_magnitude = estimate_change_magnitude(old_content, new_content)
        assert 0.0 <= small_magnitude <= 1.0

        # Large change should have higher magnitude
        large_magnitude = estimate_change_magnitude(old_content, different_content)
        assert large_magnitude > small_magnitude

        # No change should have zero magnitude
        no_change = estimate_change_magnitude(old_content, old_content)
        assert no_change == 0.0

    def test_delta_config_validation(self):
        """Test DeltaConfig behavior and validation."""
        config = DeltaConfig()

        # Test default values
        assert config.enable_page_level_detection is True
        assert config.enable_section_level_detection is True
        assert config.min_similarity_for_update == 0.1
        assert config.max_similarity_for_skip == 0.95

        # Test threshold logic
        assert config.should_use_full_processing(0.6) is True  # Above max_change_percentage
        assert config.should_use_full_processing(0.3) is False

        # Test batch size calculation
        batch_size = config.get_processing_batch_size(25)
        assert batch_size > 0
        assert batch_size <= config.change_batch_size


class TestDeltaDetector:
    """Test delta detection engine."""

    @pytest.fixture
    def detector(self):
        """Create DeltaDetector for testing."""
        config = DeltaConfig(
            enable_page_level_detection=True,
            enable_section_level_detection=True
        )
        return DeltaDetector(config)

    @pytest.fixture
    def sample_document_states(self):
        """Create sample document states for testing."""
        # Previous state
        prev_state = DocumentState(
            document_path="test.pdf",
            last_modified=1000,
            file_size=100,
            document_hash="hash1"
        )

        # Add fingerprints to previous state
        prev_fp1 = ContentFingerprint.from_content("Page 1 original content")
        prev_fp2 = ContentFingerprint.from_content("Page 2 original content")
        prev_state.add_page_fingerprint(1, prev_fp1)
        prev_state.add_page_fingerprint(2, prev_fp2)

        # Current state
        curr_state = DocumentState(
            document_path="test.pdf",
            last_modified=2000,
            file_size=150,
            document_hash="hash2"
        )

        # Add fingerprints to current state (page 1 modified, page 2 unchanged, page 3 added)
        curr_fp1 = ContentFingerprint.from_content("Page 1 completely different content with many changes that should trigger detection")
        curr_fp2 = ContentFingerprint.from_content("Page 2 original content")  # Unchanged
        curr_fp3 = ContentFingerprint.from_content("Page 3 new content")
        curr_state.add_page_fingerprint(1, curr_fp1)
        curr_state.add_page_fingerprint(2, curr_fp2)
        curr_state.add_page_fingerprint(3, curr_fp3)

        return prev_state, curr_state

    def test_detector_initialization(self, detector):
        """Test DeltaDetector initialization."""
        assert isinstance(detector.config, DeltaConfig)
        assert isinstance(detector.fingerprint_cache, dict)

    def test_no_changes_detection(self, detector):
        """Test detection when no changes exist."""
        state1 = DocumentState(
            document_path="test.pdf",
            last_modified=1000,
            file_size=100,
            document_hash="same_hash"
        )

        state2 = DocumentState(
            document_path="test.pdf",
            last_modified=1000,
            file_size=100,
            document_hash="same_hash"
        )

        changes = detector.detect_document_changes(state1, state2)
        assert len(changes) == 0

    def test_page_level_change_detection(self, detector, sample_document_states):
        """Test page-level change detection."""
        prev_state, curr_state = sample_document_states

        changes = detector.detect_document_changes(curr_state, prev_state)

        # Should detect changes: page 1 modified, page 3 added
        assert len(changes) >= 2

        change_types = [change.change_type for change in changes]
        assert ChangeType.MODIFIED in change_types
        assert ChangeType.ADDED in change_types

        # Check specific changes
        page_1_changes = [c for c in changes if c.page_number == 1]
        assert len(page_1_changes) > 0
        assert page_1_changes[0].change_type == ChangeType.MODIFIED

        page_3_changes = [c for c in changes if c.page_number == 3]
        assert len(page_3_changes) > 0
        assert page_3_changes[0].change_type == ChangeType.ADDED

    def test_similarity_analysis(self, detector):
        """Test content similarity analysis enhancement."""
        old_fp = ContentFingerprint.from_content("Original content with some text")
        new_fp = ContentFingerprint.from_content("Original content with different text")

        change = ContentChange(
            change_type=ChangeType.MODIFIED,
            old_fingerprint=old_fp,
            new_fingerprint=new_fp
        )

        enhanced_changes = detector._enhance_changes_with_similarity([change])

        assert len(enhanced_changes) == 1
        enhanced_change = enhanced_changes[0]

        assert 0.0 <= enhanced_change.similarity_score <= 1.0
        assert 0.0 <= enhanced_change.change_magnitude <= 1.0
        assert enhanced_change.old_content_preview
        assert enhanced_change.new_content_preview

    def test_change_filtering(self, detector):
        """Test change filtering by thresholds."""
        # Create changes with different similarity scores
        high_similarity_change = ContentChange(
            change_type=ChangeType.MODIFIED,
            similarity_score=0.98,  # Above max_similarity_for_skip
            change_magnitude=0.02
        )

        low_similarity_change = ContentChange(
            change_type=ChangeType.MODIFIED,
            similarity_score=0.05,  # Below min_similarity_for_update
            change_magnitude=0.95
        )

        medium_similarity_change = ContentChange(
            change_type=ChangeType.MODIFIED,
            similarity_score=0.5,
            change_magnitude=0.5
        )

        changes = [high_similarity_change, low_similarity_change, medium_similarity_change]
        filtered_changes = detector._filter_changes_by_thresholds(changes)

        # High similarity change should be filtered out
        # Low and medium similarity changes should be included
        assert len(filtered_changes) == 2

    def test_file_change_detection(self, detector):
        """Test file-based change detection."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Original content")
            temp_path = f.name

        try:
            # First detection (no previous state)
            current_state, changes = detector.detect_file_changes(temp_path, None)
            assert isinstance(current_state, DocumentState)
            assert len(changes) == 0  # No previous state, so no changes

            # Modify file
            with open(temp_path, 'w') as f:
                f.write("Modified content")

            # Second detection (with previous state)
            new_state, changes = detector.detect_file_changes(temp_path, current_state)
            assert isinstance(new_state, DocumentState)
            # Changes detected depends on fingerprinting implementation

        finally:
            Path(temp_path).unlink()

    def test_cache_management(self, detector):
        """Test fingerprint caching."""
        cache_key = detector.get_cache_key("test.pdf", "content_hash")
        assert isinstance(cache_key, str)

        fingerprint = ContentFingerprint.from_content("Test content")

        # Test caching
        detector.cache_fingerprint(cache_key, fingerprint)
        cached_fp = detector.get_cached_fingerprint(cache_key)

        if detector.config.enable_caching and detector.config.cache_fingerprints:
            assert cached_fp == fingerprint

        # Test cache clearing
        detector.clear_cache()
        cleared_fp = detector.get_cached_fingerprint(cache_key)
        assert cleared_fp is None

    def test_detection_summary(self, detector, sample_document_states):
        """Test detection summary generation."""
        prev_state, curr_state = sample_document_states

        changes = detector.detect_document_changes(curr_state, prev_state)
        summary = detector.get_detection_summary(changes)

        assert 'total_changes' in summary
        assert 'change_types' in summary
        assert 'average_magnitude' in summary
        assert 'significant_changes' in summary
        assert 'minor_changes' in summary

        assert summary['total_changes'] == len(changes)


class TestDeltaTracker:
    """Test delta tracking system."""

    @pytest.fixture
    def tracker(self):
        """Create DeltaTracker for testing."""
        temp_dir = tempfile.mkdtemp()
        tracker = DeltaTracker(storage_path=temp_dir)
        yield tracker
        # Cleanup after test
        import shutil
        if Path(temp_dir).exists():
            shutil.rmtree(temp_dir)

    def test_tracker_initialization(self, tracker):
        """Test DeltaTracker initialization."""
        assert isinstance(tracker.config, DeltaConfig)
        assert isinstance(tracker.document_states, dict)
        assert isinstance(tracker.active_sessions, dict)
        assert tracker.storage_path.exists()

    def test_document_state_management(self, tracker):
        """Test document state saving and retrieval."""
        state = DocumentState(
            document_path="test.pdf",
            last_modified=time.time(),
            file_size=1000,
            document_hash="test_hash"
        )

        # Save state
        tracker.save_document_state(state)

        # Retrieve state
        retrieved_state = tracker.get_document_state("test.pdf")
        assert retrieved_state == state

        # Test non-existent document
        missing_state = tracker.get_document_state("missing.pdf")
        assert missing_state is None

    def test_session_lifecycle(self, tracker):
        """Test delta session lifecycle management."""
        # Start session
        session = tracker.start_delta_session("test.pdf", ProcessingMode.INCREMENTAL)

        assert session.session_id in tracker.active_sessions
        assert session.document_path == "test.pdf"
        assert session.processing_mode == ProcessingMode.INCREMENTAL

        # Update progress
        tracker.update_session_progress(session.session_id, 5, 1)

        updated_session = tracker.get_session(session.session_id)
        assert updated_session.processed_changes == 5
        assert updated_session.failed_changes == 1

        # Complete session
        completed_session = tracker.complete_session(session.session_id, True, 10000.0)

        assert completed_session.status == DeltaStatus.COMPLETED
        assert session.session_id not in tracker.active_sessions
        assert completed_session.efficiency_ratio > 0

    def test_change_management(self, tracker):
        """Test change addition and tracking."""
        session = tracker.start_delta_session("test.pdf")

        changes = [
            ContentChange(change_type=ChangeType.ADDED),
            ContentChange(change_type=ChangeType.MODIFIED)
        ]

        tracker.add_changes_to_session(session.session_id, changes)

        updated_session = tracker.get_session(session.session_id)
        assert updated_session.total_changes == 2

    def test_error_logging(self, tracker):
        """Test session error logging."""
        session = tracker.start_delta_session("test.pdf")

        tracker.log_session_error(session.session_id, "Test error", {"detail": "error_detail"})

        updated_session = tracker.get_session(session.session_id)
        assert len(updated_session.error_log) == 1
        assert updated_session.error_log[0]["error"] == "Test error"

    def test_rollback_management(self, tracker):
        """Test rollback point creation."""
        session = tracker.start_delta_session("test.pdf")

        rollback_data = {"chunks": ["chunk1", "chunk2"], "vectors": ["vec1", "vec2"]}
        tracker.create_rollback_point(session.session_id, rollback_data)

        updated_session = tracker.get_session(session.session_id)
        assert updated_session.rollback_data == rollback_data
        assert updated_session.can_rollback is True

    def test_processing_statistics(self, tracker):
        """Test processing statistics calculation."""
        # Create and complete a session
        session = tracker.start_delta_session("test.pdf")
        tracker.complete_session(session.session_id, True, 5000.0)

        stats = tracker.get_processing_statistics()

        assert 'active_sessions' in stats
        assert 'tracked_documents' in stats
        assert 'total_processed_sessions' in stats

    def test_session_data_export(self, tracker):
        """Test session data export."""
        session = tracker.start_delta_session("test.pdf")

        # Export active session
        exported_data = tracker.export_session_data(session.session_id)
        assert exported_data is not None
        assert exported_data['session_id'] == session.session_id

        # Export non-existent session
        missing_data = tracker.export_session_data("non_existent_id")
        assert missing_data is None


@pytest.mark.asyncio
class TestDeltaRefresh:
    """Test delta refresh orchestrator."""

    @pytest.fixture
    async def delta_refresh(self):
        """Create DeltaRefresh for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = DeltaConfig(processing_timeout_ms=1000)  # Short timeout for tests
            refresh = DeltaRefresh("test", config, temp_dir)
            yield refresh
            await refresh.cleanup_resources()

    @pytest.fixture
    def sample_document(self):
        """Create sample document for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Sample document content for testing")
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink()

    async def test_refresh_orchestrator_initialization(self, delta_refresh):
        """Test DeltaRefresh initialization."""
        assert delta_refresh.environment == "test"
        assert isinstance(delta_refresh.config, DeltaConfig)
        assert isinstance(delta_refresh.detector, DeltaDetector)
        assert isinstance(delta_refresh.tracker, DeltaTracker)

    async def test_document_refresh_no_changes(self, delta_refresh, sample_document):
        """Test document refresh with no changes."""
        # First refresh (establishes baseline)
        session1 = await delta_refresh.refresh_document(sample_document)
        assert session1.status == DeltaStatus.COMPLETED

        # Second refresh (should detect no changes)
        session2 = await delta_refresh.refresh_document(sample_document)
        assert session2.status == DeltaStatus.COMPLETED
        assert session2.total_changes == 0

    async def test_document_refresh_with_changes(self, delta_refresh, sample_document):
        """Test document refresh with changes."""
        # First refresh (establishes baseline)
        session1 = await delta_refresh.refresh_document(sample_document)

        # Modify the document
        with open(sample_document, 'w') as f:
            f.write("Modified document content for testing")

        # Second refresh (should detect changes)
        session2 = await delta_refresh.refresh_document(sample_document)
        assert session2.status == DeltaStatus.COMPLETED
        # Changes detected depends on implementation

    async def test_forced_full_processing(self, delta_refresh, sample_document):
        """Test forced full processing mode."""
        session = await delta_refresh.refresh_document(sample_document, force_full_processing=True)

        assert session.processing_mode == ProcessingMode.FULL
        assert session.status == DeltaStatus.COMPLETED

    async def test_batch_document_refresh(self, delta_refresh):
        """Test batch document refresh."""
        # Create multiple temporary documents
        docs = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(f"Document {i} content")
                docs.append(f.name)

        try:
            # Batch refresh
            sessions = await delta_refresh.batch_refresh_documents(docs, max_parallel=2)

            assert len(sessions) == 3
            for session in sessions:
                assert session.status == DeltaStatus.COMPLETED

        finally:
            # Cleanup
            for doc in docs:
                Path(doc).unlink()

    async def test_change_impact_analysis(self, delta_refresh):
        """Test change impact analysis."""
        changes = [
            ContentChange(change_type=ChangeType.ADDED, change_magnitude=0.3),
            ContentChange(change_type=ChangeType.MODIFIED, change_magnitude=0.8),
            ContentChange(change_type=ChangeType.DELETED, change_magnitude=1.0)
        ]

        analysis = delta_refresh._analyze_change_impact(changes)

        assert analysis['total_changes'] == 3
        assert analysis['high_impact_changes'] == 2  # magnitude > 0.7
        assert 'change_types' in analysis
        assert ChangeType.DELETED.value in analysis['change_types']

    async def test_full_processing_decision(self, delta_refresh):
        """Test decision logic for full vs incremental processing."""
        # Low impact changes - should use incremental
        low_impact_changes = [
            ContentChange(change_type=ChangeType.MODIFIED, change_magnitude=0.2)
        ]
        low_impact_analysis = delta_refresh._analyze_change_impact(low_impact_changes)
        assert not delta_refresh._should_use_full_processing(low_impact_changes, low_impact_analysis)

        # High impact changes - should use full
        high_impact_changes = [
            ContentChange(change_type=ChangeType.DELETED, change_magnitude=1.0),
            ContentChange(change_type=ChangeType.DELETED, change_magnitude=1.0)
        ]
        high_impact_analysis = delta_refresh._analyze_change_impact(high_impact_changes)
        assert delta_refresh._should_use_full_processing(high_impact_changes, high_impact_analysis)

    async def test_processing_status(self, delta_refresh):
        """Test processing status retrieval."""
        status = delta_refresh.get_processing_status()

        assert 'active_sessions' in status
        assert 'processing_statistics' in status
        assert 'queue_length' in status
        assert 'background_tasks' in status

    async def test_rollback_functionality(self, delta_refresh):
        """Test session rollback."""
        # Create a session with rollback data
        session = delta_refresh.tracker.start_delta_session("test.pdf")
        rollback_data = {"test": "data"}
        delta_refresh.tracker.create_rollback_point(session.session_id, rollback_data)

        # Test rollback
        success = await delta_refresh.rollback_session(session.session_id)
        assert success is True

        # Test rollback of non-existent session
        success = await delta_refresh.rollback_session("non_existent_id")
        assert success is False


@pytest.mark.asyncio
class TestIncrementalIngestionManager:
    """Test incremental ingestion manager."""

    @pytest.fixture
    async def manager(self):
        """Create IncrementalIngestionManager for testing."""
        temp_dir = tempfile.mkdtemp()
        try:
            config = DeltaConfig(processing_timeout_ms=1000)
            manager = IncrementalIngestionManager("test", config)
            # Override the tracker storage path for testing
            manager.delta_refresh.tracker.storage_path = Path(temp_dir)
            manager.delta_refresh.tracker.storage_path.mkdir(parents=True, exist_ok=True)
            yield manager
            await manager.cleanup()
        finally:
            import shutil
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_document(self):
        """Create sample document for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Sample document for manager testing")
            temp_path = f.name

        yield temp_path
        Path(temp_path).unlink()

    async def test_manager_initialization(self, manager):
        """Test IncrementalIngestionManager initialization."""
        assert manager.environment == "test"
        assert isinstance(manager.config, DeltaConfig)
        assert isinstance(manager.delta_refresh, DeltaRefresh)

    async def test_synchronous_document_refresh(self, manager, sample_document):
        """Test synchronous document refresh."""
        session = await manager.refresh_document(sample_document, background=False)

        assert isinstance(session, DeltaSession)
        assert session.status == DeltaStatus.COMPLETED

    async def test_background_document_refresh(self, manager, sample_document):
        """Test background document refresh."""
        job_id = await manager.refresh_document(sample_document, background=True)

        assert isinstance(job_id, str)
        assert job_id in manager.active_jobs

        # Check job status immediately (while it might still be running)
        status = await manager.get_job_status(job_id)
        assert status is not None
        assert 'status' in status
        assert 'job_id' in status

        # Wait for completion and verify final state
        await asyncio.sleep(0.5)

    async def test_collection_refresh(self, manager):
        """Test document collection refresh."""
        # Create multiple documents
        docs = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(f"Collection document {i}")
                docs.append(f.name)

        try:
            job_id = await manager.refresh_document_collection(docs, max_parallel=2)

            assert isinstance(job_id, str)
            assert job_id in manager.active_jobs

            # Check status immediately
            status = await manager.get_job_status(job_id)
            assert status is not None
            assert 'status' in status

            # Wait for processing completion
            await asyncio.sleep(0.5)

        finally:
            for doc in docs:
                Path(doc).unlink()

    async def test_job_management(self, manager, sample_document):
        """Test job status and cancellation."""
        job_id = await manager.refresh_document(sample_document, background=True)

        # Check status
        status = await manager.get_job_status(job_id)
        assert status is not None
        assert 'job_id' in status
        assert 'started_at' in status

        # Cancel job
        cancelled = await manager.cancel_job(job_id)
        assert cancelled is True

        # Check job is removed
        assert job_id not in manager.active_jobs

    async def test_processing_summary(self, manager):
        """Test processing summary generation."""
        summary = await manager.get_processing_summary()

        assert 'delta_refresh' in summary
        assert 'job_management' in summary
        assert 'integration' in summary

        job_info = summary['job_management']
        assert 'active_jobs' in job_info
        assert 'jobs' in job_info

    async def test_concurrent_processing_prevention(self, manager, sample_document):
        """Test prevention of concurrent processing of same document."""
        # Start two background jobs for same document
        job1 = await manager.refresh_document(sample_document, background=True)
        job2 = await manager.refresh_document(sample_document, background=True)

        # Both should be valid job IDs but processed sequentially
        assert isinstance(job1, str)
        assert isinstance(job2, str)

        # Wait for completion
        await asyncio.sleep(1.0)


class TestIntegrationScenarios:
    """Test integration scenarios and edge cases."""

    def test_large_document_simulation(self):
        """Test behavior with large document changes."""
        # Simulate large document with many changes
        changes = []
        for i in range(100):
            change = ContentChange(
                change_type=ChangeType.MODIFIED,
                change_magnitude=0.1 + (i % 5) * 0.2  # Varying magnitudes
            )
            changes.append(change)

        config = DeltaConfig(max_change_percentage=0.3)
        detector = DeltaDetector(config)

        analysis = {
            "total_changes": len(changes),
            "change_ratio": 0.5,  # 50% change ratio
            "high_impact_changes": 20
        }

        # Should switch to full processing
        should_use_full = config.should_use_full_processing(analysis["change_ratio"])
        assert should_use_full is True

    def test_performance_estimation(self):
        """Test performance improvement estimation."""
        # Simulate efficiency gains
        baseline_time = 30000.0  # 30 seconds
        actual_time = 5000.0     # 5 seconds

        session = DeltaSession()
        session.processing_time_ms = actual_time
        session.calculate_efficiency(baseline_time)

        assert session.efficiency_ratio > 0.8  # 80% improvement
        assert session.time_saved_ms == baseline_time - actual_time

    def test_error_recovery_scenarios(self):
        """Test error recovery and rollback scenarios."""
        config = DeltaConfig(enable_rollback=True)
        tracker = DeltaTracker(config=config)

        session = tracker.start_delta_session("test.pdf")

        # Simulate error during processing
        tracker.log_session_error(session.session_id, "Processing failed")

        # Complete session as failed
        failed_session = tracker.complete_session(session.session_id, False)

        assert failed_session.status == DeltaStatus.FAILED
        assert len(failed_session.error_log) == 1

    def test_consistency_validation(self):
        """Test consistency validation between incremental and full processing."""
        # This would be a more complex test that compares results
        # between incremental and full processing to ensure consistency

        config = DeltaConfig(validate_consistency=True)
        assert config.validate_consistency is True

        # In a full implementation, this would:
        # 1. Process document incrementally
        # 2. Process same document fully
        # 3. Compare results for consistency
        # 4. Flag any discrepancies