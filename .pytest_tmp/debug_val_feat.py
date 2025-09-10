import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app_requirements import app
client = TestClient(app)
valid_data = {
    "request_id": "FR-123456",
    "title": "Valid Feature Request",
    "description": "This is a valid feature request description",
    "priority": "medium",
    "requester": "test_user",
    "status": "pending",
    "created_at": "2024-01-01T00:00:00Z"
}
resp = client.post('/api/validate/schema', json={"schema_type":"feature_request", "data": valid_data})
print('status', resp.status_code)
print(resp.json())
