# Repository Inventory Script (PowerShell)
# Generates comprehensive manifest of all files in the repository

$ErrorActionPreference = "Stop"

$root = git rev-parse --show-toplevel
$out = Join-Path $root "docs\cleanup"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $root "env\dev\logs\maintenance\inventory-$timestamp.log"

New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $logFile) | Out-Null

"[$(Get-Date -Format 'o')] Starting repository inventory..." | Tee-Object -FilePath $logFile -Append

# Git index and untracked files
git ls-files --stage | Out-File -FilePath (Join-Path $out "git-index.txt") -Encoding utf8
git ls-files --others --exclude-standard | Out-File -FilePath (Join-Path $out "git-untracked.txt") -Encoding utf8

# Generate comprehensive inventory using Python
python -c @"
import os
import json
import time
import pathlib
from datetime import datetime

root = pathlib.Path('.').resolve()
inv = []

lang_map = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
    '.tsx': 'typescript', '.sh': 'shell', '.ps1': 'powershell',
    '.yml': 'yaml', '.yaml': 'yaml', '.json': 'json',
    '.md': 'markdown', '.html': 'html', '.css': 'css',
    '.sql': 'sql', '.txt': 'text'
}

allowed_top_level = {
    'env', 'scripts', 'src_common', 'services', 'tests', 'docs',
    'config', 'requirements', 'features', 'bugs', '.github',
    'artifacts', 'archives', 'web', 'templates', 'static', 'schemas',
    'certs', 'db_migrations', '.git', '.venv', '__pycache__',
    '.pytest_cache', '.benchmarks', '.claude', 'tools'
}

for p in root.rglob('*'):
    if p.is_file():
        try:
            rel_path = str(p.relative_to(root))
            suffix = p.suffix.lower()
            is_root_file = '/' not in rel_path and '\\\\' not in rel_path
            language = lang_map.get(suffix, 'other')

            inv.append({
                'path': rel_path,
                'size': p.stat().st_size,
                'mtime': p.stat().st_mtime,
                'mtime_iso': datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                'language': language,
                'extension': suffix,
                'is_root_file': is_root_file,
                'parent_dir': str(p.parent.relative_to(root)) if p.parent != root else '.'
            })
        except Exception as e:
            print(f'Error processing {p}: {e}')

root_files = [f for f in inv if f['is_root_file']]
root_dirs = []

for item in root.iterdir():
    if item.is_dir():
        is_allowed = item.name in allowed_top_level
        root_dirs.append({
            'name': item.name,
            'allowed': is_allowed,
            'hidden': item.name.startswith('.')
        })

summary = {
    'generated_at': datetime.now().isoformat(),
    'total_files': len(inv),
    'root_files': len(root_files),
    'root_directories': len(root_dirs),
    'disallowed_root_dirs': [d['name'] for d in root_dirs if not d['allowed']],
    'language_breakdown': {}
}

for item in inv:
    lang = item['language']
    summary['language_breakdown'][lang] = summary['language_breakdown'].get(lang, 0) + 1

output = {
    'summary': summary,
    'root_files': sorted(root_files, key=lambda x: x['path']),
    'root_directories': sorted(root_dirs, key=lambda x: x['name']),
    'all_files': sorted(inv, key=lambda x: x['path'])
}

pathlib.Path('docs/cleanup/repo-inventory.json').write_text(
    json.dumps(output, indent=2)
)

print(f'\\n=== Repository Inventory Summary ===')
print(f'Generated at: {summary['generated_at']}')
print(f'Total files: {summary['total_files']}')
print(f'Root-level files: {summary['root_files']}')
print(f'Root directories: {summary['root_directories']}')
print(f'\\nDisallowed root directories: {summary['disallowed_root_dirs']}')
print(f'\\nLanguage breakdown:')
for lang, count in sorted(summary['language_breakdown'].items(), key=lambda x: -x[1]):
    print(f'  {lang}: {count}')
"@

"[$(Get-Date -Format 'o')] Inventory complete. Generated docs/cleanup/repo-inventory.json" | Tee-Object -FilePath $logFile -Append
