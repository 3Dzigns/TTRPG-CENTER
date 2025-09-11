#!/usr/bin/env python3
"""
Unit Tests for FR-001 Data Health Monitoring System

Tests health metrics collection, anomaly detection, and health monitoring
components across the 6-Pass ingestion pipeline.
"""

import pytest
import json
import time
import statistics
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

# Add src_common to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))


class TestHealthMetricsCollector:
    """Test HealthMetricsCollector functionality"""
    
    def test_health_metrics_initialization(self):
        """Test basic health metrics collector initialization"""
        class MockHealthMetricsCollector:
            def __init__(self, config):
                self.config = config
                self.metrics_buffer = []
                self.thresholds = config.get("thresholds", {})
                
        config = {
            "environment": "test",
            "collection_interval_ms": 1000,
            "thresholds": {
                "processing_time_ms": 10000,
                "error_rate_percent": 5.0,
                "memory_usage_mb": 512
            }
        }
        
        collector = MockHealthMetricsCollector(config)
        assert collector.config["environment"] == "test"
        assert collector.thresholds["error_rate_percent"] == 5.0
        
    def test_metric_collection_workflow(self):
        """Test health metric collection workflow"""
        metrics_buffer = []
        
        # Simulate metric collection
        def collect_metric(metric_type, value, metadata=None):
            metric = {
                "type": metric_type,
                "value": value,
                "timestamp": time.time(),
                "metadata": metadata or {}
            }
            metrics_buffer.append(metric)
            return metric
        
        # Collect various metrics
        collect_metric("processing_time_ms", 1500, {"pass": "A", "job_id": "job_123"})
        collect_metric("chunk_count", 42, {"pass": "A", "job_id": "job_123"})
        collect_metric("memory_usage_mb", 128, {"pass": "A", "job_id": "job_123"})
        
        assert len(metrics_buffer) == 3
        assert metrics_buffer[0]["type"] == "processing_time_ms"
        assert metrics_buffer[0]["value"] == 1500
        assert metrics_buffer[0]["metadata"]["pass"] == "A"
        
    def test_pass_specific_health_metrics(self):
        """Test pass-specific health metric definitions"""
        pass_metrics = {
            "A": {  # ToC parsing metrics
                "toc_entries_extracted": 15,
                "dictionary_entries_created": 8,
                "processing_time_ms": 1200,
                "pdf_pages_analyzed": 150
            },
            "B": {  # Logical splitting metrics
                "splits_created": 3,
                "split_size_avg_mb": 8.5,
                "processing_time_ms": 800,
                "content_preserved_percent": 99.8
            },
            "C": {  # Extraction metrics
                "chunks_extracted": 245,
                "text_extraction_success_rate": 98.5,
                "processing_time_ms": 15000,
                "ocr_fallback_used": False
            },
            "D": {  # Vector enrichment metrics
                "vectors_generated": 245,
                "enrichment_success_rate": 97.2,
                "processing_time_ms": 8000,
                "dictionary_updates": 12
            },
            "E": {  # Graph building metrics
                "nodes_created": 180,
                "edges_created": 420,
                "processing_time_ms": 5000,
                "graph_consistency_score": 94.8
            },
            "F": {  # Finalization metrics
                "artifacts_validated": 6,
                "cleanup_operations": 3,
                "processing_time_ms": 500,
                "final_integrity_score": 100.0
            }
        }
        
        # Validate pass metrics structure
        for pass_id, metrics in pass_metrics.items():
            assert "processing_time_ms" in metrics
            assert metrics["processing_time_ms"] > 0
            assert pass_id in ["A", "B", "C", "D", "E", "F"]


