# src_common/secrets.py
"""
Secrets handling and environment variable management for TTRPG Center.
Provides secure loading of environment variables with validation and defaults.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .ttrpg_logging import get_logger


logger = get_logger(__name__)


class SecretsError(Exception):
    """Custom exception for secrets handling errors."""
    pass


def load_env(env_root: Path) -> None:
    """
    Load environment variables from .env file with safe defaults.
    
    Args:
        env_root: Root path of the environment directory
        
    Raises:
        SecretsError: If .env file is missing or invalid
    """
    # First try root .env file (project-wide credentials)
    # Navigate to project root from env directory
    project_root = env_root.parent
    root_env_file = project_root / ".env"
    if root_env_file.exists():
        logger.info(f"Loading environment variables from root .env: {root_env_file}")
        _load_env_file(root_env_file)
    
    # Then try environment-specific .env file
    env_file = env_root / "config" / ".env"
    
    if not env_file.exists():
        # Try .env.template as fallback
        template_file = env_root / "config" / ".env.template"
        if template_file.exists():
            logger.warning(f"No .env file found, using .env.template: {env_file}")
            env_file = template_file
        elif not root_env_file.exists():
            raise SecretsError(f"Missing .env file and .env.template at {env_file}")
    
    if env_file.exists():
        logger.info(f"Loading environment variables from: {env_file}")
        _load_env_file(env_file)


def _load_env_file(env_file: Path) -> None:
    """Load environment variables from a specific .env file"""
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' not in line:
                    logger.warning(f"Invalid line {line_num} in {env_file}: {line}")
                    continue
                
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Set environment variable if not already set
                if key not in os.environ:
                    os.environ[key] = value
                    logger.debug(f"Set environment variable: {key}")
                else:
                    logger.debug(f"Environment variable already set: {key}")
                    
    except Exception as e:
        raise SecretsError(f"Failed to load environment file {env_file}: {str(e)}")


def get_required_secret(key: str) -> str:
    """
    Get a required secret from environment variables.
    
    Args:
        key: Environment variable key
        
    Returns:
        Secret value
        
    Raises:
        SecretsError: If secret is missing or empty
    """
    value = os.getenv(key)
    if not value:
        raise SecretsError(f"Required secret '{key}' is missing or empty")
    
    logger.debug(f"Retrieved required secret: {key}")
    return value


def get_optional_secret(key: str, default: str = "") -> str:
    """
    Get an optional secret from environment variables.
    
    Args:
        key: Environment variable key
        default: Default value if secret is not found
        
    Returns:
        Secret value or default
    """
    value = os.getenv(key, default)
    logger.debug(f"Retrieved optional secret: {key} (using default: {bool(value == default)})")
    return value


def validate_database_config() -> Dict[str, str]:
    """
    Validate and return database configuration.
    
    Returns:
        Dictionary with validated database configuration
        
    Raises:
        SecretsError: If required database configuration is missing
    """
    config = {}
    
    # Required database fields
    required_fields = [
        'ASTRA_DB_API_ENDPOINT',
        'ASTRA_DB_APPLICATION_TOKEN',
        'ASTRA_DB_ID'
    ]
    
    for field in required_fields:
        value = os.getenv(field)
        if not value:
            logger.warning(f"Database configuration missing: {field}")
            config[field] = ""  # Allow empty for dev/testing
        else:
            config[field] = value
    
    # Optional database fields with defaults
    config['ASTRA_DB_KEYSPACE'] = get_optional_secret('ASTRA_DB_KEYSPACE', 'default_keyspace')
    config['ASTRA_DB_REGION'] = get_optional_secret('ASTRA_DB_REGION', 'us-east-2')
    
    logger.info("Database configuration validated")
    return config


def validate_ai_config() -> Dict[str, str]:
    """
    Validate and return AI model configuration.
    
    Returns:
        Dictionary with AI model configuration
    """
    config = {}
    
    # AI API keys (optional for development)
    config['OPENAI_API_KEY'] = get_optional_secret('OPENAI_API_KEY')
    config['ANTHROPIC_API_KEY'] = get_optional_secret('ANTHROPIC_API_KEY')
    
    if not config['OPENAI_API_KEY'] and not config['ANTHROPIC_API_KEY']:
        logger.warning("No AI API keys configured - some features may not work")
    
    logger.info("AI configuration validated")
    return config


def validate_security_config() -> Dict[str, str]:
    """
    Validate and return security configuration.
    
    Returns:
        Dictionary with security configuration
        
    Raises:
        SecretsError: If critical security config is missing in production
    """
    config = {}
    
    env = os.getenv('APP_ENV', 'dev')
    
    # Security keys
    config['SECRET_KEY'] = get_optional_secret('SECRET_KEY')
    config['JWT_SECRET'] = get_optional_secret('JWT_SECRET')
    
    # Generate development defaults if missing
    if not config['SECRET_KEY']:
        if env == 'prod':
            raise SecretsError("SECRET_KEY is required in production")
        config['SECRET_KEY'] = 'dev-secret-key-not-secure'
        logger.warning("Using default SECRET_KEY for development")
    
    if not config['JWT_SECRET']:
        if env == 'prod':
            raise SecretsError("JWT_SECRET is required in production")
        config['JWT_SECRET'] = 'dev-jwt-secret-not-secure'
        logger.warning("Using default JWT_SECRET for development")
    
    logger.info("Security configuration validated")
    return config


def get_all_config() -> Dict[str, Any]:
    """
    Get complete application configuration from environment.
    
    Returns:
        Dictionary with all configuration values
    """
    config = {
        'environment': os.getenv('APP_ENV', 'dev'),
        'port': int(os.getenv('PORT', 8000)),
        'websocket_port': int(os.getenv('WEBSOCKET_PORT', 9000)),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'cache_ttl_seconds': int(os.getenv('CACHE_TTL_SECONDS', 0)),
        'artifacts_path': os.getenv('ARTIFACTS_PATH', './artifacts/dev')
    }
    
    # Add subsystem configs
    config['database'] = validate_database_config()
    config['ai'] = validate_ai_config()
    config['security'] = validate_security_config()
    
    logger.info("Complete application configuration loaded", extra={
        'environment': config['environment'],
        'port': config['port'],
        'component': 'secrets'
    })
    
    return config


def sanitize_config_for_logging(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a redacted copy of config suitable for logging.
    Any key containing common secret indicators will have its value replaced.
    """
    def _sanitize(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                k_lower = str(k).lower()
                if any(s in k_lower for s in ["password", "token", "secret", "api_key", "key"]):
                    out[k] = "***REDACTED***"
                else:
                    out[k] = _sanitize(v)
            return out
        elif isinstance(obj, list):
            return [_sanitize(x) for x in obj]
        else:
            return obj

    return _sanitize(config)


def sanitize_config_for_logging(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive values from config for safe logging.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Sanitized configuration safe for logging
    """
    sanitized = {}
    
    for key, value in config.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_config_for_logging(value)
        elif isinstance(key, str) and any(sensitive in key.lower() 
                                         for sensitive in ['secret', 'key', 'token', 'password']):
            sanitized[key] = '***REDACTED***' if value else ''
        else:
            sanitized[key] = value
    
    return sanitized


def check_secrets_file_permissions(env_root: Path) -> None:
    """
    Check and warn about .env file permissions on POSIX systems.
    
    Args:
        env_root: Root path of the environment directory
    """
    env_file = env_root / "config" / ".env"
    
    if not env_file.exists():
        return
    
    try:
        import stat
        file_stat = env_file.stat()
        file_perms = stat.filemode(file_stat.st_mode)
        
        # Check if file is world-readable (dangerous)
        if file_stat.st_mode & stat.S_IROTH:
            logger.warning(f"⚠️  .env file is world-readable: {env_file}")
            logger.warning("   Consider running: chmod 600 {env_file}")
        elif file_stat.st_mode & stat.S_IRGRP:
            logger.info(f"📋 .env file is group-readable: {env_file} ({file_perms})")
        else:
            logger.info(f"🔒 .env file has secure permissions: {env_file} ({file_perms})")
            
    except (ImportError, OSError) as e:
        # Windows or permission check failed
        logger.debug(f"Could not check .env file permissions: {e}")


# Utility functions for specific secret types
def get_database_url() -> Optional[str]:
    """Get formatted database URL if available."""
    config = validate_database_config()
    endpoint = config.get('ASTRA_DB_API_ENDPOINT')
    token = config.get('ASTRA_DB_APPLICATION_TOKEN')
    
    if endpoint and token:
        return f"{endpoint}?token={token}"
    return None


def get_openai_client_config() -> Dict[str, str]:
    """Get configuration for OpenAI client."""
    return {
        'api_key': get_optional_secret('OPENAI_API_KEY'),
        'organization': get_optional_secret('OPENAI_ORG_ID'),
        'max_retries': int(get_optional_secret('OPENAI_MAX_RETRIES', '3')),
        'timeout': int(get_optional_secret('OPENAI_TIMEOUT_SECONDS', '30'))
    }


def get_anthropic_client_config() -> Dict[str, str]:
    """Get configuration for Anthropic client."""
    return {
        'api_key': get_optional_secret('ANTHROPIC_API_KEY'),
        'max_retries': int(get_optional_secret('ANTHROPIC_MAX_RETRIES', '3')),
        'timeout': int(get_optional_secret('ANTHROPIC_TIMEOUT_SECONDS', '30'))
    }
