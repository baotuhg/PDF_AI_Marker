# -*- coding: utf-8 -*-
"""
AEC Table Intelligence & Management Agent for PDF AI Marker v3
Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG)

Chuyên trách:
1. Phân loại bảng biểu bản vẽ kỹ thuật xây dựng Việt Nam (4 nhóm chuẩn: Cốt thép BBS, Khối lượng BoQ, Danh mục bản vẽ, Tọa độ & Thông số).
2. Thẩm tra và kiểm tra chéo logic số liệu (TCVN 1651:2018 cho cốt thép, cân bằng khối lượng BoQ).
3. Xuất file Excel 'bang_so_lieu.xlsx' phân tầng đa cấp (Mục lục hyperlink, Sheet Tổng hợp thép, Sheet BoQ, Sheet Tọa độ, các Sheet chi tiết).
4. Xuất dữ liệu chuẩn JSON sẵn sàng nạp thẳng vào bộ kỹ năng 'aec-rebar-optimizer' và 'aec-cost-tender'.
"""
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# ĐỊNH NGHĨA PHÂN LOẠI BẢNG BIỂU CHUẨN AEC
# ─────────────────────────────────────────────────────────────────────────────
CAT_REBAR = "rebar"
CAT_BOQ = "boq"
CAT_SHEET_INDEX = "sheet_index"
CAT_SPECS = "specs"
CAT_GENERAL = "general"

CATEGORY_METADATA = {
    CAT_REBAR: {
        "name": "Thống kê Cốt thép",
        "icon": "🔩",
        "sheet_title": "🔩 Tổng hợp Cốt Thép",
        "color": "1F4E79",  # Xanh dương đậm kỹ thuật
    },
    CAT_BOQ: {
        "name": "Tổng hợp Khối lượng (BoQ)",
        "icon": "🧱",
        "sheet_title": "🧱 Tổng hợp Khối Lượng",
        "color": "385723",  # Xanh rêu công trường
    },
    CAT_SHEET_INDEX: {
        "name": "Danh mục Bản vẽ",
        "icon": "📑",
        "sheet_title": "📑 Danh mục Bản Vẽ",
        "color": "833C0C",  # Nâu hồ sơ
    },
    CAT_SPECS: {
        "name": "Tọa độ & Thông số Kỹ thuật",
        "icon": "📐",
        "sheet_title": "📐 Tọa độ & Thông Số",
        "color": "7030A0",  # Tím trắc địa / kỹ thuật
    },
    CAT_GENERAL: {
        "name": "Bảng số liệu khác",
        "icon": "📊",
        "sheet_title": "📊 Bảng Số Liệu Chung",
        "color": "595959",
    },
}

# Trọng lượng lý thuyết thép xây dựng theo TCVN 1651:2018 (kg/m)
TCVN_REBAR_WEIGHTS = {
    6: 0.222,
    8: 0.395,
    10: 0.617,
    12: 0.888,
    14: 1.208,
    16: 1.578,
    18: 1.998,
    20: 2.466,
    22: 2.984,
    25: 3.853,
    28: 4.834,
    32: 6.313,
    36: 7.990,
    40: 9.870,
}


def _strip_accents(s: str) -> str:
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).upper()


