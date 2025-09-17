/**
 * Main Wireframe Editor Controller
 *
 * Orchestrates the overall wireframe editing experience, managing
 * canvas, components, projects, and UI interactions.
 */

class WireframeEditor {
    constructor() {
        this.currentProject = null;
        this.selectedComponent = null;
        this.canvas = null;
        this.dragDrop = null;
        this.lcarsComponents = null;
        this.adminComponents = null;
        this.export = null;
        this.theme = 'admin';
        this.undoStack = [];
        this.redoStack = [];
        this.maxUndoSteps = 50;
        this.websocket = null;

        // Editor state
        this.isInitialized = false;
        this.isLoading = false;
        this.hasUnsavedChanges = false;
    }

    async initialize() {
        try {
            console.log('Initializing Wireframe Editor...');

            // Initialize core components
            await this.initializeCanvas();
            this.initializeDragDrop();
            this.initializeComponentLibraries();
            this.initializeExport();
            this.setupEventListeners();
            this.setupKeyboardShortcuts();

            // Load current project if specified in URL
            const urlParams = new URLSearchParams(window.location.search);
            const projectId = urlParams.get('project');

            if (projectId) {
                await this.loadProject(projectId);
            } else {
                await this.loadProjects();
            }

            // Initialize wireframe collections
            await this.initializeWireframeCollections();

            this.isInitialized = true;
            console.log('Wireframe Editor initialized successfully');

            // Show welcome message for new users
            this.showWelcomeMessage();

        } catch (error) {
            console.error('Failed to initialize Wireframe Editor:', error);
            this.showError('Failed to initialize editor: ' + error.message);
        }
    }

    async initializeCanvas() {
        const { default: CanvasManager } = await import('./canvas.js');
        this.canvas = new CanvasManager(this);
        await this.canvas.initialize();
    }

    initializeDragDrop() {
        this.dragDrop = new DragDropEngine(this.canvas);
    }

    initializeComponentLibraries() {
        this.lcarsComponents = new LCARSComponents(this);
        this.adminComponents = new AdminComponents(this);
    }

    async initializeExport() {
        const { default: ExportManager } = await import('./export.js');
        this.export = new ExportManager(this);
    }

    async initializeWireframeCollections() {
        try {
            const response = await fetch('/admin/api/wireframe/init', {
                method: 'POST'
            });

            if (!response.ok) {
                console.warn('Failed to initialize wireframe collections');
            }
        } catch (error) {
            console.warn('Wireframe collections initialization failed:', error);
        }
    }

