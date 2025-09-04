#!/usr/bin/env python3
"""
Phase 4 Test Runner
Comprehensive test execution for Phase 4 Admin UI implementation
"""

import subprocess
import sys
from pathlib import Path

def run_test_suite(name: str, path: str, description: str):
    """Run a test suite and report results"""
    print(f"\n{'='*60}")
    print(f"Running {name}")
    print(f"Description: {description}")
    print(f"Path: {path}")
    print('='*60)
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        path, "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0

def main():
    """Run all Phase 4 tests"""
    print("TTRPG Center - Phase 4 Admin UI Test Suite")
    print("==========================================")
    
    test_suites = [
        {
            "name": "Unit Tests - Admin Services",
            "path": "tests/unit/test_admin_services.py",
            "description": "Test all five admin service classes (ADM-001 through ADM-005)"
        },
        {
            "name": "Functional Tests - Admin API",
            "path": "tests/functional/test_admin_api.py", 
            "description": "Test FastAPI admin application endpoints and middleware"
        },
        {
            "name": "Acceptance Tests - Phase 4",
            "path": "tests/functional/test_phase4_acceptance.py",
            "description": "Validate Phase 4 Definition of Done criteria"
        }
    ]
    
    results = []
    for suite in test_suites:
        success = run_test_suite(
            suite["name"], 
            suite["path"], 
            suite["description"]
        )
        results.append((suite["name"], success))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print('='*60)
    
    total_suites = len(results)
    passed_suites = sum(1 for _, success in results if success)
    
    for name, success in results:
        status = "[PASSED]" if success else "[FAILED]"
        print(f"{status} - {name}")
    
    print(f"\nOverall: {passed_suites}/{total_suites} test suites passed")
    
    if passed_suites == total_suites:
        print("All Phase 4 tests passed! Admin UI is ready for deployment.")
        return 0
    else:
        print("Some tests failed. Please review and fix before deployment.")
        return 1

if __name__ == "__main__":
    sys.exit(main())