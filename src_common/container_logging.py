# container_logging.py
"""
FR-006: Container Logging System
Enhanced structured logging for containerized deployment with file rotation and cleanup
"""

import os
import sys
import json
import time
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from contextlib import contextmanager
import structlog

# Configure structlog for structured JSON logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)


class ContainerLogManager:
    """Enhanced log manager for containerized environment"""
    
    def __init__(self):
        self.log_directory = Path(os.getenv("LOG_DIRECTORY", "/var/log/ttrpg"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.app_env = os.getenv("APP_ENV", "dev")
        
        # Ensure log directory exists
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging with file handlers and rotation"""
        try:
            # Root logger configuration
            root_logger = logging.getLogger()
            root_logger.setLevel(getattr(logging, self.log_level))
            
            # Clear existing handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # Console handler (for container stdout)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.log_level))
            console_formatter = self._create_json_formatter()
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
            
            # File handler with rotation
            log_file = self.log_directory / "ttrpg_app.log"
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=str(log_file),
                when='midnight',
                interval=1,
                backupCount=7,  # Keep 7 days of logs by default
                encoding='utf-8',
                utc=True
            )
            file_handler.setLevel(getattr(logging, self.log_level))
            file_handler.setFormatter(console_formatter)
            root_logger.addHandler(file_handler)
            
            # Error-specific file handler
            error_log_file = self.log_directory / "ttrpg_error.log"
            error_handler = logging.handlers.TimedRotatingFileHandler(
                filename=str(error_log_file),
                when='midnight',
                interval=1,
                backupCount=14,  # Keep 14 days of error logs
                encoding='utf-8',
                utc=True
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(console_formatter)
            root_logger.addHandler(error_handler)
            
            # Access log handler for HTTP requests
            access_log_file = self.log_directory / "ttrpg_access.log"
            self._setup_access_log(access_log_file)
            
            print(f"Container logging configured: {self.log_directory}", flush=True)
            
        except Exception as e:
            print(f"Failed to setup container logging: {e}", flush=True)
    
    def _create_json_formatter(self) -> logging.Formatter:
        """Create JSON formatter for structured logging"""
        return JsonLogFormatter()
    
    def _setup_access_log(self, access_log_file: Path) -> None:
        """Setup dedicated access log for HTTP requests"""
        try:
            access_logger = logging.getLogger("ttrpg.access")
            access_logger.setLevel(logging.INFO)
            
            # Don't propagate to root logger
            access_logger.propagate = False
            
            # Access log handler
            access_handler = logging.handlers.TimedRotatingFileHandler(
                filename=str(access_log_file),
                when='midnight',
                interval=1,
                backupCount=7,
                encoding='utf-8',
                utc=True
            )
            access_handler.setLevel(logging.INFO)
            access_handler.setFormatter(self._create_json_formatter())
            access_logger.addHandler(access_handler)
            
        except Exception as e:
            print(f"Failed to setup access logging: {e}", flush=True)
    
    def cleanup_old_logs(self, retention_days: int = 5) -> Dict[str, Any]:
        """
        Clean up log files older than retention period
        
        Args:
            retention_days: Number of days to retain logs
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            deleted_files = []
            deleted_size = 0
            errors = []
            
            # Find log files to clean up
            for log_file in self.log_directory.glob("*.log*"):
                try:
                    # Skip current day's log files
                    today_suffix = datetime.now().strftime("%Y-%m-%d")
                    if today_suffix in log_file.name and not log_file.name.endswith('.log'):
                        continue
                    
                    # Skip base log files (they're actively being written to)
                    if log_file.name in ['ttrpg_app.log', 'ttrpg_error.log', 'ttrpg_access.log']:
                        continue
                    
                    # Check file age
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        
                        deleted_files.append(log_file.name)
                        deleted_size += file_size
                        
                except Exception as e:
                    errors.append(f"Error deleting {log_file.name}: {e}")
            
            result = {
                "deleted_files": deleted_files,
                "deleted_count": len(deleted_files),
                "deleted_size_bytes": deleted_size,
                "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
                "retention_days": retention_days,
                "errors": errors
            }
            
            if deleted_files:
                structlog.get_logger().info(
                    "Log cleanup completed",
                    **result
                )
            
            return result
            
        except Exception as e:
            error_result = {"error": str(e), "retention_days": retention_days}
            structlog.get_logger().error("Log cleanup failed", **error_result)
            return error_result
    
    def get_log_info(self) -> Dict[str, Any]:
        """
        Get information about log files and configuration
        
        Returns:
            Dictionary with log information
        """
        try:
            log_files = []
            total_size = 0
            
            for log_file in self.log_directory.glob("*.log*"):
                try:
                    stat = log_file.stat()
                    log_files.append({
                        "name": log_file.name,
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    total_size += stat.st_size
                except Exception as e:
                    log_files.append({
                        "name": log_file.name,
                        "error": str(e)
                    })
            
            return {
                "log_directory": str(self.log_directory),
                "log_level": self.log_level,
                "app_env": self.app_env,
                "log_files": log_files,
                "total_files": len(log_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            return {"error": str(e)}


class JsonLogFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        try:
            # Base log entry
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # Add environment context
            log_entry["env"] = os.getenv("APP_ENV", "dev")
            log_entry["service"] = "ttrpg_center"
            
            # Add process info
            log_entry["process_id"] = os.getpid()
            
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            # Add extra fields from record
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                              'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
                              'exc_text', 'stack_info']:
                    extra_fields[key] = value
            
            if extra_fields:
                log_entry["extra"] = extra_fields
            
            return json.dumps(log_entry, default=str, ensure_ascii=False)
            
        except Exception as e:
            # Fallback to basic formatting if JSON fails
            return f'{{"timestamp": "{datetime.utcnow().isoformat()}Z", "level": "ERROR", "message": "Log formatting failed: {e}"}}'


class RequestLoggerMiddleware:
    """Middleware for logging HTTP requests"""
    
    def __init__(self):
        self.access_logger = logging.getLogger("ttrpg.access")
    
    async def __call__(self, request, call_next):
        """Log HTTP request and response"""
        start_time = time.time()
        
        # Get request info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log request
            self.access_logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query": str(request.url.query) if request.url.query else None,
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "duration_ms": round(duration * 1000, 2),
                    "request_size": request.headers.get("content-length"),
                    "response_size": response.headers.get("content-length")
                }
            )
            
            return response
            
        except Exception as e:
            # Log error
            duration = time.time() - start_time
            self.access_logger.error(
                f"{request.method} {request.url.path} - ERROR",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(e)
                }
            )
            raise


@contextmanager
def log_context(**kwargs):
    """Context manager for adding structured context to logs"""
    logger = structlog.get_logger()
    bound_logger = logger.bind(**kwargs)
    
    # Store original logger
    original_logger = structlog.get_logger()
    
    try:
        # Temporarily replace logger
        structlog._config.logger_factory._logger = bound_logger._logger
        yield bound_logger
    finally:
        # Restore original logger
        structlog._config.logger_factory._logger = original_logger._logger


# Global log manager instance
_log_manager: Optional[ContainerLogManager] = None


def get_log_manager() -> ContainerLogManager:
    """Get or create the global log manager instance"""
    global _log_manager
    if _log_manager is None:
        _log_manager = ContainerLogManager()
    return _log_manager


def get_structured_logger(name: str = None) -> Any:
    """Get a structured logger instance"""
    return structlog.get_logger(name)


# Initialize container logging on import
get_log_manager()