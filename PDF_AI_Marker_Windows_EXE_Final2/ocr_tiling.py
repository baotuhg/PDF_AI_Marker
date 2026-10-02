# -*- coding: utf-8 -*-
"""
OCR độ phân giải cao cho bản vẽ khổ lớn (A3/A1/A0).

RapidOCR tự thu nhỏ ảnh có cạnh > 2000px (Global.max_side_len), làm chữ kích
thước / cao độ trên bản vẽ bị nhòe. Module này render trang ở DPI cao, cắt thành
các ô <= 2000px có vùng chồng lấn, OCR từng ô rồi ghép và khử trùng lặp.

Tọa độ trả về được quy đổi về "hệ tọa độ cơ sở" (scale cũ ~1.0–1.5) để các
ngưỡng pixel trong layout_reconstructor vẫn giữ nguyên ý nghĩa.
"""
from typing import Any, List, Tuple

RENDER_DPI = 200          # Chữ 2.5mm trên bản vẽ ~ 20px -> OCR đọc số ổn định
TILE_SIZE = 2000          # Không vượt max_side_len của RapidOCR
TILE_OVERLAP = 400        # Dòng chữ ngắn hơn vùng chồng lấn sẽ nằm trọn trong 1 ô
EDGE_MARGIN = 3           # Hộp chạm mép trong của ô = có thể bị cắt cụt


def base_scale(page_w: float, page_h: float) -> float:
    """Scale mà layout_reconstructor đã được hiệu chỉnh theo (giữ như cũ)."""
    return min(1.5, max(1.0, 1600.0 / max(1.0, page_w, page_h)))


def _tile_starts(length: int) -> List[int]:
    if length <= TILE_SIZE:
        return [0]
    step = TILE_SIZE - TILE_OVERLAP
    starts = list(range(0, length - TILE_SIZE, step))
    starts.append(length - TILE_SIZE)
    return starts


