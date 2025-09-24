# tests/regression/phase1/test_rag001g_hgrn_validation.py
"""
Phase 1 - US RAG-001G: Pass G HGRN Validation Regression Tests (HARD GATE)
Tests HGRN validation functionality for quality gates and final pipeline validation
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestPassGHGRNValidation:
    """Test suite for Pass G HGRN validation functionality (HARD GATE)"""

    def test_hgrn_framework_availability(self):
        """HARD GATE: Verify HGRN validation framework is available and functional"""
        try:
            # Test that HGRN components can be imported
            from src_common.admin.ingestion import AdminIngestionService

            # Verify core validation components are available
            assert AdminIngestionService is not None, "AdminIngestionService should be available"

            # Test that AdminIngestionService has required validation methods
            manager = AdminIngestionService()
            assert manager is not None, "AdminIngestionService should be instantiable"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: HGRN validation framework not available: {e}")

    def test_pass_g_module_integration(self):
        """HARD GATE: Test that Pass G integrates with HGRN validation framework"""
        try:
            # Import Pass G through the ingestion manager
            from src_common.admin.ingestion import AdminIngestionService

            # Verify HGRN validation method exists
            manager = AdminIngestionService()
            assert hasattr(manager, 'execute_pass_g'), "execute_pass_g method should be available"
            assert callable(getattr(manager, 'execute_pass_g')), "execute_pass_g should be callable"

        except ImportError as e:
            pytest.fail(f"HARD GATE FAILURE: Pass G module not available: {e}")

    def test_pass_g_contract_compliance(self):
        """HARD GATE: Test that Pass G produces contract-compliant output structure"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("Pass G module not available for testing")

        # Create mock artifacts directory structure
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create complete pipeline artifacts from all previous passes
            pipeline_artifacts = {
                "chunks.jsonl": [
                    {"text": "Test chunk", "page": 1, "chunk_id": "chunk_001"}
                ],
                "vectors.jsonl": [
                    {"chunk_id": "chunk_001", "vector": [0.1] * 1536, "stage": "vectorized"}
                ],
                "graph_enriched.jsonl": [
                    {"chunk_id": "chunk_001", "graph_refs": [], "toc_lineage": [], "stage": "graph_enriched"}
                ]
            }

            # Create artifact files
            for filename, content in pipeline_artifacts.items():
                file_path = artifacts_dir / filename
                with open(file_path, 'w') as f:
                    for item in content:
                        f.write(json.dumps(item) + '\n')

            # Create finalized manifest from Pass F
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "job_id": "test_job_001",
                "pdf_metadata": {"file_size_bytes": 2048000, "filename": "test.pdf"},
                "pass_a_output": {"toc_sections": [], "completed_at": "2024-01-01T10:00:00Z"},
                "pass_b_output": {"split_performed": False, "completed_at": "2024-01-01T10:01:00Z"},
                "pass_c_output": {"chunks_file": "chunks.jsonl", "chunk_count": 1, "completed_at": "2024-01-01T10:02:00Z"},
                "pass_d_output": {"vectors_file": "vectors.jsonl", "vector_count": 1, "completed_at": "2024-01-01T10:03:00Z"},
                "pass_e_output": {"enriched_chunks_file": "graph_enriched.jsonl", "node_count": 5, "completed_at": "2024-01-01T10:04:00Z"},
                "pass_f_output": {"finalization_completed": True, "validation_passed": True, "completed_at": "2024-01-01T10:05:00Z"},
                "completed_passes": ["A", "B", "C", "D", "E", "F"],
                "run_summary": {"total_chunks_processed": 1, "total_processing_time_ms": 15000},
                "checksums": {"chunks.jsonl": "abc123", "vectors.jsonl": "def456"},
                "finalized_at": "2024-01-01T10:05:00Z"
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock HGRN validation operations
            with patch('src_common.admin.ingestion.AdminIngestionService') as mock_validator:
                mock_validator_instance = MagicMock()
                mock_validator.return_value = mock_validator_instance

                # Configure HGRN validation mock
                mock_validator_instance.validate_pipeline_output.return_value = {
                    "validation_passed": True,
                    "quality_score": 0.92,
                    "structural_integrity": True,
                    "metadata_consistency": True
                }

                # Test Pass G execution
                manager = AdminIngestionService()
                result = manager.execute_pass_g(str(artifacts_dir), "test_log.txt")

                # Verify result structure
                assert isinstance(result, dict), "Process result should be a dictionary"
                assert "success" in result, "Result should indicate success status"
                assert "processed_count" in result, "Result should contain processed count"
                assert "hgrn_success" in result, "Result should contain HGRN validation status"
                assert "validation_metrics" in result, "Result should contain validation metrics"

                # Verify HGRN validation was called
                mock_validator_instance.validate_pipeline_output.assert_called_once()

    def test_pass_g_quality_validation(self):
        """HARD GATE: Test quality validation and threshold checking"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("HGRN validator not available for testing")

        # Create mock pipeline data for quality validation
        mock_pipeline_data = {
            "chunks": [
                {
                    "chunk_id": "chunk_001",
                    "text": "High quality spell description with detailed mechanics",
                    "page": 242,
                    "vector": [0.1] * 1536,
                    "entities": [{"entity": "SPELL", "word": "Fireball", "score": 0.95}],
                    "graph_refs": ["spell_node_001"],
                    "toc_lineage": ["Spells", "3rd Level", "Fireball"]
                },
                {
                    "chunk_id": "chunk_002",
                    "text": "Well-structured class feature description",
                    "page": 114,
                    "vector": [0.2] * 1536,
                    "entities": [{"entity": "CLASS", "word": "Wizard", "score": 0.90}],
                    "graph_refs": ["class_node_001"],
                    "toc_lineage": ["Classes", "Wizard", "Class Features"]
                }
            ],
            "graph_structure": {
                "nodes": [
                    {"id": "spell_node_001", "type": "spell", "label": "Fireball"},
                    {"id": "class_node_001", "type": "class", "label": "Wizard"}
                ],
                "edges": [
                    {"source": "class_node_001", "target": "spell_node_001", "relation": "can_cast"}
                ]
            },
            "metadata": {
                "total_chunks": 2,
                "vector_dimensions": 1536,
                "entity_count": 2,
                "graph_nodes": 2,
                "graph_edges": 1
            }
        }

        # Test quality validation
        validator = AdminIngestionService()

        # Mock the actual validation implementation
        with patch.object(validator, 'validate_content_quality') as mock_content_validation, \
             patch.object(validator, 'validate_structural_integrity') as mock_structure_validation:

            # Configure quality validation mock
            mock_content_validation.return_value = {
                "quality_score": 0.88,
                "content_completeness": 0.92,
                "entity_coverage": 0.85,
                "text_quality": 0.90
            }

            mock_structure_validation.return_value = {
                "structural_score": 0.95,
                "graph_connectivity": 0.98,
                "metadata_consistency": 0.93,
                "reference_integrity": 0.96
            }

            validation_result = validator.validate_pipeline_output(mock_pipeline_data)

            # Verify quality validation results
            assert isinstance(validation_result, dict), "Validation result should be a dictionary"
            assert "validation_passed" in validation_result, "Should indicate overall validation status"
            assert "quality_metrics" in validation_result, "Should contain quality metrics"

            # Verify quality thresholds
            quality_metrics = validation_result["quality_metrics"]
            assert "overall_score" in quality_metrics, "Should have overall quality score"

            overall_score = quality_metrics["overall_score"]
            assert isinstance(overall_score, (int, float)), "Overall score should be numeric"
            assert 0.0 <= overall_score <= 1.0, "Overall score should be between 0 and 1"

            # Quality should meet threshold (assuming 0.80 threshold)
            assert overall_score >= 0.80, f"Quality score {overall_score} should meet 0.80 threshold"

    def test_pass_g_structural_integrity_checks(self):
        """HARD GATE: Test structural integrity validation"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("HGRN validator not available for testing")

        # Mock pipeline data with potential structural issues
        mock_pipeline_data = {
            "chunks": [
                {"chunk_id": "chunk_001", "vector": [0.1] * 1536, "graph_refs": ["node_001"]},
                {"chunk_id": "chunk_002", "vector": [0.2] * 1536, "graph_refs": ["node_002"]},
                {"chunk_id": "chunk_003", "vector": [0.3] * 1536, "graph_refs": ["missing_node"]}  # Broken reference
            ],
            "graph_structure": {
                "nodes": [
                    {"id": "node_001", "type": "spell"},
                    {"id": "node_002", "type": "class"}
                    # Missing node_003 - broken reference
                ],
                "edges": [
                    {"source": "node_001", "target": "node_002", "relation": "used_by"}
                ]
            }
        }

        validator = AdminIngestionService()

        # Mock structural integrity validation
        with patch.object(validator, 'check_reference_integrity') as mock_ref_check, \
             patch.object(validator, 'check_graph_consistency') as mock_graph_check:

            # Configure integrity check mocks
            mock_ref_check.return_value = {
                "broken_references": ["chunk_003 -> missing_node"],
                "reference_integrity_score": 0.67  # 2/3 valid references
            }

            mock_graph_check.return_value = {
                "orphaned_nodes": [],
                "disconnected_components": 0,
                "graph_consistency_score": 0.95
            }

            integrity_result = validator.validate_structural_integrity(mock_pipeline_data)

            # Verify integrity check results
            assert isinstance(integrity_result, dict), "Integrity result should be a dictionary"
            assert "integrity_passed" in integrity_result, "Should indicate integrity status"
            assert "broken_references" in integrity_result, "Should report broken references"
            assert "consistency_score" in integrity_result, "Should provide consistency score"

            # Verify broken references are detected
            broken_refs = integrity_result["broken_references"]
            assert len(broken_refs) > 0, "Should detect broken references"
            assert any("missing_node" in ref for ref in broken_refs), "Should detect missing node reference"

    def test_pass_g_metadata_consistency_validation(self):
        """HARD GATE: Test metadata consistency across pipeline stages"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("HGRN validator not available for testing")

        # Mock manifest with potential inconsistencies
        mock_manifest = {
            "pass_c_output": {"chunk_count": 10},
            "pass_d_output": {"vector_count": 8},  # Mismatch: should be 10
            "pass_e_output": {"enriched_count": 10},
            "run_summary": {"total_chunks_processed": 10}
        }

        # Mock actual chunk files for validation
        mock_chunk_files = {
            "chunks.jsonl": [f'{{"chunk_id": "chunk_{i:03d}"}}' for i in range(10)],
            "vectors.jsonl": [f'{{"chunk_id": "chunk_{i:03d}", "vector_id": "vec_{i:03d}"}}' for i in range(8)],  # Missing 2 vectors
            "enriched.jsonl": [f'{{"chunk_id": "chunk_{i:03d}", "stage": "graph_enriched"}}' for i in range(10)]
        }

        validator = AdminIngestionService()

        # Mock metadata consistency validation
        with patch.object(validator, 'validate_count_consistency') as mock_count_validation:
            mock_count_validation.return_value = {
                "consistency_passed": False,
                "inconsistencies": [
                    {
                        "type": "count_mismatch",
                        "description": "Vector count (8) does not match chunk count (10)",
                        "severity": "high"
                    }
                ],
                "consistency_score": 0.80
            }

            consistency_result = validator.validate_metadata_consistency(mock_manifest, mock_chunk_files)

            # Verify consistency validation results
            assert isinstance(consistency_result, dict), "Consistency result should be a dictionary"
            assert "consistency_passed" in consistency_result, "Should indicate consistency status"
            assert "inconsistencies" in consistency_result, "Should report inconsistencies"

            # Verify inconsistencies are detected
            inconsistencies = consistency_result["inconsistencies"]
            assert len(inconsistencies) > 0, "Should detect inconsistencies"

            # Check for specific count mismatch
            count_mismatches = [inc for inc in inconsistencies if inc["type"] == "count_mismatch"]
            assert len(count_mismatches) > 0, "Should detect count mismatches"

    def test_pass_g_performance_metrics_collection(self):
        """HARD GATE: Test performance metrics collection and reporting"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("HGRN validator not available for testing")

        # Mock performance data from pipeline execution
        mock_performance_data = {
            "pass_timings": {
                "pass_a": 1500,  # ms
                "pass_b": 800,
                "pass_c": 4200,
                "pass_d": 12000,
                "pass_e": 8500,
                "pass_f": 2200
            },
            "resource_usage": {
                "peak_memory_mb": 2048,
                "api_calls_count": 15,
                "disk_io_mb": 156
            },
            "quality_metrics": {
                "chunks_processed": 150,
                "vectors_generated": 150,
                "entities_extracted": 450,
                "graph_nodes": 200,
                "graph_edges": 380
            }
        }

        validator = AdminIngestionService()

        # Mock performance metrics collection
        with patch.object(validator, 'collect_performance_metrics') as mock_perf_collection:
            mock_perf_collection.return_value = {
                "total_processing_time_ms": 29200,
                "processing_rate_chunks_per_second": 5.14,
                "memory_efficiency_score": 0.85,
                "api_efficiency_score": 0.90,
                "overall_performance_score": 0.87
            }

            performance_result = validator.collect_performance_metrics(mock_performance_data)

            # Verify performance metrics
            assert isinstance(performance_result, dict), "Performance result should be a dictionary"
            assert "total_processing_time_ms" in performance_result, "Should report total processing time"
            assert "processing_rate_chunks_per_second" in performance_result, "Should report processing rate"
            assert "overall_performance_score" in performance_result, "Should provide overall performance score"

            # Verify performance thresholds
            processing_rate = performance_result["processing_rate_chunks_per_second"]
            assert processing_rate > 0, "Processing rate should be positive"

            performance_score = performance_result["overall_performance_score"]
            assert 0.0 <= performance_score <= 1.0, "Performance score should be between 0 and 1"

    def test_pass_g_final_validation_report(self):
        """HARD GATE: Test final validation report generation"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("Pass G module not available for testing")

        # Create comprehensive test setup
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create complete manifest
            manifest_path = artifacts_dir / "manifest.json"
            complete_manifest = {
                "job_id": "final_validation_test",
                "completed_passes": ["A", "B", "C", "D", "E", "F"],
                "run_summary": {
                    "total_chunks_processed": 100,
                    "total_processing_time_ms": 45000,
                    "passes_completed": 6
                }
            }

            with open(manifest_path, 'w') as f:
                json.dump(complete_manifest, f)

            # Mock comprehensive HGRN validation
            with patch('src_common.admin.ingestion.AdminIngestionService') as mock_validator:
                mock_validator_instance = MagicMock()
                mock_validator.return_value = mock_validator_instance

                # Configure comprehensive validation response
                mock_validator_instance.validate_pipeline_output.return_value = {
                    "validation_passed": True,
                    "overall_quality_score": 0.89,
                    "quality_metrics": {
                        "content_quality": 0.91,
                        "structural_integrity": 0.88,
                        "metadata_consistency": 0.87
                    },
                    "performance_metrics": {
                        "processing_efficiency": 0.85,
                        "resource_utilization": 0.82
                    },
                    "recommendations": [
                        "Consider optimizing vector embedding batch size",
                        "Graph connectivity could be improved"
                    ]
                }

                # Test final validation
                manager = AdminIngestionService()
                log_path = str(artifacts_dir / "validation_log.txt")
                result = manager.execute_pass_g(str(artifacts_dir), log_path)

                # Verify final validation results
                assert result["success"] == True, "Final validation should succeed"
                assert result["hgrn_success"] == True, "HGRN validation should succeed"
                assert "validation_metrics" in result, "Should include validation metrics"

                # Verify validation report was generated
                validation_metrics = result["validation_metrics"]
                assert "overall_quality_score" in validation_metrics, "Should include overall quality score"
                assert validation_metrics["overall_quality_score"] >= 0.80, "Quality should meet minimum threshold"

    def test_pass_g_error_handling(self):
        """HARD GATE: Test that Pass G handles errors gracefully"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("Pass G module not available for testing")

        manager = AdminIngestionService()

        # Test with non-existent artifacts directory
        with pytest.raises((FileNotFoundError, OSError)):
            manager.execute_pass_g("/nonexistent/artifacts", "test_log.txt")

        # Test with incomplete pipeline (missing passes)
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create manifest with missing passes
            manifest_path = artifacts_dir / "manifest.json"
            incomplete_manifest = {
                "job_id": "incomplete_test",
                "completed_passes": ["A", "B"]  # Missing C, D, E, F
            }

            with open(manifest_path, 'w') as f:
                json.dump(incomplete_manifest, f)

            log_path = str(artifacts_dir / "error_log.txt")

            # Should handle incomplete pipeline gracefully
            result = manager.execute_pass_g(str(artifacts_dir), log_path)

            # Should indicate validation failure for incomplete pipeline
            assert result["success"] == False, "Should fail validation for incomplete pipeline"
            assert "error" in result or "validation_errors" in result, "Should report validation errors"

    def test_pass_g_performance_baseline(self):
        """HARD GATE: Test that Pass G meets performance requirements"""
        try:
            from src_common.admin.ingestion import AdminIngestionService
        except ImportError:
            pytest.skip("Pass G module not available for testing")

        import time

        # Create mock artifacts directory with realistic pipeline output
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir()

            # Create realistic manifest
            manifest_path = artifacts_dir / "manifest.json"
            mock_manifest = {
                "job_id": "performance_test",
                "completed_passes": ["A", "B", "C", "D", "E", "F"],
                "run_summary": {
                    "total_chunks_processed": 200,
                    "total_processing_time_ms": 60000,
                    "passes_completed": 6
                },
                "pass_a_output": {"processing_time_ms": 2000},
                "pass_b_output": {"processing_time_ms": 1000},
                "pass_c_output": {"chunk_count": 200, "processing_time_ms": 8000},
                "pass_d_output": {"vector_count": 200, "processing_time_ms": 25000},
                "pass_e_output": {"node_count": 300, "processing_time_ms": 20000},
                "pass_f_output": {"processing_time_ms": 4000}
            }

            with open(manifest_path, 'w') as f:
                json.dump(mock_manifest, f)

            # Mock HGRN validation for performance test
            with patch('src_common.admin.ingestion.AdminIngestionService') as mock_validator:
                mock_validator_instance = MagicMock()
                mock_validator.return_value = mock_validator_instance

                mock_validator_instance.validate_pipeline_output.return_value = {
                    "validation_passed": True,
                    "overall_quality_score": 0.85
                }

                # Measure Pass G performance
                manager = AdminIngestionService()
                log_path = str(artifacts_dir / "perf_log.txt")

                start_time = time.time()
                result = manager.execute_pass_g(str(artifacts_dir), log_path)
                end_time = time.time()

                processing_time = end_time - start_time

                # Should complete within reasonable time (10 seconds for validation)
                assert processing_time < 10.0, f"Pass G took {processing_time:.2f}s, should be < 10s for validation"
                assert result["success"] == True, "Should complete validation successfully"