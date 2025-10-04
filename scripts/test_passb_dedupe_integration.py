#!/usr/bin/env python3
"""Integration test for Pass B deduplication using Cyberpunk job."""

import json
import sys
from pathlib import Path

# Add src_common to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src_common.pass_b_logical_splitter import LogicalSplitter


def main():
    """Re-run Pass B on Cyberpunk job with deduplication enabled."""

    # Test configuration
    job_id = "job_1759593741_dev_dedupe_test"
    env = "dev"

    # Paths
    project_root = Path(__file__).parent.parent
    source_pdf = project_root / "env/dev/uploads/Cyberpunk v3 - CP4110 Core Rulebook.pdf"
    job_dir = project_root / "env/dev/artifacts" / job_id
    pass_a_manifest = project_root / "env/dev/artifacts/job_1759593741_dev/pass_a" / "job_1759593741_dev_passA.toc.json"
    job_log_file = job_dir / f"{job_id}.log"

    # Create job directory
    job_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting Pass B deduplication test...")
    print(f"Job ID: {job_id}")
    print(f"Source PDF: {source_pdf}")
    print(f"Pass A manifest: {pass_a_manifest}")

    # Run Pass B with deduplication
    splitter = LogicalSplitter(
        job_id=job_id,
        env=env,
        pass_a_manifest=pass_a_manifest,
        job_log_file=job_log_file,
    )

    result = splitter.process(source_pdf, job_dir, lightweight=False)

    # Read split_index.json
    split_index_path = job_dir / "pass_b" / "split_index.json"
    with split_index_path.open("r") as f:
        split_index = json.load(f)

    # Read split_summary.json
    summary_path = job_dir / "pass_b" / "split_summary.json"
    with summary_path.open("r") as f:
        summary = json.load(f)

    # Print results
    print("\n" + "="*80)
    print("PASS B DEDUPLICATION TEST RESULTS")
    print("="*80)

    print(f"\nJob ID: {result.job_id}")
    print(f"Split performed: {result.split_performed}")
    print(f"Total pages: {result.total_pages}")
    print(f"Unique parts created: {len(result.parts)}")

    if "skipped_duplicates" in split_index:
        skipped = split_index["skipped_duplicates"]
        print(f"Duplicate parts skipped: {len(skipped)}")
    else:
        print("Duplicate parts skipped: 0 (no duplicates found)")
        skipped = []

    if "deduplication" in summary:
        dedupe = summary["deduplication"]
        print(f"\nDeduplication Statistics:")
        print(f"  Total parts generated: {dedupe['total_parts_generated']}")
        print(f"  Unique parts: {dedupe['unique_parts']}")
        print(f"  Duplicates skipped: {dedupe['duplicate_parts_skipped']}")
        print(f"  Deduplication rate: {dedupe['deduplication_rate_percent']}%")

        # Calculate estimated runtime savings
        duplicates_skipped = dedupe['duplicate_parts_skipped']
        estimated_savings_hours = (duplicates_skipped * 120) / 3600
        print(f"  Estimated runtime savings: {estimated_savings_hours:.2f} hours (@ 120s/part)")
    else:
        print("\nNo deduplication statistics (no duplicates found)")

    # Show sample duplicate groups
    if skipped:
        print(f"\nSample duplicate groups (showing first 5):")
        seen_checksums = {}
        for part in result.parts:
            seen_checksums[part.checksum_sha256] = part.part_id

        for idx, dup in enumerate(skipped[:5], 1):
            canonical = dup["duplicates_of"]
            print(f"\n  {idx}. {dup['part_id']} (section {dup['section_id']})")
            print(f"     Pages: {dup['page_start']}-{dup['page_end']}")
            print(f"     Duplicates: {canonical}")
            print(f"     Checksum: {dup['checksum_sha256'][:16]}...")

    print("\n" + "="*80)
    print(f"\nArtifacts saved to: {job_dir}")
    print(f"Split index: {split_index_path}")
    print(f"Summary: {summary_path}")
    print("="*80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
