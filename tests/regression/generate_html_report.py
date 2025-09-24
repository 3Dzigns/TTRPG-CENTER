#!/usr/bin/env python3
"""
Regression Test HTML Report Generator
Generates comprehensive HTML reports from regression test results
"""

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import html
import base64


@dataclass
class TestResult:
    """Represents a single test result"""
    name: str
    status: str  # passed, failed, skipped, error
    duration: float
    message: str = ""
    traceback: str = ""
    phase: str = ""
    category: str = ""


@dataclass
class TestSuiteResult:
    """Represents a test suite result"""
    name: str
    tests: List[TestResult]
    duration: float
    setup_time: float = 0.0
    teardown_time: float = 0.0


class RegressionReportGenerator:
    """Generates HTML reports from regression test results"""

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize report generator

        Args:
            output_dir: Directory to save reports (defaults to current directory)
        """
        self.output_dir = output_dir or Path(__file__).parent / "reports"
        self.output_dir.mkdir(exist_ok=True)

    def parse_pytest_xml(self, xml_file: Path) -> List[TestSuiteResult]:
        """Parse pytest XML results

        Args:
            xml_file: Path to pytest XML results file

        Returns:
            List of test suite results
        """
        if not xml_file.exists():
            return []

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            test_suites = []

            # Handle both pytest and standard JUnit XML formats
            if root.tag == 'testsuite':
                # Single test suite
                test_suites.append(self._parse_testsuite_element(root))
            elif root.tag == 'testsuites':
                # Multiple test suites
                for testsuite in root.findall('testsuite'):
                    test_suites.append(self._parse_testsuite_element(testsuite))

            return test_suites

        except Exception as e:
            print(f"Error parsing XML file {xml_file}: {e}")
            return []

    def _parse_testsuite_element(self, testsuite: ET.Element) -> TestSuiteResult:
        """Parse a testsuite XML element

        Args:
            testsuite: XML testsuite element

        Returns:
            TestSuiteResult object
        """
        suite_name = testsuite.get('name', 'Unknown Suite')
        suite_time = float(testsuite.get('time', 0))

        tests = []

        for testcase in testsuite.findall('testcase'):
            test_name = testcase.get('name', 'Unknown Test')
            test_time = float(testcase.get('time', 0))
            test_classname = testcase.get('classname', '')

            # Determine test phase and category from classname or name
            phase = self._extract_phase_from_name(test_classname + test_name)
            category = self._extract_category_from_name(test_classname + test_name)

            # Check for failure, error, or skip
            failure = testcase.find('failure')
            error = testcase.find('error')
            skip = testcase.find('skipped')

            if failure is not None:
                status = 'failed'
                message = failure.get('message', '')
                traceback = failure.text or ''
            elif error is not None:
                status = 'error'
                message = error.get('message', '')
                traceback = error.text or ''
            elif skip is not None:
                status = 'skipped'
                message = skip.get('message', '')
                traceback = ''
            else:
                status = 'passed'
                message = ''
                traceback = ''

            test_result = TestResult(
                name=test_name,
                status=status,
                duration=test_time,
                message=message,
                traceback=traceback,
                phase=phase,
                category=category
            )

            tests.append(test_result)

        return TestSuiteResult(
            name=suite_name,
            tests=tests,
            duration=suite_time
        )

    def _extract_phase_from_name(self, name: str) -> str:
        """Extract phase information from test name"""
        name_lower = name.lower()

        if 'phase0' in name_lower:
            return 'Phase 0'
        elif 'phase1' in name_lower:
            return 'Phase 1'
        elif 'phase2' in name_lower:
            return 'Phase 2'
        elif 'phase3' in name_lower:
            return 'Phase 3'
        elif 'phase4' in name_lower:
            return 'Phase 4'
        elif 'phase5' in name_lower:
            return 'Phase 5'
        elif 'phase6' in name_lower:
            return 'Phase 6'
        elif 'phase7' in name_lower:
            return 'Phase 7'
        elif 'fr0' in name_lower or 'feature_request' in name_lower:
            return 'Feature Requests'
        else:
            return 'Other'

    def _extract_category_from_name(self, name: str) -> str:
        """Extract category information from test name"""
        name_lower = name.lower()

        if 'ingestion' in name_lower:
            return 'Ingestion'
        elif 'search' in name_lower or 'query' in name_lower:
            return 'Search'
        elif 'ui' in name_lower or 'interface' in name_lower:
            return 'User Interface'
        elif 'admin' in name_lower:
            return 'Administration'
        elif 'api' in name_lower:
            return 'API'
        elif 'performance' in name_lower:
            return 'Performance'
        elif 'security' in name_lower:
            return 'Security'
        elif 'environment' in name_lower:
            return 'Environment'
        else:
            return 'Functional'

    def generate_html_report(self, test_suites: List[TestSuiteResult],
                           report_title: str = "TTRPG Center Regression Test Report") -> Path:
        """Generate comprehensive HTML report

        Args:
            test_suites: List of test suite results
            report_title: Title for the report

        Returns:
            Path to generated HTML report
        """
        # Calculate overall statistics
        total_tests = sum(len(suite.tests) for suite in test_suites)
        passed_tests = sum(1 for suite in test_suites for test in suite.tests if test.status == 'passed')
        failed_tests = sum(1 for suite in test_suites for test in suite.tests if test.status == 'failed')
        error_tests = sum(1 for suite in test_suites for test in suite.tests if test.status == 'error')
        skipped_tests = sum(1 for suite in test_suites for test in suite.tests if test.status == 'skipped')

        total_duration = sum(suite.duration for suite in test_suites)

        # Group tests by phase
        tests_by_phase = {}
        for suite in test_suites:
            for test in suite.tests:
                phase = test.phase
                if phase not in tests_by_phase:
                    tests_by_phase[phase] = []
                tests_by_phase[phase].append(test)

        # Generate HTML content
        html_content = self._generate_html_template(
            report_title=report_title,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            error_tests=error_tests,
            skipped_tests=skipped_tests,
            total_duration=total_duration,
            test_suites=test_suites,
            tests_by_phase=tests_by_phase
        )

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"regression_report_{timestamp}.html"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Also create a latest.html symlink/copy
        latest_file = self.output_dir / "regression_report_latest.html"
        with open(latest_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return report_file

    def _generate_html_template(self, **kwargs) -> str:
        """Generate HTML template with test results"""
        report_title = kwargs['report_title']
        total_tests = kwargs['total_tests']
        passed_tests = kwargs['passed_tests']
        failed_tests = kwargs['failed_tests']
        error_tests = kwargs['error_tests']
        skipped_tests = kwargs['skipped_tests']
        total_duration = kwargs['total_duration']
        test_suites = kwargs['test_suites']
        tests_by_phase = kwargs['tests_by_phase']

        # Calculate success rate
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Generate phase statistics
        phase_stats = self._generate_phase_statistics(tests_by_phase)

        # Generate test suite sections
        suite_sections = self._generate_suite_sections(test_suites)

        # Generate failure details
        failure_details = self._generate_failure_details(test_suites)

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(report_title)}</title>
    <style>
        {self._get_css_styles()}
    </style>
    <script>
        {self._get_javascript()}
    </script>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>{html.escape(report_title)}</h1>
            <div class="report-info">
                <span>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                <span>Duration: {total_duration:.2f}s</span>
            </div>
        </header>

        <div class="summary-section">
            <h2>Test Summary</h2>
            <div class="summary-grid">
                <div class="summary-card total">
                    <div class="summary-number">{total_tests}</div>
                    <div class="summary-label">Total Tests</div>
                </div>
                <div class="summary-card passed">
                    <div class="summary-number">{passed_tests}</div>
                    <div class="summary-label">Passed</div>
                </div>
                <div class="summary-card failed">
                    <div class="summary-number">{failed_tests}</div>
                    <div class="summary-label">Failed</div>
                </div>
                <div class="summary-card error">
                    <div class="summary-number">{error_tests}</div>
                    <div class="summary-label">Errors</div>
                </div>
                <div class="summary-card skipped">
                    <div class="summary-number">{skipped_tests}</div>
                    <div class="summary-label">Skipped</div>
                </div>
                <div class="summary-card success-rate">
                    <div class="summary-number">{success_rate:.1f}%</div>
                    <div class="summary-label">Success Rate</div>
                </div>
            </div>
        </div>

        <div class="phase-section">
            <h2>Results by Phase</h2>
            {phase_stats}
        </div>

        <div class="navigation">
            <h2>Quick Navigation</h2>
            <div class="nav-buttons">
                <button onclick="showSection('all')">All Tests</button>
                <button onclick="showSection('failed')">Failed Tests</button>
                <button onclick="showSection('passed')">Passed Tests</button>
                <button onclick="showSection('skipped')">Skipped Tests</button>
            </div>
        </div>

        <div class="test-suites-section">
            <h2>Test Suites</h2>
            {suite_sections}
        </div>

        {failure_details}

        <footer class="footer">
            <p>TTRPG Center Regression Test Report - Generated by automated testing system</p>
        </footer>
    </div>
</body>
</html>
"""
        return html_content

    def _generate_phase_statistics(self, tests_by_phase: Dict[str, List[TestResult]]) -> str:
        """Generate phase statistics HTML"""
        if not tests_by_phase:
            return "<p>No phase data available.</p>"

        phase_html = ['<div class="phase-grid">']

        for phase, tests in sorted(tests_by_phase.items()):
            total = len(tests)
            passed = sum(1 for t in tests if t.status == 'passed')
            failed = sum(1 for t in tests if t.status == 'failed')
            errors = sum(1 for t in tests if t.status == 'error')
            skipped = sum(1 for t in tests if t.status == 'skipped')

            success_rate = (passed / total * 100) if total > 0 else 0
            status_class = 'passed' if success_rate >= 90 else 'failed' if success_rate < 70 else 'warning'

            phase_html.append(f"""
                <div class="phase-card {status_class}">
                    <h3>{html.escape(phase)}</h3>
                    <div class="phase-stats">
                        <div class="phase-stat">
                            <span class="stat-number">{total}</span>
                            <span class="stat-label">Total</span>
                        </div>
                        <div class="phase-stat">
                            <span class="stat-number">{passed}</span>
                            <span class="stat-label">Passed</span>
                        </div>
                        <div class="phase-stat">
                            <span class="stat-number">{failed + errors}</span>
                            <span class="stat-label">Failed</span>
                        </div>
                        <div class="phase-stat">
                            <span class="stat-number">{success_rate:.1f}%</span>
                            <span class="stat-label">Success</span>
                        </div>
                    </div>
                </div>
            """)

        phase_html.append('</div>')
        return '\n'.join(phase_html)

    def _generate_suite_sections(self, test_suites: List[TestSuiteResult]) -> str:
        """Generate test suite sections HTML"""
        suite_html = []

        for suite in test_suites:
            total_tests = len(suite.tests)
            passed_tests = sum(1 for t in suite.tests if t.status == 'passed')
            failed_tests = sum(1 for t in suite.tests if t.status in ['failed', 'error'])

            suite_status = 'passed' if failed_tests == 0 else 'failed'

            suite_html.append(f"""
                <div class="test-suite {suite_status}">
                    <h3 class="suite-header" onclick="toggleSuite('{suite.name}')">
                        <span class="suite-name">{html.escape(suite.name)}</span>
                        <span class="suite-stats">
                            {passed_tests}/{total_tests} passed ({suite.duration:.2f}s)
                        </span>
                        <span class="toggle-icon">▼</span>
                    </h3>
                    <div class="suite-tests" id="suite-{suite.name}">
                        {self._generate_test_rows(suite.tests)}
                    </div>
                </div>
            """)

        return '\n'.join(suite_html)

    def _generate_test_rows(self, tests: List[TestResult]) -> str:
        """Generate test result rows HTML"""
        test_html = []

        for test in tests:
            status_icon = {
                'passed': '✓',
                'failed': '✗',
                'error': '⚠',
                'skipped': '○'
            }.get(test.status, '?')

            test_html.append(f"""
                <div class="test-row {test.status}" data-status="{test.status}" data-phase="{test.phase}">
                    <span class="test-status">{status_icon}</span>
                    <span class="test-name">{html.escape(test.name)}</span>
                    <span class="test-phase">{html.escape(test.phase)}</span>
                    <span class="test-duration">{test.duration:.3f}s</span>
                    {self._generate_test_details(test)}
                </div>
            """)

        return '\n'.join(test_html)

    def _generate_test_details(self, test: TestResult) -> str:
        """Generate test details HTML"""
        if test.status in ['passed', 'skipped'] and not test.message:
            return ""

        details_html = f"""
            <div class="test-details">
                {f'<div class="test-message">{html.escape(test.message)}</div>' if test.message else ''}
                {f'<pre class="test-traceback">{html.escape(test.traceback)}</pre>' if test.traceback else ''}
            </div>
        """

        return details_html

    def _generate_failure_details(self, test_suites: List[TestSuiteResult]) -> str:
        """Generate detailed failure information"""
        failed_tests = []

        for suite in test_suites:
            for test in suite.tests:
                if test.status in ['failed', 'error']:
                    failed_tests.append((suite.name, test))

        if not failed_tests:
            return ""

        failure_html = ["""
            <div class="failure-section">
                <h2>Failure Details</h2>
        """]

        for suite_name, test in failed_tests:
            failure_html.append(f"""
                <div class="failure-detail">
                    <h4>{html.escape(test.name)} <span class="failure-suite">({html.escape(suite_name)})</span></h4>
                    <div class="failure-info">
                        <strong>Status:</strong> {test.status.title()}<br>
                        <strong>Duration:</strong> {test.duration:.3f}s<br>
                        <strong>Phase:</strong> {html.escape(test.phase)}<br>
                        <strong>Category:</strong> {html.escape(test.category)}
                    </div>
                    {f'<div class="failure-message"><strong>Message:</strong><br>{html.escape(test.message)}</div>' if test.message else ''}
                    {f'<div class="failure-traceback"><strong>Traceback:</strong><pre>{html.escape(test.traceback)}</pre></div>' if test.traceback else ''}
                </div>
            """)

        failure_html.append('</div>')
        return '\n'.join(failure_html)

    def _get_css_styles(self) -> str:
        """Get CSS styles for the HTML report"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            text-align: center;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }

        .report-info {
            display: flex;
            justify-content: center;
            gap: 2rem;
            font-size: 1.1rem;
            opacity: 0.9;
        }

        .summary-section {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .summary-card {
            text-align: center;
            padding: 1.5rem;
            border-radius: 8px;
            color: white;
        }

        .summary-card.total { background: #6c757d; }
        .summary-card.passed { background: #28a745; }
        .summary-card.failed { background: #dc3545; }
        .summary-card.error { background: #fd7e14; }
        .summary-card.skipped { background: #6f42c1; }
        .summary-card.success-rate { background: #17a2b8; }

        .summary-number {
            font-size: 2rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }

        .summary-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }

        .phase-section, .navigation, .test-suites-section, .failure-section {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .phase-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }

        .phase-card {
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 5px solid;
        }

        .phase-card.passed { border-left-color: #28a745; background: #f8fff9; }
        .phase-card.warning { border-left-color: #ffc107; background: #fffdf7; }
        .phase-card.failed { border-left-color: #dc3545; background: #fff8f8; }

        .phase-stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
            margin-top: 1rem;
        }

        .phase-stat {
            text-align: center;
        }

        .stat-number {
            display: block;
            font-size: 1.5rem;
            font-weight: bold;
            color: #495057;
        }

        .stat-label {
            font-size: 0.8rem;
            color: #6c757d;
        }

        .nav-buttons {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }

        .nav-buttons button {
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 5px;
            background: #007bff;
            color: white;
            cursor: pointer;
            transition: background 0.3s;
        }

        .nav-buttons button:hover {
            background: #0056b3;
        }

        .test-suite {
            border: 1px solid #dee2e6;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .test-suite.passed { border-left: 5px solid #28a745; }
        .test-suite.failed { border-left: 5px solid #dc3545; }

        .suite-header {
            padding: 1rem;
            background: #f8f9fa;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-radius: 8px 8px 0 0;
        }

        .suite-header:hover {
            background: #e9ecef;
        }

        .suite-tests {
            padding: 1rem;
            display: none;
        }

        .suite-tests.expanded {
            display: block;
        }

        .test-row {
            display: grid;
            grid-template-columns: 30px 1fr 100px 80px;
            gap: 1rem;
            padding: 0.5rem;
            border-bottom: 1px solid #f1f3f4;
            align-items: center;
        }

        .test-row.passed { background: #f8fff9; }
        .test-row.failed { background: #fff5f5; }
        .test-row.error { background: #fff8e1; }
        .test-row.skipped { background: #f3e5f5; }

        .test-status {
            font-size: 1.2rem;
            font-weight: bold;
        }

        .test-row.passed .test-status { color: #28a745; }
        .test-row.failed .test-status { color: #dc3545; }
        .test-row.error .test-status { color: #fd7e14; }
        .test-row.skipped .test-status { color: #6f42c1; }

        .test-name {
            font-weight: 500;
        }

        .test-phase {
            font-size: 0.9rem;
            color: #6c757d;
        }

        .test-duration {
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            color: #495057;
        }

        .test-details {
            grid-column: 1 / -1;
            margin-top: 0.5rem;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 5px;
        }

        .test-message {
            color: #721c24;
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .test-traceback {
            background: #2d3748;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 0.8rem;
            line-height: 1.4;
        }

        .failure-detail {
            border: 1px solid #f5c6cb;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background: #fff5f5;
        }

        .failure-detail h4 {
            color: #721c24;
            margin-bottom: 1rem;
        }

        .failure-suite {
            font-weight: normal;
            color: #6c757d;
            font-size: 0.9rem;
        }

        .failure-info {
            margin-bottom: 1rem;
            color: #495057;
        }

        .failure-message {
            margin-bottom: 1rem;
        }

        .failure-traceback pre {
            background: #2d3748;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 5px;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
        }

        .footer {
            text-align: center;
            padding: 2rem;
            color: #6c757d;
            border-top: 1px solid #dee2e6;
            margin-top: 2rem;
        }

        .hidden {
            display: none !important;
        }

        h2 {
            color: #495057;
            margin-bottom: 1rem;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 0.5rem;
        }

        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }

            .header h1 {
                font-size: 2rem;
            }

            .report-info {
                flex-direction: column;
                gap: 0.5rem;
            }

            .test-row {
                grid-template-columns: 30px 1fr;
                gap: 0.5rem;
            }

            .test-phase, .test-duration {
                grid-column: 2;
                font-size: 0.8rem;
            }
        }
        """

    def _get_javascript(self) -> str:
        """Get JavaScript for the HTML report"""
        return """
        function toggleSuite(suiteName) {
            const element = document.getElementById('suite-' + suiteName);
            const icon = element.previousElementSibling.querySelector('.toggle-icon');

            if (element.classList.contains('expanded')) {
                element.classList.remove('expanded');
                icon.textContent = '▼';
            } else {
                element.classList.add('expanded');
                icon.textContent = '▲';
            }
        }

        function showSection(status) {
            const testRows = document.querySelectorAll('.test-row');

            testRows.forEach(row => {
                if (status === 'all') {
                    row.classList.remove('hidden');
                } else {
                    const rowStatus = row.getAttribute('data-status');
                    if (status === 'failed' && (rowStatus === 'failed' || rowStatus === 'error')) {
                        row.classList.remove('hidden');
                    } else if (rowStatus === status) {
                        row.classList.remove('hidden');
                    } else {
                        row.classList.add('hidden');
                    }
                }
            });
        }

        // Expand first failed suite by default
        document.addEventListener('DOMContentLoaded', function() {
            const failedSuite = document.querySelector('.test-suite.failed .suite-tests');
            if (failedSuite) {
                failedSuite.classList.add('expanded');
                const icon = failedSuite.previousElementSibling.querySelector('.toggle-icon');
                if (icon) icon.textContent = '▲';
            }
        });
        """


