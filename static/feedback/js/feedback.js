/**
 * Feedback System JavaScript - Phase 6 Testing & Feedback
 * Handles feedback submission, test gate management, and real-time updates
 */

// Global feedback system configuration
window.FEEDBACK_CONFIG = {
    apiBase: '/api',
    cacheBypass: true,
    rateLimitWindow: 60000, // 1 minute
    maxRequestsPerWindow: 10,
    pollInterval: 5000, // 5 seconds for status updates
    version: '6.0.0'
};

// Feedback System Core Class
class FeedbackSystem {
    constructor() {
        this.requestHistory = [];
        this.activePolls = new Map();
        this.eventListeners = new Map();
        
        this.init();
    }
    
    init() {
        console.log('Initializing TTRPG Feedback System v' + window.FEEDBACK_CONFIG.version);
        
        // Initialize rate limiting
        this.cleanupRequestHistory();
        
        // Set up periodic cleanup
        setInterval(() => this.cleanupRequestHistory(), 30000);
        
        // Initialize UI components
        this.initializeUI();
        
        console.log('Feedback System initialized successfully');
    }
    
    initializeUI() {
        // Initialize feedback buttons
        this.initializeFeedbackButtons();
        
        // Initialize test gate controls
        this.initializeTestGateControls();
        
        // Initialize stats polling
        this.initializeStatsPolling();
    }
    
