// TTRPG Center User Interface JavaScript
console.log('TTRPG Center User Interface loaded');

class TTRPGInterface {
    constructor() {
        this.isQuerying = false;
        this.startTime = null;
        this.queryTimer = null;
        this.tokenCount = 0;
        this.memoryMode = 'session';
        this.sessionId = this.generateSessionId();
        
        this.initializeInterface();
    }
    
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    initializeInterface() {
        console.log('Initializing TTRPG interface');
        
        // Initialize memory mode
        const memorySelect = document.getElementById('memory-mode');
        if (memorySelect) {
            memorySelect.value = this.memoryMode;
            memorySelect.addEventListener('change', (e) => {
                this.memoryMode = e.target.value;
                this.updateMemoryDisplay();
            });
        }
        
        // Initialize query input
        const queryInput = document.getElementById('query-input');
        if (queryInput) {
            queryInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.submitQuery();
                }
            });
            
            queryInput.focus();
        }
        
        // Initialize submit button
        const submitBtn = document.getElementById('submit-query');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitQuery());
        }
        
        // Initialize source toggle
        const sourceToggle = document.getElementById('source-toggle');
        if (sourceToggle) {
            sourceToggle.addEventListener('click', () => this.toggleSourceInfo());
        }
        
        // Update initial metrics
        this.updateMetrics();
        this.updateMemoryDisplay();
        
        console.log('TTRPG interface initialized successfully');
    }
    
    updateMemoryDisplay() {
        const memoryDisplay = document.getElementById('memory-display');
        if (memoryDisplay) {
            const modes = {
                'session': 'SESSION-ONLY',
                'user': 'USER-WIDE',
                'party': 'PARTY-WIDE'
            };
            memoryDisplay.textContent = modes[this.memoryMode] || 'UNKNOWN';
        }
    }
    
    updateMetrics(responseTime = 0, tokens = 0) {
        // Update timer
        const timerDisplay = document.getElementById('timer-display');
        if (timerDisplay) {
            if (this.isQuerying) {
                const elapsed = Date.now() - this.startTime;
                timerDisplay.textContent = (elapsed / 1000).toFixed(1) + 's';
            } else {
                timerDisplay.textContent = responseTime > 0 ? (responseTime / 1000).toFixed(1) + 's' : '0.0s';
            }
        }
        
        // Update token count
        const tokenDisplay = document.getElementById('token-display');
        if (tokenDisplay) {
            this.tokenCount += tokens;
            tokenDisplay.textContent = this.tokenCount.toLocaleString();
        }
        
        // Update model badge
        const modelDisplay = document.getElementById('model-display');
        if (modelDisplay) {
            // This would be updated based on actual response
            modelDisplay.textContent = 'CLAUDE-3.5';
        }
    }
    
    async submitQuery() {
        if (this.isQuerying) {
            console.log('Query already in progress');
            return;
        }
        
        const queryInput = document.getElementById('query-input');
        const query = queryInput?.value?.trim();
        
        if (!query) {
            this.showError('Please enter a query');
            return;
        }
        
        console.log('Submitting query:', query);
        
        this.startQuery();
        
        try {
            const response = await this.sendQuery(query);
            this.displayResponse(response);
            this.updateMetrics(Date.now() - this.startTime, response.tokens || 0);
        } catch (error) {
            console.error('Query failed:', error);
            this.showError(`Query failed: ${error.message}`);
        } finally {
            this.endQuery();
        }
    }
    
    startQuery() {
        console.log('Starting query');
        this.isQuerying = true;
        this.startTime = Date.now();
        
        // Update UI state
        const submitBtn = document.getElementById('submit-query');
        const queryInput = document.getElementById('query-input');
        
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = 'PROCESSING...';
        }
        
        if (queryInput) {
            queryInput.disabled = true;
        }
        
        // Show loading in response area
        this.showLoading();
        
        // Start timer updates
        this.queryTimer = setInterval(() => {
            this.updateMetrics();
        }, 100);
    }
    
    endQuery() {
        console.log('Ending query');
        this.isQuerying = false;
        
        // Update UI state
        const submitBtn = document.getElementById('submit-query');
        const queryInput = document.getElementById('query-input');
        
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'EXECUTE';
        }
        
        if (queryInput) {
            queryInput.disabled = false;
            queryInput.focus();
        }
        
        // Stop timer updates
        if (this.queryTimer) {
            clearInterval(this.queryTimer);
            this.queryTimer = null;
        }
        
        // Final metrics update
        this.updateMetrics();
    }
    
    async sendQuery(query) {
        console.log('Sending query to backend:', query);
        
        const requestData = {
            query: query,
            memory_mode: this.memoryMode,
            session_id: this.sessionId
        };
        
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Received response:', data);
        
        return data;
    }
    
    showLoading() {
        const responseContent = document.getElementById('response-content');
        if (responseContent) {
            responseContent.innerHTML = `
                <div class="response-loading">
                    <div class="loading-spinner"></div>
                    PROCESSING QUERY...
                </div>
            `;
        }
    }
    
    displayResponse(response) {
        console.log('Displaying response');
        
        const responseContent = document.getElementById('response-content');
        if (!responseContent) {
            console.error('Response content element not found');
            return;
        }
        
        let html = '';
        
        if (response.answer) {
            html += `<div class="answer-text">${this.formatText(response.answer)}</div>`;
        }
        
        if (response.sources && response.sources.length > 0) {
            html += `<div class="source-info" id="source-info" style="display: none;">`;
            html += `<h4 style="color: var(--lcars-orange); margin-top: 20px;">Source Information:</h4>`;
            response.sources.forEach((source, index) => {
                html += `<div class="source-chunk" style="margin: 10px 0; padding: 10px; background: rgba(0,255,255,0.1); border-left: 3px solid var(--terminal-glow);">`;
                html += `<div style="font-size: 0.8rem; color: var(--lcars-yellow); margin-bottom: 5px;">`;
                html += `Source ${index + 1}: ${source.metadata?.source || 'Unknown'} (Page ${source.metadata?.page || 'N/A'})`;
                html += `</div>`;
                html += `<div style="font-size: 0.9rem;">${this.formatText(source.text)}</div>`;
                html += `</div>`;
            });
            html += `</div>`;
        }
        
        if (response.route_info) {
            html += `<div class="route-info" style="margin-top: 15px; font-size: 0.8rem; color: var(--lcars-blue);">`;
            html += `Route: ${response.route_info.route || 'unknown'} | `;
            html += `Model: ${response.route_info.model || 'unknown'}`;
            html += `</div>`;
        }
        
        responseContent.innerHTML = html || '<div style="color: var(--error-color);">No response received</div>';
    }
    
    formatText(text) {
        if (!text) return '';
        
        // Basic text formatting for terminal display
        return text
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--lcars-orange);">$1</strong>')
            .replace(/\*(.*?)\*/g, '<em style="color: var(--lcars-yellow);">$1</em>')
            .replace(/`(.*?)`/g, '<code style="background: rgba(0,0,0,0.5); padding: 2px 4px; color: var(--console-text);">$1</code>');
    }
    
    showError(message) {
        console.error('Showing error:', message);
        
        const responseContent = document.getElementById('response-content');
        if (responseContent) {
            responseContent.innerHTML = `
                <div style="color: var(--error-color); text-align: center; padding: 20px;">
                    <div style="font-size: 1.2rem; margin-bottom: 10px;">⚠ ERROR</div>
                    <div>${message}</div>
                </div>
            `;
        }
    }
    
    toggleSourceInfo() {
        const sourceInfo = document.getElementById('source-info');
        const toggle = document.getElementById('source-toggle');
        
        if (sourceInfo && toggle) {
            const isVisible = sourceInfo.style.display !== 'none';
            sourceInfo.style.display = isVisible ? 'none' : 'block';
            toggle.textContent = isVisible ? 'SHOW SOURCES' : 'HIDE SOURCES';
        }
    }
    
    // System status indicators
    updateSystemStatus() {
        // This would be called periodically to update system health indicators
        // For now, just log that it would happen
        console.log('System status update (placeholder)');
    }
}

// Initialize the interface when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing TTRPG interface');
    
    // Create global interface instance
    window.ttrpgInterface = new TTRPGInterface();
    
    // Set up periodic system status updates (placeholder)
    setInterval(() => {
        window.ttrpgInterface.updateSystemStatus();
    }, 30000);
});