def main():
    """Main entry point for HTML report generation"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate HTML regression test report')
    parser.add_argument('--xml-file', type=Path, help='Path to pytest XML results file')
    parser.add_argument('--output-dir', type=Path, help='Output directory for reports')
    parser.add_argument('--title', default='TTRPG Center Regression Test Report', help='Report title')

    args = parser.parse_args()

    generator = RegressionReportGenerator(args.output_dir)

    if args.xml_file and args.xml_file.exists():
        # Parse actual XML results
        test_suites = generator.parse_pytest_xml(args.xml_file)
    else:
        # Generate sample results for demonstration
        print("No XML file provided, generating sample report...")
        test_suites = _generate_sample_results()

    report_file = generator.generate_html_report(test_suites, args.title)

    print(f"HTML report generated: {report_file}")
    print(f"Open {report_file} in your browser to view the results.")


def _generate_sample_results() -> List[TestSuiteResult]:
    """Generate sample test results for demonstration"""
    sample_suites = [
        TestSuiteResult(
            name="Phase 0 - Environment Tests",
            duration=15.2,
            tests=[
                TestResult("test_dev_environment_isolation", "passed", 2.1, phase="Phase 0", category="Environment"),
                TestResult("test_test_environment_isolation", "passed", 1.8, phase="Phase 0", category="Environment"),
                TestResult("test_prod_environment_isolation", "failed", 3.2, "Environment not isolated", phase="Phase 0", category="Environment"),
                TestResult("test_port_assignments", "passed", 0.9, phase="Phase 0", category="Environment"),
            ]
        ),
        TestSuiteResult(
            name="Phase 1 - Ingestion Pipeline Tests",
            duration=45.7,
            tests=[
                TestResult("test_pass_a_pdf_parsing", "passed", 12.3, phase="Phase 1", category="Ingestion"),
                TestResult("test_pass_b_content_enrichment", "passed", 18.4, phase="Phase 1", category="Ingestion"),
                TestResult("test_pass_c_graph_compilation", "error", 15.0, "Graph compilation timeout", phase="Phase 1", category="Ingestion"),
            ]
        ),
        TestSuiteResult(
            name="Feature Requests - Advanced Search",
            duration=8.9,
            tests=[
                TestResult("test_faceted_search", "passed", 2.1, phase="Feature Requests", category="Search"),
                TestResult("test_search_performance", "passed", 1.2, phase="Feature Requests", category="Performance"),
                TestResult("test_autocomplete", "skipped", 0.0, "Not implemented", phase="Feature Requests", category="Search"),
            ]
        )
    ]

    return sample_suites


if __name__ == "__main__":
    main()