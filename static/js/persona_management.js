/**
 * Persona Management Interface
 *
 * Provides admin interface for managing persona testing framework,
 * viewing metrics, and handling alerts.
 */

class PersonaManager {
    constructor() {
        this.baseUrl = '/admin/api/personas';
        this.currentMetrics = null;
        this.currentAlerts = [];
        this.refreshInterval = null;

        this.init();
    }

    init() {
        // Load initial data
        this.loadMetrics();
        this.loadPersonaProfiles();
        this.loadAlerts();
        this.loadTestScenarios();

        // Set up auto-refresh
        this.startAutoRefresh();

        // Set up event listeners
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Tab change events
        const tabElements = document.querySelectorAll('#personaTabs button[data-bs-toggle="tab"]');
        tabElements.forEach(tab => {
            tab.addEventListener('shown.bs.tab', (event) => {
                const target = event.target.getAttribute('data-bs-target');
                this.handleTabChange(target);
            });
        });
    }

    handleTabChange(target) {
        switch (target) {
            case '#metrics':
                this.refreshMetrics();
                break;
            case '#personas':
                this.loadPersonaProfiles();
                break;
            case '#alerts':
                this.loadAlerts();
                break;
            case '#scenarios':
                this.loadTestScenarios();
                break;
        }
    }

