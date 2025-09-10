# tests/unit/test_metadata_compatibility.py
"""
Unit tests for metadata compatibility between different Unstructured versions.

Tests the metadata_utils module's ability to handle both legacy dict format
and modern ElementMetadata object format consistently.
"""

import pytest
from dataclasses import dataclass
from typing import Dict, Any, Optional

from src_common.metadata_utils import (
    md_to_dict, 
    safe_metadata_get,
    extract_page_info, 
    extract_coordinates,
    extract_source_info
)


# Mock ElementMetadata class to simulate newer Unstructured format
@dataclass
class MockElementMetadata:
    """Mock ElementMetadata similar to unstructured library"""
    page_number: Optional[int] = None
    filename: Optional[str] = None
    coordinates: Optional['MockCoordinates'] = None
    section_title: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Method available in newer ElementMetadata versions"""
        return {
            "page_number": self.page_number,
            "filename": self.filename,
            "coordinates": self.coordinates,
            "section_title": self.section_title
        }


@dataclass  
class MockCoordinates:
    """Mock coordinate object"""
    x: float
    y: float
    width: float
    height: float


class MockElementMetadataNoMethod:
    """Mock metadata object without to_dict method (fallback case)"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestMetadataUtils:
    """Test metadata utility functions"""
    
    def test_md_to_dict_with_none(self):
        """Test handling of None metadata"""
        result = md_to_dict(None)
        assert result == {}
    
    def test_md_to_dict_with_dict(self):
        """Test handling of legacy dict format"""
        metadata = {"page_number": 5, "filename": "test.pdf"}
        result = md_to_dict(metadata)
        assert result == metadata
        assert result["page_number"] == 5
        assert result["filename"] == "test.pdf"
    
    def test_md_to_dict_with_element_metadata(self):
        """Test handling of ElementMetadata object with to_dict method"""
        coords = MockCoordinates(x=10.0, y=20.0, width=100.0, height=50.0)
        metadata = MockElementMetadata(
            page_number=3, 
            filename="document.pdf",
            coordinates=coords,
            section_title="Chapter 1"
        )
        
        result = md_to_dict(metadata)
        assert isinstance(result, dict)
        assert result["page_number"] == 3
        assert result["filename"] == "document.pdf"
        assert result["section_title"] == "Chapter 1"
        assert result["coordinates"] == coords
    
    def test_md_to_dict_with_dataclass_no_method(self):
        """Test handling of dataclass without to_dict method"""
        # Create a custom dataclass that doesn't have to_dict
        @dataclass
        class CustomMetadata:
            page_number: int
            source: str
        
        metadata = CustomMetadata(page_number=7, source="custom.pdf")
        result = md_to_dict(metadata)
        assert isinstance(result, dict)
        assert result["page_number"] == 7
        assert result["source"] == "custom.pdf"
    
    def test_md_to_dict_with_fallback_attributes(self):
        """Test fallback attribute extraction"""
        metadata = MockElementMetadataNoMethod(
            page_number=9,
            filename="fallback.pdf",
            section="Introduction"
        )
        
        result = md_to_dict(metadata)
        assert isinstance(result, dict)
        assert result["page_number"] == 9
        assert result["filename"] == "fallback.pdf"
        assert result["section"] == "Introduction"
    
    def test_safe_metadata_get(self):
        """Test safe metadata value retrieval"""
        # Test with dict
        dict_metadata = {"page_number": 5, "filename": "test.pdf"}
        assert safe_metadata_get(dict_metadata, "page_number") == 5
        assert safe_metadata_get(dict_metadata, "missing_key", "default") == "default"
        
        # Test with ElementMetadata
        metadata = MockElementMetadata(page_number=3, filename="doc.pdf")
        assert safe_metadata_get(metadata, "page_number") == 3
        assert safe_metadata_get(metadata, "filename") == "doc.pdf"
        assert safe_metadata_get(metadata, "missing_key", "default") == "default"
        
        # Test with None
        assert safe_metadata_get(None, "anything", "default") == "default"
    
    def test_extract_page_info(self):
        """Test page number extraction with fallbacks"""
        # Test with dict format
        dict_metadata = {"page_number": 15}
        assert extract_page_info(dict_metadata) == 15
        
        # Test with ElementMetadata
        metadata = MockElementMetadata(page_number=8)
        assert extract_page_info(metadata) == 8
        
        # Test with alternative key names
        alt_metadata = {"page": 12}
        assert extract_page_info(alt_metadata) == 12
        
        # Test with missing page info
        empty_metadata = {"filename": "test.pdf"}
        assert extract_page_info(empty_metadata, fallback_page=99) == 99
        
        # Test with None
        assert extract_page_info(None, fallback_page=42) == 42
        
        # Test with invalid page number
        invalid_metadata = {"page_number": "not_a_number"}
        assert extract_page_info(invalid_metadata, fallback_page=1) == 1
    
    def test_extract_coordinates(self):
        """Test coordinate extraction"""
        # Test with coordinate object
        coords = MockCoordinates(x=25.5, y=30.0, width=200.0, height=100.0)
        metadata = MockElementMetadata(coordinates=coords)
        result = extract_coordinates(metadata)
        
        assert result is not None
        assert result["x"] == 25.5
        assert result["y"] == 30.0
        assert result["width"] == 200.0
        assert result["height"] == 100.0
        
        # Test with coordinate dict
        coord_dict = {"x": 10.0, "y": 15.0, "width": 50.0, "height": 25.0}
        dict_metadata = {"coordinates": coord_dict}
        result = extract_coordinates(dict_metadata)
        
        assert result is not None
        assert result["x"] == 10.0
        assert result["y"] == 15.0
        assert result["width"] == 50.0
        assert result["height"] == 25.0
        
        # Test with missing coordinates
        no_coords_metadata = {"page_number": 5}
        assert extract_coordinates(no_coords_metadata) is None
        
        # Test with None
        assert extract_coordinates(None) is None
    
    def test_extract_source_info(self):
        """Test source/filename extraction with fallbacks"""
        # Test with filename key
        metadata = {"filename": "document.pdf"}
        assert extract_source_info(metadata) == "document.pdf"
        
        # Test with ElementMetadata
        element_metadata = MockElementMetadata(filename="test.pdf")
        assert extract_source_info(element_metadata) == "test.pdf"
        
        # Test with alternative key names
        alt_metadata = {"source": "alternative.pdf"}
        assert extract_source_info(alt_metadata) == "alternative.pdf"
        
        # Test with missing source info
        no_source_metadata = {"page_number": 5}
        assert extract_source_info(no_source_metadata, fallback_source="unknown") == "unknown"
        
        # Test with None
        assert extract_source_info(None, fallback_source="default") == "default"


