"""
Comprehensive test runner for all user story test suites
Executes all tests for user stories from 01_architecture.md through 07_requirements_mgmt.md
"""
import pytest
import sys
import os
from pathlib import Path

# Add app to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_user_story_tests():
    """
    Run all user story test suites and generate comprehensive report
    """
    
    # Test suites for each user story category
    test_suites = [
        'test_architecture.py',           # 01_architecture.md - ARCH-001, ARCH-002, ARCH-003
        'test_data_rag.py',              # 02_data_rag.md - RAG-001, RAG-002, RAG-003  
        'test_workflows.py',             # 03_workflows.md - WF-001, WF-002, WF-003
        'test_admin_ui.py',              # 04_admin_ui.md - ADM-001, ADM-002, ADM-003, ADM-004
        'test_user_ui.py',               # 05_user_ui.md - UI-001, UI-002, UI-003, UI-004
        'test_testing_system.py',        # 06_testing.md - TEST-001, TEST-002, TEST-003
        'test_requirements_management.py' # 07_requirements_mgmt.md - REQ-001, REQ-002, REQ-003
    ]
    
    # Existing test suites to include
    existing_tests = [
        'test_bug_tracker.py',           # Bug tracking system
        'test_build_validator.py',       # Build validation system
        'test_ingestion_pipeline.py'    # Ingestion pipeline
    ]
    
    print("=" * 80)
    print("TTRPG CENTER - COMPREHENSIVE USER STORY TEST SUITE")
    print("=" * 80)
    print()
    
    # Set environment for testing
    os.environ['APP_ENV'] = 'test'
    os.environ['PORT'] = '8181'
    os.environ['PYTHONPATH'] = '.'
    
    # Run pytest with comprehensive reporting
    test_args = [
        '--verbose',
        '--tb=short',
        '--strict-markers',
        '--disable-warnings',
        '-x',  # Stop on first failure for debugging
    ]
    
    print("Running User Story Test Suites:")
    print("-" * 40)
    
    all_results = []
    
    for test_suite in test_suites + existing_tests:
        test_path = Path(__file__).parent / test_suite
        
        if test_path.exists():
            print(f"Running {test_suite}...")
            
            # Run individual test suite
            result = pytest.main([str(test_path)] + test_args)
            all_results.append((test_suite, result))
            
            if result == 0:
                print(f"✅ {test_suite} - PASSED")
            else:
                print(f"❌ {test_suite} - FAILED")
        else:
            print(f"⚠️  {test_suite} - NOT FOUND")
            all_results.append((test_suite, -1))
        
        print()
    
    # Summary report
    print("=" * 80)
    print("TEST EXECUTION SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, result in all_results if result == 0)
    failed_count = sum(1 for _, result in all_results if result != 0 and result != -1)
    missing_count = sum(1 for _, result in all_results if result == -1)
    
    print(f"Total Test Suites: {len(all_results)}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")
    print(f"Missing: {missing_count}")
    print()
    
    # Detailed results
    for test_suite, result in all_results:
        status = "PASSED" if result == 0 else ("FAILED" if result != -1 else "NOT FOUND")
        print(f"{test_suite:35} - {status}")
    
    print()
    print("=" * 80)
    
    # Overall status
    if failed_count == 0 and missing_count == 0:
        print("🎉 ALL USER STORY TESTS PASSED!")
        return 0
    elif failed_count > 0:
        print(f"❌ {failed_count} test suite(s) failed - review failures above")
        return 1
    else:
        print(f"⚠️  {missing_count} test suite(s) missing - implementation may be incomplete")
        return 2

def run_specific_user_story(story_number):
    """
    Run tests for a specific user story
    
    Args:
        story_number: User story number (1-7)
    """
    
    story_mapping = {
        1: 'test_architecture.py',
        2: 'test_data_rag.py', 
        3: 'test_workflows.py',
        4: 'test_admin_ui.py',
        5: 'test_user_ui.py',
        6: 'test_testing_system.py',
        7: 'test_requirements_management.py'
    }
    
    if story_number not in story_mapping:
        print(f"Invalid user story number: {story_number}. Must be 1-7.")
        return 1
    
    test_file = story_mapping[story_number]
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        print(f"Test file not found: {test_file}")
        return 1
    
    print(f"Running User Story {story_number:02d} tests: {test_file}")
    print("-" * 60)
    
    # Set test environment
    os.environ['APP_ENV'] = 'test'
    os.environ['PORT'] = '8181'
    os.environ['PYTHONPATH'] = '.'
    
    # Run tests with detailed output
    result = pytest.main([
        str(test_path),
        '--verbose',
        '--tb=long',
        '--strict-markers',
        '--disable-warnings'
    ])
    
    return result

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            story_num = int(sys.argv[1])
            exit_code = run_specific_user_story(story_num)
        except ValueError:
            print("Usage: python run_all_user_story_tests.py [story_number]")
            print("  story_number: 1-7 for specific user story, or omit for all tests")
            exit_code = 1
    else:
        exit_code = run_user_story_tests()
    
    sys.exit(exit_code)