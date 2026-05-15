import pytest
from src.utils.markdown_parser import extract_references


def test_single_reference():
    assert extract_references("See [[My Doc]] here.") == ["My Doc"]


def test_multiple_references():
    assert extract_references("See [[Doc A]] and [[Doc B]].") == ["Doc A", "Doc B"]


def test_no_references():
    assert extract_references("Plain text without refs.") == []


def test_reference_in_heading():
    assert extract_references("# Title with [[Ref]]") == ["Ref"]


def test_reference_across_lines():
    md = "First [[Doc One]]\nSecond [[Doc Two]]"
    assert extract_references(md) == ["Doc One", "Doc Two"]


def test_incomplete_ref_not_matched():
    assert extract_references("Incomplete [[ref") == []


def test_single_bracket_not_matched():
    assert extract_references("[single bracket]") == []


def test_empty_string():
    assert extract_references("") == []


def test_reference_with_spaces():
    assert extract_references("See [[My Long Document Name]].") == ["My Long Document Name"]


def test_duplicate_references():
    refs = extract_references("[[Doc A]] and [[Doc A]] again.")
    assert refs == ["Doc A", "Doc A"]


def test_reference_only():
    assert extract_references("[[Solo]]") == ["Solo"]


def test_reference_adjacent_to_markdown():
    refs = extract_references("**bold** and [[Doc A]] with `code`.")
    assert refs == ["Doc A"]
