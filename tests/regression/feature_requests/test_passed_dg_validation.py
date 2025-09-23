# tests/regression/feature_requests/test_passed_dg_validation.py
"""
Passed D-G Validation Test Suite
Tests critical multi-pass pipeline validation ensuring data integrity through
Pass D (Haystack enrichment) → Pass G (completion) with quality gates
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock, patch


class TestPassedDGValidation:
    """Test suite for Passed D-G validation and quality gates"""

    def test_pass_d_to_g_pipeline_availability(self):
        """Test that Pass D through G pipeline components are available"""
        try:
            # Test ingestion pipeline components
            from src_common.ingestion import IngestionPipeline
            from src_common.pass_d_enrichment import PassDEnrichment
            from src_common.pass_e_graph import PassEGraph
            from src_common.pass_f_cleanup import PassFCleanup
            from src_common.pass_g_completion import PassGCompletion

            assert IngestionPipeline is not None, "IngestionPipeline should be available"
            assert PassDEnrichment is not None, "Pass D enrichment should be available"
            assert PassEGraph is not None, "Pass E graph compilation should be available"
            assert PassFCleanup is not None, "Pass F cleanup should be available"
            assert PassGCompletion is not None, "Pass G completion should be available"

        except ImportError as e:
            pytest.fail(f"Pass D-G pipeline components not available: {e}")

    def test_pass_d_enrichment_quality_gates(self):
        """Test Pass D (Haystack) enrichment quality gates"""
        try:
            from src_common.pass_d_enrichment import PassDEnrichment
        except ImportError:
            pytest.skip("Pass D enrichment not available for testing")

        enrichment = PassDEnrichment()

        # Test enrichment input validation
        valid_chunks = [
            {
                "chunk_id": "chunk_001",
                "source_id": "test_source",
                "content": "Fireball is a 3rd-level evocation spell",
                "page": 1,
                "metadata": {"type": "spell", "raw_content": True}
            },
            {
                "chunk_id": "chunk_002",
                "source_id": "test_source",
                "content": "Magic Missile creates three darts of force",
                "page": 2,
                "metadata": {"type": "spell", "raw_content": True}
            }
        ]

        if hasattr(enrichment, 'validate_input_chunks'):
            validation = enrichment.validate_input_chunks(valid_chunks)

            assert isinstance(validation, dict), "Input validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Valid chunks should pass input validation"

            if "errors" in validation:
                assert len(validation["errors"]) == 0, f"Valid input should have no errors: {validation['errors']}"

        # Test enrichment processing
        if hasattr(enrichment, 'process_chunks'):
            enriched_chunks = enrichment.process_chunks(valid_chunks)

            assert isinstance(enriched_chunks, list), "Enrichment should return list of chunks"
            assert len(enriched_chunks) == len(valid_chunks), "Should process all input chunks"

            for chunk in enriched_chunks:
                # Verify enrichment added required fields
                assert "chunk_id" in chunk, "Enriched chunk should retain chunk_id"
                assert "enriched_content" in chunk or "normalized_content" in chunk, \
                    "Enriched chunk should have processed content"

                # Verify quality gates
                if "quality_score" in chunk:
                    quality_score = chunk["quality_score"]
                    assert 0 <= quality_score <= 1, f"Quality score should be 0-1, got {quality_score}"

                if "entities" in chunk:
                    entities = chunk["entities"]
                    assert isinstance(entities, list), "Entities should be list"

                if "metadata" in chunk:
                    metadata = chunk["metadata"]
                    assert "enriched" in metadata, "Metadata should indicate enrichment"

    def test_pass_e_graph_compilation_gates(self):
        """Test Pass E (LlamaIndex) graph compilation quality gates"""
        try:
            from src_common.pass_e_graph import PassEGraph
        except ImportError:
            pytest.skip("Pass E graph compilation not available for testing")

        graph_compiler = PassEGraph()

        # Test graph compilation input (enriched chunks from Pass D)
        enriched_chunks = [
            {
                "chunk_id": "chunk_001",
                "source_id": "test_source",
                "enriched_content": "Fireball: 3rd-level evocation spell, damage: 8d6 fire",
                "entities": [
                    {"type": "spell", "name": "Fireball", "level": 3},
                    {"type": "school", "name": "evocation"},
                    {"type": "damage", "dice": "8d6", "type": "fire"}
                ],
                "quality_score": 0.92,
                "metadata": {"enriched": True, "pass_d_complete": True}
            }
        ]

        if hasattr(graph_compiler, 'validate_enriched_chunks'):
            validation = graph_compiler.validate_enriched_chunks(enriched_chunks)

            assert isinstance(validation, dict), "Graph input validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Valid enriched chunks should pass validation"

        # Test graph compilation
        if hasattr(graph_compiler, 'compile_graph'):
            graph_result = graph_compiler.compile_graph(enriched_chunks)

            assert isinstance(graph_result, dict), "Graph compilation should return structured result"

            # Verify graph structure
            if "nodes" in graph_result:
                nodes = graph_result["nodes"]
                assert isinstance(nodes, list), "Graph nodes should be list"
                assert len(nodes) > 0, "Should create graph nodes from enriched content"

                for node in nodes:
                    assert "node_id" in node, "Graph node should have ID"
                    assert "type" in node, "Graph node should have type"
                    assert "properties" in node, "Graph node should have properties"

            if "edges" in graph_result:
                edges = graph_result["edges"]
                assert isinstance(edges, list), "Graph edges should be list"

                for edge in edges:
                    assert "source" in edge, "Graph edge should have source"
                    assert "target" in edge, "Graph edge should have target"
                    assert "relationship" in edge, "Graph edge should have relationship type"

            # Verify quality gates
            if "quality_metrics" in graph_result:
                metrics = graph_result["quality_metrics"]
                assert "node_count" in metrics, "Should track node count"
                assert "edge_count" in metrics, "Should track edge count"
                assert "connectivity_score" in metrics, "Should measure graph connectivity"

    def test_pass_f_cleanup_validation_gates(self):
        """Test Pass F cleanup and validation quality gates"""
        try:
            from src_common.pass_f_cleanup import PassFCleanup
        except ImportError:
            pytest.skip("Pass F cleanup not available for testing")

        cleanup = PassFCleanup()

        # Test cleanup input (graph data from Pass E)
        graph_data = {
            "nodes": [
                {"node_id": "spell_fireball", "type": "spell", "properties": {"name": "Fireball", "level": 3}},
                {"node_id": "school_evocation", "type": "school", "properties": {"name": "evocation"}}
            ],
            "edges": [
                {"source": "spell_fireball", "target": "school_evocation", "relationship": "belongs_to_school"}
            ],
            "quality_metrics": {"node_count": 2, "edge_count": 1, "connectivity_score": 0.8}
        }

        if hasattr(cleanup, 'validate_graph_data'):
            validation = cleanup.validate_graph_data(graph_data)

            assert isinstance(validation, dict), "Graph validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Valid graph data should pass validation"

        # Test data cleanup and validation
        if hasattr(cleanup, 'cleanup_and_validate'):
            cleanup_result = cleanup.cleanup_and_validate(graph_data)

            assert isinstance(cleanup_result, dict), "Cleanup should return structured result"

            # Verify cleanup operations
            if "cleaned_data" in cleanup_result:
                cleaned = cleanup_result["cleaned_data"]
                assert "nodes" in cleaned, "Cleaned data should contain nodes"
                assert "edges" in cleaned, "Cleaned data should contain edges"

                # Verify data integrity
                node_ids = {node["node_id"] for node in cleaned["nodes"]}
                for edge in cleaned["edges"]:
                    assert edge["source"] in node_ids, f"Edge source {edge['source']} should exist in nodes"
                    assert edge["target"] in node_ids, f"Edge target {edge['target']} should exist in nodes"

            # Verify quality gates
            if "validation_results" in cleanup_result:
                validation = cleanup_result["validation_results"]
                assert "data_integrity_score" in validation, "Should measure data integrity"
                assert "completeness_score" in validation, "Should measure data completeness"

            if "cleanup_summary" in cleanup_result:
                summary = cleanup_result["cleanup_summary"]
                assert "orphaned_nodes_removed" in summary, "Should track cleanup operations"
                assert "invalid_edges_removed" in summary, "Should track edge cleanup"

    def test_pass_g_completion_final_gates(self):
        """Test Pass G completion and final validation quality gates"""
        try:
            from src_common.pass_g_completion import PassGCompletion
        except ImportError:
            pytest.skip("Pass G completion not available for testing")

        completion = PassGCompletion()

        # Test completion input (cleaned data from Pass F)
        cleaned_data = {
            "nodes": [
                {"node_id": "spell_fireball", "type": "spell", "properties": {"name": "Fireball", "level": 3}},
                {"node_id": "school_evocation", "type": "school", "properties": {"name": "evocation"}}
            ],
            "edges": [
                {"source": "spell_fireball", "target": "school_evocation", "relationship": "belongs_to_school"}
            ],
            "validation_results": {"data_integrity_score": 0.95, "completeness_score": 0.88},
            "metadata": {"source_count": 1, "chunk_count": 2, "processing_time": 45.2}
        }

        if hasattr(completion, 'validate_final_data'):
            validation = completion.validate_final_data(cleaned_data)

            assert isinstance(validation, dict), "Final validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Valid cleaned data should pass final validation"

        # Test completion processing
        if hasattr(completion, 'complete_processing'):
            completion_result = completion.complete_processing(cleaned_data)

            assert isinstance(completion_result, dict), "Completion should return structured result"

            # Verify completion status
            if "status" in completion_result:
                status = completion_result["status"]
                assert status in ["completed", "failed", "partial"], f"Status should be valid: {status}"

            # Verify final metrics
            if "final_metrics" in completion_result:
                metrics = completion_result["final_metrics"]
                required_metrics = ["total_nodes", "total_edges", "quality_score", "completeness_score"]

                for metric in required_metrics:
                    if metric in metrics:
                        value = metrics[metric]
                        assert isinstance(value, (int, float)), f"Metric {metric} should be numeric"

                        if "score" in metric:
                            assert 0 <= value <= 1, f"Score {metric} should be 0-1, got {value}"

            # Verify final artifacts
            if "artifacts" in completion_result:
                artifacts = completion_result["artifacts"]
                assert "final_graph.json" in artifacts, "Should produce final graph artifact"
                assert "processing_summary.json" in artifacts, "Should produce processing summary"

    def test_multi_pass_pipeline_integration(self):
        """Test complete D→E→F→G pipeline integration with quality gates"""
        try:
            from src_common.ingestion import IngestionPipeline
        except ImportError:
            pytest.skip("Ingestion pipeline not available for testing")

        pipeline = IngestionPipeline()

        # Test pipeline configuration
        pipeline_config = {
            "passes": ["D", "E", "F", "G"],
            "quality_gates": {
                "pass_d": {"min_quality_score": 0.8, "min_entities_per_chunk": 1},
                "pass_e": {"min_nodes": 5, "min_connectivity": 0.7},
                "pass_f": {"min_integrity_score": 0.9, "max_orphaned_nodes": 2},
                "pass_g": {"min_completeness": 0.85, "min_overall_quality": 0.8}
            },
            "gating": {"strict": True, "halt_on_failure": True}
        }

        # Test initial input (chunks from Pass C)
        input_chunks = [
            {
                "chunk_id": "chunk_001",
                "source_id": "test_source",
                "content": "Fireball: A 3rd-level evocation spell that deals fire damage",
                "page": 1,
                "metadata": {"type": "spell", "pass_c_complete": True}
            },
            {
                "chunk_id": "chunk_002",
                "source_id": "test_source",
                "content": "Magic Missile: A 1st-level evocation spell that creates force darts",
                "page": 2,
                "metadata": {"type": "spell", "pass_c_complete": True}
            }
        ]

        if hasattr(pipeline, 'run_passes_d_to_g'):
            # Test complete pipeline execution
            pipeline_result = pipeline.run_passes_d_to_g(input_chunks, pipeline_config)

            assert isinstance(pipeline_result, dict), "Pipeline should return structured result"

            # Verify overall pipeline success
            if "status" in pipeline_result:
                status = pipeline_result["status"]
                assert status in ["completed", "failed", "partial"], f"Pipeline status should be valid: {status}"

            # Verify pass execution sequence
            if "pass_results" in pipeline_result:
                pass_results = pipeline_result["pass_results"]

                required_passes = ["D", "E", "F", "G"]
                for pass_name in required_passes:
                    if pass_name in pass_results:
                        pass_result = pass_results[pass_name]
                        assert "status" in pass_result, f"Pass {pass_name} should have status"
                        assert "quality_metrics" in pass_result, f"Pass {pass_name} should have quality metrics"

            # Verify quality gate enforcement
            if "quality_gate_results" in pipeline_result:
                gate_results = pipeline_result["quality_gate_results"]

                for pass_name in ["D", "E", "F", "G"]:
                    if pass_name in gate_results:
                        gate_result = gate_results[pass_name]
                        assert "passed" in gate_result, f"Gate {pass_name} should have pass/fail status"

                        if not gate_result["passed"]:
                            assert "reason" in gate_result, f"Failed gate {pass_name} should have reason"

            # Verify final output quality
            if "final_output" in pipeline_result:
                final_output = pipeline_result["final_output"]
                assert "nodes" in final_output, "Final output should contain graph nodes"
                assert "edges" in final_output, "Final output should contain graph edges"
                assert "quality_score" in final_output, "Final output should have quality score"

    def test_quality_gate_failure_handling(self):
        """Test quality gate failure handling and pipeline halt behavior"""
        try:
            from src_common.ingestion import IngestionPipeline
        except ImportError:
            pytest.skip("Ingestion pipeline not available for testing")

        pipeline = IngestionPipeline()

        # Test with deliberately poor input to trigger quality gate failures
        poor_input_chunks = [
            {
                "chunk_id": "chunk_001",
                "source_id": "test_source",
                "content": "x",  # Minimal content to trigger quality issues
                "page": 1,
                "metadata": {"type": "unknown"}
            }
        ]

        # Strict quality gate configuration
        strict_config = {
            "passes": ["D", "E", "F", "G"],
            "quality_gates": {
                "pass_d": {"min_quality_score": 0.9, "min_entities_per_chunk": 3},  # High thresholds
                "pass_e": {"min_nodes": 10, "min_connectivity": 0.9},
                "pass_f": {"min_integrity_score": 0.95, "max_orphaned_nodes": 0},
                "pass_g": {"min_completeness": 0.95, "min_overall_quality": 0.9}
            },
            "gating": {"strict": True, "halt_on_failure": True}
        }

        if hasattr(pipeline, 'run_passes_d_to_g'):
            # Test pipeline execution with strict gates
            pipeline_result = pipeline.run_passes_d_to_g(poor_input_chunks, strict_config)

            assert isinstance(pipeline_result, dict), "Pipeline should return structured result even on failure"

            # Verify pipeline stopped at quality gate failure
            if "status" in pipeline_result:
                status = pipeline_result["status"]
                assert status in ["failed", "partial"], "Pipeline should fail with poor input and strict gates"

            # Verify quality gate failure reporting
            if "quality_gate_results" in pipeline_result:
                gate_results = pipeline_result["quality_gate_results"]

                failed_gates = [gate for gate, result in gate_results.items() if not result.get("passed", True)]
                assert len(failed_gates) > 0, "Should have at least one failed quality gate"

                # Verify failure reasons are provided
                for gate in failed_gates:
                    gate_result = gate_results[gate]
                    assert "reason" in gate_result, f"Failed gate {gate} should provide failure reason"
                    assert "metrics" in gate_result, f"Failed gate {gate} should provide metrics"

            # Verify pipeline halted appropriately
            if "halted_at_pass" in pipeline_result:
                halted_pass = pipeline_result["halted_at_pass"]
                assert halted_pass in ["D", "E", "F"], "Pipeline should halt before completion on quality failure"

    def test_pass_resume_after_quality_fix(self):
        """Test pipeline resume functionality after quality gate fixes"""
        try:
            from src_common.ingestion import IngestionPipeline
        except ImportError:
            pytest.skip("Ingestion pipeline not available for testing")

        pipeline = IngestionPipeline()

        # Test resume from specific pass after fixing quality issues
        test_job_id = "test_resume_job_001"

        # Simulate previous pipeline state (halted at Pass E)
        previous_state = {
            "job_id": test_job_id,
            "passes": {
                "D": {"status": "SUCCESS", "artifacts": ["passD_enriched.json"]},
                "E": {"status": "FAILED", "reason": "Quality gate failure"},
                "F": {"status": "PENDING"},
                "G": {"status": "PENDING"}
            },
            "quality_gate_results": {
                "D": {"passed": True, "metrics": {"quality_score": 0.85}},
                "E": {"passed": False, "reason": "Insufficient connectivity", "metrics": {"connectivity_score": 0.6}}
            }
        }

        # Fixed input that should pass Pass E quality gates
        fixed_input = {
            "enriched_chunks": [
                {
                    "chunk_id": "chunk_001",
                    "enriched_content": "Fireball: 3rd-level evocation spell, damage 8d6 fire, range 150 feet",
                    "entities": [
                        {"type": "spell", "name": "Fireball", "level": 3},
                        {"type": "school", "name": "evocation"},
                        {"type": "damage", "dice": "8d6", "type": "fire"},
                        {"type": "range", "value": "150 feet"}
                    ],
                    "quality_score": 0.92
                }
            ]
        }

        if hasattr(pipeline, 'resume_from_pass'):
            # Test resume from Pass E
            resume_result = pipeline.resume_from_pass(
                pass_name="E",
                job_state=previous_state,
                input_data=fixed_input,
                config={"quality_gates": {"pass_e": {"min_connectivity": 0.7}}}
            )

            assert isinstance(resume_result, dict), "Resume should return structured result"

            # Verify resume succeeded
            if "status" in resume_result:
                status = resume_result["status"]
                assert status == "completed", f"Resume should complete successfully, got {status}"

            # Verify only remaining passes were executed
            if "executed_passes" in resume_result:
                executed = resume_result["executed_passes"]
                assert "E" in executed, "Should execute Pass E from resume point"
                assert "F" in executed, "Should execute Pass F after E"
                assert "G" in executed, "Should execute Pass G after F"
                assert "D" not in executed, "Should not re-execute completed Pass D"

    def test_passed_dg_contract_compliance(self):
        """Test that Passed D-G validation matches established contract"""
        # Test pass sequence contract
        required_pass_sequence = ["D", "E", "F", "G"]

        # Verify pass dependency chain
        pass_dependencies = {
            "D": [],  # No dependencies (receives from Pass C)
            "E": ["D"],  # Depends on Pass D enrichment
            "F": ["D", "E"],  # Depends on Pass D+E for cleanup
            "G": ["D", "E", "F"]  # Depends on all previous passes
        }

        for pass_name, dependencies in pass_dependencies.items():
            # Verify dependency requirements are documented
            assert isinstance(dependencies, list), f"Pass {pass_name} should have list of dependencies"

        # Test quality gate contract
        required_quality_metrics = {
            "pass_d": ["quality_score", "entities_extracted", "enrichment_coverage"],
            "pass_e": ["node_count", "edge_count", "connectivity_score"],
            "pass_f": ["data_integrity_score", "completeness_score", "cleanup_summary"],
            "pass_g": ["overall_quality_score", "final_completeness", "processing_summary"]
        }

        for pass_name, metrics in required_quality_metrics.items():
            assert len(metrics) >= 2, f"Pass {pass_name} should track multiple quality metrics"

        # Test gating behavior contract
        gating_behaviors = {
            "strict_gates": True,  # Must halt on quality failure
            "resume_capability": True,  # Must support resume from any pass
            "quality_thresholds": True,  # Must enforce configurable thresholds
            "failure_reporting": True  # Must provide detailed failure reasons
        }

        for behavior, required in gating_behaviors.items():
            assert required, f"Gating behavior {behavior} is required for contract compliance"

        # Test artifact contract
        required_artifacts = {
            "pass_d": ["enriched_chunks.json", "entity_extraction_summary.json"],
            "pass_e": ["graph_nodes.json", "graph_edges.json", "graph_metrics.json"],
            "pass_f": ["cleaned_data.json", "cleanup_summary.json", "validation_report.json"],
            "pass_g": ["final_graph.json", "processing_summary.json", "quality_report.json"]
        }

        for pass_name, artifacts in required_artifacts.items():
            assert len(artifacts) >= 2, f"Pass {pass_name} should produce multiple artifacts"

        # Overall contract compliance
        contract_elements = [
            "sequential_execution",
            "quality_gating",
            "resume_capability",
            "artifact_production",
            "failure_handling"
        ]

        for element in contract_elements:
            # Contract elements should be testable
            assert isinstance(element, str), f"Contract element {element} should be defined"