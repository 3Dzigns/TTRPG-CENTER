/**
 * Feedback Widgets - Phase 6 UI Components
 * Specialized widgets for feedback display and interaction
 */

// Feedback Widget Components
class FeedbackWidget {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        this.options = {
            autoRefresh: true,
            refreshInterval: 30000,
            showTimestamps: true,
            enableTooltips: true,
            ...options
        };
        
        if (!this.container) {
            throw new Error('Feedback widget container not found');
        }
        
        this.init();
    }
    
    init() {
        this.render();
        
        if (this.options.autoRefresh) {
            this.startAutoRefresh();
        }
        
        if (this.options.enableTooltips) {
            this.initializeTooltips();
        }
    }
    
    render() {
        // Override in subclasses
    }
    
    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            this.refresh();
        }, this.options.refreshInterval);
    }
    
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    refresh() {
        // Override in subclasses
    }
    
    initializeTooltips() {
        const tooltipElements = this.container.querySelectorAll('[data-tooltip]');
        tooltipElements.forEach(element => {
            this.addTooltip(element, element.dataset.tooltip);
        });
    }
    
    addTooltip(element, text) {
        element.addEventListener('mouseenter', (e) => {
            this.showTooltip(e.target, text);
        });
        
        element.addEventListener('mouseleave', () => {
            this.hideTooltip();
        });
    }
    
    showTooltip(target, text) {
        this.hideTooltip(); // Remove any existing tooltip
        
        const tooltip = document.createElement('div');
        tooltip.className = 'feedback-tooltip';
        tooltip.textContent = text;
        tooltip.style.cssText = `
            position: absolute;
            background: var(--panel-bg);
            color: var(--primary-text);
            padding: 0.5rem 0.75rem;
            border-radius: 4px;
            font-size: 0.875rem;
            border: 1px solid var(--border-color);
            z-index: 1000;
            pointer-events: none;
            white-space: nowrap;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        `;
        
        document.body.appendChild(tooltip);
        
        // Position tooltip
        const targetRect = target.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        tooltip.style.left = `${targetRect.left + (targetRect.width - tooltipRect.width) / 2}px`;
        tooltip.style.top = `${targetRect.top - tooltipRect.height - 8}px`;
        
        this.currentTooltip = tooltip;
    }
    
    hideTooltip() {
        if (this.currentTooltip) {
            this.currentTooltip.remove();
            this.currentTooltip = null;
        }
    }
    
    destroy() {
        this.stopAutoRefresh();
        this.hideTooltip();
        
        // Remove all event listeners
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Stats Dashboard Widget
class StatsWidget extends FeedbackWidget {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            refreshInterval: 15000 // Refresh stats every 15 seconds
        });
    }
    
    async render() {
        try {
            const stats = await this.fetchStats();
            this.renderStats(stats);
        } catch (error) {
            console.error('Stats widget render error:', error);
            this.renderError('Failed to load statistics');
        }
    }
    
    async fetchStats() {
        const response = await fetch('/api/feedback/stats', {
            headers: {
                'Cache-Control': 'no-store'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    }
    
    renderStats(stats) {
        this.container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card" data-tooltip="Total regression tests created from positive feedback">
                    <div class="stat-icon">
                        <i class="fas fa-check-circle"></i>
                    </div>
                    <span class="stat-number" id="regression-tests">${stats.regression_tests}</span>
                    <span class="stat-label">Regression Tests</span>
                </div>
                
                <div class="stat-card" data-tooltip="Total bug bundles created from negative feedback">
                    <div class="stat-icon">
                        <i class="fas fa-bug"></i>
                    </div>
                    <span class="stat-number" id="bug-bundles">${stats.bug_bundles}</span>
                    <span class="stat-label">Bug Reports</span>
                </div>
                
                <div class="stat-card" data-tooltip="Total feedback submissions received">
                    <div class="stat-icon">
                        <i class="fas fa-comments"></i>
                    </div>
                    <span class="stat-number" id="total-feedback">${stats.total_feedback}</span>
                    <span class="stat-label">Total Feedback</span>
                </div>
                
                <div class="stat-card" data-tooltip="Last update timestamp">
                    <div class="stat-icon">
                        <i class="fas fa-clock"></i>
                    </div>
                    <span class="stat-number">${new Date(stats.last_updated * 1000).toLocaleTimeString()}</span>
                    <span class="stat-label">Last Updated</span>
                </div>
            </div>
        `;
        
        this.initializeTooltips();
    }
    
    renderError(message) {
        this.container.innerHTML = `
            <div class="alert error">
                <i class="fas fa-exclamation-triangle"></i>
                ${message}
            </div>
        `;
    }
    
    async refresh() {
        await this.render();
    }
}

// Test Gates Widget
class TestGatesWidget extends FeedbackWidget {
    constructor(container, options = {}) {
        super(container, {
            ...options,
            refreshInterval: 10000 // Refresh gates every 10 seconds
        });
    }
    
    async render() {
        try {
            const gates = await this.fetchGates();
            this.renderGates(gates);
        } catch (error) {
            console.error('Test gates widget render error:', error);
            this.renderError('Failed to load test gates');
        }
    }
    
    async fetchGates() {
        const response = await fetch('/api/gates', {
            headers: {
                'Cache-Control': 'no-store'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        return await response.json();
    }
    
    renderGates(gates) {
        if (gates.length === 0) {
            this.container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-shield-alt"></i>
                    <h3>No Test Gates</h3>
                    <p>Create a test gate to begin automated testing</p>
                    <button class="btn primary" id="create-gate-btn">
                        <i class="fas fa-plus"></i>
                        Create Test Gate
                    </button>
                </div>
            `;
        } else {
            this.container.innerHTML = `
                <div class="gates-header">
                    <h3>Test Gates</h3>
                    <button class="btn primary" id="create-gate-btn">
                        <i class="fas fa-plus"></i>
                        New Gate
                    </button>
                </div>
                <div class="gate-list">
                    ${gates.map(gate => this.renderGate(gate)).join('')}
                </div>
            `;
        }
        
        this.initializeGateControls();
        this.initializeTooltips();
    }
    
    renderGate(gate) {
        const statusClass = gate.status;
        const statusIcon = this.getStatusIcon(gate.status);
        const createdTime = new Date(gate.created_at * 1000).toLocaleString();
        const updatedTime = new Date(gate.updated_at * 1000).toLocaleString();
        
        return `
            <div class="gate-item" data-gate="${gate.gate_id}">
                <div class="gate-header">
                    <div class="gate-info">
                        <div class="gate-id">${gate.gate_id}</div>
                        <div class="gate-env">${gate.environment.toUpperCase()}</div>
                    </div>
                    <div class="gate-status-container">
                        <div class="widget-status">
                            <span class="status-indicator ${statusClass}"></span>
                            <span class="gate-status">${gate.status.toUpperCase()}</span>
                        </div>
                        <button class="btn ${gate.status === 'running' ? 'warning' : 'primary'} gate-run-btn" 
                                data-gate-id="${gate.gate_id}"
                                ${gate.status === 'running' ? 'disabled' : ''}
                                data-tooltip="Run all tests for this gate">
                            <i class="fas fa-${gate.status === 'running' ? 'spinner fa-spin' : 'play'}"></i>
                            ${gate.status === 'running' ? 'Running' : 'Run Tests'}
                        </button>
                    </div>
                </div>
                
                <div class="gate-details">
                    <div class="gate-timestamps">
                        <span class="timestamp">
                            <i class="fas fa-calendar-plus"></i>
                            Created: ${createdTime}
                        </span>
                        <span class="timestamp gate-updated">
                            <i class="fas fa-clock"></i>
                            Updated: ${updatedTime}
                        </span>
                    </div>
                </div>
                
                ${Object.keys(gate.test_results).length > 0 ? `
                    <div class="gate-results">
                        ${Object.entries(gate.test_results).map(([testType, result]) => `
                            <div class="test-result ${result.status}" 
                                 data-tooltip="${result.count} tests, ${result.failures} failures">
                                <div class="test-result-name">${this.formatTestName(testType)}</div>
                                <div class="test-result-stats">${result.count} tests, ${result.failures} failures</div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
    
    getStatusIcon(status) {
        const icons = {
            pending: 'clock',
            running: 'spinner fa-spin',
            passed: 'check-circle',
            failed: 'times-circle'
        };
        return icons[status] || 'question-circle';
    }
    
    formatTestName(testType) {
        return testType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
    
    initializeGateControls() {
        // Initialize create gate button
        const createBtn = this.container.querySelector('#create-gate-btn');
        if (createBtn && !createBtn.dataset.initialized) {
            createBtn.dataset.initialized = 'true';
            createBtn.addEventListener('click', () => {
                if (window.feedbackSystem) {
                    window.feedbackSystem.createTestGate();
                }
            });
        }
        
        // Initialize run gate buttons
        const runButtons = this.container.querySelectorAll('.gate-run-btn');
        runButtons.forEach(button => {
            if (!button.dataset.initialized) {
                button.dataset.initialized = 'true';
                button.addEventListener('click', () => {
                    const gateId = button.dataset.gateId;
                    if (window.feedbackSystem && gateId) {
                        window.feedbackSystem.runTestGate(gateId);
                    }
                });
            }
        });
    }
    
    renderError(message) {
        this.container.innerHTML = `
            <div class="alert error">
                <i class="fas fa-exclamation-triangle"></i>
                ${message}
            </div>
        `;
    }
    
    async refresh() {
        await this.render();
    }
}

// Feedback Button Component
class FeedbackButtonWidget {
    constructor(container, feedbackData) {
        this.container = container;
        this.feedbackData = feedbackData;
        this.rendered = false;
        
        this.render();
    }
    
    render() {
        if (this.rendered) return;
        
        this.container.innerHTML = `
            <div class="feedback-buttons" data-feedback="true"
                 data-trace-id="${this.feedbackData.traceId}"
                 data-query="${this.escapeHtml(this.feedbackData.query)}"
                 data-answer="${this.escapeHtml(this.feedbackData.answer)}"
                 data-metadata='${JSON.stringify(this.feedbackData.metadata || {})}'
                 data-chunks='${JSON.stringify(this.feedbackData.chunks || [])}'
                 data-context='${JSON.stringify(this.feedbackData.context || {})}'>
                 
                <button class="feedback-btn thumbs-up" 
                        data-tooltip="Mark as good response - creates regression test">
                    <i class="fas fa-thumbs-up"></i>
                    <span>Good Answer</span>
                </button>
                
                <button class="feedback-btn thumbs-down"
                        data-tooltip="Mark as poor response - creates bug report">
                    <i class="fas fa-thumbs-down"></i>
                    <span>Poor Answer</span>
                </button>
                
                <div class="user-note-container" style="display: none;">
                    <input type="text" class="user-note-input" placeholder="Optional note about the issue...">
                </div>
            </div>
        `;
        
        this.initializeInteractions();
        this.rendered = true;
    }
    
    initializeInteractions() {
        const thumbsDown = this.container.querySelector('.thumbs-down');
        const noteContainer = this.container.querySelector('.user-note-container');
        
        // Show note input for thumbs down
        thumbsDown.addEventListener('click', () => {
            noteContainer.style.display = 'block';
            const input = noteContainer.querySelector('.user-note-input');
            setTimeout(() => input.focus(), 100);
        });
        
        // Initialize tooltips
        const tooltipElements = this.container.querySelectorAll('[data-tooltip]');
        tooltipElements.forEach(element => {
            if (window.feedbackSystem) {
                window.feedbackSystem.addTooltip(element, element.dataset.tooltip);
            }
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    setFeedbackData(data) {
        this.feedbackData = { ...this.feedbackData, ...data };
        
        const feedbackContainer = this.container.querySelector('[data-feedback]');
        if (feedbackContainer) {
            Object.entries(data).forEach(([key, value]) => {
                if (typeof value === 'object') {
                    feedbackContainer.dataset[key] = JSON.stringify(value);
                } else {
                    feedbackContainer.dataset[key] = value;
                }
            });
        }
    }
    
    disable() {
        const buttons = this.container.querySelectorAll('.feedback-btn');
        buttons.forEach(button => {
            button.disabled = true;
            button.classList.add('disabled');
        });
    }
    
    enable() {
        const buttons = this.container.querySelectorAll('.feedback-btn');
        buttons.forEach(button => {
            button.disabled = false;
            button.classList.remove('disabled');
        });
    }
}

// Empty State Component
class EmptyStateWidget {
    constructor(container, config) {
        this.container = container;
        this.config = {
            icon: 'fas fa-inbox',
            title: 'No Data',
            message: 'No items to display',
            actionText: null,
            actionCallback: null,
            ...config
        };
        
        this.render();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <i class="${this.config.icon}"></i>
                </div>
                <h3 class="empty-title">${this.config.title}</h3>
                <p class="empty-message">${this.config.message}</p>
                ${this.config.actionText ? `
                    <button class="btn primary empty-action">
                        ${this.config.actionText}
                    </button>
                ` : ''}
            </div>
        `;
        
        // Initialize action button
        if (this.config.actionCallback) {
            const actionBtn = this.container.querySelector('.empty-action');
            if (actionBtn) {
                actionBtn.addEventListener('click', this.config.actionCallback);
            }
        }
    }
}

// Export components
window.FeedbackWidgets = {
    FeedbackWidget,
    StatsWidget,
    TestGatesWidget,
    FeedbackButtonWidget,
    EmptyStateWidget
};

// Auto-initialize widgets on page load
document.addEventListener('DOMContentLoaded', () => {
    // Initialize stats widgets
    const statsContainers = document.querySelectorAll('[data-widget="stats"]');
    statsContainers.forEach(container => {
        new StatsWidget(container);
    });
    
    // Initialize gates widgets
    const gatesContainers = document.querySelectorAll('[data-widget="gates"]');
    gatesContainers.forEach(container => {
        new TestGatesWidget(container);
    });
    
    // Initialize feedback buttons
    const feedbackContainers = document.querySelectorAll('[data-widget="feedback-buttons"]');
    feedbackContainers.forEach(container => {
        const feedbackData = {
            traceId: container.dataset.traceId,
            query: container.dataset.query,
            answer: container.dataset.answer,
            metadata: JSON.parse(container.dataset.metadata || '{}'),
            chunks: JSON.parse(container.dataset.chunks || '[]'),
            context: JSON.parse(container.dataset.context || '{}')
        };
        
        new FeedbackButtonWidget(container, feedbackData);
    });
});