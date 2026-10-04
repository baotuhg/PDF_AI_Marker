# -*- coding: utf-8 -*-
"""
Layout and Table Reconstruction Engine for PDF AI Marker (Engineering Edition v3)
================================================================================
Tái tạo bố cục 2D, bảng biểu và siêu dữ liệu bản vẽ cho hồ sơ Xây dựng / Giao
thông Việt Nam từ tọa độ chữ (RapidOCR, Surya hoặc lớp text của PDF).

Nguyên tắc cốt lõi:
1. KHÔNG bỏ chữ nào: chữ chưa xếp vào mục nào nằm ở "Ghi chú / chữ khác".
2. Bảng ưu tiên dò theo ĐƯỜNG KẺ Ô trên ảnh (table_grid); chỉ đoán theo tọa độ
   chữ khi bảng không có lưới.
3. Tên bảng lấy từ CHỮ THẬT trên bản vẽ, không gán nhãn cố định.
4. Khung tên, dấu thẩm định tách theo từ khóa neo; khung tên được trích thành
   các trường (số hiệu bản vẽ, tỷ lệ, ngày, lý trình...).
5. Số liệu bảng được chuẩn hóa sang số thực (xử lý 1.525,81 kiểu VN và 63.36
   kiểu US) trong JSON; markdown giữ nguyên chữ gốc.
6. So khớp từ khóa không phụ thuộc dấu, nên dùng được cho cả chữ có dấu (Surya)
   lẫn không dấu (RapidOCR).

API chính: analyze_page(...) -> dict; reconstruct_page_layout(...) -> markdown.
"""

import json
import re
import statistics
from bisect import bisect_right
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from app_log import get_logger
    log = get_logger(__name__)
except Exception:
    import logging
    log = logging.getLogger("pdf_ai.layout")

from vn_refine import strip_accents, ALT_OPEN

LOW_CONFIDENCE = 0.75

# Bộ quy tắc khôi phục dấu / tách từ dính chùm cho chữ RapidOCR (không dấu).
# Chỉ gồm các phép khôi phục dấu thuần túy, KHÔNG đổi nghĩa câu chữ.
VIETNAMESE_AEC_RULES = [
    # NOTE: luat va-tai-lieu-cu-the (thay ca cau) da TACH sang aec_project_rules.json.
    # O day CHI giu luat khoi phuc dau / tach tu TONG QUAT, tai dung cho moi ho so.
    ('\\bGO1\\s+THAU\\b', 'GÓI THẦU'),
    ('\\bTHIET\\s*KEBVTC\\b', 'THIẾT KẾ BVTC'),
    ('\\bBérong\\b', 'Bề rộng'),
    ('\\bBerong\\b', 'Bề rộng'),
    ('\\bBe\\s*rong\\b', 'Bề rộng'),
    ('\\bGoicaucao\\s*su\\b', 'Gối cầu cao su'),
    ('\\bcotban\\s*theploai\\b', 'cốt bản thép loại'),
    ('\\btheploai\\b', 'thép loại'),
    ('\\bmat\\s*do\\s*ma\\s*([0-9]+)', 'mật độ mạ \\1'),
    ('\\bchiu\\s+lyrc\\b', 'chịu lực'),
    ('\\bchiu\\s+luc\\b', 'chịu lực'),
    ('\\bchju\\s+luc\\b', 'chịu lực'),
    ('\\bchju\\s+dong\\s+dat\\b', 'chịu động đất'),
    ('\\bchju\\b', 'chịu'),
    ('\\btiu\\s+tren\\s+xuong\\b', 'từ trên xuống'),
    ('\\bvra-nhe\\b', 'vừa - nhẹ'),
    ('\\bdamBTCT\\b', 'dầm BTCT'),
    ('\\bKetcau\\b', 'Kết cấu'),
    ('\\bSodonhip\\b', 'Sơ đồ nhịp'),
    ('\\bgira\\s+cac\\s+dam\\b', 'giữa các dầm'),
    ('\\bb6\\s+tri\\b', 'bố trí'),
    ('\\bbo\\s*tri\\b', 'bố trí'),
    ('\\bdurong\\s+be\\s+tong\\b', 'đường bê tông'),
    ('\\bdurong\\s+BT\\b', 'đường BT'),
    ('\\bdurong\\s+o\\s+to\\b', 'đường ô tô'),
    ('\\bdurong\\b', 'đường'),
    ('\\bdugclienketvoi\\b', 'được liên kết với'),
    ('\\bdugc\\b', 'được'),
    ('\\blienketvoi\\b', 'liên kết với'),
    ('\\btir\\b', 'từ'),
    ('\\bChu\\s+dau\\s+tur\\b', 'Chủ đầu tư'),
    ('\\blang\\s+nhya\\b', 'láng nhựa'),
    ('\\bdjaky\\s+thuat\\b', 'địa kỹ thuật'),
    ('\\bvemang\\s+phanquang\\b', 'về màng phản quang'),
    ('\\bDACDIEMDIACHAT\\b', 'ĐẶC ĐIỂM ĐỊA CHẤT'),
    ('\\bGIAIPHAPTHIETKE\\b', 'GIẢI PHÁP THIẾT KẾ'),
    ('\\bPhan cau\\b', 'Phần cầu'),
    ('\\bVat lieu sir dung\\b', 'Vật liệu sử dụng'),
    ('\\bsir dung\\b', 'sử dụng'),
    ('\\btuong duong\\b', 'tương đương'),
    ('\\bgita nhip\\b', 'giữa nhịp'),
    ('\\b1op phong nuoc\\b', 'lớp phòng nước'),
    ('\\b1op da dam\\b', 'lớp đá dăm'),
    ('\\bmongam\\b', 'móng ngàm'),
    ('\\bdagoc\\b', 'đá gốc'),
    ('\\bda goc\\b', 'đá gốc'),
    ('\\bgia co tr non\\b', 'gia cố tứ nón'),
    ('\\btr non\\b', 'tứ nón'),
    ('\\bGioihanchay\\b', 'Giới hạn chảy'),
    ('\\bCot thep tron tron\\b', 'Cốt thép tròn trơn'),
    ('\\bOpmai taluy\\b', 'Ốp mái ta luy'),
    ('\\bmaitaluy\\b', 'mái ta luy'),
    ('\\bcobo tri\\b', 'có bố trí'),
    ('\\bdauong thoat rurc\\b', 'đầu ống thoát nước'),
    ('\\bthoat rurc\\b', 'thoát nước'),
    ('\\blongmova\\b', 'lòng mố và'),
    ('\\blongm6\\b', 'lòng mố'),
    ('\\bsaumoduocgia\\b', 'sau mố được gia'),
    ('\\bdo doc doc\\b', 'độ dốc dọc'),
    ('\\bD6 doc ngang\\b', 'Độ dốc ngang'),
    ('\\bdo doc ngang\\b', 'độ dốc ngang'),
    ('\\bS[6o0]\\s*l[u]r?[o0]ng\\b', 'Số lượng'),
    ('\\bkh[o0]i\\s*l[u]r?[o0]ng\\b', 'khối lượng'),
    ('\\btr[o0]ng\\s*l[u]r?[o0]ng\\b', 'trọng lượng'),
    ('\\blurong\\b', 'lượng'),
    ('\\bchieu\\s*dai\\b', 'chiều dài'),
    ('\\bduong\\s*kinh\\b', 'đường kính'),
    ('\\bky\\s*hieu\\b', 'ký hiệu'),
    ('\\bdon\\s*vi\\b', 'đơn vị'),
    ('\\bghi\\s*chu\\b', 'ghi chú'),
    ('lanrcay', 'lẫn rễ cây'),
    ('\\bthc\\s*vat\\b', 'thực vật'),
    ('\\bxamvang\\b', 'xám vàng'),
    ('\\bxam den\\b', 'xám đen'),
    ('\\bxam ghi\\b', 'xám ghi'),
    ('\\bxam nau\\b', 'xám nâu'),
    ('\\blan dam san\\b', 'lẫn dăm sạn'),
    ('\\bdeo cung\\b', 'dẻo cứng'),
    ('\\bDa phien set voi\\b', 'Đá phiến sét vôi'),
    ('\\bthanh thep neoD32mm\\b', 'thanh thép neo D32mm'),
    ('\\bcac bemat m\\b', 'các bề mặt mố'),
    ('\\bbemat m\\b', 'bề mặt mố'),
    ('\\btong nhya chat C12,5\\b', 'tông nhựa chặt C12.5'),
    ('\\bchieu daynhonhat\\b', 'chiều dày nhỏ nhất'),
    ('\\bfc²\\s*=\\s*([0-9]+)\\s*MPa', "f'c = \\1 MPa"),
    ("\\bfe'\\s*=\\s*([0-9]+)\\s*MPa", "f'c = \\1 MPa"),
    ('\\bTCVN8871-1:2011÷', 'TCVN 8871-1:2011'),
    ('\\bTCVN8871-([0-9]):2011\\b', 'TCVN 8871-\\1:2011'),
    ('\\bQCVN41:2016/BGTVT\\b', 'QCVN 41:2016/BGTVT'),
    ('\\bQCVN41:2019/BGTVT\\b', 'QCVN 41:2019/BGTVT'),
    ('\\bTCVN11823-2017\\b', 'TCVN 11823:2017'),
    ('\\bTCVN9845:2013\\b', 'TCVN 9845:2013'),
    ('\\bTCVN9386-2:2012\\b', 'TCVN 9386-2:2012'),
    ('\\bTCVN9386:2012\\b', 'TCVN 9386:2012'),
    ('\\bTCVN\\s*4054-05\\b', 'TCVN 4054:2005'),
    ('\\bTCVN\\s*1651:2008\\b', 'TCVN 1651:2008'),
]

CUSTOM_RULES: List[Tuple[str, str]] = []
_custom_rules_loaded = False
_compiled_rules: Optional[List[Tuple[re.Pattern, str]]] = None

# Luật vá-tài-liệu-cụ-thể (thay cả câu) — TÁCH khỏi core sang file dữ liệu aec_project_rules.json.
PROJECT_RULES: List[Tuple[str, str]] = []
_project_rules_loaded = False


def load_project_rules() -> List[Tuple[str, str]]:
    """Nạp luật vá theo dự án từ aec_project_rules.json (giá trị khớp cả câu cho một bộ hồ sơ).
    Áp dụng TRƯỚC các luật tổng quát để giữ đúng hành vi cũ (khớp chuỗi dính nguyên gốc)."""
    global PROJECT_RULES, _project_rules_loaded
    if _project_rules_loaded:
        return PROJECT_RULES
    _project_rules_loaded = True
    for p in (Path(__file__).resolve().parent / "aec_project_rules.json",
              Path.cwd() / "aec_project_rules.json"):
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, list) and len(item) == 2:
                            PROJECT_RULES.append((str(item[0]), str(item[1])))
                        elif isinstance(item, dict) and "pattern" in item and "replace" in item:
                            PROJECT_RULES.append((str(item["pattern"]), str(item["replace"])))
            except Exception as e:
                log.warning("Đọc aec_project_rules.json lỗi (%s): %s", p, e)
            break
    return PROJECT_RULES


