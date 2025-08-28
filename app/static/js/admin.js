// Admin UI JavaScript - extracted from server template to fix f-string conflicts

console.log('Admin UI JavaScript loaded');

function refreshStatus() {
    console.log('refreshStatus() called');
    const healthDiv = document.getElementById('health-status');
    if (!healthDiv) {
        console.error('Could not find health-status element');
        alert('Error: health-status element not found in DOM');
        return;
    }
    
    console.log('Found health-status element, starting status refresh for port:', window.location.port);
    healthDiv.innerHTML = '<div class="status-pending">Checking system status...</div>';
    
    // Add timeout to fetch request
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
        console.error('Status refresh timed out after 10 seconds');
        controller.abort();
    }, 10000); // 10 second timeout
    
    fetch('/status', { 
        signal: controller.signal,
        headers: {
            'Accept': 'application/json',
            'Cache-Control': 'no-cache'
        }
    })
        .then(r => {
            clearTimeout(timeoutId);
            if (!r.ok) {
                throw new Error('Status request failed: HTTP ' + r.status + ' ' + r.statusText);
            }
            return r.json();
        })
        .then(data => {
            console.log('Status data received:', data);
            let html = '';
            
            if (data && data.health_checks) {
                Object.entries(data.health_checks).forEach(([service, status]) => {
                    const statusClass = status && status.includes('connected') ? 'status-ok' : 'status-error';
                    html += '<div class="health-check"><span>' + service + ':</span><span class="' + statusClass + '">' + (status || 'unknown') + '</span></div>';
                });
                
                // Add build info if available
                if (data.build_id) {
                    html += '<div class="health-check"><span>Build:</span><span style="color: #aaa; font-size: 11px;">' + data.build_id + '</span></div>';
                }
            } else {
                console.warn('Invalid status data structure:', data);
                html += '<div class="status-error">Invalid status data received</div>';
            }
            
            if (data && data.ngrok_public_url) {
                html += '<div class="health-check"><span>Public URL:</span><span><a href="' + data.ngrok_public_url + '" target="_blank">' + data.ngrok_public_url + '</a></span></div>';
            }
            
            if (html) {
                healthDiv.innerHTML = html;
                console.log('Status display updated successfully');
            } else {
                healthDiv.innerHTML = '<div class="status-error">No valid status data to display</div>';
                console.warn('No valid status HTML generated');
            }
        })
        .catch(error => {
            clearTimeout(timeoutId);
            console.error('Status refresh error:', error);
            console.error('Error details:', { 
                name: error.name, 
                message: error.message, 
                stack: error.stack,
                port: window.location.port,
                hostname: window.location.hostname
            });
            
            let errorMessage = 'Status update failed: ';
            if (error.name === 'AbortError') {
                errorMessage += 'Request timed out (10s)';
            } else if (error.message.includes('Failed to fetch')) {
                errorMessage += 'Network connection failed (check if server is running on port ' + window.location.port + ')';
            } else if (error.message.includes('HTTP')) {
                errorMessage += error.message;
            } else {
                errorMessage += error.message || 'Unknown error';
            }
            
            healthDiv.innerHTML = '<div class="status-error">' + errorMessage + '<br><button onclick="refreshStatus()" style="margin-top: 5px; font-size: 12px; padding: 5px 10px;">Retry</button></div>';
        });
}

