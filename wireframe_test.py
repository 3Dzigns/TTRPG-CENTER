#!/usr/bin/env python3
"""
Comprehensive Wireframe Editor Test
Tests all major functionality of the wireframe editor.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test wireframe service health."""
    print("Testing wireframe health...")
    response = requests.get(f"{BASE_URL}/admin/api/wireframe/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✅ Health check passed")

def test_api_endpoints():
    """Test all wireframe API endpoints."""
    print("Testing API endpoints...")
    
    endpoints = [
        "/admin/api/wireframe/projects",
        "/admin/api/wireframe/stats", 
        "/admin/api/wireframe/components",
        "/admin/api/wireframe/activity"
    ]
    
    for endpoint in endpoints:
        print(f"  Testing {endpoint}...")
        response = requests.get(f"{BASE_URL}{endpoint}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"  ✅ {endpoint} passed")

def test_dashboard_page():
    """Test wireframe dashboard page loads."""
    print("Testing dashboard page...")
    response = requests.get(f"{BASE_URL}/admin/wireframe")
    assert response.status_code == 200
    assert "Wireframe Dashboard" in response.text
    print("✅ Dashboard page loads")

def test_editor_page():
    """Test wireframe editor page loads."""
    print("Testing editor page...")
    response = requests.get(f"{BASE_URL}/admin/wireframe/editor")
    assert response.status_code == 200
    assert "Wireframe Editor" in response.text
    print("✅ Editor page loads")

def test_project_crud():
    """Test project creation, retrieval, and deletion."""
    print("Testing project CRUD operations...")
    
    # Create project
    project_data = {
        "name": "Test Project",
        "description": "Test project for wireframe editor",
        "canvas_settings": {
            "width": 1200,
            "height": 800,
            "theme": "admin",
            "grid_enabled": True,
            "snap_to_grid": True
        },
        "tags": ["test", "automation"]
    }
    
    print("  Creating project...")
    response = requests.post(
        f"{BASE_URL}/admin/api/wireframe/projects",
        json=project_data
    )
    assert response.status_code == 200
    create_data = response.json()
    assert create_data["status"] == "success"
    project_id = create_data["project"]["id"]
    print(f"  ✅ Project created with ID: {project_id}")
    
    # Get project
    print("  Retrieving project...")
    response = requests.get(f"{BASE_URL}/admin/api/wireframe/projects/{project_id}")
    assert response.status_code == 200
    get_data = response.json()
    assert get_data["status"] == "success"
    assert get_data["project"]["name"] == "Test Project"
    print("  ✅ Project retrieved successfully")
    
    # Update project
    print("  Updating project...")
    update_data = {
        "name": "Updated Test Project",
        "description": "Updated description"
    }
    response = requests.put(
        f"{BASE_URL}/admin/api/wireframe/projects/{project_id}",
        json=update_data
    )
    assert response.status_code == 200
    update_response = response.json()
    assert update_response["status"] == "success"
    print("  ✅ Project updated successfully")
    
    # Delete project
    print("  Deleting project...")
    response = requests.delete(f"{BASE_URL}/admin/api/wireframe/projects/{project_id}")
    assert response.status_code == 200
    delete_data = response.json()
    assert delete_data["status"] == "success"
    print("  ✅ Project deleted successfully")

def main():
    """Run all tests."""
    print("🧪 Starting Wireframe Editor Comprehensive Tests\n")
    
    try:
        test_health_check()
        test_api_endpoints()
        test_dashboard_page()
        test_editor_page()
        test_project_crud()
        
        print("\n🎉 All wireframe tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
