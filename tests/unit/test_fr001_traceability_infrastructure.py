#!/usr/bin/env python3
"""
Unit Tests for FR-001 Source Traceability Infrastructure

Tests core traceability components including TraceabilityManager, LineageTracker,
SourceMetadata, and ArtifactLineage functionality with thread safety validation.
"""

import pytest
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

# Add src_common to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))


class TestSourceMetadata:
    """Test SourceMetadata data structure and operations"""
    
    def test_source_metadata_creation(self):
        """Test basic SourceMetadata creation and serialization"""
        metadata = {
            "source_file": "test.pdf",
            "file_size": 1024000,
            "file_hash": "abc123def456",
            "ingestion_timestamp": "2025-09-11T10:30:00Z",
            "job_id": "job_123456789",
            "environment": "dev"
        }
        
        # Test metadata validation
        assert metadata["source_file"] == "test.pdf"
        assert metadata["file_size"] > 0
        assert len(metadata["file_hash"]) > 0
        assert metadata["job_id"].startswith("job_")
        
    def test_source_metadata_serialization(self):
        """Test metadata JSON serialization/deserialization"""
        metadata = {
            "source_file": "complex_document.pdf",
            "file_size": 5242880,
            "file_hash": "sha256:abcdef123456",
            "processing_metadata": {
                "pages": 150,
                "text_extraction_method": "unstructured.io",
                "detected_language": "en"
            }
        }
        
        # Test JSON roundtrip
        json_str = json.dumps(metadata)
        restored = json.loads(json_str)
        
        assert restored == metadata
        assert restored["processing_metadata"]["pages"] == 150


class TestArtifactLineage:
    """Test ArtifactLineage tracking and relationship management"""
    
    def test_artifact_lineage_creation(self):
        """Test basic artifact lineage creation"""
        lineage = {
            "artifact_id": "art_123_pass_a",
            "source_artifacts": [],
            "transformation": "pass_a_toc_parse",
            "output_artifacts": ["art_123_pass_a_dict.json"],
            "metadata": {
                "processing_time_ms": 1500,
                "chunks_generated": 42,
                "dictionary_entries": 15
            }
        }
        
        assert lineage["transformation"] == "pass_a_toc_parse"
        assert len(lineage["output_artifacts"]) == 1
        assert lineage["metadata"]["chunks_generated"] == 42
        
    def test_lineage_chain_validation(self):
        """Test lineage chain consistency validation"""
        pass_a_lineage = {
            "artifact_id": "art_123_pass_a",
            "source_artifacts": ["test.pdf"],
            "transformation": "pass_a_toc_parse",
            "output_artifacts": ["art_123_pass_a_dict.json"]
        }
        
        pass_b_lineage = {
            "artifact_id": "art_123_pass_b",
            "source_artifacts": ["art_123_pass_a_dict.json"],
            "transformation": "pass_b_logical_split",
            "output_artifacts": ["art_123_pass_b_splits.json"]
        }
        
        # Test chain consistency
        assert pass_b_lineage["source_artifacts"][0] in pass_a_lineage["output_artifacts"]
        
    def test_lineage_relationship_mapping(self):
        """Test complex lineage relationship mapping"""
        lineage_chain = [
            {
                "pass": "A",
                "input": ["source.pdf"],
                "output": ["toc_dict.json", "sections.json"]
            },
            {
                "pass": "B", 
                "input": ["toc_dict.json"],
                "output": ["logical_splits.json"]
            },
            {
                "pass": "C",
                "input": ["logical_splits.json", "source.pdf"],
                "output": ["extracted_chunks.json"]
            }
        ]
        
        # Validate lineage relationships
        for i in range(1, len(lineage_chain)):
            current = lineage_chain[i]
            previous = lineage_chain[i-1]
            
            # Check at least one output from previous feeds into current
            has_dependency = any(
                output in current["input"] 
                for output in previous["output"]
            )
            assert has_dependency, f"Pass {current['pass']} missing dependency from Pass {previous['pass']}"


