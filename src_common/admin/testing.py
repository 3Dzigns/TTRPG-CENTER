# src_common/admin/testing.py
"""
Testing & Bug Management Service - ADM-004
Environment-scoped regression tests and bug bundle management
"""

import json
import time
import uuid
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

from ..logging import get_logger


logger = get_logger(__name__)


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class BugSeverity(Enum):
    """Bug severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RegressionTest:
    """Regression test definition"""
    test_id: str
    name: str
    description: str
    environment: str
    test_type: str  # 'unit', 'functional', 'security', 'regression'
    command: str
    expected_result: str
    created_at: float
    created_by: str
    status: TestStatus = TestStatus.PENDING
    last_run: Optional[float] = None
    last_result: Optional[str] = None
    run_count: int = 0
    failure_count: int = 0
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class BugBundle:
    """Bug bundle for tracking issues"""
    bug_id: str
    title: str
    description: str
    environment: str
    severity: BugSeverity
    status: str  # 'open', 'in_progress', 'resolved', 'closed'
    created_at: float
    created_by: str
    assigned_to: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution: Optional[str] = None
    steps_to_reproduce: List[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    attachments: List[str] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.steps_to_reproduce is None:
            self.steps_to_reproduce = []
        if self.attachments is None:
            self.attachments = []
        if self.tags is None:
            self.tags = []


@dataclass
class TestExecution:
    """Test execution record"""
    execution_id: str
    test_id: str
    environment: str
    started_at: float
    completed_at: Optional[float] = None
    status: TestStatus = TestStatus.RUNNING
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    @property
    def is_complete(self) -> bool:
        return self.status in [TestStatus.PASSED, TestStatus.FAILED, TestStatus.ERROR, TestStatus.SKIPPED]


class AdminTestingService:
    """
    Testing & Bug Management Service
    
    Manages regression tests and bug bundles with environment-specific scoping.
    Provides test execution, results tracking, and issue management.
    """
    
    def __init__(self):
        self.environments = ['dev', 'test', 'prod']
        logger.info("Admin Testing Service initialized")
    
    async def get_testing_overview(self) -> Dict[str, Any]:
        """
        Get overview of testing status across all environments
        
        Returns:
            Dictionary with test and bug statistics per environment
        """
        try:
            overview = {
                "timestamp": time.time(),
                "environments": {}
            }
            
            for env in self.environments:
                tests = await self.list_tests(env)
                bugs = await self.list_bugs(env)
                recent_executions = await self.get_recent_executions(env, limit=5)
                
                # Calculate test statistics
                test_stats = {
                    "total": len(tests),
                    "by_status": {},
                    "by_type": {}
                }
                
                for test in tests:
                    status = test['status']
                    test_type = test['test_type']
                    
                    test_stats["by_status"][status] = test_stats["by_status"].get(status, 0) + 1
                    test_stats["by_type"][test_type] = test_stats["by_type"].get(test_type, 0) + 1
                
                # Calculate bug statistics
                bug_stats = {
                    "total": len(bugs),
                    "by_severity": {},
                    "by_status": {}
                }
                
                for bug in bugs:
                    severity = bug['severity']
                    status = bug['status']
                    
                    bug_stats["by_severity"][severity] = bug_stats["by_severity"].get(severity, 0) + 1
                    bug_stats["by_status"][status] = bug_stats["by_status"].get(status, 0) + 1
                
                overview["environments"][env] = {
                    "test_stats": test_stats,
                    "bug_stats": bug_stats,
                    "recent_executions": [asdict(exec) for exec in recent_executions]
                }
            
            return overview
            
        except Exception as e:
            logger.error(f"Error getting testing overview: {e}")
            raise
    
    async def list_tests(self, environment: str, test_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List regression tests for an environment
        
        Args:
            environment: Environment name
            test_type: Optional test type filter
            
        Returns:
            List of test dictionaries
        """
        try:
            tests = await self._load_environment_tests(environment)
            
            if test_type:
                tests = [test for test in tests if test.test_type == test_type]
            
            return [asdict(test) for test in tests]
            
        except Exception as e:
            logger.error(f"Error listing tests for {environment}: {e}")
            return []
    
    async def get_test(self, environment: str, test_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific test"""
        try:
            tests = await self._load_environment_tests(environment)
            
            for test in tests:
                if test.test_id == test_id:
                    return asdict(test)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting test {test_id} from {environment}: {e}")
            return None
    
    async def create_test(self, environment: str, test_data: Dict[str, Any]) -> RegressionTest:
        """
        Create a new regression test
        
        Args:
            environment: Environment name
            test_data: Test data dictionary
            
        Returns:
            Created RegressionTest object
        """
        try:
            test = RegressionTest(
                test_id=str(uuid.uuid4()),
                name=test_data['name'],
                description=test_data['description'],
                environment=environment,
                test_type=test_data['test_type'],
                command=test_data['command'],
                expected_result=test_data['expected_result'],
                created_at=time.time(),
                created_by=test_data.get('created_by', 'admin'),
                tags=test_data.get('tags', [])
            )
            
            await self._save_test(test)
            
            logger.info(f"Created test '{test.name}' in {environment}")
            return test
            
        except Exception as e:
            logger.error(f"Error creating test in {environment}: {e}")
            raise
    
    async def run_test(self, environment: str, test_id: str) -> TestExecution:
        """
        Execute a regression test
        
        Args:
            environment: Environment name
            test_id: Test identifier
            
        Returns:
            TestExecution object with results
        """
        try:
            # Get test definition
            test = await self.get_test(environment, test_id)
            if not test:
                raise ValueError(f"Test {test_id} not found in {environment}")
            
            # Create execution record
            execution = TestExecution(
                execution_id=str(uuid.uuid4()),
                test_id=test_id,
                environment=environment,
                started_at=time.time()
            )
            
            # Execute test command
            try:
                # Set environment-specific working directory
                cwd = Path(f"env/{environment}")
                
                result = subprocess.run(
                    test['command'],
                    shell=True,
                    cwd=cwd if cwd.exists() else None,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                execution.exit_code = result.returncode
                execution.stdout = result.stdout
                execution.stderr = result.stderr
                execution.completed_at = time.time()
                execution.duration_seconds = execution.completed_at - execution.started_at
                
                # Determine test result based on expected behavior
                if result.returncode == 0:
                    execution.status = TestStatus.PASSED
                else:
                    execution.status = TestStatus.FAILED
                
            except subprocess.TimeoutExpired:
                execution.status = TestStatus.ERROR
                execution.stderr = "Test execution timed out"
                execution.completed_at = time.time()
                execution.duration_seconds = execution.completed_at - execution.started_at
                
            except Exception as e:
                execution.status = TestStatus.ERROR
                execution.stderr = str(e)
                execution.completed_at = time.time()
                execution.duration_seconds = execution.completed_at - execution.started_at
            
            # Save execution record
            await self._save_execution(execution)
            
            # Update test statistics
            await self._update_test_stats(environment, test_id, execution.status)
            
            logger.info(f"Executed test {test_id} in {environment}: {execution.status.value}")
            return execution
            
        except Exception as e:
            logger.error(f"Error running test {test_id} in {environment}: {e}")
            raise
    
    async def run_test_suite(self, environment: str, test_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a suite of tests
        
        Args:
            environment: Environment name
            test_type: Optional test type filter
            
        Returns:
            Test suite results summary
        """
        try:
            tests = await self.list_tests(environment, test_type)
            
            results = {
                "suite_id": str(uuid.uuid4()),
                "environment": environment,
                "test_type": test_type,
                "started_at": time.time(),
                "total_tests": len(tests),
                "executions": []
            }
            
            # Run each test
            for test in tests:
                try:
                    execution = await self.run_test(environment, test['test_id'])
                    results["executions"].append(asdict(execution))
                except Exception as e:
                    logger.error(f"Failed to run test {test['test_id']}: {e}")
            
            results["completed_at"] = time.time()
            results["duration_seconds"] = results["completed_at"] - results["started_at"]
            
            # Calculate summary statistics
            status_counts = {}
            for execution in results["executions"]:
                status = execution['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            results["summary"] = status_counts
            
            logger.info(f"Completed test suite in {environment}: {status_counts}")
            return results
            
        except Exception as e:
            logger.error(f"Error running test suite in {environment}: {e}")
            raise
    
    async def list_bugs(self, environment: str, status: Optional[str] = None, 
                       severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List bug bundles for an environment
        
        Args:
            environment: Environment name
            status: Optional status filter
            severity: Optional severity filter
            
        Returns:
            List of bug dictionaries
        """
        try:
            bugs = await self._load_environment_bugs(environment)
            
            if status:
                bugs = [bug for bug in bugs if bug.status == status]
            
            if severity:
                bugs = [bug for bug in bugs if bug.severity.value == severity]
            
            # Sort by creation time (newest first)
            bugs.sort(key=lambda x: x.created_at, reverse=True)
            
            return [asdict(bug) for bug in bugs]
            
        except Exception as e:
            logger.error(f"Error listing bugs for {environment}: {e}")
            return []
    
    async def create_bug(self, environment: str, bug_data: Dict[str, Any]) -> BugBundle:
        """
        Create a new bug bundle
        
        Args:
            environment: Environment name
            bug_data: Bug data dictionary
            
        Returns:
            Created BugBundle object
        """
        try:
            bug = BugBundle(
                bug_id=str(uuid.uuid4()),
                title=bug_data['title'],
                description=bug_data['description'],
                environment=environment,
                severity=BugSeverity(bug_data['severity']),
                status=bug_data.get('status', 'open'),
                created_at=time.time(),
                created_by=bug_data.get('created_by', 'admin'),
                steps_to_reproduce=bug_data.get('steps_to_reproduce', []),
                expected_behavior=bug_data.get('expected_behavior'),
                actual_behavior=bug_data.get('actual_behavior'),
                test_data=bug_data.get('test_data'),
                tags=bug_data.get('tags', [])
            )
            
            await self._save_bug(bug)
            
            logger.info(f"Created bug '{bug.title}' in {environment}")
            return bug
            
        except Exception as e:
            logger.error(f"Error creating bug in {environment}: {e}")
            raise
    
    async def update_bug(self, environment: str, bug_id: str, updates: Dict[str, Any]) -> Optional[BugBundle]:
        """Update an existing bug bundle"""
        try:
            bugs = await self._load_environment_bugs(environment)
            
            for bug in bugs:
                if bug.bug_id == bug_id:
                    # Apply updates
                    if 'status' in updates:
                        bug.status = updates['status']
                        if updates['status'] == 'resolved':
                            bug.resolved_at = time.time()
                            bug.resolution = updates.get('resolution')
                    
                    if 'assigned_to' in updates:
                        bug.assigned_to = updates['assigned_to']
                    
                    if 'description' in updates:
                        bug.description = updates['description']
                    
                    if 'severity' in updates:
                        bug.severity = BugSeverity(updates['severity'])
                    
                    await self._save_bug(bug)
                    logger.info(f"Updated bug {bug_id} in {environment}")
                    return bug
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating bug {bug_id} in {environment}: {e}")
            return None
    
    async def get_recent_executions(self, environment: str, limit: int = 10) -> List[TestExecution]:
        """Get recent test executions for an environment"""
        try:
            executions_file = Path(f"env/{environment}/data/test_executions.json")
            
            if not executions_file.exists():
                return []
            
            with open(executions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            executions = []
            for exec_data in data.get('executions', []):
                execution = TestExecution(**exec_data)
                executions.append(execution)
            
            # Sort by start time (newest first) and apply limit
            executions.sort(key=lambda x: x.started_at, reverse=True)
            return executions[:limit]
            
        except Exception as e:
            logger.warning(f"Could not load executions for {environment}: {e}")
            return []
    
    async def _load_environment_tests(self, environment: str) -> List[RegressionTest]:
        """Load tests from environment storage"""
        try:
            tests_file = Path(f"env/{environment}/data/regression_tests.json")
            
            if not tests_file.exists():
                return []
            
            with open(tests_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            tests = []
            for test_data in data.get('tests', []):
                test_data['status'] = TestStatus(test_data['status'])
                test = RegressionTest(**test_data)
                tests.append(test)
            
            return tests
            
        except Exception as e:
            logger.warning(f"Could not load tests for {environment}: {e}")
            return []
    
    async def _load_environment_bugs(self, environment: str) -> List[BugBundle]:
        """Load bugs from environment storage"""
        try:
            bugs_file = Path(f"env/{environment}/data/bug_bundles.json")
            
            if not bugs_file.exists():
                return []
            
            with open(bugs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            bugs = []
            for bug_data in data.get('bugs', []):
                bug_data['severity'] = BugSeverity(bug_data['severity'])
                bug = BugBundle(**bug_data)
                bugs.append(bug)
            
            return bugs
            
        except Exception as e:
            logger.warning(f"Could not load bugs for {environment}: {e}")
            return []
    
    async def _save_test(self, test: RegressionTest):
        """Save test to environment storage"""
        try:
            tests = await self._load_environment_tests(test.environment)
            
            # Update or add test
            updated = False
            for i, existing_test in enumerate(tests):
                if existing_test.test_id == test.test_id:
                    tests[i] = test
                    updated = True
                    break
            
            if not updated:
                tests.append(test)
            
            # Save to file
            tests_file = Path(f"env/{test.environment}/data/regression_tests.json")
            tests_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "environment": test.environment,
                "updated_at": time.time(),
                "tests": []
            }
            
            for t in tests:
                test_dict = asdict(t)
                test_dict['status'] = t.status.value
                data["tests"].append(test_dict)
            
            with open(tests_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving test {test.test_id}: {e}")
            raise
    
    async def _save_bug(self, bug: BugBundle):
        """Save bug to environment storage"""
        try:
            bugs = await self._load_environment_bugs(bug.environment)
            
            # Update or add bug
            updated = False
            for i, existing_bug in enumerate(bugs):
                if existing_bug.bug_id == bug.bug_id:
                    bugs[i] = bug
                    updated = True
                    break
            
            if not updated:
                bugs.append(bug)
            
            # Save to file
            bugs_file = Path(f"env/{bug.environment}/data/bug_bundles.json")
            bugs_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "environment": bug.environment,
                "updated_at": time.time(),
                "bugs": []
            }
            
            for b in bugs:
                bug_dict = asdict(b)
                bug_dict['severity'] = b.severity.value
                data["bugs"].append(bug_dict)
            
            with open(bugs_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving bug {bug.bug_id}: {e}")
            raise
    
    async def _save_execution(self, execution: TestExecution):
        """Save test execution record"""
        try:
            executions_file = Path(f"env/{execution.environment}/data/test_executions.json")
            executions_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing executions
            executions = []
            if executions_file.exists():
                with open(executions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    executions = data.get('executions', [])
            
            # Add new execution
            exec_dict = asdict(execution)
            exec_dict['status'] = execution.status.value
            executions.append(exec_dict)
            
            # Keep only recent executions (limit to 1000)
            executions = executions[-1000:]
            
            # Save back
            data = {
                "environment": execution.environment,
                "updated_at": time.time(),
                "executions": executions
            }
            
            with open(executions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving execution {execution.execution_id}: {e}")
    
    async def _update_test_stats(self, environment: str, test_id: str, result_status: TestStatus):
        """Update test run statistics"""
        try:
            tests = await self._load_environment_tests(environment)
            
            for test in tests:
                if test.test_id == test_id:
                    test.run_count += 1
                    test.last_run = time.time()
                    test.last_result = result_status.value
                    test.status = result_status
                    
                    if result_status == TestStatus.FAILED:
                        test.failure_count += 1
                    
                    await self._save_test(test)
                    break
                    
        except Exception as e:
            logger.error(f"Error updating test stats for {test_id}: {e}")