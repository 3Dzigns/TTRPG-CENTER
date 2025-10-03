import pytest

from src_common.pass_a_toc_parser import PassATocParser


def test_pass_a_parser_initializes_category_structures():
    parser = PassATocParser(job_id="job_test", env="dev")

    assert hasattr(parser, "_category_map"), "PassATocParser should always define _category_map"
    assert parser._category_map == {}, "_category_map should start empty"

    expected_assignments = {"organic": 0, "pattern": 0, "general": 0}
    assert parser._category_assignments == expected_assignments


def test_pass_a_parser_category_state_is_instance_local():
    first = PassATocParser(job_id="first", env="dev")
    second = PassATocParser(job_id="second", env="dev")

    second._category_map["classes"] = {"terms": ["Wizard"]}
    second._category_assignments["organic"] = 1

    assert first._category_map == {}, "Category map should not leak between instances"
    assert first._category_assignments["organic"] == 0
