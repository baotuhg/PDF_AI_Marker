# -*- coding: utf-8 -*-
"""Kiểm thử bộ ghép lai RapidOCR + VietOCR (không cần nạp model)."""
import unittest

from vn_vietocr import merge, available, MODEL_DIR


class TestHybridMerge(unittest.TestCase):
    def test_accents_from_vietocr(self):
        self.assertEqual(merge("Tong chieu dai tuyen", "Tổng chiều dài tuyến"), "Tổng chiều dài tuyến")

    def test_digits_and_symbols_from_rapid(self):
        # VietOCR hay đọc '+' thành '4' -> giữ số liệu của RapidOCR
        self.assertEqual(merge("Km19+529.080", "Km1945290080"), "Km19+529.080")
        self.assertEqual(merge("Cau Km19+529", "Cầu Km1945290"), "Cầu Km19+529")

    def test_case_follows_rapid(self):
        self.assertEqual(merge("XOP CHEN KHE", "XỐP CHèn Khe"), "XỐP CHÈN KHE")
        self.assertEqual(merge("B6 tri khoan", "Bố trí khoan"), "Bố trí khoan")
        self.assertEqual(merge("dai: 27,48Km", "dài: 27,48km"), "dài: 27,48Km")

    def test_glued_words_resplit(self):
        self.assertEqual(merge("MATCATNGANGTRUGIAIDOAN4LANXE", "MẶT CẮT NGANG TRỤ GIAI ĐOẠN 4 LÀN XE"),
                         "MẶT CẮT NGANG TRỤ GIAI ĐOẠN 4 LÀN XE")
        self.assertEqual(merge("DAY20MM", "DÀY 20MM"), "DÀY 20MM")

    def test_glued_words_digit_mismatch_keeps_rapid(self):
        self.assertEqual(merge("DAY20MM", "DÀY 28MM"), "DAY20MM")

    def test_vietocr_merges_words(self):
        self.assertEqual(merge("BO TRI SO LE", "BỐ TRÍ SOLE"), "BỐ TRÍ SO LE")

    def test_reject_inserted_words(self):
        self.assertEqual(merge("THEP CHU", "THÉP TẾ CHỦ"), "THÉP CHỦ")

    def test_reject_unrelated_line(self):
        self.assertEqual(merge("D14a200", "Đường ống"), "D14a200")
        self.assertEqual(merge("abc", ""), "abc")

    def test_model_files_present(self):
        self.assertTrue(available(), f"Thiếu model VietOCR ONNX trong {MODEL_DIR}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
