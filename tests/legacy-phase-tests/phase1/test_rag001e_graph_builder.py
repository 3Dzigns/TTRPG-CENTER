# tests/regression/phase1/test_rag001e_graph_builder.py
"""
Phase 1 - US RAG-001E: Pass E Graph Building Regression Tests (HARD GATE)
Tests graph building functionality using LlamaIndex for document graphs and cross-references
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassEGraphBuilder:
    """Test suite for Pass E graph building functionality (HARD GATE)"""

    def test_llamaindex_tool_availability(self):
        """HARD GATE: Verify LlamaIndex tool is available and functional"""
        try:
            # Test that LlamaIndex can be imported
            import llama_index

            # Verify core graph components are available
            from llama_index.core import VectorStoreIndex, Document
            from llama_index.core.node_parser import SimpleNodeParser
            assert VectorStoreIndex is not None, "VectorStoreIndex should be available"
            assert Document is not None, "Document should be available"
            assert SimpleNodeParser is not None, "SimpleNodeParser should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: LlamaIndex not available: {e}")

    def test_pass_e_module_integration(self):
        """HARD GATE: Test that Pass E module exists and integrates with LlamaIndex"""
        try:
            # Import the Pass E module
            from src_common.pass_e_graph_builder import process_pass_e, PassEGraphBuilder

            # Verify functions are available
            assert callable(process_pass_e), "process_pass_e function should be available"
            assert callable(process_pass_e), "process_pass_e function should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass E module not available: {e}")

    def test_pass_e_contract_compliance(self):
        """HARD GATE: Test that Pass E produces contract-compliant output structure"""
        try:
            from src_common.pass_e_graph_builder import process_pass_e
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock vectorized chunks from Pass D
            vectors_file = artifacts_dir / "test_pass_d_vectors.jsonl"
            mock_vectorized_chunks = [
                {
                    "text": "Fireball is a 3rd-level evocation spell that deals fire damage",
                    "page": 242,
                    "type": "NarrativeText",
                    "section": "Spells",
                    "chunk_id": "chunk_001",
                    "vector": [0.1] * 1536,
                    "vector_id": "vec_001",
                    "entities": [{"entity": "SPELL", "word": "Fireball", "score": 0.95}],
                    "keywords": ["fireball", "spell", "evocation"],
                    "stage": "vectorized"
                },
                {
                    "text": "The Wizard class can learn evocation spells like Fireball",
                    "page": 114,
                    "type": "NarrativeText",
                    "section": "Classes",
                    "chunk_id": "chunk_002",
                    "vector": [0.2] * 1536,
                    "vector_id": "vec_002",
                    "entities": [{"entity": "CLASS", "word": "Wizard", "score": 0.92}],
                    "keywords": ["wizard", "class", "evocation"],
                    "stage": "vectorized"
                }
            ]

            with open(vectors_file, 'w') as f:
                for chunk in mock_vectorized_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create mock manifest from previous passes
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pdf_metadata": {"file_size_bytes": 2048000},
                "pass_a_output": {
                    "toc_sections": [
                        {"title": "Spells", "page_start": 240, "page_end": 280},
                        {"title": "Classes", "page_start": 100, "page_end": 140}
                    ]
                },
                "pass_b_output": {"split_performed": False},
                "pass_c_output": {"chunks_file": "test_chunks.jsonl", "chunk_count": 2},
                "pass_d_output": {"vectors_file": "test_pass_d_vectors.jsonl", "vector_count": 2},
                "completed_passes": ["A", "B", "C", "D"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock LlamaIndex operations
            with patch('llama_index.core.VectorStoreIndex') as mock_index, \
                 patch('llama_index.core.Document') as mock_document:

                # Configure LlamaIndex mocks
                mock_index_instance = MagicMock()
                mock_index.from_documents.return_value = mock_index_instance

                mock_doc_instance = MagicMock()
                mock_document.return_value = mock_doc_instance

                # Test process_pass_e function
                result = process_pass_e(str(artifacts_dir))

                # Verify result structure
                assert isinstance(result, dict), "Process result should be a dictionary"
                assert "graph_built" in result, "Result should indicate if graph was built"
                assert "node_count" in result, "Result should contain node count"
                assert "edge_count" in result, "Result should contain edge count"
                assert "updated_manifest" in result, "Result should contain updated manifest"

                # Verify manifest was updated
                updated_manifest = result["updated_manifest"]
                assert "pass_e_output" in updated_manifest, "Manifest should contain Pass E output"
                assert "completed_passes" in updated_manifest, "Manifest should track completed passes"
                assert "E" in updated_manifest["completed_passes"], "Pass E should be marked as completed"

    def test_pass_e_document_graph_structure(self):
        """HARD GATE: Test document graph structure creation (sections→subsections→chunks)"""
        try:
            from src_common.pass_e_graph_builder import process_pass_e
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Mock vectorized chunks with ToC hierarchy
        mock_chunks = [
            {
                "text": "Spells section introduction",
                "section": "Spells",
                "subsection": "Introduction",
                "page": 240,
                "chunk_id": "chunk_001",
                "toc_lineage": ["Spells", "Introduction"]
            },
            {
                "text": "Fireball spell description",
                "section": "Spells",
                "subsection": "3rd Level Spells",
                "page": 242,
                "chunk_id": "chunk_002",
                "toc_lineage": ["Spells", "3rd Level Spells", "Fireball"]
            },
            {
                "text": "Wizard class overview",
                "section": "Classes",
                "subsection": "Wizard",
                "page": 114,
                "chunk_id": "chunk_003",
                "toc_lineage": ["Classes", "Wizard"]
            }
        ]

        # Mock ToC sections for structure
        toc_sections = [
            {"title": "Spells", "page_start": 240, "page_end": 280},
            {"title": "Classes", "page_start": 100, "page_end": 140}
        ]

        # Mock LlamaIndex document graph building
        with patch('llama_index.core.VectorStoreIndex') as mock_index:
            mock_index_instance = MagicMock()
            mock_index.from_documents.return_value = mock_index_instance

            # Test document graph building
            graph_structure = process_pass_e(mock_chunks, toc_sections)

            # Verify graph structure
            assert isinstance(graph_structure, dict), "Graph structure should be a dictionary"
            assert "nodes" in graph_structure, "Graph should contain nodes"
            assert "edges" in graph_structure, "Graph should contain edges"
            assert "hierarchy" in graph_structure, "Graph should contain hierarchy"

            # Verify nodes contain proper types
            nodes = graph_structure["nodes"]
            node_types = {node["type"] for node in nodes}
            assert "section" in node_types, "Should have section nodes"
            assert "chunk" in node_types, "Should have chunk nodes"

            # Verify hierarchical edges exist
            edges = graph_structure["edges"]
            edge_types = {edge["relation"] for edge in edges}
            assert "contains" in edge_types, "Should have containment edges"
            assert "precedes" in edge_types, "Should have sequence edges"

    def test_pass_e_cross_reference_extraction(self):
        """HARD GATE: Test cross-reference extraction (spells ↔ classes/feats/rules)"""
        try:
            from src_common.pass_e_graph_builder import extract_cross_references
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Mock chunks with cross-reference relationships
        mock_chunks = [
            {
                "text": "Fireball is a 3rd-level evocation spell available to Wizards and Sorcerers",
                "section": "Spells",
                "chunk_id": "chunk_001",
                "entities": [
                    {"entity": "SPELL", "word": "Fireball", "score": 0.95},
                    {"entity": "CLASS", "word": "Wizards", "score": 0.90},
                    {"entity": "CLASS", "word": "Sorcerers", "score": 0.88}
                ]
            },
            {
                "text": "The Wizard class gains access to evocation spells at 3rd level",
                "section": "Classes",
                "chunk_id": "chunk_002",
                "entities": [
                    {"entity": "CLASS", "word": "Wizard", "score": 0.92},
                    {"entity": "SCHOOL", "word": "evocation", "score": 0.85}
                ]
            },
            {
                "text": "The Evocation Savant feat enhances evocation spells like Fireball",
                "section": "Feats",
                "chunk_id": "chunk_003",
                "entities": [
                    {"entity": "FEAT", "word": "Evocation Savant", "score": 0.89},
                    {"entity": "SPELL", "word": "Fireball", "score": 0.93}
                ]
            }
        ]

        # Test cross-reference extraction
        cross_references = extract_cross_references(mock_chunks)

        # Verify cross-reference structure
        assert isinstance(cross_references, list), "Cross-references should be a list"
        assert len(cross_references) > 0, "Should extract cross-references"

        # Verify cross-reference format
        for ref in cross_references:
            assert "source_chunk" in ref, "Should have source chunk"
            assert "target_chunk" in ref, "Should have target chunk"
            assert "relation_type" in ref, "Should have relation type"
            assert "confidence" in ref, "Should have confidence score"

        # Verify specific relationships
        relation_types = {ref["relation_type"] for ref in cross_references}
        expected_relations = {"class_casts_spell", "feat_enhances_spell", "spell_school_relation"}
        assert len(relation_types.intersection(expected_relations)) > 0, "Should find expected relationship types"

    def test_pass_e_toc_lineage_creation(self):
        """HARD GATE: Test Table of Contents lineage and section relationships"""
        try:
            from src_common.pass_e_graph_builder import create_toc_lineage
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Mock ToC sections with hierarchy
        toc_sections = [
            {"title": "Chapter 10: Spells", "page_start": 240, "page_end": 280, "level": 1},
            {"title": "3rd Level Spells", "page_start": 242, "page_end": 260, "level": 2, "parent": "Chapter 10: Spells"},
            {"title": "Fireball", "page_start": 242, "page_end": 243, "level": 3, "parent": "3rd Level Spells"},
            {"title": "Chapter 3: Classes", "page_start": 100, "page_end": 140, "level": 1},
            {"title": "Wizard", "page_start": 114, "page_end": 120, "level": 2, "parent": "Chapter 3: Classes"}
        ]

        # Mock chunks for lineage assignment
        mock_chunks = [
            {"text": "Fireball spell description", "page": 242, "chunk_id": "chunk_001"},
            {"text": "Wizard class features", "page": 115, "chunk_id": "chunk_002"}
        ]

        # Test ToC lineage creation
        lineage_map = create_toc_lineage(toc_sections, mock_chunks)

        # Verify lineage structure
        assert isinstance(lineage_map, dict), "Lineage map should be a dictionary"
        assert "chunk_001" in lineage_map, "Should map chunk to lineage"
        assert "chunk_002" in lineage_map, "Should map chunk to lineage"

        # Verify lineage paths
        fireball_lineage = lineage_map["chunk_001"]
        assert isinstance(fireball_lineage, list), "Lineage should be a list"
        assert "Chapter 10: Spells" in fireball_lineage, "Should include chapter"
        assert "3rd Level Spells" in fireball_lineage, "Should include section"
        assert "Fireball" in fireball_lineage, "Should include subsection"

        wizard_lineage = lineage_map["chunk_002"]
        assert "Chapter 3: Classes" in wizard_lineage, "Should include classes chapter"
        assert "Wizard" in wizard_lineage, "Should include wizard section"

    def test_pass_e_graph_metadata_storage(self):
        """HARD GATE: Test graph metadata storage and chunk enrichment"""
        try:
            from src_common.pass_e_graph_builder import process_pass_e
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock vectorized chunks
            vectors_file = artifacts_dir / "vectors.jsonl"
            mock_chunk = {
                "text": "Test spell description with cross-references",
                "page": 100,
                "chunk_id": "test_001",
                "vector": [0.1] * 1536,
                "entities": [{"entity": "SPELL", "word": "TestSpell", "score": 0.9}],
                "stage": "vectorized"
            }

            with open(vectors_file, 'w') as f:
                f.write(json.dumps(mock_chunk) + '\n')

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pass_a_output": {"toc_sections": []},
                "pass_d_output": {"vectors_file": "vectors.jsonl"},
                "completed_passes": ["A", "B", "C", "D"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock LlamaIndex operations
            with patch('llama_index.core.VectorStoreIndex') as mock_index:
                mock_index_instance = MagicMock()
                mock_index.from_documents.return_value = mock_index_instance

                # Test graph building
                result = process_pass_e(str(artifacts_dir))

                # Verify graph metadata files were created
                pass_e_output = result["updated_manifest"]["pass_e_output"]

                graph_file = artifacts_dir / pass_e_output["graph_snapshot_file"]
                assert graph_file.exists(), "Graph snapshot file should be created"

                alias_file = artifacts_dir / pass_e_output.get("alias_map_file", "alias_map.json")
                if alias_file.exists():
                    # Verify alias map content
                    with open(alias_file, 'r') as f:
                        alias_map = json.load(f)
                    assert isinstance(alias_map, dict), "Alias map should be a dictionary"

                # Verify enriched chunks file
                enriched_file = artifacts_dir / pass_e_output["enriched_chunks_file"]
                assert enriched_file.exists(), "Enriched chunks file should be created"

                with open(enriched_file, 'r') as f:
                    enriched_chunk = json.loads(f.readline().strip())

                # Verify chunk enrichment
                assert "graph_refs" in enriched_chunk, "Should contain graph references"
                assert "toc_lineage" in enriched_chunk, "Should contain ToC lineage"
                assert "related_ids" in enriched_chunk, "Should contain related chunk IDs"
                assert "stage" in enriched_chunk, "Should contain processing stage"
                assert enriched_chunk["stage"] == "graph_enriched", "Stage should be 'graph_enriched'"

    def test_pass_e_llamaindex_version_tracking(self):
        """HARD GATE: Test that LlamaIndex version can be tracked for manifest"""
        try:
            import llama_index

            # Should be able to get version information
            version = getattr(llama_index, '__version__', None)

            # Version should be available for tracking
            if version is not None:
                assert isinstance(version, str), "Version should be a string"
                assert len(version) > 0, "Version should not be empty"
            else:
                # Some packages store version differently
                try:
                    from importlib.metadata import version as get_version
                    version = get_version('llama-index')
                    assert isinstance(version, str), "Version should be a string"
                    assert len(version) > 0, "Version should not be empty"
                except:
                    pytest.skip("LlamaIndex version not accessible through standard methods")

        except ImportError:
            pytest.skip("LlamaIndex not available for version checking")

    def test_pass_e_error_handling(self):
        """HARD GATE: Test that Pass E handles errors gracefully"""
        try:
            from src_common.pass_e_graph_builder import process_pass_e
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            process_pass_e("/nonexistent/artifacts")

        # Test with missing vectors file
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create manifest without vectors file
            manifest_path = artifacts_dir / "manifest.json"
            manifest = {"completed_passes": ["A", "B", "C", "D"]}

            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)

            with pytest.raises((FileNotFoundError, KeyError)):
                process_pass_e(str(artifacts_dir))

    def test_pass_e_performance_baseline(self):
        """HARD GATE: Test that Pass E meets performance requirements"""
        try:
            from src_common.pass_e_graph_builder import process_pass_e
        except ImportError:
            pytest.skip("Pass E module not available for testing")

        import time

        # Create mock artifacts directory
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create small test vectors file
            vectors_file = artifacts_dir / "test_vectors.jsonl"
            mock_chunks = [
                {
                    "text": f"Test chunk {i} with entities",
                    "page": i,
                    "chunk_id": f"chunk_{i:03d}",
                    "vector": [0.1 * i] * 1536,
                    "entities": [{"entity": "TEST", "word": f"Entity{i}", "score": 0.9}],
                    "stage": "vectorized"
                }
                for i in range(10)  # Small test set
            ]

            with open(vectors_file, 'w') as f:
                for chunk in mock_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create mock manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "pass_a_output": {"toc_sections": []},
                "pass_d_output": {"vectors_file": "test_vectors.jsonl"},
                "completed_passes": ["A", "B", "C", "D"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock LlamaIndex for performance test
            with patch('llama_index.core.VectorStoreIndex') as mock_index:
                mock_index_instance = MagicMock()
                mock_index.from_documents.return_value = mock_index_instance

                # Measure processing time
                start_time = time.time()
                result = process_pass_e(str(artifacts_dir))
                end_time = time.time()

                processing_time = end_time - start_time

                # Should complete within reasonable time (45 seconds for test data)
                assert processing_time < 45.0, f"Pass E took {processing_time:.2f}s, should be < 45s for test data"
                assert isinstance(result, dict), "Should produce valid result"