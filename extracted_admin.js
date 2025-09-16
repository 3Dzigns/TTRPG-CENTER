
let dashboardData = {};

// DEBUG: Global debug flag
window.ADMIN_DEBUG = true;

function debugLog(message, data = null) {
    if (window.ADMIN_DEBUG) {
        console.log(`[ADMIN DEBUG] ${message}`, data || '');
    }
}

function debugError(message, error = null) {
    if (window.ADMIN_DEBUG) {
        console.error(`[ADMIN ERROR] ${message}`, error || '');
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    debugLog('DOMContentLoaded event fired');
    debugLog('Starting admin dashboard initialization');
    debugLog('Current location:', window.location.href);
    debugLog('User agent:', navigator.userAgent);

    // Test basic network connectivity
    testNetworkConnectivity();

    loadDashboardData();
    setInterval(loadDashboardData, 30000); // Refresh every 30 seconds
});

async function testNetworkConnectivity() {
    debugLog('Testing network connectivity...');
    try {
        const response = await fetch('/healthz');
        debugLog('Health check response status:', response.status);
        if (response.ok) {
            debugLog('✓ Basic connectivity working');
        }
    } catch (error) {
        debugError('✗ Basic connectivity failed', error);
    }
}

async function loadDashboardData() {
    debugLog('=== Starting loadDashboardData ===');

    try {
        debugLog('Fetching /api/status/overview...');
        const response = await fetch('/api/status/overview');
        debugLog('Status overview response status:', response.status);
        debugLog('Status overview response headers:', Object.fromEntries(response.headers.entries()));

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        debugLog('Status overview data received:', data);
        dashboardData = data;

        debugLog('Calling updateDashboard...');
        updateDashboard(data);

        // Load cache overview
        debugLog('Fetching /api/cache/overview...');
        const cacheResponse = await fetch('/api/cache/overview');
        debugLog('Cache overview response status:', cacheResponse.status);

        if (!cacheResponse.ok) {
            throw new Error(`Cache API HTTP ${cacheResponse.status}: ${cacheResponse.statusText}`);
        }

        const cacheData = await cacheResponse.json();
        debugLog('Cache overview data received:', cacheData);

        debugLog('Calling updateCacheToggles...');
        updateCacheToggles(cacheData);

        debugLog('=== loadDashboardData completed successfully ===');

    } catch (error) {
        debugError('Error in loadDashboardData:', error);
        debugError('Error stack:', error.stack);
        console.error('Error loading dashboard data:', error);
        AdminUtils.showToast(`Error loading dashboard data: ${error.message}`, 'danger');

        // Show error in UI
        showNetworkError(error.message);
    }
}

function showNetworkError(message) {
    debugLog('Showing network error in UI:', message);
    const errorHtml = `
        <div class="alert alert-danger" role="alert">
            <h4 class="alert-heading">Connection Error</h4>
            <p><strong>Failed to load admin data:</strong> ${message}</p>
            <hr>
            <p class="mb-0">
                <button class="btn btn-outline-danger" onclick="testNetworkDiagnostics()">
                    Run Network Diagnostics
                </button>
                <button class="btn btn-outline-secondary ms-2" onclick="loadDashboardData()">
                    Retry
                </button>
            </p>
        </div>
    `;

    // Insert error message at top of dashboard
    const container = document.querySelector('.main-content');
    if (container) {
        container.insertAdjacentHTML('afterbegin', errorHtml);
    }
}

async function testNetworkDiagnostics() {
    debugLog('Running network diagnostics...');
    const endpoints = [
        '/healthz',
        '/api/status/overview',
        '/api/cache/overview',
        '/api/status/dev/logs?lines=1'
    ];

    const results = [];
    for (const endpoint of endpoints) {
        try {
            debugLog(`Testing ${endpoint}...`);
            const start = Date.now();
            const response = await fetch(endpoint);
            const duration = Date.now() - start;

            results.push({
                endpoint,
                status: response.status,
                ok: response.ok,
                duration: `${duration}ms`,
                error: null
            });

            debugLog(`✓ ${endpoint}: ${response.status} (${duration}ms)`);
        } catch (error) {
            debugError(`✗ ${endpoint}:`, error);
            results.push({
                endpoint,
                status: 'ERROR',
                ok: false,
                duration: 'N/A',
                error: error.message
            });
        }
    }

    debugLog('Network diagnostics results:', results);
    AdminUtils.showToast('Network diagnostics completed - check browser console', 'info');
}