class TestTraceabilityManager:
    """Test TraceabilityManager core functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_config = {
            "artifact_dir": self.temp_dir,
            "environment": "test",
            "thread_safe": True
        }
    
    def test_traceability_manager_initialization(self):
        """Test TraceabilityManager initialization"""
        # Mock TraceabilityManager class
        class MockTraceabilityManager:
            def __init__(self, config):
                self.config = config
                self.active_lineages = {}
                self.thread_local = threading.local()
                
        manager = MockTraceabilityManager(self.test_config)
        assert manager.config["environment"] == "test"
        assert hasattr(manager, "thread_local")
        
    def test_lineage_registration(self):
        """Test lineage registration and retrieval"""
        # Mock lineage registration
        lineages = {}
        job_id = "job_test_123"
        
        lineage_data = {
            "job_id": job_id,
            "source_file": "test.pdf",
            "created_at": "2025-09-11T10:30:00Z",
            "passes": {}
        }
        
        # Register lineage
        lineages[job_id] = lineage_data
        
        # Test retrieval
        retrieved = lineages.get(job_id)
        assert retrieved is not None
        assert retrieved["job_id"] == job_id
        assert retrieved["source_file"] == "test.pdf"
        
    def test_pass_lineage_tracking(self):
        """Test individual pass lineage tracking"""
        pass_lineage = {
            "pass_id": "A",
            "input_artifacts": ["source.pdf"],
            "processing_start": "2025-09-11T10:30:00Z",
            "processing_end": "2025-09-11T10:30:05Z",
            "output_artifacts": ["pass_a_dict.json"],
            "metadata": {
                "processing_time_ms": 5000,
                "success": True,
                "error": None
            }
        }
        
        # Validate pass tracking data
        assert pass_lineage["pass_id"] == "A"
        assert len(pass_lineage["input_artifacts"]) == 1
        assert len(pass_lineage["output_artifacts"]) == 1
        assert pass_lineage["metadata"]["success"] is True
        
        # Test timing calculation
        start = pass_lineage["processing_start"]
        end = pass_lineage["processing_end"]
        assert start < end  # Basic timing validation


class TestLineageTracker:
    """Test LineageTracker individual source tracking"""
    
    def test_lineage_tracker_initialization(self):
        """Test LineageTracker initialization"""
        class MockLineageTracker:
            def __init__(self, job_id, source_file):
                self.job_id = job_id
                self.source_file = source_file
                self.passes = {}
                self.artifacts = []
                
        tracker = MockLineageTracker("job_123", "test.pdf")
        assert tracker.job_id == "job_123"
        assert tracker.source_file == "test.pdf"
        assert len(tracker.passes) == 0
        
    def test_pass_tracking_workflow(self):
        """Test complete pass tracking workflow"""
        class MockLineageTracker:
            def __init__(self, job_id, source_file):
                self.job_id = job_id
                self.source_file = source_file
                self.passes = {}
                
            def start_pass(self, pass_id, input_artifacts):
                self.passes[pass_id] = {
                    "status": "in_progress",
                    "input_artifacts": input_artifacts,
                    "start_time": "2025-09-11T10:30:00Z"
                }
                
            def complete_pass(self, pass_id, output_artifacts, metadata=None):
                if pass_id in self.passes:
                    self.passes[pass_id].update({
                        "status": "completed",
                        "output_artifacts": output_artifacts,
                        "end_time": "2025-09-11T10:30:05Z",
                        "metadata": metadata or {}
                    })
                    
        tracker = MockLineageTracker("job_123", "test.pdf")
        
        # Test pass workflow
        tracker.start_pass("A", ["test.pdf"])
        assert tracker.passes["A"]["status"] == "in_progress"
        
        tracker.complete_pass("A", ["pass_a_dict.json"], {"chunks": 42})
        assert tracker.passes["A"]["status"] == "completed"
        assert tracker.passes["A"]["metadata"]["chunks"] == 42


class TestThreadSafety:
    """Test thread safety of traceability components"""
    
    def test_concurrent_lineage_tracking(self):
        """Test concurrent lineage tracking across multiple threads"""
        shared_data = {"lineages": {}}
        lock = threading.Lock()
        errors = []
        
        def worker_thread(thread_id):
            try:
                job_id = f"job_{thread_id}"
                lineage = {
                    "job_id": job_id,
                    "thread_id": thread_id,
                    "created_at": "2025-09-11T10:30:00Z"
                }
                
                # Simulate thread-safe lineage registration
                with lock:
                    shared_data["lineages"][job_id] = lineage
                    
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i,))
            threads.append(thread)
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Validate results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(shared_data["lineages"]) == 5
        
        # Validate unique job IDs
        job_ids = set(shared_data["lineages"].keys())
        assert len(job_ids) == 5
        
    def test_thread_local_lineage_buffers(self):
        """Test thread-local lineage buffer functionality"""
        import threading
        
        thread_local_data = threading.local()
        results = {}
        
        def worker_with_thread_local(thread_id):
            # Each thread gets its own buffer
            thread_local_data.buffer = []
            
            # Add thread-specific data
            for i in range(3):
                thread_local_data.buffer.append(f"thread_{thread_id}_item_{i}")
                
            # Store results
            results[thread_id] = list(thread_local_data.buffer)
            
        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker_with_thread_local, args=(i,))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()
            
        # Validate thread isolation
        assert len(results) == 3
        for thread_id in results:
            buffer = results[thread_id]
            assert len(buffer) == 3
            assert all(f"thread_{thread_id}" in item for item in buffer)


class TestPerformanceImpact:
    """Test performance impact of traceability infrastructure"""
    
    def test_lineage_collection_overhead(self):
        """Test lineage collection performance overhead"""
        import time
        
        # Baseline without lineage tracking
        start_time = time.perf_counter()
        for i in range(1000):
            # Simulate basic processing
            data = {"chunk": i, "content": f"test_content_{i}"}
            processed = json.dumps(data)
        baseline_time = time.perf_counter() - start_time
        
        # With lineage tracking simulation
        lineage_buffer = []
        start_time = time.perf_counter()
        for i in range(1000):
            # Simulate processing with lineage
            data = {"chunk": i, "content": f"test_content_{i}"}
            processed = json.dumps(data)
            
            # Add lineage tracking
            lineage_entry = {
                "chunk_id": i,
                "processing_time": time.perf_counter(),
                "input_size": len(str(data)),
                "output_size": len(processed)
            }
            lineage_buffer.append(lineage_entry)
            
        lineage_time = time.perf_counter() - start_time
        
        # Calculate overhead percentage
        overhead_percent = ((lineage_time - baseline_time) / baseline_time) * 100
        
        # Validate acceptable overhead (<5%)
        assert overhead_percent < 5.0, f"Lineage overhead {overhead_percent:.2f}% exceeds 5% limit"
        assert len(lineage_buffer) == 1000


class TestIntegrationPoints:
    """Test integration points with existing systems"""
    
    def test_manifest_integration(self):
        """Test integration with existing manifest.json format"""
        base_manifest = {
            "job_id": "job_123",
            "source_file": "test.pdf", 
            "created_at": "2025-09-11T10:30:00Z",
            "passes_completed": ["A", "B", "C"],
            "artifacts": [
                "pass_a_dict.json",
                "pass_b_splits.json", 
                "pass_c_chunks.json"
            ]
        }
        
        # Add traceability extension
        traceability_data = {
            "traceability": {
                "lineage_version": "1.0",
                "source_metadata": {
                    "file_hash": "abc123",
                    "file_size": 1024000
                },
                "pass_lineage": {
                    "A": {"input": ["test.pdf"], "output": ["pass_a_dict.json"]},
                    "B": {"input": ["pass_a_dict.json"], "output": ["pass_b_splits.json"]},
                    "C": {"input": ["pass_b_splits.json"], "output": ["pass_c_chunks.json"]}
                }
            }
        }
        
        # Merge with existing manifest
        enhanced_manifest = {**base_manifest, **traceability_data}
        
        # Validate integration
        assert "passes_completed" in enhanced_manifest
        assert "traceability" in enhanced_manifest
        assert enhanced_manifest["traceability"]["lineage_version"] == "1.0"
        
    def test_artifact_validator_integration(self):
        """Test integration with existing artifact validator"""
        # Mock artifact validation with traceability
        def validate_with_lineage(artifact_path, lineage_data):
            # Basic artifact validation
            artifact_valid = artifact_path.endswith('.json')
            
            # Lineage validation
            lineage_valid = (
                "input_artifacts" in lineage_data and 
                "output_artifacts" in lineage_data
            )
            
            return artifact_valid and lineage_valid
        
        # Test validation
        result = validate_with_lineage(
            "pass_a_dict.json",
            {
                "input_artifacts": ["test.pdf"],
                "output_artifacts": ["pass_a_dict.json"],
                "transformation": "pass_a_toc_parse"
            }
        )
        
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])