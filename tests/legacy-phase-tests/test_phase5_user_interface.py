# tests/functional/test_phase5_user_interface.py
"""
Functional tests for Phase 5 User Interface
Tests the complete user interface functionality including endpoints, WebSocket, and memory
"""

import pytest
import asyncio
import json
import time
from httpx import AsyncClient
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
from app_user import app, memory_manager, cache_manager


class TestUserInterfaceEndpoints:
    """Test User Interface API endpoints (US-502, US-504, US-505)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def async_client(self):
        return AsyncClient(app=app, base_url="http://test")
    
    def test_health_check_endpoint(self, client):
        """Test health check returns correct status"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "user-ui"
        assert data["phase"] == "5"
        assert "timestamp" in data
    
    def test_main_ui_page_loads(self, client):
        """Test main UI page loads with correct template (US-501)"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        # Check for key UI elements
        content = response.text
        assert "TTRPG Center" in content
        assert "QUERY INTERFACE" in content
        assert "RESPONSE OUTPUT" in content
        assert "SESSION MEMORY" in content
    
    @pytest.mark.asyncio
    async def test_query_processing_endpoint(self, async_client):
        """Test query processing endpoint with memory (US-502, US-504)"""
        query_data = {
            "query": "What is a paladin?",
            "memory_mode": "session",
            "theme": "lcars"
        }
        
        async with async_client as ac:
            response = await ac.post("/api/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "answer" in data
        assert "metadata" in data
        assert "session_id" in data
        assert "timestamp" in data
        assert "cached" in data
        
        # Check metadata structure
        assert "model" in data["metadata"]
        assert "tokens" in data["metadata"]
        assert "processing_time_ms" in data["metadata"]
        assert "intent" in data["metadata"]
        assert "domain" in data["metadata"]
        
        # Verify mock response
        assert "mock answer" in data["answer"].lower()
    
    @pytest.mark.asyncio
    async def test_query_with_custom_session(self, async_client):
        """Test query processing with custom session ID"""
        session_id = "custom_session_123"
        query_data = {
            "query": "What is initiative?",
            "session_id": session_id,
            "memory_mode": "session"
        }
        
        async with async_client as ac:
            response = await ac.post("/api/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        
        # Verify session memory was updated
        memory = memory_manager.get_session_memory(session_id)
        assert len(memory) == 1
        assert memory[0]["query"] == "What is initiative?"
    
    @pytest.mark.asyncio
    async def test_query_with_image_support(self, async_client):
        """Test multimodal support - image response slot (US-503)"""
        query_data = {
            "query": "Show me a map",
            "memory_mode": "session"
        }
        
        # Mock the RAG function to return an image URL
        with patch('app_user.mock_rag_query') as mock_rag:
            mock_rag.return_value = {
                "answer": "Here is a fantasy map",
                "metadata": {"model": "test", "tokens": 42, "processing_time_ms": 500, "intent": "visual", "domain": "maps"},
                "retrieved_chunks": [],
                "image_url": "https://example.com/fantasy-map.png"
            }
            
            async with async_client as ac:
                response = await ac.post("/api/query", json=query_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["image_url"] == "https://example.com/fantasy-map.png"
    
    def test_session_memory_retrieval(self, client):
        """Test retrieving session memory (US-504)"""
        session_id = "test_memory_session"
        
        # Add some memory first
        memory_manager.add_to_session_memory(session_id, "Question 1", "Answer 1")
        memory_manager.add_to_session_memory(session_id, "Question 2", "Answer 2")
        
        response = client.get(f"/api/session/{session_id}/memory")
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["count"] == 2
        assert len(data["messages"]) == 2
        
        # Verify message structure
        message = data["messages"][0]
        assert "timestamp" in message
        assert "query" in message
        assert "response" in message
        assert "type" in message
    
    def test_clear_session_memory(self, client):
        """Test clearing session memory (US-504)"""
        session_id = "test_clear_session"
        
        # Add memory first
        memory_manager.add_to_session_memory(session_id, "Test", "Response")
        assert len(memory_manager.get_session_memory(session_id)) == 1
        
        # Clear memory
        response = client.delete(f"/api/session/{session_id}/memory")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify memory is cleared
        assert len(memory_manager.get_session_memory(session_id)) == 0
    
    def test_user_preferences_retrieval(self, client):
        """Test user preferences API (US-505)"""
        user_id = "test_user_prefs"
        
        response = client.get(f"/api/user/{user_id}/preferences")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user_id
        assert data["theme"] == "lcars"  # Default theme
        assert data["memory_enabled"] is True
        assert data["preferred_sources"] == []
        assert data["tone"] == "helpful"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_update_user_preferences(self, client):
        """Test updating user preferences (US-505)"""
        user_id = "test_user_update"
        
        # Get initial preferences to get timestamps
        initial_response = client.get(f"/api/user/{user_id}/preferences")
        initial_data = initial_response.json()
        
        # Update preferences
        update_data = {
            "theme": "terminal",
            "memory_enabled": False,
            "preferred_sources": ["PHB", "DMG"],
            "tone": "casual"
        }
        
        response = client.put(f"/api/user/{user_id}/preferences", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify preferences were updated
        updated_response = client.get(f"/api/user/{user_id}/preferences")
        updated_data = updated_response.json()
        
        assert updated_data["theme"] == "terminal"
        assert updated_data["memory_enabled"] is False
        assert updated_data["preferred_sources"] == ["PHB", "DMG"]
        assert updated_data["tone"] == "casual"
        assert updated_data["updated_at"] > initial_data["updated_at"]
    
    def test_available_themes_endpoint(self, client):
        """Test themes endpoint returns available themes (US-501)"""
        response = client.get("/api/themes")
        
        assert response.status_code == 200
        data = response.json()
        assert "themes" in data
        
        themes = data["themes"]
        assert len(themes) >= 3  # lcars, terminal, classic
        
        # Check theme structure
        lcars_theme = next((t for t in themes if t["id"] == "lcars"), None)
        assert lcars_theme is not None
        assert lcars_theme["name"] == "LCARS"
        assert "Star Trek" in lcars_theme["description"]
        
        terminal_theme = next((t for t in themes if t["id"] == "terminal"), None)
        assert terminal_theme is not None
        assert terminal_theme["name"] == "Retro Terminal"


class TestCachePolicy:
    """Test cache policy enforcement (US-507)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_dev_environment_cache_headers(self, client):
        """Test dev environment returns no-cache headers"""
        cache_manager.environment = "dev"
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "cache-control" in response.headers
        cache_control = response.headers["cache-control"]
        assert "no-store" in cache_control
        assert "no-cache" in cache_control
        assert "must-revalidate" in cache_control
    
    def test_test_environment_cache_headers(self, client):
        """Test test environment returns short TTL headers"""
        cache_manager.environment = "test"
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "cache-control" in response.headers
        cache_control = response.headers["cache-control"]
        assert "max-age=5" in cache_control
        assert "must-revalidate" in cache_control
    
    def test_prod_environment_cache_headers(self, client):
        """Test prod environment returns normal cache headers"""
        cache_manager.environment = "prod"
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "cache-control" in response.headers
        cache_control = response.headers["cache-control"]
        assert "max-age=300" in cache_control
        assert "must-revalidate" in cache_control
    
    @pytest.mark.asyncio
    async def test_fast_retest_behavior(self, async_client):
        """Test fast retest behavior respects cache policy (US-507)"""
        query_data = {
            "query": "Test query for cache",
            "session_id": "cache_test_session"
        }
        
        # Set test environment for fast retest
        cache_manager.environment = "test"
        
        async with async_client as ac:
            # First query
            start_time = time.time()
            response1 = await ac.post("/api/query", json=query_data)
            first_time = time.time() - start_time
            
            assert response1.status_code == 200
            
            # Immediate retry - should respect cache policy
            start_time = time.time()
            response2 = await ac.post("/api/query", json=query_data)
            second_time = time.time() - start_time
            
            assert response2.status_code == 200
            
            # Both responses should have cache control headers
            assert "cache-control" in response1.headers
            assert "cache-control" in response2.headers


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_invalid_query_data(self, async_client):
        """Test handling of invalid query data"""
        invalid_data = {
            "invalid_field": "value"
            # Missing required 'query' field
        }
        
        async with async_client as ac:
            response = await ac.post("/api/query", json=invalid_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_nonexistent_session_memory(self, client):
        """Test accessing memory for nonexistent session"""
        response = client.get("/api/session/nonexistent_session/memory")
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "nonexistent_session"
        assert data["count"] == 0
        assert data["messages"] == []
    
    def test_nonexistent_user_preferences(self, client):
        """Test accessing preferences for nonexistent user"""
        response = client.get("/api/user/nonexistent_user/preferences")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "nonexistent_user"
        # Should return default preferences
        assert data["theme"] == "lcars"
        assert data["memory_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_query_processing_error_handling(self, async_client):
        """Test error handling during query processing"""
        query_data = {
            "query": "Test error handling",
            "memory_mode": "session"
        }
        
        # Mock the RAG function to raise an exception
        with patch('app_user.mock_rag_query') as mock_rag:
            mock_rag.side_effect = Exception("Simulated processing error")
            
            async with async_client as ac:
                response = await ac.post("/api/query", json=query_data)
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "processing failed" in data["detail"].lower()


class TestMemoryIntegration:
    """Test memory system integration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_session_memory_workflow(self, async_client):
        """Test complete session memory workflow (US-504)"""
        session_id = "integration_test_session"
        
        # Start with empty memory
        async with async_client as ac:
            memory_response = await ac.get(f"/api/session/{session_id}/memory")
        
        assert memory_response.status_code == 200
        memory_data = memory_response.json()
        assert memory_data["count"] == 0
        
        # Ask multiple questions
        questions = [
            "What is a fighter class?",
            "How much HP does a fighter get?", 
            "What weapons can fighters use?"
        ]
        
        async with async_client as ac:
            for question in questions:
                query_data = {
                    "query": question,
                    "session_id": session_id,
                    "memory_mode": "session"
                }
                response = await ac.post("/api/query", json=query_data)
                assert response.status_code == 200
        
        # Check memory contains all questions
        async with async_client as ac:
            memory_response = await ac.get(f"/api/session/{session_id}/memory")
        
        assert memory_response.status_code == 200
        memory_data = memory_response.json()
        assert memory_data["count"] == 3
        
        # Verify questions are stored in memory
        stored_queries = [msg["query"] for msg in memory_data["messages"]]
        for question in questions:
            assert question in stored_queries
    
    @pytest.mark.asyncio
    async def test_user_preference_workflow(self, async_client):
        """Test complete user preference workflow (US-505)"""
        user_id = "integration_test_user"
        
        # Get default preferences
        async with async_client as ac:
            prefs_response = await ac.get(f"/api/user/{user_id}/preferences")
        
        assert prefs_response.status_code == 200
        prefs_data = prefs_response.json()
        assert prefs_data["theme"] == "lcars"
        
        # Update theme preference
        update_data = {"theme": "terminal"}
        
        async with async_client as ac:
            update_response = await ac.put(f"/api/user/{user_id}/preferences", json=update_data)
        
        assert update_response.status_code == 200
        
        # Verify preference was updated
        async with async_client as ac:
            updated_prefs_response = await ac.get(f"/api/user/{user_id}/preferences")
        
        assert updated_prefs_response.status_code == 200
        updated_prefs_data = updated_prefs_response.json()
        assert updated_prefs_data["theme"] == "terminal"
        assert updated_prefs_data["memory_enabled"] is True  # Other prefs unchanged
    
    def test_session_isolation(self, client):
        """Test that sessions are properly isolated"""
        session_1 = "isolated_session_1"
        session_2 = "isolated_session_2"
        
        # Add different data to each session
        memory_manager.add_to_session_memory(session_1, "Question for session 1", "Answer 1")
        memory_manager.add_to_session_memory(session_2, "Question for session 2", "Answer 2")
        
        # Verify isolation
        response_1 = client.get(f"/api/session/{session_1}/memory")
        response_2 = client.get(f"/api/session/{session_2}/memory")
        
        assert response_1.status_code == 200
        assert response_2.status_code == 200
        
        data_1 = response_1.json()
        data_2 = response_2.json()
        
        assert data_1["count"] == 1
        assert data_2["count"] == 1
        assert data_1["messages"][0]["query"] == "Question for session 1"
        assert data_2["messages"][0]["query"] == "Question for session 2"
    
    def test_user_isolation(self, client):
        """Test that user preferences are properly isolated"""
        user_1 = "isolated_user_1"
        user_2 = "isolated_user_2"
        
        # Set different preferences for each user
        client.put(f"/api/user/{user_1}/preferences", json={"theme": "lcars"})
        client.put(f"/api/user/{user_2}/preferences", json={"theme": "terminal"})
        
        # Verify isolation
        response_1 = client.get(f"/api/user/{user_1}/preferences")
        response_2 = client.get(f"/api/user/{user_2}/preferences")
        
        assert response_1.status_code == 200
        assert response_2.status_code == 200
        
        data_1 = response_1.json()
        data_2 = response_2.json()
        
        assert data_1["theme"] == "lcars"
        assert data_2["theme"] == "terminal"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])