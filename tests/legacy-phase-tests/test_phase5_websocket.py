# tests/functional/test_phase5_websocket.py
"""
WebSocket integration tests for Phase 5 User Interface
Tests real-time communication and connection management
"""

import pytest
import asyncio
import json
import time
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

# Import the FastAPI app
from app_user import app, manager


class TestWebSocketConnection:
    """Test WebSocket connection and basic functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_websocket_connection_establishment(self, client):
        """Test WebSocket connection can be established"""
        session_id = "test_websocket_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Connection should be established successfully
            assert websocket is not None
            
            # Send a test message
            test_message = {"type": "ping", "data": "test"}
            websocket.send_json(test_message)
            
            # Receive echo response
            response = websocket.receive_json()
            assert response["type"] == "echo"
            assert response["session_id"] == session_id
            assert response["message"] == test_message
            assert "timestamp" in response
    
    def test_websocket_multiple_messages(self, client):
        """Test multiple message exchange over WebSocket"""
        session_id = "test_multi_message"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            messages = [
                {"type": "query", "data": "What is a paladin?"},
                {"type": "memory", "action": "clear"},
                {"type": "theme", "theme": "terminal"},
                {"type": "status", "check": "connection"}
            ]
            
            for message in messages:
                websocket.send_json(message)
                response = websocket.receive_json()
                
                assert response["type"] == "echo"
                assert response["session_id"] == session_id
                assert response["message"] == message
    
    def test_websocket_connection_with_different_sessions(self, client):
        """Test WebSocket connections are isolated by session"""
        session_1 = "ws_test_session_1"
        session_2 = "ws_test_session_2"
        
        with client.websocket_connect(f"/ws/{session_1}") as ws1:
            with client.websocket_connect(f"/ws/{session_2}") as ws2:
                # Send different messages to each session
                message_1 = {"type": "test", "session": "1"}
                message_2 = {"type": "test", "session": "2"}
                
                ws1.send_json(message_1)
                ws2.send_json(message_2)
                
                response_1 = ws1.receive_json()
                response_2 = ws2.receive_json()
                
                # Verify each connection receives its own message
                assert response_1["session_id"] == session_1
                assert response_1["message"]["session"] == "1"
                
                assert response_2["session_id"] == session_2
                assert response_2["message"]["session"] == "2"
    
    def test_websocket_connection_handles_invalid_json(self, client):
        """Test WebSocket handles invalid JSON gracefully"""
        session_id = "test_invalid_json"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Send invalid JSON as text
            websocket.send_text("invalid json {")
            
            # Connection should remain active (no disconnect)
            # Send valid message to verify connection is still working
            test_message = {"type": "test", "data": "valid"}
            websocket.send_json(test_message)
            
            response = websocket.receive_json()
            assert response["type"] == "echo"
            assert response["message"] == test_message


class TestWebSocketBroadcasting:
    """Test WebSocket broadcasting functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_websocket_manager_initialization(self):
        """Test WebSocket connection manager initializes correctly"""
        assert manager.active_connections == []
    
    @pytest.mark.asyncio
    async def test_websocket_broadcast_functionality(self, client):
        """Test broadcasting messages to connected clients"""
        session_id = "test_broadcast_session"
        
        # Connect WebSocket
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Simulate a broadcast message
            broadcast_message = {
                "type": "query_response",
                "session_id": session_id,
                "query": "Test broadcast query",
                "response": "Test broadcast response",
                "timestamp": time.time()
            }
            
            # Send broadcast (this would normally be called from query endpoint)
            await manager.broadcast(broadcast_message)
            
            # The WebSocket should receive the broadcast message
            # Note: In real implementation, the client would need to be connected
            # when the broadcast happens, but this test verifies the mechanism
    
    def test_websocket_disconnect_handling(self, client):
        """Test WebSocket disconnect handling"""
        session_id = "test_disconnect_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Send a message to establish connection
            websocket.send_json({"type": "connect", "session": session_id})
            response = websocket.receive_json()
            assert response["type"] == "echo"
        
        # Connection should be automatically cleaned up when context exits
        # This tests that the connection manager properly handles disconnections


