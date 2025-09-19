"""Compatibility bridge exposing the FastAPI app instance for tests and tooling."""
from src_common.app import app, TTRPGApp

__all__ = ["app", "TTRPGApp"]
