import json
import time
import uuid
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class FeedbackProcessor:
    """Process user feedback and generate test cases or bug bundles"""
    
    def __init__(self):
        self.regression_dir = Path("tests/regression/cases")
        self.bugs_dir = Path("bugs")
        self.regression_dir.mkdir(parents=True, exist_ok=True)
        self.bugs_dir.mkdir(parents=True, exist_ok=True)
    
    def process_thumbs_up(self, 
                         query: str,
                         response: str,
                         context: Dict[str, Any],
                         execution_trace: List[Dict[str, Any]],
                         user_id: str = "anonymous") -> Dict[str, Any]:
        """
        Process positive feedback - create regression test case
        """
        try:
            logger.info("Processing thumbs up feedback - creating regression test")
            
            # Generate test case ID
            timestamp = int(time.time())
            case_id = f"REG-{timestamp}-{str(uuid.uuid4())[:8]}"
            
            # Analyze response to create expectations
            expectations = self._analyze_response_for_expectations(query, response, context)
            
            # Create regression test case
            test_case = {
                "case_id": case_id,
                "query": query,
                "context": {
                    "system": context.get("system", "Generic"),
                    "memory_mode": context.get("memory_mode", "session-only"),
                    "user_session": context.get("session_id", "unknown")
                },
                "model": context.get("model_used", "openai:gpt-4o-mini"),
                "parameters": {
                    "temperature": context.get("temperature", 0.3)
                },
                "expected": expectations,
                "baseline_response": {
                    "text": response,
                    "sources": context.get("sources", []),
                    "query_type": context.get("query_type", "unknown")
                },
                "origin": {
                    "env": context.get("app_env", "unknown"),
                    "user": user_id,
                    "timestamp": time.time(),
                    "source": "thumbs_up_feedback"
                },
                "status": "active",
                "execution_trace": execution_trace[-3:] if execution_trace else []  # Keep last 3 steps
            }
            
            # Save test case
            case_file = self.regression_dir / f"{case_id}.json"
            with open(case_file, 'w', encoding='utf-8') as f:
                json.dump(test_case, f, indent=2, ensure_ascii=False)
            
            # Create snapshot if needed
            self._create_test_snapshot(case_id, response, context)
            
            logger.info(f"Created regression test case: {case_id}")
            
            return {
                "success": True,
                "test_case_id": case_id,
                "file_path": str(case_file),
                "expectations_detected": len(expectations),
                "message": "Thank you! I've created a test case to ensure consistent quality for similar questions."
            }
            
        except Exception as e:
            logger.error(f"Failed to process thumbs up: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Thank you for the feedback, but I had trouble creating the test case."
            }
    
    def process_thumbs_down(self,
                           query: str,
                           response: str,
                           context: Dict[str, Any],
                           execution_trace: List[Dict[str, Any]],
                           user_feedback: str = "",
                           user_id: str = "anonymous") -> Dict[str, Any]:
        """
        Process negative feedback - create bug bundle
        """
        try:
            logger.info("Processing thumbs down feedback - creating bug bundle")
            
            # Generate bug ID
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            bug_id = f"bugid_{timestamp}-{str(uuid.uuid4())[:8]}"
            
            # Analyze the issue
            issue_analysis = self._analyze_negative_feedback(query, response, user_feedback, execution_trace)
            
            # Create comprehensive bug bundle
            bug_bundle = {
                "bug_id": bug_id,
                "env": context.get("app_env", "unknown"),
                "timestamp": time.time(),
                "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "query": query,
                "user_feedback": user_feedback,
                "response_provided": response,
                "issue_analysis": issue_analysis,
                "execution_trace": execution_trace,
                "context": {
                    "system": context.get("system"),
                    "memory_mode": context.get("memory_mode"),
                    "session_id": context.get("session_id"),
                    "query_type": context.get("query_type"),
                    "model_used": context.get("model_used")
                },
                "retrieval_data": {
                    "sources": context.get("sources", []),
                    "retrieval_count": len(context.get("sources", [])),
                    "filters_applied": context.get("filters_applied", {}),
                    "rag_query": context.get("rag_query", "")
                },
                "performance_metrics": {
                    "latency_ms": context.get("latency_ms", 0),
                    "token_usage": context.get("tokens", {}),
                    "model_calls": len([step for step in execution_trace if step.get("step") == "synthesis"])
                },
                "system_state": {
                    "app_build": context.get("app_build", "unknown"),
                    "source_hash": context.get("source_hash", ""),
                    "environment_config": {
                        "vector_store_connected": context.get("vector_store_health", False),
                        "openai_connected": context.get("openai_health", False)
                    }
                },
                "user_info": {
                    "user_id": user_id,
                    "session_length": context.get("session_length_queries", 1)
                },
                "suggested_fixes": issue_analysis.get("suggested_fixes", []),
                "severity": issue_analysis.get("severity", "medium"),
                "category": issue_analysis.get("category", "unknown")
            }
            
            # Save bug bundle
            bug_file = self.bugs_dir / f"{bug_id}.json"
            with open(bug_file, 'w', encoding='utf-8') as f:
                json.dump(bug_bundle, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created bug bundle: {bug_id}")
            
            return {
                "success": True,
                "bug_id": bug_id,
                "file_path": str(bug_file),
                "severity": issue_analysis.get("severity", "medium"),
                "message": "Thank you for the feedback! I've created a detailed report for the development team to review."
            }
            
        except Exception as e:
            logger.error(f"Failed to process thumbs down: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Thank you for the feedback. I had trouble creating the bug report, but your input is noted."
            }
    
    def _analyze_response_for_expectations(self, 
                                         query: str, 
                                         response: str, 
                                         context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze successful response to create test expectations"""
        expectations = {}
        
        # Determine answer type
        if any(word in query.lower() for word in ["list", "what are", "which", "all"]):
            expectations["answer_kind"] = "list"
            # Count items in response
            if "•" in response or "-" in response or any(f"{i}." in response for i in range(1, 20)):
                expectations["min_items"] = max(1, response.count("•") + response.count("-") + 
                                              sum(1 for i in range(1, 20) if f"{i}." in response))
        
        elif any(word in query.lower() for word in ["how much", "cost", "price"]):
            expectations["answer_kind"] = "price"
            # Look for currency mentions
            if any(curr in response.lower() for curr in ["gp", "gold", "sp", "silver"]):
                expectations["contains_currency"] = True
        
        elif any(word in query.lower() for word in ["how to", "step", "guide"]):
            expectations["answer_kind"] = "instructions"
            if any(f"{i}." in response for i in range(1, 10)):
                expectations["has_steps"] = True
        
        else:
            expectations["answer_kind"] = "informational"
        
        # Extract key terms that should be present
        response_words = response.lower().split()
        query_words = set(word.strip(".,!?") for word in query.lower().split())
        
        # Find important terms that appear in both query and response
        important_terms = []
        for word in query_words:
            if len(word) > 3 and word in response_words:
                important_terms.append(word)
        
        if important_terms:
            expectations["contains"] = important_terms[:5]  # Top 5 terms
        
        # System-specific expectations
        if context.get("system"):
            expectations["system_context"] = context["system"]
        
        # Forbidden content (common errors)
        forbidden = []
        if "pathfinder" in query.lower() and "d&d" in response.lower():
            forbidden.append("D&D rules in Pathfinder query")
        elif "d&d" in query.lower() and "pathfinder" in response.lower():
            forbidden.append("Pathfinder rules in D&D query")
        
        if forbidden:
            expectations["forbidden"] = forbidden
        
        return expectations
    
    def _analyze_negative_feedback(self, 
                                 query: str, 
                                 response: str, 
                                 feedback: str,
                                 trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze negative feedback to categorize the issue"""
        analysis = {
            "category": "unknown",
            "severity": "medium",
            "suggested_fixes": [],
            "issue_indicators": []
        }
        
        feedback_lower = feedback.lower()
        response_lower = response.lower()
        query_lower = query.lower()
        
        # Categorize issue based on feedback
        if any(term in feedback_lower for term in ["wrong", "incorrect", "inaccurate"]):
            analysis["category"] = "accuracy_error"
            analysis["severity"] = "high"
            
            # Check for cross-system contamination
            if ("pathfinder" in query_lower and "d&d" in response_lower) or \
               ("d&d" in query_lower and "pathfinder" in response_lower):
                analysis["issue_indicators"].append("cross_system_contamination")
                analysis["suggested_fixes"].append("Improve system filtering in RAG retrieval")
            
        elif any(term in feedback_lower for term in ["unclear", "confusing", "understand"]):
            analysis["category"] = "clarity_issue"
            analysis["severity"] = "medium"
            analysis["suggested_fixes"].append("Improve response clarity and structure")
            
        elif any(term in feedback_lower for term in ["incomplete", "missing", "more"]):
            analysis["category"] = "incomplete_response"
            analysis["severity"] = "medium"
            analysis["suggested_fixes"].append("Retrieve more comprehensive sources")
            analysis["suggested_fixes"].append("Increase RAG search result count")
            
        elif any(term in feedback_lower for term in ["slow", "long", "wait"]):
            analysis["category"] = "performance_issue"
            analysis["severity"] = "low"
            analysis["suggested_fixes"].append("Optimize query processing speed")
            
        elif any(term in feedback_lower for term in ["format", "layout", "display"]):
            analysis["category"] = "formatting_issue"
            analysis["severity"] = "low"
            analysis["suggested_fixes"].append("Improve response formatting")
            
        # Check trace for specific issues
        if trace:
            retrieval_steps = [step for step in trace if step.get("step") == "retrieval"]
            if retrieval_steps and len(retrieval_steps[0].get("chunks", [])) == 0:
                analysis["issue_indicators"].append("no_retrieval_results")
                analysis["suggested_fixes"].append("Improve query embedding or expand knowledge base")
            
            synthesis_steps = [step for step in trace if step.get("step") == "synthesis"]
            if synthesis_steps and synthesis_steps[0].get("tokens_out", 0) < 50:
                analysis["issue_indicators"].append("very_short_response")
                analysis["suggested_fixes"].append("Increase response length limits")
        
        # Severity escalation rules
        if len(analysis["issue_indicators"]) >= 2:
            analysis["severity"] = "high"
        
        if not analysis["suggested_fixes"]:
            analysis["suggested_fixes"] = ["Manual review required"]
        
        return analysis
    
    def _create_test_snapshot(self, case_id: str, response: str, context: Dict[str, Any]):
        """Create snapshot file for regression test"""
        try:
            snapshot_dir = Path("tests/regression/snapshots")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            snapshot = {
                "case_id": case_id,
                "expected_response": response,
                "expected_sources": context.get("sources", []),
                "expected_metrics": {
                    "min_response_length": len(response.split()),
                    "expected_source_count": len(context.get("sources", []))
                },
                "created_at": time.time()
            }
            
            snapshot_file = snapshot_dir / f"{case_id}_snapshot.json"
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"Failed to create snapshot for {case_id}: {e}")
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get feedback processing statistics"""
        try:
            # Count regression tests
            regression_files = list(self.regression_dir.glob("*.json"))
            
            # Count bug bundles
            bug_files = list(self.bugs_dir.glob("*.json"))
            
            # Analyze recent feedback
            recent_cutoff = time.time() - (7 * 24 * 3600)  # Last 7 days
            recent_tests = 0
            recent_bugs = 0
            
            for test_file in regression_files:
                try:
                    with open(test_file, 'r') as f:
                        data = json.load(f)
                        if data.get("origin", {}).get("timestamp", 0) > recent_cutoff:
                            recent_tests += 1
                except Exception:
                    continue
            
            for bug_file in bug_files:
                try:
                    with open(bug_file, 'r') as f:
                        data = json.load(f)
                        if data.get("timestamp", 0) > recent_cutoff:
                            recent_bugs += 1
                except Exception:
                    continue
            
            return {
                "total_regression_tests": len(regression_files),
                "total_bug_bundles": len(bug_files),
                "recent_positive_feedback": recent_tests,
                "recent_negative_feedback": recent_bugs,
                "feedback_ratio": {
                    "positive": recent_tests,
                    "negative": recent_bugs,
                    "ratio": f"{recent_tests}:{recent_bugs}" if recent_bugs > 0 else f"{recent_tests}:0"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get feedback stats: {e}")
            return {
                "total_regression_tests": 0,
                "total_bug_bundles": 0,
                "error": str(e)
            }

# Global instance
_feedback_processor = None

def get_feedback_processor() -> FeedbackProcessor:
    """Get global feedback processor instance"""
    global _feedback_processor
    if _feedback_processor is None:
        _feedback_processor = FeedbackProcessor()
    return _feedback_processor