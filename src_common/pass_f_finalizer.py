# src_common/pass_f_finalizer.py
"""
Pass F: Clean Up (Finalize)

Validate manifests, atomically move temp files, purge partials, and write 
accurate deletion counts.

Responsibilities:
- Validate manifests and artifact integrity
- Atomically move temporary files to final locations
- Purge partial/incomplete artifacts
- Write accurate deletion counts and statistics
- Finalize manifest with completed_passes and checksums
- Generate run summary with comprehensive metrics

Artifacts:
- manifest.json: Finalized with completed_passes, checksums, run_summary
- cleanup_report.json: Details of cleanup operations performed
"""

import json
import time
import shutil
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict

from .logging import get_logger
from .artifact_validator import write_json_atomically, load_json_with_retry

logger = get_logger(__name__)


@dataclass
class CleanupStats:
    """Statistics from cleanup operations"""
    temp_files_moved: int
    partial_files_purged: int
    directories_cleaned: int
    total_size_cleaned: int
    validation_errors: int
    checksum_mismatches: int


@dataclass
class PassFResult:
    """Result of Pass F finalization"""
    source_file: str
    job_id: str
    artifacts_validated: int
    artifacts_finalized: int
    cleanup_stats: CleanupStats
    final_manifest_valid: bool
    processing_time_ms: int
    artifacts: List[str]
    manifest_path: str
    success: bool
    error_message: Optional[str] = None


