# tests/regression/feature_requests/gating_test_framework.py
"""
Gating Test Framework Infrastructure
Reusable testing utilities for quality gates, validation, and pass management
"""

import json
import time
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import Mock, MagicMock


@dataclass
class GateResult:
    """Represents the result of a quality gate evaluation"""
    gate_name: str
    passed: bool
    value: Union[int, float, str]
    threshold: Union[int, float, str]
    margin: float
    evaluation_time: float
    critical: bool = False
    error_message: Optional[str] = None


@dataclass
class PassResult:
    """Represents the result of a pass execution"""
    pass_name: str
    status: str  # SUCCESS, FAILED, PENDING, BLOCKED
    artifacts: List[str]
    duration: float
    quality_metrics: Dict[str, Any]
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class QualityGateTestHelper:
    """Helper class for testing quality gates and validation logic"""

    def __init__(self):
        """Initialize the quality gate test helper"""
        self.default_thresholds = {
            "support_rate": 0.85,
            "path_success_rate": 0.80,
            "citation_accuracy": 0.75,
            "data_integrity": 0.95,
            "completeness": 0.90,
            "response_time": 2000  # milliseconds
        }

    def create_test_metrics(self, **overrides) -> Dict[str, Any]:
        """Create test metrics with optional overrides

        Args:
            **overrides: Metric values to override defaults

        Returns:
            Dictionary of test metrics
        """
        base_metrics = {
            "support_rate": 0.87,
            "path_success_rate": 0.82,
            "citation_accuracy": 0.78,
            "data_integrity": 0.96,
            "completeness": 0.91,
            "response_time": 1800,
            "total_queries": 100,
            "successful_queries": 82,
            "failed_queries": 18,
            "processing_time": 145.2
        }

        base_metrics.update(overrides)
        return base_metrics

    def create_gate_config(self, **overrides) -> Dict[str, Any]:
        """Create gate configuration with optional overrides

        Args:
            **overrides: Configuration values to override defaults

        Returns:
            Dictionary of gate configuration
        """
        base_config = {
            "strict_mode": True,
            "halt_on_failure": True,
            "gates": [
                {
                    "name": "support_rate",
                    "threshold": self.default_thresholds["support_rate"],
                    "operator": ">=",
                    "critical": True,
                    "error_message": "Support rate below minimum threshold"
                },
                {
                    "name": "path_success_rate",
                    "threshold": self.default_thresholds["path_success_rate"],
                    "operator": ">=",
                    "critical": True,
                    "error_message": "Path success rate below minimum threshold"
                },
                {
                    "name": "response_time",
                    "threshold": self.default_thresholds["response_time"],
                    "operator": "<=",
                    "critical": False,
                    "error_message": "Response time exceeds maximum threshold"
                }
            ]
        }

        # Apply overrides
        if "gates" in overrides:
            # Merge gate configurations
            for override_gate in overrides["gates"]:
                gate_name = override_gate.get("name")
                for i, base_gate in enumerate(base_config["gates"]):
                    if base_gate["name"] == gate_name:
                        base_config["gates"][i].update(override_gate)
                        break
                else:
                    base_config["gates"].append(override_gate)
            del overrides["gates"]

        base_config.update(overrides)
        return base_config

    def evaluate_gate(self, gate_config: Dict[str, Any], metric_value: Union[int, float],
                     evaluation_start_time: Optional[float] = None) -> GateResult:
        """Evaluate a single gate against a metric value

        Args:
            gate_config: Gate configuration dictionary
            metric_value: The metric value to evaluate
            evaluation_start_time: Optional start time for duration calculation

        Returns:
            GateResult object
        """
        start_time = evaluation_start_time or time.perf_counter()

        gate_name = gate_config["name"]
        threshold = gate_config["threshold"]
        operator = gate_config.get("operator", ">=")
        critical = gate_config.get("critical", False)
        error_message = gate_config.get("error_message")

        # Evaluate based on operator
        if operator == ">=":
            passed = metric_value >= threshold
            margin = metric_value - threshold
        elif operator == "<=":
            passed = metric_value <= threshold
            margin = threshold - metric_value
        elif operator == "==":
            passed = metric_value == threshold
            margin = 0 if passed else abs(metric_value - threshold)
        else:
            raise ValueError(f"Unsupported operator: {operator}")

        evaluation_time = time.perf_counter() - start_time

        return GateResult(
            gate_name=gate_name,
            passed=passed,
            value=metric_value,
            threshold=threshold,
            margin=margin,
            evaluation_time=evaluation_time,
            critical=critical,
            error_message=error_message if not passed else None
        )

    def evaluate_all_gates(self, gate_config: Dict[str, Any],
                          metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all gates in configuration against metrics

        Args:
            gate_config: Gate configuration dictionary
            metrics: Metrics to evaluate

        Returns:
            Dictionary with evaluation results
        """
        start_time = time.perf_counter()
        gate_results = []
        failed_gates = []
        critical_failures = []

        for gate in gate_config.get("gates", []):
            gate_name = gate["name"]

            if gate_name not in metrics:
                # Missing metric is a failure
                result = GateResult(
                    gate_name=gate_name,
                    passed=False,
                    value="MISSING",
                    threshold=gate["threshold"],
                    margin=0,
                    evaluation_time=0,
                    critical=gate.get("critical", False),
                    error_message=f"Metric {gate_name} not found in results"
                )
            else:
                result = self.evaluate_gate(gate, metrics[gate_name], start_time)

            gate_results.append(result)

            if not result.passed:
                failed_gates.append(result)
                if result.critical:
                    critical_failures.append(result)

        total_time = time.perf_counter() - start_time
        all_passed = len(failed_gates) == 0

        return {
            "all_gates_passed": all_passed,
            "total_gates": len(gate_config.get("gates", [])),
            "passed_gates": len(gate_results) - len(failed_gates),
            "failed_gates": len(failed_gates),
            "critical_failures": len(critical_failures),
            "evaluation_time": total_time,
            "gate_results": {result.gate_name: result.__dict__ for result in gate_results},
            "failed_gate_names": [result.gate_name for result in failed_gates],
            "critical_failure_names": [result.gate_name for result in critical_failures],
            "should_halt": gate_config.get("halt_on_failure", False) and len(critical_failures) > 0
        }


class PassExecutionTestHelper:
    """Helper class for testing pass execution and sequencing"""

    def __init__(self):
        """Initialize the pass execution test helper"""
        self.pass_sequence = ["A", "B", "C", "D", "E", "F"]
        self.pass_dependencies = {
            "A": [],
            "B": ["A"],
            "C": ["A", "B"],
            "D": ["A", "B", "C"],
            "E": ["A", "B", "C", "D"],
            "F": ["A", "B", "C", "D", "E"]
        }

    def create_job_state(self, **overrides) -> Dict[str, Any]:
        """Create test job state with optional overrides

        Args:
            **overrides: State values to override defaults

        Returns:
            Dictionary representing job state
        """
        base_state = {
            "job_id": f"test_job_{int(time.time())}",
            "environment": "test",
            "created_at": datetime.utcnow().isoformat(),
            "passes": {
                pass_name: {
                    "status": "PENDING",
                    "artifacts": [],
                    "started_at": None,
                    "completed_at": None,
                    "duration": 0.0,
                    "quality_metrics": {}
                }
                for pass_name in self.pass_sequence
            },
            "source_files": ["test_source.pdf"],
            "artifacts_dir": "/test/artifacts",
            "total_sources": 1,
            "processing_metrics": {
                "total_time": 0.0,
                "passes_completed": 0,
                "passes_failed": 0
            }
        }

        # Apply overrides
        if "passes" in overrides:
            for pass_name, pass_overrides in overrides["passes"].items():
                if pass_name in base_state["passes"]:
                    base_state["passes"][pass_name].update(pass_overrides)
            del overrides["passes"]

        base_state.update(overrides)
        return base_state

    def can_execute_pass(self, pass_name: str, job_state: Dict[str, Any]) -> bool:
        """Check if a pass can be executed based on dependencies

        Args:
            pass_name: Name of the pass to check
            job_state: Current job state

        Returns:
            True if pass can be executed, False otherwise
        """
        if pass_name not in self.pass_dependencies:
            return False

        dependencies = self.pass_dependencies[pass_name]
        passes = job_state.get("passes", {})

        # Check all dependencies are successful
        for dep_pass in dependencies:
            if dep_pass not in passes:
                return False

            dep_status = passes[dep_pass].get("status", "PENDING")
            if dep_status != "SUCCESS":
                return False

        return True

    def simulate_pass_execution(self, pass_name: str, duration: float = 10.0,
                              success: bool = True,
                              artifacts: Optional[List[str]] = None,
                              quality_metrics: Optional[Dict[str, Any]] = None) -> PassResult:
        """Simulate pass execution with configurable results

        Args:
            pass_name: Name of the pass
            duration: Execution duration in seconds
            success: Whether the pass should succeed
            artifacts: List of artifacts produced
            quality_metrics: Quality metrics for the pass

        Returns:
            PassResult object
        """
        start_time = datetime.utcnow()
        status = "SUCCESS" if success else "FAILED"

        if artifacts is None:
            artifacts = [f"pass{pass_name}_{status.lower()}.json"]

        if quality_metrics is None:
            quality_metrics = {
                "processing_time": duration,
                "items_processed": 100 if success else 0,
                "quality_score": 0.9 if success else 0.3
            }

        return PassResult(
            pass_name=pass_name,
            status=status,
            artifacts=artifacts,
            duration=duration,
            quality_metrics=quality_metrics,
            error=None if success else f"Pass {pass_name} simulation failure",
            started_at=start_time.isoformat(),
            completed_at=(start_time).isoformat()
        )

    def validate_pass_sequence(self, executed_passes: List[str]) -> Dict[str, Any]:
        """Validate that passes were executed in correct sequence

        Args:
            executed_passes: List of pass names in execution order

        Returns:
            Dictionary with validation results
        """
        validation_errors = []

        for i, pass_name in enumerate(executed_passes):
            if pass_name not in self.pass_sequence:
                validation_errors.append(f"Unknown pass: {pass_name}")
                continue

            # Check dependencies
            dependencies = self.pass_dependencies[pass_name]
            for dep in dependencies:
                if dep not in executed_passes[:i]:
                    validation_errors.append(
                        f"Pass {pass_name} executed before dependency {dep}"
                    )

        return {
            "valid_sequence": len(validation_errors) == 0,
            "errors": validation_errors,
            "executed_count": len(executed_passes),
            "expected_sequence": self.pass_sequence
        }


class ArtifactTestHelper:
    """Helper class for testing artifact validation and management"""

    def __init__(self):
        """Initialize the artifact test helper"""
        self.artifact_schemas = {
            "passA_toc.json": {
                "required_fields": ["source_id", "sections", "total_pages"],
                "field_types": {
                    "source_id": str,
                    "sections": list,
                    "total_pages": int
                }
            },
            "passC_chunks.json": {
                "required_fields": ["chunks", "total_chunks", "source_id"],
                "field_types": {
                    "chunks": list,
                    "total_chunks": int,
                    "source_id": str
                }
            },
            "passD_enriched.json": {
                "required_fields": ["enriched_chunks", "entity_count", "processing_summary"],
                "field_types": {
                    "enriched_chunks": list,
                    "entity_count": int,
                    "processing_summary": dict
                }
            }
        }

    def create_test_artifact(self, artifact_name: str, valid: bool = True,
                           **overrides) -> Dict[str, Any]:
        """Create test artifact data

        Args:
            artifact_name: Name of the artifact
            valid: Whether to create valid or invalid artifact
            **overrides: Field values to override

        Returns:
            Dictionary representing artifact data
        """
        if artifact_name == "passA_toc.json":
            base_data = {
                "source_id": "test_source_001",
                "sections": [
                    {"title": "Chapter 1", "page_start": 1, "page_end": 10},
                    {"title": "Chapter 2", "page_start": 11, "page_end": 25}
                ],
                "total_pages": 25,
                "extraction_metadata": {
                    "tool": "unstructured.io",
                    "version": "0.10.0",
                    "confidence": 0.92
                }
            }

            if not valid:
                # Make invalid by removing required field
                del base_data["sections"]

        elif artifact_name == "passC_chunks.json":
            base_data = {
                "chunks": [
                    {
                        "chunk_id": "chunk_001",
                        "content": "Fireball is a 3rd-level evocation spell",
                        "page": 1,
                        "metadata": {"type": "spell"}
                    },
                    {
                        "chunk_id": "chunk_002",
                        "content": "Magic Missile creates force darts",
                        "page": 2,
                        "metadata": {"type": "spell"}
                    }
                ],
                "total_chunks": 2,
                "source_id": "test_source_001",
                "processing_summary": {
                    "chunking_strategy": "semantic",
                    "avg_chunk_size": 150,
                    "processing_time": 45.2
                }
            }

            if not valid:
                # Make invalid by setting negative chunk count
                base_data["total_chunks"] = -1

        else:
            # Generic artifact structure
            base_data = {
                "artifact_type": artifact_name,
                "created_at": datetime.utcnow().isoformat(),
                "valid": valid
            }

        base_data.update(overrides)
        return base_data

    def validate_artifact(self, artifact_name: str, artifact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate artifact data against schema

        Args:
            artifact_name: Name of the artifact
            artifact_data: Artifact data to validate

        Returns:
            Dictionary with validation results
        """
        if artifact_name not in self.artifact_schemas:
            return {
                "valid": False,
                "errors": [f"Unknown artifact type: {artifact_name}"]
            }

        schema = self.artifact_schemas[artifact_name]
        errors = []

        # Check required fields
        for field in schema["required_fields"]:
            if field not in artifact_data:
                errors.append(f"Missing required field: {field}")

        # Check field types
        for field, expected_type in schema["field_types"].items():
            if field in artifact_data:
                if not isinstance(artifact_data[field], expected_type):
                    errors.append(
                        f"Field {field} has wrong type: expected {expected_type.__name__}, "
                        f"got {type(artifact_data[field]).__name__}"
                    )

        # Validate specific constraints
        if artifact_name == "passA_toc.json":
            if "sections" in artifact_data:
                sections = artifact_data["sections"]
                if not isinstance(sections, list) or len(sections) == 0:
                    errors.append("Sections must be non-empty list")

        elif artifact_name == "passC_chunks.json":
            if "total_chunks" in artifact_data:
                total_chunks = artifact_data["total_chunks"]
                if not isinstance(total_chunks, int) or total_chunks < 0:
                    errors.append("Total chunks must be non-negative integer")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "schema": artifact_name,
            "validated_fields": len(schema["required_fields"])
        }

    def create_artifact_file(self, artifact_name: str, artifact_data: Dict[str, Any],
                           base_dir: Optional[Path] = None) -> Path:
        """Create physical artifact file for testing

        Args:
            artifact_name: Name of the artifact file
            artifact_data: Data to write to file
            base_dir: Directory to create file in (uses temp dir if None)

        Returns:
            Path to created file
        """
        if base_dir is None:
            base_dir = Path(tempfile.mkdtemp())

        artifact_path = base_dir / artifact_name

        with open(artifact_path, 'w') as f:
            json.dump(artifact_data, f, indent=2)

        return artifact_path


def create_mock_gating_engine() -> Mock:
    """Create a mock gating engine for testing

    Returns:
        Mock object configured for gating engine behavior
    """
    mock_engine = Mock()

    # Configure default behaviors
    mock_engine.configure_gates.return_value = {"configured": True}
    mock_engine.evaluate_gates.return_value = {
        "all_gates_passed": True,
        "gate_results": {},
        "failed_gates": []
    }
    mock_engine.can_execute_pass.return_value = True

    return mock_engine


def create_mock_pass_runner() -> Mock:
    """Create a mock pass runner for testing

    Returns:
        Mock object configured for pass runner behavior
    """
    mock_runner = Mock()

    # Configure default behaviors
    mock_runner.initialize_job.return_value = {
        "initialized": True,
        "job_state": {"job_id": "test_job"}
    }
    mock_runner.execute_pass.return_value = {
        "status": "SUCCESS",
        "artifacts": ["test_artifact.json"]
    }
    mock_runner.validate_artifacts.return_value = {
        "valid": True,
        "errors": []
    }

    return mock_runner