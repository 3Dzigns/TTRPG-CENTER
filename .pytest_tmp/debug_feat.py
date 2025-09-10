import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app_requirements import app
client = TestClient(app)
valid_feature = {
    "title": "Enhanced User Profile Management",
    "description": "Users should be able to manage their profiles with advanced customization options including avatar upload, bio, and preferences",
    "priority": "medium",
    "requester": "product_team",
    "category": "ui",
    "business_value": "high",
    "user_story": "As a user I want to customize my profile so that I can personalize my experience"
}
resp = client.post('/api/features/submit', json=valid_feature)
print('status', resp.status_code, resp.text)
