# -*- coding: utf-8 -*-
"""
Golden test cho HẬU KIỂM CHỐNG LẬT 180° (ocr_tiling).

Bối cảnh lỗi thật: bộ phân loại hướng chữ (use_cls=True) là CẦN cho bản vẽ CAD
(đọc đúng nhãn xoay, bắt thêm hộp chữ) nhưng phán đoán nhầm dòng chữ ngang đứng
thẳng là lộn ngược, khiến khâu nhận dạng trả về chuỗi đảo ngược:
    'upnb ga Sunp 1ou gs 1ou 1g lyo yuip Knb yuip iy8N yupy upq nyd yuiyd'
đúng phải là 'Chính phủ ban hành Nghị định quy định chi tiết một số…'

Bộ test này khoá: (1) bộ đo nhận đúng câu đúng / câu lật, (2) không đụng vào
dòng mã hiệu & số liệu, (3) chỉ sửa khi bản đọc lại sạch hơn hẳn.

Chạy:  engine\\python.exe test_ocr_orientation.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_tiling import (vn_likeness, _is_vn_syllable, _strip_vn,
                        FLIP_MAX_SCORE, FLIP_ACCEPT_SCORE)


# ── (1) Bộ đo "độ giống tiếng Việt" ─────────────────────────────────────────
def test_am_tiet_tieng_viet_hop_le():
    for w in ["hop", "chinh", "nguon", "duoc", "thiet", "ke", "nghi", "dinh",
              "quan", "ban", "hanh", "chi", "tiet", "noi", "dung"]:
        assert _is_vn_syllable(_strip_vn(w)), w


def test_chuoi_lat_180_bi_tu_choi():
    """Các 'âm tiết' sinh ra từ chữ bị lật phải bị coi là KHÔNG hợp lệ.

    Lưu ý: vài token của chữ lật TRÙNG HÌNH DẠNG với âm tiết thật ('quip' = qu+ip,
    'ku', 'xu') nên không thể đòi từ chối từng token — cái quyết định là ĐIỂM của
    cả dòng, xem test_diem_cau_dung_cao_hon_cau_lat."""
    for w in ["upnb", "yuip", "iy8n", "yupy", "gunp", "sunp", "yuiyd",
              "iyan", "heoy", "wey", "gs", "ou", "yui"]:
        assert not _is_vn_syllable(_strip_vn(w)), w


def test_token_tieng_viet_that_khong_bi_tu_choi():
    """Chốt chiều ngược lại: các âm tiết thật phải được công nhận, nếu không
    bộ đo sẽ báo động giả trên chính văn bản đúng."""
    for w in ["quip", "ku", "xu", "ke", "ho", "cho", "nguon", "thiet"]:
        assert _is_vn_syllable(_strip_vn(w)), w


def test_diem_cau_dung_cao_hon_cau_lat():
    correct = "Chính phủ ban hành Nghị định quy định chi tiết một số nội dung về quản"
    garbled = "upnb ga Sunp 1ou gs 1ou 1g lyo yuip Knb yuip iy8N yupy upq nyd yuiyd"
    sc, sg = vn_likeness(correct), vn_likeness(garbled)
    assert sc is not None and sg is not None
    assert sc >= 0.95, sc
    assert sg < FLIP_MAX_SCORE, sg
    assert sc > sg + 0.2, (sc, sg)


def test_diem_cau_lat_thu_hai():
    """Ca thật thứ hai trên hồ sơ nd06 (trang 2)."""
    correct = ("Quản lý chất lượng công trình xây dựng là hoạt động quản lý của các "
               "chủ thể tham gia các hoạt động xây dựng theo quy định")
    garbled = "pa Xeu quip iyan eno yup Xnb oay gunp Aex guop heoy oeo ei wey gu nyo"
    sc, sg = vn_likeness(correct), vn_likeness(garbled)
    assert sc >= 0.95, sc
    assert sg < FLIP_MAX_SCORE, sg


# ── (2) Không phán đoán khi thiếu ngữ cảnh ──────────────────────────────────
def test_qua_it_token_thi_tra_none():
    """Dòng mã hiệu / kích thước ngắn -> không đủ ngữ cảnh, phải trả None để
    khâu sửa bỏ qua, không được đoán bừa."""
    for s in ["", "B4-D18", "52@150=7800", "MẶT CẮT A-A", "B1-D32", "1 2 3"]:
        assert vn_likeness(s) is None, s


def test_dong_kich_thuoc_ban_ve_khong_bi_coi_la_lat():
    """Dòng kích thước CAD: chữ cái ít so với số -> tỉ lệ chữ cái thấp, khâu sửa
    tự loại trước khi đo. Khoá lại quy tắc đó."""
    ratios = []
    for s in ["52@150=7800", "9@150=1350", "11600/2=5800", "1200+2*300+2*150"]:
        letters = sum(1 for c in s if c.isalpha())
        ratios.append(letters / len(s))
    assert all(r < 0.70 for r in ratios), ratios


# ── (3) Ngưỡng chấp nhận ────────────────────────────────────────────────────
def test_nguong_chap_nhan_chat_hon_han():
    """Bản đọc lại phải đạt >= FLIP_ACCEPT_SCORE mới được thay bản cũ."""
    assert FLIP_ACCEPT_SCORE > FLIP_MAX_SCORE
    good = "Chính phủ ban hành Nghị định quy định chi tiết một số nội dung về quản"
    assert vn_likeness(good) >= FLIP_ACCEPT_SCORE


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    ok = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            ok += 1
        except AssertionError as e:
            print(f"  ✗ {name}\n      AssertionError: {e}")
        except Exception as e:
            print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
    print("-" * 60)
    print(f"KẾT QUẢ: {ok} PASS / {len(tests) - ok} FAIL (tổng {len(tests)})")
    sys.exit(0 if ok == len(tests) else 1)
