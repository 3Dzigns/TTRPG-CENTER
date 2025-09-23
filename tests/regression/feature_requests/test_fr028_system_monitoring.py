"""
FR-028: Advanced System Monitoring and Observability
Test comprehensive system monitoring, metrics collection, and observability features.

This module tests the monitoring infrastructure that provides real-time system
health insights, performance metrics, alerting, and observability across all
components of the TTRPG Center platform.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR028SystemMonitoring(BaseFRTest):
    """Test suite for FR-028 Advanced System Monitoring and Observability."""

    async def asyncSetUp(self):
        """Set up test environment with monitoring infrastructure."""
        await super().asyncSetUp()
        self.metrics_collector = self._create_mock_metrics_collector()
        self.alerting_system = self._create_mock_alerting_system()
        self.dashboard_service = self._create_mock_dashboard_service()
        self.observability_engine = self._create_mock_observability_engine()

    def _create_mock_metrics_collector(self) -> Mock:
        """Create mock metrics collection system."""
        collector = Mock()
        collector.collect_system_metrics = AsyncMock()
        collector.collect_application_metrics = AsyncMock()
        collector.collect_business_metrics = AsyncMock()
        collector.aggregate_metrics = AsyncMock()
        return collector

    def _create_mock_alerting_system(self) -> Mock:
        """Create mock alerting and notification system."""
        alerting = Mock()
        alerting.evaluate_rules = AsyncMock()
        alerting.trigger_alert = AsyncMock()
        alerting.escalate_alert = AsyncMock()
        alerting.resolve_alert = AsyncMock()
        return alerting

    def _create_mock_dashboard_service(self) -> Mock:
        """Create mock dashboard and visualization service."""
        dashboard = Mock()
        dashboard.generate_dashboard = AsyncMock()
        dashboard.update_widgets = AsyncMock()
        dashboard.export_report = AsyncMock()
        dashboard.create_custom_view = AsyncMock()
        return dashboard

    def _create_mock_observability_engine(self) -> Mock:
        """Create mock observability and tracing engine."""
        engine = Mock()
        engine.trace_request = AsyncMock()
        engine.collect_logs = AsyncMock()
        engine.analyze_performance = AsyncMock()
        engine.detect_anomalies = AsyncMock()
        return engine

    async def test_comprehensive_system_metrics_collection(self):
        """Test collection of comprehensive system-level metrics."""
        # Mock system environment
        system_config = {
            "environment": "production",
            "region": "us-east-1",
            "instance_count": 3,
            "load_balancer": "enabled",
            "database_cluster": "astradb",
            "cache_layers": ["redis", "cdn"]
        }

        # Configure system metrics collection
        self.metrics_collector.collect_system_metrics.return_value = {
            "timestamp": "2024-01-01T20:00:00Z",
            "collection_interval": 60,  # seconds
            "infrastructure_metrics": {
                "cpu": {
                    "usage_percent": 45.2,
                    "load_average": {"1m": 0.8, "5m": 0.7, "15m": 0.6},
                    "cores_available": 8,
                    "processes_active": 125
                },
                "memory": {
                    "usage_percent": 67.8,
                    "total_gb": 32,
                    "available_gb": 10.3,
                    "swap_usage_percent": 12.1,
                    "cache_gb": 8.5
                },
                "disk": {
                    "usage_percent": 52.4,
                    "total_gb": 500,
                    "available_gb": 238,
                    "iops": 1200,
                    "read_throughput_mbps": 85,
                    "write_throughput_mbps": 42
                },
                "network": {
                    "inbound_mbps": 156,
                    "outbound_mbps": 89,
                    "connections_active": 450,
                    "connections_idle": 120,
                    "packet_loss_percent": 0.02
                }
            },
            "application_server_metrics": {
                "instances": [
                    {
                        "instance_id": "app-001",
                        "status": "healthy",
                        "cpu_percent": 42.1,
                        "memory_percent": 65.3,
                        "requests_per_second": 85,
                        "response_time_p95": 150,  # milliseconds
                        "error_rate": 0.008,
                        "uptime_hours": 72
                    },
                    {
                        "instance_id": "app-002",
                        "status": "healthy",
                        "cpu_percent": 48.7,
                        "memory_percent": 70.1,
                        "requests_per_second": 92,
                        "response_time_p95": 145,
                        "error_rate": 0.012,
                        "uptime_hours": 71
                    },
                    {
                        "instance_id": "app-003",
                        "status": "warning",
                        "cpu_percent": 78.9,
                        "memory_percent": 85.2,
                        "requests_per_second": 105,
                        "response_time_p95": 280,
                        "error_rate": 0.025,
                        "uptime_hours": 69
                    }
                ],
                "load_balancer": {
                    "status": "healthy",
                    "distribution_algorithm": "round_robin",
                    "health_check_interval": 30,
                    "healthy_instances": 3,
                    "total_requests": 15420,
                    "avg_response_time": 165
                }
            },
            "database_metrics": {
                "astradb_cluster": {
                    "status": "healthy",
                    "connection_pool_usage": 68,
                    "query_response_time_p95": 45,  # milliseconds
                    "queries_per_second": 156,
                    "cache_hit_rate": 0.87,
                    "storage_usage_gb": 245,
                    "replication_lag_ms": 12
                }
            },
            "cache_metrics": {
                "redis": {
                    "status": "healthy",
                    "memory_usage_percent": 45.2,
                    "hit_rate": 0.91,
                    "operations_per_second": 2400,
                    "avg_response_time": 1.2,  # milliseconds
                    "connected_clients": 45
                },
                "cdn": {
                    "status": "healthy",
                    "cache_hit_rate": 0.78,
                    "bandwidth_utilization": 0.62,
                    "edge_locations_active": 15,
                    "requests_per_second": 850
                }
            }
        }

        # Test system metrics collection
        system_metrics = await self.metrics_collector.collect_system_metrics(system_config)

        # Verify metrics structure
        self.assertIn("infrastructure_metrics", system_metrics)
        self.assertIn("application_server_metrics", system_metrics)
        self.assertIn("database_metrics", system_metrics)
        self.assertIn("cache_metrics", system_metrics)

        # Verify infrastructure metrics
        infra = system_metrics["infrastructure_metrics"]
        self.assertIn("cpu", infra)
        self.assertIn("memory", infra)
        self.assertIn("disk", infra)
        self.assertIn("network", infra)

        # Verify CPU metrics
        cpu = infra["cpu"]
        self.assertGreaterEqual(cpu["usage_percent"], 0)
        self.assertLessEqual(cpu["usage_percent"], 100)
        self.assertIn("load_average", cpu)
        self.assertIn("1m", cpu["load_average"])

        # Verify memory metrics
        memory = infra["memory"]
        self.assertGreaterEqual(memory["usage_percent"], 0)
        self.assertLessEqual(memory["usage_percent"], 100)
        self.assertGreater(memory["total_gb"], 0)

        # Verify application server health
        app_servers = system_metrics["application_server_metrics"]["instances"]
        self.assertEqual(len(app_servers), 3)

        healthy_instances = [inst for inst in app_servers if inst["status"] == "healthy"]
        warning_instances = [inst for inst in app_servers if inst["status"] == "warning"]

        self.assertEqual(len(healthy_instances), 2)
        self.assertEqual(len(warning_instances), 1)

        # Verify response time thresholds
        for instance in app_servers:
            self.assertIn("response_time_p95", instance)
            if instance["status"] == "warning":
                self.assertGreater(instance["response_time_p95"], 200)  # Higher latency for warning

        # Verify database performance
        db_metrics = system_metrics["database_metrics"]["astradb_cluster"]
        self.assertEqual(db_metrics["status"], "healthy")
        self.assertLess(db_metrics["query_response_time_p95"], 100)  # Sub-100ms queries
        self.assertGreater(db_metrics["cache_hit_rate"], 0.8)  # Good cache performance

    async def test_application_performance_monitoring(self):
        """Test application-level performance monitoring and metrics."""
        # Mock application components
        app_components = [
            "ingestion_pipeline",
            "search_service",
            "user_management",
            "content_delivery",
            "ai_processing",
            "collaboration_engine"
        ]

        # Configure application metrics collection
        self.metrics_collector.collect_application_metrics.return_value = {
            "timestamp": "2024-01-01T20:01:00Z",
            "application_metrics": {
                "ingestion_pipeline": {
                    "status": "active",
                    "jobs_in_progress": 3,
                    "jobs_queued": 12,
                    "jobs_completed_last_hour": 45,
                    "average_processing_time": 180,  # seconds
                    "success_rate": 0.96,
                    "error_types": {
                        "pdf_parsing_errors": 2,
                        "vector_embedding_failures": 1,
                        "storage_timeouts": 0
                    },
                    "resource_usage": {
                        "cpu_percent": 65.4,
                        "memory_percent": 72.1,
                        "temp_storage_gb": 8.5
                    }
                },
                "search_service": {
                    "status": "healthy",
                    "queries_per_second": 45.2,
                    "average_response_time": 85,  # milliseconds
                    "p95_response_time": 150,
                    "p99_response_time": 320,
                    "cache_hit_rate": 0.78,
                    "index_size_gb": 12.4,
                    "query_types": {
                        "vector_search": 0.65,
                        "keyword_search": 0.25,
                        "hybrid_search": 0.10
                    },
                    "error_rate": 0.005
                },
                "user_management": {
                    "status": "healthy",
                    "active_sessions": 156,
                    "login_attempts_per_minute": 8.5,
                    "authentication_success_rate": 0.94,
                    "session_duration_avg": 45,  # minutes
                    "concurrent_users": 89,
                    "user_actions_per_second": 12.3,
                    "permission_checks_per_second": 45.7
                },
                "content_delivery": {
                    "status": "healthy",
                    "requests_per_second": 125.6,
                    "bandwidth_utilization_mbps": 89.4,
                    "cache_hit_rate": 0.82,
                    "content_types_served": {
                        "pdfs": 0.45,
                        "images": 0.30,
                        "json_data": 0.20,
                        "other": 0.05
                    },
                    "cdn_performance": {
                        "edge_hit_rate": 0.76,
                        "origin_requests": 45.2,
                        "cache_invalidations": 3
                    }
                },
                "ai_processing": {
                    "status": "healthy",
                    "model_requests_per_second": 15.8,
                    "average_inference_time": 250,  # milliseconds
                    "model_accuracy_score": 0.87,
                    "gpu_utilization": 0.68,
                    "model_cache_hit_rate": 0.45,
                    "active_models": {
                        "embedding_model": {"requests": 12.3, "avg_time": 120},
                        "classification_model": {"requests": 2.1, "avg_time": 450},
                        "generation_model": {"requests": 1.4, "avg_time": 850}
                    }
                },
                "collaboration_engine": {
                    "status": "healthy",
                    "active_sessions": 23,
                    "concurrent_editors": 45,
                    "operations_per_second": 8.9,
                    "conflict_resolution_rate": 0.97,
                    "websocket_connections": 67,
                    "message_latency_p95": 15,  # milliseconds
                    "document_sync_time": 45  # milliseconds
                }
            },
            "cross_component_metrics": {
                "request_flow_latency": {
                    "user_request_to_response": 285,  # milliseconds
                    "search_to_retrieval": 125,
                    "ingestion_to_indexing": 180,
                    "ai_processing_to_results": 320
                },
                "data_consistency": {
                    "cache_coherence_score": 0.94,
                    "index_freshness_score": 0.89,
                    "replication_lag_score": 0.96
                },
                "error_correlation": {
                    "cascading_failures": 0,
                    "error_propagation_rate": 0.02,
                    "recovery_time_avg": 45  # seconds
                }
            }
        }

        # Test application metrics collection
        app_metrics = await self.metrics_collector.collect_application_metrics(app_components)

        # Verify application metrics structure
        self.assertIn("application_metrics", app_metrics)
        self.assertIn("cross_component_metrics", app_metrics)

        # Verify each component has metrics
        app_data = app_metrics["application_metrics"]
        for component in app_components:
            self.assertIn(component, app_data)
            self.assertIn("status", app_data[component])

        # Verify ingestion pipeline metrics
        ingestion = app_data["ingestion_pipeline"]
        self.assertIn("jobs_in_progress", ingestion)
        self.assertIn("success_rate", ingestion)
        self.assertGreater(ingestion["success_rate"], 0.9)  # High success rate
        self.assertIn("error_types", ingestion)

        # Verify search service performance
        search = app_data["search_service"]
        self.assertIn("average_response_time", search)
        self.assertIn("cache_hit_rate", search)
        self.assertLess(search["average_response_time"], 100)  # Fast responses
        self.assertGreater(search["cache_hit_rate"], 0.7)  # Good caching

        # Verify AI processing metrics
        ai_processing = app_data["ai_processing"]
        self.assertIn("model_requests_per_second", ai_processing)
        self.assertIn("model_accuracy_score", ai_processing)
        self.assertIn("active_models", ai_processing)
        self.assertGreater(ai_processing["model_accuracy_score"], 0.8)

        # Verify collaboration engine real-time metrics
        collaboration = app_data["collaboration_engine"]
        self.assertIn("active_sessions", collaboration)
        self.assertIn("message_latency_p95", collaboration)
        self.assertLess(collaboration["message_latency_p95"], 50)  # Low latency
        self.assertGreater(collaboration["conflict_resolution_rate"], 0.95)

        # Verify cross-component metrics
        cross_metrics = app_metrics["cross_component_metrics"]
        self.assertIn("request_flow_latency", cross_metrics)
        self.assertIn("data_consistency", cross_metrics)
        self.assertIn("error_correlation", cross_metrics)

        # Verify latency tracking
        latency = cross_metrics["request_flow_latency"]
        self.assertIn("user_request_to_response", latency)
        self.assertLess(latency["user_request_to_response"], 500)  # Sub-500ms responses

    async def test_business_metrics_and_kpi_tracking(self):
        """Test business-level metrics and KPI tracking."""
        # Mock business context
        business_context = {
            "tracking_period": "daily",
            "date": "2024-01-01",
            "feature_flags": ["advanced_search", "ai_recommendations", "real_time_collaboration"],
            "user_segments": ["free_users", "premium_users", "enterprise_users"]
        }

        # Configure business metrics collection
        self.metrics_collector.collect_business_metrics.return_value = {
            "timestamp": "2024-01-01T23:59:59Z",
            "tracking_period": "daily",
            "user_engagement_metrics": {
                "daily_active_users": 450,
                "weekly_active_users": 1200,
                "monthly_active_users": 3500,
                "new_user_registrations": 25,
                "user_retention_rates": {
                    "day_1": 0.85,
                    "day_7": 0.72,
                    "day_30": 0.58
                },
                "session_metrics": {
                    "average_session_duration": 42,  # minutes
                    "sessions_per_user": 2.3,
                    "bounce_rate": 0.18,
                    "pages_per_session": 5.6
                },
                "feature_adoption": {
                    "search_usage": 0.94,
                    "content_creation": 0.67,
                    "collaboration_features": 0.45,
                    "ai_assistance": 0.32,
                    "advanced_filters": 0.28
                }
            },
            "content_metrics": {
                "total_documents": 15420,
                "documents_added_today": 89,
                "documents_updated_today": 156,
                "search_queries_total": 5670,
                "most_searched_terms": [
                    {"term": "character creation", "count": 456},
                    {"term": "combat rules", "count": 398},
                    {"term": "spell lists", "count": 342}
                ],
                "content_quality_scores": {
                    "average_rating": 4.2,
                    "user_feedback_positive": 0.78,
                    "content_freshness_score": 0.84
                },
                "popular_content_categories": {
                    "rules_reference": 0.35,
                    "character_options": 0.28,
                    "adventures": 0.22,
                    "homebrew_content": 0.15
                }
            },
            "system_usage_metrics": {
                "api_requests_total": 125000,
                "data_transfer_gb": 89.5,
                "storage_growth_gb": 2.8,
                "processing_jobs_completed": 234,
                "ai_model_invocations": 1560,
                "collaboration_sessions": 89,
                "real_time_connections": 156
            },
            "performance_kpis": {
                "user_satisfaction_score": 0.82,
                "content_discovery_rate": 0.67,
                "search_success_rate": 0.89,
                "feature_completion_rate": 0.74,
                "support_ticket_resolution_time": 4.2,  # hours
                "system_availability": 0.999,
                "page_load_time_p95": 1.2  # seconds
            },
            "revenue_metrics": {
                "subscription_conversions": 12,
                "monthly_recurring_revenue": 2450.00,
                "churn_rate": 0.05,
                "customer_lifetime_value": 145.50,
                "premium_feature_usage": 0.68
            },
            "growth_indicators": {
                "user_growth_rate_monthly": 0.15,
                "content_growth_rate_monthly": 0.22,
                "engagement_trend": "increasing",
                "market_penetration": 0.08,
                "referral_rate": 0.23
            }
        }

        # Test business metrics collection
        business_metrics = await self.metrics_collector.collect_business_metrics(business_context)

        # Verify business metrics structure
        self.assertIn("user_engagement_metrics", business_metrics)
        self.assertIn("content_metrics", business_metrics)
        self.assertIn("system_usage_metrics", business_metrics)
        self.assertIn("performance_kpis", business_metrics)
        self.assertIn("revenue_metrics", business_metrics)
        self.assertIn("growth_indicators", business_metrics)

        # Verify user engagement quality
        engagement = business_metrics["user_engagement_metrics"]
        self.assertGreater(engagement["daily_active_users"], 0)
        self.assertGreater(engagement["user_retention_rates"]["day_1"], 0.8)  # Good day-1 retention
        self.assertLess(engagement["bounce_rate"], 0.3)  # Low bounce rate

        # Verify feature adoption tracking
        adoption = engagement["feature_adoption"]
        self.assertGreater(adoption["search_usage"], 0.9)  # Core feature high adoption
        self.assertGreater(adoption["content_creation"], 0.6)  # Good creation rate

        # Verify content health
        content = business_metrics["content_metrics"]
        self.assertGreater(content["content_quality_scores"]["average_rating"], 4.0)
        self.assertGreater(content["content_quality_scores"]["user_feedback_positive"], 0.7)
        self.assertIn("most_searched_terms", content)
        self.assertGreater(len(content["most_searched_terms"]), 0)

        # Verify performance KPIs
        kpis = business_metrics["performance_kpis"]
        self.assertGreater(kpis["user_satisfaction_score"], 0.8)
        self.assertGreater(kpis["search_success_rate"], 0.85)
        self.assertGreater(kpis["system_availability"], 0.99)
        self.assertLess(kpis["page_load_time_p95"], 2.0)  # Fast page loads

        # Verify revenue tracking
        revenue = business_metrics["revenue_metrics"]
        self.assertIn("subscription_conversions", revenue)
        self.assertIn("monthly_recurring_revenue", revenue)
        self.assertLess(revenue["churn_rate"], 0.1)  # Low churn

        # Verify growth indicators
        growth = business_metrics["growth_indicators"]
        self.assertIn("user_growth_rate_monthly", growth)
        self.assertIn("engagement_trend", growth)
        self.assertEqual(growth["engagement_trend"], "increasing")

    async def test_intelligent_alerting_and_escalation(self):
        """Test intelligent alerting system with smart escalation rules."""
        # Mock monitoring rules configuration
        alert_rules = [
            {
                "rule_id": "cpu_high",
                "name": "High CPU Usage Alert",
                "condition": "cpu_usage_percent > 80",
                "severity": "warning",
                "duration": 300,  # 5 minutes
                "escalation_chain": ["ops_team", "engineering_lead"],
                "auto_resolution": True
            },
            {
                "rule_id": "response_time_degraded",
                "name": "Response Time Degradation",
                "condition": "response_time_p95 > 500",
                "severity": "critical",
                "duration": 120,  # 2 minutes
                "escalation_chain": ["ops_team", "engineering_lead", "cto"],
                "auto_resolution": False
            },
            {
                "rule_id": "error_rate_spike",
                "name": "Error Rate Spike",
                "condition": "error_rate > 0.05",
                "severity": "high",
                "duration": 180,  # 3 minutes
                "escalation_chain": ["ops_team", "engineering_lead"],
                "auto_resolution": True
            },
            {
                "rule_id": "user_satisfaction_drop",
                "name": "User Satisfaction Drop",
                "condition": "user_satisfaction_score < 0.7",
                "severity": "medium",
                "duration": 3600,  # 1 hour
                "escalation_chain": ["product_team", "customer_success"],
                "auto_resolution": False
            }
        ]

        # Mock current system state triggering alerts
        current_metrics = {
            "cpu_usage_percent": 85.4,  # Triggers cpu_high
            "response_time_p95": 650,    # Triggers response_time_degraded
            "error_rate": 0.08,          # Triggers error_rate_spike
            "user_satisfaction_score": 0.65  # Triggers user_satisfaction_drop
        }

        # Configure alert evaluation
        self.alerting_system.evaluate_rules.return_value = {
            "evaluation_timestamp": "2024-01-01T20:05:00Z",
            "rules_evaluated": 4,
            "alerts_triggered": [
                {
                    "alert_id": "alert_001",
                    "rule_id": "cpu_high",
                    "severity": "warning",
                    "triggered_at": "2024-01-01T20:05:00Z",
                    "current_value": 85.4,
                    "threshold": 80,
                    "status": "active",
                    "duration_seconds": 300,
                    "escalation_level": 0,
                    "auto_resolution_enabled": True
                },
                {
                    "alert_id": "alert_002",
                    "rule_id": "response_time_degraded",
                    "severity": "critical",
                    "triggered_at": "2024-01-01T20:03:00Z",
                    "current_value": 650,
                    "threshold": 500,
                    "status": "escalated",
                    "duration_seconds": 120,
                    "escalation_level": 1,
                    "auto_resolution_enabled": False
                },
                {
                    "alert_id": "alert_003",
                    "rule_id": "error_rate_spike",
                    "severity": "high",
                    "triggered_at": "2024-01-01T20:02:00Z",
                    "current_value": 0.08,
                    "threshold": 0.05,
                    "status": "active",
                    "duration_seconds": 180,
                    "escalation_level": 0,
                    "auto_resolution_enabled": True
                },
                {
                    "alert_id": "alert_004",
                    "rule_id": "user_satisfaction_drop",
                    "severity": "medium",
                    "triggered_at": "2024-01-01T19:05:00Z",
                    "current_value": 0.65,
                    "threshold": 0.7,
                    "status": "acknowledged",
                    "duration_seconds": 3600,
                    "escalation_level": 0,
                    "auto_resolution_enabled": False
                }
            ],
            "suppressed_alerts": [],
            "alert_fatigue_score": 0.25
        }

        # Test alert rule evaluation
        alert_evaluation = await self.alerting_system.evaluate_rules(alert_rules, current_metrics)

        # Verify alert evaluation
        self.assertIn("alerts_triggered", alert_evaluation)
        self.assertIn("alert_fatigue_score", alert_evaluation)
        self.assertEqual(alert_evaluation["rules_evaluated"], 4)
        self.assertEqual(len(alert_evaluation["alerts_triggered"]), 4)

        # Verify alert details
        alerts = alert_evaluation["alerts_triggered"]

        # Check critical alert is escalated
        critical_alert = next(a for a in alerts if a["severity"] == "critical")
        self.assertEqual(critical_alert["status"], "escalated")
        self.assertGreater(critical_alert["escalation_level"], 0)

        # Check auto-resolution settings
        auto_resolve_alerts = [a for a in alerts if a["auto_resolution_enabled"]]
        self.assertGreater(len(auto_resolve_alerts), 0)

        # Test alert triggering and notification
        self.alerting_system.trigger_alert.return_value = {
            "notification_id": "notif_alert_001",
            "alert_id": "alert_002",
            "recipients": ["ops_team", "engineering_lead"],
            "channels": ["slack", "email", "pagerduty"],
            "message": "CRITICAL: Response time degradation detected (650ms > 500ms threshold)",
            "sent_at": "2024-01-01T20:05:00Z",
            "delivery_status": {
                "slack": "delivered",
                "email": "delivered",
                "pagerduty": "delivered"
            },
            "acknowledgment_required": True,
            "escalation_scheduled": "2024-01-01T20:10:00Z"
        }

        # Test alert notification
        notification = await self.alerting_system.trigger_alert(critical_alert)

        # Verify notification
        self.assertIn("notification_id", notification)
        self.assertIn("recipients", notification)
        self.assertIn("channels", notification)
        self.assertIn("delivery_status", notification)
        self.assertTrue(notification["acknowledgment_required"])

        # Test escalation logic
        self.alerting_system.escalate_alert.return_value = {
            "alert_id": "alert_002",
            "escalation_level": 2,
            "escalated_to": "cto",
            "escalated_at": "2024-01-01T20:10:00Z",
            "escalation_reason": "no_acknowledgment_after_5_minutes",
            "previous_recipients": ["ops_team", "engineering_lead"],
            "escalation_message": "URGENT: Critical response time issue requires immediate attention",
            "escalation_channels": ["phone", "slack", "email"]
        }

        # Test alert escalation
        escalation = await self.alerting_system.escalate_alert("alert_002", current_level=1)

        # Verify escalation
        self.assertIn("escalation_level", escalation)
        self.assertIn("escalated_to", escalation)
        self.assertIn("escalation_reason", escalation)
        self.assertEqual(escalation["escalation_level"], 2)
        self.assertIn("phone", escalation["escalation_channels"])  # Higher urgency channel

    async def test_real_time_dashboards_and_visualization(self):
        """Test real-time dashboard generation and data visualization."""
        # Mock dashboard configuration
        dashboard_config = {
            "dashboard_id": "system_overview",
            "refresh_interval": 30,  # seconds
            "user_role": "ops_admin",
            "time_range": "last_4_hours",
            "widgets": [
                {"type": "metric_card", "metric": "system_health_score"},
                {"type": "time_series", "metric": "response_time"},
                {"type": "gauge", "metric": "cpu_usage"},
                {"type": "table", "data": "active_alerts"},
                {"type": "heatmap", "data": "service_status"},
                {"type": "chart", "metric": "user_activity"}
            ]
        }

        # Configure dashboard generation
        self.dashboard_service.generate_dashboard.return_value = {
            "dashboard_id": "system_overview",
            "generated_at": "2024-01-01T20:06:00Z",
            "refresh_interval": 30,
            "widgets": [
                {
                    "widget_id": "health_score_card",
                    "type": "metric_card",
                    "title": "System Health Score",
                    "value": 0.92,
                    "status": "healthy",
                    "trend": "stable",
                    "color": "green",
                    "description": "Overall system health based on key metrics"
                },
                {
                    "widget_id": "response_time_chart",
                    "type": "time_series",
                    "title": "Response Time Trends",
                    "time_range": "last_4_hours",
                    "data_points": [
                        {"timestamp": "2024-01-01T16:00:00Z", "value": 145},
                        {"timestamp": "2024-01-01T17:00:00Z", "value": 158},
                        {"timestamp": "2024-01-01T18:00:00Z", "value": 142},
                        {"timestamp": "2024-01-01T19:00:00Z", "value": 167},
                        {"timestamp": "2024-01-01T20:00:00Z", "value": 650}  # Spike
                    ],
                    "threshold_line": 500,
                    "alert_triggered": True
                },
                {
                    "widget_id": "cpu_gauge",
                    "type": "gauge",
                    "title": "CPU Usage",
                    "current_value": 85.4,
                    "max_value": 100,
                    "warning_threshold": 70,
                    "critical_threshold": 90,
                    "status": "warning",
                    "color": "orange"
                },
                {
                    "widget_id": "alerts_table",
                    "type": "table",
                    "title": "Active Alerts",
                    "columns": ["Alert", "Severity", "Duration", "Status"],
                    "rows": [
                        ["CPU High Usage", "Warning", "5m 23s", "Active"],
                        ["Response Time Degraded", "Critical", "7m 45s", "Escalated"],
                        ["Error Rate Spike", "High", "8m 12s", "Active"]
                    ],
                    "row_count": 3
                },
                {
                    "widget_id": "service_heatmap",
                    "type": "heatmap",
                    "title": "Service Status Matrix",
                    "services": [
                        {"name": "API Gateway", "status": "healthy", "response_time": 45},
                        {"name": "Search Service", "status": "healthy", "response_time": 85},
                        {"name": "AI Processing", "status": "degraded", "response_time": 650},
                        {"name": "Database", "status": "healthy", "response_time": 25},
                        {"name": "Cache Layer", "status": "healthy", "response_time": 5}
                    ],
                    "color_scheme": "red_yellow_green"
                },
                {
                    "widget_id": "user_activity_chart",
                    "type": "chart",
                    "title": "User Activity",
                    "chart_type": "area",
                    "data": {
                        "labels": ["16:00", "17:00", "18:00", "19:00", "20:00"],
                        "datasets": [
                            {
                                "label": "Active Users",
                                "data": [120, 145, 189, 234, 156],
                                "color": "blue"
                            },
                            {
                                "label": "Requests/min",
                                "data": [850, 920, 1120, 1450, 980],
                                "color": "purple"
                            }
                        ]
                    }
                }
            ],
            "layout": {
                "grid_columns": 3,
                "responsive": True,
                "theme": "dark"
            },
            "real_time_updates": {
                "websocket_endpoint": "/ws/dashboard/system_overview",
                "update_frequency": 30,
                "last_update": "2024-01-01T20:06:00Z"
            },
            "export_options": ["png", "pdf", "json"],
            "sharing_enabled": True
        }

        # Test dashboard generation
        dashboard = await self.dashboard_service.generate_dashboard(dashboard_config)

        # Verify dashboard structure
        self.assertIn("dashboard_id", dashboard)
        self.assertIn("widgets", dashboard)
        self.assertIn("layout", dashboard)
        self.assertIn("real_time_updates", dashboard)

        # Verify widget count and types
        widgets = dashboard["widgets"]
        self.assertEqual(len(widgets), 6)

        widget_types = [w["type"] for w in widgets]
        expected_types = ["metric_card", "time_series", "gauge", "table", "heatmap", "chart"]
        for expected_type in expected_types:
            self.assertIn(expected_type, widget_types)

        # Verify metric card widget
        health_card = next(w for w in widgets if w["type"] == "metric_card")
        self.assertIn("value", health_card)
        self.assertIn("status", health_card)
        self.assertIn("trend", health_card)
        self.assertGreaterEqual(health_card["value"], 0.0)
        self.assertLessEqual(health_card["value"], 1.0)

        # Verify time series widget
        time_series = next(w for w in widgets if w["type"] == "time_series")
        self.assertIn("data_points", time_series)
        self.assertIn("threshold_line", time_series)
        self.assertGreater(len(time_series["data_points"]), 0)

        # Verify gauge widget
        gauge = next(w for w in widgets if w["type"] == "gauge")
        self.assertIn("current_value", gauge)
        self.assertIn("warning_threshold", gauge)
        self.assertIn("critical_threshold", gauge)

        # Verify table widget
        table = next(w for w in widgets if w["type"] == "table")
        self.assertIn("columns", table)
        self.assertIn("rows", table)
        self.assertIn("row_count", table)
        self.assertEqual(table["row_count"], len(table["rows"]))

        # Verify heatmap widget
        heatmap = next(w for w in widgets if w["type"] == "heatmap")
        self.assertIn("services", heatmap)
        self.assertGreater(len(heatmap["services"]), 0)

        # Verify real-time updates configuration
        real_time = dashboard["real_time_updates"]
        self.assertIn("websocket_endpoint", real_time)
        self.assertIn("update_frequency", real_time)
        self.assertEqual(real_time["update_frequency"], 30)

        # Test widget updates
        self.dashboard_service.update_widgets.return_value = {
            "updated_widgets": [
                {
                    "widget_id": "response_time_chart",
                    "new_data_point": {"timestamp": "2024-01-01T20:06:00Z", "value": 580},
                    "updated_at": "2024-01-01T20:06:00Z"
                },
                {
                    "widget_id": "cpu_gauge",
                    "new_value": 82.1,
                    "status_change": "warning_to_normal",
                    "updated_at": "2024-01-01T20:06:00Z"
                }
            ],
            "update_type": "real_time",
            "total_widgets_updated": 2
        }

        # Test real-time widget updates
        widget_updates = await self.dashboard_service.update_widgets(["response_time_chart", "cpu_gauge"])

        # Verify widget updates
        self.assertIn("updated_widgets", widget_updates)
        self.assertIn("update_type", widget_updates)
        self.assertEqual(widget_updates["total_widgets_updated"], 2)
        self.assertEqual(widget_updates["update_type"], "real_time")

    async def test_distributed_tracing_and_observability(self):
        """Test distributed tracing and request flow observability."""
        # Mock distributed request scenario
        request_trace = {
            "trace_id": "trace_abc123",
            "span_id": "span_root",
            "operation": "user_search_request",
            "start_time": "2024-01-01T20:00:00.000Z",
            "user_id": "user456",
            "request_path": "/api/v1/search",
            "request_method": "POST"
        }

        # Configure distributed tracing
        self.observability_engine.trace_request.return_value = {
            "trace_id": "trace_abc123",
            "total_duration_ms": 285,
            "status": "completed",
            "spans": [
                {
                    "span_id": "span_root",
                    "parent_span_id": None,
                    "operation": "user_search_request",
                    "service": "api_gateway",
                    "start_time": "2024-01-01T20:00:00.000Z",
                    "duration_ms": 285,
                    "status": "success",
                    "tags": {
                        "http.method": "POST",
                        "http.url": "/api/v1/search",
                        "user.id": "user456"
                    }
                },
                {
                    "span_id": "span_auth",
                    "parent_span_id": "span_root",
                    "operation": "authenticate_user",
                    "service": "auth_service",
                    "start_time": "2024-01-01T20:00:00.005Z",
                    "duration_ms": 25,
                    "status": "success",
                    "tags": {
                        "auth.method": "jwt",
                        "user.role": "premium"
                    }
                },
                {
                    "span_id": "span_search",
                    "parent_span_id": "span_root",
                    "operation": "execute_search",
                    "service": "search_service",
                    "start_time": "2024-01-01T20:00:00.030Z",
                    "duration_ms": 95,
                    "status": "success",
                    "tags": {
                        "search.query": "character optimization",
                        "search.type": "hybrid",
                        "results.count": 23
                    }
                },
                {
                    "span_id": "span_vector",
                    "parent_span_id": "span_search",
                    "operation": "vector_similarity_search",
                    "service": "vector_db",
                    "start_time": "2024-01-01T20:00:00.035Z",
                    "duration_ms": 45,
                    "status": "success",
                    "tags": {
                        "vector.dimension": 1536,
                        "similarity.threshold": 0.7,
                        "matches.found": 15
                    }
                },
                {
                    "span_id": "span_keyword",
                    "parent_span_id": "span_search",
                    "operation": "keyword_search",
                    "service": "search_service",
                    "start_time": "2024-01-01T20:00:00.040Z",
                    "duration_ms": 35,
                    "status": "success",
                    "tags": {
                        "index.name": "content_index",
                        "matches.found": 18
                    }
                },
                {
                    "span_id": "span_ai",
                    "parent_span_id": "span_root",
                    "operation": "ai_result_enhancement",
                    "service": "ai_service",
                    "start_time": "2024-01-01T20:00:00.125Z",
                    "duration_ms": 120,
                    "status": "success",
                    "tags": {
                        "model.name": "content_enhancer",
                        "model.version": "v2.1",
                        "enhancement.type": "relevance_ranking"
                    }
                },
                {
                    "span_id": "span_cache",
                    "parent_span_id": "span_root",
                    "operation": "cache_results",
                    "service": "cache_service",
                    "start_time": "2024-01-01T20:00:00.245Z",
                    "duration_ms": 15,
                    "status": "success",
                    "tags": {
                        "cache.key": "search_user456_hash789",
                        "cache.ttl": 3600
                    }
                }
            ],
            "service_map": {
                "api_gateway": {"calls": 1, "avg_duration": 285, "error_rate": 0.0},
                "auth_service": {"calls": 1, "avg_duration": 25, "error_rate": 0.0},
                "search_service": {"calls": 2, "avg_duration": 65, "error_rate": 0.0},
                "vector_db": {"calls": 1, "avg_duration": 45, "error_rate": 0.0},
                "ai_service": {"calls": 1, "avg_duration": 120, "error_rate": 0.0},
                "cache_service": {"calls": 1, "avg_duration": 15, "error_rate": 0.0}
            },
            "performance_analysis": {
                "bottleneck_service": "ai_service",
                "bottleneck_operation": "ai_result_enhancement",
                "critical_path_duration": 245,  # auth + search + ai
                "parallelizable_operations": ["vector_search", "keyword_search"],
                "optimization_opportunities": [
                    "Consider caching AI enhancement results",
                    "Optimize vector similarity threshold",
                    "Parallel execution of search types"
                ]
            },
            "error_tracking": {
                "errors_found": 0,
                "warnings": [
                    {
                        "span_id": "span_ai",
                        "message": "AI service response time approaching SLA limit",
                        "threshold": 100,
                        "actual": 120
                    }
                ]
            }
        }

        # Test request tracing
        trace_result = await self.observability_engine.trace_request(request_trace)

        # Verify trace structure
        self.assertIn("trace_id", trace_result)
        self.assertIn("total_duration_ms", trace_result)
        self.assertIn("spans", trace_result)
        self.assertIn("service_map", trace_result)
        self.assertIn("performance_analysis", trace_result)

        # Verify trace completeness
        spans = trace_result["spans"]
        self.assertGreater(len(spans), 0)
        self.assertEqual(trace_result["trace_id"], "trace_abc123")

        # Verify span hierarchy
        root_spans = [s for s in spans if s["parent_span_id"] is None]
        self.assertEqual(len(root_spans), 1)

        root_span = root_spans[0]
        self.assertEqual(root_span["operation"], "user_search_request")

        # Verify child spans
        child_spans = [s for s in spans if s["parent_span_id"] == "span_root"]
        self.assertGreater(len(child_spans), 1)

        # Verify service map
        service_map = trace_result["service_map"]
        self.assertIn("api_gateway", service_map)
        self.assertIn("search_service", service_map)
        self.assertIn("ai_service", service_map)

        for service, stats in service_map.items():
            self.assertIn("calls", stats)
            self.assertIn("avg_duration", stats)
            self.assertIn("error_rate", stats)
            self.assertGreater(stats["calls"], 0)

        # Verify performance analysis
        analysis = trace_result["performance_analysis"]
        self.assertIn("bottleneck_service", analysis)
        self.assertIn("optimization_opportunities", analysis)
        self.assertEqual(analysis["bottleneck_service"], "ai_service")
        self.assertIsInstance(analysis["optimization_opportunities"], list)

        # Test log correlation
        self.observability_engine.collect_logs.return_value = {
            "trace_id": "trace_abc123",
            "log_entries": [
                {
                    "timestamp": "2024-01-01T20:00:00.005Z",
                    "level": "INFO",
                    "service": "auth_service",
                    "span_id": "span_auth",
                    "message": "User authentication successful",
                    "fields": {"user_id": "user456", "auth_method": "jwt"}
                },
                {
                    "timestamp": "2024-01-01T20:00:00.035Z",
                    "level": "DEBUG",
                    "service": "search_service",
                    "span_id": "span_search",
                    "message": "Executing hybrid search",
                    "fields": {"query": "character optimization", "timeout": 5000}
                },
                {
                    "timestamp": "2024-01-01T20:00:00.125Z",
                    "level": "WARN",
                    "service": "ai_service",
                    "span_id": "span_ai",
                    "message": "AI processing time approaching SLA limit",
                    "fields": {"duration_ms": 120, "sla_limit_ms": 100}
                }
            ],
            "log_correlation": {
                "trace_coverage": 0.85,  # 85% of spans have associated logs
                "error_logs": 0,
                "warning_logs": 1,
                "info_logs": 2
            }
        }

        # Test log correlation
        log_correlation = await self.observability_engine.collect_logs("trace_abc123")

        # Verify log correlation
        self.assertIn("log_entries", log_correlation)
        self.assertIn("log_correlation", log_correlation)

        log_entries = log_correlation["log_entries"]
        self.assertGreater(len(log_entries), 0)

        # Verify log-span correlation
        for log_entry in log_entries:
            self.assertIn("span_id", log_entry)
            self.assertIn("service", log_entry)
            self.assertIn("timestamp", log_entry)

            # Verify span exists for log
            matching_span = next((s for s in spans if s["span_id"] == log_entry["span_id"]), None)
            self.assertIsNotNone(matching_span)
            self.assertEqual(matching_span["service"], log_entry["service"])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])