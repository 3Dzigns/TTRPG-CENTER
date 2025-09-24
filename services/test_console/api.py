"""
Test Console API Service

MVP v2 External Test Execution Architecture
Provides web-based console interface for test execution monitoring and control.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiohttp
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src_common.logging import get_logger
from src_common.config import get_environment_config

logger = get_logger(__name__)

# Console models
class ConsoleMessage(BaseModel):
    """Console message model."""
    timestamp: str
    level: str = Field(..., description="Message level: info|warning|error|success")
    message: str
    source: str = Field(..., description="Message source: test-runner|console|system")
    test_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TestCommand(BaseModel):
    """Test command model."""
    command: str = Field(..., description="Command: execute|cancel|status|logs")
    test_suite: Optional[str] = None
    test_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)

# Initialize FastAPI app
app = FastAPI(
    title="TTRPG Center - Test Console API",
    description="MVP v2 Test Console Interface",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connection established. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket connection closed. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to broadcast message: {e}")
                disconnected.append(connection)

        # Remove disconnected connections
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)

manager = ConnectionManager()

# Console message history
_message_history: List[ConsoleMessage] = []
_test_runner_base_url = "http://test-runner:8195"  # Default test runner URL

@app.on_event("startup")
async def startup_event():
    """Initialize test console service on startup."""
    logger.info("Starting Test Console API Service v2.0.0")

    # Load environment configuration
    config = get_environment_config()
    logger.info(f"Loaded configuration for environment: {config.get('environment', 'unknown')}")

    # Configure test runner URL based on environment
    env_name = config.get("environment", "test")
    if env_name == "dev":
        global _test_runner_base_url
        _test_runner_base_url = "http://localhost:8195"
    elif env_name == "prod":
        _test_runner_base_url = "http://test-runner:8195"

    # Send startup message
    startup_message = ConsoleMessage(
        timestamp=datetime.utcnow().isoformat(),
        level="info",
        message="Test Console API Service started successfully",
        source="console",
        metadata={"version": "2.0.0", "environment": env_name}
    )
    _message_history.append(startup_message)

    logger.info(f"Test runner URL configured: {_test_runner_base_url}")

@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": "test-console",
            "version": "2.0.0",
            "environment": os.getenv("TARGET_ENV", "test"),
            "active_connections": len(manager.active_connections),
            "message_history_count": len(_message_history)
        }
    )

@app.get("/")
async def get_console():
    """Serve test console web interface."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTRPG Center - Test Console</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: 'Courier New', monospace;
                background: #000;
                color: #0f0;
                margin: 0;
                padding: 20px;
            }
            .console-container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                margin-bottom: 20px;
                border: 1px solid #0f0;
                padding: 10px;
            }
            .console-output {
                background: #111;
                border: 1px solid #0f0;
                height: 400px;
                overflow-y: auto;
                padding: 10px;
                margin-bottom: 20px;
            }
            .console-input {
                display: flex;
                gap: 10px;
            }
            .console-input input {
                flex: 1;
                background: #000;
                color: #0f0;
                border: 1px solid #0f0;
                padding: 10px;
                font-family: inherit;
            }
            .console-input button {
                background: #000;
                color: #0f0;
                border: 1px solid #0f0;
                padding: 10px 20px;
                cursor: pointer;
                font-family: inherit;
            }
            .console-input button:hover {
                background: #0f0;
                color: #000;
            }
            .message {
                margin-bottom: 5px;
                font-size: 14px;
            }
            .message.info { color: #0f0; }
            .message.warning { color: #ff0; }
            .message.error { color: #f00; }
            .message.success { color: #0f0; font-weight: bold; }
            .controls {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 10px;
                margin-bottom: 20px;
            }
            .controls button {
                background: #000;
                color: #0f0;
                border: 1px solid #0f0;
                padding: 10px;
                cursor: pointer;
                font-family: inherit;
            }
            .controls button:hover {
                background: #0f0;
                color: #000;
            }
        </style>
    </head>
    <body>
        <div class="console-container">
            <div class="header">
                <h1>TTRPG CENTER - TEST CONSOLE</h1>
                <p>MVP v2 External Test Execution Interface</p>
            </div>

            <div class="controls">
                <button onclick="runTests('unit')">Run Unit Tests</button>
                <button onclick="runTests('functional')">Run Functional Tests</button>
                <button onclick="runTests('regression')">Run Regression Tests</button>
                <button onclick="runTests('security')">Run Security Tests</button>
                <button onclick="listTests()">List All Tests</button>
                <button onclick="clearConsole()">Clear Console</button>
            </div>

            <div class="console-output" id="console-output"></div>

            <div class="console-input">
                <input type="text" id="command-input" placeholder="Enter command (e.g., execute unit, status <test-id>, cancel <test-id>)">
                <button onclick="executeCommand()">Execute</button>
            </div>
        </div>

        <script>
            const ws = new WebSocket('ws://localhost:8196/ws');
            const consoleOutput = document.getElementById('console-output');

            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                addMessage(data);
            };

            ws.onopen = function(event) {
                addMessage({
                    timestamp: new Date().toISOString(),
                    level: 'info',
                    message: 'WebSocket connected to test console',
                    source: 'console'
                });
            };

            ws.onclose = function(event) {
                addMessage({
                    timestamp: new Date().toISOString(),
                    level: 'warning',
                    message: 'WebSocket connection closed',
                    source: 'console'
                });
            };

            function addMessage(data) {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${data.level}`;

                const timestamp = new Date(data.timestamp).toLocaleTimeString();
                messageDiv.innerHTML = `[${timestamp}] [${data.source.toUpperCase()}] ${data.message}`;

                if (data.test_id) {
                    messageDiv.innerHTML += ` (Test ID: ${data.test_id.substring(0, 8)}...)`;
                }

                consoleOutput.appendChild(messageDiv);
                consoleOutput.scrollTop = consoleOutput.scrollHeight;
            }

            function executeCommand() {
                const input = document.getElementById('command-input');
                const command = input.value.trim();
                if (command) {
                    addMessage({
                        timestamp: new Date().toISOString(),
                        level: 'info',
                        message: `Executing: ${command}`,
                        source: 'user'
                    });

                    // Send command via WebSocket
                    ws.send(JSON.stringify({
                        type: 'command',
                        command: command
                    }));

                    input.value = '';
                }
            }

            function runTests(suite) {
                const command = `execute ${suite}`;
                document.getElementById('command-input').value = command;
                executeCommand();
            }

            function listTests() {
                const command = 'list';
                document.getElementById('command-input').value = command;
                executeCommand();
            }

            function clearConsole() {
                consoleOutput.innerHTML = '';
                addMessage({
                    timestamp: new Date().toISOString(),
                    level: 'info',
                    message: 'Console cleared',
                    source: 'console'
                });
            }

            // Handle Enter key in command input
            document.getElementById('command-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    executeCommand();
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time console communication."""
    await manager.connect(websocket)

    try:
        # Send message history to newly connected client
        for message in _message_history[-50:]:  # Send last 50 messages
            await manager.send_personal_message(message.dict(), websocket)

        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "command":
                command = message_data.get("command", "").strip()
                await process_console_command(command, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def process_console_command(command: str, websocket: WebSocket):
    """Process console command and execute via test runner API."""

    try:
        parts = command.split()
        if not parts:
            return

        cmd = parts[0].lower()

        if cmd == "execute" and len(parts) > 1:
            test_suite = parts[1]
            await execute_test_suite_command(test_suite, websocket)

        elif cmd == "status" and len(parts) > 1:
            test_id = parts[1]
            await get_test_status_command(test_id, websocket)

        elif cmd == "cancel" and len(parts) > 1:
            test_id = parts[1]
            await cancel_test_command(test_id, websocket)

        elif cmd == "logs" and len(parts) > 1:
            test_id = parts[1]
            await get_test_logs_command(test_id, websocket)

        elif cmd == "list":
            await list_tests_command(websocket)

        else:
            error_message = ConsoleMessage(
                timestamp=datetime.utcnow().isoformat(),
                level="error",
                message=f"Unknown command: {command}",
                source="console"
            )
            await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        logger.error(f"Error processing console command '{command}': {str(e)}")
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Command failed: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

async def execute_test_suite_command(test_suite: str, websocket: WebSocket):
    """Execute test suite via test runner API."""

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "test_suite": test_suite,
                "environment": "test",
                "parallel": True,
                "timeout_seconds": 600
            }

            async with session.post(f"{_test_runner_base_url}/tests/execute", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    test_id = result.get("test_id")

                    success_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="success",
                        message=f"Test suite '{test_suite}' started successfully",
                        source="test-runner",
                        test_id=test_id
                    )

                    await manager.broadcast(success_message.dict())
                    _message_history.append(success_message)

                else:
                    error_text = await response.text()
                    error_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="error",
                        message=f"Failed to start test suite '{test_suite}': {error_text}",
                        source="test-runner"
                    )
                    await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Error executing test suite: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

async def get_test_status_command(test_id: str, websocket: WebSocket):
    """Get test status via test runner API."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{_test_runner_base_url}/tests/{test_id}/status") as response:
                if response.status == 200:
                    result = await response.json()

                    status_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="info",
                        message=f"Test status: {result.get('status')} (Progress: {result.get('progress', 0)*100:.1f}%)",
                        source="test-runner",
                        test_id=test_id,
                        metadata=result
                    )

                    await manager.send_personal_message(status_message.dict(), websocket)

                else:
                    error_text = await response.text()
                    error_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="error",
                        message=f"Failed to get test status: {error_text}",
                        source="test-runner"
                    )
                    await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Error getting test status: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

async def cancel_test_command(test_id: str, websocket: WebSocket):
    """Cancel test via test runner API."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{_test_runner_base_url}/tests/{test_id}") as response:
                if response.status == 200:
                    success_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="success",
                        message=f"Test cancelled successfully",
                        source="test-runner",
                        test_id=test_id
                    )

                    await manager.send_personal_message(success_message.dict(), websocket)

                else:
                    error_text = await response.text()
                    error_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="error",
                        message=f"Failed to cancel test: {error_text}",
                        source="test-runner"
                    )
                    await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Error cancelling test: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

async def get_test_logs_command(test_id: str, websocket: WebSocket):
    """Get test logs via test runner API."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{_test_runner_base_url}/tests/{test_id}/logs") as response:
                if response.status == 200:
                    result = await response.json()

                    stdout = result.get("stdout", "")
                    stderr = result.get("stderr", "")

                    if stdout:
                        log_message = ConsoleMessage(
                            timestamp=datetime.utcnow().isoformat(),
                            level="info",
                            message=f"STDOUT:\n{stdout}",
                            source="test-runner",
                            test_id=test_id
                        )
                        await manager.send_personal_message(log_message.dict(), websocket)

                    if stderr:
                        log_message = ConsoleMessage(
                            timestamp=datetime.utcnow().isoformat(),
                            level="warning",
                            message=f"STDERR:\n{stderr}",
                            source="test-runner",
                            test_id=test_id
                        )
                        await manager.send_personal_message(log_message.dict(), websocket)

                    if not stdout and not stderr:
                        log_message = ConsoleMessage(
                            timestamp=datetime.utcnow().isoformat(),
                            level="info",
                            message="No logs available yet",
                            source="test-runner",
                            test_id=test_id
                        )
                        await manager.send_personal_message(log_message.dict(), websocket)

                else:
                    error_text = await response.text()
                    error_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="error",
                        message=f"Failed to get test logs: {error_text}",
                        source="test-runner"
                    )
                    await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Error getting test logs: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

async def list_tests_command(websocket: WebSocket):
    """List all tests via test runner API."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{_test_runner_base_url}/tests") as response:
                if response.status == 200:
                    tests = await response.json()

                    if tests:
                        for test in tests[-10:]:  # Show last 10 tests
                            test_message = ConsoleMessage(
                                timestamp=datetime.utcnow().isoformat(),
                                level="info",
                                message=f"Test: {test.get('test_id', 'unknown')[:8]}... | Status: {test.get('status')} | Duration: {test.get('duration_seconds', 'N/A')}s",
                                source="test-runner",
                                test_id=test.get('test_id'),
                                metadata=test
                            )
                            await manager.send_personal_message(test_message.dict(), websocket)
                    else:
                        list_message = ConsoleMessage(
                            timestamp=datetime.utcnow().isoformat(),
                            level="info",
                            message="No tests found",
                            source="test-runner"
                        )
                        await manager.send_personal_message(list_message.dict(), websocket)

                else:
                    error_text = await response.text()
                    error_message = ConsoleMessage(
                        timestamp=datetime.utcnow().isoformat(),
                        level="error",
                        message=f"Failed to list tests: {error_text}",
                        source="test-runner"
                    )
                    await manager.send_personal_message(error_message.dict(), websocket)

    except Exception as e:
        error_message = ConsoleMessage(
            timestamp=datetime.utcnow().isoformat(),
            level="error",
            message=f"Error listing tests: {str(e)}",
            source="console"
        )
        await manager.send_personal_message(error_message.dict(), websocket)

if __name__ == "__main__":
    import uvicorn

    # Load port configuration
    config = get_environment_config()
    port = int(os.getenv("TEST_CONSOLE_PORT", "8196"))

    uvicorn.run(
        "services.test_console.api:app",
        host="0.0.0.0",
        port=port,
        reload=config.get("environment") == "dev"
    )