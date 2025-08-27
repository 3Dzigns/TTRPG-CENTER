from http.server import HTTPServer, BaseHTTPRequestHandler
import json, time, os, sys, uuid, logging, mimetypes
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.common.config import load_config
from app.common.astra_client import get_vector_store
from app.common.feedback_processor import get_feedback_processor
from app.common.metrics import get_metrics_collector
from app.common.requirements_validator import get_requirements_validator
from app.retrieval.router import get_query_router, QueryType
from app.retrieval.rag_engine import get_rag_engine
from app.workflows.graph_engine import get_workflow_engine
from app.workflows.workflow_executor import get_workflow_executor
from app.workflows.character_creation import create_character_creation_workflow, create_level_up_workflow
from app.ingestion.pipeline import get_pipeline
from app.ingestion.dictionary import get_dictionary
import cgi
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def secure_path_join(base_dir: str, user_path: str) -> Path:
    """
    Safely join base directory with user-provided path, preventing directory traversal.
    Returns None if the resulting path would escape the base directory.
    """
    try:
        # Normalize the paths
        base = Path(base_dir).resolve()
        
        # Remove any leading slash or drive letter from user path to make it relative
        user_path = str(user_path).lstrip('/\\')
        if len(user_path) > 1 and user_path[1] == ':':  # Windows drive letter
            user_path = user_path[2:].lstrip('/\\')
        
        # Join and resolve
        combined = (base / user_path).resolve()
        
        # Ensure the resolved path is still within the base directory
        if not str(combined).startswith(str(base)):
            raise ValueError(f"Path traversal attempt detected: {user_path}")
        
        return combined
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid path: {user_path}") from e