function showCollectionInfo() {
    console.log('showCollectionInfo() called');
    const infoDiv = document.getElementById('database-info');
    if (!infoDiv) {
        console.error('Could not find database-info element');
        alert('Error: database-info element not found in DOM');
        return;
    }
    
    console.log('Found database-info element, starting collections request');
    infoDiv.innerHTML = '<div class="status-pending">Loading database information...</div>';
    
    // Add timeout to prevent hanging requests
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
        console.error('Collections request timed out');
        controller.abort();
    }, 15000); // 15 second timeout
    
    fetch('/api/database/collections', { signal: controller.signal })
        .then(r => {
            clearTimeout(timeoutId);
            console.log('Collections response received, status:', r.status);
            if (!r.ok) {
                throw new Error('Collections request failed: ' + r.status);
            }
            return r.json();
        })
        .then(data => {
            console.log('Collections data received:', data);
            let html = '<div class="database-info">';
            
            // Current environment info
            if (data.current_environment) {
                const env = data.current_environment;
                html += '<div style="margin: 10px 0; padding: 10px; background: rgba(0,255,255,0.1); border-radius: 4px;">';
                html += '<strong>Current Environment:</strong><br>';
                html += 'Collection: <span style="color: #00ffff;">' + env.collection_name + '</span><br>';
                html += 'Environment: <span style="color: #ff6600;">' + env.environment.toUpperCase() + '</span><br>';
                html += 'Document Count: <span style="color: #00ff00;">' + env.document_count + '</span>';
                html += '</div>';
            }
            
            // All collections
            if (data.all_collections && data.all_collections.length > 0) {
                html += '<div style="margin: 10px 0;">';
                html += '<strong>All Collections in Database:</strong><br>';
                data.all_collections.forEach(collection => {
                    const isCurrentEnv = data.current_environment && collection === data.current_environment.collection_name;
                    const style = isCurrentEnv ? 'color: #00ff00; font-weight: bold;' : 'color: #aaa;';
                    html += '<span style="' + style + '">• ' + collection + (isCurrentEnv ? ' (current)' : '') + '</span><br>';
                });
                html += '</div>';
            }
            
            html += '</div>';
            infoDiv.innerHTML = html;
        })
        .catch(err => {
            console.error('showCollectionInfo error:', err);
            let errorMessage = 'Failed to load database info: ' + err.message;
            if (err.name === 'AbortError') {
                errorMessage = 'Database request timed out after 15 seconds';
            }
            infoDiv.innerHTML = '<div class="status-error">' + errorMessage + '<br><button onclick="showCollectionInfo()" style="margin-top: 5px; font-size: 12px; padding: 5px 10px;">Retry</button></div>';
        });
}

function refreshBugs() {
    console.log('refreshBugs() called');
    
    const summaryDiv = document.getElementById('bug-summary');
    const previewDiv = document.getElementById('bug-preview');
    
    if (!summaryDiv || !previewDiv) {
        console.error('Bug summary or preview div not found');
        return;
    }
    
    summaryDiv.innerHTML = 'Loading...';
    
    fetch('/api/bugs?summary=true')
        .then(r => r.json())
        .then(data => {
            console.log('Bug data structure received:', data);
            
            // Calculate stats from bugs array
            let totalBugs = 0;
            let openCount = 0;
            let closedCount = 0;
            let onHoldCount = 0;
            
            if (data.bugs && Array.isArray(data.bugs)) {
                totalBugs = data.bugs.length;
                data.bugs.forEach(bug => {
                    if (bug.status === 'open') openCount++;
                    else if (bug.status === 'closed') closedCount++;
                    else if (bug.status === 'on_hold') onHoldCount++;
                });
            }
            
            // Update summary with calculated stats
            summaryDiv.innerHTML = `Total: ${totalBugs} | Open: ${openCount} | Closed: ${closedCount} | On Hold: ${onHoldCount}`;
            
            // Update preview with recent bugs
            let previewHtml = '';
            if (data.bugs && data.bugs.length > 0) {
                // Show first 5 bugs
                const recentBugs = data.bugs.slice(0, 5);
                recentBugs.forEach(bug => {
                    const statusClass = bug.status === 'open' ? 'status-error' : 
                                       bug.status === 'closed' ? 'status-ok' : 
                                       bug.status === 'on_hold' ? 'status-warn' : 'status-pending';
                    previewHtml += `<div style="margin: 5px 0; padding: 5px; border-left: 2px solid #00ffff;">`;
                    previewHtml += `<span class="${statusClass}">[${(bug.status || 'UNKNOWN').toUpperCase()}]</span> `;
                    previewHtml += `<strong>${bug.bug_id || 'No ID'}</strong>: ${bug.title || 'No title'}`;
                    previewHtml += `</div>`;
                });
            } else {
                previewHtml = '<div style="color: #aaa;">No bugs found</div>';
            }
            previewDiv.innerHTML = previewHtml;
        })
        .catch(err => {
            console.error('refreshBugs error:', err);
            summaryDiv.innerHTML = 'Error loading bugs';
            previewDiv.innerHTML = '<div class="status-error">Failed to load bugs: ' + err.message + '</div>';
        });
}

