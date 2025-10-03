#!/usr/bin/env bash
set -euo pipefail

# Repository Inventory Script
# Generates comprehensive manifest of all files in the repository

root="$(git rev-parse --show-toplevel)"
out="$root/docs/cleanup"
timestamp=$(date +%Y%m%d_%H%M%S)
log_file="$root/env/dev/logs/maintenance/inventory-$timestamp.log"

mkdir -p "$out"
mkdir -p "$(dirname "$log_file")"

echo "[$(date -Iseconds)] Starting repository inventory..." | tee -a "$log_file"

# Git index and untracked files
git ls-files --stage > "$out/git-index.txt"
git ls-files --others --exclude-standard > "$out/git-untracked.txt"

# Generate comprehensive inventory JSON
python3 - <<'PY'
import os
import json
import time
import pathlib
from datetime import datetime

root = pathlib.Path(".").resolve()
inv = []

# Language extensions mapping
lang_map = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.sh': 'shell',
    '.ps1': 'powershell',
    '.yml': 'yaml',
    '.yaml': 'yaml',
    '.json': 'json',
    '.md': 'markdown',
    '.html': 'html',
    '.css': 'css',
    '.sql': 'sql',
    '.txt': 'text'
}

# Allowed top-level directories (per coding standards)
allowed_top_level = {
    'env', 'scripts', 'src_common', 'services', 'tests', 'docs',
    'config', 'requirements', 'features', 'bugs', '.github',
    'artifacts', 'archives', 'web', 'templates', 'static', 'schemas',
    'certs', 'db_migrations', '.git', '.venv', '__pycache__',
    '.pytest_cache', '.benchmarks', '.claude', 'tools'
}

# Walk through all files
for p in root.rglob("*"):
    if p.is_file():
        try:
            rel_path = str(p.relative_to(root))
            suffix = p.suffix.lower()

            # Determine if file is at root level
            is_root_file = '/' not in rel_path and '\\' not in rel_path

            # Determine language
            language = lang_map.get(suffix, 'other')

            # Get git status
            git_status = 'unknown'
            # This would need git integration - simplified for now

            inv.append({
                "path": rel_path,
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
                "mtime_iso": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                "language": language,
                "extension": suffix,
                "is_root_file": is_root_file,
                "parent_dir": str(p.parent.relative_to(root)) if p.parent != root else "."
            })
        except Exception as e:
            print(f"Error processing {p}: {e}")

# Analyze root files
root_files = [f for f in inv if f['is_root_file']]
root_dirs = []

for item in root.iterdir():
    if item.is_dir():
        is_allowed = item.name in allowed_top_level
        root_dirs.append({
            "name": item.name,
            "allowed": is_allowed,
            "hidden": item.name.startswith('.')
        })

# Generate summary
summary = {
    "generated_at": datetime.now().isoformat(),
    "total_files": len(inv),
    "root_files": len(root_files),
    "root_directories": len(root_dirs),
    "disallowed_root_dirs": [d['name'] for d in root_dirs if not d['allowed']],
    "language_breakdown": {}
}

# Count by language
for item in inv:
    lang = item['language']
    summary['language_breakdown'][lang] = summary['language_breakdown'].get(lang, 0) + 1

# Write inventory
output = {
    "summary": summary,
    "root_files": sorted(root_files, key=lambda x: x['path']),
    "root_directories": sorted(root_dirs, key=lambda x: x['name']),
    "all_files": sorted(inv, key=lambda x: x['path'])
}

pathlib.Path("docs/cleanup/repo-inventory.json").write_text(
    json.dumps(output, indent=2)
)

# Write summary
print(f"\n=== Repository Inventory Summary ===")
print(f"Generated at: {summary['generated_at']}")
print(f"Total files: {summary['total_files']}")
print(f"Root-level files: {summary['root_files']}")
print(f"Root directories: {summary['root_directories']}")
print(f"\nDisallowed root directories: {summary['disallowed_root_dirs']}")
print(f"\nLanguage breakdown:")
for lang, count in sorted(summary['language_breakdown'].items(), key=lambda x: -x[1]):
    print(f"  {lang}: {count}")

PY

echo "[$(date -Iseconds)] Inventory complete. Generated docs/cleanup/repo-inventory.json" | tee -a "$log_file"
