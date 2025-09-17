import pytest
from fastapi.testclient import TestClient

from src_common.app import app

client = TestClient(app)


def test_log_management_uses_data_attributes():
    response = client.get("/admin/logs")
    assert response.status_code == 200
    html = response.text
    assert 'onclick="viewLog(' not in html
    assert 'class="btn btn-outline-primary btn-sm view-log-btn"' in html
    assert 'data-log-file="' in html
