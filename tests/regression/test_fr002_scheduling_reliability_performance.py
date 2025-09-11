#!/usr/bin/env python3
"""
Regression tests for FR-002 scheduling reliability and performance.

Tests long-term reliability, performance characteristics, and regression prevention:
- Scheduler reliability under sustained load and extended operation
- Performance regression testing for throughput and latency
- Memory and resource leak detection over time
- Stress testing with high job volumes and concurrent operations
- Long-running scheduler stability and state consistency  
- Performance benchmarking and trend analysis
- Resource consumption monitoring and optimization validation
- Failure recovery performance and reliability metrics
"""

import pytest
import asyncio
import tempfile
import shutil
import os
import json
import time
import threading
import psutil
import statistics
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import weakref

# Test framework imports
from tests.conftest import BaseTestCase, TestEnvironment, MockPipeline
from src_common.logging import get_logger

# Import scheduler components (to be implemented)
try:
    from src_common.scheduler_engine import SchedulingEngine, CronParser
    from src_common.job_manager import JobManager, JobQueue, Job, JobStatus
    from src_common.scheduled_processor import ScheduledBulkProcessor
    from src_common.performance_monitor import PerformanceMonitor, MetricsCollector
    from src_common.stress_tester import SchedulerStressTester
except ImportError:
    # Mock imports for testing before implementation
    SchedulingEngine = Mock
    CronParser = Mock
    JobManager = Mock
    JobQueue = Mock
    Job = Mock
    JobStatus = Mock
    ScheduledBulkProcessor = Mock
    PerformanceMonitor = Mock
    MetricsCollector = Mock
    SchedulerStressTester = Mock

logger = get_logger(__name__)