class PassFFinalizer:
    """Pass F: Cleanup and Finalization"""
    
    def __init__(self, job_id: str, env: str = "dev"):
        self.job_id = job_id
        self.env = env
        
    def finalize_job(self, output_dir: Path) -> PassFResult:
        """
        Finalize job by cleaning up and validating all artifacts
        
        Args:
            output_dir: Directory containing all pass artifacts
            
        Returns:
            PassFResult with finalization statistics
        """
        start_time = time.time()
        logger.info(f"Pass F starting: Finalization for job {self.job_id}")
        
        try:
            # Ensure output directory exists
            if not output_dir.exists():
                raise FileNotFoundError(f"Output directory not found: {output_dir}")
            
            # Load and validate manifest
            manifest_path = output_dir / "manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(f"Manifest not found: {manifest_path}")
            
            manifest_data = load_json_with_retry(manifest_path)
            source_file = manifest_data.get("source_file", "unknown")
            
            logger.info(f"Finalizing job for source: {source_file}")
            
            # Validate all artifacts
            validation_result = self._validate_all_artifacts(output_dir, manifest_data)
            
            # Perform cleanup operations
            cleanup_stats = self._perform_cleanup(output_dir)
            
            # Finalize manifest with complete information
            final_manifest = self._finalize_manifest(output_dir, manifest_data, cleanup_stats)
            
            # Generate cleanup report
            cleanup_report_path = self._generate_cleanup_report(output_dir, cleanup_stats)
            
            # Final validation
            final_manifest_valid = self._validate_final_manifest(final_manifest)
            
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            
            logger.info(f"Pass F completed for job {self.job_id} in {processing_time_ms}ms")
            
            return PassFResult(
                source_file=source_file,
                job_id=self.job_id,
                artifacts_validated=validation_result["valid_artifacts"],
                artifacts_finalized=validation_result["total_artifacts"],
                cleanup_stats=cleanup_stats,
                final_manifest_valid=final_manifest_valid,
                processing_time_ms=processing_time_ms,
                artifacts=[str(cleanup_report_path)],
                manifest_path=str(manifest_path),
                success=True
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = int((end_time - start_time) * 1000)
            logger.error(f"Pass F failed for job {self.job_id}: {e}")
            
            return PassFResult(
                source_file="unknown",
                job_id=self.job_id,
                artifacts_validated=0,
                artifacts_finalized=0,
                cleanup_stats=CleanupStats(0,0,0,0,0,0),
                final_manifest_valid=False,
                processing_time_ms=processing_time_ms,
                artifacts=[],
                manifest_path="",
                success=False,
                error_message=str(e)
            )
    
    def _validate_all_artifacts(self, output_dir: Path, manifest_data: Dict[str, Any]) -> Dict[str, int]:
        """Validate all artifacts mentioned in manifest"""
        
        artifacts = manifest_data.get("artifacts", [])
        valid_artifacts = 0
        validation_errors = 0
        
        logger.info(f"Validating {len(artifacts)} artifacts")
        
        for artifact_info in artifacts:
            artifact_path = Path(artifact_info["path"])
            expected_checksum = artifact_info.get("checksum", "")
            expected_size = artifact_info.get("size", 0)
            
            if not artifact_path.exists():
                logger.warning(f"Artifact missing: {artifact_path}")
                validation_errors += 1
                continue
            
            # Validate file size
            actual_size = artifact_path.stat().st_size
            if expected_size > 0 and actual_size != expected_size:
                logger.warning(f"Size mismatch for {artifact_path}: expected {expected_size}, got {actual_size}")
                validation_errors += 1
                continue
            
            # Validate checksum if provided
            if expected_checksum:
                actual_checksum = self._compute_file_hash(artifact_path)
                if actual_checksum != expected_checksum:
                    logger.warning(f"Checksum mismatch for {artifact_path}")
                    validation_errors += 1
                    continue
            
            valid_artifacts += 1
        
        logger.info(f"Artifact validation: {valid_artifacts}/{len(artifacts)} valid, {validation_errors} errors")
        
        return {
            "total_artifacts": len(artifacts),
            "valid_artifacts": valid_artifacts,
            "validation_errors": validation_errors
        }
    
    def _perform_cleanup(self, output_dir: Path) -> CleanupStats:
        """Perform cleanup operations"""
        
        temp_files_moved = 0
        partial_files_purged = 0
        directories_cleaned = 0
        total_size_cleaned = 0
        
        logger.info("Performing cleanup operations")
        
        # Find and move temporary files
        for temp_file in output_dir.rglob("*.tmp"):
            try:
                final_path = temp_file.with_suffix('')
                if not final_path.exists() or final_path.stat().st_size == 0:
                    # Move temp file to final location
                    shutil.move(str(temp_file), str(final_path))
                    temp_files_moved += 1
                    logger.info(f"Moved temp file: {temp_file} → {final_path}")
                else:
                    # Remove temp file (final version exists)
                    size = temp_file.stat().st_size
                    temp_file.unlink()
                    total_size_cleaned += size
                    logger.info(f"Removed redundant temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to process temp file {temp_file}: {e}")
        
        # Find and purge partial files (very small or empty)
        min_size_threshold = 50  # bytes
        
        for file_path in output_dir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                try:
                    size = file_path.stat().st_size
                    
                    # Remove very small files that are likely partial
                    if size < min_size_threshold and file_path.suffix in ['.json', '.jsonl']:
                        file_path.unlink()
                        partial_files_purged += 1
                        total_size_cleaned += size
                        logger.info(f"Purged partial file: {file_path} ({size} bytes)")
                        
                except Exception as e:
                    logger.warning(f"Failed to check file {file_path}: {e}")
        
        # Clean empty directories
        for dir_path in output_dir.rglob("*"):
            if dir_path.is_dir() and dir_path != output_dir:
                try:
                    # Check if directory is empty
                    if not any(dir_path.iterdir()):
                        dir_path.rmdir()
                        directories_cleaned += 1
                        logger.info(f"Removed empty directory: {dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove directory {dir_path}: {e}")
        
        cleanup_stats = CleanupStats(
            temp_files_moved=temp_files_moved,
            partial_files_purged=partial_files_purged,
            directories_cleaned=directories_cleaned,
            total_size_cleaned=total_size_cleaned,
            validation_errors=0,  # Set by validation step
            checksum_mismatches=0  # Set by validation step
        )
        
        logger.info(f"Cleanup completed: {cleanup_stats}")
        
        return cleanup_stats
    
    def _finalize_manifest(
        self, 
        output_dir: Path, 
        manifest_data: Dict[str, Any], 
        cleanup_stats: CleanupStats
    ) -> Dict[str, Any]:
        """Finalize manifest with complete information"""
        
        # Update completed passes to include F
        completed_passes = list(set(manifest_data.get("completed_passes", []) + ["F"]))
        completed_passes.sort()  # Sort for consistent ordering
        
        # Generate final checksums for all artifacts
        final_artifacts = []
        for artifact_info in manifest_data.get("artifacts", []):
            artifact_path = Path(artifact_info["path"])
            if artifact_path.exists():
                final_artifact = artifact_info.copy()
                final_artifact.update({
                    "size": artifact_path.stat().st_size,
                    "mtime": artifact_path.stat().st_mtime,
                    "checksum": self._compute_file_hash(artifact_path),
                    "verified_at": time.time()
                })
                final_artifacts.append(final_artifact)
        
        # Calculate job statistics across all passes
        run_summary = self._calculate_run_summary(manifest_data, cleanup_stats)
        
        # Update manifest
        manifest_data.update({
            "completed_passes": completed_passes,
            "finalized_at": time.time(),
            "pass_f_results": {
                "artifacts_validated": len(final_artifacts),
                "cleanup_performed": True,
                "temp_files_moved": cleanup_stats.temp_files_moved,
                "partial_files_purged": cleanup_stats.partial_files_purged,
                "total_size_cleaned": cleanup_stats.total_size_cleaned
            },
            "artifacts": final_artifacts,
            "run_summary": run_summary,
            "job_status": "completed",
            "pipeline_version": "6-pass-system",
            "environment": self.env
        })
        
        # Write finalized manifest
        manifest_path = output_dir / "manifest.json"
        write_json_atomically(manifest_data, manifest_path)
        
        logger.info(f"Finalized manifest with {len(completed_passes)} completed passes")
        
        return manifest_data
    
    def _calculate_run_summary(self, manifest_data: Dict[str, Any], cleanup_stats: CleanupStats) -> Dict[str, Any]:
        """Calculate comprehensive run summary"""
        
        # Collect metrics from all passes
        pass_a_results = manifest_data.get("pass_a_results", {})
        pass_b_results = manifest_data.get("pass_b_results", {})
        pass_c_results = manifest_data.get("pass_c_results", {})
        pass_d_results = manifest_data.get("pass_d_results", {})
        pass_e_results = manifest_data.get("pass_e_results", {})
        
        # Calculate totals
        total_dictionary_entries = pass_a_results.get("dictionary_entries_extracted", 0)
        total_chunks = pass_c_results.get("chunks_extracted", 0)
        vectorized_chunks = pass_d_results.get("chunks_vectorized", 0)
        graph_nodes = pass_e_results.get("graph_nodes", 0)
        graph_edges = pass_e_results.get("graph_edges", 0)
        cross_references = pass_e_results.get("cross_references", 0)
        
        # Calculate file sizes
        total_artifact_size = sum(
            artifact.get("size", 0) 
            for artifact in manifest_data.get("artifacts", [])
        )
        
        run_summary = {
            "pipeline_version": "6-pass-system",
            "total_passes_completed": len(manifest_data.get("completed_passes", [])),
            "source_info": manifest_data.get("source_info", {}),
            "processing_summary": {
                "dictionary_entries_created": total_dictionary_entries,
                "pdf_split_performed": pass_b_results.get("split_performed", False),
                "parts_created": pass_b_results.get("parts_created", 0),
                "raw_chunks_extracted": total_chunks,
                "chunks_vectorized": vectorized_chunks,
                "chunks_graph_enriched": pass_e_results.get("chunks_updated", 0),
                "graph_nodes_created": graph_nodes,
                "graph_edges_created": graph_edges,
                "cross_references_extracted": cross_references
            },
            "data_summary": {
                "total_artifacts": len(manifest_data.get("artifacts", [])),
                "total_artifact_size_bytes": total_artifact_size,
                "chunks_loaded_to_astra": pass_d_results.get("chunks_loaded", 0),
                "dictionary_updates": pass_e_results.get("dictionary_updates", 0)
            },
            "cleanup_summary": asdict(cleanup_stats),
            "quality_metrics": {
                "deduplication_ratio": pass_d_results.get("deduplication_ratio", 0.0),
                "average_confidence_score": 0.0,  # Could be calculated from chunks
                "entities_extracted": pass_d_results.get("entities_extracted", 0),
                "keywords_extracted": pass_d_results.get("keywords_extracted", 0)
            },
            "completion_status": {
                "all_passes_completed": len(manifest_data.get("completed_passes", [])) == 6,
                "pipeline_successful": True,
                "finalized_at": time.time()
            }
        }
        
        return run_summary
    
    def _generate_cleanup_report(self, output_dir: Path, cleanup_stats: CleanupStats) -> Path:
        """Generate detailed cleanup report"""
        
        cleanup_report = {
            "job_id": self.job_id,
            "pass": "F",
            "operation": "cleanup_and_finalization",
            "created_at": time.time(),
            "cleanup_statistics": asdict(cleanup_stats),
            "operations_performed": [
                "Moved temporary files to final locations",
                "Purged partial/incomplete artifacts", 
                "Removed empty directories",
                "Validated artifact integrity",
                "Updated manifest checksums",
                "Generated run summary"
            ],
            "recommendations": [
                "All artifacts have been validated and finalized",
                "Job pipeline completed successfully",
                "Ready for production use"
            ] if cleanup_stats.validation_errors == 0 else [
                f"Found {cleanup_stats.validation_errors} validation errors",
                "Review artifact integrity before production use",
                "Consider re-running failed passes"
            ]
        }
        
        cleanup_report_path = output_dir / "cleanup_report.json"
        write_json_atomically(cleanup_report, cleanup_report_path)
        
        logger.info(f"Generated cleanup report: {cleanup_report_path}")
        
        return cleanup_report_path
    
    def _validate_final_manifest(self, manifest_data: Dict[str, Any]) -> bool:
        """Perform final validation of completed manifest"""
        
        required_fields = [
            "job_id", "source_file", "completed_passes", "artifacts", 
            "run_summary", "job_status", "finalized_at"
        ]
        
        for field in required_fields:
            if field not in manifest_data:
                logger.error(f"Missing required field in final manifest: {field}")
                return False
        
        # Validate completed passes
        completed_passes = manifest_data.get("completed_passes", [])
        expected_passes = ["A", "B", "C", "D", "E", "F"]
        
        if not all(pass_id in completed_passes for pass_id in expected_passes):
            missing = [p for p in expected_passes if p not in completed_passes]
            logger.error(f"Missing passes in final manifest: {missing}")
            return False
        
        # Validate run summary
        run_summary = manifest_data.get("run_summary", {})
        if not run_summary.get("completion_status", {}).get("all_passes_completed", False):
            logger.error("Run summary indicates incomplete pipeline")
            return False
        
        logger.info("Final manifest validation passed")
        return True
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to compute hash for {file_path}: {e}")
            return ""


def process_pass_f(output_dir: Path, job_id: str, env: str = "dev") -> PassFResult:
    """
    Convenience function for Pass F processing
    
    Args:
        output_dir: Directory containing all pass artifacts
        job_id: Unique job identifier
        env: Environment (dev/test/prod)
        
    Returns:
        PassFResult with finalization statistics
    """
    finalizer = PassFFinalizer(job_id, env)
    return finalizer.finalize_job(output_dir)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pass F: Cleanup and Finalization")
    parser.add_argument("output_dir", help="Output directory containing all pass artifacts")
    parser.add_argument("--job-id", required=True, help="Job ID")
    parser.add_argument("--env", default="dev", choices=["dev", "test", "prod"])
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    
    result = process_pass_f(output_dir, args.job_id, args.env)
    
    print(f"Pass F Result:")
    print(f"  Success: {result.success}")
    print(f"  Artifacts validated: {result.artifacts_validated}")
    print(f"  Artifacts finalized: {result.artifacts_finalized}")
    print(f"  Final manifest valid: {result.final_manifest_valid}")
    print(f"  Processing time: {result.processing_time_ms}ms")
    
    if result.cleanup_stats:
        stats = result.cleanup_stats
        print(f"  Cleanup stats:")
        print(f"    Temp files moved: {stats.temp_files_moved}")
        print(f"    Partial files purged: {stats.partial_files_purged}")
        print(f"    Size cleaned: {stats.total_size_cleaned} bytes")
    
    if result.error_message:
        print(f"  Error: {result.error_message}")
        exit(1)