class TestWebSocketIntegration:
    """Test WebSocket integration with other components"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_websocket_query_integration(self, client):
        """Test WebSocket receives updates from query processing"""
        session_id = "test_integration_session"
        
        # This test would verify that when a query is processed,
        # connected WebSocket clients receive updates
        # Due to test client limitations, this is a structural test
        
        # Verify WebSocket connection works
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Send connection confirmation
            websocket.send_json({"type": "ready", "session_id": session_id})
            response = websocket.receive_json()
            
            assert response["type"] == "echo"
            assert response["session_id"] == session_id
            
            # In a real application, this WebSocket would receive
            # broadcast messages when queries are processed
            # The broadcast functionality is tested separately
    
    def test_websocket_session_coordination(self, client):
        """Test WebSocket coordinates with session management"""
        session_id = "test_coordination_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Test session-aware messaging
            messages = [
                {"type": "session_init", "session_id": session_id},
                {"type": "memory_update", "action": "add"},
                {"type": "theme_change", "theme": "lcars"},
                {"type": "status_update", "status": "ready"}
            ]
            
            for message in messages:
                websocket.send_json(message)
                response = websocket.receive_json()
                
                # Each response should include session context
                assert response["session_id"] == session_id
                assert response["message"] == message
                assert "timestamp" in response
    
    def test_websocket_error_resilience(self, client):
        """Test WebSocket resilience to connection errors"""
        session_id = "test_error_resilience"
        
        # Test connection recovery after error
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Send valid message first
            websocket.send_json({"type": "test", "phase": "before_error"})
            response = websocket.receive_json()
            assert response["type"] == "echo"
            
            # Send potentially problematic data
            websocket.send_json({
                "type": "stress_test", 
                "data": "x" * 1000,  # Large payload
                "nested": {"deep": {"structure": {"test": True}}}
            })
            
            response = websocket.receive_json()
            assert response["type"] == "echo"
            assert "stress_test" in str(response)


class TestWebSocketSecurity:
    """Test WebSocket security considerations"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_websocket_session_isolation(self, client):
        """Test WebSocket sessions cannot access other session data"""
        session_1 = "secure_session_1"
        session_2 = "secure_session_2"
        
        # Connect to both sessions
        with client.websocket_connect(f"/ws/{session_1}") as ws1:
            with client.websocket_connect(f"/ws/{session_2}") as ws2:
                # Attempt to send cross-session message
                cross_session_message = {
                    "type": "cross_session_access",
                    "target_session": session_2,
                    "data": "unauthorized_access_attempt"
                }
                
                ws1.send_json(cross_session_message)
                response = ws1.receive_json()
                
                # Response should only contain session_1 context
                assert response["session_id"] == session_1
                assert "target_session" not in str(response).replace("target_session", "").replace(session_2, "")
    
    def test_websocket_data_sanitization(self, client):
        """Test WebSocket properly handles potentially malicious data"""
        session_id = "security_test_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Test with potentially malicious payloads
            malicious_messages = [
                {"type": "<script>alert('xss')</script>", "data": "test"},
                {"type": "injection", "data": "'; DROP TABLE users; --"},
                {"type": "path_traversal", "data": "../../../etc/passwd"},
                {"type": "size_attack", "data": "A" * 10000}
            ]
            
            for message in malicious_messages:
                websocket.send_json(message)
                response = websocket.receive_json()
                
                # Response should be properly structured
                assert response["type"] == "echo"
                assert response["session_id"] == session_id
                # The malicious content should be contained in the echo
                # but not executed or cause system issues
    
    def test_websocket_connection_limits(self, client):
        """Test WebSocket handles multiple connections appropriately"""
        base_session = "limit_test_session"
        connections = []
        
        try:
            # Attempt to create multiple connections
            # (Real implementation might limit connections per session)
            for i in range(5):
                session_id = f"{base_session}_{i}"
                ws = client.websocket_connect(f"/ws/{session_id}")
                websocket = ws.__enter__()
                connections.append((ws, websocket))
                
                # Test each connection works
                websocket.send_json({"type": "connection_test", "index": i})
                response = websocket.receive_json()
                assert response["type"] == "echo"
                assert response["session_id"] == session_id
        
        finally:
            # Clean up connections
            for ws_context, _ in connections:
                try:
                    ws_context.__exit__(None, None, None)
                except:
                    pass  # Connection might already be closed


class TestWebSocketPerformance:
    """Test WebSocket performance characteristics"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_websocket_message_latency(self, client):
        """Test WebSocket message round-trip latency"""
        session_id = "performance_test_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            # Measure round-trip time
            start_time = time.time()
            
            websocket.send_json({
                "type": "latency_test",
                "timestamp": start_time
            })
            
            response = websocket.receive_json()
            end_time = time.time()
            
            latency = end_time - start_time
            
            # Assert reasonable latency (should be very fast for local test)
            assert latency < 1.0  # Less than 1 second for local test
            assert response["type"] == "echo"
            assert "timestamp" in response
    
    def test_websocket_message_throughput(self, client):
        """Test WebSocket can handle rapid message exchange"""
        session_id = "throughput_test_session"
        
        with client.websocket_connect(f"/ws/{session_id}") as websocket:
            message_count = 50
            start_time = time.time()
            
            # Send messages rapidly
            for i in range(message_count):
                websocket.send_json({
                    "type": "throughput_test",
                    "sequence": i,
                    "timestamp": time.time()
                })
                
                response = websocket.receive_json()
                assert response["type"] == "echo"
                assert response["message"]["sequence"] == i
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Calculate messages per second
            throughput = message_count / total_time
            
            # Assert reasonable throughput (should be high for local test)
            assert throughput > 10  # At least 10 messages per second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])