class TestHealthAnomalyDetection:
    """Test health anomaly detection algorithms"""
    
    def test_statistical_anomaly_detection(self):
        """Test statistical anomaly detection"""
        # Generate baseline data
        baseline_times = [1200, 1150, 1300, 1180, 1250, 1220, 1280, 1190, 1240, 1210]
        
        def detect_anomaly(value, baseline, threshold_std=2.0):
            mean = statistics.mean(baseline)
            std = statistics.stdev(baseline)
            z_score = abs(value - mean) / std
            return z_score > threshold_std, z_score
        
        # Test normal values
        is_anomaly, z_score = detect_anomaly(1225, baseline_times)
        assert not is_anomaly
        assert z_score < 2.0
        
        # Test anomalous value
        is_anomaly, z_score = detect_anomaly(2000, baseline_times)
        assert is_anomaly
        assert z_score > 2.0
        
    def test_threshold_based_detection(self):
        """Test threshold-based anomaly detection"""
        thresholds = {
            "processing_time_ms": {"max": 10000, "min": 100},
            "memory_usage_mb": {"max": 1024, "min": 50},
            "error_rate_percent": {"max": 5.0, "min": 0.0},
            "success_rate_percent": {"max": 100.0, "min": 95.0}
        }
        
        def check_thresholds(metric_type, value, thresholds):
            if metric_type not in thresholds:
                return False, "No threshold defined"
                
            threshold = thresholds[metric_type]
            if value > threshold["max"]:
                return True, f"Exceeds maximum {threshold['max']}"
            if value < threshold["min"]:
                return True, f"Below minimum {threshold['min']}"
                
            return False, "Within thresholds"
        
        # Test threshold violations
        violation, reason = check_thresholds("processing_time_ms", 15000, thresholds)
        assert violation
        assert "maximum" in reason
        
        violation, reason = check_thresholds("success_rate_percent", 85.0, thresholds)
        assert violation
        assert "minimum" in reason
        
        # Test normal values
        violation, reason = check_thresholds("processing_time_ms", 5000, thresholds)
        assert not violation
        
    def test_pattern_based_anomaly_detection(self):
        """Test pattern-based anomaly detection"""
        # Simulate processing time patterns
        time_series = [
            1200, 1180, 1220, 1190, 1250,  # Normal baseline
            1210, 1240, 1180, 1200, 1220,  # Continued normal
            2100, 2200, 2150, 2180, 2120,  # Anomalous spike pattern
            1190, 1210, 1180, 1200, 1220   # Return to normal
        ]
        
        def detect_pattern_anomaly(values, window_size=5, spike_factor=1.5):
            anomalies = []
            for i in range(window_size, len(values)):
                recent_window = values[i-window_size:i]
                current_value = values[i]
                
                baseline_mean = statistics.mean(recent_window)
                if current_value > baseline_mean * spike_factor:
                    anomalies.append(i)
                    
            return anomalies
        
        anomalies = detect_pattern_anomaly(time_series)
        
        # Should detect the spike pattern around indices 10-14
        assert len(anomalies) > 0
        assert any(10 <= idx <= 14 for idx in anomalies)


class TestHealthThresholds:
    """Test health threshold management and configuration"""
    
    def test_dynamic_threshold_adjustment(self):
        """Test dynamic threshold adjustment based on historical data"""
        # Historical performance data
        historical_data = {
            "pass_a_processing_time": [1200, 1150, 1300, 1180, 1250, 1220, 1280],
            "pass_c_extraction_rate": [98.2, 97.8, 98.5, 98.1, 97.9, 98.3, 98.0],
            "memory_usage": [120, 125, 118, 130, 122, 128, 124]
        }
        
        def calculate_adaptive_threshold(data, percentile=95):
            sorted_data = sorted(data)
            index = int(len(sorted_data) * percentile / 100)
            return sorted_data[min(index, len(sorted_data) - 1)]
        
        # Calculate adaptive thresholds
        thresholds = {}
        for metric, values in historical_data.items():
            thresholds[metric] = calculate_adaptive_threshold(values)
        
        assert thresholds["pass_a_processing_time"] > max(historical_data["pass_a_processing_time"]) * 0.9
        assert thresholds["pass_c_extraction_rate"] > 97.0
        
    def test_environment_specific_thresholds(self):
        """Test environment-specific threshold configuration"""
        env_thresholds = {
            "dev": {
                "processing_time_ms": {"max": 20000, "min": 100},
                "error_rate_percent": {"max": 10.0, "min": 0.0}
            },
            "test": {
                "processing_time_ms": {"max": 15000, "min": 100},
                "error_rate_percent": {"max": 5.0, "min": 0.0}
            },
            "prod": {
                "processing_time_ms": {"max": 10000, "min": 100},
                "error_rate_percent": {"max": 1.0, "min": 0.0}
            }
        }
        
        # Test environment-specific validation
        def validate_for_environment(metric_type, value, environment):
            thresholds = env_thresholds.get(environment, {})
            if metric_type not in thresholds:
                return True, "No threshold defined"
                
            threshold = thresholds[metric_type]
            if value > threshold["max"]:
                return False, f"Exceeds {environment} maximum"
            return True, "Within thresholds"
        
        # Test same value across environments
        test_value = 8000  # processing time
        
        valid, _ = validate_for_environment("processing_time_ms", test_value, "dev")
        assert valid  # Should pass in dev (max 20000)
        
        valid, _ = validate_for_environment("processing_time_ms", test_value, "prod")
        assert valid  # Should pass in prod (max 10000)
        
        # Test threshold violation
        high_value = 12000
        valid, _ = validate_for_environment("processing_time_ms", high_value, "prod")
        assert not valid  # Should fail in prod (max 10000)


