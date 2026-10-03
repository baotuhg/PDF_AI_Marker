# -*- coding: utf-8 -*-
"""
Đọc lại dấu tiếng Việt cho kết quả RapidOCR bằng Surya (VLM chạy qua llama.cpp).

RapidOCR (model PP-OCRv4 tiếng Trung) định vị chữ rất tốt và đọc số ổn định,
nhưng mất toàn bộ dấu tiếng Việt. Surya đọc có dấu nhưng đôi khi "bịa" (đổi
chữ số, sinh chữ Kirin). Vì vậy mỗi ô chỉ nhận kết quả Surya khi qua kiểm tra
chéo:
  * Không chứa ký tự ngoài bảng chữ Latin/tiếng Việt.
  * Bỏ dấu đi thì phải gần giống kết quả RapidOCR.
  * Chuỗi chữ số phải khớp. Nếu lệch -> giữ bản Surya nhưng ghi kèm bản
    RapidOCR dạng ⟦OCR khác: ...⟧ và hạ điểm tin cậy để người/AI đối chiếu.
"""
import difflib
import re
import unicodedata
from typing import Any, List

ALT_OPEN, ALT_CLOSE = "⟦OCR khác: ", "⟧"
# Chữ Latin cơ bản + Latin mở rộng (đủ cho tiếng Việt) + ký hiệu kỹ thuật thường gặp
_ALLOWED = re.compile(r"^[\x20-\x7E -ɏḀ-ỿ°±×÷²³¹⁰⁴⁵⁶⁷⁸⁹ΦφØø∅≤≥≈–—‘’“”…·•√∑Δδ%‰€µ]*$")


def strip_accents(text: str) -> str:
    out = []
    for ch in text:
        if ch in "đĐðÐ":
            out.append("d" if ch in "đð" else "D")
            continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        out.append(base[:1] if base else ch)
    return "".join(out)


