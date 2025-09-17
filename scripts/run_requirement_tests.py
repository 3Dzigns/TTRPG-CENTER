import sys
from pathlib import Path
import importlib.util
import traceback

repo_root = Path(__file__).resolve().parents[1]
module_path = repo_root / 'tests' / 'functional' / 'test_requirement_compliance.py'

spec = importlib.util.spec_from_file_location('test_requirement_compliance', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

failures = []
for name in dir(module):
    if name.startswith('test_'):
        func = getattr(module, name)
        try:
            func()
            print(f"PASS: {name}")
        except Exception as exc:
            print(f"FAIL: {name} -> {exc}")
            traceback.print_exc()
            failures.append(name)

print('\nSummary:')
print(f"Failed {len(failures)} tests: {failures}")
