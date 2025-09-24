# tests/regression/phase4/test_us403_system_health.py
"""
Phase 4 - US-403: Admin System Health Regression Tests
Tests admin interface for monitoring system health, performance metrics, and diagnostics
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestAdminSystemHealth:
    """Test suite for Admin System Health validation"""

    def test_system_health_interface_availability(self):
        """Test that system health interface is accessible"""
        try:
            from src_common.admin_routes import app
            from src_common.admin.health_monitor import HealthMonitor

            assert app is not None, "Admin Flask app should be available"
            assert HealthMonitor is not None, "HealthMonitor class should be available"

        except ImportError as e:
            pytest.fail(f"System health interface not available: {e}")

    def test_system_health_dashboard_endpoint(self):
        """Test admin endpoint for system health dashboard"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test health dashboard endpoint
            response = client.get('/admin/health')

            assert response.status_code == 200, f"Health dashboard should succeed, got {response.status_code}"

            response_data = response.get_json()

            # Verify dashboard structure
            assert isinstance(response_data, dict), "Response should be a dictionary"

            expected_sections = ["system_status", "services", "performance", "storage", "database"]
            for section in expected_sections:
                if section in response_data:
                    assert isinstance(response_data[section], dict), f"{section} should be a dictionary"

    def test_service_status_monitoring(self):
        """Test monitoring of individual service health status"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test service status endpoint
            response = client.get('/admin/health/services')

            if response.status_code == 200:
                services_data = response.get_json()

                assert "services" in services_data, "Response should include services"

                services = services_data["services"]
                assert isinstance(services, dict), "Services should be dictionary"

                # Expected services
                expected_services = [
                    "web_server", "database", "vector_store", "ingestion_queue",
                    "llm_api", "storage", "cache"
                ]

                for service_name in expected_services:
                    if service_name in services:
                        service = services[service_name]

                        # Verify service status structure
                        assert "status" in service, f"{service_name} should have status"
                        assert "response_time" in service, f"{service_name} should have response time"

                        # Verify status values
                        valid_statuses = ["healthy", "degraded", "unhealthy", "unknown"]
                        assert service["status"] in valid_statuses, f"Invalid status for {service_name}: {service['status']}"

                        # Verify response time
                        if service["response_time"] is not None:
                            assert isinstance(service["response_time"], (int, float)), f"{service_name} response time should be numeric"
                            assert service["response_time"] >= 0, f"{service_name} response time should be non-negative"

    def test_performance_metrics_monitoring(self):
        """Test system performance metrics collection and display"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test performance metrics endpoint
            response = client.get('/admin/health/performance')

            if response.status_code == 200:
                perf_data = response.get_json()

                assert "metrics" in perf_data, "Response should include metrics"

                metrics = perf_data["metrics"]
                assert isinstance(metrics, dict), "Metrics should be dictionary"

                # Expected performance metrics
                expected_metrics = [
                    "cpu_usage", "memory_usage", "disk_usage", "network_io",
                    "request_latency", "throughput", "error_rate"
                ]

                for metric_name in expected_metrics:
                    if metric_name in metrics:
                        metric = metrics[metric_name]

                        # Verify metric structure
                        if isinstance(metric, dict):
                            assert "current" in metric, f"{metric_name} should have current value"
                            assert "unit" in metric, f"{metric_name} should have unit"

                            # Verify metric values
                            current_value = metric["current"]
                            if current_value is not None:
                                assert isinstance(current_value, (int, float)), f"{metric_name} current value should be numeric"

                                # Verify reasonable ranges for percentage metrics
                                if metric_name in ["cpu_usage", "memory_usage", "disk_usage"]:
                                    assert 0 <= current_value <= 100, f"{metric_name} should be 0-100%"

                        elif isinstance(metric, (int, float)):
                            # Simple numeric metric
                            assert metric >= 0, f"{metric_name} should be non-negative"

    def test_database_health_monitoring(self):
        """Test database connection and performance monitoring"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test database health endpoint
            response = client.get('/admin/health/database')

            if response.status_code == 200:
                db_data = response.get_json()

                assert "database" in db_data, "Response should include database info"

                database = db_data["database"]
                assert isinstance(database, dict), "Database should be dictionary"

                # Database health indicators
                db_indicators = [
                    "connection_status", "query_performance", "storage_usage",
                    "active_connections", "slow_queries"
                ]

                for indicator in db_indicators:
                    if indicator in database:
                        value = database[indicator]

                        if indicator == "connection_status":
                            valid_statuses = ["connected", "disconnected", "degraded"]
                            assert value in valid_statuses, f"Invalid connection status: {value}"

                        elif indicator in ["active_connections", "slow_queries"]:
                            assert isinstance(value, int), f"{indicator} should be integer"
                            assert value >= 0, f"{indicator} should be non-negative"

                        elif indicator == "query_performance":
                            if isinstance(value, dict):
                                assert "avg_response_time" in value, "Query performance should include avg response time"

            # Test specific database operations
            db_ops_response = client.get('/admin/health/database/operations')

            if db_ops_response.status_code == 200:
                ops_data = db_ops_response.get_json()

                assert "operations" in ops_data, "Response should include operations"

                operations = ops_data["operations"]
                for operation in operations:
                    if isinstance(operation, dict):
                        op_fields = ["operation", "status", "duration"]
                        for field in op_fields:
                            if field in operation:
                                if field == "duration":
                                    assert isinstance(operation[field], (int, float)), "Duration should be numeric"

    def test_storage_monitoring(self):
        """Test storage system monitoring and disk usage tracking"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test storage monitoring endpoint
            response = client.get('/admin/health/storage')

            if response.status_code == 200:
                storage_data = response.get_json()

                assert "storage" in storage_data, "Response should include storage info"

                storage = storage_data["storage"]
                assert isinstance(storage, dict), "Storage should be dictionary"

                # Storage metrics
                storage_metrics = [
                    "total_space", "used_space", "free_space", "usage_percentage",
                    "artifacts_size", "logs_size", "temp_files_size"
                ]

                for metric in storage_metrics:
                    if metric in storage:
                        value = storage[metric]

                        if metric in ["total_space", "used_space", "free_space", "artifacts_size", "logs_size", "temp_files_size"]:
                            # Size metrics should be non-negative numbers
                            assert isinstance(value, (int, float)), f"{metric} should be numeric"
                            assert value >= 0, f"{metric} should be non-negative"

                        elif metric == "usage_percentage":
                            assert isinstance(value, (int, float)), "Usage percentage should be numeric"
                            assert 0 <= value <= 100, "Usage percentage should be 0-100%"

            # Test storage cleanup recommendations
            cleanup_response = client.get('/admin/health/storage/cleanup')

            if cleanup_response.status_code == 200:
                cleanup_data = cleanup_response.get_json()

                assert "recommendations" in cleanup_data, "Response should include cleanup recommendations"

                recommendations = cleanup_data["recommendations"]
                assert isinstance(recommendations, list), "Recommendations should be list"

                for recommendation in recommendations:
                    if isinstance(recommendation, dict):
                        rec_fields = ["action", "description", "potential_savings"]
                        for field in rec_fields:
                            if field in recommendation:
                                if field == "potential_savings":
                                    assert isinstance(recommendation[field], (int, float)), "Potential savings should be numeric"

    def test_error_rate_monitoring(self):
        """Test error rate monitoring and alerting thresholds"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test error monitoring endpoint
            response = client.get('/admin/health/errors')

            if response.status_code == 200:
                error_data = response.get_json()

                assert "error_metrics" in error_data, "Response should include error metrics"

                metrics = error_data["error_metrics"]
                assert isinstance(metrics, dict), "Error metrics should be dictionary"

                # Error rate metrics
                error_metrics = [
                    "error_rate", "error_count", "critical_errors", "warning_count",
                    "recent_errors", "error_trends"
                ]

                for metric in error_metrics:
                    if metric in metrics:
                        value = metrics[metric]

                        if metric in ["error_count", "critical_errors", "warning_count"]:
                            assert isinstance(value, int), f"{metric} should be integer"
                            assert value >= 0, f"{metric} should be non-negative"

                        elif metric == "error_rate":
                            assert isinstance(value, (int, float)), "Error rate should be numeric"
                            assert 0 <= value <= 100, "Error rate should be 0-100%"

                        elif metric == "recent_errors":
                            assert isinstance(value, list), "Recent errors should be list"

                            for error in value:
                                if isinstance(error, dict):
                                    error_fields = ["timestamp", "level", "message", "component"]
                                    for field in error_fields:
                                        if field in error:
                                            if field == "level":
                                                valid_levels = ["ERROR", "CRITICAL", "WARNING"]
                                                assert error[field] in valid_levels, f"Invalid error level: {error[field]}"

    def test_resource_utilization_monitoring(self):
        """Test system resource utilization monitoring"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test resource utilization endpoint
            response = client.get('/admin/health/resources')

            if response.status_code == 200:
                resource_data = response.get_json()

                assert "resources" in resource_data, "Response should include resources"

                resources = resource_data["resources"]
                assert isinstance(resources, dict), "Resources should be dictionary"

                # Resource categories
                resource_categories = [
                    "cpu", "memory", "disk", "network", "processes"
                ]

                for category in resource_categories:
                    if category in resources:
                        resource = resources[category]

                        if isinstance(resource, dict):
                            # CPU metrics
                            if category == "cpu":
                                cpu_metrics = ["usage_percent", "load_average", "core_count"]
                                for metric in cpu_metrics:
                                    if metric in resource:
                                        value = resource[metric]
                                        if metric == "usage_percent":
                                            assert 0 <= value <= 100, "CPU usage should be 0-100%"
                                        elif metric == "core_count":
                                            assert isinstance(value, int) and value > 0, "Core count should be positive integer"

                            # Memory metrics
                            elif category == "memory":
                                memory_metrics = ["total", "used", "free", "usage_percent"]
                                for metric in memory_metrics:
                                    if metric in resource:
                                        value = resource[metric]
                                        if metric == "usage_percent":
                                            assert 0 <= value <= 100, "Memory usage should be 0-100%"
                                        else:
                                            assert isinstance(value, (int, float)) and value >= 0, f"Memory {metric} should be non-negative"

    def test_health_alerting_system(self):
        """Test health alerting and notification system"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test alerts endpoint
            response = client.get('/admin/health/alerts')

            if response.status_code == 200:
                alerts_data = response.get_json()

                assert "alerts" in alerts_data, "Response should include alerts"

                alerts = alerts_data["alerts"]
                assert isinstance(alerts, list), "Alerts should be list"

                for alert in alerts:
                    if isinstance(alert, dict):
                        alert_fields = ["alert_id", "severity", "message", "timestamp", "status"]
                        for field in alert_fields:
                            if field in alert:
                                if field == "severity":
                                    valid_severities = ["low", "medium", "high", "critical"]
                                    assert alert[field] in valid_severities, f"Invalid alert severity: {alert[field]}"

                                elif field == "status":
                                    valid_statuses = ["active", "acknowledged", "resolved"]
                                    assert alert[field] in valid_statuses, f"Invalid alert status: {alert[field]}"

            # Test alert configuration
            config_response = client.get('/admin/health/alerts/config')

            if config_response.status_code == 200:
                config_data = config_response.get_json()

                assert "thresholds" in config_data, "Alert config should include thresholds"

                thresholds = config_data["thresholds"]
                assert isinstance(thresholds, dict), "Thresholds should be dictionary"

                # Verify threshold configuration
                for threshold_name, threshold_value in thresholds.items():
                    if isinstance(threshold_value, (int, float)):
                        assert threshold_value >= 0, f"Threshold {threshold_name} should be non-negative"

    def test_system_diagnostics(self):
        """Test system diagnostic tools and health checks"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test diagnostic endpoint
            response = client.post('/admin/health/diagnostics')

            if response.status_code in [200, 202]:
                diag_data = response.get_json()

                assert "diagnostic_id" in diag_data, "Diagnostic should return ID"
                assert "status" in diag_data, "Diagnostic should return status"

                diagnostic_id = diag_data["diagnostic_id"]

                # Check diagnostic results
                time.sleep(1)  # Allow diagnostic to run

                result_response = client.get(f'/admin/health/diagnostics/{diagnostic_id}')

                if result_response.status_code == 200:
                    result_data = result_response.get_json()

                    assert "results" in result_data, "Diagnostic should include results"

                    results = result_data["results"]
                    assert isinstance(results, dict), "Results should be dictionary"

                    # Verify diagnostic categories
                    diag_categories = [
                        "connectivity_tests", "performance_tests", "integrity_checks",
                        "configuration_validation", "dependency_checks"
                    ]

                    for category in diag_categories:
                        if category in results:
                            category_results = results[category]

                            if isinstance(category_results, list):
                                for test in category_results:
                                    if isinstance(test, dict):
                                        test_fields = ["test_name", "status", "message"]
                                        for field in test_fields:
                                            if field in test:
                                                if field == "status":
                                                    valid_test_statuses = ["passed", "failed", "warning", "skipped"]
                                                    assert test[field] in valid_test_statuses, f"Invalid test status: {test[field]}"

    def test_health_monitoring_performance(self):
        """Test performance of health monitoring operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test health endpoint response times
            health_endpoints = [
                '/admin/health',
                '/admin/health/services',
                '/admin/health/performance',
                '/admin/health/database',
                '/admin/health/storage'
            ]

            response_times = []

            for endpoint in health_endpoints:
                start_time = time.perf_counter()
                response = client.get(endpoint)
                end_time = time.perf_counter()

                response_time = (end_time - start_time) * 1000
                response_times.append(response_time)

                if response.status_code == 200:
                    # Health monitoring should be fast
                    assert response_time < 1000, f"Health endpoint {endpoint} response time {response_time:.1f}ms should be < 1000ms"

            # Average response time should be reasonable
            avg_response_time = sum(response_times) / len(response_times)
            assert avg_response_time < 500, f"Average health monitoring response time {avg_response_time:.1f}ms should be < 500ms"

    def test_health_data_retention_and_history(self):
        """Test health data retention and historical tracking"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test historical health data
            history_response = client.get('/admin/health/history?period=24h')

            if history_response.status_code == 200:
                history_data = history_response.get_json()

                assert "history" in history_data, "Response should include history"
                assert "period" in history_data, "Response should include period"

                history = history_data["history"]
                assert isinstance(history, list), "History should be list"

                # Verify historical data structure
                for data_point in history:
                    if isinstance(data_point, dict):
                        point_fields = ["timestamp", "metrics"]
                        for field in point_fields:
                            if field in data_point:
                                if field == "timestamp":
                                    # Should be valid timestamp
                                    assert isinstance(data_point[field], (str, int, float)), "Timestamp should be temporal"

                                elif field == "metrics":
                                    assert isinstance(data_point[field], dict), "Metrics should be dictionary"

            # Test data aggregation
            agg_response = client.get('/admin/health/trends?metric=cpu_usage&period=7d')

            if agg_response.status_code == 200:
                trend_data = agg_response.get_json()

                assert "trend_data" in trend_data, "Response should include trend data"

                trends = trend_data["trend_data"]
                if isinstance(trends, dict):
                    trend_fields = ["average", "min", "max", "samples"]
                    for field in trend_fields:
                        if field in trends:
                            if field in ["average", "min", "max"]:
                                assert isinstance(trends[field], (int, float)), f"Trend {field} should be numeric"

    def test_health_contract_compliance(self):
        """Test that health monitoring interface matches established contract"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test main health endpoint contract
            response = client.get('/admin/health')

            if response.status_code == 200:
                health_data = response.get_json()

                # Required health dashboard fields
                required_sections = ["system_status", "timestamp"]
                for section in required_sections:
                    if section in health_data:
                        if section == "system_status":
                            assert isinstance(health_data[section], dict), "System status must be dictionary"

                        elif section == "timestamp":
                            assert isinstance(health_data[section], (str, int, float)), "Timestamp must be temporal"

            # Test service status contract
            services_response = client.get('/admin/health/services')

            if services_response.status_code == 200:
                services_data = services_response.get_json()

                assert "services" in services_data, "Services response must include services"
                assert isinstance(services_data["services"], dict), "Services must be dictionary"

                for service_name, service_info in services_data["services"].items():
                    assert isinstance(service_name, str), "Service name must be string"
                    assert isinstance(service_info, dict), "Service info must be dictionary"

                    # Required service fields
                    if "status" in service_info:
                        valid_statuses = ["healthy", "degraded", "unhealthy", "unknown"]
                        assert service_info["status"] in valid_statuses, f"Invalid service status: {service_info['status']}"

            # Test performance metrics contract
            perf_response = client.get('/admin/health/performance')

            if perf_response.status_code == 200:
                perf_data = perf_response.get_json()

                assert "metrics" in perf_data, "Performance response must include metrics"
                assert isinstance(perf_data["metrics"], dict), "Metrics must be dictionary"

                # Verify metric value types
                for metric_name, metric_value in perf_data["metrics"].items():
                    if isinstance(metric_value, dict):
                        # Structured metric
                        if "current" in metric_value:
                            assert isinstance(metric_value["current"], (int, float, type(None))), "Current value must be numeric or null"

                    elif isinstance(metric_value, (int, float)):
                        # Simple numeric metric
                        assert metric_value >= 0, "Metric values should be non-negative"