#!/usr/bin/env python3
"""
Promote Build to Test Environment
=================================

Promotes the current build with 3rd party integration to TEST environment
following proper environment separation and validation procedures.
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timezone

def validate_current_build():
    """Validate the current build is ready for promotion"""
    print("🔍 VALIDATING BUILD FOR TEST PROMOTION")
    print("=" * 50)
    
    # Check critical files exist
    critical_files = [
        "app/ingestion/dictionary_system.py",
        "app/common/run_mode.py", 
        "app/api/dictionary_endpoints.py",
        "app/templates/dictionary_tab.html",
        "app/ingestion/ingest_unstructured_haystack_llama.py",
        "test_3rd_party_integration.py"
    ]
    
    missing_files = []
    for file_path in critical_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Missing critical files: {missing_files}")
        return False
    
    print("✅ All critical files present")
    
    # Check git status is clean  
    import subprocess
    result = subprocess.run(['git', 'status', '--porcelain'], 
                          capture_output=True, text=True)
    
    if result.stdout.strip():
        print("⚠️  Working directory has uncommitted changes")
        print("   Please commit all changes before promotion")
        return False
    
    print("✅ Git working directory clean")
    
    # Get current commit hash
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                          capture_output=True, text=True)
    commit_hash = result.stdout.strip()
    
    print(f"✅ Current commit: {commit_hash[:8]}")
    
    return True

def create_test_configuration():
    """Create TEST environment configuration"""
    print("\n🔧 CREATING TEST ENVIRONMENT CONFIG")
    print("=" * 45)
    
    # Ensure config directory exists
    config_dir = Path("config")
    config_dir.mkdir(exist_ok=True)
    
    # Read current dev config as template
    dev_config_path = config_dir / ".env.dev"
    test_config_path = config_dir / ".env.test"
    
    if dev_config_path.exists():
        # Copy dev config and modify for test
        with open(dev_config_path, 'r') as f:
            dev_config = f.read()
        
        # Modify for test environment
        test_config = dev_config.replace(
            'APP_ENV=dev', 'APP_ENV=test'
        ).replace(
            'ttrpg_chunks_dev', 'ttrpg_chunks_test'
        ).replace(
            'RUN_MODE=dev', 'RUN_MODE=maint'  # Allow maintenance operations in test
        )
        
        # Add test-specific settings
        test_additions = """
# TEST Environment Specific Settings
LOG_LEVEL=INFO
DEBUG_MODE=false
ENABLE_METRICS=true
TEST_MODE=true

# Dictionary snapshots for test
DICTIONARY_COLLECTION=ttrpg_dictionary_test

# Status tracking
STATUS_RETENTION_DAYS=7
AUDIT_ENABLED=true
"""
        test_config += test_additions
        
        with open(test_config_path, 'w') as f:
            f.write(test_config)
        
        print(f"✅ Test config created: {test_config_path}")
    else:
        print("⚠️  Dev config not found - creating minimal test config")
        
        minimal_config = """# TEST Environment Configuration
APP_ENV=test
RUN_MODE=maint
LOG_LEVEL=INFO
DEBUG_MODE=false

# AstraDB settings (update with test credentials)
ASTRA_DB_API_ENDPOINT=https://your-test-db-endpoint.apps.astra.datastax.com
ASTRA_DB_APPLICATION_TOKEN=AstraCS:your-test-token
ASTRA_DB_KEYSPACE=test_keyspace

# OpenAI settings
OPENAI_API_KEY=sk-your-test-api-key

# Collections for test
COLLECTION_NAME=ttrpg_chunks_test
DICTIONARY_COLLECTION=ttrpg_dictionary_test

