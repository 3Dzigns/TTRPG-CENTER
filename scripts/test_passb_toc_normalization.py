#!/usr/bin/env python3
"""Integration test for Pass B TOC normalization using Cyberpunk job."""

import json
import sys
from pathlib import Path

# Add src_common to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src_common.pass_b_logical_splitter import LogicalSplitter


def main():
    """Re-run Pass B on Cyberpunk job with TOC normalization and validation enabled."""

    # Test configuration
    job_id = "job_1759593741_dev_toc_test"
    env = "dev"

    # Paths
    project_root = Path(__file__).parent.parent
    source_pdf = project_root / "env/dev/uploads/Cyberpunk v3 - CP4110 Core Rulebook.pdf"
    job_dir = project_root / "env/dev/artifacts" / job_id
    pass_a_manifest = project_root / "env/dev/artifacts/job_1759593741_dev/pass_a" / "job_1759593741_dev_passA.toc.json"
    job_log_file = job_dir / f"{job_id}.log"

    # Acceptance criteria from PassB_TOC_Normalization_Fix.md
    MAX_EXPECTED_PARTS = 40
    ORIGINAL_PART_COUNT = 317

    # Create job directory
    job_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting Pass B TOC Normalization Integration Test...")
    print(f"Job ID: {job_id}")
    print(f"Source PDF: {source_pdf}")
    print(f"Pass A manifest: {pass_a_manifest}")
    print(f"\nExpected outcome: <={MAX_EXPECTED_PARTS} parts (down from {ORIGINAL_PART_COUNT})")

    # Run Pass B with TOC normalization and validation
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
    print("PASS B TOC NORMALIZATION TEST RESULTS")
    print("="*80)

    print(f"\nJob ID: {result.job_id}")
    print(f"Split performed: {result.split_performed}")
    print(f"Total pages: {result.total_pages}")
    print(f"Total parts created: {len(result.parts)}")

    # Calculate part count reduction
    part_count_reduction = ORIGINAL_PART_COUNT - len(result.parts)
    reduction_pct = (part_count_reduction / ORIGINAL_PART_COUNT) * 100

    print(f"\nPart Count Analysis:")
    print(f"  Original (buggy): {ORIGINAL_PART_COUNT} parts")
    print(f"  Current (fixed): {len(result.parts)} parts")
    print(f"  Reduction: {part_count_reduction} parts ({reduction_pct:.1f}%)")

    # Acceptance criteria check
    if len(result.parts) <= MAX_EXPECTED_PARTS:
        print(f"  [PASS] Part count <= {MAX_EXPECTED_PARTS}")
    else:
        print(f"  [FAIL] Part count exceeds {MAX_EXPECTED_PARTS}")

    # Check for TOC validation statistics
    if "toc_validation" in summary:
        toc_val = summary["toc_validation"]
        print(f"\nTOC Validation Statistics:")
        print(f"  Raw TOC entries: {toc_val.get('raw_entries', 'N/A')}")
        print(f"  Valid entries: {toc_val.get('valid_entries', 'N/A')}")
        print(f"  Invalid entries: {toc_val.get('invalid_entries', 'N/A')}")
        if 'invalid_reasons' in toc_val:
            print(f"  Invalid reasons:")
            for reason, count in toc_val['invalid_reasons'].items():
                print(f"    - {reason}: {count}")

    # Check for deduplication statistics
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

    # Check for large_section_chunked parts
    large_section_parts = [p for p in result.parts if "large_section" in str(p)]
    if large_section_parts:
        print(f"\nLarge Section Chunking:")
        print(f"  Parts with large_section_chunked: {len(large_section_parts)}")

    # Show part distribution by selection reason
    selection_reasons = {}
    for part_data in split_index.get("parts", []):
        reason = part_data.get("selection_reason", "unknown")
        selection_reasons[reason] = selection_reasons.get(reason, 0) + 1

    print(f"\nPart Selection Reasons:")
    for reason, count in sorted(selection_reasons.items()):
        print(f"  {reason}: {count}")

    # Verify distinct page ranges
    page_ranges = set()
    duplicate_ranges = []
    for part_data in split_index.get("parts", []):
        range_key = (part_data['page_start'], part_data['page_end'])
        if range_key in page_ranges:
            duplicate_ranges.append(range_key)
        page_ranges.add(range_key)

    print(f"\nPage Range Analysis:")
    print(f"  Unique page ranges: {len(page_ranges)}")
    print(f"  Duplicate page ranges: {len(duplicate_ranges)}")

    if duplicate_ranges:
        print(f"  [WARNING] Found duplicate page ranges!")
        for start, end in duplicate_ranges[:5]:
            print(f"    Pages {start}-{end}")
    else:
        print(f"  [OK] All page ranges are distinct")

    print("\n" + "="*80)
    print(f"\nArtifacts saved to: {job_dir}")
    print(f"Split index: {split_index_path}")
    print(f"Summary: {summary_path}")
    print("="*80)

    # Final verdict
    print("\n" + "="*80)
    print("TEST VERDICT")
    print("="*80)

    passing = True
    if len(result.parts) > MAX_EXPECTED_PARTS:
        print(f"[FAIL] Part count {len(result.parts)} exceeds threshold {MAX_EXPECTED_PARTS}")
        passing = False
    else:
        print(f"[PASS] Part count {len(result.parts)} <= {MAX_EXPECTED_PARTS}")

    if duplicate_ranges:
        print(f"[WARNING] Found {len(duplicate_ranges)} duplicate page ranges")
    else:
        print(f"[PASS] All page ranges are distinct")

    print("="*80)

    return 0 if passing else 1


if __name__ == "__main__":
    sys.exit(main())