def load_custom_rules() -> List[Tuple[str, str]]:
    """Tự động nạp quy tắc từ điển riêng (nếu có file custom_rules.json)."""
    global CUSTOM_RULES, _custom_rules_loaded
    if _custom_rules_loaded:
        return CUSTOM_RULES
    _custom_rules_loaded = True
    search_paths = [
        Path(__file__).resolve().parent / "custom_rules.json",
        Path.cwd() / "custom_rules.json",
    ]
    for p in search_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, list) and len(item) == 2:
                            CUSTOM_RULES.append((str(item[0]), str(item[1])))
                        elif isinstance(item, dict) and "pattern" in item and "replace" in item:
                            CUSTOM_RULES.append((str(item["pattern"]), str(item["replace"])))
            except Exception as e:
                log.warning("Đọc custom_rules.json lỗi (%s): %s", p, e)
            break
    return CUSTOM_RULES


def _match_case(src: str, repl: str) -> str:
    """Giữ kiểu chữ của bản gốc: 'DUGC' -> 'ĐƯỢC', 'Dugc' -> 'Được'."""
    letters = [c for c in src if c.isalpha()]
    if len(letters) > 1 and all(c.isupper() for c in letters):
        return repl.upper()
    if letters and letters[0].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def fix_vietnamese_typos(text: str) -> str:
    """Khôi phục dấu / tách từ dính chùm cho chữ OCR không dấu (giữ kiểu hoa-thường)."""
    global _compiled_rules
    if not text:
        return ""
    if _compiled_rules is None:
        _compiled_rules = [(re.compile(p, re.IGNORECASE), r)
                           for p, r in load_project_rules() + VIETNAMESE_AEC_RULES + load_custom_rules()]
    result = text
    for pattern, replacement in _compiled_rules:
        result = pattern.sub(lambda m, r=replacement: _match_case(m.group(0), m.expand(r)), result)

    # Khôi phục dấu tiếng Việt chuyên sâu từ chữ Latin bằng vn_diacritics
    try:
        from vn_diacritics import restore_vietnamese_diacritics
        result = restore_vietnamese_diacritics(result)
    except Exception as e:
        log.debug("restore_vietnamese_diacritics lỗi (giữ nguyên text): %s", e)

    # Thêm khoảng trắng sau dấu hai chấm nếu dính chữ cái ('Trong do:Bérong').
    # Không áp dụng cho số để giữ tỷ lệ 1:500, giờ 14:30, TCVN 11823:2017.
    return re.sub(r':([A-Za-zÀ-ỹ])', r': \1', result)


# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích so khớp không dấu
# ─────────────────────────────────────────────────────────────────────────────
def fold_upper(text: str) -> str:
    """Bỏ dấu + viết hoa, GIỮ NGUYÊN độ dài để cắt lại chuỗi gốc theo vị trí."""
    return "".join(c.upper() if len(c.upper()) == 1 else c for c in strip_accents(text))


def fold_key(text: str) -> str:
    """Khóa so khớp: bỏ dấu, viết hoa, bỏ khoảng trắng/ký hiệu ('Mặt cắt' -> 'MATCAT')."""
    return re.sub(r"[^0-9A-Z]", "", fold_upper(text))


def has_kw(text: str, keywords) -> bool:
    key = fold_key(text)
    return any(kw in key for kw in keywords)


# ─────────────────────────────────────────────────────────────────────────────
# Hộp chữ & dòng
# ─────────────────────────────────────────────────────────────────────────────
def extract_box_metrics(box: List[List[float]], text: str, score: float = 1.0) -> Dict[str, Any]:
    """Trích xuất các thông số tọa độ chuẩn hóa từ hộp giới hạn 4 điểm."""
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    return {
        "text": fix_vietnamese_typos(text.strip()),
        "x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max,
        "cx": (x_min + x_max) / 2.0, "cy": (y_min + y_max) / 2.0,
        "w": x_max - x_min, "h": y_max - y_min,
        "score": score,
    }


def cluster_items_into_lines(items: List[Dict[str, Any]], y_tolerance: float = 0.0) -> List[Dict[str, Any]]:
    """Nhóm các phần tử chữ theo trục Y (dòng văn bản) dựa trên khoảng cách trọng tâm."""
    if not items:
        return []
    if y_tolerance <= 0:
        med_h = statistics.median([it["h"] for it in items]) if items else 15.0
        y_tolerance = max(6.0, med_h * 0.55)

    lines: List[Dict[str, Any]] = []
    for it in sorted(items, key=lambda it: it["cy"]):
        for line in lines:
            if abs(it["cy"] - line["cy"]) < y_tolerance:
                line["items"].append(it)
                line["cy"] = sum(x["cy"] for x in line["items"]) / len(line["items"])
                break
        else:
            lines.append({"cy": it["cy"], "items": [it]})

    lines.sort(key=lambda l: l["cy"])
    for l in lines:
        l["items"].sort(key=lambda it: it["x_min"])
    return lines


class _Cell(str):
    """Chuỗi nội dung ô bảng kèm tọa độ (.box = [x0, y0, x1, y1], hệ base_scale).

    Là str thật nên mọi xử lý chuỗi/JSON cũ giữ nguyên; .box chỉ dùng để xuất
    `cell_boxes` cho trình Đối chiếu trực quan (click ô -> khung đỏ trên trang)."""
    box = None


def _items_box(items: List[Dict[str, Any]]) -> Optional[List[float]]:
    if not items:
        return None
    return [min(it["x_min"] for it in items), min(it["y_min"] for it in items),
            max(it["x_max"] for it in items), max(it["y_max"] for it in items)]


def _cell(text: str, box: Optional[List[float]]) -> str:
    if not text or box is None:
        return text
    c = _Cell(text)
    c.box = box
    return c


def _keep_box(src: str, text: str) -> str:
    """Giữ tọa độ của ô khi nội dung được biến đổi (strip...)."""
    return _cell(text, getattr(src, "box", None))


def _join_items(items: List[Dict[str, Any]]) -> str:
    text = " ".join(" ".join(it["text"] for it in l["items"])
                    for l in cluster_items_into_lines(items)).strip()
    return _cell(text, _items_box(items))


def _median_h(items: List[Dict[str, Any]]) -> float:
    hs = [it["h"] for it in items if it["h"] > 0]
    return statistics.median(hs) if hs else 12.0


# ─────────────────────────────────────────────────────────────────────────────
# Số liệu: nhận dạng & chuẩn hóa
# ─────────────────────────────────────────────────────────────────────────────
# Tiện ích số liệu ĐÃ TÁCH sang number_utils.py (giảm kích thước file). Re-export để các
# import cũ 'from layout_reconstructor import parse_number, ...' vẫn hoạt động nguyên vẹn.
from number_utils import (  # noqa: E402,F401
    _UNIT, _NUMBER_CELL, is_number_cell, detect_number_style, parse_number,
)


# ─────────────────────────────────────────────────────────────────────────────
# Mô hình bảng
# ─────────────────────────────────────────────────────────────────────────────
def _clean_rows(rows: List[List[str]]) -> List[List[str]]:
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    keep = [i for i in range(ncol) if any(r[i].strip() for r in rows)]
    return [[_keep_box(r[i], r[i].strip()) for i in keep] for r in rows]


def split_header(rows: List[List[str]]) -> Tuple[List[str], List[List[str]]]:
    """Gộp các dòng tiêu đề cột nhiều tầng (không chứa ô số) thành một header."""
    # Từ khóa tiêu đề cột bảng khối lượng / cốt thép (so trên chữ đã bỏ dấu).
    # KHÔNG đưa ký hiệu thép (Φ20, D16) vào đây: chúng có mặt ở mọi dòng số liệu
    # của bảng cốt thép, nếu coi là từ khóa tiêu đề thì các dòng đầu bảng bị
    # nuốt vào header (lỗi đã gặp ở TC-04 và PD-07 bộ Khai Hoang 2).
    _HEADER_KW = re.compile(
        r"\bSTT\b|S\.TT|\bTT\b|KY\s*HIEU|DUONG\s*KINH|CHIEU\s*DAI|SO\s*LUONG|"
        r"TRONG\s*LUONG|KHOI\s*LUONG|DON\s*VI|GHI\s*CHU|HANG\s*MUC",
        re.IGNORECASE,
    )
    n_header = 0
    for r in rows[:5]:
        filled = [c for c in r if c]
        if not filled:
            break
        # Hàng số liệu: >= 30% ô là số thuần ('Φ20', 'D16', '(mm)' không phải số)
        numeric = sum(1 for c in filled if is_number_cell(c))
        # Từ khóa tiêu đề chỉ giữ dòng làm header khi dòng đó ít số (< 50% ô)
        has_kw_header = any(_HEADER_KW.search(strip_accents(c)) for c in filled)
        if numeric >= max(1, 0.3 * len(filled)) and not (has_kw_header and numeric < 0.5 * len(filled)):
            break
        n_header += 1
    if n_header == 0:
        return [], rows
    if n_header == len(rows):          # bảng toàn chữ: chỉ dòng đầu là header
        n_header = 1
    ncol = len(rows[0])
    header = [" ".join(r[i] for r in rows[:n_header] if r[i]).strip() for i in range(ncol)]
    return header, rows[n_header:]


def make_table(rows: List[List[str]], title: str, bbox: Optional[List[float]], source: str) -> Optional[Dict[str, Any]]:
    rows = _clean_rows(rows)
    if len(rows) < 2 or len(rows[0]) < 2:
        return None
    # Tiêu đề nằm trong ô gộp ở hàng đầu của lưới
    first = {c for c in rows[0] if c}      # ô gộp cả hàng -> mọi ô cùng một chữ
    if len(first) == 1 and len(rows[0]) >= 3 and has_kw(next(iter(first)), ["BANG", "THONGKE", "KHOILUONG"]):
        head = next(iter(first))
        title = head
        rows = rows[1:]
        if len(rows) < 2:
            return None
    header, body = split_header(rows)
    style = detect_number_style([c for r in body for c in r])

    def _rb(b):
        return [round(v, 1) for v in b] if b else None

    cell_boxes = [[_rb(getattr(c, "box", None)) for c in r] for r in body]
    has_boxes = any(b for r in cell_boxes for b in r)
    if not bbox and has_boxes:
        all_b = [b for r in cell_boxes for b in r if b]
        bbox = [min(b[0] for b in all_b), min(b[1] for b in all_b),
                max(b[2] for b in all_b), max(b[3] for b in all_b)]
    table = {
        "title": title or "Bảng (không có tiêu đề)",
        "bbox": [round(v, 1) for v in bbox] if bbox else None,
        "source": source,
        "header": header,
        "rows": body,
        "values": [[parse_number(c, style) for c in r] for r in body],
        "number_style": style,
    }
    if has_boxes:
        table["cell_boxes"] = cell_boxes
    return table


def table_to_markdown(table: Dict[str, Any]) -> str:
    def esc(c: str) -> str:
        return c.replace("|", "\\|").replace("\n", " ").strip()
    ncol = len(table["rows"][0]) if table["rows"] else len(table["header"])
    header = table["header"] or [f"Cột {i + 1}" for i in range(ncol)]
    lines = ["| " + " | ".join(esc(c) for c in header) + " |",
             "| " + " | ".join(["---"] * len(header)) + " |"]
    for r in table["rows"]:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(lines)


