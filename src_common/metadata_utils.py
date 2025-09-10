# src_common/metadata_utils.py
"""
Metadata Utilities for Unstructured Document Processing

Handles compatibility between different Unstructured library versions:
- Legacy: metadata as plain dict
- Current: metadata as ElementMetadata object (dataclass)

This utility provides consistent dict-based access regardless of the underlying format.
"""

from dataclasses import asdict, is_dataclass
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def md_to_dict(md: Any) -> Dict[str, Any]:
    """
    Normalize metadata to dict format for consistent access.
    
    Handles multiple Unstructured metadata formats:
    1. ElementMetadata with .to_dict() method (preferred for newer versions)
    2. Dataclass objects - converted with asdict()
    3. Plain dict - passed through unchanged
    4. None/empty - returns empty dict
    5. Fallback - extract public attributes as dict
    
    Args:
        md: Metadata object from Unstructured element
        
    Returns:
        Dict with metadata key-value pairs
        
    Examples:
        >>> from unstructured.documents.elements import Element
        >>> element = partition_pdf("doc.pdf")[0]  # newer version
        >>> md = md_to_dict(element.metadata)
        >>> page_num = md.get("page_number", 1)
        >>> source = md.get("filename", "unknown")
    """
    if md is None:
        return {}
    
    # Method 1: ElementMetadata with .to_dict() (newer versions)
    if hasattr(md, "to_dict") and callable(getattr(md, "to_dict")):
        try:
            result = md.to_dict()
            if isinstance(result, dict):
                return result
        except Exception as e:
            logger.debug(f"Failed to use .to_dict() method: {e}")
    
    # Method 2: Dataclass conversion
    if is_dataclass(md):
        try:
            return asdict(md)
        except Exception as e:
            logger.debug(f"Failed to convert dataclass to dict: {e}")
    
    # Method 3: Already a dict (legacy format)
    if isinstance(md, dict):
        return md
    
    # Method 4: Fallback - extract public attributes
    try:
        result = {}
        for attr_name in dir(md):
            if not attr_name.startswith("_") and not callable(getattr(md, attr_name)):
                try:
                    result[attr_name] = getattr(md, attr_name)
                except Exception:
                    # Skip attributes that can't be accessed
                    continue
        return result
    except Exception as e:
        logger.warning(f"Failed to extract metadata attributes: {e}")
        return {}


def safe_metadata_get(metadata: Any, key: str, default: Any = None) -> Any:
    """
    Safely get a value from metadata regardless of format.
    
    Args:
        metadata: Metadata object (any format)
        key: Key to retrieve
        default: Default value if key not found
        
    Returns:
        Value from metadata or default
        
    Examples:
        >>> page_num = safe_metadata_get(element.metadata, "page_number", 1)
        >>> coords = safe_metadata_get(element.metadata, "coordinates")
    """
    md_dict = md_to_dict(metadata)
    return md_dict.get(key, default)


def extract_page_info(metadata: Any, fallback_page: int = 1) -> int:
    """
    Extract page number from metadata with multiple key fallbacks.
    
    Args:
        metadata: Metadata object
        fallback_page: Page number to use if none found
        
    Returns:
        Page number (integer)
    """
    md_dict = md_to_dict(metadata)
    
    # Try multiple common page number keys
    for key in ["page_number", "page", "page_num", "pageNumber"]:
        value = md_dict.get(key)
        if value is not None:
            try:
                return int(value)
            except (ValueError, TypeError):
                continue
    
    return fallback_page


def extract_coordinates(metadata: Any) -> Optional[Dict[str, float]]:
    """
    Extract coordinate information from metadata.
    
    Args:
        metadata: Metadata object
        
    Returns:
        Dict with x, y, width, height or None if not available
    """
    md_dict = md_to_dict(metadata)
    coords = md_dict.get("coordinates")
    
    if not coords:
        return None
    
    # Handle coordinate object with attributes
    if hasattr(coords, "x") and hasattr(coords, "y"):
        try:
            return {
                "x": float(coords.x) if coords.x is not None else 0.0,
                "y": float(coords.y) if coords.y is not None else 0.0,
                "width": float(coords.width) if hasattr(coords, "width") and coords.width is not None else 0.0,
                "height": float(coords.height) if hasattr(coords, "height") and coords.height is not None else 0.0
            }
        except (ValueError, TypeError, AttributeError):
            return None
    
    # Handle coordinate dict
    if isinstance(coords, dict):
        try:
            return {
                "x": float(coords.get("x", 0)),
                "y": float(coords.get("y", 0)),
                "width": float(coords.get("width", 0)),
                "height": float(coords.get("height", 0))
            }
        except (ValueError, TypeError):
            return None
    
    return None


def extract_source_info(metadata: Any, fallback_source: str = "unknown") -> str:
    """
    Extract source/filename from metadata with multiple key fallbacks.
    
    Args:
        metadata: Metadata object
        fallback_source: Source name to use if none found
        
    Returns:
        Source filename or identifier
    """
    md_dict = md_to_dict(metadata)
    
    # Try multiple common source keys
    for key in ["filename", "source", "file_path", "source_file", "document"]:
        value = md_dict.get(key)
        if value:
            return str(value)
    
    return fallback_source