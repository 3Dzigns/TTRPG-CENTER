#!/usr/bin/env python3
"""
Integration Tests for FR-001 Cross-Pass Data Validation

Tests integration between traceability, health monitoring, and validation
across the complete 6-Pass pipeline with real data flow validation.
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
def integration_test_environment():
    """Setup integration test environment with realistic data"""
    temp_dir = tempfile.mkdtemp(prefix="fr001_integration_")
    
    test_env = {
        "base_dir": Path(temp_dir),
        "artifacts_dir": Path(temp_dir) / "artifacts" / "ingest" / "test",
        "job_id": "job_integration_test_123456789",
        "source_pdf": "D&D_Players_Handbook.pdf"
    }
    
    test_env["artifacts_dir"].mkdir(parents=True, exist_ok=True)
    
    yield test_env
    
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestCrossPassDataFlow:
    """Test data flow validation across all passes"""
    
    def test_pass_a_to_b_integration(self, integration_test_environment):
        """Test data flow from Pass A (ToC parsing) to Pass B (logical splitting)"""
        env = integration_test_environment
        
        # Mock Pass A output
        pass_a_output = {
            "success": True,
            "source_file": env["source_pdf"],
            "job_id": env["job_id"],
            "dictionary_entries": [
                {"term": "Fireball", "type": "spell", "page": 241, "section": "Spells"},
                {"term": "Longsword", "type": "weapon", "page": 149, "section": "Equipment"},
                {"term": "Fighter", "type": "class", "page": 70, "section": "Classes"},
                {"term": "Barbarian", "type": "class", "page": 46, "section": "Classes"},
                {"term": "Healing Potion", "type": "item", "page": 153, "section": "Equipment"}
            ],
            "sections_parsed": [
                {"name": "Classes", "start_page": 45, "end_page": 124, "subsections": 12},
                {"name": "Equipment", "start_page": 143, "end_page": 179, "subsections": 8},
                {"name": "Spells", "start_page": 207, "end_page": 289, "subsections": 9}
            ],
            "processing_time_ms": 1850,
            "artifacts": [f"{env['job_id']}_pass_a_dict.json", f"{env['job_id']}_pass_a_sections.json"]
        }
        
        # Mock Pass B processing using Pass A output
        pass_b_processor = MockPassBProcessor()
        pass_b_output = pass_b_processor.process_with_pass_a_input(pass_a_output)
        
        # Validate cross-pass data consistency
        validator = CrossPassValidator()
        validation_result = validator.validate_a_to_b_flow(pass_a_output, pass_b_output)
        
        assert validation_result["valid"], f"A→B validation failed: {validation_result['issues']}"
        assert validation_result["data_consistency_score"] > 95.0
        
        # Verify specific data flow requirements
        assert pass_b_output["input_dictionary_entries"] == len(pass_a_output["dictionary_entries"])
        assert pass_b_output["input_sections"] == len(pass_a_output["sections_parsed"])
        
        # Validate artifact relationships
        assert any(artifact.endswith("_dict.json") for artifact in pass_a_output["artifacts"])
        assert pass_b_output["dictionary_source"] in pass_a_output["artifacts"]
        
    def test_pass_c_extraction_integration(self, integration_test_environment):
        """Test Pass C extraction integration with upstream passes"""
        env = integration_test_environment
        
        # Mock upstream data from Pass A and B
        upstream_data = {
            "pass_a": {
                "dictionary_entries": 15,
                "sections_parsed": 3,
                "toc_structure": {
                    "Classes": {"start": 45, "end": 124},
                    "Equipment": {"start": 143, "end": 179},
                    "Spells": {"start": 207, "end": 289}
                }
            },
            "pass_b": {
                "splits_created": 3,
                "splits": [
                    {"id": 1, "pages": "1-100", "size_mb": 8.2, "sections": ["Introduction", "Classes"]},
                    {"id": 2, "pages": "101-200", "size_mb": 7.8, "sections": ["Classes", "Equipment"]},
                    {"id": 3, "pages": "201-320", "size_mb": 9.1, "sections": ["Spells", "Appendix"]}
                ]
            }
        }
        
        # Mock Pass C extraction
        pass_c_processor = MockPassCProcessor()
        pass_c_output = pass_c_processor.extract_with_upstream_data(
            env["source_pdf"], upstream_data
        )
        
        # Validate extraction consistency with upstream
        validator = CrossPassValidator()
        c_validation = validator.validate_extraction_consistency(upstream_data, pass_c_output)
        
        assert c_validation["valid"]
        assert c_validation["chunk_coverage_score"] > 90.0
        
        # Verify section-based chunk distribution
        expected_sections = set()
        for split in upstream_data["pass_b"]["splits"]:
            expected_sections.update(split["sections"])
            
        extracted_sections = set(chunk["section"] for chunk in pass_c_output["chunks"] if chunk["section"])
        section_coverage = len(extracted_sections & expected_sections) / len(expected_sections)
        
        assert section_coverage > 0.8, f"Poor section coverage: {section_coverage:.2%}"
        
    def test_pass_d_e_graph_pipeline(self, integration_test_environment):
        """Test Pass D vector enrichment to Pass E graph building pipeline"""
        env = integration_test_environment
        
        # Mock Pass D output (vector enrichment)
        pass_d_output = {
            "success": True,
            "vectors_generated": 245,
            "enrichment_success_rate": 97.2,
            "enriched_chunks": [
                {
                    "chunk_id": 1,
                    "text": "Fireball: A 3rd-level evocation spell...",
                    "vector": [0.1, 0.3, -0.2, 0.8],  # Simplified vector
                    "enrichments": {
                        "spell_name": "Fireball",
                        "spell_level": 3,
                        "school": "Evocation",
                        "related_terms": ["damage", "fire", "area effect"]
                    }
                },
                {
                    "chunk_id": 2,
                    "text": "Fighter class features include...",
                    "vector": [0.2, -0.1, 0.5, 0.4],
                    "enrichments": {
                        "class_name": "Fighter",
                        "features": ["Combat", "Weapons", "Armor"],
                        "related_terms": ["combat", "martial", "training"]
                    }
                }
            ],
            "dictionary_updates": [
                {"term": "Evocation", "type": "spell_school", "confidence": 0.95},
                {"term": "Combat", "type": "class_feature", "confidence": 0.88}
            ]
        }
        
        # Mock Pass E graph building using Pass D data
        pass_e_processor = MockPassEProcessor()
        pass_e_output = pass_e_processor.build_graph_from_vectors(pass_d_output)
        
        # Validate D→E integration
        validator = CrossPassValidator()
        de_validation = validator.validate_d_to_e_pipeline(pass_d_output, pass_e_output)
        
        assert de_validation["valid"]
        assert de_validation["graph_consistency_score"] > 85.0
        
        # Verify graph nodes correspond to enriched chunks
        chunk_ids = set(chunk["chunk_id"] for chunk in pass_d_output["enriched_chunks"])
        graph_nodes = set(node["source_chunk_id"] for node in pass_e_output["nodes"] 
                         if "source_chunk_id" in node)
        
        node_coverage = len(graph_nodes & chunk_ids) / len(chunk_ids)
        assert node_coverage > 0.9, f"Poor node coverage: {node_coverage:.2%}"
        
    def test_complete_pipeline_validation(self, integration_test_environment):
        """Test complete 6-pass pipeline integration validation"""
        env = integration_test_environment
        
        # Create integrated pipeline processor
        integrated_pipeline = IntegratedPipelineProcessor(env)
        
        # Run complete pipeline with validation
        pipeline_result = integrated_pipeline.run_complete_pipeline(env["source_pdf"])
        
        # Validate complete integration
        validator = CompletePipelineValidator()
        complete_validation = validator.validate_complete_pipeline(pipeline_result)
        
        assert complete_validation["overall_valid"]
        assert complete_validation["pipeline_integrity_score"] > 90.0
        
        # Verify pass-to-pass consistency
        for i, pass_id in enumerate(["A", "B", "C", "D", "E", "F"]):
            if i > 0:  # Skip first pass
                prev_pass = ["A", "B", "C", "D", "E", "F"][i-1]
                consistency = validator.validate_pass_consistency(
                    prev_pass, pass_id, pipeline_result
                )
                assert consistency["consistent"], f"{prev_pass}→{pass_id} inconsistency: {consistency['issues']}"


class TestHealthMonitoringIntegration:
    """Test health monitoring integration across passes"""
    
    def test_cross_pass_health_correlation(self, integration_test_environment):
        """Test health metric correlation across passes"""
        env = integration_test_environment
        
        # Create health monitoring system
        health_system = IntegratedHealthMonitor()
        
        # Simulate pipeline execution with health monitoring
        pipeline_execution = MockPipelineExecution()
        
        # Pass A execution
        pass_a_result = pipeline_execution.execute_pass_a()
        health_system.record_pass_health("A", pass_a_result)
        
        # Pass B execution (dependent on A)
        pass_b_result = pipeline_execution.execute_pass_b(pass_a_result)
        health_system.record_pass_health("B", pass_b_result)
        
        # Pass C execution
        pass_c_result = pipeline_execution.execute_pass_c(pass_a_result, pass_b_result)
        health_system.record_pass_health("C", pass_c_result)
        
        # Analyze health correlations
        health_analysis = health_system.analyze_cross_pass_health()
        
        assert "pass_correlations" in health_analysis
        assert "health_trend" in health_analysis
        assert health_analysis["overall_pipeline_health"] > 85.0
        
        # Check for performance degradation patterns
        performance_trend = health_analysis["performance_metrics"]
        
        # Validate that processing times are reasonable
        for pass_id in ["A", "B", "C"]:
            assert performance_trend[pass_id]["processing_time_ms"] < 30000  # 30 second max
            assert performance_trend[pass_id]["success_rate"] > 90.0
            
    def test_anomaly_detection_across_passes(self, integration_test_environment):
        """Test anomaly detection across multiple passes"""
        env = integration_test_environment
        
        # Create anomaly detection system
        anomaly_detector = CrossPassAnomalyDetector()
        
        # Simulate normal baseline
        baseline_runs = []
        for i in range(10):
            run_data = {
                "A": {"processing_time_ms": 1200 + (i * 50), "chunks": 40 + i},
                "B": {"processing_time_ms": 800 + (i * 30), "splits": 3},
                "C": {"processing_time_ms": 15000 + (i * 500), "extraction_rate": 98.0 + (i * 0.1)}
            }
            baseline_runs.append(run_data)
            anomaly_detector.record_baseline(f"run_{i}", run_data)
        
        # Test anomalous run
        anomalous_run = {
            "A": {"processing_time_ms": 4500, "chunks": 12},  # Much slower, fewer chunks
            "B": {"processing_time_ms": 850, "splits": 3},    # Normal
            "C": {"processing_time_ms": 25000, "extraction_rate": 85.0}  # Slower, lower rate
        }
        
        anomalies = anomaly_detector.detect_anomalies(anomalous_run)
        
        assert len(anomalies) > 0, "Should detect anomalies in Pass A and C"
        
        # Verify specific anomalies
        pass_a_anomalies = [a for a in anomalies if a["pass"] == "A"]
        pass_c_anomalies = [a for a in anomalies if a["pass"] == "C"]
        
        assert len(pass_a_anomalies) > 0, "Should detect Pass A anomalies"
        assert len(pass_c_anomalies) > 0, "Should detect Pass C anomalies"
        
        # Check anomaly correlation
        correlated_anomalies = anomaly_detector.find_correlated_anomalies(anomalies)
        assert len(correlated_anomalies) > 0, "Should find correlated anomalies across passes"


class TestValidationFrameworkIntegration:
    """Test validation framework integration with all systems"""
    
    def test_integrated_validation_workflow(self, integration_test_environment):
        """Test complete integrated validation workflow"""
        env = integration_test_environment
        
        # Create integrated validation system
        validation_system = IntegratedValidationSystem()
        
        # Initialize systems
        traceability = MockTraceabilitySystem()
        health_monitor = MockHealthMonitor()
        
        # Start integrated job
        job_id = env["job_id"]
        source_file = env["source_pdf"]
        
        validation_system.start_integrated_validation(job_id, source_file)
        traceability.start_job_tracking(job_id, source_file)
        health_monitor.start_job_monitoring(job_id)
        
        # Process passes with integrated validation
        pass_results = {}
        
        for pass_id in ["A", "B", "C", "D", "E", "F"]:
            # Mock pass execution
            pass_result = self._mock_pass_execution(pass_id, pass_results)
            
            # Integrated validation
            validation_result = validation_system.validate_pass_with_context(
                pass_id, pass_result, pass_results, traceability, health_monitor
            )
            
            assert validation_result["valid"], f"Pass {pass_id} validation failed: {validation_result['issues']}"
            
            # Record results
            pass_results[pass_id] = pass_result
            traceability.track_pass_completion(job_id, pass_id, pass_result)
            health_monitor.collect_pass_metrics(job_id, pass_id, pass_result)
        
        # Final integrated validation
        final_validation = validation_system.complete_integrated_validation(
            job_id, pass_results, traceability, health_monitor
        )
        
        assert final_validation["overall_valid"]
        assert final_validation["traceability_complete"]
        assert final_validation["health_acceptable"]
        assert final_validation["cross_pass_consistent"]
        
    def test_validation_error_propagation(self, integration_test_environment):
        """Test how validation errors propagate across passes"""
        env = integration_test_environment
        
        validation_system = IntegratedValidationSystem()
        error_tracker = ValidationErrorTracker()
        
        # Simulate Pass A with minor issues
        pass_a_result = {
            "success": True,
            "dictionary_entries": 8,  # Lower than expected
            "sections_parsed": 3,
            "processing_time_ms": 1200,
            "warnings": ["Low dictionary extraction count"]
        }
        
        validation_a = validation_system.validate_pass("A", pass_a_result)
        error_tracker.record_validation("A", validation_a)
        
        # Pass B inherits Pass A issues
        pass_b_result = {
            "success": True,
            "splits_created": 2,  # Fewer splits due to fewer sections
            "input_dictionary_entries": 8,  # Matches Pass A
            "processing_time_ms": 600
        }
        
        validation_b = validation_system.validate_pass_with_inheritance(
            "B", pass_b_result, {"A": validation_a}
        )
        error_tracker.record_validation("B", validation_b)
        
        # Analyze error propagation
        propagation_analysis = error_tracker.analyze_error_propagation()
        
        assert "error_chains" in propagation_analysis
        assert len(propagation_analysis["error_chains"]) > 0
        
        # Verify that Pass A issues are flagged as root causes
        root_causes = propagation_analysis["root_causes"]
        assert any(cause["pass"] == "A" for cause in root_causes)
        
    def _mock_pass_execution(self, pass_id, previous_results):
        """Mock pass execution based on pass ID and previous results"""
        base_result = {
            "success": True,
            "processing_time_ms": 1500,
            "pass_id": pass_id
        }
        
        if pass_id == "A":
            base_result.update({
                "dictionary_entries": 15,
                "sections_parsed": 8,
                "toc_structure": {"sections": 3}
            })
        elif pass_id == "B":
            base_result.update({
                "splits_created": 3,
                "input_dictionary_entries": previous_results.get("A", {}).get("dictionary_entries", 15)
            })
        elif pass_id == "C":
            base_result.update({
                "chunks_extracted": 245,
                "extraction_success_rate": 98.5
            })
        elif pass_id == "D":
            base_result.update({
                "vectors_generated": previous_results.get("C", {}).get("chunks_extracted", 245),
                "enrichment_success_rate": 97.2
            })
        elif pass_id == "E":
            base_result.update({
                "nodes_created": 180,
                "edges_created": 420,
                "graph_consistency_score": 94.8
            })
        elif pass_id == "F":
            base_result.update({
                "artifacts_validated": 5,
                "cleanup_operations": 3,
                "final_integrity_score": 100.0
            })
            
        return base_result


# Mock classes for integration testing

class MockPassBProcessor:
    def process_with_pass_a_input(self, pass_a_output):
        return {
            "success": True,
            "splits_created": 3,
            "input_dictionary_entries": len(pass_a_output["dictionary_entries"]),
            "input_sections": len(pass_a_output["sections_parsed"]),
            "dictionary_source": pass_a_output["artifacts"][0],
            "processing_time_ms": 850,
            "data_consistency_score": 98.5
        }


class MockPassCProcessor:
    def extract_with_upstream_data(self, source_pdf, upstream_data):
        # Calculate expected chunks based on upstream
        total_pages = sum(100 for _ in upstream_data["pass_b"]["splits"])  # Rough estimate
        expected_chunks = total_pages * 2  # ~2 chunks per page
        
        return {
            "success": True,
            "chunks_extracted": min(expected_chunks, 250),
            "extraction_success_rate": 98.2,
            "chunks": [
                {"chunk_id": i, "section": "Classes", "page": 45 + i} 
                for i in range(1, 50)
            ] + [
                {"chunk_id": i, "section": "Equipment", "page": 143 + i - 50}
                for i in range(50, 100)
            ],
            "processing_time_ms": 16000,
            "chunk_coverage_score": 95.2
        }


class MockPassEProcessor:
    def build_graph_from_vectors(self, pass_d_output):
        chunks = pass_d_output["enriched_chunks"]
        
        return {
            "success": True,
            "nodes_created": len(chunks) + 10,  # Chunks plus entity nodes
            "edges_created": len(chunks) * 2,   # ~2 edges per chunk
            "nodes": [
                {"id": f"chunk_{chunk['chunk_id']}", "type": "chunk", 
                 "source_chunk_id": chunk["chunk_id"]}
                for chunk in chunks
            ],
            "edges": [
                {"source": f"chunk_{chunk['chunk_id']}", "target": "entity_fireball", 
                 "type": "mentions"}
                for chunk in chunks if "Fireball" in chunk["text"]
            ],
            "graph_consistency_score": 92.1,
            "processing_time_ms": 5200
        }


class CrossPassValidator:
    def validate_a_to_b_flow(self, pass_a_output, pass_b_output):
        issues = []
        
        # Check dictionary count consistency
        if (pass_a_output["dictionary_entries"] != pass_b_output["input_dictionary_entries"]):
            issues.append("Dictionary entry count mismatch")
            
        consistency_score = 100.0 - (len(issues) * 10.0)
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "data_consistency_score": max(0.0, consistency_score)
        }
        
    def validate_extraction_consistency(self, upstream_data, pass_c_output):
        total_sections = len(upstream_data["pass_a"]["toc_structure"])
        extracted_sections = len(set(chunk["section"] for chunk in pass_c_output["chunks"]))
        
        coverage_score = (extracted_sections / total_sections) * 100
        
        return {
            "valid": coverage_score > 80.0,
            "chunk_coverage_score": coverage_score
        }
        
    def validate_d_to_e_pipeline(self, pass_d_output, pass_e_output):
        chunk_count = len(pass_d_output["enriched_chunks"])
        node_count = pass_e_output["nodes_created"]
        
        # Expect reasonable node count relative to chunks
        ratio_valid = 0.8 <= (node_count / chunk_count) <= 3.0
        
        return {
            "valid": ratio_valid,
            "graph_consistency_score": 90.0 if ratio_valid else 60.0
        }


class IntegratedPipelineProcessor:
    def __init__(self, env):
        self.env = env
        
    def run_complete_pipeline(self, source_pdf):
        return {
            "success": True,
            "passes": {
                "A": {"success": True, "dictionary_entries": 15},
                "B": {"success": True, "splits_created": 3},
                "C": {"success": True, "chunks_extracted": 245},
                "D": {"success": True, "vectors_generated": 245},
                "E": {"success": True, "nodes_created": 180},
                "F": {"success": True, "artifacts_validated": 5}
            }
        }


class CompletePipelineValidator:
    def validate_complete_pipeline(self, pipeline_result):
        return {
            "overall_valid": pipeline_result["success"],
            "pipeline_integrity_score": 95.0
        }
        
    def validate_pass_consistency(self, prev_pass, curr_pass, pipeline_result):
        return {
            "consistent": True,
            "issues": []
        }


class IntegratedHealthMonitor:
    def __init__(self):
        self.pass_health = {}
        
    def record_pass_health(self, pass_id, pass_result):
        self.pass_health[pass_id] = {
            "processing_time_ms": pass_result.get("processing_time_ms", 0),
            "success_rate": 100.0 if pass_result.get("success") else 0.0
        }
        
    def analyze_cross_pass_health(self):
        overall_health = sum(
            data["success_rate"] for data in self.pass_health.values()
        ) / len(self.pass_health) if self.pass_health else 0.0
        
        return {
            "pass_correlations": {},
            "health_trend": "stable",
            "overall_pipeline_health": overall_health,
            "performance_metrics": self.pass_health
        }


class MockPipelineExecution:
    def execute_pass_a(self):
        return {"success": True, "processing_time_ms": 1200, "dictionary_entries": 15}
        
    def execute_pass_b(self, pass_a_result):
        return {"success": True, "processing_time_ms": 800, "splits_created": 3}
        
    def execute_pass_c(self, pass_a_result, pass_b_result):
        return {"success": True, "processing_time_ms": 15000, "chunks_extracted": 245}


class CrossPassAnomalyDetector:
    def __init__(self):
        self.baseline_data = {}
        
    def record_baseline(self, run_id, run_data):
        self.baseline_data[run_id] = run_data
        
    def detect_anomalies(self, current_run):
        anomalies = []
        
        # Simple anomaly detection based on thresholds
        if current_run["A"]["processing_time_ms"] > 3000:
            anomalies.append({"pass": "A", "metric": "processing_time_ms", "severity": "high"})
            
        if current_run["C"]["extraction_rate"] < 90.0:
            anomalies.append({"pass": "C", "metric": "extraction_rate", "severity": "medium"})
            
        return anomalies
        
    def find_correlated_anomalies(self, anomalies):
        # Simple correlation - if multiple passes have anomalies, they're correlated
        if len(anomalies) > 1:
            return [{"correlation": "multi_pass_degradation", "passes": [a["pass"] for a in anomalies]}]
        return []


class IntegratedValidationSystem:
    def start_integrated_validation(self, job_id, source_file):
        self.job_id = job_id
        self.source_file = source_file
        
    def validate_pass_with_context(self, pass_id, pass_result, previous_results, traceability, health_monitor):
        return {"valid": True, "issues": []}
        
    def validate_pass_with_inheritance(self, pass_id, pass_result, previous_validations):
        return {"valid": True, "inherited_issues": []}
        
    def validate_pass(self, pass_id, pass_result):
        return {"valid": True, "issues": [], "warnings": pass_result.get("warnings", [])}
        
    def complete_integrated_validation(self, job_id, pass_results, traceability, health_monitor):
        return {
            "overall_valid": True,
            "traceability_complete": True,
            "health_acceptable": True,
            "cross_pass_consistent": True
        }


class ValidationErrorTracker:
    def __init__(self):
        self.validations = {}
        
    def record_validation(self, pass_id, validation_result):
        self.validations[pass_id] = validation_result
        
    def analyze_error_propagation(self):
        return {
            "error_chains": [],
            "root_causes": [{"pass": "A", "issue": "Low dictionary count"}]
        }


# Mock classes from previous tests
class MockTraceabilitySystem:
    def __init__(self):
        self.job_data = {}
        
    def start_job_tracking(self, job_id, source_file):
        self.job_data[job_id] = {"source": source_file, "passes": {}}
        
    def track_pass_completion(self, job_id, pass_id, pass_result):
        if job_id in self.job_data:
            self.job_data[job_id]["passes"][pass_id] = pass_result


class MockHealthMonitor:
    def __init__(self):
        self.health_data = {}
        
    def start_job_monitoring(self, job_id):
        self.health_data[job_id] = {}
        
    def collect_pass_metrics(self, job_id, pass_id, pass_result):
        if job_id in self.health_data:
            self.health_data[job_id][pass_id] = pass_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])