def grid_table_rows(grid: Dict[str, Any], items: List[Dict[str, Any]]) -> List[List[str]]:
    """Xếp chữ vào ô theo ranh giới hàng/cột của lưới kẻ."""
    re_, ce = grid["row_edges"], grid["col_edges"]
    nrow, ncol = len(re_) - 1, len(ce) - 1

    def col_of(it):
        return min(max(bisect_right(ce, it["cx"]) - 1, 0), ncol - 1)

    def row_of(it):
        return min(max(bisect_right(re_, it["cy"]) - 1, 0), nrow - 1)

    centers = [(ce[j] + ce[j + 1]) / 2 for j in range(ncol)]

    def spanned_cols(it):
        """Các cột mà ô gộp chứa chữ này phủ lên (vd. 'Khối lượng' phủ 4 cột)."""
        for c in grid.get("cells", []):
            if c[0] <= it["cx"] <= c[2] and c[1] <= it["cy"] <= c[3]:
                cols = [j for j in range(ncol) if c[0] - 2 <= centers[j] <= c[2] + 2]
                return cols or [col_of(it)]
        return [col_of(it)]

    def to_cells(group, replicate=False):
        buckets: Dict[int, List[Dict[str, Any]]] = {}
        for it in group:
            for c in (spanned_cols(it) if replicate else [col_of(it)]):
                buckets.setdefault(c, []).append(it)
        return [_join_items(buckets.get(c, [])) for c in range(ncol)]

    med_h = _median_h(items) if items else 12.0
    out: List[List[str]] = []
    seen_numbers = False
    for r in range(nrow):
        band = [it for it in items if row_of(it) == r]
        if not band:
            continue
        has_numbers = any(is_number_cell(it["text"]) for it in band)
        # Dải không số nằm TRƯỚC dải số liệu đầu tiên = tiêu đề cột: một hàng,
        # chữ của ô gộp được lặp cho mọi cột nó phủ ('Khối lượng' -> 4 cột con)
        if not has_numbers:
            out.append(to_cells(band, replicate=not seen_numbers))
            continue
        seen_numbers = True
        if re_[r + 1] - re_[r] <= 3.5 * med_h:
            out.append(to_cells(band))
            continue
        # Ô cao (bảng chỉ kẻ đường dọc): tách hàng theo "dòng khóa" có chữ ở >= 2
        # cột; dòng mô tả xuống dòng gắn vào dòng khóa gần nhất.
        lines = cluster_items_into_lines(band)
        keys = [l for l in lines if len({col_of(it) for it in l["items"]}) >= 2]
        if not keys:
            out.append(to_cells(band))
            continue
        groups: List[Tuple[float, List[Dict[str, Any]]]] = [(k["cy"], list(k["items"])) for k in keys]
        for l in lines:
            if any(l is k for k in keys):
                continue
            j = min(range(len(keys)), key=lambda i: abs(keys[i]["cy"] - l["cy"]))
            if abs(keys[j]["cy"] - l["cy"]) <= 3.0 * med_h:
                groups[j][1].extend(l["items"])
            else:
                groups.append((l["cy"], list(l["items"])))      # vd. dòng 'Phần móng'
        for _, g in sorted(groups, key=lambda x: min(it["y_min"] for it in x[1])):
            out.append(to_cells(g))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Bảng đoán theo tọa độ chữ (dự phòng khi không có lưới kẻ)
# ─────────────────────────────────────────────────────────────────────────────
def is_genuine_table(lines: List[Dict[str, Any]]) -> bool:
    """Chỉ nhận là bảng khi thật sự là bảng số liệu, không ép thuyết minh 2 cột thành bảng."""
    if len(lines) < 2:
        return False
    total_items = sum(len(l["items"]) for l in lines)
    avg_cols = total_items / len(lines)
    if avg_cols < 2.0:
        return False

    header_keywords = [
        "STT", "SOHIEU", "DUONGKINH", "CHIEUDAI", "SOLUONG", "TRONGLUONG", "KHOILUONG",
        "MAHIEU", "DONGIA", "THANHTIEN", "DONVI", "HANGMUC", "LYTRINH", "COC",
        "FDAO", "FDAP", "XIMANG", "DOSUT", "MAC", "WBS", "COTTHEP", "BETONG",
        "D10", "D12", "D14", "D16", "D32", "TENTHANH", "TONGCONG", "KYHIEU",
    ]
    all_key = fold_key(" ".join(it["text"] for l in lines for it in l["items"]))
    has_header_kw = any(kw in all_key for kw in header_keywords)

    num_cells = numeric_or_code_cells = long_prose_cells = 0
    for l in lines:
        for it in l["items"]:
            num_cells += 1
            t = it["text"].strip()
            if is_number_cell(t) or len(t) <= 15:
                numeric_or_code_cells += 1
            if len(t) > 35:
                long_prose_cells += 1

    density = numeric_or_code_cells / num_cells if num_cells else 0
    prose_ratio = long_prose_cells / num_cells if num_cells else 0
    if prose_ratio > 0.15:
        return False
    if avg_cols >= 3.0 and density >= 0.40:
        return True
    return has_header_kw and avg_cols >= 2.5


def text_table_rows(table_lines: List[Dict[str, Any]], col_tolerance: float = 45.0) -> List[List[str]]:
    """Gom cột theo tọa độ X của chữ (dùng khi bảng không có đường kẻ)."""
    if not table_lines:
        return []
    all_xs = sorted(it["x_min"] for l in table_lines for it in l["items"])
    all_ws = [it.get("w", 0) for l in table_lines for it in l["items"] if it.get("w", 0) > 0]
    med_w = statistics.median(all_ws) if all_ws else 60.0
    effective_tol = max(20.0, med_w * 0.45) if (col_tolerance <= 0 or col_tolerance == 45.0) else col_tolerance

    col_clusters: List[Dict[str, Any]] = []
    for x in all_xs:
        for c in col_clusters:
            if abs(x - c["mean"]) < effective_tol:
                c["points"].append(x)
                c["mean"] = sum(c["points"]) / len(c["points"])
                break
        else:
            col_clusters.append({"mean": x, "points": [x]})
    col_clusters.sort(key=lambda c: c["mean"])
    num_cols = len(col_clusters)

    rows: List[List[str]] = []
    for l in table_lines:
        cells: List[List[Dict[str, Any]]] = [[] for _ in range(num_cols)]
        for it in l["items"]:
            best = min(range(num_cols), key=lambda i: abs(it["x_min"] - col_clusters[i]["mean"]))
            if it["text"].strip():
                cells[best].append(it)
        rows.append([_cell(" ".join(it["text"].strip() for it in c), _items_box(c)) for c in cells])
    return rows


def format_table_block(table_lines: List[Dict[str, Any]], col_tolerance: float = 45.0) -> str:
    """Tương thích ngược: bảng Markdown từ các dòng chữ."""
    t = make_table(text_table_rows(table_lines, col_tolerance), "", None, "text")
    if not t:
        return "\n".join(" ".join(it["text"] for it in l["items"]) for l in table_lines)
    return table_to_markdown(t)


# ─────────────────────────────────────────────────────────────────────────────
# Văn bản thường
# ─────────────────────────────────────────────────────────────────────────────
_HEADING_RE = re.compile(r"^(?:[0-9]{1,2}\.(?:[0-9]{1,2}\.?)*\s+[A-ZÀ-Ỹ]|[IVX]{1,5}\.\s|[a-e]\)\s|"
                         r"(?:DỰ ÁN|GÓI THẦU|CÔNG TRÌNH|HẠNG MỤC|HỒ SƠ|PHẦN|CHƯƠNG|MỤC|"
                         r"DU AN|GOI THAU|CONG TRINH|HANG MUC|HO SO|PHAN|CHUONG|MUC)\b)")


def is_heading_line(text: str) -> bool:
    """Tiêu đề mục: '1. GIỚI THIỆU', 'II. ', 'PHẦN ...'. Số liệu như '12.5 m' không phải tiêu đề."""
    t = text.strip()
    if not t or len(t) > 120 or is_number_cell(t):
        return False
    if _HEADING_RE.match(t):
        return True
    # Bản không dấu ('CONG TRINH') chỉ tính khi từ đầu viết HOA, tránh câu thường 'công trình hay...'
    if t.split()[0].isupper() and _HEADING_RE.match(fold_upper(t)):
        return True
    letters = [c for c in t if c.isalpha()]
    return len(letters) >= 8 and all(c.isupper() for c in letters) and not re.search(r"\d{3,}", t)


_LIST_ITEM_RE = re.compile(r"^(?:[+\-*•]|[a-zđ]\)\s|\d{1,2}[.)]?\s+\S|[IVX]{1,4}[.)]?\s+[A-ZÀ-Ỹ])")


def starts_list_item(text: str) -> bool:
    """Dòng mở đầu một mục: '+ ...', '- ...', 'a) ...', '1 Kiểm toán', 'II Tải trọng'."""
    return bool(_LIST_ITEM_RE.match(text.strip()))


def render_column_paragraphs(items: List[Dict[str, Any]]) -> str:
    """Kết xuất một cột chữ thành các đoạn văn / danh sách."""
    blocks: List[str] = []
    curr: List[str] = []
    for l in cluster_items_into_lines(items):
        line_txt = " ".join(it["text"] for it in l["items"]).strip()
        if not line_txt:
            continue
        if is_heading_line(line_txt):
            if curr:
                blocks.append(" ".join(curr)); curr = []
            blocks.append(f"### {line_txt}")
        elif starts_list_item(line_txt):
            if curr:
                blocks.append(" ".join(curr)); curr = []
            curr.append(line_txt)
        elif curr and curr[-1].endswith((".", ":", ";")):
            blocks.append(" ".join(curr)); curr = [line_txt]
        else:
            curr.append(line_txt)
    if curr:
        blocks.append(" ".join(curr))
    return "\n\n".join(blocks)


def render_scattered_text(items: List[Dict[str, Any]]) -> str:
    """
    Chữ rời rạc trên bản vẽ -> danh sách gạch đầu dòng. Chữ cùng hàng nhưng cách
    xa nhau (thuộc hình vẽ khác nhau) được tách thành mục riêng.
    """
    return "\n".join(f"- {t}" for t in scattered_segments(items))


