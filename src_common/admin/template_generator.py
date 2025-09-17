"""
Template Generator for Wireframe Export

Generates clean HTML/CSS template stubs from wireframe projects.
Supports both LCARS and admin component styling.
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from jinja2 import Template, Environment, BaseLoader

from ..ttrpg_logging import get_logger
from .wireframe_models import WireframeProject, WireframeComponent, ComponentType

logger = get_logger(__name__)


class TemplateGenerator:
    """Service for generating HTML/CSS templates from wireframes."""

    def __init__(self):
        """Initialize template generator."""
        self.jinja_env = Environment(loader=BaseLoader())

    def generate_html_css(self, project: Dict[str, Any]) -> Dict[str, str]:
        """Generate HTML and CSS from wireframe project."""
        try:
            # Parse project data
            project_name = project.get("name", "Wireframe")
            components = project.get("components", [])
            canvas_settings = project.get("canvas_settings", {})
            export_settings = project.get("export_settings", {})

            # Generate HTML
            html_content = self._generate_html(
                project_name,
                components,
                canvas_settings,
                export_settings
            )

            # Generate CSS
            css_content = self._generate_css(
                components,
                canvas_settings,
                export_settings
            )

            logger.info(f"Generated templates for project: {project_name}")
            return {
                "html": html_content,
                "css": css_content,
                "filename_base": self._sanitize_filename(project_name)
            }

        except Exception as e:
            logger.error(f"Failed to generate templates: {str(e)}")
            raise

    def _generate_html(self, project_name: str, components: List[Dict], canvas_settings: Dict, export_settings: Dict) -> str:
        """Generate HTML structure."""
        # Determine theme
        theme = canvas_settings.get("theme", "admin")
        include_responsive = export_settings.get("include_responsive", True)
        include_accessibility = export_settings.get("include_accessibility", True)
        css_framework = export_settings.get("css_framework", "bootstrap")

        # Build viewport and meta tags
        meta_tags = []
        if include_responsive:
            meta_tags.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')

        # Build CSS links
        css_links = []
        if css_framework == "bootstrap":
            css_links.append('<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">')

        css_links.append('<link href="wireframe-styles.css" rel="stylesheet">')

        # Generate component HTML
        components_html = self._generate_components_html(components, include_accessibility)

        # Build complete HTML
        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    {meta_tags}
    <title>{project_name} - Generated Wireframe</title>
    {css_links}
</head>
<body class="wireframe-body {theme}-theme">
    <div class="wireframe-container" style="width: {canvas_width}px; height: {canvas_height}px; position: relative;">
        {components_html}
    </div>

    {javascript}
</body>
</html>"""

        # JavaScript for interactive components
        javascript = ""
        if any(comp.get("type", "").startswith("lcars_") for comp in components):
            javascript = """
    <script>
        // LCARS Component Interactions
        document.addEventListener('DOMContentLoaded', function() {
            // Status light pulse animations
            const statusLights = document.querySelectorAll('.lcars-status-light[data-pulse="true"]');
            statusLights.forEach(light => {
                setInterval(() => {
                    light.style.opacity = light.style.opacity === '0.5' ? '1' : '0.5';
                }, 1000);
            });

            // Button hover effects
            const buttons = document.querySelectorAll('.lcars-button');
            buttons.forEach(button => {
                button.addEventListener('mouseenter', function() {
                    this.style.transform = 'scale(1.05)';
                });
                button.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                });
            });
        });
    </script>"""

        return html_template.format(
            meta_tags="\n    ".join(meta_tags),
            project_name=project_name,
            css_links="\n    ".join(css_links),
            theme=theme,
            canvas_width=canvas_settings.get("width", 1200),
            canvas_height=canvas_settings.get("height", 800),
            components_html=components_html,
            javascript=javascript
        )

    def _generate_components_html(self, components: List[Dict], include_accessibility: bool) -> str:
        """Generate HTML for all components."""
        html_parts = []

        for component in components:
            component_html = self._generate_component_html(component, include_accessibility)
            if component_html:
                html_parts.append(component_html)

        return "\n        ".join(html_parts)

    def _generate_component_html(self, component: Dict, include_accessibility: bool) -> str:
        """Generate HTML for individual component."""
        comp_type = component.get("type", "")
        comp_id = component.get("id", "")
        properties = component.get("properties", {})
        x = component.get("x", 0)
        y = component.get("y", 0)
        width = component.get("width", 100)
        height = component.get("height", 50)
        z_index = component.get("z_index", 1)

        # Base positioning style
        position_style = f"position: absolute; left: {x}px; top: {y}px; width: {width}px; height: {height}px; z-index: {z_index};"

        # Accessibility attributes
        aria_attrs = ""
        if include_accessibility:
            aria_attrs = f'role="img" aria-label="{properties.get("label", comp_type)}"'

        # Generate component-specific HTML
        if comp_type == ComponentType.LCARS_STATUS_LIGHT:
            status = properties.get("status", "active")
            color = properties.get("color", "green")
            pulse = properties.get("pulse", False)
            label = properties.get("label", "Status")

            return f'''<div class="lcars-status-light status-{status} color-{color}" data-pulse="{str(pulse).lower()}" style="{position_style}" {aria_attrs}>
            <div class="status-indicator"></div>
            <span class="status-label">{label}</span>
        </div>'''

        elif comp_type == ComponentType.LCARS_BUTTON:
            text = properties.get("text", "Button")
            variant = properties.get("variant", "primary")
            disabled = "disabled" if properties.get("disabled", False) else ""

            return f'''<button class="lcars-button lcars-{variant}" style="{position_style}" {disabled} {aria_attrs}>
            {text}
        </button>'''

        elif comp_type == ComponentType.LCARS_PROGRESS_BAR:
            segments = properties.get("segments", 10)
            filled = properties.get("filled", 6)
            bar_type = properties.get("type", "tier")
            show_percentage = properties.get("show_percentage", True)
            percentage = (filled / segments) * 100 if segments > 0 else 0

            percentage_text = f'<span class="percentage-text">{percentage:.0f}%</span>' if show_percentage else ""

            return f'''<div class="lcars-progress-bar progress-{bar_type}" style="{position_style}" {aria_attrs}>
            <div class="progress-track">
                <div class="progress-fill" style="width: {percentage}%"></div>
            </div>
            {percentage_text}
        </div>'''

        elif comp_type == ComponentType.LCARS_PANEL:
            content = properties.get("content", "Panel Content")
            title = properties.get("title", "")

            title_html = f'<div class="panel-title">{title}</div>' if title else ""

            return f'''<div class="lcars-panel" style="{position_style}" {aria_attrs}>
            {title_html}
            <div class="panel-content">{content}</div>
        </div>'''

        elif comp_type == ComponentType.ADMIN_CARD:
            title = properties.get("title", "Card Title")
            content = properties.get("content", "Card content")
            has_header = properties.get("has_header", True)
            has_footer = properties.get("has_footer", False)

            header_html = f'<div class="card-header">{title}</div>' if has_header else ""
            footer_html = '<div class="card-footer">Card Footer</div>' if has_footer else ""

            return f'''<div class="card" style="{position_style}" {aria_attrs}>
            {header_html}
            <div class="card-body">{content}</div>
            {footer_html}
        </div>'''

        elif comp_type == ComponentType.ADMIN_FORM:
            label = properties.get("label", "Input Label")
            input_type = properties.get("type", "text")
            placeholder = properties.get("placeholder", "Enter value...")
            required = "required" if properties.get("required", False) else ""

            return f'''<div class="mb-3" style="{position_style}" {aria_attrs}>
            <label class="form-label">{label}</label>
            <input type="{input_type}" class="form-control" placeholder="{placeholder}" {required}>
        </div>'''

        elif comp_type == ComponentType.ADMIN_TABLE:
            headers = properties.get("headers", ["Column 1", "Column 2", "Column 3"])
            rows = properties.get("rows", 3)
            striped = properties.get("striped", True)
            bordered = properties.get("bordered", False)

            table_classes = ["table"]
            if striped:
                table_classes.append("table-striped")
            if bordered:
                table_classes.append("table-bordered")

            header_html = "<tr>" + "".join(f"<th>{header}</th>" for header in headers) + "</tr>"
            rows_html = ""
            for i in range(rows):
                row_cells = "".join(f"<td>Data {i+1}-{j+1}</td>" for j in range(len(headers)))
                rows_html += f"<tr>{row_cells}</tr>"

            return f'''<div style="{position_style}" {aria_attrs}>
            <table class="{' '.join(table_classes)}">
                <thead>{header_html}</thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>'''

        # Default fallback for unknown components
        return f'''<div class="wireframe-component component-{comp_type}" style="{position_style}" {aria_attrs}>
            <span>Component: {comp_type}</span>
        </div>'''

    def _generate_css(self, components: List[Dict], canvas_settings: Dict, export_settings: Dict) -> str:
        """Generate CSS styles."""
        theme = canvas_settings.get("theme", "admin")
        css_framework = export_settings.get("css_framework", "bootstrap")
        minify = export_settings.get("minify_output", False)
        include_comments = export_settings.get("include_comments", True)

        css_parts = []

        # Add header comment
        if include_comments:
            css_parts.append(f"""/*
 * Generated Wireframe Styles
 * Theme: {theme}
 * Framework: {css_framework}
 * Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
 */
""")

        # Base styles
        css_parts.append("""
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
}""")

        # Theme-specific styles
        if theme == "lcars":
            css_parts.append(self._generate_lcars_css())
        else:
            css_parts.append(self._generate_admin_css())

        # Component-specific styles based on what's in the wireframe
        component_types = set(comp.get("type", "") for comp in components)
        for comp_type in component_types:
            component_css = self._generate_component_css(comp_type, theme)
            if component_css:
                css_parts.append(component_css)

        # Combine all CSS
        full_css = "\n".join(css_parts)

        # Minify if requested
        if minify:
            full_css = self._minify_css(full_css)

        return full_css

    def _generate_lcars_css(self) -> str:
        """Generate LCARS theme CSS."""
        return """
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
}"""

    def _generate_admin_css(self) -> str:
        """Generate admin theme CSS."""
        return """
/* Admin Theme */
.admin-theme {
    background-color: #f8f9fa;
    color: #212529;
}

.admin-theme .wireframe-container {
    background-color: white;
    border: 1px solid #dee2e6;
}"""

    def _generate_component_css(self, comp_type: str, theme: str) -> str:
        """Generate CSS for specific component type."""
        if comp_type == ComponentType.LCARS_STATUS_LIGHT:
            return """
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
    transition: all 0.3s ease;
}

.lcars-status-light.status-active .status-indicator {
    background-color: #00ff00;
    box-shadow: 0 0 10px #00ff00;
}

.lcars-status-light.status-inactive .status-indicator {
    background-color: #ff0000;
    box-shadow: 0 0 10px #ff0000;
}

.lcars-status-light.status-warning .status-indicator {
    background-color: #ffff00;
    box-shadow: 0 0 10px #ffff00;
}"""

        elif comp_type == ComponentType.LCARS_BUTTON:
            return """
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
    box-shadow: 0 4px 15px rgba(255, 153, 0, 0.4);
}

.lcars-button:disabled {
    background: #666;
    color: #999;
    cursor: not-allowed;
    transform: none;
}"""

        elif comp_type == ComponentType.LCARS_PROGRESS_BAR:
            return """
/* LCARS Progress Bar */
.lcars-progress-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    font-weight: bold;
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

.lcars-progress-bar .percentage-text {
    color: #ff9900;
    font-family: 'Courier New', monospace;
}"""

        elif comp_type == ComponentType.ADMIN_CARD:
            return """
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

.card-footer {
    padding: 0.75rem 1rem;
    background-color: #f8f9fa;
    border-top: 1px solid #dee2e6;
}"""

        return ""

    def _minify_css(self, css: str) -> str:
        """Basic CSS minification."""
        # Remove comments
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)

        # Remove extra whitespace
        css = re.sub(r'\s+', ' ', css)

        # Remove whitespace around certain characters
        css = re.sub(r'\s*([{}:;,>+~])\s*', r'\1', css)

        return css.strip()

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize project name for filename use."""
        # Remove special characters and spaces
        sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '', name.replace(' ', '_'))

        # Ensure it's not empty
        if not sanitized:
            sanitized = "wireframe"

        return sanitized.lower()

    def generate_export_package(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """Generate complete export package with multiple files."""
        try:
            # Generate HTML and CSS
            templates = self.generate_html_css(project)

            # Create file package
            package = {
                "files": {
                    f"{templates['filename_base']}.html": templates["html"],
                    "wireframe-styles.css": templates["css"]
                },
                "project_name": project.get("name", "Wireframe"),
                "generated_at": datetime.utcnow().isoformat(),
                "components_count": len(project.get("components", [])),
                "export_settings": project.get("export_settings", {})
            }

            # Add README if requested
            export_settings = project.get("export_settings", {})
            if export_settings.get("include_comments", True):
                readme_content = self._generate_readme(project, templates["filename_base"])
                package["files"]["README.md"] = readme_content

            return package

        except Exception as e:
            logger.error(f"Failed to generate export package: {str(e)}")
            raise

    def _generate_readme(self, project: Dict[str, Any], filename_base: str) -> str:
        """Generate README for export package."""
        project_name = project.get("name", "Wireframe")
        components_count = len(project.get("components", []))
        canvas_settings = project.get("canvas_settings", {})

        return f"""# {project_name} - Generated Wireframe

This wireframe was generated from TTRPG Center's UI Wireframe tool.

## Files

- `{filename_base}.html` - Main HTML structure
- `wireframe-styles.css` - Component styling
- `README.md` - This documentation

## Project Details

- **Components**: {components_count} components
- **Canvas Size**: {canvas_settings.get('width', 1200)}x{canvas_settings.get('height', 800)}px
- **Theme**: {canvas_settings.get('theme', 'admin')}
- **Generated**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Usage

1. Open `{filename_base}.html` in a web browser
2. Customize styles in `wireframe-styles.css` as needed
3. Replace placeholder content with real data
4. Add JavaScript functionality for interactive components

## Component Types Used

{self._list_component_types(project.get('components', []))}

## Notes

This is a wireframe template. You may need to:
- Add real content and data
- Implement backend functionality
- Add responsive breakpoints
- Enhance accessibility features
- Add proper form validation
- Implement interactive behaviors

Generated by TTRPG Center Wireframe Tool
"""

    def _list_component_types(self, components: List[Dict]) -> str:
        """List unique component types in the project."""
        types = set(comp.get("type", "unknown") for comp in components)
        if not types:
            return "- No components"

        return "\n".join(f"- {comp_type.replace('_', ' ').title()}" for comp_type in sorted(types))