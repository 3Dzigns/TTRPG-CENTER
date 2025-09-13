# Smoke Tests

"""
Smoke testing module for TTRPG Center environments.

Smoke tests are fast, basic tests that validate core functionality
is working after deployments. These tests should run quickly and
catch major issues without deep validation.

Test Categories:
- Environment connectivity
- Health endpoint validation
- Basic API functionality
- Service availability
- Environment isolation

Usage:
    pytest tests/smoke/                    # Run all smoke tests
    pytest tests/smoke/ -m smoke          # Run smoke tests only
    pytest tests/smoke/ --tb=short        # Run with minimal output
"""