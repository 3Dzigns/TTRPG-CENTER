#!/usr/bin/env python3
"""
Environment Isolation Validation Script

Validates that environment isolation is properly configured and enforced.
MVP v2 Environment Isolation Requirements.
"""

import os
import sys
from pathlib import Path

# Add src_common to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src_common"))

from environment_isolation import validate_environment, EnvironmentIsolationError
from config import get_environment_config, get_config_manager
from logging import get_logger

logger = get_logger(__name__)


def main():
    """Main validation function."""
    print("🔍 TTRPG Center - Environment Isolation Validation")
    print("=" * 60)

    try:
        # Detect current environment
        current_env = os.getenv("TARGET_ENV", os.getenv("APP_ENV", "dev"))
        print(f"Current Environment: {current_env}")
        print()

        # Run validation
        print("Running environment isolation validation...")
        results = validate_environment()

        # Display results
        print()
        print("Validation Results:")
        print("-" * 40)

        passed = 0
        failed = 0

        for check_name, result in results.items():
            status = "✅ PASS" if result.startswith("PASS") else "❌ FAIL"
            print(f"{status} {check_name}: {result}")

            if result.startswith("PASS"):
                passed += 1
            else:
                failed += 1

        print()
        print(f"Summary: {passed} passed, {failed} failed")

        # Get environment configuration
        print()
        print("Environment Configuration:")
        print("-" * 40)

        config_manager = get_config_manager()
        env_config = config_manager.get_environment_config()

        key_configs = [
            "environment", "base_port", "code_path", "data_path", "logs_path",
            "artifacts_path", "uploads_path", "cache_path", "ssl_path",
            "admin_api_url", "user_api_url", "ingest_service_url", "orchestrator_url", "test_runner_url"
        ]

        for key in key_configs:
            if key in env_config:
                print(f"{key}: {env_config[key]}")

        # Test path validation
        print()
        print("Path Validation Tests:")
        print("-" * 40)

        test_paths = [
            f"env/{current_env}/data/test.txt",  # Should pass
            "env/other_env/data/test.txt" if current_env != "dev" else "env/test/data/test.txt",  # Should fail
            "src_common/config.py",  # Should pass (shared)
            "scripts/validate-environment.py",  # Should pass
        ]

        for test_path in test_paths:
            try:
                is_valid = config_manager.env_validator.validate_path_access(test_path)
                status = "✅ ALLOWED" if is_valid else "❌ BLOCKED"
                print(f"{status} {test_path}")
            except EnvironmentIsolationError as e:
                print(f"❌ BLOCKED {test_path} - {e}")

        # Database configuration check
        print()
        print("Database Configuration Check:")
        print("-" * 40)

        db_config = config_manager.get_database_config()

        env_specific_checks = [
            ("cassandra_keyspace", "should contain environment name"),
            ("mongo_uri", "should contain environment name"),
            ("redis_url", "should contain environment identifier"),
        ]

        for config_key, description in env_specific_checks:
            value = db_config.get(config_key)
            if value:
                has_env = any(env in str(value) for env in ["dev", "test", "prod"])
                status = "✅" if has_env else "⚠️"
                print(f"{status} {config_key}: {value} ({description})")

        # Service URL validation
        print()
        print("Service URL Validation:")
        print("-" * 40)

        services = ["orchestrator", "admin_api", "user_api", "ingest", "test_runner"]
        for service in services:
            try:
                url = config_manager.get_service_url(service)
                print(f"✅ {service}: {url}")
            except Exception as e:
                print(f"❌ {service}: Error - {e}")

        # Final result
        print()
        if failed == 0:
            print("🎉 Environment isolation validation PASSED!")
            return 0
        else:
            print("⚠️ Environment isolation validation found issues!")
            print("Please review the failed checks and fix configuration.")
            return 1

    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        logger.error(f"Validation error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)