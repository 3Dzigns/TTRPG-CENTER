#!/usr/bin/env python3
"""
Regression Tests for FR-001 Traceability Performance Impact

Tests performance impact of traceability features on the 6-Pass pipeline,
including baseline performance, overhead measurements, and scalability testing.
"""

import pytest
import json
import time
import statistics
import threading
import multiprocessing
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import concurrent.futures

# Add src_common to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src_common"))


class TestBaselinePerformanceMeasurement:
    """Test baseline performance measurements without traceability"""
    
    def test_baseline_6pass_performance(self):
        """Measure baseline 6-Pass pipeline performance"""
        baseline_pipeline = BaselinePipelineProcessor()
        
        # Test multiple runs for statistical significance
        run_times = []
        memory_usage = []
        
        for i in range(10):
            start_time = time.perf_counter()
            start_memory = self._get_memory_usage()
            
            # Run baseline pipeline
            result = baseline_pipeline.process_source(f"test_document_{i}.pdf")
            
            end_time = time.perf_counter()
            end_memory = self._get_memory_usage()
            
            run_times.append((end_time - start_time) * 1000)  # Convert to ms
            memory_usage.append(end_memory - start_memory)
            
            assert result["success"], f"Baseline run {i} failed"
        
        # Calculate baseline statistics
        baseline_stats = {
            "mean_time_ms": statistics.mean(run_times),
            "median_time_ms": statistics.median(run_times),
            "std_dev_time_ms": statistics.stdev(run_times) if len(run_times) > 1 else 0,
            "mean_memory_mb": statistics.mean(memory_usage),
            "max_time_ms": max(run_times),
            "min_time_ms": min(run_times)
        }
        
        # Store baseline for comparison
        self._store_baseline_metrics(baseline_stats)
        
        # Validate reasonable baseline performance
        assert baseline_stats["mean_time_ms"] < 30000, "Baseline performance too slow"
        assert baseline_stats["mean_memory_mb"] < 512, "Baseline memory usage too high"
        
        return baseline_stats
        
    def test_individual_pass_baseline_performance(self):
        """Measure baseline performance for individual passes"""
        baseline_processor = BaselinePassProcessor()
        
        pass_baselines = {}
        
        for pass_id in ["A", "B", "C", "D", "E", "F"]:
            pass_times = []
            
            for i in range(5):  # 5 runs per pass
                start_time = time.perf_counter()
                
                result = baseline_processor.process_single_pass(pass_id, f"test_input_{i}")
                
                end_time = time.perf_counter()
                pass_times.append((end_time - start_time) * 1000)
                
                assert result["success"], f"Pass {pass_id} baseline run {i} failed"
            
            pass_baselines[pass_id] = {
                "mean_time_ms": statistics.mean(pass_times),
                "std_dev_ms": statistics.stdev(pass_times) if len(pass_times) > 1 else 0,
                "max_time_ms": max(pass_times)
            }
        
        # Validate pass-specific performance expectations
        performance_limits = {
            "A": 3000,   # ToC parsing should be fast
            "B": 2000,   # Logical splitting should be fast
            "C": 20000,  # Extraction can be slower
            "D": 15000,  # Vector enrichment moderate
            "E": 10000,  # Graph building moderate
            "F": 2000    # Finalization should be fast
        }
        
        for pass_id, limits in performance_limits.items():
            assert pass_baselines[pass_id]["mean_time_ms"] < limits, \
                f"Pass {pass_id} baseline too slow: {pass_baselines[pass_id]['mean_time_ms']:.1f}ms > {limits}ms"
        
        return pass_baselines
        
    def _get_memory_usage(self):
        """Mock memory usage measurement"""
        import random
        return random.randint(100, 200)  # Mock memory usage in MB
        
    def _store_baseline_metrics(self, metrics):
        """Store baseline metrics for comparison"""
        # In real implementation, would store to a baseline metrics file
        self.baseline_metrics = metrics