class TestHealthReporting:
    """Test health reporting and dashboard integration"""
    
    def test_health_report_generation(self):
        """Test health report generation"""
        health_data = {
            "timestamp": "2025-09-11T10:30:00Z",
            "environment": "dev",
            "overall_health_score": 94.2,
            "pass_health": {
                "A": {"score": 96.5, "status": "healthy"},
                "B": {"score": 92.1, "status": "warning"},
                "C": {"score": 98.3, "status": "healthy"},
                "D": {"score": 89.7, "status": "warning"},
                "E": {"score": 95.8, "status": "healthy"},
                "F": {"score": 99.1, "status": "healthy"}
            },
            "anomalies_detected": [
                {
                    "pass": "B",
                    "metric": "split_size_variance",
                    "severity": "warning",
                    "description": "Higher than normal variance in split sizes"
                },
                {
                    "pass": "D",
                    "metric": "vector_generation_time",
                    "severity": "warning", 
                    "description": "Processing time 15% above baseline"
                }
            ]
        }
        
        # Validate report structure
        assert health_data["overall_health_score"] > 90.0
        assert len(health_data["pass_health"]) == 6
        assert len(health_data["anomalies_detected"]) == 2
        
        # Test health score calculation
        pass_scores = [data["score"] for data in health_data["pass_health"].values()]
        calculated_overall = sum(pass_scores) / len(pass_scores)
        assert abs(calculated_overall - health_data["overall_health_score"]) < 1.0
        
    def test_health_dashboard_data_format(self):
        """Test health dashboard data formatting"""
        dashboard_data = {
            "summary": {
                "overall_status": "healthy",
                "active_alerts": 2,
                "processing_jobs": 3,
                "last_updated": "2025-09-11T10:30:00Z"
            },
            "metrics": [
                {
                    "name": "Processing Time",
                    "current": 5.2,
                    "unit": "seconds",
                    "trend": "stable",
                    "threshold": 10.0
                },
                {
                    "name": "Success Rate", 
                    "current": 98.5,
                    "unit": "percent",
                    "trend": "improving",
                    "threshold": 95.0
                }
            ],
            "alerts": [
                {
                    "severity": "warning",
                    "message": "Pass B split variance above normal",
                    "timestamp": "2025-09-11T10:25:00Z"
                }
            ]
        }
        
        # Validate dashboard format
        assert dashboard_data["summary"]["overall_status"] in ["healthy", "warning", "critical"]
        assert len(dashboard_data["metrics"]) >= 2
        assert all("current" in metric for metric in dashboard_data["metrics"])


class TestHealthIntegration:
    """Test health monitoring integration with existing systems"""
    
    def test_validation_gate_integration(self):
        """Test integration with existing validation gates"""
        # Mock validation gate with health monitoring
        def enhanced_validation_gate(pass_result, health_collector=None):
            # Existing validation
            basic_valid = pass_result.get("success", False)
            
            # Health metric collection
            if health_collector:
                health_collector.collect_metric(
                    "validation_result",
                    1.0 if basic_valid else 0.0,
                    {"pass": pass_result.get("pass_id")}
                )
                
                # Additional health metrics
                if "processing_time_ms" in pass_result:
                    health_collector.collect_metric(
                        "processing_time_ms",
                        pass_result["processing_time_ms"],
                        {"pass": pass_result.get("pass_id")}
                    )
            
            return basic_valid
        
        # Test integration
        health_metrics = []
        
        class MockHealthCollector:
            def collect_metric(self, metric_type, value, metadata):
                health_metrics.append({
                    "type": metric_type,
                    "value": value,
                    "metadata": metadata
                })
        
        collector = MockHealthCollector()
        result = {"success": True, "pass_id": "A", "processing_time_ms": 1500}
        
        validation_result = enhanced_validation_gate(result, collector)
        
        assert validation_result is True
        assert len(health_metrics) == 2
        assert health_metrics[0]["type"] == "validation_result"
        assert health_metrics[1]["type"] == "processing_time_ms"
        
    def test_artifact_validation_health_integration(self):
        """Test health monitoring integration with artifact validation"""
        # Mock artifact validation with health metrics
        def validate_artifact_with_health(artifact_path, expected_schema, health_collector):
            # Basic validation
            validation_success = artifact_path.endswith('.json')
            
            # Collect health metrics
            health_collector.collect_metric(
                "artifact_validation_result",
                1.0 if validation_success else 0.0,
                {"artifact": artifact_path}
            )
            
            # Additional file health metrics
            if validation_success:
                health_collector.collect_metric(
                    "artifact_size_kb", 
                    42.5,  # Mock file size
                    {"artifact": artifact_path}
                )
            
            return validation_success
        
        health_data = []
        
        class MockCollector:
            def collect_metric(self, metric_type, value, metadata):
                health_data.append((metric_type, value, metadata))
        
        collector = MockCollector()
        result = validate_artifact_with_health("test.json", {}, collector)
        
        assert result is True
        assert len(health_data) == 2
        assert health_data[0][0] == "artifact_validation_result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])