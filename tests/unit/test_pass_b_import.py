"""Smoke tests for Pass B logical splitter module import."""

import importlib
import py_compile
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "src_common" / "pass_b_logical_splitter.py"


def test_pass_b_module_compiles(tmp_path):
    """The Pass B module should compile without syntax errors."""
    compiled_path = tmp_path / "pass_b.cpython-test.pyc"
    py_compile.compile(str(MODULE_PATH), cfile=str(compiled_path))
    module = importlib.import_module("src_common.pass_b_logical_splitter")
    assert hasattr(module, "LogicalSplitter"), "LogicalSplitter class missing"
