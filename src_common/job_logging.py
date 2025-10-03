"""
Job Logging Bridge - Route logs to both container logs and job-specific log files.

This module provides unified logging that ensures observability at both the
container level (for operators) and job level (for users tracking specific jobs).
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from .ttrpg_logging import get_logger

# Module-level logger for container logs
container_logger = get_logger(__name__)


def log_to_job(
    message: str,
    log_file_path: Optional[Path] = None,
    level: str = "info",
    pass_name: Optional[str] = None
) -> None:
    """
    Log message to both container logger and job-specific log file.

    This ensures visibility at both levels:
    - Container logs: For operators monitoring service health
    - Job logs: For users tracking specific ingestion jobs

    Args:
        message: Log message to write
        log_file_path: Path to job-specific log file (optional)
        level: Log level (info, debug, warning, error)
        pass_name: Pass identifier (A-G) for context

    Example:
        log_to_job("Processing chunk 1/100", log_file_path, "info", "C")
    """
    # Add timestamp and pass context
    timestamp = datetime.now().isoformat()
    if pass_name:
        formatted_message = f"[{timestamp}] Pass {pass_name}: {message}"
    else:
        formatted_message = f"[{timestamp}] {message}"

    # Log to container (for operators)
    log_func = getattr(container_logger, level, container_logger.info)
    log_func(message)  # Don't duplicate timestamp (logger adds it)

    # Log to job file (for users)
    if log_file_path:
        try:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file_path, 'a', encoding='utf-8') as f:
                f.write(formatted_message + "\n")
                f.flush()  # Ensure immediate write for real-time observability
        except Exception as e:
            container_logger.error(f"Failed to write to job log {log_file_path}: {e}")


def log_heartbeat(
    current: int,
    total: int,
    item_name: str,
    log_file_path: Optional[Path] = None,
    pass_name: Optional[str] = None,
    last_log_time: float = 0,
    heartbeat_interval: float = 8.0
) -> float:
    """
    Log progress heartbeat if enough time has passed.

    Ensures no silence >10 seconds by emitting progress updates.

    Args:
        current: Current item index (1-based)
        total: Total items to process
        item_name: Name/description of current item
        log_file_path: Path to job log file
        pass_name: Pass identifier (A-G)
        last_log_time: Timestamp of last heartbeat
        heartbeat_interval: Minimum seconds between heartbeats (default 8s)

    Returns:
        Updated last_log_time (use this for next call)

    Example:
        import time
        last_log = 0
        for idx, chunk in enumerate(chunks, 1):
            last_log = log_heartbeat(idx, len(chunks), chunk.name,
                                    log_file_path, "C", last_log)
            process(chunk)
    """
    import time
    current_time = time.time()

    if current_time - last_log_time >= heartbeat_interval:
        progress_pct = (current / total * 100) if total > 0 else 0
        message = f"Processing {current}/{total} ({progress_pct:.1f}%): {item_name}"
        log_to_job(message, log_file_path, "info", pass_name)
        return current_time

    return last_log_time


def log_upsert_result(
    operation: str,  # "NEW", "CHANGED", "UNCHANGED", "DELETED"
    item_id: str,
    item_type: str,  # "chunk", "term", "vector", "edge"
    log_file_path: Optional[Path] = None,
    pass_name: Optional[str] = None,
    details: Optional[str] = None
) -> None:
    """
    Log database upsert operation with standardized format.

    Enables validation of what actually changed in the database.

    Args:
        operation: One of NEW, CHANGED, UNCHANGED, DELETED
        item_id: Identifier of the item
        item_type: Type of item (chunk, term, vector, edge)
        log_file_path: Path to job log file
        pass_name: Pass identifier (A-G)
        details: Optional additional details (e.g., "512 chars, confidence=0.95")

    Example:
        log_upsert_result("NEW", "chunk_123", "chunk", log_file_path, "C",
                         "512 chars, page 45")
    """
    # Emoji indicators for visual scanning
    emoji_map = {
        "NEW": "📝",
        "CHANGED": "✏️",
        "UNCHANGED": "✓",
        "DELETED": "🗑️"
    }

    emoji = emoji_map.get(operation, "•")
    message = f"{emoji} {operation}: {item_type} '{item_id}'"

    if details:
        message += f" ({details})"

    # Log at appropriate level
    level = "info" if operation in ["NEW", "CHANGED", "DELETED"] else "debug"
    log_to_job(message, log_file_path, level, pass_name)


def log_pass_start(
    pass_name: str,
    description: str,
    log_file_path: Optional[Path] = None
) -> None:
    """Log start of pass execution."""
    message = f"{'='*60}\n{description}\n{'='*60}"
    log_to_job(message, log_file_path, "info", pass_name)


def log_pass_complete(
    pass_name: str,
    duration_seconds: float,
    stats: dict,
    log_file_path: Optional[Path] = None
) -> None:
    """Log completion of pass with summary statistics."""
    stats_str = ", ".join(f"{k}={v}" for k, v in stats.items())
    message = f"Completed in {duration_seconds:.2f}s - {stats_str}"
    log_to_job(message, log_file_path, "info", pass_name)
    log_to_job("="*60, log_file_path, "info", pass_name)