# Test-specific settings
TEST_MODE=true
ENABLE_METRICS=true
STATUS_RETENTION_DAYS=7
"""
        
        with open(test_config_path, 'w') as f:
            f.write(minimal_config)
        
        print(f"✅ Minimal test config created: {test_config_path}")
    
    return True

def create_promotion_manifest():
    """Create promotion manifest for tracking"""
    print("\n📋 CREATING PROMOTION MANIFEST")
    print("=" * 40)
    
    # Get git info
    import subprocess
    commit_result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                 capture_output=True, text=True)
    commit_hash = commit_result.stdout.strip()
    
    branch_result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True)
    branch = branch_result.stdout.strip()
    
    # Create manifest
    manifest = {
        "promotion_id": f"test-{int(time.time())}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_env": "dev",
        "target_env": "test",
        "git_info": {
            "commit_hash": commit_hash,
            "branch": branch,
            "commit_hash_short": commit_hash[:8]
        },
        "features_included": [
            "3rd party integration pipeline (Unstructured + Haystack + LlamaIndex)",
            "Automatic dictionary system with AstraDB persistence",
            "RUN_MODE guardrails and compliance system", 
            "Admin UI dictionary tab with editing capabilities",
            "Enhanced knowledge graph with semantic relationships",
            "Image preservation and linking system",
            "Structured status events for all ingestion phases"
        ],
        "validation_status": "passed",
        "deployment_ready": True,
        "rollback_commit": commit_hash,
        "test_requirements": [
            "Update .env.test with test environment credentials",
            "Run test_3rd_party_integration.py for validation",
            "Verify dictionary endpoints are accessible",
            "Test RUN_MODE enforcement in test environment",
            "Validate image extraction and linking",
            "Confirm knowledge graph creation"
        ]
    }
    
    # Save manifest
    manifest_dir = Path("artifacts/promotions")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_file = manifest_dir / f"promote_to_test_{manifest['promotion_id']}.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✅ Promotion manifest created: {manifest_file}")
    print(f"   Promotion ID: {manifest['promotion_id']}")
    print(f"   Commit: {commit_hash[:8]}")
    
    return manifest

def run_pre_promotion_tests():
    """Run basic tests before promotion"""
    print("\n🧪 RUNNING PRE-PROMOTION TESTS")
    print("=" * 40)
    
    try:
        # Test imports
        print("Testing module imports...")
        
        # Test dictionary system
        from app.ingestion.dictionary_system import DictionaryCreationSystem
        print("✅ Dictionary system import successful")
        
        # Test run mode system
        from app.common.run_mode import get_run_mode_manager, RunMode
        print("✅ RUN_MODE system import successful")
        
        # Test API endpoints
        from app.api.dictionary_endpoints import router
        print("✅ Dictionary API endpoints import successful")
        
        # Test basic dictionary functionality
        dict_system = DictionaryCreationSystem("test")
        print("✅ Dictionary system initialization successful")
        
        # Test RUN_MODE functionality
        run_mode_mgr = get_run_mode_manager()
        print(f"✅ RUN_MODE manager active: {run_mode_mgr.current_mode.value}")
        
        print("✅ All pre-promotion tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Pre-promotion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_deployment_instructions():
    """Generate deployment instructions for test environment"""
    
    instructions = """
# TTRPG CENTER - TEST ENVIRONMENT DEPLOYMENT

## 🚀 Deployment Instructions

### Prerequisites
1. Test environment AstraDB instance configured
2. Test OpenAI API key available  
3. Test domain/server access configured

### Environment Setup
1. Update `config/.env.test` with actual test environment credentials:
   ```bash
   # Update these values with your test environment settings
   ASTRA_DB_API_ENDPOINT=https://your-test-db-endpoint.apps.astra.datastax.com
   ASTRA_DB_APPLICATION_TOKEN=AstraCS:your-test-token
   ASTRA_DB_KEYSPACE=test_keyspace
   OPENAI_API_KEY=sk-your-test-api-key
   ```

2. Set environment for test deployment:
   ```bash
   export APP_ENV=test
   export RUN_MODE=maint  # Allow maintenance operations for initial setup
   ```

