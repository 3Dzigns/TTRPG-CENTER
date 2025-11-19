#!/usr/bin/env python3
"""
secrets_utils.py - Docker Secrets Utility Module
================================================

Provides helper functions for reading Docker Swarm secrets with fallback
to environment variables for backward compatibility.

Usage:
    from secrets_utils import read_secret, read_all_secrets

    api_key = read_secret("openai_api_key", "OPENAI_API_KEY")
    all_secrets = read_all_secrets()

Version: 1.0.0
Author: n8n TTRPG Center
"""

import os
from pathlib import Path
from typing import Optional, Dict


__version__ = "1.0.0"

# Docker secrets mount point
SECRETS_DIR = Path("/run/secrets")


def read_secret(
    secret_name: str,
    fallback_env: Optional[str] = None,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Read Docker secret with fallback to environment variable.

    This function provides seamless migration from environment variables
    to Docker secrets. It will:
    1. First try to read from Docker secret file (/run/secrets/<secret_name>)
    2. Fall back to environment variable if specified
    3. Return default value if neither are found

    Args:
        secret_name: Name of Docker secret (e.g., "openai_api_key")
        fallback_env: Environment variable name for fallback (e.g., "OPENAI_API_KEY")
        default: Default value if secret and env var not found

    Returns:
        Secret value or None if not found

    Examples:
        >>> # Try Docker secret first, then OPENAI_API_KEY env var
        >>> api_key = read_secret("openai_api_key", "OPENAI_API_KEY")

        >>> # Docker secret only (no fallback)
        >>> password = read_secret("postgres_password")

        >>> # With default value
        >>> user = read_secret("postgres_user", "POSTGRES_USER", default="postgres")
    """
    # Try Docker secret first
    secret_path = SECRETS_DIR / secret_name
    if secret_path.exists() and secret_path.is_file():
        try:
            with open(secret_path, 'r', encoding='utf-8') as f:
                value = f.read().strip()
                if value:  # Only return non-empty values
                    return value
        except (IOError, OSError) as e:
            # Log warning but continue to fallback
            print(f"Warning: Failed to read Docker secret '{secret_name}': {e}")

    # Fall back to environment variable
    if fallback_env:
        value = os.getenv(fallback_env)
        if value:
            return value

    # Return default value
    return default


def read_all_secrets() -> Dict[str, str]:
    """
    Read all available Docker secrets from /run/secrets directory.

    Returns:
        Dictionary mapping secret names to values

    Examples:
        >>> secrets = read_all_secrets()
        >>> print(secrets.keys())
        dict_keys(['openai_api_key', 'neo4j_password', ...])
    """
    secrets = {}

    if not SECRETS_DIR.exists():
        return secrets

    for secret_file in SECRETS_DIR.iterdir():
        if secret_file.is_file():
            try:
                with open(secret_file, 'r', encoding='utf-8') as f:
                    value = f.read().strip()
                    if value:
                        secrets[secret_file.name] = value
            except (IOError, OSError):
                # Skip files that cannot be read
                continue

    return secrets


def secret_exists(secret_name: str) -> bool:
    """
    Check if a Docker secret exists.

    Args:
        secret_name: Name of Docker secret

    Returns:
        True if secret file exists and is readable

    Examples:
        >>> if secret_exists("openai_api_key"):
        ...     api_key = read_secret("openai_api_key")
    """
    secret_path = SECRETS_DIR / secret_name
    return secret_path.exists() and secret_path.is_file()


def get_secret_path(secret_name: str) -> Path:
    """
    Get the full path to a Docker secret file.

    Args:
        secret_name: Name of Docker secret

    Returns:
        Path object pointing to secret file

    Examples:
        >>> path = get_secret_path("openai_api_key")
        >>> print(path)
        /run/secrets/openai_api_key
    """
    return SECRETS_DIR / secret_name


def list_available_secrets() -> list:
    """
    List all available Docker secret names.

    Returns:
        List of secret names (file names in /run/secrets)

    Examples:
        >>> secrets = list_available_secrets()
        >>> print(secrets)
        ['openai_api_key', 'neo4j_password', 'postgres_user']
    """
    if not SECRETS_DIR.exists():
        return []

    return [f.name for f in SECRETS_DIR.iterdir() if f.is_file()]


# Backward compatibility aliases
get_secret = read_secret  # Alias for backward compatibility


if __name__ == "__main__":
    """
    Test secrets utility module.
    """
    print(f"Docker Secrets Utility v{__version__}")
    print(f"Secrets directory: {SECRETS_DIR}")
    print(f"Secrets directory exists: {SECRETS_DIR.exists()}")
    print()

    # List available secrets
    available = list_available_secrets()
    print(f"Available secrets ({len(available)}):")
    for secret_name in available:
        print(f"  - {secret_name}")
    print()

    # Test reading with fallback
    test_cases = [
        ("openai_api_key", "OPENAI_API_KEY"),
        ("neo4j_user", "NEO4J_USER"),
        ("neo4j_password", "NEO4J_PASSWORD"),
        ("postgres_user", "POSTGRES_USER"),
        ("postgres_password", "POSTGRES_PASSWORD"),
        ("postgres_db", "POSTGRES_DB"),
    ]

    print("Testing secret reads (with fallback):")
    for secret_name, env_var in test_cases:
        value = read_secret(secret_name, env_var)
        if value:
            # Mask secret value for security
            masked = value[:4] + "*" * (len(value) - 4) if len(value) > 4 else "***"
            source = "secret" if secret_exists(secret_name) else "env_var"
            print(f"  ✓ {secret_name}: {masked} (from {source})")
        else:
            print(f"  ✗ {secret_name}: NOT FOUND")
    print()

    # Read all secrets
    all_secrets = read_all_secrets()
    print(f"All secrets loaded: {len(all_secrets)} total")
