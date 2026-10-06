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
    parse_length_expr, _safe_eval_arith, _len_to_meters, _num_token, shape_segments,
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


# ── (Option B) SUY CHIỀU DÀI KHAI TRIỂN TỪ HÌNH DẠNG (giá trị SHX) ────────────
def test_shape_segments_loc_goc_va_duong_kinh():
    # '90' là góc uốn -> loại; '16' = đường kính -> loại; giữ các đoạn thật
    segs = shape_segments("16 1200 300 300 150 150 90", "vn", diameter=16)
    assert segs == [1200.0, 300.0, 300.0, 150.0, 150.0], segs


def test_khai_trien_tu_hinh_dang():
    """Thanh có chiều dài dạng biến (a+2b+2c) nhưng ô hình dạng có kích thước SHX
    -> suy chiều dài khai triển = tổng các đoạn, tính được trọng lượng, có cờ."""
    tbl = {
        "header": ["Ký hiệu", "Đường kính (mm)", "Hình dạng", "Chiều dài", "Số lượng", "Trọng lượng (kg)"],
        "rows": [["T1", "16", "1200 300 300 150 150 90", "a+2b+2c", "10", ""]],
        "number_style": "vn", "page": 5, "sheet": "KC-07",
    }
    res = AECTableAuditor.audit(tbl, CAT_REBAR)
    it = res["rebar_items"]
    assert len(it) == 1 and it[0]["length_kind"] == "from_shape", res["rebar_items"]
    assert it[0]["length_mm"] == 2100, it[0]        # 1200+300+300+150+150
    assert it[0]["shape_segments_mm"] == [1200, 300, 300, 150, 150]
    assert "khai_trien_tu_hinh" in {d["kind"] for d in res["warnings_detail"]}


def test_khong_suy_duoc_thi_bao_phuc_tap():
    """Chiều dài dạng biến và hình dạng KHÔNG đủ đoạn -> giữ cờ hình học phức tạp, không tính."""
    tbl = {
        "header": ["Ký hiệu", "Đường kính (mm)", "Hình dạng", "Chiều dài", "Số lượng", "Trọng lượng (kg)"],
        "rows": [["T9", "16", "90", "a+b", "4", ""]],
        "number_style": "vn", "page": 5, "sheet": "KC-07",
    }
    res = AECTableAuditor.audit(tbl, CAT_REBAR)
    assert res["rebar_items"] == [], res["rebar_items"]
    assert "hinh_hoc_phuc_tap" in {d["kind"] for d in res["warnings_detail"]}


# ── Trình chạy độc lập ────────────────────────────────────────────────────────
# ── (5) Hồi quy từ hồ sơ cầu thực tế: tiêu đề bị OCR đọc hỏng ─────────────────
# Trước đây 74 cảnh báo, ~85% là giả: lấy nhầm cột kg/m làm cột khối lượng, mất đơn vị
# vì '(oan)'/'()', đọc '7,900,00' thành 790000, và lấy cột kg/m làm đường kính (Φ1).
def _bridge_table(header, rows, style="vn"):
    return {"page": 1, "header": header, "rows": rows, "number_style": style}


def _mk(res):
    return [(d["mark"], d["kind"]) for d in res.get("warnings_detail", [])]


