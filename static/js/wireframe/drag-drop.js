/**
 * Drag and Drop Engine for Wireframe Editor
 *
 * Handles component dragging from palette to canvas and within canvas.
 * Supports grid snapping, collision detection, and visual feedback.
 */

class DragDropEngine {
    constructor(canvasManager) {
        this.canvas = canvasManager;
        this.isDragging = false;
        this.draggedElement = null;
        this.draggedComponent = null;
        this.dragOffset = { x: 0, y: 0 };
        this.dropZones = [];
        this.ghostElement = null;
        this.snapToGrid = true;
        this.gridSize = 10;

        this.initialize();
    }

    initialize() {
        this.setupPaletteDragHandlers();
        this.setupCanvasDragHandlers();
        this.setupDropZones();

        // Listen for settings changes
        document.addEventListener('gridSettingsChanged', (e) => {
            this.snapToGrid = e.detail.snapToGrid;
            this.gridSize = e.detail.gridSize;
        });
    }

    setupPaletteDragHandlers() {
        const palette = document.querySelector('.component-palette');
        if (!palette) return;

        // Make component items draggable
        palette.addEventListener('dragstart', (e) => {
            const componentItem = e.target.closest('.component-item');
            if (!componentItem) return;

            const componentType = componentItem.dataset.type;

            // Store component data for drop handling
            e.dataTransfer.setData('text/plain', JSON.stringify({
                type: componentType,
                source: 'palette'
            }));

            // Set drag image
            this.setDragImage(e, componentItem);

            // Add visual feedback
            componentItem.classList.add('dragging');
            this.highlightDropZones();
        });

        palette.addEventListener('dragend', (e) => {
            const componentItem = e.target.closest('.component-item');
            if (componentItem) {
                componentItem.classList.remove('dragging');
            }
            this.clearDropZoneHighlights();
        });
    }

