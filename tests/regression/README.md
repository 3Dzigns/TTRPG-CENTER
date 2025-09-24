# TTRPG Center Regression Test Suite

A comprehensive regression testing framework for the TTRPG Center application, ensuring system stability and functionality across all development phases and feature implementations.

## Overview

The regression test suite provides systematic validation of:
- **7 Development Phases** - From environment isolation to requirements management
- **34+ Feature Requests** - Advanced search, spell builder, user preferences, and more
- **System Integration** - End-to-end workflow validation
- **Performance Benchmarks** - Response time and throughput requirements
- **Golden Master Validation** - Reference-based consistency checking

## Test Architecture

### Phase-Based Testing Structure

```
tests/regression/
├── phase0/          # Environment isolation & bootstrap
├── phase1/          # Three-pass ingestion pipeline
├── phase2/          # RAG retrieval & model routing
├── phase3/          # Graph workflows
├── phase4/          # Admin UI
├── phase5/          # User UI (retro terminal/LCARS)
├── phase6/          # Testing & feedback automation
├── phase7/          # Requirements management
├── feature_requests/ # FR-001 through FR-034+ implementations
├── golden_masters/   # Reference data and validation
└── reports/         # Generated HTML test reports
```

### Test Categories

- **Unit Tests**: Component-level validation
- **Integration Tests**: Cross-component interaction
- **Performance Tests**: Response time and throughput
- **Contract Tests**: API and interface compliance
- **Golden Master Tests**: Reference-based validation
- **End-to-End Tests**: Complete workflow validation

## Quick Start

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-html pytest-xdist pytest-cov
pip install selenium playwright  # For UI testing
pip install requests httpx       # For API testing
```

### Running Tests

#### Full Regression Suite (Recommended for CI/CD)
```powershell
# Windows PowerShell
.\Run-RegressionSuite.ps1 -Environment dev -Parallel $true -GenerateReport $true
```

```bash
# Linux/macOS
./run_regression_suite.sh --environment dev --parallel true --generate-report true
```

#### Individual Phase Testing
```bash
# Test specific phase
pytest tests/regression/phase1/ -v --tb=short

# Test with HTML report
pytest tests/regression/phase2/ --html=reports/phase2_report.html

# Test with coverage
pytest tests/regression/phase3/ --cov=src_common --cov-report=html
```

#### Feature Request Testing
```bash
# Test all feature requests
pytest tests/regression/feature_requests/ -v

# Test specific feature
pytest tests/regression/feature_requests/test_fr001_advanced_search.py -v
```

#### Performance Testing
```bash
# Run performance benchmarks
pytest tests/regression/ -m performance --durations=10

# Parallel execution for faster results
pytest tests/regression/ -n auto --dist worksteal
```

### Golden Master Validation

```bash
# Generate golden master references
python tests/regression/golden_masters/generate_golden_masters.py

# Validate against golden masters
python tests/regression/golden_masters/validate_golden_masters.py
```

## Test Configuration

### Environment-Specific Testing

Tests automatically adapt to environment context:

```bash
# Development environment (port 8000)
TTRPG_ENV=dev pytest tests/regression/

# Test environment (port 8181)
TTRPG_ENV=test pytest tests/regression/

# Production validation (port 8282)
TTRPG_ENV=prod pytest tests/regression/ -m "not destructive"
```

### Test Markers

Use pytest markers to run specific test categories:

```bash
# Performance tests only
pytest -m performance

# Contract compliance tests
pytest -m contract

# Integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Critical path tests
pytest -m critical
```

### Parallel Execution

Optimize test execution time:

```bash
# Auto-detect CPU cores
pytest -n auto

# Specific worker count
pytest -n 4

# Distributed execution
pytest -n 2 --dist worksteal
```

## Report Generation

### HTML Reports

Generate comprehensive HTML reports:

```bash
# Basic HTML report
pytest --html=reports/regression_report.html --self-contained-html

# Custom report with golden master data
python tests/regression/generate_html_report.py \
  --xml-file results.xml \
  --title "TTRPG Center Regression Report" \
  --output-dir reports/
```

### Coverage Reports

```bash
# HTML coverage report
pytest --cov=src_common --cov-report=html:reports/coverage/

# Terminal coverage summary
pytest --cov=src_common --cov-report=term-missing

# XML coverage for CI/CD
pytest --cov=src_common --cov-report=xml:reports/coverage.xml
```

### JUnit XML Output

```bash
# JUnit XML for CI/CD integration
pytest --junit-xml=reports/junit.xml

# With test durations
pytest --junit-xml=reports/junit.xml --durations=10
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Regression Tests

on: [push, pull_request]

