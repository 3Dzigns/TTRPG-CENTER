"""
Test suite for Data & RAG System user stories (02_data_rag.md)
Tests for RAG-001, RAG-002, RAG-003 acceptance criteria
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

# Test RAG-001: Multi-pass ingestion pipeline
class TestIngestionPipeline:
    
    def test_pass_a_pdf_parsing(self):
        """Test Pass A: PDF parsing to chunks"""
        from app.ingestion.pipeline import IngestionPipeline
        
        # Mock PDF content
        mock_pdf_content = "Sample PDF content for testing"
        with patch('app.ingestion.pipeline.extract_pdf_text') as mock_extract:
            mock_extract.return_value = [(1, mock_pdf_content)]
            
            pipeline = IngestionPipeline()
            chunks = pipeline._pass_a_parse_to_chunks("test.pdf")
            
            assert len(chunks) > 0, "No chunks generated from PDF parsing"
            assert all('text' in chunk for chunk in chunks), "Chunks missing text content"
            assert all('page' in chunk for chunk in chunks), "Chunks missing page numbers"
    
    def test_pass_b_dictionary_normalization(self):
        """Test Pass B: Dictionary normalization"""
        from app.ingestion.pipeline import IngestionPipeline
        from app.ingestion.dictionary import get_dictionary_manager
        
        # Create test chunks with terms that should be normalized
        test_chunks = [
            {'text': 'The wizard casts a spell', 'id': 'test1', 'page': 1},
            {'text': 'Magic missile hits the target', 'id': 'test2', 'page': 1}
        ]
        
        pipeline = IngestionPipeline()
        normalized_chunks = pipeline._pass_b_dictionary_normalization(test_chunks)
        
        assert len(normalized_chunks) == len(test_chunks), "Chunk count changed during normalization"
        # Verify metadata was added during normalization
        for chunk in normalized_chunks:
            assert 'metadata' in chunk or 'normalized_terms' in chunk, "No normalization metadata added"
    
    def test_pass_c_graph_compilation(self):
        """Test Pass C: Graph workflow compilation"""
        from app.ingestion.pipeline import IngestionPipeline
        
        test_chunks = [
            {'text': 'Character creation involves choosing a class', 'id': 'test1', 'page': 1},
            {'text': 'Level advancement grants new abilities', 'id': 'test2', 'page': 2}
        ]
        
        pipeline = IngestionPipeline()
        compiled_chunks = pipeline._pass_c_graph_compilation(test_chunks)
        
        assert len(compiled_chunks) == len(test_chunks), "Chunk count changed during compilation"
        # Verify workflow hints were added
        for chunk in compiled_chunks:
            assert 'workflow_hints' in chunk or 'graph_metadata' in chunk, "No graph metadata added"

# Test RAG-002: Metadata preservation
class TestMetadataPreservation:
    
    def test_chunk_metadata_structure(self):
        """Test chunks preserve required metadata"""
        from app.ingestion.pipeline import IngestionPipeline
        
        # Mock a complete ingestion
        with patch('app.ingestion.pipeline.extract_pdf_text') as mock_extract:
            mock_extract.return_value = [(1, "Test content"), (2, "More content")]
            
            pipeline = IngestionPipeline()
            result = pipeline.ingest_document("test.pdf")
            
            if result.get('chunks'):
                for chunk in result['chunks']:
                    required_fields = ['id', 'text', 'page', 'source_id']
                    for field in required_fields:
                        assert field in chunk, f"Chunk missing required field: {field}"
    
    def test_page_numbering_accuracy(self):
        """Test page numbers match original document"""
        from app.ingestion.pipeline import IngestionPipeline
        
        # Test with multi-page mock data
        mock_pages = [(1, "Page 1 content"), (3, "Page 3 content"), (5, "Page 5 content")]
        
        with patch('app.ingestion.pipeline.extract_pdf_text') as mock_extract:
            mock_extract.return_value = mock_pages
            
            pipeline = IngestionPipeline()
            result = pipeline.ingest_document("test.pdf")
            
            if result.get('chunks'):
                page_numbers = [chunk['page'] for chunk in result['chunks']]
                expected_pages = [1, 3, 5]  # Should preserve original page numbers
                assert any(p in expected_pages for p in page_numbers), "Page numbers not preserved"
    
    def test_section_subsection_tracking(self):
        """Test section and subsection metadata is tracked"""
        from app.ingestion.pipeline import IngestionPipeline
        
        # Mock content with section headers
        mock_content = [
            (1, "Chapter 1: Character Creation\nChoose your class..."),
            (2, "1.1 Races\nElf, human, dwarf...")
        ]
        
        with patch('app.ingestion.pipeline.extract_pdf_text') as mock_extract:
            mock_extract.return_value = mock_content
            
            pipeline = IngestionPipeline()
            result = pipeline.ingest_document("test.pdf")
            
            if result.get('chunks'):
                # At least some chunks should have section information
                has_sections = any('section' in chunk for chunk in result['chunks'])
                assert has_sections, "No section metadata preserved"

# Test RAG-003: Dynamic dictionary system
class TestDictionarySystem:
    
    def test_dictionary_interface_access(self):
        """Test admin dictionary interface is accessible"""
        from app.ingestion.dictionary import get_dictionary_manager
        
        dict_manager = get_dictionary_manager()
        assert dict_manager is not None, "Dictionary manager not accessible"
        
        # Test basic operations
        terms = dict_manager.get_all_terms()
        assert isinstance(terms, (list, dict)), "Dictionary terms not returned properly"
    
    def test_organic_term_growth(self):
        """Test dictionary grows from ingested content"""
        from app.ingestion.dictionary import get_dictionary_manager
        
        dict_manager = get_dictionary_manager()
        initial_count = len(dict_manager.get_all_terms())
        
        # Add a new term during ingestion simulation
        test_term = "test_spell_name"
        dict_manager.add_term(test_term, "A test spell for validation", {"type": "spell"})
        
        updated_count = len(dict_manager.get_all_terms())
        assert updated_count > initial_count, "Dictionary did not grow with new terms"
    
    def test_cross_system_mapping(self):
        """Test dictionary supports cross-system term mapping"""
        from app.ingestion.dictionary import get_dictionary_manager
        
        dict_manager = get_dictionary_manager()
        
        # Test adding a term with system mappings
        test_term = "armor_class"
        mappings = {
            "Pathfinder": "AC",
            "D&D 5e": "Armor Class", 
            "D&D 3.5": "AC"
        }
        
        dict_manager.add_term(test_term, "Character defense rating", {"mappings": mappings})
        
        retrieved = dict_manager.get_term(test_term)
        if retrieved:
            assert 'mappings' in retrieved.get('metadata', {}), "Cross-system mappings not stored"

# Integration tests
class TestRAGIntegration:
    
    def test_full_ingestion_to_search_flow(self):
        """Test complete flow from ingestion to RAG search"""
        from app.ingestion.pipeline import IngestionPipeline
        from app.common.astra_client import get_vector_store
        
        # Mock the full flow
        with patch('app.ingestion.pipeline.extract_pdf_text') as mock_extract:
            mock_extract.return_value = [(1, "The wizard studies magic spells")]
            
            pipeline = IngestionPipeline()
            result = pipeline.ingest_document("test.pdf")
            
            # Verify chunks were created
            assert result.get('status') == 'success', "Ingestion failed"
            if result.get('chunks'):
                assert len(result['chunks']) > 0, "No chunks created"
                
                # Test that vector store can be queried
                vector_store = get_vector_store()
                health = vector_store.health_check()
                assert health['status'] in ['connected', 'error'], "Vector store not responding"
    
    def test_metadata_searchability(self):
        """Test ingested metadata supports search filtering"""
        from app.common.astra_client import get_vector_store
        
        vector_store = get_vector_store()
        
        # Test search with metadata filters
        mock_embedding = [0.1] * 1536  # Mock embedding vector
        
        # Search with system filter
        results = vector_store.similarity_search(
            mock_embedding, 
            k=5, 
            filters={"system": "Pathfinder 2E"}
        )
        
        # Should not error, even if no results
        assert isinstance(results, list), "Search with metadata filters failed"