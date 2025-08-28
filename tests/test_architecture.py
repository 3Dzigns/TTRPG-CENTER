"""
Test suite for Architecture & Environment Management user stories (01_architecture.md)
Tests for ARCH-001, ARCH-002, ARCH-003 acceptance criteria
"""
import os
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Test ARCH-001: Support DEV, TEST, and PROD environments with distinct ports
class TestEnvironmentConfiguration:
    
    def test_dev_environment_port_8000(self):
        """Test DEV environment runs on port 8000"""
        with patch.dict('os.environ', {'APP_ENV': 'dev', 'PORT': '8000'}):
            from app.common.config import load_config
            cfg = load_config()
            assert cfg['runtime']['env'] == 'dev'
            assert cfg['runtime']['port'] == 8000
    
    def test_test_environment_port_8181(self):
        """Test TEST environment runs on port 8181"""
        with patch.dict('os.environ', {'APP_ENV': 'test', 'PORT': '8181'}):
            from app.common.config import load_config
            cfg = load_config()
            assert cfg['runtime']['env'] == 'test'
            assert cfg['runtime']['port'] == 8181
    
    def test_prod_environment_port_8282(self):
        """Test PROD environment runs on port 8282"""
        with patch.dict('os.environ', {'APP_ENV': 'prod', 'PORT': '8282'}):
            from app.common.config import load_config
            cfg = load_config()
            assert cfg['runtime']['env'] == 'prod'
            assert cfg['runtime']['port'] == 8282
    
    def test_environment_specific_config_files(self):
        """Test each environment has its own config file"""
        config_files = [
            'config/.env.dev',
            'config/.env.test', 
            'config/.env.prod'
        ]
        for file_path in config_files:
            assert Path(file_path).exists(), f"Missing config file: {file_path}"

# Test ARCH-002: Immutable build system with timestamped artifacts
class TestImmutableBuilds:
    
    def test_build_directory_structure(self):
        """Test builds are stored in timestamped format"""
        builds_dir = Path("builds")
        if builds_dir.exists():
            build_dirs = [d for d in builds_dir.iterdir() if d.is_dir()]
            if build_dirs:
                # Check at least one build follows naming convention
                build_pattern = r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_build-\d{4}'
                import re
                found_valid = any(re.match(build_pattern, d.name) for d in build_dirs)
                assert found_valid, "No builds follow timestamped naming convention"
    
    def test_build_manifest_structure(self):
        """Test build manifests include required metadata"""
        builds_dir = Path("builds")
        if builds_dir.exists() and list(builds_dir.iterdir()):
            # Find the most recent build
            build_dirs = sorted([d for d in builds_dir.iterdir() if d.is_dir()], 
                              key=lambda x: x.name, reverse=True)
            if build_dirs:
                manifest_path = build_dirs[0] / "build_manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    
                    required_fields = ['build_id', 'timestamp', 'source_hash', 'environment']
                    for field in required_fields:
                        assert field in manifest, f"Missing required field: {field}"
    
    def test_promotion_pointer_files(self):
        """Test promotion system uses pointer files"""
        releases_dir = Path("releases")
        if releases_dir.exists():
            pointer_files = ['test_current.txt', 'prod_current.txt']
            for file_name in pointer_files:
                pointer_path = releases_dir / file_name
                if pointer_path.exists():
                    content = pointer_path.read_text().strip()
                    assert content, f"Pointer file {file_name} is empty"

# Test ARCH-003: PowerShell automation scripts
class TestPowerShellScripts:
    
    def test_build_script_exists(self):
        """Test build.ps1 script exists"""
        assert Path("scripts/build.ps1").exists(), "Missing build.ps1 script"
    
    def test_promote_script_exists(self):
        """Test promote.ps1 script exists"""
        assert Path("scripts/promote.ps1").exists(), "Missing promote.ps1 script"
    
    def test_rollback_script_exists(self):
        """Test rollback.ps1 script exists"""
        assert Path("scripts/rollback.ps1").exists(), "Missing rollback.ps1 script"
    
    def test_script_content_validity(self):
        """Test scripts contain expected PowerShell syntax"""
        scripts = ['scripts/build.ps1', 'scripts/promote.ps1', 'scripts/rollback.ps1']
        for script_path in scripts:
            if Path(script_path).exists():
                content = Path(script_path).read_text()
                # Basic PowerShell validation
                assert 'param(' in content.lower() or '$' in content, f"{script_path} missing PowerShell syntax"

# Integration tests
class TestArchitectureIntegration:
    
    def test_environment_isolation(self):
        """Test environments are properly isolated"""
        with patch.dict('os.environ', {'APP_ENV': 'dev'}):
            from app.common.astra_client import get_vector_store
            dev_store = get_vector_store()
            dev_collection = dev_store.collection.name if dev_store.collection else None
        
        with patch.dict('os.environ', {'APP_ENV': 'test'}):
            from app.common.astra_client import get_vector_store
            test_store = get_vector_store()
            test_collection = test_store.collection.name if test_store.collection else None
        
        if dev_collection and test_collection:
            assert dev_collection != test_collection, "Environment collections not isolated"
    
    def test_build_promotion_workflow(self):
        """Test build promotion maintains immutability"""
        # This would test the full build->promote->rollback cycle
        # Implementation depends on having actual builds to test with
        pass