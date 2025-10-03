#!/usr/bin/env python
"""Identify removal candidates - files that appear unused"""

import json
import pathlib
from datetime import datetime, timedelta

def identify_removal_candidates():
    """Identify files that may be safe to remove"""

    root = pathlib.Path(".")
    candidates = []

    # Load inventory
    inv_file = root / "docs/cleanup/repo-inventory.json"
    if not inv_file.exists():
        print("Error: Run inventory.py first")
        return

    with open(inv_file) as f:
        inventory = json.load(f)

    # Criteria for removal candidates
    old_threshold = datetime.now() - timedelta(days=90)  # 90 days old

    for file_info in inventory.get('all_files', []):
        path = pathlib.Path(file_info['path'])

        # Skip if in protected directories
        protected_dirs = ['env', 'src_common', 'services', 'tests', 'scripts', '.github', 'tools']
        if any(path.parts[0] == d for d in protected_dirs if len(path.parts) > 0):
            continue

        # Check age
        mtime = datetime.fromtimestamp(file_info['mtime'])
        is_old = mtime < old_threshold

        # Check if it's a known temp/debug file
        is_temp = any(pattern in path.name.lower() for pattern in [
            'temp', 'tmp', 'debug', 'test_output', 'scratch'
        ])

        # Check size (very small or very large unused files)
        is_tiny = file_info['size'] < 100  # < 100 bytes
        is_huge = file_info['size'] > 10_000_000  # > 10MB

        # Categorize
        if path.suffix == '.pyc' or '__pycache__' in path.parts:
            category = 'compiled_python'
            reason = 'Compiled Python bytecode (auto-generated)'
            action = 'safe_to_delete'
        elif is_temp:
            category = 'temp_files'
            reason = 'Temporary/debug file'
            action = 'quarantine'
        elif is_old and is_tiny:
            category = 'old_tiny_files'
            reason = f'Old ({mtime.date()}) and tiny ({file_info["size"]} bytes)'
            action = 'quarantine'
        elif path.suffix in ['.log', '.tmp']:
            category = 'log_temp'
            reason = 'Log or temp file'
            action = 'quarantine'
        else:
            continue  # Not a candidate

        candidates.append({
            'path': str(path),
            'size': file_info['size'],
            'mtime': file_info['mtime_iso'],
            'category': category,
            'reason': reason,
            'action': action
        })

    # Group by category
    by_category = {}
    for c in candidates:
        cat = c['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(c)

    # Generate report
    report = {
        'generated_at': datetime.now().isoformat(),
        'total_candidates': len(candidates),
        'by_category': {k: len(v) for k, v in by_category.items()},
        'candidates': candidates
    }

    # Write JSON report
    (root / 'docs/cleanup/removal-candidates.json').write_text(
        json.dumps(report, indent=2)
    )

    # Write Markdown report
    md_lines = [
        "# Removal Candidates Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Total Candidates:** {report['total_candidates']}",
        "",
        "## Summary by Category",
        ""
    ]

    for category, count in report['by_category'].items():
        md_lines.append(f"- **{category}**: {count} files")

    md_lines.extend([
        "",
        "## Candidates by Category",
        ""
    ])

    for category, files in sorted(by_category.items()):
        md_lines.extend([
            f"### {category.replace('_', ' ').title()} ({len(files)})",
            "",
            "| Path | Size | Last Modified | Reason | Action |",
            "|------|------|---------------|--------|--------|"
        ])

        for f in files[:20]:  # Limit to 20 per category in report
            md_lines.append(
                f"| `{f['path']}` | {f['size']} | {f['mtime'][:10]} | {f['reason']} | {f['action']} |"
            )

        if len(files) > 20:
            md_lines.append(f"\n... and {len(files) - 20} more")
        md_lines.append("")

    md_lines.extend([
        "## Recommended Actions",
        "",
        "1. **safe_to_delete**: Can be deleted immediately (compiled bytecode)",
        "2. **quarantine**: Move to quarantine/YYYYMMDD/ for review",
        "3. **keep**: Preserve (not shown in this report)",
        "",
        "## Next Steps",
        "",
        "```bash",
        "# Delete compiled Python files",
        "find . -type f -name '*.pyc' -delete",
        "find . -type d -name '__pycache__' -exec rm -rf {} +",
        "",
        "# Review and quarantine other candidates",
        "python scripts/maintenance/quarantine_candidates.py",
        "```",
        ""
    ])

    (root / 'docs/cleanup/Removal-Candidates.md').write_text('\n'.join(md_lines))

    print(f"=== Removal Candidates Report ===")
    print(f"Total candidates: {len(candidates)}")
    print(f"\nBy category:")
    for category, count in report['by_category'].items():
        print(f"  {category}: {count}")
    print(f"\nReports generated:")
    print(f"  - docs/cleanup/removal-candidates.json")
    print(f"  - docs/cleanup/Removal-Candidates.md")

    return report

if __name__ == '__main__':
    identify_removal_candidates()