function filterBugs() {
    const filter = document.getElementById('bug-filter').value;
    console.log('Filtering bugs by:', filter);
    
    const previewDiv = document.getElementById('bug-preview');
    previewDiv.innerHTML = '<div class="status-pending">Filtering...</div>';
    
    fetch(`/api/bugs?filter=${filter}&preview=true`)
        .then(r => r.json())
        .then(data => {
            let previewHtml = '';
            if (data.bugs && data.bugs.length > 0) {
                data.bugs.forEach(bug => {
                    const statusClass = bug.status === 'open' ? 'status-error' : 
                                       bug.status === 'closed' ? 'status-ok' : 'status-pending';
                    previewHtml += `<div style="margin: 5px 0; padding: 5px; border-left: 2px solid #00ffff;">`;
                    previewHtml += `<span class="${statusClass}">[${bug.status.toUpperCase()}]</span> `;
                    previewHtml += `<strong>${bug.bug_id}</strong>: ${bug.title}`;
                    previewHtml += `</div>`;
                });
            } else {
                previewHtml = '<div style="color: #aaa;">No bugs match filter</div>';
            }
            previewDiv.innerHTML = previewHtml;
        })
        .catch(err => {
            console.error('filterBugs error:', err);
            previewDiv.innerHTML = '<div class="status-error">Filter failed: ' + err.message + '</div>';
        });
}

// Admin authority management
let adminSession = {
    authenticated: false,
    expires: 0
};

function requestAdminAction(action) {
    console.log('Admin action requested:', action);
    
    if (!isAdminAuthenticated()) {
        promptAdminAuthentication(action);
        return;
    }
    
    // Execute the admin action
    executeAdminAction(action);
}

function isAdminAuthenticated() {
    return adminSession.authenticated && Date.now() < adminSession.expires;
}

function promptAdminAuthentication(pendingAction) {
    const authCode = prompt(
        'Admin Authentication Required\n\n' +
        'Enter admin authentication code for: ' + pendingAction + '\n' +
        '(This session will be valid for 10 minutes)'
    );
    
    if (!authCode) {
        console.log('Admin authentication cancelled');
        return;
    }
    
    // For development, accept simple codes. In production, this would validate against secure backend
    const validCodes = ['admin', 'ADMIN', 'dev123', 'DEV123'];
    
    if (validCodes.includes(authCode)) {
        adminSession.authenticated = true;
        adminSession.expires = Date.now() + (10 * 60 * 1000); // 10 minutes
        // Set admin token based on auth code for server-side validation
        adminSession.token = 'dev-admin-' + authCode.toLowerCase();
        
        console.log('Admin authentication successful');
        alert('Admin authentication successful! Session valid for 10 minutes.');
        
        // Execute the pending action
        executeAdminAction(pendingAction);
    } else {
        alert('Invalid admin authentication code. Access denied.');
        console.log('Admin authentication failed');
    }
}

function executeAdminAction(action) {
    console.log('Executing admin action:', action);
    
    switch(action) {
        case 'cleanup-selected':
            cleanupSelectedCollection();
            break;
        case 'cleanup-all':
            cleanupEnvironmentData();
            break;
        default:
            console.error('Unknown admin action:', action);
    }
}

function cleanupSelectedCollection() {
    const select = document.getElementById('cleanup-collection-select');
    if (!select || !select.value) {
        alert('Please select a collection to cleanup');
        return;
    }
    
    if (!confirm(`Are you sure you want to cleanup the collection "${select.value}"? This cannot be undone.`)) {
        return;
    }
    
    console.log('Cleaning up selected collection:', select.value);
    
    fetch('/api/database/cleanup-collection', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-Admin-Token': adminSession.token || ''
        },
        body: JSON.stringify({ 
            collection_name: select.value,
            confirm: true
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(`Successfully cleaned up collection: ${data.deleted} documents deleted`);
            showCollectionInfo(); // Refresh collection info
        } else {
            alert(`Cleanup failed: ${data.error}`);
        }
    })
    .catch(err => {
        console.error('Cleanup error:', err);
        alert('Cleanup request failed: ' + err.message);
    });
}

function cleanupEnvironmentData() {
    const env = window.location.port === '8000' ? 'DEV' : 
                window.location.port === '8181' ? 'TEST' : 
                window.location.port === '8282' ? 'PROD' : 'UNKNOWN';
    
    if (!confirm(`Are you sure you want to cleanup ALL data in the ${env} environment? This cannot be undone.`)) {
        return;
    }
    
    console.log('Cleaning up all environment data');
    
    fetch('/api/database/cleanup', {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'X-Admin-Token': adminSession.token || ''
        },
        body: JSON.stringify({ 
            confirm: true
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(`Successfully cleaned up environment: ${data.deleted} documents deleted`);
            showCollectionInfo(); // Refresh collection info
        } else {
            alert(`Cleanup failed: ${data.error}`);
        }
    })
    .catch(err => {
        console.error('Environment cleanup error:', err);
        alert('Environment cleanup failed: ' + err.message);
    });
}

