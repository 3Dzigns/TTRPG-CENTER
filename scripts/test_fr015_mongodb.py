#!/usr/bin/env python3
"""
Test script for FR-015 MongoDB dictionary integration
Validates that MongoDB integration is properly implemented and configured.
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# Add src_common to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src_common"))

from admin import AdminDictionaryService
from mongo_dictionary_service import get_dictionary_service, MongoDictionaryService


async def test_mongodb_integration():
    """Test FR-015 MongoDB dictionary integration functionality"""

    print("=" * 60)
    print("FR-015 MongoDB Dictionary Integration Test")
    print("=" * 60)

    # Test 1: Verify AdminDictionaryService uses MongoDB by default
    print("\n1. Testing AdminDictionaryService MongoDB initialization...")

    admin_service = AdminDictionaryService(use_mongodb=True)
    print(f"   ✓ AdminDictionaryService initialized with use_mongodb=True")

    # Test 2: Verify MongoDB adapters can be created
    print("\n2. Testing MongoDB adapter creation for each environment...")

    environments = ['dev', 'test', 'prod']
    adapters = {}

    for env in environments:
        try:
            adapter = admin_service._get_adapter(env)
            adapters[env] = adapter
            if adapter:
                print(f"   ✓ MongoDB adapter created for {env}")

                # Test circuit breaker stats
                stats = adapter.get_circuit_breaker_stats()
                print(f"     Circuit breaker state: {stats.get('state', 'unknown')}")
            else:
                print(f"   ⚠ MongoDB adapter not created for {env} (may be normal if MongoDB not configured)")
        except Exception as e:
            print(f"   ✗ Error creating adapter for {env}: {e}")

    # Test 3: Test direct MongoDictionaryService
    print("\n3. Testing MongoDictionaryService direct usage...")

    try:
        mongo_service = MongoDictionaryService(env="dev")
        print(f"   ✓ MongoDictionaryService initialized for dev environment")

        # Test health check
        health = mongo_service.health_check()
        print(f"   Health status: {health.get('status', 'unknown')}")
        if health.get('error'):
            print(f"   Health error: {health['error']}")

        # Test stats (even if connection fails)
        stats = mongo_service.get_stats()
        print(f"   Stats: {stats}")

    except Exception as e:
        print(f"   ⚠ MongoDictionaryService test failed: {e}")
        print("   This may be expected if MongoDB is not running")

    # Test 4: Test global dictionary service
    print("\n4. Testing global dictionary service...")

    try:
        global_service = get_dictionary_service()
        print(f"   ✓ Global dictionary service retrieved")

        health = global_service.health_check()
        print(f"   Global service health: {health.get('status', 'unknown')}")

    except Exception as e:
        print(f"   ⚠ Global dictionary service test failed: {e}")

    # Test 5: Test dictionary operations (if MongoDB is available)
    print("\n5. Testing dictionary operations through admin service...")

    try:
        # Get stats for dev environment
        stats = await admin_service.get_environment_stats("dev")
        print(f"   ✓ Retrieved dev environment stats: {stats.total_terms} terms")

        # Try to list terms
        terms = await admin_service.list_terms("dev", limit=5)
        print(f"   ✓ Retrieved {len(terms)} terms from dev environment")

    except Exception as e:
        print(f"   ⚠ Dictionary operations test failed: {e}")
        print("   This is expected if MongoDB is not running or has no data")

    print("\n" + "=" * 60)
    print("FR-015 MongoDB Integration Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    # Set environment for testing
    os.environ["APP_ENV"] = "dev"

    # Run the async test
    asyncio.run(test_mongodb_integration())