    setupCanvasDragHandlers() {
        const canvasContainer = document.getElementById('canvasContainer');
        const componentsLayer = document.getElementById('componentsLayer');

        if (!canvasContainer || !componentsLayer) return;

        // Canvas drop handling
        canvasContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';

            // Show drop position preview
            this.showDropPreview(e);
        });

        canvasContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            this.handleCanvasDrop(e);
            this.hideDropPreview();
        });

        canvasContainer.addEventListener('dragleave', (e) => {
            // Only hide preview if leaving the canvas container
            if (!canvasContainer.contains(e.relatedTarget)) {
                this.hideDropPreview();
            }
        });

        // Component movement within canvas
        componentsLayer.addEventListener('mousedown', (e) => {
            this.handleComponentMouseDown(e);
        });

        document.addEventListener('mousemove', (e) => {
            this.handleMouseMove(e);
        });

        document.addEventListener('mouseup', (e) => {
            this.handleMouseUp(e);
        });
    }

    setupDropZones() {
        this.dropZones = [
            {
                element: document.getElementById('canvasContainer'),
                type: 'canvas',
                accepts: ['all']
            }
        ];
    }

    setDragImage(event, element) {
        // Create a custom drag image
        const dragImage = element.cloneNode(true);
        dragImage.style.position = 'absolute';
        dragImage.style.top = '-1000px';
        dragImage.style.left = '-1000px';
        dragImage.style.opacity = '0.8';
        dragImage.style.transform = 'rotate(2deg)';

        document.body.appendChild(dragImage);

        event.dataTransfer.setDragImage(dragImage, 50, 25);

        // Clean up drag image after drag starts
        setTimeout(() => {
            if (dragImage.parentNode) {
                dragImage.parentNode.removeChild(dragImage);
            }
        }, 0);
    }

    highlightDropZones() {
        this.dropZones.forEach(zone => {
            if (zone.element) {
                zone.element.classList.add('drop-zone-active');
            }
        });
    }

    clearDropZoneHighlights() {
        this.dropZones.forEach(zone => {
            if (zone.element) {
                zone.element.classList.remove('drop-zone-active', 'drop-zone-hover');
            }
        });
    }

    showDropPreview(event) {
        const canvasContainer = document.getElementById('canvasContainer');
        const rect = canvasContainer.getBoundingClientRect();

        let x = event.clientX - rect.left;
        let y = event.clientY - rect.top;

        // Apply grid snapping
        if (this.snapToGrid) {
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
        }

        // Create or update ghost element
        if (!this.ghostElement) {
            this.ghostElement = document.createElement('div');
            this.ghostElement.className = 'drop-preview';
            this.ghostElement.innerHTML = `
                <div class="drop-preview-box">
                    <i class="fas fa-plus"></i>
                    <span>Drop here</span>
                </div>
            `;
            canvasContainer.appendChild(this.ghostElement);
        }

        // Position ghost element
        this.ghostElement.style.left = x + 'px';
        this.ghostElement.style.top = y + 'px';
        this.ghostElement.style.display = 'block';

        // Add hover effect to drop zone
        canvasContainer.classList.add('drop-zone-hover');
    }

    hideDropPreview() {
        if (this.ghostElement) {
            this.ghostElement.style.display = 'none';
        }

        const canvasContainer = document.getElementById('canvasContainer');
        if (canvasContainer) {
            canvasContainer.classList.remove('drop-zone-hover');
        }
    }

    async handleCanvasDrop(event) {
        try {
            const data = JSON.parse(event.dataTransfer.getData('text/plain'));

            if (data.source === 'palette') {
                await this.createComponentFromPalette(event, data.type);
            }
        } catch (error) {
            console.error('Error handling canvas drop:', error);
        }
    }

    async createComponentFromPalette(event, componentType) {
        const canvasContainer = document.getElementById('canvasContainer');
        const rect = canvasContainer.getBoundingClientRect();

        let x = event.clientX - rect.left;
        let y = event.clientY - rect.top;

        // Apply grid snapping
        if (this.snapToGrid) {
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
        }

        // Get default properties for component type
        const defaultProps = this.getDefaultComponentProperties(componentType);

        // Create component data
        const componentData = {
            type: componentType,
            category: this.getComponentCategory(componentType),
            name: defaultProps.name || componentType.replace('_', ' '),
            x: x,
            y: y,
            width: defaultProps.width || 100,
            height: defaultProps.height || 50,
            z_index: this.getNextZIndex(),
            properties: defaultProps.properties || {},
            styles: defaultProps.styles || {}
        };

        // Add component to canvas
        if (this.canvas && this.canvas.addComponent) {
            await this.canvas.addComponent(componentData);
        }

        // Trigger component added event
        this.dispatchEvent('componentAdded', { component: componentData });
    }

    getDefaultComponentProperties(componentType) {
        const defaults = {
            'lcars_status_light': {
                name: 'Status Light',
                width: 30,
                height: 30,
                properties: {
                    status: 'active',
                    color: 'green',
                    pulse: false,
                    label: 'Status'
                }
            },
            'lcars_button': {
                name: 'LCARS Button',
                width: 120,
                height: 40,
                properties: {
                    text: 'Button',
                    variant: 'primary',
                    disabled: false
                }
            },
            'lcars_panel': {
                name: 'LCARS Panel',
                width: 200,
                height: 150,
                properties: {
                    title: 'Panel Title',
                    content: 'Panel content goes here'
                }
            },
            'lcars_progress_bar': {
                name: 'Progress Bar',
                width: 200,
                height: 25,
                properties: {
                    segments: 10,
                    filled: 6,
                    type: 'tier',
                    show_percentage: true
                }
            },
            'lcars_dropdown': {
                name: 'LCARS Dropdown',
                width: 150,
                height: 35,
                properties: {
                    options: ['Option 1', 'Option 2', 'Option 3'],
                    selected: 'Option 1',
                    placeholder: 'Select...'
                }
            },
            'admin_card': {
                name: 'Bootstrap Card',
                width: 300,
                height: 200,
                properties: {
                    title: 'Card Title',
                    content: 'Card content goes here',
                    has_header: true,
                    has_footer: false
                }
            },
            'admin_form': {
                name: 'Form Group',
                width: 250,
                height: 80,
                properties: {
                    label: 'Input Label',
                    type: 'text',
                    placeholder: 'Enter value...',
                    required: false
                }
            },
            'admin_table': {
                name: 'Data Table',
                width: 400,
                height: 250,
                properties: {
                    headers: ['Column 1', 'Column 2', 'Column 3'],
                    rows: 5,
                    striped: true,
                    bordered: false
                }
            },
            'admin_button': {
                name: 'Admin Button',
                width: 100,
                height: 40,
                properties: {
                    text: 'Button',
                    variant: 'primary',
                    size: 'medium'
                }
            },
            'admin_navigation': {
                name: 'Navigation',
                width: 300,
                height: 50,
                properties: {
                    items: ['Home', 'About', 'Contact'],
                    orientation: 'horizontal'
                }
            }
        };

        return defaults[componentType] || {
            name: componentType.replace('_', ' '),
            width: 100,
            height: 50,
            properties: {}
        };
    }

    getComponentCategory(componentType) {
        if (componentType.startsWith('lcars_')) {
            return 'lcars';
        } else if (componentType.startsWith('admin_')) {
            return 'admin';
        }
        return 'custom';
    }

    getNextZIndex() {
        const components = document.querySelectorAll('.wireframe-component');
        let maxZ = 0;

        components.forEach(comp => {
            const z = parseInt(comp.style.zIndex) || 1;
            if (z > maxZ) maxZ = z;
        });

        return maxZ + 1;
    }

    // Component movement within canvas
    handleComponentMouseDown(event) {
        const component = event.target.closest('.wireframe-component');
        if (!component) return;

        // Don't start drag on resize handles
        if (event.target.classList.contains('resize-handle')) return;

        event.preventDefault();

        this.isDragging = true;
        this.draggedElement = component;
        this.draggedComponent = this.canvas.getComponentById(component.dataset.componentId);

        const rect = component.getBoundingClientRect();
        const canvasRect = document.getElementById('canvasContainer').getBoundingClientRect();

        this.dragOffset = {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };

        // Add dragging class
        component.classList.add('dragging');

        // Bring to front temporarily
        component.style.zIndex = 9999;

        // Prevent text selection
        document.body.classList.add('no-select');
    }

    handleMouseMove(event) {
        if (!this.isDragging || !this.draggedElement) return;

        event.preventDefault();

        const canvasContainer = document.getElementById('canvasContainer');
        const canvasRect = canvasContainer.getBoundingClientRect();

        let x = event.clientX - canvasRect.left - this.dragOffset.x;
        let y = event.clientY - canvasRect.top - this.dragOffset.y;

        // Apply grid snapping
        if (this.snapToGrid) {
            x = Math.round(x / this.gridSize) * this.gridSize;
            y = Math.round(y / this.gridSize) * this.gridSize;
        }

        // Constrain to canvas bounds
        const canvasWidth = canvasContainer.scrollWidth;
        const canvasHeight = canvasContainer.scrollHeight;
        const compWidth = parseInt(this.draggedElement.style.width) || 100;
        const compHeight = parseInt(this.draggedElement.style.height) || 50;

        x = Math.max(0, Math.min(x, canvasWidth - compWidth));
        y = Math.max(0, Math.min(y, canvasHeight - compHeight));

        // Update element position
        this.draggedElement.style.left = x + 'px';
        this.draggedElement.style.top = y + 'px';
    }

    async handleMouseUp(event) {
        if (!this.isDragging) return;

        const component = this.draggedElement;
        const componentData = this.draggedComponent;

        if (component && componentData) {
            // Remove dragging class
            component.classList.remove('dragging');

            // Restore z-index
            component.style.zIndex = componentData.z_index || 1;

            // Update component data
            const newX = parseInt(component.style.left) || 0;
            const newY = parseInt(component.style.top) || 0;

            if (newX !== componentData.x || newY !== componentData.y) {
                // Update component position
                await this.canvas.updateComponent(componentData.id, {
                    x: newX,
                    y: newY
                });

                // Trigger component moved event
                this.dispatchEvent('componentMoved', {
                    component: componentData,
                    oldPosition: { x: componentData.x, y: componentData.y },
                    newPosition: { x: newX, y: newY }
                });
            }
        }

        // Reset drag state
        this.isDragging = false;
        this.draggedElement = null;
        this.draggedComponent = null;
        this.dragOffset = { x: 0, y: 0 };

        // Remove no-select class
        document.body.classList.remove('no-select');
    }

    // Touch support for mobile devices
    setupTouchHandlers() {
        const componentsLayer = document.getElementById('componentsLayer');
        if (!componentsLayer) return;

        let touchStartData = null;

        componentsLayer.addEventListener('touchstart', (e) => {
            const component = e.target.closest('.wireframe-component');
            if (!component) return;

            const touch = e.touches[0];
            touchStartData = {
                component: component,
                startX: touch.clientX,
                startY: touch.clientY,
                componentX: parseInt(component.style.left) || 0,
                componentY: parseInt(component.style.top) || 0
            };

            component.classList.add('dragging');
        });

        componentsLayer.addEventListener('touchmove', (e) => {
            if (!touchStartData) return;
            e.preventDefault();

            const touch = e.touches[0];
            const deltaX = touch.clientX - touchStartData.startX;
            const deltaY = touch.clientY - touchStartData.startY;

            let newX = touchStartData.componentX + deltaX;
            let newY = touchStartData.componentY + deltaY;

            // Apply grid snapping
            if (this.snapToGrid) {
                newX = Math.round(newX / this.gridSize) * this.gridSize;
                newY = Math.round(newY / this.gridSize) * this.gridSize;
            }

            touchStartData.component.style.left = newX + 'px';
            touchStartData.component.style.top = newY + 'px';
        });

        componentsLayer.addEventListener('touchend', async (e) => {
            if (!touchStartData) return;

            const component = touchStartData.component;
            component.classList.remove('dragging');

            // Update component data
            const componentId = component.dataset.componentId;
            const newX = parseInt(component.style.left) || 0;
            const newY = parseInt(component.style.top) || 0;

            await this.canvas.updateComponent(componentId, {
                x: newX,
                y: newY
            });

            touchStartData = null;
        });
    }

    // Utility methods
    dispatchEvent(eventName, detail) {
        const event = new CustomEvent(eventName, { detail });
        document.dispatchEvent(event);
    }

    // Collision detection
    checkCollision(element1, element2) {
        const rect1 = element1.getBoundingClientRect();
        const rect2 = element2.getBoundingClientRect();

        return !(rect1.right < rect2.left ||
                rect1.left > rect2.right ||
                rect1.bottom < rect2.top ||
                rect1.top > rect2.bottom);
    }

    // Snap position to grid
    snapToGridPosition(x, y) {
        if (!this.snapToGrid) return { x, y };

        return {
            x: Math.round(x / this.gridSize) * this.gridSize,
            y: Math.round(y / this.gridSize) * this.gridSize
        };
    }
}

// Export for use in main editor
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DragDropEngine;
} else if (typeof window !== 'undefined') {
    window.DragDropEngine = DragDropEngine;
}