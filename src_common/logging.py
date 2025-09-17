"""Compatibility shim for legacy imports expecting `src_common.logging`.
Delegates to the unified structured logging utilities in `ttrpg_logging`.
"""

from .ttrpg_logging import (
    setup_logging,
    get_logger,
    LogContext,
    log_function_call,
    sanitize_for_logging,
    jlog,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "LogContext",
    "log_function_call",
    "sanitize_for_logging",
    "jlog",
]
