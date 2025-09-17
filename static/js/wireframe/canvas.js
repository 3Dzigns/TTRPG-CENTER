/**
 * Canvas Manager for Wireframe Editor
 *
 * Manages the HTML5 canvas, component rendering, zoom/pan functionality,
 * and overall canvas state management.
 */

class CanvasManager {
    constructor(editor) {
        this.editor = editor;
        this.canvas = null;
        this.ctx = null;
        this.components = new Map();
        this.settings = {
            width: 1200,
            height: 800,
            grid_size: 10,
            grid_enabled: true,
            snap_to_grid: true,
            zoom_level: 1.0,
            background_color: '#ffffff',
            grid_color: '#e0e0e0',
            theme: 'admin'
        };
        this.isDirty = false;
        this.animationFrame = null;
    }

    async initialize() {
        try {
            this.canvas = document.getElementById('wireframeCanvas');
            this.componentsLayer = document.getElementById('componentsLayer');
            this.canvasContainer = document.getElementById('canvasContainer');

            if (!this.canvas || !this.componentsLayer || !this.canvasContainer) {
                throw new Error('Required canvas elements not found');
            }

            this.ctx = this.canvas.getContext('2d');
            this.setupCanvas();
            this.setupEventListeners();
            this.startRenderLoop();

            console.log('Canvas Manager initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Canvas Manager:', error);
            throw error;
        }
    }

    setupCanvas() {
        // Set canvas size
        this.updateCanvasSize();

        // Set up container
        this.canvasContainer.style.width = this.settings.width + 'px';
        this.canvasContainer.style.height = this.settings.height + 'px';

        // Apply initial grid
        this.updateGrid();

        // Apply initial theme
        this.applyTheme();
    }

    updateCanvasSize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvasContainer.getBoundingClientRect();

        // Set actual canvas size
        this.canvas.width = this.settings.width * dpr;
        this.canvas.height = this.settings.height * dpr;

        // Set display size
        this.canvas.style.width = this.settings.width + 'px';
        this.canvas.style.height = this.settings.height + 'px';

        // Scale context for high DPI displays
        this.ctx.scale(dpr, dpr);

