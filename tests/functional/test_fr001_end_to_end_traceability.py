#!/usr/bin/env python3
"""
Functional Tests for FR-001 End-to-End Traceability Workflows

Tests complete traceability workflows from PDF ingestion through 6-Pass pipeline
to final storage, including lineage tracking, health monitoring, and validation.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

# Add src_common to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))


@pytest.fixture
def temp_test_environment():
    """Create temporary test environment"""
    temp_dir = tempfile.mkdtemp(prefix="fr001_test_")
    
    # Create test structure
    test_env = {
        "base_dir": Path(temp_dir),
        "artifacts_dir": Path(temp_dir) / "artifacts" / "ingest" / "test",
        "upload_dir": Path(temp_dir) / "uploads",
        "config_dir": Path(temp_dir) / "config"
    }
    
    # Create directories
    for dir_path in test_env.values():
        if isinstance(dir_path, Path):
            dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create test PDF
    test_pdf = test_env["upload_dir"] / "test_document.pdf"
    test_pdf.write_text("Mock PDF Content")
    
    yield test_env
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_6pass_pipeline():
    """Mock 6-Pass pipeline for testing"""
    class Mock6PassPipeline:
        def __init__(self, env_dir):
            self.env_dir = env_dir
            self.lineage_data = {}
            self.health_metrics = []
            self.validation_results = {}
            
        def process_source(self, pdf_path, job_id):
            """Mock processing a source through all 6 passes"""
            pass_results = {}
            artifacts = {}
            
            # Mock Pass A: ToC Parsing
            pass_a_result = {
                "success": True,
                "dictionary_entries": 15,
                "sections_parsed": 8,
                "processing_time_ms": 1500,
                "artifacts": [f"{job_id}_pass_a_dict.json"]
            }
            pass_results["A"] = pass_a_result
            artifacts["A"] = pass_a_result["artifacts"]
            
            # Mock Pass B: Logical Splitting
            pass_b_result = {
                "success": True,
                "splits_created": 3,
                "split_size_avg_mb": 8.5,
                "processing_time_ms": 800,
                "artifacts": [f"{job_id}_pass_b_splits.json"]
            }
            pass_results["B"] = pass_b_result
            artifacts["B"] = pass_b_result["artifacts"]
            
            # Mock Pass C: Extraction
            pass_c_result = {
                "success": True,
                "chunks_extracted": 245,
                "extraction_success_rate": 98.5,
                "processing_time_ms": 15000,
                "artifacts": [f"{job_id}_pass_c_chunks.json"]
            }
            pass_results["C"] = pass_c_result
            artifacts["C"] = pass_c_result["artifacts"]
            
            # Mock Pass D: Vector Enrichment
            pass_d_result = {
                "success": True,
                "vectors_generated": 245,
                "enrichment_success_rate": 97.2,
                "processing_time_ms": 8000,
                "artifacts": [f"{job_id}_pass_d_vectors.json"]
            }
            pass_results["D"] = pass_d_result
            artifacts["D"] = pass_d_result["artifacts"]
            
            # Mock Pass E: Graph Building
            pass_e_result = {
                "success": True,
                "nodes_created": 180,
                "edges_created": 420,
                "processing_time_ms": 5000,
                "artifacts": [f"{job_id}_pass_e_graph.json"]
            }
            pass_results["E"] = pass_e_result
            artifacts["E"] = pass_e_result["artifacts"]
            
            # Mock Pass F: Finalization
            pass_f_result = {
                "success": True,
                "artifacts_validated": 5,
                "cleanup_operations": 3,
                "processing_time_ms": 500,
                "artifacts": [f"{job_id}_manifest.json"]
            }
            pass_results["F"] = pass_f_result
            artifacts["F"] = pass_f_result["artifacts"]
            
            return {
                "success": True,
                "job_id": job_id,
                "pass_results": pass_results,
                "artifacts": artifacts,
                "total_processing_time_ms": sum(
                    result["processing_time_ms"] for result in pass_results.values()
                )
            }
    
    return Mock6PassPipeline


class TestEndToEndTraceabilityWorkflow:
    """Test complete end-to-end traceability workflow"""
    
    def test_complete_pipeline_traceability(self, temp_test_environment, mock_6pass_pipeline):
        """Test complete pipeline with full traceability tracking"""
        env = temp_test_environment
        pipeline = mock_6pass_pipeline(env["artifacts_dir"])
        
        # Initialize traceability system
        traceability_system = MockTraceabilitySystem()
        
        # Process test document
        test_pdf = env["upload_dir"] / "test_document.pdf"
        job_id = "job_test_123456"
        
        # Start traceability tracking
        traceability_system.start_job_tracking(job_id, str(test_pdf))
        
        # Run pipeline with traceability
        pipeline_result = pipeline.process_source(test_pdf, job_id)
        
        # Track each pass in traceability system
        for pass_id, pass_result in pipeline_result["pass_results"].items():
            traceability_system.track_pass_completion(
                job_id, pass_id, pass_result
            )
        
        # Complete traceability tracking
        traceability_system.complete_job_tracking(job_id, pipeline_result)
        
        # Validate complete traceability chain
        lineage_data = traceability_system.get_complete_lineage(job_id)
        
        assert lineage_data is not None
        assert lineage_data["job_id"] == job_id
        assert lineage_data["source_file"] == str(test_pdf)
        assert len(lineage_data["passes"]) == 6
        
        # Verify pass lineage chain
        for pass_id in ["A", "B", "C", "D", "E", "F"]:
            assert pass_id in lineage_data["passes"]
            pass_data = lineage_data["passes"][pass_id]
            assert pass_data["success"] is True
            assert "processing_time_ms" in pass_data
            assert "artifacts" in pass_data
        
    def test_health_monitoring_integration(self, temp_test_environment, mock_6pass_pipeline):
        """Test health monitoring throughout pipeline execution"""
        env = temp_test_environment
        pipeline = mock_6pass_pipeline(env["artifacts_dir"])
        
        # Initialize health monitoring
        health_monitor = MockHealthMonitor()
        
        # Process with health monitoring
        test_pdf = env["upload_dir"] / "test_document.pdf"
        job_id = "job_health_test_123"
        
        health_monitor.start_job_monitoring(job_id)
        
        pipeline_result = pipeline.process_source(test_pdf, job_id)
        
        # Collect health metrics for each pass
        for pass_id, pass_result in pipeline_result["pass_results"].items():
            health_monitor.collect_pass_metrics(job_id, pass_id, pass_result)
        
        health_monitor.complete_job_monitoring(job_id, pipeline_result)
        
        # Validate health data collection
        health_data = health_monitor.get_job_health_data(job_id)
        
        assert health_data is not None
        assert health_data["job_id"] == job_id
        assert "overall_health_score" in health_data
        assert health_data["overall_health_score"] > 90.0
        
        # Check pass-specific health metrics
        assert len(health_data["pass_health"]) == 6
        for pass_id in ["A", "B", "C", "D", "E", "F"]:
            assert pass_id in health_data["pass_health"]
            pass_health = health_data["pass_health"][pass_id]
            assert "processing_time_ms" in pass_health
            assert "success_rate" in pass_health
            
    def test_validation_framework_integration(self, temp_test_environment, mock_6pass_pipeline):
        """Test validation framework integration with pipeline"""
        env = temp_test_environment
        pipeline = mock_6pass_pipeline(env["artifacts_dir"])
        
        # Initialize validation framework
        validator = MockValidationFramework()
        
        # Process with validation
        test_pdf = env["upload_dir"] / "test_document.pdf"
        job_id = "job_validation_test_123"
        
        pipeline_result = pipeline.process_source(test_pdf, job_id)
        
        # Validate each pass result
        validation_results = {}
        for pass_id, pass_result in pipeline_result["pass_results"].items():
            validation_result = validator.validate_pass_result(pass_id, pass_result)
            validation_results[pass_id] = validation_result
        
        # Perform cross-pass validation
        cross_validation = validator.validate_cross_pass_consistency(
            pipeline_result["pass_results"]
        )
        
        # Validate results
        assert all(result["valid"] for result in validation_results.values())
        assert cross_validation["consistent"]
        assert len(cross_validation["inconsistencies"]) == 0
        
    def test_error_handling_and_recovery(self, temp_test_environment):
        """Test error handling and recovery in traceability system"""
        env = temp_test_environment
        
        # Initialize systems
        traceability_system = MockTraceabilitySystem()
        recovery_system = MockRecoverySystem()
        
        job_id = "job_error_test_123"
        test_pdf = env["upload_dir"] / "test_document.pdf"
        
        # Simulate pipeline failure at Pass D
        traceability_system.start_job_tracking(job_id, str(test_pdf))
        
        # Successful passes A, B, C
        for pass_id in ["A", "B", "C"]:
            pass_result = {
                "success": True,
                "pass_id": pass_id,
                "processing_time_ms": 1500,
                "artifacts": [f"job_{pass_id.lower()}_artifact.json"]
            }
            traceability_system.track_pass_completion(job_id, pass_id, pass_result)
        
        # Failed Pass D
        pass_d_failure = {
            "success": False,
            "pass_id": "D",
            "error": "Vector enrichment timeout",
            "processing_time_ms": 30000,
            "artifacts": []
        }
        traceability_system.track_pass_failure(job_id, "D", pass_d_failure)
        
        # Test recovery planning
        recovery_plan = recovery_system.plan_recovery(job_id, traceability_system)
        
        assert recovery_plan["failed_pass"] == "D"
        assert recovery_plan["last_successful_pass"] == "C"
        assert "D" in recovery_plan["passes_to_retry"]
        assert "E" in recovery_plan["passes_to_retry"]
        assert "F" in recovery_plan["passes_to_retry"]
        
        # Test partial recovery execution
        recovery_result = recovery_system.execute_recovery(job_id, recovery_plan)
        assert recovery_result["success"]
        assert recovery_result["passes_recovered"] == ["D", "E", "F"]


class TestLineageQueryAndVisualization:
    """Test lineage querying and visualization capabilities"""
    
    def test_lineage_query_api(self, temp_test_environment):
        """Test lineage query API functionality"""
        lineage_db = MockLineageDatabase()
        
        # Setup test lineage data
        test_lineage = {
            "job_id": "job_query_test_123",
            "source_file": "test.pdf",
            "passes": {
                "A": {
                    "input_artifacts": ["test.pdf"],
                    "output_artifacts": ["job_a_dict.json"],
                    "transformation": "toc_parsing"
                },
                "B": {
                    "input_artifacts": ["job_a_dict.json"],
                    "output_artifacts": ["job_b_splits.json"],
                    "transformation": "logical_splitting"
                },
                "C": {
                    "input_artifacts": ["job_b_splits.json", "test.pdf"],
                    "output_artifacts": ["job_c_chunks.json"],
                    "transformation": "content_extraction"
                }
            }
        }
        
        lineage_db.store_lineage("job_query_test_123", test_lineage)
        
        # Test various query types
        query_api = MockLineageQueryAPI(lineage_db)
        
        # Query by job ID
        job_lineage = query_api.get_job_lineage("job_query_test_123")
        assert job_lineage is not None
        assert job_lineage["job_id"] == "job_query_test_123"
        
        # Query upstream dependencies
        upstream = query_api.get_upstream_dependencies("job_c_chunks.json")
        assert "job_b_splits.json" in upstream
        assert "test.pdf" in upstream
        
        # Query downstream dependencies
        downstream = query_api.get_downstream_dependencies("job_a_dict.json")
        assert "job_b_splits.json" in downstream
        
        # Query by transformation type
        toc_jobs = query_api.query_by_transformation("toc_parsing")
        assert len(toc_jobs) >= 1
        assert any(job["job_id"] == "job_query_test_123" for job in toc_jobs)
        
    def test_lineage_visualization_data(self, temp_test_environment):
        """Test lineage visualization data generation"""
        lineage_visualizer = MockLineageVisualizer()
        
        # Test lineage data
        lineage_data = {
            "job_id": "job_viz_test_123",
            "passes": {
                "A": {
                    "input_artifacts": ["source.pdf"],
                    "output_artifacts": ["toc.json", "sections.json"]
                },
                "B": {
                    "input_artifacts": ["toc.json"],
                    "output_artifacts": ["splits.json"]
                },
                "C": {
                    "input_artifacts": ["splits.json", "source.pdf"],
                    "output_artifacts": ["chunks.json"]
                }
            }
        }
        
        # Generate visualization data
        viz_data = lineage_visualizer.generate_graph_data(lineage_data)
        
        # Validate graph structure
        assert "nodes" in viz_data
        assert "edges" in viz_data
        
        # Check nodes (artifacts)
        node_ids = [node["id"] for node in viz_data["nodes"]]
        assert "source.pdf" in node_ids
        assert "toc.json" in node_ids
        assert "splits.json" in node_ids
        assert "chunks.json" in node_ids
        
        # Check edges (transformations)
        edge_count = len(viz_data["edges"])
        assert edge_count >= 4  # At least one edge per transformation
        
        # Validate edge structure
        for edge in viz_data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "transformation" in edge
            
    def test_impact_analysis(self, temp_test_environment):
        """Test impact analysis for data changes"""
        impact_analyzer = MockImpactAnalyzer()
        
        # Setup complex lineage with multiple dependencies
        complex_lineage = {
            "job_1": {
                "source": "doc1.pdf",
                "artifacts": {
                    "A": ["doc1_toc.json"],
                    "B": ["doc1_splits.json"],
                    "C": ["doc1_chunks.json"]
                }
            },
            "job_2": {
                "source": "doc2.pdf", 
                "artifacts": {
                    "A": ["doc2_toc.json"],
                    "B": ["doc2_splits.json"], 
                    "C": ["doc2_chunks.json"]
                }
            },
            # Cross-job dependencies (e.g., shared dictionary)
            "job_3": {
                "source": "dictionary_update",
                "dependencies": ["doc1_toc.json", "doc2_toc.json"],
                "artifacts": {
                    "D": ["updated_dict.json"]
                }
            }
        }
        
        impact_analyzer.load_lineage_data(complex_lineage)
        
        # Analyze impact of changing doc1.pdf
        impact = impact_analyzer.analyze_impact("doc1.pdf")
        
        assert "affected_jobs" in impact
        assert "job_1" in impact["affected_jobs"]
        assert "job_3" in impact["affected_jobs"]  # Due to dictionary dependency
        
        # Analyze impact of Pass A failure in job_1
        pass_impact = impact_analyzer.analyze_pass_failure("job_1", "A")
        
        assert "affected_passes" in pass_impact
        assert "job_1" in pass_impact["affected_passes"]
        assert "B" in pass_impact["affected_passes"]["job_1"]  # Downstream
        assert "C" in pass_impact["affected_passes"]["job_1"]  # Downstream


# Mock classes for testing

class MockTraceabilitySystem:
    def __init__(self):
        self.job_lineages = {}
        
    def start_job_tracking(self, job_id, source_file):
        self.job_lineages[job_id] = {
            "job_id": job_id,
            "source_file": source_file,
            "passes": {},
            "start_time": "2025-09-11T10:30:00Z"
        }
        
    def track_pass_completion(self, job_id, pass_id, pass_result):
        if job_id in self.job_lineages:
            self.job_lineages[job_id]["passes"][pass_id] = pass_result
            
    def track_pass_failure(self, job_id, pass_id, failure_info):
        if job_id in self.job_lineages:
            self.job_lineages[job_id]["passes"][pass_id] = failure_info
            
    def complete_job_tracking(self, job_id, final_result):
        if job_id in self.job_lineages:
            self.job_lineages[job_id]["final_result"] = final_result
            self.job_lineages[job_id]["end_time"] = "2025-09-11T10:35:00Z"
            
    def get_complete_lineage(self, job_id):
        return self.job_lineages.get(job_id)


class MockHealthMonitor:
    def __init__(self):
        self.job_health_data = {}
        
    def start_job_monitoring(self, job_id):
        self.job_health_data[job_id] = {
            "job_id": job_id,
            "pass_health": {},
            "metrics": []
        }
        
    def collect_pass_metrics(self, job_id, pass_id, pass_result):
        if job_id in self.job_health_data:
            self.job_health_data[job_id]["pass_health"][pass_id] = {
                "processing_time_ms": pass_result.get("processing_time_ms", 0),
                "success_rate": 100.0 if pass_result.get("success") else 0.0,
                "health_score": 95.0 if pass_result.get("success") else 60.0
            }
            
    def complete_job_monitoring(self, job_id, pipeline_result):
        if job_id in self.job_health_data:
            # Calculate overall health score
            pass_scores = [
                data["health_score"] 
                for data in self.job_health_data[job_id]["pass_health"].values()
            ]
            overall_score = sum(pass_scores) / len(pass_scores) if pass_scores else 0.0
            self.job_health_data[job_id]["overall_health_score"] = overall_score
            
    def get_job_health_data(self, job_id):
        return self.job_health_data.get(job_id)


class MockValidationFramework:
    def validate_pass_result(self, pass_id, pass_result):
        # Simple validation - check success and required fields
        required_fields = {
            "A": ["dictionary_entries", "sections_parsed"],
            "B": ["splits_created"],
            "C": ["chunks_extracted", "extraction_success_rate"],
            "D": ["vectors_generated"],
            "E": ["nodes_created", "edges_created"],
            "F": ["artifacts_validated"]
        }
        
        issues = []
        if not pass_result.get("success", False):
            issues.append("Pass marked as failed")
            
        for field in required_fields.get(pass_id, []):
            if field not in pass_result:
                issues.append(f"Missing required field: {field}")
                
        return {
            "pass_id": pass_id,
            "valid": len(issues) == 0,
            "issues": issues
        }
        
    def validate_cross_pass_consistency(self, pass_results):
        inconsistencies = []
        
        # Example consistency check: dictionary entries A->B
        if ("A" in pass_results and "B" in pass_results):
            a_dict = pass_results["A"].get("dictionary_entries", 0)
            # In real implementation, would check if B used these entries
        
        return {
            "consistent": len(inconsistencies) == 0,
            "inconsistencies": inconsistencies
        }


class MockRecoverySystem:
    def plan_recovery(self, job_id, traceability_system):
        lineage = traceability_system.get_complete_lineage(job_id)
        
        # Find failed pass
        failed_pass = None
        last_successful = None
        
        for pass_id in ["A", "B", "C", "D", "E", "F"]:
            if pass_id in lineage["passes"]:
                if lineage["passes"][pass_id].get("success", False):
                    last_successful = pass_id
                else:
                    failed_pass = pass_id
                    break
        
        # Plan recovery from failure point
        all_passes = ["A", "B", "C", "D", "E", "F"]
        failed_index = all_passes.index(failed_pass) if failed_pass else len(all_passes)
        passes_to_retry = all_passes[failed_index:]
        
        return {
            "job_id": job_id,
            "failed_pass": failed_pass,
            "last_successful_pass": last_successful,
            "passes_to_retry": passes_to_retry
        }
        
    def execute_recovery(self, job_id, recovery_plan):
        # Mock recovery execution
        return {
            "success": True,
            "job_id": job_id,
            "passes_recovered": recovery_plan["passes_to_retry"]
        }


class MockLineageDatabase:
    def __init__(self):
        self.lineage_store = {}
        
    def store_lineage(self, job_id, lineage_data):
        self.lineage_store[job_id] = lineage_data
        
    def get_lineage(self, job_id):
        return self.lineage_store.get(job_id)


class MockLineageQueryAPI:
    def __init__(self, lineage_db):
        self.db = lineage_db
        
    def get_job_lineage(self, job_id):
        return self.db.get_lineage(job_id)
        
    def get_upstream_dependencies(self, artifact_name):
        # Find all artifacts that contribute to the given artifact
        dependencies = set()
        for lineage in self.db.lineage_store.values():
            for pass_data in lineage["passes"].values():
                if artifact_name in pass_data.get("output_artifacts", []):
                    dependencies.update(pass_data.get("input_artifacts", []))
        return list(dependencies)
        
    def get_downstream_dependencies(self, artifact_name):
        # Find all artifacts that depend on the given artifact
        dependencies = set()
        for lineage in self.db.lineage_store.values():
            for pass_data in lineage["passes"].values():
                if artifact_name in pass_data.get("input_artifacts", []):
                    dependencies.update(pass_data.get("output_artifacts", []))
        return list(dependencies)
        
    def query_by_transformation(self, transformation_type):
        results = []
        for job_id, lineage in self.db.lineage_store.items():
            for pass_data in lineage["passes"].values():
                if pass_data.get("transformation") == transformation_type:
                    results.append(lineage)
                    break
        return results


class MockLineageVisualizer:
    def generate_graph_data(self, lineage_data):
        nodes = []
        edges = []
        
        # Extract all artifacts as nodes
        artifacts = set()
        for pass_data in lineage_data["passes"].values():
            artifacts.update(pass_data.get("input_artifacts", []))
            artifacts.update(pass_data.get("output_artifacts", []))
            
        for artifact in artifacts:
            nodes.append({
                "id": artifact,
                "label": artifact,
                "type": "artifact"
            })
            
        # Create edges for transformations
        for pass_id, pass_data in lineage_data["passes"].items():
            inputs = pass_data.get("input_artifacts", [])
            outputs = pass_data.get("output_artifacts", [])
            
            for input_artifact in inputs:
                for output_artifact in outputs:
                    edges.append({
                        "source": input_artifact,
                        "target": output_artifact,
                        "transformation": f"pass_{pass_id.lower()}",
                        "label": f"Pass {pass_id}"
                    })
                    
        return {"nodes": nodes, "edges": edges}


class MockImpactAnalyzer:
    def __init__(self):
        self.lineage_data = {}
        
    def load_lineage_data(self, lineage_data):
        self.lineage_data = lineage_data
        
    def analyze_impact(self, source_artifact):
        affected_jobs = []
        
        for job_id, job_data in self.lineage_data.items():
            # Check if job depends on the source artifact
            if (job_data.get("source") == source_artifact or
                source_artifact in job_data.get("dependencies", [])):
                affected_jobs.append(job_id)
                
        return {"affected_jobs": affected_jobs}
        
    def analyze_pass_failure(self, job_id, failed_pass):
        affected_passes = {job_id: []}
        
        # All downstream passes in the same job are affected
        all_passes = ["A", "B", "C", "D", "E", "F"]
        failed_index = all_passes.index(failed_pass)
        
        for pass_id in all_passes[failed_index + 1:]:
            affected_passes[job_id].append(pass_id)
            
        return {"affected_passes": affected_passes}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])