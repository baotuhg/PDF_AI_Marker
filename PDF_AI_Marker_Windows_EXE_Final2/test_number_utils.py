# -*- coding: utf-8 -*-
"""Golden test cho number_utils (tách khỏi layout_reconstructor) — chốt hành vi chuẩn hóa số VN/US."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from number_utils import is_number_cell, detect_number_style, parse_number
import layout_reconstructor as L   # xác minh re-export còn hoạt động


def test_is_number_cell():
    assert is_number_cell("1.525,81")
    assert is_number_cell("250 kg")
    assert not is_number_cell("Ghi chú")
    assert not is_number_cell("12 34")        # hai số cách nhau không phải 1 con số


def test_detect_style():
    assert detect_number_style(["1.525,81", "25,50"]) == "vn"
    assert detect_number_style(["1,525.81", "25.50"]) == "us"


def test_parse_vn_us():
    assert parse_number("1.525,81", "vn") == 1525.81
    assert parse_number("1.525", "vn") == 1525.0        # chấm phân nghìn VN
    assert parse_number("1,525.81", "us") == 1525.81
    assert parse_number("25,50", "vn") == 25.5
    assert parse_number("Ghi chú") is None


def test_reexport_tu_layout():
    """office_reader dùng 'from layout_reconstructor import parse_number' — re-export phải còn."""
    assert L.parse_number("1.525,81", "vn") == 1525.81
    assert L.detect_number_style(["25,50"]) == "vn"


def _run_standalone() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    p = fa = 0
    for n, f in tests:
        try:
            f(); print(f"  ✓ {n}"); p += 1
        except Exception as e:
            print(f"  ✗ {n}: {e}"); fa += 1
    print("-" * 56)
    print(f"KẾT QUẢ: {p} PASS / {fa} FAIL (tổng {p + fa})")
    return 1 if fa else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
