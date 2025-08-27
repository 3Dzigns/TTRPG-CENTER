"""
Requirements Schema Validation System (REQ-001/002/003)
Immutable JSON requirements management with schema validation
"""
import json
import jsonschema
from typing import Dict, List, Any, Optional
from pathlib import Path
import uuid
import time

class RequirementsValidator:
    def __init__(self):
        self.requirements_schema = {
            "type": "object",
            "properties": {
                "metadata": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "version": {"type": "string"},
                        "created": {"type": "number"},
                        "status": {"type": "string", "enum": ["draft", "approved", "implemented", "verified"]},
                        "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["id", "version", "created", "status", "priority", "category"]
                },
                "functional": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "user_story": {"type": "string"},
                        "acceptance_criteria": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "business_rules": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["title", "description", "acceptance_criteria"]
                },
                "technical": {
                    "type": "object",
                    "properties": {
                        "components": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "apis": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "data_models": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "testing": {
                    "type": "object",
                    "properties": {
                        "test_scenarios": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "performance_criteria": {
                            "type": "object",
                            "properties": {
                                "response_time_ms": {"type": "number"},
                                "throughput_rps": {"type": "number"},
                                "availability_percent": {"type": "number"}
                            }
                        }
                    }
                },
                "implementation": {
                    "type": "object",
                    "properties": {
                        "estimated_effort": {"type": "string"},
                        "milestone": {"type": "string"},
                        "implementation_notes": {"type": "string"},
                        "code_references": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["metadata", "functional"]
        }
    
    def validate_requirement(self, requirement: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single requirement against schema"""
        try:
            jsonschema.validate(requirement, self.requirements_schema)
            return {"valid": True, "errors": []}
        except jsonschema.ValidationError as e:
            return {"valid": False, "errors": [str(e)]}
        except Exception as e:
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}
    
    def validate_requirements_file(self, file_path: str) -> Dict[str, Any]:
        """Validate an entire requirements file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, dict) or "requirements" not in data:
                return {"valid": False, "errors": ["File must contain 'requirements' array"]}
            
            requirements = data["requirements"]
            if not isinstance(requirements, list):
                return {"valid": False, "errors": ["Requirements must be an array"]}
            
            validation_results = {
                "valid": True,
                "total_requirements": len(requirements),
                "valid_requirements": 0,
                "invalid_requirements": 0,
                "errors": [],
                "requirement_errors": {}
            }
            
            for i, req in enumerate(requirements):
                result = self.validate_requirement(req)
                if result["valid"]:
                    validation_results["valid_requirements"] += 1
                else:
                    validation_results["invalid_requirements"] += 1
                    validation_results["valid"] = False
                    req_id = req.get("metadata", {}).get("id", f"requirement_{i}")
                    validation_results["requirement_errors"][req_id] = result["errors"]
            
            return validation_results
            
        except json.JSONDecodeError as e:
            return {"valid": False, "errors": [f"Invalid JSON: {str(e)}"]}
        except FileNotFoundError:
            return {"valid": False, "errors": [f"File not found: {file_path}"]}
        except Exception as e:
            return {"valid": False, "errors": [f"Validation failed: {str(e)}"]}
    
    def create_requirement_template(self, 
                                  title: str, 
                                  description: str,
                                  category: str = "feature",
                                  priority: str = "medium") -> Dict[str, Any]:
        """Create a new requirement template following the schema"""
        return {
            "metadata": {
                "id": f"REQ-{str(uuid.uuid4())[:8].upper()}",
                "version": "1.0.0",
                "created": time.time(),
                "status": "draft",
                "priority": priority,
                "category": category,
                "tags": []
            },
            "functional": {
                "title": title,
                "description": description,
                "user_story": f"As a user, I want {title.lower()} so that {description.lower()}",
                "acceptance_criteria": [
                    "Feature is implemented according to specification",
                    "All tests pass",
                    "Documentation is updated"
                ],
                "business_rules": []
            },
            "technical": {
                "components": [],
                "apis": [],
                "dependencies": [],
                "data_models": []
            },
            "testing": {
                "test_scenarios": [
                    "Happy path testing",
                    "Error handling testing",
                    "Performance testing"
                ],
                "performance_criteria": {
                    "response_time_ms": 2000,
                    "throughput_rps": 100,
                    "availability_percent": 99.9
                }
            },
            "implementation": {
                "estimated_effort": "TBD",
                "milestone": "TBD",
                "implementation_notes": "",
                "code_references": []
            }
        }
    
    def get_requirements_stats(self, file_path: str) -> Dict[str, Any]:
        """Get statistics about requirements in a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            requirements = data.get("requirements", [])
            
            stats = {
                "total": len(requirements),
                "by_status": {},
                "by_priority": {},
                "by_category": {}
            }
            
            for req in requirements:
                metadata = req.get("metadata", {})
                status = metadata.get("status", "unknown")
                priority = metadata.get("priority", "unknown")
                category = metadata.get("category", "unknown")
                
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
                stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
            
            return stats
            
        except Exception as e:
            return {"error": str(e)}


def get_requirements_validator():
    """Factory function for requirements validator"""
    return RequirementsValidator()