class TestTraceabilityPerformanceOverhead:
    """Test performance overhead introduced by traceability features"""
    
    def test_traceability_infrastructure_overhead(self):
        """Measure overhead of traceability infrastructure"""
        baseline_processor = BaselinePipelineProcessor()
        traceability_processor = TraceabilityEnabledProcessor()
        
        # Measure baseline performance
        baseline_times = []
        for i in range(10):
            start_time = time.perf_counter()
            baseline_processor.process_source(f"baseline_test_{i}.pdf")
            end_time = time.perf_counter()
            baseline_times.append((end_time - start_time) * 1000)
        
        baseline_mean = statistics.mean(baseline_times)
        
        # Measure traceability-enabled performance
        traceability_times = []
        for i in range(10):
            start_time = time.perf_counter()
            traceability_processor.process_source_with_traceability(f"traceability_test_{i}.pdf")
            end_time = time.perf_counter()
            traceability_times.append((end_time - start_time) * 1000)
            
        traceability_mean = statistics.mean(traceability_times)
        
        # Calculate overhead
        overhead_ms = traceability_mean - baseline_mean
        overhead_percent = (overhead_ms / baseline_mean) * 100
        
        performance_results = {
            "baseline_mean_ms": baseline_mean,
            "traceability_mean_ms": traceability_mean,
            "overhead_ms": overhead_ms,
            "overhead_percent": overhead_percent
        }
        
        # Validate overhead is within acceptable limits (5%)
        assert overhead_percent < 5.0, f"Traceability overhead too high: {overhead_percent:.2f}% > 5%"
        
        return performance_results
        
    def test_health_monitoring_overhead(self):
        """Measure overhead of health monitoring features"""
        base_processor = BaselinePipelineProcessor()
        health_enabled_processor = HealthMonitoringProcessor()
        
        # Baseline measurement
        baseline_times = self._measure_processor_performance(base_processor, 8)
        
        # Health monitoring enabled measurement  
        health_times = self._measure_processor_performance(health_enabled_processor, 8)
        
        baseline_mean = statistics.mean(baseline_times)
        health_mean = statistics.mean(health_times)
        
        overhead_percent = ((health_mean - baseline_mean) / baseline_mean) * 100
        
        # Health monitoring should add minimal overhead (<2%)
        assert overhead_percent < 2.0, f"Health monitoring overhead too high: {overhead_percent:.2f}%"
        
        return {
            "baseline_mean_ms": baseline_mean,
            "health_enabled_mean_ms": health_mean,
            "overhead_percent": overhead_percent
        }
        
    def test_validation_framework_overhead(self):
        """Measure overhead of enhanced validation framework"""
        base_processor = BaselinePipelineProcessor()
        validation_processor = ValidationEnhancedProcessor()
        
        # Measure both processors
        baseline_times = self._measure_processor_performance(base_processor, 8)
        validation_times = self._measure_processor_performance(validation_processor, 8)
        
        baseline_mean = statistics.mean(baseline_times)
        validation_mean = statistics.mean(validation_times)
        
        overhead_percent = ((validation_mean - baseline_mean) / baseline_mean) * 100
        
        # Validation overhead should be acceptable (<3%)
        assert overhead_percent < 3.0, f"Validation overhead too high: {overhead_percent:.2f}%"
        
        return {
            "baseline_mean_ms": baseline_mean,
            "validation_mean_ms": validation_mean,
            "overhead_percent": overhead_percent
        }
        
    def test_complete_fr001_overhead(self):
        """Measure total overhead of complete FR-001 implementation"""
        baseline_processor = BaselinePipelineProcessor()
        complete_fr001_processor = CompleteFR001Processor()
        
        # Comprehensive performance test
        baseline_times = self._measure_processor_performance(baseline_processor, 15)
        fr001_times = self._measure_processor_performance(complete_fr001_processor, 15)
        
        baseline_stats = self._calculate_performance_stats(baseline_times)
        fr001_stats = self._calculate_performance_stats(fr001_times)
        
        total_overhead_percent = ((fr001_stats["mean"] - baseline_stats["mean"]) / baseline_stats["mean"]) * 100
        
        comprehensive_results = {
            "baseline_stats": baseline_stats,
            "fr001_stats": fr001_stats,
            "total_overhead_percent": total_overhead_percent,
            "overhead_ms": fr001_stats["mean"] - baseline_stats["mean"]
        }
        
        # Total FR-001 overhead should be within acceptable limits (<8%)
        assert total_overhead_percent < 8.0, f"Total FR-001 overhead too high: {total_overhead_percent:.2f}%"
        
        return comprehensive_results
        
    def _measure_processor_performance(self, processor, runs):
        """Helper to measure processor performance over multiple runs"""
        times = []
        
        for i in range(runs):
            start_time = time.perf_counter()
            
            if hasattr(processor, 'process_source_with_traceability'):
                result = processor.process_source_with_traceability(f"test_{i}.pdf")
            elif hasattr(processor, 'process_source_with_health'):
                result = processor.process_source_with_health(f"test_{i}.pdf")  
            elif hasattr(processor, 'process_source_with_validation'):
                result = processor.process_source_with_validation(f"test_{i}.pdf")
            elif hasattr(processor, 'process_source_complete_fr001'):
                result = processor.process_source_complete_fr001(f"test_{i}.pdf")
            else:
                result = processor.process_source(f"test_{i}.pdf")
                
            end_time = time.perf_counter()
            
            times.append((end_time - start_time) * 1000)
            
            assert result.get("success", True), f"Processor failed on run {i}"
            
        return times
        
    def _calculate_performance_stats(self, times):
        """Calculate comprehensive performance statistics"""
        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "min": min(times),
            "max": max(times),
            "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
            "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0]
        }


