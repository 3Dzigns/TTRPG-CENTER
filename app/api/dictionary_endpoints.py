#!/usr/bin/env python3
"""
Dictionary API Endpoints for Admin UI
=====================================

User Story: Dictionary tab in Admin UI shows dictionary entries directly 
from persisted snapshot for fast single-read retrieval
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import os

from app.ingestion.dictionary_system import DictionaryCreationSystem
from app.common.run_mode import enforce_execution_over_reasoning, get_current_run_mode, RunMode

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

def get_dictionary_system() -> DictionaryCreationSystem:
    """Get dictionary system instance with RUN_MODE compliance"""
    enforce_execution_over_reasoning("get_dictionary_system")
    env = os.getenv("APP_ENV", "dev")
    return DictionaryCreationSystem(env)

@router.get("/snapshots")
async def list_dictionary_snapshots() -> Dict[str, Any]:
    """
    List available dictionary snapshots
    
    User Story: Fast single-read retrieval of dictionary snapshots
    """
    try:
        dict_system = get_dictionary_system()
        
        # Get all snapshots from AstraDB
        collection = dict_system.database.get_collection("ttrpg_dictionary_snapshots")
        snapshots = list(collection.find({}, projection={"entries": False}))  # Exclude large entries field
        
        # Sort by creation date
        snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {
            "success": True,
            "count": len(snapshots),
            "snapshots": snapshots
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list snapshots: {str(e)}")

@router.get("/snapshots/{snapshot_id}")
async def get_dictionary_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """
    Get specific dictionary snapshot with all entries
    
    User Story: Dictionary tab shows entries directly from persisted snapshot
    """
    try:
        dict_system = get_dictionary_system()
        snapshot = dict_system.get_dictionary_snapshot(snapshot_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Dictionary snapshot '{snapshot_id}' not found")
        
        return {
            "success": True,
            "snapshot": snapshot
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get snapshot: {str(e)}")

@router.get("/snapshots/{snapshot_id}/entries")
async def get_dictionary_entries(
    snapshot_id: str,
    concept_type: Optional[str] = Query(None, description="Filter by concept type (spell, feat, monster, etc.)"),
    search: Optional[str] = Query(None, description="Search in concept names"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page")
) -> Dict[str, Any]:
    """
    Get dictionary entries with filtering and pagination
    
    User Story: Dictionary tab with filtering and search capabilities
    """
    try:
        dict_system = get_dictionary_system()
        snapshot = dict_system.get_dictionary_snapshot(snapshot_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Dictionary snapshot '{snapshot_id}' not found")
        
        entries = snapshot.get("entries", [])
        
        # Apply filters
        filtered_entries = entries
        
        if concept_type:
            filtered_entries = [e for e in filtered_entries if e.get("concept_type") == concept_type]
        
        if search:
            search_lower = search.lower()
            filtered_entries = [
                e for e in filtered_entries 
                if search_lower in e.get("concept_name", "").lower() 
                or search_lower in e.get("description", "").lower()
            ]
        
        # Apply pagination
        total_count = len(filtered_entries)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_entries = filtered_entries[start_idx:end_idx]
        
        return {
            "success": True,
            "total_count": total_count,
            "page": page,
            "page_size": page_size,
            "total_pages": (total_count + page_size - 1) // page_size,
            "entries": page_entries,
            "filters": {
                "concept_type": concept_type,
                "search": search
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get entries: {str(e)}")

@router.get("/snapshots/{snapshot_id}/statistics")
async def get_dictionary_statistics(snapshot_id: str) -> Dict[str, Any]:
    """Get statistics for a dictionary snapshot"""
    try:
        dict_system = get_dictionary_system()
        snapshot = dict_system.get_dictionary_snapshot(snapshot_id)
        
        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Dictionary snapshot '{snapshot_id}' not found")
        
        return {
            "success": True,
            "statistics": snapshot.get("statistics", {}),
            "metadata": {
                "created_at": snapshot.get("created_at"),
                "env": snapshot.get("env"),
                "collection_name": snapshot.get("collection_name")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@router.put("/entries/{entry_id}")
async def update_dictionary_entry(entry_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update dictionary entry for cross-system normalization
    
    User Story: Edit dictionary terms via Admin UI for cross-system normalization
    """
    try:
        # Check if updates are allowed in current mode
        run_mode = get_current_run_mode()
        if run_mode == RunMode.SERVE:
            raise HTTPException(
                status_code=403, 
                detail="Dictionary updates not allowed in SERVE mode. Switch to MAINT mode."
            )
        
        dict_system = get_dictionary_system()
        
        # Validate updates - only allow safe fields
        allowed_fields = [
            "concept_name", "description", "metadata", 
            "related_concepts", "prerequisites"
        ]
        
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not safe_updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        success = dict_system.update_dictionary_entry(entry_id, safe_updates, user_id="admin_ui")
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found or update failed")
        
        return {
            "success": True,
            "message": f"Entry '{entry_id}' updated successfully",
            "updated_fields": list(safe_updates.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update entry: {str(e)}")

@router.get("/concept-types")
async def get_available_concept_types() -> Dict[str, Any]:
    """Get list of available concept types across all snapshots"""
    try:
        dict_system = get_dictionary_system()
        
        # Get concept types from all snapshots
        collection = dict_system.database.get_collection("ttrpg_dictionary_snapshots")
        snapshots = list(collection.find({}, projection={"statistics.concept_types": 1}))
        
        concept_types = set()
        for snapshot in snapshots:
            stats = snapshot.get("statistics", {})
            types = stats.get("concept_types", {})
            concept_types.update(types.keys())
        
        return {
            "success": True,
            "concept_types": sorted(list(concept_types))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get concept types: {str(e)}")