class TestRealWorldScenarios:
    """Test scenarios that match actual usage patterns"""
    
    def test_pass_c_extraction_pattern(self):
        """Test the pattern used in Pass C extraction"""
        # Simulate new Unstructured element with ElementMetadata
        coords = MockCoordinates(x=10.0, y=20.0, width=100.0, height=50.0)
        metadata = MockElementMetadata(
            page_number=5,
            filename="ttrpg_manual.pdf", 
            coordinates=coords
        )
        
        # Simulate element object with metadata attribute
        class MockElement:
            def __init__(self, metadata):
                self.metadata = metadata
        
        element = MockElement(metadata)
        
        # Test the pattern from pass_c_extraction.py
        page_num = extract_page_info(getattr(element, 'metadata', None), fallback_page=1)
        coordinates = extract_coordinates(getattr(element, 'metadata', None))
        
        assert page_num == 5
        assert coordinates is not None
        assert coordinates["x"] == 10.0
        assert coordinates["width"] == 100.0
    
    def test_orchestrator_service_pattern(self):
        """Test the pattern used in orchestrator service"""
        # Simulate chunk object with metadata
        class MockChunk:
            def __init__(self, metadata):
                self.metadata = metadata
        
        metadata = MockElementMetadata(page_number=7, section_title="Combat Rules")
        chunk = MockChunk(metadata)
        
        # Test the pattern from orchestrator/service.py  
        meta_page = safe_metadata_get(chunk.metadata, "page") or safe_metadata_get(chunk.metadata, "page_number")
        sec = safe_metadata_get(chunk.metadata, "section") or safe_metadata_get(chunk.metadata, "section_title")
        
        assert meta_page == 7
        assert sec == "Combat Rules"
    
    def test_app_feedback_pattern(self):
        """Test the pattern used in app feedback"""
        # Simulate feedback object with metadata
        class MockFeedback:
            def __init__(self, metadata):
                self.metadata = metadata
        
        metadata = MockElementMetadata()
        metadata_dict = md_to_dict(metadata)
        metadata_dict["model"] = "gpt-4"
        
        feedback = MockFeedback(metadata_dict)
        
        # Test the pattern from app_feedback.py
        model = safe_metadata_get(feedback.metadata, "model", "unknown")
        assert model == "gpt-4"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__])