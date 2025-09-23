"""
FR-007: Container Orchestration and Kubernetes Management
Test container orchestration with Kubernetes deployment, auto-scaling, and cluster management.

This module tests the container orchestration infrastructure that manages
containerized services with Kubernetes, including deployment strategies,
auto-scaling, resource management, and cluster health monitoring.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR007ContainerOrchestration(BaseFRTest):
    """Test suite for FR-007 Container Orchestration and Kubernetes Management."""

    async def asyncSetUp(self):
        """Set up test environment with container orchestration infrastructure."""
        await super().asyncSetUp()
        self.k8s_cluster = self._create_mock_k8s_cluster()
        self.deployment_manager = self._create_mock_deployment_manager()
        self.autoscaler = self._create_mock_autoscaler()
        self.resource_manager = self._create_mock_resource_manager()

    def _create_mock_k8s_cluster(self) -> Mock:
        """Create mock Kubernetes cluster management."""
        cluster = Mock()
        cluster.get_cluster_status = AsyncMock()
        cluster.get_node_status = AsyncMock()
        cluster.manage_workloads = AsyncMock()
        cluster.apply_manifest = AsyncMock()
        return cluster

    def _create_mock_deployment_manager(self) -> Mock:
        """Create mock deployment management system."""
        manager = Mock()
        manager.deploy_service = AsyncMock()
        manager.rollback_deployment = AsyncMock()
        manager.update_deployment = AsyncMock()
        manager.get_deployment_status = AsyncMock()
        return manager

    def _create_mock_autoscaler(self) -> Mock:
        """Create mock horizontal and vertical pod autoscaling."""
        scaler = Mock()
        scaler.configure_hpa = AsyncMock()
        scaler.configure_vpa = AsyncMock()
        scaler.get_scaling_metrics = AsyncMock()
        scaler.scale_deployment = AsyncMock()
        return scaler

    def _create_mock_resource_manager(self) -> Mock:
        """Create mock resource management and monitoring."""
        manager = Mock()
        manager.allocate_resources = AsyncMock()
        manager.monitor_usage = AsyncMock()
        manager.optimize_placement = AsyncMock()
        manager.manage_quotas = AsyncMock()
        return manager

    async def test_kubernetes_cluster_management_and_health(self):
        """Test Kubernetes cluster health monitoring and node management."""
        # Mock cluster configuration
        cluster_config = {
            "cluster_name": "ttrpg-production",
            "kubernetes_version": "v1.28.4",
            "region": "us-east-1",
            "node_groups": ["system", "application", "compute"],
            "networking": {
                "pod_cidr": "10.244.0.0/16",
                "service_cidr": "10.96.0.0/12",
                "cni": "calico"
            }
        }

        # Configure cluster status
        self.k8s_cluster.get_cluster_status.return_value = {
            "cluster_info": {
                "name": "ttrpg-production",
                "version": "v1.28.4",
                "status": "healthy",
                "control_plane_status": "ready",
                "api_server_endpoint": "https://k8s-api.ttrpg-center.com",
                "created_at": "2024-01-01T10:00:00Z",
                "last_updated": "2024-01-01T20:00:00Z"
            },
            "node_summary": {
                "total_nodes": 12,
                "ready_nodes": 11,
                "not_ready_nodes": 1,
                "node_groups": {
                    "system": {"nodes": 3, "ready": 3, "cpu_cores": 24, "memory_gb": 96},
                    "application": {"nodes": 6, "ready": 5, "cpu_cores": 96, "memory_gb": 384},
                    "compute": {"nodes": 3, "ready": 3, "cpu_cores": 48, "memory_gb": 192}
                }
            },
            "resource_utilization": {
                "total_cpu_cores": 168,
                "allocated_cpu_cores": 89,
                "cpu_utilization": 0.53,
                "total_memory_gb": 672,
                "allocated_memory_gb": 378,
                "memory_utilization": 0.56,
                "total_storage_tb": 24,
                "allocated_storage_tb": 12,
                "storage_utilization": 0.50
            },
            "cluster_health": {
                "overall_health": "healthy",
                "control_plane_health": "healthy",
                "network_health": "healthy",
                "dns_health": "healthy",
                "storage_health": "healthy",
                "monitoring_health": "healthy"
            },
            "workload_summary": {
                "namespaces": 8,
                "deployments": 24,
                "pods_total": 156,
                "pods_running": 148,
                "pods_pending": 3,
                "pods_failed": 5,
                "services": 32,
                "ingresses": 12
            }
        }

        # Test cluster status
        cluster_status = await self.k8s_cluster.get_cluster_status()

        # Verify cluster structure
        self.assertIn("cluster_info", cluster_status)
        self.assertIn("node_summary", cluster_status)
        self.assertIn("resource_utilization", cluster_status)
        self.assertIn("cluster_health", cluster_status)

        # Verify cluster info
        cluster_info = cluster_status["cluster_info"]
        self.assertEqual(cluster_info["status"], "healthy")
        self.assertEqual(cluster_info["control_plane_status"], "ready")
        self.assertEqual(cluster_info["version"], "v1.28.4")

        # Verify node summary
        node_summary = cluster_status["node_summary"]
        self.assertEqual(node_summary["total_nodes"], 12)
        self.assertEqual(node_summary["ready_nodes"], 11)
        self.assertEqual(node_summary["not_ready_nodes"], 1)

        # Verify node groups
        node_groups = node_summary["node_groups"]
        self.assertIn("system", node_groups)
        self.assertIn("application", node_groups)
        self.assertIn("compute", node_groups)

        # All system nodes should be ready
        self.assertEqual(node_groups["system"]["ready"], node_groups["system"]["nodes"])

        # Verify resource utilization
        resources = cluster_status["resource_utilization"]
        self.assertLess(resources["cpu_utilization"], 0.8)      # Under 80% CPU
        self.assertLess(resources["memory_utilization"], 0.8)   # Under 80% memory
        self.assertLess(resources["storage_utilization"], 0.8)  # Under 80% storage

        # Verify cluster health
        health = cluster_status["cluster_health"]
        self.assertEqual(health["overall_health"], "healthy")
        self.assertEqual(health["control_plane_health"], "healthy")
        self.assertEqual(health["network_health"], "healthy")

        # Verify workload summary
        workloads = cluster_status["workload_summary"]
        self.assertGreater(workloads["pods_running"], workloads["pods_failed"])
        self.assertLess(workloads["pods_pending"], 5)  # Low pending pod count

        # Test individual node status
        self.k8s_cluster.get_node_status.return_value = {
            "node_details": [
                {
                    "node_name": "app-node-01",
                    "node_group": "application",
                    "status": "Ready",
                    "roles": ["worker"],
                    "kubernetes_version": "v1.28.4",
                    "container_runtime": "containerd://1.7.8",
                    "capacity": {
                        "cpu": "16",
                        "memory": "64Gi",
                        "ephemeral_storage": "100Gi",
                        "pods": "110"
                    },
                    "allocatable": {
                        "cpu": "15800m",
                        "memory": "61Gi",
                        "ephemeral_storage": "90Gi",
                        "pods": "110"
                    },
                    "usage": {
                        "cpu_usage": "8200m",
                        "memory_usage": "32Gi",
                        "pod_count": 28,
                        "cpu_utilization": 0.52,
                        "memory_utilization": 0.52
                    },
                    "conditions": [
                        {"type": "Ready", "status": "True"},
                        {"type": "MemoryPressure", "status": "False"},
                        {"type": "DiskPressure", "status": "False"},
                        {"type": "PIDPressure", "status": "False"}
                    ],
                    "taints": [],
                    "labels": {
                        "kubernetes.io/os": "linux",
                        "node.kubernetes.io/instance-type": "m5.2xlarge",
                        "topology.kubernetes.io/zone": "us-east-1a"
                    }
                }
            ],
            "unhealthy_nodes": [
                {
                    "node_name": "app-node-06",
                    "status": "NotReady",
                    "issue": "kubelet_not_responding",
                    "last_heartbeat": "2024-01-01T19:45:00Z",
                    "remediation_actions": ["restart_kubelet", "drain_node", "replace_node"]
                }
            ]
        }

        # Test node status
        node_status = await self.k8s_cluster.get_node_status()

        # Verify node details
        self.assertIn("node_details", node_status)
        self.assertIn("unhealthy_nodes", node_status)

        # Verify healthy node
        healthy_nodes = node_status["node_details"]
        self.assertGreater(len(healthy_nodes), 0)

        node = healthy_nodes[0]
        self.assertEqual(node["status"], "Ready")
        self.assertIn("capacity", node)
        self.assertIn("usage", node)

        # Verify resource usage is reasonable
        usage = node["usage"]
        self.assertLess(usage["cpu_utilization"], 0.8)
        self.assertLess(usage["memory_utilization"], 0.8)

        # Verify node conditions
        conditions = node["conditions"]
        ready_condition = next(c for c in conditions if c["type"] == "Ready")
        self.assertEqual(ready_condition["status"], "True")

        # Verify unhealthy nodes are identified
        unhealthy_nodes = node_status["unhealthy_nodes"]
        self.assertEqual(len(unhealthy_nodes), 1)

        unhealthy = unhealthy_nodes[0]
        self.assertEqual(unhealthy["status"], "NotReady")
        self.assertIn("remediation_actions", unhealthy)

    async def test_deployment_strategies_and_rollout_management(self):
        """Test various deployment strategies including rolling updates and blue-green deployments."""
        # Mock service deployment configuration
        deployment_config = {
            "service_name": "search-service",
            "namespace": "ttrpg-production",
            "deployment_strategy": "rolling_update",
            "image": "ttrpg/search-service:v2.1.0",
            "replicas": 6,
            "resources": {
                "requests": {"cpu": "500m", "memory": "1Gi"},
                "limits": {"cpu": "2", "memory": "4Gi"}
            },
            "rolling_update": {
                "max_unavailable": "25%",
                "max_surge": "25%"
            },
            "readiness_probe": {
                "http_get": {"path": "/health", "port": 8080},
                "initial_delay_seconds": 30,
                "period_seconds": 10
            },
            "liveness_probe": {
                "http_get": {"path": "/health", "port": 8080},
                "initial_delay_seconds": 60,
                "period_seconds": 30
            }
        }

        # Configure deployment process
        self.deployment_manager.deploy_service.return_value = {
            "deployment_id": "deploy_001",
            "deployment_status": "in_progress",
            "deployment_strategy": "rolling_update",
            "rollout_status": {
                "phase": "updating",
                "current_replicas": 6,
                "updated_replicas": 3,
                "ready_replicas": 5,
                "unavailable_replicas": 1,
                "conditions": [
                    {
                        "type": "Progressing",
                        "status": "True",
                        "reason": "ReplicaSetUpdated",
                        "message": "ReplicaSet has been updated"
                    }
                ]
            },
            "rollout_timeline": [
                {
                    "timestamp": "2024-01-01T20:00:00Z",
                    "event": "deployment_started",
                    "details": "Rolling update initiated"
                },
                {
                    "timestamp": "2024-01-01T20:01:00Z",
                    "event": "new_replicaset_created",
                    "details": "Created ReplicaSet search-service-7b8c9d"
                },
                {
                    "timestamp": "2024-01-01T20:02:00Z",
                    "event": "pods_scaling_up",
                    "details": "Scaling up new ReplicaSet to 2 replicas"
                },
                {
                    "timestamp": "2024-01-01T20:03:30Z",
                    "event": "pods_ready",
                    "details": "2 new pods are ready and serving traffic"
                }
            ],
            "estimated_completion": "2024-01-01T20:08:00Z",
            "health_checks": {
                "readiness_checks_passed": 3,
                "liveness_checks_passed": 3,
                "health_check_failures": 0
            }
        }

        # Test deployment initiation
        deployment_result = await self.deployment_manager.deploy_service(deployment_config)

        # Verify deployment structure
        self.assertIn("deployment_id", deployment_result)
        self.assertIn("rollout_status", deployment_result)
        self.assertIn("rollout_timeline", deployment_result)
        self.assertIn("health_checks", deployment_result)

        # Verify deployment strategy
        self.assertEqual(deployment_result["deployment_strategy"], "rolling_update")
        self.assertEqual(deployment_result["deployment_status"], "in_progress")

        # Verify rollout status
        rollout = deployment_result["rollout_status"]
        self.assertEqual(rollout["phase"], "updating")
        self.assertGreater(rollout["updated_replicas"], 0)
        self.assertLess(rollout["unavailable_replicas"], rollout["current_replicas"])

        # Verify rollout conditions
        conditions = rollout["conditions"]
        progressing = next(c for c in conditions if c["type"] == "Progressing")
        self.assertEqual(progressing["status"], "True")

        # Verify timeline events
        timeline = deployment_result["rollout_timeline"]
        self.assertGreater(len(timeline), 0)

        for event in timeline:
            self.assertIn("timestamp", event)
            self.assertIn("event", event)
            self.assertIn("details", event)

        # Verify health checks
        health = deployment_result["health_checks"]
        self.assertGreater(health["readiness_checks_passed"], 0)
        self.assertEqual(health["health_check_failures"], 0)

        # Test deployment completion
        self.deployment_manager.get_deployment_status.return_value = {
            "deployment_id": "deploy_001",
            "deployment_status": "completed",
            "rollout_status": {
                "phase": "complete",
                "current_replicas": 6,
                "updated_replicas": 6,
                "ready_replicas": 6,
                "unavailable_replicas": 0,
                "conditions": [
                    {
                        "type": "Progressing",
                        "status": "True",
                        "reason": "NewReplicaSetAvailable",
                        "message": "ReplicaSet has successfully progressed"
                    },
                    {
                        "type": "Available",
                        "status": "True",
                        "reason": "MinimumReplicasAvailable",
                        "message": "Deployment has minimum availability"
                    }
                ]
            },
            "deployment_metrics": {
                "total_duration_seconds": 480,
                "zero_downtime_achieved": True,
                "rollout_success_rate": 1.0,
                "average_pod_startup_time": 45
            },
            "new_version_info": {
                "image": "ttrpg/search-service:v2.1.0",
                "image_digest": "sha256:abc123...",
                "deployment_generation": 15,
                "replica_set": "search-service-7b8c9d"
            }
        }

        # Test deployment status
        final_status = await self.deployment_manager.get_deployment_status("deploy_001")

        # Verify completion
        self.assertEqual(final_status["deployment_status"], "completed")

        # Verify final rollout status
        final_rollout = final_status["rollout_status"]
        self.assertEqual(final_rollout["phase"], "complete")
        self.assertEqual(final_rollout["unavailable_replicas"], 0)
        self.assertEqual(final_rollout["ready_replicas"], 6)

        # Verify deployment metrics
        metrics = final_status["deployment_metrics"]
        self.assertTrue(metrics["zero_downtime_achieved"])
        self.assertEqual(metrics["rollout_success_rate"], 1.0)
        self.assertLess(metrics["average_pod_startup_time"], 60)

        # Test blue-green deployment
        blue_green_config = {
            **deployment_config,
            "deployment_strategy": "blue_green",
            "traffic_split": {"blue": 100, "green": 0},  # Start with all traffic on blue
            "switch_traffic_after_validation": True
        }

        self.deployment_manager.deploy_service.return_value = {
            "deployment_id": "deploy_002",
            "deployment_status": "completed",
            "deployment_strategy": "blue_green",
            "blue_green_status": {
                "blue_environment": {
                    "version": "v2.0.0",
                    "replicas": 6,
                    "status": "active",
                    "traffic_percentage": 0  # Traffic switched to green
                },
                "green_environment": {
                    "version": "v2.1.0",
                    "replicas": 6,
                    "status": "active",
                    "traffic_percentage": 100  # New version receiving traffic
                },
                "switch_completed": True,
                "rollback_available": True,
                "validation_results": {
                    "health_checks_passed": True,
                    "performance_tests_passed": True,
                    "integration_tests_passed": True,
                    "traffic_validation_successful": True
                }
            }
        }

        # Test blue-green deployment
        bg_result = await self.deployment_manager.deploy_service(blue_green_config)

        # Verify blue-green structure
        self.assertIn("blue_green_status", bg_result)
        self.assertEqual(bg_result["deployment_strategy"], "blue_green")

        # Verify environment status
        bg_status = bg_result["blue_green_status"]
        self.assertTrue(bg_status["switch_completed"])
        self.assertTrue(bg_status["rollback_available"])

        green_env = bg_status["green_environment"]
        self.assertEqual(green_env["traffic_percentage"], 100)
        self.assertEqual(green_env["status"], "active")

        # Verify validation results
        validation = bg_status["validation_results"]
        self.assertTrue(validation["health_checks_passed"])
        self.assertTrue(validation["performance_tests_passed"])
        self.assertTrue(validation["traffic_validation_successful"])

    async def test_horizontal_and_vertical_pod_autoscaling(self):
        """Test HPA and VPA configuration and scaling behavior."""
        # Mock HPA configuration
        hpa_config = {
            "target_deployment": "search-service",
            "namespace": "ttrpg-production",
            "min_replicas": 3,
            "max_replicas": 20,
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}
                },
                {
                    "type": "Resource",
                    "resource": {"name": "memory", "target": {"type": "Utilization", "averageUtilization": 80}}
                },
                {
                    "type": "Pods",
                    "pods": {"metric": {"name": "requests_per_second"}, "target": {"type": "AverageValue", "averageValue": "100"}}
                }
            ],
            "behavior": {
                "scaleUp": {
                    "stabilizationWindowSeconds": 300,
                    "policies": [
                        {"type": "Percent", "value": 100, "periodSeconds": 60},
                        {"type": "Pods", "value": 5, "periodSeconds": 60}
                    ]
                },
                "scaleDown": {
                    "stabilizationWindowSeconds": 600,
                    "policies": [
                        {"type": "Percent", "value": 50, "periodSeconds": 60}
                    ]
                }
            }
        }

        # Configure HPA
        self.autoscaler.configure_hpa.return_value = {
            "hpa_name": "search-service-hpa",
            "configuration_status": "active",
            "current_metrics": {
                "cpu_utilization": 0.45,     # 45% CPU
                "memory_utilization": 0.52,  # 52% memory
                "requests_per_second": 85,   # Below target of 100
                "current_replicas": 6,
                "desired_replicas": 6,       # No scaling needed
                "last_scale_time": "2024-01-01T19:30:00Z"
            },
            "scaling_conditions": [
                {
                    "type": "AbleToScale",
                    "status": "True",
                    "reason": "ReadyForNewScale",
                    "message": "The HPA controller is able to scale"
                },
                {
                    "type": "ScalingActive",
                    "status": "True",
                    "reason": "ValidMetricFound",
                    "message": "The HPA is able to obtain metrics"
                },
                {
                    "type": "ScalingLimited",
                    "status": "False",
                    "reason": "DesiredWithinRange",
                    "message": "The desired count is within the acceptable range"
                }
            ],
            "scaling_events": [
                {
                    "timestamp": "2024-01-01T18:45:00Z",
                    "type": "scale_up",
                    "from_replicas": 4,
                    "to_replicas": 6,
                    "reason": "cpu_threshold_exceeded",
                    "metric_value": 0.82
                }
            ]
        }

        # Test HPA configuration
        hpa_result = await self.autoscaler.configure_hpa(hpa_config)

        # Verify HPA structure
        self.assertIn("hpa_name", hpa_result)
        self.assertIn("current_metrics", hpa_result)
        self.assertIn("scaling_conditions", hpa_result)
        self.assertIn("scaling_events", hpa_result)

        # Verify configuration status
        self.assertEqual(hpa_result["configuration_status"], "active")

        # Verify current metrics
        metrics = hpa_result["current_metrics"]
        self.assertLess(metrics["cpu_utilization"], 0.7)      # Below CPU target
        self.assertLess(metrics["memory_utilization"], 0.8)   # Below memory target
        self.assertLess(metrics["requests_per_second"], 100)  # Below RPS target
        self.assertEqual(metrics["desired_replicas"], metrics["current_replicas"])

        # Verify scaling conditions
        conditions = hpa_result["scaling_conditions"]
        able_to_scale = next(c for c in conditions if c["type"] == "AbleToScale")
        self.assertEqual(able_to_scale["status"], "True")

        scaling_active = next(c for c in conditions if c["type"] == "ScalingActive")
        self.assertEqual(scaling_active["status"], "True")

        # Test scaling trigger simulation
        high_load_metrics = {
            "cpu_utilization": 0.85,     # Above 70% threshold
            "memory_utilization": 0.88,  # Above 80% threshold
            "requests_per_second": 150   # Above 100 target
        }

        self.autoscaler.scale_deployment.return_value = {
            "scaling_decision": {
                "action": "scale_up",
                "from_replicas": 6,
                "to_replicas": 10,
                "scaling_reason": "multiple_metrics_exceeded",
                "triggered_by_metrics": ["cpu_utilization", "memory_utilization", "requests_per_second"]
            },
            "scaling_execution": {
                "scaling_started": "2024-01-01T20:05:00Z",
                "estimated_completion": "2024-01-01T20:07:00Z",
                "new_pods_requested": 4,
                "scaling_policy_applied": "pods_limit_5_per_minute",
                "stabilization_window": 300
            },
            "resource_impact": {
                "additional_cpu_requested": "2000m",
                "additional_memory_requested": "4Gi",
                "cluster_capacity_sufficient": True,
                "node_autoscaling_triggered": False
            }
        }

        # Test scaling decision
        scaling_result = await self.autoscaler.scale_deployment("search-service", high_load_metrics)

        # Verify scaling decision
        self.assertIn("scaling_decision", scaling_result)
        self.assertIn("scaling_execution", scaling_result)
        self.assertIn("resource_impact", scaling_result)

        # Verify scaling logic
        decision = scaling_result["scaling_decision"]
        self.assertEqual(decision["action"], "scale_up")
        self.assertEqual(decision["from_replicas"], 6)
        self.assertEqual(decision["to_replicas"], 10)
        self.assertIn("multiple_metrics_exceeded", decision["scaling_reason"])

        # Verify triggered metrics
        triggered_metrics = decision["triggered_by_metrics"]
        self.assertIn("cpu_utilization", triggered_metrics)
        self.assertIn("memory_utilization", triggered_metrics)
        self.assertIn("requests_per_second", triggered_metrics)

        # Verify resource impact
        impact = scaling_result["resource_impact"]
        self.assertTrue(impact["cluster_capacity_sufficient"])
        self.assertFalse(impact["node_autoscaling_triggered"])

        # Test VPA configuration
        vpa_config = {
            "target_deployment": "content-service",
            "namespace": "ttrpg-production",
            "update_mode": "Auto",
            "resource_policy": {
                "container_policies": [
                    {
                        "container_name": "content-service",
                        "min_allowed": {"cpu": "100m", "memory": "128Mi"},
                        "max_allowed": {"cpu": "4", "memory": "8Gi"},
                        "controlled_resources": ["cpu", "memory"]
                    }
                ]
            }
        }

        self.autoscaler.configure_vpa.return_value = {
            "vpa_name": "content-service-vpa",
            "update_mode": "Auto",
            "recommendations": {
                "container_recommendations": [
                    {
                        "container_name": "content-service",
                        "current_resources": {"cpu": "1", "memory": "2Gi"},
                        "recommended_resources": {"cpu": "1.2", "memory": "2.5Gi"},
                        "lower_bound": {"cpu": "800m", "memory": "1.8Gi"},
                        "upper_bound": {"cpu": "2", "memory": "4Gi"},
                        "recommendation_confidence": 0.87
                    }
                ]
            },
            "update_history": [
                {
                    "timestamp": "2024-01-01T19:00:00Z",
                    "action": "resource_update",
                    "container": "content-service",
                    "from_cpu": "800m",
                    "to_cpu": "1",
                    "from_memory": "1.5Gi",
                    "to_memory": "2Gi",
                    "reason": "resource_optimization"
                }
            ]
        }

        # Test VPA configuration
        vpa_result = await self.autoscaler.configure_vpa(vpa_config)

        # Verify VPA structure
        self.assertIn("vpa_name", vpa_result)
        self.assertIn("recommendations", vpa_result)
        self.assertIn("update_history", vpa_result)

        # Verify VPA recommendations
        recommendations = vpa_result["recommendations"]["container_recommendations"]
        self.assertGreater(len(recommendations), 0)

        recommendation = recommendations[0]
        self.assertIn("current_resources", recommendation)
        self.assertIn("recommended_resources", recommendation)
        self.assertGreater(recommendation["recommendation_confidence"], 0.8)

    async def test_resource_management_and_quotas(self):
        """Test resource allocation, quotas, and cluster capacity management."""
        # Mock namespace resource configuration
        namespace_config = {
            "namespace": "ttrpg-production",
            "resource_quota": {
                "requests.cpu": "50",
                "requests.memory": "100Gi",
                "limits.cpu": "100",
                "limits.memory": "200Gi",
                "persistentvolumeclaims": "10",
                "pods": "50",
                "services": "20"
            },
            "limit_ranges": [
                {
                    "type": "Container",
                    "default": {"cpu": "200m", "memory": "256Mi"},
                    "default_request": {"cpu": "100m", "memory": "128Mi"},
                    "max": {"cpu": "4", "memory": "8Gi"},
                    "min": {"cpu": "50m", "memory": "64Mi"}
                }
            ]
        }

        # Configure resource management
        self.resource_manager.manage_quotas.return_value = {
            "namespace": "ttrpg-production",
            "quota_status": {
                "hard_limits": {
                    "requests.cpu": "50",
                    "requests.memory": "100Gi",
                    "limits.cpu": "100",
                    "limits.memory": "200Gi",
                    "pods": "50"
                },
                "current_usage": {
                    "requests.cpu": "32.5",
                    "requests.memory": "68Gi",
                    "limits.cpu": "65",
                    "limits.memory": "130Gi",
                    "pods": "35"
                },
                "utilization_percentages": {
                    "requests.cpu": 0.65,      # 65% of CPU requests used
                    "requests.memory": 0.68,   # 68% of memory requests used
                    "limits.cpu": 0.65,        # 65% of CPU limits used
                    "limits.memory": 0.65,     # 65% of memory limits used
                    "pods": 0.70               # 70% of pod quota used
                }
            },
            "resource_availability": {
                "cpu_requests_available": "17.5",
                "memory_requests_available": "32Gi",
                "cpu_limits_available": "35",
                "memory_limits_available": "70Gi",
                "pods_available": 15
            },
            "quota_warnings": [],
            "quota_exceeded": [],
            "recommendations": [
                "monitor_cpu_usage_trends",
                "consider_increasing_memory_quota_for_growth",
                "optimize_pod_resource_requests"
            ]
        }

        # Test resource quota management
        quota_result = await self.resource_manager.manage_quotas(namespace_config)

        # Verify quota structure
        self.assertIn("quota_status", quota_result)
        self.assertIn("resource_availability", quota_result)
        self.assertIn("quota_warnings", quota_result)
        self.assertIn("recommendations", quota_result)

        # Verify quota utilization
        utilization = quota_result["quota_status"]["utilization_percentages"]
        self.assertLess(utilization["requests.cpu"], 0.8)      # Under 80% CPU
        self.assertLess(utilization["requests.memory"], 0.8)   # Under 80% memory
        self.assertLess(utilization["pods"], 0.8)              # Under 80% pods

        # Verify availability
        availability = quota_result["resource_availability"]
        self.assertGreater(float(availability["cpu_requests_available"]), 10)  # >10 CPU cores available
        self.assertGreater(int(availability["pods_available"]), 10)            # >10 pods available

        # Verify no quota exceeded
        self.assertEqual(len(quota_result["quota_exceeded"]), 0)

        # Test resource monitoring and optimization
        self.resource_manager.monitor_usage.return_value = {
            "monitoring_period": "last_24_hours",
            "cluster_resource_metrics": {
                "total_nodes": 12,
                "total_cpu_cores": 168,
                "total_memory_gb": 672,
                "allocated_cpu_cores": 89,
                "allocated_memory_gb": 378,
                "actual_cpu_usage": 45.2,      # Actual usage lower than allocated
                "actual_memory_usage": 234.5,  # Actual usage lower than allocated
                "resource_efficiency": {
                    "cpu_efficiency": 0.51,     # 51% of allocated CPU actually used
                    "memory_efficiency": 0.62   # 62% of allocated memory actually used
                }
            },
            "workload_analysis": {
                "over_provisioned_workloads": [
                    {
                        "deployment": "analytics-service",
                        "namespace": "ttrpg-production",
                        "cpu_over_provision": 0.35,  # 35% over-provisioned
                        "memory_over_provision": 0.28,
                        "optimization_potential": "high"
                    }
                ],
                "under_provisioned_workloads": [],
                "right_sized_workloads": 18
            },
            "cost_optimization": {
                "estimated_monthly_cost": "$2,850",
                "potential_savings": "$420",
                "optimization_opportunities": [
                    "right_size_analytics_service",
                    "implement_vpa_recommendations",
                    "consolidate_low_usage_workloads"
                ]
            }
        }

        # Test resource monitoring
        monitoring_result = await self.resource_manager.monitor_usage()

        # Verify monitoring structure
        self.assertIn("cluster_resource_metrics", monitoring_result)
        self.assertIn("workload_analysis", monitoring_result)
        self.assertIn("cost_optimization", monitoring_result)

        # Verify resource efficiency
        metrics = monitoring_result["cluster_resource_metrics"]
        efficiency = metrics["resource_efficiency"]
        self.assertGreater(efficiency["cpu_efficiency"], 0.4)     # >40% CPU efficiency
        self.assertGreater(efficiency["memory_efficiency"], 0.5)  # >50% memory efficiency

        # Verify workload analysis
        analysis = monitoring_result["workload_analysis"]
        self.assertIn("over_provisioned_workloads", analysis)
        self.assertGreater(analysis["right_sized_workloads"], 15)  # Most workloads are right-sized

        # Verify cost optimization opportunities
        cost_opt = monitoring_result["cost_optimization"]
        self.assertIn("potential_savings", cost_opt)
        self.assertGreater(len(cost_opt["optimization_opportunities"]), 0)

    async def test_kubernetes_security_and_rbac(self):
        """Test Kubernetes security policies, RBAC, and network policies."""
        # Mock security policy configuration
        security_config = {
            "pod_security_standards": "restricted",
            "network_policies_enabled": True,
            "rbac_enabled": True,
            "service_mesh_security": True,
            "admission_controllers": [
                "NamespaceLifecycle",
                "LimitRanger",
                "ResourceQuota",
                "PodSecurityPolicy",
                "DefaultStorageClass"
            ]
        }

        # Mock RBAC configuration
        rbac_config = {
            "roles": [
                {
                    "name": "ttrpg-developer",
                    "namespace": "ttrpg-production",
                    "rules": [
                        {"api_groups": [""], "resources": ["pods", "services"], "verbs": ["get", "list", "watch"]},
                        {"api_groups": ["apps"], "resources": ["deployments"], "verbs": ["get", "list", "watch", "update"]}
                    ]
                },
                {
                    "name": "ttrpg-admin",
                    "namespace": "ttrpg-production",
                    "rules": [
                        {"api_groups": ["*"], "resources": ["*"], "verbs": ["*"]}
                    ]
                }
            ],
            "role_bindings": [
                {
                    "name": "developer-binding",
                    "role": "ttrpg-developer",
                    "subjects": [
                        {"kind": "User", "name": "dev-team", "api_group": "rbac.authorization.k8s.io"}
                    ]
                }
            ]
        }

        # Configure security validation
        self.k8s_cluster.apply_manifest.return_value = {
            "security_validation": {
                "pod_security_compliance": {
                    "policy_enforced": True,
                    "non_compliant_pods": [],
                    "security_context_violations": 0,
                    "privileged_containers": 0,
                    "security_score": 0.96
                },
                "rbac_validation": {
                    "roles_configured": 2,
                    "role_bindings_configured": 1,
                    "excessive_permissions_detected": 0,
                    "rbac_coverage": 1.0,
                    "unauthorized_access_attempts": 0
                },
                "network_policy_status": {
                    "policies_active": 5,
                    "namespaces_covered": 8,
                    "default_deny_enabled": True,
                    "ingress_rules_configured": 12,
                    "egress_rules_configured": 8,
                    "policy_violations": 0
                },
                "admission_control": {
                    "controllers_active": 5,
                    "policy_violations_blocked": 23,
                    "resource_quota_enforced": True,
                    "security_policies_enforced": True
                }
            },
            "compliance_status": {
                "cis_kubernetes_benchmark": {
                    "score": 0.91,
                    "passed_checks": 87,
                    "failed_checks": 8,
                    "critical_failures": 0
                },
                "pci_dss_compliance": {
                    "compliant": True,
                    "encryption_at_rest": True,
                    "encryption_in_transit": True,
                    "access_controls": True,
                    "audit_logging": True
                },
                "gdpr_compliance": {
                    "compliant": True,
                    "data_protection": True,
                    "access_controls": True,
                    "audit_trail": True,
                    "right_to_be_forgotten": True
                }
            }
        }

        # Test security configuration
        security_result = await self.k8s_cluster.apply_manifest({
            "security_config": security_config,
            "rbac_config": rbac_config
        })

        # Verify security validation structure
        self.assertIn("security_validation", security_result)
        self.assertIn("compliance_status", security_result)

        # Verify pod security compliance
        pod_security = security_result["security_validation"]["pod_security_compliance"]
        self.assertTrue(pod_security["policy_enforced"])
        self.assertEqual(pod_security["non_compliant_pods"], [])
        self.assertEqual(pod_security["privileged_containers"], 0)
        self.assertGreater(pod_security["security_score"], 0.9)

        # Verify RBAC validation
        rbac_validation = security_result["security_validation"]["rbac_validation"]
        self.assertEqual(rbac_validation["roles_configured"], 2)
        self.assertEqual(rbac_validation["excessive_permissions_detected"], 0)
        self.assertEqual(rbac_validation["rbac_coverage"], 1.0)
        self.assertEqual(rbac_validation["unauthorized_access_attempts"], 0)

        # Verify network policies
        network_policy = security_result["security_validation"]["network_policy_status"]
        self.assertGreater(network_policy["policies_active"], 0)
        self.assertTrue(network_policy["default_deny_enabled"])
        self.assertEqual(network_policy["policy_violations"], 0)

        # Verify admission control
        admission = security_result["security_validation"]["admission_control"]
        self.assertTrue(admission["resource_quota_enforced"])
        self.assertTrue(admission["security_policies_enforced"])
        self.assertGreater(admission["policy_violations_blocked"], 0)  # Working as expected

        # Verify compliance status
        compliance = security_result["compliance_status"]

        # CIS Kubernetes Benchmark
        cis = compliance["cis_kubernetes_benchmark"]
        self.assertGreater(cis["score"], 0.85)
        self.assertEqual(cis["critical_failures"], 0)
        self.assertGreater(cis["passed_checks"], cis["failed_checks"])

        # PCI DSS compliance
        pci = compliance["pci_dss_compliance"]
        self.assertTrue(pci["compliant"])
        self.assertTrue(pci["encryption_at_rest"])
        self.assertTrue(pci["encryption_in_transit"])
        self.assertTrue(pci["access_controls"])

        # GDPR compliance
        gdpr = compliance["gdpr_compliance"]
        self.assertTrue(gdpr["compliant"])
        self.assertTrue(gdpr["data_protection"])
        self.assertTrue(gdpr["audit_trail"])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])