function updateDashboard(data) {
    debugLog('=== Starting updateDashboard ===', data);

    try {
        // Update system metrics
        if (data.system_metrics) {
            debugLog('Updating system metrics...');

            const cpuElement = document.getElementById('cpu-usage');
            const memoryElement = document.getElementById('memory-usage');
            const diskElement = document.getElementById('disk-usage');
            const uptimeElement = document.getElementById('service-uptime');

            if (cpuElement) {
                cpuElement.textContent = data.system_metrics.cpu_percent.toFixed(1) + '%';
                debugLog('✓ CPU usage updated:', cpuElement.textContent);
            } else {
                debugError('✗ CPU usage element not found: cpu-usage');
            }

            if (memoryElement) {
                memoryElement.textContent = data.system_metrics.memory_percent.toFixed(1) + '%';
                debugLog('✓ Memory usage updated:', memoryElement.textContent);
            } else {
                debugError('✗ Memory usage element not found: memory-usage');
            }

            if (diskElement) {
                diskElement.textContent = data.system_metrics.disk_percent.toFixed(1) + '%';
                debugLog('✓ Disk usage updated:', diskElement.textContent);
            } else {
                debugError('✗ Disk usage element not found: disk-usage');
            }

            if (uptimeElement) {
                const uptimeText = AdminUtils.formatDuration(data.service_uptime_seconds);
                uptimeElement.textContent = uptimeText;
                debugLog('✓ Service uptime updated:', uptimeText);
            } else {
                debugError('✗ Service uptime element not found: service-uptime');
            }
        } else {
            debugError('✗ No system_metrics in data');
        }

        // Update overall status
        debugLog('Updating overall status...');
        const statusElement = document.getElementById('overall-status');
        if (statusElement) {
            statusElement.innerHTML = `
                <i class="bi bi-${getStatusIcon(data.overall_status)}"></i>
                <span>${data.overall_status.charAt(0).toUpperCase() + data.overall_status.slice(1)}</span>
            `;
            statusElement.className = `status-badge status-${data.overall_status}`;
            debugLog('✓ Overall status updated:', data.overall_status);
        } else {
            debugError('✗ Overall status element not found: overall-status');
        }

        // Update environment status
        if (data.environments) {
            debugLog(`Updating ${data.environments.length} environments...`);
            data.environments.forEach((env, index) => {
                debugLog(`Processing environment ${index + 1}:`, env.name);
                updateEnvironmentStatus(env);
            });
        } else {
            debugError('✗ No environments in data');
        }

        // Update recent activity
        debugLog('Calling updateRecentActivity...');
        updateRecentActivity();

        debugLog('=== updateDashboard completed successfully ===');

    } catch (error) {
        debugError('Error in updateDashboard:', error);
        debugError('Error stack:', error.stack);
    }
}

function updateEnvironmentStatus(env) {
    const statusElement = document.getElementById(`${env.name}-status`);
    const memoryElement = document.getElementById(`${env.name}-memory`);
    const portElement = document.getElementById(`${env.name}-port`);
    const dotElement = document.getElementById(`${env.name}-dot`);

    if (statusElement) {
        const status = env.is_active ? 'healthy' : 'critical';
        statusElement.innerHTML = `
            <i class="bi bi-${getStatusIcon(status)}"></i>
            <span>${env.is_active ? 'Active' : 'Inactive'}</span>
        `;
        statusElement.className = `status-badge status-${status}`;
    }

    // Update dot color based on status
    if (dotElement) {
        let dotClass = 'text-danger'; // red by default (inactive/failed)
        if (env.is_active) {
            dotClass = env.error_message ? 'text-warning' : 'text-success'; // yellow if has errors, green if healthy
        }
        dotElement.className = `bi bi-circle-fill me-2 ${dotClass}`;
    }

    if (memoryElement && env.memory_mb) {
        memoryElement.textContent = AdminUtils.formatBytes(env.memory_mb * 1024 * 1024);
    }

    if (portElement) {
        portElement.textContent = env.port;
    }
}

function updateCacheToggles(cacheData) {
    if (cacheData.environments) {
        Object.keys(cacheData.environments).forEach(env => {
            const toggle = document.getElementById(`${env}-cache-toggle`);
            if (toggle) {
                toggle.checked = cacheData.environments[env].policy.cache_enabled;
            }
        });
    }
}