def _extract_number(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(" ", "").replace(",", ".")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. AI TABLE CLASSIFIER AGENT (AGENT PHÂN LOẠI BẢNG)
# ─────────────────────────────────────────────────────────────────────────────
class AECTableClassifier:
    """Agent phân tích tiêu đề, cấu trúc cột, đơn vị tính để phân nhóm bảng biểu."""

    REBAR_TITLE_KEYWORDS = [
        "THONG KE COT THEP", "THONG KE THEP", "BANG KE THEP", "COT THEP",
        "BANG THEP", "REBAR", "STEEL SCHEDULE", "THEP DAM", "THEP COT",
        "THEP SAN", "THEP MONG", "THEP BE TONG", "THEP GIA CUONG"
    ]
    REBAR_COL_KEYWORDS = [
        "DUONG KINH", "PHI", "FI", "DIA", "D (MM)", "HINH DANG",
        "HINH DANG THANH", "SO THANH", "SO LUONG", "CHIEU DAI",
        "TONG CHIEU DAI", "TRONG LUONG", "KHOI LUONG", "KG"
    ]

    BOQ_TITLE_KEYWORDS = [
        "KHOI LUONG", "TIEN LUONG", "TONG HOP KHOI LUONG", "BANG BOQ",
        "BILL OF QUANTITIES", "TAKEOFF", "DU TOAN", "GIA DU THAU",
        "TONG HOP VAT TU", "KHOI LUONG XAY LAP"
    ]
    BOQ_COL_KEYWORDS = [
        "HANG MUC", "TEN CONG VIEC", "NOI DUNG CONG VIEC", "DON VI", "DVT",
        "KHOI LUONG", "DON GIA", "THANH TIEN", "M3", "M2", "TAN"
    ]

    INDEX_TITLE_KEYWORDS = [
        "DANH MUC BAN VE", "DANH SACH BAN VE", "BANG KE BAN VE",
        "MUC LUC BAN VE", "SHEET INDEX", "DRAWING LIST", "DANH MUC HO SO"
    ]
    INDEX_COL_KEYWORDS = [
        "SO HIEU BAN VE", "KY HIEU BAN VE", "TEN BAN VE", "TY LE", "GIAI DOAN", "NGAY"
    ]

    SPECS_TITLE_KEYWORDS = [
        "TOA DO", "TIM COC", "COC KHOAN NHOI", "CHI TIEU CO LY",
        "THONG SO KY THUAT", "TAI TRONG", "MAC BE TONG", "CAP DO BEN", "SPECS"
    ]
    SPECS_COL_KEYWORDS = [
        "TOA DO X", "TOA DO Y", "CAO DO", "MUC NUOC", "SUC CHIU TAI", "DO SUT"
    ]

    @classmethod
    def classify(cls, table: Dict[str, Any]) -> Tuple[str, str, float]:
        """
        Phân tích bảng và trả về: (category_code, category_name, confidence_score)
        """
        title = _strip_accents(str(table.get("title", "")))
        headers = [_strip_accents(str(h)) for h in (table.get("header") or [])]
        header_text = " ".join(headers)
        all_text = title + " " + header_text

        # 1. Điểm số Thống kê Cốt thép
        rebar_score = 0
        if any(kw in title for kw in cls.REBAR_TITLE_KEYWORDS):
            rebar_score += 60
        rebar_hits = sum(1 for kw in cls.REBAR_COL_KEYWORDS if kw in header_text)
        rebar_score += rebar_hits * 15
        # Kiểm tra ký tự đặc biệt Phi Φ trong cột
        raw_header = " ".join(str(h) for h in (table.get("header") or []))
        if any(c in raw_header for c in ["Φ", "φ", "Ø", "ø", "Fi", "fi"]):
            rebar_score += 40

        # 2. Điểm số BoQ Khối lượng
        boq_score = 0
        if any(kw in title for kw in cls.BOQ_TITLE_KEYWORDS):
            boq_score += 55
        boq_hits = sum(1 for kw in cls.BOQ_COL_KEYWORDS if kw in header_text)
        boq_score += boq_hits * 14

        # 3. Điểm số Danh mục bản vẽ
        index_score = 0
        if any(kw in title for kw in cls.INDEX_TITLE_KEYWORDS):
            index_score += 70
        idx_hits = sum(1 for kw in cls.INDEX_COL_KEYWORDS if kw in header_text)
        index_score += idx_hits * 20

        # 4. Điểm số Tọa độ & Thông số
        specs_score = 0
        if any(kw in title for kw in cls.SPECS_TITLE_KEYWORDS):
            specs_score += 60
        specs_hits = sum(1 for kw in cls.SPECS_COL_KEYWORDS if kw in header_text)
        specs_score += specs_hits * 15

        # Phán quyết theo điểm số tối đa
        scores = [
            (CAT_REBAR, rebar_score),
            (CAT_BOQ, boq_score),
            (CAT_SHEET_INDEX, index_score),
            (CAT_SPECS, specs_score),
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        top_cat, top_score = scores[0]

        if top_score >= 40:
            confidence = min(1.0, top_score / 100.0)
            return top_cat, CATEGORY_METADATA[top_cat]["name"], confidence

        return CAT_GENERAL, CATEGORY_METADATA[CAT_GENERAL]["name"], 0.3


# ─────────────────────────────────────────────────────────────────────────────
# 2. AUDIT & CROSS-CHECK ENGINE (AGENT THẨM TRA LOGIC SỐ LIỆU)
# ─────────────────────────────────────────────────────────────────────────────
class AECTableAuditor:
    """Agent kiểm tra tính nhất quán toán học và quy chuẩn kỹ thuật của số liệu bóc tách."""

    @classmethod
    def audit(cls, table: Dict[str, Any], category: str) -> Dict[str, Any]:
        result = {
            "status": "ok",
            "warnings": [],
            "rebar_items": [],
            "rebar_summary": {},
            "boq_summary": {},
        }
        if category == CAT_REBAR:
            cls._audit_rebar(table, result)
        elif category == CAT_BOQ:
            cls._audit_boq(table, result)
        return result

    @classmethod
    def _audit_rebar(cls, table: Dict[str, Any], result: Dict[str, Any]):
        headers = [_strip_accents(str(h)) for h in (table.get("header") or [])]
        rows = table.get("rows") or []
        if not headers or not rows:
            return

        col_mark = cls._find_col(headers, ["KY HIEU", "TEN THANH", "SO HIEU", "MARK", "STT"])
        col_dia = cls._find_col(headers, ["DUONG KINH", "PHI", "FI", "DIA", "D (MM)"])
        col_len = cls._find_col(headers, ["CHIEU DAI", "CD (MM)", "CD (M)", "LENGTH"])
        col_qty = cls._find_col(headers, ["SO LUONG", "SO THANH", "QTY", "SL"])
        col_tot_len = cls._find_col(headers, ["TONG CHIEU DAI", "TONG CD", "TOTAL LENGTH"])
        col_weight = cls._find_col(headers, ["TRONG LUONG", "KHOI LUONG", "WEIGHT", "KG"])

        total_weight_reported = 0.0
        total_weight_calculated = 0.0
        weight_by_group = {"d_le_10": 0.0, "d_le_18": 0.0, "d_gt_18": 0.0}

        for idx, row in enumerate(rows, 1):
            dia_raw = row[col_dia] if (col_dia is not None and col_dia < len(row)) else None
            len_raw = row[col_len] if (col_len is not None and col_len < len(row)) else None
            qty_raw = row[col_qty] if (col_qty is not None and col_qty < len(row)) else None
            wt_raw = row[col_weight] if (col_weight is not None and col_weight < len(row)) else None
            mark_raw = row[col_mark] if (col_mark is not None and col_mark < len(row)) else f"Thanh {idx}"

            dia = _extract_number(dia_raw)
            length = _extract_number(len_raw)
            qty = _extract_number(qty_raw)
            weight = _extract_number(wt_raw)

            if dia is None:
                continue

            dia_int = int(round(dia))
            # 1. Phát hiện đường kính lạ
            if dia_int not in TCVN_REBAR_WEIGHTS:
                result["warnings"].append(
                    f"Dòng {idx} ({mark_raw}): Đường kính Φ{dia_int} bất thường ngoài TCVN (có thể OCR đọc lệch)."
                )

            unit_w = TCVN_REBAR_WEIGHTS.get(dia_int, (dia_int ** 2) / 162.0)
            calc_len_m = 0.0
            if length is not None and qty is not None:
                # Nếu chiều dài ghi bằng mm (> 100) thì đổi sang m
                l_m = (length / 1000.0) if length > 100 else length
                calc_len_m = l_m * qty
                calc_weight = calc_len_m * unit_w
                total_weight_calculated += calc_weight

                # Phân nhóm đường kính
                if dia_int <= 10:
                    weight_by_group["d_le_10"] += calc_weight
                elif dia_int <= 18:
                    weight_by_group["d_le_18"] += calc_weight
                else:
                    weight_by_group["d_gt_18"] += calc_weight

                # 2. Đối chiếu trọng lượng tính toán vs ghi trên bảng
                if weight is not None:
                    total_weight_reported += weight
                    if weight > 0 and abs(weight - calc_weight) / weight > 0.08:
                        result["warnings"].append(
                            f"Dòng {idx} ({mark_raw}): Bảng ghi {weight:.1f}kg, tính toán TCVN là {calc_weight:.1f}kg (lệch >8%)."
                        )

                # Thu thập bản ghi phục vụ aec-rebar-optimizer
                result["rebar_items"].append({
                    "mark": str(mark_raw),
                    "diameter": dia_int,
                    "length_mm": int(round(length if length > 100 else length * 1000)),
                    "quantity": int(round(qty)),
                    "total_weight_kg": round(calc_weight, 2),
                    "page": table.get("page", 1),
                    "sheet": table.get("sheet", ""),
                    "sheet_title": table.get("sheet_title", ""),
                })

        result["rebar_summary"] = {
            "total_bars": len(result["rebar_items"]),
            "calc_weight_kg": round(total_weight_calculated, 2),
            "reported_weight_kg": round(total_weight_reported, 2) if total_weight_reported > 0 else None,
            "weight_by_group": {k: round(v, 2) for k, v in weight_by_group.items()},
        }
        if result["warnings"]:
            result["status"] = "warning"

    @classmethod
    def _audit_boq(cls, table: Dict[str, Any], result: Dict[str, Any]):
        headers = [_strip_accents(str(h)) for h in (table.get("header") or [])]
        rows = table.get("rows") or []
        col_qty = cls._find_col(headers, ["KHOI LUONG", "KHOI LUONG THIET KE", "QTY", "KL"])
        col_price = cls._find_col(headers, ["DON GIA", "UNIT PRICE", "GIA"])
        col_amount = cls._find_col(headers, ["THANH TIEN", "TOTAL AMOUNT", "TONG TIEN"])

        total_amount = 0.0
        for idx, row in enumerate(rows, 1):
            if col_qty is not None and col_price is not None and col_amount is not None:
                q = _extract_number(row[col_qty]) if col_qty < len(row) else None
                p = _extract_number(row[col_price]) if col_price < len(row) else None
                a = _extract_number(row[col_amount]) if col_amount < len(row) else None
                if q is not None and p is not None and a is not None:
                    calc_a = q * p
                    total_amount += a
                    if a > 0 and abs(calc_a - a) / a > 0.05:
                        result["warnings"].append(
                            f"Dòng {idx}: Thành tiền ghi {a:,.0f}, tích KL x Đơn giá là {calc_a:,.0f}."
                        )
        result["boq_summary"] = {"total_amount": round(total_amount, 2), "total_items": len(rows)}
        if result["warnings"]:
            result["status"] = "warning"

    @staticmethod
    def _find_col(headers: List[str], keywords: List[str]) -> Optional[int]:
        for i, h in enumerate(headers):
            if any(kw in h for kw in keywords):
                return i
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-TIER EXCEL WORKBOOK EXPORTER (XUẤT EXCEL PHÂN NHÓM CHUYÊN NGHIỆP)
# ─────────────────────────────────────────────────────────────────────────────
def export_aec_excel(tables: List[Dict[str, Any]], excel_path: Path):
    """
    Xuất file bang_so_lieu.xlsx phân tầng 4 nhóm nghiệp vụ:
    - Sheet 1: 📑 Mục Lục Bảng Biểu (Interactive Index có Hyperlink)
    - Sheet 2: 🔩 Tổng Hợp Cốt Thép (Tổng bảng BBS toàn bộ công trình)
    - Sheet 3: 🧱 Tổng Hợp Khối Lượng (BoQ Master)
    - Sheet 4: 📐 Tọa Độ & Kỹ Thuật (Specs Master)
    - Các Sheet con chi tiết từng bảng
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return

    wb = openpyxl.Workbook()
    default_sheet = wb.active

    if not tables:
        ws = wb.create_sheet(title="Thông báo")
        ws.cell(row=1, column=1, value="Không tìm thấy bảng số liệu kẻ ô trong tài liệu này.")
        wb.remove(default_sheet)
        wb.save(str(excel_path))
        return

    # Style definitions
    font_brand = Font(name="Segoe UI", size=13, bold=True, color="FFFFFF")
    font_head = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    font_sub = Font(name="Segoe UI", size=9, italic=True, color="64748B")
    font_data = Font(name="Segoe UI", size=9.5)
    font_bold = Font(name="Segoe UI", size=9.5, bold=True)
    font_link = Font(name="Segoe UI", size=9.5, color="004C99", underline="single")

    fill_brand = PatternFill(start_color="0F2942", end_color="0F2942", fill_type="solid")
    fill_index_hdr = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_warn = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")

    # 1. Phân loại và thẩm tra toàn bộ bảng
    categorized: Dict[str, List[Dict[str, Any]]] = {
        CAT_REBAR: [], CAT_BOQ: [], CAT_SHEET_INDEX: [], CAT_SPECS: [], CAT_GENERAL: []
    }
    for idx, tbl in enumerate(tables, 1):
        cat, cat_name, conf = AECTableClassifier.classify(tbl)
        audit_res = AECTableAuditor.audit(tbl, cat)
        tbl["_id"] = idx
        tbl["_cat"] = cat
        tbl["_cat_name"] = cat_name
        tbl["_audit"] = audit_res
        categorized[cat].append(tbl)

    # 2. TẠO SHEET 1: MỤC LỤC BẢNG BIỂU (HYPERLINK NAVIGATION)
    ws_index = wb.create_sheet(title="📑 Mục Lục Bảng Biểu")
    wb.remove(default_sheet)

    ws_index.merge_cells("A1:H1")
    c_title = ws_index["A1"]
    c_title.value = "📑 HỆ THỐNG QUẢN LÝ BẢNG BIỂU CÔNG TRÌNH (AEC TABLE INTELLIGENCE)"
    c_title.font = font_brand
    c_title.fill = fill_brand
    c_title.alignment = align_left
    ws_index.row_dimensions[1].height = 30

    idx_headers = ["STT", "Bản vẽ", "Tên Bản vẽ", "Trang", "Tiêu đề Bảng", "Phân loại Nghiệp vụ", "Số dòng", "Thẩm tra Logic / Thao tác"]
    for c_i, h in enumerate(idx_headers, 1):
        c = ws_index.cell(row=2, column=c_i, value=h)
        c.font = font_head
        c.fill = fill_index_hdr
        c.alignment = align_center
        c.border = thin_border
    ws_index.row_dimensions[2].height = 24

    for r_i, tbl in enumerate(tables, 3):
        p_num = tbl.get("page", "?")
        sh = tbl.get("sheet") or "—"
        stitle = tbl.get("sheet_title") or "—"
        btitle = tbl.get("title") or "Bảng số liệu"
        cname = tbl.get("_cat_name") or "Khác"
        icon = CATEGORY_METADATA.get(tbl.get("_cat", CAT_GENERAL), {}).get("icon", "📊")
        num_rows = len(tbl.get("rows") or [])
        status = "✅ Khớp" if tbl.get("_audit", {}).get("status") == "ok" else f"⚠️ {len(tbl.get('_audit', {}).get('warnings', []))} cảnh báo"
        sheet_target = f"B{tbl['_id']}_P{p_num}"[:31]

        vals = [
            (1, tbl["_id"], align_center),
            (2, sh, align_center),
            (3, stitle, align_left),
            (4, p_num, align_center),
            (5, btitle, align_left),
            (6, f"{icon} {cname}", align_left),
            (7, num_rows, align_right),
            (8, status, align_center),
        ]
        is_zebra = (r_i % 2 == 1)
        for col_idx, val, al in vals:
            c = ws_index.cell(row=r_i, column=col_idx, value=val)
            c.font = font_data
            c.alignment = al
            c.border = thin_border
            if is_zebra:
                c.fill = fill_zebra
            if col_idx == 8 and "⚠️" in str(val):
                c.fill = fill_warn

        # Hyperlink mở sheet chi tiết
        c_action = ws_index.cell(row=r_i, column=8)
        c_action.hyperlink = f"#'{sheet_target}'!A1"
        c_action.font = font_link
        ws_index.row_dimensions[r_i].height = 20

    # 3. TẠO SHEET 2: TỔNG HỢP CỐT THÉP (NẾU CÓ BẢNG THÉP)
    rebar_list = categorized[CAT_REBAR]
    if rebar_list:
        ws_rebar = wb.create_sheet(title="🔩 Tổng Hợp Cốt Thép")
        ws_rebar.merge_cells("A1:G1")
        ws_rebar["A1"].value = "🔩 BẢNG TỔNG HỢP THỐNG KÊ CỐT THÉP TOÀN DỰ ÁN (TCVN 1651:2018)"
        ws_rebar["A1"].font = font_brand
        ws_rebar["A1"].fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        ws_rebar["A1"].alignment = align_left
        ws_rebar.row_dimensions[1].height = 28

        # Khối tổng hợp nhanh nhóm thép
        tot_d10 = sum(t["_audit"]["rebar_summary"]["weight_by_group"].get("d_le_10", 0) for t in rebar_list)
        tot_d18 = sum(t["_audit"]["rebar_summary"]["weight_by_group"].get("d_le_18", 0) for t in rebar_list)
        tot_gt18 = sum(t["_audit"]["rebar_summary"]["weight_by_group"].get("d_gt_18", 0) for t in rebar_list)
        grand_total = tot_d10 + tot_d18 + tot_gt18

        summary_rows = [
            ("Nhóm Thép Tròn / Cuộn (Φ ≤ 10mm):", f"{tot_d10:,.2f} kg ({tot_d10/1000:,.3f} tấn)"),
            ("Nhóm Thép Vằn Vừa (10 < Φ ≤ 18mm):", f"{tot_d18:,.2f} kg ({tot_d18/1000:,.3f} tấn)"),
            ("Nhóm Thép Thanh Lớn (Φ > 18mm):", f"{tot_gt18:,.2f} kg ({tot_gt18/1000:,.3f} tấn)"),
            ("TỔNG KHỐI LƯỢNG CỐT THÉP DỰ KIẾN:", f"{grand_total:,.2f} kg ({grand_total/1000:,.3f} tấn)"),
        ]
        curr_r = 3
        for lbl, val in summary_rows:
            ws_rebar.cell(row=curr_r, column=1, value=lbl).font = font_bold
            ws_rebar.cell(row=curr_r, column=3, value=val).font = font_bold
            curr_r += 1
        curr_r += 1

        # Gom danh sách thanh từ tất cả các bảng thép
        rebar_headers = ["STT", "Bản vẽ", "Ký hiệu thanh", "Đường kính (mm)", "Chiều dài (mm)", "Số lượng", "Khối lượng (kg)"]
        for c_i, h in enumerate(rebar_headers, 1):
            c = ws_rebar.cell(row=curr_r, column=c_i, value=h)
            c.font = font_head
            c.fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
            c.alignment = align_center
            c.border = thin_border
        ws_rebar.row_dimensions[curr_r].height = 24
        curr_r += 1

        item_idx = 1
        for tbl in rebar_list:
            items = tbl.get("_audit", {}).get("rebar_items", [])
            for it in items:
                ws_rebar.cell(row=curr_r, column=1, value=item_idx).alignment = align_center
                ws_rebar.cell(row=curr_r, column=2, value=tbl.get("sheet", f"P{tbl.get('page')}")).alignment = align_center
                ws_rebar.cell(row=curr_r, column=3, value=it["mark"]).alignment = align_left
                ws_rebar.cell(row=curr_r, column=4, value=it["diameter"]).alignment = align_right
                ws_rebar.cell(row=curr_r, column=5, value=it["length_mm"]).alignment = align_right
                ws_rebar.cell(row=curr_r, column=6, value=it["quantity"]).alignment = align_right
                ws_rebar.cell(row=curr_r, column=7, value=it["total_weight_kg"]).alignment = align_right

                for c_i in range(1, 8):
                    ws_rebar.cell(row=curr_r, column=c_i).border = thin_border
                    ws_rebar.cell(row=curr_r, column=c_i).font = font_data
                curr_r += 1
                item_idx += 1

    # 4. TẠO SHEET CHI TIẾT TỪNG BẢNG
    for tbl in tables:
        p_num = tbl.get("page", "?")
        sheet_target = f"B{tbl['_id']}_P{p_num}"[:31]
        ws_sub = wb.create_sheet(title=sheet_target)

        # Tiêu đề bảng
        t_title = tbl.get("title") or "Bảng số liệu"
        ws_sub.cell(row=1, column=1, value=f"{tbl.get('_cat_name', '')}: {t_title}").font = font_brand
        ws_sub.cell(row=1, column=1).fill = fill_brand
        ws_sub.row_dimensions[1].height = 26

        # Subtitle metadata & Link về Mục lục
        meta_str = f"Trang {p_num} • Bản vẽ: {tbl.get('sheet', '—')} - {tbl.get('sheet_title', '')}"
        ws_sub.cell(row=2, column=1, value=meta_str).font = font_sub
        c_back = ws_sub.cell(row=2, column=4, value="🔙 Quay lại Mục lục")
        c_back.hyperlink = "#'📑 Mục Lục Bảng Biểu'!A1"
        c_back.font = font_link

        headers = tbl.get("header") or []
        body_rows = tbl.get("rows") or []
        values = tbl.get("values") or []
        ncol = max(len(headers), max((len(r) for r in body_rows), default=1))

        # Header hàng
        r = 4
        if headers:
            for c_i, h in enumerate(headers, 1):
                c = ws_sub.cell(row=r, column=c_i, value=h)
                c.font = font_head
                c.fill = fill_index_hdr
                c.alignment = align_center
                c.border = thin_border
            ws_sub.row_dimensions[r].height = 22
            r += 1

        # Data rows
        for r_idx, row_data in enumerate(body_rows):
            is_z = (r_idx % 2 == 1)
            row_vals = values[r_idx] if r_idx < len(values) else []
            for c_i in range(1, ncol + 1):
                val_raw = row_data[c_i - 1] if c_i - 1 < len(row_data) else ""
                num_val = row_vals[c_i - 1] if c_i - 1 < len(row_vals) else None

                c = ws_sub.cell(row=r, column=c_i)
                if num_val is not None and isinstance(num_val, (int, float)):
                    c.value = num_val
                    c.alignment = align_right
                    c.number_format = "#,##0.00" if isinstance(num_val, float) and not num_val.is_integer() else "#,##0"
                else:
                    c.value = val_raw
                    c.alignment = align_left

                c.border = thin_border
                c.font = font_data
                if is_z:
                    c.fill = fill_zebra
            ws_sub.row_dimensions[r].height = 20
            r += 1

        # Tự động canh độ rộng cột
        for col in ws_sub.columns:
            m_len = max((len(str(cell.value or "")) for cell in col), default=0)
            c_letter = get_column_letter(col[0].column)
            ws_sub.column_dimensions[c_letter].width = max(min(m_len + 4, 50), 12)

    # Tự động canh độ rộng cột Sheet Mục Lục
    for col in ws_index.columns:
        m_len = max((len(str(cell.value or "")) for cell in col), default=0)
        c_letter = get_column_letter(col[0].column)
        ws_index.column_dimensions[c_letter].width = max(min(m_len + 4, 45), 10)

    wb.save(str(excel_path))


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPORT JSON FOR 'aec-rebar-optimizer' & 'aec-cost-tender'
# ─────────────────────────────────────────────────────────────────────────────
def export_specialized_jsons(tables: List[Dict[str, Any]], result_dir: Path):
    """
    Xuất dữ liệu có cấu trúc phục vụ trực tiếp cho các skill AEC:
    1. rebar_for_cutting_optimizer.json -> nạp vào aec-rebar-optimizer
    2. boq_for_cost_tender.json -> nạp vào aec-cost-tender
    """
    import json
    all_rebar_items = []
    for tbl in tables:
        items = tbl.get("_audit", {}).get("rebar_items", [])
        all_rebar_items.extend(items)

    if all_rebar_items:
        rebar_file = result_dir / "thep_cho_to_hop_cat.json"
        rebar_file.write_text(json.dumps(all_rebar_items, ensure_ascii=False, indent=2), encoding="utf-8")

    all_boq_items = []
    for tbl in tables:
        if tbl.get("_cat") == CAT_BOQ:
            all_boq_items.append({
                "page": tbl.get("page"),
                "sheet": tbl.get("sheet"),
                "sheet_title": tbl.get("sheet_title"),
                "title": tbl.get("title"),
                "headers": tbl.get("header"),
                "rows": tbl.get("rows"),
            })
    if all_boq_items:
        boq_file = result_dir / "tien_luong_du_toan_boq.json"
        boq_file.write_text(json.dumps(all_boq_items, ensure_ascii=False, indent=2), encoding="utf-8")