def test_tieu_de_mat_don_vi_khong_bao_lech_gia():
    """'Chiều dài (oan)' + 'Tổng chiều dài ()': đơn vị phải SUY từ tính nhất quán, không mặc định mm."""
    h = ["Ký hiệu", "Đường kính (mm)", "Chiều dài (oan)", "Trọng lượng (kg/m)",
         "Số lượng (thanh)", "Tổng chiều dài ()", "Tổng khối lượng (kg)"]
    rows = [["F1", "D25", "7262", "3,850", "30", "217,86", "838,76"],
            ["F1A", "D25", "8262", "3,850", "30", "247,86", "954,26"],
            ["F1B", "D25", "6025", "3,850", "30", "180,75", "695,89"],
            ["F2", "D25", "7262", "3,850", "30", "217,86", "838,76"]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    assert _mk(res) == [], _mk(res)


def test_cot_kg_tren_m_hong_tieu_de_khong_bi_lay_lam_khoi_luong():
    """'Trọng lượng (u/ay)' là cột kg/m bị OCR hỏng: nhận ra bằng DỮ LIỆU (≈ TCVN), lấy 'Tổng khối lượng'."""
    h = ["Ký hiệu", "Đường kính (mm)", "Chiều dài (nm)", "Trọng lượng (u/ay)",
         "Số lượng (thanh)", "Tổng chiều dài (m)", "Tổng khối lượng (kg)"]
    rows = [["W1", "D25", "8.467,00", "3,85", "27", "228,61", "880,14"],
            ["W1A", "D25", "9.467,00", "3,85", "26", "246,14", "947,65"],
            ["W2", "D20", "7.290,00", "2,47", "27", "196,83", "486,17"],
            ["W2A", "D20", "8.290,00", "2,47", "26", "215,54", "532,38"]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    assert _mk(res) == [], _mk(res)


def test_dau_phan_cach_ocr_doc_nguoc_duoc_sua():
    """'7,900,00' = 7.900,00 mm (OCR đọc dấu chấm nghìn thành phẩy). Phải ra 7900, không phải 790000."""
    from table_agent import parse_length_expr
    assert parse_length_expr("7,900,00", "vn") == (7900.0, "number")
    assert parse_length_expr("1,153,00", "vn") == (1153.0, "number")
    assert parse_length_expr("7.900,00", "vn") == (7900.0, "number")     # dạng đúng không đổi
    assert parse_length_expr("1,234,567", "vn")[0] == 1234567.0           # không có phần thập phân -> giữ nguyên
    h = ["Ký hiệu", "Đường kính (mm)", "Chiều dài (nm)", "Trọng lượng (u/ay)",
         "Số lượng (thanh)", "Tổng chiều dài (m)", "Tổng khối lượng (kg)"]
    rows = [["W1", "D25", "8.467,00", "3,85", "27", "228,61", "880,14"],
            ["W1A", "D25", "9.467,00", "3,85", "26", "246,14", "947,65"],
            ["W2", "D20", "7.290,00", "2,47", "27", "196,83", "486,17"],
            ["W3", "D20", "7,900,00", "2,47", "34", "268,60", "663,44"]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    assert _mk(res) == [], _mk(res)
    w3 = [i for i in res["rebar_items"] if i["mark"] == "W3"][0]
    assert w3["length_mm"] == 7900, w3          # file nạp optimizer phải đúng chiều dài


def test_loi_that_van_bi_bat():
    """Khối lượng ghi đúng NỬA tính toán (trang 21 hồ sơ cầu) và ô tổng dài = 0 phải VẪN được cờ."""
    h = ["Ký hiệu", "Đường kính (mm)", "Chiều dài (mm)", "Trọng lượng (kg/m)",
         "Số lượng (thanh)", "Tổng chiều dài (m)", "Tổng khối lượng (kg)"]
    rows = [["K1", "D22", "8.496", "2,980", "18", "152,93", "227,86"],       # ghi = ½ (456,3)
            ["K2", "D22", "4.200", "2,980", "18", "75,60", "225,29"],        # đúng
            ["K3", "D22", "5.512", "2,980", "17", "93,70", "279,24"],        # đúng
            ["A8", "D20", "1.000,00", "2,470", "7", "00", "17,29"]]          # ô tổng dài đọc thành 00
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    ks = _mk(res)
    assert ("K1", "lech_trong_luong") in ks, ks
    assert ("A8", "o_tong_dai_bang_0") in ks, ks
    assert ("K2", "lech_trong_luong") not in ks and ("K3", "lech_trong_luong") not in ks, ks


def test_tieu_de_gop_o_khong_tham_tra_sai():
    """Tiêu đề gộp ô làm cột đường kính trỏ sang cột kg/m (0,888): không được sinh 'Φ1' + lệch giả."""
    h = ["Bộ phận MẶT CẦU", "MẶT CẦU MỘT NHỊP", "(mm) MẶT CẦU", "Ký hiệu Đường kính KL đơn vị",
         "(mm) MẶT CẦU", "(Thanh) MẶT CẦU", "(Kg) MẶT CẦU"]
    rows = [["", "L3", "D12", "0,888", "15000", "20", "266,40"],
            ["Gờ lan", "L2", "D14", "1,208", "1920", "300", "695,81"],
            ["can", "L1", "D14", "1,208", "2180", "300", "790,03"],
            ["", "L3'", "D12", "0,888", "6000", "40", "213,12"]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    ks = [k for _, k in _mk(res)]
    assert "lech_trong_luong" not in ks and "duong_kinh_la" not in ks, _mk(res)
    assert "tieu_de_khong_tin_cay" in ks, _mk(res)      # trung thực: báo là không tự thẩm tra được


def test_o_khoi_luong_trong_va_tong_bang_so_theo_cap():
    """Số 482.08 trượt sang cột Ghi chú -> ô khối lượng trống: cờ riêng dòng đó, KHÔNG làm lệch cả bảng."""
    h = ["STT", "Tên thanh", "Đường kính (mm)", "Số lượng Thanh", "Chiều dài (mm)",
         "Trọng lượng Đơn vị (Kg/m)", "Trọng lượng Tổng (Kg)", "Ghi chú"]
    rows = [["1", "A1", "D32", "5", "15.280,00", "6,31", "", "482.08 Thép tròn"],
            ["2", "A2", "D12", "10", "14.500,00", "0,89", "128,76", "Thép tròn"],
            ["3", "A3", "D12", "18", "15.400,00", "0,89", "246,15", "Thép tròn"],
            ["4", "B1", "D32", "8", "17.320,00", "6,31", "874,31", "Thép tròn"]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    ks = _mk(res)
    assert ("A1", "o_khoi_luong_trong") in ks, ks
    assert all(k != "lech_tong_bang" for _, k in ks), ks


def test_chu_thich_duong_kinh_khong_phai_hinh_hoc_phuc_tap():
    """'D12', 'D>18', '10<D<18' trong cột chiều dài là chú giải, không phải thanh uốn cần khai triển."""
    h = ["STT", "Đường kính (mm)", "Chiều dài (mm)", "Số lượng", "Trọng lượng (kg)"]
    rows = [["1", "D12", "D12", "", ""], ["2", "D14", "D>18", "", ""],
            ["3", "D16", "10<D<18", "", ""], ["4", "D18", "D<10mm", "", ""]]
    res = AECTableAuditor.audit(_bridge_table(h, rows), CAT_REBAR)
    assert not [d for d in res.get("warnings_detail", []) if d["kind"] == "hinh_hoc_phuc_tap"], _mk(res)


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
