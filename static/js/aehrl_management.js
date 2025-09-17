/**
 * AEHRL Management Interface
 *
 * Provides interactive interface for managing AEHRL correction recommendations,
 * viewing metrics, and monitoring alerts.
 */

class AEHRLManager {
    constructor() {
        this.corrections = [];
        this.filteredCorrections = [];
        this.currentFilters = {
            type: '',
            confidence: '',
            job_id: '',
            sort_by: 'confidence'
        };
        this.metrics = null;
        this.alerts = [];

        this.init();
    }

    async init() {
        await this.loadData();
        this.setupEventListeners();
        this.renderCorrections();
        this.updateDashboard();
    }

    async loadData() {
        try {
            this.showLoading(true);

            // Load corrections, metrics, and alerts in parallel
            const [correctionsResponse, metricsResponse, alertsResponse] = await Promise.all([
                fetch('/admin/api/aehrl/corrections'),
                fetch('/admin/api/aehrl/metrics'),
                fetch('/admin/api/aehrl/alerts')
            ]);

            if (correctionsResponse.ok) {
                const correctionsData = await correctionsResponse.json();
                this.corrections = correctionsData.corrections || [];
                this.filteredCorrections = [...this.corrections];
            }

            if (metricsResponse.ok) {
                const metricsData = await metricsResponse.json();
                this.metrics = metricsData;
            }

            if (alertsResponse.ok) {
                const alertsData = await alertsResponse.json();
                this.alerts = alertsData.alerts || [];
            }

            console.log(`Loaded ${this.corrections.length} corrections, ${this.alerts.length} alerts`);

        } catch (error) {
            console.error('Error loading AEHRL data:', error);
            this.showError('Failed to load AEHRL data: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    setupEventListeners() {
        // Modal action confirmation
        document.getElementById('confirmActionBtn').addEventListener('click', () => {
            this.executeModalAction();
        });

        // Tab change events
        document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
            tab.addEventListener('shown.bs.tab', (event) => {
                const targetTab = event.target.getAttribute('data-bs-target');
                if (targetTab === '#metrics') {
                    this.renderMetrics();
                } else if (targetTab === '#alerts') {
                    this.renderAlerts();
                }
            });
        });
    }

