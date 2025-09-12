# src_common/artifact_preservation.py
"""
Artifact Preservation System - Manages Pass C artifact copying for bypassed processing

When Pass C is bypassed due to SHA matching, this system ensures that Pass D and E
still have access to the required artifacts from previous processing runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class ArtifactCopyResult:
    """Result of artifact copying operation"""
    success: bool
    artifacts_copied: int
    source_path: str
    destination_path: str
    error_message: Optional[str] = None
    copied_files: List[str] = None


class ArtifactPreservationManager:
    """Manages copying of Pass C artifacts for bypassed processing"""
    
    def __init__(self, environment: str):
        self.env = environment
        self.logger = get_logger(__name__)
    
    def identify_pass_c_artifacts(self, artifacts_dir: Path) -> List[Path]:
        """
        Identify Pass C artifacts that need to be preserved
        
        Args:
            artifacts_dir: Directory containing Pass C artifacts
            
        Returns:
            List of artifact file paths that Pass D/E depend on
        """
        artifacts = []
        
        if not artifacts_dir.exists():
            self.logger.warning(f"Artifacts directory not found: {artifacts_dir}")
            return artifacts
        
        # Pass C typically creates these artifacts that Pass D/E need:
        # 1. extracted_content.json - Raw extracted content
        # 2. chunks.json - Initial chunked content
        # 3. text_segments/ - Directory with text segments
        # 4. images/ - Directory with extracted images (if any)
        # 5. metadata.json - Extraction metadata
        
        expected_artifacts = [
            "extracted_content.json",
            "chunks.json", 
            "metadata.json",
            "manifest.json"
        ]
        
        # Check for expected files
        for artifact_name in expected_artifacts:
            artifact_path = artifacts_dir / artifact_name
            if artifact_path.exists():
                artifacts.append(artifact_path)
                self.logger.debug(f"Found Pass C artifact: {artifact_path}")
            else:
                self.logger.warning(f"Expected Pass C artifact not found: {artifact_path}")
        
        # Check for common directories
        expected_dirs = ["text_segments", "images", "tables"]
        for dir_name in expected_dirs:
            dir_path = artifacts_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Add all files in the directory
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        artifacts.append(file_path)
                        
        self.logger.info(f"Identified {len(artifacts)} Pass C artifacts in {artifacts_dir}")
        return artifacts
    
    def copy_artifacts_from_previous_run(self, source_artifacts_path: Path, 
                                       destination_artifacts_path: Path) -> ArtifactCopyResult:
        """
        Copy Pass C artifacts from a previous processing run to current job artifacts
        
        Args:
            source_artifacts_path: Path to previous run's artifacts
            destination_artifacts_path: Path to current job's artifacts directory
            
        Returns:
            ArtifactCopyResult with copy operation details
        """
        self.logger.info(f"Copying Pass C artifacts from {source_artifacts_path} to {destination_artifacts_path}")
        
        if not source_artifacts_path.exists():
            return ArtifactCopyResult(
                success=False,
                artifacts_copied=0,
                source_path=str(source_artifacts_path),
                destination_path=str(destination_artifacts_path),
                error_message=f"Source artifacts directory not found: {source_artifacts_path}"
            )
        
        # Ensure destination directory exists
        destination_artifacts_path.mkdir(parents=True, exist_ok=True)
        
        # Identify artifacts to copy
        artifacts_to_copy = self.identify_pass_c_artifacts(source_artifacts_path)
        
        if not artifacts_to_copy:
            return ArtifactCopyResult(
                success=False,
                artifacts_copied=0,
                source_path=str(source_artifacts_path),
                destination_path=str(destination_artifacts_path),
                error_message="No Pass C artifacts found to copy",
                copied_files=[]
            )
        
        copied_files = []
        failed_copies = []
        
        try:
            for artifact_path in artifacts_to_copy:
                # Calculate relative path from source artifacts directory
                relative_path = artifact_path.relative_to(source_artifacts_path)
                dest_path = destination_artifacts_path / relative_path
                
                # Ensure destination directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    # Copy the file
                    shutil.copy2(artifact_path, dest_path)
                    copied_files.append(str(relative_path))
                    self.logger.debug(f"Copied artifact: {relative_path}")
                    
                except Exception as e:
                    failed_copies.append(f"{relative_path}: {str(e)}")
                    self.logger.error(f"Failed to copy {artifact_path}: {e}")
            
            if failed_copies:
                error_msg = f"Failed to copy {len(failed_copies)} artifacts: {'; '.join(failed_copies[:3])}"
                if len(failed_copies) > 3:
                    error_msg += f" and {len(failed_copies) - 3} more"
            else:
                error_msg = None
            
            success = len(copied_files) > 0
            
            result = ArtifactCopyResult(
                success=success,
                artifacts_copied=len(copied_files),
                source_path=str(source_artifacts_path),
                destination_path=str(destination_artifacts_path),
                error_message=error_msg,
                copied_files=copied_files
            )
            
            if success:
                self.logger.info(f"Successfully copied {len(copied_files)} Pass C artifacts")
            else:
                self.logger.error(f"Failed to copy any artifacts - {error_msg}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Unexpected error during artifact copying: {e}")
            return ArtifactCopyResult(
                success=False,
                artifacts_copied=len(copied_files),
                source_path=str(source_artifacts_path),
                destination_path=str(destination_artifacts_path),
                error_message=f"Unexpected error: {str(e)}",
                copied_files=copied_files
            )
    
    def validate_required_artifacts_exist(self, artifacts_dir: Path) -> Dict[str, bool]:
        """
        Validate that required Pass C artifacts exist for Pass D/E processing
        
        Args:
            artifacts_dir: Directory to check for required artifacts
            
        Returns:
            Dictionary mapping artifact names to their existence status
        """
        required_artifacts = {
            "extracted_content.json": False,
            "chunks.json": False,
            "metadata.json": False,
            "manifest.json": False
        }
        
        if not artifacts_dir.exists():
            self.logger.warning(f"Artifacts directory does not exist: {artifacts_dir}")
            return required_artifacts
        
        for artifact_name in required_artifacts.keys():
            artifact_path = artifacts_dir / artifact_name
            required_artifacts[artifact_name] = artifact_path.exists()
            
        missing_artifacts = [name for name, exists in required_artifacts.items() if not exists]
        
        if missing_artifacts:
            self.logger.warning(f"Missing required artifacts in {artifacts_dir}: {missing_artifacts}")
        else:
            self.logger.info(f"All required Pass C artifacts found in {artifacts_dir}")
            
        return required_artifacts
    
    def create_bypass_marker(self, artifacts_dir: Path, source_hash: str, bypass_reason: str) -> bool:
        """
        Create a marker file indicating that Pass C was bypassed
        
        Args:
            artifacts_dir: Artifacts directory for current job
            source_hash: SHA hash of the source file
            bypass_reason: Reason why Pass C was bypassed
            
        Returns:
            True if marker created successfully
        """
        try:
            marker_path = artifacts_dir / "pass_c_bypassed.json"
            marker_data = {
                "pass_c_bypassed": True,
                "source_hash": source_hash,
                "bypass_reason": bypass_reason,
                "bypass_timestamp": str(Path(__file__).stat().st_mtime),
                "environment": self.env
            }
            
            import json
            with marker_path.open('w', encoding='utf-8') as f:
                json.dump(marker_data, f, indent=2)
                
            self.logger.info(f"Created Pass C bypass marker: {marker_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create bypass marker: {e}")
            return False
    
    def get_artifacts_path_for_job(self, job_id: str) -> Path:
        """
        Get the expected artifacts path for a job ID
        
        Args:
            job_id: Job identifier
            
        Returns:
            Path to job's artifacts directory
        """
        # Construct path based on standard artifacts structure
        project_root = Path(__file__).resolve().parents[1]
        artifacts_path = project_root / "artifacts" / "ingest" / self.env / job_id
        return artifacts_path


def get_artifact_manager(environment: str) -> ArtifactPreservationManager:
    """
    Factory function to get configured artifact preservation manager
    
    Args:
        environment: Environment (dev/test/prod)
        
    Returns:
        Configured ArtifactPreservationManager instance
    """
    return ArtifactPreservationManager(environment)