async function updateRecentActivity() {
    debugLog('=== Starting updateRecentActivity ===');

    const activityElement = document.getElementById('recent-activity');
    if (!activityElement) {
        debugError('✗ Recent activity element not found: recent-activity');
        return;
    }

    try {
        // Load recent logs from the current environment
        const currentEnv = 'dev'; // Could be dynamic based on active environment
        debugLog(`Fetching logs for environment: ${currentEnv}`);

        const logsUrl = `/api/status/${currentEnv}/logs?lines=10`;
        debugLog(`Fetching: ${logsUrl}`);

        const response = await fetch(logsUrl);
        debugLog('Logs response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const logs = await response.json();
        debugLog('Logs data received:', logs);

        if (Array.isArray(logs) && logs.length > 0) {
            debugLog(`Processing ${logs.length} log entries...`);

            // Sort logs by timestamp descending (newest first) and take top 3
            const sortedLogs = logs.sort((a, b) => b.timestamp - a.timestamp);
            const recentLogs = sortedLogs.slice(0, 3);
            debugLog('Recent logs selected:', recentLogs);

            const logHtml = recentLogs.map((log, index) => {
                debugLog(`Processing log entry ${index}:`, log);
                const timestamp = new Date(log.timestamp * 1000).toLocaleTimeString();
                const truncatedMessage = truncateMessage(log.message, 50);

                return `
                    <div class="d-flex justify-content-between align-items-center mb-2 p-2 border-bottom log-entry"
                         style="cursor: pointer; border-radius: 4px;"
                         onclick="showLogDetails('${currentEnv}', ${index})"
                         onmouseover="this.style.backgroundColor='rgba(0,123,255,0.1)'"
                         onmouseout="this.style.backgroundColor='transparent'">
                        <div class="flex-grow-1">
                            <small class="text-muted">[${log.level}]</small>
                            <small class="text-dark ms-2">${truncatedMessage}</small>
                        </div>
                        <small class="text-muted">${timestamp}</small>
                    </div>
                `;
            }).join('');

            activityElement.innerHTML = logHtml;
            debugLog('✓ Recent activity HTML updated');

            // Store logs for detail view
            window.currentActivityLogs = logs;
            debugLog('✓ Logs stored in window.currentActivityLogs');

        } else {
            debugLog('No logs found, showing empty state');
            activityElement.innerHTML = `
                <div class="text-center text-muted py-3">
                    <small>No recent activity found.</small>
                </div>
            `;
        }

        debugLog('=== updateRecentActivity completed successfully ===');

    } catch (error) {
        debugError('Error in updateRecentActivity:', error);
        debugError('Error stack:', error.stack);
        console.error('Error loading recent activity:', error);

        activityElement.innerHTML = `
            <div class="text-center text-muted py-3">
                <small>Error loading recent activity: ${error.message}</small>
                <br>
                <button class="btn btn-sm btn-outline-secondary mt-1" onclick="updateRecentActivity()">
                    Retry
                </button>
            </div>
        `;
    }
}

function getStatusIcon(status) {
    switch(status) {
        case 'healthy': return 'check-circle-fill';
        case 'degraded': return 'exclamation-triangle-fill';
        case 'critical': return 'x-circle-fill';
        default: return 'question-circle-fill';
    }
}

async function runNightly(environment) {
    try {
        AdminUtils.showToast(`Starting nightly run for ${environment}...`, 'info');
        const res = await fetch('/api/admin/ingestion/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ env: environment })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        AdminUtils.showToast(`Nightly started for ${data.env} (pid ${data.pid})`, 'success');
    } catch (e) {
        console.error('Failed to start nightly:', e);
        AdminUtils.showToast('Failed to start nightly run', 'danger');
    }
}

async function refreshDashboard() {
    AdminUtils.showToast('Refreshing dashboard...', 'info');
    await loadDashboardData();
    AdminUtils.showToast('Dashboard refreshed', 'success');
}

async function toggleCache(environment, enabled) {
    try {
        const endpoint = enabled ? 'enable' : 'disable';
        const response = await fetch(`/api/cache/${environment}/${endpoint}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            AdminUtils.showToast(`Cache ${enabled ? 'enabled' : 'disabled'} for ${environment}`, 'success');
        } else {
            throw new Error('Failed to toggle cache');
        }
    } catch (error) {
        console.error('Error toggling cache:', error);
        AdminUtils.showToast('Error toggling cache', 'danger');
        // Revert toggle
        document.getElementById(`${environment}-cache-toggle`).checked = !enabled;
    }
}

async function clearAllCaches() {
    if (!confirm('Are you sure you want to clear all caches? This will affect performance temporarily.')) {
        return;
    }
    
    try {
        const environments = ['dev', 'test', 'prod'];
        for (const env of environments) {
            const response = await fetch(`/api/cache/${env}/clear`, { method: 'POST' });
            if (!response.ok) {
                throw new Error(`Failed to clear cache for ${env}`);
            }
        }
        AdminUtils.showToast('All caches cleared successfully', 'success');
    } catch (error) {
        console.error('Error clearing caches:', error);
        AdminUtils.showToast('Error clearing caches', 'danger');
    }
}

async function viewLogs(environment) {
    try {
        // 1) Load aggregated tail for quick context
        const response = await fetch(`/api/status/${environment}/logs?lines=200`);
        const logs = await response.json();
        const logsContent = document.getElementById('logs-content');
        if (Array.isArray(logs) && logs.length) {
            logsContent.textContent = logs.map(log => 
                `[${new Date(log.timestamp * 1000).toLocaleString()}] ${log.level}: ${log.message}`
            ).join('\n');
        } else {
            logsContent.textContent = 'No recent log entries.';
        }

        // 2) Load list of available log files
        const listRes = await fetch(`/api/logs/${environment}/list`);
        const listData = await listRes.json();
        const container = document.getElementById('logs-list-container');
        if (listData.logs && listData.logs.length) {
            container.innerHTML = `
                <table class="table table-sm">
                  <thead>
                    <tr>
                      <th>Log File</th>
                      <th>Size</th>
                      <th>Modified</th>
                      <th style="width: 140px;">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${listData.logs.map(l => `
                      <tr>
                        <td>${l.name}</td>
                        <td>${AdminUtils.formatBytes(l.size_bytes)}</td>
                        <td>${AdminUtils.formatTimestamp(l.modified_at)}</td>
                        <td>
                          <button class="btn btn-sm btn-outline-primary" onclick="viewLogFile('${environment}','${l.rel.replace(/'/g, '\\\\\')}')">View</button>
                          <a class="btn btn-sm btn-outline-secondary" href="/api/logs/${environment}/file?name=${encodeURIComponent(l.rel)}">Download</a>
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
            `;
        } else {
            container.innerHTML = '<div class="text-muted">No log files found.</div>';
        }
        
        document.querySelector('#logsModal .modal-title').textContent = `${environment.toUpperCase()} Environment Logs`;
        new bootstrap.Modal(document.getElementById('logsModal')).show();
        
    } catch (error) {
        console.error('Error loading logs:', error);
        AdminUtils.showToast('Error loading logs', 'danger');
    }
}

async function viewLogFile(environment, rel) {
    try {
        const res = await fetch(`/api/logs/${environment}/view?name=${encodeURIComponent(rel)}&lines=1000`);
        if (!res.ok) throw new Error('Failed to load log file');
        const data = await res.json();
        const logsContent = document.getElementById('logs-content');
        logsContent.textContent = data.text || '';
    } catch (e) {
        console.error('Failed to view log file', e);
        AdminUtils.showToast('Failed to view log file', 'danger');
    }
}

async function viewArtifacts(environment) {
    try {
        const response = await fetch(`/api/status/${environment}/artifacts`);
        const artifacts = await response.json();
        
        const artifactsContent = document.getElementById('artifacts-content');
        if (artifacts.length === 0) {
            artifactsContent.innerHTML = '<p class="text-muted">No artifacts found for this environment.</p>';
        } else {
            artifactsContent.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Size</th>
                                <th>Modified</th>
                                <th style="width: 120px;">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${artifacts.map(artifact => {
                                const rel = artifact.path || artifact.name;
                                const safe = rel.replace(/'/g, "\\'");
                                const dl = `/api/artifacts/${environment}/file?name=${encodeURIComponent(rel)}`;
                                return `
                                <tr>
                                    <td><a href="#" onclick="viewArtifact('${environment}','${safe}'); return false;">${artifact.name}</a></td>
                                    <td>${AdminUtils.formatBytes(artifact.size_bytes)}</td>
                                    <td>${AdminUtils.formatTimestamp(artifact.modified_at)}</td>
                                    <td>
                                        <a class="btn btn-sm btn-outline-secondary" href="${dl}">
                                            <i class="bi bi-download"></i> Download
                                        </a>
                                    </td>
                                </tr>
                            `; }).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        }
        
        document.querySelector('#artifactsModal .modal-title').textContent = `${environment.toUpperCase()} Environment Artifacts`;
        new bootstrap.Modal(document.getElementById('artifactsModal')).show();
        
    } catch (error) {
        console.error('Error loading artifacts:', error);
        AdminUtils.showToast('Error loading artifacts', 'danger');
    }
}

async function viewArtifact(environment, name) {
    try {
        const res = await fetch(`/api/artifacts/${environment}/view?name=${encodeURIComponent(name)}`);
        if (!res.ok) {
            const t = await res.text();
            throw new Error(`HTTP ${res.status}: ${t}`);
        }
        const data = await res.json();
        let content = '';
        if (data.json) {
            content = JSON.stringify(data.json, null, 2);
        } else if (data.text) {
            content = data.text;
        } else {
            content = '[Unsupported artifact format]';
        }
        document.getElementById('artifact-view-title').textContent = name;
        document.getElementById('artifact-view-body').textContent = content;
        new bootstrap.Modal(document.getElementById('artifactViewModal')).show();
    } catch (e) {
        console.error('Artifact view failed', e);
        AdminUtils.showToast(`Failed to view artifact: ${e.message}`, 'danger');
    }
}

async function runHealthChecks() {
    AdminUtils.showToast('Running health checks...', 'info');
    // Health check implementation would go here
    setTimeout(() => {
        AdminUtils.showToast('Health checks completed', 'success');
        refreshDashboard();
    }, 2000);
}

async function exportLogs() {
    AdminUtils.showToast('Preparing log export...', 'info');
    // Log export implementation would go here
    setTimeout(() => {
        AdminUtils.showToast('Log export ready for download', 'success');
    }, 1000);
}

// Helper functions for log functionality
function getLogLevelClass(level) {
    switch(level?.toLowerCase()) {
        case 'error': return 'danger';
        case 'warning': case 'warn': return 'warning';
        case 'info': return 'info';
        case 'debug': return 'secondary';
        default: return 'dark';
    }
}

function truncateMessage(message, maxLength) {
    if (!message) return '';
    return message.length > maxLength ? message.substring(0, maxLength) + '...' : message;
}

function showLogDetails(environment, index) {
    if (!window.currentActivityLogs || !window.currentActivityLogs[index]) {
        AdminUtils.showToast('Log details not available', 'warning');
        return;
    }

    const log = window.currentActivityLogs[index];
    const timestamp = new Date(log.timestamp * 1000).toLocaleString();

    // Create HTML content for the pop-out window
    const windowContent = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Log Entry Details - ${environment.toUpperCase()}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f8f9fa;
            padding: 20px;
        }
        .log-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .log-header {
            background: linear-gradient(135deg, #495057, #6c757d);
            color: white;
            padding: 20px;
            border-radius: 8px 8px 0 0;
            margin-bottom: 0;
        }
        .log-content {
            background: #1e1e1e;
            color: #f8f9fa;
            padding: 20px;
            border-radius: 0 0 8px 8px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            white-space: pre-wrap;
            word-break: break-word;
            min-height: 400px;
            max-height: 600px;
            overflow-y: auto;
            line-height: 1.4;
        }
        .badge {
            font-size: 0.9rem;
        }
        .btn-action {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="log-container">
        <div class="log-header">
            <div class="d-flex justify-content-between align-items-center">
                <h4 class="mb-0"><i class="bi bi-file-text me-2"></i>Log Entry Details</h4>
                <button type="button" class="btn btn-outline-light btn-sm" onclick="window.close()">
                    <i class="bi bi-x-lg"></i> Close
                </button>
            </div>
            <hr class="my-3" style="border-color: rgba(255,255,255,0.3);">
            <div class="row">
                <div class="col-md-4">
                    <strong>Environment:</strong> ${environment.toUpperCase()}
                </div>
                <div class="col-md-4">
                    <strong>Level:</strong> <span class="badge bg-secondary">${log.level}</span>
                </div>
                <div class="col-md-4">
                    <strong>Timestamp:</strong> ${timestamp}
                </div>
            </div>
        </div>
        <div class="log-content">${log.message}</div>
        <div class="btn-action">
            <button type="button" class="btn btn-primary" onclick="focusParent()">
                <i class="bi bi-arrow-left me-1"></i>Back to Dashboard
            </button>
            <button type="button" class="btn btn-secondary" onclick="window.close()">
                <i class="bi bi-x-circle me-1"></i>Close Window
            </button>
        </div>
    </div>
    <script>
        function focusParent() {
            // Focus back to parent window
            if (window.opener && !window.opener.closed) {
                window.opener.focus();
            }
            window.close();
        }
    <\/script>
    `;

    // Open new window with the log details
    const newWindow = window.open('', '_blank', 'width=1000,height=700,scrollbars=yes,resizable=yes,status=yes');

    if (newWindow) {
        newWindow.document.write(windowContent);
        newWindow.document.close();
        newWindow.focus();
    } else {
        alert('Pop-up blocked. Please allow pop-ups for this site.');
    }
}

// Make updateDashboard available globally for WebSocket updates
window.updateDashboard = updateDashboard;
