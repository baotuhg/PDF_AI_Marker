# -*- coding: utf-8 -*-
"""
Bộ kiểm thử (golden test) cho engine khôi phục dấu tiếng Việt AEC — vn_diacritics.

Mục tiêu chính: CHỐT hành vi an toàn của lớp ngữ cảnh (Bước 3) sau khi sửa lỗi
sai dấu đồng âm. Hai nhóm đối lập:

  (A) CHỐNG SAI DẤU (anti-corruption): các từ đồng âm không dấu & nhãn IN HOA
      KHÔNG được bị gán dấu bừa (vd 'đá dăm' KHÔNG biến thành 'đã dầm',
      'VA' KHÔNG biến thành 'VÀ', 'mo da'(mỏ đá) KHÔNG thành 'mố đã').

  (B) PHỤC HỒI ĐÚNG (positive): các cụm có ngữ cảnh chắc chắn VẪN được gán dấu
      (vd 'coc C1'→'cọc C1', 'da hoan thanh'→'đã hoàn thành', số liệu giữ nguyên).

Chạy độc lập (không cần pytest):
    engine\\python.exe test_vn_diacritics.py
Hoặc qua pytest:
    engine\\python.exe -m pytest test_vn_diacritics.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vn_diacritics import restore_vietnamese_diacritics as R, _is_caps_label, VietnameseDiacriticRestorer


# ─────────────────────────────────────────────────────────────────────────────
# (A) CHỐNG SAI DẤU ĐỒNG ÂM & BẢO VỆ NHÃN IN HOA (regression guards)
# ─────────────────────────────────────────────────────────────────────────────
def test_da_dam_khong_thanh_da_dam_sai():
    """'đá dăm' (vật liệu) không được biến thành 'đã dầm'."""
    out = R("da dam loai 1")
    assert "đá dăm" in out, out
    assert "đã dầm" not in out, out


def test_da_kich_thuoc_cot_lieu_giu_nghia_da():
    """'đá 1x2' (cốt liệu) không bị biến 'đá' → 'đã'."""
    out = R("lop be tong da 1x2")
    assert "đá 1x2" in out, out
    assert "đã" not in out, out


def test_mo_da_la_mo_da_khong_phai_mo_da():
    """'mo da' = 'mỏ đá' — không được gán dấu thành 'mố đã'/'mố đá'."""
    out = R("mo da xay dung")
    assert "mố đã" not in out, out
    assert "đã" not in out, out


def test_nhan_in_hoa_khong_bi_gan_dau():
    """Nhãn/ký hiệu IN HOA trên bản vẽ (VA, GA...) phải giữ nguyên, không thành 'VÀ'."""
    out = R("VA GA THU NUOC")
    assert "VÀ" not in out, out
    assert out.startswith("VA "), out


def test_cach_xa_khong_thanh_xa():
    """'cách xa 5m' không bị biến 'xa' → 'xã' (địa danh chỉ gán dấu trước tên riêng viết hoa)."""
    out = R("cach xa 5m")
    assert "xã" not in out, out


def test_ma_hieu_giu_nguyen_hoa_thuong():
    """'coc C1' → 'cọc C1' — KHÔNG hạ mã hiệu thành 'cọc c1' (lỗi match_case cũ)."""
    assert R("coc C1") == "cọc C1", R("coc C1")
    assert R("dam T2") == "dầm T2", R("dam T2")
    assert R("thep D16") == "thép D16", R("thep D16")


def test_so_lieu_do_dac_bao_toan_100_phan_tram():
    """Số đo & mã kỹ thuật phải nguyên vẹn tuyệt đối."""
    assert "1.525,81" in R("Kich thuoc 1.525,81 m")
    assert "D1000" in R("coc khoan nhoi D1000")
    assert "63.36" in R("cao do 63.36")


def test_mac_khong_an_vao_mac_dinh():
    """'mác' chỉ gán khi theo sau là mã/chữ số, không đụng 'mặc định' (mac dinh)."""
    out = R("thong so mac dinh")
    assert "mác dinh" not in out, out


def test_thi_cong_khong_thanh_thi_cong_sai():
    """'thi công' không được biến thành 'thì công' (đồng âm 'thi'↔'thì')."""
    assert "thì công" not in R("bien phap thi cong"), R("bien phap thi cong")
    assert R("da thi cong") == "đã thi công", R("da thi cong")


def test_mau_den_khong_thanh_mau_den_sai():
    """'màu đen' không được biến thành 'màu đến' (đồng âm 'den'↔'đen'/'đến')."""
    assert "đến" not in R("son mau den"), R("son mau den")


def test_cua_khong_thanh_cua_sai():
    """'cửa' không được biến thành 'của' (đồng âm 'cua'↔'cửa'/'của')."""
    assert "của sổ" not in R("cua so lua"), R("cua so lua")
    assert "của đi" not in R("cua di nhom kinh"), R("cua di nhom kinh")


# ─────────────────────────────────────────────────────────────────────────────
# (B) PHỤC HỒI ĐÚNG KHI NGỮ CẢNH CHẮC CHẮN (positive functionality)
# ─────────────────────────────────────────────────────────────────────────────
def test_gan_dau_cau_kien_khi_co_ma_hieu():
    assert R("mo M1") == "mố M1"
    assert R("bang 3") == "bảng 3"


def test_da_dong_tu_duoc_phuc_hoi():
    """'đã + động từ' (ngữ cảnh an toàn) vẫn được phục hồi."""
    assert R("da hoan thanh 50%") == "đã hoàn thành 50%"
    assert R("da duoc nghiem thu").startswith("đã được")
    assert R("da thi cong").startswith("đã thi công")


def test_so_luong_neo_theo_chu_so():
    assert "2 lớp" in R("be tong 2 lop")
    assert "mác 250" in R("mac 250")
    assert "mác M300" in R("mac M300")


def test_cum_tu_ghep_van_hoat_dong():
    """Lớp cụm từ ghép (Bước 2) không bị ảnh hưởng bởi thay đổi lớp ngữ cảnh."""
    assert R("chu dau tu") == "chủ đầu tư"
    assert "dự án đầu tư xây dựng" in R("ban quan ly du an dau tu xay dung")


def test_tieu_de_in_hoa_van_duoc_phuc_hoi_qua_cum_tu():
    """Tiêu đề IN HOA là cụm từ ghép vẫn được gán dấu (khác với nhãn lẻ in hoa)."""
    assert R("CHU DAU TU") == "CHỦ ĐẦU TƯ"


def test_hu_tu_chu_thuong_duoc_phuc_hoi():
    out = R("vat lieu la da dam")
    assert "là" in out, out
    assert "đá dăm" in out, out


# ─────────────────────────────────────────────────────────────────────────────
# (C) HÀM PHỤ TRỢ
# ─────────────────────────────────────────────────────────────────────────────
def test_sua_loi_ocr_nguoi_dung_literal():
    """Sửa lỗi OCR người dùng dạy được áp dụng literal ở Bước 4."""
    r = VietnameseDiacriticRestorer()
    assert r.add_correction("chiu lyrc", "chịu lực") is True
    assert "chịu lực" in r.restore("ket cau chiu lyrc la chinh")


def test_sua_loi_ocr_giu_kieu_hoa():
    """Sửa lỗi giữ đúng hoa/thường theo chỗ gốc (kể cả nhãn IN HOA)."""
    r = VietnameseDiacriticRestorer()
    r.add_correction("mo cau", "mố cầu")
    assert "mố cầu" in r.restore("phan mo cau phia bac")
    assert "MỐ CẦU" in r.restore("CHI TIET MO CAU")


def test_khong_hoc_sua_so():
    """Cặp sửa chứa SỐ bị từ chối ở tầng restorer (chống phá số liệu)."""
    r = VietnameseDiacriticRestorer()
    assert r.add_correction("12.5", "13.0") is False


def test_is_caps_label():
    assert _is_caps_label("VA") is True
    assert _is_caps_label("M1") is True         # có 1 chữ cái viết hoa
    assert _is_caps_label("BTCT") is True
    assert _is_caps_label("Va") is False        # Title Case → không phải nhãn
    assert _is_caps_label("coc") is False
    assert _is_caps_label("123") is False       # không có chữ cái
    assert _is_caps_label("") is False


# ─────────────────────────────────────────────────────────────────────────────
# Trình chạy độc lập (không cần pytest)
# ─────────────────────────────────────────────────────────────────────────────
# ── Lớp SỬA LỖI CHẮC CHẮN: chạy cả với dòng đã có dấu một phần ─────────────────
# Đo trên Thông tư 13/2021: trước ~10 lỗi/1000 từ ('chi phi' x34, 'S6' x39...), vì dòng đã
# có dấu bị bỏ qua nên không bao giờ được sửa. Sau: 0,6‰, mọi từ bị đổi đều đúng.
def test_sua_loi_chac_chan_tren_dong_da_co_dau():
    from vn_diacritics import restore_vietnamese_diacritics as R
    cases = {
        "Căn cứ Nghi định số 10/2021/NĐ-CP của Chính phủ về quản lý chi phi đầu tư xây dựng":
            "Căn cứ Nghị định số 10/2021/NĐ-CP của Chính phủ về quản lý chi phí đầu tư xây dựng",
        "Chi số giá xây dựng công trình được tính theo công thức sau":
            "Chỉ số giá xây dựng công trình được tính theo công thức sau",
        "Độc lập - Tự do - Hạnh phúc S6: 13/2021/TT-BXD Hà Nội": "Độc lập - Tự do - Hạnh phúc Số: 13/2021/TT-BXD Hà Nội",
        "CÔNG BAO/S6 809 + 810/Ngày 19-9-2021": "CÔNG BÁO/Số 809 + 810/Ngày 19-9-2021",
        "Tỷ trong bình quân của chi phí xây dựng, thiết bị": "Tỷ trọng bình quân của chi phí xây dựng, thiết bị",
        "thay thế Phu lục số 5 của Thông tư của Bộ trường Bộ Xây dựng": "thay thế Phụ lục số 5 của Thông tư của Bộ trưởng Bộ Xây dựng",
    }
    for src, want in cases.items():
        assert R(src) == want, (src, R(src))


def test_sua_loi_chac_chan_khong_dung_vao_chu_dung():
    """Các cụm có VẺ giống lỗi nhưng đúng tiếng Việt phải GIỮ NGUYÊN (khóa ngữ cảnh bằng lookahead)."""
    from vn_diacritics import restore_vietnamese_diacritics as R
    keep = [
        "Chủ đầu tư chi số tiền 5 triệu đồng cho nhà thầu thi công",      # 'chi số tiền' = chi một số tiền
        "Dự án có tổng vốn 10 tỷ trong năm 2026 theo kế hoạch",            # 'tỷ trong năm' = billion in year
        "Phụ lục I ban hành kèm Nghị định số 10/2021/NĐ-CP, chi phí đầu tư xây dựng",
        "Thứ trưởng Bộ Xây dựng ký, khối lượng thi công theo thiết kế",
    ]
    for t in keep:
        assert R(t) == t, (t, R(t))


def test_dau_tu_khong_thanh_dau_tu_dong_am():
    """'dau tu' phải ra 'đầu tư' (trước đây 'đầu từ' vì từ điển chọn 'từ')."""
    from vn_diacritics import restore_vietnamese_diacritics as R
    assert R("chi phi dau tu xay dung") == "chi phí đầu tư xây dựng"
    assert R("du an dau tu cong trinh giao thong").startswith("dự án đầu tư")


def test_sua_loi_chac_chan_idempotent():
    from vn_diacritics import apply_safe_fixes
    t = "Căn cứ Nghi định số 10/2021/NĐ-CP, chi phi đầu từ xây dựng, Phu lục I, Chi số giá"
    once = apply_safe_fixes(t)
    assert apply_safe_fixes(once) == once
    assert "Nghị định" in once and "chi phí" in once and "đầu tư xây" in once and "Phụ lục" in once


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
            print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
            failed += 1
    print("-" * 60)
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL (tổng {passed + failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
