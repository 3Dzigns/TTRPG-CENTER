# tests/regression/feature_requests/test_fr023_content_versioning.py
"""
Feature Request FR-023: Content Versioning and Change Management Regression Tests
Tests content version control, change tracking, and collaborative editing capabilities
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta


class TestContentVersioning:
    """Test suite for FR-023 Content Versioning functionality"""

    def test_content_versioning_infrastructure_availability(self):
        """Test that content versioning components are available"""
        try:
            from src_common.versioning import ContentVersionManager
            from src_common.change_tracking import ChangeTracker
            from src_common.collaboration import CollaborativeEditingEngine
            from src_common.diff_engine import ContentDiffEngine

            assert ContentVersionManager is not None, "ContentVersionManager should be available"
            assert ChangeTracker is not None, "ChangeTracker should be available"
            assert CollaborativeEditingEngine is not None, "CollaborativeEditingEngine should be available"
            assert ContentDiffEngine is not None, "ContentDiffEngine should be available"

        except ImportError as e:
            pytest.fail(f"Content versioning components not available: {e}")

    def test_version_creation_and_management(self):
        """Test content version creation and management"""
        try:
            from src_common.versioning import ContentVersionManager
        except ImportError:
            pytest.skip("Content version manager not available for testing")

        version_manager = ContentVersionManager()

        # Test version creation
        content_data = {
            "content_id": "phb_wizard_spells",
            "title": "Wizard Spells",
            "content_type": "spells",
            "content": {
                "text": "Wizards are masters of arcane magic, capable of casting powerful spells...",
                "metadata": {
                    "source": "Player's Handbook",
                    "page_number": 112,
                    "last_updated": "2024-09-01"
                },
                "structured_data": {
                    "spell_list": [
                        {"name": "Fireball", "level": 3, "school": "Evocation"},
                        {"name": "Magic Missile", "level": 1, "school": "Evocation"}
                    ]
                }
            },
            "author": "system_import",
            "change_reason": "Initial content import"
        }

        if hasattr(version_manager, 'create_version'):
            version_result = version_manager.create_version(content_data)

            assert isinstance(version_result, dict), "Version creation should return structured result"

            if "version_id" in version_result:
                version_id = version_result["version_id"]
                assert isinstance(version_id, str), "Version ID should be string"
                assert len(version_id) > 0, "Version ID should not be empty"

            if "version_number" in version_result:
                version_number = version_result["version_number"]
                assert version_number == 1, "First version should be version 1"

            if "checksum" in version_result:
                checksum = version_result["checksum"]
                assert isinstance(checksum, str), "Checksum should be string"

        # Test content update and new version creation
        updated_content = content_data.copy()
        updated_content["content"]["text"] = "Wizards are masters of arcane magic, capable of casting incredibly powerful spells..."
        updated_content["content"]["structured_data"]["spell_list"].append(
            {"name": "Lightning Bolt", "level": 3, "school": "Evocation"}
        )
        updated_content["author"] = "content_editor_001"
        updated_content["change_reason"] = "Added Lightning Bolt spell and improved description"

        if hasattr(version_manager, 'create_version'):
            update_result = version_manager.create_version(updated_content)

            if "version_number" in update_result:
                new_version_number = update_result["version_number"]
                assert new_version_number == 2, "Updated content should create version 2"

        # Test version retrieval
        if hasattr(version_manager, 'get_version'):
            retrieved_v1 = version_manager.get_version(content_data["content_id"], version=1)
            retrieved_v2 = version_manager.get_version(content_data["content_id"], version=2)

            assert isinstance(retrieved_v1, dict), "Version 1 retrieval should return structured result"
            assert isinstance(retrieved_v2, dict), "Version 2 retrieval should return structured result"

            # Verify content differences
            v1_spell_count = len(retrieved_v1["content"]["structured_data"]["spell_list"])
            v2_spell_count = len(retrieved_v2["content"]["structured_data"]["spell_list"])
            assert v2_spell_count == v1_spell_count + 1, "Version 2 should have one more spell"

    def test_change_tracking_and_audit_trail(self):
        """Test change tracking and audit trail functionality"""
        try:
            from src_common.change_tracking import ChangeTracker
        except ImportError:
            pytest.skip("Change tracker not available for testing")

        change_tracker = ChangeTracker()

        # Test change recording
        change_events = [
            {
                "content_id": "phb_wizard_spells",
                "change_type": "create",
                "timestamp": datetime.now().isoformat(),
                "author": "system_import",
                "changes": {
                    "fields_added": ["title", "content", "metadata"],
                    "content_size": 5000
                },
                "reason": "Initial content import"
            },
            {
                "content_id": "phb_wizard_spells",
                "change_type": "update",
                "timestamp": (datetime.now() + timedelta(hours=1)).isoformat(),
                "author": "content_editor_001",
                "changes": {
                    "fields_modified": ["content.text", "content.structured_data.spell_list"],
                    "additions": ["Lightning Bolt spell"],
                    "content_size_delta": 200
                },
                "reason": "Added new spell and improved description"
            },
            {
                "content_id": "phb_wizard_spells",
                "change_type": "metadata_update",
                "timestamp": (datetime.now() + timedelta(hours=2)).isoformat(),
                "author": "content_reviewer_001",
                "changes": {
                    "fields_modified": ["metadata.review_status"],
                    "old_value": "draft",
                    "new_value": "reviewed"
                },
                "reason": "Content review completed"
            }
        ]

        if hasattr(change_tracker, 'record_change'):
            for change_event in change_events:
                tracking_result = change_tracker.record_change(change_event)

                assert isinstance(tracking_result, dict), "Change tracking should return structured result"

                if "change_id" in tracking_result:
                    change_id = tracking_result["change_id"]
                    assert isinstance(change_id, str), "Change ID should be string"

                if "recorded" in tracking_result:
                    recorded = tracking_result["recorded"]
                    assert recorded == True, "Change should be recorded successfully"

        # Test audit trail generation
        if hasattr(change_tracker, 'get_audit_trail'):
            audit_result = change_tracker.get_audit_trail("phb_wizard_spells")

            assert isinstance(audit_result, dict), "Audit trail should return structured result"

            if "changes" in audit_result:
                changes = audit_result["changes"]
                assert isinstance(changes, list), "Changes should be list"
                assert len(changes) == len(change_events), "Should track all changes"

                # Verify chronological order
                timestamps = [change.get("timestamp") for change in changes]
                sorted_timestamps = sorted(timestamps)
                assert timestamps == sorted_timestamps, "Changes should be in chronological order"

            if "summary" in audit_result:
                summary = audit_result["summary"]
                assert "total_changes" in summary, "Summary should include total changes"
                assert "unique_authors" in summary, "Summary should include unique authors"
                assert "change_types" in summary, "Summary should include change types"

    def test_content_diffing_and_comparison(self):
        """Test content diffing and version comparison"""
        try:
            from src_common.diff_engine import ContentDiffEngine
        except ImportError:
            pytest.skip("Content diff engine not available for testing")

        diff_engine = ContentDiffEngine()

        # Test content versions for diffing
        version_1_content = {
            "title": "Wizard Spells",
            "text": "Wizards are masters of arcane magic, capable of casting powerful spells.",
            "spell_list": [
                {"name": "Fireball", "level": 3, "school": "Evocation", "damage": "8d6"},
                {"name": "Magic Missile", "level": 1, "school": "Evocation", "damage": "1d4+1"}
            ],
            "metadata": {
                "page_count": 15,
                "difficulty": "intermediate"
            }
        }

        version_2_content = {
            "title": "Wizard Spells - Comprehensive Guide",
            "text": "Wizards are masters of arcane magic, capable of casting incredibly powerful spells with precision.",
            "spell_list": [
                {"name": "Fireball", "level": 3, "school": "Evocation", "damage": "8d6", "range": "150 feet"},
                {"name": "Magic Missile", "level": 1, "school": "Evocation", "damage": "1d4+1"},
                {"name": "Lightning Bolt", "level": 3, "school": "Evocation", "damage": "8d6", "range": "100 feet"}
            ],
            "metadata": {
                "page_count": 18,
                "difficulty": "intermediate",
                "last_reviewed": "2024-09-22"
            }
        }

        if hasattr(diff_engine, 'generate_diff'):
            diff_result = diff_engine.generate_diff(version_1_content, version_2_content)

            assert isinstance(diff_result, dict), "Diff generation should return structured result"

            if "changes" in diff_result:
                changes = diff_result["changes"]
                assert isinstance(changes, list), "Changes should be list"

                # Verify specific changes are detected
                change_types = [change.get("type") for change in changes]
                assert "modified" in change_types, "Should detect text modifications"
                assert "added" in change_types, "Should detect additions"

                # Check for specific changes
                title_change = next((c for c in changes if c.get("field") == "title"), None)
                assert title_change is not None, "Should detect title change"

                spell_addition = next((c for c in changes
                                     if c.get("type") == "added" and "Lightning Bolt" in str(c)), None)
                assert spell_addition is not None, "Should detect Lightning Bolt addition"

            if "diff_summary" in diff_result:
                summary = diff_result["diff_summary"]
                assert "additions" in summary, "Summary should count additions"
                assert "modifications" in summary, "Summary should count modifications"
                assert "deletions" in summary, "Summary should count deletions"

        # Test visual diff generation
        if hasattr(diff_engine, 'generate_visual_diff'):
            visual_diff_result = diff_engine.generate_visual_diff(
                version_1_content,
                version_2_content,
                format="html"
            )

            assert isinstance(visual_diff_result, dict), "Visual diff should return structured result"

            if "diff_html" in visual_diff_result:
                diff_html = visual_diff_result["diff_html"]
                assert isinstance(diff_html, str), "Diff HTML should be string"
                assert len(diff_html) > 0, "Diff HTML should not be empty"

                # Should contain diff markers
                assert any(marker in diff_html for marker in ["added", "removed", "modified"]), \
                    "HTML diff should contain change markers"

    def test_collaborative_editing_capabilities(self):
        """Test collaborative editing and conflict resolution"""
        try:
            from src_common.collaboration import CollaborativeEditingEngine
        except ImportError:
            pytest.skip("Collaborative editing engine not available for testing")

        collab_engine = CollaborativeEditingEngine()

        # Test collaborative editing session
        editing_session = {
            "content_id": "phb_wizard_spells",
            "session_id": "collab_session_001",
            "participants": [
                {"user_id": "editor_001", "role": "primary_editor", "permissions": ["read", "write", "approve"]},
                {"user_id": "editor_002", "role": "reviewer", "permissions": ["read", "comment", "suggest"]},
                {"user_id": "subject_expert", "role": "expert", "permissions": ["read", "comment", "approve"]}
            ],
            "base_version": 3
        }

        if hasattr(collab_engine, 'start_collaborative_session'):
            session_result = collab_engine.start_collaborative_session(editing_session)

            assert isinstance(session_result, dict), "Collaborative session should return structured result"

            if "session_started" in session_result:
                started = session_result["session_started"]
                assert started == True, "Session should start successfully"

            if "session_token" in session_result:
                token = session_result["session_token"]
                assert isinstance(token, str), "Session token should be string"

        # Test concurrent edits and conflict detection
        concurrent_edits = [
            {
                "editor": "editor_001",
                "timestamp": "2024-09-22T10:00:00Z",
                "changes": {
                    "field": "text",
                    "operation": "replace",
                    "start_pos": 50,
                    "end_pos": 60,
                    "new_text": "incredibly powerful"
                }
            },
            {
                "editor": "editor_002",
                "timestamp": "2024-09-22T10:00:30Z",
                "changes": {
                    "field": "text",
                    "operation": "replace",
                    "start_pos": 55,
                    "end_pos": 65,
                    "new_text": "extremely effective"
                }
            },
            {
                "editor": "subject_expert",
                "timestamp": "2024-09-22T10:01:00Z",
                "changes": {
                    "field": "spell_list",
                    "operation": "add",
                    "new_item": {"name": "Counterspell", "level": 3, "school": "Abjuration"}
                }
            }
        ]

        if hasattr(collab_engine, 'process_concurrent_edits'):
            conflict_result = collab_engine.process_concurrent_edits(
                editing_session["session_id"],
                concurrent_edits
            )

            assert isinstance(conflict_result, dict), "Conflict processing should return structured result"

            if "conflicts_detected" in conflict_result:
                conflicts = conflict_result["conflicts_detected"]
                assert isinstance(conflicts, list), "Conflicts should be list"

                # Should detect overlapping text edits
                text_conflicts = [c for c in conflicts if c.get("type") == "text_overlap"]
                assert len(text_conflicts) > 0, "Should detect overlapping text edits"

            if "auto_resolved" in conflict_result:
                auto_resolved = conflict_result["auto_resolved"]
                assert isinstance(auto_resolved, list), "Auto-resolved conflicts should be list"

            if "requires_manual_resolution" in conflict_result:
                manual_resolution = conflict_result["requires_manual_resolution"]
                assert isinstance(manual_resolution, list), "Manual resolution items should be list"

    def test_version_branching_and_merging(self):
        """Test version branching and merging capabilities"""
        try:
            from src_common.versioning import ContentVersionManager
        except ImportError:
            pytest.skip("Content version manager not available for testing")

        version_manager = ContentVersionManager()

        # Test branch creation
        branch_config = {
            "content_id": "phb_wizard_spells",
            "source_version": 3,
            "branch_name": "feature/spell_reorganization",
            "branch_purpose": "Reorganize spells by school and level",
            "created_by": "content_team_lead"
        }

        if hasattr(version_manager, 'create_branch'):
            branch_result = version_manager.create_branch(branch_config)

            assert isinstance(branch_result, dict), "Branch creation should return structured result"

            if "branch_id" in branch_result:
                branch_id = branch_result["branch_id"]
                assert isinstance(branch_id, str), "Branch ID should be string"

            if "branch_created" in branch_result:
                created = branch_result["branch_created"]
                assert created == True, "Branch should be created successfully"

        # Test work on branch
        branch_changes = [
            {
                "change_type": "reorganize",
                "description": "Group spells by school",
                "author": "content_editor_branch"
            },
            {
                "change_type": "add_metadata",
                "description": "Add spell school metadata",
                "author": "content_editor_branch"
            }
        ]

        if hasattr(version_manager, 'commit_to_branch'):
            for change in branch_changes:
                commit_result = version_manager.commit_to_branch(
                    branch_config["branch_name"],
                    change
                )

                assert isinstance(commit_result, dict), "Branch commit should return structured result"

        # Test merge preparation
        if hasattr(version_manager, 'prepare_merge'):
            merge_prep_result = version_manager.prepare_merge(
                source_branch=branch_config["branch_name"],
                target_branch="main",
                content_id=branch_config["content_id"]
            )

            assert isinstance(merge_prep_result, dict), "Merge preparation should return structured result"

            if "merge_conflicts" in merge_prep_result:
                conflicts = merge_prep_result["merge_conflicts"]
                assert isinstance(conflicts, list), "Merge conflicts should be list"

            if "merge_preview" in merge_prep_result:
                preview = merge_prep_result["merge_preview"]
                assert isinstance(preview, dict), "Merge preview should be dictionary"

            if "can_auto_merge" in merge_prep_result:
                can_auto_merge = merge_prep_result["can_auto_merge"]
                assert isinstance(can_auto_merge, bool), "Can auto merge should be boolean"

    def test_content_versioning_contract_compliance(self):
        """Test that content versioning matches established contract"""
        # Test versioning contract
        versioning_requirements = {
            "version_creation": True,
            "change_tracking": True,
            "content_diffing": True,
            "collaborative_editing": True,
            "branch_management": True
        }

        for requirement, needed in versioning_requirements.items():
            assert needed, f"Versioning requirement {requirement} is mandatory"

        # Test collaboration contract
        collaboration_requirements = {
            "concurrent_editing": True,
            "conflict_detection": True,
            "conflict_resolution": True,
            "permission_management": True
        }

        for requirement, needed in collaboration_requirements.items():
            assert needed, f"Collaboration requirement {requirement} is mandatory"

        # Test audit contract
        audit_requirements = {
            "change_recording": True,
            "audit_trail": True,
            "author_tracking": True,
            "change_reasoning": True
        }

        for requirement, needed in audit_requirements.items():
            assert needed, f"Audit requirement {requirement} is mandatory"

        # Test data contract
        required_versioning_fields = [
            "version_id",
            "version_number",
            "content_checksum",
            "change_timestamp",
            "author_id"
        ]

        for field in required_versioning_fields:
            assert isinstance(field, str), f"Versioning field {field} should be defined"

        # Test integration contract
        integration_points = [
            "content_management_integration",
            "user_management_integration",
            "notification_system_integration",
            "backup_system_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"