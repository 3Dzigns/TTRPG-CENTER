# src_common/admin/testing.py
"""
Testing & Bug Management Service - ADM-004
Environment-scoped regression tests and bug bundle management
"""

import json
import time
import uuid
import subprocess
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

from ..ttrpg_logging import get_logger


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


class BugPriority(Enum):
    """Bug priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class BugStatus(Enum):
    """Bug status values"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    DUPLICATE = "duplicate"
    WONT_FIX = "wont_fix"
    NEEDS_INFO = "needs_info"
    TESTING = "testing"


class BugComponent(Enum):
    """Bug component categories"""
    UI = "ui"
    API = "api"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    INGESTION = "ingestion"
    SEARCH = "search"
    PERFORMANCE = "performance"
    SECURITY = "security"
    INFRASTRUCTURE = "infrastructure"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    OTHER = "other"


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
class BugActivity:
    """Bug activity record for tracking changes"""
    activity_id: str
    bug_id: str
    activity_type: str  # 'created', 'updated', 'assigned', 'resolved', 'commented'
    user: str
    timestamp: float
    description: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class BugBundle:
    """Enhanced bug bundle for comprehensive tracking"""
    bug_id: str
    title: str
    description: str
    environment: str
    severity: BugSeverity
    priority: BugPriority
    status: BugStatus
    component: BugComponent
    created_at: float
    created_by: str
    assigned_to: Optional[str] = None
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None
    resolution: Optional[str] = None
    steps_to_reproduce: List[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    test_data: Optional[Dict[str, Any]] = None
    attachments: List[str] = None
    tags: List[str] = None
    related_bugs: List[str] = None  # Related bug IDs
    duplicate_of: Optional[str] = None  # If this is a duplicate
    test_failure_id: Optional[str] = None  # Associated test failure
    activity_log: List[BugActivity] = None
    last_updated: float = None
    last_updated_by: Optional[str] = None
    estimation_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    labels: List[str] = None  # Additional categorization
    milestone: Optional[str] = None
    version_found: Optional[str] = None
    version_fixed: Optional[str] = None

    def __post_init__(self):
        if self.steps_to_reproduce is None:
            self.steps_to_reproduce = []
        if self.attachments is None:
            self.attachments = []
        if self.tags is None:
            self.tags = []
        if self.related_bugs is None:
            self.related_bugs = []
        if self.activity_log is None:
            self.activity_log = []
        if self.labels is None:
            self.labels = []
        if self.last_updated is None:
            self.last_updated = self.created_at


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

    def _serialize_test(self, test: RegressionTest) -> Dict[str, Any]:
        """Convert test dataclass to JSON-serializable dict"""
        test_dict = asdict(test)
        test_dict['status'] = test.status.value  # Convert enum to string
        return test_dict

    def _serialize_bug(self, bug: BugBundle) -> Dict[str, Any]:
        """Convert bug dataclass to JSON-serializable dict"""
        bug_dict = asdict(bug)
        bug_dict['severity'] = bug.severity.value  # Convert enum to string
        bug_dict['priority'] = bug.priority.value  # Convert enum to string
        bug_dict['status'] = bug.status.value  # Convert enum to string
        bug_dict['component'] = bug.component.value  # Convert enum to string

        # Serialize activity log
        if bug_dict.get('activity_log'):
            bug_dict['activity_log'] = [asdict(activity) for activity in bug.activity_log]

        return bug_dict

    def _serialize_execution(self, execution: TestExecution) -> Dict[str, Any]:
        """Convert execution dataclass to JSON-serializable dict"""
        exec_dict = asdict(execution)
        exec_dict['status'] = execution.status.value  # Convert enum to string
        return exec_dict

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
                    "recent_executions": [self._serialize_execution(exec) for exec in recent_executions]
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

            return [self._serialize_test(test) for test in tests]

        except Exception as e:
            logger.error(f"Error listing tests for {environment}: {e}")
            return []

    async def get_test(self, environment: str, test_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific test"""
        try:
            tests = await self._load_environment_tests(environment)

            for test in tests:
                if test.test_id == test_id:
                    return self._serialize_test(test)

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
                    results["executions"].append(self._serialize_execution(execution))
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
                       severity: Optional[str] = None, priority: Optional[str] = None,
                       component: Optional[str] = None, assigned_to: Optional[str] = None,
                       created_by: Optional[str] = None, tags: Optional[List[str]] = None,
                       search: Optional[str] = None, limit: Optional[int] = None,
                       offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List bug bundles for an environment with advanced filtering

        Args:
            environment: Environment name
            status: Optional status filter
            severity: Optional severity filter
            priority: Optional priority filter
            component: Optional component filter
            assigned_to: Optional assignee filter
            created_by: Optional creator filter
            tags: Optional tags filter (bug must have ALL specified tags)
            search: Optional full-text search in title/description
            limit: Optional limit for pagination
            offset: Optional offset for pagination

        Returns:
            List of bug dictionaries
        """
        try:
            bugs = await self._load_environment_bugs(environment)

            # Apply filters
            if status:
                bugs = [bug for bug in bugs if bug.status.value == status]

            if severity:
                bugs = [bug for bug in bugs if bug.severity.value == severity]

            if priority:
                bugs = [bug for bug in bugs if bug.priority.value == priority]

            if component:
                bugs = [bug for bug in bugs if bug.component.value == component]

            if assigned_to:
                bugs = [bug for bug in bugs if bug.assigned_to == assigned_to]

            if created_by:
                bugs = [bug for bug in bugs if bug.created_by == created_by]

            if tags:
                bugs = [bug for bug in bugs if all(tag in bug.tags for tag in tags)]

            if search:
                search_lower = search.lower()
                bugs = [bug for bug in bugs
                       if search_lower in bug.title.lower()
                       or search_lower in bug.description.lower()
                       or any(search_lower in tag.lower() for tag in bug.tags)]

            # Sort by priority (urgent first), then by creation time (newest first)
            priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
            bugs.sort(key=lambda x: (priority_order.get(x.priority.value, 4), -x.created_at))

            # Apply pagination
            if offset:
                bugs = bugs[offset:]
            if limit:
                bugs = bugs[:limit]

            return [self._serialize_bug(bug) for bug in bugs]

        except Exception as e:
            logger.error(f"Error listing bugs for {environment}: {e}")
            return []

    async def create_bug(self, environment: str, bug_data: Dict[str, Any]) -> BugBundle:
        """
        Create a new bug bundle with enhanced tracking

        Args:
            environment: Environment name
            bug_data: Bug data dictionary

        Returns:
            Created BugBundle object
        """
        try:
            current_time = time.time()
            bug_id = str(uuid.uuid4())
            created_by = bug_data.get('created_by', 'admin')

            # Create initial activity record
            activity = BugActivity(
                activity_id=str(uuid.uuid4()),
                bug_id=bug_id,
                activity_type='created',
                user=created_by,
                timestamp=current_time,
                description=f"Bug created: {bug_data.get('title', 'No title')}",
                details={'initial_status': bug_data.get('status', 'open')}
            )

            bug = BugBundle(
                bug_id=bug_id,
                title=bug_data['title'],
                description=bug_data['description'],
                environment=environment,
                severity=BugSeverity(bug_data['severity']),
                priority=BugPriority(bug_data.get('priority', 'medium')),
                status=BugStatus(bug_data.get('status', 'open')),
                component=BugComponent(bug_data.get('component', 'other')),
                created_at=current_time,
                created_by=created_by,
                assigned_to=bug_data.get('assigned_to'),
                steps_to_reproduce=bug_data.get('steps_to_reproduce', []),
                expected_behavior=bug_data.get('expected_behavior'),
                actual_behavior=bug_data.get('actual_behavior'),
                test_data=bug_data.get('test_data'),
                tags=bug_data.get('tags', []),
                related_bugs=bug_data.get('related_bugs', []),
                test_failure_id=bug_data.get('test_failure_id'),
                estimation_hours=bug_data.get('estimation_hours'),
                labels=bug_data.get('labels', []),
                milestone=bug_data.get('milestone'),
                version_found=bug_data.get('version_found'),
                activity_log=[activity],
                last_updated=current_time,
                last_updated_by=created_by
            )

            await self._save_bug(bug)

            logger.info(f"Created bug '{bug.title}' ({bug_id}) in {environment}")
            return bug

        except Exception as e:
            logger.error(f"Error creating bug in {environment}: {e}")
            raise

    async def update_bug(self, environment: str, bug_id: str, updates: Dict[str, Any],
                         updated_by: str = 'admin') -> Optional[BugBundle]:
        """Update an existing bug bundle with activity tracking"""
        try:
            bugs = await self._load_environment_bugs(environment)

            for bug in bugs:
                if bug.bug_id == bug_id:
                    current_time = time.time()
                    changes = []
                    activity_details = {}

                    # Track all changes
                    if 'status' in updates and updates['status'] != bug.status.value:
                        old_status = bug.status.value
                        new_status = updates['status']
                        bug.status = BugStatus(new_status)
                        changes.append(f"Status: {old_status} → {new_status}")
                        activity_details['status_change'] = {'from': old_status, 'to': new_status}

                        # Handle status-specific updates
                        if new_status == 'resolved':
                            bug.resolved_at = current_time
                            bug.resolution = updates.get('resolution', 'No resolution provided')
                        elif new_status == 'closed':
                            bug.closed_at = current_time
                            if not bug.resolved_at:
                                bug.resolved_at = current_time

                    if 'assigned_to' in updates and updates['assigned_to'] != bug.assigned_to:
                        old_assignee = bug.assigned_to or 'Unassigned'
                        new_assignee = updates['assigned_to'] or 'Unassigned'
                        bug.assigned_to = updates['assigned_to']
                        changes.append(f"Assignee: {old_assignee} → {new_assignee}")
                        activity_details['assignee_change'] = {'from': old_assignee, 'to': new_assignee}

                    if 'priority' in updates and updates['priority'] != bug.priority.value:
                        old_priority = bug.priority.value
                        new_priority = updates['priority']
                        bug.priority = BugPriority(new_priority)
                        changes.append(f"Priority: {old_priority} → {new_priority}")
                        activity_details['priority_change'] = {'from': old_priority, 'to': new_priority}

                    if 'severity' in updates and updates['severity'] != bug.severity.value:
                        old_severity = bug.severity.value
                        new_severity = updates['severity']
                        bug.severity = BugSeverity(new_severity)
                        changes.append(f"Severity: {old_severity} → {new_severity}")
                        activity_details['severity_change'] = {'from': old_severity, 'to': new_severity}

                    if 'component' in updates and updates['component'] != bug.component.value:
                        old_component = bug.component.value
                        new_component = updates['component']
                        bug.component = BugComponent(new_component)
                        changes.append(f"Component: {old_component} → {new_component}")
                        activity_details['component_change'] = {'from': old_component, 'to': new_component}

                    # Update other fields
                    simple_fields = ['title', 'description', 'expected_behavior', 'actual_behavior',
                                   'resolution', 'estimation_hours', 'actual_hours', 'milestone',
                                   'version_found', 'version_fixed']
                    for field in simple_fields:
                        if field in updates:
                            old_value = getattr(bug, field, None)
                            new_value = updates[field]
                            if old_value != new_value:
                                setattr(bug, field, new_value)
                                changes.append(f"{field.replace('_', ' ').title()}: updated")
                                activity_details[f'{field}_updated'] = True

                    # Update list fields
                    list_fields = ['tags', 'labels', 'related_bugs', 'steps_to_reproduce']
                    for field in list_fields:
                        if field in updates:
                            setattr(bug, field, updates[field])
                            changes.append(f"{field.replace('_', ' ').title()}: updated")
                            activity_details[f'{field}_updated'] = True

                    # Create activity record if there were changes
                    if changes:
                        activity = BugActivity(
                            activity_id=str(uuid.uuid4()),
                            bug_id=bug_id,
                            activity_type='updated',
                            user=updated_by,
                            timestamp=current_time,
                            description=f"Updated: {', '.join(changes)}",
                            details=activity_details
                        )
                        bug.activity_log.append(activity)
                        bug.last_updated = current_time
                        bug.last_updated_by = updated_by

                    await self._save_bug(bug)
                    logger.info(f"Updated bug {bug_id} in {environment}: {', '.join(changes)}")
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
                # Convert status string to enum
                exec_data['status'] = TestStatus(exec_data['status'])
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
        """Load bugs from environment storage with enhanced data handling"""
        try:
            bugs_file = Path(f"env/{environment}/data/bug_bundles.json")

            if not bugs_file.exists():
                return []

            with open(bugs_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            bugs = []
            for bug_data in data.get('bugs', []):
                # Handle enum conversions
                bug_data['severity'] = BugSeverity(bug_data['severity'])
                bug_data['priority'] = BugPriority(bug_data.get('priority', 'medium'))
                bug_data['status'] = BugStatus(bug_data.get('status', 'open'))
                bug_data['component'] = BugComponent(bug_data.get('component', 'other'))

                # Handle activity log conversion
                if 'activity_log' in bug_data and bug_data['activity_log']:
                    activities = []
                    for activity_data in bug_data['activity_log']:
                        activity = BugActivity(**activity_data)
                        activities.append(activity)
                    bug_data['activity_log'] = activities

                # Ensure default values for new fields
                defaults = {
                    'related_bugs': [],
                    'labels': [],
                    'last_updated': bug_data.get('created_at', time.time()),
                    'last_updated_by': bug_data.get('created_by', 'unknown')
                }
                for key, default_value in defaults.items():
                    if key not in bug_data:
                        bug_data[key] = default_value

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
        """Save bug to environment storage with enhanced data handling"""
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
                "schema_version": "2.0",  # Track schema version for future migrations
                "bugs": []
            }

            for b in bugs:
                bug_dict = asdict(b)
                # Convert enums to strings
                bug_dict['severity'] = b.severity.value
                bug_dict['priority'] = b.priority.value
                bug_dict['status'] = b.status.value
                bug_dict['component'] = b.component.value

                # Convert activity log to dicts
                if bug_dict.get('activity_log'):
                    bug_dict['activity_log'] = [asdict(activity) for activity in b.activity_log]

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

    async def get_bug(self, environment: str, bug_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific bug"""
        try:
            bugs = await self._load_environment_bugs(environment)

            for bug in bugs:
                if bug.bug_id == bug_id:
                    return self._serialize_bug(bug)

            return None

        except Exception as e:
            logger.error(f"Error getting bug {bug_id} from {environment}: {e}")
            return None

    async def create_bug_from_test_failure(self, environment: str, test_execution: TestExecution,
                                         test_definition: Dict[str, Any], created_by: str = 'system') -> BugBundle:
        """
        Automatically create a bug from a test failure with context preservation

        Args:
            environment: Environment name
            test_execution: Failed test execution
            test_definition: Test definition data
            created_by: User creating the bug

        Returns:
            Created BugBundle object
        """
        try:
            # Determine severity based on test type and failure
            severity_map = {
                'security': 'critical',
                'regression': 'high',
                'functional': 'medium',
                'unit': 'low'
            }
            severity = severity_map.get(test_definition.get('test_type', 'unit'), 'medium')

            # Determine component based on test tags or type
            component_map = {
                'api': 'api',
                'ui': 'ui',
                'database': 'database',
                'auth': 'authentication',
                'security': 'security',
                'performance': 'performance'
            }
            component = 'other'
            for tag in test_definition.get('tags', []):
                if tag.lower() in component_map:
                    component = component_map[tag.lower()]
                    break

            # Create comprehensive bug data
            bug_data = {
                'title': f"Test Failure: {test_definition.get('name', 'Unknown Test')}",
                'description': self._generate_failure_description(test_execution, test_definition),
                'severity': severity,
                'priority': 'high' if severity in ['critical', 'high'] else 'medium',
                'status': 'open',
                'component': component,
                'created_by': created_by,
                'test_failure_id': test_execution.execution_id,
                'expected_behavior': test_definition.get('expected_result'),
                'actual_behavior': self._extract_failure_summary(test_execution),
                'steps_to_reproduce': self._generate_reproduction_steps(test_execution, test_definition),
                'test_data': {
                    'test_id': test_execution.test_id,
                    'execution_id': test_execution.execution_id,
                    'command': test_definition.get('command'),
                    'exit_code': test_execution.exit_code,
                    'duration': test_execution.duration_seconds,
                    'environment': environment
                },
                'tags': ['test-failure', 'automated'] + test_definition.get('tags', []),
                'labels': [f"test-type:{test_definition.get('test_type', 'unknown')}"],
                'version_found': os.getenv('APP_VERSION', 'unknown')
            }

            bug = await self.create_bug(environment, bug_data)
            logger.info(f"Auto-created bug {bug.bug_id} from test failure {test_execution.execution_id}")
            return bug

        except Exception as e:
            logger.error(f"Error creating bug from test failure: {e}")
            raise

    def _generate_failure_description(self, execution: TestExecution, test_def: Dict[str, Any]) -> str:
        """Generate comprehensive failure description"""
        desc = f"Automated test failure detected in {execution.environment} environment.\n\n"
        desc += f"**Test Details:**\n"
        desc += f"- Test ID: {execution.test_id}\n"
        desc += f"- Test Type: {test_def.get('test_type', 'unknown')}\n"
        desc += f"- Execution ID: {execution.execution_id}\n"
        desc += f"- Failed at: {datetime.fromtimestamp(execution.started_at).isoformat()}\n"
        desc += f"- Duration: {execution.duration_seconds:.2f}s\n"
        desc += f"- Exit Code: {execution.exit_code}\n\n"

        if execution.stderr:
            desc += f"**Error Output:**\n```\n{execution.stderr[:1000]}\n```\n\n"
        if execution.stdout:
            desc += f"**Standard Output:**\n```\n{execution.stdout[:1000]}\n```\n\n"

        desc += f"**Test Description:**\n{test_def.get('description', 'No description available')}"
        return desc

    def _extract_failure_summary(self, execution: TestExecution) -> str:
        """Extract concise failure summary from execution"""
        if execution.stderr:
            # Try to extract the most relevant error line
            lines = execution.stderr.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['error:', 'failed:', 'exception:', 'assert']):
                    return line.strip()
            return execution.stderr[:200] + '...' if len(execution.stderr) > 200 else execution.stderr
        return f"Test failed with exit code {execution.exit_code}"

    def _generate_reproduction_steps(self, execution: TestExecution, test_def: Dict[str, Any]) -> List[str]:
        """Generate reproduction steps from test execution"""
        steps = [
            f"1. Navigate to {execution.environment} environment",
            f"2. Run command: {test_def.get('command', 'Unknown command')}",
            "3. Observe the failure"
        ]
        if test_def.get('test_data'):
            steps.insert(1, "2. Ensure test data is properly set up")
        return steps

    async def bulk_update_bugs(self, environment: str, bug_ids: List[str],
                              updates: Dict[str, Any], updated_by: str = 'admin') -> Dict[str, Any]:
        """
        Perform bulk updates on multiple bugs

        Args:
            environment: Environment name
            bug_ids: List of bug IDs to update
            updates: Updates to apply to all bugs
            updated_by: User performing the update

        Returns:
            Summary of bulk operation results
        """
        try:
            results = {
                'updated': [],
                'failed': [],
                'not_found': [],
                'total_requested': len(bug_ids)
            }

            for bug_id in bug_ids:
                try:
                    updated_bug = await self.update_bug(environment, bug_id, updates, updated_by)
                    if updated_bug:
                        results['updated'].append(bug_id)
                    else:
                        results['not_found'].append(bug_id)
                except Exception as e:
                    logger.error(f"Failed to update bug {bug_id}: {e}")
                    results['failed'].append({'bug_id': bug_id, 'error': str(e)})

            logger.info(f"Bulk update completed: {len(results['updated'])} updated, "
                       f"{len(results['failed'])} failed, {len(results['not_found'])} not found")
            return results

        except Exception as e:
            logger.error(f"Error in bulk update operation: {e}")
            raise

    async def bulk_assign_bugs(self, environment: str, bug_ids: List[str],
                              assignee: str, assigned_by: str = 'admin') -> Dict[str, Any]:
        """
        Bulk assign bugs to a user

        Args:
            environment: Environment name
            bug_ids: List of bug IDs to assign
            assignee: User to assign bugs to
            assigned_by: User performing the assignment

        Returns:
            Summary of assignment results
        """
        updates = {'assigned_to': assignee}
        return await self.bulk_update_bugs(environment, bug_ids, updates, assigned_by)

    async def search_bugs(self, environment: str, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Advanced full-text search across bug data

        Args:
            environment: Environment name
            query: Search query string
            filters: Additional filters to apply

        Returns:
            List of matching bugs with relevance scoring
        """
        try:
            bugs = await self._load_environment_bugs(environment)
            results = []

            query_lower = query.lower()
            query_terms = query_lower.split()

            for bug in bugs:
                score = 0
                matches = []

                # Search in title (highest weight)
                if query_lower in bug.title.lower():
                    score += 10
                    matches.append('title')
                for term in query_terms:
                    if term in bug.title.lower():
                        score += 5

                # Search in description
                if query_lower in bug.description.lower():
                    score += 5
                    matches.append('description')
                for term in query_terms:
                    if term in bug.description.lower():
                        score += 2

                # Search in tags
                for tag in bug.tags:
                    if query_lower in tag.lower():
                        score += 3
                        matches.append('tags')

                # Search in labels
                for label in bug.labels or []:
                    if query_lower in label.lower():
                        score += 2
                        matches.append('labels')

                # Search in activity log
                for activity in bug.activity_log:
                    if query_lower in activity.description.lower():
                        score += 1
                        matches.append('activity')

                # Apply additional filters
                if filters:
                    passes_filters = True
                    for key, value in filters.items():
                        if hasattr(bug, key):
                            attr_value = getattr(bug, key)
                            if hasattr(attr_value, 'value'):  # Enum
                                attr_value = attr_value.value
                            if attr_value != value:
                                passes_filters = False
                                break
                    if not passes_filters:
                        continue

                # Include if there's a match
                if score > 0:
                    bug_dict = self._serialize_bug(bug)
                    bug_dict['_search_score'] = score
                    bug_dict['_search_matches'] = matches
                    results.append(bug_dict)

            # Sort by relevance score (highest first)
            results.sort(key=lambda x: x['_search_score'], reverse=True)

            logger.info(f"Search for '{query}' in {environment} returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error searching bugs in {environment}: {e}")
            return []

    async def get_bug_analytics(self, environment: str, date_from: Optional[float] = None,
                               date_to: Optional[float] = None) -> Dict[str, Any]:
        """
        Generate analytics and insights for bug data

        Args:
            environment: Environment name
            date_from: Optional start date (timestamp)
            date_to: Optional end date (timestamp)

        Returns:
            Analytics data dictionary
        """
        try:
            bugs = await self._load_environment_bugs(environment)

            # Apply date filters
            if date_from or date_to:
                filtered_bugs = []
                for bug in bugs:
                    if date_from and bug.created_at < date_from:
                        continue
                    if date_to and bug.created_at > date_to:
                        continue
                    filtered_bugs.append(bug)
                bugs = filtered_bugs

            # Calculate metrics
            total_bugs = len(bugs)
            if total_bugs == 0:
                return {'total_bugs': 0, 'message': 'No bugs found for the specified criteria'}

            # Status distribution
            status_dist = {}
            severity_dist = {}
            priority_dist = {}
            component_dist = {}
            assignee_dist = {}
            resolution_times = []
            open_times = []

            current_time = time.time()

            for bug in bugs:
                # Status distribution
                status = bug.status.value
                status_dist[status] = status_dist.get(status, 0) + 1

                # Severity distribution
                severity = bug.severity.value
                severity_dist[severity] = severity_dist.get(severity, 0) + 1

                # Priority distribution
                priority = bug.priority.value
                priority_dist[priority] = priority_dist.get(priority, 0) + 1

                # Component distribution
                component = bug.component.value
                component_dist[component] = component_dist.get(component, 0) + 1

                # Assignee distribution
                assignee = bug.assigned_to or 'Unassigned'
                assignee_dist[assignee] = assignee_dist.get(assignee, 0) + 1

                # Resolution time calculation
                if bug.resolved_at:
                    resolution_time = bug.resolved_at - bug.created_at
                    resolution_times.append(resolution_time)
                elif bug.status.value in ['open', 'in_progress', 'needs_info']:
                    open_time = current_time - bug.created_at
                    open_times.append(open_time)

            # Calculate averages
            avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0
            avg_open_time = sum(open_times) / len(open_times) if open_times else 0

            # Calculate percentages
            resolved_count = status_dist.get('resolved', 0) + status_dist.get('closed', 0)
            resolution_rate = (resolved_count / total_bugs) * 100 if total_bugs > 0 else 0

            return {
                'total_bugs': total_bugs,
                'resolution_rate_percent': round(resolution_rate, 2),
                'distributions': {
                    'status': status_dist,
                    'severity': severity_dist,
                    'priority': priority_dist,
                    'component': component_dist,
                    'assignee': assignee_dist
                },
                'timing_metrics': {
                    'avg_resolution_time_hours': round(avg_resolution_time / 3600, 2) if avg_resolution_time else 0,
                    'avg_open_time_hours': round(avg_open_time / 3600, 2) if avg_open_time else 0,
                    'resolved_bugs': len(resolution_times),
                    'open_bugs': len(open_times)
                },
                'date_range': {
                    'from': date_from,
                    'to': date_to,
                    'duration_days': round((date_to - date_from) / 86400, 2) if date_from and date_to else None
                },
                'generated_at': current_time
            }

        except Exception as e:
            logger.error(f"Error generating bug analytics for {environment}: {e}")
            raise

    async def export_test_results(self, environment: Optional[str] = None) -> Dict[str, Any]:
        """Export test results and execution history"""
        try:
            export_data = {
                "exported_at": time.time(),
                "environments": {}
            }

            environments = [environment] if environment else self.environments

            for env in environments:
                tests = await self.list_tests(env)
                bugs = await self.list_bugs(env)
                executions = await self.get_recent_executions(env, limit=100)

                export_data["environments"][env] = {
                    "tests": tests,
                    "bugs": bugs,
                    "executions": [self._serialize_execution(exec) for exec in executions]
                }

            return export_data

        except Exception as e:
            logger.error(f"Error exporting test results: {e}")
            raise

    async def stop_all_tests(self, environment: str) -> bool:
        """Stop all running tests in an environment"""
        try:
            # In a real implementation, this would kill running test processes
            # For now, we'll just mark running tests as stopped
            tests = await self._load_environment_tests(environment)

            stopped_count = 0
            for test in tests:
                if test.status == TestStatus.RUNNING:
                    test.status = TestStatus.ERROR
                    test.last_result = "Test execution stopped by admin"
                    await self._save_test(test)
                    stopped_count += 1

            logger.info(f"Stopped {stopped_count} running tests in {environment}")
            return True

        except Exception as e:
            logger.error(f"Error stopping tests in {environment}: {e}")
            return False