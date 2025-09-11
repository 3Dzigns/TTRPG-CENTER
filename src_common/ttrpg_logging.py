# src_common/logging.py
"""
Structured JSON logging utility for TTRPG Center.
Provides consistent, environment-aware logging across all components.
"""

import json
import logging as _logging
import logging.config as _logging_config
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from pythonjsonlogger import jsonlogger  # type: ignore
    _HAVE_JSONLOGGER = True
except Exception:
    jsonlogger = None  # type: ignore
    _HAVE_JSONLOGGER = False


def jlog(level: str, msg: str, **fields) -> None:
    """
    Quick structured logging function for simple use cases.
    
    Args:
        level: Log level (INFO, ERROR, WARNING, DEBUG)
        msg: Log message
        **fields: Additional fields to include in the log record
    """
    record = {
        "timestamp": time.time(),
        "level": level.upper(),
        "message": msg,
        "environment": os.getenv('APP_ENV', 'dev'),
        **fields
    }
    
    # Remove any None values
    record = {k: v for k, v in record.items() if v is not None}
    
    # Write to stdout for console capture
    print(json.dumps(record), flush=True)


if _HAVE_JSONLOGGER:
    class TTRPGJsonFormatter(jsonlogger.JsonFormatter):
        """Custom JSON formatter that adds TTRPG-specific context."""

        def add_fields(self, log_record: Dict[str, Any], record: _logging.LogRecord, message_dict: Dict[str, Any]) -> None:
            super().add_fields(log_record, record, message_dict)

            # Add standard fields
            log_record['timestamp'] = time.time()
            log_record['environment'] = os.getenv('APP_ENV', 'dev')
            log_record['component'] = getattr(record, 'component', 'unknown')

            # Add trace information if available
            if hasattr(record, 'trace_id'):
                log_record['trace_id'] = record.trace_id
            if hasattr(record, 'user_id'):
                log_record['user_id'] = record.user_id
            if hasattr(record, 'session_id'):
                log_record['session_id'] = record.session_id

            # Add performance metrics if available
            if hasattr(record, 'duration_ms'):
                log_record['duration_ms'] = record.duration_ms
            if hasattr(record, 'tokens'):
                log_record['tokens'] = record.tokens
            if hasattr(record, 'model'):
                log_record['model'] = record.model
else:
    class TTRPGJsonFormatter(_logging.Formatter):
        """Fallback formatter when python-json-logger is unavailable."""

        def format(self, record: _logging.LogRecord) -> str:
            # Simple line format with key context; used only if 'json' formatter selected.
            env = os.getenv('APP_ENV', 'dev')
            ts = f"{time.time():.3f}"
            msg = super().format(record)
            return f"{ts} {record.name} {record.levelname} [{env}] {msg}"


def setup_logging(config_path: Optional[Path] = None, log_file: Optional[Path] = None) -> _logging.Logger:
    """
    Set up logging configuration for the TTRPG Center application.
    
    Args:
        config_path: Path to logging configuration file. If None, uses default config.
        log_file: Path to log file. If None, logs only to console.
        
    Returns:
        Configured logger instance
    """
    env = os.getenv('APP_ENV', 'dev')
    # Respect LOG_LEVEL if provided
    level_name = os.getenv('LOG_LEVEL', 'INFO').upper()
    level_value = getattr(_logging, level_name, _logging.INFO)
    
    # Prepare handlers list
    handlers_list = ['console']
    handlers_config = {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if env != 'dev' else 'console',
            'level': level_name,
            'stream': 'ext://sys.stdout'
        }
    }
    
    # Add file handler if log_file is specified
    if log_file:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        handlers_config['file'] = {
            'class': 'logging.FileHandler',
            'filename': str(log_file),
            'formatter': 'json' if env != 'dev' else 'console',
            'level': level_name,
            'mode': 'a',
            'encoding': 'utf-8'
        }
        handlers_list.append('file')

    # Default logging configuration
    default_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': TTRPGJsonFormatter,
                'format': '%(timestamp)s %(name)s %(levelname)s %(message)s'
            },
            'console': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': handlers_config,
        'root': {
            'level': level_name,
            'handlers': handlers_list
        },
        'loggers': {
            'ttrpg': {
                'level': 'DEBUG' if env == 'dev' else 'INFO',
                # Let records propagate to root so test caplog can capture
                'handlers': [],
                'propagate': True
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': handlers_list,
                'propagate': False
            },
            'fastapi': {
                'level': 'INFO',
                'handlers': handlers_list, 
                'propagate': False
            }
        }
    }
    
    # Try to load config from file if specified
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                
            # Add file handler if logs directory exists
            log_dir = Path(f"env/{env}/logs")
            if log_dir.exists():
                file_config['handlers']['file'] = {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(log_dir / 'app.log'),
                    'formatter': 'json',
                    'level': 'INFO',
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5
                }
                # Add file handler to all loggers
                for logger_config in file_config.get('loggers', {}).values():
                    if 'handlers' in logger_config:
                        logger_config['handlers'].append('file')
                file_config['root']['handlers'].append('file')
                
            # Ensure ttrpg logger propagates to root for test capture
            if 'loggers' in file_config and 'ttrpg' in file_config['loggers']:
                file_config['loggers']['ttrpg']['propagate'] = True
            _logging_config.dictConfig(file_config)
        except Exception as e:
            print(f"Warning: Failed to load logging config from {config_path}: {e}")
            _logging_config.dictConfig(default_config)
    else:
        _logging_config.dictConfig(default_config)
    
    return _logging.getLogger('ttrpg')


def get_logger(name: str) -> _logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name, typically __name__ of the calling module
        
    Returns:
        Logger instance configured with TTRPG formatting
    """
    logger = _logging.getLogger(f"ttrpg.{name}")
    # Make sure a handler exists via root; explicit handlers not bound here
    return logger


class LogContext:
    """
    Context manager for adding consistent fields to log records.
    """
    
    def __init__(self, **fields):
        self.fields = fields
        self.old_factory = _logging.getLogRecordFactory()
    
    def __enter__(self):
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.fields.items():
                setattr(record, key, value)
            return record
        
        _logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _logging.setLogRecordFactory(self.old_factory)


def log_function_call(func):
    """
    Decorator to automatically log function entry/exit with timing.
    """
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        logger.info(
            f"Entering {func.__name__}",
            extra={
                'function': func.__name__,
                'component': 'function_call'
            }
        )
        
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Exiting {func.__name__}",
                extra={
                    'function': func.__name__,
                    'duration_ms': duration_ms,
                    'component': 'function_call'
                }
            )
            
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                extra={
                    'function': func.__name__,
                    'duration_ms': duration_ms,
                    'error': str(e),
                    'component': 'function_call'
                }
            )
            raise
    
    return wrapper


# Security: Function to sanitize log data
def sanitize_for_logging(data: Any) -> Any:
    """
    Remove sensitive information from data before logging.
    
    Args:
        data: Data to sanitize (dict, str, list, etc.)
        
    Returns:
        Sanitized data safe for logging
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in ['password', 'token', 'key', 'secret', 'api']):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = sanitize_for_logging(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]
    elif isinstance(data, str):
        s = data.lower()
        # Redact common bearer/API key patterns regardless of length
        sensitive_markers = ['authorization:', 'bearer ', 'token', 'key=', 'password=', 'sk-', 'pk-']
        if any(marker in s for marker in sensitive_markers):
            return '***REDACTED***'
    
    return data
