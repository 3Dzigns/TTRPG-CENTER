#!/usr/bin/env python3
"""Simple test server to verify basic functionality"""

import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Load environment variables manually for testing
def load_test_env():
    """Load environment variables from config file"""
    env_file = "config/.env.dev"
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

class SimpleHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == '/health':
            self._send_json({"ok": True, "status": "running"})
        elif self.path == '/status':
            self._send_json({
                "env": "test",
                "port": 8000,
                "services": {
                    "astra_token": "present" if os.getenv("ASTRA_DB_APPLICATION_TOKEN") else "missing",
                    "openai_key": "present" if os.getenv("OPENAI_API_KEY") else "missing"
                }
            })
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == '/api/query':
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())
                
                # Simple mock response
                response = {
                    "query": data.get("query", ""),
                    "response": f"Mock response for: {data.get('query', '')}",
                    "success": True,
                    "test_mode": True
                }
                self._send_json(response)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "endpoint not found"}, 404)

if __name__ == "__main__":
    load_test_env()
    
    # Verify environment
    required = ["ASTRA_DB_APPLICATION_TOKEN", "OPENAI_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"Warning: Missing env vars: {missing}")
    
    print("Starting test server on http://localhost:8000")
    print("Endpoints: /health, /status, /api/query")
    
    server = HTTPServer(('localhost', 8000), SimpleHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()