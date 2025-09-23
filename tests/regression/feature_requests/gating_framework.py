"""
Gating Test Framework Infrastructure
Provides centralized gating mechanisms, quality gates, and validation infrastructure for all feature requests.
"""

import pytest
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class GateStatus(Enum):
    """Gate status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class GateSeverity(Enum):
    """Gate severity levels."""
    CRITICAL = "critical"      # Must pass for deployment
    HIGH = "high"             # Should pass, blocking with approval
    MEDIUM = "medium"         # Should pass, warning only
    LOW = "low"              # Nice to have, informational


@dataclass
class GateResult:
    """Individual gate execution result."""
    gate_id: str
    name: str
    status: GateStatus
    severity: GateSeverity
    execution_time: float
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    threshold_met: bool = True
    score: float = 1.0


@dataclass
class QualityThreshold:
    """Quality threshold definition."""
    metric_name: str
    min_value: float
    max_value: Optional[float] = None
    unit: str = ""
    description: str = ""


class GatingFramework:
    """Central gating framework for FR validation."""

    def __init__(self):
        self.gates = {}
        self.execution_history = []
        self.quality_thresholds = self._initialize_quality_thresholds()
        self.gate_dependencies = {}

    def _initialize_quality_thresholds(self) -> Dict[str, QualityThreshold]:
        """Initialize quality thresholds for all FR categories."""
        return {
            # Pipeline Quality Gates (FR-001, Passed D-G)
            'pipeline_pass_success_rate': QualityThreshold(
                'pipeline_pass_success_rate', 0.95, 1.0, '%',
                'Sequential pass execution success rate must be ≥95%'
            ),
            'data_quality_score': QualityThreshold(
                'data_quality_score', 0.85, 1.0, 'score',
                'Data quality validation score must be ≥85%'
            ),
            'ingestion_gate_compliance': QualityThreshold(
                'ingestion_gate_compliance', 0.9, 1.0, '%',
                'Modular ingestion gate compliance must be ≥90%'
            ),

            # Infrastructure Quality Gates (FR-002 through FR-007)
            'service_availability': QualityThreshold(
                'service_availability', 0.999, 1.0, '%',
                'Service availability must be ≥99.9%'
            ),
            'response_time_p95': QualityThreshold(
                'response_time_p95', 0, 500, 'ms',
                'P95 response time must be ≤500ms'
            ),
            'security_scan_pass_rate': QualityThreshold(
                'security_scan_pass_rate', 0.95, 1.0, '%',
                'Security vulnerability scan pass rate must be ≥95%'
            ),
            'container_startup_time': QualityThreshold(
                'container_startup_time', 0, 30, 'seconds',
                'Container startup time must be ≤30 seconds'
            ),

            # Search and Data Quality Gates (FR-009 through FR-014)
            'search_precision': QualityThreshold(
                'search_precision', 0.85, 1.0, 'score',
                'Search precision must be ≥85%'
            ),
            'search_recall': QualityThreshold(
                'search_recall', 0.8, 1.0, 'score',
                'Search recall must be ≥80%'
            ),
            'data_consistency_score': QualityThreshold(
                'data_consistency_score', 0.99, 1.0, '%',
                'Data consistency across systems must be ≥99%'
            ),

            # UI/UX Quality Gates (FR-016 through FR-019)
            'page_load_time': QualityThreshold(
                'page_load_time', 0, 2000, 'ms',
                'Page load time must be ≤2 seconds'
            ),
            'accessibility_score': QualityThreshold(
                'accessibility_score', 0.9, 1.0, 'score',
                'WCAG accessibility score must be ≥90%'
            ),
            'mobile_responsiveness': QualityThreshold(
                'mobile_responsiveness', 0.95, 1.0, 'score',
                'Mobile responsiveness score must be ≥95%'
            ),

            # AI and Analytics Quality Gates (FR-020 through FR-027)
            'model_accuracy': QualityThreshold(
                'model_accuracy', 0.85, 1.0, 'score',
                'ML model accuracy must be ≥85%'
            ),
            'prediction_latency': QualityThreshold(
                'prediction_latency', 0, 100, 'ms',
                'ML prediction latency must be ≤100ms'
            ),
            'analytics_data_freshness': QualityThreshold(
                'analytics_data_freshness', 0, 300, 'seconds',
                'Analytics data freshness must be ≤5 minutes'
            ),

            # Operations and Monitoring Quality Gates (FR-029 through FR-034)
            'backup_success_rate': QualityThreshold(
                'backup_success_rate', 0.99, 1.0, '%',
                'Backup success rate must be ≥99%'
            ),
            'monitoring_coverage': QualityThreshold(
                'monitoring_coverage', 0.95, 1.0, '%',
                'System monitoring coverage must be ≥95%'
            ),
            'compliance_score': QualityThreshold(
                'compliance_score', 0.9, 1.0, 'score',
                'Regulatory compliance score must be ≥90%'
            ),
            'disaster_recovery_rto': QualityThreshold(
                'disaster_recovery_rto', 0, 14400, 'seconds',
                'Disaster recovery RTO must be ≤4 hours'
            ),
            'integration_test_coverage': QualityThreshold(
                'integration_test_coverage', 0.8, 1.0, '%',
                'Integration test coverage must be ≥80%'
            )
        }

    def register_gate(self, gate_id: str, name: str, severity: GateSeverity,
                     test_function: callable, dependencies: List[str] = None):
        """Register a new quality gate."""
        self.gates[gate_id] = {
            'name': name,
            'severity': severity,
            'test_function': test_function,
            'dependencies': dependencies or []
        }
        if dependencies:
            self.gate_dependencies[gate_id] = dependencies

    async def execute_gate(self, gate_id: str, context: Dict[str, Any] = None) -> GateResult:
        """Execute a specific quality gate."""
        if gate_id not in self.gates:
            raise ValueError(f"Gate {gate_id} not registered")

        gate_config = self.gates[gate_id]
        start_time = time.time()

        try:
            # Check dependencies first
            for dep_gate_id in gate_config['dependencies']:
                dep_result = await self.execute_gate(dep_gate_id, context)
                if dep_result.status == GateStatus.FAILED and dep_result.severity == GateSeverity.CRITICAL:
                    return GateResult(
                        gate_id=gate_id,
                        name=gate_config['name'],
                        status=GateStatus.BLOCKED,
                        severity=gate_config['severity'],
                        execution_time=time.time() - start_time,
                        message=f"Blocked by failed dependency: {dep_gate_id}",
                        details={'dependency_failure': dep_gate_id},
                        timestamp=datetime.utcnow()
                    )

            # Execute the gate test
            result_data = await gate_config['test_function'](context or {})

            # Evaluate against quality thresholds
            threshold_results = self._evaluate_thresholds(gate_id, result_data)

            # Determine gate status
            status = GateStatus.PASSED if threshold_results['all_passed'] else GateStatus.FAILED

            result = GateResult(
                gate_id=gate_id,
                name=gate_config['name'],
                status=status,
                severity=gate_config['severity'],
                execution_time=time.time() - start_time,
                message=threshold_results['summary'],
                details=result_data,
                timestamp=datetime.utcnow(),
                threshold_met=threshold_results['all_passed'],
                score=threshold_results['overall_score']
            )

            self.execution_history.append(result)
            return result

        except Exception as e:
            error_result = GateResult(
                gate_id=gate_id,
                name=gate_config['name'],
                status=GateStatus.FAILED,
                severity=gate_config['severity'],
                execution_time=time.time() - start_time,
                message=f"Gate execution failed: {str(e)}",
                details={'error': str(e), 'exception_type': type(e).__name__},
                timestamp=datetime.utcnow(),
                threshold_met=False,
                score=0.0
            )

            self.execution_history.append(error_result)
            return error_result

    def _evaluate_thresholds(self, gate_id: str, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate result data against quality thresholds."""
        threshold_results = []
        overall_score = 1.0

        for metric_name, threshold in self.quality_thresholds.items():
            if metric_name in result_data:
                value = result_data[metric_name]
                passed = self._check_threshold(value, threshold)
                threshold_results.append({
                    'metric': metric_name,
                    'value': value,
                    'threshold': threshold,
                    'passed': passed
                })

                if not passed:
                    overall_score *= 0.8  # Reduce score for each failed threshold

        all_passed = all(tr['passed'] for tr in threshold_results)
        failed_count = len([tr for tr in threshold_results if not tr['passed']])

        summary = f"Thresholds: {len(threshold_results) - failed_count}/{len(threshold_results)} passed"
        if failed_count > 0:
            failed_metrics = [tr['metric'] for tr in threshold_results if not tr['passed']]
            summary += f" (Failed: {', '.join(failed_metrics)})"

        return {
            'all_passed': all_passed,
            'overall_score': overall_score,
            'summary': summary,
            'detailed_results': threshold_results
        }

    def _check_threshold(self, value: float, threshold: QualityThreshold) -> bool:
        """Check if a value meets the quality threshold."""
        if value < threshold.min_value:
            return False
        if threshold.max_value is not None and value > threshold.max_value:
            return False
        return True

    async def execute_gate_suite(self, gate_ids: List[str],
                                context: Dict[str, Any] = None) -> Dict[str, GateResult]:
        """Execute a suite of quality gates with dependency resolution."""
        # Resolve execution order based on dependencies
        execution_order = self._resolve_execution_order(gate_ids)

        results = {}
        context = context or {}

        for gate_id in execution_order:
            if gate_id in gate_ids:  # Only execute requested gates
                result = await self.execute_gate(gate_id, context)
                results[gate_id] = result

                # Update context with result for downstream gates
                context[f'gate_result_{gate_id}'] = result

                # For critical failures, consider stopping execution
                if (result.status == GateStatus.FAILED and
                    result.severity == GateSeverity.CRITICAL):
                    logger.warning(f"Critical gate {gate_id} failed, continuing with remaining gates")

        return results

    def _resolve_execution_order(self, gate_ids: List[str]) -> List[str]:
        """Resolve gate execution order based on dependencies."""
        ordered = []
        visited = set()
        temp_visited = set()

        def visit(gate_id: str):
            if gate_id in temp_visited:
                raise ValueError(f"Circular dependency detected involving gate {gate_id}")
            if gate_id in visited:
                return

            temp_visited.add(gate_id)

            # Visit dependencies first
            for dep in self.gate_dependencies.get(gate_id, []):
                visit(dep)

            temp_visited.remove(gate_id)
            visited.add(gate_id)
            ordered.append(gate_id)

        for gate_id in gate_ids:
            if gate_id not in visited:
                visit(gate_id)

        return ordered

    def generate_gating_report(self, results: Dict[str, GateResult]) -> Dict[str, Any]:
        """Generate comprehensive gating report."""
        total_gates = len(results)
        passed_gates = len([r for r in results.values() if r.status == GateStatus.PASSED])
        failed_gates = len([r for r in results.values() if r.status == GateStatus.FAILED])
        blocked_gates = len([r for r in results.values() if r.status == GateStatus.BLOCKED])

        critical_failures = [
            r for r in results.values()
            if r.status == GateStatus.FAILED and r.severity == GateSeverity.CRITICAL
        ]

        overall_score = sum(r.score for r in results.values()) / total_gates if total_gates > 0 else 0

        # Determine overall deployment readiness
        deployment_ready = (
            len(critical_failures) == 0 and
            passed_gates / total_gates >= 0.8 and  # At least 80% gates pass
            overall_score >= 0.85  # Overall score ≥85%
        )

        return {
            'summary': {
                'total_gates': total_gates,
                'passed_gates': passed_gates,
                'failed_gates': failed_gates,
                'blocked_gates': blocked_gates,
                'success_rate': passed_gates / total_gates if total_gates > 0 else 0,
                'overall_score': overall_score,
                'deployment_ready': deployment_ready
            },
            'critical_failures': [
                {
                    'gate_id': r.gate_id,
                    'name': r.name,
                    'message': r.message,
                    'details': r.details
                }
                for r in critical_failures
            ],
            'detailed_results': {
                gate_id: {
                    'name': result.name,
                    'status': result.status.value,
                    'severity': result.severity.value,
                    'score': result.score,
                    'execution_time': result.execution_time,
                    'message': result.message,
                    'threshold_met': result.threshold_met,
                    'timestamp': result.timestamp.isoformat()
                }
                for gate_id, result in results.items()
            },
            'recommendations': self._generate_recommendations(results),
            'next_steps': self._generate_next_steps(results, deployment_ready)
        }

    def _generate_recommendations(self, results: Dict[str, GateResult]) -> List[str]:
        """Generate recommendations based on gate results."""
        recommendations = []

        failed_results = [r for r in results.values() if r.status == GateStatus.FAILED]

        for result in failed_results:
            if result.severity == GateSeverity.CRITICAL:
                recommendations.append(
                    f"CRITICAL: Address {result.name} failure before deployment - {result.message}"
                )
            elif result.severity == GateSeverity.HIGH:
                recommendations.append(
                    f"HIGH: Review {result.name} issues - {result.message}"
                )
            elif result.severity == GateSeverity.MEDIUM:
                recommendations.append(
                    f"MEDIUM: Consider improving {result.name} - {result.message}"
                )

        # Performance recommendations
        slow_gates = [r for r in results.values() if r.execution_time > 60]  # >1 minute
        if slow_gates:
            recommendations.append(
                f"PERFORMANCE: Optimize slow gates: {', '.join([r.name for r in slow_gates])}"
            )

        return recommendations

    def _generate_next_steps(self, results: Dict[str, GateResult], deployment_ready: bool) -> List[str]:
        """Generate next steps based on gate results."""
        next_steps = []

        if deployment_ready:
            next_steps.append("✅ All critical gates passed - system ready for deployment")
            next_steps.append("Continue with deployment pipeline")

            # Check for warnings
            warning_gates = [
                r for r in results.values()
                if r.status == GateStatus.FAILED and r.severity in [GateSeverity.MEDIUM, GateSeverity.LOW]
            ]
            if warning_gates:
                next_steps.append(f"Address {len(warning_gates)} warning-level issues in next iteration")
        else:
            next_steps.append("❌ System NOT ready for deployment")

            critical_failures = [
                r for r in results.values()
                if r.status == GateStatus.FAILED and r.severity == GateSeverity.CRITICAL
            ]
            if critical_failures:
                next_steps.append(f"Fix {len(critical_failures)} critical failures before proceeding")
                for failure in critical_failures[:3]:  # Show first 3
                    next_steps.append(f"  - {failure.name}: {failure.message}")

            high_failures = [
                r for r in results.values()
                if r.status == GateStatus.FAILED and r.severity == GateSeverity.HIGH
            ]
            if high_failures:
                next_steps.append(f"Review {len(high_failures)} high-priority issues")

        next_steps.append("Re-run gating suite after addressing issues")

        return next_steps