jobs:
  regression:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]
        environment: [dev, test]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run regression tests
      env:
        TTRPG_ENV: ${{ matrix.environment }}
      run: |
        pytest tests/regression/ \
          --junit-xml=reports/junit-${{ matrix.environment }}.xml \
          --html=reports/report-${{ matrix.environment }}.html \
          --cov=src_common \
          --cov-report=xml:reports/coverage-${{ matrix.environment }}.xml \
          -n auto

    - name: Upload test reports
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-reports-${{ matrix.environment }}-py${{ matrix.python-version }}
        path: reports/

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: reports/coverage-${{ matrix.environment }}.xml
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any

    environment {
        TTRPG_ENV = 'test'
    }

    stages {
        stage('Setup') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pip install -r requirements-test.txt'
            }
        }

        stage('Regression Tests') {
            parallel {
                stage('Phase Tests') {
                    steps {
                        sh '''
                            pytest tests/regression/phase*/ \
                              --junit-xml=reports/phase-tests.xml \
                              --html=reports/phase-tests.html \
                              -n 4
                        '''
                    }
                }

                stage('Feature Tests') {
                    steps {
                        sh '''
                            pytest tests/regression/feature_requests/ \
                              --junit-xml=reports/feature-tests.xml \
                              --html=reports/feature-tests.html \
                              -n 2
                        '''
                    }
                }
            }
        }

        stage('Golden Master Validation') {
            steps {
                sh 'python tests/regression/golden_masters/validate_golden_masters.py'
            }
        }

        stage('Report Generation') {
            steps {
                sh '''
                    python tests/regression/generate_html_report.py \
                      --xml-file reports/phase-tests.xml \
                      --title "TTRPG Center Regression Report - Build ${BUILD_NUMBER}"
                '''
            }
        }
    }

    post {
        always {
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'reports',
                reportFiles: '*.html',
                reportName: 'Regression Test Report'
            ])

            publishTestResults testResultsPattern: 'reports/*.xml'
        }
    }
}
```

## Test Development Guidelines

### Writing New Tests

1. **Follow Naming Conventions**
   ```python
   # Phase tests: test_phaseN_feature_name.py
   tests/regression/phase2/test_us201_query_classification.py

   # Feature tests: test_frNNN_feature_name.py
   tests/regression/feature_requests/test_fr015_user_preferences.py
   ```

2. **Use Test Structure Template**
   ```python
   class TestFeatureName:
       """Test suite for Feature Name validation"""

       def test_feature_availability(self):
           """Test that feature components are available"""
           # Implementation availability check

       def test_feature_functionality(self):
           """Test core feature functionality"""
           # Main feature logic validation

       def test_feature_performance(self):
           """Test feature performance requirements"""
           # Performance benchmark validation

       def test_feature_contract_compliance(self):
           """Test feature contract compliance"""
           # API/interface contract validation
   ```

3. **Include Contract Compliance Tests**
   ```python
   def test_contract_compliance(self):
       """Ensure feature meets established contracts"""
       # Data structure validation
       # API endpoint validation
       # Performance requirement validation
       # Error handling validation
   ```

### Performance Testing Guidelines

1. **Response Time Benchmarks**
   ```python
   @pytest.mark.performance
   def test_search_response_time(self):
       start_time = time.perf_counter()
       results = search_engine.search("test query")
       duration = time.perf_counter() - start_time

       assert duration < 2.0, f"Search took {duration:.2f}s, expected <2.0s"
   ```

2. **Throughput Testing**
   ```python
   @pytest.mark.performance
   def test_ingestion_throughput(self):
       pages_processed = run_ingestion_benchmark()
       throughput = pages_processed / benchmark_duration

       assert throughput >= 10, f"Throughput {throughput} pages/min, expected >=10"
   ```

### Golden Master Guidelines

1. **Creating Reference Data**
   ```python
   # Generate new golden master
   golden_master = {
       "api_response_structure": expected_structure,
       "performance_benchmarks": expected_performance,
       "ui_component_structure": expected_ui
   }

   save_golden_master("feature_name.json", golden_master)
   ```

2. **Validating Against References**
   ```python
   def test_against_golden_master(self):
       current_state = get_current_system_state()
       golden_master = load_golden_master("system_baseline.json")

       validation = validate_against_master(current_state, golden_master)
       assert validation["valid"], f"Golden master validation failed: {validation['errors']}"
   ```

## Test Data Management

### Test Fixtures

Shared test data is available through fixtures:

```python
@pytest.fixture
def sample_spell_data():
    return load_test_data("spells/sample_spells.json")

@pytest.fixture
def mock_api_responses():
    return load_golden_master("api_responses.json")

@pytest.fixture
def test_environment():
    return EnvironmentManager("test")
