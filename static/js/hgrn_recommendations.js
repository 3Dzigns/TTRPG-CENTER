/**
 * HGRN Recommendations Management Interface
 *
 * Provides interactive interface for viewing and managing HGRN validation
 * recommendations with filtering, search, and action capabilities.
 */

class HGRNRecommendationsManager {
    constructor() {
        this.recommendations = [];
        this.filteredRecommendations = [];
        this.currentFilters = {
            environment: '',
            severity: '',
            type: '',
            status: ''
        };

        this.init();
    }

    async init() {
        await this.loadRecommendations();
        this.setupEventListeners();
        this.renderRecommendations();
        this.updateStats();
    }

    async loadRecommendations() {
        try {
            this.showLoading(true);

            const response = await fetch('/admin/api/hgrn/recommendations');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.recommendations = data.recommendations || [];
            this.filteredRecommendations = [...this.recommendations];

            console.log(`Loaded ${this.recommendations.length} HGRN recommendations`);

        } catch (error) {
            console.error('Error loading HGRN recommendations:', error);
            this.showError('Failed to load HGRN recommendations: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    setupEventListeners() {
        // Modal action confirmation
        document.getElementById('confirmActionBtn').addEventListener('click', () => {
            this.executeModalAction();
        });
    }

    renderRecommendations() {
        const container = document.getElementById('recommendationsContainer');
        const emptyState = document.getElementById('emptyState');

        if (this.filteredRecommendations.length === 0) {
            container.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';

        const html = this.filteredRecommendations.map(rec => this.renderRecommendationCard(rec)).join('');
        container.innerHTML = html;
    }

    renderRecommendationCard(recommendation) {
        const {
            id, type, severity, confidence, title, description, evidence,
            suggested_action, page_refs, chunk_ids, created_at, accepted, rejected,
            job_id, environment
        } = recommendation;

        const severityColor = this.getSeverityColor(severity);
        const typeIcon = this.getTypeIcon(type);
        const confidencePercent = Math.round(confidence * 100);
        const status = accepted ? 'accepted' : (rejected ? 'rejected' : 'pending');
        const statusBadge = this.getStatusBadge(status);

        return `
            <div class="card recommendation-card severity-${severity}" data-id="${id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center">
                        <i class="bi ${typeIcon} fs-5 me-2"></i>
                        <h5 class="mb-0">${this.escapeHtml(title)}</h5>
                    </div>
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge confidence-badge" style="background-color: ${this.getConfidenceColor(confidence)}">
                            ${confidencePercent}% confidence
                        </span>
                        <span class="badge bg-${severityColor}">${severity.toUpperCase()}</span>
                        ${statusBadge}
                    </div>
                </div>
                <div class="card-body">
                    <div class="recommendation-metadata mb-3">
                        <div class="row">
                            <div class="col-md-6">
                                <small><strong>Job ID:</strong> ${job_id}</small><br>
                                <small><strong>Environment:</strong> <span class="badge bg-secondary">${environment}</span></small><br>
                                <small><strong>Type:</strong> ${type}</small>
                            </div>
                            <div class="col-md-6">
                                <small><strong>Created:</strong> ${this.formatDate(created_at)}</small><br>
                                <small><strong>Pages:</strong> ${page_refs.length > 0 ? page_refs.join(', ') : 'N/A'}</small><br>
                                <small><strong>Chunks:</strong> ${chunk_ids.length}</small>
                            </div>
                        </div>
                    </div>

                    <div class="mb-3">
                        <h6>Description</h6>
                        <p class="mb-0">${this.escapeHtml(description)}</p>
                    </div>

                    <div class="mb-3">
                        <h6>Suggested Action</h6>
                        <p class="mb-0">${this.escapeHtml(suggested_action)}</p>
                    </div>

                    ${this.renderEvidence(evidence)}

                    <div class="recommendation-actions">
                        ${this.renderActionButtons(id, status)}
                    </div>
                </div>
            </div>
        `;
    }

    renderEvidence(evidence) {
        if (!evidence || Object.keys(evidence).length === 0) {
            return '';
        }

        const evidenceEntries = Object.entries(evidence)
            .map(([key, value]) => {
                let displayValue;
                if (typeof value === 'object') {
                    displayValue = JSON.stringify(value, null, 2);
                } else {
                    displayValue = String(value);
                }

                return `<div class="mb-2">
                    <strong>${this.escapeHtml(key)}:</strong>
                    <div class="evidence-code">${this.escapeHtml(displayValue)}</div>
                </div>`;
            })
            .join('');

        return `
            <div class="mb-3">
                <h6>Evidence</h6>
                ${evidenceEntries}
            </div>
        `;
    }

    renderActionButtons(recommendationId, status) {
        if (status === 'accepted') {
            return `
                <div class="d-flex gap-2">
                    <span class="text-success"><i class="bi bi-check-circle"></i> Accepted</span>
                    <button class="btn btn-sm btn-outline-secondary" onclick="hgrnManager.rejectRecommendation('${recommendationId}')">
                        <i class="bi bi-x-circle"></i> Reject
                    </button>
                </div>
            `;
        } else if (status === 'rejected') {
            return `
                <div class="d-flex gap-2">
                    <span class="text-danger"><i class="bi bi-x-circle"></i> Rejected</span>
                    <button class="btn btn-sm btn-outline-success" onclick="hgrnManager.acceptRecommendation('${recommendationId}')">
                        <i class="bi bi-check-circle"></i> Accept
                    </button>
                </div>
            `;
        } else {
            return `
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-success" onclick="hgrnManager.acceptRecommendation('${recommendationId}')">
                        <i class="bi bi-check-circle"></i> Accept
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="hgrnManager.rejectRecommendation('${recommendationId}')">
                        <i class="bi bi-x-circle"></i> Reject
                    </button>
                </div>
            `;
        }
    }

    async acceptRecommendation(recommendationId) {
        const recommendation = this.recommendations.find(r => r.id === recommendationId);
        if (!recommendation) return;

        this.showActionModal(
            'Accept Recommendation',
            `Are you sure you want to accept the recommendation "${recommendation.title}"?`,
            () => this.performRecommendationAction(recommendationId, 'accept')
        );
    }

    async rejectRecommendation(recommendationId) {
        const recommendation = this.recommendations.find(r => r.id === recommendationId);
        if (!recommendation) return;

        this.showActionModal(
            'Reject Recommendation',
            `Are you sure you want to reject the recommendation "${recommendation.title}"?`,
            () => this.performRecommendationAction(recommendationId, 'reject')
        );
    }

    async performRecommendationAction(recommendationId, action) {
        try {
            this.showLoading(true);

            const response = await fetch(`/admin/api/hgrn/recommendations/${recommendationId}/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            if (result.success) {
                // Update local state
                const recommendation = this.recommendations.find(r => r.id === recommendationId);
                if (recommendation) {
                    recommendation.accepted = action === 'accept';
                    recommendation.rejected = action === 'reject';
                }

                this.applyFilters();
                this.renderRecommendations();
                this.updateStats();

                this.showSuccess(`Recommendation ${action}ed successfully`);
            } else {
                throw new Error(result.error || 'Unknown error');
            }

        } catch (error) {
            console.error(`Error ${action}ing recommendation:`, error);
            this.showError(`Failed to ${action} recommendation: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    filterRecommendations() {
        // Update filter values
        this.currentFilters.environment = document.getElementById('environmentFilter').value;
        this.currentFilters.severity = document.getElementById('severityFilter').value;
        this.currentFilters.type = document.getElementById('typeFilter').value;
        this.currentFilters.status = document.getElementById('statusFilter').value;

        this.applyFilters();
        this.renderRecommendations();
        this.updateStats();
    }

    applyFilters() {
        this.filteredRecommendations = this.recommendations.filter(rec => {
            // Environment filter
            if (this.currentFilters.environment && rec.environment !== this.currentFilters.environment) {
                return false;
            }

            // Severity filter
            if (this.currentFilters.severity && rec.severity !== this.currentFilters.severity) {
                return false;
            }

            // Type filter
            if (this.currentFilters.type && rec.type !== this.currentFilters.type) {
                return false;
            }

            // Status filter
            if (this.currentFilters.status) {
                const status = rec.accepted ? 'accepted' : (rec.rejected ? 'rejected' : 'pending');
                if (status !== this.currentFilters.status) {
                    return false;
                }
            }

            return true;
        });
    }

    updateStats() {
        const critical = this.filteredRecommendations.filter(r => r.severity === 'critical').length;
        const high = this.filteredRecommendations.filter(r => r.severity === 'high').length;
        const pending = this.filteredRecommendations.filter(r => !r.accepted && !r.rejected).length;
        const resolved = this.filteredRecommendations.filter(r => r.accepted || r.rejected).length;

        document.getElementById('criticalCount').textContent = critical;
        document.getElementById('highCount').textContent = high;
        document.getElementById('pendingCount').textContent = pending;
        document.getElementById('resolvedCount').textContent = resolved;
    }

    showActionModal(title, message, action) {
        document.getElementById('actionModalTitle').textContent = title;
        document.getElementById('actionModalBody').textContent = message;

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

    getSeverityColor(severity) {
        const colors = {
            'critical': 'danger',
            'high': 'warning',
            'medium': 'info',
            'low': 'success'
        };
        return colors[severity] || 'secondary';
    }

    getTypeIcon(type) {
        const icons = {
            'dictionary': 'bi-book',
            'graph': 'bi-diagram-3',
            'chunk': 'bi-file-text',
            'ocr': 'bi-eye'
        };
        return icons[type] || 'bi-info-circle';
    }

    getStatusBadge(status) {
        const badges = {
            'accepted': '<span class="badge bg-success">Accepted</span>',
            'rejected': '<span class="badge bg-danger">Rejected</span>',
            'pending': '<span class="badge bg-warning text-dark">Pending</span>'
        };
        return badges[status] || '';
    }

    getConfidenceColor(confidence) {
        if (confidence >= 0.8) return '#28a745';
        if (confidence >= 0.6) return '#ffc107';
        return '#dc3545';
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
}

// Global functions for template access
function refreshRecommendations() {
    hgrnManager.loadRecommendations().then(() => {
        hgrnManager.applyFilters();
        hgrnManager.renderRecommendations();
        hgrnManager.updateStats();
    });
}

function filterRecommendations() {
    hgrnManager.filterRecommendations();
}

// Initialize when DOM is loaded
let hgrnManager;
document.addEventListener('DOMContentLoaded', () => {
    hgrnManager = new HGRNRecommendationsManager();
});