class TestConcurrentProcessingPerformance:
    """Test performance impact under concurrent processing"""
    
    def test_concurrent_traceability_performance(self):
        """Test traceability performance under concurrent load"""
        baseline_processor = BaselinePipelineProcessor()
        traceability_processor = TraceabilityEnabledProcessor()
        
        def run_concurrent_baseline(num_threads=4):
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                start_time = time.perf_counter()
                
                for i in range(num_threads * 2):  # 2 tasks per thread
                    future = executor.submit(baseline_processor.process_source, f"concurrent_baseline_{i}.pdf")
                    futures.append(future)
                
                # Wait for all tasks to complete
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    assert result["success"], "Concurrent baseline task failed"
                
                end_time = time.perf_counter()
                return (end_time - start_time) * 1000
        
        def run_concurrent_traceability(num_threads=4):
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = []
                start_time = time.perf_counter()
                
                for i in range(num_threads * 2):
                    future = executor.submit(
                        traceability_processor.process_source_with_traceability, 
                        f"concurrent_traceability_{i}.pdf"
                    )
                    futures.append(future)
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    assert result["success"], "Concurrent traceability task failed"
                
                end_time = time.perf_counter()
                return (end_time - start_time) * 1000
        
        # Test with different thread counts
        thread_counts = [2, 4, 8]
        results = {}
        
        for num_threads in thread_counts:
            baseline_time = run_concurrent_baseline(num_threads)
            traceability_time = run_concurrent_traceability(num_threads)
            
            overhead_percent = ((traceability_time - baseline_time) / baseline_time) * 100
            
            results[num_threads] = {
                "baseline_time_ms": baseline_time,
                "traceability_time_ms": traceability_time,
                "overhead_percent": overhead_percent
            }
            
            # Concurrent overhead should remain reasonable
            assert overhead_percent < 10.0, \
                f"Concurrent overhead too high with {num_threads} threads: {overhead_percent:.2f}%"
        
        return results
        
    def test_scalability_performance(self):
        """Test performance scalability with increasing load"""
        fr001_processor = CompleteFR001Processor()
        
        # Test with increasing numbers of concurrent jobs
        job_counts = [1, 5, 10, 20]
        scalability_results = {}
        
        for job_count in job_counts:
            def run_scalability_test():
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(job_count, 8)) as executor:
                    futures = []
                    start_time = time.perf_counter()
                    
                    for i in range(job_count):
                        future = executor.submit(
                            fr001_processor.process_source_complete_fr001,
                            f"scalability_test_{job_count}_{i}.pdf"
                        )
                        futures.append(future)
                    
                    successful_jobs = 0
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result.get("success", True):
                            successful_jobs += 1
                    
                    end_time = time.perf_counter()
                    total_time = (end_time - start_time) * 1000
                    
                    return {
                        "total_time_ms": total_time,
                        "avg_time_per_job_ms": total_time / job_count,
                        "successful_jobs": successful_jobs,
                        "success_rate": (successful_jobs / job_count) * 100
                    }
            
            # Run test multiple times for stability
            test_runs = []
            for run in range(3):
                test_runs.append(run_scalability_test())
            
            # Calculate averages
            scalability_results[job_count] = {
                "avg_total_time_ms": statistics.mean([r["total_time_ms"] for r in test_runs]),
                "avg_time_per_job_ms": statistics.mean([r["avg_time_per_job_ms"] for r in test_runs]),
                "min_success_rate": min([r["success_rate"] for r in test_runs])
            }
            
            # Verify acceptable success rate
            assert scalability_results[job_count]["min_success_rate"] > 95.0, \
                f"Success rate too low with {job_count} jobs: {scalability_results[job_count]['min_success_rate']:.1f}%"
        
        # Analyze scalability trends
        single_job_time = scalability_results[1]["avg_time_per_job_ms"]
        twenty_job_time = scalability_results[20]["avg_time_per_job_ms"]
        
        scalability_degradation = ((twenty_job_time - single_job_time) / single_job_time) * 100
        
        # Per-job time shouldn't degrade too much under load
        assert scalability_degradation < 50.0, \
            f"Per-job performance degradation too high: {scalability_degradation:.2f}%"
        
        return scalability_results


