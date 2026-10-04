# -*- coding: utf-8 -*-
"""
Golden test cho THẨM TRA SỐ LIỆU bảng thống kê cốt thép (table_agent).

Khóa các cải tiến cho cấu kiện hình học phức tạp:
  (1) Parser chiều dài dạng công thức tổ hợp đoạn (thanh uốn): '1200+2*300+2*150' -> 2100.
  (2) Truyền ô ĐƯỜNG KÍNH gộp theo hàng (không loại thầm dòng trống đường kính).
  (3) Đổi đơn vị theo TIÊU ĐỀ cột (mm/cm/m), không đoán theo độ lớn.
  (4) Audit mở rộng: cờ lệch trọng lượng / tổng bảng / đường kính lạ / hình học phức tạp.

Chạy:  engine\\python.exe test_table_agent.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from table_agent import (
    AECTableAuditor, CAT_REBAR,
    parse_length_expr, _safe_eval_arith, _len_to_meters, _num_token,
)


# ── (1) Parser chiều dài ──────────────────────────────────────────────────────
def test_parse_cong_thuc_thanh_uon():
    assert parse_length_expr("1200+2*300+2*150", "vn") == (2100.0, "formula")
    assert parse_length_expr("2x300", "vn") == (600.0, "formula")          # 'x' = nhân
    assert parse_length_expr("(1200+300)*2", "vn") == (3000.0, "formula")


def test_parse_so_don_va_don_vi_vn():
    assert parse_length_expr("2000", "vn") == (2000.0, "number")
    assert parse_length_expr("1.525", "vn") == (1525.0, "number")          # chấm phân nghìn VN
    assert parse_length_expr("2,5", "vn") == (2.5, "number")               # phẩy thập phân VN


def test_parse_cong_thuc_co_bien_la_symbolic():
    """Chiều dài còn biến (a+2b) -> không tính được -> 'symbolic' (cần hình dạng)."""
    assert parse_length_expr("a+2b", "vn") == (None, "symbolic")
    assert parse_length_expr("L=2a+b", "vn") == (None, "symbolic")


def test_safe_eval_khong_dung_eval():
    assert _safe_eval_arith("1200+2*300", "vn") == 1800.0
    assert _safe_eval_arith("badtext", "vn") is None


def test_doi_don_vi_theo_header():
    assert _len_to_meters(2100, "mm") == 2.1
    assert _len_to_meters(250, "cm") == 2.5
    assert _len_to_meters(3, "m") == 3.0
    assert _len_to_meters(2500, None) == 2.5      # dự phòng: >100 coi là mm
    assert _len_to_meters(2.5, None) == 2.5


# ── Dựng bảng thép mẫu giống đầu ra make_table ────────────────────────────────
def _rebar_table():
    return {
        "header": ["Ký hiệu", "Đường kính (mm)", "Chiều dài (mm)", "Số lượng", "Trọng lượng (kg)"],
        "rows": [
            ["T1", "16", "1200+2*300+2*150", "10", "33.1"],   # thanh uốn: công thức đúng -> không cờ
            ["T2", "",   "2000",             "5",  "15.78"],   # đường kính GỘP (trống) -> truyền 16
            ["T3", "20", "3000",             "4",  "50.0"],    # lệch trọng lượng -> cờ
            ["T4", "10", "a+2b",             "8",  ""],         # hình học phức tạp -> cờ, không tính
            ["T5", "17", "1000",             "2",  ""],         # đường kính ngoài TCVN -> cờ
        ],
        "number_style": "vn",
        "page": 7,
        "sheet": "KC-05",
    }


def _audit():
    return AECTableAuditor.audit(_rebar_table(), CAT_REBAR)


def _kinds(res):
    return {d["kind"] for d in res.get("warnings_detail", [])}


# ── (1) thanh uốn tính đúng, KHÔNG báo lệch sai ───────────────────────────────
def test_thanh_uon_tinh_dung_khong_bao_lech():
    res = _audit()
    t1 = [d for d in res["warnings_detail"] if d["mark"] == "T1" and d["kind"] == "lech_trong_luong"]
    assert t1 == [], ("T1 bị báo lệch sai", res["warnings_detail"])


# ── (2) đường kính gộp theo hàng: T2 không bị loại, lấy Φ16 ────────────────────
def test_truyen_duong_kinh_gop_hang():
    res = _audit()
    t2 = [it for it in res["rebar_items"] if it["mark"] == "T2"]
    assert t2 and t2[0]["diameter"] == 16, res["rebar_items"]


# ── (4) các cờ audit xuất hiện đúng loại ──────────────────────────────────────
def test_co_canh_bao_dung_loai():
    res = _audit()
    k = _kinds(res)
    assert "lech_trong_luong" in k      # T3
    assert "hinh_hoc_phuc_tap" in k     # T4 (chiều dài a+2b)
    assert "duong_kinh_la" in k         # T5 (Φ17)
    assert res["status"] == "warning"


# ── chiều dài 'symbolic' KHÔNG được tính vào thép ─────────────────────────────
def test_symbolic_khong_tinh_trong_luong():
    res = _audit()
    assert all(it["mark"] != "T4" for it in res["rebar_items"]), res["rebar_items"]
    # 4 dòng tính được (T1,T2,T3,T5), T4 bị loại khỏi tính toán
    assert res["rebar_summary"]["total_bars"] == 4, res["rebar_summary"]
    assert res["rebar_summary"]["length_unit"] == "mm"


# ── cảnh báo mang theo trang/bản vẽ để đối chiếu ──────────────────────────────
def test_canh_bao_co_trang_ban_ve():
    res = _audit()
    for d in res["warnings_detail"]:
        assert d["page"] == 7 and d["sheet"] == "KC-05"


# ── Trình chạy độc lập ────────────────────────────────────────────────────────
def _run_standalone() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}\n      AssertionError: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print("-" * 60)
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL (tổng {passed + failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
