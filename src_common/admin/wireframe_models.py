"""
Wireframe Editor Data Models

Provides MongoDB data models for wireframe projects, components, and canvas management.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


class ComponentType(str, Enum):
    """Component type classification."""
    LCARS_STATUS_LIGHT = "lcars_status_light"
    LCARS_BUTTON = "lcars_button"
    LCARS_PANEL = "lcars_panel"
    LCARS_PROGRESS_BAR = "lcars_progress_bar"
    LCARS_DROPDOWN = "lcars_dropdown"
    LCARS_TEXT_AREA = "lcars_text_area"
    ADMIN_CARD = "admin_card"
    ADMIN_FORM = "admin_form"
    ADMIN_TABLE = "admin_table"
    ADMIN_BUTTON = "admin_button"
    ADMIN_NAVIGATION = "admin_navigation"
    ADMIN_DASHBOARD = "admin_dashboard"


class ComponentCategory(str, Enum):
    """Component category grouping."""
    LCARS = "lcars"
    ADMIN = "admin"
    CUSTOM = "custom"


class WireframeComponent(BaseModel):
    """Individual wireframe component definition."""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    type: ComponentType
    category: ComponentCategory
    name: str
    description: str
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 50.0
    rotation: float = 0.0
    z_index: int = 1
    properties: Dict[str, Any] = Field(default_factory=dict)
    styles: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CanvasSettings(BaseModel):
    """Canvas configuration and display settings."""
    width: int = 1200
    height: int = 800
    grid_size: int = 10
    grid_enabled: bool = True
    snap_to_grid: bool = True
    zoom_level: float = 1.0
    background_color: str = "#ffffff"
    grid_color: str = "#e0e0e0"
    theme: str = "admin"  # "admin" or "lcars"


class ExportSettings(BaseModel):
    """Code generation and export settings."""
    format: str = "html_css"  # Future: "react", "vue"
    include_responsive: bool = True
    include_accessibility: bool = True
    css_framework: str = "bootstrap"  # "bootstrap", "lcars", "custom"
    minify_output: bool = False
    include_comments: bool = True


class WireframeProject(BaseModel):
    """Main wireframe project document."""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    name: str
    description: str = ""
    owner: str  # User ID or "admin"
    components: List[WireframeComponent] = Field(default_factory=list)
    canvas_settings: CanvasSettings = Field(default_factory=CanvasSettings)
    export_settings: ExportSettings = Field(default_factory=ExportSettings)
    tags: List[str] = Field(default_factory=list)
    is_template: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }


class ComponentLibraryItem(BaseModel):
    """Component library definition for palette."""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    type: ComponentType
    category: ComponentCategory
    name: str
    description: str
    icon: str = ""  # SVG or icon class
    default_width: float = 100.0
    default_height: float = 50.0
    default_properties: Dict[str, Any] = Field(default_factory=dict)
    default_styles: Dict[str, Any] = Field(default_factory=dict)
    template_html: str = ""
    template_css: str = ""
    is_active: bool = True
    sort_order: int = 0

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            ObjectId: str
        }


class ProjectActivity(BaseModel):
    """Activity log for wireframe projects."""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    project_id: str
    user: str
    action: str  # "created", "updated", "exported", "deleted"
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            ObjectId: str
        }


# Default component library definitions
DEFAULT_LCARS_COMPONENTS = [
    ComponentLibraryItem(
        type=ComponentType.LCARS_STATUS_LIGHT,
        category=ComponentCategory.LCARS,
        name="Status Light",
        description="LCARS-style status indicator with colored states",
        default_width=30.0,
        default_height=30.0,
        default_properties={
            "status": "active",
            "color": "green",
            "pulse": False,
            "label": "Status"
        },
        template_html='<div class="lcars-status-light" data-status="{status}"><span>{label}</span></div>',
        template_css='.lcars-status-light { border-radius: 50%; border: 2px solid #ff9900; }'
    ),
    ComponentLibraryItem(
        type=ComponentType.LCARS_BUTTON,
        category=ComponentCategory.LCARS,
        name="LCARS Button",
        description="LCARS-themed button with characteristic styling",
        default_width=120.0,
        default_height=40.0,
        default_properties={
            "text": "Button",
            "variant": "primary",
            "disabled": False
        },
        template_html='<button class="lcars-button lcars-{variant}" {disabled}>{text}</button>',
        template_css='.lcars-button { background: linear-gradient(45deg, #ff9900, #ffcc00); }'
    ),
    ComponentLibraryItem(
        type=ComponentType.LCARS_PROGRESS_BAR,
        category=ComponentCategory.LCARS,
        name="Progress/Token Bar",
        description="Segmented progress bar for tier/rollover/bonus tokens",
        default_width=200.0,
        default_height=25.0,
        default_properties={
            "segments": 10,
            "filled": 6,
            "type": "tier",
            "show_percentage": True
        },
        template_html='<div class="lcars-progress-bar" data-type="{type}"><div class="progress-fill" style="width: {percentage}%"></div></div>',
        template_css='.lcars-progress-bar { background: #333; border: 1px solid #ff9900; }'
    )
]

DEFAULT_ADMIN_COMPONENTS = [
    ComponentLibraryItem(
        type=ComponentType.ADMIN_CARD,
        category=ComponentCategory.ADMIN,
        name="Bootstrap Card",
        description="Standard Bootstrap card component",
        default_width=300.0,
        default_height=200.0,
        default_properties={
            "title": "Card Title",
            "content": "Card content goes here",
            "has_header": True,
            "has_footer": False
        },
        template_html='<div class="card"><div class="card-header">{title}</div><div class="card-body">{content}</div></div>',
        template_css='.card { border: 1px solid #dee2e6; border-radius: 0.375rem; }'
    ),
    ComponentLibraryItem(
        type=ComponentType.ADMIN_FORM,
        category=ComponentCategory.ADMIN,
        name="Form Group",
        description="Bootstrap form input group",
        default_width=250.0,
        default_height=80.0,
        default_properties={
            "label": "Input Label",
            "type": "text",
            "placeholder": "Enter value...",
            "required": False
        },
        template_html='<div class="mb-3"><label class="form-label">{label}</label><input type="{type}" class="form-control" placeholder="{placeholder}" {required}></div>',
        template_css='.form-control { border: 1px solid #ced4da; border-radius: 0.375rem; }'
    ),
    ComponentLibraryItem(
        type=ComponentType.ADMIN_TABLE,
        category=ComponentCategory.ADMIN,
        name="Data Table",
        description="Bootstrap-styled data table",
        default_width=400.0,
        default_height=250.0,
        default_properties={
            "headers": ["Column 1", "Column 2", "Column 3"],
            "rows": 5,
            "striped": True,
            "bordered": False
        },
        template_html='<table class="table {classes}"><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>',
        template_css='.table { width: 100%; margin-bottom: 1rem; }'
    )
]