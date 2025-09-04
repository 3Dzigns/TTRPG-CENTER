# tests/unit/test_logging.py
"""
Unit tests for structured JSON logging utility.
"""

import json
import logging
import os
import time
from io import StringIO

import pytest

from src_common.logging import (
    jlog, setup_logging, get_logger, LogContext, 
    sanitize_for_logging, TTRPGJsonFormatter
)


def test_jlog_no_throw(capsys, monkeypatch):
    """Test that jlog function emits valid JSON without throwing errors."""
    monkeypatch.setenv("APP_ENV", "test")
    
    jlog('INFO', 'hello', step='init')
    
    captured = capsys.readouterr()
    output = captured.out.strip()
    
    # Should be valid JSON
    log_record = json.loads(output)
    
    assert log_record['level'] == 'INFO'
    assert log_record['message'] == 'hello'
    assert log_record['environment'] == 'test'
    assert log_record['step'] == 'init'
    assert 'timestamp' in log_record


def test_jlog_with_various_types(capsys, monkeypatch):
    """Test jlog with various data types."""
    monkeypatch.setenv("APP_ENV", "dev")
    
    jlog('DEBUG', 'test message', 
         count=42, 
         success=True, 
         duration=1.5,
         items=['a', 'b', 'c'],
         metadata={'key': 'value'})
    
    captured = capsys.readouterr()
    log_record = json.loads(captured.out.strip())
    
    assert log_record['count'] == 42
    assert log_record['success'] is True
    assert log_record['duration'] == 1.5
    assert log_record['items'] == ['a', 'b', 'c']
    assert log_record['metadata'] == {'key': 'value'}


def test_jlog_filters_none_values(capsys, monkeypatch):
    """Test that jlog filters out None values."""
    monkeypatch.setenv("APP_ENV", "test")
    
    jlog('INFO', 'test', valid_field='value', none_field=None)
    
    captured = capsys.readouterr()
    log_record = json.loads(captured.out.strip())
    
    assert 'valid_field' in log_record
    assert 'none_field' not in log_record
    assert log_record['valid_field'] == 'value'


def test_setup_logging_returns_logger():
    """Test that setup_logging returns a configured logger."""
    logger = setup_logging()
    
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'ttrpg'


def test_get_logger_returns_named_logger():
    """Test that get_logger returns properly named logger."""
    logger = get_logger('test_module')
    
    assert isinstance(logger, logging.Logger)
    assert logger.name == 'ttrpg.test_module'


def test_ttrpg_json_formatter():
    """Test TTRPGJsonFormatter adds required fields."""
    formatter = TTRPGJsonFormatter()
    
    # Create a mock log record
    record = logging.LogRecord(
        name='test', level=logging.INFO, pathname='', lineno=0,
        msg='test message', args=(), exc_info=None
    )
    
    # Add optional fields
    record.trace_id = 'trace-123'
    record.user_id = 'user-456'
    record.duration_ms = 150.5
    record.component = 'test_component'
    
    # Format the record
    formatted = formatter.format(record)
    log_data = json.loads(formatted)
    
    assert 'timestamp' in log_data
    assert 'environment' in log_data
    assert log_data['trace_id'] == 'trace-123'
    assert log_data['user_id'] == 'user-456'
    assert log_data['duration_ms'] == 150.5
    assert log_data['component'] == 'test_component'


def test_log_context_manager(caplog):
    """Test LogContext adds fields to log records."""
    logger = get_logger('test_context')
    
    with LogContext(trace_id='ctx-123', operation='test_op'):
        logger.info('test message')
    
    # Check that context fields were added
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert hasattr(record, 'trace_id')
    assert hasattr(record, 'operation')
    assert record.trace_id == 'ctx-123'
    assert record.operation == 'test_op'


