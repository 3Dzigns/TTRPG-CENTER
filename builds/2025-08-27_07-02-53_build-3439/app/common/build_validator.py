"""Build validation utilities for promotion commands"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class BuildValidationError(Exception):
    """Exception raised when build validation fails"""
    pass

class BuildValidator:
    """Validates build artifacts before promotion"""
    
    def __init__(self):
        self.builds_dir = Path("./builds")
    
    def validate_build_exists(self, build_id: str) -> bool:
        """Check if build exists and has valid manifest"""
        try:
            build_path = self.builds_dir / build_id
            if not build_path.exists():
                logger.error(f"Build directory does not exist: {build_path}")
                return False
            
            manifest_path = build_path / "build-manifest.json"
            if not manifest_path.exists():
                logger.error(f"Build manifest does not exist: {manifest_path}")
                return False
            
            # Validate manifest structure
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                
            required_fields = ["build_id", "timestamp", "environment", "status"]
            missing_fields = [field for field in required_fields if field not in manifest]
            
            if missing_fields:
                logger.error(f"Build manifest missing required fields: {missing_fields}")
                return False
            
            if manifest.get("status") != "success":
                logger.error(f"Build status is not successful: {manifest.get('status')}")
                return False
            
            logger.info(f"Build {build_id} validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Build validation error for {build_id}: {e}")
            return False
    
    def get_build_info(self, build_id: str) -> Optional[Dict[str, Any]]:
        """Get build information from manifest"""
        try:
            if not self.validate_build_exists(build_id):
                return None
            
            build_path = self.builds_dir / build_id
            manifest_path = build_path / "build-manifest.json"
            
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            return manifest
            
        except Exception as e:
            logger.error(f"Error retrieving build info for {build_id}: {e}")
            return None
    
    def validate_promotion_path(self, from_env: str, to_env: str) -> bool:
        """Validate that promotion path is allowed (adjacency rule)"""
        valid_paths = [
            ("dev", "test"),
            ("test", "prod")
        ]
        
        if (from_env, to_env) not in valid_paths:
            logger.error(f"Invalid promotion path: {from_env} -> {to_env}. Only adjacent environments allowed.")
            return False
        
        logger.info(f"Promotion path validated: {from_env} -> {to_env}")
        return True
    
    def validate_build_for_promotion(self, build_id: str, from_env: str, to_env: str) -> Dict[str, Any]:
        """Comprehensive validation for build promotion"""
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "build_info": None
        }
        
        try:
            # Check promotion path
            if not self.validate_promotion_path(from_env, to_env):
                validation_result["errors"].append(f"Invalid promotion path: {from_env} -> {to_env}")
            
            # Check build exists and is valid
            if not self.validate_build_exists(build_id):
                validation_result["errors"].append(f"Build {build_id} does not exist or is invalid")
            else:
                build_info = self.get_build_info(build_id)
                validation_result["build_info"] = build_info
                
                # Check if build is from correct source environment
                if build_info and build_info.get("environment") != from_env:
                    validation_result["errors"].append(
                        f"Build {build_id} is from {build_info.get('environment')}, not {from_env}"
                    )
                
                # Check build age (warn if older than 7 days)
                if build_info:
                    import time
                    build_time = build_info.get("timestamp", 0)
                    age_days = (time.time() - build_time) / (24 * 3600)
                    if age_days > 7:
                        validation_result["warnings"].append(
                            f"Build {build_id} is {age_days:.1f} days old"
                        )
            
            # Overall validation result
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
            if validation_result["valid"]:
                logger.info(f"Build promotion validation passed for {build_id}: {from_env} -> {to_env}")
            else:
                logger.error(f"Build promotion validation failed: {validation_result['errors']}")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Build promotion validation error: {e}")
            validation_result["errors"].append(f"Validation error: {str(e)}")
            return validation_result

# Global instance
_validator = None

def get_build_validator() -> BuildValidator:
    """Get global build validator instance"""
    global _validator
    if _validator is None:
        _validator = BuildValidator()
    return _validator