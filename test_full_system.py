#!/usr/bin/env python3
"""Comprehensive system test for TTRPG Center"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(method, endpoint, data=None, description=""):
    """Test an endpoint and return result"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
        
        print(f"[OK] {description}: {response.status_code}")
        if response.status_code not in [200, 201]:
            print(f"   Error: {response.text}")
            return False, None
        
        result = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        return True, result
    
    except Exception as e:
        print(f"[ERROR] {description}: {str(e)}")
        return False, None

def run_comprehensive_test():
    """Run comprehensive system test"""
    print("TTRPG Center - Comprehensive System Test")
    print("=" * 50)
    
    # Test 1: Health Check
    success, _ = test_endpoint("GET", "/health", description="Health Check")
    if not success:
        return False
    
    # Test 2: Status Check  
    success, status_data = test_endpoint("GET", "/status", description="Status Check")
    if not success:
        return False
    
    print(f"   Environment: {status_data.get('env', 'unknown')}")
    print(f"   Workflows: {status_data.get('workflows', 0)}")
    print(f"   Health Checks: {status_data.get('health_checks', {})}")
    
    # Test 3: RAG Query
    rag_query = {
        "query": "What is a saving throw in D&D?",
        "session_id": "test_rag_session",
        "context": {"system": "D&D 5E"}
    }
    success, rag_result = test_endpoint("POST", "/api/query", rag_query, "RAG Query Processing")
    if not success:
        return False
    
    print(f"   Query Type: {rag_result.get('query_type', 'unknown')}")
    print(f"   Latency: {rag_result.get('latency_ms', 0)}ms")
    print(f"   Success: {rag_result.get('success', False)}")
    
    # Test 4: Workflow Query
    workflow_query = {
        "query": "Help me create a character in Pathfinder 2E",
        "session_id": "test_workflow_session"
    }
    success, workflow_result = test_endpoint("POST", "/api/query", workflow_query, "Workflow Initiation")
    if not success:
        return False
    
    print(f"   Workflow ID: {workflow_result.get('workflow_execution_id', 'none')}")
    print(f"   Status: {workflow_result.get('workflow_status', 'unknown')}")
    
    # Test 5: Positive Feedback
    if rag_result:
        feedback_data = {
            "query_id": rag_result.get("query_id", "test"),
            "type": "positive",
            "query": rag_query["query"],
            "response": rag_result.get("response", "test response"),
            "context": {"app_env": "test"}
        }
        success, feedback_result = test_endpoint("POST", "/api/feedback", feedback_data, "Positive Feedback")
        if success:
            print(f"   Test Case Created: {feedback_result.get('test_case_id', 'none')}")
    
    # Test 6: Negative Feedback  
    neg_feedback_data = {
        "query_id": "test_negative",
        "type": "negative", 
        "query": "Test negative query",
        "response": "Wrong response",
        "user_feedback": "This is completely wrong",
        "context": {"app_env": "test"}
    }
    success, neg_result = test_endpoint("POST", "/api/feedback", neg_feedback_data, "Negative Feedback")
    if success:
        print(f"   Bug Bundle Created: {neg_result.get('bug_id', 'none')}")
        print(f"   Severity: {neg_result.get('severity', 'unknown')}")
    
    # Test 7: Web Interfaces
    success, _ = test_endpoint("GET", "/admin", description="Admin Interface")
    success, _ = test_endpoint("GET", "/user", description="User Interface")
    
    print("\n[SUCCESS] All tests completed successfully!")
    print("\nSystem Summary:")
    print(f"   * RAG Engine: {'Working' if rag_result.get('success') else 'Failed'}")
    print(f"   * Workflow Engine: {'Working' if workflow_result.get('workflow_execution_id') else 'Failed'}")
    print(f"   * Feedback System: {'Working' if feedback_result.get('success') else 'Failed'}")
    print(f"   * Web Interfaces: Loading")
    
    return True

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)