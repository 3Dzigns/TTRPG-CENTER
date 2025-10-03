#!/usr/bin/env python
"""Relocate Stray Files to Canonical Locations"""

import os
import json
import shutil
import pathlib
from datetime import datetime

def relocate_stray_files():
    """Relocate stray files from root to appropriate directories"""

    root = pathlib.Path(".")
    timestamp = datetime.now().strftime("%Y%m%d")
    quarantine_dir = root / f"quarantine/{timestamp}"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    relocations = []

    # Define relocation rules
    rules = {
        # Logs -> env/dev/logs/historical/
        "*.log": ("env/dev/logs/historical", "log files"),

        # Test files -> tests/unit/
        "test_*.py": ("tests/unit", "test scripts"),

        # PDFs -> quarantine (test artifacts)
        "*.pdf": (f"quarantine/{timestamp}", "test PDFs"),

        # Database files -> env/dev/data/
        "*.db": ("env/dev/data", "database files"),

        # Patch files -> quarantine (old patches)
        "patch_*.py": (f"quarantine/{timestamp}", "patch scripts"),

        # Temp/test HTML -> quarantine
        "temp*.html": (f"quarantine/{timestamp}", "temp HTML"),
        "test*.html": (f"quarantine/{timestamp}", "test HTML"),

        # Analysis/planning docs -> docs/analysis/
        "*-analysis-report.md": ("docs/analysis", "analysis reports"),
        "*_VALIDATION_SUMMARY.md": ("docs/analysis", "validation summaries"),
        "*ROADMAP.md": ("docs/planning", "roadmaps"),
        "*INDEX.md": ("docs", "index files"),

        # Feature/bug docs -> docs/features or docs/bugs
        "FR-*.md": ("docs/features", "feature docs"),
        "Current_issue.md": ("docs/bugs", "issue tracking"),

        # Cleanup summaries -> docs/cleanup
        "CLEANUP_*.md": ("docs/cleanup", "cleanup summaries"),

        # App files - analyze separately
        "app_*.py": (None, "app files - needs analysis"),

        # Other temp files
        "TEMP_*": (f"quarantine/{timestamp}", "temp files"),
        "nul": (f"quarantine/{timestamp}", "null device file"),
        "security-report.json": ("env/dev/logs/security", "security reports"),
    }

    # Process each rule
    for pattern, (dest, description) in rules.items():
        if dest is None:
            continue  # Skip items needing manual analysis

        for file in root.glob(pattern):
            if file.is_file() and file.parent == root:
                dest_path = root / dest
                dest_path.mkdir(parents=True, exist_ok=True)

                dest_file = dest_path / file.name

                try:
                    # Use git mv if file is tracked
                    import subprocess
                    result = subprocess.run(['git', 'ls-files', str(file)],
                                          capture_output=True, text=True)
                    if result.stdout.strip():
                        # File is tracked, use git mv
                        subprocess.run(['git', 'mv', str(file), str(dest_file)], check=True)
                        method = "git mv"
                    else:
                        # File is untracked, use regular move
                        shutil.move(str(file), str(dest_file))
                        method = "mv"

                    relocations.append({
                        "source": str(file),
                        "destination": str(dest_file),
                        "reason": description,
                        "method": method
                    })
                    print(f"{method}: {file} -> {dest_file}")
                except Exception as e:
                    print(f"Error moving {file}: {e}")

    # Handle directories
    dir_rules = {
        "Test Uploads": "env/dev/uploads/test-fixtures",
        "tmp_test_job": f"quarantine/{timestamp}/tmp_test_job",
        "tmp_overflow": f"quarantine/{timestamp}/tmp_overflow",
        "manual_job": f"quarantine/{timestamp}/manual_job",
        "manual_job_full": f"quarantine/{timestamp}/manual_job_full",
        ";C": f"quarantine/{timestamp}/unknown_C_dir",
        "docker-data": f"quarantine/{timestamp}/docker-data",
    }

    for src_dir, dest_rel in dir_rules.items():
        src_path = root / src_dir
        if src_path.exists() and src_path.is_dir():
            dest_path = root / dest_rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                shutil.move(str(src_path), str(dest_path))
                relocations.append({
                    "source": str(src_path),
                    "destination": str(dest_path),
                    "reason": "stray directory",
                    "method": "mv"
                })
                print(f"mv: {src_path} -> {dest_path}")
            except Exception as e:
                print(f"Error moving directory {src_path}: {e}")

    # Generate relocation report
    report = {
        "relocation_date": timestamp,
        "total_relocations": len(relocations),
        "relocations": relocations
    }

    (root / "docs/cleanup/relocations.json").write_text(json.dumps(report, indent=2))

    # Generate markdown report
    md_lines = [
        "# File Relocation Report",
        "",
        f"**Date:** {timestamp}",
        f"**Total Relocations:** {len(relocations)}",
        "",
        "## Relocated Files",
        "",
        "| Source | Destination | Reason | Method |",
        "|--------|-------------|--------|--------|"
    ]

    for r in relocations:
        md_lines.append(f"| `{r['source']}` | `{r['destination']}` | {r['reason']} | {r['method']} |")

    md_lines.extend([
        "",
        "## Notes",
        "",
        "- All relocations preserve file history when using `git mv`",
        "- Quarantined files can be restored if needed",
        "- App files (app_*.py) require manual analysis before relocation",
        ""
    ])

    (root / "docs/cleanup/relocations-report.md").write_text('\n'.join(md_lines))

    print(f"\n=== Relocation Summary ===")
    print(f"Date: {timestamp}")
    print(f"Files/directories relocated: {len(relocations)}")
    print(f"\nReports generated:")
    print(f"  - docs/cleanup/relocations.json")
    print(f"  - docs/cleanup/relocations-report.md")

    return report

if __name__ == '__main__':
    relocate_stray_files()
