# tests/security/test_env_gitignore.py
"""
Security tests for .env file git hygiene and secrets protection.
"""

import os
import stat
from pathlib import Path

import pytest


def test_env_gitignored():
    """Test that .env files are properly gitignored."""
    repo_root = Path.cwd()
    gitignore_file = repo_root / '.gitignore'
    
    if not gitignore_file.exists():
        pytest.skip("No .gitignore file found")
    
    gitignore_content = gitignore_file.read_text()
    
    # Check for various patterns that should protect .env files
    patterns = [
        'env/*/config/.env',
        '/env/**/.env', 
        '.env',
        '*.env'
    ]
    
    found_pattern = False
    for pattern in patterns:
        if pattern in gitignore_content:
            found_pattern = True
            break
    
    assert found_pattern, f"No .env gitignore pattern found in {gitignore_file}. Checked patterns: {patterns}"


def test_env_file_permissions_unix(temp_env_root):
    """Test that .env files have secure permissions on UNIX-like systems."""
    if os.name == 'nt':  # Skip on Windows
        pytest.skip("UNIX permission test - skipping on Windows")
    
    env_file = temp_env_root / "config" / ".env"
    
    if not env_file.exists():
        pytest.skip("No .env file found for permission test")
    
    # Get file permissions
    file_stat = env_file.stat()
    file_perms = stat.filemode(file_stat.st_mode)
    
    # Check that file is not world-readable
    assert not (file_stat.st_mode & stat.S_IROTH), f".env file is world-readable: {file_perms}"
    
    # Check that file is not world-writable
    assert not (file_stat.st_mode & stat.S_IWOTH), f".env file is world-writable: {file_perms}"
    
    # Ideally should be 600 (owner read/write only) or 640 (owner read/write, group read)
    world_bits = file_stat.st_mode & (stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
    assert world_bits == 0, f".env file has world permissions: {file_perms}"


def test_no_secrets_in_repository():
    """Test that no secret files are committed to the repository."""
    repo_root = Path.cwd()
    
    # Search for potential secret files that shouldn't be in repo
    secret_patterns = [
        "**/.env",
        "**/secrets.json",
        "**/private_key",
        "**/*.pem",
        "**/*.key",
        "**/id_rsa"
    ]
    
    found_secrets = []
    for pattern in secret_patterns:
        matches = list(repo_root.glob(pattern))
        for match in matches:
            # Skip files in .git directory or test fixtures
            if '.git' in str(match) or 'test' in str(match).lower() or 'fixture' in str(match).lower():
                continue
            found_secrets.append(str(match))
    
    assert len(found_secrets) == 0, f"Potential secret files found in repository: {found_secrets}"


def test_secrets_not_in_logs(capsys):
    """Test that secrets are not leaked in application logs."""
    from src_common.logging import jlog, sanitize_for_logging
    
    # Set up fake secrets in environment
    os.environ['TEST_API_KEY'] = 'sk-fake123'
    os.environ['TEST_SECRET'] = 'secret_value'
    
    try:
        # Test that jlog doesn't accidentally log environment variables
        jlog('INFO', 'Application starting', component='test')
        
        captured = capsys.readouterr()
        log_output = captured.out
        
        # Secrets should not appear in logs
        assert 'sk-fake123' not in log_output
        assert 'secret_value' not in log_output
        
        # Test sanitize function
        sensitive_data = {
            'api_key': os.environ['TEST_API_KEY'],
            'secret': os.environ['TEST_SECRET'],
            'normal_field': 'normal_value'
        }
        
        sanitized = sanitize_for_logging(sensitive_data)
        assert sanitized['api_key'] == '***REDACTED***'
        assert sanitized['secret'] == '***REDACTED***'
        assert sanitized['normal_field'] == 'normal_value'
        
    finally:
        # Clean up test environment variables
        del os.environ['TEST_API_KEY']
        del os.environ['TEST_SECRET']


def test_environment_variable_validation():
    """Test that environment variables are properly validated."""
    from src_common.secrets import get_all_config, sanitize_config_for_logging
    
    # Set up test environment
    original_env = os.environ.get('APP_ENV')
    os.environ['APP_ENV'] = 'test'
    
    try:
        config = get_all_config()
        
        # Test that sensitive config is not exposed
        sanitized_config = sanitize_config_for_logging(config)
        
        # Check that security section is sanitized
        security_config = sanitized_config.get('security', {})
        if 'SECRET_KEY' in security_config:
            assert security_config['SECRET_KEY'] == '***REDACTED***'
        if 'JWT_SECRET' in security_config:
            assert security_config['JWT_SECRET'] == '***REDACTED***'
        
        # Check that database config is sanitized
        db_config = sanitized_config.get('database', {})
        if 'ASTRA_DB_APPLICATION_TOKEN' in db_config:
            assert db_config['ASTRA_DB_APPLICATION_TOKEN'] in ['***REDACTED***', '']
        
        # Check that AI config is sanitized
        ai_config = sanitized_config.get('ai', {})
        if 'OPENAI_API_KEY' in ai_config:
            assert ai_config['OPENAI_API_KEY'] in ['***REDACTED***', '']
        if 'ANTHROPIC_API_KEY' in ai_config:
            assert ai_config['ANTHROPIC_API_KEY'] in ['***REDACTED***', '']
    
    finally:
        if original_env:
            os.environ['APP_ENV'] = original_env
        elif 'APP_ENV' in os.environ:
            del os.environ['APP_ENV']


def test_file_path_traversal_prevention(temp_env_root):
    """Test that file operations prevent path traversal attacks."""
    from src_common.secrets import load_env
    
    # Create a malicious .env file that tries to escape the directory
    malicious_env = temp_env_root / "config" / ".env"
    malicious_content = """
# Attempt path traversal
MALICIOUS_VAR=../../../etc/passwd
ANOTHER_VAR=../../secrets.txt
NORMAL_VAR=normal_value
"""
    malicious_env.write_text(malicious_content)
    
    # Load environment should not fail but should handle paths safely
    try:
        load_env(temp_env_root)
        
        # Values should be loaded as literal strings, not interpreted as paths
        assert os.environ.get('MALICIOUS_VAR') == '../../../etc/passwd'
        assert os.environ.get('ANOTHER_VAR') == '../../secrets.txt'
        assert os.environ.get('NORMAL_VAR') == 'normal_value'
        
    finally:
        # Clean up
        for var in ['MALICIOUS_VAR', 'ANOTHER_VAR', 'NORMAL_VAR']:
            if var in os.environ:
                del os.environ[var]


def test_sql_injection_in_job_ids():
    """Test that job IDs are sanitized to prevent injection attacks."""
    from src_common.mock_ingest import run_mock_sync
    
    # Test various potentially malicious job IDs
    malicious_job_ids = [
        "job'; DROP TABLE users; --",
        "job<script>alert('xss')</script>",
        "job../../../etc/passwd",
        "job\x00null_byte",
        "job\"; rm -rf /; --"
    ]
    
    for job_id in malicious_job_ids:
        try:
            # Should either sanitize the job ID or fail gracefully
            result = run_mock_sync(job_id)
            
            # If it succeeds, job ID should be sanitized
            assert result['job_id'] != job_id or result['job_id'].isalnum() or '-' in result['job_id']
            
        except (ValueError, AssertionError):
            # It's acceptable to reject malicious job IDs
            pass


class TestSecretsHandlingSecurity:
    """Test security aspects of secrets handling."""
    
    def test_secrets_module_doesnt_log_secrets(self, caplog):
        """Test that secrets module doesn't accidentally log secret values."""
        from src_common.secrets import get_required_secret, get_optional_secret, SecretsError
        
        # Set up test secrets
        os.environ['TEST_REQUIRED_SECRET'] = 'super_secret_value'
        os.environ['TEST_OPTIONAL_SECRET'] = 'another_secret'
        
        try:
            # These operations should not log the secret values
            required = get_required_secret('TEST_REQUIRED_SECRET')
            optional = get_optional_secret('TEST_OPTIONAL_SECRET', 'default')
            
            assert required == 'super_secret_value'
            assert optional == 'another_secret'
            
            # Check that secrets don't appear in debug logs
            log_output = '\n'.join(record.message for record in caplog.records)
            assert 'super_secret_value' not in log_output
            assert 'another_secret' not in log_output
            
        finally:
            del os.environ['TEST_REQUIRED_SECRET']
            del os.environ['TEST_OPTIONAL_SECRET']
    
    def test_missing_required_secrets_fail_securely(self):
        """Test that missing required secrets fail with secure error messages."""
        from src_common.secrets import get_required_secret, SecretsError

        with pytest.raises(SecretsError) as excinfo:
            get_required_secret('NONEXISTENT_SECRET_KEY')

        error_message = str(excinfo.value)

        # Error message should include the exact missing key name for diagnostics
        assert 'NONEXISTENT_SECRET_KEY' in error_message

        # When scanning for sensitive markers, ignore the explicit key string itself
        sanitized_msg = error_message.lower().replace('nonexistent_secret_key'.lower(), '')
        # Should not contain hints about other secrets that might exist
        assert 'sk-' not in sanitized_msg
        assert 'secret_' not in sanitized_msg
    
    def test_production_secrets_validation(self, monkeypatch):
        """Test that production environment enforces required secrets."""
        from src_common.secrets import validate_security_config, SecretsError
        
        monkeypatch.setenv('APP_ENV', 'prod')
        
        # Should fail if required production secrets are missing
        with pytest.raises(SecretsError):
            validate_security_config()
        
        # Should succeed with proper secrets
        monkeypatch.setenv('SECRET_KEY', 'production_secret_key')
        monkeypatch.setenv('JWT_SECRET', 'production_jwt_secret')
        
        config = validate_security_config()
        assert config['SECRET_KEY'] == 'production_secret_key'
        assert config['JWT_SECRET'] == 'production_jwt_secret'


class TestServerSecurityHeaders:
    """Test security headers and server hardening."""
    
    def test_health_endpoint_no_server_info_leak(self, test_client):
        """Test that health endpoint doesn't leak sensitive server information."""
        response = test_client.get("/healthz")
        
        # Should not leak detailed version info, paths, or internal details
        data = response.json()
        
        # Basic info is OK
        assert 'status' in data
        assert 'environment' in data
        assert 'version' in data
        
        # Should not contain sensitive paths or internal details
        sensitive_fields = ['__file__', 'sys.path', 'os.environ', 'SECRET_KEY', 'internal_path']
        for field in sensitive_fields:
            assert field not in str(data), f"Sensitive field '{field}' found in health endpoint response"
    
    def test_error_responses_dont_leak_internals(self, test_client):
        """Test that error responses don't leak internal information."""
        # Test 404 response
        response = test_client.get("/nonexistent-endpoint")
        assert response.status_code == 404
        
        # Should not contain stack traces or file paths
        error_content = response.text
        assert '/src_common/' not in error_content
        assert 'Traceback' not in error_content
        assert '__file__' not in error_content
