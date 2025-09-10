"""
Artifact Validation and Integrity Checking for Ingestion Pipeline

This module provides validation, atomic file operations, and retry logic
for ingestion artifacts to prevent Pass B JSON parsing failures.
"""

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
import tempfile
import shutil

from .logging import get_logger

logger = get_logger(__name__)


class ArtifactValidationError(Exception):
    """Custom exception for artifact validation failures."""
    pass


def validate_json_artifact(file_path: Path, expected_schema_keys: Optional[set] = None) -> bool:
    """
    Validate that a JSON artifact file is valid and non-empty.
    
    Args:
        file_path: Path to JSON file to validate
        expected_schema_keys: Optional set of top-level keys that must be present
        
    Returns:
        True if valid, raises ArtifactValidationError if invalid
        
    Raises:
        ArtifactValidationError: If file is missing, empty, invalid JSON, or missing schema keys
    """
    if not file_path.exists():
        raise ArtifactValidationError(f"Artifact file does not exist: {file_path}")
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size == 0:
        raise ArtifactValidationError(f"Artifact file is empty (0 bytes): {file_path}")
    
    if file_size < 10:  # Minimum reasonable JSON size
        raise ArtifactValidationError(f"Artifact file is suspiciously small ({file_size} bytes): {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ArtifactValidationError(f"Invalid JSON in artifact {file_path}: {e}")
    except Exception as e:
        raise ArtifactValidationError(f"Failed to read artifact {file_path}: {e}")
    
    # Validate expected schema keys if provided
    if expected_schema_keys:
        if not isinstance(data, dict):
            raise ArtifactValidationError(f"Artifact {file_path} should contain a JSON object, got {type(data)}")
        
        missing_keys = expected_schema_keys - set(data.keys())
        if missing_keys:
            raise ArtifactValidationError(f"Artifact {file_path} missing required keys: {missing_keys}")
    
    logger.debug(f"Artifact validation passed: {file_path} ({file_size} bytes)")
    return True


def load_json_with_retry(file_path: Path, max_retries: int = 3, retry_delay_ms: int = 250, 
                         expected_schema_keys: Optional[set] = None) -> Dict[str, Any]:
    """
    Load JSON with retry logic to handle race conditions and transient failures.
    
    Args:
        file_path: Path to JSON file
        max_retries: Maximum number of retry attempts
        retry_delay_ms: Delay between retries in milliseconds
        expected_schema_keys: Optional set of top-level keys that must be present
        
    Returns:
        Loaded JSON data as dictionary
        
    Raises:
        ArtifactValidationError: If all retry attempts fail
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            # Validate before loading
            validate_json_artifact(file_path, expected_schema_keys=expected_schema_keys)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f"Successfully loaded JSON from {file_path} on attempt {attempt + 1}")
            return data
            
        except (json.JSONDecodeError, ArtifactValidationError, FileNotFoundError) as e:
            last_error = e
            
            if attempt < max_retries:
                delay_ms = retry_delay_ms * (2 ** attempt)  # Exponential backoff
                logger.warning(f"JSON load failed on attempt {attempt + 1}/{max_retries + 1}: {e}. Retrying in {delay_ms}ms...")
                time.sleep(delay_ms / 1000.0)
            else:
                logger.error(f"Failed to load JSON from {file_path} after {max_retries + 1} attempts")
    
    raise ArtifactValidationError(f"Failed to load JSON from {file_path} after {max_retries + 1} attempts. Last error: {last_error}")


def write_json_atomically(data: Any, target_path: Path) -> None:
    """
    Write JSON data atomically using temporary file and rename.
    
    Args:
        data: Data to write as JSON
        target_path: Final path for the file
        
    Raises:
        Exception: If write operation fails
    """
    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temporary file in same directory as target
    temp_suffix = f".tmp.{os.getpid()}.{int(time.time() * 1000000)}"
    temp_path = target_path.with_suffix(target_path.suffix + temp_suffix)
    
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk
        
        # Atomic rename
        if os.name == 'nt':  # Windows
            # Windows requires target to not exist for rename
            if target_path.exists():
                target_path.unlink()
        
        temp_path.rename(target_path)
        
        file_size = target_path.stat().st_size
        logger.debug(f"Atomically wrote JSON to {target_path} ({file_size} bytes)")
        
    except Exception as e:
        # Clean up temporary file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        raise e


def create_manifest(job_dir: Path, source_file: str, passes_completed: list, checksums: Dict[str, str]) -> None:
    """
    Create or update a manifest.json file for job integrity checking.
    
    Args:
        job_dir: Job artifacts directory
        source_file: Source PDF filename
        passes_completed: List of completed pass names
        checksums: Dictionary mapping filename to checksum
    """
    manifest_path = job_dir / "manifest.json"
    
    manifest_data = {
        "source_file": source_file,
        "created_at": time.time(),
        "passes_completed": passes_completed,
        "checksums": checksums,
        "build_version": "BUG-018-fix",  # Version identifier for compatibility
        "last_updated": time.time()
    }
    
    write_json_atomically(manifest_data, manifest_path)
    logger.info(f"Updated manifest for {source_file}: {passes_completed}")


def verify_manifest_integrity(job_dir: Path, required_pass: str) -> bool:
    """
    Verify that manifest and artifacts are consistent for resuming a pass.
    
    Args:
        job_dir: Job artifacts directory
        required_pass: Pass name that should be completed
        
    Returns:
        True if integrity check passes, False if re-run is needed
    """
    manifest_path = job_dir / "manifest.json"
    
    try:
        if not manifest_path.exists():
            logger.warning(f"No manifest found in {job_dir}, will re-run passes")
            return False
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        # Check if required pass was completed
        if required_pass not in manifest.get("passes_completed", []):
            logger.info(f"Pass {required_pass} not completed according to manifest, will re-run")
            return False
        
        # Verify file checksums
        checksums = manifest.get("checksums", {})
        for filename, expected_checksum in checksums.items():
            file_path = job_dir / filename
            if not file_path.exists():
                logger.warning(f"Artifact file {filename} missing, will re-run passes")
                return False
            
            actual_checksum = calculate_file_checksum(file_path)
            if actual_checksum != expected_checksum:
                logger.warning(f"Checksum mismatch for {filename}, will re-run passes")
                return False
        
        logger.debug(f"Manifest integrity check passed for {job_dir}")
        return True
        
    except Exception as e:
        logger.warning(f"Error checking manifest integrity in {job_dir}: {e}, will re-run passes")
        return False


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem usage, handling special characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for all filesystems
    """
    # Remove file extension for processing
    name, ext = os.path.splitext(filename)
    
    # Replace problematic characters
    sanitized = name
    sanitized = sanitized.replace("'", "_")  # Apostrophes
    sanitized = sanitized.replace('"', "_")  # Quotes
    sanitized = sanitized.replace("(", "_")  # Parentheses
    sanitized = sanitized.replace(")", "_")
    sanitized = sanitized.replace(" ", "_")  # Spaces
    sanitized = sanitized.replace("&", "_and_")  # Ampersands
    
    # Remove other special characters that could cause issues
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Ensure not empty
    if not sanitized:
        sanitized = "unknown"
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100].rstrip('_')
    
    return sanitized.lower() + ext.lower()