    setupEventListeners() {
        // Project management
        document.getElementById('newProjectBtn')?.addEventListener('click', () => this.showNewProjectModal());
        document.getElementById('createProjectBtn')?.addEventListener('click', () => this.createProject());
        document.getElementById('saveBtn')?.addEventListener('click', () => this.saveProject());

        // Toolbar actions
        document.getElementById('undoBtn')?.addEventListener('click', () => this.undo());
        document.getElementById('redoBtn')?.addEventListener('click', () => this.redo());
        document.getElementById('gridToggleBtn')?.addEventListener('click', () => this.toggleGrid());
        document.getElementById('snapToggleBtn')?.addEventListener('click', () => this.toggleSnapToGrid());
        document.getElementById('zoomInBtn')?.addEventListener('click', () => this.zoomIn());
        document.getElementById('zoomOutBtn')?.addEventListener('click', () => this.zoomOut());

        // Theme switching
        document.querySelectorAll('input[name="theme"]').forEach(radio => {
            radio.addEventListener('change', (e) => this.changeTheme(e.target.value));
        });

        // Export
        document.getElementById('exportBtn')?.addEventListener('click', () => this.showExportModal());

        // Component selection
        document.addEventListener('componentSelected', (e) => this.handleComponentSelected(e.detail));
        document.addEventListener('componentAdded', (e) => this.handleComponentAdded(e.detail));
        document.addEventListener('componentMoved', (e) => this.handleComponentMoved(e.detail));

        // Property panel
        this.setupPropertyPanelListeners();

        // Canvas deselection
        document.getElementById('canvasContainer')?.addEventListener('click', (e) => {
            if (e.target.id === 'canvasContainer') {
                this.deselectComponent();
            }
        });

        // Window events
        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return e.returnValue;
            }
        });

        // Auto-save
        setInterval(() => {
            if (this.hasUnsavedChanges && this.currentProject) {
                this.autoSave();
            }
        }, 30000); // Auto-save every 30 seconds
    }

    setupPropertyPanelListeners() {
        // Position and size inputs
        ['propX', 'propY', 'propWidth', 'propHeight', 'propZIndex'].forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('change', () => this.updateSelectedComponentProperty());
            }
        });

        // Rotation slider
        const rotationSlider = document.getElementById('propRotation');
        if (rotationSlider) {
            rotationSlider.addEventListener('input', (e) => {
                document.getElementById('rotationValue').textContent = e.target.value;
                this.updateSelectedComponentProperty();
            });
        }

        // Action buttons
        document.getElementById('duplicateBtn')?.addEventListener('click', () => this.duplicateComponent());
        document.getElementById('deleteBtn')?.addEventListener('click', () => this.deleteComponent());
        document.getElementById('toFrontBtn')?.addEventListener('click', () => this.bringToFront());
        document.getElementById('toBackBtn')?.addEventListener('click', () => this.sendToBack());
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Only handle shortcuts when not typing in inputs
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case 'Delete':
                case 'Backspace':
                    if (this.selectedComponent) {
                        e.preventDefault();
                        this.deleteComponent();
                    }
                    break;

                case 'Escape':
                    this.deselectComponent();
                    break;

                case 'd':
                    if (e.ctrlKey && this.selectedComponent) {
                        e.preventDefault();
                        this.duplicateComponent();
                    }
                    break;

                case 'z':
                    if (e.ctrlKey && !e.shiftKey) {
                        e.preventDefault();
                        this.undo();
                    } else if (e.ctrlKey && e.shiftKey) {
                        e.preventDefault();
                        this.redo();
                    }
                    break;

                case 's':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.saveProject();
                    }
                    break;

                case 'ArrowUp':
                case 'ArrowDown':
                case 'ArrowLeft':
                case 'ArrowRight':
                    if (this.selectedComponent && !e.ctrlKey) {
                        e.preventDefault();
                        this.moveSelectedComponent(e.key, e.shiftKey ? 10 : 1);
                    }
                    break;
            }
        });
    }

    // Project Management
    async loadProjects() {
        try {
            const response = await fetch('/admin/api/wireframe/projects');
            const data = await response.json();

            if (data.status === 'success') {
                this.updateProjectsList(data.projects);
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    updateProjectsList(projects) {
        const projectsList = document.getElementById('projectsList');
        if (!projectsList) return;

        // Clear existing projects (except "New Project" option)
        const items = projectsList.querySelectorAll('li:not(:first-child):not(.dropdown-divider)');
        items.forEach(item => item.remove());

        // Add projects
        projects.forEach(project => {
            const li = document.createElement('li');
            li.innerHTML = `<a class="dropdown-item" href="#" data-project-id="${project.id}">${this.escapeHtml(project.name)}</a>`;

            li.addEventListener('click', (e) => {
                e.preventDefault();
                this.loadProject(project.id);
            });

            projectsList.appendChild(li);
        });
    }

    async loadProject(projectId) {
        try {
            this.isLoading = true;
            this.showLoadingState(true);

            const response = await fetch(`/admin/api/wireframe/projects/${projectId}`);
            const data = await response.json();

            if (data.status === 'success') {
                this.currentProject = data.project;
                this.canvas.loadProject(this.currentProject);
                this.updateUI();
                this.hasUnsavedChanges = false;

                // Update browser URL
                const url = new URL(window.location);
                url.searchParams.set('project', projectId);
                window.history.pushState({}, '', url);

                this.showSuccess(`Loaded project: ${this.currentProject.name}`);
            } else {
                throw new Error(data.message || 'Failed to load project');
            }
        } catch (error) {
            console.error('Failed to load project:', error);
            this.showError('Failed to load project: ' + error.message);
        } finally {
            this.isLoading = false;
            this.showLoadingState(false);
        }
    }

    showNewProjectModal() {
        const modal = new bootstrap.Modal(document.getElementById('newProjectModal'));
        modal.show();

        // Clear form
        document.getElementById('newProjectForm').reset();
    }

    async createProject() {
        try {
            const form = document.getElementById('newProjectForm');
            const formData = new FormData(form);

            const projectData = {
                name: formData.get('projectName'),
                description: formData.get('projectDescription'),
                tags: formData.get('projectTags') ? formData.get('projectTags').split(',').map(t => t.trim()) : []
            };

            const response = await fetch('/admin/api/wireframe/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(projectData)
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.currentProject = data.project;
                this.canvas.loadProject(this.currentProject);
                this.updateUI();
                this.hasUnsavedChanges = false;

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('newProjectModal'));
                modal.hide();

                this.showSuccess(`Created project: ${this.currentProject.name}`);
            } else {
                throw new Error(data.message || 'Failed to create project');
            }
        } catch (error) {
            console.error('Failed to create project:', error);
            this.showError('Failed to create project: ' + error.message);
        }
    }

    async saveProject() {
        if (!this.currentProject) {
            this.showWarning('No project to save');
            return;
        }

        try {
            const projectData = {
                components: this.canvas.getComponents(),
                canvas_settings: this.canvas.getSettings(),
                export_settings: this.export ? this.export.getSettings() : {}
            };

            const response = await fetch(`/admin/api/wireframe/projects/${this.currentProject.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(projectData)
            });

            const data = await response.json();

            if (data.status === 'success') {
                this.hasUnsavedChanges = false;
                this.showSuccess('Project saved successfully');
            } else {
                throw new Error(data.message || 'Failed to save project');
            }
        } catch (error) {
            console.error('Failed to save project:', error);
            this.showError('Failed to save project: ' + error.message);
        }
    }

    async autoSave() {
        if (!this.currentProject || this.isLoading) return;

        try {
            await this.saveProject();
            console.log('Auto-saved project');
        } catch (error) {
            console.warn('Auto-save failed:', error);
        }
    }

    // Component Management
    handleComponentSelected(detail) {
        this.selectedComponent = detail;
        this.updatePropertiesPanel();
    }

    handleComponentAdded(detail) {
        this.addToUndoStack('add_component', detail);
        this.hasUnsavedChanges = true;
    }

    handleComponentMoved(detail) {
        this.addToUndoStack('move_component', detail);
        this.hasUnsavedChanges = true;
    }

    updateSelectedComponentProperty() {
        if (!this.selectedComponent) return;

        const updates = {};
        const inputs = ['propX', 'propY', 'propWidth', 'propHeight', 'propZIndex', 'propRotation'];

        inputs.forEach(id => {
            const input = document.getElementById(id);
            if (input && input.value !== '') {
                const property = id.replace('prop', '').toLowerCase();
                if (property === 'zindex') property = 'z_index';
                updates[property] = parseFloat(input.value) || 0;
            }
        });

        if (Object.keys(updates).length > 0) {
            this.canvas.updateComponent(this.selectedComponent.componentId, updates);
            this.hasUnsavedChanges = true;
        }
    }

    updatePropertiesPanel() {
        const propertiesPanel = document.getElementById('componentProperties');
        const noSelection = document.getElementById('noSelection');

        if (!this.selectedComponent) {
            propertiesPanel.classList.add('d-none');
            noSelection.classList.remove('d-none');
            return;
        }

        noSelection.classList.add('d-none');
        propertiesPanel.classList.remove('d-none');

        // Get component data
        const component = this.canvas.getComponentById(this.selectedComponent.componentId);
        if (!component) return;

        // Update position and size inputs
        document.getElementById('propX').value = component.x || 0;
        document.getElementById('propY').value = component.y || 0;
        document.getElementById('propWidth').value = component.width || 100;
        document.getElementById('propHeight').value = component.height || 50;
        document.getElementById('propZIndex').value = component.z_index || 1;
        document.getElementById('propRotation').value = component.rotation || 0;
        document.getElementById('rotationValue').textContent = component.rotation || 0;

        // Update component-specific properties
        this.updateSpecificProperties(component);
    }

    updateSpecificProperties(component) {
        const container = document.getElementById('specificProperties');
        if (!container) return;

        // Clear existing properties
        container.innerHTML = '';

        // Get property editor based on component type
        const properties = this.getComponentTypeProperties(component.type);

        properties.forEach(prop => {
            const currentValue = component.properties?.[prop.name] || prop.default;
            const input = this.createPropertyInput(prop, currentValue);
            container.appendChild(input);
        });
    }

    getComponentTypeProperties(componentType) {
        // This would return property definitions for each component type
        // For now, return basic properties
        return [
            { name: 'opacity', type: 'range', min: 0, max: 1, step: 0.1, default: 1, label: 'Opacity' }
        ];
    }

    createPropertyInput(prop, currentValue) {
        const div = document.createElement('div');
        div.className = 'mb-2';

        const label = document.createElement('label');
        label.className = 'form-label form-label-sm';
        label.textContent = prop.label;

        let input;
        switch (prop.type) {
            case 'range':
                input = document.createElement('input');
                input.type = 'range';
                input.className = 'form-range';
                input.min = prop.min || 0;
                input.max = prop.max || 100;
                input.step = prop.step || 1;
                input.value = currentValue;
                break;

            case 'select':
                input = document.createElement('select');
                input.className = 'form-select form-select-sm';
                prop.options.forEach(option => {
                    const opt = document.createElement('option');
                    opt.value = option;
                    opt.textContent = option;
                    opt.selected = option === currentValue;
                    input.appendChild(opt);
                });
                break;

            case 'checkbox':
                input = document.createElement('input');
                input.type = 'checkbox';
                input.className = 'form-check-input';
                input.checked = currentValue;
                break;

            default:
                input = document.createElement('input');
                input.type = 'text';
                input.className = 'form-control form-control-sm';
                input.value = currentValue;
        }

        input.addEventListener('change', () => {
            this.updateComponentProperty(prop.name, input.value);
        });

        div.appendChild(label);
        div.appendChild(input);
        return div;
    }

    updateComponentProperty(propertyName, value) {
        if (!this.selectedComponent) return;

        const updates = {
            properties: {
                [propertyName]: value
            }
        };

        this.canvas.updateComponent(this.selectedComponent.componentId, updates);
        this.hasUnsavedChanges = true;
    }

    // Toolbar Actions
    changeTheme(theme) {
        this.theme = theme;
        this.canvas.setTheme(theme);

        // Dispatch theme change event
        const event = new CustomEvent('themeChanged', { detail: { theme } });
        document.dispatchEvent(event);
    }

    toggleGrid() {
        this.canvas.toggleGrid();
        const button = document.getElementById('gridToggleBtn');
        button.classList.toggle('active');
    }

    toggleSnapToGrid() {
        this.canvas.toggleSnapToGrid();
        const button = document.getElementById('snapToggleBtn');
        button.classList.toggle('active');
    }

    zoomIn() {
        this.canvas.zoomIn();
        this.updateZoomDisplay();
    }

    zoomOut() {
        this.canvas.zoomOut();
        this.updateZoomDisplay();
    }

    updateZoomDisplay() {
        const zoomLevel = this.canvas.getZoomLevel();
        document.getElementById('zoomLevel').textContent = Math.round(zoomLevel * 100) + '%';
    }

    // Component Actions
    duplicateComponent() {
        if (!this.selectedComponent) return;

        const component = this.canvas.getComponentById(this.selectedComponent.componentId);
        if (component) {
            const duplicate = {
                ...component,
                x: component.x + 20,
                y: component.y + 20
            };
            this.canvas.addComponent(duplicate);
            this.hasUnsavedChanges = true;
        }
    }

    deleteComponent() {
        if (!this.selectedComponent) return;

        this.canvas.removeComponent(this.selectedComponent.componentId);
        this.deselectComponent();
        this.hasUnsavedChanges = true;
    }

    bringToFront() {
        if (!this.selectedComponent) return;

        const maxZ = this.canvas.getMaxZIndex();
        this.canvas.updateComponent(this.selectedComponent.componentId, { z_index: maxZ + 1 });
        this.updatePropertiesPanel();
        this.hasUnsavedChanges = true;
    }

    sendToBack() {
        if (!this.selectedComponent) return;

        this.canvas.updateComponent(this.selectedComponent.componentId, { z_index: 1 });
        this.updatePropertiesPanel();
        this.hasUnsavedChanges = true;
    }

    moveSelectedComponent(direction, distance) {
        if (!this.selectedComponent) return;

        const component = this.canvas.getComponentById(this.selectedComponent.componentId);
        if (!component) return;

        let { x, y } = component;

        switch (direction) {
            case 'ArrowUp': y -= distance; break;
            case 'ArrowDown': y += distance; break;
            case 'ArrowLeft': x -= distance; break;
            case 'ArrowRight': x += distance; break;
        }

        this.canvas.updateComponent(this.selectedComponent.componentId, { x, y });
        this.updatePropertiesPanel();
        this.hasUnsavedChanges = true;
    }

    deselectComponent() {
        this.selectedComponent = null;
        document.querySelectorAll('.wireframe-component.selected').forEach(comp => {
            comp.classList.remove('selected');
        });
        this.updatePropertiesPanel();
    }

    // Undo/Redo
    addToUndoStack(action, data) {
        this.undoStack.push({ action, data, timestamp: Date.now() });

        if (this.undoStack.length > this.maxUndoSteps) {
            this.undoStack.shift();
        }

        // Clear redo stack when new action is performed
        this.redoStack = [];
    }

    undo() {
        if (this.undoStack.length === 0) return;

        const action = this.undoStack.pop();
        this.redoStack.push(action);

        // Apply undo logic based on action type
        this.applyUndoAction(action);
    }

    redo() {
        if (this.redoStack.length === 0) return;

        const action = this.redoStack.pop();
        this.undoStack.push(action);

        // Apply redo logic based on action type
        this.applyRedoAction(action);
    }

    applyUndoAction(action) {
        switch (action.action) {
            case 'add_component':
                this.canvas.removeComponent(action.data.component.id);
                break;
            case 'move_component':
                this.canvas.updateComponent(
                    action.data.component.id,
                    action.data.oldPosition
                );
                break;
        }
    }

    applyRedoAction(action) {
        switch (action.action) {
            case 'add_component':
                this.canvas.addComponent(action.data.component);
                break;
            case 'move_component':
                this.canvas.updateComponent(
                    action.data.component.id,
                    action.data.newPosition
                );
                break;
        }
    }

    // Export
    showExportModal() {
        if (!this.currentProject) {
            this.showWarning('No project to export');
            return;
        }

        const modal = new bootstrap.Modal(document.getElementById('exportModal'));
        modal.show();
    }

    // UI State Management
    updateUI() {
        if (this.currentProject) {
            document.getElementById('currentProjectName').textContent = this.currentProject.name;
        }
    }

    showLoadingState(loading) {
        const elements = document.querySelectorAll('.loading-indicator');
        elements.forEach(el => {
            el.style.display = loading ? 'block' : 'none';
        });
    }

    showWelcomeMessage() {
        if (!this.currentProject) {
            this.showInfo('Welcome to Wireframe Editor! Create a new project or load an existing one to get started.');
        }
    }

    // Notification Methods
    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'danger');
    }

    showWarning(message) {
        this.showToast(message, 'warning');
    }

    showInfo(message) {
        this.showToast(message, 'info');
    }

    showToast(message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${this.escapeHtml(message)}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    // Utility Methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    generateId() {
        return 'comp_' + Math.random().toString(36).substr(2, 9);
    }
}

// Export for global use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = WireframeEditor;
} else if (typeof window !== 'undefined') {
    window.WireframeEditor = WireframeEditor;
}