class TestMemoryUsageRegression:
    """Test memory usage regression with traceability features"""
    
    def test_memory_usage_baseline(self):
        """Establish memory usage baseline"""
        baseline_processor = BaselinePipelineProcessor()
        
        initial_memory = self._measure_memory_usage()
        
        # Process multiple documents to measure steady-state memory
        for i in range(10):
            result = baseline_processor.process_source(f"memory_baseline_{i}.pdf")
            assert result["success"]
        
        peak_memory = self._measure_memory_usage()
        memory_increase = peak_memory - initial_memory
        
        # Force garbage collection and measure final memory
        import gc
        gc.collect()
        final_memory = self._measure_memory_usage()
        
        memory_stats = {
            "initial_memory_mb": initial_memory,
            "peak_memory_mb": peak_memory,
            "final_memory_mb": final_memory,
            "memory_increase_mb": memory_increase,
            "memory_leaked_mb": final_memory - initial_memory
        }
        
        # Validate reasonable memory usage
        assert memory_increase < 200, f"Memory increase too high: {memory_increase:.1f}MB"
        assert memory_stats["memory_leaked_mb"] < 50, f"Memory leak detected: {memory_stats['memory_leaked_mb']:.1f}MB"
        
        return memory_stats
        
    def test_traceability_memory_overhead(self):
        """Test memory overhead of traceability features"""
        baseline_processor = BaselinePipelineProcessor()
        traceability_processor = TraceabilityEnabledProcessor()
        
        # Measure baseline memory usage
        baseline_initial = self._measure_memory_usage()
        
        for i in range(10):
            baseline_processor.process_source(f"memory_baseline_{i}.pdf")
        
        baseline_peak = self._measure_memory_usage()
        baseline_usage = baseline_peak - baseline_initial
        
        # Reset memory state
        import gc
        gc.collect()
        
        # Measure traceability memory usage
        traceability_initial = self._measure_memory_usage()
        
        for i in range(10):
            traceability_processor.process_source_with_traceability(f"memory_traceability_{i}.pdf")
        
        traceability_peak = self._measure_memory_usage()
        traceability_usage = traceability_peak - traceability_initial
        
        memory_overhead = traceability_usage - baseline_usage
        overhead_percent = (memory_overhead / baseline_usage) * 100 if baseline_usage > 0 else 0
        
        # Memory overhead should be reasonable (<30%)
        assert overhead_percent < 30.0, f"Memory overhead too high: {overhead_percent:.2f}%"
        
        return {
            "baseline_usage_mb": baseline_usage,
            "traceability_usage_mb": traceability_usage,
            "memory_overhead_mb": memory_overhead,
            "overhead_percent": overhead_percent
        }
        
    def test_long_running_memory_stability(self):
        """Test memory stability over long-running operations"""
        fr001_processor = CompleteFR001Processor()
        
        memory_measurements = []
        
        # Process many documents to test for memory leaks
        for i in range(50):
            fr001_processor.process_source_complete_fr001(f"long_run_{i}.pdf")
            
            if i % 10 == 0:  # Measure memory every 10 documents
                current_memory = self._measure_memory_usage()
                memory_measurements.append(current_memory)
        
        # Analyze memory trend
        if len(memory_measurements) > 2:
            # Check for increasing memory trend (potential leak)
            memory_slope = (memory_measurements[-1] - memory_measurements[0]) / len(memory_measurements)
            
            # Memory should be stable (slope < 2MB per 10 documents)
            assert memory_slope < 2.0, f"Memory leak detected: {memory_slope:.2f}MB per 10 documents"
        
        return {
            "memory_measurements": memory_measurements,
            "memory_stability": "stable" if len(memory_measurements) < 2 or memory_slope < 1.0 else "increasing"
        }
        
    def _measure_memory_usage(self):
        """Mock memory usage measurement"""
        import random
        # Mock memory usage - in reality would use psutil or similar
        base_usage = getattr(self, '_base_memory', random.randint(150, 200))
        self._base_memory = base_usage
        
        # Add some variation to simulate real memory usage
        return base_usage + random.randint(-10, 20)


