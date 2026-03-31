# tests/test_validator.py – 11 unit tests for validation layer
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from validation.validator import (
    validate_structure, validate_amounts, validate_balanced,
    find_missing, validate_all, ValidationError
)

def test_structure_empty():
    with pytest.raises(ValidationError, match="ריק"):
        validate_structure([])

def test_structure_missing_semel():
    with pytest.raises(ValidationError, match="semel"):
        validate_structure([{"semel": "", "amount": 100}])

def test_structure_valid():
    validate_structure([{"semel": "123", "amount": 100}])

def test_amounts_invalid():
    with pytest.raises(ValidationError, match="תקין"):
        validate_amounts([{"semel": "1", "amount": "abc"}])

def test_amounts_valid():
    validate_amounts([{"semel": "1", "amount": "1234.56"}])

def test_balanced_ok():
    lines = [{"side": "debit", "amount": "1000"}, {"side": "credit", "amount": "1000"}]
    validate_balanced(lines)

def test_balanced_fail():
    lines = [{"side": "debit", "amount": "1000"}, {"side": "credit", "amount": "999"}]
    with pytest.raises(ValidationError, match="לא מאוזנת"):
        validate_balanced(lines)

def test_find_missing():
    rows  = [{"semel": "A"}, {"semel": "B"}, {"semel": "C"}]
    index = {"A": {}, "C": {}}
    missing = find_missing(rows, index)
    assert len(missing) == 1 and missing[0]["semel"] == "B"

def test_find_missing_none():
    rows  = [{"semel": "A"}, {"semel": "B"}]
    index = {"A": {}, "B": {}}
    assert find_missing(rows, index) == []

def test_validate_all_valid():
    rows  = [{"semel": "X", "amount": "500"}]
    lines = [{"side": "debit", "amount": "500"}, {"side": "credit", "amount": "500"}]
    index = {"X": {}}
    result = validate_all(rows, lines, index)
    assert result["valid"] is True
    assert result["balanced"] is True
    assert result["missing"] == []

def test_validate_all_unbalanced():
    rows  = [{"semel": "X", "amount": "500"}]
    lines = [{"side": "debit", "amount": "500"}, {"side": "credit", "amount": "400"}]
    index = {"X": {}}
    result = validate_all(rows, lines, index)
    assert result["valid"] is False
    assert result["balanced"] is False
