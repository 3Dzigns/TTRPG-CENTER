"""
Wireframe Editor Backend Service

Provides REST API endpoints and business logic for wireframe project management,
canvas operations, and component library management.
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import HTTPException
from bson import ObjectId

from ..mongodb_service import MongoDBService
from ..ttrpg_logging import get_logger
from .wireframe_models import (
    WireframeProject, WireframeComponent, ComponentLibraryItem,
    ProjectActivity, ComponentType, ComponentCategory,
    DEFAULT_LCARS_COMPONENTS, DEFAULT_ADMIN_COMPONENTS
)

logger = get_logger(__name__)


class WireframeEditorService:
    """Service class for wireframe editor operations."""

    def __init__(self, mongodb_service: MongoDBService):
        """Initialize with MongoDB service."""
        self.mongodb = mongodb_service
        self.projects_collection = "wireframe_projects"
        self.components_collection = "wireframe_components"
        self.activities_collection = "wireframe_activities"

    async def initialize_collections(self) -> Dict[str, Any]:
        """Initialize MongoDB collections and default data."""
        try:
            # Ensure collections exist
            collections = await self.mongodb.list_collections()

            # Create indexes for performance
            if self.projects_collection not in collections:
                await self.mongodb.create_index(
                    self.projects_collection,
                    [("owner", 1), ("created_at", -1)]
                )
                await self.mongodb.create_index(
                    self.projects_collection,
                    [("name", "text"), ("description", "text")]
                )

            if self.components_collection not in collections:
                await self.mongodb.create_index(
                    self.components_collection,
                    [("category", 1), ("type", 1), ("sort_order", 1)]
                )

            if self.activities_collection not in collections:
                await self.mongodb.create_index(
                    self.activities_collection,
                    [("project_id", 1), ("timestamp", -1)]
                )

            # Initialize default component library
            await self._initialize_component_library()

            logger.info("Wireframe editor collections initialized successfully")
            return {
                "status": "success",
                "message": "Collections initialized",
                "collections": [self.projects_collection, self.components_collection, self.activities_collection]
            }

        except Exception as e:
            logger.error(f"Failed to initialize wireframe collections: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

    async def _initialize_component_library(self) -> None:
        """Initialize default component library if empty."""
        try:
            # Check if component library already exists
            existing_count = await self.mongodb.count_documents(self.components_collection, {})

            if existing_count == 0:
                # Insert default LCARS components
                for i, component in enumerate(DEFAULT_LCARS_COMPONENTS):
                    component_dict = component.dict()
                    component_dict["sort_order"] = i
                    await self.mongodb.insert_document(self.components_collection, component_dict)

                # Insert default admin components
                for i, component in enumerate(DEFAULT_ADMIN_COMPONENTS):
                    component_dict = component.dict()
                    component_dict["sort_order"] = i + 100
                    await self.mongodb.insert_document(self.components_collection, component_dict)

                logger.info("Default component library initialized")

        except Exception as e:
            logger.error(f"Failed to initialize component library: {str(e)}")
            raise

    # Project Management
    async def create_project(self, project_data: Dict[str, Any], user: str = "admin") -> Dict[str, Any]:
        """Create new wireframe project."""
        try:
            # Validate required fields
            if not project_data.get("name"):
                raise HTTPException(status_code=400, detail="Project name is required")

            # Create project instance
            project = WireframeProject(
                name=project_data["name"],
                description=project_data.get("description", ""),
                owner=user,
                tags=project_data.get("tags", [])
            )

            # Insert into database
            project_dict = project.dict()
            result = await self.mongodb.insert_document(self.projects_collection, project_dict)

            # Log activity
            await self._log_activity(project.id, user, "created", {
                "project_name": project.name
            })

            logger.info(f"Created wireframe project: {project.name} (ID: {project.id})")
            return {
                "status": "success",
                "project_id": project.id,
                "project": project_dict
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create wireframe project: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Project creation failed: {str(e)}")

    async def get_projects(self, user: str = "admin", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get wireframe projects for user."""
        try:
            # Query projects
            query = {"owner": user}
            projects = await self.mongodb.find_documents(
                self.projects_collection,
                query,
                sort=[("updated_at", -1)],
                limit=limit,
                skip=offset
            )

            # Get total count
            total_count = await self.mongodb.count_documents(self.projects_collection, query)

            # Convert to list and update last_accessed
            project_list = []
            for project in projects:
                # Update last_accessed timestamp
                await self.mongodb.update_document(
                    self.projects_collection,
                    {"id": project["id"]},
                    {"$set": {"last_accessed": datetime.utcnow()}}
                )
                project_list.append(project)

            return {
                "status": "success",
                "projects": project_list,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            logger.error(f"Failed to get wireframe projects: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")

    async def get_project(self, project_id: str, user: str = "admin") -> Dict[str, Any]:
        """Get specific wireframe project."""
        try:
            # Find project
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Update last_accessed
            await self.mongodb.update_document(
                self.projects_collection,
                {"id": project_id},
                {"$set": {"last_accessed": datetime.utcnow()}}
            )

            return {
                "status": "success",
                "project": project
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get wireframe project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

    async def update_project(self, project_id: str, updates: Dict[str, Any], user: str = "admin") -> Dict[str, Any]:
        """Update wireframe project."""
        try:
            # Verify ownership
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Prepare updates
            update_data = {
                "updated_at": datetime.utcnow(),
                "version": project.get("version", 1) + 1
            }

            # Update allowed fields
            allowed_fields = ["name", "description", "components", "canvas_settings", "export_settings", "tags"]
            for field in allowed_fields:
                if field in updates:
                    update_data[field] = updates[field]

            # Update in database
            result = await self.mongodb.update_document(
                self.projects_collection,
                {"id": project_id},
                {"$set": update_data}
            )

            # Log activity
            await self._log_activity(project_id, user, "updated", {
                "fields_updated": list(updates.keys())
            })

            logger.info(f"Updated wireframe project {project_id}")
            return {
                "status": "success",
                "updated_fields": list(updates.keys()),
                "version": update_data["version"]
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update wireframe project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

    async def delete_project(self, project_id: str, user: str = "admin") -> Dict[str, Any]:
        """Delete wireframe project."""
        try:
            # Verify ownership
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Delete project
            await self.mongodb.delete_document(
                self.projects_collection,
                {"id": project_id}
            )

            # Log activity
            await self._log_activity(project_id, user, "deleted", {
                "project_name": project.get("name", "Unknown")
            })

            logger.info(f"Deleted wireframe project {project_id}")
            return {
                "status": "success",
                "message": "Project deleted successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete wireframe project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

    # Component Library Management
    async def get_component_library(self, category: Optional[str] = None) -> Dict[str, Any]:
        """Get component library items."""
        try:
            # Build query
            query = {"is_active": True}
            if category:
                query["category"] = category

            # Get components
            components = await self.mongodb.find_documents(
                self.components_collection,
                query,
                sort=[("category", 1), ("sort_order", 1)]
            )

            # Group by category
            grouped_components = {}
            for component in components:
                cat = component.get("category", "other")
                if cat not in grouped_components:
                    grouped_components[cat] = []
                grouped_components[cat].append(component)

            return {
                "status": "success",
                "components": list(components),
                "grouped_components": grouped_components
            }

        except Exception as e:
            logger.error(f"Failed to get component library: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get components: {str(e)}")

    # Component Operations
    async def add_component_to_project(self, project_id: str, component_data: Dict[str, Any], user: str = "admin") -> Dict[str, Any]:
        """Add component to wireframe project."""
        try:
            # Verify project ownership
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Create component
            component = WireframeComponent(**component_data)

            # Add to project components
            components = project.get("components", [])
            components.append(component.dict())

            # Update project
            await self.mongodb.update_document(
                self.projects_collection,
                {"id": project_id},
                {"$set": {
                    "components": components,
                    "updated_at": datetime.utcnow(),
                    "version": project.get("version", 1) + 1
                }}
            )

            # Log activity
            await self._log_activity(project_id, user, "component_added", {
                "component_type": component.type,
                "component_id": component.id
            })

            logger.info(f"Added component to project {project_id}: {component.type}")
            return {
                "status": "success",
                "component_id": component.id,
                "component": component.dict()
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to add component to project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to add component: {str(e)}")

    async def update_component(self, project_id: str, component_id: str, updates: Dict[str, Any], user: str = "admin") -> Dict[str, Any]:
        """Update component in wireframe project."""
        try:
            # Get project
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Find and update component
            components = project.get("components", [])
            component_found = False

            for i, component in enumerate(components):
                if component.get("id") == component_id:
                    # Update component fields
                    for field, value in updates.items():
                        if field in ["x", "y", "width", "height", "rotation", "z_index", "properties", "styles"]:
                            components[i][field] = value

                    components[i]["updated_at"] = datetime.utcnow().isoformat()
                    component_found = True
                    break

            if not component_found:
                raise HTTPException(status_code=404, detail="Component not found")

            # Update project
            await self.mongodb.update_document(
                self.projects_collection,
                {"id": project_id},
                {"$set": {
                    "components": components,
                    "updated_at": datetime.utcnow(),
                    "version": project.get("version", 1) + 1
                }}
            )

            return {
                "status": "success",
                "message": "Component updated successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update component {component_id} in project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to update component: {str(e)}")

    async def delete_component(self, project_id: str, component_id: str, user: str = "admin") -> Dict[str, Any]:
        """Delete component from wireframe project."""
        try:
            # Get project
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Remove component
            components = project.get("components", [])
            original_count = len(components)
            components = [c for c in components if c.get("id") != component_id]

            if len(components) == original_count:
                raise HTTPException(status_code=404, detail="Component not found")

            # Update project
            await self.mongodb.update_document(
                self.projects_collection,
                {"id": project_id},
                {"$set": {
                    "components": components,
                    "updated_at": datetime.utcnow(),
                    "version": project.get("version", 1) + 1
                }}
            )

            return {
                "status": "success",
                "message": "Component deleted successfully"
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete component {component_id} from project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to delete component: {str(e)}")

    # Activity Logging
    async def _log_activity(self, project_id: str, user: str, action: str, details: Dict[str, Any]) -> None:
        """Log project activity."""
        try:
            activity = ProjectActivity(
                project_id=project_id,
                user=user,
                action=action,
                details=details
            )

            await self.mongodb.insert_document(
                self.activities_collection,
                activity.dict()
            )

        except Exception as e:
            logger.warning(f"Failed to log activity: {str(e)}")

    async def get_project_activities(self, project_id: str, user: str = "admin", limit: int = 50) -> Dict[str, Any]:
        """Get project activity log."""
        try:
            # Verify project access
            project = await self.mongodb.find_one(
                self.projects_collection,
                {"id": project_id, "owner": user}
            )

            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Get activities
            activities = await self.mongodb.find_documents(
                self.activities_collection,
                {"project_id": project_id},
                sort=[("timestamp", -1)],
                limit=limit
            )

            return {
                "status": "success",
                "activities": list(activities)
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get activities for project {project_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get activities: {str(e)}")

    # Health Check
    async def health_check(self) -> Dict[str, Any]:
        """Check wireframe editor service health."""
        try:
            # Test MongoDB connection
            collections_count = len(await self.mongodb.list_collections())

            # Get some basic stats
            projects_count = await self.mongodb.count_documents(self.projects_collection, {})
            components_count = await self.mongodb.count_documents(self.components_collection, {})

            return {
                "status": "healthy",
                "service": "wireframe_editor",
                "mongodb_collections": collections_count,
                "projects_count": projects_count,
                "component_library_count": components_count,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Wireframe editor health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "service": "wireframe_editor",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }