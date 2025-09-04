# src_common/__init__.py
"""
TTRPG Center - Common shared modules

This package contains shared utilities and components used across all
environments (dev/test/prod) in the TTRPG Center application.

Key modules:
- app: Main FastAPI application
- logging: Structured JSON logging utilities  
- mock_ingest: Mock ingestion pipeline for testing

Environment isolation is maintained through configuration, not code separation.
"""

__version__ = "0.1.0"