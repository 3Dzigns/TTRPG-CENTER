# src_common/schema_validator.py
"""
Phase 7: JSON Schema Validation Service
Validates requirements and feature requests against defined schemas (US-705, US-706)
"""

import json
import pathlib
from typing import Dict, Any, List, Optional, Tuple
import jsonschema
from jsonschema import Draft7Validator
from dataclasses import dataclass

from src_common.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationError:
    """Schema validation error details"""
    field_path: str
    message: str
    invalid_value: Any
    schema_path: str


@dataclass
class ValidationResult:
    """Schema validation result"""
    is_valid: bool
    errors: List[ValidationError]
    schema_name: str
    validation_time_ms: float


class SchemaValidator:
    """JSON Schema validation service for requirements and feature requests"""
    
    def __init__(self, schemas_dir: pathlib.Path = None):
        self.schemas_dir = schemas_dir or pathlib.Path("schemas")
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._validator_cache: Dict[str, Draft7Validator] = {}
        
        # Ensure schemas directory exists
        self.schemas_dir.mkdir(parents=True, exist_ok=True)
        
        # Load schemas on initialization
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all JSON schemas from schemas directory"""
        schema_files = [
            "requirements.schema.json",
            "feature_request.schema.json"
        ]
        
        for schema_file in schema_files:
            schema_path = self.schemas_dir / schema_file
            if schema_path.exists():
                try:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                    
                    schema_name = schema_file.replace('.schema.json', '')
                    self._schema_cache[schema_name] = schema
                    
                    # Create validator with format checking
                    validator = Draft7Validator(
                        schema,
                        format_checker=jsonschema.FormatChecker()
                    )
                    self._validator_cache[schema_name] = validator
                    
                    logger.info(f"Loaded schema: {schema_name}")
                    
                except Exception as e:
                    logger.error(f"Error loading schema {schema_file}: {e}")
    
    def validate_requirements(self, requirements_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate requirements JSON against schema (US-705)
        
        Args:
            requirements_data: Requirements data to validate
            
        Returns:
            ValidationResult with validation status and errors
        """
        import time
        start_time = time.perf_counter()
        
        return self._validate_data(requirements_data, "requirements", start_time)
    
    def validate_feature_request(self, feature_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate feature request JSON against schema (US-706)
        
        Args:
            feature_data: Feature request data to validate
            
        Returns:
            ValidationResult with validation status and errors
        """
        import time
        start_time = time.perf_counter()
        
        return self._validate_data(feature_data, "feature_request", start_time)
    
    def _validate_data(self, data: Dict[str, Any], schema_name: str, 
                      start_time: float) -> ValidationResult:
        """Internal method to validate data against specific schema"""
        import time
        
        errors = []
        
        if schema_name not in self._validator_cache:
            error = ValidationError(
                field_path="schema",
                message=f"Schema '{schema_name}' not found",
                invalid_value=schema_name,
                schema_path=""
            )
            validation_time = (time.perf_counter() - start_time) * 1000
            return ValidationResult(
                is_valid=False,
                errors=[error],
                schema_name=schema_name,
                validation_time_ms=validation_time
            )
        
        validator = self._validator_cache[schema_name]
        
        try:
            # Perform validation
            validation_errors = list(validator.iter_errors(data))
            
            for error in validation_errors:
                validation_error = ValidationError(
                    field_path=".".join(str(x) for x in error.absolute_path),
                    message=error.message,
                    invalid_value=error.instance if hasattr(error, 'instance') else None,
                    schema_path=".".join(str(x) for x in error.schema_path)
                )
                errors.append(validation_error)
            
            validation_time = (time.perf_counter() - start_time) * 1000
            
            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                schema_name=schema_name,
                validation_time_ms=validation_time
            )
            
            if result.is_valid:
                logger.debug(f"Schema validation passed for {schema_name}")
            else:
                logger.warning(f"Schema validation failed for {schema_name}: {len(errors)} errors")
            
            return result
            
        except Exception as e:
            logger.error(f"Schema validation error for {schema_name}: {e}")
            error = ValidationError(
                field_path="validation",
                message=f"Validation error: {str(e)}",
                invalid_value=None,
                schema_path=""
            )
            validation_time = (time.perf_counter() - start_time) * 1000
            return ValidationResult(
                is_valid=False,
                errors=[error],
                schema_name=schema_name,
                validation_time_ms=validation_time
            )
    
    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        """Get loaded schema by name"""
        return self._schema_cache.get(schema_name)
    
    def get_available_schemas(self) -> List[str]:
        """Get list of available schema names"""
        return list(self._schema_cache.keys())
    
    def validate_json_file(self, file_path: pathlib.Path, 
                          schema_name: str) -> ValidationResult:
        """
        Validate JSON file against schema
        
        Args:
            file_path: Path to JSON file to validate
            schema_name: Name of schema to validate against
            
        Returns:
            ValidationResult with validation status and errors
        """
        import time
        start_time = time.perf_counter()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return self._validate_data(data, schema_name, start_time)
            
        except json.JSONDecodeError as e:
            validation_time = (time.perf_counter() - start_time) * 1000
            error = ValidationError(
                field_path="json",
                message=f"Invalid JSON: {str(e)}",
                invalid_value=str(file_path),
                schema_path=""
            )
            return ValidationResult(
                is_valid=False,
                errors=[error],
                schema_name=schema_name,
                validation_time_ms=validation_time
            )
        except Exception as e:
            validation_time = (time.perf_counter() - start_time) * 1000
            error = ValidationError(
                field_path="file",
                message=f"Error reading file: {str(e)}",
                invalid_value=str(file_path),
                schema_path=""
            )
            return ValidationResult(
                is_valid=False,
                errors=[error],
                schema_name=schema_name,
                validation_time_ms=validation_time
            )
    
    def validate_requirements_directory(self, requirements_dir: pathlib.Path) -> List[Tuple[str, ValidationResult]]:
        """
        Validate all requirements files in directory
        
        Args:
            requirements_dir: Directory containing requirements JSON files
            
        Returns:
            List of (filename, ValidationResult) tuples
        """
        results = []
        
        if not requirements_dir.exists():
            return results
        
        for req_file in requirements_dir.glob("*.json"):
            try:
                result = self.validate_json_file(req_file, "requirements")
                results.append((req_file.name, result))
            except Exception as e:
                logger.error(f"Error validating requirements file {req_file}: {e}")
        
        return results
    
    def validate_features_directory(self, features_dir: pathlib.Path) -> List[Tuple[str, ValidationResult]]:
        """
        Validate all feature request files in directory
        
        Args:
            features_dir: Directory containing feature request JSON files
            
        Returns:
            List of (filename, ValidationResult) tuples
        """
        results = []
        
        if not features_dir.exists():
            return results
        
        for feature_file in features_dir.glob("FR-*.json"):
            try:
                result = self.validate_json_file(feature_file, "feature_request")
                results.append((feature_file.name, result))
            except Exception as e:
                logger.error(f"Error validating feature request file {feature_file}: {e}")
        
        return results
    
    def generate_validation_report(self, results: List[Tuple[str, ValidationResult]]) -> Dict[str, Any]:
        """
        Generate summary validation report
        
        Args:
            results: List of validation results
            
        Returns:
            Dictionary with validation summary
        """
        total_files = len(results)
        valid_files = sum(1 for _, result in results if result.is_valid)
        invalid_files = total_files - valid_files
        
        total_errors = sum(len(result.errors) for _, result in results)
        avg_validation_time = sum(result.validation_time_ms for _, result in results) / max(total_files, 1)
        
        error_summary = {}
        for filename, result in results:
            if not result.is_valid:
                error_summary[filename] = [
                    {
                        "field": error.field_path,
                        "message": error.message,
                        "schema_path": error.schema_path
                    }
                    for error in result.errors
                ]
        
        return {
            "summary": {
                "total_files": total_files,
                "valid_files": valid_files,
                "invalid_files": invalid_files,
                "total_errors": total_errors,
                "validation_success_rate": (valid_files / max(total_files, 1)) * 100,
                "average_validation_time_ms": round(avg_validation_time, 2)
            },
            "errors": error_summary,
            "timestamp": import_time().strftime("%Y-%m-%d %H:%M:%S")
        }


def import_time():
    """Import time module for timestamp generation"""
    import time
    return time


class SchemaSecurityValidator:
    """Additional security-focused validation for preventing injection attacks"""
    
    @staticmethod
    def sanitize_string_fields(data: Dict[str, Any], 
                             max_length: int = 10000) -> Dict[str, Any]:
        """
        Sanitize string fields to prevent injection attacks
        
        Args:
            data: Data to sanitize
            max_length: Maximum allowed string length
            
        Returns:
            Sanitized data dictionary
        """
        if isinstance(data, dict):
            return {
                key: SchemaSecurityValidator.sanitize_string_fields(value, max_length)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [
                SchemaSecurityValidator.sanitize_string_fields(item, max_length)
                for item in data
            ]
        elif isinstance(data, str):
            # Remove potentially dangerous characters
            sanitized = data.replace('<', '&lt;').replace('>', '&gt;')
            sanitized = sanitized.replace('"', '&quot;').replace("'", '&#x27;')
            
            # Truncate if too long
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length] + "..."
            
            return sanitized
        else:
            return data
    
    @staticmethod
    def validate_no_scripts(data: Dict[str, Any]) -> List[str]:
        """
        Check for potential script injection in string fields
        
        Args:
            data: Data to check
            
        Returns:
            List of fields containing potentially dangerous content
        """
        dangerous_fields = []
        
        def check_value(value: Any, path: str = ""):
            if isinstance(value, dict):
                for key, val in value.items():
                    check_value(val, f"{path}.{key}" if path else key)
            elif isinstance(value, list):
                for i, val in enumerate(value):
                    check_value(val, f"{path}[{i}]")
            elif isinstance(value, str):
                # Check for script tags, javascript:, data: urls, etc.
                lower_val = value.lower()
                dangerous_patterns = [
                    '<script', '</script>', 'javascript:', 'data:', 'vbscript:',
                    'onload=', 'onerror=', 'onclick=', 'eval(', 'alert(',
                    'document.cookie', 'window.location', 'innerHTML'
                ]
                
                for pattern in dangerous_patterns:
                    if pattern in lower_val:
                        dangerous_fields.append(f"{path}: contains '{pattern}'")
                        break
        
        check_value(data)
        return dangerous_fields