### Database Setup  
1. Create test collections in AstraDB:
   ```python
   # Collections needed:
   - ttrpg_chunks_test (vector collection for chunks)
   - ttrpg_dictionary_test (collection for dictionary snapshots)
   ```

2. Verify database connectivity:
   ```bash
   python -c "from app.common.astra_client import get_vector_store; print('DB connection OK')"
   ```

### Application Deployment
1. Install additional dependencies (if not already installed):
   ```bash
   pip install unstructured[all-docs]  # For PDF processing
   pip install haystack-ai              # For preprocessing
   pip install llama-index             # For knowledge graphs (optional)
   ```

2. Run validation tests:
   ```bash
   python test_3rd_party_integration.py
   ```

3. Start application in test mode:
   ```bash
   APP_ENV=test python app/server.py
   ```

### Feature Validation Checklist
- [ ] Dictionary API endpoints accessible at `/api/dictionary/`
- [ ] Dictionary tab loads in Admin UI  
- [ ] 3-pass integration pipeline functional
- [ ] RUN_MODE guardrails enforce test restrictions
- [ ] Image extraction and linking working
- [ ] Knowledge graph creation operational
- [ ] Status events properly structured and logged

### Post-Deployment Verification
1. Access dictionary tab in Admin UI
2. Run sample ingestion to test full pipeline
3. Verify dictionary snapshots are created
4. Test edit functionality for dictionary entries
5. Confirm RUN_MODE restrictions work properly

### Rollback Procedure
If issues arise, rollback to previous commit:
```bash
git checkout {rollback_commit}
git push -f origin main  # Only if safe to force push
```

### Support
- Check `artifacts/status/test/` for detailed logs
- Review `artifacts/promotions/` for promotion history
- Run diagnostic tests with `test_3rd_party_integration.py`
"""
    
    instructions_file = Path("DEPLOYMENT_TEST.md")
    with open(instructions_file, 'w') as f:
        f.write(instructions.strip())
    
    print(f"📝 Deployment instructions created: {instructions_file}")
    return instructions_file

def main():
    """Main promotion workflow"""
    print("🚀 TTRPG CENTER - PROMOTE TO TEST ENVIRONMENT")
    print("=" * 80)
    
    # Step 1: Validate current build
    if not validate_current_build():
        print("❌ Build validation failed. Cannot promote to test.")
        return False
    
    # Step 2: Create test configuration  
    if not create_test_configuration():
        print("❌ Failed to create test configuration.")
        return False
    
    # Step 3: Run pre-promotion tests
    if not run_pre_promotion_tests():
        print("❌ Pre-promotion tests failed. Cannot promote to test.")
        return False
    
    # Step 4: Create promotion manifest
    manifest = create_promotion_manifest()
    if not manifest:
        print("❌ Failed to create promotion manifest.")
        return False
    
    # Step 5: Generate deployment instructions
    deployment_file = generate_deployment_instructions()
    
    print("\n" + "=" * 80)
    print("🎉 PROMOTION TO TEST ENVIRONMENT READY")
    print("=" * 80)
    
    print(f"\n✅ Build validated and prepared for test deployment")
    print(f"✅ Test configuration created")  
    print(f"✅ Pre-promotion tests passed")
    print(f"✅ Promotion manifest created: {manifest['promotion_id']}")
    print(f"✅ Deployment instructions generated: {deployment_file}")
    
    print(f"\n📋 NEXT STEPS:")
    print(f"   1. Review and update config/.env.test with actual test credentials")
    print(f"   2. Deploy to test environment following {deployment_file}")
    print(f"   3. Run validation tests in test environment")
    print(f"   4. Verify all features work as expected")
    
    print(f"\n🚀 FEATURES PROMOTED:")
    for feature in manifest['features_included']:
        print(f"   ✅ {feature}")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    print("\n🎯 Promotion preparation complete!")