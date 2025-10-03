#!/usr/bin/env python
"""Path Policy Linter - Validates repository file organization"""

import sys
import pathlib
import argparse
from typing import List, Tuple

# Allowed top-level directories
ALLOWED_TOP_LEVEL = {
    'env', 'scripts', 'src_common', 'services', 'tests', 'docs',
    'config', 'requirements', 'features', 'bugs', '.github',
    'artifacts', 'archives', 'web', 'templates', 'static', 'schemas',
    'certs', 'db_migrations', '.git', '.venv', '__pycache__',
    '.pytest_cache', '.benchmarks', '.claude', 'tools', 'ci',
    'claudedocs', 'MVP-Version-2', 'audit', 'test_fixtures',
    'quarantine'
}

# File type to directory mapping
FILE_RULES = {
    'test_*.py': 'tests/unit',
    '*_test.py': 'tests/unit',
    '*.test.js': 'tests/unit',
    '*.test.ts': 'tests/unit',
    '*.log': 'env/*/logs',
    '*.pdf': 'env/*/uploads or quarantine',
    '*.db': 'env/*/data',
    '*analysis*.md': 'docs/analysis',
    '*roadmap*.md': 'docs/planning',
    'BUG-*.md': 'docs/bugs',
    'FR-*.md': 'docs/features',
}

class PathViolation:
    def __init__(self, path: str, rule: str, suggestion: str):
        self.path = path
        self.rule = rule
        self.suggestion = suggestion

    def __str__(self):
        return f"❌ {self.path}\n   Rule: {self.rule}\n   Suggestion: {self.suggestion}"

def check_top_level_dirs(root: pathlib.Path) -> List[PathViolation]:
    """Check for disallowed top-level directories"""
    violations = []

    for item in root.iterdir():
        if item.is_dir() and item.name not in ALLOWED_TOP_LEVEL:
            violations.append(PathViolation(
                str(item),
                "Disallowed top-level directory",
                f"Move to quarantine/{item.name} or appropriate subdirectory"
            ))

    return violations

def check_root_files(root: pathlib.Path) -> List[PathViolation]:
    """Check for misplaced root files"""
    violations = []

    # Files that should never be in root
    prohibited_patterns = {
        'test_*.py': 'tests/unit/',
        '*_test.py': 'tests/unit/',
        '*.log': 'env/dev/logs/',
        '*.pdf': 'quarantine/ or env/dev/uploads/',
        '*.db': 'env/dev/data/',
        'patch_*.py': 'quarantine/ (deprecated)',
        'temp*.html': 'quarantine/',
        'TEMP_*': 'quarantine/',
    }

    for pattern, dest in prohibited_patterns.items():
        for file in root.glob(pattern):
            if file.parent == root:
                violations.append(PathViolation(
                    str(file),
                    f"Root-level {pattern} file not allowed",
                    f"Move to {dest}"
                ))

    return violations

def check_test_organization(root: pathlib.Path) -> List[PathViolation]:
    """Check test file organization"""
    violations = []

    # Find test files outside tests/ directory
    for test_file in root.rglob('test_*.py'):
        if not str(test_file).startswith(str(root / 'tests')):
            violations.append(PathViolation(
                str(test_file),
                "Test file outside tests/ directory",
                f"Move to tests/unit/ or tests/functional/"
            ))

    return violations

def check_env_isolation(root: pathlib.Path) -> List[PathViolation]:
    """Check environment isolation rules"""
    violations = []

    # Check for cross-environment references in Python files
    for py_file in root.rglob('*.py'):
        if '.git' in py_file.parts or '.venv' in py_file.parts:
            continue

        try:
            content = py_file.read_text()

            # Check for hardcoded environment paths
            for env in ['dev', 'test', 'prod']:
                if f'env/{env}/' in content or f'env\\{env}\\' in content:
                    # Check if file is allowed to access this environment
                    file_env = None
                    if 'env' in py_file.parts:
                        env_idx = py_file.parts.index('env')
                        if env_idx + 1 < len(py_file.parts):
                            file_env = py_file.parts[env_idx + 1]

                    if file_env and file_env != env:
                        violations.append(PathViolation(
                            str(py_file),
                            f"Cross-environment reference: {file_env} → {env}",
                            f"Use environment variables or config for env-specific paths"
                        ))
        except:
            pass

    return violations

def check_artifact_placement(root: pathlib.Path) -> List[PathViolation]:
    """Check artifact file placement"""
    violations = []

    # Artifacts should be under env/<env>/artifacts/ or artifacts/
    for manifest in root.rglob('manifest.json'):
        if '.git' in manifest.parts:
            continue

        path_str = str(manifest)
        if 'artifacts' in manifest.parts:
            # Check if properly organized
            idx = manifest.parts.index('artifacts')
            if idx + 1 < len(manifest.parts):
                # Should have env subdirectory
                if manifest.parts[idx + 1] not in ['dev', 'test', 'prod']:
                    violations.append(PathViolation(
                        path_str,
                        "Artifact not organized by environment",
                        "Move to artifacts/<env>/<job_id>/"
                    ))

    return violations

def run_lint(root: pathlib.Path, fix: bool = False) -> Tuple[int, List[PathViolation]]:
    """Run all lint checks"""
    all_violations = []

    print("🔍 Running path policy checks...\n")

    # Run all checks
    checks = [
        ("Top-level directories", check_top_level_dirs),
        ("Root files", check_root_files),
        ("Test organization", check_test_organization),
        ("Environment isolation", check_env_isolation),
        ("Artifact placement", check_artifact_placement),
    ]

    for check_name, check_func in checks:
        print(f"Checking {check_name}...")
        violations = check_func(root)
        all_violations.extend(violations)

        if violations:
            print(f"  ❌ Found {len(violations)} violation(s)")
        else:
            print(f"  ✅ Passed")

    return len(all_violations), all_violations

def main():
    parser = argparse.ArgumentParser(description='Path policy linter')
    parser.add_argument('--fix', action='store_true', help='Auto-fix violations where safe')
    parser.add_argument('--root', default='.', help='Repository root path')
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()

    violation_count, violations = run_lint(root, args.fix)

    if violations:
        print(f"\n{'='*60}")
        print(f"❌ Found {violation_count} violation(s):\n")
        for v in violations:
            print(v)
            print()

        if args.fix:
            print("Note: Auto-fix not yet implemented. Please fix violations manually.")

        sys.exit(1)
    else:
        print(f"\n{'='*60}")
        print("✅ All path policy checks passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()
