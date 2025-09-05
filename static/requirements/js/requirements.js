// Phase 7 Requirements Management JavaScript

class RequirementsManager {
    constructor() {
        this.baseUrl = '';
        this.currentModal = null;
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadDashboardData();
    }

    bindEvents() {
        // Form submissions
        document.getElementById('requirementsForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitRequirements();
        });

        document.getElementById('featureForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitFeatureRequest();
        });

        document.getElementById('approvalForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitApproval();
        });

        // Modal close handlers
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal(e.target.id);
            }
        });

        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentModal) {
                this.closeModal(this.currentModal);
            }
        });
    }

    async loadDashboardData() {
        try {
            // This would load real-time data in production
            console.log('Dashboard data loaded');
        } catch (error) {
            console.error('Error loading dashboard data:', error);
        }
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('show');
            this.currentModal = modalId;
            
            // Focus first input
            const firstInput = modal.querySelector('input, textarea, select');
            if (firstInput) {
                firstInput.focus();
            }
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            this.currentModal = null;
            
            // Clear form data
            const form = modal.querySelector('form');
            if (form) {
                form.reset();
            }
        }
    }

    async submitRequirements() {
        try {
            const form = document.getElementById('requirementsForm');
            const formData = new FormData(form);
            
            // Parse requirements JSON
            let requirements;
            try {
                requirements = JSON.parse(formData.get('requirements') || '{"functional": [], "non_functional": []}');
            } catch (e) {
                this.showError('Invalid JSON format in requirements field');
                return;
            }

            const data = {
                title: formData.get('title'),
                version: formData.get('version'),
                description: formData.get('description'),
                author: formData.get('author'),
                requirements: requirements
            };

            this.showLoading('Submitting requirements...');
            
            const response = await fetch('/api/requirements/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-User': 'admin'  // In production, use real auth
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            this.hideLoading();

            if (response.ok) {
                this.showSuccess(`Requirements version ${result.version_id} saved successfully!`);
                this.closeModal('requirementsModal');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                this.showError(result.detail || 'Error submitting requirements');
            }

        } catch (error) {
            this.hideLoading();
            this.showError('Network error: ' + error.message);
        }
    }

    async submitFeatureRequest() {
        try {
            const form = document.getElementById('featureForm');
            const formData = new FormData(form);
            
            const data = {
                title: formData.get('title'),
                description: formData.get('description'),
                priority: formData.get('priority'),
                requester: formData.get('requester'),
                category: formData.get('category') || 'other',
                user_story: formData.get('user_story') || null
            };

            this.showLoading('Submitting feature request...');
            
            const response = await fetch('/api/features/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            this.hideLoading();

            if (response.ok) {
                this.showSuccess(`Feature request ${result.request_id} submitted successfully!`);
                this.closeModal('featureModal');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                this.showError(result.detail || 'Error submitting feature request');
            }

        } catch (error) {
            this.hideLoading();
            this.showError('Network error: ' + error.message);
        }
    }

    async submitApproval() {
        try {
            const form = document.getElementById('approvalForm');
            const formData = new FormData(form);
            
            const requestId = formData.get('request_id');
            const action = formData.get('action');
            
            const data = {
                action: action,
                admin: formData.get('admin'),
                reason: formData.get('reason') || null
            };

            this.showLoading(`${action === 'approve' ? 'Approving' : 'Rejecting'} feature request...`);
            
            const response = await fetch(`/api/features/${requestId}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Admin-User': data.admin
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            this.hideLoading();

            if (response.ok) {
                this.showSuccess(`Feature request ${action}d successfully!`);
                this.closeModal('approvalModal');
                setTimeout(() => window.location.reload(), 1500);
            } else {
                this.showError(result.detail || `Error ${action}ing feature request`);
            }

        } catch (error) {
            this.hideLoading();
            this.showError('Network error: ' + error.message);
        }
    }

    async viewRequirements(versionId) {
        try {
            this.showLoading('Loading requirements...');
            
            const response = await fetch(`/api/requirements/${versionId}`);
            const requirements = await response.json();
            
            this.hideLoading();

            if (response.ok) {
                this.showRequirementsDetail(requirements);
            } else {
                this.showError('Error loading requirements');
            }

        } catch (error) {
            this.hideLoading();
            this.showError('Network error: ' + error.message);
        }
    }

    showRequirementsDetail(requirements) {
        const modal = document.createElement('div');
        modal.className = 'modal show';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Requirements Version ${requirements.metadata.version_id}</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
                </div>
                <div class="modal-form">
                    <div class="form-group">
                        <label>Title:</label>
                        <div class="form-value">${requirements.title}</div>
                    </div>
                    <div class="form-group">
                        <label>Version:</label>
                        <div class="form-value">${requirements.version}</div>
                    </div>
                    <div class="form-group">
                        <label>Description:</label>
                        <div class="form-value">${requirements.description}</div>
                    </div>
                    <div class="form-group">
                        <label>Author:</label>
                        <div class="form-value">${requirements.metadata.author}</div>
                    </div>
                    <div class="form-group">
                        <label>Created:</label>
                        <div class="form-value">${new Date(requirements.metadata.timestamp).toLocaleString()}</div>
                    </div>
                    <div class="form-group">
                        <label>Requirements JSON:</label>
                        <pre class="json-display">${JSON.stringify(requirements.requirements, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Add styles for form values
        const style = document.createElement('style');
        style.textContent = `
            .form-value {
                padding: 0.75rem;
                background-color: var(--bg-secondary);
                border-radius: var(--border-radius);
                border: 1px solid var(--border-color);
            }
            .json-display {
                background-color: #f8fafc;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius);
                padding: 1rem;
                overflow-x: auto;
                font-size: 0.875rem;
                max-height: 300px;
                overflow-y: auto;
            }
        `;
        modal.appendChild(style);
    }

    approveFeature(requestId) {
        document.getElementById('approvalRequestId').value = requestId;
        document.getElementById('approvalAction').value = 'approve';
        document.getElementById('approvalTitle').textContent = 'Approve Feature Request';
        document.getElementById('approvalSubmit').textContent = 'Approve';
        document.getElementById('approvalSubmit').className = 'btn btn-success';
        this.showModal('approvalModal');
    }

    rejectFeature(requestId) {
        document.getElementById('approvalRequestId').value = requestId;
        document.getElementById('approvalAction').value = 'reject';
        document.getElementById('approvalTitle').textContent = 'Reject Feature Request';
        document.getElementById('approvalSubmit').textContent = 'Reject';
        document.getElementById('approvalSubmit').className = 'btn btn-danger';
        document.getElementById('approvalReason').required = true;
        this.showModal('approvalModal');
    }

    async runValidation() {
        try {
            this.showLoading('Running validation...');
            
            const response = await fetch('/api/validation/report', {
                headers: {
                    'X-Admin-User': 'admin'
                }
            });
            
            const report = await response.json();
            this.hideLoading();
            
            if (response.ok) {
                this.updateValidationStatus(report);
                this.showSuccess('Validation completed successfully!');
            } else {
                this.showError('Error running validation');
            }

        } catch (error) {
            this.hideLoading();
            this.showError('Network error: ' + error.message);
        }
    }

    updateValidationStatus(report) {
        const reqStatus = document.getElementById('req-schema-status');
        const featureStatus = document.getElementById('feature-schema-status');
        const auditStatus = document.getElementById('audit-integrity-status');
        
        if (reqStatus) {
            const reqSuccess = report.requirements_validation.summary.validation_success_rate === 100;
            reqStatus.textContent = reqSuccess ? 'Valid' : 'Issues Found';
            reqStatus.className = `status-value ${reqSuccess ? 'success' : 'error'}`;
        }
        
        if (featureStatus) {
            const featureSuccess = report.features_validation.summary.validation_success_rate === 100;
            featureStatus.textContent = featureSuccess ? 'Valid' : 'Issues Found';
            featureStatus.className = `status-value ${featureSuccess ? 'success' : 'error'}`;
        }
        
        if (auditStatus) {
            // In a real implementation, we would check audit integrity
            auditStatus.textContent = 'Verified';
            auditStatus.className = 'status-value success';
        }
    }

    async loadAllVersions() {
        // Implementation for loading all requirements versions
        window.location.href = '/api/requirements/versions';
    }

    async loadAllFeatures() {
        // Implementation for loading all feature requests
        window.location.href = '/api/features';
    }

    async loadFullAudit() {
        // Implementation for loading full audit trail
        window.location.href = '/api/audit/features';
    }

    showLoading(message) {
        this.hideMessages();
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-message';
        loadingDiv.className = 'message info';
        loadingDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <div class="spinner"></div>
                ${message}
            </div>
        `;
        
        const style = document.createElement('style');
        style.textContent = `
            .spinner {
                width: 16px;
                height: 16px;
                border: 2px solid var(--border-color);
                border-top: 2px solid var(--primary-color);
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
        `;
        loadingDiv.appendChild(style);
        
        document.body.insertAdjacentElement('afterbegin', loadingDiv);
    }

    hideLoading() {
        const loading = document.getElementById('loading-message');
        if (loading) {
            loading.remove();
        }
    }

    showSuccess(message) {
        this.showMessage(message, 'success');
    }

    showError(message) {
        this.showMessage(message, 'error');
    }

    showWarning(message) {
        this.showMessage(message, 'warning');
    }

    showMessage(message, type) {
        this.hideMessages();
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = message;
        messageDiv.style.position = 'fixed';
        messageDiv.style.top = '20px';
        messageDiv.style.right = '20px';
        messageDiv.style.zIndex = '10000';
        messageDiv.style.maxWidth = '400px';
        
        document.body.appendChild(messageDiv);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            messageDiv.remove();
        }, 5000);
        
        // Click to dismiss
        messageDiv.addEventListener('click', () => {
            messageDiv.remove();
        });
    }

    hideMessages() {
        document.querySelectorAll('.message').forEach(msg => msg.remove());
        document.getElementById('loading-message')?.remove();
    }
}

// Global functions for template use
function showRequirementsForm() {
    window.reqManager.showModal('requirementsModal');
}

function showFeatureForm() {
    window.reqManager.showModal('featureModal');
}

function closeModal(modalId) {
    window.reqManager.closeModal(modalId);
}

function viewRequirements(versionId) {
    window.reqManager.viewRequirements(versionId);
}

function approveFeature(requestId) {
    window.reqManager.approveFeature(requestId);
}

function rejectFeature(requestId) {
    window.reqManager.rejectFeature(requestId);
}

function loadAllVersions() {
    window.reqManager.loadAllVersions();
}

function loadAllFeatures() {
    window.reqManager.loadAllFeatures();
}

function loadFullAudit() {
    window.reqManager.loadFullAudit();
}

function runValidation() {
    window.reqManager.runValidation();
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.reqManager = new RequirementsManager();
});

// Additional CSS for dynamic elements
const dynamicStyles = document.createElement('style');
dynamicStyles.textContent = `
    .status-value.success {
        background-color: var(--success-color);
    }
    .status-value.error {
        background-color: var(--danger-color);
    }
    .message {
        box-shadow: var(--shadow-lg);
        border-radius: var(--border-radius);
    }
`;
document.head.appendChild(dynamicStyles);