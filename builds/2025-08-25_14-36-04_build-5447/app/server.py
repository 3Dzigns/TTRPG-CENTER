from http.server import HTTPServer, BaseHTTPRequestHandler
import json, time, os, sys, uuid, logging
from urllib.parse import urlparse, parse_qs

from app.common.config import load_config
from app.common.astra_client import get_vector_store
from app.common.feedback_processor import get_feedback_processor
from app.common.metrics import get_metrics_collector
from app.retrieval.router import get_query_router, QueryType
from app.retrieval.rag_engine import get_rag_engine
from app.workflows.graph_engine import get_workflow_engine
from app.workflows.workflow_executor import get_workflow_executor
from app.workflows.character_creation import create_character_creation_workflow, create_level_up_workflow
from app.ingestion.pipeline import get_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cfg = load_config()

# Initialize core components
try:
    vector_store = get_vector_store()
    feedback_processor = get_feedback_processor()
    metrics_collector = get_metrics_collector()
    query_router = get_query_router()
    rag_engine = get_rag_engine()
    workflow_engine = get_workflow_engine()
    workflow_executor = get_workflow_executor()
    ingestion_pipeline = get_pipeline()
    
    # Create default workflows if they don't exist
    pf2e_char_creation = create_character_creation_workflow("Pathfinder 2E")
    workflow_engine.save_workflow(pf2e_char_creation)
    
    pf2e_level_up = create_level_up_workflow("Pathfinder 2E")
    workflow_engine.save_workflow(pf2e_level_up)
    
    logger.info("All core components initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize components: {e}")
    raise

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, data, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        if isinstance(data, dict) or isinstance(data, list):
            self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))
        else:
            self.wfile.write(str(data).encode("utf-8"))

    def _send_html(self, code, html):
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        if path == "/health":
            self._send(200, {"ok": True, "env": cfg["runtime"]["env"], "timestamp": time.time()})
        elif path == "/status":
            ngrok = os.getenv("NGROK_PUBLIC_URL", "")
            build_id = os.getenv("APP_RELEASE_BUILD", "dev")
            
            # Detailed health checks
            health_checks = {
                "astra_vector": vector_store.health_check()["status"],
                "astra_graph": "connected" if cfg["graph"]["token_present"] else "missing_token", 
                "openai": "connected" if cfg["openai"]["key_present"] else "missing_key"
            }
            
            # Get current metrics
            current_stats = metrics_collector.get_current_stats()
            
            self._send(200, {
                "env": cfg["runtime"]["env"],
                "port": cfg["runtime"]["port"],
                "build_id": build_id,
                "health_checks": health_checks,
                "ngrok_public_url": ngrok if cfg["runtime"]["env"] == "prod" else "",
                "performance": current_stats,
                "workflows": len(workflow_engine.workflows),
                "active_executions": len(workflow_engine.active_executions)
            })
        elif path == "/" or path == "/admin":
            # Basic admin UI
            admin_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TTRPG Center Admin - {cfg['runtime']['env'].upper()}</title>
    <style>
        body {{ 
            background: linear-gradient(135deg, #0c1445 0%, #1a2456 100%);
            color: #00ffff;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .card {{ 
            background: rgba(0, 255, 255, 0.1);
            border: 1px solid #00ffff;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .status-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .health-check {{ display: flex; justify-content: space-between; margin: 10px 0; }}
        .status-ok {{ color: #00ff00; }}
        .status-error {{ color: #ff4444; }}
        button {{ 
            background: #00ffff; 
            color: #000; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }}
        button:hover {{ background: #44ffff; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TTRPG Center Admin</h1>
            <p>Environment: <strong>{cfg['runtime']['env'].upper()}</strong> | Port: {cfg['runtime']['port']}</p>
        </div>
        
        <div class="status-grid">
            <div class="card">
                <h3>System Status</h3>
                <div id="health-status">Loading...</div>
                <button onclick="refreshStatus()">Refresh Status</button>
            </div>
            
            <div class="card">
                <h3>Ingestion Console</h3>
                <p>Upload and process TTRPG source materials</p>
                <button onclick="alert('Ingestion UI - Coming Soon')">Open Ingestion</button>
            </div>
            
            <div class="card">
                <h3>Dictionary Management</h3>
                <p>View and edit normalization dictionary</p>
                <button onclick="alert('Dictionary UI - Coming Soon')">Manage Dictionary</button>
            </div>
            
            <div class="card">
                <h3>Regression Tests</h3>
                <p>View and manage automated test cases</p>
                <button onclick="alert('Regression UI - Coming Soon')">View Tests</button>
            </div>
            
            <div class="card">
                <h3>Bug Bundles</h3>
                <p>Review thumbs-down feedback</p>
                <button onclick="alert('Bug UI - Coming Soon')">View Bugs</button>
            </div>
            
            <div class="card">
                <h3>Requirements</h3>
                <p>Manage immutable requirements and feature requests</p>
                <button onclick="alert('Requirements UI - Coming Soon')">View Requirements</button>
            </div>
        </div>
    </div>
    
    <script>
        function refreshStatus() {{
            fetch('/status')
                .then(r => r.json())
                .then(data => {{
                    const healthDiv = document.getElementById('health-status');
                    let html = '<div class="health-check"><span>Build ID:</span><span>' + data.build_id + '</span></div>';
                    
                    Object.entries(data.health_checks).forEach(([service, status]) => {{
                        const statusClass = status.includes('connected') ? 'status-ok' : 'status-error';
                        html += '<div class="health-check"><span>' + service + ':</span><span class="' + statusClass + '">' + status + '</span></div>';
                    }});
                    
                    if (data.ngrok_public_url) {{
                        html += '<div class="health-check"><span>Public URL:</span><span><a href="' + data.ngrok_public_url + '" target="_blank">' + data.ngrok_public_url + '</a></span></div>';
                    }}
                    
                    healthDiv.innerHTML = html;
                }});
        }}
        
        // Auto-refresh status every 30 seconds
        refreshStatus();
        setInterval(refreshStatus, 30000);
    </script>
</body>
</html>
"""
            self._send_html(200, admin_html)
        elif path == "/user":
            # Basic user UI
            user_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TTRPG Center</title>
    <style>
        body {{ 
            background: linear-gradient(135deg, #0c1445 0%, #1a2456 100%);
            color: #00ffff;
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .query-panel {{ 
            background: rgba(0, 255, 255, 0.1);
            border: 1px solid #00ffff;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }}
        .response-area {{
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid #444;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            min-height: 300px;
        }}
        input[type="text"] {{ 
            width: 100%;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border: 1px solid #00ffff;
            color: #00ffff;
            border-radius: 4px;
            margin: 10px 0;
        }}
        button {{ 
            background: #00ffff; 
            color: #000; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
        }}
        button:hover {{ background: #44ffff; }}
        .stats {{ display: flex; gap: 20px; margin: 10px 0; }}
        .stat-badge {{ 
            background: rgba(255, 255, 255, 0.1);
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TTRPG Center</h1>
            <p>Your AI-Powered TTRPG Assistant</p>
        </div>
        
        <div class="query-panel">
            <h3>Ask a Question</h3>
            <input type="text" id="queryInput" placeholder="What would you like to know about TTRPGs?" />
            <div class="stats">
                <div class="stat-badge">Timer: <span id="timer">0ms</span></div>
                <div class="stat-badge">Tokens: <span id="tokens">0</span></div>
                <div class="stat-badge">Model: <span id="model">-</span></div>
            </div>
            <button onclick="submitQuery()">Submit Query</button>
            <button onclick="clearResponse()">Clear</button>
        </div>
        
        <div class="response-area">
            <div id="response">Welcome to TTRPG Center! Ask me anything about tabletop RPGs.</div>
        </div>
    </div>
    
    <script>
        let startTime;
        let currentQueryData = null;
        let sessionId = generateSessionId();
        
        function generateSessionId() {{
            return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }}
        
        function submitQuery() {{
            const query = document.getElementById('queryInput').value;
            if (!query.trim()) return;
            
            startTime = Date.now();
            document.getElementById('response').innerHTML = 'Processing query...';
            document.getElementById('timer').textContent = '0ms';
            document.getElementById('tokens').textContent = '0';
            document.getElementById('model').textContent = 'processing...';
            
            // Real API call
            fetch('/api/query', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{
                    query: query,
                    session_id: sessionId,
                    context: {{
                        app_env: 'user_interface'
                    }}
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                const elapsed = Date.now() - startTime;
                
                // Update UI
                document.getElementById('timer').textContent = (data.latency_ms || elapsed) + 'ms';
                document.getElementById('tokens').textContent = (data.tokens?.total || 0);
                document.getElementById('model').textContent = data.model || 'unknown';
                
                // Store query data for feedback
                currentQueryData = data;
                
                // Format response
                let responseHtml = '<p><strong>Query:</strong> ' + data.query + '</p>';
                responseHtml += '<p><strong>Response:</strong> ' + data.response + '</p>';
                
                // Show sources if available
                if (data.sources && data.sources.length > 0) {{
                    responseHtml += '<div style="margin-top: 15px; font-size: 12px; color: #aaa;">';
                    responseHtml += '<strong>Sources:</strong><br>';
                    data.sources.forEach((source, i) => {{
                        responseHtml += `${{i+1}}. ${{source.source_id}} (page ${{source.page}}) - Score: ${{source.score}}<br>`;
                    }});
                    responseHtml += '</div>';
                }}
                
                // Show workflow info if applicable
                if (data.workflow_execution_id) {{
                    responseHtml += '<div style="margin-top: 10px; padding: 8px; background: rgba(0,100,255,0.1); border-radius: 4px;">';
                    responseHtml += '<strong>Workflow:</strong> ' + data.workflow_execution_id + ' (Status: ' + (data.workflow_status || 'unknown') + ')';
                    responseHtml += '</div>';
                }}
                
                // Add feedback buttons
                responseHtml += '<div style="margin-top: 20px; padding: 10px; background: rgba(0,255,0,0.1); border-radius: 4px;">';
                responseHtml += '<button onclick="thumbsUp()" style="background: #00ff00; margin-right: 10px;">👍 Helpful</button>';
                responseHtml += '<button onclick="thumbsDown()" style="background: #ff4444; color: white;">👎 Not Helpful</button>';
                responseHtml += '</div>';
                
                document.getElementById('response').innerHTML = responseHtml;
            }})
            .catch(error => {{
                console.error('Query failed:', error);
                document.getElementById('response').innerHTML = 
                    '<p style="color: #ff4444;">Error processing query: ' + error.message + '</p>';
            }});
        }}
        
        function thumbsUp() {{
            if (!currentQueryData) {{
                alert('No query data available for feedback');
                return;
            }}
            
            fetch('/api/feedback', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{
                    query_id: currentQueryData.query_id,
                    type: 'positive',
                    query: currentQueryData.query,
                    response: currentQueryData.response,
                    context: {{
                        app_env: '{cfg["runtime"]["env"]}',
                        query_type: currentQueryData.query_type,
                        model_used: currentQueryData.model,
                        sources: currentQueryData.sources || []
                    }}
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                alert('👍 Thank you! ' + (data.message || 'Feedback recorded'));
            }})
            .catch(error => {{
                alert('👍 Feedback noted (offline)');
            }});
        }}
        
        function thumbsDown() {{
            if (!currentQueryData) {{
                alert('No query data available for feedback');
                return;
            }}
            
            const userFeedback = prompt('What was wrong with this response? (optional)', '');
            
            fetch('/api/feedback', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json'
                }},
                body: JSON.stringify({{
                    query_id: currentQueryData.query_id,
                    type: 'negative',
                    query: currentQueryData.query,
                    response: currentQueryData.response,
                    user_feedback: userFeedback || '',
                    context: {{
                        app_env: '{cfg["runtime"]["env"]}',
                        query_type: currentQueryData.query_type,
                        model_used: currentQueryData.model,
                        sources: currentQueryData.sources || []
                    }}
                }})
            }})
            .then(response => response.json())
            .then(data => {{
                alert('👎 Thank you for the feedback! ' + (data.message || 'Bug report created'));
            }})
            .catch(error => {{
                alert('👎 Feedback noted (offline)');
            }});
        }}
        
        function clearResponse() {{
            document.getElementById('response').innerHTML = 'Ready for your next question.';
            document.getElementById('queryInput').value = '';
            document.getElementById('timer').textContent = '0ms';
            document.getElementById('tokens').textContent = '0';
            document.getElementById('model').textContent = '-';
        }}
        
        // Enter key support
        document.getElementById('queryInput').addEventListener('keypress', function(e) {{
            if (e.key === 'Enter') {{
                submitQuery();
            }}
        }});
    </script>
</body>
</html>
"""
            self._send_html(200, user_html)
        else:
            self._send(404, {"error": "not found", "path": self.path})

    def do_POST(self):
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        if path == "/api/query":
            self._handle_query_request()
        elif path == "/api/feedback":
            self._handle_feedback_request()
        elif path == "/api/workflow/start":
            self._handle_workflow_start()
        elif path == "/api/workflow/continue":
            self._handle_workflow_continue()
        elif path == "/api/ingest":
            self._handle_ingestion_request()
        else:
            self._send(404, {"error": "endpoint not found"})
    
    def _handle_query_request(self):
        """Handle main query processing"""
        try:
            # Parse request
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send(400, {"error": "no data provided"})
                return
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            query = data.get('query', '').strip()
            session_id = data.get('session_id', str(uuid.uuid4()))
            user_id = data.get('user_id', 'anonymous')
            context = data.get('context', {})
            
            if not query:
                self._send(400, {"error": "query is required"})
                return
            
            # Generate query ID and start timing
            query_id = str(uuid.uuid4())[:8]
            start_time = time.time()
            
            logger.info(f"Processing query {query_id}: {query[:50]}...")
            
            # Route query
            routing_result = query_router.route_query(query, context)
            query_type = routing_result["query_type"]
            
            # Process based on type
            if query_type == QueryType.RAG_LOOKUP:
                filters = routing_result.get("suggested_filters", {})
                result = rag_engine.query(query, filters=filters)
                
            elif query_type == QueryType.WORKFLOW:
                # Start or continue workflow
                suggested_workflow = routing_result.get("suggested_workflow")
                if suggested_workflow:
                    execution_id = workflow_engine.start_workflow(suggested_workflow, {"query": query})
                    if execution_id:
                        execution = workflow_engine.get_execution(execution_id)
                        step_result = workflow_executor.execute_node(execution, query)
                        
                        result = {
                            "response": step_result.get("response", "Workflow started"),
                            "workflow_execution_id": execution_id,
                            "current_node": execution.current_node,
                            "workflow_status": execution.status,
                            "success": step_result.get("success", True),
                            "query_type": "workflow"
                        }
                    else:
                        result = {"response": "Failed to start workflow", "success": False}
                else:
                    result = {"response": "Workflow type not recognized", "success": False}
            
            elif query_type == QueryType.CALCULATION:
                # Simple calculation handler
                result = {
                    "response": "Calculation queries not yet implemented. Please rephrase as a lookup query.",
                    "success": True,
                    "query_type": "calculation"
                }
            
            else:  # FALLBACK or UNKNOWN
                result = rag_engine._fallback_response(query, "Query type not supported")
            
            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Record metrics
            metrics_collector.record_query(
                query_id=query_id,
                query=query,
                query_type=query_type.value,
                model_used=result.get("model", "unknown"),
                latency_ms=latency_ms,
                token_usage=result.get("tokens", {}),
                success=result.get("success", False),
                user_id=user_id,
                session_id=session_id,
                sources_retrieved=len(result.get("sources", []))
            )
            
            # Format response
            response = {
                "query_id": query_id,
                "query": query,
                "response": result.get("response", "No response generated"),
                "query_type": query_type.value,
                "routing_confidence": routing_result.get("confidence", 0.0),
                "latency_ms": latency_ms,
                "model": result.get("model", "unknown"),
                "tokens": result.get("tokens", {}),
                "sources": result.get("sources", []),
                "success": result.get("success", False),
                "session_id": session_id,
                "workflow_execution_id": result.get("workflow_execution_id"),
                "workflow_status": result.get("workflow_status")
            }
            
            self._send(200, response)
            
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid json"})
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            self._send(500, {"error": f"query processing failed: {str(e)}"})
    
    def _handle_feedback_request(self):
        """Handle user feedback (thumbs up/down)"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            query_id = data.get('query_id', '')
            feedback_type = data.get('type', '')  # 'positive' or 'negative'
            query = data.get('query', '')
            response_text = data.get('response', '')
            user_feedback = data.get('user_feedback', '')
            context = data.get('context', {})
            execution_trace = data.get('execution_trace', [])
            
            if feedback_type == 'positive':
                result = feedback_processor.process_thumbs_up(
                    query=query,
                    response=response_text,
                    context=context,
                    execution_trace=execution_trace
                )
            elif feedback_type == 'negative':
                result = feedback_processor.process_thumbs_down(
                    query=query,
                    response=response_text,
                    context=context,
                    execution_trace=execution_trace,
                    user_feedback=user_feedback
                )
            else:
                self._send(400, {"error": "feedback type must be 'positive' or 'negative'"})
                return
            
            self._send(200, result)
            
        except Exception as e:
            logger.error(f"Feedback processing failed: {e}")
            self._send(500, {"error": f"feedback processing failed: {str(e)}"})
    
    def _handle_workflow_start(self):
        """Start a new workflow execution"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            workflow_id = data.get('workflow_id', '')
            initial_context = data.get('context', {})
            
            execution_id = workflow_engine.start_workflow(workflow_id, initial_context)
            
            if execution_id:
                execution = workflow_engine.get_execution(execution_id)
                self._send(200, {
                    "execution_id": execution_id,
                    "workflow_id": workflow_id,
                    "current_node": execution.current_node,
                    "status": execution.status
                })
            else:
                self._send(400, {"error": f"workflow {workflow_id} not found"})
                
        except Exception as e:
            logger.error(f"Workflow start failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_workflow_continue(self):
        """Continue workflow execution"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            execution_id = data.get('execution_id', '')
            user_input = data.get('user_input', '')
            
            execution = workflow_engine.get_execution(execution_id)
            if not execution:
                self._send(404, {"error": "execution not found"})
                return
            
            # Execute current node
            step_result = workflow_executor.execute_node(execution, user_input)
            
            # Move to next node if successful
            if step_result.get("success", False):
                execution.move_to_next_node(step_result)
            
            self._send(200, {
                "execution_id": execution_id,
                "response": step_result.get("response", ""),
                "current_node": execution.current_node,
                "status": execution.status,
                "step_result": step_result
            })
            
        except Exception as e:
            logger.error(f"Workflow continue failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_ingestion_request(self):
        """Handle file ingestion requests"""
        # Placeholder for ingestion endpoint
        self._send(501, {"error": "ingestion endpoint not yet implemented"})

def main():
    port = cfg["runtime"]["port"]
    env = cfg["runtime"]["env"]
    build_id = os.getenv("APP_RELEASE_BUILD", "dev")
    
    print(f"Starting TTRPG Center on :{port} [{env}] (build: {build_id})")
    print(f"Admin UI: http://localhost:{port}/admin")
    print(f"User UI: http://localhost:{port}/user")
    print(f"Health: http://localhost:{port}/health")
    
    try:
        HTTPServer(("0.0.0.0", port), Handler).serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down TTRPG Center...")

if __name__ == "__main__":
    main()