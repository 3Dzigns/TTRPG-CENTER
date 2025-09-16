#!/usr/bin/env python3
"""
Validation script for FR-015 MongoDB Dictionary Integration
Checks that all components are properly integrated and configured.
"""

import sys
import os
from pathlib import Path

# Set up paths and environment
project_root = Path(__file__).parent.parent
src_path = project_root / "src_common"
sys.path.insert(0, str(src_path))

os.environ["APP_ENV"] = "dev"

def check_file_exists(file_path, description):
    """Check if a file exists and report result"""
    if file_path.exists():
        print(f"PASS - {description}: {file_path.name}")
        return True
    else:
        print(f"FAIL - {description}: {file_path.name} NOT FOUND")
        return False

def check_mongodb_service():
    """Verify MongoDB dictionary service components"""
    print("\n1. MongoDB Dictionary Service Components")
    print("-" * 45)

    components = [
        (project_root / "src_common" / "mongo_dictionary_service.py", "MongoDB Dictionary Service"),
        (project_root / "src_common" / "admin" / "mongo_adapter.py", "MongoDB Adapter"),
        (project_root / "src_common" / "admin" / "dictionary_models.py", "Dictionary Models"),
        (project_root / "src_common" / "patterns" / "circuit_breaker.py", "Circuit Breaker Pattern"),
        (project_root / "src_common" / "models" / "unified_dictionary.py", "Unified Dictionary Models")
    ]

    results = []
    for file_path, description in components:
        results.append(check_file_exists(file_path, description))

    return all(results)

def check_admin_routes():
    """Verify admin routes have MongoDB endpoints"""
    print("\n2. Admin Routes MongoDB Integration")
    print("-" * 38)

    try:
        with open(project_root / "src_common" / "admin_routes.py", "r") as f:
            content = f.read()

        endpoints = [
            "/api/admin/mongodb/health",
            "/api/admin/mongodb/status/{environment}",
            "/api/admin/mongodb/{environment}/reset-circuit-breaker"
        ]

        results = []
        for endpoint in endpoints:
            if endpoint in content:
                print(f"PASS - API endpoint: {endpoint}")
                results.append(True)
            else:
                print(f"FAIL - API endpoint missing: {endpoint}")
                results.append(False)

        # Check MongoDB initialization
        if "use_mongodb=True" in content:
            print("PASS - AdminDictionaryService initialized with MongoDB enabled")
            results.append(True)
        else:
            print("FAIL - AdminDictionaryService not configured for MongoDB")
            results.append(False)

        return all(results)

    except Exception as e:
        print(f"FAIL - Error checking admin routes: {e}")
        return False

def check_admin_templates():
    """Verify admin templates have MongoDB status displays"""
    print("\n3. Admin Templates MongoDB Integration")
    print("-" * 39)

    templates = [
        (project_root / "templates" / "admin_dashboard.html", "Admin Dashboard"),
        (project_root / "templates" / "admin" / "dictionary.html", "Dictionary Management")
    ]

    results = []
    for template_path, description in templates:
        try:
            with open(template_path, "r") as f:
                content = f.read()

            # Check for MongoDB status elements (different for each template)
            if "admin_dashboard.html" in str(template_path):
                mongodb_elements = [
                    "mongodb-status",
                    "mongo-connection",
                    "mongo-entries",
                    "loadMongoDBStatus"
                ]
            else:  # dictionary.html
                mongodb_elements = [
                    "dict-backend-status",
                    "dict-connection-status",
                    "checkBackendStatus",
                    "MongoDB"
                ]

            template_ok = True
            for element in mongodb_elements:
                if element in content:
                    print(f"PASS - {description} has {element}")
                else:
                    print(f"FAIL - {description} missing {element}")
                    template_ok = False

            results.append(template_ok)

        except Exception as e:
            print(f"FAIL - Error checking {description}: {e}")
            results.append(False)

    return all(results)

def check_performance_indexes():
    """Verify performance indexes are configured"""
    print("\n4. Performance Indexes Configuration")
    print("-" * 37)

    try:
        from mongo_dictionary_service import MongoDictionaryService

        # Check the index creation logic exists
        service = MongoDictionaryService(env="dev")

        # Look for index configuration in the service
        if hasattr(service, '_ensure_indexes'):
            print("PASS - Index creation method exists")

            # Check the service file for performance-related indexes
            with open(project_root / "src_common" / "mongo_dictionary_service.py", "r") as f:
                content = f.read()

            performance_indexes = [
                "primary_term_lookup",
                "term_normalized_index",
                "weighted_text_search",
                "1.5s search requirement"
            ]

            results = []
            for index_name in performance_indexes:
                if index_name in content:
                    print(f"PASS - Performance index/requirement: {index_name}")
                    results.append(True)
                else:
                    print(f"FAIL - Missing performance index/requirement: {index_name}")
                    results.append(False)

            return all(results)
        else:
            print("FAIL - Index creation method not found")
            return False

    except Exception as e:
        print(f"FAIL - Error checking performance indexes: {e}")
        return False

def check_circuit_breaker_integration():
    """Verify circuit breaker pattern is integrated"""
    print("\n5. Circuit Breaker Integration")
    print("-" * 30)

    try:
        with open(project_root / "src_common" / "admin" / "mongo_adapter.py", "r") as f:
            content = f.read()

        circuit_breaker_features = [
            "CircuitBreaker",
            "CircuitBreakerConfig",
            "get_circuit_breaker_stats",
            "reset_circuit_breaker",
            "_execute_with_circuit_breaker"
        ]

        results = []
        for feature in circuit_breaker_features:
            if feature in content:
                print(f"PASS - Circuit breaker feature: {feature}")
                results.append(True)
            else:
                print(f"FAIL - Missing circuit breaker feature: {feature}")
                results.append(False)

        return all(results)

    except Exception as e:
        print(f"FAIL - Error checking circuit breaker integration: {e}")
        return False

def main():
    """Run all validation checks"""
    print("FR-015 MongoDB Dictionary Integration Validation")
    print("=" * 50)

    checks = [
        ("MongoDB Service Components", check_mongodb_service),
        ("Admin Routes Integration", check_admin_routes),
        ("Admin Templates Integration", check_admin_templates),
        ("Performance Indexes", check_performance_indexes),
        ("Circuit Breaker Integration", check_circuit_breaker_integration)
    ]

    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"\nFAIL - {check_name}: Unexpected error: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)

    for i, (check_name, _) in enumerate(checks):
        status = "PASS" if results[i] else "FAIL"
        print(f"{check_name}: {status}")

    overall_pass = all(results)
    print(f"\nOverall Status: {'PASS - FR-015 integration is complete' if overall_pass else 'FAIL - Some components are missing'}")
    print("=" * 50)

    return overall_pass

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)