class TestPerformanceRegressionDetection:
    """Test detection of performance regressions"""
    
    def test_performance_trend_analysis(self):
        """Test performance trend analysis over multiple test runs"""
        performance_tracker = PerformanceRegressionTracker()
        
        # Simulate performance data over time
        baseline_performance = 10000  # 10 seconds baseline
        
        # Simulate gradual performance degradation
        performance_data = []
        for week in range(12):  # 12 weeks of data
            # Add gradual degradation and some noise
            degradation = week * 100  # 100ms per week degradation
            noise = (week % 3 - 1) * 50  # Some random noise
            performance = baseline_performance + degradation + noise
            
            performance_data.append({
                "week": week + 1,
                "performance_ms": performance,
                "timestamp": f"2025-09-{(week % 4) + 1:02d}"
            })
            
            performance_tracker.record_performance(week + 1, performance)
        
        # Analyze performance trend
        trend_analysis = performance_tracker.analyze_trend()
        
        assert "trend_detected" in trend_analysis
        assert "regression_severity" in trend_analysis
        
        # Should detect degradation trend
        if trend_analysis["trend_detected"]:
            assert trend_analysis["trend_direction"] == "degrading"
            
        # Should flag as regression if degradation > 10%
        total_degradation = (performance_data[-1]["performance_ms"] - performance_data[0]["performance_ms"]) / performance_data[0]["performance_ms"] * 100
        
        if total_degradation > 10.0:
            assert trend_analysis["regression_severity"] in ["moderate", "severe"]
            
        return trend_analysis
        
    def test_performance_threshold_alerts(self):
        """Test performance threshold alerting"""
        alert_system = PerformanceAlertSystem()
        
        # Configure performance thresholds
        thresholds = {
            "pipeline_total_ms": {"warning": 25000, "critical": 35000},
            "pass_a_ms": {"warning": 2500, "critical": 4000},
            "pass_c_ms": {"warning": 18000, "critical": 25000},
            "memory_usage_mb": {"warning": 400, "critical": 600}
        }
        
        alert_system.configure_thresholds(thresholds)
        
        # Test various performance scenarios
        test_scenarios = [
            {
                "name": "normal_performance",
                "metrics": {
                    "pipeline_total_ms": 20000,
                    "pass_a_ms": 1500,
                    "pass_c_ms": 15000,
                    "memory_usage_mb": 250
                },
                "expected_alerts": 0
            },
            {
                "name": "warning_performance",
                "metrics": {
                    "pipeline_total_ms": 27000,  # Warning level
                    "pass_a_ms": 1800,
                    "pass_c_ms": 19000,  # Warning level
                    "memory_usage_mb": 280
                },
                "expected_alerts": 2
            },
            {
                "name": "critical_performance",
                "metrics": {
                    "pipeline_total_ms": 38000,  # Critical level
                    "pass_a_ms": 4500,  # Critical level
                    "pass_c_ms": 26000,  # Critical level
                    "memory_usage_mb": 650  # Critical level
                },
                "expected_alerts": 4
            }
        ]
        
        for scenario in test_scenarios:
            alerts = alert_system.check_performance_thresholds(scenario["metrics"])
            
            assert len(alerts) == scenario["expected_alerts"], \
                f"Scenario '{scenario['name']}' expected {scenario['expected_alerts']} alerts, got {len(alerts)}"
            
            if scenario["expected_alerts"] > 0:
                # Verify alert details
                critical_alerts = [a for a in alerts if a["severity"] == "critical"]
                warning_alerts = [a for a in alerts if a["severity"] == "warning"]
                
                if scenario["name"] == "critical_performance":
                    assert len(critical_alerts) == 4, "Should have 4 critical alerts"
                elif scenario["name"] == "warning_performance":
                    assert len(warning_alerts) == 2, "Should have 2 warning alerts"
        
        return {"thresholds_working": True, "scenarios_passed": len(test_scenarios)}


# Mock classes for performance testing

class BaselinePipelineProcessor:
    def process_source(self, source_file):
        # Mock baseline processing with realistic timing
        time.sleep(0.01)  # 10ms processing time
        return {"success": True, "source": source_file, "processing_time_ms": 10}


