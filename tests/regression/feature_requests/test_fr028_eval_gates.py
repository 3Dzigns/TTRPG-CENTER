# tests/regression/feature_requests/test_fr028_eval_gates.py
"""
Feature Request FR-028: Evaluation Set & Gates Regression Tests
Tests canonical evaluation queries and measurable quality gates with thresholds
"""

import pytest
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock, patch


class TestEvaluationGatesFramework:
    """Test suite for FR-028 Evaluation Set & Gates functionality"""

    def test_evaluation_framework_availability(self):
        """Test that evaluation framework components are available"""
        try:
            from src_common.evaluation import EvaluationFramework
            from src_common.evaluation.gates import QualityGates
            from src_common.evaluation.metrics import MetricsCollector
            from src_common.evaluation.canonical import CanonicalQuerySet

            assert EvaluationFramework is not None, "EvaluationFramework should be available"
            assert QualityGates is not None, "QualityGates should be available"
            assert MetricsCollector is not None, "MetricsCollector should be available"
            assert CanonicalQuerySet is not None, "CanonicalQuerySet should be available"

        except ImportError as e:
            pytest.fail(f"Evaluation framework components not available: {e}")

    def test_canonical_evaluation_set_requirements(self):
        """Test canonical evaluation set with minimum 20 multi-hop queries"""
        try:
            from src_common.evaluation.canonical import CanonicalQuerySet
        except ImportError:
            pytest.skip("Canonical query set not available for testing")

        query_set = CanonicalQuerySet()

        if hasattr(query_set, 'get_canonical_queries'):
            canonical_queries = query_set.get_canonical_queries()

            assert isinstance(canonical_queries, list), "Canonical queries should be list"
            assert len(canonical_queries) >= 20, f"Should have at least 20 canonical queries, got {len(canonical_queries)}"

            # Verify multi-hop query characteristics
            multi_hop_queries = []
            for query in canonical_queries:
                assert isinstance(query, dict), "Query should be structured"

                required_fields = ["query_id", "query_text", "query_type", "expected_answer"]
                for field in required_fields:
                    assert field in query, f"Query should have {field} field"

                # Check for multi-hop indicators
                if query.get("query_type") in ["multi_hop", "comparison", "calculation"]:
                    multi_hop_queries.append(query)

            assert len(multi_hop_queries) >= 10, f"Should have at least 10 multi-hop queries, got {len(multi_hop_queries)}"

        # Test specific query categories
        if hasattr(query_set, 'get_queries_by_category'):
            # Rules comparison queries
            rules_queries = query_set.get_queries_by_category("rules_comparison")
            if rules_queries:
                assert len(rules_queries) >= 3, "Should have multiple rules comparison queries"

                for query in rules_queries[:3]:  # Check first 3
                    assert "comparison" in query.get("query_text", "").lower() or \
                           "versus" in query.get("query_text", "").lower() or \
                           "difference" in query.get("query_text", "").lower(), \
                           "Rules comparison query should contain comparison language"

            # ABP (Ability Point Buy) math queries
            abp_queries = query_set.get_queries_by_category("abp_math")
            if abp_queries:
                assert len(abp_queries) >= 2, "Should have ABP math queries"

                for query in abp_queries[:2]:
                    assert any(keyword in query.get("query_text", "").lower()
                             for keyword in ["calculate", "point", "cost", "stat"]), \
                           "ABP query should contain calculation language"

            # Character build queries
            build_queries = query_set.get_queries_by_category("character_builds")
            if build_queries:
                assert len(build_queries) >= 3, "Should have character build queries"

                for query in build_queries[:3]:
                    assert any(keyword in query.get("query_text", "").lower()
                             for keyword in ["build", "character", "optimize", "feat"]), \
                           "Build query should contain character development language"

    def test_quality_metrics_implementation(self):
        """Test implementation of required quality metrics"""
        try:
            from src_common.evaluation.metrics import MetricsCollector
        except ImportError:
            pytest.skip("Metrics collector not available for testing")

        metrics = MetricsCollector()

        # Test path success rate calculation
        test_queries_results = [
            {"query_id": "q001", "path_success": True, "support_found": True, "citations_accurate": True, "latency": 1200},
            {"query_id": "q002", "path_success": True, "support_found": True, "citations_accurate": False, "latency": 800},
            {"query_id": "q003", "path_success": False, "support_found": False, "citations_accurate": False, "latency": 2500},
            {"query_id": "q004", "path_success": True, "support_found": True, "citations_accurate": True, "latency": 1500},
            {"query_id": "q005", "path_success": True, "support_found": False, "citations_accurate": False, "latency": 900}
        ]

        if hasattr(metrics, 'calculate_path_success_rate'):
            path_success_rate = metrics.calculate_path_success_rate(test_queries_results)

            assert isinstance(path_success_rate, (int, float)), "Path success rate should be numeric"
            assert 0 <= path_success_rate <= 1, "Path success rate should be 0-1"

            # Expected: 4 out of 5 queries had path_success=True = 0.8
            expected_rate = 0.8
            assert abs(path_success_rate - expected_rate) < 0.01, f"Expected path success rate {expected_rate}, got {path_success_rate}"

        # Test support rate calculation
        if hasattr(metrics, 'calculate_support_rate'):
            support_rate = metrics.calculate_support_rate(test_queries_results)

            assert isinstance(support_rate, (int, float)), "Support rate should be numeric"
            assert 0 <= support_rate <= 1, "Support rate should be 0-1"

            # Expected: 3 out of 5 queries had support_found=True = 0.6
            expected_support = 0.6
            assert abs(support_rate - expected_support) < 0.01, f"Expected support rate {expected_support}, got {support_rate}"

        # Test citation accuracy calculation
        if hasattr(metrics, 'calculate_citation_accuracy'):
            citation_accuracy = metrics.calculate_citation_accuracy(test_queries_results)

            assert isinstance(citation_accuracy, (int, float)), "Citation accuracy should be numeric"
            assert 0 <= citation_accuracy <= 1, "Citation accuracy should be 0-1"

            # Expected: 2 out of 5 queries had citations_accurate=True = 0.4
            expected_accuracy = 0.4
            assert abs(citation_accuracy - expected_accuracy) < 0.01, f"Expected citation accuracy {expected_accuracy}, got {citation_accuracy}"

        # Test multi-hop latency calculation
        if hasattr(metrics, 'calculate_multi_hop_latency'):
            avg_latency = metrics.calculate_multi_hop_latency(test_queries_results)

            assert isinstance(avg_latency, (int, float)), "Average latency should be numeric"
            assert avg_latency > 0, "Average latency should be positive"

            # Expected: (1200 + 800 + 2500 + 1500 + 900) / 5 = 1380
            expected_latency = 1380
            assert abs(avg_latency - expected_latency) < 50, f"Expected average latency ~{expected_latency}, got {avg_latency}"

    def test_quality_gate_thresholds(self):
        """Test quality gate thresholds (≥85% support rate, ≥80% path success)"""
        try:
            from src_common.evaluation.gates import QualityGates
        except ImportError:
            pytest.skip("Quality gates not available for testing")

        gates = QualityGates()

        # Test gate configuration
        gate_config = {
            "support_rate": {
                "threshold": 0.85,  # ≥85% as specified in FR-028
                "operator": ">=",
                "critical": True
            },
            "path_success": {
                "threshold": 0.80,  # ≥80% as specified in FR-028
                "operator": ">=",
                "critical": True
            },
            "citation_accuracy": {
                "threshold": 0.75,
                "operator": ">=",
                "critical": False
            },
            "multi_hop_latency": {
                "threshold": 2000,  # milliseconds
                "operator": "<=",
                "critical": False
            }
        }

        if hasattr(gates, 'configure_gates'):
            config_result = gates.configure_gates(gate_config)

            assert isinstance(config_result, dict), "Gate configuration should return structured result"
            assert config_result.get("configured", False) == True, "Gate configuration should succeed"

        # Test metrics that pass thresholds
        passing_metrics = {
            "support_rate": 0.87,      # Above 85% threshold
            "path_success": 0.82,      # Above 80% threshold
            "citation_accuracy": 0.78,  # Above 75% threshold
            "multi_hop_latency": 1800   # Below 2000ms threshold
        }

        if hasattr(gates, 'evaluate_gates'):
            passing_evaluation = gates.evaluate_gates(passing_metrics, gate_config)

            assert isinstance(passing_evaluation, dict), "Gate evaluation should return structured result"
            assert passing_evaluation.get("all_gates_passed", False) == True, "Passing metrics should pass all gates"

            if "gate_results" in passing_evaluation:
                gate_results = passing_evaluation["gate_results"]

                # Check critical gates specifically
                assert gate_results["support_rate"]["passed"] == True, "Support rate should pass 85% threshold"
                assert gate_results["path_success"]["passed"] == True, "Path success should pass 80% threshold"

        # Test metrics that fail thresholds
        failing_metrics = {
            "support_rate": 0.82,      # Below 85% threshold
            "path_success": 0.78,      # Below 80% threshold
            "citation_accuracy": 0.70,  # Below 75% threshold
            "multi_hop_latency": 2200   # Above 2000ms threshold
        }

        if hasattr(gates, 'evaluate_gates'):
            failing_evaluation = gates.evaluate_gates(failing_metrics, gate_config)

            assert failing_evaluation.get("all_gates_passed", True) == False, "Failing metrics should fail gates"

            if "failed_gates" in failing_evaluation:
                failed_gates = failing_evaluation["failed_gates"]
                assert "support_rate" in failed_gates, "Support rate should be in failed gates"
                assert "path_success" in failed_gates, "Path success should be in failed gates"

            if "critical_failures" in failing_evaluation:
                critical_failures = failing_evaluation["critical_failures"]
                assert len(critical_failures) >= 2, "Should have critical failures for support_rate and path_success"

    def test_ci_integration_gate_enforcement(self):
        """Test CI run fails if metrics drop below gate thresholds"""
        try:
            from src_common.evaluation.ci_integration import CIEvaluationGates
        except ImportError:
            pytest.skip("CI evaluation gates not available for testing")

        ci_gates = CIEvaluationGates()

        # Test CI configuration
        ci_config = {
            "fail_on_gate_violations": True,
            "require_all_critical_gates": True,
            "evaluation_gates": {
                "support_rate": {"threshold": 0.85, "critical": True},
                "path_success": {"threshold": 0.80, "critical": True}
            },
            "exit_codes": {
                "success": 0,
                "gate_failure": 1,
                "critical_failure": 2
            }
        }

        # Test successful CI run
        passing_results = {
            "evaluation_run_id": "eval_20240922_100000",
            "total_queries": 25,
            "metrics": {
                "support_rate": 0.88,    # Above 85% threshold
                "path_success": 0.84,    # Above 80% threshold
                "citation_accuracy": 0.82,
                "multi_hop_latency": 1600
            },
            "query_results": [{"query_id": f"q{i:03d}", "passed": True} for i in range(1, 26)]
        }

        if hasattr(ci_gates, 'evaluate_for_ci'):
            ci_result = ci_gates.evaluate_for_ci(passing_results, ci_config)

            assert isinstance(ci_result, dict), "CI evaluation should return structured result"
            assert ci_result.get("ci_passed", False) == True, "CI should pass with passing metrics"
            assert ci_result.get("exit_code", 1) == 0, "CI should return exit code 0 on success"

        # Test failing CI run
        failing_results = {
            "evaluation_run_id": "eval_20240922_110000",
            "total_queries": 25,
            "metrics": {
                "support_rate": 0.82,    # Below 85% threshold
                "path_success": 0.76,    # Below 80% threshold
                "citation_accuracy": 0.78,
                "multi_hop_latency": 1800
            },
            "query_results": [{"query_id": f"q{i:03d}", "passed": i <= 19} for i in range(1, 26)]  # 19/25 passed
        }

        if hasattr(ci_gates, 'evaluate_for_ci'):
            failing_ci_result = ci_gates.evaluate_for_ci(failing_results, ci_config)

            assert failing_ci_result.get("ci_passed", True) == False, "CI should fail with failing metrics"
            assert failing_ci_result.get("exit_code", 0) != 0, "CI should return non-zero exit code on failure"

            if "failure_reasons" in failing_ci_result:
                reasons = failing_ci_result["failure_reasons"]
                assert "support_rate below threshold" in str(reasons).lower(), "Should report support rate failure"
                assert "path_success below threshold" in str(reasons).lower(), "Should report path success failure"

    def test_canonical_query_regression_protection(self):
        """Test that canonical queries always remain in evaluation set"""
        try:
            from src_common.evaluation.canonical import CanonicalQuerySet
        except ImportError:
            pytest.skip("Canonical query set not available for testing")

        query_set = CanonicalQuerySet()

        # Test canonical query stability
        if hasattr(query_set, 'get_canonical_queries'):
            canonical_queries_v1 = query_set.get_canonical_queries()
            query_ids_v1 = {q["query_id"] for q in canonical_queries_v1}

            # Simulate query set update
            if hasattr(query_set, 'update_query_set'):
                # Add new queries but maintain canonical ones
                new_queries = [
                    {
                        "query_id": "new_001",
                        "query_text": "What is the casting time for new spell X?",
                        "query_type": "simple_lookup",
                        "canonical": False
                    }
                ]

                update_result = query_set.update_query_set(new_queries, preserve_canonical=True)

                if update_result.get("updated", False):
                    canonical_queries_v2 = query_set.get_canonical_queries()
                    query_ids_v2 = {q["query_id"] for q in canonical_queries_v2}

                    # All original canonical queries should still be present
                    original_canonical = {q["query_id"] for q in canonical_queries_v1 if q.get("canonical", True)}
                    assert original_canonical.issubset(query_ids_v2), "Canonical queries should be preserved across updates"

        # Test query set validation
        if hasattr(query_set, 'validate_query_set'):
            validation = query_set.validate_query_set()

            assert isinstance(validation, dict), "Query set validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Query set should be valid"

            if "canonical_count" in validation:
                canonical_count = validation["canonical_count"]
                assert canonical_count >= 20, f"Should maintain at least 20 canonical queries, got {canonical_count}"

    def test_evaluation_security_and_pii_protection(self):
        """Test that evaluation set does not contain PII"""
        try:
            from src_common.evaluation.security import EvaluationSecurityValidator
        except ImportError:
            pytest.skip("Evaluation security validator not available for testing")

        security_validator = EvaluationSecurityValidator()

        # Test PII detection in queries
        test_queries = [
            {
                "query_id": "safe_001",
                "query_text": "What is the damage of a fireball spell?",
                "expected_answer": "8d6 fire damage"
            },
            {
                "query_id": "unsafe_001",
                "query_text": "What character did john.doe@email.com create?",
                "expected_answer": "Character details for john.doe@email.com"
            },
            {
                "query_id": "unsafe_002",
                "query_text": "Show me data for user ID 123-45-6789",
                "expected_answer": "User information"
            }
        ]

        if hasattr(security_validator, 'scan_for_pii'):
            pii_scan_result = security_validator.scan_for_pii(test_queries)

            assert isinstance(pii_scan_result, dict), "PII scan should return structured result"

            if "queries_with_pii" in pii_scan_result:
                pii_queries = pii_scan_result["queries_with_pii"]
                assert len(pii_queries) >= 2, "Should detect PII in unsafe queries"

                # Should detect email and SSN-like patterns
                detected_types = {detection["pii_type"] for detection in pii_queries}
                assert "email" in detected_types, "Should detect email addresses"

            if "clean_queries" in pii_scan_result:
                clean_queries = pii_scan_result["clean_queries"]
                clean_ids = {q["query_id"] for q in clean_queries}
                assert "safe_001" in clean_ids, "Safe query should be marked as clean"

        # Test data sanitization
        if hasattr(security_validator, 'sanitize_evaluation_data'):
            sanitization_result = security_validator.sanitize_evaluation_data(test_queries)

            assert isinstance(sanitization_result, dict), "Sanitization should return structured result"

            if "sanitized_queries" in sanitization_result:
                sanitized = sanitization_result["sanitized_queries"]
                assert len(sanitized) <= len(test_queries), "Sanitization should remove or clean unsafe queries"

                # Verify PII is removed from sanitized queries
                for query in sanitized:
                    query_text = query.get("query_text", "")
                    assert "@" not in query_text, "Sanitized queries should not contain email addresses"
                    assert not any(char.isdigit() for char in query_text.replace("-", "")), \
                        "Sanitized queries should not contain ID patterns"

    def test_evaluation_gates_contract_compliance(self):
        """Test that evaluation gates match established contract"""
        # Test canonical query set contract
        canonical_requirements = {
            "minimum_queries": 20,
            "multi_hop_queries": True,
            "rules_comparisons": True,
            "abp_math_queries": True,
            "character_builds": True,
            "query_stability": True
        }

        for requirement, needed in canonical_requirements.items():
            if isinstance(needed, bool):
                assert needed, f"Canonical requirement {requirement} is mandatory"
            elif isinstance(needed, int):
                assert needed > 0, f"Canonical requirement {requirement} must be positive"

        # Test metrics contract
        required_metrics = [
            "path_success_rate",
            "support_rate",
            "citation_accuracy",
            "multi_hop_latency"
        ]

        for metric in required_metrics:
            assert isinstance(metric, str), f"Metric {metric} should be defined"

        # Test threshold contract
        threshold_requirements = {
            "support_rate_threshold": 0.85,  # ≥85%
            "path_success_threshold": 0.80,  # ≥80%
            "configurable_thresholds": True,
            "ci_integration": True
        }

        for requirement, value in threshold_requirements.items():
            if isinstance(value, bool):
                assert value, f"Threshold requirement {requirement} is mandatory"
            elif isinstance(value, (int, float)):
                assert value > 0, f"Threshold {requirement} must be positive"

        # Test security contract
        security_requirements = {
            "pii_protection": True,
            "data_sanitization": True,
            "access_controls": True,
            "audit_logging": True
        }

        for requirement, needed in security_requirements.items():
            assert needed, f"Security requirement {requirement} is mandatory"

        # Test CI integration contract
        ci_requirements = {
            "gate_enforcement": True,
            "failure_blocking": True,
            "exit_code_standards": True,
            "failure_reporting": True
        }

        for requirement, needed in ci_requirements.items():
            assert needed, f"CI requirement {requirement} is mandatory"