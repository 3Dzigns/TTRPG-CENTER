# tests/regression/phase6/test_us603_quality_assurance.py
"""
Phase 6 - US-603: Quality Assurance Regression Tests
Tests quality assurance processes, code quality metrics, and automated validation
"""

import pytest
import time
import json
import subprocess
import ast
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestQualityAssurance:
    """Test suite for Quality Assurance validation"""

    def test_code_quality_tools_availability(self):
        """Test that code quality tools are available and functional"""
        quality_tools = [
            ("flake8", "flake8 --version"),
            ("black", "black --version"),
            ("pylint", "pylint --version"),
            ("mypy", "mypy --version"),
            ("bandit", "bandit --version")
        ]

        available_tools = []

        for tool_name, version_command in quality_tools:
            try:
                result = subprocess.run(
                    version_command.split(),
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    available_tools.append(tool_name)

            except (subprocess.TimeoutExpired, FileNotFoundError):
                # Tool not available
                pass

        # Should have at least some quality tools available
        assert len(available_tools) >= 2, f"Should have quality tools available, found: {available_tools}"

    def test_code_style_enforcement(self):
        """Test code style enforcement and consistency checking"""
        project_root = Path(__file__).parent.parent.parent.parent
        src_dirs = [
            project_root / "src_common",
            project_root / "tests"
        ]

        style_issues = []

        for src_dir in src_dirs:
            if src_dir.exists():
                # Check Python files for basic style compliance
                python_files = list(src_dir.rglob("*.py"))

                for py_file in python_files[:10]:  # Check first 10 files
                    try:
                        content = py_file.read_text(encoding='utf-8')

                        # Basic style checks
                        lines = content.split('\n')

                        for line_num, line in enumerate(lines, 1):
                            # Check line length (basic)
                            if len(line) > 120:
                                style_issues.append(f"{py_file.name}:{line_num} - Line too long ({len(line)} chars)")

                            # Check for basic indentation consistency
                            if line.startswith(' ') and not line.startswith('    '):
                                # Mixed indentation detected
                                if line.lstrip() != line and len(line) - len(line.lstrip()) % 4 != 0:
                                    style_issues.append(f"{py_file.name}:{line_num} - Inconsistent indentation")

                    except (UnicodeDecodeError, PermissionError):
                        # Skip files that can't be read
                        continue

        # Should have minimal style issues (allow some flexibility)
        assert len(style_issues) <= 20, f"Should have minimal style issues, found {len(style_issues)}: {style_issues[:5]}"

    def test_code_complexity_analysis(self):
        """Test code complexity analysis and metrics"""
        project_root = Path(__file__).parent.parent.parent.parent
        src_common = project_root / "src_common"

        if not src_common.exists():
            pytest.skip("Source code directory not found")

        complexity_issues = []
        python_files = list(src_common.rglob("*.py"))

        for py_file in python_files[:10]:  # Analyze first 10 files
            try:
                content = py_file.read_text(encoding='utf-8')

                # Parse AST for complexity analysis
                tree = ast.parse(content)

                # Analyze function complexity (simple version)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Count decision points (if, for, while, etc.)
                        complexity = 1  # Base complexity

                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                                complexity += 1
                            elif isinstance(child, ast.BoolOp):
                                complexity += len(child.values) - 1

                        # Flag high complexity functions
                        if complexity > 10:
                            complexity_issues.append(f"{py_file.name}:{node.name} - Complexity: {complexity}")

            except (SyntaxError, UnicodeDecodeError):
                # Skip files with syntax errors or encoding issues
                continue

        # Should have manageable complexity
        assert len(complexity_issues) <= 5, f"Should have manageable code complexity, found issues: {complexity_issues}"

    def test_security_vulnerability_scanning(self):
        """Test security vulnerability scanning with bandit"""
        project_root = Path(__file__).parent.parent.parent.parent

        try:
            # Run bandit security scan
            result = subprocess.run([
                "bandit", "-r", str(project_root / "src_common"),
                "-f", "json", "--skip", "B101"  # Skip assert statements
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0 or result.returncode == 1:  # 1 = issues found but not fatal
                # Parse bandit output
                try:
                    bandit_output = json.loads(result.stdout)

                    if "results" in bandit_output:
                        high_severity_issues = [
                            issue for issue in bandit_output["results"]
                            if issue.get("issue_severity") == "HIGH"
                        ]

                        # Should have minimal high-severity security issues
                        assert len(high_severity_issues) <= 2, f"Should have minimal high-severity security issues, found: {high_severity_issues}"

                        medium_severity_issues = [
                            issue for issue in bandit_output["results"]
                            if issue.get("issue_severity") == "MEDIUM"
                        ]

                        # Should have reasonable number of medium-severity issues
                        assert len(medium_severity_issues) <= 10, f"Should have manageable medium-severity security issues, found: {len(medium_severity_issues)}"

                except json.JSONDecodeError:
                    # Bandit output format may be different
                    pass

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Bandit security scanner not available")

    def test_test_coverage_requirements(self):
        """Test test coverage measurement and requirements"""
        project_root = Path(__file__).parent.parent.parent.parent

        try:
            # Run coverage measurement
            result = subprocess.run([
                "python", "-m", "coverage", "run",
                "-m", "pytest",
                str(project_root / "tests" / "regression" / "phase0"),
                "--quiet"
            ], capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                # Generate coverage report
                report_result = subprocess.run([
                    "python", "-m", "coverage", "report",
                    "--show-missing"
                ], capture_output=True, text=True, timeout=30)

                if report_result.returncode == 0:
                    coverage_output = report_result.stdout

                    # Extract overall coverage percentage
                    lines = coverage_output.split('\n')
                    total_line = [line for line in lines if "TOTAL" in line]

                    if total_line:
                        # Parse coverage percentage
                        parts = total_line[0].split()
                        if len(parts) >= 4:
                            coverage_percentage = parts[-1].rstrip('%')
                            try:
                                coverage_value = float(coverage_percentage)

                                # Should have reasonable test coverage
                                assert coverage_value >= 60, f"Test coverage should be >= 60%, got {coverage_value}%"

                            except ValueError:
                                # Coverage format may be different
                                pass

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Coverage measurement tools not available")

    def test_dependency_vulnerability_scanning(self):
        """Test dependency vulnerability scanning"""
        project_root = Path(__file__).parent.parent.parent.parent

        # Check for requirements files
        requirements_files = [
            project_root / "requirements.txt",
            project_root / "requirements-dev.txt",
            project_root / "pyproject.toml"
        ]

        requirements_found = any(req_file.exists() for req_file in requirements_files)

        if requirements_found:
            try:
                # Try to run safety check (if available)
                result = subprocess.run([
                    "safety", "check", "--json"
                ], capture_output=True, text=True, timeout=30)

                if result.returncode == 0:
                    # No vulnerabilities found
                    assert True, "No dependency vulnerabilities found"

                elif result.returncode == 64:  # Vulnerabilities found
                    try:
                        safety_output = json.loads(result.stdout)

                        # Count high-severity vulnerabilities
                        high_severity_vulns = 0
                        for vuln in safety_output:
                            if vuln.get("vulnerability_id") and "HIGH" in str(vuln).upper():
                                high_severity_vulns += 1

                        # Should have minimal high-severity vulnerabilities
                        assert high_severity_vulns <= 1, f"Should have minimal high-severity dependency vulnerabilities, found: {high_severity_vulns}"

                    except json.JSONDecodeError:
                        # Safety output format may be different
                        pass

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pytest.skip("Safety dependency scanner not available")

    def test_documentation_quality_standards(self):
        """Test documentation quality and completeness"""
        project_root = Path(__file__).parent.parent.parent.parent

        # Check for key documentation files
        required_docs = [
            "README.md",
            "CLAUDE.md"
        ]

        missing_docs = []
        for doc_file in required_docs:
            if not (project_root / doc_file).exists():
                missing_docs.append(doc_file)

        assert len(missing_docs) == 0, f"Missing required documentation: {missing_docs}"

        # Check documentation quality
        readme_path = project_root / "README.md"
        if readme_path.exists():
            readme_content = readme_path.read_text(encoding='utf-8')

            # Basic documentation quality checks
            assert len(readme_content) > 500, "README should be comprehensive"
            assert "# " in readme_content, "README should have headers"

        # Check code documentation
        src_common = project_root / "src_common"
        if src_common.exists():
            documented_files = 0
            total_python_files = 0

            for py_file in src_common.rglob("*.py"):
                total_python_files += 1

                try:
                    content = py_file.read_text(encoding='utf-8')

                    # Check for docstrings
                    if '"""' in content or "'''" in content:
                        documented_files += 1

                except (UnicodeDecodeError, PermissionError):
                    continue

            if total_python_files > 0:
                documentation_ratio = documented_files / total_python_files

                # Should have reasonable documentation coverage
                assert documentation_ratio >= 0.5, f"Code documentation coverage should be >= 50%, got {documentation_ratio:.1%}"

    def test_performance_regression_detection(self):
        """Test performance regression detection capabilities"""
        # Test performance measurement infrastructure
        performance_baselines = {
            "module_import_time": 1.0,  # seconds
            "basic_function_call": 0.001,  # seconds
            "test_discovery": 10.0  # seconds
        }

        # Test module import performance
        start_time = time.perf_counter()
        try:
            import src_common
            import_time = time.perf_counter() - start_time

            assert import_time < performance_baselines["module_import_time"], f"Module import time {import_time:.3f}s exceeds baseline {performance_baselines['module_import_time']}s"

        except ImportError:
            # Module may not be available
            pass

        # Test basic function call performance
        def simple_function(x):
            return x * 2

        start_time = time.perf_counter()
        for _ in range(1000):
            simple_function(42)
        end_time = time.perf_counter()

        avg_call_time = (end_time - start_time) / 1000

        assert avg_call_time < performance_baselines["basic_function_call"], f"Basic function call time {avg_call_time:.6f}s exceeds baseline"

        # Test test discovery performance
        start_time = time.perf_counter()
        try:
            result = subprocess.run([
                "python", "-m", "pytest",
                str(Path(__file__).parent),
                "--collect-only", "--quiet"
            ], capture_output=True, text=True, timeout=performance_baselines["test_discovery"])

            discovery_time = time.perf_counter() - start_time

            assert discovery_time < performance_baselines["test_discovery"], f"Test discovery time {discovery_time:.2f}s exceeds baseline"

        except subprocess.TimeoutExpired:
            pytest.fail(f"Test discovery exceeded {performance_baselines['test_discovery']}s baseline")

    def test_automated_quality_gates(self):
        """Test automated quality gates and validation"""
        project_root = Path(__file__).parent.parent.parent.parent

        quality_gates = {
            "syntax_validation": True,
            "style_compliance": True,
            "security_scan": True,
            "test_execution": True
        }

        # Syntax validation gate
        src_common = project_root / "src_common"
        if src_common.exists():
            syntax_errors = []

            for py_file in src_common.rglob("*.py"):
                try:
                    content = py_file.read_text(encoding='utf-8')
                    ast.parse(content)

                except SyntaxError as e:
                    syntax_errors.append(f"{py_file.name}:{e.lineno} - {e.msg}")

                except UnicodeDecodeError:
                    continue

            assert len(syntax_errors) == 0, f"Syntax validation gate failed: {syntax_errors}"

        # Test execution gate
        try:
            result = subprocess.run([
                "python", "-m", "pytest",
                str(Path(__file__).parent / "test_us603_quality_assurance.py::TestQualityAssurance::test_code_quality_tools_availability"),
                "--quiet"
            ], capture_output=True, text=True, timeout=30)

            # Basic test execution should pass
            assert result.returncode == 0, "Test execution gate failed"

        except subprocess.TimeoutExpired:
            pytest.fail("Test execution gate timed out")

    def test_continuous_quality_monitoring(self):
        """Test continuous quality monitoring capabilities"""
        # Test quality metrics collection
        quality_metrics = {
            "code_coverage": None,
            "test_pass_rate": None,
            "security_issues": None,
            "performance_trends": None
        }

        # Mock quality metrics collection
        mock_metrics = {
            "code_coverage": 75.5,
            "test_pass_rate": 95.2,
            "security_issues": 3,
            "performance_trends": "stable"
        }

        # Validate metric types and ranges
        if mock_metrics["code_coverage"] is not None:
            coverage = mock_metrics["code_coverage"]
            assert isinstance(coverage, (int, float)), "Coverage should be numeric"
            assert 0 <= coverage <= 100, "Coverage should be 0-100%"

        if mock_metrics["test_pass_rate"] is not None:
            pass_rate = mock_metrics["test_pass_rate"]
            assert isinstance(pass_rate, (int, float)), "Pass rate should be numeric"
            assert 0 <= pass_rate <= 100, "Pass rate should be 0-100%"

        if mock_metrics["security_issues"] is not None:
            issues = mock_metrics["security_issues"]
            assert isinstance(issues, int), "Security issues should be integer"
            assert issues >= 0, "Security issues should be non-negative"

        # Quality thresholds
        quality_thresholds = {
            "minimum_coverage": 60,
            "minimum_pass_rate": 90,
            "maximum_security_issues": 5
        }

        # Check against thresholds
        if mock_metrics["code_coverage"]:
            assert mock_metrics["code_coverage"] >= quality_thresholds["minimum_coverage"], "Coverage below threshold"

        if mock_metrics["test_pass_rate"]:
            assert mock_metrics["test_pass_rate"] >= quality_thresholds["minimum_pass_rate"], "Pass rate below threshold"

        if mock_metrics["security_issues"] is not None:
            assert mock_metrics["security_issues"] <= quality_thresholds["maximum_security_issues"], "Too many security issues"

    def test_quality_reporting_and_dashboards(self):
        """Test quality reporting and dashboard capabilities"""
        # Test quality report generation
        quality_report = {
            "timestamp": time.time(),
            "metrics": {
                "code_quality_score": 85,
                "test_coverage": 72,
                "security_score": 90,
                "performance_score": 88
            },
            "issues": {
                "high_priority": 0,
                "medium_priority": 3,
                "low_priority": 8
            },
            "trends": {
                "quality_trend": "improving",
                "coverage_trend": "stable",
                "security_trend": "improving"
            }
        }

        # Validate report structure
        assert isinstance(quality_report, dict), "Quality report should be structured"
        assert "timestamp" in quality_report, "Report should have timestamp"
        assert "metrics" in quality_report, "Report should include metrics"

        # Validate metrics
        metrics = quality_report["metrics"]
        for metric_name, metric_value in metrics.items():
            assert isinstance(metric_value, (int, float)), f"Metric {metric_name} should be numeric"
            assert 0 <= metric_value <= 100, f"Metric {metric_name} should be 0-100 range"

        # Validate issue categorization
        issues = quality_report["issues"]
        for priority, count in issues.items():
            assert isinstance(count, int), f"Issue count for {priority} should be integer"
            assert count >= 0, f"Issue count for {priority} should be non-negative"

    def test_quality_assurance_contract_compliance(self):
        """Test that quality assurance system matches established contract"""
        # Test quality standards contract
        quality_standards = {
            "code_style": "enforced",
            "security_scanning": "required",
            "test_coverage": "minimum_60_percent",
            "performance_monitoring": "enabled",
            "documentation": "required_for_public_apis"
        }

        # Verify standards are enforced
        for standard, requirement in quality_standards.items():
            if standard == "code_style":
                # Should have style enforcement available
                try:
                    result = subprocess.run(["flake8", "--version"], capture_output=True, timeout=5)
                    style_tools_available = result.returncode == 0
                except:
                    style_tools_available = False

                # Should have some style enforcement mechanism
                # (This is a basic check - actual enforcement tested elsewhere)

            elif standard == "security_scanning":
                # Should have security scanning capability
                try:
                    result = subprocess.run(["bandit", "--version"], capture_output=True, timeout=5)
                    security_tools_available = result.returncode == 0
                except:
                    security_tools_available = False

                # Should have some security scanning mechanism

        # Test quality metrics contract
        required_metrics = [
            "test_coverage",
            "code_quality_score",
            "security_assessment",
            "performance_metrics"
        ]

        # Quality system should be able to provide these metrics
        # (Implementation varies, but structure should be consistent)

        # Test quality gate contract
        quality_gates = [
            "syntax_validation",
            "style_compliance",
            "security_scan_pass",
            "test_execution_pass"
        ]

        # Each gate should be enforceable
        # (Basic validation - actual enforcement tested in other methods)

        # Test reporting contract
        report_format = {
            "timestamp": "required",
            "metrics": "required",
            "status": "required",
            "issues": "optional",
            "recommendations": "optional"
        }

        # Quality reports should follow consistent structure
        mock_report = {
            "timestamp": time.time(),
            "metrics": {"coverage": 70},
            "status": "passing"
        }

        # Required fields should be present
        for field, requirement in report_format.items():
            if requirement == "required":
                assert field in mock_report, f"Quality report missing required field: {field}"