    renderCorrections() {
        const container = document.getElementById('correctionsContainer');
        const emptyState = document.getElementById('correctionsEmptyState');

        if (this.filteredCorrections.length === 0) {
            container.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';

        const html = this.filteredCorrections.map(correction => this.renderCorrectionCard(correction)).join('');
        container.innerHTML = html;
    }

    renderCorrectionCard(correction) {
        const confidenceLevel = this.getConfidenceLevel(correction.confidence);
        const confidencePercent = Math.round(correction.confidence * 100);
        const typeDisplay = this.formatCorrectionType(correction.type);

        return `
            <div class="card correction-card confidence-${confidenceLevel}" data-id="${correction.id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center">
                        <i class="bi ${this.getTypeIcon(correction.type)} fs-5 me-2"></i>
                        <h5 class="mb-0">${this.escapeHtml(correction.description)}</h5>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge confidence-badge" style="background-color: ${this.getConfidenceColor(correction.confidence)}">
                            ${confidencePercent}% confidence
                        </span>
                        <span class="badge bg-secondary">${typeDisplay}</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="correction-metadata mb-3">
                        <div class="row">
                            <div class="col-md-6">
                                <small><strong>Target:</strong> ${this.escapeHtml(correction.target)}</small><br>
                                <small><strong>Job ID:</strong> ${correction.job_id || 'N/A'}</small><br>
                                <small><strong>Environment:</strong> <span class="badge bg-secondary">${correction.environment}</span></small>
                            </div>
                            <div class="col-md-6">
                                <small><strong>Created:</strong> ${this.formatDate(correction.created_at)}</small><br>
                                <small><strong>Type:</strong> ${typeDisplay}</small><br>
                                <small><strong>Impact:</strong> ${correction.impact_assessment || 'Not assessed'}</small>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <h6>Proposed Change</h6>
                        <div class="correction-diff">
                            <div class="diff-old mb-2">
                                <strong>Current:</strong> ${this.escapeHtml(JSON.stringify(correction.current_value))}
                            </div>
                            <div class="diff-new">
                                <strong>Suggested:</strong> ${this.escapeHtml(JSON.stringify(correction.suggested_value))}
                            </div>
                        </div>
                    </div>

                    <div class="correction-actions">
                        <div class="d-flex gap-2">
                            <button class="btn btn-success" onclick="aehrlManager.acceptCorrection('${correction.id}')">
                                <i class="bi bi-check-circle"></i> Accept
                            </button>
                            <button class="btn btn-danger" onclick="aehrlManager.rejectCorrection('${correction.id}')">
                                <i class="bi bi-x-circle"></i> Reject
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    renderMetrics() {
        const metricsContent = document.getElementById('metricsContent');
        const correctionStatsContent = document.getElementById('correctionStatsContent');

        if (!this.metrics) {
            metricsContent.innerHTML = '<p class="text-muted">No metrics data available</p>';
            correctionStatsContent.innerHTML = '<p class="text-muted">No statistics available</p>';
            return;
        }

        // Render evaluation metrics
        const metrics = this.metrics.metrics || {};
        metricsContent.innerHTML = `
            <div class="row">
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">Total Queries</small>
                        <div class="h4">${metrics.total_queries || 0}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">Total Claims</small>
                        <div class="h4">${metrics.total_claims || 0}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">Avg Support Rate</small>
                        <div class="h4">${this.formatPercentage(metrics.avg_support_rate)}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">Avg Hallucination Rate</small>
                        <div class="h4">${this.formatPercentage(metrics.avg_hallucination_rate)}</div>
                    </div>
                </div>
            </div>
        `;

        // Render correction statistics
        const corrections = this.metrics.corrections || {};
        correctionStatsContent.innerHTML = `
            <div class="row">
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">Pending</small>
                        <div class="h4">${corrections.pending_count || 0}</div>
                    </div>
                </div>
                <div class="col-6">
                    <div class="metric-item mb-3">
                        <small class="text-muted">High Confidence</small>
                        <div class="h4">${corrections.pending_by_confidence?.high || 0}</div>
                    </div>
                </div>
            </div>
            <div class="mt-3">
                <small class="text-muted">By Type:</small>
                ${Object.entries(corrections.pending_by_type || {}).map(([type, count]) =>
                    `<div class="d-flex justify-content-between">
                        <span>${this.formatCorrectionType(type)}</span>
                        <span class="badge bg-secondary">${count}</span>
                    </div>`
                ).join('')}
            </div>
        `;
    }

    renderAlerts() {
        const alertsContainer = document.getElementById('alertsContainer');

        if (this.alerts.length === 0) {
            alertsContainer.innerHTML = '<p class="text-muted">No recent alerts</p>';
            return;
        }

        const html = this.alerts.map(alert => `
            <div class="alert-item alert-${alert.severity}">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong>${alert.type.replace(/_/g, ' ').toUpperCase()}</strong>
                        <p class="mb-1">${alert.message}</p>
                        <small class="text-muted">${this.formatDate(alert.timestamp)}</small>
                    </div>
                    <span class="badge bg-${this.getSeverityColor(alert.severity)}">${alert.severity}</span>
                </div>
            </div>
        `).join('');

        alertsContainer.innerHTML = html;
    }

    async acceptCorrection(correctionId) {
        const correction = this.corrections.find(c => c.id === correctionId);
        if (!correction) return;

        this.showActionModal(
            'Accept Correction',
            `Are you sure you want to accept the correction for "${correction.target}"? This will apply the suggested change.`,
            () => this.performCorrectionAction(correctionId, 'accept')
        );
    }

    async rejectCorrection(correctionId) {
        const correction = this.corrections.find(c => c.id === correctionId);
        if (!correction) return;

        this.showActionModal(
            'Reject Correction',
            `Are you sure you want to reject the correction for "${correction.target}"?`,
            () => this.performCorrectionAction(correctionId, 'reject'),
            true // Show rejection reason input
        );
    }

    async performCorrectionAction(correctionId, action) {
        try {
            this.showLoading(true);

            const url = `/admin/api/aehrl/corrections/${correctionId}/${action}`;
            const options = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            };

            if (action === 'reject') {
                const reason = document.getElementById('rejectionReason').value;
                options.body = JSON.stringify({ reason });
            }

            const response = await fetch(url, options);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            if (result.success) {
                // Remove from local state
                this.corrections = this.corrections.filter(c => c.id !== correctionId);
                this.applyFilters();
                this.renderCorrections();
                this.updateDashboard();

                this.showSuccess(`Correction ${action}ed successfully`);
            } else {
                throw new Error(result.error || 'Unknown error');
            }

        } catch (error) {
            console.error(`Error ${action}ing correction:`, error);
            this.showError(`Failed to ${action} correction: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    filterCorrections() {
        // Update filter values
        this.currentFilters.type = document.getElementById('typeFilter').value;
        this.currentFilters.confidence = document.getElementById('confidenceFilter').value;
        this.currentFilters.job_id = document.getElementById('jobFilter').value;
        this.currentFilters.sort_by = document.getElementById('sortBy').value;

        this.applyFilters();
        this.renderCorrections();
    }

    applyFilters() {
        this.filteredCorrections = this.corrections.filter(correction => {
            // Type filter
            if (this.currentFilters.type && correction.type !== this.currentFilters.type) {
                return false;
            }

            // Confidence filter
            if (this.currentFilters.confidence) {
                const confidenceLevel = this.getConfidenceLevel(correction.confidence);
                if (confidenceLevel !== this.currentFilters.confidence) {
                    return false;
                }
            }

            // Job ID filter
            if (this.currentFilters.job_id) {
                const jobId = correction.job_id || '';
                if (!jobId.toLowerCase().includes(this.currentFilters.job_id.toLowerCase())) {
                    return false;
                }
            }

            return true;
        });

        // Apply sorting
        this.filteredCorrections.sort((a, b) => {
            switch (this.currentFilters.sort_by) {
                case 'confidence':
                    return b.confidence - a.confidence;
                case 'created_at':
                    return new Date(b.created_at) - new Date(a.created_at);
                case 'type':
                    return a.type.localeCompare(b.type);
                default:
                    return 0;
            }
        });
    }

    updateDashboard() {
        // Update metrics cards
        if (this.metrics && this.metrics.metrics) {
            const metrics = this.metrics.metrics;
            document.getElementById('avgSupportRate').textContent = this.formatPercentage(metrics.avg_support_rate);
            document.getElementById('hallucinationRate').textContent = this.formatPercentage(metrics.avg_hallucination_rate);
        }

        document.getElementById('pendingCorrections').textContent = this.corrections.length;
        document.getElementById('recentAlerts').textContent = this.alerts.length;
    }

    async loadAlerts() {
        try {
            this.showLoading(true);
            const response = await fetch('/admin/api/aehrl/alerts');

            if (response.ok) {
                const data = await response.json();
                this.alerts = data.alerts || [];
                this.renderAlerts();
                this.updateDashboard();
            }
        } catch (error) {
            console.error('Error loading alerts:', error);
            this.showError('Failed to load alerts: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    showActionModal(title, message, action, showRejectionReason = false) {
        document.getElementById('actionModalTitle').textContent = title;
        document.getElementById('actionModalBody').textContent = message;

        const rejectionGroup = document.getElementById('rejectionReasonGroup');
        if (showRejectionReason) {
            rejectionGroup.style.display = 'block';
            document.getElementById('rejectionReason').value = '';
        } else {
            rejectionGroup.style.display = 'none';
        }

        this.pendingModalAction = action;

        const modal = new bootstrap.Modal(document.getElementById('actionModal'));
        modal.show();
    }

    executeModalAction() {
        if (this.pendingModalAction) {
            this.pendingModalAction();
            this.pendingModalAction = null;
        }

        const modal = bootstrap.Modal.getInstance(document.getElementById('actionModal'));
        modal.hide();
    }

    // Utility functions
    getConfidenceLevel(confidence) {
        if (confidence >= 0.8) return 'high';
        if (confidence >= 0.6) return 'medium';
        return 'low';
    }

    getConfidenceColor(confidence) {
        if (confidence >= 0.8) return '#28a745';
        if (confidence >= 0.6) return '#ffc107';
        return '#dc3545';
    }

    getTypeIcon(type) {
        const icons = {
            'dictionary_update': 'bi-book',
            'graph_edge_fix': 'bi-diagram-2',
            'graph_node_fix': 'bi-circle',
            'metadata_correction': 'bi-tags',
            'chunk_revision': 'bi-file-text'
        };
        return icons[type] || 'bi-tools';
    }

    formatCorrectionType(type) {
        return type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    getSeverityColor(severity) {
        const colors = {
            'high': 'danger',
            'medium': 'warning',
            'low': 'info'
        };
        return colors[severity] || 'secondary';
    }

    formatPercentage(value) {
        if (value === null || value === undefined) return '--';
        return Math.round(value * 100) + '%';
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showLoading(show) {
        const spinner = document.querySelector('.loading-spinner');
        spinner.style.display = show ? 'inline-block' : 'none';
    }

    showError(message) {
        console.error(message);
        // TODO: Implement toast notifications
        alert('Error: ' + message);
    }

    showSuccess(message) {
        console.log(message);
        // TODO: Implement toast notifications
        // For now, just log success
    }
}

// Global functions for template access
function refreshData() {
    aehrlManager.loadData().then(() => {
        aehrlManager.applyFilters();
        aehrlManager.renderCorrections();
        aehrlManager.updateDashboard();
    });
}

function filterCorrections() {
    aehrlManager.filterCorrections();
}

function loadAlerts() {
    aehrlManager.loadAlerts();
}

// Initialize when DOM is loaded
let aehrlManager;
document.addEventListener('DOMContentLoaded', () => {
    aehrlManager = new AEHRLManager();
});