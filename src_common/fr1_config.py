# src_common/fr1_config.py
"""
FR1 Configuration Module - Environment-specific settings for FR1 enhancements
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from .logging import get_logger

logger = get_logger(__name__)

class FR1Config:
    """FR1 Enhancement Configuration Management"""
    
    def __init__(self, env: str = "dev"):
        """
        Initialize FR1 configuration for specific environment.
        
        Args:
            env: Environment name (dev, test, prod)
        """
        self.env = env
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load FR1 configuration with environment-specific overrides"""
        # Default configuration
        config = {
            "preprocessor": {
                "size_threshold_mb": 40.0,  # Default 40MB threshold (override via FR1_SIZE_THRESHOLD_MB)
                "semantic_split_preferred": True,  # Prefer chapter/ToC over page windows
                "fallback_to_pages": True,  # Fall back to page windows if no structure
                "max_pages_per_part": 40,  # Safety ceiling per extracted part
                "max_split_parts": 50,  # Safety limit on number of parts
                "enable_ocr": True,  # Enable OCR for low/zero-text pages (unstructured hi_res)
            },
            "concurrency": {
                "pass_a": 4,  # Pass A concurrency
                "pass_b": 6,  # Pass B concurrency  
                "pass_c": 2,  # Pass C concurrency
                "rate_limit_delay_ms": 100,  # Delay between third-party API calls
                "max_retries": 3,  # Max retries for failed operations
            },
            "quality": {
                "section_title_coverage_threshold": 0.98,  # 98% coverage required
                "integrity_validation_enabled": True,
                "dictionary_canonicalization_enabled": True,
                "procedure_extraction_enabled": False,  # Feature flag for E4
            },
            "logging": {
                "split_events": True,  # Log preprocessing split events
                "concurrency_metrics": True,  # Log threading metrics
                "integrity_violations": True,  # Log integrity check failures
            }
        }
        
        # Environment-specific overrides
        env_overrides = {
            "dev": {
                "preprocessor": {"size_threshold_mb": 30.0, "enable_ocr": True},  # Lower threshold for dev
                "concurrency": {"pass_a": 2, "pass_b": 3, "pass_c": 1},  # Conservative dev settings
            },
            "test": {
                "preprocessor": {"size_threshold_mb": 25.0, "enable_ocr": True},  # Even lower for test fixtures
                "concurrency": {"pass_a": 1, "pass_b": 1, "pass_c": 1},  # Single-threaded for determinism
                "quality": {"procedure_extraction_enabled": False},  # Disable experimental features
            },
            "prod": {
                "preprocessor": {"size_threshold_mb": 50.0, "enable_ocr": True},  # Higher threshold for production
                "concurrency": {"pass_a": 8, "pass_b": 12, "pass_c": 4},  # More aggressive prod settings
                "quality": {"procedure_extraction_enabled": True},  # Enable all features in prod
            }
        }
        
        # Apply environment overrides
        if self.env in env_overrides:
            config = self._merge_config(config, env_overrides[self.env])
        
        # Apply environment variable overrides
        config = self._apply_env_overrides(config)
        
        logger.info(f"FR1 configuration loaded for environment: {self.env}")
        logger.debug(f"Configuration: {config}")
        
        return config
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides with FR1_ prefix"""
        env_mappings = {
            "FR1_SIZE_THRESHOLD_MB": ("preprocessor", "size_threshold_mb", float),
            "FR1_ENABLE_OCR": ("preprocessor", "enable_ocr", lambda x: x.lower() == "true"),
            "FR1_MAX_PAGES_PER_PART": ("preprocessor", "max_pages_per_part", int),
            "FR1_PASS_A_CONCURRENCY": ("concurrency", "pass_a", int),
            "FR1_PASS_B_CONCURRENCY": ("concurrency", "pass_b", int),
            "FR1_PASS_C_CONCURRENCY": ("concurrency", "pass_c", int),
            "FR1_RATE_LIMIT_DELAY_MS": ("concurrency", "rate_limit_delay_ms", int),
            "FR1_SECTION_COVERAGE_THRESHOLD": ("quality", "section_title_coverage_threshold", float),
            "FR1_PROCEDURE_EXTRACTION": ("quality", "procedure_extraction_enabled", lambda x: x.lower() == "true"),
        }
        
        for env_var, (section, key, converter) in env_mappings.items():
            if env_value := os.getenv(env_var):
                try:
                    config[section][key] = converter(env_value)
                    logger.info(f"Applied env override: {env_var}={env_value}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid env override {env_var}={env_value}: {e}")
        
        return config
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        return self._config.get(section, {}).get(key, default)
    
    def get_preprocessor_config(self) -> Dict[str, Any]:
        """Get preprocessor configuration"""
        return self._config["preprocessor"]
    
    def get_concurrency_config(self) -> Dict[str, Any]:
        """Get concurrency configuration"""
        return self._config["concurrency"]
    
    def get_quality_config(self) -> Dict[str, Any]:
        """Get quality configuration"""
        return self._config["quality"]
    
    def should_split_by_size(self, file_size_mb: float) -> bool:
        """Determine if file should be split based on size threshold"""
        threshold = self.get("preprocessor", "size_threshold_mb", 40.0)
        should_split = file_size_mb >= threshold
        
        if self.get("logging", "split_events", True):
            if should_split:
                logger.info(f"Size-based splitting triggered: {file_size_mb:.1f}MB >= {threshold}MB")
            else:
                logger.debug(f"Size-based splitting not needed: {file_size_mb:.1f}MB < {threshold}MB")
        
        return should_split
    
    def validate_config(self) -> bool:
        """Validate configuration values are within acceptable ranges"""
        issues = []
        
        # Validate thresholds
        threshold = self.get("preprocessor", "size_threshold_mb", 0)
        if threshold <= 0:
            issues.append(f"Invalid size threshold: {threshold}MB (must be > 0)")
        
        # Validate concurrency limits
        for pass_name in ["pass_a", "pass_b", "pass_c"]:
            concurrency = self.get("concurrency", pass_name, 0)
            if not (1 <= concurrency <= 32):
                issues.append(f"Invalid {pass_name} concurrency: {concurrency} (must be 1-32)")
        
        # Validate quality thresholds
        coverage = self.get("quality", "section_title_coverage_threshold", 0)
        if not (0.0 <= coverage <= 1.0):
            issues.append(f"Invalid section coverage threshold: {coverage} (must be 0.0-1.0)")
        
        if issues:
            for issue in issues:
                logger.error(f"Configuration validation error: {issue}")
            return False
        
        logger.info("FR1 configuration validation passed")
        return True


# Global configuration instance
_config_instance: Optional[FR1Config] = None

def get_fr1_config(env: str = None) -> FR1Config:
    """Get global FR1 configuration instance"""
    global _config_instance
    
    if _config_instance is None or (env and _config_instance.env != env):
        # Determine environment from various sources
        if not env:
            env = os.getenv("TTRPG_ENV", "dev")
        
        _config_instance = FR1Config(env)
        
        # Validate configuration on creation
        if not _config_instance.validate_config():
            logger.error("FR1 configuration validation failed - using defaults")
    
    return _config_instance
