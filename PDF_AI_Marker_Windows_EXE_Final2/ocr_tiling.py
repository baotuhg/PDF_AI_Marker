# -*- coding: utf-8 -*-
"""
OCR độ phân giải cao cho bản vẽ khổ lớn (A3/A1/A0).

RapidOCR tự thu nhỏ ảnh có cạnh > 2000px (Global.max_side_len), làm chữ kích
thước / cao độ trên bản vẽ bị nhòe. Module này render trang ở DPI cao, cắt thành
các ô <= 2000px có vùng chồng lấn, OCR từng ô rồi ghép và khử trùng lặp.

Tọa độ trả về được quy đổi về "hệ tọa độ cơ sở" (scale cũ ~1.0–1.5) để các
ngưỡng pixel trong layout_reconstructor vẫn giữ nguyên ý nghĩa.
"""
import re
import unicodedata
from typing import Any, List, Optional, Tuple

# ── GPU ACCELERATION SETTINGS (NVIDIA RTX / DirectML) ────────────────────────
RENDER_DPI = 240          # Chữ 2.0mm trên bản vẽ ~ 27px -> Nhìn rõ từng nét chữ nhỏ, số mũ và phi Φ
TILE_SIZE = 2400          # Mở rộng kích thước tile (GPU RTX 4070 tính toán ma trận siêu tốc)
TILE_OVERLAP = 500        # Vùng chồng lấn 500px -> Không bao giờ cắt cụt chuỗi số trắc địa dài
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


