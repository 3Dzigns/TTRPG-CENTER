# tests/unit/test_phase5_user_services.py
"""
Unit tests for Phase 5 User UI Services
Tests memory management, theme handling, and query processing
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Import User UI classes
from app_user import MemoryManager, CachePolicyManager, QueryRequest, QueryResponse, UserPreferences


class TestMemoryManager:
    """Test Memory Management Service (US-504, US-505)"""
    
    @pytest.fixture
    def memory_manager(self):
        return MemoryManager()
    
    def test_memory_manager_initialization(self, memory_manager):
        """Test memory manager initializes correctly"""
        assert memory_manager.sessions == {}
        assert memory_manager.users == {}
    
    def test_session_memory_creation(self, memory_manager):
        """Test session memory is created on first access"""
        session_id = "test_session_123"
        
        messages = memory_manager.get_session_memory(session_id)
        
        assert messages == []
        assert session_id in memory_manager.sessions
        assert "created_at" in memory_manager.sessions[session_id]
        assert "updated_at" in memory_manager.sessions[session_id]
    
    def test_add_to_session_memory(self, memory_manager):
        """Test adding messages to session memory"""
        session_id = "test_session_123"
        query = "What is a wizard?"
        response = "A wizard is a spellcaster who learns magic through study."
        
        memory_manager.add_to_session_memory(session_id, query, response)
        
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 1
        assert messages[0]["query"] == query
        assert messages[0]["response"] == response
        assert messages[0]["type"] == "qa_pair"
        assert "timestamp" in messages[0]
    
    def test_multiple_session_memory_entries(self, memory_manager):
        """Test multiple entries are stored in session memory"""
        session_id = "test_session_123"
        
        # Add multiple entries
        entries = [
            ("What is a fighter?", "A fighter is a warrior class."),
            ("What is a rogue?", "A rogue is a stealthy class."),
            ("What is a cleric?", "A cleric is a divine spellcaster.")
        ]
        
        for query, response in entries:
            memory_manager.add_to_session_memory(session_id, query, response)
        
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 3
        
        # Check all entries are preserved
        for i, (query, response) in enumerate(entries):
            assert messages[i]["query"] == query
            assert messages[i]["response"] == response
    
    def test_clear_session_memory(self, memory_manager):
        """Test clearing session memory"""
        session_id = "test_session_123"
        
        # Add some data
        memory_manager.add_to_session_memory(session_id, "test", "response")
        assert len(memory_manager.get_session_memory(session_id)) == 1
        
        # Clear memory
        memory_manager.clear_session_memory(session_id)
        
        # Session should be removed
        assert session_id not in memory_manager.sessions
        
        # Getting memory again should create empty session
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 0
    
    def test_session_memory_isolation(self, memory_manager):
        """Test sessions are isolated from each other"""
        session_1 = "session_1"
        session_2 = "session_2"
        
        memory_manager.add_to_session_memory(session_1, "query 1", "response 1")
        memory_manager.add_to_session_memory(session_2, "query 2", "response 2")
        
        messages_1 = memory_manager.get_session_memory(session_1)
        messages_2 = memory_manager.get_session_memory(session_2)
        
        assert len(messages_1) == 1
        assert len(messages_2) == 1
        assert messages_1[0]["query"] == "query 1"
        assert messages_2[0]["query"] == "query 2"
    
    def test_user_preferences_creation(self, memory_manager):
        """Test user preferences are created with defaults"""
        user_id = "test_user_123"
        
        preferences = memory_manager.get_user_preferences(user_id)
        
        assert preferences.user_id == user_id
        assert preferences.theme == "lcars"  # Default theme
        assert preferences.memory_enabled is True
        assert preferences.preferred_sources == []
        assert preferences.tone == "helpful"
        assert preferences.created_at > 0
        assert preferences.updated_at > 0
    
    def test_update_user_preferences(self, memory_manager):
        """Test updating user preferences"""
        user_id = "test_user_123"
        
        # Get initial preferences
        initial_prefs = memory_manager.get_user_preferences(user_id)
        initial_updated = initial_prefs.updated_at
        
        # Update preferences
        updates = {
            "theme": "terminal",
            "memory_enabled": False,
            "preferred_sources": ["PHB", "DMG"],
            "tone": "casual"
        }
        
        memory_manager.update_user_preferences(user_id, updates)
        
        # Get updated preferences
        updated_prefs = memory_manager.get_user_preferences(user_id)
        
        assert updated_prefs.theme == "terminal"
        assert updated_prefs.memory_enabled is False
        assert updated_prefs.preferred_sources == ["PHB", "DMG"]
        assert updated_prefs.tone == "casual"
        assert updated_prefs.updated_at > initial_updated
    
    def test_user_preference_isolation(self, memory_manager):
        """Test user preferences are isolated"""
        user_1 = "user_1"
        user_2 = "user_2"
        
        memory_manager.update_user_preferences(user_1, {"theme": "lcars"})
        memory_manager.update_user_preferences(user_2, {"theme": "terminal"})
        
        prefs_1 = memory_manager.get_user_preferences(user_1)
        prefs_2 = memory_manager.get_user_preferences(user_2)
        
        assert prefs_1.theme == "lcars"
        assert prefs_2.theme == "terminal"


class TestCachePolicyManager:
    """Test Cache Policy Management (US-507)"""
    
    @pytest.fixture
    def cache_manager(self):
        return CachePolicyManager()
    
    def test_cache_manager_initialization(self, cache_manager):
        """Test cache manager initializes with dev environment"""
        assert cache_manager.environment == "dev"
    
    def test_dev_environment_cache_headers(self, cache_manager):
        """Test dev environment returns no-cache headers"""
        cache_manager.environment = "dev"
        
        headers = cache_manager.get_cache_headers("/api/test")
        
        assert "Cache-Control" in headers
        assert "no-store" in headers["Cache-Control"]
        assert "no-cache" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]
        assert "Pragma" in headers
        assert headers["Pragma"] == "no-cache"
        assert "Expires" in headers
        assert headers["Expires"] == "0"
    
    def test_test_environment_cache_headers(self, cache_manager):
        """Test test environment returns short TTL headers"""
        cache_manager.environment = "test"
        
        headers = cache_manager.get_cache_headers("/api/test")
        
        assert "Cache-Control" in headers
        assert "max-age=5" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]
    
    def test_prod_environment_cache_headers(self, cache_manager):
        """Test prod environment returns normal cache headers"""
        cache_manager.environment = "prod"
        
        headers = cache_manager.get_cache_headers("/api/test")
        
        assert "Cache-Control" in headers
        assert "max-age=300" in headers["Cache-Control"]
        assert "must-revalidate" in headers["Cache-Control"]
    
    def test_cache_headers_consistency(self, cache_manager):
        """Test cache headers are consistent across calls"""
        cache_manager.environment = "test"
        
        headers_1 = cache_manager.get_cache_headers("/api/query")
        headers_2 = cache_manager.get_cache_headers("/api/memory")
        
        # Both should have same cache policy
        assert headers_1["Cache-Control"] == headers_2["Cache-Control"]


class TestUserUIModels:
    """Test Pydantic models for User UI"""
    
    def test_query_request_model(self):
        """Test QueryRequest model validation"""
        # Valid request
        request_data = {
            "query": "What is a paladin?",
            "session_id": "session_123",
            "user_id": "user_456",
            "memory_mode": "session",
            "theme": "lcars"
        }
        
        request = QueryRequest(**request_data)
        
        assert request.query == "What is a paladin?"
        assert request.session_id == "session_123"
        assert request.user_id == "user_456"
        assert request.memory_mode == "session"
        assert request.theme == "lcars"
    
    def test_query_request_defaults(self):
        """Test QueryRequest model with defaults"""
        request = QueryRequest(query="Test query")
        
        assert request.query == "Test query"
        assert request.session_id is None
        assert request.user_id is None
        assert request.memory_mode == "session"
        assert request.theme == "lcars"
    
    def test_query_response_model(self):
        """Test QueryResponse model"""
        response_data = {
            "answer": "A paladin is a holy warrior.",
            "metadata": {"model": "test-model", "tokens": 42},
            "image_url": "https://example.com/image.png",
            "session_id": "session_123",
            "timestamp": time.time(),
            "cached": True
        }
        
        response = QueryResponse(**response_data)
        
        assert response.answer == "A paladin is a holy warrior."
        assert response.metadata["model"] == "test-model"
        assert response.metadata["tokens"] == 42
        assert response.image_url == "https://example.com/image.png"
        assert response.session_id == "session_123"
        assert response.cached is True
    
    def test_query_response_optional_fields(self):
        """Test QueryResponse with optional fields"""
        response = QueryResponse(
            answer="Test answer",
            metadata={},
            session_id="session_123",
            timestamp=time.time()
        )
        
        assert response.answer == "Test answer"
        assert response.image_url is None
        assert response.cached is False  # Default value
    
    def test_user_preferences_model(self):
        """Test UserPreferences model"""
        current_time = time.time()
        
        prefs_data = {
            "user_id": "user_123",
            "theme": "terminal",
            "memory_enabled": False,
            "preferred_sources": ["PHB", "DMG"],
            "tone": "casual",
            "created_at": current_time,
            "updated_at": current_time
        }
        
        prefs = UserPreferences(**prefs_data)
        
        assert prefs.user_id == "user_123"
        assert prefs.theme == "terminal"
        assert prefs.memory_enabled is False
        assert prefs.preferred_sources == ["PHB", "DMG"]
        assert prefs.tone == "casual"
        assert prefs.created_at == current_time
        assert prefs.updated_at == current_time
    
    def test_user_preferences_defaults(self):
        """Test UserPreferences with defaults"""
        prefs = UserPreferences(
            user_id="user_123",
            created_at=time.time(),
            updated_at=time.time()
        )
        
        assert prefs.theme == "lcars"
        assert prefs.memory_enabled is True
        assert prefs.preferred_sources == []
        assert prefs.tone == "helpful"


@pytest.mark.asyncio
class TestMemoryIntegration:
    """Integration tests for memory management"""
    
    @pytest.fixture
    def memory_manager(self):
        return MemoryManager()
    
    async def test_session_workflow(self, memory_manager):
        """Test complete session workflow"""
        session_id = "integration_session"
        
        # Start with empty session
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 0
        
        # Simulate conversation
        conversation = [
            ("What is initiative?", "Initiative determines turn order in combat."),
            ("How do I roll for it?", "Roll 1d20 and add your Dexterity modifier."),
            ("What if there's a tie?", "The player with higher Dexterity goes first.")
        ]
        
        for query, response in conversation:
            memory_manager.add_to_session_memory(session_id, query, response)
        
        # Verify all messages stored
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 3
        
        # Verify conversation order (newest first)
        assert messages[0]["query"] == "What if there's a tie?"
        assert messages[1]["query"] == "How do I roll for it?"
        assert messages[2]["query"] == "What is initiative?"
        
        # Clear and verify
        memory_manager.clear_session_memory(session_id)
        messages = memory_manager.get_session_memory(session_id)
        assert len(messages) == 0
    
    async def test_user_preference_workflow(self, memory_manager):
        """Test complete user preference workflow"""
        user_id = "integration_user"
        
        # Get default preferences
        prefs = memory_manager.get_user_preferences(user_id)
        assert prefs.theme == "lcars"
        assert prefs.memory_enabled is True
        
        # Update theme preference
        memory_manager.update_user_preferences(user_id, {"theme": "terminal"})
        
        prefs = memory_manager.get_user_preferences(user_id)
        assert prefs.theme == "terminal"
        assert prefs.memory_enabled is True  # Other prefs unchanged
        
        # Update multiple preferences
        updates = {
            "memory_enabled": False,
            "preferred_sources": ["PHB"],
            "tone": "professional"
        }
        memory_manager.update_user_preferences(user_id, updates)
        
        prefs = memory_manager.get_user_preferences(user_id)
        assert prefs.theme == "terminal"  # Previous update preserved
        assert prefs.memory_enabled is False
        assert prefs.preferred_sources == ["PHB"]
        assert prefs.tone == "professional"
    
    async def test_concurrent_session_access(self, memory_manager):
        """Test concurrent access to different sessions"""
        sessions = ["session_1", "session_2", "session_3"]
        
        # Simulate concurrent session activity
        tasks = []
        for i, session_id in enumerate(sessions):
            async def add_messages(sid, index):
                for j in range(5):
                    query = f"Query {index}_{j}"
                    response = f"Response {index}_{j}"
                    memory_manager.add_to_session_memory(sid, query, response)
            
            tasks.append(add_messages(session_id, i))
        
        # Run concurrently
        await asyncio.gather(*tasks)
        
        # Verify each session has correct messages
        for i, session_id in enumerate(sessions):
            messages = memory_manager.get_session_memory(session_id)
            assert len(messages) == 5
            
            # Check messages are from correct session
            for j, message in enumerate(messages):
                expected_query = f"Query {i}_{4-j}"  # Newest first
                assert message["query"] == expected_query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])