// Visible admin authentication functions
function authenticateAdmin() {
    const input = document.getElementById('admin-code-input');
    const statusDiv = document.getElementById('admin-status');
    const authCode = input.value.trim();
    
    if (!authCode) {
        statusDiv.innerHTML = '<span style="color: #ff4444;">Please enter an admin code</span>';
        return;
    }
    
    // For development, accept simple codes
    const validCodes = ['admin', 'ADMIN', 'dev123', 'DEV123'];
    
    if (validCodes.includes(authCode)) {
        adminSession.authenticated = true;
        adminSession.expires = Date.now() + (10 * 60 * 1000); // 10 minutes
        adminSession.token = 'dev-admin-' + authCode.toLowerCase();
        
        // Clear the input for security
        input.value = '';
        
        // Update status display
        const expiryTime = new Date(adminSession.expires).toLocaleTimeString();
        statusDiv.innerHTML = `<span style="color: #00ff00;">✅ Authenticated until ${expiryTime}</span>`;
        
        console.log('Admin authentication successful via card');
        
        // Start countdown timer
        updateAuthTimer();
    } else {
        statusDiv.innerHTML = '<span style="color: #ff4444;">❌ Invalid admin code. Use: admin, ADMIN, dev123, or DEV123</span>';
        input.value = '';
    }
}

function clearAdminAuth() {
    adminSession.authenticated = false;
    adminSession.expires = 0;
    adminSession.token = '';
    
    const statusDiv = document.getElementById('admin-status');
    statusDiv.innerHTML = '<span style="color: #aaa;">Not authenticated</span>';
    
    console.log('Admin authentication cleared');
}

function updateAuthTimer() {
    const statusDiv = document.getElementById('admin-status');
    
    if (!adminSession.authenticated || Date.now() >= adminSession.expires) {
        clearAdminAuth();
        return;
    }
    
    const remainingMs = adminSession.expires - Date.now();
    const remainingMins = Math.ceil(remainingMs / (60 * 1000));
    const expiryTime = new Date(adminSession.expires).toLocaleTimeString();
    
    statusDiv.innerHTML = `<span style="color: #00ff00;">✅ Authenticated (${remainingMins} min remaining, expires ${expiryTime})</span>`;
    
    // Update every 30 seconds
    setTimeout(updateAuthTimer, 30000);
}

// Override old cleanup functions with admin-protected versions
function cleanupSelectedCollection() {
    console.log('cleanupSelectedCollection() called - checking admin auth');
    if (!isAdminAuthenticated()) {
        alert('Please authenticate using the Admin Authentication card above first.');
        return;
    }
    executeAdminAction('cleanup-selected');
}

function cleanupEnvironmentData() {
    console.log('cleanupEnvironmentData() called - checking admin auth');  
    if (!isAdminAuthenticated()) {
        alert('Please authenticate using the Admin Authentication card above first.');
        return;
    }
    executeAdminAction('cleanup-all');
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing admin UI');
    
    // Auto-refresh status every 30 seconds
    refreshStatus();
    setInterval(refreshStatus, 30000);
    
    // Load bug management data on page load
    refreshBugs();
    
    // Add Enter key support for admin authentication
    const adminInput = document.getElementById('admin-code-input');
    if (adminInput) {
        adminInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                authenticateAdmin();
            }
        });
    }
    
    // Override any existing cleanup functions to ensure admin protection
    // Use setTimeout to ensure this happens after inline script executes
    setTimeout(() => {
        console.log('Applying admin function overrides...');
        window.cleanupSelectedCollection = cleanupSelectedCollection;
        window.cleanupEnvironmentData = cleanupEnvironmentData;
        window.authenticateAdmin = authenticateAdmin;
        window.clearAdminAuth = clearAdminAuth;
        console.log('Admin function overrides applied successfully');
        
        // Verify the overrides worked
        if (typeof window.cleanupSelectedCollection === 'function') {
            console.log('cleanupSelectedCollection override: SUCCESS');
        }
        if (typeof window.cleanupEnvironmentData === 'function') {
            console.log('cleanupEnvironmentData override: SUCCESS');
        }
    }, 100); // Small delay to ensure inline script has executed
    
    console.log('Admin UI initialization complete');
});