def _key(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", strip_accents(text).lower())


def _digits(text: str) -> str:
    """Chuỗi chữ số để so khớp. Bỏ các số 0/1/6 đứng lẻ dính chữ cái vì đó
    thường là chữ có dấu bị RapidOCR đọc nhầm ('s6'=số, 'M6'=mố, '1op'=lớp)."""
    compact = re.sub(r"\s+", "", strip_accents(text))
    cleaned = re.sub(r"(?<=[A-Za-z])[016](?!\d)|(?<!\d)[016](?=[A-Za-z])", "", compact)
    return "".join(re.findall(r"\d", cleaned))


TITLE_BLOCK_ADMIN_KEYWORDS = [
    "CONGTY", "CHUDAUTU", "GIAMDOC", "CHUNHIEM", "CHUTRI", "NGUOIVE",
    "KIEMTRA", "GIAIDOAN", "THIETKE", "BANVE", "TYLE", "NGAY", "KYTEN",
    "HOVATEN", "PHEDUYET", "THAMDINH", "HANGMUC", "GOITHAU", "DUAN",
    "CONGTRINH", "SCALE", "DATE", "DWG", "REV", "SHEET", "CAD"
]


def is_title_block_or_margin_box(box, text: str, W: int, H: int) -> bool:
    """Bỏ qua khung viền bìa ngoài, lề trắng và chữ hành chính lặp lại trong khung tên."""
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # 1. Mép lề trắng ngoài cùng bản vẽ (border margins)
    if min_x <= 0.02 * W or max_x >= 0.98 * W or min_y <= 0.02 * H or max_y >= 0.98 * H:
        return True

    # 2. Vùng Khung tên bản vẽ (góc dưới phải hoặc dải mép phải)
    in_tb_zone = (min_x >= 0.65 * W and min_y >= 0.68 * H) or (min_x >= 0.82 * W)
    if in_tb_zone:
        k = re.sub(r"[^A-Z]", "", strip_accents(text).upper())
        if any(kw in k for kw in TITLE_BLOCK_ADMIN_KEYWORDS):
            return True

    return False


def needs_refine(text: str) -> bool:
    """Chỉ gửi ô chữ có khả năng là tiếng Việt cần phục hồi dấu.
    Bỏ qua mã hiệu kỹ thuật và số đo như D14, KC-01, 1500x200, STT..."""
    words = re.findall(r"[A-Za-zÀ-ỹ]{2,}", text)
    if not words:
        return False
    skip_codes = {"STT", "TL", "KC", "DA", "CT", "TCVN", "CAD", "PDF", "OK", "REV",
                  "D10", "D12", "D14", "D16", "D18", "D20", "D22", "D25", "D28", "D32",
                  "CB300", "CB400", "CIII", "CII"}
    meaningful = [w for w in words if w.upper() not in skip_codes and re.search(r"[aeiouyAEIOUYà-ỹĂ-Ỹ]", w)]
    return len(meaningful) > 0


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def judge(rapid: str, surya: str):
    """Trả về (text_dùng, điểm_phạt, lý_do) theo quy tắc kiểm tra chéo."""
    if not surya or not _ALLOWED.match(surya):
        return rapid, None, "surya_rejected_script"
    rk, sk = _key(rapid), _key(surya)
    ratio = difflib.SequenceMatcher(None, rk, sk).ratio()
    if ratio < 0.40:
        return rapid, None, "surya_rejected_mismatch"
    # VLM đôi khi thêm chữ không có trên bản vẽ ('Trọng lượng giá trị (kg/m)')
    if len(sk) > 1.40 * len(rk) and len(sk) - len(rk) > 3:
        return rapid, None, "surya_rejected_added_text"
    if _digits(rapid) != _digits(surya):
        return f"{surya} {ALT_OPEN}{rapid}{ALT_CLOSE}", 0.5, "digits_differ"
    return surya, None, "ok"


class SuryaRefiner:
    """Giữ một phiên llama-server Surya cho cả tài liệu."""

    def __init__(self):
        self._manager = None
        self.stats = {"sent": 0, "accepted": 0, "rejected": 0, "digits_differ": 0, "skipped_title": 0}

    def _get_manager(self):
        if self._manager is None:
            from surya.inference import SuryaInferenceManager
            self._manager = SuryaInferenceManager()
        return self._manager

    def refine(self, pil_img, results: List[List[Any]]) -> List[List[Any]]:
        """results: [[box, text, score], ...] theo tọa độ của pil_img. Sửa tại chỗ."""
        from surya.inference.schema import BatchInputItem, PROMPT_TYPE_BLOCK
        batch, targets = [], []
        W, H = pil_img.size
        for idx, entry in enumerate(results):
            text = str(entry[1])
            if not needs_refine(text):
                continue
            # Bỏ qua khung viền bìa và chữ hành chính lặp lại trong khung tên
            if is_title_block_or_margin_box(entry[0], text, W, H):
                self.stats["skipped_title"] = self.stats.get("skipped_title", 0) + 1
                continue
            xs = [p[0] for p in entry[0]]
            ys = [p[1] for p in entry[0]]
            x0, y0 = max(0, int(min(xs)) - 4), max(0, int(min(ys)) - 4)
            x1, y1 = min(W, int(max(xs)) + 4), min(H, int(max(ys)) + 4)
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue
            batch.append(BatchInputItem(
                image=pil_img.crop((x0, y0, x1, y1)),
                prompt_type=PROMPT_TYPE_BLOCK,
                max_tokens=min(512, 48 + 3 * len(text)),
                metadata={"idx": idx},
            ))
            targets.append(idx)
        if not batch:
            return results
        self.stats["sent"] += len(batch)
        for out in self._get_manager().generate(batch):
            idx = out.metadata["idx"]
            entry = results[idx]
            if out.error:
                self.stats["rejected"] += 1
                continue
            new_text, penalty, reason = judge(str(entry[1]), _html_to_text(out.raw))
            if reason.startswith("surya_rejected"):
                self.stats["rejected"] += 1
                continue
            self.stats["accepted"] += 1
            if penalty is not None:
                self.stats["digits_differ"] += 1
                entry[2] = min(float(entry[2]), penalty)
            entry[1] = new_text
        return results

    def close(self):
        if self._manager is not None:
            try:
                self._manager.stop()
            except Exception:
                pass
            self._manager = None
