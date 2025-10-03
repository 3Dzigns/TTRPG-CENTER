#!/usr/bin/env python
"""Tests for path linter"""

import pytest
import pathlib
from tools.path_lint import (
    check_top_level_dirs,
    check_root_files,
    check_test_organization,
    ALLOWED_TOP_LEVEL
)

def test_allowed_top_level_dirs(tmp_path):
    """Test that allowed directories don't trigger violations"""
    # Create allowed directories
    for dir_name in ['env', 'scripts', 'src_common', 'tests']:
        (tmp_path / dir_name).mkdir()

    violations = check_top_level_dirs(tmp_path)
    assert len(violations) == 0

def test_disallowed_top_level_dir(tmp_path):
    """Test that disallowed directories trigger violations"""
    (tmp_path / 'random_stuff').mkdir()

    violations = check_top_level_dirs(tmp_path)
    assert len(violations) == 1
    assert 'random_stuff' in violations[0].path

def test_root_test_files(tmp_path):
    """Test that root-level test files trigger violations"""
    (tmp_path / 'test_something.py').touch()

    violations = check_root_files(tmp_path)
    assert len(violations) > 0
    assert any('test_something.py' in v.path for v in violations)

def test_root_log_files(tmp_path):
    """Test that root-level log files trigger violations"""
    (tmp_path / 'app.log').touch()

    violations = check_root_files(tmp_path)
    assert len(violations) > 0
    assert any('app.log' in v.path for v in violations)

def test_proper_test_organization(tmp_path):
    """Test that tests in correct location don't trigger violations"""
    tests_dir = tmp_path / 'tests' / 'unit'
    tests_dir.mkdir(parents=True)
    (tests_dir / 'test_valid.py').touch()

    violations = check_test_organization(tmp_path)
    assert len(violations) == 0

def test_misplaced_test_files(tmp_path):
    """Test that tests outside tests/ trigger violations"""
    src_dir = tmp_path / 'src_common'
    src_dir.mkdir()
    (src_dir / 'test_misplaced.py').touch()

    violations = check_test_organization(tmp_path)
    assert len(violations) > 0
    assert any('test_misplaced.py' in v.path for v in violations)

def test_allowed_top_level_constants():
    """Test that ALLOWED_TOP_LEVEL contains expected directories"""
    required_dirs = {
        'env', 'scripts', 'src_common', 'services', 'tests',
        'docs', 'config', 'tools'
    }
    assert required_dirs.issubset(ALLOWED_TOP_LEVEL)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
