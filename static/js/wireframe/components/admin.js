/**
 * Admin Component Library
 *
 * Provides Bootstrap-style admin components for wireframe editor including
 * cards, forms, tables, buttons, and navigation elements.
 */

class AdminComponents {
    constructor(editor) {
        this.editor = editor;
        this.components = new Map();
        this.initialize();
    }

    initialize() {
        this.registerComponents();
        this.setupEventListeners();
    }

    registerComponents() {
        // Register all admin component types
        this.registerComponent('admin_card', this.createCard.bind(this));
        this.registerComponent('admin_form', this.createFormGroup.bind(this));
        this.registerComponent('admin_table', this.createTable.bind(this));
        this.registerComponent('admin_button', this.createButton.bind(this));
        this.registerComponent('admin_navigation', this.createNavigation.bind(this));
        this.registerComponent('admin_dashboard', this.createDashboard.bind(this));
    }

    registerComponent(type, createFunction) {
        this.components.set(type, createFunction);
    }

    createComponent(type, data) {
        const createFunction = this.components.get(type);
        if (!createFunction) {
            console.warn(`Unknown admin component type: ${type}`);
            return this.createGenericComponent(type, data);
        }
        return createFunction(data);
    }

    createCard(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            title = 'Card Title',
            content = 'Card content goes here',
            has_header = true,
            has_footer = false,
            footer_text = 'Card Footer',
            variant = 'default'
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-card';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_card';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Component structure
        const headerHtml = has_header ? `
            <div class="card-header bg-${variant === 'primary' ? 'primary text-white' : 'light'}">
                ${this.escapeHtml(title)}
            </div>
        ` : '';

        const footerHtml = has_footer ? `
            <div class="card-footer bg-light text-muted">
                ${this.escapeHtml(footer_text)}
            </div>
        ` : '';

        element.innerHTML = `
            <div class="card h-100 ${variant !== 'default' ? 'border-' + variant : ''}">
                ${headerHtml}
                <div class="card-body">
                    ${this.escapeHtml(content)}
                </div>
                ${footerHtml}
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    createFormGroup(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            label = 'Input Label',
            type = 'text',
            placeholder = 'Enter value...',
            required = false,
            help_text = '',
            size = 'default'
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-form-group';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_form';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Determine input size class
        const sizeClass = size === 'small' ? 'form-control-sm' :
                          size === 'large' ? 'form-control-lg' : '';

        // Component structure
        element.innerHTML = `
            <div class="mb-3 h-100">
                <label class="form-label ${required ? 'required' : ''}">${this.escapeHtml(label)}</label>
                <input type="${type}"
                       class="form-control ${sizeClass}"
                       placeholder="${this.escapeHtml(placeholder)}"
                       ${required ? 'required' : ''}>
                ${help_text ? `<div class="form-text">${this.escapeHtml(help_text)}</div>` : ''}
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    createTable(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            headers = ['Column 1', 'Column 2', 'Column 3'],
            rows = 3,
            striped = true,
            bordered = false,
            hover = true,
            responsive = true,
            size = 'default'
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-table';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_table';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Build table classes
        const tableClasses = ['table'];
        if (striped) tableClasses.push('table-striped');
        if (bordered) tableClasses.push('table-bordered');
        if (hover) tableClasses.push('table-hover');
        if (size === 'small') tableClasses.push('table-sm');

        // Generate table headers
        const headerHtml = headers.map(header =>
            `<th scope="col">${this.escapeHtml(header)}</th>`
        ).join('');

        // Generate table rows
        const rowsHtml = Array.from({ length: rows }, (_, rowIndex) => {
            const cellsHtml = headers.map((_, colIndex) =>
                `<td>Data ${rowIndex + 1}-${colIndex + 1}</td>`
            ).join('');
            return `<tr>${cellsHtml}</tr>`;
        }).join('');

        // Component structure
        const tableHtml = `
            <table class="${tableClasses.join(' ')}">
                <thead>
                    <tr>${headerHtml}</tr>
                </thead>
                <tbody>
                    ${rowsHtml}
                </tbody>
            </table>
        `;

        element.innerHTML = `
            <div class="h-100 ${responsive ? 'table-responsive' : ''}" style="overflow: auto;">
                ${tableHtml}
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    createButton(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            text = 'Button',
            variant = 'primary',
            size = 'default',
            disabled = false,
            outline = false,
            icon = '',
            block = false
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-button';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_button';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Build button classes
        const buttonClasses = ['btn'];
        buttonClasses.push(outline ? `btn-outline-${variant}` : `btn-${variant}`);

        if (size === 'small') buttonClasses.push('btn-sm');
        if (size === 'large') buttonClasses.push('btn-lg');
        if (block) buttonClasses.push('w-100');

        // Icon HTML
        const iconHtml = icon ? `<i class="fas fa-${icon} me-2"></i>` : '';

        // Component structure
        element.innerHTML = `
            <button type="button"
                    class="${buttonClasses.join(' ')} h-100"
                    ${disabled ? 'disabled' : ''}>
                ${iconHtml}${this.escapeHtml(text)}
            </button>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    createNavigation(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            items = ['Home', 'About', 'Services', 'Contact'],
            orientation = 'horizontal',
            variant = 'pills',
            justified = false,
            active_item = items[0] || 'Home'
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-navigation';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_navigation';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Build nav classes
        const navClasses = ['nav'];
        if (variant === 'tabs') navClasses.push('nav-tabs');
        if (variant === 'pills') navClasses.push('nav-pills');
        if (orientation === 'vertical') navClasses.push('flex-column');
        if (justified) navClasses.push('nav-justified');

        // Generate navigation items
        const itemsHtml = items.map(item => {
            const isActive = item === active_item;
            return `
                <li class="nav-item">
                    <a class="nav-link ${isActive ? 'active' : ''}" href="#">
                        ${this.escapeHtml(item)}
                    </a>
                </li>
            `;
        }).join('');

        // Component structure
        element.innerHTML = `
            <ul class="${navClasses.join(' ')} h-100">
                ${itemsHtml}
            </ul>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    createDashboard(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            title = 'Dashboard',
            widgets = ['Stats', 'Chart', 'Recent Activity'],
            layout = 'grid',
            columns = 3
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-dashboard';
        element.dataset.componentId = id;
        element.dataset.componentType = 'admin_dashboard';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Generate widgets
        const widgetsHtml = widgets.map((widget, index) => {
            const colClass = layout === 'grid' ? `col-md-${12 / columns}` : 'col-12';
            return `
                <div class="${colClass} mb-3">
                    <div class="card">
                        <div class="card-header">
                            <h6 class="mb-0">${this.escapeHtml(widget)}</h6>
                        </div>
                        <div class="card-body">
                            <div class="placeholder-content">
                                <div class="placeholder-chart"></div>
                                <div class="placeholder-text">
                                    <div class="placeholder-line"></div>
                                    <div class="placeholder-line"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Component structure
        element.innerHTML = `
            <div class="dashboard-container h-100">
                <div class="dashboard-header mb-3">
                    <h4>${this.escapeHtml(title)}</h4>
                </div>
                <div class="dashboard-content">
                    <div class="row">
                        ${widgetsHtml}
                    </div>
                </div>
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyDashboardStyles();
        this.makeSelectable(element);
        return element;
    }

    createGenericComponent(type, data) {
        const { id, x, y, width, height, z_index } = data;

        const element = document.createElement('div');
        element.className = 'wireframe-component admin-generic';
        element.dataset.componentId = id;
        element.dataset.componentType = type;

        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        element.innerHTML = `
            <div class="generic-component border rounded p-3 h-100 d-flex align-items-center justify-content-center">
                <div class="text-center text-muted">
                    <i class="fas fa-cube fa-2x mb-2"></i>
                    <div class="component-label">${type.replace('_', ' ')}</div>
                </div>
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    // Styling methods
    applyDashboardStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .admin-dashboard .placeholder-content {
                min-height: 120px;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .admin-dashboard .placeholder-chart {
                height: 60px;
                background: linear-gradient(45deg, #f8f9fa 25%, #e9ecef 25%, #e9ecef 50%, #f8f9fa 50%, #f8f9fa 75%, #e9ecef 75%);
                background-size: 20px 20px;
                border-radius: 4px;
                border: 1px dashed #dee2e6;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #6c757d;
                font-size: 12px;
            }
            .admin-dashboard .placeholder-chart::before {
                content: "Chart Area";
            }
            .admin-dashboard .placeholder-text {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            .admin-dashboard .placeholder-line {
                height: 10px;
                background: #e9ecef;
                border-radius: 2px;
            }
            .admin-dashboard .placeholder-line:nth-child(2) {
                width: 60%;
            }
        `;
        document.head.appendChild(style);
    }

    // Utility methods
    createResizeHandles() {
        return `
            <div class="resize-handles">
                <div class="resize-handle resize-nw" data-direction="nw"></div>
                <div class="resize-handle resize-ne" data-direction="ne"></div>
                <div class="resize-handle resize-sw" data-direction="sw"></div>
                <div class="resize-handle resize-se" data-direction="se"></div>
                <div class="resize-handle resize-n" data-direction="n"></div>
                <div class="resize-handle resize-s" data-direction="s"></div>
                <div class="resize-handle resize-e" data-direction="e"></div>
                <div class="resize-handle resize-w" data-direction="w"></div>
            </div>
        `;
    }

    makeSelectable(element) {
        element.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectComponent(element);
        });
    }

    selectComponent(element) {
        // Remove selection from other components
        document.querySelectorAll('.wireframe-component.selected').forEach(comp => {
            comp.classList.remove('selected');
        });

        // Select this component
        element.classList.add('selected');

        // Trigger selection event
        const event = new CustomEvent('componentSelected', {
            detail: {
                componentId: element.dataset.componentId,
                componentType: element.dataset.componentType,
                element: element
            }
        });
        document.dispatchEvent(event);
    }

    setupEventListeners() {
        // Listen for theme changes
        document.addEventListener('themeChanged', (e) => {
            if (e.detail.theme === 'admin') {
                this.applyAdminTheme();
            }
        });

        // Handle form interactions
        document.addEventListener('click', (e) => {
            if (e.target.matches('.admin-form-group input')) {
                e.stopPropagation();
            }
        });

        // Handle navigation interactions
        document.addEventListener('click', (e) => {
            if (e.target.matches('.admin-navigation .nav-link')) {
                e.preventDefault();
                e.stopPropagation();

                // Update active state
                const navContainer = e.target.closest('.admin-navigation');
                navContainer.querySelectorAll('.nav-link').forEach(link => {
                    link.classList.remove('active');
                });
                e.target.classList.add('active');

                // Trigger property change event
                const event = new CustomEvent('componentPropertyChanged', {
                    detail: {
                        componentId: navContainer.dataset.componentId,
                        property: 'active_item',
                        value: e.target.textContent.trim()
                    }
                });
                document.dispatchEvent(event);
            }
        });
    }

    applyAdminTheme() {
        // Apply global admin theme styles
        const style = document.createElement('style');
        style.id = 'admin-global-theme';
        style.textContent = `
            .wireframe-component.selected {
                outline: 2px solid #007bff !important;
                outline-offset: 2px;
            }
            .resize-handle {
                background: #007bff;
                border: 1px solid #0056b3;
            }
            .resize-handle:hover {
                background: #0056b3;
            }
            .admin-form-group .form-label.required::after {
                content: " *";
                color: #dc3545;
            }
            .placeholder-content {
                background: #f8f9fa;
                border: 1px dashed #dee2e6;
                border-radius: 0.375rem;
            }
        `;

        // Remove existing theme
        const existing = document.getElementById('admin-global-theme');
        if (existing) existing.remove();

        document.head.appendChild(style);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Property editor helpers
    getPropertyEditor(componentType, property, currentValue) {
        const editors = {
            'admin_card': {
                'title': { type: 'text', label: 'Card Title' },
                'content': { type: 'textarea', label: 'Card Content' },
                'has_header': { type: 'checkbox', label: 'Show Header' },
                'has_footer': { type: 'checkbox', label: 'Show Footer' },
                'variant': { type: 'select', label: 'Variant', options: ['default', 'primary', 'secondary', 'success', 'danger', 'warning', 'info'] }
            },
            'admin_form': {
                'label': { type: 'text', label: 'Label Text' },
                'type': { type: 'select', label: 'Input Type', options: ['text', 'email', 'password', 'number', 'tel', 'url'] },
                'placeholder': { type: 'text', label: 'Placeholder' },
                'required': { type: 'checkbox', label: 'Required Field' },
                'size': { type: 'select', label: 'Size', options: ['small', 'default', 'large'] }
            },
            'admin_table': {
                'headers': { type: 'array', label: 'Column Headers' },
                'rows': { type: 'number', label: 'Number of Rows', min: 1, max: 20 },
                'striped': { type: 'checkbox', label: 'Striped Rows' },
                'bordered': { type: 'checkbox', label: 'Bordered' },
                'hover': { type: 'checkbox', label: 'Hover Effect' }
            },
            'admin_button': {
                'text': { type: 'text', label: 'Button Text' },
                'variant': { type: 'select', label: 'Style', options: ['primary', 'secondary', 'success', 'danger', 'warning', 'info', 'light', 'dark'] },
                'size': { type: 'select', label: 'Size', options: ['small', 'default', 'large'] },
                'outline': { type: 'checkbox', label: 'Outline Style' },
                'icon': { type: 'text', label: 'Icon (FontAwesome)' }
            },
            'admin_navigation': {
                'items': { type: 'array', label: 'Navigation Items' },
                'orientation': { type: 'select', label: 'Orientation', options: ['horizontal', 'vertical'] },
                'variant': { type: 'select', label: 'Style', options: ['tabs', 'pills'] },
                'justified': { type: 'checkbox', label: 'Justified' }
            }
        };

        return editors[componentType]?.[property] || { type: 'text', label: property };
    }
}

// Export for use in main editor
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminComponents;
} else if (typeof window !== 'undefined') {
    window.AdminComponents = AdminComponents;
}