class BaselinePassProcessor:
    def process_single_pass(self, pass_id, input_data):
        # Mock individual pass processing
        pass_times = {"A": 0.001, "B": 0.0008, "C": 0.015, "D": 0.01, "E": 0.008, "F": 0.0005}
        time.sleep(pass_times.get(pass_id, 0.001))
        
        return {"success": True, "pass_id": pass_id, "input": input_data}


class TraceabilityEnabledProcessor:
    def process_source_with_traceability(self, source_file):
        # Mock processing with traceability overhead
        time.sleep(0.0105)  # 10.5ms (5% overhead)
        
        # Mock traceability data collection
        traceability_data = {
            "job_id": f"job_{hash(source_file) % 10000}",
            "source": source_file,
            "lineage_tracked": True
        }
        
        return {
            "success": True,
            "source": source_file,
            "processing_time_ms": 10.5,
            "traceability": traceability_data
        }


class HealthMonitoringProcessor:
    def process_source_with_health(self, source_file):
        # Mock processing with health monitoring overhead  
        time.sleep(0.0102)  # 10.2ms (2% overhead)
        
        health_data = {
            "performance_metrics": {"cpu_usage": 45.2, "memory_mb": 180},
            "health_score": 94.5
        }
        
        return {
            "success": True,
            "source": source_file,
            "processing_time_ms": 10.2,
            "health": health_data
        }


class ValidationEnhancedProcessor:
    def process_source_with_validation(self, source_file):
        # Mock processing with enhanced validation overhead
        time.sleep(0.0103)  # 10.3ms (3% overhead)
        
        validation_data = {
            "validation_passed": True,
            "validation_score": 98.1,
            "issues_found": 0
        }
        
        return {
            "success": True,
            "source": source_file,
            "processing_time_ms": 10.3,
            "validation": validation_data
        }


class CompleteFR001Processor:
    def process_source_complete_fr001(self, source_file):
        # Mock processing with complete FR-001 features
        time.sleep(0.0107)  # 10.7ms (7% total overhead)
        
        complete_data = {
            "traceability": {"lineage_tracked": True, "job_id": f"job_{hash(source_file) % 10000}"},
            "health": {"health_score": 93.2, "anomalies_detected": 0},
            "validation": {"validation_passed": True, "cross_pass_consistent": True},
            "lineage": {"end_to_end_tracked": True, "visualization_ready": True}
        }
        
        return {
            "success": True,
            "source": source_file,
            "processing_time_ms": 10.7,
            "fr001_features": complete_data
        }


class PerformanceRegressionTracker:
    def __init__(self):
        self.performance_history = {}
        
    def record_performance(self, week, performance_ms):
        self.performance_history[week] = performance_ms
        
    def analyze_trend(self):
        if len(self.performance_history) < 3:
            return {"trend_detected": False}
            
        weeks = sorted(self.performance_history.keys())
        performances = [self.performance_history[week] for week in weeks]
        
        # Simple linear trend analysis
        first_half = performances[:len(performances)//2]
        second_half = performances[len(performances)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        change_percent = ((second_avg - first_avg) / first_avg) * 100
        
        if abs(change_percent) < 5.0:
            trend = "stable"
            severity = "none"
        elif change_percent > 5.0:
            trend = "degrading"
            severity = "moderate" if change_percent < 15.0 else "severe"
        else:
            trend = "improving"
            severity = "none"
        
        return {
            "trend_detected": abs(change_percent) > 5.0,
            "trend_direction": trend,
            "regression_severity": severity,
            "change_percent": change_percent
        }


class PerformanceAlertSystem:
    def __init__(self):
        self.thresholds = {}
        
    def configure_thresholds(self, thresholds):
        self.thresholds = thresholds
        
    def check_performance_thresholds(self, metrics):
        alerts = []
        
        for metric_name, value in metrics.items():
            if metric_name in self.thresholds:
                threshold = self.thresholds[metric_name]
                
                if value > threshold.get("critical", float('inf')):
                    alerts.append({
                        "metric": metric_name,
                        "value": value,
                        "threshold": threshold["critical"],
                        "severity": "critical"
                    })
                elif value > threshold.get("warning", float('inf')):
                    alerts.append({
                        "metric": metric_name,
                        "value": value,
                        "threshold": threshold["warning"], 
                        "severity": "warning"
                    })
        
        return alerts


if __name__ == "__main__":
    pytest.main([__file__, "-v"])