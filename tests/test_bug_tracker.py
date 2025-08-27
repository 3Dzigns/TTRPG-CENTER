"""Unit tests for bug tracker system with peer review automation"""

import unittest
import tempfile
import os
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

from app.common.bug_tracker import BugTracker, BugSource, BugStatus, SeverityLevel


class TestBugTracker(unittest.TestCase):
    """Test cases for bug tracker functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.bug_tracker = BugTracker()
        # Override bugs directory to use temp directory
        self.bug_tracker.bugs_dir = Path(self.temp_dir)
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_generate_10_digit_id(self):
        """Test 10-digit ID generation"""
        # Generate multiple IDs and test format
        ids = []
        for _ in range(10):
            bug_id = self.bug_tracker._generate_10_digit_id()
            ids.append(bug_id)
            
            # Test format
            self.assertEqual(len(bug_id), 10)
            self.assertTrue(bug_id.isdigit())
            self.assertNotEqual(bug_id[0], '0')  # First digit not zero
        
        # Test uniqueness
        self.assertEqual(len(set(ids)), len(ids), "Generated IDs should be unique")
    
    def test_create_bug_basic(self):
        """Test basic bug creation"""
        bug_data = {
            "title": "Test Bug",
            "description": "Test description",
            "severity": "medium",
            "category": "testing"
        }
        
        bug_id = self.bug_tracker.create_bug(bug_data)
        
        # Verify ID format
        self.assertEqual(len(bug_id), 10)
        self.assertTrue(bug_id.isdigit())
        
        # Verify file was created
        bug_file = self.bug_tracker.bugs_dir / f"{bug_id}.json"
        self.assertTrue(bug_file.exists())
        
        # Verify content
        with open(bug_file, 'r') as f:
            saved_bug = json.load(f)
        
        self.assertEqual(saved_bug["bug_id"], bug_id)
        self.assertEqual(saved_bug["title"], "Test Bug")
        self.assertEqual(saved_bug["status"], BugStatus.OPEN.value)
    
    def test_create_peer_review_bug(self):
        """Test peer review bug creation with admin controls"""
        bug_data = {
            "title": "Peer Review Bug",
            "description": "Found by peer review",
            "severity": "high",
            "category": "error_handling",
            "source": BugSource.PEER_REVIEW.value
        }
        
        bug_id = self.bug_tracker.create_bug(bug_data)
        bug = self.bug_tracker.get_bug(bug_id)
        
        # Check admin controls for peer review bugs
        admin_controls = bug["admin_controls"]
        self.assertFalse(admin_controls["can_modify_status"])
        self.assertTrue(admin_controls["can_put_on_hold"])
        self.assertTrue(admin_controls["auto_close_enabled"])
        self.assertTrue(admin_controls["severity_escalation_enabled"])
    
    def test_create_user_bug(self):
        """Test user-submitted bug with different admin controls"""
        bug_data = {
            "title": "User Bug",
            "description": "Found by user",
            "severity": "medium",
            "category": "ui_functionality",
            "source": BugSource.UI_SUBMISSION.value
        }
        
        bug_id = self.bug_tracker.create_bug(bug_data)
        bug = self.bug_tracker.get_bug(bug_id)
        
        # Check admin controls for user bugs
        admin_controls = bug["admin_controls"]
        self.assertTrue(admin_controls["can_modify_status"])
        self.assertTrue(admin_controls["can_put_on_hold"])
        self.assertFalse(admin_controls["auto_close_enabled"])
        self.assertFalse(admin_controls["severity_escalation_enabled"])
    
    def test_severity_escalation(self):
        """Test severity escalation logic"""
        # Test escalation path
        self.assertEqual(
            self.bug_tracker._escalate_severity(SeverityLevel.LOW.value),
            SeverityLevel.MEDIUM.value
        )
        self.assertEqual(
            self.bug_tracker._escalate_severity(SeverityLevel.MEDIUM.value),
            SeverityLevel.HIGH.value
        )
        self.assertEqual(
            self.bug_tracker._escalate_severity(SeverityLevel.HIGH.value),
            SeverityLevel.CRITICAL.value
        )
        # Critical stays critical
        self.assertEqual(
            self.bug_tracker._escalate_severity(SeverityLevel.CRITICAL.value),
            SeverityLevel.CRITICAL.value
        )
    
    def test_put_bug_on_hold(self):
        """Test putting bug on hold"""
        # Create a user bug (can be put on hold)
        bug_data = {
            "title": "Test Bug",
            "source": BugSource.UI_SUBMISSION.value
        }
        bug_id = self.bug_tracker.create_bug(bug_data)
        
        # Put on hold
        success = self.bug_tracker.put_bug_on_hold(bug_id, "Testing hold functionality")
        self.assertTrue(success)
        
        # Verify status change
        bug = self.bug_tracker.get_bug(bug_id)
        self.assertEqual(bug["status"], BugStatus.ON_HOLD.value)
        self.assertEqual(bug["on_hold_reason"], "Testing hold functionality")
        self.assertIn("on_hold_at", bug)
    
    def test_admin_close_bug(self):
        """Test admin closing bug"""
        # Create a user bug (can be closed by admin)
        bug_data = {
            "title": "Test Bug",
            "source": BugSource.UI_SUBMISSION.value
        }
        bug_id = self.bug_tracker.create_bug(bug_data)
        
        # Admin close
        success = self.bug_tracker.admin_close_bug(bug_id, "Fixed in latest build")
        self.assertTrue(success)
        
        # Verify status change
        bug = self.bug_tracker.get_bug(bug_id)
        self.assertEqual(bug["status"], BugStatus.CLOSED.value)
        self.assertEqual(bug["closed_reason"], "Fixed in latest build")
        self.assertEqual(bug["closed_by"], "admin")
    
    def test_admin_cannot_close_peer_review_bug(self):
        """Test that admin cannot close peer review bugs"""
        # Create a peer review bug
        bug_data = {
            "title": "Peer Review Bug",
            "source": BugSource.PEER_REVIEW.value
        }
        bug_id = self.bug_tracker.create_bug(bug_data)
        
        # Try to admin close (should fail)
        success = self.bug_tracker.admin_close_bug(bug_id, "Trying to close")
        self.assertFalse(success)
        
        # Verify bug is still open
        bug = self.bug_tracker.get_bug(bug_id)
        self.assertEqual(bug["status"], BugStatus.OPEN.value)
    
    def test_handle_recurring_bug(self):
        """Test handling of recurring peer review bugs"""
        # Create initial peer review bug
        bug_data = {
            "title": "Recurring Bug",
            "severity": SeverityLevel.MEDIUM.value,
            "source": BugSource.PEER_REVIEW.value
        }
        bug_id = self.bug_tracker.create_bug(bug_data)
        
        # Simulate finding it again in another review
        new_review_data = {
            "build_id": "new_sha",
            "severity": SeverityLevel.MEDIUM.value,
            "timestamp": time.time(),
            "provider": "test"
        }
        
        success = self.bug_tracker.handle_recurring_bug(bug_id, new_review_data)
        self.assertTrue(success)
        
        # Verify escalation
        bug = self.bug_tracker.get_bug(bug_id)
        self.assertEqual(bug["severity"], SeverityLevel.HIGH.value)
        self.assertTrue(bug["severity_escalated"])
        self.assertEqual(len(bug["peer_review_history"]), 2)
    
    def test_get_bugs_by_criteria(self):
        """Test filtering bugs by criteria"""
        # Create bugs with different statuses
        open_bug = self.bug_tracker.create_bug({"title": "Open Bug"})
        
        closed_bug = self.bug_tracker.create_bug({"title": "Closed Bug"})
        self.bug_tracker.admin_close_bug(closed_bug, "Test closure")
        
        on_hold_bug = self.bug_tracker.create_bug({"title": "Hold Bug"})
        self.bug_tracker.put_bug_on_hold(on_hold_bug, "Test hold")
        
        # Test filtering
        open_bugs = self.bug_tracker.get_bugs_by_criteria({"status": BugStatus.OPEN.value})
        closed_bugs = self.bug_tracker.get_bugs_by_criteria({"status": BugStatus.CLOSED.value})
        hold_bugs = self.bug_tracker.get_bugs_by_criteria({"status": BugStatus.ON_HOLD.value})
        
        self.assertEqual(len(open_bugs), 1)
        self.assertEqual(len(closed_bugs), 1)  
        self.assertEqual(len(hold_bugs), 1)
        
        self.assertEqual(open_bugs[0]["bug_id"], open_bug)
        self.assertEqual(closed_bugs[0]["bug_id"], closed_bug)
        self.assertEqual(hold_bugs[0]["bug_id"], on_hold_bug)


class TestBugTrackerErrorHandling(unittest.TestCase):
    """Test error handling in bug tracker"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.bug_tracker = BugTracker()
        self.bug_tracker.bugs_dir = Path(self.temp_dir)
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_nonexistent_bug(self):
        """Test getting a bug that doesn't exist"""
        bug = self.bug_tracker.get_bug("9999999999")
        self.assertIsNone(bug)
    
    def test_put_nonexistent_bug_on_hold(self):
        """Test putting nonexistent bug on hold"""
        success = self.bug_tracker.put_bug_on_hold("9999999999", "Test")
        self.assertFalse(success)
    
    def test_admin_close_nonexistent_bug(self):
        """Test admin closing nonexistent bug"""
        success = self.bug_tracker.admin_close_bug("9999999999", "Test")
        self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()