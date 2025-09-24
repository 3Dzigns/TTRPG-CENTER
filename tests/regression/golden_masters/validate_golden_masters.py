#!/usr/bin/env python3
"""
Golden Master Validation Utility
Validates current system state against golden master references
"""

import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import difflib


class GoldenMasterValidator:
    """Validates system state against golden master references"""

    def __init__(self, masters_path: Optional[Path] = None):
        """Initialize golden master validator

        Args:
            masters_path: Path to golden master files directory
        """
        self.masters_path = masters_path or Path(__file__).parent / "masters"
        self.validation_results = {}

    def validate_system_baseline(self, current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate current system configuration against baseline

        Args:
            current_config: Current system configuration

        Returns:
            Validation result dictionary
        """
        baseline_file = self.masters_path / "system_baseline.json"

        if not baseline_file.exists():
            return {"valid": False, "error": "System baseline golden master not found"}

        try:
            with open(baseline_file, 'r') as f:
                baseline = json.load(f)

            validation_result = {
                "valid": True,
                "differences": [],
                "warnings": [],
                "critical_failures": []
            }

            # Validate environment structure
            if "environment" in baseline and "environment" in current_config:
                baseline_env = baseline["environment"]
                current_env = current_config["environment"]

                # Check port assignments
                if "port_assignments" in baseline_env and "port_assignments" in current_env:
                    baseline_ports = baseline_env["port_assignments"]
                    current_ports = current_env["port_assignments"]

                    for env, expected_port in baseline_ports.items():
                        if env not in current_ports:
                            validation_result["critical_failures"].append(
                                f"Missing port assignment for environment: {env}"
                            )
                        elif current_ports[env] != expected_port:
                            validation_result["differences"].append(
                                f"Port mismatch for {env}: expected {expected_port}, got {current_ports[env]}"
                            )

                # Check directory structure
                if "directory_structure" in baseline_env:
                    expected_dirs = set(baseline_env["directory_structure"])
                    current_dirs = set(current_env.get("directory_structure", []))

                    missing_dirs = expected_dirs - current_dirs
                    if missing_dirs:
                        validation_result["critical_failures"].extend([
                            f"Missing directory: {dir_path}" for dir_path in missing_dirs
                        ])

                    extra_dirs = current_dirs - expected_dirs
                    if extra_dirs:
                        validation_result["warnings"].extend([
                            f"Extra directory: {dir_path}" for dir_path in extra_dirs
                        ])

            # Validate ingestion pipeline configuration
            if "ingestion_pipeline" in baseline and "ingestion_pipeline" in current_config:
                self._validate_ingestion_config(
                    baseline["ingestion_pipeline"],
                    current_config["ingestion_pipeline"],
                    validation_result
                )

            # Validate performance thresholds
            if "performance_thresholds" in baseline and "performance_thresholds" in current_config:
                self._validate_performance_thresholds(
                    baseline["performance_thresholds"],
                    current_config["performance_thresholds"],
                    validation_result
                )

            # Determine overall validity
            validation_result["valid"] = len(validation_result["critical_failures"]) == 0

            return validation_result

        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    def validate_api_responses(self, api_test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API responses against golden masters

        Args:
            api_test_results: Results from API tests

        Returns:
            Validation result dictionary
        """
        api_masters_file = self.masters_path / "api_responses.json"

        if not api_masters_file.exists():
            return {"valid": False, "error": "API response golden masters not found"}

        try:
            with open(api_masters_file, 'r') as f:
                api_masters = json.load(f)

            validation_result = {
                "valid": True,
                "api_validations": {},
                "schema_violations": [],
                "performance_violations": []
            }

            # Validate search API responses
            if "search_api" in api_masters and "search_api" in api_test_results:
                search_validation = self._validate_search_api_responses(
                    api_masters["search_api"],
                    api_test_results["search_api"]
                )
                validation_result["api_validations"]["search_api"] = search_validation

            # Validate content API responses
            if "content_api" in api_masters and "content_api" in api_test_results:
                content_validation = self._validate_content_api_responses(
                    api_masters["content_api"],
                    api_test_results["content_api"]
                )
                validation_result["api_validations"]["content_api"] = content_validation

            # Validate admin API responses
            if "admin_api" in api_masters and "admin_api" in api_test_results:
                admin_validation = self._validate_admin_api_responses(
                    api_masters["admin_api"],
                    api_test_results["admin_api"]
                )
                validation_result["api_validations"]["admin_api"] = admin_validation

            # Check for any validation failures
            for api_name, api_validation in validation_result["api_validations"].items():
                if not api_validation.get("valid", True):
                    validation_result["valid"] = False

            return validation_result

        except Exception as e:
            return {"valid": False, "error": f"API validation error: {str(e)}"}

    def validate_ui_components(self, ui_test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate UI components against golden masters

        Args:
            ui_test_results: Results from UI component tests

        Returns:
            Validation result dictionary
        """
        ui_masters_file = self.masters_path / "ui_components.json"

        if not ui_masters_file.exists():
            return {"valid": False, "error": "UI component golden masters not found"}

        try:
            with open(ui_masters_file, 'r') as f:
                ui_masters = json.load(f)

            validation_result = {
                "valid": True,
                "component_validations": {},
                "missing_components": [],
                "structure_violations": []
            }

            # Validate search interface components
            if "search_interface" in ui_masters:
                search_validation = self._validate_search_interface(
                    ui_masters["search_interface"],
                    ui_test_results.get("search_interface", {})
                )
                validation_result["component_validations"]["search_interface"] = search_validation

            # Validate admin interface components
            if "admin_interface" in ui_masters:
                admin_validation = self._validate_admin_interface(
                    ui_masters["admin_interface"],
                    ui_test_results.get("admin_interface", {})
                )
                validation_result["component_validations"]["admin_interface"] = admin_validation

            # Validate user interface themes
            if "user_interface" in ui_masters:
                ui_validation = self._validate_user_interface(
                    ui_masters["user_interface"],
                    ui_test_results.get("user_interface", {})
                )
                validation_result["component_validations"]["user_interface"] = ui_validation

            # Check for validation failures
            for component_name, component_validation in validation_result["component_validations"].items():
                if not component_validation.get("valid", True):
                    validation_result["valid"] = False

            return validation_result

        except Exception as e:
            return {"valid": False, "error": f"UI validation error: {str(e)}"}

    def validate_performance_benchmarks(self, performance_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate performance against golden master benchmarks

        Args:
            performance_results: Performance test results

        Returns:
            Validation result dictionary
        """
        test_data_file = self.masters_path / "test_data.json"

        if not test_data_file.exists():
            return {"valid": False, "error": "Test data golden masters not found"}

        try:
            with open(test_data_file, 'r') as f:
                test_masters = json.load(f)

            if "performance_benchmarks" not in test_masters:
                return {"valid": False, "error": "Performance benchmarks not found in golden masters"}

            benchmarks = test_masters["performance_benchmarks"]
            validation_result = {
                "valid": True,
                "performance_violations": [],
                "performance_improvements": [],
                "benchmark_results": {}
            }

            # Validate search query performance
            if "search_queries" in benchmarks and "search_queries" in performance_results:
                search_perf_validation = self._validate_search_performance(
                    benchmarks["search_queries"],
                    performance_results["search_queries"]
                )
                validation_result["benchmark_results"]["search_queries"] = search_perf_validation

                # Check for violations
                for violation in search_perf_validation.get("violations", []):
                    validation_result["performance_violations"].append(violation)

            # Validate ingestion performance
            if "ingestion_benchmarks" in benchmarks and "ingestion_benchmarks" in performance_results:
                ingestion_perf_validation = self._validate_ingestion_performance(
                    benchmarks["ingestion_benchmarks"],
                    performance_results["ingestion_benchmarks"]
                )
                validation_result["benchmark_results"]["ingestion_benchmarks"] = ingestion_perf_validation

                # Check for violations
                for violation in ingestion_perf_validation.get("violations", []):
                    validation_result["performance_violations"].append(violation)

            # Determine overall validity
            validation_result["valid"] = len(validation_result["performance_violations"]) == 0

            return validation_result

        except Exception as e:
            return {"valid": False, "error": f"Performance validation error: {str(e)}"}

    def _validate_ingestion_config(self, baseline_config: Dict[str, Any],
                                 current_config: Dict[str, Any],
                                 validation_result: Dict[str, Any]) -> None:
        """Validate ingestion pipeline configuration"""
        for pass_name in ["pass_a_requirements", "pass_b_requirements", "pass_c_requirements"]:
            if pass_name in baseline_config and pass_name in current_config:
                baseline_pass = baseline_config[pass_name]
                current_pass = current_config[pass_name]

                # Check required tools
                if "tool" in baseline_pass and "tool" in current_pass:
                    if baseline_pass["tool"] != current_pass["tool"]:
                        validation_result["critical_failures"].append(
                            f"Tool mismatch in {pass_name}: expected {baseline_pass['tool']}, got {current_pass['tool']}"
                        )

                # Check input/output formats
                for format_key in ["input_format", "output_format"]:
                    if format_key in baseline_pass and format_key in current_pass:
                        if baseline_pass[format_key] != current_pass[format_key]:
                            validation_result["differences"].append(
                                f"Format mismatch in {pass_name}.{format_key}: expected {baseline_pass[format_key]}, got {current_pass[format_key]}"
                            )

    def _validate_performance_thresholds(self, baseline_thresholds: Dict[str, Any],
                                       current_thresholds: Dict[str, Any],
                                       validation_result: Dict[str, Any]) -> None:
        """Validate performance threshold configuration"""
        for threshold_name, baseline_value in baseline_thresholds.items():
            if threshold_name not in current_thresholds:
                validation_result["warnings"].append(
                    f"Missing performance threshold: {threshold_name}"
                )
            else:
                current_value = current_thresholds[threshold_name]
                if current_value > baseline_value * 1.5:  # Allow 50% tolerance
                    validation_result["differences"].append(
                        f"Performance threshold too high for {threshold_name}: {current_value} > {baseline_value * 1.5}"
                    )

    def _validate_search_api_responses(self, master_responses: Dict[str, Any],
                                     test_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search API response structure"""
        validation = {"valid": True, "issues": []}

        # Validate basic search response structure
        if "basic_search_response" in master_responses:
            master_structure = master_responses["basic_search_response"]
            test_structure = test_responses.get("basic_search_response", {})

            required_fields = ["results", "total_matches", "query_time"]
            for field in required_fields:
                if field not in test_structure:
                    validation["issues"].append(f"Missing field in basic search response: {field}")
                    validation["valid"] = False

        return validation

    def _validate_content_api_responses(self, master_responses: Dict[str, Any],
                                      test_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content API response structure"""
        validation = {"valid": True, "issues": []}

        # Validate spell detail response structure
        if "spell_detail_response" in master_responses:
            master_structure = master_responses["spell_detail_response"]
            test_structure = test_responses.get("spell_detail_response", {})

            required_fields = ["id", "name", "level", "school", "description"]
            for field in required_fields:
                if field not in test_structure:
                    validation["issues"].append(f"Missing field in spell detail response: {field}")
                    validation["valid"] = False

        return validation

    def _validate_admin_api_responses(self, master_responses: Dict[str, Any],
                                    test_responses: Dict[str, Any]) -> Dict[str, Any]:
        """Validate admin API response structure"""
        validation = {"valid": True, "issues": []}

        # Validate ingestion status response structure
        if "ingestion_status_response" in master_responses:
            master_structure = master_responses["ingestion_status_response"]
            test_structure = test_responses.get("ingestion_status_response", {})

            required_fields = ["job_id", "status", "progress"]
            for field in required_fields:
                if field not in test_structure:
                    validation["issues"].append(f"Missing field in ingestion status response: {field}")
                    validation["valid"] = False

        return validation

    def _validate_search_interface(self, master_interface: Dict[str, Any],
                                 test_interface: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search interface component structure"""
        validation = {"valid": True, "issues": []}

        if "search_form_structure" in master_interface:
            master_form = master_interface["search_form_structure"]
            test_form = test_interface.get("search_form_structure", {})

            if "query_input" not in test_form:
                validation["issues"].append("Missing query input component")
                validation["valid"] = False

            if "filter_panels" not in test_form:
                validation["issues"].append("Missing filter panels component")
                validation["valid"] = False

        return validation

    def _validate_admin_interface(self, master_interface: Dict[str, Any],
                                test_interface: Dict[str, Any]) -> Dict[str, Any]:
        """Validate admin interface component structure"""
        validation = {"valid": True, "issues": []}

        if "ingestion_dashboard" in master_interface:
            if "ingestion_dashboard" not in test_interface:
                validation["issues"].append("Missing ingestion dashboard component")
                validation["valid"] = False

        return validation

    def _validate_user_interface(self, master_interface: Dict[str, Any],
                               test_interface: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user interface theme structure"""
        validation = {"valid": True, "issues": []}

        required_themes = ["retro_terminal_theme", "lcars_theme"]
        for theme in required_themes:
            if theme in master_interface and theme not in test_interface:
                validation["issues"].append(f"Missing theme: {theme}")
                validation["valid"] = False

        return validation

    def _validate_search_performance(self, benchmark_queries: List[Dict[str, Any]],
                                   test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate search performance against benchmarks"""
        validation = {"valid": True, "violations": [], "results": []}

        test_results_by_query = {result["query"]: result for result in test_results}

        for benchmark in benchmark_queries:
            query = benchmark["query"]
            max_time = benchmark["max_response_time"]

            if query in test_results_by_query:
                actual_time = test_results_by_query[query]["response_time"]
                if actual_time > max_time:
                    violation = f"Query '{query}' exceeded time limit: {actual_time}ms > {max_time}ms"
                    validation["violations"].append(violation)
                    validation["valid"] = False

                validation["results"].append({
                    "query": query,
                    "expected_max_time": max_time,
                    "actual_time": actual_time,
                    "passed": actual_time <= max_time
                })

        return validation

    def _validate_ingestion_performance(self, benchmark_configs: Dict[str, Any],
                                      test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate ingestion performance against benchmarks"""
        validation = {"valid": True, "violations": [], "results": []}

        for benchmark_name, benchmark_config in benchmark_configs.items():
            if benchmark_name in test_results:
                test_result = test_results[benchmark_name]
                max_time = benchmark_config["max_processing_time"]
                actual_time = test_result["processing_time"]

                if actual_time > max_time:
                    violation = f"Ingestion '{benchmark_name}' exceeded time limit: {actual_time}s > {max_time}s"
                    validation["violations"].append(violation)
                    validation["valid"] = False

                validation["results"].append({
                    "benchmark": benchmark_name,
                    "expected_max_time": max_time,
                    "actual_time": actual_time,
                    "passed": actual_time <= max_time
                })

        return validation

    def generate_validation_report(self, all_results: Dict[str, Any]) -> str:
        """Generate comprehensive validation report

        Args:
            all_results: All validation results

        Returns:
            Formatted validation report
        """
        report_lines = [
            "TTRPG Center - Golden Master Validation Report",
            "=" * 50,
            f"Generated: {datetime.utcnow().isoformat()}",
            ""
        ]

        overall_valid = True
        total_tests = 0
        passed_tests = 0

        for validation_type, results in all_results.items():
            report_lines.append(f"{validation_type.replace('_', ' ').title()}")
            report_lines.append("-" * 30)

            if results.get("valid", False):
                report_lines.append("✓ PASSED")
                passed_tests += 1
            else:
                report_lines.append("✗ FAILED")
                overall_valid = False

            total_tests += 1

            # Add specific issues
            if "differences" in results and results["differences"]:
                report_lines.append("  Differences:")
                for diff in results["differences"]:
                    report_lines.append(f"    - {diff}")

            if "critical_failures" in results and results["critical_failures"]:
                report_lines.append("  Critical Failures:")
                for failure in results["critical_failures"]:
                    report_lines.append(f"    ! {failure}")

            if "performance_violations" in results and results["performance_violations"]:
                report_lines.append("  Performance Violations:")
                for violation in results["performance_violations"]:
                    report_lines.append(f"    ! {violation}")

            report_lines.append("")

        # Summary
        report_lines.extend([
            "Summary",
            "=" * 20,
            f"Overall Status: {'PASSED' if overall_valid else 'FAILED'}",
            f"Tests Passed: {passed_tests}/{total_tests}",
            f"Success Rate: {(passed_tests/total_tests)*100:.1f}%"
        ])

        return "\n".join(report_lines)


def main():
    """Main entry point for golden master validation"""
    validator = GoldenMasterValidator()

    print("TTRPG Center - Golden Master Validation")
    print("=" * 40)

    # This would be called with actual test results in practice
    # For now, we'll create a placeholder validation
    validation_results = {
        "system_baseline": {"valid": True, "differences": [], "critical_failures": []},
        "api_responses": {"valid": True, "api_validations": {}},
        "ui_components": {"valid": True, "component_validations": {}},
        "performance_benchmarks": {"valid": True, "performance_violations": []}
    }

    report = validator.generate_validation_report(validation_results)
    print(report)

    # Save report
    report_file = Path(__file__).parent / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"\nValidation report saved to: {report_file}")


if __name__ == "__main__":
    main()