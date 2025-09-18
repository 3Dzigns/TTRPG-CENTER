import os
import subprocess
import sys
from pathlib import Path


def test_pytest_collect_only_ok():
    repo_root = Path(__file__).resolve().parents[2]
    cmd = [sys.executable, "-m", "pytest", "tests/unit/test_llm_mode.py", "--collect-only", "-q"]
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = subprocess.run(cmd, cwd=repo_root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
