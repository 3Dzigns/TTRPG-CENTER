# src_common/admin/logs.py
"""
Log Management Service - FR-008
Centralized viewing, searching, filtering, and downloading of logs
"""

import os
import glob
import json
import asyncio
import zipfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import stat

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class LogEntry:
    """Individual log entry information"""
    job_id: str
    job_type: str  # 'ad-hoc' or 'nightly'
    lane: str
    status: str  # 'running', 'completed', 'failed', 'pending'
    pid: Optional[int]
    start_time: Optional[float]
    end_time: Optional[float]
    duration_seconds: Optional[float]
    file_size_bytes: int
    sources: List[str]
    environment: str
    log_file: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdminLogService:
    """Log Management Service for admin interface"""

    def __init__(self):
        self.base_log_dir = Path("env")

    async def get_logs_overview(self,
                              environment: Optional[str] = None,
                              status: Optional[str] = None,
                              job_type: Optional[str] = None,
                              search: Optional[str] = None,
                              date_from: Optional[str] = None,
                              date_to: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive logs overview with filtering"""
        try:
            logs = await self._scan_log_files(environment, status, job_type, search, date_from, date_to)

            # Calculate statistics
            total_count = len(logs)
            running_count = len([log for log in logs if log.status == 'running'])
            total_size_bytes = sum(log.file_size_bytes for log in logs)

            return {
                "total_count": total_count,
                "running_count": running_count,
                "total_size_bytes": total_size_bytes,
                "logs": [log.to_dict() for log in logs]
            }

        except Exception as e:
            logger.error(f"Error getting logs overview: {e}")
            return {
                "total_count": 0,
                "running_count": 0,
                "total_size_bytes": 0,
                "logs": [],
                "error": str(e)
            }

    async def _scan_log_files(self,
                            environment: Optional[str] = None,
                            status: Optional[str] = None,
                            job_type: Optional[str] = None,
                            search: Optional[str] = None,
                            date_from: Optional[str] = None,
                            date_to: Optional[str] = None) -> List[LogEntry]:
        """Scan log directories and build log entries"""
        logs = []

        # Determine which environments to scan
        envs_to_scan = [environment] if environment and environment != 'all' else ['dev', 'test', 'prod']

        for env in envs_to_scan:
            env_log_dir = self.base_log_dir / env / "logs"
            if not env_log_dir.exists():
                continue

            # Scan for log files
            log_patterns = [
                "nightly_ingestion_*.log",
                "adhoc_ingestion_*.log",
                "ingestion_*.log",
                "*.log"
            ]

            for pattern in log_patterns:
                for log_file in env_log_dir.glob(pattern):
                    try:
                        log_entry = await self._parse_log_file(log_file, env)
                        if log_entry and self._matches_filters(log_entry, status, job_type, search, date_from, date_to):
                            logs.append(log_entry)
                    except Exception as e:
                        logger.warning(f"Error parsing log file {log_file}: {e}")

        # Sort by start time (newest first)
        logs.sort(key=lambda x: x.start_time or 0, reverse=True)

        return logs

    async def _parse_log_file(self, log_file: Path, environment: str) -> Optional[LogEntry]:
        """Parse a log file and extract metadata"""
        try:
            file_stat = log_file.stat()
            file_size = file_stat.st_size

            # Extract job info from filename
            filename = log_file.name
            job_id = self._extract_job_id(filename)
            job_type = self._extract_job_type(filename)
            lane = self._extract_lane(log_file)

            # Try to determine status by checking if file is still being written
            status = await self._determine_log_status(log_file)

            # Extract timing information
            start_time, end_time = await self._extract_timing_info(log_file)
            duration_seconds = None
            if start_time and end_time:
                duration_seconds = end_time - start_time

            # Extract source information
            sources = await self._extract_sources(log_file)

            # Get PID if running
            pid = await self._get_running_pid(job_id, environment) if status == 'running' else None

            return LogEntry(
                job_id=job_id,
                job_type=job_type,
                lane=lane,
                status=status,
                pid=pid,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration_seconds,
                file_size_bytes=file_size,
                sources=sources,
                environment=environment,
                log_file=str(log_file)
            )

        except Exception as e:
            logger.error(f"Error parsing log file {log_file}: {e}")
            return None

    def _extract_lane(self, log_file: Path) -> str:
        """Derive the content lane from the log header if present."""
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as handle:
                head = handle.read(512)
            cleaned = head.replace('\r', ' ').replace('\n', ' ')
            for token in cleaned.split():
                if token.lower().startswith('lane='):
                    value = token.split('=', 1)[1].strip().upper()
                    if value in {'A', 'B', 'C'}:
                        return value
        except Exception:
            logger.debug("Unable to extract lane from %s", log_file)
        return 'A'

    def _extract_job_id(self, filename: str) -> str:
        """Extract job ID from log filename"""
        # Try to extract timestamp-based ID or use filename
        if 'nightly_ingestion_' in filename:
            # nightly_ingestion_2025-01-15_14-30-25.log -> nightly_2025-01-15_14-30-25
            parts = filename.replace('nightly_ingestion_', '').replace('.log', '')
            return f"nightly_{parts}"
        elif 'adhoc_ingestion_' in filename:
            # adhoc_ingestion_2025-01-15_14-30-25.log -> adhoc_2025-01-15_14-30-25
            parts = filename.replace('adhoc_ingestion_', '').replace('.log', '')
            return f"adhoc_{parts}"
        elif filename.startswith('job_'):
            return filename.replace('.log', '')
        else:
            # Use filename without extension
            return filename.replace('.log', '')

    def _extract_job_type(self, filename: str) -> str:
        """Extract job type from log filename"""
        if 'nightly' in filename.lower():
            return 'nightly'
        elif 'adhoc' in filename.lower():
            return 'ad-hoc'
        elif filename.lower().startswith('job_'):
            return 'ad-hoc'
        else:
            return 'ad-hoc'  # Default

    async def _determine_log_status(self, log_file: Path) -> str:
        """Determine if log is from running, completed, or failed job"""
        try:
            # Check if file was modified recently (within last 5 minutes)
            file_stat = log_file.stat()
            last_modified = datetime.fromtimestamp(file_stat.st_mtime)
            now = datetime.now()

            if (now - last_modified).total_seconds() < 300:  # 5 minutes
                # Check if file contains completion markers
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        # Read last few lines to check for completion
                        f.seek(max(0, file_stat.st_size - 2048))  # Last 2KB
                        tail = f.read()

                        if 'ingestion completed successfully' in tail.lower():
                            return 'completed'
                        elif 'error' in tail.lower() or 'failed' in tail.lower():
                            return 'failed'
                        else:
                            return 'running'
                except:
                    return 'running'
            else:
                # File hasn't been modified recently, check content for status
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if 'ingestion completed successfully' in content.lower():
                            return 'completed'
                        elif 'error' in content.lower() or 'failed' in content.lower():
                            return 'failed'
                        else:
                            return 'completed'  # Assume completed if no errors
                except:
                    return 'completed'

        except Exception as e:
            logger.warning(f"Error determining log status for {log_file}: {e}")
            return 'completed'

    async def _extract_timing_info(self, log_file: Path) -> tuple[Optional[float], Optional[float]]:
        """Extract start and end times from log file"""
        try:
            start_time = None
            end_time = None

            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # Get start time from first few lines
                f.seek(0)
                first_lines = []
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    first_lines.append(line)

                # Look for timestamp in first lines
                for line in first_lines:
                    if timestamp := self._extract_timestamp_from_line(line):
                        start_time = timestamp
                        break

                # Get end time from last few lines
                file_stat = log_file.stat()
                if file_stat.st_size > 1024:
                    f.seek(max(0, file_stat.st_size - 1024))  # Last 1KB
                    last_lines = f.readlines()

                    # Look for timestamp in last lines (reverse order)
                    for line in reversed(last_lines):
                        if timestamp := self._extract_timestamp_from_line(line):
                            end_time = timestamp
                            break

            return start_time, end_time

        except Exception as e:
            logger.warning(f"Error extracting timing info from {log_file}: {e}")
            return None, None

    def _extract_timestamp_from_line(self, line: str) -> Optional[float]:
        """Extract timestamp from a log line"""
        try:
            # Look for ISO format timestamp: 2025-01-15T14:30:25
            import re
            pattern = r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})'
            match = re.search(pattern, line)
            if match:
                timestamp_str = match.group(1)
                # Handle both T and space separators
                timestamp_str = timestamp_str.replace('T', ' ')
                dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                return dt.timestamp()
        except:
            pass
        return None

    async def _extract_sources(self, log_file: Path) -> List[str]:
        """Extract source files from log content"""
        sources = []
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(4096)  # First 4KB should contain source info

                # Look for common patterns indicating source files
                import re

                # Pattern for PDF files
                pdf_pattern = r'([^/\s]+\.pdf)'
                pdf_matches = re.findall(pdf_pattern, content, re.IGNORECASE)
                sources.extend(pdf_matches[:5])  # Limit to 5 sources

                # Pattern for file paths
                path_pattern = r'Processing\s+["\']?([^"\']+)["\']?'
                path_matches = re.findall(path_pattern, content, re.IGNORECASE)
                for match in path_matches[:3]:
                    if match not in sources:
                        sources.append(Path(match).name)

        except Exception as e:
            logger.warning(f"Error extracting sources from {log_file}: {e}")

        return sources if sources else ['Unknown']

    async def _get_running_pid(self, job_id: str, environment: str) -> Optional[int]:
        """Get PID for running job"""
        try:
            # This would need to be implemented based on how jobs are tracked
            # For now, return None as PID tracking would require job registry
            return None
        except:
            return None

    def _matches_filters(self, log_entry: LogEntry,
                        status: Optional[str] = None,
                        job_type: Optional[str] = None,
                        search: Optional[str] = None,
                        date_from: Optional[str] = None,
                        date_to: Optional[str] = None) -> bool:
        """Check if log entry matches all specified filters"""

        # Status filter
        if status and status != 'all' and log_entry.status != status:
            return False

        # Job type filter
        if job_type and job_type != 'all' and log_entry.job_type != job_type:
            return False

        # Search filter (job ID or sources)
        if search:
            search_lower = search.lower()
            if (search_lower not in log_entry.job_id.lower() and
                not any(search_lower in source.lower() for source in log_entry.sources)):
                return False

        # Date range filter
        if date_from or date_to:
            if not log_entry.start_time:
                return False

            log_date = datetime.fromtimestamp(log_entry.start_time).date()

            if date_from:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                if log_date < from_date:
                    return False

            if date_to:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                if log_date > to_date:
                    return False

        return True

    async def get_log_content(self, job_id: str, environment: str, lines: int = 1000) -> Dict[str, Any]:
        """Get log file content"""
        try:
            # Find the log file for this job
            env_log_dir = self.base_log_dir / environment / "logs"
            log_files = list(env_log_dir.glob("*.log"))

            target_file = None
            for log_file in log_files:
                if job_id in str(log_file):
                    target_file = log_file
                    break

            if not target_file or not target_file.exists():
                return {"content": "Log file not found", "error": "File not found"}

            # Read log content
            try:
                with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                    if lines == 0:  # All lines
                        content = f.read()
                    else:
                        # Read last N lines
                        lines_list = f.readlines()
                        content = ''.join(lines_list[-lines:])

                return {
                    "content": content,
                    "file_size": target_file.stat().st_size,
                    "last_modified": target_file.stat().st_mtime
                }

            except Exception as e:
                return {"content": f"Error reading log file: {e}", "error": str(e)}

        except Exception as e:
            logger.error(f"Error getting log content for {job_id}: {e}")
            return {"content": f"Error: {e}", "error": str(e)}

    async def get_job_status(self, job_id: str, environment: str) -> Dict[str, Any]:
        """Get current status of a job"""
        try:
            logs = await self._scan_log_files(environment)
            for log in logs:
                if log.job_id == job_id:
                    return {
                        "status": log.status,
                        "pid": log.pid,
                        "start_time": log.start_time,
                        "end_time": log.end_time
                    }

            return {"status": "not_found", "error": "Job not found"}

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return {"status": "error", "error": str(e)}

    async def export_logs(self, environment: Optional[str] = None) -> bytes:
        """Export logs as ZIP file"""
        try:
            import io

            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                # Determine which environments to include
                envs_to_export = [environment] if environment and environment != 'all' else ['dev', 'test', 'prod']

                for env in envs_to_export:
                    env_log_dir = self.base_log_dir / env / "logs"
                    if not env_log_dir.exists():
                        continue

                    # Add all log files from this environment
                    for log_file in env_log_dir.glob("*.log"):
                        try:
                            archive_path = f"{env}/{log_file.name}"
                            zip_file.write(log_file, archive_path)
                        except Exception as e:
                            logger.warning(f"Error adding {log_file} to export: {e}")

            zip_buffer.seek(0)
            return zip_buffer.getvalue()

        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            raise