# Global gating framework instance
gating_framework = GatingFramework()


# Decorator for registering gate functions
def quality_gate(gate_id: str, name: str, severity: GateSeverity, dependencies: List[str] = None):
    """Decorator to register a function as a quality gate."""
    def decorator(func):
        gating_framework.register_gate(gate_id, name, severity, func, dependencies)
        return func
    return decorator


# Pre-configured gate suites for different validation scenarios
GATE_SUITES = {
    'critical_deployment': [
        'pipeline_validation',
        'security_scan',
        'performance_baseline',
        'data_integrity'
    ],
    'full_validation': [
        'pipeline_validation',
        'infrastructure_health',
        'security_scan',
        'performance_baseline',
        'search_quality',
        'ui_responsiveness',
        'ai_model_accuracy',
        'monitoring_coverage',
        'backup_validation',
        'compliance_check',
        'disaster_recovery',
        'integration_test'
    ],
    'smoke_test': [
        'basic_connectivity',
        'service_health',
        'auth_validation'
    ]
}


async def run_gate_suite(suite_name: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run a predefined gate suite and return comprehensive results."""
    if suite_name not in GATE_SUITES:
        raise ValueError(f"Unknown gate suite: {suite_name}")

    gate_ids = GATE_SUITES[suite_name]
    results = await gating_framework.execute_gate_suite(gate_ids, context)
    report = gating_framework.generate_gating_report(results)

    return {
        'suite_name': suite_name,
        'execution_timestamp': datetime.utcnow().isoformat(),
        'gate_results': results,
        'report': report
    }


if __name__ == "__main__":
    # Example usage and testing
    import asyncio

    async def example_gate_function(context: Dict[str, Any]) -> Dict[str, Any]:
        """Example gate function."""
        return {
            'pipeline_pass_success_rate': 0.96,
            'data_quality_score': 0.88,
            'response_time_p95': 450
        }

    # Register example gate
    gating_framework.register_gate(
        'example_gate',
        'Example Quality Gate',
        GateSeverity.HIGH,
        example_gate_function
    )

    async def main():
        # Execute example gate
        result = await gating_framework.execute_gate('example_gate')
        print(f"Gate result: {result}")

        # Generate report
        report = gating_framework.generate_gating_report({'example_gate': result})
        print(f"Report: {json.dumps(report, indent=2, default=str)}")

    # Run example
    # asyncio.run(main())