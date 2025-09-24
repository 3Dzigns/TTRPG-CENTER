# tests/regression/phase1/test_lane_a_integration.py
"""
Phase 1 - Lane A Integration Tests: Complete 7-Pass Pipeline Flow (HARD GATE)
Tests the complete ingestion pipeline (A→B→C→D→E→F→G) as an integrated system
"""

import json
import pytest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLaneAIntegration:
    """Test suite for complete Lane A pipeline integration (HARD GATE)"""

    def test_lane_a_pipeline_availability(self):
        """HARD GATE: Verify all Lane A pipeline components are available"""
        try:
            # Test that all pass modules can be imported
            from src_common.pass_a_toc_parser import process_pdf_parsing
            from src_common.pass_b_logical_splitter import process_logical_split
            from src_common.pass_c_extraction import process_extraction
            from src_common.pass_d_vector_enrichment import process_vector_enrichment
            from src_common.pass_e_graph_builder import process_graph_building
            from src_common.pass_f_finalizer import process_finalization
            from src_common.admin.ingestion import IngestionManager

            # Verify all functions are callable
            assert callable(process_pdf_parsing), "Pass A should be available"
            assert callable(process_logical_split), "Pass B should be available"
            assert callable(process_extraction), "Pass C should be available"
            assert callable(process_vector_enrichment), "Pass D should be available"
            assert callable(process_graph_building), "Pass E should be available"
            assert callable(process_finalization), "Pass F should be available"

            # Verify Pass G through IngestionManager
            manager = IngestionManager()
            assert hasattr(manager, 'execute_pass_g'), "Pass G should be available"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Lane A pipeline components not available: {e}")

    def test_lane_a_sequential_execution(self):
        """HARD GATE: Test sequential execution of all 7 passes (A→B→C→D→E→F→G)"""
        # Create mock artifacts directory for full pipeline test
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create mock PDF file
            test_pdf_path = artifacts_dir / "test_document.pdf"
            with open(test_pdf_path, 'wb') as f:
                # Create small PDF content (under 25MB threshold)
                pdf_content = b"%PDF-1.4\n" + b"Content " * 1000 + b"\n%%EOF"
                f.write(pdf_content)

            # Initialize manifest for pipeline tracking
            manifest_path = artifacts_dir / "manifest.json"
            initial_manifest = {
                "job_id": "lane_a_integration_test",
                "pdf_metadata": {
                    "filename": "test_document.pdf",
                    "file_size_bytes": len(pdf_content)
                },
                "created_at": "2024-01-01T10:00:00Z",
                "completed_passes": []
            }

            with open(manifest_path, 'w') as f:
                json.dump(initial_manifest, f)

            # Mock external dependencies for all passes
            with patch('unstructured.partition.auto.partition') as mock_unstructured, \
                 patch('pypdf.PdfReader') as mock_pypdf, \
                 patch('openai.Embedding.create') as mock_openai, \
                 patch('llama_index.core.VectorStoreIndex') as mock_llamaindex, \
                 patch('src_common.hgrn_validator.HGRNValidator') as mock_hgrn:

                # Configure Pass A mock (unstructured.io)
                mock_element = MagicMock()
                mock_element.text = "Test content from PDF"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_unstructured.return_value = [mock_element]

                # Configure Pass B mock (PyPDF)
                mock_pypdf_instance = MagicMock()
                mock_pypdf.return_value = mock_pypdf_instance
                mock_pypdf_instance.pages = [MagicMock()]

                # Configure Pass D mock (OpenAI embeddings)
                mock_openai.return_value = {
                    'data': [{'embedding': [0.1] * 1536}]
                }

                # Configure Pass E mock (LlamaIndex)
                mock_llamaindex_instance = MagicMock()
                mock_llamaindex.from_documents.return_value = mock_llamaindex_instance

                # Configure Pass G mock (HGRN validation)
                mock_hgrn_instance = MagicMock()
                mock_hgrn.return_value = mock_hgrn_instance
                mock_hgrn_instance.validate_pipeline_output.return_value = {
                    "validation_passed": True,
                    "overall_quality_score": 0.90
                }

                # Execute complete pipeline sequentially
                pipeline_results = {}

                # Pass A: PDF parsing and ToC extraction
                from src_common.pass_a_toc_parser import process_pdf_parsing
                result_a = process_pdf_parsing(str(artifacts_dir))
                pipeline_results["pass_a"] = result_a

                # Verify Pass A results and manifest update
                assert isinstance(result_a, dict), "Pass A should return dictionary"
                assert "updated_manifest" in result_a, "Pass A should update manifest"
                assert "A" in result_a["updated_manifest"]["completed_passes"], "Pass A should mark completion"

                # Update manifest file with Pass A results
                with open(manifest_path, 'w') as f:
                    json.dump(result_a["updated_manifest"], f)

                # Pass B: Logical splitting (should be no-op for small file)
                from src_common.pass_b_logical_splitter import process_logical_split
                result_b = process_logical_split(str(artifacts_dir))
                pipeline_results["pass_b"] = result_b

                # Verify Pass B results
                assert isinstance(result_b, dict), "Pass B should return dictionary"
                assert "B" in result_b["updated_manifest"]["completed_passes"], "Pass B should mark completion"

                # Update manifest
                with open(manifest_path, 'w') as f:
                    json.dump(result_b["updated_manifest"], f)

                # Pass C: Content extraction and chunking
                from src_common.pass_c_extraction import process_extraction
                result_c = process_extraction(str(artifacts_dir))
                pipeline_results["pass_c"] = result_c

                # Verify Pass C results
                assert isinstance(result_c, dict), "Pass C should return dictionary"
                assert "C" in result_c["updated_manifest"]["completed_passes"], "Pass C should mark completion"

                # Update manifest
                with open(manifest_path, 'w') as f:
                    json.dump(result_c["updated_manifest"], f)

                # Pass D: Vector enrichment
                from src_common.pass_d_vector_enrichment import process_vector_enrichment
                result_d = process_vector_enrichment(str(artifacts_dir))
                pipeline_results["pass_d"] = result_d

                # Verify Pass D results
                assert isinstance(result_d, dict), "Pass D should return dictionary"
                assert "D" in result_d["updated_manifest"]["completed_passes"], "Pass D should mark completion"

                # Update manifest
                with open(manifest_path, 'w') as f:
                    json.dump(result_d["updated_manifest"], f)

                # Pass E: Graph building
                from src_common.pass_e_graph_builder import process_graph_building
                result_e = process_graph_building(str(artifacts_dir))
                pipeline_results["pass_e"] = result_e

                # Verify Pass E results
                assert isinstance(result_e, dict), "Pass E should return dictionary"
                assert "E" in result_e["updated_manifest"]["completed_passes"], "Pass E should mark completion"

                # Update manifest
                with open(manifest_path, 'w') as f:
                    json.dump(result_e["updated_manifest"], f)

                # Pass F: Finalization
                from src_common.pass_f_finalizer import process_finalization
                result_f = process_finalization(str(artifacts_dir))
                pipeline_results["pass_f"] = result_f

                # Verify Pass F results
                assert isinstance(result_f, dict), "Pass F should return dictionary"
                assert "F" in result_f["updated_manifest"]["completed_passes"], "Pass F should mark completion"
                assert result_f["finalization_completed"] == True, "Pass F should complete finalization"

                # Update manifest
                with open(manifest_path, 'w') as f:
                    json.dump(result_f["updated_manifest"], f)

                # Pass G: HGRN validation
                from src_common.admin.ingestion import IngestionManager
                manager = IngestionManager()
                log_path = str(artifacts_dir / "lane_a_test.log")
                result_g = manager.execute_pass_g(str(artifacts_dir), log_path)
                pipeline_results["pass_g"] = result_g

                # Verify Pass G results
                assert isinstance(result_g, dict), "Pass G should return dictionary"
                assert result_g["success"] == True, "Pass G should succeed"
                assert result_g["hgrn_success"] == True, "Pass G HGRN validation should succeed"

                # Verify complete pipeline execution
                assert len(pipeline_results) == 7, "All 7 passes should execute"

                # Verify final manifest contains all passes
                final_manifest = result_f["updated_manifest"]
                expected_passes = ["A", "B", "C", "D", "E", "F"]
                for pass_letter in expected_passes:
                    assert pass_letter in final_manifest["completed_passes"], f"Pass {pass_letter} should be completed"

    def test_lane_a_data_flow_integrity(self):
        """HARD GATE: Test data flow integrity between passes"""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create test data that flows through the pipeline
            test_chunks = [
                {
                    "text": "Fireball is a 3rd-level evocation spell",
                    "page": 242,
                    "chunk_id": "chunk_001",
                    "section": "Spells"
                }
            ]

            # Create initial chunks file (simulating Pass C output)
            chunks_file = artifacts_dir / "chunks.jsonl"
            with open(chunks_file, 'w') as f:
                for chunk in test_chunks:
                    f.write(json.dumps(chunk) + '\n')

            # Create manifest tracking the data
            manifest_path = artifacts_dir / "manifest.json"
            manifest = {
                "job_id": "data_flow_test",
                "pass_c_output": {"chunks_file": "chunks.jsonl", "chunk_count": 1},
                "completed_passes": ["A", "B", "C"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)

            # Mock dependencies for data flow test
            with patch('openai.Embedding.create') as mock_openai, \
                 patch('llama_index.core.VectorStoreIndex') as mock_llamaindex:

                # Configure vector embedding mock
                mock_openai.return_value = {
                    'data': [{'embedding': [0.1, 0.2, 0.3] * 512}]  # 1536-dim vector
                }

                # Configure graph building mock
                mock_llamaindex_instance = MagicMock()
                mock_llamaindex.from_documents.return_value = mock_llamaindex_instance

                # Test Pass D: Vector enrichment
                from src_common.pass_d_vector_enrichment import process_vector_enrichment
                result_d = process_vector_enrichment(str(artifacts_dir))

                # Verify Pass D enriched the data
                assert "pass_d_output" in result_d["updated_manifest"], "Pass D should add output to manifest"
                pass_d_output = result_d["updated_manifest"]["pass_d_output"]
                assert "vectors_file" in pass_d_output, "Pass D should create vectors file"

                # Verify vectors file was created and contains enriched data
                vectors_file = artifacts_dir / pass_d_output["vectors_file"]
                assert vectors_file.exists(), "Vectors file should be created"

                with open(vectors_file, 'r') as f:
                    vectorized_chunk = json.loads(f.readline().strip())

                # Verify data enrichment
                assert "vector" in vectorized_chunk, "Chunk should have vector"
                assert "vector_id" in vectorized_chunk, "Chunk should have vector ID"
                assert "stage" in vectorized_chunk, "Chunk should have processing stage"
                assert vectorized_chunk["stage"] == "vectorized", "Stage should be 'vectorized'"
                assert vectorized_chunk["chunk_id"] == "chunk_001", "Chunk ID should be preserved"
                assert vectorized_chunk["text"] == test_chunks[0]["text"], "Text should be preserved"

                # Update manifest for next pass
                with open(manifest_path, 'w') as f:
                    json.dump(result_d["updated_manifest"], f)

                # Test Pass E: Graph building
                from src_common.pass_e_graph_builder import process_graph_building
                result_e = process_graph_building(str(artifacts_dir))

                # Verify Pass E further enriched the data
                assert "pass_e_output" in result_e["updated_manifest"], "Pass E should add output to manifest"
                pass_e_output = result_e["updated_manifest"]["pass_e_output"]
                assert "enriched_chunks_file" in pass_e_output, "Pass E should create enriched chunks file"

                # Verify enriched chunks file
                enriched_file = artifacts_dir / pass_e_output["enriched_chunks_file"]
                assert enriched_file.exists(), "Enriched chunks file should be created"

                with open(enriched_file, 'r') as f:
                    graph_enriched_chunk = json.loads(f.readline().strip())

                # Verify graph enrichment preserves and enhances data
                assert "graph_refs" in graph_enriched_chunk, "Chunk should have graph references"
                assert "toc_lineage" in graph_enriched_chunk, "Chunk should have ToC lineage"
                assert "stage" in graph_enriched_chunk, "Chunk should have processing stage"
                assert graph_enriched_chunk["stage"] == "graph_enriched", "Stage should be 'graph_enriched'"
                assert graph_enriched_chunk["chunk_id"] == "chunk_001", "Chunk ID should be preserved through pipeline"

                # Verify all original data is preserved
                assert graph_enriched_chunk["text"] == test_chunks[0]["text"], "Original text should be preserved"
                assert graph_enriched_chunk["page"] == test_chunks[0]["page"], "Original page should be preserved"

    def test_lane_a_error_recovery(self):
        """HARD GATE: Test error recovery and rollback capabilities"""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create manifest with partial completion
            manifest_path = artifacts_dir / "manifest.json"
            partial_manifest = {
                "job_id": "error_recovery_test",
                "pass_a_output": {"toc_sections": [], "completed_at": "2024-01-01T10:00:00Z"},
                "pass_b_output": {"split_performed": False, "completed_at": "2024-01-01T10:01:00Z"},
                "completed_passes": ["A", "B"]
            }

            with open(manifest_path, 'w') as f:
                json.dump(partial_manifest, f)

            # Simulate Pass C failure scenario
            from src_common.pass_c_extraction import process_extraction

            # Test with missing input data (should handle gracefully)
            try:
                result_c = process_extraction(str(artifacts_dir))
                # If it doesn't raise an exception, verify error handling in result
                if isinstance(result_c, dict) and "error" in result_c:
                    assert "error" in result_c, "Should report error gracefully"
                    assert result_c["extraction_performed"] == False, "Should indicate extraction failed"
            except (FileNotFoundError, KeyError) as e:
                # Expected behavior - should raise appropriate exceptions for missing data
                assert "chunks" in str(e).lower() or "file" in str(e).lower(), "Should report missing file/data error"

            # Verify manifest integrity after error
            with open(manifest_path, 'r') as f:
                recovered_manifest = json.load(f)

            # Manifest should still be valid and not corrupted
            assert recovered_manifest["job_id"] == "error_recovery_test", "Job ID should be preserved"
            assert "A" in recovered_manifest["completed_passes"], "Completed passes should be preserved"
            assert "B" in recovered_manifest["completed_passes"], "Completed passes should be preserved"
            assert "C" not in recovered_manifest.get("completed_passes", []), "Failed pass should not be marked complete"

    def test_lane_a_performance_baseline(self):
        """HARD GATE: Test complete pipeline performance baseline"""
        # Note: This is a performance baseline test, not a stress test
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create minimal test data for performance measurement
            test_pdf_content = b"%PDF-1.4\nMinimal test content\n%%EOF"
            test_pdf_path = artifacts_dir / "perf_test.pdf"
            with open(test_pdf_path, 'wb') as f:
                f.write(test_pdf_content)

            # Create initial manifest
            manifest_path = artifacts_dir / "manifest.json"
            manifest = {
                "job_id": "performance_baseline_test",
                "pdf_metadata": {"file_size_bytes": len(test_pdf_content)},
                "completed_passes": []
            }

            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)

            # Mock all external dependencies for consistent performance measurement
            with patch('unstructured.partition.auto.partition') as mock_unstructured, \
                 patch('openai.Embedding.create') as mock_openai, \
                 patch('llama_index.core.VectorStoreIndex') as mock_llamaindex, \
                 patch('src_common.hgrn_validator.HGRNValidator') as mock_hgrn:

                # Configure minimal mocks
                mock_element = MagicMock()
                mock_element.text = "Performance test content"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_unstructured.return_value = [mock_element]

                mock_openai.return_value = {'data': [{'embedding': [0.1] * 1536}]}
                mock_llamaindex.from_documents.return_value = MagicMock()

                mock_hgrn_instance = MagicMock()
                mock_hgrn.return_value = mock_hgrn_instance
                mock_hgrn_instance.validate_pipeline_output.return_value = {
                    "validation_passed": True,
                    "overall_quality_score": 0.85
                }

                # Measure pipeline execution time
                start_time = time.time()

                # Execute passes A through F
                try:
                    from src_common.pass_a_toc_parser import process_pdf_parsing
                    result_a = process_pdf_parsing(str(artifacts_dir))

                    with open(manifest_path, 'w') as f:
                        json.dump(result_a["updated_manifest"], f)

                    from src_common.pass_b_logical_splitter import process_logical_split
                    result_b = process_logical_split(str(artifacts_dir))

                    with open(manifest_path, 'w') as f:
                        json.dump(result_b["updated_manifest"], f)

                    from src_common.pass_c_extraction import process_extraction
                    result_c = process_extraction(str(artifacts_dir))

                    with open(manifest_path, 'w') as f:
                        json.dump(result_c["updated_manifest"], f)

                    from src_common.pass_d_vector_enrichment import process_vector_enrichment
                    result_d = process_vector_enrichment(str(artifacts_dir))

                    with open(manifest_path, 'w') as f:
                        json.dump(result_d["updated_manifest"], f)

                    from src_common.pass_e_graph_builder import process_graph_building
                    result_e = process_graph_building(str(artifacts_dir))

                    with open(manifest_path, 'w') as f:
                        json.dump(result_e["updated_manifest"], f)

                    from src_common.pass_f_finalizer import process_finalization
                    result_f = process_finalization(str(artifacts_dir))

                    # Pass G
                    from src_common.admin.ingestion import IngestionManager
                    manager = IngestionManager()
                    log_path = str(artifacts_dir / "perf_test.log")
                    result_g = manager.execute_pass_g(str(artifacts_dir), log_path)

                    end_time = time.time()
                    total_time = end_time - start_time

                    # Performance baseline: complete pipeline should execute within 2 minutes for minimal test data
                    assert total_time < 120.0, f"Complete pipeline took {total_time:.2f}s, should be < 120s for minimal test data"

                    # Verify all passes completed successfully
                    assert result_f["finalization_completed"] == True, "Finalization should complete"
                    assert result_g["success"] == True, "HGRN validation should succeed"

                except Exception as e:
                    end_time = time.time()
                    total_time = end_time - start_time
                    pytest.fail(f"Pipeline failed after {total_time:.2f}s with error: {e}")

    def test_lane_a_manifest_consistency(self):
        """HARD GATE: Test manifest consistency throughout pipeline execution"""
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Track manifest evolution through pipeline
            manifest_states = []

            # Create initial manifest
            manifest_path = artifacts_dir / "manifest.json"
            initial_manifest = {
                "job_id": "manifest_consistency_test",
                "pdf_metadata": {"filename": "test.pdf", "file_size_bytes": 1024},
                "created_at": "2024-01-01T10:00:00Z",
                "completed_passes": []
            }

            with open(manifest_path, 'w') as f:
                json.dump(initial_manifest, f)
            manifest_states.append(initial_manifest.copy())

            # Mock minimal dependencies
            with patch('unstructured.partition.auto.partition') as mock_unstructured, \
                 patch('openai.Embedding.create') as mock_openai, \
                 patch('llama_index.core.VectorStoreIndex') as mock_llamaindex:

                mock_element = MagicMock()
                mock_element.text = "Consistency test content"
                mock_element.metadata.page_number = 1
                mock_element.category = "NarrativeText"
                mock_unstructured.return_value = [mock_element]

                mock_openai.return_value = {'data': [{'embedding': [0.1] * 1536}]}
                mock_llamaindex.from_documents.return_value = MagicMock()

                # Execute passes and track manifest evolution
                pass_modules = [
                    ("A", "src_common.pass_a_toc_parser", "process_pdf_parsing"),
                    ("B", "src_common.pass_b_logical_splitter", "process_logical_split"),
                    ("C", "src_common.pass_c_extraction", "process_extraction"),
                    ("D", "src_common.pass_d_vector_enrichment", "process_vector_enrichment"),
                    ("E", "src_common.pass_e_graph_builder", "process_graph_building"),
                    ("F", "src_common.pass_f_finalizer", "process_finalization")
                ]

                for pass_letter, module_name, function_name in pass_modules:
                    try:
                        # Import and execute pass
                        module = __import__(module_name, fromlist=[function_name])
                        pass_function = getattr(module, function_name)
                        result = pass_function(str(artifacts_dir))

                        # Update manifest and track state
                        updated_manifest = result["updated_manifest"]
                        with open(manifest_path, 'w') as f:
                            json.dump(updated_manifest, f)
                        manifest_states.append(updated_manifest.copy())

                        # Verify manifest consistency invariants
                        assert updated_manifest["job_id"] == initial_manifest["job_id"], f"Job ID should remain consistent through Pass {pass_letter}"
                        assert updated_manifest["created_at"] == initial_manifest["created_at"], f"Creation time should remain consistent through Pass {pass_letter}"
                        assert pass_letter in updated_manifest["completed_passes"], f"Pass {pass_letter} should be marked as completed"

                        # Verify pass-specific output was added
                        pass_output_key = f"pass_{pass_letter.lower()}_output"
                        assert pass_output_key in updated_manifest, f"Pass {pass_letter} should add {pass_output_key} to manifest"

                        # Verify no regression in previous passes
                        for prev_pass in ["A", "B", "C", "D", "E", "F"]:
                            if prev_pass < pass_letter:  # Only check completed passes
                                assert prev_pass in updated_manifest["completed_passes"], f"Previous pass {prev_pass} should remain marked as completed"

                    except Exception as e:
                        pytest.fail(f"Manifest consistency test failed at Pass {pass_letter}: {e}")

                # Verify final manifest state
                final_manifest = manifest_states[-1]
                expected_passes = ["A", "B", "C", "D", "E", "F"]
                for pass_letter in expected_passes:
                    assert pass_letter in final_manifest["completed_passes"], f"Final manifest should include Pass {pass_letter}"

                # Verify all pass outputs are present
                for pass_letter in expected_passes:
                    pass_output_key = f"pass_{pass_letter.lower()}_output"
                    assert pass_output_key in final_manifest, f"Final manifest should contain {pass_output_key}"

                # Verify run summary is present (added by Pass F)
                assert "run_summary" in final_manifest, "Final manifest should contain run summary"
                assert "finalized_at" in final_manifest, "Final manifest should contain finalization timestamp"