    initializeFeedbackButtons() {
        const feedbackButtons = document.querySelectorAll('.feedback-btn');
        
        feedbackButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleFeedbackClick(button);
            });
        });
    }
    
    initializeTestGateControls() {
        const gateButtons = document.querySelectorAll('.gate-run-btn');
        
        gateButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const gateId = button.dataset.gateId;
                this.runTestGate(gateId);
            });
        });
        
        // Initialize create gate button
        const createGateBtn = document.getElementById('create-gate-btn');
        if (createGateBtn) {
            createGateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.createTestGate();
            });
        }
    }
    
    initializeStatsPolling() {
        // Poll for stats updates every 30 seconds on stats page
        if (window.location.pathname.includes('stats')) {
            this.startStatsPolling();
        }
        
        // Poll for gate status updates on gates page
        if (window.location.pathname.includes('gates')) {
            this.startGateStatusPolling();
        }
    }
    
    // Feedback Submission (US-601, US-602)
    async handleFeedbackClick(button) {
        const rating = button.classList.contains('thumbs-up') ? 'thumbs_up' : 'thumbs_down';
        const feedbackData = this.extractFeedbackData(button);
        
        if (!feedbackData) {
            this.showAlert('Error: Missing feedback data', 'error');
            return;
        }
        
        // Check rate limiting
        if (!this.checkRateLimit()) {
            this.showAlert('Rate limit exceeded. Please wait before submitting more feedback.', 'warning');
            return;
        }
        
        // Disable button and show loading
        button.disabled = true;
        button.classList.add('loading');
        
        try {
            const feedback = {
                trace_id: feedbackData.traceId || this.generateTraceId(),
                rating: rating,
                query: feedbackData.query,
                answer: feedbackData.answer,
                metadata: feedbackData.metadata || {},
                retrieved_chunks: feedbackData.chunks || [],
                context: feedbackData.context || {},
                user_note: feedbackData.userNote
            };
            
            const response = await this.submitFeedback(feedback);
            
            if (response.success) {
                this.showAlert(response.message, 'success');
                this.updateFeedbackUI(button, response);
                
                // Trigger immediate stats update
                if (typeof this.updateStats === 'function') {
                    await this.updateStats();
                }
            } else {
                throw new Error(response.message || 'Feedback submission failed');
            }
            
        } catch (error) {
            console.error('Feedback submission error:', error);
            this.showAlert(`Failed to submit feedback: ${error.message}`, 'error');
            
        } finally {
            button.disabled = false;
            button.classList.remove('loading');
        }
    }
    
    extractFeedbackData(button) {
        // Extract feedback data from button's parent container
        const container = button.closest('.feedback-widget') || button.closest('[data-feedback]');
        
        if (!container) {
            console.error('No feedback container found for button');
            return null;
        }
        
        return {
            traceId: container.dataset.traceId,
            query: container.dataset.query || container.querySelector('.query-text')?.textContent,
            answer: container.dataset.answer || container.querySelector('.answer-text')?.textContent,
            metadata: this.parseDataAttribute(container.dataset.metadata),
            chunks: this.parseDataAttribute(container.dataset.chunks),
            context: this.parseDataAttribute(container.dataset.context),
            userNote: container.querySelector('.user-note-input')?.value
        };
    }
    
    parseDataAttribute(data) {
        if (!data) return {};
        try {
            return JSON.parse(data);
        } catch {
            return {};
        }
    }
    
    generateTraceId() {
        return 'trace_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    // API Communication with Cache Bypass (US-604)
    async submitFeedback(feedback) {
        const response = await fetch(`${window.FEEDBACK_CONFIG.apiBase}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Cache-Control': 'no-store', // Cache bypass (US-604)
                'Pragma': 'no-cache'
            },
            body: JSON.stringify(feedback)
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }
        
        return await response.json();
    }
    
    // Test Gate Management (US-603)
    async createTestGate(environment = 'dev') {
        try {
            const response = await fetch(`${window.FEEDBACK_CONFIG.apiBase}/gates`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-store'
                },
                body: JSON.stringify({ environment })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const gate = await response.json();
            this.showAlert(`Test gate created: ${gate.gate_id}`, 'success');
            
            // Refresh gates list if on gates page
            if (window.location.pathname.includes('gates')) {
                setTimeout(() => window.location.reload(), 1500);
            }
            
            return gate;
            
        } catch (error) {
            console.error('Gate creation error:', error);
            this.showAlert(`Failed to create test gate: ${error.message}`, 'error');
            throw error;
        }
    }
    
    async runTestGate(gateId) {
        try {
            const button = document.querySelector(`[data-gate-id="${gateId}"]`);
            if (button) {
                button.disabled = true;
                button.classList.add('loading');
            }
            
            const response = await fetch(`${window.FEEDBACK_CONFIG.apiBase}/gates/${gateId}/run`, {
                method: 'POST',
                headers: {
                    'Cache-Control': 'no-store'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const gate = await response.json();
            this.showAlert(`Test gate ${gateId} started`, 'info');
            
            // Start polling for gate status updates
            this.startGatePolling(gateId);
            
            return gate;
            
        } catch (error) {
            console.error('Gate run error:', error);
            this.showAlert(`Failed to run test gate: ${error.message}`, 'error');
            
            // Re-enable button
            const button = document.querySelector(`[data-gate-id="${gateId}"]`);
            if (button) {
                button.disabled = false;
                button.classList.remove('loading');
            }
            
            throw error;
        }
    }
    
    async getGateStatus(gateId) {
        const response = await fetch(`${window.FEEDBACK_CONFIG.apiBase}/gates/${gateId}`, {
            headers: {
                'Cache-Control': 'no-store'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    }
    
    // Polling for Real-time Updates
    startGatePolling(gateId) {
        if (this.activePolls.has(gateId)) {
            return; // Already polling this gate
        }
        
        const pollInterval = setInterval(async () => {
            try {
                const gate = await this.getGateStatus(gateId);
                this.updateGateUI(gate);
                
                // Stop polling if gate is complete
                if (gate.status === 'passed' || gate.status === 'failed') {
                    clearInterval(pollInterval);
                    this.activePolls.delete(gateId);
                    
                    // Re-enable run button
                    const button = document.querySelector(`[data-gate-id="${gateId}"]`);
                    if (button) {
                        button.disabled = false;
                        button.classList.remove('loading');
                    }
                }
                
            } catch (error) {
                console.error(`Gate polling error for ${gateId}:`, error);
                clearInterval(pollInterval);
                this.activePolls.delete(gateId);
            }
        }, window.FEEDBACK_CONFIG.pollInterval);
        
        this.activePolls.set(gateId, pollInterval);
    }
    
    startStatsPolling() {
        setInterval(async () => {
            try {
                await this.updateStats();
            } catch (error) {
                console.error('Stats polling error:', error);
            }
        }, 30000); // Poll every 30 seconds
    }
    
    startGateStatusPolling() {
        setInterval(async () => {
            try {
                await this.updateGatesList();
            } catch (error) {
                console.error('Gates polling error:', error);
            }
        }, window.FEEDBACK_CONFIG.pollInterval);
    }
    
    // UI Updates
    updateFeedbackUI(button, response) {
        // Update button state
        button.classList.add('submitted');
        
        // Add feedback indicator
        const indicator = document.createElement('span');
        indicator.className = 'feedback-indicator';
        indicator.textContent = response.action_taken === 'regression_test_created' ? 
            'Regression Test Created' : 'Bug Report Created';
        
        button.parentNode.appendChild(indicator);
        
        // Add fade effect
        setTimeout(() => {
            indicator.style.opacity = '0.7';
        }, 3000);
    }
    
    updateGateUI(gate) {
        const gateElement = document.querySelector(`[data-gate="${gate.gate_id}"]`);
        if (!gateElement) return;
        
        // Update status indicator
        const statusIndicator = gateElement.querySelector('.status-indicator');
        if (statusIndicator) {
            statusIndicator.className = `status-indicator ${gate.status}`;
        }
        
        // Update status text
        const statusText = gateElement.querySelector('.gate-status');
        if (statusText) {
            statusText.textContent = gate.status.toUpperCase();
        }
        
        // Update test results
        const resultsContainer = gateElement.querySelector('.gate-results');
        if (resultsContainer && gate.test_results) {
            this.updateTestResults(resultsContainer, gate.test_results);
        }
        
        // Update timestamp
        const timestamp = gateElement.querySelector('.gate-updated');
        if (timestamp) {
            timestamp.textContent = new Date(gate.updated_at * 1000).toLocaleTimeString();
        }
    }
    
    updateTestResults(container, results) {
        container.innerHTML = '';
        
        Object.entries(results).forEach(([testType, result]) => {
            const resultElement = document.createElement('div');
            resultElement.className = `test-result ${result.status}`;
            
            resultElement.innerHTML = `
                <div class="test-result-name">${this.formatTestName(testType)}</div>
                <div class="test-result-stats">
                    ${result.count} tests, ${result.failures} failures
                </div>
            `;
            
            container.appendChild(resultElement);
        });
    }
    
    formatTestName(testType) {
        return testType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    async updateStats() {
        try {
            const response = await fetch(`${window.FEEDBACK_CONFIG.apiBase}/feedback/stats`, {
                headers: {
                    'Cache-Control': 'no-store'
                }
            });
            
            if (!response.ok) return;
            
            const stats = await response.json();
            
            // Update stat cards
            this.updateStatCard('regression-tests', stats.regression_tests);
            this.updateStatCard('bug-bundles', stats.bug_bundles);
            this.updateStatCard('total-feedback', stats.total_feedback);
            
        } catch (error) {
            console.error('Stats update error:', error);
        }
    }
    
    updateStatCard(cardId, value) {
        const card = document.getElementById(cardId);
        if (card) {
            const numberElement = card.querySelector('.stat-number');
            if (numberElement) {
                numberElement.textContent = value;
            }
        }
    }
    
    async updateGatesList() {
        // Implementation would fetch and update gates list
        // Placeholder for dynamic gates list update
    }
    
    // Rate Limiting
    checkRateLimit() {
        const now = Date.now();
        const windowStart = now - window.FEEDBACK_CONFIG.rateLimitWindow;
        
        // Clean old requests
        this.requestHistory = this.requestHistory.filter(time => time > windowStart);
        
        // Check limit
        if (this.requestHistory.length >= window.FEEDBACK_CONFIG.maxRequestsPerWindow) {
            return false;
        }
        
        // Add current request
        this.requestHistory.push(now);
        return true;
    }
    
    cleanupRequestHistory() {
        const cutoff = Date.now() - window.FEEDBACK_CONFIG.rateLimitWindow;
        this.requestHistory = this.requestHistory.filter(time => time > cutoff);
    }
    
    // UI Helpers
    showAlert(message, type = 'info') {
        const alertsContainer = this.getOrCreateAlertsContainer();
        
        const alert = document.createElement('div');
        alert.className = `alert ${type}`;
        alert.innerHTML = `
            <i class="fas fa-${this.getAlertIcon(type)}"></i>
            ${message}
            <button class="alert-close" onclick="this.parentNode.remove()">×</button>
        `;
        
        alertsContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentNode) {
                alert.remove();
            }
        }, 5000);
    }
    
    getAlertIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    getOrCreateAlertsContainer() {
        let container = document.getElementById('alerts-container');
        
        if (!container) {
            container = document.createElement('div');
            container.id = 'alerts-container';
            container.style.cssText = `
                position: fixed;
                top: 2rem;
                right: 2rem;
                z-index: 1000;
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        
        return container;
    }
    
    // Cleanup
    destroy() {
        // Clear all active polls
        this.activePolls.forEach(pollInterval => {
            clearInterval(pollInterval);
        });
        this.activePolls.clear();
        
        // Remove event listeners
        this.eventListeners.forEach((listener, element) => {
            element.removeEventListener(listener.event, listener.handler);
        });
        this.eventListeners.clear();
        
        console.log('Feedback System destroyed');
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (typeof window.feedbackSystem === 'undefined') {
        window.feedbackSystem = new FeedbackSystem();
    }
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FeedbackSystem };
}