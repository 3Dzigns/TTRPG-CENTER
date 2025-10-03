#!/usr/bin/env python
"""Reachability Analysis Script - Identifies reachable code paths"""

import os
import json
import pathlib
import subprocess
import ast
from collections import defaultdict
from datetime import datetime

def find_entry_points():
    """Find all entry points in the codebase"""
    entry_points = []
    root = pathlib.Path(".")

    # FastAPI apps
    for py_file in root.rglob("*.py"):
        try:
            content = py_file.read_text()
            if "FastAPI()" in content or "app = FastAPI" in content:
                entry_points.append({
                    "file": str(py_file),
                    "type": "fastapi_app",
                    "description": "FastAPI application"
                })
        except:
            pass

    # CLI scripts (if __name__ == "__main__")
    for py_file in root.rglob("*.py"):
        try:
            content = py_file.read_text()
            if '__name__ == "__main__"' in content or "__name__ == '__main__'" in content:
                entry_points.append({
                    "file": str(py_file),
                    "type": "cli_script",
                    "description": "CLI script with main entry point"
                })
        except:
            pass

    # Docker CMD/ENTRYPOINT
    for dockerfile in root.rglob("Dockerfile*"):
        try:
            content = dockerfile.read_text()
            for line in content.split('\n'):
                if line.strip().startswith('CMD') or line.strip().startswith('ENTRYPOINT'):
                    entry_points.append({
                        "file": str(dockerfile),
                        "type": "docker_entry",
                        "description": f"Docker entry point: {line.strip()}"
                    })
        except:
            pass

    # Test files
    for test_file in root.rglob("test_*.py"):
        entry_points.append({
            "file": str(test_file),
            "type": "test",
            "description": "Test file"
        })

    return entry_points

def analyze_imports(file_path):
    """Analyze imports in a Python file"""
    imports = []
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except:
        pass

    return imports

def generate_reachability_map():
    """Generate complete reachability analysis"""

    print("Finding entry points...")
    entry_points = find_entry_points()

    print(f"Found {len(entry_points)} entry points")

    # Group by type
    by_type = defaultdict(list)
    for ep in entry_points:
        by_type[ep['type']].append(ep)

    # Analyze imports from entry points
    reachable_modules = set()
    for ep in entry_points:
        if ep['file'].endswith('.py'):
            imports = analyze_imports(ep['file'])
            reachable_modules.update(imports)

    report = {
        "generated_at": datetime.now().isoformat(),
        "entry_points": {
            "total": len(entry_points),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "details": entry_points
        },
        "reachable_modules": sorted(list(reachable_modules)),
        "analysis": {
            "fastapi_apps": [ep for ep in entry_points if ep['type'] == 'fastapi_app'],
            "cli_scripts": [ep for ep in entry_points if ep['type'] == 'cli_script'],
            "docker_entries": [ep for ep in entry_points if ep['type'] == 'docker_entry'],
            "tests": [ep for ep in entry_points if ep['type'] == 'test']
        }
    }

    # Write JSON report
    pathlib.Path('docs/reachability/reachability-analysis.json').write_text(
        json.dumps(report, indent=2)
    )

    # Write Markdown report
    md_lines = [
        "# Reachable Code Paths",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Summary",
        "",
        f"- **Total Entry Points:** {report['entry_points']['total']}",
        f"- **Reachable Modules:** {len(report['reachable_modules'])}",
        "",
        "## Entry Points by Type",
        ""
    ]

    for ep_type, count in report['entry_points']['by_type'].items():
        md_lines.append(f"### {ep_type.replace('_', ' ').title()} ({count})")
        md_lines.append("")
        for ep in by_type[ep_type]:
            md_lines.append(f"- `{ep['file']}` - {ep['description']}")
        md_lines.append("")

    md_lines.extend([
        "## Reachable Modules",
        "",
        "The following modules are directly imported by entry points:",
        ""
    ])

    for module in sorted(reachable_modules)[:50]:  # Top 50
        md_lines.append(f"- {module}")

    if len(reachable_modules) > 50:
        md_lines.append(f"\n... and {len(reachable_modules) - 50} more")

    md_lines.extend([
        "",
        "## Analysis Notes",
        "",
        "### Static Analysis",
        "- Entry points identified through code scanning",
        "- Import graph generated from AST parsing",
        "- Docker CMD/ENTRYPOINT tracked",
        "",
        "### Recommended Actions",
        "1. Review unreferenced files for potential removal",
        "2. Consolidate duplicate entry points",
        "3. Document all service entry points",
        "4. Add test coverage for untested modules",
        ""
    ])

    pathlib.Path('docs/reachability/Reachable-Code-Paths.md').write_text('\n'.join(md_lines))

    print(f"\n=== Reachability Analysis Complete ===")
    print(f"Entry points found: {len(entry_points)}")
    print(f"Reachable modules: {len(reachable_modules)}")
    print(f"\nReports generated:")
    print(f"  - docs/reachability/reachability-analysis.json")
    print(f"  - docs/reachability/Reachable-Code-Paths.md")

    return report

if __name__ == '__main__':
    generate_reachability_map()
