# -*- coding: utf-8 -*-
"""
Bộ kiểm thử cho AEC Experience Engine sau khi sửa lỗi "đọc nghìn PDF mà không học được gì".

Nguyên nhân lỗi cũ: distill_text_experience() chỉ dò 3 DANH SÁCH CỨNG rồi thêm lại chính các
mục cứng đó — không hề đọc nội dung tài liệu. Hết vài hồ sơ đầu là cạn → mãi mãi new_* = 0.

Bộ test chốt hành vi MỚI:
  (A) Học THẬT từ nội dung: từ viết tắt tự định nghĩa + thuật ngữ lặp lại.
  (B) Học TIẾP khi gặp hồ sơ mới (điều bản cũ KHÔNG làm được).
  (C) Plateau ĐÚNG: đọc lại cùng hồ sơ → 0 (không phải lỗi, là đúng).
  (D) An toàn: KHÔNG tự bơm thuật ngữ học-tự-động vào bộ khôi phục dấu (chống vòng lặp).
  (E) Idempotent: nạp vào engine sống không phình bộ nhớ khi đọc batch (sửa rò rỉ).

Chạy:  engine\\python.exe test_experience_engine.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from experience_engine import AECExperienceEngine

DOC1 = ("Mặt cắt ngang tuyến đường thiết kế. Bản vẽ thể hiện mặt cắt ngang và trắc dọc. "
        "Bê tông cốt thép (BTCT) mác 300 cho kết cấu. Kết cấu bê tông cốt thép chịu lực chính.")
DOC2 = ("Hệ thống phòng cháy chữa cháy (PCCC) theo quy chuẩn hiện hành. "
        "Thiết kế phòng cháy chữa cháy cho toàn công trình.")


def _fresh_engine() -> AECExperienceEngine:
    db = os.path.join(tempfile.mkdtemp(prefix="exp_"), "db.json")
    return AECExperienceEngine(db_path=db)


# ── (A) Học THẬT từ nội dung ──────────────────────────────────────────────────
def test_hoc_tu_viet_tat_tu_dinh_nghia():
    e = _fresh_engine()
    out = e.distill_text_experience(DOC1)
    assert out["new_abbr"] >= 1, out
    assert e.knowledge["abbreviations"].get("BTCT") == "Bê tông cốt thép", e.knowledge["abbreviations"]


def test_hoc_thuat_ngu_lap_lai():
    e = _fresh_engine()
    out = e.distill_text_experience(DOC1)
    assert out["new_terms"] >= 1, out
    assert "mặt cắt ngang" in e.knowledge["term_glossary"], list(e.knowledge["term_glossary"])[:10]


def test_khong_hoc_rac_khong_dau():
    """Chuỗi OCR không dấu / rác KHÔNG được coi là thuật ngữ."""
    e = _fresh_engine()
    out = e.distill_text_experience("abcx mnop qrst abcx mnop qrst khong dau gi ca khong dau gi ca")
    assert out["new_terms"] == 0, (out, e.knowledge["term_glossary"])


# ── (B) Học TIẾP với hồ sơ mới (bản cũ KHÔNG làm được) ─────────────────────────
def test_van_hoc_tiep_voi_ho_so_moi():
    e = _fresh_engine()
    e.distill_text_experience(DOC1)                 # đã học BTCT
    out2 = e.distill_text_experience(DOC2)          # hồ sơ mới → PCCC
    assert out2["new_abbr"] >= 1, out2
    assert "PCCC" in e.knowledge["abbreviations"], e.knowledge["abbreviations"]
    assert out2["new_terms"] >= 1, out2


# ── (C) Plateau đúng: đọc lại cùng hồ sơ → 0 ──────────────────────────────────
def test_doc_lai_cung_ho_so_khong_hoc_them():
    e = _fresh_engine()
    first = e.distill_text_experience(DOC1)
    again = e.distill_text_experience(DOC1)
    assert first["new_abbr"] + first["new_terms"] > 0, first   # lần đầu CÓ học
    assert again == {"new_abbr": 0, "new_terms": 0}, again      # lần sau đúng = 0


# ── (D) An toàn: không bơm term_glossary vào bộ khôi phục dấu ──────────────────
def test_khong_bom_thuat_ngu_vao_restorer():
    import vn_diacritics
    e = _fresh_engine()
    e.distill_text_experience(DOC1)
    before = list(vn_diacritics.AEC_COMPOUND_PHRASES)
    e.sync_to_live_engines()
    after = vn_diacritics.AEC_COMPOUND_PHRASES
    added = [p for p in after if p not in before]
    # term_glossary không được xuất hiện trong luật khôi phục dấu
    term_keys = set(e.knowledge["term_glossary"])
    assert all(pat not in term_keys for pat, _ in added), added


# ── (E) Idempotent: nạp engine sống không phình bộ nhớ ────────────────────────
def test_sync_idempotent_khong_ro_ri():
    import vn_diacritics
    e = _fresh_engine()
    e.knowledge["unsticking_rules"]["xyzdinhnhau"] = "xyz dinh nhau"
    e.knowledge["learned_phrases"]["cum tu test"] = "cụm từ test"

    base_unstick = len(vn_diacritics.AEC_UNSTICKING_RULES)
    base_compound = len(vn_diacritics.AEC_COMPOUND_PHRASES)

    e.sync_to_live_engines()
    after1_u = len(vn_diacritics.AEC_UNSTICKING_RULES)
    after1_c = len(vn_diacritics.AEC_COMPOUND_PHRASES)

    e.sync_to_live_engines()   # gọi lại nhiều lần (mô phỏng đọc nhiều hồ sơ)
    e.sync_to_live_engines()
    after3_u = len(vn_diacritics.AEC_UNSTICKING_RULES)
    after3_c = len(vn_diacritics.AEC_COMPOUND_PHRASES)

    assert after1_u == base_unstick + 1, (base_unstick, after1_u)
    assert after1_c == base_compound + 1, (base_compound, after1_c)
    # Gọi lại KHÔNG được thêm nữa (bản cũ sẽ +1 mỗi lần → rò rỉ)
    assert after3_u == after1_u, (after1_u, after3_u)
    assert after3_c == after1_c, (after1_c, after3_c)


# ── (F) HỌC CÓ GIÁM SÁT: SỬA LỖI OCR TỪ NGƯỜI DÙNG ───────────────────────────
def test_hoc_sua_loi_ocr_chu_an_toan():
    """Sửa lỗi CHỮ do người dùng xác nhận → lưu + đánh dấu an toàn để áp dụng lại."""
    e = _fresh_engine()
    res = e.learn_ocr_correction("chiu lyrc", "chịu lực", source="hs1")
    assert res["stored"] and res["safe"], res
    assert e.get_safe_corrections().get("chiu lyrc") == "chịu lực"


def test_khong_tong_quat_hoa_sua_so():
    """Sửa SỐ chỉ lưu truy vết, KHÔNG được áp dụng tự động cho hồ sơ khác."""
    e = _fresh_engine()
    res = e.learn_ocr_correction("12.5", "13.0", source="hs1")
    assert res["stored"] is True, res
    assert res["safe"] is False, res
    assert "12.5" not in e.get_safe_corrections()


def test_bo_qua_sua_khong_doi_va_ky_hieu_ocr_khac():
    """Bỏ ký hiệu ⟦OCR khác: …⟧; nếu sau khi bỏ mà không đổi thì không lưu."""
    e = _fresh_engine()
    res = e.learn_ocr_correction("BTCT⟦OCR khác: BTGT⟧", "BTCT")
    assert res["stored"] is False, res   # raw sau khi bỏ ⟦⟧ == corrected


def test_dem_so_lan_sua_tang_dan():
    e = _fresh_engine()
    e.learn_ocr_correction("coc khoan nhoi", "cọc khoan nhồi")
    e.learn_ocr_correction("coc khoan nhoi", "cọc khoan nhồi")
    assert e.knowledge["ocr_corrections"]["coc khoan nhoi"]["count"] == 2


# ── Hàm phụ trợ ───────────────────────────────────────────────────────────────
def test_acronym_matches():
    assert AECExperienceEngine._acronym_matches("BTCT", "Bê tông cốt thép") is True
    assert AECExperienceEngine._acronym_matches("PCCC", "Phòng cháy chữa cháy") is True
    assert AECExperienceEngine._acronym_matches("ABC", "Bê tông cốt thép") is False
    assert AECExperienceEngine._acronym_matches("X", "một từ") is False


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
            print(f"  ✗ {name}\n      {type(e).__name__}: {e}")
            failed += 1
    print("-" * 60)
    print(f"KẾT QUẢ: {passed} PASS / {failed} FAIL (tổng {passed + failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
