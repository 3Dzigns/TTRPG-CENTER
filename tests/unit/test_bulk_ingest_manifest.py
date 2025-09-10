"""
Unit Tests for BUG-001 Fixes - Bulk Ingestion Manifest and Resume Logic
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add src_common to path for testing
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))

from scripts.bulk_ingest import Pass6Pipeline


class TestPass6Pipeline:
    """Test cases for Pass6Pipeline resume and manifest logic"""
    
    def setup_method(self):
        """Setup test environment"""
        self.pipeline = Pass6Pipeline("test")
    
    def test_should_run_pass_no_resume_always_true(self):
        """Test that when resume=False, _should_run_pass always returns True"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Should return True regardless of manifest existence
            assert self.pipeline._should_run_pass("A", output_dir, resume=False) == True
            assert self.pipeline._should_run_pass("B", output_dir, resume=False) == True
    
    def test_should_run_pass_resume_no_manifest(self):
        """Test resume logic when no manifest exists"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Should return True when no manifest exists
            assert self.pipeline._should_run_pass("A", output_dir, resume=True) == True
    
    def test_should_run_pass_resume_pass_not_completed(self):
        """Test resume logic when pass is not marked as completed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_path = output_dir / "manifest.json"
            
            # Create manifest with some completed passes (but not A)
            manifest_data = {
                "completed_passes": ["B", "C"],
                "pass_b": {"success": True},
                "pass_c": {"success": True}
            }
            
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)
            
            # Pass A is not in completed_passes, should return True
            assert self.pipeline._should_run_pass("A", output_dir, resume=True) == True
    
    def test_should_run_pass_resume_pass_completed_valid_artifacts(self):
        """Test resume logic when pass is completed and has valid artifacts"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_path = output_dir / "manifest.json"
            
            # Create manifest with Pass A completed
            manifest_data = {
                "completed_passes": ["A"],
                "pass_a": {"success": True}
            }
            
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)
            
            # Mock _validate_pass_artifacts to return True
            with patch.object(self.pipeline, '_validate_pass_artifacts', return_value=True):
                # Should return False (don't run pass, it's complete and valid)
                assert self.pipeline._should_run_pass("A", output_dir, resume=True) == False
    
    def test_should_run_pass_resume_pass_completed_invalid_artifacts(self):
        """Test resume logic when pass is completed but artifacts are invalid"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_path = output_dir / "manifest.json"
            
            # Create manifest with Pass A completed
            manifest_data = {
                "completed_passes": ["A"],
                "pass_a": {"success": True}
            }
            
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)
            
            # Mock _validate_pass_artifacts to return False (invalid artifacts)
            with patch.object(self.pipeline, '_validate_pass_artifacts', return_value=False):
                # Should return True (run pass again, artifacts are missing/invalid)
                assert self.pipeline._should_run_pass("A", output_dir, resume=True) == True
    
    def test_should_run_pass_resume_corrupt_manifest(self):
        """Test resume logic when manifest is corrupt/unreadable"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_path = output_dir / "manifest.json"
            
            # Create corrupt manifest
            with open(manifest_path, "w") as f:
                f.write("invalid json content")
            
            # Should return True and handle the exception gracefully
            assert self.pipeline._should_run_pass("A", output_dir, resume=True) == True
    
    def test_validate_pass_artifacts_pass_a(self):
        """Test artifact validation for Pass A"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_path = output_dir / "manifest.json"
            
            # Create valid manifest
            manifest_data = {
                "completed_passes": ["A"],
                "pass_a": {"success": True}
            }
            
            with open(manifest_path, "w") as f:
                json.dump(manifest_data, f)
            
            # Should return True - manifest exists and is valid
            assert self.pipeline._validate_pass_artifacts("A", output_dir, manifest_data) == True
    
    def test_validate_pass_artifacts_missing_files(self):
        """Test artifact validation when expected files are missing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_data = {
                "completed_passes": ["B"],
                "pass_b": {"success": True}
            }
            
            # Pass B expects split_index.json but it doesn't exist
            # Should return False
            assert self.pipeline._validate_pass_artifacts("B", output_dir, manifest_data) == False
    
    def test_validate_pass_artifacts_failed_in_manifest(self):
        """Test artifact validation when pass is marked as failed in manifest"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            manifest_data = {
                "completed_passes": ["A"],
                "pass_a": {"success": False}  # Marked as failed
            }
            
            # Should return False - pass marked as failed
            assert self.pipeline._validate_pass_artifacts("A", output_dir, manifest_data) == False
    
    def test_job_id_for_consistency(self):
        """Test that _job_id_for generates consistent IDs for same file"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(b"test content")
            
        try:
            # Generate job ID twice for same file
            job_id_1 = self.pipeline._job_id_for(temp_path)
            job_id_2 = self.pipeline._job_id_for(temp_path)
            
            # Should be the same (within same second)
            assert job_id_1 == job_id_2
            
            # Should include file attributes in hash
            assert len(job_id_1.split('_')) == 3  # job_{timestamp}_{hash}
            assert job_id_1.startswith("job_")
            
        finally:
            temp_path.unlink()
    
    def test_job_id_for_different_files(self):
        """Test that _job_id_for generates different IDs for different files"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file_1:
            temp_path_1 = Path(temp_file_1.name)
            temp_file_1.write(b"test content 1")
            
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file_2:
            temp_path_2 = Path(temp_file_2.name)
            temp_file_2.write(b"test content 2 - different")
            
        try:
            job_id_1 = self.pipeline._job_id_for(temp_path_1)
            job_id_2 = self.pipeline._job_id_for(temp_path_2)
            
            # Should be different
            assert job_id_1 != job_id_2
            
        finally:
            temp_path_1.unlink()
            temp_path_2.unlink()


if __name__ == "__main__":
    pytest.main([__file__])