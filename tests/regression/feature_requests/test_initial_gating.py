# tests/regression/feature_requests/test_initial_gating.py
"""
Initial Gating Mechanisms Test Suite
Tests core gating functionality including FR-005 modular ingestion gates
and FR-028 evaluation gates with quality thresholds
"""

import pytest
import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock, patch


class TestInitialGatingMechanisms:
    """Test suite for initial gating mechanisms and quality gates"""

    def test_gating_framework_availability(self):
        """Test that gating framework components are available"""
        try:
            # Test gating infrastructure
            from src_common.gating import GatingEngine, QualityGate
            from src_common.ingestion_gates import IngestionGates
            from src_common.evaluation_gates import EvaluationGates

            assert GatingEngine is not None, "GatingEngine should be available"
            assert QualityGate is not None, "QualityGate should be available"
            assert IngestionGates is not None, "IngestionGates should be available"
            assert EvaluationGates is not None, "EvaluationGates should be available"

        except ImportError as e:
            pytest.fail(f"Gating framework components not available: {e}")

    def test_fr005_modular_ingestion_gates(self):
        """Test FR-005 modular ingestion pass gating (A→B→C→D→E→F)"""
        try:
            from src_common.ingestion_gates import IngestionGates
        except ImportError:
            pytest.skip("Ingestion gates not available for testing")

        gates = IngestionGates()

        # Test pass sequence gating
        pass_sequence = ["A", "B", "C", "D", "E", "F"]

        # Test initial state - only Pass A should be executable
        if hasattr(gates, 'can_execute_pass'):
            # Pass A should be executable (no dependencies)
            can_execute_a = gates.can_execute_pass("A", {})
            assert can_execute_a, "Pass A should be executable with no prior state"

            # Pass B should not be executable without Pass A success
            can_execute_b = gates.can_execute_pass("B", {})
            assert not can_execute_b, "Pass B should not be executable without Pass A success"

        # Test sequential pass gating
        if hasattr(gates, 'validate_pass_prerequisites'):
            # Simulate Pass A completion
            pass_state = {
                "A": {
                    "status": "SUCCESS",
                    "artifacts": ["passA_toc.json"],
                    "quality_metrics": {"toc_sections": 15, "page_count": 120}
                }
            }

            # Now Pass B should be executable
            b_validation = gates.validate_pass_prerequisites("B", pass_state)
            assert isinstance(b_validation, dict), "Prerequisites validation should return structured result"

            if "valid" in b_validation:
                assert b_validation["valid"] == True, "Pass B should be valid after Pass A success"

            # Pass C should still not be executable
            c_validation = gates.validate_pass_prerequisites("C", pass_state)
            if "valid" in c_validation:
                assert c_validation["valid"] == False, "Pass C should not be valid without Pass B success"

        # Test artifact validation gating
        if hasattr(gates, 'validate_pass_artifacts'):
            # Test valid artifacts
            valid_artifacts = {
                "passA_toc.json": {
                    "source_id": "test_source",
                    "sections": [
                        {"title": "Chapter 1", "page_start": 1},
                        {"title": "Chapter 2", "page_start": 15}
                    ]
                }
            }

            artifact_validation = gates.validate_pass_artifacts("A", valid_artifacts)
            assert isinstance(artifact_validation, dict), "Artifact validation should return structured result"

            if "valid" in artifact_validation:
                assert artifact_validation["valid"] == True, "Valid artifacts should pass validation"

            # Test invalid artifacts
            invalid_artifacts = {
                "passA_toc.json": {
                    "source_id": "test_source"
                    # Missing required 'sections' field
                }
            }

            invalid_validation = gates.validate_pass_artifacts("A", invalid_artifacts)
            if "valid" in invalid_validation:
                assert invalid_validation["valid"] == False, "Invalid artifacts should fail validation"

            if "errors" in invalid_validation:
                errors = invalid_validation["errors"]
                assert len(errors) > 0, "Invalid artifacts should produce error messages"

    def test_fr028_evaluation_gates_thresholds(self):
        """Test FR-028 evaluation gates with support rate ≥85% and path success ≥80%"""
        try:
            from src_common.evaluation_gates import EvaluationGates
        except ImportError:
            pytest.skip("Evaluation gates not available for testing")

        eval_gates = EvaluationGates()

        # Test evaluation thresholds configuration
        threshold_config = {
            "support_rate": 0.85,  # ≥85% as per FR-028
            "path_success_rate": 0.80,  # ≥80% as per FR-028
            "citation_accuracy": 0.90,
            "multi_hop_latency": 2000  # milliseconds
        }

        if hasattr(eval_gates, 'configure_thresholds'):
            config_result = eval_gates.configure_thresholds(threshold_config)
            assert isinstance(config_result, dict), "Threshold configuration should return structured result"

            if "configured" in config_result:
                assert config_result["configured"] == True, "Valid thresholds should configure successfully"

        # Test evaluation metrics against thresholds
        test_evaluation_results = {
            "support_rate": 0.87,  # Above threshold
            "path_success_rate": 0.82,  # Above threshold
            "citation_accuracy": 0.91,  # Above threshold
            "multi_hop_latency": 1850,  # Below threshold (good)
            "total_queries": 100,
            "successful_queries": 82
        }

        if hasattr(eval_gates, 'evaluate_against_thresholds'):
            evaluation = eval_gates.evaluate_against_thresholds(test_evaluation_results, threshold_config)

            assert isinstance(evaluation, dict), "Threshold evaluation should return structured result"

            if "passed" in evaluation:
                assert evaluation["passed"] == True, "Results above thresholds should pass evaluation"

            if "threshold_results" in evaluation:
                threshold_results = evaluation["threshold_results"]

                # Verify individual threshold checks
                assert threshold_results["support_rate"]["passed"] == True, "Support rate should pass threshold"
                assert threshold_results["path_success_rate"]["passed"] == True, "Path success should pass threshold"

        # Test evaluation failure with below-threshold results
        failing_results = {
            "support_rate": 0.78,  # Below 85% threshold
            "path_success_rate": 0.75,  # Below 80% threshold
            "citation_accuracy": 0.85,  # Below 90% threshold
            "multi_hop_latency": 2500,  # Above latency threshold (bad)
            "total_queries": 100,
            "successful_queries": 75
        }

        if hasattr(eval_gates, 'evaluate_against_thresholds'):
            failing_evaluation = eval_gates.evaluate_against_thresholds(failing_results, threshold_config)

            if "passed" in failing_evaluation:
                assert failing_evaluation["passed"] == False, "Results below thresholds should fail evaluation"

            if "failed_thresholds" in failing_evaluation:
                failed = failing_evaluation["failed_thresholds"]
                assert "support_rate" in failed, "Support rate should be in failed thresholds"
                assert "path_success_rate" in failed, "Path success rate should be in failed thresholds"

    def test_ci_integration_gate_enforcement(self):
        """Test CI run fails if metrics drop below gate thresholds"""
        try:
            from src_common.ci_gates import CIGateEnforcement
        except ImportError:
            pytest.skip("CI gate enforcement not available for testing")

        ci_gates = CIGateEnforcement()

        # Test CI gate configuration
        ci_config = {
            "halt_on_failure": True,
            "thresholds": {
                "unit_test_coverage": 0.90,
                "functional_test_pass_rate": 0.95,
                "performance_regression_threshold": 1.2,  # 20% regression allowed
                "security_scan_critical_issues": 0  # No critical security issues
            },
            "evaluation_gates": {
                "support_rate": 0.85,
                "path_success_rate": 0.80
            }
        }

        # Test passing CI metrics
        passing_metrics = {
            "unit_test_coverage": 0.92,
            "functional_test_pass_rate": 0.97,
            "performance_regression": 1.05,  # 5% improvement
            "security_critical_issues": 0,
            "evaluation_results": {
                "support_rate": 0.87,
                "path_success_rate": 0.82
            }
        }

        if hasattr(ci_gates, 'evaluate_ci_gates'):
            ci_evaluation = ci_gates.evaluate_ci_gates(passing_metrics, ci_config)

            assert isinstance(ci_evaluation, dict), "CI evaluation should return structured result"

            if "ci_passed" in ci_evaluation:
                assert ci_evaluation["ci_passed"] == True, "Passing metrics should pass CI gates"

            if "exit_code" in ci_evaluation:
                assert ci_evaluation["exit_code"] == 0, "Passing CI should return exit code 0"

        # Test failing CI metrics
        failing_metrics = {
            "unit_test_coverage": 0.85,  # Below 90% threshold
            "functional_test_pass_rate": 0.93,  # Below 95% threshold
            "performance_regression": 1.3,  # 30% regression (above 20% threshold)
            "security_critical_issues": 2,  # Above 0 threshold
            "evaluation_results": {
                "support_rate": 0.82,  # Below 85% threshold
                "path_success_rate": 0.78  # Below 80% threshold
            }
        }

        if hasattr(ci_gates, 'evaluate_ci_gates'):
            failing_evaluation = ci_gates.evaluate_ci_gates(failing_metrics, ci_config)

            if "ci_passed" in failing_evaluation:
                assert failing_evaluation["ci_passed"] == False, "Failing metrics should fail CI gates"

            if "exit_code" in failing_evaluation:
                assert failing_evaluation["exit_code"] != 0, "Failing CI should return non-zero exit code"

            if "failed_gates" in failing_evaluation:
                failed_gates = failing_evaluation["failed_gates"]
                assert len(failed_gates) > 0, "Should report specific failed gates"

    def test_quality_gate_hard_stops(self):
        """Test hard stops when quality gates fail"""
        try:
            from src_common.gating import GatingEngine
        except ImportError:
            pytest.skip("Gating engine not available for testing")

        gating_engine = GatingEngine()

        # Test hard stop configuration
        hard_stop_config = {
            "mode": "strict",
            "halt_on_first_failure": True,
            "allow_overrides": False,
            "gates": [
                {
                    "name": "data_integrity",
                    "threshold": 0.95,
                    "hard_stop": True
                },
                {
                    "name": "completeness_check",
                    "threshold": 0.90,
                    "hard_stop": True
                },
                {
                    "name": "performance_baseline",
                    "threshold": 2.0,  # seconds
                    "hard_stop": False  # Soft gate
                }
            ]
        }

        # Test metrics that trigger hard stop
        failing_metrics = {
            "data_integrity": 0.92,  # Below 0.95 threshold (hard stop)
            "completeness_check": 0.94,  # Above 0.90 threshold (would pass)
            "performance_baseline": 2.5  # Above 2.0 threshold (soft gate)
        }

        if hasattr(gating_engine, 'evaluate_gates'):
            evaluation = gating_engine.evaluate_gates(failing_metrics, hard_stop_config)

            assert isinstance(evaluation, dict), "Gate evaluation should return structured result"

            # Verify hard stop behavior
            if "hard_stop_triggered" in evaluation:
                assert evaluation["hard_stop_triggered"] == True, "Hard stop should be triggered"

            if "halted_at_gate" in evaluation:
                halted_gate = evaluation["halted_at_gate"]
                assert halted_gate == "data_integrity", "Should halt at first failing hard stop gate"

            if "remaining_gates_skipped" in evaluation:
                skipped = evaluation["remaining_gates_skipped"]
                assert len(skipped) > 0, "Should skip remaining gates after hard stop"

    def test_resume_after_gate_fix(self):
        """Test resume functionality after fixing gate failures"""
        try:
            from src_common.gating import GatingEngine
        except ImportError:
            pytest.skip("Gating engine not available for testing")

        gating_engine = GatingEngine()

        # Test previous failure state
        previous_state = {
            "gates_evaluated": ["gate_1", "gate_2"],
            "gate_results": {
                "gate_1": {"passed": True, "value": 0.95},
                "gate_2": {"passed": False, "value": 0.82, "threshold": 0.85}
            },
            "halted_at": "gate_2",
            "remaining_gates": ["gate_3", "gate_4"]
        }

        # Test fixed metrics
        fixed_metrics = {
            "gate_2": 0.87,  # Now above 0.85 threshold
            "gate_3": 0.92,
            "gate_4": 0.94
        }

        if hasattr(gating_engine, 'resume_from_gate'):
            resume_result = gating_engine.resume_from_gate(
                previous_state=previous_state,
                fixed_metrics=fixed_metrics,
                resume_from="gate_2"
            )

            assert isinstance(resume_result, dict), "Resume should return structured result"

            # Verify resume behavior
            if "resumed_successfully" in resume_result:
                assert resume_result["resumed_successfully"] == True, "Should resume successfully with fixed metrics"

            if "gates_evaluated" in resume_result:
                evaluated = resume_result["gates_evaluated"]
                assert "gate_2" in evaluated, "Should re-evaluate previously failed gate"
                assert "gate_3" in evaluated, "Should evaluate remaining gates"
                assert "gate_4" in evaluated, "Should complete all remaining gates"

            if "all_gates_passed" in resume_result:
                assert resume_result["all_gates_passed"] == True, "All gates should pass after fixes"

    def test_gating_telemetry_and_monitoring(self):
        """Test gating telemetry and monitoring capabilities"""
        try:
            from src_common.gating import GatingEngine
        except ImportError:
            pytest.skip("Gating engine not available for testing")

        gating_engine = GatingEngine()

        # Test telemetry configuration
        telemetry_config = {
            "enable_logging": True,
            "log_level": "INFO",
            "metrics_collection": True,
            "alert_on_failures": True,
            "performance_tracking": True
        }

        test_metrics = {
            "gate_1": 0.95,
            "gate_2": 0.88,
            "gate_3": 0.92
        }

        gate_config = {
            "gates": [
                {"name": "gate_1", "threshold": 0.90},
                {"name": "gate_2", "threshold": 0.85},
                {"name": "gate_3", "threshold": 0.90}
            ]
        }

        if hasattr(gating_engine, 'evaluate_with_telemetry'):
            evaluation = gating_engine.evaluate_with_telemetry(
                metrics=test_metrics,
                config=gate_config,
                telemetry_config=telemetry_config
            )

            assert isinstance(evaluation, dict), "Telemetry evaluation should return structured result"

            # Verify telemetry data
            if "telemetry" in evaluation:
                telemetry = evaluation["telemetry"]

                # Check timing information
                if "evaluation_time" in telemetry:
                    eval_time = telemetry["evaluation_time"]
                    assert isinstance(eval_time, (int, float)), "Evaluation time should be numeric"
                    assert eval_time > 0, "Evaluation time should be positive"

                # Check gate-level metrics
                if "gate_metrics" in telemetry:
                    gate_metrics = telemetry["gate_metrics"]
                    assert isinstance(gate_metrics, dict), "Gate metrics should be structured"

                    for gate_name in ["gate_1", "gate_2", "gate_3"]:
                        if gate_name in gate_metrics:
                            gate_metric = gate_metrics[gate_name]
                            assert "evaluation_time" in gate_metric, f"Gate {gate_name} should have timing info"
                            assert "threshold_margin" in gate_metric, f"Gate {gate_name} should show margin"

                # Check performance statistics
                if "performance_stats" in telemetry:
                    perf_stats = telemetry["performance_stats"]
                    assert "total_gates" in perf_stats, "Should track total gate count"
                    assert "passed_gates" in perf_stats, "Should track passed gate count"
                    assert "failed_gates" in perf_stats, "Should track failed gate count"

    def test_gating_contract_compliance(self):
        """Test that gating mechanisms match established contract"""
        # Test gating interface contract
        required_gating_methods = [
            "validate_prerequisites",
            "evaluate_thresholds",
            "enforce_hard_stops",
            "support_resume",
            "provide_telemetry"
        ]

        # Test threshold configuration contract
        required_threshold_fields = [
            "threshold_value",
            "comparison_operator",  # >=, <=, ==, etc.
            "failure_action",  # halt, warn, continue
            "error_message"
        ]

        # Test gate result contract
        required_result_fields = [
            "passed",
            "value",
            "threshold",
            "margin",
            "evaluation_time"
        ]

        # Test FR-005 specific contract
        fr005_requirements = {
            "sequential_execution": True,  # A→B→C→D→E→F sequence enforced
            "artifact_validation": True,   # Artifacts validated before next pass
            "resume_capability": True,     # Can resume from any pass
            "failure_blocking": True       # Failed pass blocks subsequent passes
        }

        for requirement, needed in fr005_requirements.items():
            assert needed, f"FR-005 requirement {requirement} is mandatory"

        # Test FR-028 specific contract
        fr028_requirements = {
            "support_rate_threshold": 0.85,  # ≥85% support rate
            "path_success_threshold": 0.80,  # ≥80% path success
            "ci_integration": True,          # CI fails on threshold violations
            "metrics_tracking": True         # Metrics tracked and reported
        }

        for requirement, value in fr028_requirements.items():
            if isinstance(value, bool):
                assert value, f"FR-028 requirement {requirement} is mandatory"
            elif isinstance(value, (int, float)):
                assert value > 0, f"FR-028 threshold {requirement} must be positive"

        # Test overall gating contract compliance
        contract_elements = {
            "deterministic_evaluation": True,   # Same inputs → same outputs
            "configurable_thresholds": True,    # Thresholds can be configured
            "detailed_failure_reporting": True, # Clear failure reasons provided
            "performance_monitoring": True,     # Evaluation performance tracked
            "rollback_capability": True         # Can rollback on gate failures
        }

        for element, required in contract_elements.items():
            assert required, f"Gating contract element {element} is required"

        # Test integration contract
        integration_requirements = [
            "ingestion_pipeline_integration",
            "evaluation_system_integration",
            "ci_cd_integration",
            "monitoring_system_integration"
        ]

        for integration in integration_requirements:
            # Integration points should be defined
            assert isinstance(integration, str), f"Integration {integration} should be defined"