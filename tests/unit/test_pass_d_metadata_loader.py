"""Unit tests for Pass D metadata loader.

Tests compliance with PassD_Cassandra_Metadata_Fix.md requirements:
- Happy path: metadata present in various manifest locations
- Missing file: manifest does not exist
- Malformed payload: invalid JSON or missing required fields
- Field name compatibility: file_sha vs source_hash
- Manifest path compatibility: unified_v1 vs legacy locations
"""

import json
import pytest
import tempfile
from pathlib import Path

from src_common.pass_d_vector_enrichment import VectorEnricher


class TestPassDMetadataLoader:
    """Test Pass D metadata loading logic."""

    def test_metadata_from_unified_v1_manifest(self):
        """Test metadata loading from unified_v1 manifest location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_unified"

            # Create unified_v1 manifest at job_dir/{job_id}_pass_a_manifest.json
            manifest_path = job_dir / f"{job_id}_pass_a_manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_file": "test.pdf",
                "environment": "dev",
                "source_info": {
                    "source_hash": "abc123def456"
                }
            }
            manifest_path.write_text(json.dumps(manifest_data))

            # Initialize enricher and load metadata
            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            assert metadata.source_hash == "abc123def456"
            assert metadata.source_file == "test.pdf"
            assert metadata.environment == "dev"
            assert metadata.job_id == job_id

    def test_metadata_from_main_manifest_with_file_sha(self):
        """Test metadata loading from main manifest using pass_0_result.file_sha."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_main"

            # Create main manifest with pass_0_result.file_sha (unified_v1 field name)
            manifest_path = job_dir / "manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_file": "cyberpunk.pdf",
                "environment": "dev",
                "pass_0_result": {
                    "file_sha": "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0"
                }
            }
            manifest_path.write_text(json.dumps(manifest_data))

            # Initialize enricher and load metadata
            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            assert metadata.source_hash == "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0"
            assert metadata.source_file == "cyberpunk.pdf"
            assert metadata.environment == "dev"

    def test_metadata_from_legacy_manifest_location(self):
        """Test metadata loading from legacy manifest location (job_dir/pass_a/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_legacy"

            # Create legacy manifest at job_dir/pass_a/{job_id}_pass_a_manifest.json
            pass_a_dir = job_dir / "pass_a"
            pass_a_dir.mkdir()
            manifest_path = pass_a_dir / f"{job_id}_pass_a_manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_file": "legacy.pdf",
                "environment": "test",
                "source_info": {
                    "source_hash": "legacy_hash_123"
                }
            }
            manifest_path.write_text(json.dumps(manifest_data))

            # Initialize enricher and load metadata
            enricher = VectorEnricher(job_id=job_id, env="test")
            metadata = enricher._load_source_metadata(job_dir)

            assert metadata.source_hash == "legacy_hash_123"
            assert metadata.source_file == "legacy.pdf"
            assert metadata.environment == "test"

    def test_metadata_missing_manifest_file(self):
        """Test error handling when no manifest files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_missing"

            # No manifests created - should raise RuntimeError
            enricher = VectorEnricher(job_id=job_id, env="dev")

            with pytest.raises(RuntimeError) as exc_info:
                enricher._load_source_metadata(job_dir)

            # Verify error message includes checked paths
            error_msg = str(exc_info.value)
            assert "Unable to determine source metadata" in error_msg
            assert "Checked paths:" in error_msg
            assert "manifest.json" in error_msg

    def test_metadata_malformed_json(self):
        """Test error handling for malformed JSON in manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_malformed"

            # Create manifest with invalid JSON
            manifest_path = job_dir / "manifest.json"
            manifest_path.write_text("{invalid json content")

            # Should still raise RuntimeError (fails to parse, no fallback)
            enricher = VectorEnricher(job_id=job_id, env="dev")

            with pytest.raises(RuntimeError) as exc_info:
                enricher._load_source_metadata(job_dir)

            assert "Unable to determine source metadata" in str(exc_info.value)

    def test_metadata_missing_required_fields(self):
        """Test error handling when manifest exists but lacks required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_incomplete"

            # Create manifest missing source_hash
            manifest_path = job_dir / "manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_file": "test.pdf",
                "environment": "dev"
                # No source_hash or pass_0_result.file_sha
            }
            manifest_path.write_text(json.dumps(manifest_data))

            enricher = VectorEnricher(job_id=job_id, env="dev")

            with pytest.raises(RuntimeError) as exc_info:
                enricher._load_source_metadata(job_dir)

            error_msg = str(exc_info.value)
            assert "Unable to determine source metadata" in error_msg
            assert "Required fields:" in error_msg

    def test_metadata_source_file_as_list(self):
        """Test handling of source_file as list (takes first element)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_list"

            manifest_path = job_dir / "manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_file": ["first.pdf", "second.pdf"],  # List format
                "environment": "dev",
                "source_info": {
                    "source_hash": "hash_for_list"
                }
            }
            manifest_path.write_text(json.dumps(manifest_data))

            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            # Should take first element from list
            assert metadata.source_file == "first.pdf"
            assert metadata.source_hash == "hash_for_list"

    def test_metadata_fallback_field_names(self):
        """Test fallback through multiple field name variations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_fallback"

            # Test source_path instead of source_file
            manifest_path = job_dir / "manifest.json"
            manifest_data = {
                "job_id": job_id,
                "source_path": "/uploads/fallback.pdf",  # Alternative field name
                "environment": "dev",
                "pass_0_result": {
                    "file_sha": "fallback_hash"
                }
            }
            manifest_path.write_text(json.dumps(manifest_data))

            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            assert metadata.source_file == "/uploads/fallback.pdf"
            assert metadata.source_hash == "fallback_hash"

    def test_metadata_priority_order(self):
        """Test that unified_v1 manifest takes priority over legacy location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_test_priority"

            # Create both unified_v1 and legacy manifests
            unified_manifest = job_dir / f"{job_id}_pass_a_manifest.json"
            unified_data = {
                "job_id": job_id,
                "source_file": "unified.pdf",
                "source_info": {"source_hash": "unified_hash"}
            }
            unified_manifest.write_text(json.dumps(unified_data))

            legacy_dir = job_dir / "pass_a"
            legacy_dir.mkdir()
            legacy_manifest = legacy_dir / f"{job_id}_pass_a_manifest.json"
            legacy_data = {
                "job_id": job_id,
                "source_file": "legacy.pdf",
                "source_info": {"source_hash": "legacy_hash"}
            }
            legacy_manifest.write_text(json.dumps(legacy_data))

            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            # Should use unified_v1 manifest (takes priority)
            assert metadata.source_file == "unified.pdf"
            assert metadata.source_hash == "unified_hash"


class TestPassDMetadataIntegration:
    """Integration tests simulating Cyberpunk job artifacts."""

    def test_cyberpunk_job_simulation(self):
        """Test metadata loading with Cyberpunk-like manifest structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir)
            job_id = "job_1759593741_dev"

            # Simulate main manifest (as seen in actual job)
            main_manifest = job_dir / "manifest.json"
            main_data = {
                "job_id": job_id,
                "environment": "dev",
                "source_file": "Cyberpunk v3 - CP4110 Core Rulebook.pdf",
                "pass_0_result": {
                    "file_sha": "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0",
                    "page_count": 382
                }
            }
            main_manifest.write_text(json.dumps(main_data))

            # Simulate Pass A manifest (as seen in actual job)
            pass_a_manifest = job_dir / f"{job_id}_pass_a_manifest.json"
            pass_a_data = {
                "job_id": job_id,
                "source_file": "Cyberpunk v3 - CP4110 Core Rulebook.pdf",
                "source_path": "/app/env/dev/uploads/Cyberpunk v3 - CP4110 Core Rulebook.pdf",
                "environment": "dev",
                "source_info": {
                    "file_size": 25335892,
                    "source_hash": "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0"
                }
            }
            pass_a_manifest.write_text(json.dumps(pass_a_data))

            # Initialize enricher and load metadata
            enricher = VectorEnricher(job_id=job_id, env="dev")
            metadata = enricher._load_source_metadata(job_dir)

            # Verify metadata is loaded correctly
            assert metadata.job_id == job_id
            assert metadata.environment == "dev"
            assert metadata.source_file == "Cyberpunk v3 - CP4110 Core Rulebook.pdf"
            assert metadata.source_hash == "4f81185e7057b5d697aabb86040312da236e687b5f3ae5d42d54224ef2f2e1a0"
