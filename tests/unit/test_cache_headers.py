"""
Tests for Cache-Control middleware (BP001 P0-003)
"""

import os
from fastapi.testclient import TestClient

from src_common.app import app


def test_cache_control_no_store(monkeypatch):
    # Default or zero TTL should set no-store
    monkeypatch.setenv("CACHE_TTL_SECONDS", "0")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "no-store"


def test_cache_control_private_max_age(monkeypatch):
    monkeypatch.setenv("CACHE_TTL_SECONDS", "5")
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers.get("Cache-Control") == "private, max-age=5"