```

### Environment Isolation

Tests automatically use isolated environments:

```python
def test_with_isolation(test_environment):
    # Automatically uses env/test/ directory
    # Isolated database, config, logs
    # No interference with dev/prod
    assert test_environment.port == 8181
```

## Debugging Failed Tests

### Verbose Output
```bash
# Maximum verbosity
pytest tests/regression/phase1/ -vvv --tb=long

# Show local variables in tracebacks
pytest tests/regression/phase1/ --tb=long --showlocals

# Stop on first failure
pytest tests/regression/phase1/ -x
```

### Test Isolation
```bash
# Run single test method
pytest tests/regression/phase2/test_us201_query_classification.py::TestQueryClassification::test_classification_accuracy -v

# Run with pdb debugger
pytest tests/regression/phase2/ --pdb

# Run with specific environment
TTRPG_ENV=dev pytest tests/regression/phase2/ -v
```

### Log Analysis
```bash
# Capture and show logs
pytest tests/regression/ --log-cli-level=DEBUG

# Save logs to file
pytest tests/regression/ --log-file=test_debug.log --log-file-level=DEBUG
```

## Performance Optimization

### Test Execution Speed

1. **Parallel Execution**: Use `-n auto` for CPU-based parallelization
2. **Test Markers**: Use markers to skip slow tests during development
3. **Fixture Scope**: Use `session` or `module` scope for expensive fixtures
4. **Test Order**: Run fast tests first with `--lf` (last failed)

### Resource Management

1. **Memory Usage**: Monitor with `pytest-monitor` plugin
2. **Database Cleanup**: Use transaction rollbacks in fixtures
3. **File Cleanup**: Use temporary directories and cleanup fixtures
4. **Network Mocking**: Mock external API calls during unit tests

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Add project root to Python path
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"

   # Or use pytest's conftest.py for path management
   ```

2. **Environment Issues**
   ```bash
   # Verify environment configuration
   pytest tests/regression/phase0/ -v

   # Check port availability
   netstat -an | grep 8000
   ```

3. **Database Connection**
   ```bash
   # Test database connectivity
   pytest tests/regression/phase0/test_us001_environment_isolation.py::TestEnvironmentIsolation::test_database_isolation -v
   ```

4. **Performance Test Failures**
   ```bash
   # Run with relaxed timeouts
   pytest tests/regression/ -m performance --timeout=300

   # Profile slow tests
   pytest tests/regression/ --durations=0
   ```

### Getting Help

1. **Test Logs**: Check `env/{environment}/logs/` for detailed logs
2. **Report Issues**: Include test output, environment, and system info
3. **Golden Master Validation**: Regenerate references if system intentionally changed
4. **Performance Issues**: Check system resources and network connectivity

## Maintenance

### Regular Tasks

1. **Update Golden Masters**: When system intentionally changes
2. **Review Performance Benchmarks**: Adjust thresholds as system evolves
3. **Clean Test Data**: Remove outdated test artifacts
4. **Update Dependencies**: Keep test libraries current

### Monthly Review

1. **Test Coverage Analysis**: Identify gaps in test coverage
2. **Performance Trend Analysis**: Monitor performance regression over time
3. **Flaky Test Identification**: Address tests with inconsistent results
4. **Test Suite Optimization**: Remove redundant tests, improve execution time

---

## Appendix

### Test Matrix

| Phase | Components Tested | Test Count | Avg Duration |
|-------|-------------------|------------|--------------|
| Phase 0 | Environment isolation, bootstrap | 15 | 30s |
| Phase 1 | Three-pass ingestion pipeline | 25 | 120s |
| Phase 2 | RAG retrieval, model routing | 20 | 90s |
| Phase 3 | Graph workflows | 18 | 60s |
| Phase 4 | Admin UI | 22 | 45s |
| Phase 5 | User UI, themes | 24 | 40s |
| Phase 6 | Test automation | 16 | 35s |
| Phase 7 | Requirements management | 19 | 50s |
| Feature Requests | FR-001 through FR-034+ | 85+ | 180s |

### Performance Benchmarks

| Component | Target Response Time | Throughput | Success Rate |
|-----------|---------------------|------------|--------------|
| Search API | <2.0s | 50 req/s | >99% |
| Query Classification | <150ms | 100 req/s | >95% |
| Ingestion Pipeline | <30s/page | 10 pages/min | >98% |
| UI Load Time | <3.0s | N/A | >99% |
| Database Operations | <100ms | 200 ops/s | >99.9% |

### Support Contacts

- **Test Framework**: See `tests/regression/README.md`
- **CI/CD Integration**: See `.github/workflows/` or `Jenkinsfile`
- **Performance Issues**: Check system monitoring dashboards
- **Bug Reports**: Include test output and environment details