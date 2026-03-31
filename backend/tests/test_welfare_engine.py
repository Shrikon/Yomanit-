# tests/test_welfare_engine.py – Unit Tests
# מריץ: cd C:\yomanit\backend && python -m pytest tests/ -v

import pytest
from decimal import Decimal
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from validation.validator import (
    validate_structure, validate_balanced, find_missing,
    validate_all, ValidationError
)
from parsers.welfare import apply_welfare_splits


# ─────────────────────────────────────────────
# VALIDATOR TESTS
# ─────────────────────────────────────────────

class TestValidateStructure:
    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="ריק"):
            validate_structure([])

    def test_missing_semel_raises(self):
        with pytest.raises(ValidationError, match="semel"):
            validate_structure([{"amount": 100}])

    def test_valid_passes(self):
        validate_structure([{"semel": "123", "amount": 100}])


class TestValidateBalanced:
    def test_balanced_passes(self):
        lines = [
            {"side": "debit",  "amount": 1000},
            {"side": "credit", "amount": 1000},
        ]
        validate_balanced(lines)

    def test_unbalanced_raises(self):
        lines = [
            {"side": "debit",  "amount": 1000},
            {"side": "credit", "amount": 900},
        ]
        with pytest.raises(ValidationError, match="מאוזן"):
            validate_balanced(lines)

    def test_tolerance_passes(self):
        lines = [
            {"side": "debit",  "amount": "1000.005"},
            {"side": "credit", "amount": "1000.000"},
        ]
        validate_balanced(lines)


class TestFindMissing:
    def test_finds_missing(self):
        rows  = [{"semel": "A"}, {"semel": "B"}, {"semel": "C"}]
        index = {"A": {}, "B": {}}
        missing = find_missing(rows, index)
        assert len(missing) == 1
        assert missing[0]["semel"] == "C"

    def test_none_missing(self):
        rows  = [{"semel": "A"}, {"semel": "B"}]
        index = {"A": {}, "B": {}}
        assert find_missing(rows, index) == []


# ─────────────────────────────────────────────
# INDEX CACHE TESTS
# ─────────────────────────────────────────────

class TestIndexCache:
    def test_import(self):
        from index_cache import get_index, invalidate, clear_all
        assert callable(get_index)

    def test_clear_all(self):
        from index_cache import _cache, clear_all
        _cache[("a", "b")] = {"test": 1}
        clear_all()
        assert len(_cache) == 0

    def test_invalidate(self):
        from index_cache import _cache, invalidate
        _cache[("muni1", "tmpl1")] = {"test": 1}
        invalidate("muni1", "tmpl1")
        assert ("muni1", "tmpl1") not in _cache


# ─────────────────────────────────────────────
# APPLY_WELFARE_SPLITS TESTS
# ─────────────────────────────────────────────

def make_parsed(rows, summary_mishrad=0, summary_choz=0):
    return {
        "rows": rows,
        "summary_mishrad": summary_mishrad,
        "summary_choz": summary_choz,
        "municipality": "test",
        "period": "2026-01",
        "month": 1,
        "total_debit": summary_mishrad,
        "total_credit": 0,
        "missing_index": [],
    }


def base_row(semel, mishrad, zikuy, debit_acct="1001", credit_acct="2001"):
    return {
        "semel": semel,
        "name": f"test {semel}",
        "debit_total": Decimal(str(mishrad)),
        "zikuy_hodesh": Decimal(str(zikuy)),
        "has_ממשלה": mishrad != 0,
        "in_index": True,
        "debit_account": debit_acct,
        "credit_account": credit_acct,
    }


class TestApplyWelfareSplits:
    def test_positive_mishrad_creates_debit(self):
        row = base_row("A", mishrad=1000, zikuy=0)
        matched, _ = apply_welfare_splits(make_parsed([row], summary_mishrad=1000))
        debits = [r for r in matched if r["side"] == "debit" and r["semel"] == "A"]
        assert len(debits) == 1
        assert debits[0]["amount"] == 1000.0

    def test_positive_zikuy_creates_credit(self):
        row = base_row("A", mishrad=0, zikuy=500)
        matched, _ = apply_welfare_splits(make_parsed([row]))
        credits = [r for r in matched if r["side"] == "credit" and r["semel"] == "A"]
        assert len(credits) == 1
        assert credits[0]["amount"] == 500.0

    def test_negative_mishrad_creates_credit(self):
        row = base_row("A", mishrad=-200, zikuy=0)
        matched, _ = apply_welfare_splits(make_parsed([row]))
        credits = [r for r in matched if r["side"] == "credit" and r["semel"] == "A"]
        assert len(credits) == 1
        assert credits[0]["amount"] == 200.0

    def test_negative_zikuy_creates_debit(self):
        row = base_row("A", mishrad=0, zikuy=-100)
        matched, _ = apply_welfare_splits(make_parsed([row]))
        debits = [r for r in matched if r["side"] == "debit" and r["semel"] == "A"]
        assert len(debits) == 1
        assert debits[0]["amount"] == 100.0

    def test_choz_always_credit(self):
        parsed = make_parsed([], summary_mishrad=1000, summary_choz=352274)
        matched, _ = apply_welfare_splits(parsed)
        choz = [r for r in matched if r.get("semel") == "חוז"]
        assert len(choz) == 1
        assert choz[0]["side"] == "credit"
        assert choz[0]["amount"] == 352274.0

    def test_not_in_index_goes_to_missing(self):
        row = base_row("UNKNOWN", mishrad=500, zikuy=0)
        row["in_index"] = False
        matched, missing = apply_welfare_splits(make_parsed([row]))
        assert "UNKNOWN" not in [r["semel"] for r in matched]
        assert any(r["semel"] == "UNKNOWN" for r in missing)
