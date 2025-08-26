"""Unit tests for build validation functionality"""

import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from app.common.build_validator import BuildValidator, BuildValidationError


class TestBuildValidator(unittest.TestCase):
    """Test cases for build validation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.validator = BuildValidator()
        
        # Mock valid build manifest
        self.valid_manifest = {
            "build_id": "test_build_123",
            "timestamp": 1640995200,  # 2022-01-01
            "environment": "test",
            "status": "success",
            "artifacts": ["schema", "config", "embeddings"]
        }
        
        # Mock invalid build manifest
        self.invalid_manifest = {
            "build_id": "test_build_456",
            "timestamp": 1640995200,
            "status": "failed"  # Missing environment field
        }
    
    @patch('pathlib.Path.exists')
    def test_validate_build_exists_missing_directory(self, mock_exists):
        """Test validation fails when build directory doesn't exist"""
        mock_exists.return_value = False
        
        result = self.validator.validate_build_exists("nonexistent_build")
        
        self.assertFalse(result)
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_build_exists_valid_build(self, mock_file, mock_exists):
        """Test validation passes for valid build"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.valid_manifest)
        
        result = self.validator.validate_build_exists("test_build_123")
        
        self.assertTrue(result)
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_build_exists_invalid_manifest(self, mock_file, mock_exists):
        """Test validation fails for invalid manifest"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.invalid_manifest)
        
        result = self.validator.validate_build_exists("test_build_456")
        
        self.assertFalse(result)
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_validate_build_exists_failed_status(self, mock_file, mock_exists):
        """Test validation fails for builds with failed status"""
        mock_exists.return_value = True
        failed_manifest = self.valid_manifest.copy()
        failed_manifest["status"] = "failed"
        mock_file.return_value.read.return_value = json.dumps(failed_manifest)
        
        result = self.validator.validate_build_exists("failed_build")
        
        self.assertFalse(result)
    
    def test_validate_promotion_path_valid_paths(self):
        """Test valid promotion paths are accepted"""
        valid_paths = [
            ("dev", "test"),
            ("test", "prod")
        ]
        
        for from_env, to_env in valid_paths:
            with self.subTest(from_env=from_env, to_env=to_env):
                result = self.validator.validate_promotion_path(from_env, to_env)
                self.assertTrue(result)
    
    def test_validate_promotion_path_invalid_paths(self):
        """Test invalid promotion paths are rejected"""
        invalid_paths = [
            ("dev", "prod"),  # Skipping test
            ("test", "dev"),  # Reverse direction
            ("prod", "test"), # Reverse direction
            ("invalid", "test")  # Non-existent environment
        ]
        
        for from_env, to_env in invalid_paths:
            with self.subTest(from_env=from_env, to_env=to_env):
                result = self.validator.validate_promotion_path(from_env, to_env)
                self.assertFalse(result)
    
    @patch.object(BuildValidator, 'validate_promotion_path')
    @patch.object(BuildValidator, 'validate_build_exists')
    @patch.object(BuildValidator, 'get_build_info')
    def test_validate_build_for_promotion_success(self, mock_get_info, mock_exists, mock_path):
        """Test comprehensive promotion validation success"""
        mock_path.return_value = True
        mock_exists.return_value = True
        mock_get_info.return_value = self.valid_manifest
        
        result = self.validator.validate_build_for_promotion("test_build_123", "test", "prod")
        
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
        self.assertIsNotNone(result["build_info"])
    
    @patch.object(BuildValidator, 'validate_promotion_path')
    @patch.object(BuildValidator, 'validate_build_exists')
    def test_validate_build_for_promotion_failure(self, mock_exists, mock_path):
        """Test comprehensive promotion validation failure"""
        mock_path.return_value = False
        mock_exists.return_value = False
        
        result = self.validator.validate_build_for_promotion("nonexistent_build", "dev", "prod")
        
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)
    
    @patch.object(BuildValidator, 'validate_promotion_path')
    @patch.object(BuildValidator, 'validate_build_exists')
    @patch.object(BuildValidator, 'get_build_info')
    @patch('time.time')
    def test_validate_build_for_promotion_old_build_warning(self, mock_time, mock_get_info, mock_exists, mock_path):
        """Test warning for old builds"""
        mock_path.return_value = True
        mock_exists.return_value = True
        
        # Mock current time to be 10 days after build timestamp
        old_manifest = self.valid_manifest.copy()
        old_manifest["timestamp"] = 1640995200  # Old timestamp
        mock_time.return_value = 1640995200 + (10 * 24 * 3600)  # 10 days later
        mock_get_info.return_value = old_manifest
        
        result = self.validator.validate_build_for_promotion("old_build", "test", "prod")
        
        self.assertTrue(result["valid"])  # Should still be valid
        self.assertGreater(len(result["warnings"]), 0)  # But should have warnings
        self.assertIn("days old", result["warnings"][0])
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_build_info_success(self, mock_file, mock_exists):
        """Test successful retrieval of build info"""
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = json.dumps(self.valid_manifest)
        
        result = self.validator.get_build_info("test_build_123")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["build_id"], "test_build_123")
        self.assertEqual(result["status"], "success")
    
    @patch.object(BuildValidator, 'validate_build_exists')
    def test_get_build_info_invalid_build(self, mock_exists):
        """Test get_build_info returns None for invalid build"""
        mock_exists.return_value = False
        
        result = self.validator.get_build_info("invalid_build")
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()