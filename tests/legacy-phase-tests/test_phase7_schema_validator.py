# tests/unit/test_phase7_schema_validator.py
"""
Unit tests for Phase 7 Schema Validation System
Tests US-705: Requirements schema validation and US-706: Feature request schema validation
"""

import json
import pytest
import tempfile
import pathlib
from unittest.mock import patch, MagicMock

from src_common.schema_validator import (
    SchemaValidator,
    SchemaSecurityValidator,
    ValidationError,
    ValidationResult
)


class TestSchemaValidator:
    """Test suite for Schema Validator (US-705, US-706)"""
    
    def setup_method(self):
        """Set up test environment with temporary schemas"""
        self.temp_dir = tempfile.mkdtemp()
        self.schemas_dir = pathlib.Path(self.temp_dir) / "schemas"
        self.schemas_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test schemas
        self.create_test_schemas()
        
        self.validator = SchemaValidator(self.schemas_dir)
    
    def create_test_schemas(self):
        """Create minimal test schemas for validation"""
        # Requirements schema
        req_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Requirements Schema",
            "type": "object",
            "required": ["title", "version", "description", "requirements", "metadata"],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                "description": {"type": "string", "minLength": 1},
                "requirements": {
                    "type": "object",
                    "required": ["functional", "non_functional"],
                    "properties": {
                        "functional": {"type": "array"},
                        "non_functional": {"type": "array"}
                    }
                },
                "metadata": {
                    "type": "object",
                    "required": ["version_id", "author", "timestamp"],
                    "properties": {
                        "version_id": {"type": "integer"},
                        "author": {"type": "string"},
                        "timestamp": {"type": "string"}
                    }
                }
            }
        }
        
        # Feature request schema
        feature_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Test Feature Request Schema",
            "type": "object",
            "required": ["request_id", "title", "description", "priority", "requester", "status", "created_at"],
            "properties": {
                "request_id": {"type": "string", "pattern": r"^FR-\d+$"},
                "title": {"type": "string", "minLength": 5},
                "description": {"type": "string", "minLength": 10},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "requester": {"type": "string", "minLength": 1},
                "status": {"type": "string", "enum": ["pending", "approved", "rejected"]},
                "created_at": {"type": "string", "format": "date-time"}
            }
        }
        
        # Write schemas to files
        with open(self.schemas_dir / "requirements.schema.json", 'w') as f:
            json.dump(req_schema, f, indent=2)
        
        with open(self.schemas_dir / "feature_request.schema.json", 'w') as f:
            json.dump(feature_schema, f, indent=2)
    
    def test_schema_loading_on_init(self):
        """Test that schemas are loaded during initialization"""
        schemas = self.validator.get_available_schemas()
        
        assert "requirements" in schemas
        assert "feature_request" in schemas
        assert len(schemas) == 2
    
    def test_get_schema(self):
        """Test retrieving loaded schemas"""
        req_schema = self.validator.get_schema("requirements")
        assert req_schema is not None
        assert req_schema["title"] == "Test Requirements Schema"
        
        feature_schema = self.validator.get_schema("feature_request")
        assert feature_schema is not None
        assert feature_schema["title"] == "Test Feature Request Schema"
    
    def test_get_nonexistent_schema(self):
        """Test getting non-existent schema returns None"""
        schema = self.validator.get_schema("nonexistent")
        assert schema is None
    
    def test_validate_requirements_valid(self):
        """Test validating valid requirements data (US-705)"""
        valid_requirements = {
            "title": "Test Requirements",
            "version": "1.0.0",
            "description": "Test description",
            "requirements": {
                "functional": [],
                "non_functional": []
            },
            "metadata": {
                "version_id": 123456,
                "author": "test_author",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        result = self.validator.validate_requirements(valid_requirements)
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []
        assert result.schema_name == "requirements"
        assert result.validation_time_ms > 0
    
    def test_validate_requirements_invalid(self):
        """Test validating invalid requirements data"""
        invalid_requirements = {
            "title": "",  # Empty title (violates minLength)
            "version": "invalid-version",  # Invalid version format
            "description": "Test description",
            "requirements": {
                "functional": [],
                # Missing non_functional (required field)
            },
            "metadata": {
                "version_id": "not-a-number",  # Wrong type
                "author": "test_author",
                # Missing timestamp (required field)
            }
        }
        
        result = self.validator.validate_requirements(invalid_requirements)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Check specific error types
        error_messages = [error.message for error in result.errors]
        error_paths = [error.field_path for error in result.errors]
        
        # Print for debugging
        print(f"Error messages: {error_messages}")
        print(f"Error paths: {error_paths}")
        
        # Should have errors for various violations - based on actual jsonschema messages
        assert any("non-empty" in msg or "empty" in msg for msg in error_messages)  # Empty title
        assert any("does not match" in msg for msg in error_messages)  # Pattern error
        assert any("required property" in msg for msg in error_messages)  # Missing required fields
        assert any("not of type" in msg for msg in error_messages)  # Type error
    
    def test_validate_feature_request_valid(self):
        """Test validating valid feature request data (US-706)"""
        valid_feature = {
            "request_id": "FR-123456",
            "title": "Test Feature Request",
            "description": "This is a test feature request description",
            "priority": "medium",
            "requester": "test_user",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        result = self.validator.validate_feature_request(valid_feature)
        
        assert result.is_valid is True
        assert result.errors == []
        assert result.schema_name == "feature_request"
    
    def test_validate_feature_request_invalid(self):
        """Test validating invalid feature request data"""
        invalid_feature = {
            "request_id": "INVALID-ID",  # Wrong pattern
            "title": "Test",  # Too short (minLength: 5)
            "description": "Short",  # Too short (minLength: 10)
            "priority": "invalid",  # Not in enum
            "requester": "",  # Empty (minLength: 1)
            "status": "unknown",  # Not in enum
            "created_at": "invalid-date"  # Invalid date format
        }
        
        result = self.validator.validate_feature_request(invalid_feature)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        
        # Check that all invalid fields generated errors
        error_paths = [error.field_path for error in result.errors]
        assert "request_id" in error_paths
        assert "title" in error_paths
        assert "description" in error_paths
        assert "priority" in error_paths
        assert "status" in error_paths
    
    def test_validate_nonexistent_schema(self):
        """Test validating against non-existent schema"""
        data = {"test": "data"}
        
        result = self.validator._validate_data(data, "nonexistent", 0)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message
    
    def test_validate_json_file_valid(self):
        """Test validating valid JSON file"""
        # Create temporary JSON file
        test_file = pathlib.Path(self.temp_dir) / "test_requirements.json"
        valid_data = {
            "title": "File Test",
            "version": "1.0.0",
            "description": "Test from file",
            "requirements": {
                "functional": [],
                "non_functional": []
            },
            "metadata": {
                "version_id": 123,
                "author": "test",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
        
        with open(test_file, 'w') as f:
            json.dump(valid_data, f)
        
        result = self.validator.validate_json_file(test_file, "requirements")
        
        assert result.is_valid is True
        assert result.errors == []
    
    def test_validate_json_file_invalid_json(self):
        """Test validating file with invalid JSON"""
        # Create file with invalid JSON
        test_file = pathlib.Path(self.temp_dir) / "invalid.json"
        with open(test_file, 'w') as f:
            f.write('{"invalid": json}')  # Invalid JSON syntax
        
        result = self.validator.validate_json_file(test_file, "requirements")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Invalid JSON" in result.errors[0].message
    
    def test_validate_json_file_not_found(self):
        """Test validating non-existent file"""
        nonexistent = pathlib.Path(self.temp_dir) / "nonexistent.json"
        
        result = self.validator.validate_json_file(nonexistent, "requirements")
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert "Error reading file" in result.errors[0].message
    
    def test_validate_directory_requirements(self):
        """Test validating all requirements files in directory"""
        req_dir = pathlib.Path(self.temp_dir) / "requirements"
        req_dir.mkdir(exist_ok=True)
        
        # Create valid and invalid requirement files
        valid_req = {
            "title": "Valid Requirements",
            "version": "1.0.0",
            "description": "Valid description",
            "requirements": {"functional": [], "non_functional": []},
            "metadata": {"version_id": 1, "author": "test", "timestamp": "2024-01-01T00:00:00Z"}
        }
        
        invalid_req = {
            "title": "",  # Invalid - empty title
            "version": "1.0.0",
            "description": "Invalid description"
            # Missing required fields
        }
        
        with open(req_dir / "valid.json", 'w') as f:
            json.dump(valid_req, f)
        
        with open(req_dir / "invalid.json", 'w') as f:
            json.dump(invalid_req, f)
        
        results = self.validator.validate_requirements_directory(req_dir)
        
        assert len(results) == 2
        filenames = [filename for filename, _ in results]
        assert "valid.json" in filenames
        assert "invalid.json" in filenames
        
        # Check results
        for filename, result in results:
            if filename == "valid.json":
                assert result.is_valid is True
            elif filename == "invalid.json":
                assert result.is_valid is False
    
    def test_validate_directory_features(self):
        """Test validating all feature request files in directory"""
        feature_dir = pathlib.Path(self.temp_dir) / "features"
        feature_dir.mkdir(exist_ok=True)
        
        valid_feature = {
            "request_id": "FR-123",
            "title": "Valid Feature",
            "description": "Valid feature description",
            "priority": "medium",
            "requester": "user",
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        with open(feature_dir / "FR-123.json", 'w') as f:
            json.dump(valid_feature, f)
        
        results = self.validator.validate_features_directory(feature_dir)
        
        assert len(results) == 1
        filename, result = results[0]
        assert filename == "FR-123.json"
        assert result.is_valid is True
    
    def test_generate_validation_report(self):
        """Test generating validation summary report"""
        # Create mock results
        valid_result = ValidationResult(
            is_valid=True,
            errors=[],
            schema_name="test",
            validation_time_ms=10.5
        )
        
        invalid_result = ValidationResult(
            is_valid=False,
            errors=[
                ValidationError("field1", "error message", "value", "schema.path"),
                ValidationError("field2", "another error", "value2", "schema.path2")
            ],
            schema_name="test",
            validation_time_ms=15.2
        )
        
        results = [
            ("valid.json", valid_result),
            ("invalid.json", invalid_result)
        ]
        
        report = self.validator.generate_validation_report(results)
        
        assert "summary" in report
        assert "errors" in report
        assert "timestamp" in report
        
        summary = report["summary"]
        assert summary["total_files"] == 2
        assert summary["valid_files"] == 1
        assert summary["invalid_files"] == 1
        assert summary["total_errors"] == 2
        assert summary["validation_success_rate"] == 50.0
        assert summary["average_validation_time_ms"] == 12.85
        
        # Check error details
        assert "invalid.json" in report["errors"]
        assert len(report["errors"]["invalid.json"]) == 2


class TestSchemaSecurityValidator:
    """Test suite for Schema Security Validator"""
    
    def test_sanitize_string_fields(self):
        """Test sanitization of potentially dangerous string content"""
        dangerous_data = {
            "title": "<script>alert('xss')</script>",
            "description": "Normal text with 'quotes' and \"double quotes\"",
            "nested": {
                "field": "<div onclick='malicious()'>content</div>",
                "array": ["<img src=x onerror=alert(1)>", "normal text"]
            }
        }
        
        sanitized = SchemaSecurityValidator.sanitize_string_fields(dangerous_data)
        
        assert "&lt;script&gt;" in sanitized["title"]
        assert "&quot;" in sanitized["description"]
        assert "&#x27;" in sanitized["description"]
        assert "&lt;div" in sanitized["nested"]["field"]
        assert "&lt;img" in sanitized["nested"]["array"][0]
        assert sanitized["nested"]["array"][1] == "normal text"  # Unchanged
    
    def test_sanitize_long_strings(self):
        """Test truncation of overly long strings"""
        long_string = "a" * 15000
        data = {"field": long_string}
        
        sanitized = SchemaSecurityValidator.sanitize_string_fields(data, max_length=100)
        
        assert len(sanitized["field"]) == 103  # 100 + "..."
        assert sanitized["field"].endswith("...")
    
    def test_validate_no_scripts(self):
        """Test detection of potentially dangerous script content"""
        dangerous_data = {
            "title": "Normal title",
            "description": "This contains <script>alert('xss')</script>",
            "user_input": "javascript:malicious_function()",
            "nested": {
                "field": "document.cookie stealing attempt",
                "another": "onclick=bad_function()",
                "safe": "This is perfectly safe content"
            },
            "array": ["eval(malicious_code)", "safe content", "vbscript:another_attack"]
        }
        
        dangerous_fields = SchemaSecurityValidator.validate_no_scripts(dangerous_data)
        
        assert len(dangerous_fields) > 0
        
        # Check that dangerous patterns were detected
        dangerous_str = " ".join(dangerous_fields)
        assert "script" in dangerous_str.lower()
        assert "javascript:" in dangerous_str.lower()
        assert "document.cookie" in dangerous_str.lower()
        assert "onclick=" in dangerous_str.lower()
        assert "eval(" in dangerous_str.lower()
        assert "vbscript:" in dangerous_str.lower()
        
        # Safe content should not appear in dangerous fields
        assert not any("safe content" in field for field in dangerous_fields)
        assert not any("perfectly safe" in field for field in dangerous_fields)
    
    def test_validate_no_scripts_clean_data(self):
        """Test that clean data passes security validation"""
        clean_data = {
            "title": "Clean Title",
            "description": "This is a perfectly normal description",
            "nested": {
                "field": "Normal content",
                "array": ["Safe text", "More safe text"]
            }
        }
        
        dangerous_fields = SchemaSecurityValidator.validate_no_scripts(clean_data)
        
        assert dangerous_fields == []


class TestValidationError:
    """Test ValidationError data class"""
    
    def test_validation_error_creation(self):
        """Test creating ValidationError instances"""
        error = ValidationError(
            field_path="test.field",
            message="Test error message",
            invalid_value="invalid",
            schema_path="properties.test.field"
        )
        
        assert error.field_path == "test.field"
        assert error.message == "Test error message"
        assert error.invalid_value == "invalid"
        assert error.schema_path == "properties.test.field"


class TestValidationResult:
    """Test ValidationResult data class"""
    
    def test_validation_result_creation(self):
        """Test creating ValidationResult instances"""
        errors = [
            ValidationError("field1", "error1", "value1", "path1"),
            ValidationError("field2", "error2", "value2", "path2")
        ]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            schema_name="test_schema",
            validation_time_ms=25.5
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert result.schema_name == "test_schema"
        assert result.validation_time_ms == 25.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])