# ── HẬU KIỂM CHỐNG LẬT 180° ─────────────────────────────────────────────────
# Bộ phân loại hướng chữ (use_cls=True) là CẦN THIẾT cho bản vẽ CAD: nó đọc
# đúng nhãn kích thước xoay 90/270 và bắt thêm hộp chữ (đo trên bản vẽ thép:
# 166 hộp / 17 mẫu '52@150' so với 154 / 8 khi tắt cls). Nhưng với DÒNG CHỮ
# NGANG đứng thẳng, nó phán đoán nhầm là lộn ngược -> khâu nhận dạng đọc ảnh
# đã lật và trả về chuỗi đảo ngược, ví dụ trang 1 Nghị định 15/2021:
#   'upnb ga Sunp 1ou gs 1ou 1g lyo yuip Knb yuip iy8N yupy upq nyd yuiyd'
#   đúng phải là 'Chính phủ ban hành Nghị định quy định chi tiết một số…'
# Dấu hiệu nhận biết: điểm "giống tiếng Việt" thấp (0.36–0.71 so với 0.93–1.0
# của dòng đúng). Cách chữa: đọc LẠI chính vùng ảnh đó bằng bộ máy không-cls
# rồi chỉ nhận khi kết quả mới tốt hơn hẳn — nhờ vậy bản vẽ CAD (vốn đã đúng
# từ đầu) không bị thay đổi.
_ONSETS = ("ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "qu", "th", "tr",
           "b", "c", "d", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x")
_CODAS = ("ch", "ng", "nh", "c", "m", "n", "p", "t")
# Cụm nguyên âm (âm đệm+âm chính+âm cuối vần) CÓ THẬT trong tiếng Việt.
# Phải liệt kê thay vì cho phép mọi cụm 1–3 nguyên âm: nếu chỉ kiểm tra "toàn
# nguyên âm", chữ lật vẫn lọt ('yui' trong 'yuip' trông hợp lệ) và bộ đo mất
# tác dụng phân biệt.
_NUCLEI = {
    "a", "ai", "ao", "au", "ay",
    "e", "eo", "eu",
    "i", "ia", "ie", "iu", "ieu",
    "o", "oa", "oai", "oao", "oay", "oe", "oeo", "oi", "oo",
    "u", "ua", "uay", "ue", "ui", "uo", "uoi", "uou", "uy", "uya", "uye", "uyu",
    "y", "ye", "yeu",
}
_VN_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

FLIP_MIN_TOKENS = 6        # ít token quá thì là nhãn/mã hiệu, không đủ ngữ cảnh phán đoán
FLIP_MAX_SCORE = 0.78      # dưới ngưỡng này coi là nghi bị lật
FLIP_ACCEPT_SCORE = 0.85   # bản đọc lại phải thật sạch mới được thay thế
FLIP_ACCEPT_MARGIN = 0.10  # và phải hơn bản cũ một khoảng rõ rệt
# Dòng văn xuôi chủ yếu là chữ cái; dòng kích thước CAD thì không. Đo trên dòng
# lật thật gặp tỉ lệ 0.66 (có lẫn chữ số), nên ngưỡng phải dưới mức đó — 0.70
# ban đầu bỏ sót hẳn một số hộp. Bù lại, khâu "chấp nhận" bên dưới đã chặt.
FLIP_LETTER_RATIO = 0.45
# Bản đọc lại lệch độ dài bao nhiêu là bất thường. So theo SỐ CHỮ CÁI (bỏ dấu
# câu/khoảng trắng) chứ không theo độ dài chuỗi, và biên rộng: chữ bị lật mất
# hẳn ký tự nên tỉ lệ thật có thể tới ~1.6 ('u uo e u in yuip…' dài 35 chữ cái
# so với bản đúng 55). Đây chỉ là lưới an toàn phụ; tín hiệu chính là điểm.
FLIP_LEN_LO, FLIP_LEN_HI = 0.5, 2.5
_UPRIGHT_ENGINE = None


def _strip_vn(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def _is_vn_syllable(tok: str) -> bool:
    """'hop', 'chinh', 'nguon' -> True; 'upnb', 'yuip', 'iy8n' -> False."""
    if not (1 <= len(tok) <= 7):
        return False
    for on in _ONSETS + ("",):
        if on and not tok.startswith(on):
            continue
        rest = tok[len(on):]
        for cd in _CODAS + ("",):
            if cd and not rest.endswith(cd):
                continue
            body = rest[:len(rest) - len(cd)] if cd else rest
            if body in _NUCLEI:
                return True
    return False


def vn_likeness(text: str) -> Optional[float]:
    """Tỉ lệ âm tiết tiếng Việt hợp lệ trên tổng token chữ (>=2 ký tự).
    Trả None khi quá ít token để phán đoán an toàn."""
    toks = [_strip_vn(t) for t in _VN_WORD_RE.findall(text or "") if len(t) >= 2]
    if len(toks) < FLIP_MIN_TOKENS:
        return None
    return sum(1 for t in toks if _is_vn_syllable(t)) / len(toks)


def _upright_engine():
    """Bộ máy OCR KHÔNG bật cls, dùng riêng cho khâu đọc lại. Nạp muộn để những
    trang không bị lật không phải chịu thêm chi phí bộ nhớ."""
    global _UPRIGHT_ENGINE
    if _UPRIGHT_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        kwargs = dict(max_side_len=3000, det_limit_side_len=1536,
                      det_limit_type="max", det_thresh=0.25, det_unclip_ratio=1.8)
        try:
            import onnxruntime
            if "DmlExecutionProvider" in onnxruntime.get_available_providers():
                kwargs.update(det_use_dml=True, rec_use_dml=True)
        except Exception:
            pass
        _UPRIGHT_ENGINE = RapidOCR(use_cls=False, **kwargs)
    return _UPRIGHT_ENGINE


def repair_flipped_boxes(results, pil_img) -> int:
    """Đọc lại bằng bộ máy không-cls những hộp nghi bị lật 180°; sửa tại chỗ.
    Trả về số hộp đã sửa. Chỉ thay khi bản mới sạch hơn hẳn (xem các ngưỡng FLIP_*)."""
    if not results:
        return 0
    cand = []
    for i, e in enumerate(results):
        txt = str(e[1])
        letters = sum(1 for c in txt if c.isalpha())
        if not txt or letters / len(txt) < FLIP_LETTER_RATIO:
            continue                       # dòng mã hiệu / kích thước — không đủ ngữ cảnh
        sc = vn_likeness(txt)
        if sc is not None and sc < FLIP_MAX_SCORE:
            cand.append((i, e, sc, txt))
    if not cand:
        return 0
    try:
        eng = _upright_engine()
    except Exception:
        return 0                           # thiếu bộ máy -> giữ nguyên, không làm hỏng kết quả
    width, height = pil_img.size
    fixed = 0
    for _i, e, old_sc, old_txt in cand:
        xs = [float(p[0]) for p in e[0]]
        ys = [float(p[1]) for p in e[0]]
        old_letters = sum(1 for c in old_txt if c.isalpha())
        best = None
        # Cắt sát hộp (pad nhỏ) có thể cụt nét chữ và làm điểm tụt dưới ngưỡng chấp
        # nhận — đo trên hồ sơ thật: cùng một dòng, pad=4 chỉ đạt 0.833 còn nới lề
        # ngang lên 20 đạt 0.889. Nên thử vài mức lề và lấy bản đọc SẠCH NHẤT.
        for pad_x, pad_y in ((4, 4), (20, 4), (60, 4), (20, 14)):
            box = (max(0, int(min(xs)) - pad_x), max(0, int(min(ys)) - pad_y),
                   min(width, int(max(xs)) + pad_x), min(height, int(max(ys)) + pad_y))
            if box[2] - box[0] < 8 or box[3] - box[1] < 8:
                continue
            try:
                res2, _ = eng(pil_img.crop(box).convert("RGB"))
            except Exception:
                continue
            if not res2:
                continue
            new_txt = " ".join(str(r[1]).strip() for r in res2 if str(r[1]).strip())
            new_sc = vn_likeness(new_txt)
            if new_sc is None or new_sc < FLIP_ACCEPT_SCORE or new_sc < old_sc + FLIP_ACCEPT_MARGIN:
                continue
            new_letters = sum(1 for c in new_txt if c.isalpha())
            if old_letters and not (FLIP_LEN_LO <= new_letters / old_letters <= FLIP_LEN_HI):
                continue                   # đổi độ dài quá nhiều -> nghi đọc hỏng, giữ bản cũ
            if best is None or new_sc > best[0]:
                best = (new_sc, new_txt)
        if best is not None:
            e[1] = best[1]
            if len(e) > 3:
                e[3] = None                # vị trí ký tự không còn khớp với chữ mới
            fixed += 1
    return fixed


def make_rapid_engine():
    """RapidOCR chạy trên GPU qua DirectML (NVIDIA GeForce RTX 4070 / DX12).
    Khai thác tối đa sức mạnh GPU rời:
    - max_side_len=3000: Không nén ảnh khổ lớn A0/A1
    - det_limit_side_len=1536 (max): Nhìn rõ từng chữ số 1.5mm và ký hiệu phi Φ
    - det_thresh=0.25: Nhận diện cả nét vẽ CAD mờ nhạt
    - det_unclip_ratio=1.8: Bao trọn dấu tiếng Việt trên và dưới chữ
    """
    from rapidocr_onnxruntime import RapidOCR
    try:
        import onnxruntime
        if "DmlExecutionProvider" in onnxruntime.get_available_providers():
            return RapidOCR(
                use_cls=True,
                det_use_dml=True,
                cls_use_dml=True,
                rec_use_dml=True,
                max_side_len=3000,
                det_limit_side_len=1536,
                det_limit_type="max",
                det_thresh=0.25,
                det_unclip_ratio=1.8,
            ), "DirectML GPU (NVIDIA RTX 4070)"
    except Exception:
        pass
    return RapidOCR(use_cls=True), "CPU"


def enhance_contrast_clahe(pil_img):
    """
    Tăng cường tương phản cục bộ bằng CLAHE (OpenCV) cho ảnh bản vẽ CAD scan.
    Làm nổi rõ nét chữ mảnh, chữ mờ mà KHÔNG làm đứt nét hoặc mất dấu chấm thập phân.
    """
    try:
        import cv2
        import numpy as np
        img_np = np.array(pil_img)
        if len(img_np.shape) == 3:
            lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge((cl, a, b)), cv2.COLOR_LAB2RGB)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(img_np)
        from PIL import Image
        return Image.fromarray(enhanced)
    except Exception:
        return pil_img


def ocr_pil(engine, pil_img, factor: float, refiner=None) -> List[List[Any]]:
    """OCR một ảnh trang đã render (có thể đã xoay); trả tọa độ nhân `factor`
    (pixel ảnh -> hệ tọa độ cơ sở)."""
    enhanced = enhance_contrast_clahe(pil_img)
    results = ocr_image_tiled(engine, enhanced)
    before = [e[1] for e in results]
    if refiner is not None and results:
        refiner.refine(pil_img, results)
    _scale_entries(results, factor, before)
    return results


def ocr_pdf_page(engine, page, refiner=None, with_image: bool = False):
    """Render trang PDF ở RENDER_DPI, OCR theo ô, tự động nhận diện & xoay đúng chiều, trả tọa độ ở hệ base_scale.

    refiner: đối tượng có .refine(pil_img, results) (vd. SuryaRefiner) để đọc
    lại dấu tiếng Việt trước khi quy đổi tọa độ.
    with_image=True: trả (results, pil_img, factor) để dò bảng kẻ ô trên ảnh.
    """
    pw, ph = page.get_size()
    render_scale = RENDER_DPI / 72.0
    pil_img = page.render(scale=render_scale).to_pil()
    enhanced = enhance_contrast_clahe(pil_img)
    results = ocr_image_tiled(engine, enhanced)

    # ── Tự động nhận biết trang bị xoay ngang / xoay dọc (Auto-Orientation) ──
    # Nếu chữ thẳng đứng (chiều cao > 2 chiều rộng) áp đảo chữ nằm ngang -> trang bị nghiêng/xoay 90/270 độ
    h_cnt = sum(1 for e in results if abs(e[0][1][0] - e[0][0][0]) >= 2.0 * abs(e[0][2][1] - e[0][1][1]) and abs(e[0][1][0] - e[0][0][0]) > 20)
    v_cnt = sum(1 for e in results if abs(e[0][2][1] - e[0][1][1]) >= 2.0 * abs(e[0][1][0] - e[0][0][0]) and abs(e[0][2][1] - e[0][1][1]) > 20)
    if v_cnt >= 12 and v_cnt > 2.0 * h_cnt:
        # Thử xoay 90 độ
        img_90 = page.render(scale=render_scale, rotation=90).to_pil()
        enh_90 = enhance_contrast_clahe(img_90)
        res_90 = ocr_image_tiled(engine, enh_90)
        h_90 = sum(1 for e in res_90 if abs(e[0][1][0] - e[0][0][0]) >= 2.0 * abs(e[0][2][1] - e[0][1][1]) and abs(e[0][1][0] - e[0][0][0]) > 20)
        v_90 = sum(1 for e in res_90 if abs(e[0][2][1] - e[0][1][1]) >= 2.0 * abs(e[0][1][0] - e[0][0][0]) and abs(e[0][2][1] - e[0][1][1]) > 20)
        if h_90 > v_90 and h_90 > h_cnt:
            pil_img = img_90
            results = res_90
            pw, ph = ph, pw
        else:
            # Thử xoay 270 độ nếu xoay 90 chưa đạt
            img_270 = page.render(scale=render_scale, rotation=270).to_pil()
            enh_270 = enhance_contrast_clahe(img_270)
            res_270 = ocr_image_tiled(engine, enh_270)
            h_270 = sum(1 for e in res_270 if abs(e[0][1][0] - e[0][0][0]) >= 2.0 * abs(e[0][2][1] - e[0][1][1]) and abs(e[0][1][0] - e[0][0][0]) > 20)
            v_270 = sum(1 for e in res_270 if abs(e[0][2][1] - e[0][1][1]) >= 2.0 * abs(e[0][1][0] - e[0][0][0]) and abs(e[0][2][1] - e[0][1][1]) > 20)
            if h_270 > v_270 and h_270 > h_cnt:
                pil_img = img_270
                results = res_270
                pw, ph = ph, pw

    # Sau khi đã chốt chiều trang: đọc lại những hộp nghi bị cls lật ngược.
    try:
        repair_flipped_boxes(results, pil_img)
    except Exception:
        pass

    before = [e[1] for e in results]
    if refiner is not None and results:
        refiner.refine(pil_img, results)
    factor = base_scale(pw, ph) / render_scale
    _scale_entries(results, factor, before)
    if with_image:
        return results, pil_img, factor
    return results