        this.markDirty();
    }

    setupEventListeners() {
        // Handle canvas container resize
        const resizeObserver = new ResizeObserver(() => {
            this.updateCanvasSize();
        });
        resizeObserver.observe(this.canvasContainer);

        // Handle wheel events for zoom
        this.canvasContainer.addEventListener('wheel', (e) => {
            if (e.ctrlKey) {
                e.preventDefault();
                this.handleZoom(e);
            }
        });
    }

    startRenderLoop() {
        const render = () => {
            if (this.isDirty) {
                this.render();
                this.isDirty = false;
            }
            this.animationFrame = requestAnimationFrame(render);
        };
        render();
    }

    render() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.settings.width, this.settings.height);

        // Draw background
        this.drawBackground();

        // Draw grid if enabled
        if (this.settings.grid_enabled) {
            this.drawGrid();
        }

        // Draw guidelines and helpers
        this.drawHelpers();
    }

    drawBackground() {
        this.ctx.fillStyle = this.settings.background_color;
        this.ctx.fillRect(0, 0, this.settings.width, this.settings.height);
    }

    drawGrid() {
        const gridSize = this.settings.grid_size;
        const width = this.settings.width;
        const height = this.settings.height;

        this.ctx.strokeStyle = this.settings.grid_color;
        this.ctx.lineWidth = 0.5;
        this.ctx.setLineDash([]);

        this.ctx.beginPath();

        // Vertical lines
        for (let x = 0; x <= width; x += gridSize) {
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, height);
        }

        // Horizontal lines
        for (let y = 0; y <= height; y += gridSize) {
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(width, y);
        }

        this.ctx.stroke();
    }

    drawHelpers() {
        // Draw alignment guides when dragging
        if (this.editor.dragDrop && this.editor.dragDrop.isDragging) {
            this.drawAlignmentGuides();
        }

        // Draw selection bounds
        if (this.editor.selectedComponent) {
            this.drawSelectionBounds();
        }
    }

    drawAlignmentGuides() {
        // This would draw alignment guides for snapping
        // Implementation depends on drag-drop requirements
    }

    drawSelectionBounds() {
        // Selection bounds are handled by CSS, but we could draw
        // additional canvas-based selection indicators here
    }

    // Component Management
    loadProject(project) {
        try {
            // Clear existing components
            this.clearComponents();

            // Update canvas settings
            if (project.canvas_settings) {
                this.updateSettings(project.canvas_settings);
            }

            // Load components
            if (project.components && Array.isArray(project.components)) {
                project.components.forEach(componentData => {
                    this.addComponent(componentData);
                });
            }

            this.markDirty();
            console.log(`Loaded project with ${project.components?.length || 0} components`);
        } catch (error) {
            console.error('Failed to load project:', error);
            throw error;
        }
    }

    async addComponent(componentData) {
        try {
            // Generate ID if not provided
            if (!componentData.id) {
                componentData.id = this.generateComponentId();
            }

            // Create component element based on type
            const element = this.createComponentElement(componentData);
            if (!element) {
                throw new Error(`Failed to create component of type: ${componentData.type}`);
            }

            // Add to components layer
            this.componentsLayer.appendChild(element);

            // Store component data
            this.components.set(componentData.id, {
                ...componentData,
                element: element
            });

            // Update positions and styling
            this.updateComponentElement(componentData.id, componentData);

            this.markDirty();
            return componentData.id;

        } catch (error) {
            console.error('Failed to add component:', error);
            throw error;
        }
    }

    createComponentElement(componentData) {
        const { type, category } = componentData;

        // Use appropriate component library based on category
        if (category === 'lcars' && this.editor.lcarsComponents) {
            return this.editor.lcarsComponents.createComponent(type, componentData);
        } else if (category === 'admin' && this.editor.adminComponents) {
            return this.editor.adminComponents.createComponent(type, componentData);
        }

        // Fallback to generic component
        return this.createGenericComponent(componentData);
    }

    createGenericComponent(componentData) {
        const { id, x, y, width, height, z_index, type } = componentData;

        const element = document.createElement('div');
        element.className = 'wireframe-component generic-component';
        element.dataset.componentId = id;
        element.dataset.componentType = type;

        element.innerHTML = `
            <div class="generic-content">
                <span>${type}</span>
            </div>
            ${this.createResizeHandles()}
        `;

        this.makeComponentSelectable(element);
        return element;
    }

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

    makeComponentSelectable(element) {
        element.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectComponent(element);
        });
    }

    selectComponent(element) {
        // Remove selection from other components
        this.componentsLayer.querySelectorAll('.wireframe-component.selected').forEach(comp => {
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

    updateComponent(componentId, updates) {
        const component = this.components.get(componentId);
        if (!component) {
            console.warn(`Component ${componentId} not found`);
            return;
        }

        // Update component data
        Object.assign(component, updates);

        // Update component element
        this.updateComponentElement(componentId, updates);

        this.markDirty();
    }

    updateComponentElement(componentId, updates) {
        const component = this.components.get(componentId);
        if (!component || !component.element) return;

        const element = component.element;

        // Update position and size
        if ('x' in updates) element.style.left = updates.x + 'px';
        if ('y' in updates) element.style.top = updates.y + 'px';
        if ('width' in updates) element.style.width = updates.width + 'px';
        if ('height' in updates) element.style.height = updates.height + 'px';
        if ('z_index' in updates) element.style.zIndex = updates.z_index;
        if ('rotation' in updates) element.style.transform = `rotate(${updates.rotation}deg)`;

        // Update component-specific properties
        if ('properties' in updates) {
            this.updateComponentProperties(element, updates.properties);
        }

        // Update styling
        if ('styles' in updates) {
            this.updateComponentStyles(element, updates.styles);
        }
    }

    updateComponentProperties(element, properties) {
        // Update component-specific properties based on type
        const componentType = element.dataset.componentType;

        // This would delegate to the appropriate component library
        // for property updates
    }

    updateComponentStyles(element, styles) {
        // Apply custom styles to component
        Object.entries(styles).forEach(([property, value]) => {
            element.style.setProperty(property, value);
        });
    }

    removeComponent(componentId) {
        const component = this.components.get(componentId);
        if (!component) {
            console.warn(`Component ${componentId} not found`);
            return;
        }

        // Remove element from DOM
        if (component.element && component.element.parentNode) {
            component.element.parentNode.removeChild(component.element);
        }

        // Remove from components map
        this.components.delete(componentId);

        this.markDirty();
    }

    clearComponents() {
        // Remove all component elements
        this.componentsLayer.innerHTML = '';

        // Clear components map
        this.components.clear();

        this.markDirty();
    }

    // Component Queries
    getComponents() {
        return Array.from(this.components.values()).map(comp => {
            const { element, ...data } = comp;
            return data;
        });
    }

    getComponentById(componentId) {
        const component = this.components.get(componentId);
        if (!component) return null;

        const { element, ...data } = component;
        return data;
    }

    getMaxZIndex() {
        let maxZ = 0;
        this.components.forEach(comp => {
            const z = comp.z_index || 1;
            if (z > maxZ) maxZ = z;
        });
        return maxZ;
    }

    // Settings Management
    updateSettings(newSettings) {
        Object.assign(this.settings, newSettings);

        // Apply settings changes
        if ('width' in newSettings || 'height' in newSettings) {
            this.updateCanvasSize();
        }

        if ('grid_enabled' in newSettings || 'grid_size' in newSettings || 'grid_color' in newSettings) {
            this.updateGrid();
        }

        if ('theme' in newSettings) {
            this.applyTheme();
        }

        this.markDirty();
    }

    getSettings() {
        return { ...this.settings };
    }

    updateGrid() {
        if (this.settings.grid_enabled) {
            this.canvasContainer.classList.add('grid-enabled');
            this.canvasContainer.style.backgroundSize = `${this.settings.grid_size}px ${this.settings.grid_size}px`;
        } else {
            this.canvasContainer.classList.remove('grid-enabled');
        }
        this.markDirty();
    }

    applyTheme() {
        // Remove existing theme classes
        this.canvasContainer.classList.remove('admin-theme', 'lcars-theme');

        // Apply new theme
        this.canvasContainer.classList.add(this.settings.theme + '-theme');

        // Update canvas colors based on theme
        if (this.settings.theme === 'lcars') {
            this.settings.background_color = '#001122';
            this.settings.grid_color = 'rgba(255, 153, 0, 0.3)';
        } else {
            this.settings.background_color = '#ffffff';
            this.settings.grid_color = '#e0e0e0';
        }

        this.markDirty();
    }

    // Zoom and Pan
    handleZoom(event) {
        const delta = event.deltaY > 0 ? -0.1 : 0.1;
        const newZoom = Math.max(0.1, Math.min(3.0, this.settings.zoom_level + delta));

        this.setZoom(newZoom);
    }

    setZoom(zoomLevel) {
        this.settings.zoom_level = zoomLevel;

        // Apply zoom transform
        this.componentsLayer.style.transform = `scale(${zoomLevel})`;
        this.componentsLayer.style.transformOrigin = '0 0';

        // Update canvas container size to maintain scrolling
        const scaledWidth = this.settings.width * zoomLevel;
        const scaledHeight = this.settings.height * zoomLevel;
        this.canvasContainer.style.width = scaledWidth + 'px';
        this.canvasContainer.style.height = scaledHeight + 'px';

        this.markDirty();

        // Dispatch zoom change event
        const event = new CustomEvent('zoomChanged', {
            detail: { zoomLevel }
        });
        document.dispatchEvent(event);
    }

    zoomIn() {
        this.setZoom(Math.min(3.0, this.settings.zoom_level + 0.2));
    }

    zoomOut() {
        this.setZoom(Math.max(0.1, this.settings.zoom_level - 0.2));
    }

    getZoomLevel() {
        return this.settings.zoom_level;
    }

    // Grid and Snap
    toggleGrid() {
        this.updateSettings({ grid_enabled: !this.settings.grid_enabled });
    }

    toggleSnapToGrid() {
        this.updateSettings({ snap_to_grid: !this.settings.snap_to_grid });

        // Notify drag-drop engine
        const event = new CustomEvent('gridSettingsChanged', {
            detail: {
                snapToGrid: this.settings.snap_to_grid,
                gridSize: this.settings.grid_size
            }
        });
        document.dispatchEvent(event);
    }

    snapToGrid(x, y) {
        if (!this.settings.snap_to_grid) {
            return { x, y };
        }

        const gridSize = this.settings.grid_size;
        return {
            x: Math.round(x / gridSize) * gridSize,
            y: Math.round(y / gridSize) * gridSize
        };
    }

    // Theme Management
    setTheme(theme) {
        this.updateSettings({ theme });

        // Dispatch theme change event
        const event = new CustomEvent('themeChanged', {
            detail: { theme }
        });
        document.dispatchEvent(event);
    }

    // Export Functionality
    exportAsImage(format = 'png') {
        // Create a temporary canvas for export
        const exportCanvas = document.createElement('canvas');
        const exportCtx = exportCanvas.getContext('2d');

        exportCanvas.width = this.settings.width;
        exportCanvas.height = this.settings.height;

        // Draw background
        exportCtx.fillStyle = this.settings.background_color;
        exportCtx.fillRect(0, 0, this.settings.width, this.settings.height);

        // Draw grid if enabled
        if (this.settings.grid_enabled) {
            this.drawGridOnContext(exportCtx);
        }

        // Draw components (this would need to render components to canvas)
        // For now, we'll use html2canvas or similar for component rendering

        return exportCanvas.toDataURL(`image/${format}`);
    }

    drawGridOnContext(ctx) {
        const gridSize = this.settings.grid_size;
        const width = this.settings.width;
        const height = this.settings.height;

        ctx.strokeStyle = this.settings.grid_color;
        ctx.lineWidth = 1;

        ctx.beginPath();

        for (let x = 0; x <= width; x += gridSize) {
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
        }

        for (let y = 0; y <= height; y += gridSize) {
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
        }

        ctx.stroke();
    }

    // Utility Methods
    markDirty() {
        this.isDirty = true;
    }

    generateComponentId() {
        return 'comp_' + Math.random().toString(36).substr(2, 9);
    }

    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }
}

// Export for use in main editor
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CanvasManager;
} else if (typeof window !== 'undefined') {
    window.CanvasManager = CanvasManager;
}