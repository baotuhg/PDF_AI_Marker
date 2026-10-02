# -*- coding: utf-8 -*-
"""
Chữ font SHX của AutoCAD trong PDF.

Khi AutoCAD in ra PDF, chữ font SHX (romans.shx, txt.shx, font SHX tiếng Việt...)
KHÔNG nằm trong lớp chữ mà bị vẽ thành các nét hình học. Có hai trường hợp:

1. AutoCAD 2016+ (biến PDFSHX=1) kèm theo chú thích ẩn Subj="AutoCAD SHX Text"
   chứa đúng nội dung chữ -> đọc trực tiếp, chính xác tuyệt đối (có thể là mã
   TCVN3/VNI nếu dùng font SHX tiếng Việt cũ -> giải mã).
2. Không có chú thích: chữ chỉ còn là nét vẽ -> phải OCR vùng đó. Module này
   phát hiện trang "chữ nét vẽ" (lớp chữ ít nhưng nhiều đối tượng nét vẽ) để
   worker tự OCR bổ sung, rồi ghép với lớp chữ sẵn có (không trùng lặp).
"""
import ctypes
from typing import Any, Dict, List

SHX_SUBJECT_KEYS = ("SHX",)


def _annot_str(annot, key: str) -> str:
    import pypdfium2.raw as R
    n = R.FPDFAnnot_GetStringValue(annot, key.encode(), None, 0)
    if n <= 2:
        return ""
    buf = (ctypes.c_ushort * (n // 2))()
    R.FPDFAnnot_GetStringValue(annot, key.encode(), buf, n)
    return bytes(buf).decode("utf-16-le", errors="ignore").rstrip("\x00")


def _decode_legacy(texts: List[str]) -> List[str]:
    """Font SHX tiếng Việt cũ thường mã TCVN3 hoặc VNI -> Unicode. Xét TỪNG chú
    thích vì một bản vẽ có thể lẫn font SHX Unicode và font SHX mã cũ; chú thích
    quá ngắn để tự nhận dạng thì theo mã chiếm đa số của cả trang."""
    from vn_legacy import (looks_like_vni, looks_like_tcvn3, vni_to_unicode, tcvn3_to_unicode,
                           _REAL_VI, VNI_CHARS, _TCVN3_CHARS)
    kinds = []
    for t in texts:
        if _REAL_VI.search(t):
            kinds.append("unicode")
        elif looks_like_vni(t):
            kinds.append("vni")
        elif looks_like_tcvn3(t):
            kinds.append("tcvn")
        else:
            kinds.append("")
    legacy = [k for k in kinds if k in ("vni", "tcvn")]
    page_kind = max(set(legacy), key=legacy.count) if legacy else ""
    out = []
    special = {"vni": VNI_CHARS, "tcvn": _TCVN3_CHARS}
    for t, k in zip(texts, kinds):
        # Chú thích ngắn chưa rõ mã: theo mã chiếm đa số của trang, nếu có ký tự đặc trưng của mã đó
        if not k and page_kind and any(ch in special[page_kind] for ch in t):
            k = page_kind
        out.append(vni_to_unicode(t) if k == "vni" else tcvn3_to_unicode(t) if k == "tcvn" else t)
    return out


def shx_annotation_boxes(page, scale: float, rotate_box=None) -> List[List[Any]]:
    """Chú thích 'AutoCAD SHX Text' -> [[box, text, 1.0]] theo hệ tọa độ cơ sở
    (gốc trên-trái, nhân scale). rotate_box: hàm xoay bbox (điểm PDF) theo hướng
    chữ của trang, dùng chung với lớp chữ pdftext."""
    import pypdfium2.raw as R
    W, H = page.get_size()
    found = []
    for i in range(R.FPDFPage_GetAnnotCount(page.raw)):
        annot = R.FPDFPage_GetAnnot(page.raw, i)
        try:
            subj = _annot_str(annot, "Subj")
            if not any(k in subj.upper() for k in SHX_SUBJECT_KEYS):
                continue
            text = _annot_str(annot, "Contents").strip()
            rect = R.FS_RECTF()
            if not text or not R.FPDFAnnot_GetRect(annot, ctypes.byref(rect)):
                continue
            x0, x1 = sorted((rect.left, rect.right))
            y0, y1 = sorted((H - rect.top, H - rect.bottom))     # PDF (gốc dưới) -> gốc trên
            found.append((text, [x0, y0, x1, y1]))
        finally:
            R.FPDFPage_CloseAnnot(annot)
    out = []
    for text, bb in zip(_decode_legacy([t for t, _ in found]), [b for _, b in found]):
        if rotate_box is not None:
            bb = rotate_box(bb)
        x0, y0, x1, y1 = (v * scale for v in bb)
        out.append([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, 1.0])
    return out


def page_object_stats(page, limit: int = 50000) -> Dict[str, Any]:
    """Đếm nhanh đối tượng cấp trên cùng của trang: chữ, nét vẽ, ảnh, form."""
    import pypdfium2.raw as R
    total = R.FPDFPage_CountObjects(page.raw)
    stats = {"total": total, "text": 0, "path": 0, "image": 0, "form": 0, "image_area": 0.0}
    W, H = page.get_size()
    for i in range(min(total, limit)):
        obj = R.FPDFPage_GetObject(page.raw, i)
        t = R.FPDFPageObj_GetType(obj)
        if t == R.FPDF_PAGEOBJ_TEXT:
            stats["text"] += 1
        elif t == R.FPDF_PAGEOBJ_PATH:
            stats["path"] += 1
        elif t == R.FPDF_PAGEOBJ_FORM:
            stats["form"] += 1
        elif t == R.FPDF_PAGEOBJ_IMAGE:
            stats["image"] += 1
            l, b, r, tp = ctypes.c_float(), ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
            if R.FPDFPageObj_GetBounds(obj, ctypes.byref(l), ctypes.byref(b), ctypes.byref(r), ctypes.byref(tp)):
                stats["image_area"] += max(0.0, r.value - l.value) * max(0.0, tp.value - b.value) / max(1.0, W * H)
    return stats


def needs_ocr(n_text_chars: int, stats: Dict[str, Any], page_size) -> str:
    """Lý do cần OCR bổ sung ('' nếu không cần):
    - 'scan'        : trang là ảnh, không có lớp chữ
    - 'vector_text' : lớp chữ gần như trống nhưng có nét vẽ -> chữ SHX bị vẽ thành nét
    - 'mixed_shx'   : bản vẽ khổ lớn, rất nhiều nét vẽ -> có thể lẫn chữ SHX ngoài lớp chữ
    """
    big = max(page_size) >= 1100          # >= A3
    vector = stats["path"] + stats["form"]
    if n_text_chars < 30 and stats["image_area"] > 0.5:
        return "scan"
    if n_text_chars < 200 and vector >= 20:
        return "vector_text"
    if big and vector >= 3000:
        return "mixed_shx"
    return ""


def merge_boxes(primary: List[List[Any]], extra: List[List[Any]], thr: float = 0.3) -> List[List[Any]]:
    """Thêm hộp của 'extra' (OCR) không trùng với 'primary' (lớp chữ / chú thích SHX)."""
    def bb(e):
        xs = [p[0] for p in e[0]]; ys = [p[1] for p in e[0]]
        return min(xs), min(ys), max(xs), max(ys)
    prim = [bb(e) for e in primary]
    out = list(primary)
    for e in extra:
        x0, y0, x1, y1 = bb(e)
        area = max(1e-6, (x1 - x0) * (y1 - y0))
        dup = False
        for a in prim:
            ix = max(0.0, min(x1, a[2]) - max(x0, a[0]))
            iy = max(0.0, min(y1, a[3]) - max(y0, a[1]))
            if ix * iy / area > thr:
                dup = True
                break
        if not dup:
            out.append(e)
    return out