class TestSchedulingReliabilityAndPerformance(BaseTestCase):
    """Base class for scheduling reliability and performance tests."""
    
    @pytest.fixture(autouse=True)
    def setup_performance_testing_environment(self, temp_env_dir):
        """Set up performance testing environment with monitoring and metrics collection."""
        self.env_dir = temp_env_dir
        self.artifacts_dir = self.env_dir / "artifacts" / "ingest" / "dev"
        self.queue_state_dir = self.env_dir / "queue_state"
        self.metrics_dir = self.env_dir / "metrics"
        self.performance_logs_dir = self.env_dir / "performance_logs"
        
        # Create required directories
        for directory in [self.artifacts_dir, self.queue_state_dir, self.metrics_dir, self.performance_logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Performance testing configuration
        self.performance_config = {
            "environment": "dev",
            "upload_directories": [str(self.env_dir / "uploads")],
            "artifacts_base": str(self.artifacts_dir),
            "queue_state_dir": str(self.queue_state_dir),
            "metrics_dir": str(self.metrics_dir),
            "performance_monitoring": {
                "enabled": True,
                "collection_interval_seconds": 1,
                "memory_threshold_mb": 1024,
                "cpu_threshold_percent": 80,
                "disk_threshold_percent": 90
            },
            "stress_testing": {
                "max_concurrent_jobs": 20,
                "job_creation_rate_per_second": 5,
                "total_test_jobs": 1000,
                "sustained_load_duration_minutes": 10
            },
            "reliability_thresholds": {
                "max_acceptable_failure_rate": 0.01,  # 1% failure rate
                "max_response_time_ms": 1000,
                "max_memory_growth_mb_per_hour": 50,
                "min_uptime_hours": 24
            }
        }
        
        # Initialize performance monitoring
        self.performance_monitor = PerformanceMonitor(config=self.performance_config)
        self.metrics_collector = MetricsCollector(config=self.performance_config)
        
        # Track system resources at test start
        self.initial_system_metrics = self.capture_system_metrics()
        
        # Create mock pipeline with performance simulation
        self.mock_pipeline = self.create_performance_aware_mock_pipeline()
    
    def capture_system_metrics(self) -> Dict[str, Any]:
        """Capture current system metrics for baseline and comparison."""
        process = psutil.Process()
        
        return {
            "timestamp": datetime.now(),
            "memory": {
                "rss_mb": process.memory_info().rss / 1024 / 1024,
                "vms_mb": process.memory_info().vms / 1024 / 1024,
                "percent": process.memory_percent()
            },
            "cpu": {
                "percent": process.cpu_percent(interval=0.1),
                "times": process.cpu_times()
            },
            "threads": process.num_threads(),
            "fds": process.num_fds() if hasattr(process, 'num_fds') else 0,
            "system_memory_percent": psutil.virtual_memory().percent,
            "system_cpu_percent": psutil.cpu_percent(interval=0.1)
        }
    
    def create_performance_aware_mock_pipeline(self):
        """Create mock pipeline that simulates realistic performance characteristics."""
        mock_pipeline = Mock()
        
        # Simulate variable processing times based on document characteristics
        async def performance_aware_processing(*args, **kwargs):
            source_path = kwargs.get("source_path", "")
            
            # Simulate different processing times based on document type
            if "large" in source_path.lower():
                processing_time = 2.0 + (time.time() % 1.0)  # 2-3 seconds
                memory_usage_mb = 200 + int(time.time() % 100)  # 200-300 MB
            elif "complex" in source_path.lower():
                processing_time = 1.5 + (time.time() % 0.5)  # 1.5-2 seconds
                memory_usage_mb = 150 + int(time.time() % 50)   # 150-200 MB
            else:
                processing_time = 0.5 + (time.time() % 0.3)  # 0.5-0.8 seconds
                memory_usage_mb = 50 + int(time.time() % 30)   # 50-80 MB
            
            # Simulate processing delay
            await asyncio.sleep(processing_time)
            
            return {
                "job_id": kwargs.get("job_id", f"job_{int(time.time())}"),
                "status": "completed",
                "processing_time_seconds": processing_time,
                "memory_usage_mb": memory_usage_mb,
                "passes_completed": 6,
                "artifacts_created": 10 + int(time.time() % 10)
            }
        
        mock_pipeline.process_source = AsyncMock(side_effect=performance_aware_processing)
        return mock_pipeline
    
    def calculate_performance_regression(self, baseline_metrics: Dict, current_metrics: Dict) -> Dict[str, Any]:
        """Calculate performance regression between baseline and current metrics."""
        regression_analysis = {
            "timestamp": datetime.now(),
            "baseline_timestamp": baseline_metrics["timestamp"],
            "current_timestamp": current_metrics["timestamp"],
            "regressions": [],
            "improvements": [],
            "overall_regression_score": 0.0
        }
        
        # Memory regression analysis
        memory_change_mb = current_metrics["memory"]["rss_mb"] - baseline_metrics["memory"]["rss_mb"]
        memory_change_percent = (memory_change_mb / baseline_metrics["memory"]["rss_mb"]) * 100
        
        if memory_change_percent > 10:  # > 10% memory increase
            regression_analysis["regressions"].append({
                "metric": "memory_usage",
                "change_mb": memory_change_mb,
                "change_percent": memory_change_percent,
                "severity": "high" if memory_change_percent > 25 else "medium"
            })
        elif memory_change_percent < -5:  # > 5% memory decrease (improvement)
            regression_analysis["improvements"].append({
                "metric": "memory_usage",
                "change_mb": memory_change_mb,
                "change_percent": memory_change_percent
            })
        
        # Thread count regression analysis  
        thread_change = current_metrics["threads"] - baseline_metrics["threads"]
        if thread_change > 5:  # Significant thread increase
            regression_analysis["regressions"].append({
                "metric": "thread_count",
                "change": thread_change,
                "severity": "medium" if thread_change < 15 else "high"
            })
        
        # Calculate overall regression score (0-100, where 0 is no regression)
        regression_score = 0
        for regression in regression_analysis["regressions"]:
            if regression["severity"] == "high":
                regression_score += 30
            elif regression["severity"] == "medium":
                regression_score += 15
            else:
                regression_score += 5
        
        regression_analysis["overall_regression_score"] = min(regression_score, 100)
        
        return regression_analysis


class TestSchedulerReliabilityUnderLoad(TestSchedulingReliabilityAndPerformance):
    """Test scheduler reliability under sustained load conditions."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load_reliability_24_hours(self):
        """Test scheduler reliability under sustained load for 24 hours (compressed to 5 minutes for testing)."""
        scheduler = SchedulingEngine(config=self.performance_config)
        job_manager = JobManager(
            config=self.performance_config,
            pipeline=self.mock_pipeline
        )
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        # Simulate 24-hour load in compressed time (5 minutes = 300 seconds)
        test_duration_seconds = 300  # 5 minutes for testing
        jobs_per_hour_simulation = 100  # Simulate processing 100 jobs per hour
        total_jobs = int((jobs_per_hour_simulation * test_duration_seconds) / 3600 * 24)  # Scale for 24 hours
        
        reliability_metrics = {
            "start_time": datetime.now(),
            "total_jobs_created": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "scheduler_restarts": 0,
            "memory_samples": [],
            "response_time_samples": [],
            "error_events": []
        }
        
        # Create job generation task
        async def job_generator():
            job_count = 0
            while job_count < total_jobs:
                try:
                    job_id = job_manager.create_job(
                        name=f"reliability_test_job_{job_count:06d}",
                        job_type="bulk_ingestion",
                        source_path=f"/test/uploads/document_{job_count % 10}.pdf",
                        environment="dev",
                        priority=1
                    )
                    reliability_metrics["total_jobs_created"] += 1
                    job_count += 1
                    
                    # Control job creation rate
                    await asyncio.sleep(test_duration_seconds / total_jobs)
                    
                except Exception as e:
                    reliability_metrics["error_events"].append({
                        "timestamp": datetime.now(),
                        "type": "job_creation_error",
                        "error": str(e)
                    })
        
        # Create job processing task
        async def job_processor():
            while datetime.now() < reliability_metrics["start_time"] + timedelta(seconds=test_duration_seconds):
                try:
                    # Process pending jobs
                    pending_jobs = job_manager.get_pending_jobs(limit=5)
                    
                    if pending_jobs:
                        # Process jobs concurrently (up to 5 at a time)
                        tasks = []
                        for job in pending_jobs:
                            task = self.process_job_with_metrics(job, job_manager, reliability_metrics)
                            tasks.append(task)
                        
                        if tasks:
                            await asyncio.gather(*tasks, return_exceptions=True)
                    
                    await asyncio.sleep(1)  # Processing cycle delay
                    
                except Exception as e:
                    reliability_metrics["error_events"].append({
                        "timestamp": datetime.now(),
                        "type": "job_processing_error",
                        "error": str(e)
                    })
        
        # Create system monitoring task
        async def system_monitor():
            while datetime.now() < reliability_metrics["start_time"] + timedelta(seconds=test_duration_seconds):
                try:
                    current_metrics = self.capture_system_metrics()
                    reliability_metrics["memory_samples"].append(current_metrics["memory"]["rss_mb"])
                    
                    # Check for memory growth issues
                    if current_metrics["memory"]["rss_mb"] > 500:  # Alert if memory > 500MB
                        reliability_metrics["error_events"].append({
                            "timestamp": datetime.now(),
                            "type": "high_memory_usage",
                            "memory_mb": current_metrics["memory"]["rss_mb"]
                        })
                    
                    await asyncio.sleep(10)  # Monitor every 10 seconds
                    
                except Exception as e:
                    reliability_metrics["error_events"].append({
                        "timestamp": datetime.now(),
                        "type": "monitoring_error",
                        "error": str(e)
                    })
        
        # Run sustained load test
        await asyncio.gather(
            job_generator(),
            job_processor(),
            system_monitor()
        )
        
        # Stop performance monitoring
        self.performance_monitor.stop_monitoring()
        
        # Analyze reliability results
        reliability_metrics["end_time"] = datetime.now()
        reliability_metrics["total_duration_seconds"] = test_duration_seconds
        reliability_metrics["failure_rate"] = (
            reliability_metrics["jobs_failed"] / max(reliability_metrics["total_jobs_created"], 1)
        )
        
        # Assert reliability requirements
        assert reliability_metrics["failure_rate"] <= self.performance_config["reliability_thresholds"]["max_acceptable_failure_rate"], \
            f"Failure rate {reliability_metrics['failure_rate']:.4f} exceeds threshold"
        
        assert len(reliability_metrics["error_events"]) < 10, \
            f"Too many error events: {len(reliability_metrics['error_events'])}"
        
        # Memory growth analysis
        if reliability_metrics["memory_samples"]:
            memory_growth = max(reliability_metrics["memory_samples"]) - min(reliability_metrics["memory_samples"])
            max_memory_growth = self.performance_config["reliability_thresholds"]["max_memory_growth_mb_per_hour"]
            
            assert memory_growth <= max_memory_growth, \
                f"Memory growth {memory_growth:.2f}MB exceeds threshold {max_memory_growth}MB"
    
    async def process_job_with_metrics(self, job: Job, job_manager: JobManager, metrics: Dict):
        """Process a job while collecting performance metrics."""
        start_time = time.time()
        
        try:
            await job_manager.start_job(job.id)
            
            # Simulate processing
            result = await self.mock_pipeline.process_source(
                job_id=job.id,
                source_path=job.source_path
            )
            
            await job_manager.complete_job(job.id, result)
            metrics["jobs_completed"] += 1
            
            # Record response time
            response_time_ms = (time.time() - start_time) * 1000
            metrics["response_time_samples"].append(response_time_ms)
            
        except Exception as e:
            await job_manager.fail_job(job.id, str(e))
            metrics["jobs_failed"] += 1
            
            metrics["error_events"].append({
                "timestamp": datetime.now(),
                "type": "job_execution_error", 
                "job_id": job.id,
                "error": str(e)
            })
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_leak_detection_long_running(self):
        """Test for memory leaks during long-running scheduler operations."""
        scheduler = SchedulingEngine(config=self.performance_config)
        job_manager = JobManager(
            config=self.performance_config,
            pipeline=self.mock_pipeline
        )
        
        # Memory tracking setup
        memory_samples = []
        gc_collections = []
        object_counts = {}
        
        # Initial memory baseline
        initial_memory = self.capture_system_metrics()["memory"]["rss_mb"]
        memory_samples.append((datetime.now(), initial_memory))
        
        # Create and process jobs continuously for memory leak detection
        test_duration_seconds = 120  # 2 minutes for testing
        start_time = datetime.now()
        job_count = 0
        
        while datetime.now() < start_time + timedelta(seconds=test_duration_seconds):
            # Create batch of jobs
            batch_jobs = []
            for i in range(5):
                job_id = job_manager.create_job(
                    name=f"memory_leak_test_job_{job_count:06d}",
                    job_type="bulk_ingestion",
                    source_path=f"/test/uploads/document_{job_count % 10}.pdf",
                    environment="dev",
                    priority=1
                )
                batch_jobs.append(job_manager.get_job(job_id))
                job_count += 1
            
            # Process batch
            tasks = []
            for job in batch_jobs:
                task = self.process_job_for_memory_test(job, job_manager)
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
            # Sample memory usage
            current_memory = self.capture_system_metrics()["memory"]["rss_mb"]
            memory_samples.append((datetime.now(), current_memory))
            
            # Force garbage collection and track
            gc_before = len(gc.get_objects())
            gc.collect()
            gc_after = len(gc.get_objects())
            
            gc_collections.append({
                "timestamp": datetime.now(),
                "objects_before": gc_before,
                "objects_after": gc_after,
                "objects_collected": gc_before - gc_after
            })
            
            # Track specific object types that might leak
            object_counts[datetime.now()] = {
                "Job": len([obj for obj in gc.get_objects() if isinstance(obj, type) and obj.__name__ == "Job"]),
                "asyncio_tasks": len([obj for obj in gc.get_objects() if str(type(obj)).startswith("<class 'asyncio")]),
                "threads": threading.active_count()
            }
            
            await asyncio.sleep(2)  # Brief pause between batches
        
        # Analyze memory usage patterns
        memory_analysis = self.analyze_memory_usage_patterns(memory_samples, gc_collections, object_counts)
        
        # Assert no significant memory leaks
        assert memory_analysis["trend"] != "increasing", \
            f"Memory leak detected: {memory_analysis['trend_description']}"
        
        assert memory_analysis["max_memory_growth_mb"] <= 100, \
            f"Excessive memory growth: {memory_analysis['max_memory_growth_mb']:.2f}MB"
        
        # Verify garbage collection is effective
        effective_gc_collections = [gc for gc in gc_collections if gc["objects_collected"] > 0]
        assert len(effective_gc_collections) > 0, "Garbage collection appears ineffective"
    
    async def process_job_for_memory_test(self, job: Job, job_manager: JobManager):
        """Process job specifically for memory leak testing."""
        await job_manager.start_job(job.id)
        
        # Simulate processing with potential memory allocations
        large_data = [f"data_chunk_{i}" for i in range(1000)]  # Simulate processing data
        
        result = await self.mock_pipeline.process_source(
            job_id=job.id,
            source_path=job.source_path,
            processing_data=large_data
        )
        
        await job_manager.complete_job(job.id, result)
        
        # Explicitly del large_data to test if references are properly cleaned up
        del large_data
    
    def analyze_memory_usage_patterns(self, memory_samples: List[Tuple], gc_collections: List[Dict], 
                                     object_counts: Dict) -> Dict[str, Any]:
        """Analyze memory usage patterns to detect leaks and growth trends."""
        if len(memory_samples) < 2:
            return {"trend": "insufficient_data"}
        
        # Extract memory values and timestamps
        timestamps = [sample[0] for sample in memory_samples]
        memory_values = [sample[1] for sample in memory_samples]
        
        # Calculate memory growth trend
        initial_memory = memory_values[0]
        final_memory = memory_values[-1]
        max_memory = max(memory_values)
        min_memory = min(memory_values)
        
        memory_growth = final_memory - initial_memory
        max_memory_growth = max_memory - initial_memory
        
        # Simple trend analysis
        halfway_point = len(memory_values) // 2
        first_half_avg = statistics.mean(memory_values[:halfway_point])
        second_half_avg = statistics.mean(memory_values[halfway_point:])
        
        if second_half_avg > first_half_avg * 1.1:  # 10% increase
            trend = "increasing"
            trend_description = f"Memory increased from {first_half_avg:.2f}MB to {second_half_avg:.2f}MB"
        elif second_half_avg < first_half_avg * 0.9:  # 10% decrease
            trend = "decreasing"
            trend_description = f"Memory decreased from {first_half_avg:.2f}MB to {second_half_avg:.2f}MB"
        else:
            trend = "stable"
            trend_description = f"Memory remained stable around {statistics.mean(memory_values):.2f}MB"
        
        return {
            "trend": trend,
            "trend_description": trend_description,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "max_memory_mb": max_memory,
            "min_memory_mb": min_memory,
            "memory_growth_mb": memory_growth,
            "max_memory_growth_mb": max_memory_growth,
            "gc_collections_count": len(gc_collections),
            "total_objects_collected": sum(gc["objects_collected"] for gc in gc_collections),
            "memory_samples_count": len(memory_samples),
            "test_duration_minutes": (timestamps[-1] - timestamps[0]).total_seconds() / 60
        }


class TestPerformanceRegression(TestSchedulingReliabilityAndPerformance):
    """Test performance regression detection and benchmarking."""
    
    @pytest.mark.asyncio
    async def test_throughput_performance_regression(self):
        """Test job processing throughput and detect performance regressions."""
        scheduler = SchedulingEngine(config=self.performance_config)
        processor = ScheduledBulkProcessor(
            config=self.performance_config,
            pipeline=self.mock_pipeline
        )
        
        # Baseline performance test
        baseline_results = await self.run_throughput_benchmark(
            processor, 
            job_count=50,
            test_name="baseline"
        )
        
        # Simulate potential performance regression (slower processing)
        original_process_source = self.mock_pipeline.process_source
        
        async def slower_processing(*args, **kwargs):
            result = await original_process_source(*args, **kwargs)
            # Add artificial delay to simulate regression
            await asyncio.sleep(0.1)  # 100ms additional delay
            return result
        
        # Current performance test with potential regression
        self.mock_pipeline.process_source = AsyncMock(side_effect=slower_processing)
        
        current_results = await self.run_throughput_benchmark(
            processor,
            job_count=50, 
            test_name="current_with_regression"
        )
        
        # Restore original pipeline
        self.mock_pipeline.process_source = original_process_source
        
        # Analyze performance regression
        regression_analysis = self.analyze_throughput_regression(baseline_results, current_results)
        
        # Assert performance regression thresholds
        throughput_regression_percent = regression_analysis["throughput_change_percent"]
        response_time_regression_percent = regression_analysis["response_time_change_percent"]
        
        # Allow up to 20% throughput regression (configurable threshold)
        assert throughput_regression_percent <= 20, \
            f"Throughput regression {throughput_regression_percent:.2f}% exceeds 20% threshold"
        
        # Allow up to 30% response time increase (configurable threshold)
        assert response_time_regression_percent <= 30, \
            f"Response time regression {response_time_regression_percent:.2f}% exceeds 30% threshold"
        
        # Log performance comparison for analysis
        logger.info(f"Performance comparison: {json.dumps(regression_analysis, indent=2, default=str)}")
    
    async def run_throughput_benchmark(self, processor: ScheduledBulkProcessor, job_count: int, 
                                     test_name: str) -> Dict[str, Any]:
        """Run throughput benchmark test."""
        start_time = datetime.now()
        
        # Create test jobs
        test_jobs = []
        for i in range(job_count):
            job = Job(
                id=f"{test_name}_job_{i:03d}",
                name=f"{test_name}_throughput_test_{i}",
                job_type="bulk_ingestion",
                source_path=f"/test/uploads/benchmark_document_{i % 10}.pdf",
                environment="dev",
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            test_jobs.append(job)
        
        # Process jobs and collect metrics
        response_times = []
        successful_jobs = 0
        failed_jobs = 0
        
        # Process jobs with concurrency limit
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent jobs
        
        async def process_single_job(job):
            nonlocal successful_jobs, failed_jobs
            async with semaphore:
                job_start_time = time.time()
                try:
                    result = await processor.execute_job(job)
                    job_end_time = time.time()
                    
                    response_time_ms = (job_end_time - job_start_time) * 1000
                    response_times.append(response_time_ms)
                    
                    if result["status"] == "completed":
                        successful_jobs += 1
                    else:
                        failed_jobs += 1
                        
                except Exception as e:
                    failed_jobs += 1
                    logger.error(f"Job {job.id} failed: {e}")
        
        # Execute all jobs
        tasks = [process_single_job(job) for job in test_jobs]
        await asyncio.gather(*tasks)
        
        end_time = datetime.now()
        total_duration_seconds = (end_time - start_time).total_seconds()
        
        # Calculate throughput metrics
        results = {
            "test_name": test_name,
            "start_time": start_time,
            "end_time": end_time,
            "total_duration_seconds": total_duration_seconds,
            "total_jobs": job_count,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": successful_jobs / job_count if job_count > 0 else 0,
            "throughput_jobs_per_second": successful_jobs / total_duration_seconds if total_duration_seconds > 0 else 0,
            "response_times": {
                "min_ms": min(response_times) if response_times else 0,
                "max_ms": max(response_times) if response_times else 0,
                "mean_ms": statistics.mean(response_times) if response_times else 0,
                "median_ms": statistics.median(response_times) if response_times else 0,
                "p95_ms": self.calculate_percentile(response_times, 95) if response_times else 0,
                "p99_ms": self.calculate_percentile(response_times, 99) if response_times else 0,
            }
        }
        
        return results
    
    def analyze_throughput_regression(self, baseline: Dict, current: Dict) -> Dict[str, Any]:
        """Analyze throughput regression between baseline and current performance."""
        baseline_throughput = baseline["throughput_jobs_per_second"]
        current_throughput = current["throughput_jobs_per_second"]
        
        baseline_response_time = baseline["response_times"]["mean_ms"]
        current_response_time = current["response_times"]["mean_ms"]
        
        # Calculate percentage changes
        throughput_change_percent = 0
        if baseline_throughput > 0:
            throughput_change_percent = ((baseline_throughput - current_throughput) / baseline_throughput) * 100
        
        response_time_change_percent = 0
        if baseline_response_time > 0:
            response_time_change_percent = ((current_response_time - baseline_response_time) / baseline_response_time) * 100
        
        return {
            "baseline_throughput_jobs_per_second": baseline_throughput,
            "current_throughput_jobs_per_second": current_throughput,
            "throughput_change_percent": throughput_change_percent,
            "baseline_mean_response_time_ms": baseline_response_time,
            "current_mean_response_time_ms": current_response_time,
            "response_time_change_percent": response_time_change_percent,
            "baseline_p95_response_time_ms": baseline["response_times"]["p95_ms"],
            "current_p95_response_time_ms": current["response_times"]["p95_ms"],
            "baseline_success_rate": baseline["success_rate"],
            "current_success_rate": current["success_rate"],
            "performance_regression_detected": (
                throughput_change_percent > 10 or response_time_change_percent > 15
            )
        }
    
    def calculate_percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile value from data list."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        
        if index >= len(sorted_data):
            index = len(sorted_data) - 1
        
        return sorted_data[index]
    
    @pytest.mark.asyncio
    async def test_concurrent_load_performance_scaling(self):
        """Test performance scaling under different concurrent load levels."""
        processor = ScheduledBulkProcessor(
            config=self.performance_config,
            pipeline=self.mock_pipeline
        )
        
        # Test different concurrency levels
        concurrency_levels = [1, 2, 5, 10, 20]
        scaling_results = {}
        
        for concurrency in concurrency_levels:
            logger.info(f"Testing concurrency level: {concurrency}")
            
            # Configure processor for specific concurrency
            processor_config = self.performance_config.copy()
            processor_config["max_concurrent_jobs"] = concurrency
            
            # Run performance test
            result = await self.run_concurrent_load_test(processor, concurrency, job_count=50)
            scaling_results[concurrency] = result
            
            # Brief pause between tests
            await asyncio.sleep(1)
        
        # Analyze scaling characteristics
        scaling_analysis = self.analyze_performance_scaling(scaling_results)
        
        # Assert scaling expectations
        # Throughput should generally increase with concurrency (up to a point)
        throughput_improvements = 0
        previous_throughput = 0
        
        for concurrency in concurrency_levels:
            current_throughput = scaling_results[concurrency]["throughput_jobs_per_second"]
            if current_throughput > previous_throughput:
                throughput_improvements += 1
            previous_throughput = current_throughput
        
        # Should see throughput improvements in at least 60% of concurrency increases
        improvement_rate = throughput_improvements / (len(concurrency_levels) - 1)
        assert improvement_rate >= 0.6, \
            f"Poor scaling: only {improvement_rate:.1%} of concurrency increases improved throughput"
        
        # Resource efficiency should be reasonable
        max_memory_per_job = scaling_analysis["max_memory_per_job_mb"]
        assert max_memory_per_job <= 50, \
            f"Memory usage per job too high: {max_memory_per_job:.2f}MB"
        
        logger.info(f"Scaling analysis: {json.dumps(scaling_analysis, indent=2, default=str)}")
    
    async def run_concurrent_load_test(self, processor: ScheduledBulkProcessor, concurrency: int, 
                                     job_count: int) -> Dict[str, Any]:
        """Run concurrent load test with specified concurrency level."""
        start_time = datetime.now()
        initial_memory = self.capture_system_metrics()["memory"]["rss_mb"]
        
        # Create test jobs
        test_jobs = []
        for i in range(job_count):
            job = Job(
                id=f"concurrent_{concurrency}_job_{i:03d}",
                name=f"concurrent_load_test_c{concurrency}_{i}",
                job_type="bulk_ingestion",
                source_path=f"/test/uploads/concurrent_document_{i % 10}.pdf",
                environment="dev",
                priority=1,
                created_at=datetime.now(),
                status=JobStatus.PENDING
            )
            test_jobs.append(job)
        
        # Process jobs with specified concurrency
        semaphore = asyncio.Semaphore(concurrency)
        completed_jobs = 0
        failed_jobs = 0
        response_times = []
        
        async def process_concurrent_job(job):
            nonlocal completed_jobs, failed_jobs
            async with semaphore:
                job_start_time = time.time()
                try:
                    result = await processor.execute_job(job)
                    job_end_time = time.time()
                    
                    response_time_ms = (job_end_time - job_start_time) * 1000
                    response_times.append(response_time_ms)
                    
                    if result["status"] == "completed":
                        completed_jobs += 1
                    else:
                        failed_jobs += 1
                        
                except Exception as e:
                    failed_jobs += 1
                    logger.error(f"Concurrent job {job.id} failed: {e}")
        
        # Execute all jobs
        tasks = [process_concurrent_job(job) for job in test_jobs]
        await asyncio.gather(*tasks)
        
        end_time = datetime.now()
        final_memory = self.capture_system_metrics()["memory"]["rss_mb"]
        
        total_duration_seconds = (end_time - start_time).total_seconds()
        
        return {
            "concurrency_level": concurrency,
            "total_jobs": job_count,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": completed_jobs / job_count if job_count > 0 else 0,
            "total_duration_seconds": total_duration_seconds,
            "throughput_jobs_per_second": completed_jobs / total_duration_seconds if total_duration_seconds > 0 else 0,
            "mean_response_time_ms": statistics.mean(response_times) if response_times else 0,
            "p95_response_time_ms": self.calculate_percentile(response_times, 95) if response_times else 0,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_usage_mb": final_memory - initial_memory
        }
    
    def analyze_performance_scaling(self, scaling_results: Dict[int, Dict]) -> Dict[str, Any]:
        """Analyze performance scaling characteristics across concurrency levels."""
        concurrency_levels = sorted(scaling_results.keys())
        
        throughput_values = [scaling_results[c]["throughput_jobs_per_second"] for c in concurrency_levels]
        response_time_values = [scaling_results[c]["mean_response_time_ms"] for c in concurrency_levels]
        memory_values = [scaling_results[c]["memory_usage_mb"] for c in concurrency_levels]
        
        # Calculate scaling efficiency
        max_throughput = max(throughput_values)
        optimal_concurrency = concurrency_levels[throughput_values.index(max_throughput)]
        
        # Memory efficiency analysis
        memory_per_job_values = []
        for c in concurrency_levels:
            if scaling_results[c]["completed_jobs"] > 0:
                memory_per_job = scaling_results[c]["memory_usage_mb"] / scaling_results[c]["completed_jobs"]
                memory_per_job_values.append(memory_per_job)
            else:
                memory_per_job_values.append(0)
        
        return {
            "concurrency_levels_tested": concurrency_levels,
            "max_throughput_jobs_per_second": max_throughput,
            "optimal_concurrency_level": optimal_concurrency,
            "throughput_scaling_efficiency": max_throughput / concurrency_levels[-1],  # Throughput per concurrency unit
            "min_response_time_ms": min(response_time_values),
            "max_response_time_ms": max(response_time_values),
            "max_memory_usage_mb": max(memory_values),
            "max_memory_per_job_mb": max(memory_per_job_values) if memory_per_job_values else 0,
            "scaling_degradation_point": self.find_scaling_degradation_point(scaling_results)
        }
    
    def find_scaling_degradation_point(self, scaling_results: Dict[int, Dict]) -> Optional[int]:
        """Find the concurrency level where performance scaling starts to degrade."""
        concurrency_levels = sorted(scaling_results.keys())
        
        if len(concurrency_levels) < 3:
            return None
        
        throughput_values = [scaling_results[c]["throughput_jobs_per_second"] for c in concurrency_levels]
        
        # Find the point where throughput stops increasing or starts decreasing
        for i in range(1, len(throughput_values) - 1):
            current = throughput_values[i]
            next_val = throughput_values[i + 1]
            
            # If next throughput is more than 10% lower, we've found degradation point
            if next_val < current * 0.9:
                return concurrency_levels[i]
        
        return None


class TestStressTesting(TestSchedulingReliabilityAndPerformance):
    """Test scheduler under extreme stress conditions."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_extreme_job_volume_stress(self):
        """Test scheduler behavior under extreme job volumes."""
        stress_config = self.performance_config.copy()
        stress_config["stress_testing"]["total_test_jobs"] = 500  # Reduced for testing
        
        stress_tester = SchedulerStressTester(config=stress_config)
        scheduler = SchedulingEngine(config=stress_config)
        job_manager = JobManager(
            config=stress_config,
            pipeline=self.mock_pipeline
        )
        
        # Configure stress test parameters
        stress_test_params = {
            "total_jobs": 500,
            "max_concurrent_jobs": 25,
            "job_creation_rate_per_second": 10,
            "test_duration_minutes": 3,  # Reduced for testing
            "memory_limit_mb": 1024,
            "expected_failure_rate_threshold": 0.05  # 5%
        }
        
        # Start stress test
        stress_results = await stress_tester.run_extreme_volume_test(
            scheduler=scheduler,
            job_manager=job_manager,
            **stress_test_params
        )
        
        # Analyze stress test results
        assert stress_results["total_jobs_created"] >= stress_test_params["total_jobs"] * 0.8, \
            f"Failed to create sufficient jobs: {stress_results['total_jobs_created']}"
        
        assert stress_results["failure_rate"] <= stress_test_params["expected_failure_rate_threshold"], \
            f"Failure rate {stress_results['failure_rate']:.3f} exceeds threshold {stress_test_params['expected_failure_rate_threshold']}"
        
        assert stress_results["peak_memory_mb"] <= stress_test_params["memory_limit_mb"], \
            f"Memory usage {stress_results['peak_memory_mb']:.2f}MB exceeds limit {stress_test_params['memory_limit_mb']}MB"
        
        # System should remain responsive
        assert stress_results["system_responsive"] is True, "System became unresponsive during stress test"
        
        # Resource cleanup verification
        final_memory = self.capture_system_metrics()["memory"]["rss_mb"]
        initial_memory = self.initial_system_metrics["memory"]["rss_mb"]
        memory_retention = final_memory - initial_memory
        
        assert memory_retention <= 200, \
            f"Excessive memory retention after stress test: {memory_retention:.2f}MB"
        
        logger.info(f"Stress test results: {json.dumps(stress_results, indent=2, default=str)}")
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_recovery(self):
        """Test scheduler recovery from resource exhaustion scenarios."""
        scheduler = SchedulingEngine(config=self.performance_config)
        job_manager = JobManager(
            config=self.performance_config,
            pipeline=self.mock_pipeline
        )
        
        # Simulate resource exhaustion scenarios
        exhaustion_scenarios = [
            {
                "name": "memory_exhaustion",
                "resource_type": "memory",
                "exhaust_method": self.simulate_memory_exhaustion,
                "recovery_time_seconds": 10
            },
            {
                "name": "high_cpu_load",
                "resource_type": "cpu",
                "exhaust_method": self.simulate_high_cpu_load,
                "recovery_time_seconds": 5
            },
            {
                "name": "disk_space_shortage", 
                "resource_type": "disk",
                "exhaust_method": self.simulate_disk_shortage,
                "recovery_time_seconds": 5
            }
        ]
        
        recovery_results = {}
        
        for scenario in exhaustion_scenarios:
            logger.info(f"Testing resource exhaustion scenario: {scenario['name']}")
            
            # Create baseline jobs before exhaustion
            baseline_jobs = []
            for i in range(5):
                job_id = job_manager.create_job(
                    name=f"pre_exhaustion_job_{i}",
                    job_type="bulk_ingestion",
                    source_path=f"/test/uploads/baseline_{i}.pdf",
                    environment="dev",
                    priority=1
                )
                baseline_jobs.append(job_id)
            
            # Process baseline jobs successfully
            baseline_success_count = 0
            for job_id in baseline_jobs:
                try:
                    job = job_manager.get_job(job_id)
                    await job_manager.start_job(job_id)
                    result = await self.mock_pipeline.process_source(job_id=job_id, source_path=job.source_path)
                    await job_manager.complete_job(job_id, result)
                    baseline_success_count += 1
                except Exception as e:
                    logger.warning(f"Baseline job {job_id} failed: {e}")
            
            # Simulate resource exhaustion
            exhaustion_task = asyncio.create_task(
                scenario["exhaust_method"](duration_seconds=scenario["recovery_time_seconds"])
            )
            
            # Create jobs during resource exhaustion
            exhaustion_jobs = []
            for i in range(5):
                try:
                    job_id = job_manager.create_job(
                        name=f"during_exhaustion_job_{i}",
                        job_type="bulk_ingestion", 
                        source_path=f"/test/uploads/exhaustion_{i}.pdf",
                        environment="dev",
                        priority=1
                    )
                    exhaustion_jobs.append(job_id)
                except Exception as e:
                    logger.info(f"Expected job creation failure during exhaustion: {e}")
            
            # Wait for exhaustion to end
            await exhaustion_task
            
            # Test recovery by creating and processing jobs
            recovery_jobs = []
            for i in range(5):
                job_id = job_manager.create_job(
                    name=f"recovery_job_{i}",
                    job_type="bulk_ingestion",
                    source_path=f"/test/uploads/recovery_{i}.pdf", 
                    environment="dev",
                    priority=1
                )
                recovery_jobs.append(job_id)
            
            # Process recovery jobs
            recovery_success_count = 0
            for job_id in recovery_jobs:
                try:
                    job = job_manager.get_job(job_id)
                    await job_manager.start_job(job_id)
                    result = await self.mock_pipeline.process_source(job_id=job_id, source_path=job.source_path)
                    await job_manager.complete_job(job_id, result)
                    recovery_success_count += 1
                except Exception as e:
                    logger.warning(f"Recovery job {job_id} failed: {e}")
            
            # Analyze recovery effectiveness
            recovery_rate = recovery_success_count / len(recovery_jobs) if recovery_jobs else 0
            
            recovery_results[scenario["name"]] = {
                "baseline_success_count": baseline_success_count,
                "baseline_success_rate": baseline_success_count / len(baseline_jobs),
                "exhaustion_jobs_created": len(exhaustion_jobs),
                "recovery_jobs_created": len(recovery_jobs), 
                "recovery_success_count": recovery_success_count,
                "recovery_rate": recovery_rate,
                "scenario": scenario
            }
            
            # Assert recovery is effective
            assert recovery_rate >= 0.8, \
                f"Poor recovery from {scenario['name']}: {recovery_rate:.1%} success rate"
        
        # Overall recovery assessment
        overall_recovery_rates = [result["recovery_rate"] for result in recovery_results.values()]
        average_recovery_rate = statistics.mean(overall_recovery_rates)
        
        assert average_recovery_rate >= 0.8, \
            f"Overall recovery rate too low: {average_recovery_rate:.1%}"
        
        logger.info(f"Resource exhaustion recovery results: {json.dumps(recovery_results, indent=2, default=str)}")
    
    async def simulate_memory_exhaustion(self, duration_seconds: int):
        """Simulate memory exhaustion condition."""
        # Allocate large amounts of memory temporarily
        memory_hog = []
        try:
            # Allocate memory in chunks
            for _ in range(duration_seconds):
                chunk = [0] * (10 * 1024 * 1024)  # 10MB chunk of integers
                memory_hog.append(chunk)
                await asyncio.sleep(1)
        finally:
            # Clean up allocated memory
            del memory_hog
            gc.collect()
    
    async def simulate_high_cpu_load(self, duration_seconds: int):
        """Simulate high CPU load condition."""
        def cpu_intensive_work():
            end_time = time.time() + 1  # 1 second of CPU work
            while time.time() < end_time:
                # Perform CPU-intensive calculation
                sum(i * i for i in range(10000))
        
        # Run CPU-intensive work for specified duration
        for _ in range(duration_seconds):
            await asyncio.get_event_loop().run_in_executor(None, cpu_intensive_work)
    
    async def simulate_disk_shortage(self, duration_seconds: int):
        """Simulate disk space shortage condition."""
        # Create temporary large files to simulate disk shortage
        temp_files = []
        try:
            for i in range(duration_seconds):
                temp_file = self.env_dir / f"disk_hog_{i}.tmp"
                with open(temp_file, 'wb') as f:
                    f.write(b'0' * (50 * 1024 * 1024))  # 50MB file
                temp_files.append(temp_file)
                await asyncio.sleep(1)
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    temp_file.unlink()
                except FileNotFoundError:
                    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not slow"])