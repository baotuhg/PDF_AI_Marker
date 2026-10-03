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


def _clean_ocr_digits(text: str) -> str:
    """
    Chuỗi chữ số chuẩn hóa để so khớp 2 bộ OCR (RapidOCR vs Surya).
    Khử triệt để các báo động giả do RapidOCR đọc nhầm dấu tiếng Việt thành số
    (s6=số, ng6=ngõ, ph6=phố, B0=bộ, 1op=lớp, 16=lỗ, c6=có, h8=hồ, m6=mố, d0=độ),
    đọc nhầm ký hiệu đường kính (032=Ø32), số La Mã (I-1=I-I), gạch chéo (217=2/7),
    chữ O trong số (3OMPA=30MPA, O2=02), số mũ (Km²=Km2), và ký hiệu LaTeX của Surya.
    """
    if not text:
        return ""
    # 1. Khử cú pháp LaTeX nếu Surya sinh ra (vd: H_{4\%}, \text{ mm}, \times)
    t = re.sub(r"\\[a-zA-Z]+", " ", text)
    t = re.sub(r"[{}_$]", " ", t)

    # 2. Chuẩn hóa Unicode NFKD (Km² -> Km2, ³ -> 3, etc.)
    t = unicodedata.normalize("NFKD", t)

    # 3. Chuẩn hóa chữ O/o giữa hoặc liền kề số thành 0 (vd: 3OMPA -> 30MPA, O2KHE -> 02KHE)
    t = re.sub(r"(?<=\d)[oO]|[oO](?=\d)", "0", t)

    # 4. Bỏ dấu tiếng Việt về chữ không dấu cơ bản (giữ nguyên khoảng trắng giữa các từ)
    out = []
    for ch in t:
        if ch in "đĐðÐ":
            out.append("d" if ch in "đð" else "D")
        else:
            base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
            out.append(base[:1] if base else ch)
    t = "".join(out)

    # 5. Khử các từ nhầm dấu kinh điển của RapidOCR
    t = re.sub(r"\b[sS]6\b", "so", t)
    t = re.sub(r"\b[nN]g6\b", "ngo", t)
    t = re.sub(r"\b[pP]h6\b", "pho", t)
    t = re.sub(r"\b[bB]0\b", "bo", t)
    t = re.sub(r"\b[mM]6\b", "mo", t)
    t = re.sub(r"\b[dD][06]\b", "do", t)
    t = re.sub(r"\b[cC]6\b", "co", t)
    t = re.sub(r"\b[hH]8\b", "ho", t)
    t = re.sub(r"\b[tT]6\b", "to", t)
    t = re.sub(r"\b[lL]6\b", "lo", t)
    t = re.sub(r"\b16\s*(khoan|lo)\b", r"lo \1", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(so|co so)\s+16\b", r"\1 lo", t, flags=re.IGNORECASE)
    t = re.sub(r"\b1[oO]p\b", "lop", t, flags=re.IGNORECASE)
    t = re.sub(r"\b[tT]y\s*11\b", "tyle", t, flags=re.IGNORECASE)
    t = re.sub(r"\b2\s*lu[pP]o?i?\s*thep\b", "2 luoi thep", t, flags=re.IGNORECASE)
    t = re.sub(r"dan\s*0\s*100", "dan o 100", t, flags=re.IGNORECASE)

    # 6. Khử số 0, 6, 8 dính liền chữ cái (không phải số thực)
    t = re.sub(r"(?<=[A-Za-z])[068](?![0-9])", "", t)
    t = re.sub(r"(?<![0-9])[068](?=[A-Za-z])", "", t)
    # Khử số 1 dính giữa 2 chữ cái hoặc ở đầu từ chữ cái (1op -> op)
    t = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "", t)
    t = re.sub(r"\b1(?=[a-zA-Z]{2,})", "", t)

    # 7. Khử số 0 đứng trước đường kính cốt thép do đọc nhầm Ø (CHOT 032 -> CHOT 32, 032 -> 32)
    t = re.sub(r"(?<=CHOT\s)0(?=(1[02468]|2[0258]|32)\b)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?<=CHOT)0(?=(1[02468]|2[0258]|32)\b)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?<=THEP\s)0(?=(1[02468]|2[0258]|32)\b)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"(?<=THEP)0(?=(1[02468]|2[0258]|32)\b)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b0(?=(1[02468]|2[0258]|32)\b)", "", t)

    # 8. Chuẩn hóa số La Mã I - 1 -> I - I
    t = re.sub(r"I\s*-\s*1\b", "I-I", t)
    # Chuẩn hóa phân số (217) -> (2/7)
    t = re.sub(r"\((\d)1(\d)\)", r"(\1/\2)", t)
    # Chuẩn hóa đầu dòng số thứ tự 1.KICHTHUOC -> KICHTHUOC
    t = re.sub(r"^\s*1\.\s*(?=[A-Za-z])", "", t)
    # Chuẩn hóa l=1m vs 1=1m
    t = re.sub(r"\b1=(?=\d)", "l=", t)

    return "".join(re.findall(r"\d", t))


_digits = _clean_ocr_digits


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
    Bỏ qua mã hiệu kỹ thuật và số đo như D14, KC-01, 1500x200, STT...
    Đồng thời bỏ qua con dấu thẩm định hành chính để tránh xung đột không cần thiết."""
    words = re.findall(r"[A-Za-zÀ-ỹ]{2,}", text)
    if not words:
        return False
    skip_codes = {"STT", "TL", "KC", "DA", "CT", "TCVN", "CAD", "PDF", "OK", "REV",
                  "D10", "D12", "D14", "D16", "D18", "D20", "D22", "D25", "D28", "D32",
                  "CB300", "CB400", "CIII", "CII"}
    meaningful = [w for w in words if w.upper() not in skip_codes and re.search(r"[aeiouyAEIOUYà-ỹĂ-Ỹ]", w)]
    if not meaningful:
        return False
    # Bỏ qua chữ hành chính con dấu thẩm định lặp lại trên bản vẽ
    k = re.sub(r"[^A-Z]", "", strip_accents(text).upper())
    if any(kw in k for kw in ["SGTVT", "QLCLCT", "THEOVANBAN", "SOGIAOTHONG"]):
        return False
    return True


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup
    text = BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def judge(rapid: str, surya: str):
    """Trả về (text_dùng, điểm_phạt, lý_do) theo quy tắc kiểm tra chéo."""
    if not surya or not _ALLOWED.match(surya):
        return rapid, None, "surya_rejected_script"

    # Tẩy ký tự CJK rác nếu có
    surya_clean = re.sub(r"[\u4e00-\u9fff]+", "", surya).strip()
    rapid_clean = re.sub(r"[\u4e00-\u9fff]+", "", rapid).strip()
    if not surya_clean:
        return rapid, None, "surya_rejected_empty"

    rk, sk = _key(rapid_clean), _key(surya_clean)
    ratio = difflib.SequenceMatcher(None, rk, sk).ratio()
    if ratio < 0.40:
        return rapid, None, "surya_rejected_mismatch"
    # VLM đôi khi thêm chữ không có trên bản vẽ ('Trọng lượng giá trị (kg/m)')
    if len(sk) > 1.40 * len(rk) and len(sk) - len(rk) > 3:
        return rapid, None, "surya_rejected_added_text"

    dr = _clean_ocr_digits(rapid_clean)
    ds = _clean_ocr_digits(surya_clean)
    if dr != ds:
        # Nếu chỉ khác ở dấu hành chính lặp lại -> chấp nhận Surya, không ghi xung đột
        if any(k in rapid_clean.upper() or k in surya_clean.upper() for k in ["SGTVT", "QLCLCT", "THEO VAN BAN", "SOGIAOTHONG"]):
            return surya_clean, None, "stamp_ignored"
        return f"{surya_clean} {ALT_OPEN}{rapid_clean}{ALT_CLOSE}", 0.5, "digits_differ"
    return surya_clean, None, "ok"


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