    async loadMetrics() {
        try {
            const timePeriod = document.getElementById('timePeriodFilter')?.value || '7';
            const response = await fetch(`${this.baseUrl}/metrics?days_back=${timePeriod}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.currentMetrics = data;
            this.updateMetricsDisplay(data);

        } catch (error) {
            console.error('Error loading metrics:', error);
            this.showError('Failed to load persona metrics');
        }
    }

    updateMetricsDisplay(data) {
        // Update overview cards
        document.getElementById('totalQueries').textContent = data.total_queries || '0';
        document.getElementById('avgAppropriatenesss').textContent =
            data.avg_appropriateness_score ? data.avg_appropriateness_score.toFixed(3) : '0.000';
        document.getElementById('avgSatisfaction').textContent =
            data.avg_satisfaction_score ? data.avg_satisfaction_score.toFixed(3) : '0.000';

        // Update persona breakdown table
        this.updatePersonaMetricsTable(data.persona_breakdown || {});
    }

    updatePersonaMetricsTable(personaBreakdown) {
        const tbody = document.getElementById('personaMetricsBody');
        if (!tbody) return;

        if (Object.keys(personaBreakdown).length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center">No metrics data available</td></tr>';
            return;
        }

        tbody.innerHTML = '';

        Object.entries(personaBreakdown).forEach(([personaId, metrics]) => {
            const row = document.createElement('tr');

            const appropriatenessScore = metrics.avg_appropriateness || 0;
            const satisfactionScore = metrics.avg_satisfaction || 0;
            const hallucinationRate = metrics.hallucination_rate || 0;

            // Determine status based on scores
            let statusBadge = '';
            if (appropriatenessScore >= 0.8 && satisfactionScore >= 0.8) {
                statusBadge = '<span class="badge bg-success">Good</span>';
            } else if (appropriatenessScore >= 0.6 && satisfactionScore >= 0.6) {
                statusBadge = '<span class="badge bg-warning">Needs Attention</span>';
            } else {
                statusBadge = '<span class="badge bg-danger">Issues</span>';
            }

            row.innerHTML = `
                <td>
                    <strong>${this.formatPersonaId(personaId)}</strong>
                </td>
                <td>${metrics.query_count || 0}</td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="progress flex-grow-1 me-2" style="height: 20px;">
                            <div class="progress-bar" role="progressbar"
                                 style="width: ${(appropriatenessScore * 100)}%"
                                 aria-valuenow="${appropriatenessScore}"
                                 aria-valuemin="0" aria-valuemax="1">
                            </div>
                        </div>
                        <small>${appropriatenessScore.toFixed(3)}</small>
                    </div>
                </td>
                <td>
                    <div class="d-flex align-items-center">
                        <div class="progress flex-grow-1 me-2" style="height: 20px;">
                            <div class="progress-bar bg-info" role="progressbar"
                                 style="width: ${(satisfactionScore * 100)}%"
                                 aria-valuenow="${satisfactionScore}"
                                 aria-valuemin="0" aria-valuemax="1">
                            </div>
                        </div>
                        <small>${satisfactionScore.toFixed(3)}</small>
                    </div>
                </td>
                <td>
                    <small class="text-muted">
                        ${metrics.avg_response_time ? `${metrics.avg_response_time.toFixed(0)}ms` : 'N/A'}
                    </small>
                </td>
                <td>${statusBadge}</td>
            `;

            tbody.appendChild(row);
        });
    }

    async loadPersonaProfiles() {
        try {
            const response = await fetch(`${this.baseUrl}/profiles`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.updatePersonaProfilesDisplay(data.personas || []);

        } catch (error) {
            console.error('Error loading persona profiles:', error);
            this.showError('Failed to load persona profiles');
        }
    }

    updatePersonaProfilesDisplay(personas) {
        const container = document.getElementById('personaProfilesContainer');
        if (!container) return;

        if (personas.length === 0) {
            container.innerHTML = '<div class="col-12 text-center"><p>No persona profiles available</p></div>';
            return;
        }

        container.innerHTML = '';

        personas.forEach(persona => {
            const col = document.createElement('div');
            col.className = 'col-md-4 mb-3';

            const experienceColor = this.getExperienceColor(persona.experience_level);
            const typeIcon = this.getPersonaTypeIcon(persona.persona_type);

            col.innerHTML = `
                <div class="card persona-card h-100">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h6 class="mb-0">
                            <i class="${typeIcon} me-2"></i>${persona.name}
                        </h6>
                        <span class="badge ${experienceColor}">${persona.experience_level}</span>
                    </div>
                    <div class="card-body">
                        <p class="card-text text-muted small">
                            ${persona.description || 'No description available'}
                        </p>
                        <div class="row text-center">
                            <div class="col-6">
                                <small class="text-muted">Comfort</small>
                                <div class="fw-bold">${persona.technical_comfort}/10</div>
                            </div>
                            <div class="col-6">
                                <small class="text-muted">Detail</small>
                                <div class="fw-bold">${persona.preferred_detail_level}</div>
                            </div>
                        </div>
                        <div class="mt-2">
                            ${persona.languages.map(lang =>
                                `<span class="badge bg-light text-dark me-1">${lang}</span>`
                            ).join('')}
                        </div>
                    </div>
                    <div class="card-footer">
                        <div class="btn-group w-100">
                            <button class="btn btn-sm btn-outline-primary"
                                    onclick="personaManager.viewPersonaDetails('${persona.id}')">
                                <i class="fas fa-eye"></i> View
                            </button>
                            <button class="btn btn-sm btn-outline-success"
                                    onclick="personaManager.testPersona('${persona.id}')">
                                <i class="fas fa-play"></i> Test
                            </button>
                        </div>
                    </div>
                </div>
            `;

            container.appendChild(col);
        });
    }

    async loadAlerts() {
        try {
            const response = await fetch(`${this.baseUrl}/alerts`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.currentAlerts = data.alerts || [];
            this.updateAlertsDisplay(this.currentAlerts);

            // Update alert count in overview
            document.getElementById('activeAlerts').textContent = this.currentAlerts.length;

        } catch (error) {
            console.error('Error loading alerts:', error);
            this.showError('Failed to load alerts');
        }
    }

    updateAlertsDisplay(alerts) {
        const container = document.getElementById('alertsContainer');
        if (!container) return;

        if (alerts.length === 0) {
            container.innerHTML = '<p class="text-center text-muted">No recent alerts</p>';
            return;
        }

        container.innerHTML = '';

        alerts.forEach(alert => {
            const alertElement = document.createElement('div');
            alertElement.className = `alert ${this.getAlertClass(alert.type)} alert-dismissible fade show`;

            const timestamp = new Date(alert.timestamp).toLocaleString();
            const icon = this.getAlertIcon(alert.type);

            alertElement.innerHTML = `
                <div class="d-flex align-items-start">
                    <i class="${icon} me-2 mt-1"></i>
                    <div class="flex-grow-1">
                        <h6 class="alert-heading mb-1">${this.formatAlertType(alert.type)}</h6>
                        <p class="mb-1">${this.formatAlertMessage(alert)}</p>
                        <small class="text-muted">
                            <i class="fas fa-clock me-1"></i>${timestamp}
                            <span class="mx-2">•</span>
                            <i class="fas fa-user me-1"></i>Persona: ${this.formatPersonaId(alert.persona_id)}
                        </small>
                    </div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;

            container.appendChild(alertElement);
        });
    }

