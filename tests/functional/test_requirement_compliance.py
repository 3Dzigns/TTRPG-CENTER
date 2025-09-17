import os
import sys
from pathlib import Path
from dataclasses import dataclass

import pytest
import requests
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src_common.app import app as main_app

BASE_URL = os.getenv('TTRPG_BASE_URL', 'http://localhost:8000')
_test_client = TestClient(main_app)


@dataclass
class SimpleResponse:
    status_code: int
    _json: dict

    def json(self) -> dict:
        return self._json


def _get(path: str) -> SimpleResponse:
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return SimpleResponse(response.status_code, response.json())
    except requests.RequestException:
        pass

    client_response = _test_client.get(path)
    return SimpleResponse(client_response.status_code, client_response.json())


def _post(path: str, payload: dict | None = None) -> SimpleResponse:
    url = f"{BASE_URL}{path}"
    try:
        response = requests.post(url, json=payload or {}, timeout=5)
        if response.status_code == 200:
            return SimpleResponse(response.status_code, response.json())
    except requests.RequestException:
        pass

    client_response = _test_client.post(path, json=payload or {})
    return SimpleResponse(client_response.status_code, client_response.json())


def test_fr001_deletion_queue_endpoint_exists():
    """FR-001 requires an admin reviewable deletion queue API."""
    resp = _get("/api/admin/deletion-queue")
    assert resp.status_code == 200, (
        "Expected deletion queue endpoint per FR-001, "
        f"but got status {resp.status_code}"
    )


def test_fr004_health_report_generation_present():
    """FR-004 expects daily health reports written under artifacts/health."""
    run_resp = _post("/api/admin/health/run", {"environment": "dev", "force": True})
    assert run_resp.status_code == 200, (
        "Health run endpoint should succeed for FR-004, got "
        f"status {run_resp.status_code}"
    )
    payload = run_resp.json()
    env = payload.get("environment", "dev")
    date_slug = payload.get("date")

    health_root = Path("artifacts/health") / env
    assert health_root.exists(), 'Health reports directory missing'

    report_dir = health_root / date_slug
    assert report_dir.exists(), 'Health report directory not created'
    assert (report_dir / "report.json").exists(), 'Report file missing'
    assert (report_dir / "actions.json").exists(), 'Actions file missing'


def test_fr004_health_actions_endpoint_available():
    """FR-004 mandates admin-accessible corrective action queue."""
    resp = _get("/api/admin/health/actions")
    assert resp.status_code == 200, (
        "Expected health corrective actions endpoint per FR-004, "
        f"but got status {resp.status_code}"
    )
