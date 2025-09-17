# tests/unit/test_pass_c_bypass_system.py
"""
Unit tests for SHA-based Pass C bypass system

Tests cover:
- SHA validation and bypass logic
- Artifact preservation mechanisms
- Safe upsert/removal of chunks
- Database schema and operations
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src_common.pass_c_bypass_validator import (
    PassCBypassValidator, get_bypass_validator, 
    ProcessingRecord, BypassValidationResult
)
from src_common.artifact_preservation import (
    ArtifactPreservationManager, get_artifact_manager,
    ArtifactCopyResult
)
from src_common.models import SourceIngestionHistory
from src_common.astra_loader import AstraLoader


class TestPassCBypassValidator:
    """Test SHA-based bypass validation logic"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('src_common.pass_c_bypass_validator.sessionmaker') as mock_session_maker:
            mock_session = Mock()
            mock_session_maker.return_value = mock_session
            yield mock_session
    
    @pytest.fixture
    def mock_astra_client(self):
        """Mock AstraDB client"""
        with patch('src_common.pass_c_bypass_validator.AstraLoader') as mock_loader:
            mock_client = Mock()
            mock_collection = Mock()
            mock_client.get_collection.return_value = mock_collection
            
            mock_loader_instance = Mock()
            mock_loader_instance.client = mock_client
            mock_loader_instance.collection_name = "test_collection"
            mock_loader.return_value = mock_loader_instance
            
            yield mock_client, mock_collection
    
    def test_check_source_processed_found(self, mock_db_session):
        """Test checking for existing processed source - found"""
        validator = PassCBypassValidator("dev")
        
        # Mock database return
        mock_result = Mock()
        mock_result.source_hash = "abcd1234"
        mock_result.source_path = "/path/to/source.pdf"
        mock_result.chunk_count = 150
        mock_result.last_processed_at = datetime.now(timezone.utc)
        mock_result.environment = "dev"
        mock_result.pass_c_artifacts_path = "/artifacts/path"
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_result
        
        result = validator.check_source_processed("abcd1234")
        
        assert result is not None
        assert isinstance(result, ProcessingRecord)
        assert result.source_hash == "abcd1234"
        assert result.chunk_count == 150
        assert result.pass_c_artifacts_path == "/artifacts/path"
    
    def test_check_source_processed_not_found(self, mock_db_session):
        """Test checking for existing processed source - not found"""
        validator = PassCBypassValidator("dev")
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = validator.check_source_processed("nonexistent")
        
        assert result is None
    
    def test_get_astra_chunk_count_success(self, mock_astra_client):
        """Test getting chunk count from AstraDB - success"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 150
        
        validator = PassCBypassValidator("dev")
        count = validator.get_astra_chunk_count_by_source("abcd1234")
        
        assert count == 150
        mock_collection.count_documents.assert_called_once_with(
            {"metadata.source_hash": "abcd1234"},
            upper_bound=10000
        )
    
    def test_get_astra_chunk_count_no_client(self):
        """Test getting chunk count when AstraDB client unavailable"""
        with patch('src_common.pass_c_bypass_validator.AstraLoader') as mock_loader:
            mock_loader.return_value.client = None
            
            validator = PassCBypassValidator("dev")
            count = validator.get_astra_chunk_count_by_source("abcd1234")
            
            assert count == 0
    
    def test_validate_chunk_count_match_success(self, mock_astra_client):
        """Test chunk count validation - success"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 150
        
        validator = PassCBypassValidator("dev")
        result = validator.validate_chunk_count_match("abcd1234", 150)
        
        assert result is True
    
    def test_validate_chunk_count_match_failure(self, mock_astra_client):
        """Test chunk count validation - failure"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 120  # Different from expected
        
        validator = PassCBypassValidator("dev")
        result = validator.validate_chunk_count_match("abcd1234", 150)
        
        assert result is False
    
    def test_can_bypass_pass_c_first_time(self, mock_db_session):
        """Test bypass validation - first time processing"""
        validator = PassCBypassValidator("dev")
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        
        result = validator.can_bypass_pass_c("abcd1234", Path("/test.pdf"))
        
        assert isinstance(result, BypassValidationResult)
        assert result.can_bypass is False
        assert "first time processing" in result.reason
        assert result.processing_record is None
    
    def test_can_bypass_pass_c_chunk_count_mismatch(self, mock_db_session, mock_astra_client):
        """Test bypass validation - chunk count mismatch"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 120  # Different count
        
        validator = PassCBypassValidator("dev")
        
        # Mock existing processing record
        mock_result = Mock()
        mock_result.source_hash = "abcd1234"
        mock_result.source_path = "/path/to/source.pdf"
        mock_result.chunk_count = 150  # Expected count
        mock_result.last_processed_at = datetime.now(timezone.utc)
        mock_result.environment = "dev"
        mock_result.pass_c_artifacts_path = None
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_result
        
        result = validator.can_bypass_pass_c("abcd1234", Path("/test.pdf"))
        
        assert result.can_bypass is False
        assert "mismatch" in result.reason
        assert result.expected_chunk_count == 150
        assert result.astra_chunk_count == 120
    
    def test_can_bypass_pass_c_success_no_artifacts(self, mock_db_session, mock_astra_client):
        """Test bypass validation - success without artifacts"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 150  # Matching count
        
        validator = PassCBypassValidator("dev")
        
        # Mock existing processing record without artifacts
        mock_result = Mock()
        mock_result.source_hash = "abcd1234"
        mock_result.source_path = "/path/to/source.pdf"
        mock_result.chunk_count = 150
        mock_result.last_processed_at = datetime.now(timezone.utc)
        mock_result.environment = "dev"
        mock_result.pass_c_artifacts_path = None
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_result
        
        result = validator.can_bypass_pass_c("abcd1234", Path("/test.pdf"))
        
        assert result.can_bypass is True
        assert "can bypass Pass C" in result.reason
        assert result.expected_chunk_count == 150
        assert result.astra_chunk_count == 150
    
    def test_can_bypass_pass_c_success_with_artifacts(self, mock_db_session, mock_astra_client):
        """Test bypass validation - success with artifacts check"""
        mock_client, mock_collection = mock_astra_client
        mock_collection.count_documents.return_value = 150
        
        validator = PassCBypassValidator("dev")
        
        # Create temporary artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_path = Path(temp_dir) / "artifacts"
            artifacts_path.mkdir()
            
            # Mock existing processing record with artifacts
            mock_result = Mock()
            mock_result.source_hash = "abcd1234"
            mock_result.source_path = "/path/to/source.pdf"
            mock_result.chunk_count = 150
            mock_result.last_processed_at = datetime.now(timezone.utc)
            mock_result.environment = "dev"
            mock_result.pass_c_artifacts_path = str(artifacts_path)
            
            mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_result
            
            result = validator.can_bypass_pass_c("abcd1234", Path("/test.pdf"))
            
            assert result.can_bypass is True
    
    def test_record_successful_processing_new(self, mock_db_session):
        """Test recording successful processing - new record"""
        validator = PassCBypassValidator("dev")
        
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None  # No existing
        
        success = validator.record_successful_processing(
            "abcd1234", Path("/test.pdf"), 150, Path("/artifacts")
        )
        
        assert success is True
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    def test_record_successful_processing_update(self, mock_db_session):
        """Test recording successful processing - update existing"""
        validator = PassCBypassValidator("dev")
        
        mock_existing = Mock()
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = mock_existing
        
        success = validator.record_successful_processing(
            "abcd1234", Path("/test.pdf"), 150, Path("/artifacts")
        )
        
        assert success is True
        assert mock_existing.chunk_count == 150
        mock_db_session.commit.assert_called_once()
    
    def test_remove_chunks_for_source(self, mock_astra_client):
        """Test removing chunks for a source"""
        mock_client, mock_collection = mock_astra_client
        
        mock_delete_result = Mock()
        mock_delete_result.deleted_count = 150
        mock_collection.delete_many.return_value = mock_delete_result
        
        validator = PassCBypassValidator("dev")
        removed_count = validator.remove_chunks_for_source("abcd1234")
        
        assert removed_count == 150
        mock_collection.delete_many.assert_called_once_with({"metadata.source_hash": "abcd1234"})


class TestArtifactPreservationManager:
    """Test artifact preservation functionality"""
    
    @pytest.fixture
    def temp_artifacts(self):
        """Create temporary artifacts structure"""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_dir = Path(temp_dir) / "source_artifacts"
            source_dir.mkdir()
            
            # Create sample artifacts
            (source_dir / "extracted_content.json").write_text('{"test": "data"}')
            (source_dir / "chunks.json").write_text('{"chunks": []}')
            (source_dir / "metadata.json").write_text('{"metadata": "info"}')
            
            # Create subdirectory with files
            images_dir = source_dir / "images"
            images_dir.mkdir()
            (images_dir / "image1.jpg").write_text("fake image data")
            
            dest_dir = Path(temp_dir) / "dest_artifacts"
            
            yield source_dir, dest_dir
    
    def test_identify_pass_c_artifacts(self, temp_artifacts):
        """Test identifying Pass C artifacts"""
        source_dir, dest_dir = temp_artifacts
        
        manager = ArtifactPreservationManager("dev")
        artifacts = manager.identify_pass_c_artifacts(source_dir)
        
        assert len(artifacts) >= 4  # At least the 4 files we created
        
        artifact_names = [f.name for f in artifacts]
        assert "extracted_content.json" in artifact_names
        assert "chunks.json" in artifact_names
        assert "metadata.json" in artifact_names
        assert "image1.jpg" in artifact_names
    
    def test_copy_artifacts_success(self, temp_artifacts):
        """Test successful artifact copying"""
        source_dir, dest_dir = temp_artifacts
        
        manager = ArtifactPreservationManager("dev")
        result = manager.copy_artifacts_from_previous_run(source_dir, dest_dir)
        
        assert result.success is True
        assert result.artifacts_copied >= 4
        assert len(result.copied_files) >= 4
        
        # Verify files were actually copied
        assert (dest_dir / "extracted_content.json").exists()
        assert (dest_dir / "chunks.json").exists()
        assert (dest_dir / "images" / "image1.jpg").exists()
    
    def test_copy_artifacts_source_missing(self):
        """Test artifact copying when source missing"""
        manager = ArtifactPreservationManager("dev")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_source = Path(temp_dir) / "nonexistent"
            dest_dir = Path(temp_dir) / "dest"
            
            result = manager.copy_artifacts_from_previous_run(nonexistent_source, dest_dir)
            
            assert result.success is False
            assert "not found" in result.error_message
            assert result.artifacts_copied == 0
    
    def test_validate_required_artifacts_exist_complete(self, temp_artifacts):
        """Test validating required artifacts - all present"""
        source_dir, dest_dir = temp_artifacts
        
        # Add missing manifest.json
        (source_dir / "manifest.json").write_text('{"manifest": "data"}')
        
        manager = ArtifactPreservationManager("dev")
        result = manager.validate_required_artifacts_exist(source_dir)
        
        assert result["extracted_content.json"] is True
        assert result["chunks.json"] is True
        assert result["metadata.json"] is True
        assert result["manifest.json"] is True
    
    def test_validate_required_artifacts_missing(self, temp_artifacts):
        """Test validating required artifacts - some missing"""
        source_dir, dest_dir = temp_artifacts
        
        manager = ArtifactPreservationManager("dev")
        result = manager.validate_required_artifacts_exist(source_dir)
        
        assert result["extracted_content.json"] is True
        assert result["chunks.json"] is True
        assert result["metadata.json"] is True
        assert result["manifest.json"] is False  # This one we didn't create
    
    def test_create_bypass_marker(self, temp_artifacts):
        """Test creating bypass marker file"""
        source_dir, dest_dir = temp_artifacts
        dest_dir.mkdir()
        
        manager = ArtifactPreservationManager("dev")
        success = manager.create_bypass_marker(
            dest_dir, "abcd1234", "SHA and chunk count match"
        )
        
        assert success is True
        
        marker_path = dest_dir / "pass_c_bypassed.json"
        assert marker_path.exists()
        
        marker_data = json.loads(marker_path.read_text())
        assert marker_data["pass_c_bypassed"] is True
        assert marker_data["source_hash"] == "abcd1234"
        assert marker_data["bypass_reason"] == "SHA and chunk count match"
        assert marker_data["environment"] == "dev"


class TestAstraLoaderEnhancements:
    """Test vector-store-backed AstraLoader functionality for bypass system."""

    @pytest.fixture
    def loader_with_mock_store(self, monkeypatch):
        store = Mock()
        store.backend_name = "astra"
        store.collection_name = "ttrpg_chunks_dev"
        store.upsert_documents.return_value = 2
        store.delete_by_source_hash.return_value = 1
        store.count_documents_for_source.return_value = 150
        store.count_documents.return_value = 200
        store.get_sources_with_chunk_counts.return_value = {
            "status": "ready",
            "environment": "dev",
            "sources": [
                {
                    "source_hash": "job123",
                    "source_file": "Unknown Source",
                    "chunk_count": 7,
                    "last_updated": 123.0,
                }
            ],
            "total_sources": 1,
            "total_chunks": 7,
            "collection_name": "ttrpg_chunks_dev",
        }
        monkeypatch.setattr("src_common.astra_loader.make_vector_store", lambda env: store)
        loader = AstraLoader("dev")
        return loader, store

    def test_safe_upsert_chunks_success(self, loader_with_mock_store):
        loader, store = loader_with_mock_store
        test_chunks = [
            {"id": "chunk1", "content": "Test content 1", "metadata": {"page": 1}},
            {"id": "chunk2", "content": "Test content 2", "metadata": {"page": 2}},
        ]

        result = loader.safe_upsert_chunks_for_source(test_chunks, "abcd1234")

        store.delete_by_source_hash.assert_called_once_with("abcd1234")
        store.upsert_documents.assert_called_once()
        docs = store.upsert_documents.call_args[0][0]
        assert all(doc["metadata"].get("source_hash") == "abcd1234" for doc in docs)
        assert result.success is True
        assert result.chunks_loaded == store.upsert_documents.return_value

    def test_validate_chunk_integrity_success(self, loader_with_mock_store):
        loader, store = loader_with_mock_store
        store.count_documents_for_source.return_value = 150

        result = loader.validate_chunk_integrity("abcd1234", 150)

        store.count_documents_for_source.assert_called_once_with("abcd1234")
        assert result["integrity_valid"] is True
        assert result["expected_count"] == 150
        assert result["actual_count"] == 150
        assert result["status"] == "validated"

    def test_validate_chunk_integrity_mismatch(self, loader_with_mock_store):
        loader, store = loader_with_mock_store
        store.count_documents_for_source.return_value = 120

        result = loader.validate_chunk_integrity("abcd1234", 150)

        assert result["integrity_valid"] is False
        assert result["actual_count"] == 120
        assert result["status"] == "mismatch"

    def test_get_sources_with_chunk_counts(self, loader_with_mock_store):
        loader, store = loader_with_mock_store
        payload = loader.get_sources_with_chunk_counts()

        store.get_sources_with_chunk_counts.assert_called_once()
        assert payload["status"] == "ready"
        assert payload["total_chunks"] == 7

    def test_safe_upsert_handles_backend_error(self, loader_with_mock_store):
        loader, store = loader_with_mock_store
        store.backend_name = 'cassandra'
        store.upsert_documents.side_effect = RuntimeError("boom")

        result = loader.safe_upsert_chunks_for_source([], "abcd1234")

        assert result.success is False
        assert result.error_message == "boom"


class TestFactoryFunctions:
    """Test factory functions"""
    
    def test_get_bypass_validator(self):
        """Test bypass validator factory"""
        validator = get_bypass_validator("dev")
        assert isinstance(validator, PassCBypassValidator)
        assert validator.env == "dev"
    
    def test_get_artifact_manager(self):
        """Test artifact manager factory"""
        manager = get_artifact_manager("dev")
        assert isinstance(manager, ArtifactPreservationManager)
        assert manager.env == "dev"


@pytest.mark.integration
class TestBypassSystemIntegration:
    """Integration tests for complete bypass system"""
    
    @pytest.fixture
    def temp_environment(self):
        """Create temporary test environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()
            
            # Create test PDF
            test_pdf = Path(temp_dir) / "test.pdf"
            test_pdf.write_text("fake PDF content for testing")
            
            yield temp_dir, test_pdf, artifacts_dir
    
    def test_full_bypass_workflow_first_time(self, temp_environment):
        """Test full bypass workflow - first time processing"""
        temp_dir, test_pdf, artifacts_dir = temp_environment
        
        # This would be a full integration test requiring database setup
        # For unit testing, we mock the components
        pass
    
    def test_full_bypass_workflow_bypass_approved(self, temp_environment):
        """Test full bypass workflow - bypass approved"""
        temp_dir, test_pdf, artifacts_dir = temp_environment
        
        # This would test the complete workflow when bypass is approved
        # For unit testing, we mock the components
        pass
