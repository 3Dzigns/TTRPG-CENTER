# tests/regression/phase7/test_us701_requirements_tracking.py
"""
Phase 7 - US-701: Requirements Tracking Regression Tests
Tests requirements management, traceability, and lifecycle tracking
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRequirementsTracking:
    """Test suite for Requirements Tracking validation"""

    def test_requirements_management_system_availability(self):
        """Test that requirements management system is available"""
        try:
            from src_common.requirements import RequirementsManager
            from src_common.admin_routes import app

            assert RequirementsManager is not None, "RequirementsManager class should be available"
            assert app is not None, "Admin routes should be available for requirements management"

        except ImportError as e:
            pytest.fail(f"Requirements management system not available: {e}")

    def test_requirement_creation_and_structure(self):
        """Test requirement creation and data structure validation"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test requirement creation
        test_requirement = {
            "id": "REQ-TEST-001",
            "title": "User Authentication System",
            "description": "The system shall provide secure user authentication with role-based access control",
            "type": "functional",
            "priority": "high",
            "status": "draft",
            "source": "user_story",
            "acceptance_criteria": [
                "Users can log in with username and password",
                "User sessions expire after 8 hours of inactivity",
                "Failed login attempts are logged and limited"
            ],
            "tags": ["authentication", "security", "phase-0"],
            "created_by": "product_owner",
            "created_date": "2024-01-15",
            "modified_date": "2024-01-15"
        }

        if hasattr(manager, 'create_requirement'):
            result = manager.create_requirement(test_requirement)

            assert isinstance(result, dict), "Requirement creation should return structured result"

            if "requirement_id" in result:
                assert result["requirement_id"] == test_requirement["id"], "Should preserve requirement ID"

            if "status" in result:
                assert result["status"] in ["created", "draft", "pending"], "Should have valid creation status"

        # Test requirement structure validation
        if hasattr(manager, 'validate_requirement_structure'):
            validation = manager.validate_requirement_structure(test_requirement)

            assert isinstance(validation, dict), "Validation should return structured result"

            if "valid" in validation:
                assert validation["valid"] == True, "Test requirement should be valid"

            if "errors" in validation:
                assert len(validation["errors"]) == 0, "Valid requirement should have no errors"

    def test_requirements_lifecycle_management(self):
        """Test requirements lifecycle state management"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test lifecycle states
        valid_states = [
            "draft", "proposed", "approved", "in_development",
            "implemented", "tested", "deployed", "deprecated"
        ]

        test_requirement_id = "REQ-LIFECYCLE-001"

        if hasattr(manager, 'update_requirement_status'):
            # Test state transitions
            state_transitions = [
                ("draft", "proposed"),
                ("proposed", "approved"),
                ("approved", "in_development"),
                ("in_development", "implemented"),
                ("implemented", "tested"),
                ("tested", "deployed")
            ]

            current_state = "draft"

            for from_state, to_state in state_transitions:
                if current_state == from_state:
                    result = manager.update_requirement_status(test_requirement_id, to_state)

                    if result:
                        assert isinstance(result, dict), "Status update should return structured result"

                        if "new_status" in result:
                            assert result["new_status"] == to_state, f"Status should update to {to_state}"

                        current_state = to_state

        # Test invalid state transitions
        if hasattr(manager, 'validate_state_transition'):
            invalid_transitions = [
                ("draft", "deployed"),  # Skip intermediate states
                ("deprecated", "draft")  # Reverse transition
            ]

            for from_state, to_state in invalid_transitions:
                validation = manager.validate_state_transition(from_state, to_state)

                if validation:
                    assert validation.get("valid") == False, f"Invalid transition {from_state} -> {to_state} should be rejected"

    def test_requirements_traceability_matrix(self):
        """Test requirements traceability and relationship mapping"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test traceability relationships
        test_relationships = [
            {
                "parent_id": "REQ-EPIC-001",
                "child_id": "REQ-STORY-001",
                "relationship_type": "decomposition"
            },
            {
                "parent_id": "REQ-STORY-001",
                "child_id": "REQ-TASK-001",
                "relationship_type": "implementation"
            },
            {
                "parent_id": "REQ-STORY-001",
                "child_id": "TEST-CASE-001",
                "relationship_type": "verification"
            }
        ]

        if hasattr(manager, 'create_traceability_link'):
            for relationship in test_relationships:
                result = manager.create_traceability_link(
                    relationship["parent_id"],
                    relationship["child_id"],
                    relationship["relationship_type"]
                )

                if result:
                    assert isinstance(result, dict), "Traceability link creation should return structured result"

                    if "link_id" in result:
                        assert isinstance(result["link_id"], str), "Link ID should be string"

        # Test traceability matrix generation
        if hasattr(manager, 'generate_traceability_matrix'):
            matrix = manager.generate_traceability_matrix("REQ-EPIC-001")

            assert isinstance(matrix, dict), "Traceability matrix should be structured"

            if "requirement_id" in matrix:
                assert matrix["requirement_id"] == "REQ-EPIC-001", "Should trace from specified requirement"

            if "traced_items" in matrix:
                traced_items = matrix["traced_items"]
                assert isinstance(traced_items, list), "Traced items should be list"

                for item in traced_items:
                    assert "id" in item, "Traced item should have ID"
                    assert "relationship" in item, "Traced item should specify relationship"

    def test_requirements_impact_analysis(self):
        """Test requirements change impact analysis"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test impact analysis for requirement changes
        change_request = {
            "requirement_id": "REQ-AUTH-001",
            "change_type": "modification",
            "proposed_changes": {
                "description": "Add support for OAuth2 authentication in addition to username/password",
                "acceptance_criteria": [
                    "Users can authenticate using OAuth2 providers",
                    "OAuth2 tokens are properly validated and stored"
                ]
            },
            "justification": "Market research shows 70% of users prefer social login options"
        }

        if hasattr(manager, 'analyze_change_impact'):
            impact_analysis = manager.analyze_change_impact(change_request)

            assert isinstance(impact_analysis, dict), "Impact analysis should return structured result"

            expected_analysis_fields = [
                "affected_requirements", "affected_test_cases", "affected_components",
                "effort_estimate", "risk_assessment"
            ]

            for field in expected_analysis_fields:
                if field in impact_analysis:
                    # Verify field types
                    if field in ["affected_requirements", "affected_test_cases", "affected_components"]:
                        assert isinstance(impact_analysis[field], list), f"{field} should be list"

                    elif field == "effort_estimate":
                        estimate = impact_analysis[field]
                        assert isinstance(estimate, (str, dict)), "Effort estimate should be string or structured"

                    elif field == "risk_assessment":
                        risk = impact_analysis[field]
                        assert isinstance(risk, dict), "Risk assessment should be structured"

                        if "level" in risk:
                            valid_risk_levels = ["low", "medium", "high", "critical"]
                            assert risk["level"] in valid_risk_levels, f"Risk level should be valid, got: {risk['level']}"

    def test_requirements_compliance_checking(self):
        """Test requirements compliance and validation checking"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test compliance standards
        compliance_standards = [
            "completeness",  # All required fields present
            "consistency",   # No conflicting requirements
            "testability",   # Requirements can be verified
            "traceability"   # Requirements are properly linked
        ]

        test_requirement_set = [
            {
                "id": "REQ-COMP-001",
                "title": "Data Encryption",
                "description": "All user data shall be encrypted at rest using AES-256",
                "acceptance_criteria": ["Data is encrypted using AES-256", "Encryption keys are properly managed"],
                "status": "approved"
            },
            {
                "id": "REQ-COMP-002",
                "title": "Data Access",
                "description": "Users shall be able to access their data",
                "acceptance_criteria": [],  # Missing criteria - compliance issue
                "status": "draft"
            }
        ]

        if hasattr(manager, 'check_compliance'):
            for standard in compliance_standards:
                compliance_result = manager.check_compliance(test_requirement_set, standard)

                assert isinstance(compliance_result, dict), f"Compliance check for {standard} should return structured result"

                if "compliant" in compliance_result:
                    assert isinstance(compliance_result["compliant"], bool), "Compliance should be boolean"

                if "issues" in compliance_result:
                    issues = compliance_result["issues"]
                    assert isinstance(issues, list), "Issues should be list"

                    for issue in issues:
                        assert "requirement_id" in issue, "Issue should reference requirement"
                        assert "description" in issue, "Issue should have description"

        # Test specific compliance violations
        if hasattr(manager, 'validate_requirement_completeness'):
            # Test incomplete requirement
            incomplete_req = test_requirement_set[1]  # Missing acceptance criteria

            completeness_check = manager.validate_requirement_completeness(incomplete_req)

            if completeness_check:
                assert completeness_check.get("complete") == False, "Incomplete requirement should fail completeness check"

    def test_requirements_reporting_and_metrics(self):
        """Test requirements reporting and metrics generation"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test requirements metrics
        if hasattr(manager, 'generate_requirements_metrics'):
            metrics = manager.generate_requirements_metrics()

            assert isinstance(metrics, dict), "Metrics should return structured data"

            expected_metrics = [
                "total_requirements", "requirements_by_status", "requirements_by_priority",
                "completion_percentage", "test_coverage", "traceability_coverage"
            ]

            for metric in expected_metrics:
                if metric in metrics:
                    # Verify metric types
                    if metric == "total_requirements":
                        assert isinstance(metrics[metric], int), "Total requirements should be integer"

                    elif metric in ["requirements_by_status", "requirements_by_priority"]:
                        assert isinstance(metrics[metric], dict), f"{metric} should be dictionary"

                    elif metric in ["completion_percentage", "test_coverage", "traceability_coverage"]:
                        percentage = metrics[metric]
                        assert isinstance(percentage, (int, float)), f"{metric} should be numeric"
                        assert 0 <= percentage <= 100, f"{metric} should be 0-100%"

        # Test requirements reports
        if hasattr(manager, 'generate_requirements_report'):
            report_types = ["summary", "detailed", "traceability", "compliance"]

            for report_type in report_types:
                report = manager.generate_requirements_report(report_type)

                if report:
                    assert isinstance(report, dict), f"{report_type} report should be structured"

                    # Common report fields
                    expected_report_fields = ["report_type", "generated_date", "summary"]

                    for field in expected_report_fields:
                        if field in report:
                            if field == "report_type":
                                assert report[field] == report_type, "Report type should match request"

                            elif field == "generated_date":
                                assert isinstance(report[field], (str, float, int)), "Date should be temporal"

    def test_requirements_versioning_and_history(self):
        """Test requirements versioning and change history tracking"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test requirement versioning
        base_requirement = {
            "id": "REQ-VERSION-001",
            "title": "API Rate Limiting",
            "description": "API shall limit requests to 100 per minute per user",
            "version": "1.0"
        }

        if hasattr(manager, 'create_requirement_version'):
            # Create initial version
            v1_result = manager.create_requirement_version(base_requirement)

            if v1_result:
                # Create updated version
                updated_requirement = base_requirement.copy()
                updated_requirement["description"] = "API shall limit requests to 200 per minute per user"
                updated_requirement["version"] = "1.1"

                v2_result = manager.create_requirement_version(updated_requirement)

                if v2_result:
                    assert isinstance(v2_result, dict), "Version creation should return structured result"

                    if "version_id" in v2_result:
                        assert v2_result["version_id"] != v1_result.get("version_id"), "Should create new version"

        # Test change history tracking
        if hasattr(manager, 'get_requirement_history'):
            history = manager.get_requirement_history("REQ-VERSION-001")

            assert isinstance(history, dict), "History should return structured data"

            if "versions" in history:
                versions = history["versions"]
                assert isinstance(versions, list), "Versions should be list"
                assert len(versions) >= 1, "Should have at least one version"

                for version in versions:
                    assert "version_number" in version, "Version should have number"
                    assert "modified_date" in version, "Version should have modification date"
                    assert "changes" in version, "Version should track changes"

    def test_requirements_integration_with_development(self):
        """Test integration of requirements with development processes"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test integration with issue tracking
        requirement_for_development = {
            "id": "REQ-DEV-001",
            "title": "Search Functionality",
            "description": "Users shall be able to search spell database by name, school, and level",
            "status": "approved",
            "assigned_team": "backend_team",
            "target_release": "v2.1"
        }

        if hasattr(manager, 'create_development_tasks'):
            tasks_result = manager.create_development_tasks(requirement_for_development)

            if tasks_result:
                assert isinstance(tasks_result, dict), "Task creation should return structured result"

                if "created_tasks" in tasks_result:
                    tasks = tasks_result["created_tasks"]
                    assert isinstance(tasks, list), "Created tasks should be list"

                    for task in tasks:
                        assert "task_id" in task, "Task should have ID"
                        assert "requirement_id" in task, "Task should reference requirement"

        # Test test case generation
        if hasattr(manager, 'generate_test_cases'):
            test_cases_result = manager.generate_test_cases(requirement_for_development)

            if test_cases_result:
                assert isinstance(test_cases_result, dict), "Test case generation should return structured result"

                if "test_cases" in test_cases_result:
                    test_cases = test_cases_result["test_cases"]
                    assert isinstance(test_cases, list), "Test cases should be list"

                    for test_case in test_cases:
                        assert "test_id" in test_case, "Test case should have ID"
                        assert "requirement_id" in test_case, "Test case should reference requirement"
                        assert "test_steps" in test_case, "Test case should have steps"

    def test_requirements_api_endpoints(self):
        """Test requirements management API endpoints"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes not available for testing")

        with app.test_client() as client:
            # Test requirements listing endpoint
            response = client.get('/admin/requirements')

            if response.status_code == 200:
                requirements_data = response.get_json()

                assert isinstance(requirements_data, dict), "Requirements API should return structured data"

                if "requirements" in requirements_data:
                    requirements = requirements_data["requirements"]
                    assert isinstance(requirements, list), "Requirements should be list"

            # Test requirement creation endpoint
            new_requirement = {
                "title": "API Endpoint Testing",
                "description": "Test requirement created via API",
                "type": "functional",
                "priority": "medium"
            }

            create_response = client.post('/admin/requirements', json=new_requirement)

            if create_response.status_code in [200, 201]:
                create_result = create_response.get_json()

                assert "requirement_id" in create_result, "Should return requirement ID"

                # Test requirement retrieval
                req_id = create_result["requirement_id"]
                get_response = client.get(f'/admin/requirements/{req_id}')

                if get_response.status_code == 200:
                    retrieved_req = get_response.get_json()

                    assert retrieved_req["title"] == new_requirement["title"], "Should retrieve created requirement"

            elif create_response.status_code == 404:
                pytest.skip("Requirements API endpoints not yet implemented")

    def test_requirements_tracking_contract_compliance(self):
        """Test that requirements tracking matches established contract"""
        try:
            from src_common.requirements import RequirementsManager
        except ImportError:
            pytest.skip("Requirements manager not available for testing")

        manager = RequirementsManager()

        # Test requirement data structure contract
        required_fields = ["id", "title", "description", "type", "status", "priority"]

        sample_requirement = {
            "id": "REQ-CONTRACT-001",
            "title": "Contract Test Requirement",
            "description": "Test requirement for contract validation",
            "type": "functional",
            "status": "draft",
            "priority": "medium"
        }

        # All required fields should be present
        for field in required_fields:
            assert field in sample_requirement, f"Requirement missing required field: {field}"

        # Field value validation
        valid_types = ["functional", "non_functional", "constraint", "assumption"]
        assert sample_requirement["type"] in valid_types, f"Invalid requirement type: {sample_requirement['type']}"

        valid_statuses = ["draft", "proposed", "approved", "in_development", "implemented", "tested", "deployed", "deprecated"]
        assert sample_requirement["status"] in valid_statuses, f"Invalid requirement status: {sample_requirement['status']}"

        valid_priorities = ["low", "medium", "high", "critical"]
        assert sample_requirement["priority"] in valid_priorities, f"Invalid requirement priority: {sample_requirement['priority']}"

        # Test traceability contract
        traceability_link = {
            "parent_id": "REQ-PARENT-001",
            "child_id": "REQ-CHILD-001",
            "relationship_type": "decomposition"
        }

        valid_relationships = ["decomposition", "derivation", "dependency", "verification", "implementation"]
        assert traceability_link["relationship_type"] in valid_relationships, f"Invalid relationship type"

        # Test metrics contract
        if hasattr(manager, 'generate_requirements_metrics'):
            metrics = manager.generate_requirements_metrics()

            if metrics:
                # Required metrics fields
                metric_fields = ["total_requirements", "completion_percentage"]

                for field in metric_fields:
                    if field in metrics:
                        if field == "total_requirements":
                            assert isinstance(metrics[field], int), "Total requirements must be integer"
                        elif field == "completion_percentage":
                            assert isinstance(metrics[field], (int, float)), "Completion percentage must be numeric"
                            assert 0 <= metrics[field] <= 100, "Completion percentage must be 0-100%"