#!/usr/bin/env python3
"""
Log Cleanup Utility - Remove log files older than specified retention period

Usage:
  python scripts/cleanup_logs.py --retain 30 [--env dev] [--dry-run] [--verbose]

Features:
- Removes log files older than specified days based on file modification time
- Supports multiple environments (dev/test/prod)
- Dry-run mode for testing
- Detailed logging and statistics
- Safe deletion with error handling
- Windows Scheduler compatible

Examples:
  # Remove logs older than 30 days in dev environment
  python scripts/cleanup_logs.py --retain 30 --env dev
  
  # Preview what would be deleted (dry-run)
  python scripts/cleanup_logs.py --retain 7 --dry-run --verbose
  
  # Clean all environments, keep 14 days
  python scripts/cleanup_logs.py --retain 14 --env all
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add project root to Python path for imports
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src_common.ttrpg_logging import get_logger

logger = get_logger(__name__)


class LogCleanupResult:
    """Result of log cleanup operation"""
    
    def __init__(self):
        self.files_scanned = 0
        self.files_deleted = 0
        self.files_failed = 0
        self.bytes_freed = 0
        self.errors: List[str] = []
        self.deleted_files: List[str] = []
        self.failed_files: List[Tuple[str, str]] = []  # (file_path, error_message)
    
    def add_success(self, file_path: Path, file_size: int):
        """Record successful deletion"""
        self.files_deleted += 1
        self.bytes_freed += file_size
        self.deleted_files.append(str(file_path))
    
    def add_failure(self, file_path: Path, error_message: str):
        """Record failed deletion"""
        self.files_failed += 1
        self.failed_files.append((str(file_path), error_message))
        self.errors.append(f"{file_path}: {error_message}")
    
    def format_bytes(self, bytes_count: int) -> str:
        """Format bytes in human-readable form"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} TB"
    
    def get_summary(self) -> str:
        """Get formatted summary of cleanup results"""
        return (
            f"Cleanup Summary:\n"
            f"  Files scanned: {self.files_scanned}\n"
            f"  Files deleted: {self.files_deleted}\n"
            f"  Files failed: {self.files_failed}\n"
            f"  Space freed: {self.format_bytes(self.bytes_freed)}\n"
            f"  Errors: {len(self.errors)}"
        )


