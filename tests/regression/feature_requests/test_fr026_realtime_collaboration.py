"""
FR-026: Real-time Collaboration and Concurrent Editing
Test comprehensive real-time collaboration capabilities for multi-user content editing.

This module tests the real-time collaboration system that enables multiple users
to simultaneously edit documents, share sessions, and collaborate on content
with conflict resolution and operational transformation support.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional

from tests.regression.feature_requests.base_fr_test import BaseFRTest


class TestFR026RealtimeCollaboration(BaseFRTest):
    """Test suite for FR-026 Real-time Collaboration and Concurrent Editing."""

    async def asyncSetUp(self):
        """Set up test environment with collaboration infrastructure."""
        await super().asyncSetUp()
        self.collaboration_engine = self._create_mock_collaboration_engine()
        self.websocket_manager = self._create_mock_websocket_manager()
        self.operational_transform = self._create_mock_operational_transform()
        self.conflict_resolver = self._create_mock_conflict_resolver()

    def _create_mock_collaboration_engine(self) -> Mock:
        """Create mock collaboration engine for testing."""
        engine = Mock()
        engine.create_session = AsyncMock()
        engine.join_session = AsyncMock()
        engine.leave_session = AsyncMock()
        engine.sync_document = AsyncMock()
        engine.apply_operation = AsyncMock()
        return engine

    def _create_mock_websocket_manager(self) -> Mock:
        """Create mock WebSocket connection manager."""
        manager = Mock()
        manager.connect_user = AsyncMock()
        manager.disconnect_user = AsyncMock()
        manager.broadcast_operation = AsyncMock()
        manager.send_to_user = AsyncMock()
        manager.get_active_users = AsyncMock()
        return manager

    def _create_mock_operational_transform(self) -> Mock:
        """Create mock operational transformation system."""
        ot = Mock()
        ot.transform_operation = AsyncMock()
        ot.compose_operations = AsyncMock()
        ot.invert_operation = AsyncMock()
        ot.apply_to_document = AsyncMock()
        return ot

    def _create_mock_conflict_resolver(self) -> Mock:
        """Create mock conflict resolution system."""
        resolver = Mock()
        resolver.detect_conflicts = AsyncMock()
        resolver.resolve_conflict = AsyncMock()
        resolver.merge_changes = AsyncMock()
        resolver.create_resolution_strategy = AsyncMock()
        return resolver

    async def test_realtime_document_synchronization(self):
        """Test real-time document synchronization across multiple users."""
        # Mock document and user setup
        document_id = "test_doc_123"
        users = [
            {"user_id": "user1", "name": "Alice", "role": "editor"},
            {"user_id": "user2", "name": "Bob", "role": "reviewer"},
            {"user_id": "user3", "name": "Charlie", "role": "editor"}
        ]

        # Mock initial document state
        initial_document = {
            "id": document_id,
            "content": "# TTRPG Campaign Guide\n\n## Chapter 1: Introduction\nWelcome to the adventure!",
            "version": 1,
            "last_modified": "2024-01-01T10:00:00Z",
            "collaborators": []
        }

        # Configure collaboration session creation
        self.collaboration_engine.create_session.return_value = {
            "session_id": "session_abc123",
            "document_id": document_id,
            "created_at": "2024-01-01T10:00:00Z",
            "owner": "user1",
            "participants": [],
            "document_state": initial_document,
            "operation_log": []
        }

        # Test session creation
        session = await self.collaboration_engine.create_session(document_id, "user1")

        # Verify session structure
        self.assertIn("session_id", session)
        self.assertIn("document_id", session)
        self.assertIn("document_state", session)
        self.assertEqual(session["document_id"], document_id)
        self.assertEqual(session["owner"], "user1")

        # Test users joining session
        for user in users:
            self.collaboration_engine.join_session.return_value = {
                "success": True,
                "user_id": user["user_id"],
                "session_id": session["session_id"],
                "current_document": session["document_state"],
                "active_participants": len(session["participants"]) + 1,
                "user_cursor": {"line": 1, "column": 1},
                "permissions": {
                    "can_edit": user["role"] in ["editor"],
                    "can_comment": True,
                    "can_view": True
                }
            }

            join_result = await self.collaboration_engine.join_session(
                session["session_id"], user["user_id"]
            )

            # Verify join success
            self.assertTrue(join_result["success"])
            self.assertEqual(join_result["user_id"], user["user_id"])
            self.assertIn("permissions", join_result)
            self.assertIn("current_document", join_result)

        # Test WebSocket connections
        for user in users:
            self.websocket_manager.connect_user.return_value = {
                "connection_id": f"ws_{user['user_id']}",
                "user_id": user["user_id"],
                "session_id": session["session_id"],
                "connected_at": "2024-01-01T10:05:00Z",
                "heartbeat_interval": 30
            }

            connection = await self.websocket_manager.connect_user(
                user["user_id"], session["session_id"]
            )

            # Verify WebSocket connection
            self.assertIn("connection_id", connection)
            self.assertIn("heartbeat_interval", connection)
            self.assertEqual(connection["user_id"], user["user_id"])

    async def test_concurrent_editing_with_operational_transformation(self):
        """Test concurrent editing with operational transformation for conflict resolution."""
        # Mock document state
        document_content = "Line 1\nLine 2\nLine 3"

        # Mock concurrent operations from different users
        operation_user1 = {
            "type": "insert",
            "position": 7,  # After "Line 1\n"
            "content": "New content here\n",
            "user_id": "user1",
            "timestamp": "2024-01-01T10:01:00Z",
            "operation_id": "op_001"
        }

        operation_user2 = {
            "type": "delete",
            "position": 14,  # "Line 2\n"
            "length": 7,
            "user_id": "user2",
            "timestamp": "2024-01-01T10:01:05Z",
            "operation_id": "op_002"
        }

        operation_user3 = {
            "type": "replace",
            "position": 21,  # "Line 3"
            "length": 6,
            "content": "Modified Line 3",
            "user_id": "user3",
            "timestamp": "2024-01-01T10:01:10Z",
            "operation_id": "op_003"
        }

        # Configure operational transformation
        self.operational_transform.transform_operation.side_effect = [
            # Transform op_002 against op_001
            {
                "type": "delete",
                "position": 30,  # Adjusted for insertion
                "length": 7,
                "user_id": "user2",
                "timestamp": "2024-01-01T10:01:05Z",
                "operation_id": "op_002_transformed",
                "transformed_against": ["op_001"]
            },
            # Transform op_003 against op_001 and op_002
            {
                "type": "replace",
                "position": 30,  # Adjusted for insert and delete
                "length": 6,
                "content": "Modified Line 3",
                "user_id": "user3",
                "timestamp": "2024-01-01T10:01:10Z",
                "operation_id": "op_003_transformed",
                "transformed_against": ["op_001", "op_002_transformed"]
            }
        ]

        # Test operation transformation
        transformed_op2 = await self.operational_transform.transform_operation(
            operation_user2, [operation_user1]
        )
        transformed_op3 = await self.operational_transform.transform_operation(
            operation_user3, [operation_user1, transformed_op2]
        )

        # Verify transformations
        self.assertIn("transformed_against", transformed_op2)
        self.assertIn("transformed_against", transformed_op3)
        self.assertEqual(transformed_op2["position"], 30)  # Position adjusted
        self.assertEqual(transformed_op3["position"], 30)  # Position adjusted

        # Configure document application
        self.operational_transform.apply_to_document.side_effect = [
            "Line 1\nNew content here\nLine 2\nLine 3",  # After op_001
            "Line 1\nNew content here\nLine 3",  # After op_002_transformed
            "Line 1\nNew content here\nModified Line 3"  # After op_003_transformed
        ]

        # Test sequential application
        result1 = await self.operational_transform.apply_to_document(document_content, operation_user1)
        result2 = await self.operational_transform.apply_to_document(result1, transformed_op2)
        result3 = await self.operational_transform.apply_to_document(result2, transformed_op3)

        # Verify final result
        self.assertEqual(result3, "Line 1\nNew content here\nModified Line 3")

        # Test operation broadcasting
        self.websocket_manager.broadcast_operation.return_value = {
            "broadcast_id": "broadcast_123",
            "operation": operation_user1,
            "recipients": ["user2", "user3"],
            "sent_at": "2024-01-01T10:01:00Z",
            "delivery_confirmations": []
        }

        broadcast_result = await self.websocket_manager.broadcast_operation(
            "session_abc123", operation_user1, exclude_user="user1"
        )

        # Verify broadcast
        self.assertIn("broadcast_id", broadcast_result)
        self.assertIn("recipients", broadcast_result)
        self.assertEqual(len(broadcast_result["recipients"]), 2)

    async def test_conflict_detection_and_resolution(self):
        """Test conflict detection and automated resolution strategies."""
        # Mock conflicting operations
        operation_a = {
            "type": "replace",
            "position": 10,
            "length": 5,
            "content": "Hello",
            "user_id": "user1",
            "timestamp": "2024-01-01T10:01:00Z"
        }

        operation_b = {
            "type": "replace",
            "position": 12,
            "length": 8,
            "content": "World",
            "user_id": "user2",
            "timestamp": "2024-01-01T10:01:02Z"
        }

        # Configure conflict detection
        self.conflict_resolver.detect_conflicts.return_value = {
            "has_conflicts": True,
            "conflict_type": "overlapping_edits",
            "conflicting_operations": [operation_a, operation_b],
            "conflict_severity": "medium",
            "affected_range": {"start": 10, "end": 20},
            "resolution_required": True,
            "auto_resolvable": True
        }

        # Test conflict detection
        conflict_result = await self.conflict_resolver.detect_conflicts([operation_a, operation_b])

        # Verify conflict detection
        self.assertTrue(conflict_result["has_conflicts"])
        self.assertEqual(conflict_result["conflict_type"], "overlapping_edits")
        self.assertEqual(len(conflict_result["conflicting_operations"]), 2)
        self.assertIn("affected_range", conflict_result)

        # Configure resolution strategies
        self.conflict_resolver.create_resolution_strategy.return_value = {
            "strategy": "timestamp_priority",
            "description": "Apply operations in timestamp order with transformation",
            "steps": [
                {"action": "apply", "operation": operation_a, "reason": "earlier_timestamp"},
                {"action": "transform_and_apply", "operation": operation_b, "transform_against": [operation_a]}
            ],
            "expected_result": "Resolved content with both changes integrated",
            "confidence": 0.85
        }

        # Test resolution strategy creation
        strategy = await self.conflict_resolver.create_resolution_strategy(conflict_result)

        # Verify strategy
        self.assertIn("strategy", strategy)
        self.assertIn("steps", strategy)
        self.assertIn("confidence", strategy)
        self.assertGreater(strategy["confidence"], 0.8)
        self.assertEqual(len(strategy["steps"]), 2)

        # Configure merge execution
        self.conflict_resolver.merge_changes.return_value = {
            "success": True,
            "merged_content": "Original Hello World text",
            "operations_applied": [operation_a, "transformed_operation_b"],
            "resolution_method": "timestamp_priority",
            "merge_timestamp": "2024-01-01T10:01:05Z",
            "conflicts_resolved": 1,
            "manual_review_required": False
        }

        # Test conflict resolution
        merge_result = await self.conflict_resolver.merge_changes([operation_a, operation_b], strategy)

        # Verify merge result
        self.assertTrue(merge_result["success"])
        self.assertIn("merged_content", merge_result)
        self.assertIn("operations_applied", merge_result)
        self.assertFalse(merge_result["manual_review_required"])
        self.assertEqual(merge_result["conflicts_resolved"], 1)

    async def test_user_presence_and_cursor_tracking(self):
        """Test real-time user presence awareness and cursor position tracking."""
        # Mock active users in session
        session_users = [
            {
                "user_id": "user1",
                "name": "Alice",
                "avatar": "avatar1.png",
                "role": "editor",
                "status": "active"
            },
            {
                "user_id": "user2",
                "name": "Bob",
                "avatar": "avatar2.png",
                "role": "reviewer",
                "status": "typing"
            },
            {
                "user_id": "user3",
                "name": "Charlie",
                "avatar": "avatar3.png",
                "role": "viewer",
                "status": "idle"
            }
        ]

        # Configure presence tracking
        self.websocket_manager.get_active_users.return_value = {
            "session_id": "session_abc123",
            "active_users": session_users,
            "total_connected": 3,
            "last_activity": {
                "user1": "2024-01-01T10:05:00Z",
                "user2": "2024-01-01T10:04:45Z",
                "user3": "2024-01-01T10:03:30Z"
            },
            "cursor_positions": {
                "user1": {"line": 5, "column": 12, "selection": None},
                "user2": {"line": 3, "column": 8, "selection": {"start": {"line": 3, "column": 8}, "end": {"line": 3, "column": 15}}},
                "user3": {"line": 1, "column": 1, "selection": None}
            },
            "typing_indicators": {
                "user2": {"is_typing": True, "started_at": "2024-01-01T10:04:40Z"}
            }
        }

        # Test presence retrieval
        presence = await self.websocket_manager.get_active_users("session_abc123")

        # Verify presence structure
        self.assertIn("active_users", presence)
        self.assertIn("cursor_positions", presence)
        self.assertIn("typing_indicators", presence)
        self.assertEqual(presence["total_connected"], 3)

        # Verify user presence
        users = presence["active_users"]
        self.assertEqual(len(users), 3)
        for user in users:
            self.assertIn("user_id", user)
            self.assertIn("name", user)
            self.assertIn("status", user)
            self.assertIn(user["status"], ["active", "typing", "idle", "away"])

        # Verify cursor tracking
        cursors = presence["cursor_positions"]
        self.assertEqual(len(cursors), 3)
        for user_id, cursor in cursors.items():
            self.assertIn("line", cursor)
            self.assertIn("column", cursor)
            self.assertIn("selection", cursor)
            self.assertGreaterEqual(cursor["line"], 1)
            self.assertGreaterEqual(cursor["column"], 1)

        # Test cursor update broadcasting
        cursor_update = {
            "user_id": "user1",
            "position": {"line": 7, "column": 20},
            "selection": {"start": {"line": 7, "column": 15}, "end": {"line": 7, "column": 25}},
            "timestamp": "2024-01-01T10:05:30Z"
        }

        self.websocket_manager.broadcast_operation.return_value = {
            "type": "cursor_update",
            "data": cursor_update,
            "recipients": ["user2", "user3"],
            "sent_at": "2024-01-01T10:05:30Z"
        }

        # Test cursor update broadcast
        cursor_broadcast = await self.websocket_manager.broadcast_operation(
            "session_abc123", {"type": "cursor_update", "data": cursor_update}, exclude_user="user1"
        )

        # Verify cursor broadcast
        self.assertEqual(cursor_broadcast["type"], "cursor_update")
        self.assertIn("recipients", cursor_broadcast)
        self.assertEqual(len(cursor_broadcast["recipients"]), 2)

    async def test_comment_and_annotation_system(self):
        """Test collaborative commenting and annotation features."""
        # Mock document with annotations
        document_annotations = {
            "document_id": "test_doc_123",
            "comments": [
                {
                    "comment_id": "comment_001",
                    "user_id": "user1",
                    "content": "This section needs more detail about character creation",
                    "position": {"line": 3, "column": 1},
                    "created_at": "2024-01-01T10:00:00Z",
                    "resolved": False,
                    "replies": []
                },
                {
                    "comment_id": "comment_002",
                    "user_id": "user2",
                    "content": "Great introduction! Very engaging.",
                    "position": {"line": 1, "column": 1},
                    "created_at": "2024-01-01T10:05:00Z",
                    "resolved": False,
                    "replies": [
                        {
                            "reply_id": "reply_001",
                            "user_id": "user1",
                            "content": "Thanks! I'll expand on it further.",
                            "created_at": "2024-01-01T10:10:00Z"
                        }
                    ]
                }
            ],
            "highlights": [
                {
                    "highlight_id": "highlight_001",
                    "user_id": "user3",
                    "range": {"start": {"line": 2, "column": 5}, "end": {"line": 2, "column": 20}},
                    "color": "#ffeb3b",
                    "note": "Important terminology",
                    "created_at": "2024-01-01T10:15:00Z"
                }
            ]
        }

        # Test comment creation
        new_comment = {
            "user_id": "user3",
            "content": "Should we add an example here?",
            "position": {"line": 4, "column": 10},
            "type": "suggestion"
        }

        self.collaboration_engine.apply_operation.return_value = {
            "success": True,
            "operation_type": "add_comment",
            "comment_id": "comment_003",
            "comment": {
                **new_comment,
                "comment_id": "comment_003",
                "created_at": "2024-01-01T10:20:00Z",
                "resolved": False,
                "replies": []
            },
            "notification_sent": True
        }

        # Test comment addition
        comment_result = await self.collaboration_engine.apply_operation(
            "session_abc123", {"type": "add_comment", "data": new_comment}
        )

        # Verify comment creation
        self.assertTrue(comment_result["success"])
        self.assertIn("comment_id", comment_result)
        self.assertEqual(comment_result["operation_type"], "add_comment")

        # Test comment reply
        reply_data = {
            "comment_id": "comment_003",
            "user_id": "user1",
            "content": "Yes, a practical example would be helpful"
        }

        self.collaboration_engine.apply_operation.return_value = {
            "success": True,
            "operation_type": "add_reply",
            "reply_id": "reply_002",
            "parent_comment": "comment_003",
            "reply": {
                **reply_data,
                "reply_id": "reply_002",
                "created_at": "2024-01-01T10:25:00Z"
            }
        }

        # Test reply addition
        reply_result = await self.collaboration_engine.apply_operation(
            "session_abc123", {"type": "add_reply", "data": reply_data}
        )

        # Verify reply creation
        self.assertTrue(reply_result["success"])
        self.assertIn("reply_id", reply_result)
        self.assertEqual(reply_result["parent_comment"], "comment_003")

        # Test annotation highlighting
        highlight_data = {
            "user_id": "user2",
            "range": {"start": {"line": 5, "column": 1}, "end": {"line": 5, "column": 15}},
            "color": "#4caf50",
            "note": "Key concept",
            "category": "important"
        }

        self.collaboration_engine.apply_operation.return_value = {
            "success": True,
            "operation_type": "add_highlight",
            "highlight_id": "highlight_002",
            "highlight": {
                **highlight_data,
                "highlight_id": "highlight_002",
                "created_at": "2024-01-01T10:30:00Z"
            }
        }

        # Test highlight addition
        highlight_result = await self.collaboration_engine.apply_operation(
            "session_abc123", {"type": "add_highlight", "data": highlight_data}
        )

        # Verify highlight creation
        self.assertTrue(highlight_result["success"])
        self.assertIn("highlight_id", highlight_result)
        self.assertEqual(highlight_result["operation_type"], "add_highlight")

    async def test_permission_management_and_access_control(self):
        """Test role-based permissions and access control in collaborative sessions."""
        # Mock user roles and permissions
        user_permissions = {
            "owner": {
                "can_edit": True,
                "can_delete": True,
                "can_invite": True,
                "can_manage_permissions": True,
                "can_comment": True,
                "can_resolve_comments": True,
                "can_export": True,
                "can_view_history": True
            },
            "editor": {
                "can_edit": True,
                "can_delete": False,
                "can_invite": False,
                "can_manage_permissions": False,
                "can_comment": True,
                "can_resolve_comments": True,
                "can_export": True,
                "can_view_history": True
            },
            "reviewer": {
                "can_edit": False,
                "can_delete": False,
                "can_invite": False,
                "can_manage_permissions": False,
                "can_comment": True,
                "can_resolve_comments": False,
                "can_export": False,
                "can_view_history": True
            },
            "viewer": {
                "can_edit": False,
                "can_delete": False,
                "can_invite": False,
                "can_manage_permissions": False,
                "can_comment": False,
                "can_resolve_comments": False,
                "can_export": False,
                "can_view_history": False
            }
        }

        # Test permission checking for different operations
        test_operations = [
            {"type": "edit_content", "required_permission": "can_edit"},
            {"type": "delete_section", "required_permission": "can_delete"},
            {"type": "add_comment", "required_permission": "can_comment"},
            {"type": "resolve_comment", "required_permission": "can_resolve_comments"},
            {"type": "invite_user", "required_permission": "can_invite"},
            {"type": "change_permissions", "required_permission": "can_manage_permissions"}
        ]

        for role, permissions in user_permissions.items():
            for operation in test_operations:
                # Mock permission check
                has_permission = permissions.get(operation["required_permission"], False)

                self.collaboration_engine.apply_operation.return_value = {
                    "success": has_permission,
                    "operation_type": operation["type"],
                    "user_role": role,
                    "permission_required": operation["required_permission"],
                    "permission_granted": has_permission,
                    "error": None if has_permission else "insufficient_permissions"
                }

                # Test operation with role
                result = await self.collaboration_engine.apply_operation(
                    "session_abc123",
                    {
                        "type": operation["type"],
                        "user_id": f"test_user_{role}",
                        "user_role": role
                    }
                )

                # Verify permission enforcement
                expected_success = permissions.get(operation["required_permission"], False)
                self.assertEqual(result["success"], expected_success)
                self.assertEqual(result["permission_granted"], expected_success)

                if not expected_success:
                    self.assertEqual(result["error"], "insufficient_permissions")

        # Test permission escalation request
        escalation_request = {
            "user_id": "reviewer_user",
            "current_role": "reviewer",
            "requested_role": "editor",
            "justification": "Need to make corrections to technical content",
            "session_id": "session_abc123"
        }

        self.collaboration_engine.apply_operation.return_value = {
            "success": True,
            "operation_type": "request_permission_escalation",
            "request_id": "escalation_001",
            "status": "pending",
            "requires_approval_from": ["owner"],
            "expires_at": "2024-01-01T12:00:00Z"
        }

        # Test escalation request
        escalation_result = await self.collaboration_engine.apply_operation(
            "session_abc123", {"type": "request_permission_escalation", "data": escalation_request}
        )

        # Verify escalation request
        self.assertTrue(escalation_result["success"])
        self.assertIn("request_id", escalation_result)
        self.assertEqual(escalation_result["status"], "pending")
        self.assertIn("requires_approval_from", escalation_result)

    async def test_session_persistence_and_recovery(self):
        """Test session persistence, recovery, and history management."""
        # Mock session state for persistence
        session_state = {
            "session_id": "session_abc123",
            "document_id": "test_doc_123",
            "participants": ["user1", "user2", "user3"],
            "operation_log": [
                {"operation_id": "op_001", "type": "insert", "timestamp": "2024-01-01T10:01:00Z"},
                {"operation_id": "op_002", "type": "delete", "timestamp": "2024-01-01T10:02:00Z"},
                {"operation_id": "op_003", "type": "replace", "timestamp": "2024-01-01T10:03:00Z"}
            ],
            "current_version": 4,
            "checkpoints": [
                {"version": 1, "timestamp": "2024-01-01T10:00:00Z", "content_hash": "hash1"},
                {"version": 3, "timestamp": "2024-01-01T10:02:30Z", "content_hash": "hash3"}
            ],
            "last_saved": "2024-01-01T10:03:00Z"
        }

        # Test session persistence
        self.collaboration_engine.sync_document.return_value = {
            "success": True,
            "session_id": "session_abc123",
            "document_version": 4,
            "operations_persisted": 3,
            "last_checkpoint": "2024-01-01T10:02:30Z",
            "next_checkpoint_due": "2024-01-01T10:05:00Z",
            "storage_location": "persistent_store://sessions/session_abc123"
        }

        # Test document synchronization
        sync_result = await self.collaboration_engine.sync_document("session_abc123")

        # Verify synchronization
        self.assertTrue(sync_result["success"])
        self.assertIn("document_version", sync_result)
        self.assertIn("operations_persisted", sync_result)
        self.assertEqual(sync_result["operations_persisted"], 3)

        # Test session recovery after disconnection
        recovery_request = {
            "session_id": "session_abc123",
            "user_id": "user2",
            "last_known_version": 2,
            "reconnect_timestamp": "2024-01-01T10:04:00Z"
        }

        self.collaboration_engine.join_session.return_value = {
            "success": True,
            "session_recovered": True,
            "current_version": 4,
            "missed_operations": [
                {"operation_id": "op_003", "type": "replace", "timestamp": "2024-01-01T10:03:00Z"}
            ],
            "document_state": {
                "content": "Updated document content",
                "version": 4,
                "last_modified": "2024-01-01T10:03:00Z"
            },
            "active_participants": ["user1", "user3"],
            "recovery_method": "operation_replay"
        }

        # Test session recovery
        recovery_result = await self.collaboration_engine.join_session(
            "session_abc123", "user2", recovery_request
        )

        # Verify recovery
        self.assertTrue(recovery_result["success"])
        self.assertTrue(recovery_result["session_recovered"])
        self.assertIn("missed_operations", recovery_result)
        self.assertIn("current_version", recovery_result)
        self.assertEqual(recovery_result["current_version"], 4)
        self.assertEqual(len(recovery_result["missed_operations"]), 1)

        # Test version history access
        history_request = {
            "session_id": "session_abc123",
            "from_version": 1,
            "to_version": 4,
            "include_operations": True
        }

        self.collaboration_engine.sync_document.return_value = {
            "success": True,
            "version_history": [
                {
                    "version": 1,
                    "timestamp": "2024-01-01T10:00:00Z",
                    "author": "user1",
                    "operation": {"type": "initial_create"},
                    "content_preview": "# TTRPG Campaign Guide"
                },
                {
                    "version": 2,
                    "timestamp": "2024-01-01T10:01:00Z",
                    "author": "user1",
                    "operation": {"type": "insert", "content": "Introduction section"},
                    "content_preview": "# TTRPG Campaign Guide\n\n## Introduction"
                },
                {
                    "version": 3,
                    "timestamp": "2024-01-01T10:02:00Z",
                    "author": "user2",
                    "operation": {"type": "delete", "content": "removed text"},
                    "content_preview": "# TTRPG Campaign Guide\n\n## Introduction (edited)"
                },
                {
                    "version": 4,
                    "timestamp": "2024-01-01T10:03:00Z",
                    "author": "user3",
                    "operation": {"type": "replace", "content": "enhanced content"},
                    "content_preview": "# TTRPG Campaign Guide\n\n## Enhanced Introduction"
                }
            ],
            "total_versions": 4,
            "can_revert": True
        }

        # Test history retrieval
        history_result = await self.collaboration_engine.sync_document(
            "session_abc123", action="get_history", params=history_request
        )

        # Verify history
        self.assertTrue(history_result["success"])
        self.assertIn("version_history", history_result)
        self.assertEqual(len(history_result["version_history"]), 4)
        self.assertEqual(history_result["total_versions"], 4)
        self.assertTrue(history_result["can_revert"])

        for version in history_result["version_history"]:
            self.assertIn("version", version)
            self.assertIn("timestamp", version)
            self.assertIn("author", version)
            self.assertIn("operation", version)
            self.assertIn("content_preview", version)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])