    async loadTestScenarios() {
        try {
            const response = await fetch(`${this.baseUrl}/scenarios`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            this.updateTestScenariosDisplay(data.scenarios || []);

        } catch (error) {
            console.error('Error loading test scenarios:', error);
            this.showError('Failed to load test scenarios');
        }
    }

    updateTestScenariosDisplay(scenarios) {
        const container = document.getElementById('scenariosContainer');
        if (!container) return;

        if (scenarios.length === 0) {
            container.innerHTML = '<p class="text-center text-muted">No test scenarios available</p>';
            return;
        }

        container.innerHTML = '';

        scenarios.forEach(scenario => {
            const scenarioElement = document.createElement('div');
            scenarioElement.className = 'card mb-3';

            const priorityBadge = this.getPriorityBadge(scenario.priority);

            scenarioElement.innerHTML = `
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-0">${scenario.name}</h6>
                        <small class="text-muted">${scenario.persona_profile.name}</small>
                    </div>
                    <div>
                        ${priorityBadge}
                        <button class="btn btn-sm btn-outline-primary ms-2"
                                onclick="personaManager.runScenario('${scenario.id}')">
                            <i class="fas fa-play"></i> Run
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <p class="card-text">${scenario.description}</p>
                    <div class="row">
                        <div class="col-md-8">
                            <strong>Query:</strong>
                            <p class="text-muted small">"${scenario.query}"</p>
                        </div>
                        <div class="col-md-4">
                            <strong>Expected Traits:</strong>
                            <div class="mt-1">
                                ${scenario.expected_response_traits.map(trait =>
                                    `<span class="badge bg-light text-dark me-1">${trait}</span>`
                                ).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            container.appendChild(scenarioElement);
        });
    }

    // Utility Methods
    formatPersonaId(personaId) {
        return personaId.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    getExperienceColor(level) {
        const colors = {
            'beginner': 'bg-info',
            'intermediate': 'bg-warning',
            'advanced': 'bg-success',
            'expert': 'bg-danger'
        };
        return colors[level] || 'bg-secondary';
    }

    getPersonaTypeIcon(type) {
        const icons = {
            'new_user': 'fas fa-user-plus',
            'expert_user': 'fas fa-user-graduate',
            'dungeon_master': 'fas fa-crown',
            'player': 'fas fa-user',
            'mobile_user': 'fas fa-mobile-alt',
            'streaming_host': 'fas fa-video',
            'rules_lawyer': 'fas fa-gavel',
            'world_builder': 'fas fa-globe'
        };
        return icons[type] || 'fas fa-user';
    }

    getAlertClass(type) {
        const classes = {
            'low_appropriateness': 'alert-warning',
            'detail_level_mismatch': 'alert-info',
            'low_satisfaction': 'alert-warning',
            'hallucination_detected': 'alert-danger',
            'inappropriate_content': 'alert-danger'
        };
        return classes[type] || 'alert-secondary';
    }

    getAlertIcon(type) {
        const icons = {
            'low_appropriateness': 'fas fa-exclamation-triangle',
            'detail_level_mismatch': 'fas fa-align-left',
            'low_satisfaction': 'fas fa-frown',
            'hallucination_detected': 'fas fa-eye',
            'inappropriate_content': 'fas fa-ban'
        };
        return icons[type] || 'fas fa-info-circle';
    }

    formatAlertType(type) {
        return type.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    formatAlertMessage(alert) {
        switch (alert.type) {
            case 'low_appropriateness':
                return `Response appropriateness score (${alert.value}) below threshold (${alert.threshold})`;
            case 'detail_level_mismatch':
                return `Detail level mismatch - score: ${alert.value}, threshold: ${alert.threshold}`;
            case 'low_satisfaction':
                return `User satisfaction predicted (${alert.value}) below threshold (${alert.threshold})`;
            case 'hallucination_detected':
                return 'Potential hallucination detected in response';
            case 'inappropriate_content':
                return 'Inappropriate content detected for persona';
            default:
                return alert.message || 'Unknown alert type';
        }
    }

    getPriorityBadge(priority) {
        const badges = {
            1: '<span class="badge bg-light text-dark">Low</span>',
            2: '<span class="badge bg-info">Normal</span>',
            3: '<span class="badge bg-warning">High</span>',
            4: '<span class="badge bg-danger">Critical</span>',
            5: '<span class="badge bg-dark">Urgent</span>'
        };
        return badges[priority] || badges[2];
    }

    // Action Methods
    async refreshMetrics() {
        const button = document.querySelector('button[onclick="refreshMetrics()"]');
        const originalText = button.innerHTML;

        button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
        button.disabled = true;

        try {
            await this.loadMetrics();
        } finally {
            button.innerHTML = originalText;
            button.disabled = false;
        }
    }

    async exportReport() {
        try {
            this.showLoading('Generating report...');

            const response = await fetch(`${this.baseUrl}/export`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `persona-report-${new Date().toISOString().split('T')[0]}.json`;
            a.click();
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error('Error exporting report:', error);
            this.showError('Failed to export report');
        } finally {
            this.hideLoading();
        }
    }

    async clearAlerts() {
        if (!confirm('Are you sure you want to clear all alerts?')) {
            return;
        }

        try {
            const response = await fetch(`${this.baseUrl}/alerts`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            await this.loadAlerts();

        } catch (error) {
            console.error('Error clearing alerts:', error);
            this.showError('Failed to clear alerts');
        }
    }

    async viewPersonaDetails(personaId) {
        try {
            const response = await fetch(`${this.baseUrl}/profiles/${personaId}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            // TODO: Show persona details in modal
            console.log('Persona details:', data);

        } catch (error) {
            console.error('Error loading persona details:', error);
            this.showError('Failed to load persona details');
        }
    }

    async testPersona(personaId) {
        try {
            this.showLoading('Running persona test...');

            const response = await fetch(`${this.baseUrl}/test/${personaId}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            // TODO: Show test results
            console.log('Test results:', data);

        } catch (error) {
            console.error('Error testing persona:', error);
            this.showError('Failed to test persona');
        } finally {
            this.hideLoading();
        }
    }

    async runScenario(scenarioId) {
        try {
            this.showLoading('Running test scenario...');

            const response = await fetch(`${this.baseUrl}/scenarios/${scenarioId}/run`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            // TODO: Show scenario results
            console.log('Scenario results:', data);

        } catch (error) {
            console.error('Error running scenario:', error);
            this.showError('Failed to run scenario');
        } finally {
            this.hideLoading();
        }
    }

    async runTestScenarios() {
        if (!confirm('This will run all test scenarios. Continue?')) {
            return;
        }

        try {
            this.showLoading('Running all test scenarios...');

            const response = await fetch(`${this.baseUrl}/scenarios/run-all`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            // TODO: Show results summary
            console.log('All scenarios results:', data);

        } catch (error) {
            console.error('Error running scenarios:', error);
            this.showError('Failed to run test scenarios');
        } finally {
            this.hideLoading();
        }
    }

    startAutoRefresh() {
        // Refresh metrics every 30 seconds
        this.refreshInterval = setInterval(() => {
            if (document.querySelector('#metrics-tab.active')) {
                this.loadMetrics();
            }
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    showLoading(message = 'Loading...') {
        const modal = document.getElementById('loadingModal');
        const messageElement = modal.querySelector('p');
        messageElement.textContent = message;

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    }

    hideLoading() {
        const modal = document.getElementById('loadingModal');
        const bsModal = bootstrap.Modal.getInstance(modal);
        if (bsModal) {
            bsModal.hide();
        }
    }

    showError(message) {
        // Create a temporary alert
        const alertContainer = document.createElement('div');
        alertContainer.className = 'position-fixed top-0 end-0 p-3';
        alertContainer.style.zIndex = '9999';

        alertContainer.innerHTML = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        document.body.appendChild(alertContainer);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertContainer.parentNode) {
                alertContainer.parentNode.removeChild(alertContainer);
            }
        }, 5000);
    }
}

// Global instance
let personaManager;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    personaManager = new PersonaManager();
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (personaManager) {
        personaManager.stopAutoRefresh();
    }
});

// Global functions for HTML onclick handlers
function refreshMetrics() {
    if (personaManager) {
        personaManager.refreshMetrics();
    }
}

function exportReport() {
    if (personaManager) {
        personaManager.exportReport();
    }
}

function clearAlerts() {
    if (personaManager) {
        personaManager.clearAlerts();
    }
}

function runTestScenarios() {
    if (personaManager) {
        personaManager.runTestScenarios();
    }
}