def _bbox(box) -> Tuple[float, float, float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return min(xs), min(ys), max(xs), max(ys)


def _overlap_ratio(a, b) -> float:
    """Diện tích giao / diện tích hộp nhỏ hơn."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return inter / area if area > 0 else 0.0


def _char_spans(entry, x_off: float = 0.0):
    """Vị trí từng ký tự/từ [(chuỗi, x0, x1)] (tọa độ ảnh trang) từ kết quả
    RapidOCR return_word_box, cùng định dạng 'chars' của lớp chữ PDF. Nhờ đó
    layout_reconstructor.split_items_on_columns cắt được hộp OCR vắt qua đường kẻ
    cột (vd. '453,106416,79227314,9807' = 3 ô D6/D10/D12 dính nhau ở PT-01).
    Trả None nếu không ghép được chính xác với chữ đã đọc hoặc chữ viết dọc."""
    if len(entry) < 5 or not entry[3] or not entry[4]:
        return None
    text = str(entry[1])
    bx = _bbox(entry[0])
    if (bx[3] - bx[1]) > 1.5 * (bx[2] - bx[0]):
        return None
    spans, pos = [], 0
    for word, wbox in zip(entry[4], entry[3]):
        word = str(word)
        k = text.find(word, pos) if word else -1
        if k < 0 or not wbox:
            return None
        spans += [(ch, None, None) for ch in text[pos:k]]
        wx = [float(p[0]) + x_off for p in wbox]
        spans.append((word, min(wx), max(wx)))
        pos = k + len(word)
    spans += [(ch, None, None) for ch in text[pos:]]
    return spans


def _run(engine, img, x_off: float = 0.0, y_off: float = 0.0) -> List[List[Any]]:
    """[[box, text, score, chars]] theo tọa độ ảnh trang."""
    try:
        res, _ = engine(img, return_word_box=True)
    except TypeError:                      # bản RapidOCR cũ không có return_word_box
        res, _ = engine(img)
    out = []
    for entry in res or []:
        box = [[float(p[0]) + x_off, float(p[1]) + y_off] for p in entry[0]]
        out.append([box, entry[1], float(entry[2]), _char_spans(entry, x_off)])
    return out


def _scale_entries(results, factor: float, before_refine=None) -> None:
    """Nhân tọa độ với factor; bỏ vị trí ký tự của hộp đã được Surya sửa chữ
    (ghép lại theo ký tự cũ sẽ làm mất chữ có dấu)."""
    for i, entry in enumerate(results):
        entry[0] = [[p[0] * factor, p[1] * factor] for p in entry[0]]
        if len(entry) > 3:
            if entry[3] and (before_refine is None or before_refine[i] == entry[1]):
                entry[3] = [(c, None if a is None else a * factor, None if b is None else b * factor)
                            for c, a, b in entry[3]]
            else:
                entry[3] = None


def ocr_image_tiled(engine, pil_img) -> List[List[Any]]:
    """OCR ảnh lớn theo từng ô; trả về [[box, text, score, chars], ...] theo tọa độ ảnh gốc."""
    width, height = pil_img.size
    xs, ys = _tile_starts(width), _tile_starts(height)
    if len(xs) == 1 and len(ys) == 1:
        return _run(engine, pil_img)

    full, cut = [], []   # hộp nằm trọn trong ô / hộp chạm mép trong (có thể bị cắt)
    for y0 in ys:
        for x0 in xs:
            x1, y1 = min(width, x0 + TILE_SIZE), min(height, y0 + TILE_SIZE)
            for entry in _run(engine, pil_img.crop((x0, y0, x1, y1)), x0, y0):
                bx = _bbox(entry[0])
                touches_inner_edge = (
                    (x0 > 0 and bx[0] <= x0 + EDGE_MARGIN) or
                    (x1 < width and bx[2] >= x1 - EDGE_MARGIN) or
                    (y0 > 0 and bx[1] <= y0 + EDGE_MARGIN) or
                    (y1 < height and bx[3] >= y1 - EDGE_MARGIN)
                )
                (cut if touches_inner_edge else full).append((bx, entry))

    # Khử trùng lặp trong vùng chồng lấn: giữ bản có chữ dài hơn / điểm cao hơn
    full.sort(key=lambda it: (len(str(it[1][1])), it[1][2]), reverse=True)
    kept: List[Tuple[Any, List[Any]]] = []
    for bx, entry in full:
        if all(_overlap_ratio(bx, k[0]) < 0.5 for k in kept):
            kept.append((bx, entry))

    # Hộp bị cắt chỉ giữ khi ô khác không đọc được bản đầy đủ (dòng rất dài
    # vắt qua ranh giới ô) -> thà lặp một đoạn ngắn còn hơn mất số liệu.
    full_boxes = [k[0] for k in kept]
    for bx, entry in cut:
        if all(_overlap_ratio(bx, fb) < 0.5 for fb in full_boxes):
            kept.append((bx, entry))

    kept.sort(key=lambda it: (it[0][1], it[0][0]))
    return [entry for _, entry in kept]


def make_rapid_engine():
    """RapidOCR chạy trên GPU qua DirectML (mọi card DX12) nếu có, không thì CPU.
    Trên RTX 4070: ~2.4s/trang A3 200 DPI so với ~16s trên CPU.

    use_cls=True: bản vẽ có rất nhiều kích thước viết dọc (đọc từ dưới lên).
    RapidOCR xoay hộp chữ dọc 90° ngược chiều kim đồng hồ nên chữ bị lộn ngược;
    bộ phân loại hướng (cls) lật lại 180°. Tắt cls thì '20x13=260', '450', '550'
    trên TC-04 ra '0', '000', 'rn' hoặc mất hẳn."""
    from rapidocr_onnxruntime import RapidOCR
    try:
        import onnxruntime
        if "DmlExecutionProvider" in onnxruntime.get_available_providers():
            return RapidOCR(use_cls=True, det_use_dml=True, cls_use_dml=True,
                            rec_use_dml=True), "DirectML GPU"
    except Exception:
        pass
    return RapidOCR(use_cls=True), "CPU"


def ocr_pil(engine, pil_img, factor: float, refiner=None) -> List[List[Any]]:
    """OCR một ảnh trang đã render (có thể đã xoay); trả tọa độ nhân `factor`
    (pixel ảnh -> hệ tọa độ cơ sở)."""
    results = ocr_image_tiled(engine, pil_img)
    before = [e[1] for e in results]
    if refiner is not None and results:
        refiner.refine(pil_img, results)
    _scale_entries(results, factor, before)
    return results


def ocr_pdf_page(engine, page, refiner=None, with_image: bool = False):
    """Render trang PDF ở RENDER_DPI, OCR theo ô, trả tọa độ ở hệ base_scale.

    refiner: đối tượng có .refine(pil_img, results) (vd. SuryaRefiner) để đọc
    lại dấu tiếng Việt trước khi quy đổi tọa độ.
    with_image=True: trả (results, pil_img, factor) để dò bảng kẻ ô trên ảnh.
    """
    pw, ph = page.get_size()
    render_scale = RENDER_DPI / 72.0
    pil_img = page.render(scale=render_scale).to_pil()
    results = ocr_image_tiled(engine, pil_img)
    before = [e[1] for e in results]
    if refiner is not None and results:
        refiner.refine(pil_img, results)
    factor = base_scale(pw, ph) / render_scale
    _scale_entries(results, factor, before)
    if with_image:
        return results, pil_img, factor
    return results
