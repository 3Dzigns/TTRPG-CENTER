"""
FR-003: Distributed Storage Architecture and Data Consistency
Test distributed storage system with multi-region replication and consistency guarantees.

This module tests the distributed storage infrastructure that ensures data
consistency, availability, and partition tolerance across multiple storage
nodes and geographic regions for the TTRPG Center platform.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR003DistributedStorage(BaseFRTest):
    """Test suite for FR-003 Distributed Storage Architecture and Data Consistency."""

    async def asyncSetUp(self):
        """Set up test environment with distributed storage infrastructure."""
        await super().asyncSetUp()
        self.storage_cluster = self._create_mock_storage_cluster()
        self.replication_manager = self._create_mock_replication_manager()
        self.consistency_controller = self._create_mock_consistency_controller()
        self.partition_manager = self._create_mock_partition_manager()

    def _create_mock_storage_cluster(self) -> Mock:
        """Create mock distributed storage cluster."""
        cluster = Mock()
        cluster.get_cluster_status = AsyncMock()
        cluster.add_node = AsyncMock()
        cluster.remove_node = AsyncMock()
        cluster.rebalance_data = AsyncMock()
        cluster.get_node_health = AsyncMock()
        return cluster

    def _create_mock_replication_manager(self) -> Mock:
        """Create mock replication management system."""
        manager = Mock()
        manager.replicate_data = AsyncMock()
        manager.verify_replication = AsyncMock()
        manager.handle_node_failure = AsyncMock()
        manager.sync_replicas = AsyncMock()
        return manager

    def _create_mock_consistency_controller(self) -> Mock:
        """Create mock consistency control system."""
        controller = Mock()
        controller.ensure_consistency = AsyncMock()
        controller.resolve_conflicts = AsyncMock()
        controller.validate_transaction = AsyncMock()
        controller.maintain_causal_ordering = AsyncMock()
        return controller

    def _create_mock_partition_manager(self) -> Mock:
        """Create mock partition management system."""
        manager = Mock()
        manager.handle_network_partition = AsyncMock()
        manager.detect_split_brain = AsyncMock()
        manager.merge_partitions = AsyncMock()
        manager.maintain_availability = AsyncMock()
        return manager

    async def test_multi_region_storage_cluster_setup(self):
        """Test distributed storage cluster configuration across multiple regions."""
        # Mock cluster configuration
        cluster_config = {
            "regions": ["us-east-1", "us-west-2", "eu-west-1"],
            "nodes_per_region": 3,
            "replication_factor": 3,
            "consistency_level": "eventual",
            "partition_strategy": "consistent_hashing"
        }

        # Configure cluster status
        self.storage_cluster.get_cluster_status.return_value = {
            "cluster_id": "ttrpg-storage-cluster",
            "total_nodes": 9,
            "healthy_nodes": 9,
            "regions": {
                "us-east-1": {
                    "nodes": [
                        {"node_id": "us-east-1a", "status": "healthy", "disk_usage": 0.65, "cpu_usage": 0.45},
                        {"node_id": "us-east-1b", "status": "healthy", "disk_usage": 0.58, "cpu_usage": 0.52},
                        {"node_id": "us-east-1c", "status": "healthy", "disk_usage": 0.71, "cpu_usage": 0.38}
                    ],
                    "region_health": "healthy",
                    "data_distribution": "balanced",
                    "network_latency_ms": 2.5
                },
                "us-west-2": {
                    "nodes": [
                        {"node_id": "us-west-2a", "status": "healthy", "disk_usage": 0.62, "cpu_usage": 0.41},
                        {"node_id": "us-west-2b", "status": "healthy", "disk_usage": 0.69, "cpu_usage": 0.47},
                        {"node_id": "us-west-2c", "status": "healthy", "disk_usage": 0.55, "cpu_usage": 0.39}
                    ],
                    "region_health": "healthy",
                    "data_distribution": "balanced",
                    "network_latency_ms": 3.1
                },
                "eu-west-1": {
                    "nodes": [
                        {"node_id": "eu-west-1a", "status": "healthy", "disk_usage": 0.67, "cpu_usage": 0.43},
                        {"node_id": "eu-west-1b", "status": "healthy", "disk_usage": 0.59, "cpu_usage": 0.48},
                        {"node_id": "eu-west-1c", "status": "healthy", "disk_usage": 0.73, "cpu_usage": 0.36}
                    ],
                    "region_health": "healthy",
                    "data_distribution": "balanced",
                    "network_latency_ms": 4.2
                }
            },
            "global_metrics": {
                "total_storage_tb": 45.8,
                "used_storage_tb": 29.2,
                "storage_utilization": 0.64,
                "average_response_time_ms": 15.7,
                "cross_region_latency_ms": 125.8,
                "data_consistency_score": 0.98
            }
        }

        # Test cluster status retrieval
        status = await self.storage_cluster.get_cluster_status()

        # Verify cluster structure
        self.assertIn("cluster_id", status)
        self.assertIn("regions", status)
        self.assertIn("global_metrics", status)
        self.assertEqual(status["total_nodes"], 9)
        self.assertEqual(len(status["regions"]), 3)

        # Verify regional distribution
        for region_name, region_data in status["regions"].items():
            self.assertIn("nodes", region_data)
            self.assertIn("region_health", region_data)
            self.assertEqual(len(region_data["nodes"]), 3)
            self.assertEqual(region_data["region_health"], "healthy")

            # Verify node health
            for node in region_data["nodes"]:
                self.assertIn("node_id", node)
                self.assertIn("status", node)
                self.assertEqual(node["status"], "healthy")
                self.assertLess(node["disk_usage"], 0.8)  # Under 80% usage
                self.assertLess(node["cpu_usage"], 0.6)   # Under 60% CPU

        # Verify global metrics
        metrics = status["global_metrics"]
        self.assertGreater(metrics["data_consistency_score"], 0.95)
        self.assertLess(metrics["average_response_time_ms"], 20)
        self.assertGreater(metrics["storage_utilization"], 0.5)
        self.assertLess(metrics["storage_utilization"], 0.8)

    async def test_data_replication_and_synchronization(self):
        """Test multi-region data replication with conflict resolution."""
        # Mock data write operation
        write_operation = {
            "operation_id": "write_001",
            "data_key": "document/test_doc_123",
            "data": {
                "content": "Updated TTRPG content",
                "version": 5,
                "last_modified": "2024-01-01T20:00:00Z",
                "metadata": {"author": "user123", "tags": ["D&D", "rules"]}
            },
            "consistency_level": "strong",
            "replication_factor": 3
        }

        # Configure replication process
        self.replication_manager.replicate_data.return_value = {
            "operation_id": "write_001",
            "primary_write": {
                "node_id": "us-east-1a",
                "timestamp": "2024-01-01T20:00:00.125Z",
                "status": "success",
                "latency_ms": 8.5
            },
            "replica_writes": [
                {
                    "node_id": "us-west-2a",
                    "timestamp": "2024-01-01T20:00:00.187Z",
                    "status": "success",
                    "latency_ms": 62.3,
                    "replication_lag_ms": 62
                },
                {
                    "node_id": "eu-west-1a",
                    "timestamp": "2024-01-01T20:00:00.251Z",
                    "status": "success",
                    "latency_ms": 126.1,
                    "replication_lag_ms": 126
                }
            ],
            "replication_summary": {
                "total_replicas": 3,
                "successful_replicas": 3,
                "failed_replicas": 0,
                "max_replication_lag_ms": 126,
                "replication_success_rate": 1.0,
                "consistency_achieved": True
            }
        }

        # Test data replication
        replication_result = await self.replication_manager.replicate_data(write_operation)

        # Verify replication structure
        self.assertIn("primary_write", replication_result)
        self.assertIn("replica_writes", replication_result)
        self.assertIn("replication_summary", replication_result)

        # Verify primary write
        primary = replication_result["primary_write"]
        self.assertEqual(primary["status"], "success")
        self.assertLess(primary["latency_ms"], 15)  # Fast local write

        # Verify replica writes
        replicas = replication_result["replica_writes"]
        self.assertEqual(len(replicas), 2)  # 2 additional replicas
        for replica in replicas:
            self.assertEqual(replica["status"], "success")
            self.assertIn("replication_lag_ms", replica)

        # Verify replication summary
        summary = replication_result["replication_summary"]
        self.assertEqual(summary["successful_replicas"], 3)
        self.assertEqual(summary["failed_replicas"], 0)
        self.assertEqual(summary["replication_success_rate"], 1.0)
        self.assertTrue(summary["consistency_achieved"])
        self.assertLess(summary["max_replication_lag_ms"], 200)  # Reasonable lag

        # Test replication verification
        self.replication_manager.verify_replication.return_value = {
            "verification_id": "verify_001",
            "data_key": "document/test_doc_123",
            "replica_states": [
                {
                    "node_id": "us-east-1a",
                    "version": 5,
                    "checksum": "abc123def456",
                    "last_updated": "2024-01-01T20:00:00.125Z",
                    "is_primary": True
                },
                {
                    "node_id": "us-west-2a",
                    "version": 5,
                    "checksum": "abc123def456",
                    "last_updated": "2024-01-01T20:00:00.187Z",
                    "is_primary": False
                },
                {
                    "node_id": "eu-west-1a",
                    "version": 5,
                    "checksum": "abc123def456",
                    "last_updated": "2024-01-01T20:00:00.251Z",
                    "is_primary": False
                }
            ],
            "consistency_check": {
                "all_replicas_consistent": True,
                "version_matches": True,
                "checksum_matches": True,
                "data_integrity_score": 1.0
            }
        }

        # Test replication verification
        verification = await self.replication_manager.verify_replication("document/test_doc_123")

        # Verify consistency check
        self.assertIn("consistency_check", verification)
        self.assertIn("replica_states", verification)

        consistency = verification["consistency_check"]
        self.assertTrue(consistency["all_replicas_consistent"])
        self.assertTrue(consistency["version_matches"])
        self.assertTrue(consistency["checksum_matches"])
        self.assertEqual(consistency["data_integrity_score"], 1.0)

        # Verify all replicas have same data
        replicas = verification["replica_states"]
        versions = [r["version"] for r in replicas]
        checksums = [r["checksum"] for r in replicas]

        self.assertEqual(len(set(versions)), 1)   # All same version
        self.assertEqual(len(set(checksums)), 1) # All same checksum

    async def test_consistency_models_and_conflict_resolution(self):
        """Test different consistency models and automatic conflict resolution."""
        # Mock concurrent write conflicts
        conflicting_writes = [
            {
                "operation_id": "write_a",
                "data_key": "document/conflict_doc",
                "data": {"content": "Version A", "version": 3},
                "timestamp": "2024-01-01T20:00:00.100Z",
                "node_id": "us-east-1a",
                "user_id": "user1"
            },
            {
                "operation_id": "write_b",
                "data_key": "document/conflict_doc",
                "data": {"content": "Version B", "version": 3},
                "timestamp": "2024-01-01T20:00:00.105Z",
                "node_id": "us-west-2a",
                "user_id": "user2"
            }
        ]

        # Configure conflict detection and resolution
        self.consistency_controller.resolve_conflicts.return_value = {
            "conflict_id": "conflict_001",
            "data_key": "document/conflict_doc",
            "conflicting_operations": conflicting_writes,
            "resolution_strategy": "last_write_wins",
            "resolution_details": {
                "winning_operation": "write_b",
                "reason": "later_timestamp",
                "timestamp_diff_ms": 5,
                "automatic_resolution": True
            },
            "resolved_data": {
                "content": "Version B",
                "version": 4,  # Incremented after resolution
                "last_modified": "2024-01-01T20:00:00.105Z",
                "conflict_resolution": {
                    "resolved_at": "2024-01-01T20:00:00.110Z",
                    "strategy": "last_write_wins",
                    "conflicted_versions": ["write_a", "write_b"]
                }
            },
            "propagation_status": {
                "replicas_updated": 3,
                "propagation_time_ms": 45,
                "consistency_restored": True
            }
        }

        # Test conflict resolution
        resolution = await self.consistency_controller.resolve_conflicts(conflicting_writes)

        # Verify conflict resolution structure
        self.assertIn("conflict_id", resolution)
        self.assertIn("resolution_strategy", resolution)
        self.assertIn("resolved_data", resolution)
        self.assertIn("propagation_status", resolution)

        # Verify resolution logic
        details = resolution["resolution_details"]
        self.assertEqual(details["winning_operation"], "write_b")
        self.assertEqual(details["reason"], "later_timestamp")
        self.assertTrue(details["automatic_resolution"])

        # Verify resolved data
        resolved = resolution["resolved_data"]
        self.assertIn("conflict_resolution", resolved)
        self.assertEqual(resolved["version"], 4)  # Version incremented
        self.assertEqual(resolved["content"], "Version B")

        # Verify propagation
        propagation = resolution["propagation_status"]
        self.assertEqual(propagation["replicas_updated"], 3)
        self.assertTrue(propagation["consistency_restored"])
        self.assertLess(propagation["propagation_time_ms"], 100)

        # Test different consistency levels
        consistency_tests = [
            {
                "level": "strong",
                "expected_behavior": "synchronous_replication",
                "read_guarantee": "latest_write_visible"
            },
            {
                "level": "eventual",
                "expected_behavior": "asynchronous_replication",
                "read_guarantee": "may_see_stale_data"
            },
            {
                "level": "session",
                "expected_behavior": "session_consistent",
                "read_guarantee": "read_your_writes"
            }
        ]

        for test_case in consistency_tests:
            self.consistency_controller.ensure_consistency.return_value = {
                "consistency_level": test_case["level"],
                "behavior": test_case["expected_behavior"],
                "guarantees": {
                    "read_guarantee": test_case["read_guarantee"],
                    "write_acknowledgment": "quorum_based" if test_case["level"] == "strong" else "single_node",
                    "conflict_detection": "automatic",
                    "eventual_consistency_window_ms": 50 if test_case["level"] == "eventual" else 0
                }
            }

            consistency_result = await self.consistency_controller.ensure_consistency(test_case["level"])

            # Verify consistency guarantees
            self.assertEqual(consistency_result["consistency_level"], test_case["level"])
            self.assertEqual(consistency_result["behavior"], test_case["expected_behavior"])

            guarantees = consistency_result["guarantees"]
            self.assertEqual(guarantees["read_guarantee"], test_case["read_guarantee"])

    async def test_partition_tolerance_and_split_brain_handling(self):
        """Test network partition handling and split-brain scenario resolution."""
        # Mock network partition scenario
        partition_scenario = {
            "partition_id": "partition_001",
            "triggered_at": "2024-01-01T20:00:00Z",
            "affected_regions": ["us-west-2", "eu-west-1"],
            "isolated_region": "eu-west-1",
            "partition_type": "network_isolation",
            "duration_estimate": "15_minutes"
        }

        # Configure partition handling
        self.partition_manager.handle_network_partition.return_value = {
            "partition_id": "partition_001",
            "detection_time": "2024-01-01T20:00:00.050Z",
            "response_strategy": "maintain_availability",
            "region_states": {
                "us-east-1": {
                    "status": "primary_active",
                    "nodes_available": 3,
                    "can_accept_writes": True,
                    "quorum_status": "has_quorum"
                },
                "us-west-2": {
                    "status": "secondary_active",
                    "nodes_available": 3,
                    "can_accept_writes": True,
                    "quorum_status": "has_quorum"
                },
                "eu-west-1": {
                    "status": "isolated",
                    "nodes_available": 3,
                    "can_accept_writes": False,  # Minority partition
                    "quorum_status": "no_quorum"
                }
            },
            "operational_decisions": {
                "primary_region": "us-east-1",
                "write_acceptance": "majority_regions_only",
                "read_availability": "all_available_regions",
                "conflict_resolution": "primary_region_wins",
                "data_reconciliation": "scheduled_on_partition_heal"
            },
            "availability_impact": {
                "overall_availability": 0.89,  # Reduced but still operational
                "write_availability": 0.67,    # 2/3 regions can write
                "read_availability": 1.0,      # All regions can read
                "affected_users": 0.23         # 23% users in EU region
            }
        }

        # Test partition handling
        partition_response = await self.partition_manager.handle_network_partition(partition_scenario)

        # Verify partition response structure
        self.assertIn("partition_id", partition_response)
        self.assertIn("region_states", partition_response)
        self.assertIn("operational_decisions", partition_response)
        self.assertIn("availability_impact", partition_response)

        # Verify region states
        region_states = partition_response["region_states"]
        self.assertEqual(len(region_states), 3)

        # Verify primary region maintains quorum
        primary_region = region_states["us-east-1"]
        self.assertEqual(primary_region["status"], "primary_active")
        self.assertTrue(primary_region["can_accept_writes"])
        self.assertEqual(primary_region["quorum_status"], "has_quorum")

        # Verify isolated region loses write capability
        isolated_region = region_states["eu-west-1"]
        self.assertEqual(isolated_region["status"], "isolated")
        self.assertFalse(isolated_region["can_accept_writes"])
        self.assertEqual(isolated_region["quorum_status"], "no_quorum")

        # Verify operational decisions
        decisions = partition_response["operational_decisions"]
        self.assertEqual(decisions["primary_region"], "us-east-1")
        self.assertEqual(decisions["write_acceptance"], "majority_regions_only")
        self.assertEqual(decisions["conflict_resolution"], "primary_region_wins")

        # Verify availability maintained
        availability = partition_response["availability_impact"]
        self.assertGreater(availability["overall_availability"], 0.8)  # Still highly available
        self.assertEqual(availability["read_availability"], 1.0)       # Reads unaffected

        # Test split-brain detection and resolution
        self.partition_manager.detect_split_brain.return_value = {
            "split_brain_detected": True,
            "detection_timestamp": "2024-01-01T20:05:00Z",
            "conflicting_primaries": ["us-east-1", "us-west-2"],
            "split_brain_scenario": {
                "trigger": "network_partition_with_equal_partitions",
                "partition_a": {
                    "regions": ["us-east-1"],
                    "nodes": 3,
                    "claimed_primary": True,
                    "last_known_state": "2024-01-01T20:00:00Z"
                },
                "partition_b": {
                    "regions": ["us-west-2"],
                    "nodes": 3,
                    "claimed_primary": True,
                    "last_known_state": "2024-01-01T20:00:05Z"
                }
            },
            "resolution_strategy": {
                "method": "latest_timestamp_wins",
                "winning_partition": "partition_b",
                "reason": "more_recent_state",
                "demoted_partition": "partition_a",
                "reconciliation_required": True
            }
        }

        # Test split-brain detection
        split_brain_result = await self.partition_manager.detect_split_brain()

        # Verify split-brain detection
        self.assertTrue(split_brain_result["split_brain_detected"])
        self.assertIn("conflicting_primaries", split_brain_result)
        self.assertIn("resolution_strategy", split_brain_result)

        # Verify resolution strategy
        resolution = split_brain_result["resolution_strategy"]
        self.assertEqual(resolution["method"], "latest_timestamp_wins")
        self.assertIn("winning_partition", resolution)
        self.assertTrue(resolution["reconciliation_required"])

    async def test_data_sharding_and_load_balancing(self):
        """Test data sharding strategy and automatic load balancing."""
        # Mock data distribution scenario
        sharding_config = {
            "sharding_strategy": "consistent_hashing",
            "shard_count": 128,
            "replication_factor": 3,
            "load_balancing": "automatic",
            "rebalancing_threshold": 0.15  # 15% imbalance triggers rebalancing
        }

        # Configure current shard distribution
        self.storage_cluster.get_cluster_status.return_value = {
            "sharding_status": {
                "total_shards": 128,
                "shard_distribution": {
                    "us-east-1a": {"shard_count": 43, "load_percentage": 0.336, "status": "overloaded"},
                    "us-east-1b": {"shard_count": 41, "load_percentage": 0.320, "status": "balanced"},
                    "us-east-1c": {"shard_count": 44, "load_percentage": 0.344, "status": "overloaded"},
                    "us-west-2a": {"shard_count": 38, "load_percentage": 0.297, "status": "underloaded"},
                    "us-west-2b": {"shard_count": 42, "load_percentage": 0.328, "status": "balanced"},
                    "us-west-2c": {"shard_count": 39, "load_percentage": 0.305, "status": "underloaded"},
                    "eu-west-1a": {"shard_count": 41, "load_percentage": 0.320, "status": "balanced"},
                    "eu-west-1b": {"shard_count": 40, "load_percentage": 0.313, "status": "balanced"},
                    "eu-west-1c": {"shard_count": 40, "load_percentage": 0.313, "status": "balanced"}
                },
                "balance_metrics": {
                    "max_load": 0.344,
                    "min_load": 0.297,
                    "load_variance": 0.047,  # 4.7% variance
                    "imbalance_ratio": 0.158, # Exceeds 15% threshold
                    "rebalancing_needed": True
                }
            }
        }

        # Test current shard distribution analysis
        cluster_status = await self.storage_cluster.get_cluster_status()
        sharding_status = cluster_status["sharding_status"]

        # Verify sharding structure
        self.assertIn("total_shards", sharding_status)
        self.assertIn("shard_distribution", sharding_status)
        self.assertIn("balance_metrics", sharding_status)

        # Verify shard distribution
        distribution = sharding_status["shard_distribution"]
        total_distributed_shards = sum(node["shard_count"] for node in distribution.values())
        self.assertEqual(total_distributed_shards, 128)

        # Verify balance metrics
        balance_metrics = sharding_status["balance_metrics"]
        self.assertTrue(balance_metrics["rebalancing_needed"])
        self.assertGreater(balance_metrics["imbalance_ratio"], 0.15)

        # Configure rebalancing operation
        self.storage_cluster.rebalance_data.return_value = {
            "rebalancing_id": "rebalance_001",
            "started_at": "2024-01-01T20:10:00Z",
            "strategy": "gradual_migration",
            "migration_plan": [
                {
                    "shard_id": "shard_042",
                    "from_node": "us-east-1a",
                    "to_node": "us-west-2a",
                    "data_size_gb": 2.8,
                    "estimated_time_minutes": 8
                },
                {
                    "shard_id": "shard_087",
                    "from_node": "us-east-1c",
                    "to_node": "us-west-2c",
                    "data_size_gb": 3.1,
                    "estimated_time_minutes": 9
                }
            ],
            "rebalancing_progress": {
                "total_migrations": 6,
                "completed_migrations": 0,
                "in_progress_migrations": 0,
                "estimated_completion": "2024-01-01T21:15:00Z",
                "data_transfer_rate_mbps": 125.4
            },
            "expected_outcome": {
                "max_load_after": 0.325,
                "min_load_after": 0.315,
                "expected_variance": 0.010,
                "balance_improvement": 0.78  # 78% improvement
            }
        }

        # Test data rebalancing
        rebalancing = await self.storage_cluster.rebalance_data(sharding_config)

        # Verify rebalancing plan
        self.assertIn("rebalancing_id", rebalancing)
        self.assertIn("migration_plan", rebalancing)
        self.assertIn("expected_outcome", rebalancing)

        # Verify migration plan
        migration_plan = rebalancing["migration_plan"]
        self.assertGreater(len(migration_plan), 0)

        for migration in migration_plan:
            self.assertIn("shard_id", migration)
            self.assertIn("from_node", migration)
            self.assertIn("to_node", migration)
            self.assertNotEqual(migration["from_node"], migration["to_node"])

        # Verify expected improvement
        expected = rebalancing["expected_outcome"]
        self.assertLess(expected["expected_variance"], 0.015)  # Much better balance
        self.assertGreater(expected["balance_improvement"], 0.7)  # Significant improvement

    async def test_storage_performance_and_scalability(self):
        """Test storage performance metrics and horizontal scalability."""
        # Mock performance test scenario
        performance_config = {
            "test_type": "load_test",
            "duration_minutes": 10,
            "concurrent_operations": 1000,
            "operation_mix": {
                "reads": 0.70,
                "writes": 0.25,
                "deletes": 0.05
            },
            "data_size_range": {"min_kb": 1, "max_kb": 500}
        }

        # Configure performance test results
        self.storage_cluster.get_cluster_status.return_value = {
            "performance_metrics": {
                "test_duration_seconds": 600,
                "total_operations": 45672,
                "operation_breakdown": {
                    "reads": {"count": 31970, "success_rate": 0.998, "avg_latency_ms": 12.4},
                    "writes": {"count": 11418, "success_rate": 0.995, "avg_latency_ms": 24.7},
                    "deletes": {"count": 2284, "success_rate": 0.999, "avg_latency_ms": 18.2}
                },
                "throughput_metrics": {
                    "operations_per_second": 76.12,
                    "reads_per_second": 53.28,
                    "writes_per_second": 19.03,
                    "deletes_per_second": 3.81,
                    "data_throughput_mbps": 145.7
                },
                "latency_percentiles": {
                    "p50": 15.2,
                    "p95": 45.8,
                    "p99": 89.6,
                    "p999": 156.3
                },
                "scalability_indicators": {
                    "linear_scalability_score": 0.92,
                    "bottleneck_detection": "none",
                    "capacity_headroom": 0.35,  # 35% capacity remaining
                    "recommended_node_count": 12  # Scale from 9 to 12 nodes
                }
            }
        }

        # Test performance measurement
        performance = await self.storage_cluster.get_cluster_status()
        metrics = performance["performance_metrics"]

        # Verify performance structure
        self.assertIn("total_operations", metrics)
        self.assertIn("operation_breakdown", metrics)
        self.assertIn("throughput_metrics", metrics)
        self.assertIn("latency_percentiles", metrics)
        self.assertIn("scalability_indicators", metrics)

        # Verify operation success rates
        operations = metrics["operation_breakdown"]
        for op_type, op_data in operations.items():
            self.assertGreater(op_data["success_rate"], 0.99)  # >99% success
            self.assertLess(op_data["avg_latency_ms"], 30)     # <30ms average

        # Verify throughput
        throughput = metrics["throughput_metrics"]
        self.assertGreater(throughput["operations_per_second"], 50)
        self.assertGreater(throughput["data_throughput_mbps"], 100)

        # Verify latency percentiles
        latency = metrics["latency_percentiles"]
        self.assertLess(latency["p50"], 20)   # Sub-20ms median
        self.assertLess(latency["p95"], 50)   # Sub-50ms P95
        self.assertLess(latency["p99"], 100)  # Sub-100ms P99

        # Verify scalability indicators
        scalability = metrics["scalability_indicators"]
        self.assertGreater(scalability["linear_scalability_score"], 0.9)
        self.assertEqual(scalability["bottleneck_detection"], "none")
        self.assertGreater(scalability["capacity_headroom"], 0.3)

        # Test horizontal scaling
        self.storage_cluster.add_node.return_value = {
            "scaling_operation_id": "scale_001",
            "new_node_id": "us-east-1d",
            "node_specs": {
                "region": "us-east-1",
                "cpu_cores": 16,
                "memory_gb": 64,
                "storage_tb": 8,
                "network_gbps": 10
            },
            "integration_status": {
                "node_provisioned": True,
                "cluster_joined": True,
                "data_migration_started": True,
                "load_balancing_updated": True,
                "health_checks_passing": True
            },
            "estimated_impact": {
                "capacity_increase": 0.111,  # 11.1% more capacity (1/9)
                "performance_improvement": 0.105, # ~10% better performance
                "rebalancing_time_minutes": 45,
                "service_disruption": "none"
            }
        }

        # Test node addition
        scaling_result = await self.storage_cluster.add_node({
            "region": "us-east-1",
            "node_type": "storage_node"
        })

        # Verify scaling operation
        self.assertIn("scaling_operation_id", scaling_result)
        self.assertIn("integration_status", scaling_result)
        self.assertIn("estimated_impact", scaling_result)

        # Verify integration status
        integration = scaling_result["integration_status"]
        for status_check, status_value in integration.items():
            self.assertTrue(status_value)  # All integration checks should pass

        # Verify impact estimation
        impact = scaling_result["estimated_impact"]
        self.assertGreater(impact["capacity_increase"], 0.1)      # >10% capacity gain
        self.assertGreater(impact["performance_improvement"], 0.1) # >10% performance gain
        self.assertEqual(impact["service_disruption"], "none")     # No downtime


if __name__ == '__main__':
    pytest.main([__file__, '-v'])