# tests/regression/phase1/test_rag001d_vector_enrichment.py
"""
Phase 1 - US RAG-001D: Pass D Vector Enrichment Regression Tests (HARD GATE)
Tests vector enrichment functionality using Haystack for embeddings, NER, and deduplication
"""

import json
import pytest
import tempfile
import os
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassDVectorEnrichment:
    """Test suite for Pass D vector enrichment functionality (HARD GATE)"""

    def test_haystack_tool_availability(self):
        """HARD GATE: Verify Haystack tool is available and functional"""
        try:
            # Test that Haystack can be imported
            import haystack

            # Verify core embedding components are available
            from haystack.document_stores import InMemoryDocumentStore
            from haystack.nodes import EmbeddingRetriever
            assert InMemoryDocumentStore is not None, "InMemoryDocumentStore should be available"
            assert EmbeddingRetriever is not None, "EmbeddingRetriever should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Haystack not available: {e}")

    def test_pass_d_module_integration(self):
        """HARD GATE: Test that Pass D module exists and integrates with Haystack"""
        try:
            # Import the Pass D module
            from src_common.pass_d_vector_enrichment import process_pass_d, PassDVectorEnricher

            # Verify functions are available
            assert callable(process_pass_d), "process_pass_d function should be available"
            assert callable(process_pass_d), "process_pass_d function should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass D module not available: {e}")

    def test_pass_d_contract_compliance(self):
        """HARD GATE: Test that Pass D produces contract-compliant output structure"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock chunks file from Pass C
            chunks_file = artifacts_dir / "test_pass_c_chunks.jsonl"
            mock_chunks = [
                {
                    "text": "Fireball is a 3rd-level evocation spell",
                    "page": 242,
                    "type": "NarrativeText",
                    "section": "Spells",
                    "chunk_id": "chunk_001"
                },
                {
                    "text": "The Wizard class gains access to many spells",
                    "page": 114,
                    "type": "NarrativeText",
                    "section": "Classes",
                    "chunk_id": "chunk_002"
                }
            ]

            with open(chunks_file, 'w') as f:
                for chunk in mock_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create mock manifest from previous passes
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 2048000},
                "pass_a_output": {"toc_sections": []},
                "pass_b_output": {"split_performed": False},
                "pass_c_output": {"chunks_file": "test_pass_c_chunks.jsonl", "chunk_count": 2},
                "completed_passes": ["A", "B", "C"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock OpenAI embeddings and Haystack operations
            with patch('openai.Embedding.create') as mock_openai, \
                 patch('haystack.nodes.EmbeddingRetriever') as mock_retriever:

                # Configure OpenAI mock
                mock_openai.return_value = {
                    'data': [
                        {'embedding': [0.1, 0.2, 0.3] * 512},  # 1536-dim embedding
                        {'embedding': [0.4, 0.5, 0.6] * 512}
                    ]
                }

                # Configure Haystack mock
                mock_retriever_instance = MagicMock()
                mock_retriever.return_value = mock_retriever_instance

                # Test process_pass_d function
                result = process_pass_d(str(artifacts_dir))

                # Verify result structure
                assert isinstance(result, dict), "Process result should be a dictionary"
                assert "enrichment_performed" in result, "Result should indicate if enrichment was performed"
                assert "vector_count" in result, "Result should contain vector count"
                assert "updated_manifest" in result, "Result should contain updated manifest"

                # Verify manifest was updated
                updated_manifest = result["updated_manifest"]
                assert "pass_d_output" in updated_manifest, "Manifest should contain Pass D output"
                assert "completed_passes" in updated_manifest, "Manifest should track completed passes"
                assert "D" in updated_manifest["completed_passes"], "Pass D should be marked as completed"

    def test_pass_d_vector_embedding(self):
        """HARD GATE: Test vector embedding functionality with OpenAI API"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Mock chunks for embedding
        mock_chunks = [
            {
                "text": "Fireball deals 8d6 fire damage",
                "page": 242,
                "type": "NarrativeText",
                "chunk_id": "chunk_001"
            },
            {
                "text": "Magic Missile automatically hits its target",
                "page": 257,
                "type": "NarrativeText",
                "chunk_id": "chunk_002"
            }
        ]

        # Mock OpenAI embedding API
        with patch('openai.Embedding.create') as mock_openai:
            # Configure mock to return embeddings
            mock_openai.return_value = {
                'data': [
                    {'embedding': np.random.rand(1536).tolist()},
                    {'embedding': np.random.rand(1536).tolist()}
                ]
            }

            # Test vector enrichment
            enriched_chunks = process_pass_d(mock_chunks)

            # Verify enriched chunks structure
            assert isinstance(enriched_chunks, list), "Enriched chunks should be a list"
            assert len(enriched_chunks) == 2, "Should return same number of chunks"

            for chunk in enriched_chunks:
                assert "vector" in chunk, "Each chunk should have vector"
                assert "vector_id" in chunk, "Each chunk should have vector_id"
                assert "embedding_model" in chunk, "Each chunk should specify embedding model"
                assert len(chunk["vector"]) == 1536, "Vector should be 1536 dimensions"

            # Verify OpenAI was called
            mock_openai.assert_called()

    def test_pass_d_ner_extraction(self):
        """HARD GATE: Test Named Entity Recognition and keyword extraction"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Test text with recognizable entities
        test_text = "The Wizard Gandalf casts Fireball at the Dragon. Roll initiative using a d20."

        # Mock NER pipeline
        with patch('haystack.nodes.EntityExtractor') as mock_ner:
            mock_ner_instance = MagicMock()
            mock_ner.return_value = mock_ner_instance

            # Configure mock to return entities
            mock_ner_instance.extract.return_value = [
                {"entity": "PERSON", "word": "Gandalf", "score": 0.95},
                {"entity": "SPELL", "word": "Fireball", "score": 0.88},
                {"entity": "CREATURE", "word": "Dragon", "score": 0.92}
            ]

            # Test entity extraction
            entities, keywords = process_pass_d(test_text)

            # Verify extraction results
            assert isinstance(entities, list), "Entities should be a list"
            assert isinstance(keywords, list), "Keywords should be a list"
            assert len(entities) > 0, "Should extract entities"

            # Verify entity structure
            for entity in entities:
                assert "entity" in entity, "Each entity should have type"
                assert "word" in entity, "Each entity should have text"
                assert "score" in entity, "Each entity should have confidence score"

    def test_pass_d_deduplication(self):
        """HARD GATE: Test chunk deduplication and fragment merging"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Mock chunks with duplicates and small fragments
        mock_chunks = [
            {
                "text": "Fireball is a 3rd-level spell",
                "page": 242,
                "chunk_id": "chunk_001",
                "type": "NarrativeText"
            },
            {
                "text": "Fireball is a 3rd-level spell",  # Exact duplicate
                "page": 242,
                "chunk_id": "chunk_002",
                "type": "NarrativeText"
            },
            {
                "text": "Short text",  # Small fragment
                "page": 243,
                "chunk_id": "chunk_003",
                "type": "NarrativeText"
            },
            {
                "text": "Another short piece",  # Small fragment
                "page": 243,
                "chunk_id": "chunk_004",
                "type": "NarrativeText"
            }
        ]

        # Test deduplication
        deduplicated_chunks = process_pass_d(mock_chunks)

        # Verify deduplication results
        assert isinstance(deduplicated_chunks, list), "Result should be a list"
        assert len(deduplicated_chunks) < len(mock_chunks), "Should reduce chunk count through deduplication"

        # Verify no exact duplicates remain
        texts = [chunk["text"] for chunk in deduplicated_chunks]
        assert len(texts) == len(set(texts)), "No duplicate texts should remain"

    def test_pass_d_vector_storage_format(self):
        """HARD GATE: Test vector storage format and metadata"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock chunks file
            chunks_file = artifacts_dir / "test_chunks.jsonl"
            mock_chunk = {
                "text": "Test spell description",
                "page": 100,
                "type": "NarrativeText",
                "chunk_id": "test_001"
            }

            with open(chunks_file, 'w') as f:
                f.write(json.dumps(mock_chunk) + '\n')

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pass_c_output": {"chunks_file": "test_chunks.jsonl"},
                "completed_passes": ["A", "B", "C"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock vector operations
            with patch('openai.Embedding.create') as mock_openai:
                mock_openai.return_value = {
                    'data': [{'embedding': np.random.rand(1536).tolist()}]
                }

                # Test vector enrichment
                result = process_pass_d(str(artifacts_dir))

                # Verify vector file was created
                pass_d_output = result["updated_manifest"]["pass_d_output"]
                vectors_file = artifacts_dir / pass_d_output["vectors_file"]
                assert vectors_file.exists(), "Vectors file should be created"

                # Verify vector file content
                with open(vectors_file, 'r') as f:
                    vectorized_chunk = json.loads(f.readline().strip())

                # Verify vectorized chunk structure
                assert "vector" in vectorized_chunk, "Should contain vector"
                assert "vector_id" in vectorized_chunk, "Should contain vector_id"
                assert "chunk_hash" in vectorized_chunk, "Should contain chunk_hash"
                assert "embedding_model" in vectorized_chunk, "Should contain embedding_model"
                assert "entities" in vectorized_chunk, "Should contain extracted entities"
                assert "keywords" in vectorized_chunk, "Should contain keywords"
                assert "stage" in vectorized_chunk, "Should contain processing stage"
                assert vectorized_chunk["stage"] == "vectorized", "Stage should be 'vectorized'"

    def test_pass_d_haystack_version_tracking(self):
        """HARD GATE: Test that Haystack version can be tracked for manifest"""
        try:
            import haystack

            # Should be able to get version information
            version = getattr(haystack, '__version__', None)

            # Version should be available for tracking
            if version is not None:
                assert isinstance(version, str), "Version should be a string"
                assert len(version) > 0, "Version should not be empty"
            else:
                # Some packages store version differently
                try:
                    from importlib.metadata import version as get_version
                    version = get_version('haystack-ai')
                    assert isinstance(version, str), "Version should be a string"
                    assert len(version) > 0, "Version should not be empty"
                except:
                    pytest.skip("Haystack version not accessible through standard methods")

        except ImportError:
            pytest.skip("Haystack not available for version checking")

    def test_pass_d_error_handling(self):
        """HARD GATE: Test that Pass D handles errors gracefully"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            process_pass_d("/nonexistent/artifacts")

        # Test with invalid manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create invalid manifest
            manifest_path = artifacts_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                f.write("invalid json content")

            with pytest.raises(json.JSONDecodeError):
                process_pass_d(str(artifacts_dir))

    def test_pass_d_performance_baseline(self):
        """HARD GATE: Test that Pass D meets performance requirements"""
        try:
            from src_common.pass_d_vector_enrichment import process_pass_d
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        import time

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create small test chunks file
            chunks_file = artifacts_dir / "test_chunks.jsonl"
            mock_chunks = [
                {"text": f"Test chunk {i}", "page": i, "chunk_id": f"chunk_{i:03d}"}
                for i in range(5)  # Small test set
            ]

            with open(chunks_file, 'w') as f:
                for chunk in mock_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pass_c_output": {"chunks_file": "test_chunks.jsonl"},
                "completed_passes": ["A", "B", "C"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock external API calls for performance test
            with patch('openai.Embedding.create') as mock_openai:
                mock_openai.return_value = {
                    'data': [{'embedding': np.random.rand(1536).tolist()} for _ in range(5)]
                }

                # Measure processing time
                start_time = time.time()
                result = process_pass_d(str(artifacts_dir))
                end_time = time.time()

                processing_time = end_time - start_time

                # Should complete within reasonable time (30 seconds for test data)
                assert processing_time < 30.0, f"Pass D took {processing_time:.2f}s, should be < 30s for test data"
                assert isinstance(result, dict), "Should produce valid result"

    def test_pass_d_batch_processing(self):
        """HARD GATE: Test batch processing capabilities for efficiency"""
        try:
            from src_common.pass_d_vector_enrichment import process_chunks_in_batches
        except ImportError:
            pytest.skip("Pass D module not available for testing")

        # Create larger chunk set for batch testing
        mock_chunks = [
            {
                "text": f"Test content for chunk number {i}",
                "page": i // 10 + 1,
                "chunk_id": f"chunk_{i:03d}"
            }
            for i in range(50)  # Batch size test
        ]

        # Mock batch embedding API
        with patch('openai.Embedding.create') as mock_openai:
            # Configure mock for batch responses
            mock_openai.return_value = {
                'data': [{'embedding': np.random.rand(1536).tolist()} for _ in range(50)]
            }

            # Test batch processing
            processed_chunks = process_chunks_in_batches(mock_chunks, batch_size=10)

            # Verify batch processing results
            assert isinstance(processed_chunks, list), "Result should be a list"
            assert len(processed_chunks) == 50, "Should process all chunks"

            # Verify API was called efficiently (should be 5 calls for 50 chunks with batch_size=10)
            assert mock_openai.call_count <= 5, "Should use batch processing to minimize API calls"