def test_sanitize_for_logging_removes_secrets():
    """Test that sanitize_for_logging removes sensitive information."""
    sensitive_data = {
        'username': 'john_doe',
        'password': 'secret123',
        'api_key': 'sk-1234567890',
        'token': 'bearer_token_here',
        'SECRET_KEY': 'super_secret',
        'data': {
            'public_info': 'this is fine',
            'private_key': 'should_be_redacted'
        }
    }
    
    sanitized = sanitize_for_logging(sensitive_data)
    
    # Public data should remain
    assert sanitized['username'] == 'john_doe'
    assert sanitized['data']['public_info'] == 'this is fine'
    
    # Sensitive data should be redacted
    assert sanitized['password'] == '***REDACTED***'
    assert sanitized['api_key'] == '***REDACTED***'
    assert sanitized['token'] == '***REDACTED***'
    assert sanitized['SECRET_KEY'] == '***REDACTED***'
    assert sanitized['data']['private_key'] == '***REDACTED***'


def test_sanitize_for_logging_handles_lists():
    """Test sanitization works with nested lists."""
    data = [
        {'public': 'info'},
        {'secret': 'sensitive'},
        'normal string',
        {'nested': [{'password': '123'}]}
    ]
    
    sanitized = sanitize_for_logging(data)
    
    assert sanitized[0]['public'] == 'info'
    assert sanitized[1]['secret'] == '***REDACTED***'
    assert sanitized[2] == 'normal string'
    assert sanitized[3]['nested'][0]['password'] == '***REDACTED***'


def test_sanitize_for_logging_handles_strings():
    """Test sanitization of potentially sensitive strings."""
    sensitive_string = "Authorization: Bearer sk-1234567890abcdef"
    normal_string = "This is a normal log message"
    
    sanitized_sensitive = sanitize_for_logging(sensitive_string)
    sanitized_normal = sanitize_for_logging(normal_string)
    
    assert sanitized_sensitive == '***REDACTED***'
    assert sanitized_normal == normal_string


class TestLoggingConfiguration:
    """Test logging configuration and setup."""
    
    def test_logging_config_dev_environment(self, monkeypatch):
        """Test logging configuration for dev environment."""
        monkeypatch.setenv("APP_ENV", "dev")
        
        logger = setup_logging()
        
        # Dev should have DEBUG level
        assert logger.level <= logging.DEBUG
    
    def test_logging_config_prod_environment(self, monkeypatch):
        """Test logging configuration for production environment."""
        monkeypatch.setenv("APP_ENV", "prod")
        
        logger = setup_logging()
        
        # Production should use structured logging
        assert logger.name == 'ttrpg'
    
    def test_logging_respects_log_level_env_var(self, monkeypatch):
        """Test that LOG_LEVEL environment variable is respected."""
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        
        logger = setup_logging()
        
        # Should respect the LOG_LEVEL setting
        assert logger.isEnabledFor(logging.WARNING)
    
    def test_no_secrets_in_default_log_output(self, caplog, monkeypatch):
        """Test that secrets don't appear in logs by default."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret123")
        monkeypatch.setenv("APP_ENV", "test")
        
        logger = get_logger('security_test')
        
        # This should not log the secret
        logger.info("Application starting", extra={
            'config_loaded': True,
            'environment': os.getenv('APP_ENV')
        })
        
        # Check that secret is not in log output
        log_output = caplog.text
        assert "sk-secret123" not in log_output


class TestPerformanceLogging:
    """Test performance-related logging features."""
    
    def test_timing_fields_in_logs(self, caplog):
        """Test that timing information is properly logged."""
        logger = get_logger('perf_test')
        
        start_time = time.time()
        time.sleep(0.01)  # Small delay
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info("Operation completed", extra={
            'duration_ms': duration_ms,
            'operation': 'test_op'
        })
        
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, 'duration_ms')
        assert hasattr(record, 'operation')
        assert record.duration_ms > 0
    
    def test_component_field_in_logs(self, caplog):
        """Test that component field is added to log records."""
        logger = get_logger('component_test')
        
        logger.info("Component message", extra={'component': 'ingestion'})
        
        record = caplog.records[0]
        assert hasattr(record, 'component')
        assert record.component == 'ingestion'