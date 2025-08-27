"""Enhanced bug tracking system with peer review automation"""

import json
import logging
import time
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

class BugSource(Enum):
    """Source of bug reports"""
    USER_REPORT = "user_report"
    PEER_REVIEW = "peer_review" 
    CLI_SUBMISSION = "cli_submission"
    UI_SUBMISSION = "ui_submission"

class BugStatus(Enum):
    """Bug status states"""
    OPEN = "open"
    CLOSED = "closed"
    ON_HOLD = "on_hold"
    IN_PROGRESS = "in_progress"

class SeverityLevel(Enum):
    """Bug severity levels with escalation order"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class BugTracker:
    """Enhanced bug tracking system with automation for peer reviews"""
    
    def __init__(self):
        self.bugs_dir = Path("bugs")
        self.bugs_dir.mkdir(exist_ok=True)
    
    def _generate_10_digit_id(self) -> str:
        """Generate a unique 10-digit ID for bugs and feature requests"""
        while True:
            # Generate a 10-digit number: first digit can't be 0
            first_digit = random.randint(1, 9)
            remaining_digits = random.randint(0, 999999999)
            bug_id = f"{first_digit}{remaining_digits:09d}"
            
            # Ensure uniqueness by checking if file exists
            bug_file = self.bugs_dir / f"{bug_id}.json"
            if not bug_file.exists():
                return bug_id
        
    def create_bug(self, bug_data: Dict[str, Any]) -> str:
        """Create a new bug report with proper automation setup"""
        bug_id = bug_data.get("bug_id")
        if not bug_id:
            bug_id = self._generate_10_digit_id()
        
        # Set admin controls based on source
        source = bug_data.get("source", BugSource.USER_REPORT.value)
        bug_data["admin_controls"] = self._get_admin_controls(source)
        
        # Initialize peer review history if it's a peer review bug
        if source == BugSource.PEER_REVIEW.value:
            if "peer_review_history" not in bug_data:
                bug_data["peer_review_history"] = []
            
            review_entry = {
                "review_sha": bug_data.get("build_id", ""),
                "severity": bug_data.get("severity", "medium"),
                "found_date": bug_data.get("timestamp", time.time()),
                "provider": bug_data.get("provider", "unknown")
            }
            bug_data["peer_review_history"].append(review_entry)
        
        # Ensure bug_id is set in the data
        bug_data["bug_id"] = bug_id
        
        # Write bug file
        bug_file = self.bugs_dir / f"{bug_id}.json"
        with open(bug_file, 'w', encoding='utf-8') as f:
            json.dump(bug_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Created bug {bug_id} from source: {source}")
        return bug_id
    
    def _get_admin_controls(self, source: str) -> Dict[str, Any]:
        """Get admin control settings based on bug source"""
        if source == BugSource.PEER_REVIEW.value:
            return {
                "can_modify_status": False,  # Admin cannot directly change status
                "can_put_on_hold": True,     # Admin can put on hold
                "auto_close_enabled": True,  # System auto-closes when fixed
                "severity_escalation_enabled": True  # Severity escalates if recurring
            }
        else:
            return {
                "can_modify_status": True,   # Admin can change status
                "can_put_on_hold": True,     # Admin can put on hold
                "auto_close_enabled": False, # No auto-closure
                "severity_escalation_enabled": False  # No severity escalation
            }
    
    def check_for_auto_closure(self, review_sha: str) -> List[str]:
        """Check if any peer review bugs should be auto-closed based on current code"""
        closed_bugs = []
        
        # Get all open peer review bugs
        open_pr_bugs = self.get_bugs_by_criteria({
            "status": BugStatus.OPEN.value,
            "source": BugSource.PEER_REVIEW.value
        })
        
        for bug in open_pr_bugs:
            if self._should_auto_close_bug(bug, review_sha):
                self.auto_close_bug(bug["bug_id"], review_sha)
                closed_bugs.append(bug["bug_id"])
        
        return closed_bugs
    
    def _should_auto_close_bug(self, bug: Dict[str, Any], review_sha: str) -> bool:
        """Determine if a bug should be auto-closed based on current review"""
        # Check if the bug is on hold (no auto-closure if on hold)
        if bug.get("status") == BugStatus.ON_HOLD.value:
            return False
        
        # For now, we'll implement a simple check - in a full system, this would
        # analyze the current code to see if the issue still exists
        # This is a placeholder for more sophisticated analysis
        
        # Check if this review_sha already addressed the issue
        # (This would be enhanced with actual code analysis)
        admin_controls = bug.get("admin_controls", {})
        return admin_controls.get("auto_close_enabled", False)
    
    def auto_close_bug(self, bug_id: str, review_sha: str) -> bool:
        """Automatically close a bug with system attribution"""
        try:
            bug = self.get_bug(bug_id)
            if not bug:
                return False
            
            # Update bug status and add closure info
            bug["status"] = BugStatus.CLOSED.value
            bug["closed_by"] = "system_auto_closure"
            bug["closed_at"] = time.time()
            bug["closed_reason"] = f"Automatically closed - issue resolved in review {review_sha}"
            
            # Save updated bug
            self._save_bug(bug)
            logger.info(f"Auto-closed bug {bug_id} due to resolution in {review_sha}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to auto-close bug {bug_id}: {e}")
            return False
    
    def handle_recurring_bug(self, existing_bug_id: str, new_review_data: Dict[str, Any]) -> bool:
        """Handle a bug that has been found again in peer review"""
        try:
            bug = self.get_bug(existing_bug_id)
            if not bug:
                return False
            
            # Check if bug is on hold (no escalation if on hold)
            if bug.get("status") == BugStatus.ON_HOLD.value:
                logger.info(f"Bug {existing_bug_id} is on hold - no severity escalation")
                return True
            
            # Add to peer review history
            if "peer_review_history" not in bug:
                bug["peer_review_history"] = []
            
            review_entry = {
                "review_sha": new_review_data.get("build_id", ""),
                "severity": new_review_data.get("severity", "medium"),
                "found_date": new_review_data.get("timestamp", time.time()),
                "provider": new_review_data.get("provider", "unknown")
            }
            bug["peer_review_history"].append(review_entry)
            
            # Escalate severity if enabled
            admin_controls = bug.get("admin_controls", {})
            if admin_controls.get("severity_escalation_enabled", False):
                old_severity = bug.get("severity", "low")
                new_severity = self._escalate_severity(old_severity)
                if new_severity != old_severity:
                    bug["severity"] = new_severity
                    bug["severity_escalated"] = True
                    bug["escalation_reason"] = f"Recurring issue - escalated from {old_severity} to {new_severity}"
                    logger.info(f"Escalated severity of bug {existing_bug_id} from {old_severity} to {new_severity}")
            
            # Reopen if closed
            if bug.get("status") == BugStatus.CLOSED.value:
                bug["status"] = BugStatus.OPEN.value
                bug["reopened_by"] = "system_peer_review"
                bug["reopened_at"] = time.time()
                bug["reopened_reason"] = "Reopened - issue found again in peer review"
            
            self._save_bug(bug)
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle recurring bug {existing_bug_id}: {e}")
            return False
    
    def _escalate_severity(self, current_severity: str) -> str:
        """Escalate bug severity to next level"""
        escalation_map = {
            SeverityLevel.LOW.value: SeverityLevel.MEDIUM.value,
            SeverityLevel.MEDIUM.value: SeverityLevel.HIGH.value,
            SeverityLevel.HIGH.value: SeverityLevel.CRITICAL.value,
            SeverityLevel.CRITICAL.value: SeverityLevel.CRITICAL.value  # Max level
        }
        return escalation_map.get(current_severity, SeverityLevel.MEDIUM.value)
    
    def put_bug_on_hold(self, bug_id: str, admin_reason: str) -> bool:
        """Put a bug on hold (admin action)"""
        try:
            bug = self.get_bug(bug_id)
            if not bug:
                return False
            
            admin_controls = bug.get("admin_controls", {})
            if not admin_controls.get("can_put_on_hold", False):
                logger.warning(f"Cannot put bug {bug_id} on hold - not allowed by admin controls")
                return False
            
            bug["status"] = BugStatus.ON_HOLD.value
            bug["on_hold_reason"] = admin_reason
            bug["on_hold_at"] = time.time()
            bug["on_hold_by"] = "admin"
            
            self._save_bug(bug)
            logger.info(f"Put bug {bug_id} on hold: {admin_reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to put bug {bug_id} on hold: {e}")
            return False
    
    def admin_close_bug(self, bug_id: str, admin_reason: str) -> bool:
        """Admin closes a bug (only allowed for non-peer-review bugs)"""
        try:
            bug = self.get_bug(bug_id)
            if not bug:
                return False
            
            admin_controls = bug.get("admin_controls", {})
            if not admin_controls.get("can_modify_status", False):
                logger.warning(f"Cannot close bug {bug_id} - not allowed by admin controls")
                return False
            
            bug["status"] = BugStatus.CLOSED.value
            bug["closed_by"] = "admin"
            bug["closed_at"] = time.time()
            bug["closed_reason"] = admin_reason
            
            self._save_bug(bug)
            logger.info(f"Admin closed bug {bug_id}: {admin_reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to admin close bug {bug_id}: {e}")
            return False
    
    def get_bug(self, bug_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific bug by ID"""
        try:
            bug_file = self.bugs_dir / f"{bug_id}.json"
            if not bug_file.exists():
                return None
            
            with open(bug_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Failed to get bug {bug_id}: {e}")
            return None
    
    def _save_bug(self, bug: Dict[str, Any]) -> bool:
        """Save bug data to file"""
        try:
            bug_id = bug.get("bug_id")
            if not bug_id:
                return False
            
            bug_file = self.bugs_dir / f"{bug_id}.json"
            with open(bug_file, 'w', encoding='utf-8') as f:
                json.dump(bug, f, indent=2, ensure_ascii=False)
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to save bug: {e}")
            return False
    
    def get_bugs_by_criteria(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get bugs matching specific criteria"""
        matching_bugs = []
        
        try:
            bug_files = list(self.bugs_dir.glob("*.json"))
            
            for bug_file in bug_files:
                try:
                    with open(bug_file, 'r', encoding='utf-8') as f:
                        bug = json.load(f)
                    
                    # Check if bug matches all criteria
                    matches = True
                    for key, value in criteria.items():
                        if bug.get(key) != value:
                            matches = False
                            break
                    
                    if matches:
                        matching_bugs.append(bug)
                        
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get bugs by criteria: {e}")
        
        return matching_bugs
    
    def get_on_hold_bugs(self) -> List[Dict[str, Any]]:
        """Get all bugs that are on hold"""
        return self.get_bugs_by_criteria({"status": BugStatus.ON_HOLD.value})
    
    def process_peer_review(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a peer review and handle bug creation/updates"""
        result = {
            "bugs_created": [],
            "bugs_updated": [],
            "bugs_closed": [],
            "bugs_escalated": []
        }
        
        review_sha = review_data.get("sha", "")
        
        # First, check for auto-closure opportunities
        closed_bugs = self.check_for_auto_closure(review_sha)
        result["bugs_closed"] = closed_bugs
        
        # Process each issue in the review
        issues = review_data.get("issues", [])
        for issue in issues:
            # Check if this is a recurring issue
            existing_bug = self._find_existing_peer_review_bug(issue)
            
            if existing_bug:
                # Handle recurring bug
                if self.handle_recurring_bug(existing_bug["bug_id"], {
                    "build_id": review_sha,
                    "severity": issue.get("severity", "medium"),
                    "timestamp": time.time(),
                    "provider": review_data.get("provider", "unknown")
                }):
                    result["bugs_updated"].append(existing_bug["bug_id"])
                    if existing_bug.get("severity_escalated"):
                        result["bugs_escalated"].append(existing_bug["bug_id"])
            else:
                # Create new bug
                bug_data = self._convert_review_issue_to_bug(issue, review_data)
                bug_id = self.create_bug(bug_data)
                result["bugs_created"].append(bug_id)
        
        return result
    
    def _find_existing_peer_review_bug(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find existing peer review bug for the same issue"""
        # This would implement logic to match issues across reviews
        # For now, match by review_id or title similarity
        review_id = issue.get("id", "")
        title = issue.get("title", "")
        
        peer_review_bugs = self.get_bugs_by_criteria({
            "source": BugSource.PEER_REVIEW.value
        })
        
        for bug in peer_review_bugs:
            if bug.get("review_id") == review_id or bug.get("title") == title:
                return bug
        
        return None
    
    def _convert_review_issue_to_bug(self, issue: Dict[str, Any], review_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a peer review issue to bug format"""
        bug_id = self._generate_10_digit_id()
        review_id = issue.get("id", "")
        
        return {
            "bug_id": bug_id,
            "timestamp": f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
            "environment": "dev",
            "build_id": review_data.get("sha", ""),
            "severity": issue.get("severity", "medium"),
            "category": self._categorize_issue(issue),
            "status": BugStatus.OPEN.value,
            "title": issue.get("title", ""),
            "description": issue.get("details", ""),
            "review_id": review_id,
            "source": BugSource.PEER_REVIEW.value,
            "provider": review_data.get("provider", "unknown"),
            "files": issue.get("files", []),
            "requirements": issue.get("requirements", [])
        }
    
    def _categorize_issue(self, issue: Dict[str, Any]) -> str:
        """Categorize an issue based on its content"""
        title = issue.get("title", "").lower()
        details = issue.get("details", "").lower()
        
        if "error" in title or "exception" in title:
            return "error_handling"
        elif "security" in title or "traversal" in title or "vulnerability" in title:
            return "security"
        elif "test" in title or "testing" in title:
            return "testing"
        elif "performance" in title or "timeout" in title:
            return "performance"
        else:
            return "general"

# Global instance
_bug_tracker = None

def get_bug_tracker() -> BugTracker:
    """Get global bug tracker instance"""
    global _bug_tracker
    if _bug_tracker is None:
        _bug_tracker = BugTracker()
    return _bug_tracker