def scattered_segments(items: List[Dict[str, Any]], gap_factor: float = 3.0) -> List[str]:
    """Các cụm chữ theo dòng, cắt tại khoảng trống ngang lớn (> gap_factor × cỡ chữ)."""
    # Model OCR gốc tiếng Trung đôi khi đọc ký hiệu hình vẽ thành chữ Hán -> rác
    items = [it for it in items if not re.fullmatch(r"[\u3000-\u9fff\uff00-\uffef\W]*", it["text"])]
    if not items:
        return []
    max_gap = max(25.0, _median_h(items) * gap_factor)
    out: List[str] = []
    for line in cluster_items_into_lines(items):
        segment: List[Dict[str, Any]] = []
        for it in line["items"]:
            if segment and it["x_min"] - segment[-1]["x_max"] > max_gap:
                out.append(" ".join(s["text"] for s in segment))
                segment = []
            segment.append(it)
        if segment:
            out.append(" ".join(s["text"] for s in segment))
    return [t for t in out if t.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Khung tên, dấu thẩm định, siêu dữ liệu bản vẽ
# ─────────────────────────────────────────────────────────────────────────────
TITLE_BLOCK_KW = [
    "HOSOTHIETKE", "CHUCDANH", "HOVATEN", "CHUKY", "TYLEBANVE", "BANVESO", "BANVES6", "BANVES0",
    "LANXUATBAN", "CNTK", "CHUNHIEM", "CHUNHIEMTHIETKE", "KIEMTRA", "GIAMDOC", "CHUDAUTU",
    "TUVANTHIETKE", "DONVITUVAN", "COQUANTHIETKE", "DONVITHIETKE", "GOITHAU", "TENCONGTRINH",
    "SOAT", "CTTHIETKE", "BANVETHICONG", "KYHIEUBANVE", "TENBANVE", "GIAIDOANTHIETKE",
    "THEHIEN", "THIETKEBANVE", "QUANLYKYTHUAT", "THOIGIANHOANTHANH", "NGAYHOANTHANH",
    "CANBOTHIETKE", "NGUOIVE", "NGUOIKIEM", "TRUONGPHONG", "CHUTRIBOMON", "DONVITHAMTRA"
]
TITLE_BLOCK_STRONG_KW = {
    "CHUCDANH", "HOVATEN", "CHUKY", "TYLEBANVE", "BANVESO", "BANVES6", "BANVES0", "LANXUATBAN",
    "CNTK", "KYHIEUBANVE", "TENBANVE", "CHUNHIEM", "CHUNHIEMTHIETKE", "GIAIDOANTHIETKE",
    "THEHIEN", "COQUANTHIETKE", "DONVITHIETKE", "CHUDAUTU", "GIAMDOC", "QUANLYKYTHUAT",
    "TUVANTHIETKE", "CHUTRIBOMON", "CANBOTHIETKE", "NGUOIVE", "NGUOIKIEM", "TRUONGPHONG"
}
STAMP_KW = ["THAMDINH", "PHEDUYET", "SOGIAOTHONG", "GIAOTHONGVANTAI", "VANTAI", "THEOVANBAN",
            "QLCLCT", "KYTEN", "THAMTRA", "KHOATHAMTRA", "BAOCAOKETQUA", "KETQUATHAMTRA", "DONVITHAMTRA"]

COVER_PAGE_KW = [
    "HOSOTHIETKE", "THIETKEBANVETHICONG", "BANVETHICONG", "BAOCAOKINHTEKYTHUAT",
    "BAOCAONGHIENCUUKHATHTHI", "HOSOMOITHAU", "HOSOYEUCAU", "THIETKEKITHUAT",
    "THIETKEKYTHUATTHICONG", "HOSOTHICONG", "BANVETHOICONG"
]
COVER_AVOID_KW = [
    "MATDUNG", "MATBANG", "MATCAT", "THONGKECOTTHEP", "TRACDOC", "TRACNGANG", "CHITIET"
]


def is_cover_page(items: List[Dict[str, Any]], page_num: int = 1) -> bool:
    """Nhận diện Tờ bìa / Trang bìa hồ sơ thiết kế công trình xây dựng Việt Nam.
    Chỉ áp dụng cho trang đầu tiên (page_num == 1) hoặc trang 2 nếu không có khung tên CAD."""
    if page_num > 2:
        return False
    # Nếu trang chứa các nhãn khung tên bản vẽ kỹ thuật CAD thì chắc chắn KHÔNG phải bìa
    all_key = fold_key(" ".join(it["text"] for it in items))
    tb_drawing_kw = ["TENBANVE", "GIAIDOANTHIETKE", "CHUNHIEMTHIETKE", "QUANLYKYTHUAT",
                     "THEHIEN", "NGUOIVE", "TYLEBANVE", "BANVESO"]
    if sum(1 for kw in tb_drawing_kw if kw in all_key) >= 2:
        return False

    # Bìa thường có số lượng item ít (< 65 items)
    if len(items) > 65:
        return False

    has_cover_kw = any(kw in all_key for kw in COVER_PAGE_KW)
    if not has_cover_kw:
        if page_num == 1 and ("CONGTRINH" in all_key or "DUAN" in all_key) and ("CHUDAUTU" in all_key or "TUVAN" in all_key or "THIETKE" in all_key):
            has_cover_kw = True
    if not has_cover_kw:
        return False
    avoid_hits = sum(1 for kw in COVER_AVOID_KW if kw in all_key)
    return avoid_hits == 0


def extract_cover_metadata(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Trích xuất thông tin tổng thể của dự án/công trình từ tờ bìa."""
    meta: Dict[str, Any] = {}
    lines = [l["items"] for l in cluster_items_into_lines(items)]
    full_lines = [" ".join(it["text"] for it in line).strip() for line in lines if line]
    joined_text = "\n".join(full_lines)

    for i, line in enumerate(full_lines):
        line_k = fold_key(line)
        # 1. Công trình
        if any(k in line_k for k in ["CONGTRINH", "DUAN", "TENCONGTRINH"]) and "cong_trinh" not in meta:
            v = _search(r"(?:CONG\s*TRINH|DU\s*AN|TEN\s*CONG\s*TRINH)\s*[:.]?\s*(.+)$", line)
            if v and len(v) > 3 and not any(bad in fold_key(v) for bad in ["THEOVANBAN", "SO", "NGAY"]):
                meta["cong_trinh"] = v
            elif i + 1 < len(full_lines):
                nxt = full_lines[i + 1]
                if not any(k in fold_key(nxt) for k in ["HANGMUC", "CHUDAUTU", "THEOVANBAN"]):
                    meta["cong_trinh"] = nxt

        # 2. Hạng mục
        if "HANGMUC" in line_k and "hang_muc" not in meta:
            v = _search(r"HANG\s*MUC\s*[:.]?\s*(.+)$", line)
            if v and len(v) > 2:
                meta["hang_muc"] = v
            elif i + 1 < len(full_lines):
                meta["hang_muc"] = full_lines[i + 1]

        # 3. Chủ đầu tư
        if "CHUDAUTU" in line_k and "chu_dau_tu" not in meta:
            v = _search(r"CHU\s*DAU\s*TU\s*[:.]?\s*(.+)$", line)
            if v and len(v) > 2:
                meta["chu_dau_tu"] = v
            elif i + 1 < len(full_lines):
                meta["chu_dau_tu"] = full_lines[i + 1]

        # 4. Tư vấn thiết kế
        if any(k in line_k for k in ["COQUANTHIETKE", "DONVITHIETKE", "TUVANTHIETKE", "TUVANXAYDUNG", "XAYDUNGVATHIETKE"]) and "don_vi_thiet_ke" not in meta:
            meta["don_vi_thiet_ke"] = line

        # 5. Địa điểm
        if any(k in line_k for k in ["DIADIEM", "DIACHI"]) and "dia_diem" not in meta:
            v = _search(r"(?:DIA\s*DIEM|DIA\s*CHI)\s*[:.]?\s*(.+)$", line)
            if v and len(v) > 2:
                meta["dia_diem"] = v
            elif i + 1 < len(full_lines):
                meta["dia_diem"] = full_lines[i + 1]

    m_nam = re.search(r"\b(202\d|19\d\d)\b", joined_text)
    if m_nam and "nam" not in meta:
        meta["nam"] = m_nam.group(1)

    for gd in ["THIẾT KẾ BẢN VẼ THI CÔNG", "THIẾT KẾ KỸ THUẬT THI CÔNG", "THIẾT KẾ CƠ SỞ", "BÁO CÁO KINH TẾ KỸ THUẬT"]:
        if fold_key(gd) in fold_key(joined_text):
            meta["giai_doan"] = gd
            break

    return meta


def render_cover_page(items: List[Dict[str, Any]], meta: Dict[str, Any]) -> str:
    """Kết xuất trang bìa thành Markdown trang trọng, gọn gàng, loại bỏ hoàn toàn bảng rác."""
    sections = []
    giai_doan = meta.get("giai_doan", "HỒ SƠ THIẾT KẾ BẢN VẼ THI CÔNG")
    sections.append(f"# 📑 {giai_doan.upper()}")

    details = []
    if meta.get("cong_trinh"):
        details.append(f"- **Công trình / Dự án:** {meta['cong_trinh']}")
    if meta.get("hang_muc"):
        details.append(f"- **Hạng mục:** {meta['hang_muc']}")
    if meta.get("chu_dau_tu"):
        details.append(f"- **Chủ đầu tư:** {meta['chu_dau_tu']}")
    if meta.get("don_vi_thiet_ke"):
        details.append(f"- **Đơn vị tư vấn thiết kế:** {meta['don_vi_thiet_ke']}")
    if meta.get("dia_diem"):
        details.append(f"- **Địa điểm xây dựng:** {meta['dia_diem']}")
    if meta.get("nam"):
        details.append(f"- **Thời gian / Năm thực hiện:** {meta['nam']}")

    if details:
        sections.append("\n".join(details))

    other_lines = []
    for l in cluster_items_into_lines(items):
        txt = " ".join(it["text"] for it in l["items"]).strip()
        if not txt or any(txt == meta.get(k) for k in meta):
            continue
        if len(txt) > 3 and txt not in other_lines:
            other_lines.append(txt)

    if other_lines:
        sections.append("> **Thông tin khác trên trang bìa:**\n" + "\n".join(f"> - {t}" for t in other_lines[:15]))

    return "\n\n".join(sections)


def find_title_block(items, grids, min_x, min_y, page_w, page_h):
    """Khung tên: vùng chứa >= 2 từ khóa khung tên, nằm ở đáy hoặc mép phải trang.
    Trả về (tb_items, tb_grids): danh sách chữ khung tên và TẤT CẢ các lưới kẻ ô thuộc khung tên."""
    zone = [it for it in items
            if it["cy"] >= min_y + 0.65 * page_h or it["cx"] >= min_x + 0.72 * page_w]
    anchors, hits = [], set()
    for it in zone:
        key = fold_key(it["text"])
        found = [kw for kw in TITLE_BLOCK_KW if kw in key]
        if found:
            anchors.append(it)
            hits.update(found)

    strong_hits = hits & TITLE_BLOCK_STRONG_KW
    if len(hits) < 2 or not strong_hits:
        return [], []

    # Khung tên CAD chuẩn:
    # 1. Góc dưới phải (x0 >= min_x + 0.50*pw, y0 >= min_y + 0.60*ph)
    # 2. Dải mép phải (x0 >= min_x + 0.75*pw, w <= 0.25*pw)
    # 3. Dải đáy mép dưới (y0 >= min_y + 0.82*ph, h <= 0.18*ph)
    # Tuyệt đối không nhận bảng số liệu phủ > 55% bề rộng trang mà không ở đáy
    matched_grids = []
    for g in grids:
        x0, y0, x1, y1 = g["bbox"]
        w, h = x1 - x0, y1 - y0
        if w > 0.55 * page_w and y0 < min_y + 0.80 * page_h:
            continue
        inside = [a for a in anchors if x0 <= a["cx"] <= x1 and y0 <= a["cy"] <= y1]
        is_br_corner = (x0 >= min_x + 0.50 * page_w and y0 >= min_y + 0.60 * page_h)
        is_right_strip = (x0 >= min_x + 0.75 * page_w and w <= 0.25 * page_w)
        is_bottom_strip = (y0 >= min_y + 0.82 * page_h and h <= 0.18 * page_h)
        if not (is_br_corner or is_right_strip or is_bottom_strip):
            continue
        if len(inside) >= 2 or (len(inside) >= 1 and (is_right_strip or is_br_corner)):
            matched_grids.append(g)

    if matched_grids:
        gx0 = min(g["bbox"][0] for g in matched_grids) - 5
        gy0 = min(g["bbox"][1] for g in matched_grids) - 5
        gx1 = max(g["bbox"][2] for g in matched_grids) + 5
        gy1 = max(g["bbox"][3] for g in matched_grids) + 5
        region = (gx0, gy0, gx1, gy1)
        tb_grids = matched_grids
    else:
        # Nếu không có lưới bao quanh khung tên, gom các anchor nằm đúng vùng khung tên
        tb_anchors = [a for a in anchors if (a["cx"] >= min_x + 0.50 * page_w and a["cy"] >= min_y + 0.60 * page_h)
                      or a["cx"] >= min_x + 0.75 * page_w or a["cy"] >= min_y + 0.82 * page_h]
        if not tb_anchors:
            return [], []
        pad = 2 * _median_h(tb_anchors)
        region = (min(a["x_min"] for a in tb_anchors) - pad, min(a["y_min"] for a in tb_anchors) - pad,
                  max(a["x_max"] for a in tb_anchors) + pad, max(a["y_max"] for a in tb_anchors) + pad)
        tb_grids = []

    tb_items = [it for it in items if region[0] <= it["cx"] <= region[2] and region[1] <= it["cy"] <= region[3]]
    return tb_items, tb_grids


def find_stamp(items, excluded_ids, page_w, page_h):
    """Dấu thẩm định: gom quanh chữ 'THẨM ĐỊNH' / 'SỞ GIAO THÔNG' ở bất kỳ vị trí nào."""
    pool = [it for it in items if id(it) not in excluded_ids]
    # Chữ neo phải ngắn (tiêu đề con dấu), không phải câu văn có cụm 'được phê duyệt'
    short = [it for it in pool if len(it["text"]) <= 40]
    mains = [it for it in short if has_kw(it["text"], ["THAMDINH", "PHEDUYET", "THAMTRA"])] or \
            [it for it in short if has_kw(it["text"], ["SOGIAOTHONG"])]
    if not mains:
        return []
    main = mains[0]
    med_h = _median_h(pool)
    related = [it for it in short
               if abs(it["cy"] - main["cy"]) <= 10 * med_h and abs(it["cx"] - main["cx"]) <= 0.2 * page_w
               and (has_kw(it["text"], STAMP_KW) or
                    (has_kw(it["text"], ["NGAY"]) and has_kw(it["text"], ["THANG", "NAM"])))]
    related = related or [main]
    x0 = min(it["x_min"] for it in related) - med_h
    x1 = max(it["x_max"] for it in related) + med_h
    y0 = min(it["y_min"] for it in related) - med_h * 0.5
    y1 = max(it["y_max"] for it in related) + med_h * 0.5
    # Mọc thêm các dòng liền kề nằm trong cùng cột (vd. dòng 'SỞ GIAO THÔNG…'
    # bị OCR đọc sai nên không khớp từ khóa), tối đa ~16 dòng chữ.
    for _ in range(3):
        grow = [it for it in pool if x0 <= it["cx"] <= x1
                and y0 - 2.5 * med_h <= it["cy"] <= y1 + 2.5 * med_h
                and not (y0 <= it["cy"] <= y1)]
        if not grow or (y1 - y0) > 16 * med_h:
            break
        y0 = min([y0] + [it["y_min"] - med_h * 0.3 for it in grow])
        y1 = max([y1] + [it["y_max"] + med_h * 0.3 for it in grow])
    return [it for it in pool if x0 <= it["cx"] <= x1 and y0 <= it["cy"] <= y1]


def _search(pattern: str, text: str, group: int = 1) -> Optional[str]:
    """Tìm trên bản bỏ dấu, trả về đoạn chữ GỐC (có dấu) tương ứng."""
    m = re.search(pattern, fold_upper(text))
    if not m:
        return None
    return text[m.start(group):m.end(group)].strip(" :.-|")


def extract_sheet_metadata(tb_items: List[Dict[str, Any]], all_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    if not tb_items:
        return meta

    tb_lines = cluster_items_into_lines(tb_items)
    lines_txt = [" ".join(it["text"] for it in l["items"]).strip() for l in tb_lines if l["items"]]
    joined = " | ".join(lines_txt)

    # 1. Trích xuất regex cho số hiệu, tỷ lệ, ngày tháng, giai đoạn
    v = _search(r"(?:BAN\s*VE\s*S[O06]|KY\s*HIEU\s*BAN\s*VE|SO\s*HIEU)\s*[:.]?\s*([A-Z]{1,6}\s*[-.]\s*\d+[A-Z0-9.\-/]*|\d+[A-Z0-9.\-/]*)", joined)
    if v:
        meta["so_hieu_ban_ve"] = re.sub(r"\s+", "", v)
    else:
        m_code = re.search(r"\b(KT[\s.\-_]*\d+[A-Z0-9.\-/]*|KC[\s.\-_]*\d+[A-Z0-9.\-/]*|XLNT[\s.\-_]*\d+[A-Z0-9.\-/]*|KT[.]{1,3})\b", joined, re.I)
        if m_code:
            meta["so_hieu_ban_ve"] = re.sub(r"\s+", "", m_code.group(1))

    if "so_hieu_ban_ve" in meta:
        s = meta["so_hieu_ban_ve"]
        s = re.sub(r"[.\-_]+", "-", s).strip("-")
        s = re.sub(r"\b([A-Z]{2,4})-(\d)\b", r"\1-0\2", s)
        meta["so_hieu_ban_ve"] = s

    v = _search(r"TY\s*L[E3]\s*(?:BAN\s*VE)?\s*[:.]?\s*(1\s*[/:]\s*\d+|KTL|KT)", joined)
    if v:
        meta["ty_le"] = re.sub(r"\s+", "", v)

    v = _search(r"LAN\s*XUAT\s*BAN\s*[:.]?\s*(\d+)", joined)
    if v:
        meta["lan_xuat_ban"] = v

    m = re.search(r"NGAY\W{0,8}(\d{1,2})\W{0,8}THANG\W{0,8}(\d{1,2})\W{0,8}NAM\W{0,4}(\d{4})", fold_upper(joined))
    if m:
        meta["ngay"] = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    else:
        m = re.search(r"(?:THOI\s*GIAN|NAM)\W{0,4}((?:19|20)\d\d)", fold_upper(joined))
        if m:
            meta["nam"] = m.group(1)

    m_gd = re.search(r"GIAI\s*DOAN[^\w]*(TK[A-Z0-9.\-/]+|T\.K\.[A-Z0-9.\-/]+|BVTC|THIET\s*KE[^\n|]+)", joined, re.I)
    if m_gd:
        meta["giai_doan"] = m_gd.group(1).strip()

    # 2. Quét tuần tự theo các mục nhãn của khung tên CAD Việt Nam
    SECTION_RULES = [
        ("COQUANTHIETKE", "don_vi_thiet_ke"),
        ("DONVITHIETKE", "don_vi_thiet_ke"),
        ("TUVANTHIETKE", "don_vi_thiet_ke"),
        ("TENCONGTRINH", "cong_trinh"),
        ("CONGTRINH", "cong_trinh"),
        ("CHUNHIEMTHIETKE", "chu_nhiem"),
        ("CHUNHIEM", "chu_nhiem"),
        ("QUANLYKYTHUAT", "quan_ly_ky_thuat"),
        ("TENBANVE", "ten_ban_ve"),
        ("THEHIEN", "the_hien"),
        ("NGUOIVE", "the_hien"),
        ("CHUDAUTU", "chu_dau_tu"),
        ("HANGMUC", "hang_muc"),
        ("DIADIEM", "dia_chi"),
        ("DIACHI", "dia_chi"),
    ]

    for i, line in enumerate(lines_txt):
        k = fold_key(line)
        if any(bad in k for bad in ["GIAMDOC", "TNHH", "TRANG", "GHICHU"]):
            continue

        matched_field = None
        for sk, field in SECTION_RULES:
            if sk in k and field not in meta:
                val_inline = _search(rf"{sk}\s*[:.]?\s*(.+)$", line)
                if val_inline and len(val_inline) > 2:
                    meta[field] = val_inline
                else:
                    matched_field = field
                break

        if matched_field and matched_field not in meta:
            val_parts = []
            for j in range(i + 1, min(i + 4, len(lines_txt))):
                nxt = lines_txt[j].strip()
                nxt_k = fold_key(nxt)
                if any(sk in nxt_k for sk, _ in SECTION_RULES) or any(bad in nxt_k for bad in ["GIAIDOAN", "THOIGIAN", "GIAMDOC", "TNHH"]):
                    break
                val_parts.append(nxt)
            if val_parts:
                meta[matched_field] = " ".join(val_parts)

    title = _sheet_title(tb_items)
    if title and "ten_ban_ve" not in meta:
        meta["ten_ban_ve"] = title

    ly_trinh = []
    for it in all_items:
        for m in re.finditer(r"KM\s*\d+\s*\+\s*\d+(?:[.,]\d+)?", fold_upper(it["text"])):
            v = re.sub(r"\s+", "", it["text"][m.start():m.end()])
            if v not in ly_trinh:
                ly_trinh.append(v)
    if ly_trinh:
        meta["ly_trinh"] = ly_trinh
    return meta


def _sheet_title(tb_items: List[Dict[str, Any]]) -> Optional[str]:
    """Tên bản vẽ: dòng chữ ngay phía trên ô 'Tỷ lệ bản vẽ', cùng cột."""
    anchors = [it for it in tb_items if has_kw(it["text"], ["TYLEBANVE", "BANVESO", "TENBANVE"])]
    if not anchors:
        return None
    anchor = min(anchors, key=lambda it: it["x_min"])
    med_h = _median_h(tb_items)
    cands = [it for it in tb_items
             if it["y_max"] <= anchor["y_min"] + 2 and it["cx"] >= anchor["x_min"] - 2 * med_h
             and not re.search(r"KM\s*\d", fold_upper(it["text"]))
             and not has_kw(it["text"], ["CONGTY", "CTY", "GIAMDOC", "NGAY", "THANG"])]
    if not cands:
        return None
    lines = cluster_items_into_lines(cands)
    picked = [lines[-1]]
    for l in reversed(lines[:-1]):
        if len(picked) >= 3 or picked[0]["cy"] - l["cy"] > 2.2 * med_h:
            break
        picked.insert(0, l)
    return " ".join(" ".join(it["text"] for it in l["items"]) for l in picked).strip() or None


def render_title_block_banner(meta: Dict[str, Any]) -> str:
    """Tạo banner bản vẽ kỹ thuật gọn gàng, súc tích thay vì in hàng chục gạch đầu dòng lặp đi lặp lại."""
    so_hieu = meta.get("so_hieu_ban_ve", "—")
    ten_bv = meta.get("ten_ban_ve", "Bản vẽ chi tiết")
    ty_le = meta.get("ty_le", "KT")
    giai_doan = meta.get("giai_doan", "")

    header_line = f"> 📐 **Bản vẽ:** `{so_hieu}` — **{ten_bv.upper()}** | **Tỷ lệ:** {ty_le}"
    if giai_doan:
        header_line += f" | **Giai đoạn:** {giai_doan}"

    parts = [header_line]
    sub_info = []
    if meta.get("cong_trinh"):
        sub_info.append(f"**Công trình:** {meta['cong_trinh']}")
    if meta.get("chu_dau_tu"):
        sub_info.append(f"**Chủ đầu tư:** {meta['chu_dau_tu']}")
    if meta.get("don_vi_thiet_ke"):
        sub_info.append(f"**Đơn vị thiết kế:** {meta['don_vi_thiet_ke']}")
    if meta.get("chu_nhiem"):
        sub_info.append(f"**Chủ nhiệm:** {meta['chu_nhiem']}")

    if sub_info:
        parts.append("> " + " · ".join(sub_info))

    return "\n".join(parts)


def render_title_block(tb_items, meta) -> str:
    """Tương thích ngược: trả về banner bản vẽ gọn gàng."""
    return render_title_block_banner(meta)


def render_stamp(stamp_items) -> str:
    lines = cluster_items_into_lines(stamp_items, y_tolerance=8.0)
    txt = "\n> ".join(" ".join(x["text"] for x in l["items"]) for l in lines)
    return f"> **DẤU THẨM ĐỊNH / PHÊ DUYỆT:**\n> {txt}"


# ─────────────────────────────────────────────────────────────────────────────
# Bản vẽ CAD
# ─────────────────────────────────────────────────────────────────────────────
CAD_KW = ["TYLE", "MATDUNG", "MATBANG", "MATCAT", "CHITIET", "THONGKECOTTHEP", "THONGKECHITIET",
          "HOSOTHIETKE", "BANVETHICONG", "TVTK", "LANCAN", "THOATNUOC", "BANVESO", "CHUCDANH", "TRACDOC",
          "TRACNGANG", "BOTRICOTTHEP", "CATNGANG", "MATCATNGANG", "MCN", "NENDUONG", "DAPNEN", "DAONEN",
          "TRACDIA", "TUVANXAYDUNG", "CHUTRI", "THAMTRA", "KYTEN", "THIETKE"]
VIEW_KW = ["MATDUNG", "MATBANG", "MATCAT", "CHITIET", "HOPTHU", "TRACDOC", "TRACNGANG", "BOTRI", "CATNGANG", "MATCATNGANG"]


def is_cad_drawing_sheet(items: List[Dict[str, Any]], page_w: float, page_h: float) -> bool:
    """Bản vẽ kỹ thuật: khổ ngang, có tiêu đề hình vẽ / khung tên / tỷ lệ."""
    if len(items) < 15:
        return False
    # Thuyết minh (kể cả khổ ngang 2 cột) có nhiều dòng câu văn dài; bản vẽ chủ yếu là nhãn ngắn
    long_ratio = sum(1 for it in items if len(it["text"]) > 45) / len(items)
    if long_ratio > 0.20:
        return False
    key = fold_key(" ".join(it["text"] for it in items))
    kw_count = sum(1 for kw in CAD_KW if kw in key)
    is_landscape = (page_w / page_h) >= 1.20
    return (is_landscape and kw_count >= 2) or kw_count >= 4


def _text_tables_by_keyword(items, excluded, ctx):
    """Bảng không kẻ ô: tìm tiêu đề 'BẢNG/THỐNG KÊ/KHỐI LƯỢNG' rồi gom chữ phía dưới."""
    med_h = _median_h(items)
    headers = [it for it in items if id(it) not in excluded and len(it["text"]) < 90
               and has_kw(it["text"], ["BANG", "THONGKE", "KHOILUONG"])]
    for hdr in sorted(headers, key=lambda it: it["cy"]):
        if id(hdr) in excluded:
            continue
        region = [it for it in items if id(it) not in excluded and it is not hdr
                  and hdr["x_min"] - 3 * med_h <= it["cx"] <= hdr["x_max"] + 12 * med_h
                  and hdr["y_max"] - 2 <= it["cy"] <= hdr["y_max"] + 25 * med_h]
        if len(region) < 6:
            continue
        lines = cluster_items_into_lines(region, y_tolerance=max(6.0, med_h * 0.5))
        if not is_genuine_table(lines):
            continue
        t = make_table(text_table_rows(lines, col_tolerance=35.0), hdr["text"],
                       [min(i["x_min"] for i in region), hdr["y_min"],
                        max(i["x_max"] for i in region), max(i["y_max"] for i in region)], "text")
        if t:
            excluded.add(id(hdr))
            excluded.update(id(it) for it in region)
            ctx["tables"].append(t)


# ─────────────────────────────────────────────────────────────────────────────
# Phân tích trang
# ─────────────────────────────────────────────────────────────────────────────
def split_items_on_columns(items: List[Dict[str, Any]], grids: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cắt hộp chữ vắt qua đường kẻ cột của bảng (vd. '217 Lắp dựng...' dính số
    thứ tự vào cột tên công việc). Cần vị trí từng ký tự (lớp chữ PDF)."""
    out: List[Dict[str, Any]] = []
    for it in items:
        chars = it.get("chars")
        edges: List[float] = []
        if chars:
            for g in grids:
                x0, y0, x1, y1 = g["bbox"]
                if y0 <= it["cy"] <= y1 and it["x_max"] > x0 and it["x_min"] < x1:
                    # Chỉ cắt tại đường kẻ có thật ở độ cao dòng chữ này (không cắt
                    # tiêu đề nhóm nằm trong ô gộp phủ nhiều cột như 'Khối lượng')
                    borders = [v for c in g["cells"] if c[1] - 2 <= it["cy"] <= c[3] + 2 for v in (c[0], c[2])]
                    edges += [e for e in g["col_edges"][1:-1] if it["x_min"] + 1 < e < it["x_max"] - 1
                              and any(abs(e - v) <= 4 for v in borders)]
        if not edges:
            out.append(it)
            continue
        edges.sort()
        pieces: List[List[Tuple[str, Optional[float], Optional[float]]]] = [[] for _ in range(len(edges) + 1)]
        idx = 0
        for ch, cx0, cx1 in chars:
            if cx0 is not None:
                idx = bisect_right(edges, (cx0 + cx1) / 2)
            pieces[idx].append((ch, cx0, cx1))
        for piece in pieces:
            text = "".join(ch for ch, _, _ in piece).strip()
            xs = [v for _, a, b in piece for v in (a, b) if v is not None]
            if not text or not xs:
                continue
            box = [[min(xs), it["y_min"]], [max(xs), it["y_min"]], [max(xs), it["y_max"]], [min(xs), it["y_max"]]]
            out.append(extract_box_metrics(box, text, it["score"]))
    return out


def _grid_title(grid, items, excluded, med_h) -> Tuple[str, List[Dict[str, Any]]]:
    """Tiêu đề bảng: 1–2 dòng chữ ngay phía trên lưới, chồng lấn theo chiều ngang."""
    x0, y0, x1, y1 = grid["bbox"]
    span = x1 - x0
    cands = [it for it in items if id(it) not in excluded
             and y0 - 5 * med_h <= it["y_max"] <= y0 + med_h * 0.5
             and x0 - 0.1 * span <= it["cx"] <= x1 + 0.1 * span]
    cands = [it for it in cands if not any(kw in fold_key(it["text"])
             for kw in ["KYTEN", "CHUKY", "CHUTRI", "BOMON", "THAMTRA", "THAMDINH", "PHEDUYET", "GIAMDOC", "CHUDAUTU"])]
    if not cands:
        return "", []
    lines = cluster_items_into_lines(cands)[-2:]
    title_lines = []
    for l in lines:
        ltxt = " ".join(it["text"] for it in l["items"]).strip()
        if any(kw in fold_key(ltxt) for kw in ["BANG", "THONGKE", "KHOILUONG", "DANHMUC", "TOADO", "BANGKE"]):
            title_lines.append(l)
    if not title_lines:
        text_cands = [l for l in lines if not re.fullmatch(r"^[\d.,\s\-/+xX*#()]+$", " ".join(it["text"] for it in l["items"]).strip())]
        title_lines = [text_cands[-1]] if text_cands else []
    else:
        title_lines = title_lines[-1:]
    used = [it for l in title_lines for it in l["items"]]
    title_res = " ".join(" ".join(it["text"] for it in l["items"]) for l in title_lines).strip()
    if re.fullmatch(r"^[\d.,\s\-/+xX*#()]+$", title_res) or len(title_res) < 3:
        return "", []
    return title_res, used


def is_suspicious_for_review(it: Dict[str, Any], stamp_ids: set, tb_ids: set) -> bool:
    """
    Bộ lọc khử báo động giả thông minh cho can_kiem_tra.md:
    Chỉ giữ lại các nghi vấn thực sự:
    1. Xung đột số liệu 2 bộ OCR (ALT_OPEN) không phải con dấu hành chính lặp lại.
    2. Chữ/số bị garbled hoặc điểm tin cậy rất thấp (< 0.55).
    Loại bỏ:
    - Con dấu hành chính và khung tên đã nhận diện.
    - Ký tự rác CJK, hạt bụi dấu câu (? ★ △ ° .).
    - Kích thước hình học thuần túy (800, 1000, 300, 810) có score >= 0.50.
    - Ký hiệu trục bản vẽ / số hiệu thanh đơn lẻ (A, B, C, 0, 1, 2) có score >= 0.50.
    - Ký hiệu đường kính / cốt thép (D10, D19, Phi14, Phi20) có score >= 0.55.
    - Tên mặt cắt, tỷ lệ bản vẽ kỹ thuật (TỶ LỆ 1/50, MẶT CẮT I-I).
    """
    txt = it["text"].strip()
    score = it.get("score", 1.0)
    it_id = id(it)

    # 1. Bỏ qua nếu thuộc vùng con dấu hoặc khung tên đã nhận diện
    if it_id in stamp_ids or it_id in tb_ids:
        return False

    # 2. Xung đột 2 bộ OCR
    if ALT_OPEN in txt:
        # Bỏ qua nếu là con dấu hành chính lặp lại
        if any(k in txt.upper() for k in ["SGTVT", "QLCLCT", "THEO VAN BAN", "THEO VĂN BẢN", "GIAO THONG", "GIAO THÔNG", "NAM 202", "NĂM 202"]):
            return False
        return True

    # Nếu score >= LOW_CONFIDENCE (0.75) thì đạt chuẩn tin cậy
    if score >= LOW_CONFIDENCE:
        return False

    # 3. Ký tự CJK chữ Hán
    if re.search(r"[\u4e00-\u9fff]", txt):
        return False

    # 4. Loại bỏ hạt bụi dấu câu, ký hiệu đơn lẻ
    if txt in list("?★△.°)~-+/*=,;:[]{}'\"") or re.fullmatch(r"[\W_]+", txt):
        return False

    # 5. Chữ hành chính dấu thẩm định
    if any(k in txt.upper() for k in ["SGTVT", "QLCLCT", "THEO VAN BAN", "THEO VĂN BẢN", "GIAO THONG", "GIAO THÔNG"]):
        return False

    # 6. Kích thước hình học thuần túy (vd: 800, 810, 1000, 15., 7.) với score >= 0.50
    if re.fullmatch(r"^\d{1,6}([.,]\d*)?$", txt) and score >= 0.50:
        return False

    # 7. Ký hiệu trục tròn / số hiệu thanh đơn lẻ (A, B, C, 0, 1, 2, 8) với score >= 0.50
    if len(txt) == 1 and score >= 0.50:
        return False

    # 8. Mã hiệu ngắn 2-4 ký tự (BI, B1, VII, 10b, pp) với score >= 0.50
    if re.fullmatch(r"^[A-Za-z0-9_]{2,4}$", txt) and score >= 0.50:
        return False

    # 9. Ký hiệu cốt thép (D10, D19, Phi14, Phi20, D10(F), D10G1) với score >= 0.55
    if re.fullmatch(r"^(D|Φ|φ)\d{1,2}[A-Za-z0-9_() -]*$", txt) and score >= 0.55:
        return False

    # 10. Tên mặt cắt / Tỷ lệ bản vẽ
    if any(kw in txt.upper() for kw in ["TY LE", "TỶ LỆ", "MAT CAT", "MẶT CẮT", "CẮT"]):
        return False

    # 11. Ký hiệu kỹ thuật và đơn vị thường gặp
    if txt in ["(ww)", "(wu)", "(s/eu)", "om", "bi", "da", "dao", "rn", "rL", "AC"]:
        return False

    return True


def analyze_page(ocr_res: List[Any], image=None, factor: float = 1.0, dpi: float = 200.0, page_num: int = 1) -> Dict[str, Any]:
    """
    Phân tích một trang từ danh sách hộp chữ [[box, text, score], ...].
    image/factor/dpi: ảnh trang (tùy chọn) để dò bảng kẻ ô; factor quy đổi pixel
    ảnh -> hệ tọa độ của box.
    page_num: số thứ tự trang (1-indexed) để nhận biết trang bìa.

    Trả về {markdown, tables, metadata, low_confidence, layout}.
    """
    empty = {"markdown": "", "tables": [], "metadata": {}, "low_confidence": [], "layout": "empty"}
    items = []
    for entry in ocr_res or []:
        if not entry or len(entry) < 2:
            continue
        text = str(entry[1]).strip()
        # Khử chữ Hán rác (CJK) do RapidOCR sinh ra từ vết lem mực, mộc dấu hoặc nét vẽ CAD
        if re.search(r"[\u4e00-\u9fff]", text):
            text = re.sub(r"[\u4e00-\u9fff]+", "", text).strip()
        if not text:
            continue
        score = float(entry[2]) if len(entry) > 2 else 1.0
        it = extract_box_metrics(entry[0], text, score)
        if len(entry) > 3 and entry[3]:
            it["chars"] = entry[3]          # [(ký tự, x0, x1)] từ lớp chữ PDF
        items.append(it)
    if not items:
        return empty

    # 0. Kiểm tra Tờ bìa / Trang bìa hồ sơ công trình
    if is_cover_page(items, page_num=page_num):
        meta = extract_cover_metadata(items)
        markdown = render_cover_page(items, meta)
        low = [it for it in items if it.get("score", 1.0) < 0.50]
        return {
            "markdown": markdown.strip(),
            "tables": [],
            "metadata": meta,
            "low_confidence": low,
            "layout": "cover_page"
        }

    min_x = min(it["x_min"] for it in items); max_x = max(it["x_max"] for it in items)
    min_y = min(it["y_min"] for it in items); max_y = max(it["y_max"] for it in items)
    page_w, page_h = max(1.0, max_x - min_x), max(1.0, max_y - min_y)
    med_h = _median_h(items)

    cad = is_cad_drawing_sheet(items, page_w, page_h)
    grids = []
    if image is not None:
        from table_grid import detect_ruled_tables
        grids = detect_ruled_tables(image, factor, dpi, allow_tall=not cad)
    if grids:
        items = split_items_on_columns(items, grids)

    ctx: Dict[str, Any] = {"tables": []}
    tb_items, tb_grids = find_title_block(items, grids, min_x, min_y, page_w, page_h)
    excluded = set(id(it) for it in tb_items)
    tb_grid_set = set(id(g) for g in tb_grids)
    if tb_items:
        cad = True

    # Chữ nằm trong lưới bảng kẻ ô không thuộc dấu thẩm định
    in_grids = set()
    for g in grids:
        if id(g) in tb_grid_set:
            continue
        gx0, gy0, gx1, gy1 = g["bbox"]
        g_items = [it for it in items if gx0 <= it["cx"] <= gx1 and gy0 <= it["cy"] <= gy1]
        if any(has_kw(it["text"], ["THAMDINH", "PHEDUYET", "SOGIAOTHONG", "THAMTRA"]) for it in g_items):
            continue
        in_grids.update(id(it) for it in g_items)
    stamp_items = find_stamp(items, excluded | in_grids, page_w, page_h)
    excluded.update(id(it) for it in stamp_items)

    # Bảng kẻ ô: chỉ nhận lưới có chữ ở >= 15% số ô
    for g in grids:
        if id(g) in tb_grid_set:
            continue
        x0, y0, x1, y1 = g["bbox"]
        inside = [it for it in items if id(it) not in excluded
                  and x0 <= it["cx"] <= x1 and y0 <= it["cy"] <= y1]
        if len(inside) < 3:
            continue
        # Content safety net: loại trừ khung tên nếu chữ bên trong chứa >= 2 từ khóa khung tên mạnh
        inside_key = fold_key(" ".join(it["text"] for it in inside))
        if sum(1 for kw in TITLE_BLOCK_STRONG_KW if kw in inside_key) >= 2:
            continue
        filled = sum(1 for c in g["cells"]
                     if any(c[0] <= it["cx"] <= c[2] and c[1] <= it["cy"] <= c[3] for it in inside))
        if filled < max(3, 0.15 * len(g["cells"])):
            continue
        title, title_items = _grid_title(g, items, excluded | set(id(it) for it in inside), med_h)
        t = make_table(grid_table_rows(g, inside), title, g["bbox"], "grid")
        if not t or (not t["header"] and len(t["rows"]) <= 3):
            continue
        # Trên bản vẽ CAD: phân biệt bảng kỹ thuật thật sự với hình vẽ mặt bằng/kết cấu chia ô
        if cad:
            is_table_by_title = has_kw(t.get("title", ""), ["BANG", "THONGKE", "KHOILUONG", "DANHMUC", "TOADO", "BANGKE", "QUYCACH", "CHITIEU"])
            header_str = fold_key(" ".join(t.get("header") or []))
            is_table_by_header = any(kw in header_str for kw in [
                "STT", "KYHIEU", "TENTHANH", "DUONGKINH", "CHIEUDAI", "SOLUONG",
                "TRONGLUONG", "KHOILUONG", "DONVI", "DONGIA", "THANHTIEN", "GIAIDOAN", "SOHIEU"
            ])
            if not is_table_by_title and not is_table_by_header:
                continue
        ctx["tables"].append(t)
        excluded.update(id(it) for it in inside)
        excluded.update(id(it) for it in title_items)

    meta = extract_sheet_metadata(tb_items, items)

    if cad:
        markdown = _render_cad(items, excluded, ctx, stamp_items, tb_items, meta, min_y, page_h)
        layout = "cad_drawing"
    else:
        markdown, layout = _render_document(items, excluded, ctx, stamp_items, tb_items, meta,
                                            min_x, min_y, page_w, page_h)

    low = []
    stamp_ids = set(id(it) for it in stamp_items)
    tb_ids = set(id(it) for it in tb_items)
    for g in tb_grids:
        gx0, gy0, gx1, gy1 = g["bbox"]
        for it in items:
            if gx0 <= it["cx"] <= gx1 and gy0 <= it["cy"] <= gy1:
                tb_ids.add(id(it))

    for it in items:
        if is_suspicious_for_review(it, stamp_ids, tb_ids):
            low.append({"text": it["text"], "score": round(it["score"], 3),
                        "bbox": [round(it["x_min"], 1), round(it["y_min"], 1),
                                 round(it["x_max"], 1), round(it["y_max"], 1)]})
    if low:
        shown = " · ".join(f"`{x['text']}`" for x in low[:30])
        more = f" (và {len(low) - 30} mục khác)" if len(low) > 30 else ""
        markdown += (f"\n\n> ⚠️ **Cần đối chiếu bản gốc** — OCR độ tin cậy thấp: {shown}{more}")

    return {"markdown": markdown.strip(), "tables": ctx["tables"], "metadata": meta,
            "low_confidence": low, "layout": layout}


def _render_cad(items, excluded, ctx, stamp_items, tb_items, meta, min_y, page_h) -> str:
    sections: List[str] = []
    # Đặt banner bản vẽ kỹ thuật lên đầu trang
    if tb_items or meta:
        sections.append(render_title_block_banner(meta))

    view_items = [it for it in items if id(it) not in excluded and len(it["text"]) < 80
                  and has_kw(it["text"], VIEW_KW)
                  and (has_kw(it["text"], ["TYLE", "TL1"]) or it["y_min"] < min_y + 0.45 * page_h
                       or it["h"] >= 1.3 * _median_h(items))]
    if view_items:
        sections.append("### CÁC HÌNH VẼ KỸ THUẬT")
        sections.append("\n".join(f"- **{v['text']}**" for v in sorted(view_items, key=lambda x: (x["cy"], x["cx"]))))
        excluded.update(id(v) for v in view_items)

    _text_tables_by_keyword(items, excluded, ctx)
    for t in ctx["tables"]:
        sections.append(f"### {t['title']}\n\n{table_to_markdown(t)}")

    # Mọi chữ còn lại (ghi chú, kích thước, cao độ, lý trình...) KHÔNG được bỏ.
    leftover = [it for it in items if id(it) not in excluded]
    leftover_md = render_scattered_text(leftover)
    if leftover_md:
        sections.append(f"### GHI CHÚ / CHỮ KHÁC TRÊN BẢN VẼ\n\n{leftover_md}")
    if stamp_items:
        sections.append(render_stamp(stamp_items))
    return "\n\n".join(sections)


def _render_document(items, excluded, ctx, stamp_items, tb_items, meta,
                     min_x, min_y, page_w, page_h) -> Tuple[str, str]:
    flow = [it for it in items if id(it) not in excluded]
    placed: List[Tuple[float, str]] = [(t["bbox"][1] if t["bbox"] else 0.0,
                                        (f"**{t['title']}**\n\n" if not t["title"].startswith("Bảng (") else "")
                                        + table_to_markdown(t))
                                       for t in ctx["tables"]]
    layout = "document"

    split_x = min_x + page_w * 0.5
    header_y_max = min_y + max(40.0, page_h * 0.15)
    footer_y_min = min_y + page_h - max(30.0, page_h * 0.08)
    mid = [it for it in flow if header_y_max < it["cy"] < footer_y_min]
    crossing = [it for it in mid if it["x_min"] < split_x < it["x_max"]]
    left = [it for it in mid if it["cx"] < split_x]
    right = [it for it in mid if it["cx"] >= split_x]
    two_col = (len(mid) >= 6 and len(crossing) <= max(1, len(mid) * 0.06)
               and len(left) >= len(mid) * 0.20 and len(right) >= len(mid) * 0.20)

    if two_col:
        layout = "two_column"

        def spans_middle(it):
            return it["x_min"] < split_x < it["x_max"] or abs(it["cx"] - split_x) < 0.12 * page_w

        # Đầu/chân trang: chỉ chữ vắt qua giữa hoặc nằm giữa trang; phần còn lại thuộc cột
        header = [it for it in flow if it["cy"] <= header_y_max and spans_middle(it)]
        footer = [it for it in flow if it["cy"] >= footer_y_min and spans_middle(it)]
        edge = [it for it in flow if (it["cy"] <= header_y_max or it["cy"] >= footer_y_min) and not spans_middle(it)]
        left = sorted(left + [it for it in edge if it["cx"] < split_x], key=lambda it: it["cy"])
        right = sorted(right + [it for it in edge if it["cx"] >= split_x], key=lambda it: it["cy"])
        parts = [render_column_paragraphs(x) for x in (header, left, right)]
        parts += [md for _, md in sorted(placed)]
        parts.append(render_column_paragraphs(footer))
        body = "\n\n".join(p for p in parts if p)
    else:
        all_lines = cluster_items_into_lines(flow)
        blocks: List[Tuple[float, str]] = list(placed)
        pending: List[Dict[str, Any]] = []
        last_para: Optional[Tuple[int, float]] = None      # (vị trí trong blocks, cy dòng cuối)
        line_h = _median_h(flow) if flow else 12.0

        def flush():
            nonlocal pending, last_para
            if not pending:
                return
            last_para = None
            if is_genuine_table(pending):
                t = make_table(text_table_rows(pending), "", None, "text")
                if t:
                    ctx["tables"].append(t)
                    blocks.append((pending[0]["cy"], table_to_markdown(t)))
                    pending = []
                    return
            for l in pending:
                blocks.append((l["cy"], " ".join(it["text"] for it in l["items"])))
            pending = []

        for l in all_lines:
            row = l["items"]
            if len(row) >= 3 or (len(row) == 2 and all(len(it["text"]) <= 30 for it in row)):
                pending.append(l)
                continue
            flush()
            text = " ".join(it["text"] for it in row).strip()
            if not text:
                continue
            if is_heading_line(text):
                blocks.append((l["cy"], f"### {text}"))
                last_para = None
                continue
            bullet = starts_list_item(text)
            # Dòng tiếp của cùng đoạn: sát dòng trên và dòng trên chưa kết thúc câu
            if (last_para is not None and not bullet and l["cy"] - last_para[1] <= 1.9 * line_h
                    and not blocks[last_para[0]][1].endswith((".", ":", ";", "?", "!"))):
                y, md = blocks[last_para[0]]
                blocks[last_para[0]] = (y, md + " " + text)
                last_para = (last_para[0], l["cy"])
            else:
                blocks.append((l["cy"], text))
                last_para = (len(blocks) - 1, l["cy"])
        flush()
        body = "\n\n".join(md for _, md in sorted(blocks, key=lambda b: b[0]))

    extra = []
    if stamp_items:
        extra.append(render_stamp(stamp_items))
    if tb_items:
        extra.append(render_title_block(tb_items, meta))
    return "\n\n".join([body] + extra), layout


def reconstruct_page_layout(ocr_res: List[Any], page_width: float = 0.0) -> str:
    """Tương thích ngược: chỉ trả Markdown (không dò bảng kẻ ô vì không có ảnh)."""
    return analyze_page(ocr_res)["markdown"]


# ─────────────────────────────────────────────────────────────────────────────
# PDF có lớp chữ (pdftext) -> hộp chữ cho analyze_page
# ─────────────────────────────────────────────────────────────────────────────
def rotate_bbox(b, k: int, W: float, H: float) -> List[float]:
    """Xoay bbox (gốc trên-trái, trang W×H điểm) k lần 90° để chữ về nằm ngang.
    Khớp với ảnh.rotate(90) khi k=1, rotate(-90) khi k=3, rotate(180) khi k=2."""
    x0, y0, x1, y1 = b
    if k == 1:
        return [y0, W - x1, y1, W - x0]
    if k == 3:
        return [H - y1, x0, H - y0, x1]
    if k == 2:
        return [W - x1, H - y1, W - x0, H - y0]
    return [x0, y0, x1, y1]


def pdftext_page_to_boxes(page_dict: Dict[str, Any], scale: float) -> Tuple[List[List[Any]], int]:
    """Chuyển dictionary_output(keep_chars=True) của pdftext thành [[box, text, 1.0]].

    - Font TCVN3 (.VnTime...) và VNI (VNI-Times...) được chuyển sang Unicode.
    - Trang có chữ xoay (bản vẽ CAD in dọc giấy): xoay hệ tọa độ theo hướng chữ
      chiếm đa số để chữ về nằm ngang. Trả kèm k (số lần xoay 90°) để xoay ảnh
      trang tương ứng: k=1 -> ảnh.rotate(90), k=3 -> ảnh.rotate(-90), k=2 -> 180.
    - Ký tự được ghép lại theo khoảng cách thật (không theo dòng của pdftext) để
      mỗi ô bảng / cụm chữ thành một hộp, từ không bị cắt đôi.
    """
    from vn_legacy import (is_tcvn3_font, is_upper_font, looks_like_tcvn3, tcvn3_to_unicode,
                           is_vni_font, looks_like_vni, vni_merge)

    W = float(page_dict.get("width") or 0) or 1.0
    H = float(page_dict.get("height") or 0) or 1.0
    chars: List[Dict[str, Any]] = []
    fallback: List[List[Any]] = []
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not any(sp.get("chars") for sp in spans):
                text = "".join(sp.get("text", "") for sp in spans).strip()
                if text and line.get("bbox"):
                    fallback.append({"text": text, "bbox": line["bbox"]})
                continue
            for sp in spans:
                font = (sp.get("font") or {}).get("name") or ""
                enc = "tcvn" if is_tcvn3_font(font) else "vni" if is_vni_font(font) else None
                upper = is_upper_font(font)
                for c in sp.get("chars") or []:
                    ch = c.get("char", "")
                    if enc == "tcvn":
                        ch = tcvn3_to_unicode(ch, upper)
                    chars.append({"ch": ch, "bbox": list(c["bbox"]), "enc": enc})

    # Font không khai tên rõ nhưng nội dung là mã cũ: VNI kiểm trước (dấu hiệu đặc trưng hơn)
    plain = "".join(c["ch"] for c in chars if not c["enc"])
    if looks_like_vni(plain):
        for c in chars:
            c["enc"] = c["enc"] or "vni"
    elif looks_like_tcvn3(plain):
        for c in chars:
            if not c["enc"]:
                c["ch"] = tcvn3_to_unicode(c["ch"])

    # VNI: gộp ký tự dấu vào chữ gốc đứng trước (cả chữ lẫn bbox)
    if any(c["enc"] == "vni" for c in chars):
        merged: List[Dict[str, Any]] = []
        i = 0
        while i < len(chars):
            if chars[i]["enc"] != "vni":
                merged.append(chars[i]); i += 1
                continue
            j = i
            while j < len(chars) and chars[j]["enc"] == "vni":
                j += 1
            seg = chars[i:j]
            for text, idx in vni_merge([c["ch"] for c in seg]):
                bbs = [seg[k]["bbox"] for k in idx]
                merged.append({"ch": text, "enc": "vni",
                               "bbox": [min(b[0] for b in bbs), min(b[1] for b in bbs),
                                        max(b[2] for b in bbs), max(b[3] for b in bbs)]})
            i = j
        chars = merged

    # Hướng đọc chiếm đa số: so vị trí các ký tự liên tiếp
    votes = [0, 0, 0, 0]
    for a, b in zip(chars, chars[1:]):
        dx = (b["bbox"][0] + b["bbox"][2] - a["bbox"][0] - a["bbox"][2]) / 2
        dy = (b["bbox"][1] + b["bbox"][3] - a["bbox"][1] - a["bbox"][3]) / 2
        if abs(dx) + abs(dy) == 0 or abs(dx) + abs(dy) > 50:
            continue
        if abs(dx) >= abs(dy):
            votes[0 if dx > 0 else 2] += 1
        else:
            votes[1 if dy > 0 else 3] += 1
    k = max(range(4), key=lambda i: votes[i]) if sum(votes) else 0
    if votes[k] < 1.5 * votes[0]:
        k = 0

    def rot(b):
        return rotate_bbox(b, k, W, H)

    out: List[List[Any]] = []

    def emit(text, bbox, char_pos=None):
        text = text.strip()
        if not text:
            return
        x0, y0, x1, y1 = (v * scale for v in bbox)
        out.append([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, 1.0, char_pos])

    run: List[Dict[str, Any]] = []
    pending_space = False

    def run_text_of(run) -> str:
        """Quyết định dấu cách giữa các ký tự của một cụm.
        Chữ giãn cách ký tự ('P H Ò N G  K I Ể M'): khoảng cách giữa các chữ cái đều
        nhau -> chỉ tách từ ở khoảng rộng hơn hẳn mức trung bình."""
        gaps = [c["gap"] for c in run[1:]]
        hs = sorted(c["b"][3] - c["b"][1] for c in run)
        h = max(hs[len(hs) // 2], 1.0)
        spaced = False
        if len(run) >= 4 and gaps:
            g = sorted(gaps)[len(gaps) // 2]
            explicit = sum(1 for c in run[1:] if c["sp"]) / len(gaps)
            spaced = g > 0.25 * h or explicit > 0.6
            word_gap = max(1.8 * g, g + 0.35 * h)
        text = run[0]["ch"]
        for c in run[1:]:
            if spaced:
                brk = c["gap"] > word_gap
            else:
                brk = c["sp"] or c["gap"] > 0.6 * h
            text += (" " if brk else "") + c["ch"]
        return text

    def flush():
        nonlocal run
        if run:
            run_text = run_text_of(run)
            # Vị trí từng ký tự (để cắt tại đường kẻ cột); dấu cách không có vị trí
            char_pos, i = [], 0
            # Ký tự ghép (vd. 'ﬁ') làm lệch vị trí -> bỏ thông tin vị trí cho cụm này
            aligned = len(run_text.replace(" ", "")) == len(run)
            for ch in (run_text if aligned else ""):
                if ch == " ":
                    char_pos.append((" ", None, None))
                else:
                    b = run[i]["b"]
                    char_pos.append((ch, b[0] * scale, b[2] * scale))
                    i += 1
            emit(run_text, [min(c["b"][0] for c in run), min(c["b"][1] for c in run),
                            max(c["b"][2] for c in run), max(c["b"][3] for c in run)], char_pos or None)
        run = []

    for c in chars:
        ch = c["ch"]
        if not ch or ch.isspace():
            pending_space = True
            continue
        b = rot(c["bbox"])
        c = {"ch": ch, "b": b, "gap": 0.0, "sp": False}
        if run:
            p = run[-1]["b"]
            h = max(p[3] - p[1], b[3] - b[1], 1.0)
            same_line = abs((b[1] + b[3]) / 2 - (p[1] + p[3]) / 2) < 0.6 * h
            gap = b[0] - p[2]
            if same_line and -0.5 * h <= gap <= 1.2 * h:
                c["gap"], c["sp"] = gap, pending_space
                run.append(c)
                pending_space = False
                continue
            flush()
        run, pending_space = [c], False
    flush()
    for f in fallback:
        emit(f["text"], rot(f["bbox"]))
    return out, k


# ─────────────────────────────────────────────────────────────────────────────
# Đóng gói tài liệu & chia đoạn cho AI
# ─────────────────────────────────────────────────────────────────────────────
def format_full_markdown_document(pages: List[Dict[str, Any]]) -> str:
    """Đóng gói danh sách trang thành tài liệu Markdown với tiêu đề trang rõ ràng."""
    md_parts: List[str] = []
    for idx, p in enumerate(pages):
        page_num = p.get("page", idx + 1)
        meta = p.get("metadata") or {}
        sheet = " · ".join(x for x in [meta.get("so_hieu_ban_ve"), meta.get("ten_ban_ve")] if x)
        title = f"## [Trang {page_num}]" + (f" {sheet}" if sheet else "")
        body = (p.get("markdown") or p.get("text", "")).strip()
        md_parts.append(f"<!-- Page {page_num} -->\n{title}\n\n{body}\n")
    return "\n".join(md_parts)


def chunk_markdown(markdown: str, max_chars: int = 3000) -> List[Tuple[str, str]]:
    """Chia Markdown một trang theo mục '### '. Mục quá dài: bảng cắt theo hàng
    (lặp lại dòng tiêu đề cột), văn bản cắt theo đoạn. Trả [(tên_mục, nội_dung)]."""
    sections: List[Tuple[str, List[str]]] = [("", [])]
    for line in markdown.splitlines():
        if line.startswith("### "):
            sections.append((line[4:].strip(), [line]))
        else:
            sections[-1][1].append(line)

    chunks: List[Tuple[str, str]] = []
    for name, lines in sections:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if len(text) <= max_chars:
            chunks.append((name, text))
            continue
        buf: List[str] = []
        table_head: List[str] = []
        prefix = f"### {name} (tiếp)" if name else ""
        size, prev_row = 0, False
        for line in lines:
            is_row = line.startswith("|")
            if is_row:
                if not prev_row:
                    table_head = [line]
                elif len(table_head) == 1 and re.match(r"^\|\s*-", line):
                    table_head.append(line)
            elif line.strip():
                table_head = []
            prev_row = is_row
            if size + len(line) > max_chars and buf:
                chunks.append((name, "\n".join(buf).strip()))
                buf = [prefix] if prefix else []
                if is_row and len(table_head) == 2 and line not in table_head:
                    buf += table_head
                size = sum(len(x) + 1 for x in buf)
            buf.append(line)
            size += len(line) + 1
        if "\n".join(buf).strip():
            chunks.append((name, "\n".join(buf).strip()))
    return chunks
