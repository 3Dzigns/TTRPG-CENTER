#!/usr/bin/env python3
"""Monitor Ultimate Magic pipeline processing."""

import time
import sys
from pathlib import Path

# Add ingestion to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.core.job_registry import JobRegistry
from ingestion.config import Settings

JOB_ID = "6854445f-4f1f-e9bd-f825-79f92680d070"

def check_status():
    """Check and print pipeline status."""
    settings = Settings()
    registry = JobRegistry.global_instance(settings=settings)

    job = registry.get(JOB_ID)

    if not job:
        print("❌ Job not found in registry")
        return False

    state_name = job.state.name if hasattr(job.state, 'name') else str(job.state)

    print(f"\n{'='*60}")
    print(f"Job State: {state_name}")
    print(f"Stage: {job.stage}")
    print(f"Message: {job.message}")
    print(f"{'='*60}")

    # Check artifacts
    artifacts_dir = settings.artifacts_dir / JOB_ID

    unstructured_file = artifacts_dir / "unstructured" / "elements.json"
    if unstructured_file.exists():
        size_kb = unstructured_file.stat().st_size / 1024
        print(f"✓ Unstructured: {size_kb:.1f} KB")
    else:
        print("⏳ Unstructured: Processing...")

    metadata_file = artifacts_dir / "metadata" / "elements_with_meta.json"
    if metadata_file.exists():
        size_kb = metadata_file.stat().st_size / 1024
        print(f"✓ Metadata: {size_kb:.1f} KB")
    else:
        print("⏳ Metadata: Pending...")

    embeddings_file = artifacts_dir / "embeddings" / "embeddings.json"
    if embeddings_file.exists():
        size_kb = embeddings_file.stat().st_size / 1024
        print(f"✓ Embeddings: {size_kb:.1f} KB")
    else:
        print("⏳ Embeddings: Pending...")

    # Check if complete
    if state_name in ["COMPLETED", "FAILED", "ERROR"]:
        print(f"\n🏁 Pipeline finished with state: {state_name}")
        return False  # Stop monitoring

    return True  # Continue monitoring

def main():
    """Main monitoring loop."""
    print("=== ULTIMATE MAGIC PIPELINE MONITOR ===")
    print(f"Job ID: {JOB_ID}")
    print(f"Started: {time.strftime('%H:%M:%S')}")

    for i in range(60):  # Monitor for up to 10 minutes (60 * 10 seconds)
        print(f"\n--- Check {i+1}/60 at {time.strftime('%H:%M:%S')} ---")

        try:
            should_continue = check_status()
            if not should_continue:
                break
        except Exception as e:
            print(f"❌ Error checking status: {e}")

        time.sleep(10)  # Check every 10 seconds

    print("\n=== MONITORING COMPLETE ===")

if __name__ == "__main__":
    main()
