# -*- coding: utf-8 -*-
"""
Nhận dạng & chuẩn hóa SỐ LIỆU trong ô bảng (tách khỏi layout_reconstructor để giảm kích thước
và dùng lại độc lập). Xử lý đúng số kiểu VN (1.525,81 / 1.525 phân nghìn) lẫn US (1,525.81).

Di dời nguyên khối từ layout_reconstructor — hành vi bất biến (có test_number_utils.py bảo chứng).
"""
import re
from typing import List, Optional

_UNIT = r"(?:mm|cm|dm|m|m2|m3|m²|m³|km|kg|kg/m|kg/m3|t|tấn|T|kN|MPa|%|cái|thanh|md)"
_NUMBER_CELL = re.compile(r"^\s*[-+]?\s*\d[\d.,\s]*\s*" + _UNIT + r"?\s*$", re.IGNORECASE)


def is_number_cell(text: str) -> bool:
    return bool(text) and bool(_NUMBER_CELL.match(text)) and not re.search(r"\d\s+\d", text.strip())


def detect_number_style(cells: List[str]) -> str:
    """'vn' (1.525,81 hoặc 1.525), 'us' (1,525.81) hoặc 'unknown' theo đa số ô trong bảng.
    Bảng cốt thép VN hay dùng dấu chấm phân nghìn cho số nguyên lớn (1.525 kg).
    """
    vn = us = 0
    for c in cells:
        t = c.strip()
        # VN: có dấu phẩy thập phân, hoặc số nguyên dùng chấm phân nghìn (1.525, 12.500)
        if (re.search(r"\d\.\d{3},\d+$", t)                    # 1.525,81
                or re.search(r"(?<![\d.])\d+,\d{1,2}$", t)     # 25,50
                or re.search(r"^\d{1,3}(?:\.\d{3})+$", t)):    # 1.525 (nguyên, phân nghìn)
            vn += 1
        elif (re.search(r"\d,\d{3}\.\d+$", t)                  # 1,525.81
              or re.search(r"(?<![\d,])\d+\.\d{1,2}$", t)):    # 25.50
            us += 1
    if vn > us:
        return "vn"
    if us > vn:
        return "us"
    # Mặc định bản vẽ VN → vn
    return "vn"


def parse_number(text: str, style: str = "unknown") -> Optional[float]:
    """Đổi chữ số trong ô thành float; None nếu ô không phải một con số."""
    if not is_number_cell(text):
        return None
    m = re.match(r"\s*([-+]?)\s*(\d[\d.,]*)", text)
    if not m:
        return None
    sign, s = m.group(1), m.group(2).rstrip(".,")
    if "." in s and "," in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        s = s.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in s:
        if s.count(",") > 1 or (style == "us" and re.fullmatch(r"\d{1,3}(,\d{3})+", s)):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        if s.count(".") > 1 or (style == "vn" and re.fullmatch(r"\d{1,3}\.\d{3}", s)):
            s = s.replace(".", "")
    try:
        return float(sign + s)
    except ValueError:
        return None
