/**
 * Export Manager for Wireframe Editor
 *
 * Handles exporting wireframes to various formats including HTML/CSS,
 * images, and future React/Vue components.
 */

class ExportManager {
    constructor(editor) {
        this.editor = editor;
        this.settings = {
            format: 'html_css',
            include_responsive: true,
            include_accessibility: true,
            css_framework: 'bootstrap',
            minify_output: false,
            include_comments: true
        };
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Export modal events
        document.getElementById('previewBtn')?.addEventListener('click', () => this.generatePreview());
        document.getElementById('downloadBtn')?.addEventListener('click', () => this.downloadExport());

        // Export settings events
        const settingsInputs = ['exportFormat', 'cssFramework', 'includeResponsive', 'includeAccessibility', 'includeComments', 'minifyOutput'];
        settingsInputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                input.addEventListener('change', () => this.updateSettings());
            }
        });
    }

    updateSettings() {
        this.settings = {
            format: document.getElementById('exportFormat')?.value || 'html_css',
            css_framework: document.getElementById('cssFramework')?.value || 'bootstrap',
            include_responsive: document.getElementById('includeResponsive')?.checked || false,
            include_accessibility: document.getElementById('includeAccessibility')?.checked || false,
            include_comments: document.getElementById('includeComments')?.checked || false,
            minify_output: document.getElementById('minifyOutput')?.checked || false
        };
    }

    getSettings() {
        return { ...this.settings };
    }

    async generatePreview() {
        try {
            if (!this.editor.currentProject) {
                throw new Error('No project loaded');
            }

            // Show loading state
            const previewBtn = document.getElementById('previewBtn');
            const originalText = previewBtn.textContent;
            previewBtn.textContent = 'Generating...';
            previewBtn.disabled = true;

            // Update settings from form
            this.updateSettings();

            // Generate export data
            const exportData = await this.generateExport();

            // Display preview
            this.displayPreview(exportData);

        } catch (error) {
            console.error('Failed to generate preview:', error);
            this.showError('Failed to generate preview: ' + error.message);
        } finally {
            // Reset button state
            const previewBtn = document.getElementById('previewBtn');
            previewBtn.textContent = 'Generate Preview';
            previewBtn.disabled = false;
        }
    }

    async downloadExport() {
        try {
            if (!this.editor.currentProject) {
                throw new Error('No project loaded');
            }

            // Show loading state
            const downloadBtn = document.getElementById('downloadBtn');
            const originalText = downloadBtn.innerHTML;
            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Generating...';
            downloadBtn.disabled = true;

            // Update settings from form
            this.updateSettings();

            // Send export request to server
            const response = await fetch(`/admin/api/wireframe/projects/${this.editor.currentProject.id}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    export_settings: this.settings
                })
            });

            if (!response.ok) {
                throw new Error('Export request failed');
            }

            const data = await response.json();

            if (data.status === 'success') {
                // Download the export package
                this.downloadFiles(data.export_package);

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('exportModal'));
                modal.hide();

                this.showSuccess('Export downloaded successfully');
            } else {
                throw new Error(data.message || 'Export failed');
            }

        } catch (error) {
            console.error('Failed to download export:', error);
            this.showError('Failed to download export: ' + error.message);
        } finally {
            // Reset button state
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.innerHTML = originalText;
            downloadBtn.disabled = false;
        }
    }

    async generateExport() {
        // Get project data
        const projectData = {
            ...this.editor.currentProject,
            components: this.editor.canvas.getComponents(),
            canvas_settings: this.editor.canvas.getSettings(),
            export_settings: this.settings
        };

        // Generate based on format
        switch (this.settings.format) {
            case 'html_css':
                return this.generateHtmlCss(projectData);
            case 'react':
                return this.generateReact(projectData);
            case 'vue':
                return this.generateVue(projectData);
            default:
                throw new Error(`Unsupported export format: ${this.settings.format}`);
        }
    }

    generateHtmlCss(projectData) {
        const { name, components, canvas_settings, export_settings } = projectData;

        // Generate HTML structure
        const html = this.generateHtml(name, components, canvas_settings, export_settings);

        // Generate CSS styles
        const css = this.generateCss(components, canvas_settings, export_settings);

        return {
            files: {
                [`${this.sanitizeFilename(name)}.html`]: html,
                'wireframe-styles.css': css
            },
            preview: this.formatPreviewHtml(html, css)
        };
    }

    generateHtml(projectName, components, canvasSettings, exportSettings) {
        const theme = canvasSettings.theme || 'admin';
        const includeResponsive = exportSettings.include_responsive;
        const includeAccessibility = exportSettings.include_accessibility;
        const cssFramework = exportSettings.css_framework;

        // Build meta tags
        const metaTags = [];
        if (includeResponsive) {
            metaTags.push('<meta name="viewport" content="width=device-width, initial-scale=1.0">');
        }

        // Build CSS links
        const cssLinks = [];
        if (cssFramework === 'bootstrap') {
            cssLinks.push('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">');
        }
        cssLinks.push('<link href="wireframe-styles.css" rel="stylesheet">');

        // Generate components HTML
        const componentsHtml = this.generateComponentsHtml(components, includeAccessibility);

        // Build complete HTML
        const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    ${metaTags.join('\n    ')}
    <title>${this.escapeHtml(projectName)} - Generated Wireframe</title>
    ${cssLinks.join('\n    ')}
</head>
<body class="wireframe-body ${theme}-theme">
    <div class="wireframe-container" style="width: ${canvasSettings.width}px; height: ${canvasSettings.height}px; position: relative;">
        ${componentsHtml}
    </div>

    ${this.generateJavaScript(components, theme)}
</body>
</html>`;

        return this.settings.minify_output ? this.minifyHtml(html) : html;
    }

    generateComponentsHtml(components, includeAccessibility) {
        return components.map(component =>
            this.generateComponentHtml(component, includeAccessibility)
        ).join('\n        ');
    }

    generateComponentHtml(component, includeAccessibility) {
        const { type, x, y, width, height, z_index, properties = {} } = component;

        // Base positioning style
        const positionStyle = `position: absolute; left: ${x}px; top: ${y}px; width: ${width}px; height: ${height}px; z-index: ${z_index || 1};`;

        // Accessibility attributes
        const ariaAttrs = includeAccessibility ?
            `role="img" aria-label="${this.escapeHtml(properties.label || type)}"` : '';

        // Generate component-specific HTML
        switch (type) {
            case 'lcars_status_light':
                return this.generateStatusLightHtml(component, positionStyle, ariaAttrs);
            case 'lcars_button':
                return this.generateLcarsButtonHtml(component, positionStyle, ariaAttrs);
            case 'lcars_progress_bar':
                return this.generateProgressBarHtml(component, positionStyle, ariaAttrs);
            case 'admin_card':
                return this.generateCardHtml(component, positionStyle, ariaAttrs);
            case 'admin_form':
                return this.generateFormHtml(component, positionStyle, ariaAttrs);
            case 'admin_table':
                return this.generateTableHtml(component, positionStyle, ariaAttrs);
            default:
                return this.generateGenericHtml(component, positionStyle, ariaAttrs);
        }
    }

    generateStatusLightHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const status = properties.status || 'active';
        const color = properties.color || 'green';
        const label = properties.label || 'Status';

        return `<div class="lcars-status-light status-${status} color-${color}" style="${positionStyle}" ${ariaAttrs}>
            <div class="status-indicator"></div>
            <span class="status-label">${this.escapeHtml(label)}</span>
        </div>`;
    }

    generateLcarsButtonHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const text = properties.text || 'Button';
        const variant = properties.variant || 'primary';
        const disabled = properties.disabled ? 'disabled' : '';

        return `<button class="lcars-button lcars-${variant}" style="${positionStyle}" ${disabled} ${ariaAttrs}>
            ${this.escapeHtml(text)}
        </button>`;
    }

    generateProgressBarHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const segments = properties.segments || 10;
        const filled = properties.filled || 6;
        const percentage = segments > 0 ? (filled / segments) * 100 : 0;
        const showPercentage = properties.show_percentage !== false;

        const percentageText = showPercentage ?
            `<span class="percentage-text">${Math.round(percentage)}%</span>` : '';

        return `<div class="lcars-progress-bar" style="${positionStyle}" ${ariaAttrs}>
            <div class="progress-track">
                <div class="progress-fill" style="width: ${percentage}%"></div>
            </div>
            ${percentageText}
        </div>`;
    }

    generateCardHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const title = properties.title || 'Card Title';
        const content = properties.content || 'Card content';
        const hasHeader = properties.has_header !== false;

        const headerHtml = hasHeader ?
            `<div class="card-header">${this.escapeHtml(title)}</div>` : '';

        return `<div class="card" style="${positionStyle}" ${ariaAttrs}>
            ${headerHtml}
            <div class="card-body">${this.escapeHtml(content)}</div>
        </div>`;
    }

    generateFormHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const label = properties.label || 'Input Label';
        const type = properties.type || 'text';
        const placeholder = properties.placeholder || 'Enter value...';
        const required = properties.required ? 'required' : '';

        return `<div class="mb-3" style="${positionStyle}" ${ariaAttrs}>
            <label class="form-label">${this.escapeHtml(label)}</label>
            <input type="${type}" class="form-control" placeholder="${this.escapeHtml(placeholder)}" ${required}>
        </div>`;
    }

    generateTableHtml(component, positionStyle, ariaAttrs) {
        const { properties = {} } = component;
        const headers = properties.headers || ['Column 1', 'Column 2', 'Column 3'];
        const rows = properties.rows || 3;

        const headerHtml = headers.map(h => `<th>${this.escapeHtml(h)}</th>`).join('');
        const rowsHtml = Array.from({ length: rows }, (_, i) => {
            const cells = headers.map((_, j) => `<td>Data ${i+1}-${j+1}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        return `<div style="${positionStyle}" ${ariaAttrs}>
            <table class="table">
                <thead><tr>${headerHtml}</tr></thead>
                <tbody>${rowsHtml}</tbody>
            </table>
        </div>`;
    }

    generateGenericHtml(component, positionStyle, ariaAttrs) {
        const { type } = component;
        return `<div class="wireframe-component component-${type}" style="${positionStyle}" ${ariaAttrs}>
            <span>Component: ${type}</span>
        </div>`;
    }

    generateJavaScript(components, theme) {
        // Only include JavaScript if there are interactive components
        const hasInteractive = components.some(comp =>
            comp.type.includes('button') || comp.type.includes('dropdown')
        );

        if (!hasInteractive) return '';

        return `
    <script>
        // Generated wireframe interactions
        document.addEventListener('DOMContentLoaded', function() {
            // LCARS component interactions
            const statusLights = document.querySelectorAll('.lcars-status-light[data-pulse="true"]');
            statusLights.forEach(light => {
                setInterval(() => {
                    light.style.opacity = light.style.opacity === '0.5' ? '1' : '0.5';
                }, 1000);
            });

            // Button hover effects
            const buttons = document.querySelectorAll('.lcars-button, .btn');
            buttons.forEach(button => {
                button.addEventListener('mouseenter', function() {
                    this.style.transform = 'scale(1.05)';
                });
                button.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                });
            });
        });
    </script>`;
    }

    generateCss(components, canvasSettings, exportSettings) {
        const theme = canvasSettings.theme || 'admin';
        const includeComments = exportSettings.include_comments;

        let css = '';

        // Add header comment
        if (includeComments) {
            css += `/*
 * Generated Wireframe Styles
 * Theme: ${theme}
 * Generated: ${new Date().toISOString()}
 */

`;
        }

        // Base styles
        css += this.getBaseCss();

        // Theme-specific styles
        if (theme === 'lcars') {
            css += this.getLcarsCss();
        } else {
            css += this.getAdminCss();
        }

        // Component-specific styles
        const componentTypes = new Set(components.map(comp => comp.type));
        componentTypes.forEach(type => {
            css += this.getComponentCss(type, theme);
        });

        return this.settings.minify_output ? this.minifyCss(css) : css;
    }

    getBaseCss() {
        return `
/* Base Wireframe Styles */
.wireframe-body {
    margin: 0;
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #f8f9fa;
}

.wireframe-container {
    background-color: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    margin: 0 auto;
    overflow: hidden;
}

`;
    }

    getLcarsCss() {
        return `
/* LCARS Theme */
.lcars-theme {
    background: linear-gradient(135deg, #000011 0%, #001122 100%);
    color: #ff9900;
    font-family: 'Courier New', monospace;
}

.lcars-theme .wireframe-container {
    background: linear-gradient(135deg, #001122 0%, #002244 100%);
    border: 2px solid #ff9900;
    border-radius: 15px;
}

`;
    }

    getAdminCss() {
        return `
/* Admin Theme */
.admin-theme {
    background-color: #f8f9fa;
    color: #212529;
}

.admin-theme .wireframe-container {
    background-color: white;
    border: 1px solid #dee2e6;
}

`;
    }

    getComponentCss(componentType, theme) {
        const cssMap = {
            'lcars_status_light': this.getStatusLightCss(),
            'lcars_button': this.getLcarsButtonCss(),
            'lcars_progress_bar': this.getProgressBarCss(),
            'admin_card': this.getCardCss(),
            'admin_form': this.getFormCss(),
            'admin_table': this.getTableCss()
        };

        return cssMap[componentType] || '';
    }

    getStatusLightCss() {
        return `
/* LCARS Status Light */
.lcars-status-light {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: bold;
}

.lcars-status-light .status-indicator {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 2px solid #ff9900;
}

.lcars-status-light.status-active .status-indicator {
    background-color: #00ff00;
    box-shadow: 0 0 10px #00ff00;
}

`;
    }

    getLcarsButtonCss() {
        return `
/* LCARS Button */
.lcars-button {
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
}

.lcars-button:hover {
    background: linear-gradient(45deg, #ffcc00, #ffff00);
    transform: scale(1.05);
}

`;
    }

    getProgressBarCss() {
        return `
/* LCARS Progress Bar */
.lcars-progress-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: 'Courier New', monospace;
    color: #ff9900;
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

.lcars-progress-bar .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #ff9900, #ffcc00);
    transition: width 0.5s ease;
}

`;
    }

    getCardCss() {
        return `
/* Admin Card */
.card {
    border: 1px solid #dee2e6;
    border-radius: 0.375rem;
    background-color: white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.card-header {
    padding: 0.75rem 1rem;
    background-color: #f8f9fa;
    border-bottom: 1px solid #dee2e6;
    font-weight: 600;
}

.card-body {
    padding: 1rem;
}

`;
    }

    getFormCss() {
        return `
/* Form Controls */
.form-control {
    border: 1px solid #ced4da;
    border-radius: 0.375rem;
    padding: 0.375rem 0.75rem;
}

.form-label {
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.mb-3 {
    margin-bottom: 1rem;
}

`;
    }

    getTableCss() {
        return `
/* Table */
.table {
    width: 100%;
    margin-bottom: 1rem;
    border-collapse: collapse;
}

.table th,
.table td {
    padding: 0.75rem;
    border-bottom: 1px solid #dee2e6;
}

.table th {
    font-weight: 600;
    background-color: #f8f9fa;
}

`;
    }

    // React and Vue generation (placeholder implementations)
    generateReact(projectData) {
        throw new Error('React export not yet implemented');
    }

    generateVue(projectData) {
        throw new Error('Vue export not yet implemented');
    }

    // Preview and download functionality
    displayPreview(exportData) {
        const previewContainer = document.getElementById('exportPreview');
        if (!previewContainer) return;

        if (exportData.preview) {
            previewContainer.innerHTML = this.formatCodePreview(exportData.preview);
        } else {
            // Show file list
            const fileList = Object.keys(exportData.files).map(filename =>
                `<strong>${filename}</strong> (${this.getFileSize(exportData.files[filename])} characters)`
            ).join('<br>');

            previewContainer.innerHTML = `<div class="text-muted">Files to be exported:<br><br>${fileList}</div>`;
        }
    }

    formatCodePreview(html) {
        // Basic syntax highlighting for HTML
        return html
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/(&lt;\/?[^&\s]*&gt;)/g, '<span style="color: #e83e8c;">$1</span>')
            .replace(/(class|id|style)=/g, '<span style="color: #d73e48;">$1</span>=')
            .replace(/="([^"]*)"/g, '="<span style="color: #032f62;">$1</span>"');
    }

    formatPreviewHtml(html, css) {
        const maxLength = 1000;
        const truncatedHtml = html.length > maxLength ?
            html.substring(0, maxLength) + '...\n\n<!-- HTML truncated for preview -->' : html;

        return `${truncatedHtml}\n\n/* CSS styles */\n${css.substring(0, 500)}...`;
    }

    downloadFiles(exportPackage) {
        const { files } = exportPackage;

        if (Object.keys(files).length === 1) {
            // Single file download
            const [filename, content] = Object.entries(files)[0];
            this.downloadFile(filename, content);
        } else {
            // Multiple files - create ZIP
            this.downloadZip(files, exportPackage.project_name || 'wireframe');
        }
    }

    downloadFile(filename, content) {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        URL.revokeObjectURL(url);
    }

    async downloadZip(files, projectName) {
        // For now, download files individually
        // In the future, we could use JSZip or similar to create actual ZIP files
        Object.entries(files).forEach(([filename, content]) => {
            setTimeout(() => this.downloadFile(filename, content), 100);
        });

        this.showInfo(`Downloaded ${Object.keys(files).length} files. Consider using a proper ZIP library for better UX.`);
    }

    // Utility methods
    sanitizeFilename(name) {
        return name.replace(/[^a-zA-Z0-9\-_]/g, '_').toLowerCase();
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    minifyHtml(html) {
        return html
            .replace(/\s+/g, ' ')
            .replace(/>\s+</g, '><')
            .trim();
    }

    minifyCss(css) {
        return css
            .replace(/\/\*.*?\*\//g, '')
            .replace(/\s+/g, ' ')
            .replace(/\s*([{}:;,>+~])\s*/g, '$1')
            .trim();
    }

    getFileSize(content) {
        return new Blob([content]).size;
    }

    // Notification methods
    showSuccess(message) {
        this.editor.showSuccess(message);
    }

    showError(message) {
        this.editor.showError(message);
    }

    showInfo(message) {
        this.editor.showInfo(message);
    }
}

// Export for use in main editor
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExportManager;
} else if (typeof window !== 'undefined') {
    window.ExportManager = ExportManager;
}