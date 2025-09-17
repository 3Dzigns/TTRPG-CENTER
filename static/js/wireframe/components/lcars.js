/**
 * LCARS Component Library
 *
 * Provides LCARS-themed components for wireframe editor including
 * status lights, buttons, panels, progress bars, and dropdowns.
 */

class LCARSComponents {
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
        // Register all LCARS component types
        this.registerComponent('lcars_status_light', this.createStatusLight.bind(this));
        this.registerComponent('lcars_button', this.createButton.bind(this));
        this.registerComponent('lcars_panel', this.createPanel.bind(this));
        this.registerComponent('lcars_progress_bar', this.createProgressBar.bind(this));
        this.registerComponent('lcars_dropdown', this.createDropdown.bind(this));
        this.registerComponent('lcars_text_area', this.createTextArea.bind(this));
    }

    registerComponent(type, createFunction) {
        this.components.set(type, createFunction);
    }

    createComponent(type, data) {
        const createFunction = this.components.get(type);
        if (!createFunction) {
            console.warn(`Unknown LCARS component type: ${type}`);
            return this.createGenericComponent(type, data);
        }
        return createFunction(data);
    }

    createStatusLight(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            status = 'active',
            color = 'green',
            pulse = false,
            label = 'Status'
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-status-light';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_status_light';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Component structure
        element.innerHTML = `
            <div class="status-light-container">
                <div class="status-indicator status-${status} color-${color} ${pulse ? 'pulse' : ''}"
                     data-status="${status}" data-color="${color}"></div>
                <span class="status-label">${this.escapeHtml(label)}</span>
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSStatusLightStyles(element);
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
            disabled = false
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-button-wrapper';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_button';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Component structure
        element.innerHTML = `
            <button class="lcars-button lcars-${variant}" ${disabled ? 'disabled' : ''}>
                ${this.escapeHtml(text)}
            </button>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSButtonStyles(element);
        this.makeSelectable(element);

        return element;
    }

    createPanel(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            title = 'Panel Title',
            content = 'Panel content goes here',
            has_border = true
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-panel';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_panel';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Component structure
        element.innerHTML = `
            <div class="lcars-panel-container ${has_border ? 'bordered' : ''}">
                ${title ? `<div class="panel-header">${this.escapeHtml(title)}</div>` : ''}
                <div class="panel-content">${this.escapeHtml(content)}</div>
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSPanelStyles(element);
        this.makeSelectable(element);

        return element;
    }

    createProgressBar(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            segments = 10,
            filled = 6,
            type = 'tier',
            show_percentage = true,
            label = ''
        } = properties;

        const percentage = segments > 0 ? (filled / segments) * 100 : 0;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-progress-bar';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_progress_bar';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Generate segments
        const segmentsHtml = Array.from({ length: segments }, (_, i) => {
            const isFilled = i < filled;
            return `<div class="progress-segment ${isFilled ? 'filled' : ''}" data-segment="${i}"></div>`;
        }).join('');

        // Component structure
        element.innerHTML = `
            <div class="progress-container progress-${type}">
                ${label ? `<div class="progress-label">${this.escapeHtml(label)}</div>` : ''}
                <div class="progress-track">
                    <div class="progress-segments">${segmentsHtml}</div>
                    <div class="progress-fill" style="width: ${percentage}%"></div>
                </div>
                ${show_percentage ? `<div class="progress-percentage">${Math.round(percentage)}%</div>` : ''}
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSProgressBarStyles(element);
        this.makeSelectable(element);

        return element;
    }

    createDropdown(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            options = ['Option 1', 'Option 2', 'Option 3'],
            selected = options[0] || 'Select...',
            placeholder = 'Select...',
            disabled = false
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-dropdown';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_dropdown';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Generate options
        const optionsHtml = options.map(option =>
            `<div class="dropdown-option" data-value="${this.escapeHtml(option)}">${this.escapeHtml(option)}</div>`
        ).join('');

        // Component structure
        element.innerHTML = `
            <div class="lcars-dropdown-container ${disabled ? 'disabled' : ''}">
                <div class="dropdown-selected" data-selected="${this.escapeHtml(selected)}">
                    <span class="selected-text">${this.escapeHtml(selected)}</span>
                    <i class="dropdown-arrow fas fa-chevron-down"></i>
                </div>
                <div class="dropdown-menu">
                    ${optionsHtml}
                </div>
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSDropdownStyles(element);
        this.makeSelectable(element);
        this.setupDropdownInteraction(element);

        return element;
    }

    createTextArea(data) {
        const {
            id, x, y, width, height, z_index,
            properties = {}, styles = {}
        } = data;

        const {
            text = 'Terminal output...',
            placeholder = 'Enter text...',
            readonly = false,
            monospace = true
        } = properties;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-text-area';
        element.dataset.componentId = id;
        element.dataset.componentType = 'lcars_text_area';

        // Set positioning and size
        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        // Component structure
        element.innerHTML = `
            <div class="lcars-text-area-container">
                <textarea class="lcars-textarea ${monospace ? 'monospace' : ''}"
                         placeholder="${this.escapeHtml(placeholder)}"
                         ${readonly ? 'readonly' : ''}>${this.escapeHtml(text)}</textarea>
            </div>
            ${this.createResizeHandles()}
        `;

        this.applyLCARSTextAreaStyles(element);
        this.makeSelectable(element);

        return element;
    }

    createGenericComponent(type, data) {
        const { id, x, y, width, height, z_index } = data;

        const element = document.createElement('div');
        element.className = 'wireframe-component lcars-generic';
        element.dataset.componentId = id;
        element.dataset.componentType = type;

        element.style.position = 'absolute';
        element.style.left = x + 'px';
        element.style.top = y + 'px';
        element.style.width = width + 'px';
        element.style.height = height + 'px';
        element.style.zIndex = z_index || 1;

        element.innerHTML = `
            <div class="generic-component">
                <div class="component-label">${type}</div>
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeSelectable(element);
        return element;
    }

    // Styling methods
    applyLCARSStatusLightStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-status-light .status-light-container {
                display: flex;
                align-items: center;
                gap: 8px;
                height: 100%;
            }
            .lcars-status-light .status-indicator {
                width: 16px;
                height: 16px;
                border-radius: 50%;
                border: 2px solid #ff9900;
                transition: all 0.3s ease;
                flex-shrink: 0;
            }
            .lcars-status-light .status-indicator.status-active.color-green {
                background-color: #00ff00;
                box-shadow: 0 0 10px #00ff00;
            }
            .lcars-status-light .status-indicator.status-inactive.color-red {
                background-color: #ff0000;
                box-shadow: 0 0 10px #ff0000;
            }
            .lcars-status-light .status-indicator.status-warning.color-yellow {
                background-color: #ffff00;
                box-shadow: 0 0 10px #ffff00;
            }
            .lcars-status-light .status-indicator.pulse {
                animation: pulse 1s infinite;
            }
            .lcars-status-light .status-label {
                color: #ff9900;
                font-size: 12px;
                font-weight: bold;
                font-family: 'Courier New', monospace;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        `;
        document.head.appendChild(style);
    }

    applyLCARSButtonStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-button-wrapper .lcars-button {
                width: 100%;
                height: 100%;
                background: linear-gradient(45deg, #ff9900, #ffcc00);
                border: none;
                border-radius: 20px;
                color: #000;
                font-weight: bold;
                font-family: 'Courier New', monospace;
                cursor: pointer;
                transition: all 0.3s ease;
                text-transform: uppercase;
                letter-spacing: 1px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .lcars-button-wrapper .lcars-button:hover {
                background: linear-gradient(45deg, #ffcc00, #ffff00);
                transform: scale(1.05);
                box-shadow: 0 4px 15px rgba(255, 153, 0, 0.4);
            }
            .lcars-button-wrapper .lcars-button:disabled {
                background: #666;
                color: #999;
                cursor: not-allowed;
                transform: none;
            }
            .lcars-button-wrapper .lcars-button.lcars-secondary {
                background: linear-gradient(45deg, #0099ff, #00ccff);
                color: #000;
            }
            .lcars-button-wrapper .lcars-button.lcars-danger {
                background: linear-gradient(45deg, #ff0000, #ff6666);
                color: #fff;
            }
        `;
        document.head.appendChild(style);
    }

    applyLCARSPanelStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-panel .lcars-panel-container {
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, #001122 0%, #002244 100%);
                color: #ff9900;
                font-family: 'Courier New', monospace;
                display: flex;
                flex-direction: column;
            }
            .lcars-panel .lcars-panel-container.bordered {
                border: 2px solid #ff9900;
                border-radius: 15px;
            }
            .lcars-panel .panel-header {
                background: linear-gradient(90deg, #ff9900, #ffcc00);
                color: #000;
                padding: 8px 15px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                border-radius: 12px 12px 0 0;
            }
            .lcars-panel .panel-content {
                flex: 1;
                padding: 15px;
                overflow: auto;
                font-size: 14px;
                line-height: 1.4;
            }
        `;
        document.head.appendChild(style);
    }

    applyLCARSProgressBarStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-progress-bar .progress-container {
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                gap: 10px;
                font-family: 'Courier New', monospace;
                color: #ff9900;
            }
            .lcars-progress-bar .progress-label {
                font-size: 12px;
                font-weight: bold;
                white-space: nowrap;
            }
            .lcars-progress-bar .progress-track {
                flex: 1;
                height: 20px;
                background: #333;
                border: 2px solid #ff9900;
                border-radius: 10px;
                overflow: hidden;
                position: relative;
            }
            .lcars-progress-bar .progress-segments {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                display: flex;
            }
            .lcars-progress-bar .progress-segment {
                flex: 1;
                border-right: 1px solid #ff9900;
                background: transparent;
            }
            .lcars-progress-bar .progress-segment.filled {
                background: rgba(255, 153, 0, 0.3);
            }
            .lcars-progress-bar .progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #ff9900, #ffcc00);
                transition: width 0.5s ease;
            }
            .lcars-progress-bar .progress-percentage {
                font-size: 12px;
                font-weight: bold;
                white-space: nowrap;
            }
        `;
        document.head.appendChild(style);
    }

    applyLCARSDropdownStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-dropdown .lcars-dropdown-container {
                width: 100%;
                height: 100%;
                position: relative;
                font-family: 'Courier New', monospace;
            }
            .lcars-dropdown .dropdown-selected {
                width: 100%;
                height: 100%;
                background: linear-gradient(135deg, #001122 0%, #002244 100%);
                border: 2px solid #ff9900;
                border-radius: 10px;
                color: #ff9900;
                cursor: pointer;
                display: flex;
                align-items: center;
                padding: 0 15px;
                justify-content: space-between;
            }
            .lcars-dropdown .dropdown-selected:hover {
                border-color: #ffcc00;
                background: linear-gradient(135deg, #002244 0%, #003366 100%);
            }
            .lcars-dropdown .selected-text {
                flex: 1;
                font-weight: bold;
                text-transform: uppercase;
            }
            .lcars-dropdown .dropdown-arrow {
                color: #ff9900;
                transition: transform 0.3s ease;
            }
            .lcars-dropdown .dropdown-menu {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: #001122;
                border: 2px solid #ff9900;
                border-top: none;
                border-radius: 0 0 10px 10px;
                max-height: 200px;
                overflow-y: auto;
                z-index: 1000;
                display: none;
            }
            .lcars-dropdown .dropdown-option {
                padding: 10px 15px;
                color: #ff9900;
                cursor: pointer;
                border-bottom: 1px solid #ff9900;
            }
            .lcars-dropdown .dropdown-option:hover {
                background: #ff9900;
                color: #000;
            }
            .lcars-dropdown .dropdown-option:last-child {
                border-bottom: none;
            }
            .lcars-dropdown.open .dropdown-arrow {
                transform: rotate(180deg);
            }
            .lcars-dropdown.open .dropdown-menu {
                display: block;
            }
        `;
        document.head.appendChild(style);
    }

    applyLCARSTextAreaStyles(element) {
        const style = document.createElement('style');
        style.textContent = `
            .lcars-text-area .lcars-text-area-container {
                width: 100%;
                height: 100%;
                position: relative;
            }
            .lcars-text-area .lcars-textarea {
                width: 100%;
                height: 100%;
                background: #001122;
                border: 2px solid #ff9900;
                border-radius: 10px;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                padding: 15px;
                resize: none;
                outline: none;
                line-height: 1.4;
            }
            .lcars-text-area .lcars-textarea.monospace {
                font-family: 'Courier New', monospace;
            }
            .lcars-text-area .lcars-textarea:focus {
                border-color: #ffcc00;
                box-shadow: 0 0 10px rgba(255, 153, 0, 0.3);
            }
            .lcars-text-area .lcars-textarea::placeholder {
                color: #ff9900;
                opacity: 0.7;
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

    setupDropdownInteraction(element) {
        const selected = element.querySelector('.dropdown-selected');
        const menu = element.querySelector('.dropdown-menu');
        const options = element.querySelectorAll('.dropdown-option');

        selected.addEventListener('click', (e) => {
            e.stopPropagation();
            element.classList.toggle('open');
        });

        options.forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const value = option.dataset.value;
                const text = option.textContent;

                selected.querySelector('.selected-text').textContent = text;
                selected.dataset.selected = value;

                element.classList.remove('open');

                // Trigger change event
                const changeEvent = new CustomEvent('componentPropertyChanged', {
                    detail: {
                        componentId: element.dataset.componentId,
                        property: 'selected',
                        value: value
                    }
                });
                document.dispatchEvent(changeEvent);
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', () => {
            element.classList.remove('open');
        });
    }

    setupEventListeners() {
        // Listen for theme changes
        document.addEventListener('themeChanged', (e) => {
            if (e.detail.theme === 'lcars') {
                this.applyLCARSTheme();
            }
        });
    }

    applyLCARSTheme() {
        // Apply global LCARS theme styles
        const style = document.createElement('style');
        style.id = 'lcars-global-theme';
        style.textContent = `
            .wireframe-component.selected {
                outline: 2px solid #ffcc00 !important;
                outline-offset: 2px;
            }
            .resize-handle {
                background: #ff9900;
                border: 1px solid #ffcc00;
            }
            .resize-handle:hover {
                background: #ffcc00;
            }
        `;

        // Remove existing theme
        const existing = document.getElementById('lcars-global-theme');
        if (existing) existing.remove();

        document.head.appendChild(style);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export for use in main editor
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LCARSComponents;
} else if (typeof window !== 'undefined') {
    window.LCARSComponents = LCARSComponents;
}