class LogCleanupManager:
    """Manages cleanup of log files based on retention policy"""
    
    def __init__(self, retain_days: int, dry_run: bool = False, verbose: bool = False):
        self.retain_days = retain_days
        self.dry_run = dry_run
        self.verbose = verbose
        self.logger = get_logger(__name__)
        
        # Calculate cutoff time
        cutoff_datetime = datetime.now() - timedelta(days=retain_days)
        self.cutoff_timestamp = cutoff_datetime.timestamp()
        
        self.logger.info(f"Log cleanup initialized:")
        self.logger.info(f"  Retention period: {retain_days} days")
        self.logger.info(f"  Cutoff date: {cutoff_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"  Dry run mode: {dry_run}")
    
    def get_log_directories(self, environment: str = "dev") -> List[Path]:
        """
        Get list of log directories to scan
        
        Args:
            environment: Environment to clean ("dev", "test", "prod", or "all")
            
        Returns:
            List of log directory paths
        """
        project_root = Path(__file__).resolve().parents[1]
        log_directories = []
        
        if environment == "all":
            environments = ["dev", "test", "prod"]
        else:
            environments = [environment]
        
        for env in environments:
            # Standard log directory
            env_log_dir = project_root / "env" / env / "logs"
            if env_log_dir.exists():
                log_directories.append(env_log_dir)
            
            # Check for additional log locations
            artifacts_log_dir = project_root / "artifacts" / "logs" / env
            if artifacts_log_dir.exists():
                log_directories.append(artifacts_log_dir)
        
        # Add root-level logs directory if it exists
        root_logs = project_root / "logs"
        if root_logs.exists():
            log_directories.append(root_logs)
        
        return log_directories
    
    def identify_log_files(self, log_directories: List[Path]) -> List[Path]:
        """
        Identify all log files in the specified directories
        
        Args:
            log_directories: List of directories to scan
            
        Returns:
            List of log file paths
        """
        log_files = []
        
        # Common log file patterns
        log_patterns = [
            "*.log",
            "*.log.*",  # Rotated logs like app.log.1
            "*_*.log",  # Date/time stamped logs
            "nightly_*.log",
            "bulk_ingest_*.log",
            "scheduler_*.log",
            "pipeline_*.log"
        ]
        
        for log_dir in log_directories:
            if not log_dir.exists():
                self.logger.warning(f"Log directory does not exist: {log_dir}")
                continue
            
            self.logger.info(f"Scanning log directory: {log_dir}")
            
            # Scan for log files using patterns
            dir_files = []
            for pattern in log_patterns:
                matches = list(log_dir.glob(pattern))
                dir_files.extend(matches)
            
            # Also scan subdirectories (one level deep)
            for subdir in log_dir.iterdir():
                if subdir.is_dir():
                    for pattern in log_patterns:
                        matches = list(subdir.glob(pattern))
                        dir_files.extend(matches)
            
            # Filter to only actual files (not directories)
            dir_log_files = [f for f in dir_files if f.is_file()]
            log_files.extend(dir_log_files)
            
            self.logger.info(f"Found {len(dir_log_files)} log files in {log_dir}")
        
        # Remove duplicates and sort
        unique_log_files = list(set(log_files))
        unique_log_files.sort()
        
        self.logger.info(f"Total unique log files found: {len(unique_log_files)}")
        return unique_log_files
    
    def filter_old_files(self, log_files: List[Path]) -> List[Tuple[Path, datetime, int]]:
        """
        Filter log files to only those older than retention period
        
        Args:
            log_files: List of log file paths
            
        Returns:
            List of tuples (file_path, modification_time, file_size) for old files
        """
        old_files = []
        
        for file_path in log_files:
            try:
                # Get file modification time
                file_stat = file_path.stat()
                mod_time = file_stat.st_mtime
                mod_datetime = datetime.fromtimestamp(mod_time)
                file_size = file_stat.st_size
                
                # Check if file is older than cutoff
                if mod_time < self.cutoff_timestamp:
                    old_files.append((file_path, mod_datetime, file_size))
                    
                    if self.verbose:
                        self.logger.info(f"File marked for deletion: {file_path}")
                        self.logger.info(f"  Modified: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.logger.info(f"  Size: {file_size} bytes")
                else:
                    if self.verbose:
                        self.logger.info(f"File retained: {file_path}")
                        self.logger.info(f"  Modified: {mod_datetime.strftime('%Y-%m-%d %H:%M:%S')} (newer than cutoff)")
                        
            except Exception as e:
                self.logger.error(f"Error checking file {file_path}: {e}")
                continue
        
        self.logger.info(f"Files older than {self.retain_days} days: {len(old_files)}")
        return old_files
    
    def delete_old_files(self, old_files: List[Tuple[Path, datetime, int]]) -> LogCleanupResult:
        """
        Delete old log files
        
        Args:
            old_files: List of (file_path, mod_time, file_size) tuples
            
        Returns:
            LogCleanupResult with deletion statistics
        """
        result = LogCleanupResult()
        result.files_scanned = len(old_files)
        
        if not old_files:
            self.logger.info("No files to delete")
            return result
        
        if self.dry_run:
            self.logger.info(f"DRY RUN: Would delete {len(old_files)} files")
            for file_path, mod_time, file_size in old_files:
                self.logger.info(f"  Would delete: {file_path}")
                self.logger.info(f"    Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info(f"    Size: {result.format_bytes(file_size)}")
                result.add_success(file_path, file_size)  # For statistics only
            return result
        
        # Actually delete files
        self.logger.info(f"Deleting {len(old_files)} old log files...")
        
        for file_path, mod_time, file_size in old_files:
            try:
                if self.verbose:
                    self.logger.info(f"Deleting: {file_path}")
                    self.logger.info(f"  Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.logger.info(f"  Size: {result.format_bytes(file_size)}")
                
                # Delete the file
                file_path.unlink()
                result.add_success(file_path, file_size)
                
            except Exception as e:
                error_msg = f"Failed to delete {file_path}: {e}"
                self.logger.error(error_msg)
                result.add_failure(file_path, str(e))
        
        return result
    
    def cleanup_logs(self, environment: str = "dev") -> LogCleanupResult:
        """
        Main cleanup method
        
        Args:
            environment: Environment to clean ("dev", "test", "prod", or "all")
            
        Returns:
            LogCleanupResult with cleanup statistics
        """
        self.logger.info(f"Starting log cleanup for environment: {environment}")
        
        try:
            # Get log directories
            log_directories = self.get_log_directories(environment)
            
            if not log_directories:
                self.logger.warning(f"No log directories found for environment: {environment}")
                return LogCleanupResult()
            
            # Find all log files
            log_files = self.identify_log_files(log_directories)
            
            if not log_files:
                self.logger.info("No log files found")
                return LogCleanupResult()
            
            # Filter to old files
            old_files = self.filter_old_files(log_files)
            
            # Delete old files
            result = self.delete_old_files(old_files)
            
            # Log summary
            self.logger.info("Log cleanup completed")
            self.logger.info(result.get_summary())
            
            if result.errors and not self.dry_run:
                self.logger.warning("Some files could not be deleted:")
                for error in result.errors[:10]:  # Show first 10 errors
                    self.logger.warning(f"  {error}")
                if len(result.errors) > 10:
                    self.logger.warning(f"  ... and {len(result.errors) - 10} more errors")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Log cleanup failed: {e}")
            result = LogCleanupResult()
            result.add_failure(Path("cleanup_operation"), str(e))
            return result


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Clean up old log files based on retention period",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Remove logs older than 30 days in dev environment
  python scripts/cleanup_logs.py --retain 30 --env dev
  
  # Preview what would be deleted (dry-run)
  python scripts/cleanup_logs.py --retain 7 --dry-run --verbose
  
  # Clean all environments, keep 14 days
  python scripts/cleanup_logs.py --retain 14 --env all
  
  # Windows Scheduler command (run weekly, keep 30 days):
  python "C:\\path\\to\\scripts\\cleanup_logs.py" --retain 30 --env all
        """
    )
    
    parser.add_argument(
        "--retain", 
        type=int, 
        required=True,
        help="Number of days to retain log files (files older than this will be deleted)"
    )
    
    parser.add_argument(
        "--env",
        choices=["dev", "test", "prod", "all"],
        default="dev",
        help="Environment to clean logs for (default: dev)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting files"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true", 
        help="Enable verbose logging (show details for each file)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point"""
    args = parse_arguments()
    
    # Configure logging level
    import logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Validate arguments
    if args.retain < 1:
        print("Error: --retain must be at least 1 day", file=sys.stderr)
        return 1
    
    if args.retain > 365:
        print("Warning: Retention period is very long (>365 days)", file=sys.stderr)
    
    try:
        # Create cleanup manager
        cleanup_manager = LogCleanupManager(
            retain_days=args.retain,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
        
        # Run cleanup
        result = cleanup_manager.cleanup_logs(args.env)
        
        # Print final summary
        print(result.get_summary())
        
        if args.dry_run:
            print(f"\nDRY RUN: No files were actually deleted")
            print(f"Would have freed: {result.format_bytes(result.bytes_freed)}")
        else:
            if result.files_deleted > 0:
                print(f"Successfully freed: {result.format_bytes(result.bytes_freed)}")
            
            if result.files_failed > 0:
                print(f"Warning: {result.files_failed} files could not be deleted")
        
        # Return appropriate exit code
        if result.files_failed > 0 and not args.dry_run:
            return 2  # Partial failure
        elif result.errors and not args.dry_run:
            return 1  # Errors occurred
        else:
            return 0  # Success
            
    except KeyboardInterrupt:
        print("\nCleanup interrupted by user", file=sys.stderr)
        return 130
        
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)