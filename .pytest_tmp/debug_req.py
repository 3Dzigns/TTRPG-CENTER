import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app_requirements import app
client = TestClient(app)
valid_requirements = {
    "title": "Test Requirements Document",
    "version": "1.0.0",
    "description": "Comprehensive test requirements for TTRPG Center",
    "requirements": {
        "functional": [
            {
                "id": "FR-001",
                "title": "User Authentication",
                "description": "Users must be able to authenticate securely",
                "priority": "high",
                "category": "security"
            }
        ],
        "non_functional": [
            {
                "id": "NFR-001",
                "title": "Response Time",
                "description": "API responses must be under 2 seconds",
                "priority": "medium",
                "category": "performance"
            }
        ]
    },
    "stakeholders": [
        {
            "name": "Product Owner",
            "role": "Requirements Owner",
            "involvement": "primary"
        }
    ],
    "author": "test_architect"
}
resp = client.post('/api/requirements/submit', json=valid_requirements, headers={'X-Admin-User':'test_admin'})
print('status', resp.status_code)
print(resp.json())