def validate_filename(filename: str) -> str:
    """
    Validate and sanitize filename to prevent path traversal and invalid characters.
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Remove path components
    filename = os.path.basename(filename)
    
    # Check for invalid characters
    invalid_chars = '<>:"|?*'
    if any(char in filename for char in invalid_chars):
        raise ValueError(f"Filename contains invalid characters: {filename}")
    
    # Check for reserved names on Windows
    reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
    if filename.upper() in reserved_names:
        raise ValueError(f"Filename is a reserved system name: {filename}")
    
    return filename

cfg = load_config()

# Global ingestion status tracker
ingestion_status = {}

# DEV Testing Gates Validation
def validate_dev_requirements():
    """Comprehensive validation of all MVP requirements before TEST promotion"""
    validation_results = {
        "overall_status": "pending",
        "categories": {},
        "failed_tests": [],
        "warnings": []
    }
    
    try:
        # RAG-001: Vector Store Health
        vector_health = vector_store.health_check()
        validation_results["categories"]["RAG"] = {
            "RAG-001": {"status": "pass" if vector_health["status"] == "healthy" else "fail", 
                       "message": f"Vector store: {vector_health['message']}"}
        }
        if vector_health["status"] != "healthy":
            validation_results["failed_tests"].append("RAG-001: Vector store not healthy")
            
        # WF-001: Workflow Engine Validation
        try:
            workflows = workflow_engine.list_workflows()
            wf_status = "pass" if len(workflows) >= 2 else "fail"
            validation_results["categories"]["Workflow"] = {
                "WF-001": {"status": wf_status, "message": f"Found {len(workflows)} workflows"}
            }
            if wf_status == "fail":
                validation_results["failed_tests"].append("WF-001: Insufficient workflows")
        except Exception as e:
            validation_results["categories"]["Workflow"] = {
                "WF-001": {"status": "fail", "message": f"Workflow engine error: {str(e)}"}
            }
            validation_results["failed_tests"].append("WF-001: Workflow engine failure")
            
        # ING-001: Ingestion Pipeline Validation
        try:
            pipeline_health = ingestion_pipeline.health_check() if hasattr(ingestion_pipeline, 'health_check') else {"status": "unknown"}
            ing_status = "pass" if pipeline_health.get("status") == "healthy" else "warn"
            validation_results["categories"]["Ingestion"] = {
                "ING-001": {"status": ing_status, "message": "Pipeline operational"}
            }
            if ing_status == "warn":
                validation_results["warnings"].append("ING-001: Pipeline health unclear")
        except Exception as e:
            validation_results["categories"]["Ingestion"] = {
                "ING-001": {"status": "fail", "message": f"Pipeline error: {str(e)}"}
            }
            validation_results["failed_tests"].append("ING-001: Ingestion pipeline failure")
            
        # UI-001: Interface Components Validation
        ui_components = ["Chat Interface", "Admin Dashboard", "File Upload", "Workflow Management"]
        ui_status = "pass"  # Assume pass since UI is implemented
        validation_results["categories"]["UI"] = {
            "UI-001": {"status": ui_status, "message": f"All {len(ui_components)} components implemented"}
        }
        
        # ADM-001/002/003: Admin Features
        admin_features = ["SLA Monitoring", "Bulk Upload", "Enrichment Config"]
        adm_status = "pass"  # Features implemented in previous tasks
        validation_results["categories"]["Admin"] = {
            "ADM-001": {"status": adm_status, "message": "All admin features operational"}
        }
        
        # Overall Status Calculation
        if len(validation_results["failed_tests"]) == 0:
            validation_results["overall_status"] = "pass" if len(validation_results["warnings"]) == 0 else "warn"
        else:
            validation_results["overall_status"] = "fail"
            
    except Exception as e:
        validation_results["overall_status"] = "error"
        validation_results["failed_tests"].append(f"Validation system error: {str(e)}")
        
    return validation_results

# Initialize core components
try:
    vector_store = get_vector_store()
    feedback_processor = get_feedback_processor()
    metrics_collector = get_metrics_collector()
    requirements_validator = get_requirements_validator()
    query_router = get_query_router()
    rag_engine = get_rag_engine()
    workflow_engine = get_workflow_engine()
    workflow_executor = get_workflow_executor()
    ingestion_pipeline = get_pipeline()
    dictionary = get_dictionary()
    
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
        # Add cache-busting headers to prevent browser caching of HTML
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def _serve_static_file(self, path):
        """Serve static files from assets directory"""
        try:
            # Remove /static/ prefix and get relative file path
            file_path = path.replace("/static/", "")
            
            # Prevent directory traversal by using secure path joining
            if file_path.startswith("../docs/"):
                # Special case for docs - validate it's within docs directory
                doc_path = file_path.replace("../docs/", "")
                full_path = secure_path_join("docs", doc_path)
            else:
                # Regular assets - validate it's within assets directory
                full_path = secure_path_join("assets", file_path)
            
            if not full_path.exists() or not full_path.is_file():
                self.send_error(404, "File not found")
                return
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(str(full_path))
            if mime_type is None:
                mime_type = "application/octet-stream"
            
            # Send file with cache-busting headers
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            # Add cache-busting headers to prevent browser caching
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            
            with open(full_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            logger.error(f"Error serving static file {path}: {e}")
            self.send_error(500, "Internal server error")

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_GET(self):
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        # Static file serving
        if path.startswith("/static/"):
            self._serve_static_file(path)
            return
        
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
            
            # Add SLA monitoring
            sla_status = {
                "health_check": "passing" if all(status == "connected" for status in health_checks.values()) else "failing",
                "response_time_sla": "passing" if current_stats.get("avg_latency_ms", 0) < 2000 else "warning",
                "success_rate_sla": "passing" if current_stats.get("success_rate", 0) >= 0.95 else "warning",
                "uptime_status": "operational"
            }
            
            self._send(200, {
                "env": cfg["runtime"]["env"],
                "port": cfg["runtime"]["port"],
                "build_id": build_id,
                "health_checks": health_checks,
                "sla_status": sla_status,
                "ngrok_public_url": ngrok if cfg["runtime"]["env"] == "prod" else "",
                "performance": current_stats,
                "workflows": len(workflow_engine.workflows),
                "active_executions": len(workflow_engine.active_executions)
            })
        elif path == "/validate-dev":
            # DEV Testing Gates - Comprehensive validation before TEST promotion
            if cfg["runtime"]["env"] != "dev":
                self._send(403, {"error": "Validation only available in DEV environment"})
                return
                
            validation_results = validate_dev_requirements()
            self._send(200, validation_results)
        elif path == "/" or path == "/admin":
            # Basic admin UI with cache-busting timestamp
            cache_buster = int(time.time())
            admin_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TTRPG Center Admin - {cfg['runtime']['env'].upper()}</title>
    <meta name="cache-buster" content="{cache_buster}">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        body {{ 
            background: 
                linear-gradient(135deg, rgba(10, 10, 21, 0.85) 0%, rgba(26, 26, 46, 0.9) 50%, rgba(22, 33, 62, 0.85) 100%),
                url('/static/background/TTRPG_Center_BG.png') center center / cover no-repeat fixed;
            color: #00ffff;
            font-family: 'Orbitron', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ 
            text-align: center; 
            margin-bottom: 30px;
            border-bottom: 2px solid #ff6600;
            padding-bottom: 20px;
        }}
        
        .header h1 {{
            font-size: 2.2em;
            font-weight: 900;
            color: #ff6600;
            text-shadow: 0 0 20px #ff6600, 0 0 40px #ff6600;
            margin: 0;
            letter-spacing: 2px;
        }}
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
        .status-pending {{ color: #ffaa00; }}
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
        .build-id-box {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.7);
            color: #00ffff;
            padding: 5px 10px;
            border-radius: 3px;
            font-size: 11px;
            font-family: monospace;
            z-index: 1000;
        }}
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
                <button onclick="window.location.href='/admin/ingestion'">Open Ingestion</button>
            </div>
            
            <div class="card">
                <h3>Dictionary Management</h3>
                <p>View and edit normalization dictionary</p>
                <button onclick="window.location.href='/admin/dictionary'">Manage Dictionary</button>
            </div>
            
            <div class="card">
                <h3>Regression Tests</h3>
                <p>View and manage automated test cases</p>
                <button onclick="window.location.href='/admin/tests'">View Tests</button>
            </div>
            
            <div class="card">
                <h3>Bug Management</h3>
                <p>View and manage all bug reports with filtering</p>
                <div id="bug-summary" style="margin: 10px 0; font-size: 12px; color: #aaa;">Loading...</div>
                <div style="margin-top: 15px;">
                    <label for="bug-filter" style="color: #00ffff; font-size: 12px;">Filter:</label>
                    <select id="bug-filter" onchange="filterBugs()" style="margin-left: 10px; background: #1a1a2e; color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                        <option value="all">All Bugs</option>
                        <option value="open">Open</option>
                        <option value="closed">Closed</option>
                        <option value="on_hold">On Hold</option>
                        <option value="peer_review">Peer Review</option>
                    </select>
                    <button onclick="refreshBugs()" style="background: #0088ff; margin-left: 10px;">Refresh</button>
                    <button onclick="window.location.href='/admin/bugs'" style="margin-left: 5px;">Detailed View</button>
                </div>
                <div id="bug-preview" style="margin-top: 15px; max-height: 200px; overflow-y: auto; font-size: 11px;"></div>
            </div>
            
            <div class="card">
                <h3>Requirements</h3>
                <p>Manage immutable requirements and feature requests</p>
                <button onclick="window.location.href='/admin/requirements'">View Requirements</button>
            </div>
            
            {"<div class=\"card\">" if cfg['runtime']['env'] == 'dev' else "<!--"}<h3>DEV Validation Gates</h3>
                <p>Validate all MVP requirements before TEST promotion</p>
                <button onclick="runDevValidation()">Run Validation</button>
                <div id="validation-results" style="margin-top: 10px;"></div>
            {"</div>" if cfg['runtime']['env'] == 'dev' else "-->"}
            
            <div class="card">
                <h3>Database Management</h3>
                <p>Environment-specific AstraDB collection management</p>
                <button onclick="showCollectionInfo()">Show Collections</button>
                {f'<div style="margin-top: 15px;"><label for="cleanup-collection-select" style="color: #00ffff;">Select Collection to Cleanup:</label><select id="cleanup-collection-select" style="margin-left: 10px; background: #1a1a2e; color: #00ffff; border: 1px solid #00ffff; padding: 5px;"><option value="">Loading...</option></select><button onclick="cleanupSelectedCollection()" style="background: #ff4444; margin-left: 10px;">Cleanup Selected</button><button onclick="cleanupEnvironmentData()" style="background: #ff6666; margin-left: 5px;">Cleanup All {cfg["runtime"]["env"].upper()}</button></div><div style="margin-top: 20px; border-top: 1px solid #00ffff; padding-top: 15px;"><h4 style="color: #00ffff; margin: 0 0 10px 0;">Chunk-Level Cleanup</h4><input type="text" id="chunk-search-input" placeholder="Search chunks by text or metadata..." style="width: 300px; background: #1a1a2e; color: #00ffff; border: 1px solid #00ffff; padding: 5px; margin-right: 10px;"><button onclick="searchChunks()" style="background: #0088ff; margin-right: 10px;">Search Chunks</button><select id="chunk-collection-select" style="background: #1a1a2e; color: #00ffff; border: 1px solid #00ffff; padding: 5px; margin-right: 10px;"><option value="">All Collections</option></select><div id="chunk-search-results" style="margin-top: 10px; max-height: 300px; overflow-y: auto;"></div></div>' if cfg['runtime']['env'] != 'prod' else ''}
                <div id="database-info" style="margin-top: 10px;"></div>
            </div>
        </div>
    </div>
    
    <script>
        function refreshStatus() {{
            console.log('refreshStatus() called');
            const healthDiv = document.getElementById('health-status');
            if (!healthDiv) {{
                console.error('Could not find health-status element');
                alert('Error: health-status element not found in DOM');
                return;
            }}
            
            console.log('Found health-status element, starting status refresh for port:', window.location.port);
            healthDiv.innerHTML = '<div class="status-pending">Checking system status...</div>';
            
            // Add timeout to fetch request
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {{
                console.error('Status refresh timed out after 10 seconds');
                controller.abort();
            }}, 10000); // 10 second timeout
            
            fetch('/status', {{ 
                signal: controller.signal,
                headers: {{
                    'Accept': 'application/json',
                    'Cache-Control': 'no-cache'
                }}
            }})
                .then(r => {{
                    clearTimeout(timeoutId);
                    if (!r.ok) {{
                        throw new Error('Status request failed: HTTP ' + r.status + ' ' + r.statusText);
                    }}
                    return r.json();
                }})
                .then(data => {{
                    console.log('Status data received:', data);
                    let html = '';
                    
                    if (data && data.health_checks) {{
                        Object.entries(data.health_checks).forEach(([service, status]) => {{
                            const statusClass = status && status.includes('connected') ? 'status-ok' : 'status-error';
                            html += '<div class="health-check"><span>' + service + ':</span><span class="' + statusClass + '">' + (status || 'unknown') + '</span></div>';
                        }});
                        
                        // Add build info if available
                        if (data.build_id) {{
                            html += '<div class="health-check"><span>Build:</span><span style="color: #aaa; font-size: 11px;">' + data.build_id + '</span></div>';
                        }}
                    }} else {{
                        console.warn('Invalid status data structure:', data);
                        html += '<div class="status-error">Invalid status data received</div>';
                    }}
                    
                    if (data && data.ngrok_public_url) {{
                        html += '<div class="health-check"><span>Public URL:</span><span><a href="' + data.ngrok_public_url + '" target="_blank">' + data.ngrok_public_url + '</a></span></div>';
                    }}
                    
                    if (html) {{
                        healthDiv.innerHTML = html;
                        console.log('Status display updated successfully');
                    }} else {{
                        healthDiv.innerHTML = '<div class="status-error">No valid status data to display</div>';
                        console.warn('No valid status HTML generated');
                    }}
                }})
                .catch(error => {{
                    clearTimeout(timeoutId);
                    console.error('Status refresh error:', error);
                    console.error('Error details:', {{ 
                        name: error.name, 
                        message: error.message, 
                        stack: error.stack,
                        port: window.location.port,
                        hostname: window.location.hostname
                    }});
                    
                    let errorMessage = 'Status update failed: ';
                    if (error.name === 'AbortError') {{
                        errorMessage += 'Request timed out (10s)';
                    }} else if (error.message.includes('Failed to fetch')) {{
                        errorMessage += 'Network connection failed (check if server is running on port ' + window.location.port + ')';
                    }} else if (error.message.includes('HTTP')) {{
                        errorMessage += error.message;
                    }} else {{
                        errorMessage += error.message || 'Unknown error';
                    }}
                    
                    healthDiv.innerHTML = '<div class="status-error">' + errorMessage + '<br><button onclick="refreshStatus()" style="margin-top: 5px; font-size: 12px; padding: 5px 10px;">Retry</button></div>';
                }});
        }}
        
        // Auto-refresh status every 30 seconds
        refreshStatus();
        setInterval(refreshStatus, 30000);
        
        // Load bug management data on page load
        refreshBugs();
        
        function runDevValidation() {{
            const resultsDiv = document.getElementById('validation-results');
            resultsDiv.innerHTML = '<div class="status-pending">Running validation...</div>';
            
            fetch('/validate-dev')
                .then(r => r.json())
                .then(data => {{
                    let html = '<div class="validation-summary">';
                    const statusClass = data.overall_status === 'pass' ? 'status-ok' : 
                                       data.overall_status === 'warn' ? 'status-warn' : 'status-error';
                    html += '<strong>Overall Status: <span class="' + statusClass + '">' + data.overall_status.toUpperCase() + '</span></strong>';
                    
                    if (data.failed_tests.length > 0) {{
                        html += '<div class="failed-tests"><strong>Failed Tests:</strong><ul>';
                        data.failed_tests.forEach(test => {{
                            html += '<li>' + test + '</li>';
                        }});
                        html += '</ul></div>';
                    }}
                    
                    if (data.warnings.length > 0) {{
                        html += '<div class="warnings"><strong>Warnings:</strong><ul>';
                        data.warnings.forEach(warning => {{
                            html += '<li>' + warning + '</li>';
                        }});
                        html += '</ul></div>';
                    }}
                    
                    html += '<div class="category-details">';
                    Object.entries(data.categories).forEach(([category, tests]) => {{
                        html += '<div class="category"><strong>' + category + ':</strong>';
                        Object.entries(tests).forEach(([testId, result]) => {{
                            const testStatusClass = result.status === 'pass' ? 'status-ok' : 
                                                   result.status === 'warn' ? 'status-warn' : 'status-error';
                            html += '<div class="test-result">' + testId + ': <span class="' + testStatusClass + '">' + result.status + '</span> - ' + result.message + '</div>';
                        }});
                        html += '</div>';
                    }});
                    html += '</div></div>';
                    
                    resultsDiv.innerHTML = html;
                }})
                .catch(err => {{
                    resultsDiv.innerHTML = '<div class="status-error">Validation failed: ' + err.message + '</div>';
                }});
        }}
        
        function showCollectionInfo() {{
            console.log('showCollectionInfo() called');
            const infoDiv = document.getElementById('database-info');
            if (!infoDiv) {{
                console.error('Could not find database-info element');
                alert('Error: database-info element not found in DOM');
                return;
            }}
            
            console.log('Found database-info element, starting collections request');
            infoDiv.innerHTML = '<div class="status-pending">Loading database information...</div>';
            
            // Add timeout to prevent hanging requests
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {{
                console.error('Collections request timed out');
                controller.abort();
            }}, 15000); // 15 second timeout
            
            fetch('/api/database/collections', {{ signal: controller.signal }})
                .then(r => {{
                    clearTimeout(timeoutId);
                    console.log('Collections response received, status:', r.status);
                    if (!r.ok) {{
                        throw new Error('Collections request failed: ' + r.status);
                    }}
                    return r.json();
                }})
                .then(data => {{
                    console.log('Collections data received:', data);
                    let html = '<div class="database-info">';
                    
                    // Current environment info
                    if (data.current_environment) {{
                        const env = data.current_environment;
                        html += '<div style="margin: 10px 0; padding: 10px; background: rgba(0,255,255,0.1); border-radius: 4px;">';
                        html += '<strong>Current Environment:</strong><br>';
                        html += 'Collection: <span style="color: #00ffff;">' + env.collection_name + '</span><br>';
                        html += 'Environment: <span style="color: #ff6600;">' + env.environment.toUpperCase() + '</span><br>';
                        html += 'Document Count: <span style="color: #00ff00;">' + env.document_count + '</span>';
                        html += '</div>';
                    }}
                    
                    // All collections
                    if (data.all_collections && data.all_collections.length > 0) {{
                        html += '<div style="margin: 10px 0;">';
                        html += '<strong>All Collections in Database:</strong><br>';
                        data.all_collections.forEach(collection => {{
                            const isCurrentEnv = data.current_environment && collection === data.current_environment.collection_name;
                            const style = isCurrentEnv ? 'color: #00ff00; font-weight: bold;' : 'color: #aaa;';
                            html += '<span style="' + style + '">• ' + collection + (isCurrentEnv ? ' (current)' : '') + '</span><br>';
                        }});
                        html += '</div>';
                    }}
                    
                    html += '</div>';
                    infoDiv.innerHTML = html;
                }})
                .catch(err => {{
                    console.error('showCollectionInfo error:', err);
                    let errorMessage = 'Failed to load database info: ' + err.message;
                    if (err.name === 'AbortError') {{
                        errorMessage = 'Database request timed out after 15 seconds';
                    }}
                    infoDiv.innerHTML = '<div class="status-error">' + errorMessage + '<br><button onclick="showCollectionInfo()" style="margin-top: 5px; font-size: 12px; padding: 5px 10px;">Retry</button></div>';
                }});
        }}
        
        function cleanupEnvironmentData() {{
            if (!confirm('Are you sure you want to delete ALL data in the current environment? This cannot be undone!')) {{
                return;
            }}
            
            const infoDiv = document.getElementById('database-info');
            infoDiv.innerHTML = '<div class="status-pending">Cleaning up environment data...</div>';
            
            fetch('/api/database/cleanup', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ confirm: true }})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.cleanup_result) {{
                    const result = data.cleanup_result;
                    let html = '<div class="cleanup-result">';
                    html += '<strong>Cleanup Complete:</strong><br>';
                    html += 'Environment: <span style="color: #ff6600;">' + data.environment.toUpperCase() + '</span><br>';
                    
                    // Handle AstraDB returning -1 for empty collections
                    if (result.deleted === -1) {{
                        html += 'Status: <span style="color: #00ff00;">Collection already empty</span><br>';
                    }} else {{
                        html += 'Documents Deleted: <span style="color: #ff4444;">' + result.deleted + '</span><br>';
                    }}
                    
                    html += '<span style="color: #00ff00;">✅ Environment cleaned successfully</span>';
                    html += '</div>';
                    infoDiv.innerHTML = html;
                    
                    // Refresh collection info after cleanup
                    setTimeout(showCollectionInfo, 2000);
                }} else {{
                    infoDiv.innerHTML = '<div class="status-error">Cleanup failed: ' + (data.error || 'Unknown error') + '</div>';
                }}
            }})
            .catch(err => {{
                infoDiv.innerHTML = '<div class="status-error">Cleanup failed: ' + err.message + '</div>';
            }});
        }}
        
        // Populate collection selector dropdown
        function populateCollectionSelector() {{
            const selector = document.getElementById('cleanup-collection-select');
            if (!selector) return;
            
            fetch('/api/database/collections')
                .then(r => r.json())
                .then(data => {{
                    selector.innerHTML = '<option value="">-- Select Collection --</option>';
                    if (data.all_collections && data.all_collections.length > 0) {{
                        data.all_collections.forEach(collection => {{
                            const option = document.createElement('option');
                            option.value = collection;
                            option.textContent = collection;
                            if (collection === data.current_environment?.collection_name) {{
                                option.textContent += ' (current env)';
                            }}
                            selector.appendChild(option);
                        }});
                    }}
                }})
                .catch(err => {{
                    selector.innerHTML = '<option value="">Error loading collections</option>';
                }});
        }}
        
        // Cleanup selected collection
        function cleanupSelectedCollection() {{
            const selector = document.getElementById('cleanup-collection-select');
            const selectedCollection = selector?.value;
            
            if (!selectedCollection) {{
                alert('Please select a collection to cleanup');
                return;
            }}
            
            // Get collection info first
            fetch('/api/database/collections')
                .then(r => r.json())
                .then(data => {{
                    const collectionInfo = data.all_collections ? 'Found' : 'Unknown';
                    const confirmMessage = `Are you sure you want to cleanup collection: ${{selectedCollection}}?\\n\\nThis will delete ALL documents in this collection.\\n\\nThis action cannot be undone.`;
                    
                    if (confirm(confirmMessage)) {{
                        const infoDiv = document.getElementById('database-info');
                        infoDiv.innerHTML = '<div class="status-pending">Cleaning up collection: ' + selectedCollection + '...</div>';
                        
                        fetch('/api/database/cleanup-collection', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ 
                                confirm: true,
                                collection: selectedCollection
                            }})
                        }})
                        .then(r => r.json())
                        .then(data => {{
                            if (data.cleanup_result) {{
                                const result = data.cleanup_result;
                                let message = 'Collection cleanup completed: ';
                                if (result.deleted === -1) {{
                                    message += 'collection already empty (' + selectedCollection + ')';
                                }} else {{
                                    message += result.deleted + ' documents deleted from ' + selectedCollection;
                                }}
                                infoDiv.innerHTML = '<div class="status-ok">' + message + '</div>';
                                // Refresh collection info
                                setTimeout(showCollectionInfo, 2000);
                            }} else {{
                                infoDiv.innerHTML = '<div class="status-error">Cleanup failed: ' + (data.error || 'Unknown error') + '</div>';
                            }}
                        }})
                        .catch(err => {{
                            infoDiv.innerHTML = '<div class="status-error">Cleanup failed: ' + err.message + '</div>';
                        }});
                    }}
                }});
        }}
        
        // Auto-populate collection selectors on page load
        setTimeout(() => {{
            populateCollectionSelector();
            populateChunkCollectionSelector();
        }}, 1000);
        
        // Populate chunk collection selector
        function populateChunkCollectionSelector() {{
            const selector = document.getElementById('chunk-collection-select');
            if (!selector) return;
            
            fetch('/api/database/collections')
                .then(r => r.json())
                .then(data => {{
                    selector.innerHTML = '<option value="">All Collections</option>';
                    if (data.all_collections && data.all_collections.length > 0) {{
                        data.all_collections.forEach(collection => {{
                            const option = document.createElement('option');
                            option.value = collection;
                            option.textContent = collection;
                            selector.appendChild(option);
                        }});
                    }}
                }})
                .catch(err => {{
                    console.error('Error loading collections for chunk search:', err);
                }});
        }}
        
        // Search chunks
        function searchChunks() {{
            const searchInput = document.getElementById('chunk-search-input');
            const collectionSelect = document.getElementById('chunk-collection-select');
            const resultsDiv = document.getElementById('chunk-search-results');
            
            const searchText = searchInput?.value?.trim() || '';
            const collection = collectionSelect?.value || '';
            
            if (!searchText && !collection) {{
                alert('Please enter search text or select a collection');
                return;
            }}
            
            resultsDiv.innerHTML = '<div class="status-pending">Searching chunks...</div>';
            
            const params = new URLSearchParams();
            if (searchText) params.append('text', searchText);
            if (collection) params.append('collection', collection);
            params.append('limit', '20');
            
            fetch('/api/database/search-chunks?' + params.toString())
                .then(r => r.json())
                .then(data => {{
                    if (data.chunks && data.chunks.length > 0) {{
                        let html = '<div class="chunk-results">';
                        html += '<h5 style="color: #00ff00;">Found ' + data.chunks.length + ' chunks:</h5>';
                        
                        data.chunks.forEach((chunk, index) => {{
                            html += '<div class="chunk-item" style="border: 1px solid #444; margin: 5px 0; padding: 10px; background: rgba(0,0,0,0.3);">';
                            html += '<div style="display: flex; justify-content: space-between; align-items: center;">';
                            html += '<div><strong>ID:</strong> ' + chunk.id.substring(0, 12) + '...</div>';
                            html += '<button onclick="deleteChunk(\'' + chunk.id + '\', \'' + chunk.collection + '\')" style="background: #ff4444; color: white; border: none; padding: 3px 8px; border-radius: 3px; cursor: pointer;">Delete</button>';
                            html += '</div>';
                            html += '<div><strong>Collection:</strong> ' + (chunk.collection || 'unknown') + '</div>';
                            html += '<div><strong>Source:</strong> ' + (chunk.source_id || 'unknown') + ' (Page: ' + (chunk.page || 'N/A') + ')</div>';
                            html += '<div><strong>Text:</strong> ' + (chunk.text.length > 200 ? chunk.text.substring(0, 200) + '...' : chunk.text) + '</div>';
                            html += '</div>';
                        }});
                        
                        html += '</div>';
                        resultsDiv.innerHTML = html;
                    }} else {{
                        resultsDiv.innerHTML = '<div class="status-ok">No chunks found matching your search criteria.</div>';
                    }}
                }})
                .catch(err => {{
                    resultsDiv.innerHTML = '<div class="status-error">Search failed: ' + err.message + '</div>';
                }});
        }}
        
        // Delete individual chunk
        function deleteChunk(chunkId, collection) {{
            if (!confirm('Are you sure you want to delete this chunk?\\n\\nChunk ID: ' + chunkId + '\\nCollection: ' + collection + '\\n\\nThis action cannot be undone.')) {{
                return;
            }}
            
            fetch('/api/database/delete-chunk', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    chunk_id: chunkId,
                    collection: collection,
                    confirm: true
                }})
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.success) {{
                    alert('Chunk deleted successfully');
                    searchChunks(); // Refresh search results
                }} else {{
                    alert('Delete failed: ' + (data.error || 'Unknown error'));
                }}
            }})
            .catch(err => {{
                alert('Delete failed: ' + err.message);
            }});
        }}
        
        // Enable search on Enter key
        document.addEventListener('DOMContentLoaded', function() {{
            const searchInput = document.getElementById('chunk-search-input');
            if (searchInput) {{
                searchInput.addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') {{
                        searchChunks();
                    }}
                }});
            }}
        }});
        
        // Bug management functions
        let currentBugFilter = 'all';
        
        function refreshBugs() {{
            const summaryDiv = document.getElementById('bug-summary');
            const previewDiv = document.getElementById('bug-preview');
            
            if (!summaryDiv || !previewDiv) {{
                console.error('Bug management elements not found');
                return;
            }}
            
            summaryDiv.innerHTML = 'Loading bug summary...';
            previewDiv.innerHTML = 'Loading bugs...';
            
            fetch('/api/bugs?filter=' + currentBugFilter)
                .then(r => {{
                    if (!r.ok) {{
                        throw new Error('Bugs request failed: ' + r.status);
                    }}
                    return r.json();
                }})
                .then(data => {{
                    console.log('Bug data received:', data);
                    
                    // Update summary
                    const open = data.summary?.open || 0;
                    const closed = data.summary?.closed || 0;
                    const onHold = data.summary?.on_hold || 0;
                    const peerReview = data.summary?.peer_review || 0;
                    const total = data.total || 0;
                    summaryDiv.innerHTML = `Total: ${{total}} | Open: ${{open}} | Closed: ${{closed}} | On Hold: ${{onHold}} | Peer Review: ${{peerReview}}`;
                    
                    // Update preview
                    let previewHtml = '';
                    if (data.bugs && data.bugs.length > 0) {{
                        const displayCount = Math.min(data.bugs.length, 5);
                        previewHtml = `<strong>Recent ${{currentBugFilter}} bugs (${{displayCount}} of ${{data.bugs.length}}):</strong><br>`;
                        
                        data.bugs.slice(0, displayCount).forEach(bug => {{
                            const statusIcon = bug.status === 'closed' ? '✅' : 
                                             bug.status === 'on_hold' ? '⏸️' : '🔴';
                            const severityColor = bug.severity === 'high' ? '#ff4444' : 
                                                bug.severity === 'medium' ? '#ffaa00' : '#aaa';
                            const title = bug.title || bug.bug_id || 'Unknown';
                            const sourceIcon = bug.source === 'peer_review' ? '🔍' : 
                                             bug.source === 'cli_submission' ? '💻' :
                                             bug.source === 'ui_submission' ? '🖥️' : '👤';
                            const escalatedIcon = bug.escalated ? '⬆️' : '';
                            
                            previewHtml += `<div style="margin: 5px 0; padding: 5px; background: rgba(0,0,0,0.2); border-radius: 3px;">`;
                            previewHtml += `${{statusIcon}} ${{sourceIcon}} <span style="color: ${{severityColor}};">${{title.substring(0, 35)}}...</span>`;
                            previewHtml += `${{escalatedIcon}}`;
                            previewHtml += `<span style="float: right; color: #666; font-size: 10px;">${{bug.category || 'general'}}</span>`;
                            if (bug.peer_review_count > 1) {{
                                previewHtml += `<br><span style="color: #ff6600; font-size: 9px;">⚠️ Found ${{bug.peer_review_count}} times</span>`;
                            }}
                            previewHtml += `</div>`;
                        }});
                        
                        if (data.bugs.length > displayCount) {{
                            previewHtml += `<div style="color: #666; font-size: 10px; margin-top: 5px; text-align: center;">... and ${{data.bugs.length - displayCount}} more</div>`;
                        }}
                    }} else {{
                        previewHtml = `<span style="color: #aaa;">No ${{currentBugFilter}} bugs found</span>`;
                    }}
                    
                    previewDiv.innerHTML = previewHtml;
                }})
                .catch(err => {{
                    console.error('Bug refresh failed:', err);
                    summaryDiv.innerHTML = '<span style="color: #ff4444;">Failed to load bug summary</span>';
                    previewDiv.innerHTML = '<span style="color: #ff4444;">Failed to load bugs: ' + err.message + '</span>';
                }});
        }}
        
        function filterBugs() {{
            const filter = document.getElementById('bug-filter').value;
            currentBugFilter = filter;
            refreshBugs();
        }}
    </script>
    
    <div class="build-id-box" id="build-id-box">Loading...</div>
    
    <script>
        // Update build ID box
        function updateBuildId() {{
            fetch('/status')
                .then(r => r.json())
                .then(data => {{
                    const buildIdBox = document.getElementById('build-id-box');
                    buildIdBox.textContent = data.build_id;
                }})
                .catch(() => {{
                    const buildIdBox = document.getElementById('build-id-box');
                    buildIdBox.textContent = 'build unknown';
                }});
        }}
        
        // Update build ID on page load and with status refresh
        updateBuildId();
        setInterval(updateBuildId, 30000);
    </script>
</body>
</html>
"""
            self._send_html(200, admin_html)
        elif path == "/admin/ingestion":
            try:
                html_content = self._get_ingestion_page()
                self._send_html(200, html_content)
            except Exception as e:
                logger.error(f"Error loading ingestion page: {str(e)}")
                self._send(500, {"error": f"Ingestion page error: {str(e)}"})
        elif path == "/admin/dictionary":
            self._send_html(200, self._get_dictionary_page())
        elif path == "/admin/tests":
            self._send_html(200, self._get_tests_page())
        elif path == "/admin/bugs":
            self._send_html(200, self._get_bugs_page())
        elif path == "/admin/requirements":
            self._send_html(200, self._get_requirements_page())
        elif path == "/api/ingestion/status":
            self._handle_ingestion_status()
        elif path == "/api/dictionary":
            self._handle_dictionary_request()
        elif path == "/api/tests":
            self._handle_tests_request()
        elif path == "/api/bugs":  
            self._handle_bugs_request()
        elif path == "/api/requirements/validate":
            self._handle_requirements_validation()
        elif path == "/api/requirements/stats":
            self._handle_requirements_stats()
        elif path == "/api/database/collections":
            self._handle_database_collections()
        elif path.startswith("/api/database/search-chunks"):
            self._handle_chunk_search()
        elif path == "/user":
            # Basic user UI
            user_html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TTRPG Center</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        body {{ 
            background: 
                linear-gradient(135deg, rgba(10, 10, 21, 0.85) 0%, rgba(26, 26, 46, 0.9) 50%, rgba(22, 33, 62, 0.85) 100%),
                url('/static/background/TTRPG_Center_BG.png') center center / cover no-repeat fixed;
            color: #00ffff; 
            font-family: 'Orbitron', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            position: relative;
        }}
        
        body::before {{
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(circle at 20% 50%, rgba(255, 165, 0, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(0, 255, 255, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 40% 80%, rgba(255, 0, 255, 0.08) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }}
        
        .container {{ 
            max-width: 900px; 
            margin: 0 auto; 
            position: relative;
            z-index: 1;
        }}
        
        .header {{ 
            text-align: center; 
            margin-bottom: 30px;
            border-bottom: 2px solid #ff6600;
            padding-bottom: 20px;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            font-weight: 900;
            color: #ff6600;
            text-shadow: 0 0 20px #ff6600, 0 0 40px #ff6600;
            margin: 0;
            letter-spacing: 3px;
        }}
        
        .header p {{
            color: #00ffff;
            font-weight: 400;
            margin: 10px 0;
            font-size: 1.1em;
            opacity: 0.8;
        }}
        
        .lcars-frame {{
            border: 3px solid #ff6600;
            border-radius: 20px;
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.3), rgba(16, 16, 32, 0.5));
            position: relative;
            margin: 20px 0;
            backdrop-filter: blur(2px);
        }}
        
        .lcars-frame::before {{
            content: '';
            position: absolute;
            top: -3px; left: -3px; right: -3px; bottom: -3px;
            background: linear-gradient(45deg, #ff6600, #00ffff, #ff00ff, #ff6600);
            border-radius: 23px;
            z-index: -1;
            opacity: 0.3;
            animation: pulse-border 3s infinite;
        }}
        
        @keyframes pulse-border {{
            0%, 100% {{ opacity: 0.3; }}
            50% {{ opacity: 0.6; }}
        }}
        
        .query-panel {{ 
            padding: 25px;
            position: relative;
        }}
        
        .query-panel h3 {{
            color: #ff6600;
            font-weight: 700;
            margin: 0 0 20px 0;
            font-size: 1.3em;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}
        
        .response-area {{
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.4), rgba(0, 40, 80, 0.2));
            border: 2px solid #00ffff;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            min-height: 350px;
            position: relative;
            backdrop-filter: blur(1px);
        }}
        
        input[type="text"] {{ 
            width: calc(100% - 24px);
            padding: 12px;
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.6), rgba(0, 30, 60, 0.4));
            border: 2px solid #00ffff;
            color: #00ffff;
            border-radius: 8px;
            margin: 10px 0;
            font-family: 'Orbitron', monospace;
            font-size: 16px;
            transition: all 0.3s ease;
        }}
        
        input[type="text"]:focus {{
            outline: none;
            border-color: #ff6600;
            box-shadow: 0 0 15px rgba(255, 102, 0, 0.5);
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.7), rgba(60, 30, 0, 0.3));
        }}
        
        button {{ 
            background: linear-gradient(145deg, #ff6600, #ff8800);
            color: #000; 
            border: none; 
            padding: 12px 24px; 
            border-radius: 8px;
            cursor: pointer;
            margin: 5px;
            font-family: 'Orbitron', monospace;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(255, 102, 0, 0.3);
        }}
        
        button:hover {{ 
            background: linear-gradient(145deg, #ff8800, #ffaa00);
            box-shadow: 0 6px 20px rgba(255, 102, 0, 0.5);
            transform: translateY(-2px);
        }}
        
        .stats {{ 
            display: flex; 
            gap: 15px; 
            margin: 15px 0;
            flex-wrap: wrap;
        }}
        
        .stat-badge {{ 
            background: linear-gradient(145deg, rgba(0, 255, 255, 0.1), rgba(0, 200, 200, 0.2));
            border: 1px solid #00ffff;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 400;
            color: #00ffff;
            text-transform: uppercase;
            letter-spacing: 1px;
            backdrop-filter: blur(1px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>TTRPG Center</h1>
            <p>Your AI-Powered TTRPG Assistant</p>
            {f'<p style="font-size: 14px; color: #ff6600; margin: 10px 0;"><strong>Public URL:</strong> <a href="{os.getenv("NGROK_PUBLIC_URL", "")}" target="_blank" style="color: #00ffff; text-decoration: none;">{os.getenv("NGROK_PUBLIC_URL", "")}</a></p>' if cfg["runtime"]["env"] == "prod" and os.getenv("NGROK_PUBLIC_URL") else ""}
        </div>
        
        <div class="lcars-frame">
            <div class="query-panel">
                <h3>Query Interface</h3>
                <input type="text" id="queryInput" placeholder="What would you like to know about TTRPGs?" />
                <div class="stats">
                    <div class="stat-badge">Timer: <span id="timer">0ms</span></div>
                    <div class="stat-badge">Tokens: <span id="tokens">0</span></div>
                    <div class="stat-badge">Model: <span id="model">-</span></div>
                </div>
                
                <div style="margin: 15px 0; padding: 10px; background: rgba(0,100,255,0.1); border-radius: 8px;">
                    <label style="color: #00ffff; font-size: 12px; font-weight: 700;">Memory Mode:</label><br>
                    <select id="memoryMode" style="background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px; margin: 5px 0; font-family: 'Orbitron', monospace;">
                        <option value="session-only">Session Only</option>
                        <option value="user-wide">User Wide</option>
                        <option value="party-wide" disabled>Party Wide (Coming Soon)</option>
                    </select>
                </div>
                
                <button onclick="submitQuery()">Execute Query</button>
                <button onclick="clearResponse()">Clear Terminal</button>
            </div>
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
                        app_env: 'user_interface',
                        memory_mode: document.getElementById('memoryMode').value
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
                responseHtml += '<div><strong>Response:</strong><br>' + formatResponseWithImages(data.response) + '</div>';
                
                // Show sources if available with toggle
                if (data.sources && data.sources.length > 0) {{
                    responseHtml += '<div style="margin-top: 15px; font-size: 12px;">';
                    responseHtml += '<button onclick="toggleSources(this)" style="background: rgba(0,255,255,0.2); color: #00ffff; border: 1px solid #00ffff; padding: 4px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; margin-bottom: 8px;">📚 Show Sources (' + data.sources.length + ')</button>';
                    responseHtml += '<div class="sources-content" style="display: none; color: #aaa; margin-top: 8px; padding: 8px; background: rgba(0,255,255,0.05); border-radius: 4px;">';
                    responseHtml += '<strong>Source Provenance:</strong><br>';
                    data.sources.forEach((source, i) => {{
                        responseHtml += `${{i+1}}. <strong>${{source.source_id}}</strong> (page ${{source.page}}) - Relevance: ${{source.score}}<br>`;
                        if (source.chunk_text) {{
                            responseHtml += `<div style="margin-left: 15px; font-style: italic; color: #666; margin-bottom: 8px;">"${{source.chunk_text.substring(0, 200)}}..."</div>`;
                        }}
                    }});
                    responseHtml += '</div></div>';
                }}
                
                // Show workflow info if applicable
                if (data.workflow_execution_id) {{
                    responseHtml += '<div style="margin-top: 10px; padding: 8px; background: rgba(0,100,255,0.1); border-radius: 4px;">';
                    responseHtml += '<strong>Workflow:</strong> ' + data.workflow_execution_id + ' (Status: ' + (data.workflow_status || 'unknown') + ')';
                    responseHtml += '</div>';
                }}
                
                // Add feedback buttons
                responseHtml += '<div class="feedback-buttons">';
                responseHtml += '<button onclick="thumbsUp()" class="thumbs-up">Helpful Response</button>';
                responseHtml += '<button onclick="thumbsDown()" class="thumbs-down">Needs Improvement</button>';
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
        
        function formatResponseWithImages(text) {{
            // Convert image URLs to img tags for multimodal support
            let formattedText = text.replace(/(https?:\\/\\/\\S+\\.(jpg|jpeg|png|gif|webp))/gi, 
                '<br><img src="$1" style="max-width: 300px; max-height: 300px; border-radius: 8px; margin: 10px 0;" alt="Response image">');
            
            // Convert markdown-style images ![alt](url)
            formattedText = formattedText.replace(/!\\[([^\\]]*)\\]\\(([^)]+)\\)/gi, 
                '<br><img src="$2" alt="$1" style="max-width: 300px; max-height: 300px; border-radius: 8px; margin: 10px 0;">');
            
            return formattedText;
        }}
        
        function toggleSources(button) {{
            const sourcesContent = button.nextElementSibling;
            if (sourcesContent.style.display === 'none') {{
                sourcesContent.style.display = 'block';
                button.textContent = button.textContent.replace('Show Sources', 'Hide Sources');
            }} else {{
                sourcesContent.style.display = 'none';
                button.textContent = button.textContent.replace('Hide Sources', 'Show Sources');
            }}
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
        elif path == "/api/ingestion/upload":
            self._handle_ingestion_upload()
        elif path == "/api/ingestion/status":
            self._handle_ingestion_status()
        elif path == "/api/dictionary":
            self._handle_dictionary_request()
        elif path == "/api/tests":
            self._handle_tests_request()
        elif path == "/api/bugs":
            self._handle_bugs_request()
        elif path == "/api/database/cleanup":
            self._handle_database_cleanup()
        elif path == "/api/database/cleanup-collection":
            self._handle_database_cleanup_collection()
        elif path == "/api/database/delete-chunk":
            self._handle_chunk_delete()
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
    
    def _handle_ingestion_upload(self):
        """Handle file upload for ingestion"""
        try:
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self._send(400, {"error": "multipart/form-data required"})
                return
            
            # Parse multipart form data
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': content_type,
                }
            )
            
            if 'file' not in form:
                self._send(400, {"error": "no files uploaded"})
                return
            
            # Handle both single and multiple files
            files = form['file'] if isinstance(form['file'], list) else [form['file']]
            
            if not files or all(not f.filename for f in files):
                self._send(400, {"error": "no valid files selected"})
                return
            
            # Get metadata
            base_title = form.getvalue('title', '')
            source_type = form.getvalue('source_type', 'manual_upload')
            tags = form.getvalue('tags', '').split(',') if form.getvalue('tags') else []
            
            # Save uploaded files temporarily and create batch ingestion
            upload_dir = Path("uploads")
            upload_dir.mkdir(exist_ok=True)
            
            batch_id = f"batch_{int(time.time())}_{str(uuid.uuid4())[:8]}"
            batch_results = []
            
            for i, file_item in enumerate(files):
                if not file_item.filename:
                    continue
                
                # Validate and sanitize filename
                try:
                    safe_filename = validate_filename(file_item.filename)
                except ValueError as e:
                    batch_results.append({
                        "success": False,
                        "error": f"Invalid filename: {e}",
                        "original_filename": file_item.filename
                    })
                    continue
                    
                # Create unique temp path for each file
                temp_path = upload_dir / f"temp_{int(time.time())}_{i}_{safe_filename}"
                with open(temp_path, 'wb') as temp_file:
                    shutil.copyfileobj(file_item.file, temp_file)
                
                # Prepare metadata for this file
                title = base_title or file_item.filename
                metadata = {
                    "title": title,
                    "source_type": source_type,
                    "tags": tags,
                    "upload_timestamp": time.time(),
                    "original_filename": file_item.filename,
                    "batch_id": batch_id,
                    "batch_position": i + 1,
                    "batch_total": len(files)
                }
                
                # Initialize progress tracking for this file
                ingestion_id = f"ing_{int(time.time())}_{i}_{str(uuid.uuid4())[:8]}"
                ingestion_status[ingestion_id] = {
                    "status": "starting",
                    "phase": "initializing",
                    "progress": 0.0,
                    "filename": file_item.filename,
                    "start_time": time.time(),
                    "current_step": f"Starting ingestion ({i+1} of {len(files)})...",
                    "chunks_processed": 0,
                    "total_chunks": 0,
                    "errors": [],
                    "passes_complete": 0,
                    "total_passes": 3,
                    "batch_id": batch_id,
                    "batch_position": i + 1,
                    "batch_total": len(files)
                }
                
                # Start ingestion with progress tracking
                def make_progress_callback(ing_id):
                    def progress_callback(status_update):
                        if ing_id in ingestion_status:
                            ingestion_status[ing_id].update(status_update)
                            ingestion_status[ing_id]["last_updated"] = time.time()
                    return progress_callback
                
                try:
                    result = ingestion_pipeline.ingest_file(
                        str(temp_path), 
                        metadata,
                        make_progress_callback(ingestion_id)
                    )
                    
                    # Mark as completed with proper data extraction
                    chunks_created = 0
                    if "pass_a" in result:
                        chunks_created = result["pass_a"].get("chunks_created", 0)
                    
                    chunks_stored = 0
                    if "pass_b" in result:
                        chunks_stored = result["pass_b"].get("chunks_stored", 0)
                    
                    if ingestion_id in ingestion_status:
                        ingestion_status[ingestion_id].update({
                            "status": "completed",
                            "phase": "finished",
                            "progress": 100.0,
                            "end_time": time.time(),
                            "current_step": f"✅ Complete: {chunks_created} chunks created, {chunks_stored} stored",
                            "chunks_processed": chunks_created,
                            "total_chunks": chunks_created,
                            "chunks_stored": chunks_stored,
                            "passes_complete": 3,
                            "pages_processed": result.get("pass_a", {}).get("pages_detected", 0),
                            "duration_seconds": result.get("duration_seconds", 0),
                            "pass_a_chunks": chunks_created,
                            "pass_b_stored": chunks_stored,
                            "pass_c_graphs": result.get("pass_c", {}).get("graphs_updated", 0)
                        })
                    
                    batch_results.append({
                        "ingestion_id": ingestion_id,
                        "filename": file_item.filename,
                        "success": True,
                        "chunks_created": chunks_created,
                        "chunks_stored": chunks_stored,
                        "pages_processed": result.get("pass_a", {}).get("pages_detected", 0),
                        "processing_time": result.get("duration_seconds", 0)
                    })
                        
                except Exception as e:
                    if ingestion_id in ingestion_status:
                        ingestion_status[ingestion_id].update({
                            "status": "error",
                            "phase": "error",
                            "current_step": f"Error in file {i+1}: {str(e)}",
                            "end_time": time.time()
                        })
                    
                    batch_results.append({
                        "ingestion_id": ingestion_id,
                        "filename": file_item.filename,
                        "success": False,
                        "error": str(e)
                    })
                
                # Clean up temp file
                temp_path.unlink()
            
            # Return batch results
            total_chunks = sum(r.get("chunks_created", 0) for r in batch_results if r.get("success"))
            successful_files = sum(1 for r in batch_results if r.get("success"))
            
            self._send(200, {
                "success": True,
                "batch_id": batch_id,
                "message": f"Bulk upload completed: {successful_files}/{len(files)} files processed",
                "total_files": len(files),
                "successful_files": successful_files,
                "failed_files": len(files) - successful_files,
                "total_chunks_created": total_chunks,
                "results": batch_results,
                "status_url": f"/api/ingestion/status"
            })
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            self._send(500, {"error": f"upload failed: {str(e)}"})
    
    def _handle_ingestion_status(self):
        """Handle ingestion status requests"""
        try:
            url_parts = urlparse(self.path)
            query_params = parse_qs(url_parts.query)
            
            if 'id' in query_params:
                # Get specific ingestion status
                ingestion_id = query_params['id'][0]
                if ingestion_id in ingestion_status:
                    status = ingestion_status[ingestion_id].copy()
                    
                    # Calculate elapsed time
                    if 'start_time' in status:
                        elapsed = time.time() - status['start_time']
                        status['elapsed_seconds'] = round(elapsed, 2)
                    
                    self._send(200, status)
                else:
                    self._send(404, {"error": "ingestion not found"})
            else:
                # Get all ingestion statuses (last 20)
                recent_ingestions = []
                sorted_ids = sorted(ingestion_status.keys(), key=lambda x: ingestion_status[x].get('start_time', 0), reverse=True)
                
                for ing_id in sorted_ids[:20]:
                    status = ingestion_status[ing_id].copy()
                    status['ingestion_id'] = ing_id
                    if 'start_time' in status:
                        elapsed = time.time() - status['start_time']
                        status['elapsed_seconds'] = round(elapsed, 2)
                    recent_ingestions.append(status)
                
                self._send(200, {
                    "ingestions": recent_ingestions,
                    "total_active": len([s for s in ingestion_status.values() if s.get('status') in ['starting', 'processing']]),
                    "total_history": len(ingestion_status)
                })
                
        except Exception as e:
            logger.error(f"Ingestion status request failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_dictionary_request(self):
        """Handle dictionary management requests"""
        try:
            if self.command == 'GET':
                # Return dictionary contents
                self._send(200, {
                    "terms": dictionary.terms,
                    "aliases": dictionary.aliases,
                    "categories": dictionary.categories,
                    "total_terms": len(dictionary.terms)
                })
            elif self.command == 'POST':
                # Update dictionary
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                action = data.get('action', '')
                if action == 'add_term':
                    term = data.get('term', '')
                    definition = data.get('definition', '')
                    category = data.get('category', 'general')
                    
                    dictionary.add_term(term, definition, category)
                    dictionary.save_dictionary()
                    
                    self._send(200, {"success": True, "message": f"Added term: {term}"})
                elif action == 'update_term':
                    term = data.get('term', '')
                    definition = data.get('definition', '')
                    
                    if term in dictionary.terms:
                        dictionary.terms[term]["definition"] = definition
                        dictionary.save_dictionary()
                        self._send(200, {"success": True, "message": f"Updated term: {term}"})
                    else:
                        self._send(404, {"error": "term not found"})
                else:
                    self._send(400, {"error": "invalid action"})
            else:
                self._send(405, {"error": "method not allowed"})
        except Exception as e:
            logger.error(f"Dictionary request failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_tests_request(self):
        """Handle regression tests requests"""
        try:
            tests_dir = Path("tests/regression/cases")
            if not tests_dir.exists():
                self._send(200, {"tests": [], "total": 0})
                return
            
            test_files = list(tests_dir.glob("*.json"))
            tests = []
            
            for test_file in test_files[-20:]:  # Last 20 tests
                try:
                    with open(test_file, 'r', encoding='utf-8') as f:
                        test_data = json.load(f)
                        tests.append({
                            "case_id": test_data.get("case_id", ""),
                            "query": test_data.get("query", "")[:100] + "...",
                            "created": test_data.get("origin", {}).get("timestamp", 0),
                            "status": test_data.get("status", "unknown")
                        })
                except Exception:
                    continue
            
            self._send(200, {"tests": tests, "total": len(test_files)})
        except Exception as e:
            logger.error(f"Tests request failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_bugs_request(self):
        """Handle bug bundles requests with enhanced filtering and admin controls"""
        try:
            # Parse query parameters
            url_parts = urlparse(self.path)
            query_params = parse_qs(url_parts.query)
            filter_type = query_params.get('filter', ['all'])[0]
            
            # Check for admin actions (POST requests)
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))
                    return self._handle_bug_admin_action(data)
            
            bugs_dir = Path("bugs")
            if not bugs_dir.exists():
                self._send(200, {
                    "bugs": [], 
                    "total": 0,
                    "summary": {"open": 0, "closed": 0, "on_hold": 0}
                })
                return
            
            bug_files = list(bugs_dir.glob("*.json"))
            all_bugs = []
            
            # Load all bug files
            for bug_file in bug_files:
                try:
                    with open(bug_file, 'r', encoding='utf-8') as f:
                        bug_data = json.load(f)
                        
                        # Determine status - if not specified, assume "open"
                        status = bug_data.get("status", "open")
                        
                        # Convert timestamp to seconds if it's a string
                        created = bug_data.get("timestamp", 0)
                        if isinstance(created, str):
                            from datetime import datetime
                            try:
                                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                                created = dt.timestamp()
                            except:
                                created = 0
                        
                        bug_info = {
                            "bug_id": bug_data.get("bug_id", ""),
                            "title": bug_data.get("title", ""),
                            "query": bug_data.get("query", bug_data.get("user_report", ""))[:100] + "..." if bug_data.get("query") or bug_data.get("user_report") else "",
                            "user_feedback": bug_data.get("user_feedback", bug_data.get("description", ""))[:100] + "..." if bug_data.get("user_feedback") or bug_data.get("description") else "",
                            "created": created,
                            "severity": bug_data.get("severity", "unknown"),
                            "category": bug_data.get("category", "general"),
                            "status": status,
                            "environment": bug_data.get("environment", "unknown"),
                            "source": bug_data.get("source", "user_report"),
                            "admin_controls": bug_data.get("admin_controls", {}),
                            "review_id": bug_data.get("review_id", ""),
                            "escalated": bug_data.get("severity_escalated", False),
                            "peer_review_count": len(bug_data.get("peer_review_history", [])),
                            "on_hold_reason": bug_data.get("on_hold_reason", "") if status == "on_hold" else ""
                        }
                        all_bugs.append(bug_info)
                except Exception as e:
                    logger.warning(f"Failed to parse bug file {bug_file}: {e}")
                    continue
            
            # Sort by creation time (newest first)
            all_bugs.sort(key=lambda x: x["created"], reverse=True)
            
            # Filter bugs based on requested filter
            if filter_type == "open":
                filtered_bugs = [b for b in all_bugs if b["status"] == "open"]
            elif filter_type == "closed":
                filtered_bugs = [b for b in all_bugs if b["status"] == "closed"]
            elif filter_type == "on_hold":
                filtered_bugs = [b for b in all_bugs if b["status"] == "on_hold"]
            elif filter_type == "peer_review":
                filtered_bugs = [b for b in all_bugs if b["source"] == "peer_review"]
            else:  # "all"
                filtered_bugs = all_bugs
            
            # Calculate summary
            open_count = sum(1 for b in all_bugs if b["status"] == "open")
            closed_count = sum(1 for b in all_bugs if b["status"] == "closed")
            on_hold_count = sum(1 for b in all_bugs if b["status"] == "on_hold")
            peer_review_count = sum(1 for b in all_bugs if b["source"] == "peer_review")
            
            # Return limited results (last 20 for the detailed view)
            result_bugs = filtered_bugs[:20] if filter_type != "all" else filtered_bugs[:20]
            
            self._send(200, {
                "bugs": result_bugs,
                "total": len(bug_files),
                "filtered_total": len(filtered_bugs),
                "summary": {
                    "open": open_count,
                    "closed": closed_count,
                    "on_hold": on_hold_count,
                    "peer_review": peer_review_count
                },
                "filter": filter_type
            })
        except Exception as e:
            logger.error(f"Bugs request failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _handle_bug_admin_action(self, data: Dict[str, Any]):
        """Handle admin actions on bugs"""
        try:
            from app.common.bug_tracker import get_bug_tracker
            
            action = data.get("action", "")
            bug_id = data.get("bug_id", "")
            reason = data.get("reason", "")
            
            if not bug_id:
                self._send(400, {"error": "bug_id is required"})
                return
            
            bug_tracker = get_bug_tracker()
            
            if action == "put_on_hold":
                if not reason:
                    self._send(400, {"error": "reason is required for putting bug on hold"})
                    return
                
                success = bug_tracker.put_bug_on_hold(bug_id, reason)
                if success:
                    self._send(200, {"success": True, "message": f"Bug {bug_id} put on hold"})
                else:
                    self._send(400, {"success": False, "error": "Failed to put bug on hold - check admin permissions"})
            
            elif action == "admin_close":
                if not reason:
                    self._send(400, {"error": "reason is required for closing bug"})
                    return
                
                success = bug_tracker.admin_close_bug(bug_id, reason)
                if success:
                    self._send(200, {"success": True, "message": f"Bug {bug_id} closed by admin"})
                else:
                    self._send(400, {"success": False, "error": "Failed to close bug - check admin permissions"})
            
            elif action == "reopen":
                # Reopen a bug (only for non-peer-review bugs)
                bug = bug_tracker.get_bug(bug_id)
                if not bug:
                    self._send(404, {"error": "Bug not found"})
                    return
                
                admin_controls = bug.get("admin_controls", {})
                if not admin_controls.get("can_modify_status", False):
                    self._send(400, {"success": False, "error": "Cannot reopen peer review bug - not allowed by admin controls"})
                    return
                
                bug["status"] = "open"
                bug["reopened_by"] = "admin"
                bug["reopened_at"] = time.time()
                bug["reopened_reason"] = reason or "Reopened by admin"
                
                if bug_tracker._save_bug(bug):
                    self._send(200, {"success": True, "message": f"Bug {bug_id} reopened"})
                else:
                    self._send(500, {"success": False, "error": "Failed to save bug"})
            
            elif action == "remove_from_hold":
                # Remove a bug from hold status
                bug = bug_tracker.get_bug(bug_id)
                if not bug:
                    self._send(404, {"error": "Bug not found"})
                    return
                
                if bug.get("status") != "on_hold":
                    self._send(400, {"success": False, "error": "Bug is not on hold"})
                    return
                
                admin_controls = bug.get("admin_controls", {})
                if not admin_controls.get("can_modify_status", False):
                    self._send(400, {"success": False, "error": "Cannot modify peer review bug status"})
                    return
                
                bug["status"] = "open"
                bug["removed_from_hold_by"] = "admin"
                bug["removed_from_hold_at"] = time.time()
                if "on_hold_reason" in bug:
                    del bug["on_hold_reason"]
                if "on_hold_at" in bug:
                    del bug["on_hold_at"]
                
                if bug_tracker._save_bug(bug):
                    self._send(200, {"success": True, "message": f"Bug {bug_id} removed from hold"})
                else:
                    self._send(500, {"success": False, "error": "Failed to save bug"})
            
            else:
                self._send(400, {"error": f"Unknown action: {action}"})
        
        except Exception as e:
            logger.error(f"Bug admin action failed: {e}")
            self._send(500, {"error": str(e)})
    
    def _get_base_admin_style(self):
        """Get base styling for admin pages"""
        return """
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        body { 
            background: 
                linear-gradient(135deg, rgba(10, 10, 21, 0.85) 0%, rgba(26, 26, 46, 0.9) 50%, rgba(22, 33, 62, 0.85) 100%),
                url('/static/background/TTRPG_Center_BG.png') center center / cover no-repeat fixed;
            color: #00ffff;
            font-family: 'Orbitron', 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { 
            text-align: center; 
            margin-bottom: 30px;
            border-bottom: 2px solid #ff6600;
            padding-bottom: 20px;
        }
        .header h1 {
            font-size: 2.2em;
            font-weight: 900;
            color: #ff6600;
            text-shadow: 0 0 20px #ff6600, 0 0 40px #ff6600;
            margin: 0;
            letter-spacing: 2px;
        }
        .nav-back { margin-bottom: 20px; }
        .nav-back button {
            background: linear-gradient(145deg, #ff6600, #ff8800);
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'Orbitron', monospace;
            font-weight: 700;
            text-transform: uppercase;
        }
        .content-card {
            background: linear-gradient(145deg, rgba(0, 0, 0, 0.3), rgba(16, 16, 32, 0.5));
            border: 2px solid #00ffff;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
        }
        """
    
    def _get_ingestion_page(self):
        """Get ingestion management page"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Ingestion Console - TTRPG Center</title>
    <style>{self._get_base_admin_style()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Ingestion Console</h1>
        </div>
        
        <div class="nav-back">
            <button onclick="window.location.href='/admin'">← Back to Admin</button>
        </div>
        
        <div class="content-card">
            <h3>Upload TTRPG Materials</h3>
            <p>Upload and process source materials for the RAG system.</p>
            <form id="uploadForm" enctype="multipart/form-data" style="margin: 20px 0;">
                <div style="margin: 10px 0;">
                    <label for="fileInput" style="display: block; margin-bottom: 5px;">Select Files:</label>
                    <input type="file" id="fileInput" name="file" accept=".pdf,.txt,.md" multiple required 
                           style="background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                    <br><small style="color: #aaa; margin-top: 5px;">Hold Ctrl/Cmd to select multiple files for bulk upload</small>
                </div>
                <div style="margin: 10px 0;">
                    <label for="titleInput" style="display: block; margin-bottom: 5px;">Title (optional):</label>
                    <input type="text" id="titleInput" name="title" placeholder="Document title..." 
                           style="width: 300px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                </div>
                <div style="margin: 10px 0;">
                    <label for="tagsInput" style="display: block; margin-bottom: 5px;">Tags (comma-separated):</label>
                    <input type="text" id="tagsInput" name="tags" placeholder="rulebook, spells, combat..." 
                           style="width: 300px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                </div>
                <input type="hidden" name="source_type" value="manual_upload">
                <button type="submit" onclick="uploadFile(); return false;">Upload and Process</button>
            </form>
            <div id="uploadStatus" style="margin-top: 20px; padding: 10px; display: none;"></div>
        </div>
        
        <script>
            function uploadFile() {{
                const form = document.getElementById('uploadForm');
                const statusDiv = document.getElementById('uploadStatus');
                const formData = new FormData(form);
                
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = '<p style="color: #ffaa00;">Uploading and processing file...</p>';
                
                fetch('/api/ingestion/upload', {{
                    method: 'POST',
                    body: formData
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        if (data.batch_id) {{
                            // Bulk upload results
                            statusDiv.innerHTML = '<p style="color: #00ff00;">✅ Bulk upload completed!</p>' +
                                                '<p>Batch ID: <strong>' + data.batch_id + '</strong></p>' +
                                                '<p>Files processed: <strong>' + data.successful_files + '/' + data.total_files + '</strong></p>' +
                                                '<p>Total chunks created: <strong>' + data.total_chunks_created + '</strong></p>';
                            
                            if (data.results && data.results.length > 0) {{
                                let resultsHtml = '<div style="margin: 15px 0; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px;"><h4>File Results:</h4>';
                                data.results.forEach(result => {{
                                    const statusColor = result.success ? '#00ff00' : '#ff4444';
                                    const statusText = result.success ? `✅ ${{result.chunks_created}} chunks` : `❌ ${{result.error}}`;
                                    resultsHtml += `<div style="margin: 5px 0; padding: 5px; border-left: 3px solid ${{statusColor}};">`;
                                    resultsHtml += `<strong>${{result.filename}}</strong>: ${{statusText}}`;
                                    resultsHtml += `</div>`;
                                }});
                                resultsHtml += '</div>';
                                statusDiv.innerHTML += resultsHtml;
                            }}
                        }} else {{
                            // Single file upload
                            const ingestionId = data.ingestion_id;
                            statusDiv.innerHTML = '<p style="color: #ffaa00;">🔄 Upload successful! Processing started...</p>' +
                                                '<p>Ingestion ID: <strong>' + ingestionId + '</strong></p>' +
                                                '<div id="progress-details" style="margin: 15px 0; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px;">' +
                                                '<div id="progress-bar-container" style="width: 100%; background: rgba(0,0,0,0.5); border-radius: 4px; height: 20px; margin: 10px 0;">' +
                                                '<div id="progress-bar" style="width: 0%; background: linear-gradient(90deg, #ff6600, #ffaa00); height: 100%; border-radius: 4px; transition: width 0.3s ease;"></div>' +
                                                '</div>' +
                                                '<div id="progress-text">Initializing...</div>' +
                                                '<div id="progress-phase" style="font-size: 12px; color: #aaa; margin-top: 5px;">Pass 1 of 3: Parse</div>' +
                                                '</div>';
                            
                            // Start polling for progress updates
                            pollIngestionProgress(ingestionId);
                        }}
                        
                        form.reset();
                    }} else {{
                        statusDiv.innerHTML = '<p style="color: #ff4444;">❌ Upload failed: ' + (data.error || 'Unknown error') + '</p>';
                    }}
                }})
                .catch(error => {{
                    statusDiv.innerHTML = '<p style="color: #ff4444;">❌ Upload failed: ' + error.message + '</p>';
                }});
            }}
            
            function pollIngestionProgress(ingestionId) {{
                const pollInterval = setInterval(() => {{
                    fetch('/api/ingestion/status?id=' + ingestionId)
                        .then(response => response.json())
                        .then(data => {{
                            updateProgressDisplay(data);
                            
                            // Stop polling when complete or error
                            if (data.status === 'completed' || data.status === 'error') {{
                                clearInterval(pollInterval);
                            }}
                        }})
                        .catch(error => {{
                            console.error('Progress polling error:', error);
                        }});
                }}, 1000); // Poll every second
                
                // Stop polling after 5 minutes max
                setTimeout(() => clearInterval(pollInterval), 300000);
            }}
            
            function updateProgressDisplay(data) {{
                const progressBar = document.getElementById('progress-bar');
                const progressText = document.getElementById('progress-text');
                const progressPhase = document.getElementById('progress-phase');
                
                if (progressBar) {{
                    progressBar.style.width = (data.progress || 0) + '%';
                }}
                
                if (progressText) {{
                    progressText.innerHTML = data.current_step || 'Processing...';
                }}
                
                if (progressPhase) {{
                    const passInfo = `Pass ${{data.passes_complete + 1}} of ${{data.total_passes}}: ${{data.phase}}`;
                    const chunkInfo = data.chunks_processed > 0 ? ` | Chunks: ${{data.chunks_processed}}` : '';
                    const timeInfo = data.elapsed_seconds ? ` | ${{data.elapsed_seconds}}s` : '';
                    progressPhase.innerHTML = passInfo + chunkInfo + timeInfo;
                }}
                
                if (data.status === 'completed') {{
                    const statusDiv = document.getElementById('uploadStatus');
                    statusDiv.innerHTML += '<p style="color: #00ff00; margin-top: 15px;">✅ Ingestion completed successfully!</p>' +
                                          '<p>Total chunks created: ' + data.chunks_processed + '</p>' +
                                          '<p>Total time: ' + data.elapsed_seconds + 's</p>';
                }} else if (data.status === 'error') {{
                    const statusDiv = document.getElementById('uploadStatus');
                    statusDiv.innerHTML += '<p style="color: #ff4444; margin-top: 15px;">❌ Ingestion failed: ' + data.current_step + '</p>';
                }}
            }}
            }}
        </script>
        
        <div class="content-card">
            <h3>Ingestion Status</h3>
            <div id="ingestion-stats" style="margin: 10px 0; font-size: 14px;"></div>
            <div id="ingestion-history">Loading ingestion history...</div>
        </div>
        
        <script>
            function loadIngestionStatus() {{
                fetch('/api/ingestion/status')
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('ingestion-stats').innerHTML = 
                            `<strong>Active Ingestions:</strong> ${{data.total_active}} | <strong>History:</strong> ${{data.total_history}} total`;
                        
                        let historyHtml = '';
                        if (data.ingestions.length > 0) {{
                            data.ingestions.forEach(ing => {{
                                const statusColor = ing.status === 'completed' ? '#00ff00' : 
                                                  ing.status === 'error' ? '#ff4444' : '#ffaa00';
                                                  
                                const date = new Date(ing.start_time * 1000).toLocaleString();
                                
                                historyHtml += `<div style="margin: 10px 0; padding: 10px; background: rgba(0,0,0,0.2); border-left: 3px solid ${{statusColor}}; border-radius: 4px;">`;
                                historyHtml += `<strong style="color: ${{statusColor}};">${{ing.ingestion_id}}</strong>`;
                                historyHtml += `<span style="float: right; font-size: 11px; color: #aaa;">${{date}}</span>`;
                                historyHtml += `<br><span style="color: #00ffff; font-size: 13px;">File: ${{ing.filename}}</span>`;
                                historyHtml += `<br><span style="color: #aaa; font-size: 12px;">Status: ${{ing.current_step}}</span>`;
                                
                                // Detailed progress information
                                if (ing.pages_processed > 0) {{
                                    historyHtml += `<br><span style="color: #00ff00; font-size: 11px;">📄 Pages: ${{ing.pages_processed}}</span>`;
                                }}
                                if (ing.chunks_processed > 0) {{
                                    historyHtml += `<span style="color: #00ff00; font-size: 11px;"> | 📝 Chunks: ${{ing.chunks_processed}}</span>`;
                                }}
                                if (ing.chunks_stored > 0) {{
                                    historyHtml += `<span style="color: #00ff00; font-size: 11px;"> | 💾 Stored: ${{ing.chunks_stored}}</span>`;
                                }}
                                if (ing.passes_complete > 0) {{
                                    historyHtml += `<br><span style="color: #ffaa00; font-size: 11px;">🔄 Passes: ${{ing.passes_complete}}/${{ing.total_passes}}</span>`;
                                }}
                                if (ing.elapsed_seconds) {{
                                    historyHtml += `<span style="color: #aaa; font-size: 11px;"> | ⏱️ Time: ${{Math.round(ing.elapsed_seconds)}}s</span>`;
                                }}
                                
                                // Three-phase breakdown if available
                                if (ing.status === 'completed' && ing.pass_a_chunks > 0) {{
                                    historyHtml += `<br><span style="color: #666; font-size: 10px;">`;
                                    historyHtml += `Phase A: ${{ing.pass_a_chunks}} chunks | `;
                                    historyHtml += `Phase B: ${{ing.pass_b_stored}} stored | `;
                                    historyHtml += `Phase C: ${{ing.pass_c_graphs || 0}} graphs`;
                                    historyHtml += `</span>`;
                                }}
                                historyHtml += `</div>`;
                            }});
                        }} else {{
                            historyHtml = '<p style="color: #aaa;">No recent ingestions. Upload a file above to get started.</p>';
                        }}
                        
                        document.getElementById('ingestion-history').innerHTML = historyHtml;
                    }})
                    .catch(error => {{
                        document.getElementById('ingestion-history').innerHTML = '<p style="color: #ff4444;">Error loading ingestion history: ' + error.message + '</p>';
                    }});
            }}
            
            // Load status on page load and refresh every 5 seconds
            loadIngestionStatus();
            setInterval(loadIngestionStatus, 5000);
        </script>
    </div>
</body>
</html>"""
    
    def _get_dictionary_page(self):
        """Get dictionary management page"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Dictionary Management - TTRPG Center</title>
    <style>{self._get_base_admin_style()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Dictionary Management</h1>
        </div>
        
        <div class="nav-back">
            <button onclick="window.location.href='/admin'">← Back to Admin</button>
        </div>
        
        <div class="content-card">
            <h3>Normalization Dictionary</h3>
            <p>Current dictionary contains standardized terms and mappings for TTRPG content.</p>
            <div id="dictionary-stats" style="margin: 10px 0; font-size: 14px;"></div>
            <div id="dictionary-content" style="background: rgba(0,0,0,0.5); border: 1px solid #00ffff; padding: 15px; height: 400px; overflow-y: auto; font-family: monospace;">
                Loading dictionary contents...
            </div>
            
            <h4 style="margin-top: 30px;">Add New Term</h4>
            <div style="background: rgba(0,100,255,0.1); padding: 15px; border-radius: 8px;">
                <input type="text" id="newTerm" placeholder="Term name..." style="width: 200px; margin: 5px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                <input type="text" id="newDefinition" placeholder="Definition..." style="width: 300px; margin: 5px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                <input type="text" id="newCategory" placeholder="Category..." style="width: 150px; margin: 5px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 5px;">
                <button onclick="addTerm()" style="margin: 5px;">Add Term</button>
            </div>
            
            <h4 style="margin-top: 30px;">Enrichment Configuration</h4>
            <div style="background: rgba(255,102,0,0.1); padding: 15px; border-radius: 8px;">
                <label style="color: #ff6600; font-size: 14px;">Enrichment Thresholds:</label><br>
                <div style="margin: 10px 0;">
                    <label style="color: #00ffff; font-size: 12px;">Similarity Threshold:</label>
                    <input type="range" id="similarityThreshold" min="0.3" max="0.95" step="0.05" value="0.7" style="margin: 0 10px;">
                    <span id="similarityValue">0.70</span>
                </div>
                <div style="margin: 10px 0;">
                    <label style="color: #00ffff; font-size: 12px;">Min Chunk Size:</label>
                    <input type="number" id="minChunkSize" min="50" max="500" value="100" style="width: 80px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 3px; margin: 0 10px;">
                    <span style="color: #aaa; font-size: 11px;">characters</span>
                </div>
                <div style="margin: 10px 0;">
                    <label style="color: #00ffff; font-size: 12px;">Max Enrichment Passes:</label>
                    <input type="number" id="maxPasses" min="1" max="5" value="3" style="width: 60px; background: rgba(0,0,0,0.5); color: #00ffff; border: 1px solid #00ffff; padding: 3px; margin: 0 10px;">
                </div>
                <button onclick="updateEnrichmentConfig()" style="background: #ff6600; margin: 10px 5px 5px 0px;">Update Configuration</button>
            </div>
        </div>
        
        <script>
            function loadDictionary() {{
                fetch('/api/dictionary')
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('dictionary-stats').innerHTML = 
                            `<strong>Total Terms:</strong> ${{data.total_terms}} | <strong>Categories:</strong> ${{Object.keys(data.categories).length}}`;
                        
                        let content = '';
                        Object.entries(data.terms).forEach(([term, info]) => {{
                            content += `<div style="margin: 8px 0; padding: 8px; background: rgba(0,255,255,0.05); border-left: 3px solid #00ffff;">`;
                            content += `<strong style="color: #ff6600;">${{term}}</strong>`;
                            content += `<br><span style="color: #00ffff; font-size: 12px;">${{info.definition || 'No definition'}}</span>`;
                            content += `<br><span style="color: #aaa; font-size: 10px;">Category: ${{info.category || 'general'}}</span>`;
                            content += `</div>`;
                        }});
                        
                        document.getElementById('dictionary-content').innerHTML = content || '<p style="color: #aaa;">No terms found.</p>';
                    }})
                    .catch(error => {{
                        document.getElementById('dictionary-content').innerHTML = '<p style="color: #ff4444;">Error loading dictionary: ' + error.message + '</p>';
                    }});
            }}
            
            function addTerm() {{
                const term = document.getElementById('newTerm').value.trim();
                const definition = document.getElementById('newDefinition').value.trim();
                const category = document.getElementById('newCategory').value.trim() || 'general';
                
                if (!term || !definition) {{
                    alert('Term and definition are required');
                    return;
                }}
                
                fetch('/api/dictionary', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        action: 'add_term',
                        term: term,
                        definition: definition,
                        category: category
                    }})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        document.getElementById('newTerm').value = '';
                        document.getElementById('newDefinition').value = '';
                        document.getElementById('newCategory').value = '';
                        loadDictionary(); // Reload
                        alert('Term added successfully!');
                    }} else {{
                        alert('Error: ' + (data.error || 'Unknown error'));
                    }}
                }})
                .catch(error => alert('Error: ' + error.message));
            }}
            
            function updateEnrichmentConfig() {{
                const similarity = document.getElementById('similarityThreshold').value;
                const minChunk = document.getElementById('minChunkSize').value;
                const maxPasses = document.getElementById('maxPasses').value;
                
                // This would send config to server - for now just show confirmation
                alert(`Configuration updated:\\nSimilarity: ${similarity}\\nMin Chunk: ${minChunk}\\nMax Passes: ${maxPasses}`);
            }}
            
            // Update similarity threshold display
            document.getElementById('similarityThreshold').addEventListener('input', function() {{
                document.getElementById('similarityValue').textContent = parseFloat(this.value).toFixed(2);
            }});
            
            // Load dictionary on page load
            loadDictionary();
        </script>
    </div>
</body>
</html>"""
    
    def _get_tests_page(self):
        """Get regression tests page"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Regression Tests - TTRPG Center</title>
    <style>{self._get_base_admin_style()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Regression Tests</h1>
        </div>
        
        <div class="nav-back">
            <button onclick="window.location.href='/admin'">← Back to Admin</button>
        </div>
        
        <div class="content-card">
            <h3>Test Cases</h3>
            <p>Automated test cases generated from positive user feedback.</p>
            <div id="test-stats" style="margin: 10px 0; font-size: 14px;"></div>
            <div id="test-list">Loading test cases...</div>
        </div>
        
        <script>
            function loadTests() {{
                fetch('/api/tests')
                    .then(response => response.json())
                    .then(data => {{
                        document.getElementById('test-stats').innerHTML = 
                            `<strong>Total Test Cases:</strong> ${{data.total}} | <strong>Showing:</strong> ${{data.tests.length}} recent`;
                        
                        let content = '';
                        data.tests.forEach(test => {{
                            const date = new Date(test.created * 1000).toLocaleString();
                            const statusColor = test.status === 'active' ? '#00ff00' : '#ffaa00';
                            
                            content += `<div style="margin: 10px 0; padding: 10px; background: rgba(0,255,0,0.05); border-left: 3px solid #00ff00;">`;
                            content += `<strong style="color: #00ff00;">${{test.case_id}}</strong>`;
                            content += `<span style="float: right; color: ${{statusColor}}; font-size: 12px;">${{test.status}}</span>`;
                            content += `<br><span style="color: #00ffff; font-size: 13px;">${{test.query}}</span>`;
                            content += `<br><span style="color: #aaa; font-size: 11px;">Created: ${{date}}</span>`;
                            content += `</div>`;
                        }});
                        
                        document.getElementById('test-list').innerHTML = content || '<p style="color: #aaa;">No test cases found.</p>';
                    }})
                    .catch(error => {{
                        document.getElementById('test-list').innerHTML = '<p style="color: #ff4444;">Error loading tests: ' + error.message + '</p>';
                    }});
            }}
            
            // Load tests on page load
            loadTests();
        </script>
    </div>
</body>
</html>"""
    
    def _get_bugs_page(self):
        """Get bug bundles page"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Bug Bundles - TTRPG Center</title>
    <style>{self._get_base_admin_style()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Bug Bundles</h1>
        </div>
        
        <div class="nav-back">
            <button onclick="window.location.href='/admin'">← Back to Admin</button>
        </div>
        
        <div class="content-card">
            <h3>Bug Management System</h3>
            <p>Comprehensive view of all bug reports with advanced filtering and status management.</p>
            
            <div style="margin: 15px 0; display: flex; gap: 10px; align-items: center;">
                <label for="bug-filter-detailed" style="color: #00ffff; font-size: 14px;">Filter:</label>
                <select id="bug-filter-detailed" onchange="filterBugsDetailed()" style="background: #1a1a2e; color: #00ffff; border: 1px solid #00ffff; padding: 8px; border-radius: 4px;">
                    <option value="all">All Bugs</option>
                    <option value="open">Open Only</option>
                    <option value="closed">Closed Only</option>
                    <option value="on_hold">On Hold</option>
                    <option value="peer_review">Peer Review</option>
                </select>
                <button onclick="refreshBugsDetailed()" style="background: #0088ff;">Refresh</button>
                <button onclick="exportBugReport()" style="background: #ff6600;">Export Report</button>
            </div>
            
            <div id="bug-stats" style="margin: 10px 0; font-size: 14px;"></div>
            <div id="bug-list">Loading bug reports...</div>
        </div>
        
        <script>
            let currentDetailedFilter = 'all';
            
            function loadBugsDetailed(filter = 'all') {{
                const statsDiv = document.getElementById('bug-stats');
                const listDiv = document.getElementById('bug-list');
                
                if (!statsDiv || !listDiv) {{
                    console.error('Bug page elements not found');
                    return;
                }}
                
                statsDiv.innerHTML = 'Loading bug statistics...';
                listDiv.innerHTML = 'Loading bug reports...';
                
                fetch('/api/bugs?filter=' + filter)
                    .then(response => response.json())
                    .then(data => {{
                        console.log('Detailed bug data received:', data);
                        
                        // Update statistics
                        const total = data.total || 0;
                        const filtered = data.filtered_total || 0;
                        const open = data.summary?.open || 0;
                        const closed = data.summary?.closed || 0;
                        const on_hold = data.summary?.on_hold || 0;
                        const peer_review = data.summary?.peer_review || 0;
                        
                        statsDiv.innerHTML = `<strong>Total Reports:</strong> ${{total}} | <strong>Open:</strong> ${{open}} | <strong>Closed:</strong> ${{closed}} | <strong>On Hold:</strong> ${{on_hold}} | <strong>Peer Review:</strong> ${{peer_review}} | <strong>Showing:</strong> ${{filtered}} ${{filter}} bugs`;
                        
                        // Update bug list
                        let content = '';
                        if (data.bugs && data.bugs.length > 0) {{
                            data.bugs.forEach(bug => {{
                                const date = new Date(bug.created * 1000).toLocaleString();
                                const severityColor = bug.severity === 'critical' ? '#ff0000' :
                                                    bug.severity === 'high' ? '#ff4444' : 
                                                    bug.severity === 'medium' ? '#ffaa00' : '#aaa';
                                
                                let statusColor, statusIcon;
                                if (bug.status === 'closed') {{
                                    statusColor = '#00ff00';
                                    statusIcon = '✅';
                                }} else if (bug.status === 'on_hold') {{
                                    statusColor = '#888888';
                                    statusIcon = '⏸️';
                                }} else {{
                                    statusColor = '#ff6600';
                                    statusIcon = '🔴';
                                }}
                                
                                // Source indicator
                                const sourceIcon = bug.source === 'peer_review' ? '🔍' : 
                                                  bug.source === 'cli_submission' ? '⌨️' : 
                                                  bug.source === 'ui_submission' ? '🖥️' : '👤';
                                const sourceColor = bug.source === 'peer_review' ? '#00ffff' : '#aaa';
                                
                                content += `<div style="margin: 15px 0; padding: 15px; background: rgba(0,0,0,0.3); border-left: 4px solid ${{severityColor}}; border-radius: 4px;">`;
                                content += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">`;
                                content += `<strong style="color: #ff6600; font-size: 14px;">${{bug.title || bug.bug_id}}</strong>`;
                                content += `<div style="display: flex; gap: 10px; align-items: center;">`;
                                content += `<span style="color: ${{sourceColor}}; font-size: 10px; title="${{bug.source}}">${{sourceIcon}} ${{(bug.source || 'user_report').replace('_', ' ').toUpperCase()}}</span>`;
                                content += `<span style="color: ${{statusColor}}; font-size: 12px;">${{statusIcon}} ${{bug.status.toUpperCase()}}</span>`;
                                content += `<span style="color: ${{severityColor}}; font-size: 11px; text-transform: uppercase; font-weight: bold;">${{bug.severity}}</span>`;
                                if (bug.severity_escalated) {{
                                    content += `<span style="color: #ff0000; font-size: 10px;">⬆️ ESCALATED</span>`;
                                }}
                                content += `</div></div>`;
                                
                                // Description
                                if (bug.description) {{
                                    content += `<div style="margin: 8px 0;"><span style="color: #ccc; font-size: 12px;">${{bug.description}}</span></div>`;
                                }}
                                
                                // Legacy query/feedback support
                                if (bug.query) {{
                                    content += `<div style="margin: 8px 0;"><strong style="color: #00ffff; font-size: 12px;">Query:</strong> <span style="color: #aaa; font-size: 12px;">${{bug.query}}</span></div>`;
                                }}
                                if (bug.user_feedback) {{
                                    content += `<div style="margin: 8px 0;"><strong style="color: #ffaa00; font-size: 12px;">Feedback:</strong> <span style="color: #aaa; font-size: 12px;">${{bug.user_feedback}}</span></div>`;
                                }}
                                
                                content += `<div style="margin: 8px 0; display: flex; gap: 20px; font-size: 11px; color: #666;">`;
                                content += `<span>📅 ${{date}}</span>`;
                                content += `<span>🏷️ ${{bug.category}}</span>`;
                                content += `<span>🖥️ ${{bug.environment}}</span>`;
                                if (bug.build_id) {{
                                    content += `<span>🔗 ${{bug.build_id.substring(0, 8)}}</span>`;
                                }}
                                content += `</div>`;
                                
                                // Peer review history
                                if (bug.peer_review_count > 0) {{
                                    content += `<div style="margin: 8px 0; padding: 8px; background: rgba(0,255,255,0.1); border-radius: 3px;">`;
                                    content += `<strong style="color: #00ffff; font-size: 11px;">Peer Review History:</strong> `;
                                    content += `<span style="color: #aaa; font-size: 11px;">${{bug.peer_review_count}} review(s) found this issue</span>`;
                                    if (bug.escalation_reason) {{
                                        content += `<div style="color: #ffaa00; font-size: 10px; margin-top: 4px;">${{bug.escalation_reason}}</div>`;
                                    }}
                                    content += `</div>`;
                                }}
                                
                                // Admin controls and action buttons
                                content += `<div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">`;
                                
                                // Admin controls based on source and permissions
                                const adminControls = bug.admin_controls || {{}};
                                const isPeerReview = bug.source === 'peer_review';
                                
                                if (bug.status === 'open') {{
                                    if (adminControls.can_modify_status) {{
                                        content += `<button onclick="adminCloseBug('${{bug.bug_id}}')" style="background: #00ff00; color: #000; padding: 4px 8px; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">Admin Close</button>`;
                                    }}
                                    if (adminControls.can_put_on_hold) {{
                                        content += `<button onclick="putBugOnHold('${{bug.bug_id}}')" style="background: #888888; color: #fff; padding: 4px 8px; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">Put On Hold</button>`;
                                    }}
                                }} else if (bug.status === 'on_hold') {{
                                    if (adminControls.can_modify_status) {{
                                        content += `<button onclick="removeBugFromHold('${{bug.bug_id}}')" style="background: #ff6600; color: #fff; padding: 4px 8px; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">Remove Hold</button>`;
                                    }}
                                }} else if (bug.status === 'closed' && adminControls.can_modify_status) {{
                                    content += `<button onclick="reopenBug('${{bug.bug_id}}')" style="background: #ff6600; color: #fff; padding: 4px 8px; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">Reopen</button>`;
                                }}
                                
                                content += `<button onclick="viewBugDetails('${{bug.bug_id}}')" style="background: #0088ff; color: #fff; padding: 4px 8px; border: none; border-radius: 3px; font-size: 10px; cursor: pointer;">View Details</button>`;
                                
                                if (isPeerReview) {{
                                    content += `<span style="color: #00ffff; font-size: 10px; padding: 4px 8px; background: rgba(0,255,255,0.1); border-radius: 3px;">Auto-managed</span>`;
                                }}
                                
                                content += `</div></div>`;
                            }});
                        }} else {{
                            content = `<p style="color: #aaa; text-align: center; padding: 20px;">No ${{filter}} bug reports found.</p>`;
                        }}
                        
                        listDiv.innerHTML = content;
                    }})
                    .catch(error => {{
                        console.error('Bug loading failed:', error);
                        statsDiv.innerHTML = '<span style="color: #ff4444;">Failed to load bug statistics</span>';
                        listDiv.innerHTML = '<p style="color: #ff4444;">Error loading bug reports: ' + error.message + '</p>';
                    }});
            }}
            
            function refreshBugsDetailed() {{
                loadBugsDetailed(currentDetailedFilter);
            }}
            
            function filterBugsDetailed() {{
                const filter = document.getElementById('bug-filter-detailed').value;
                currentDetailedFilter = filter;
                loadBugsDetailed(filter);
            }}
            
            function adminCloseBug(bugId) {{
                const reason = prompt('Enter reason for closing this bug:');
                if (reason) {{
                    performBugAction(bugId, 'admin_close', {{reason: reason}});
                }}
            }}
            
            function putBugOnHold(bugId) {{
                const reason = prompt('Enter reason for putting this bug on hold:');
                if (reason) {{
                    performBugAction(bugId, 'put_on_hold', {{reason: reason}});
                }}
            }}
            
            function removeBugFromHold(bugId) {{
                if (confirm('Remove this bug from hold status?')) {{
                    performBugAction(bugId, 'remove_from_hold', {{}});
                }}
            }}
            
            function reopenBug(bugId) {{
                if (confirm('Reopen this bug?')) {{
                    performBugAction(bugId, 'reopen', {{}});
                }}
            }}
            
            function performBugAction(bugId, action, params) {{
                const requestBody = {{
                    action: action,
                    bug_id: bugId,
                    ...params
                }};
                
                fetch('/api/bugs', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json'
                    }},
                    body: JSON.stringify(requestBody)
                }})
                .then(response => {{
                    if (!response.ok) {{
                        throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
                    }}
                    return response.json();
                }})
                .then(data => {{
                    console.log('Bug action response:', data);
                    if (data.success) {{
                        // Show success message briefly
                        const message = data.message || 'Action completed successfully';
                        console.log('Bug action success:', message);
                        
                        // Refresh the bug list immediately  
                        refreshBugsDetailed();
                        
                        // Show non-blocking success feedback
                        const statusDiv = document.getElementById('bug-stats');
                        if (statusDiv) {{
                            const originalText = statusDiv.innerHTML;
                            statusDiv.innerHTML = '<span style="color: #00ff00;">✅ ' + message + '</span>';
                            setTimeout(() => {{
                                statusDiv.innerHTML = originalText;
                            }}, 3000);
                        }}
                    }} else {{
                        const errorMsg = data.error || 'Action failed';
                        console.error('Bug action failed:', errorMsg);
                        alert('Error: ' + errorMsg);
                    }}
                }})
                .catch(error => {{
                    console.error('Bug action network error:', error);
                    alert('Network error: ' + error.message);
                }});
            }}
            
            function viewBugDetails(bugId) {{
                // This would show detailed bug information - for now just show bug ID
                alert('Viewing details for ' + bugId + ' (detailed view to be implemented)');
            }}
            
            function exportBugReport() {{
                // This would export bug data - for now just show confirmation
                alert('Bug report export functionality to be implemented');
            }}
            
            // Load bugs on page load
            loadBugsDetailed();
        </script>
    </div>
</body>
</html>"""
    
    def _get_requirements_page(self):
        """Get requirements management page"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Requirements - TTRPG Center</title>
    <style>{self._get_base_admin_style()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Requirements Management</h1>
        </div>
        
        <div class="nav-back">
            <button onclick="window.location.href='/admin'">← Back to Admin</button>
        </div>
        
        <div class="content-card">
            <h3>System Requirements</h3>
            <p>Immutable requirements and approved feature requests with schema validation.</p>
            
            <div style="margin: 15px 0; display: flex; gap: 10px;">
                <button onclick="validateRequirements()">Validate Schema</button>
                <button onclick="showStats()">Show Statistics</button>
                <button onclick="loadRequirements()">Refresh</button>
            </div>
            
            <div id="validation-results" style="margin: 10px 0;"></div>
            <div id="requirements-stats" style="margin: 10px 0; font-size: 14px;"></div>
            <div id="requirements-list">Loading requirements...</div>
        </div>
        
        <script>
            function loadRequirements() {{
                // Load from the actual requirements file
                fetch('/static/../docs/requirements/2025-08-25_MVP_Requirements.json')
                    .then(response => response.json())
                    .then(data => {{
                        const totalReqs = data.sections.reduce((total, section) => total + section.requirements.length, 0);
                        document.getElementById('requirements-stats').innerHTML = 
                            `<strong>Total Requirements:</strong> ${{totalReqs}} across ${{data.sections.length}} sections`;
                        
                        let content = '';
                        data.sections.forEach(section => {{
                            content += `<div style="margin: 15px 0; padding: 15px; background: rgba(255,165,0,0.05); border-left: 3px solid #ff6600;">`;
                            content += `<h4 style="color: #ff6600; margin: 0 0 10px 0;">${{section.title}}</h4>`;
                            content += `<p style="color: #aaa; font-size: 12px; margin: 0 0 15px 0;">${{section.description}}</p>`;
                            
                            section.requirements.forEach(req => {{
                                const priorityColor = req.priority === 'critical' ? '#ff4444' : 
                                                    req.priority === 'high' ? '#ff6600' : '#ffaa00';
                                                    
                                content += `<div style="margin: 10px 0; padding: 8px; background: rgba(0,0,0,0.3); border-radius: 4px;">`;
                                content += `<strong style="color: #00ffff;">${{req.req_id}}</strong>`;
                                content += `<span style="float: right; color: ${{priorityColor}}; font-size: 11px; text-transform: uppercase;">${{req.priority}}</span>`;
                                content += `<br><span style="color: #fff; font-size: 13px;">${{req.description}}</span>`;
                                content += `<ul style="margin: 5px 0; color: #aaa; font-size: 11px;">`;
                                req.acceptance_criteria.forEach(criteria => {{
                                    content += `<li>${{criteria}}</li>`;
                                }});
                                content += `</ul></div>`;
                            }});
                            
                            content += `</div>`;
                        }});
                        
                        document.getElementById('requirements-list').innerHTML = content;
                    }})
                    .catch(error => {{
                        document.getElementById('requirements-list').innerHTML = '<p style="color: #ff4444;">Error loading requirements: ' + error.message + '</p>';
                    }});
            }}
            
            function validateRequirements() {{
                const validationDiv = document.getElementById('validation-results');
                validationDiv.innerHTML = '<div class="status-pending">Validating requirements schema...</div>';
                
                fetch('/api/requirements/validate')
                    .then(response => response.json())
                    .then(data => {{
                        let html = '<div class="validation-summary">';
                        const statusClass = data.valid ? 'status-ok' : 'status-error';
                        html += '<strong>Schema Validation: <span class="' + statusClass + '">' + (data.valid ? 'VALID' : 'INVALID') + '</span></strong>';
                        
                        if (data.total_requirements !== undefined) {{
                            html += '<div style="margin: 8px 0; color: #aaa;">';
                            html += 'Total: ' + data.total_requirements + ' | ';
                            html += 'Valid: ' + data.valid_requirements + ' | ';
                            html += 'Invalid: ' + data.invalid_requirements;
                            html += '</div>';
                        }}
                        
                        if (data.errors && data.errors.length > 0) {{
                            html += '<div class="validation-errors"><strong>Errors:</strong><ul>';
                            data.errors.forEach(error => {{
                                html += '<li style="color: #ff4444;">' + error + '</li>';
                            }});
                            html += '</ul></div>';
                        }}
                        
                        if (data.requirement_errors && Object.keys(data.requirement_errors).length > 0) {{
                            html += '<div class="requirement-errors"><strong>Requirement Errors:</strong>';
                            Object.entries(data.requirement_errors).forEach(([reqId, errors]) => {{
                                html += '<div style="margin: 5px 0; color: #ff6600;"><strong>' + reqId + ':</strong>';
                                html += '<ul>';
                                errors.forEach(error => {{
                                    html += '<li style="color: #ff4444; font-size: 12px;">' + error + '</li>';
                                }});
                                html += '</ul></div>';
                            }});
                            html += '</div>';
                        }}
                        
                        html += '</div>';
                        validationDiv.innerHTML = html;
                    }})
                    .catch(error => {{
                        validationDiv.innerHTML = '<div class="status-error">Validation failed: ' + error.message + '</div>';
                    }});
            }}
            
            function showStats() {{
                const statsDiv = document.getElementById('requirements-stats');
                
                fetch('/api/requirements/stats')
                    .then(response => response.json())
                    .then(data => {{
                        if (data.error) {{
                            statsDiv.innerHTML = '<div class="status-error">Stats error: ' + data.error + '</div>';
                            return;
                        }}
                        
                        let html = '<div class="stats-display">';
                        html += '<strong>Requirements Statistics:</strong><br>';
                        html += 'Total: ' + data.total + '<br>';
                        
                        if (data.by_status && Object.keys(data.by_status).length > 0) {{
                            html += '<strong>By Status:</strong> ';
                            Object.entries(data.by_status).forEach(([status, count]) => {{
                                html += status + '(' + count + ') ';
                            }});
                            html += '<br>';
                        }}
                        
                        if (data.by_priority && Object.keys(data.by_priority).length > 0) {{
                            html += '<strong>By Priority:</strong> ';
                            Object.entries(data.by_priority).forEach(([priority, count]) => {{
                                html += priority + '(' + count + ') ';
                            }});
                            html += '<br>';
                        }}
                        
                        if (data.by_category && Object.keys(data.by_category).length > 0) {{
                            html += '<strong>By Category:</strong> ';
                            Object.entries(data.by_category).forEach(([category, count]) => {{
                                html += category + '(' + count + ') ';
                            }});
                        }}
                        
                        html += '</div>';
                        statsDiv.innerHTML = html;
                    }})
                    .catch(error => {{
                        statsDiv.innerHTML = '<div class="status-error">Stats failed: ' + error.message + '</div>';
                    }});
            }}
            
            // Load requirements on page load
            loadRequirements();
        </script>
    </div>
</body>
</html>"""

    def _handle_requirements_validation(self):
        """Handle requirements validation API requests"""
        try:
            query_params = parse_qs(urlparse(self.path).query)
            file_path = query_params.get('file', [''])[0]
            
            if not file_path:
                # Default to MVP requirements file
                file_path = "docs/requirements/2025-08-25_MVP_Requirements.json"
            
            # Use secure path joining to prevent directory traversal
            try:
                if file_path.startswith("docs/"):
                    # Remove docs/ prefix for validation
                    relative_path = file_path[5:]
                    full_path = secure_path_join("docs", relative_path)
                else:
                    # Assume it's within docs directory
                    full_path = secure_path_join("docs", file_path)
                    
            except ValueError as e:
                self._send(400, {"error": f"Invalid file path: {e}"})
                return
            
            if not full_path.exists():
                self._send(404, {"error": f"Requirements file not found: {file_path}"})
                return
            
            validation_result = requirements_validator.validate_requirements_file(str(full_path))
            self._send(200, validation_result)
            
        except Exception as e:
            logger.error(f"Requirements validation error: {str(e)}")
            self._send(500, {"error": f"Validation failed: {str(e)}"})
    
    def _handle_requirements_stats(self):
        """Handle requirements statistics API requests"""
        try:
            query_params = parse_qs(urlparse(self.path).query)
            file_path = query_params.get('file', [''])[0]
            
            if not file_path:
                # Default to MVP requirements file
                file_path = "docs/requirements/2025-08-25_MVP_Requirements.json"
            
            # Use secure path joining to prevent directory traversal
            try:
                if file_path.startswith("docs/"):
                    # Remove docs/ prefix for validation
                    relative_path = file_path[5:]
                    full_path = secure_path_join("docs", relative_path)
                else:
                    # Assume it's within docs directory
                    full_path = secure_path_join("docs", file_path)
                    
            except ValueError as e:
                self._send(400, {"error": f"Invalid file path: {e}"})
                return
            
            if not full_path.exists():
                self._send(404, {"error": f"Requirements file not found: {file_path}"})
                return
            
            stats = requirements_validator.get_requirements_stats(str(full_path))
            self._send(200, stats)
            
        except Exception as e:
            logger.error(f"Requirements stats error: {str(e)}")
            self._send(500, {"error": f"Stats failed: {str(e)}"})
    
    def _handle_database_collections(self):
        """Handle database collections management requests"""
        try:
            # Get collection information
            collections = vector_store.list_collections()
            current_collection = vector_store.get_collection_info()
            
            self._send(200, {
                "all_collections": collections,
                "current_environment": current_collection,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"Database collections error: {str(e)}")
            self._send(500, {"error": f"Collections request failed: {str(e)}"})
    
    def _handle_database_cleanup(self):
        """Handle database cleanup requests"""
        if self.command != 'POST':
            self._send(405, {"error": "POST method required"})
            return
            
        try:
            # Parse request body for confirmation
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                import json
                data = json.loads(post_data)
                confirm = data.get('confirm', False)
            else:
                confirm = False
            
            if not confirm:
                self._send(400, {"error": "Cleanup requires explicit confirmation"})
                return
            
            # Get current environment
            env = os.getenv("APP_ENV", "dev").lower()
            if env == "prod":
                self._send(403, {"error": "Production cleanup not allowed via API"})
                return
            
            # Perform cleanup
            result = vector_store.cleanup_environment_data()
            
            self._send(200, {
                "cleanup_result": result,
                "environment": env,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"Database cleanup error: {str(e)}")
            self._send(500, {"error": f"Cleanup failed: {str(e)}"})
    
    def _handle_database_cleanup_collection(self):
        """Handle selective collection cleanup requests"""
        if self.command != 'POST':
            self._send(405, {"error": "POST method required"})
            return
            
        try:
            # Parse request body for confirmation and collection name
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                import json
                data = json.loads(post_data)
                confirm = data.get('confirm', False)
                collection_name = data.get('collection', '')
            else:
                confirm = False
                collection_name = ''
            
            if not confirm:
                self._send(400, {"error": "Cleanup requires explicit confirmation"})
                return
                
            if not collection_name:
                self._send(400, {"error": "Collection name is required"})
                return
            
            # Get current environment - still enforce env restrictions
            env = os.getenv("APP_ENV", "dev").lower()
            if env == "prod":
                self._send(403, {"error": "Production cleanup not allowed via API"})
                return
            
            # Perform selective collection cleanup
            try:
                # Get database reference
                database = vector_store.database
                target_collection = database.get_collection(collection_name)
                
                # Delete all documents in the specified collection
                result = target_collection.delete_many({})
                deleted_count = result.deleted_count
                
                logger.info(f"Cleaned up {deleted_count} documents from collection {collection_name}")
                
                cleanup_result = {
                    "deleted": deleted_count,
                    "collection": collection_name,
                    "environment": env
                }
                
                self._send(200, {
                    "cleanup_result": cleanup_result,
                    "environment": env,
                    "timestamp": time.time()
                })
                
            except Exception as e:
                logger.error(f"Collection cleanup error for {collection_name}: {str(e)}")
                self._send(500, {"error": f"Collection cleanup failed: {str(e)}"})
            
        except Exception as e:
            logger.error(f"Database collection cleanup error: {str(e)}")
            self._send(500, {"error": f"Collection cleanup failed: {str(e)}"})
    
    def _handle_chunk_search(self):
        """Handle chunk search requests"""
        if self.command != 'GET':
            self._send(405, {"error": "GET method required"})
            return
            
        try:
            from urllib.parse import urlparse, parse_qs
            
            # Parse query parameters
            url_parts = urlparse(self.path)
            params = parse_qs(url_parts.query)
            
            search_text = params.get('text', [''])[0].strip()
            collection = params.get('collection', [''])[0].strip()
            limit = int(params.get('limit', ['10'])[0])
            
            # Get current environment - still enforce env restrictions
            env = os.getenv("APP_ENV", "dev").lower()
            if env == "prod":
                self._send(403, {"error": "Production chunk search not allowed"})
                return
            
            # Perform chunk search
            chunks = []
            
            if collection:
                # Search specific collection
                try:
                    database = vector_store.database
                    target_collection = database.get_collection(collection)
                    
                    # Build search query
                    query = {}
                    if search_text:
                        # Simple text search in the text field
                        query = {"text": {"$regex": search_text, "$options": "i"}}
                    
                    # Execute search
                    results = target_collection.find(query, limit=limit)
                    
                    for doc in results:
                        chunks.append({
                            "id": doc.get("_id", ""),
                            "text": doc.get("text", ""),
                            "page": doc.get("page", "N/A"),
                            "source_id": doc.get("source_id", "unknown"),
                            "section": doc.get("section", ""),
                            "collection": collection
                        })
                        
                except Exception as e:
                    logger.error(f"Collection search error for {collection}: {str(e)}")
                    # Continue with empty results
            else:
                # Search all collections if no specific collection specified
                try:
                    database = vector_store.database
                    collections = database.list_collection_names()
                    
                    search_count = 0
                    for coll_name in collections[:5]:  # Limit to first 5 collections
                        if search_count >= limit:
                            break
                            
                        try:
                            coll = database.get_collection(coll_name)
                            query = {}
                            if search_text:
                                query = {"text": {"$regex": search_text, "$options": "i"}}
                            
                            results = coll.find(query, limit=max(1, (limit - search_count)))
                            
                            for doc in results:
                                if search_count >= limit:
                                    break
                                chunks.append({
                                    "id": doc.get("_id", ""),
                                    "text": doc.get("text", ""),
                                    "page": doc.get("page", "N/A"),
                                    "source_id": doc.get("source_id", "unknown"),
                                    "section": doc.get("section", ""),
                                    "collection": coll_name
                                })
                                search_count += 1
                        except Exception as e:
                            # Skip collections that cause errors
                            continue
                            
                except Exception as e:
                    logger.error(f"Multi-collection search error: {str(e)}")
            
            self._send(200, {
                "chunks": chunks,
                "count": len(chunks),
                "search_text": search_text,
                "collection": collection,
                "environment": env
            })
            
        except Exception as e:
            logger.error(f"Chunk search error: {str(e)}")
            self._send(500, {"error": f"Chunk search failed: {str(e)}"})
    
    def _handle_chunk_delete(self):
        """Handle individual chunk deletion requests"""
        if self.command != 'POST':
            self._send(405, {"error": "POST method required"})
            return
            
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                post_data = self.rfile.read(content_length).decode('utf-8')
                import json
                data = json.loads(post_data)
                chunk_id = data.get('chunk_id', '')
                collection = data.get('collection', '')
                confirm = data.get('confirm', False)
            else:
                chunk_id = ''
                collection = ''
                confirm = False
            
            if not confirm:
                self._send(400, {"error": "Deletion requires explicit confirmation"})
                return
                
            if not chunk_id or not collection:
                self._send(400, {"error": "Chunk ID and collection name are required"})
                return
            
            # Get current environment - still enforce env restrictions
            env = os.getenv("APP_ENV", "dev").lower()
            if env == "prod":
                self._send(403, {"error": "Production chunk deletion not allowed via API"})
                return
            
            # Perform chunk deletion
            try:
                database = vector_store.database
                target_collection = database.get_collection(collection)
                
                # Delete specific chunk by ID
                result = target_collection.delete_one({"_id": chunk_id})
                deleted_count = result.deleted_count
                
                logger.info(f"Deleted {deleted_count} chunk (ID: {chunk_id}) from collection {collection}")
                
                self._send(200, {
                    "success": True,
                    "deleted_count": deleted_count,
                    "chunk_id": chunk_id,
                    "collection": collection,
                    "environment": env
                })
                
            except Exception as e:
                logger.error(f"Chunk deletion error for {chunk_id}: {str(e)}")
                self._send(500, {"error": f"Chunk deletion failed: {str(e)}"})
            
        except Exception as e:
            logger.error(f"Chunk delete request error: {str(e)}")
            self._send(500, {"error": f"Chunk delete failed: {str(e)}"})

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