# -*- coding: utf-8 -*-
"""
Chuyển mã font tiếng Việt cũ TCVN3 (ABC: .VnTime, .VnArial, .VnTimeH...) sang Unicode.

Bản vẽ AutoCAD và văn bản cũ ở Việt Nam rất hay dùng font TCVN3: lớp chữ trong
PDF khi đó là các ký tự Latin-1 như 'Tû lÖ' (= 'Tỷ lệ'), 'Chñ nhiÖm' (= 'Chủ
nhiệm'). Font họ ...H (.VnTimeH, .VnArialH) là font chữ HOA: cùng mã nhưng hiển
thị chữ in hoa.
"""
import re
import unicodedata
from typing import Any, List, Tuple

# Bảng mã TCVN 5712:1993 (VN3) -> Unicode
_TCVN3 = {
    "¨": "ă", "©": "â", "ª": "ê", "«": "ô", "¬": "ơ", "­": "ư", "®": "đ",
    "¡": "Ă", "¢": "Â", "£": "Ê", "¤": "Ô", "¥": "Ơ", "¦": "Ư", "§": "Đ",
    "µ": "à", "¶": "ả", "·": "ã", "¸": "á", "¹": "ạ",
    "»": "ằ", "¼": "ẳ", "½": "ẵ", "¾": "ắ", "Æ": "ặ",
    "Ç": "ầ", "È": "ẩ", "É": "ẫ", "Ê": "ấ", "Ë": "ậ",
    "Ì": "è", "Î": "ẻ", "Ï": "ẽ", "Ð": "é", "Ñ": "ẹ",
    "Ò": "ề", "Ó": "ể", "Ô": "ễ", "Õ": "ế", "Ö": "ệ",
    "×": "ì", "Ø": "ỉ", "Ü": "ĩ", "Ý": "í", "Þ": "ị",
    "ß": "ò", "á": "ỏ", "â": "õ", "ã": "ó", "ä": "ọ",
    "å": "ồ", "æ": "ổ", "ç": "ỗ", "è": "ố", "é": "ộ",
    "ê": "ờ", "ë": "ở", "ì": "ỡ", "í": "ớ", "î": "ợ",
    "ï": "ù", "ñ": "ủ", "ò": "ũ", "ó": "ú", "ô": "ụ",
    "õ": "ừ", "ö": "ử", "÷": "ữ", "ø": "ứ", "ù": "ự",
    "ú": "ỳ", "û": "ỷ", "ü": "ỹ", "ý": "ý", "þ": "ỵ",
}
_TRANS = str.maketrans(_TCVN3)
_TCVN3_CHARS = set(_TCVN3)
# Ký tự tiếng Việt Unicode thật (nếu có thì văn bản không phải TCVN3)
_REAL_VI = re.compile(r"[ạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹơưăđ]", re.IGNORECASE)


def is_tcvn3_font(font_name: str) -> bool:
    """'.VnTime', 'ABCDEF+.VnArialH', 'VnTimeH,Bold'... (không phải VNI-Times)."""
    return bool(font_name) and bool(re.search(r"(?:^|[+.])Vn[A-Z][A-Za-z]*", font_name))


def is_upper_font(font_name: str) -> bool:
    return bool(re.search(r"Vn[A-Za-z]*?H(?:[,\-]|Bold|Italic|$)", font_name or ""))


def looks_like_tcvn3(text: str) -> bool:
    """Nhận dạng theo nội dung khi tên font không rõ: nhiều ký tự mã TCVN3 dính
    chữ Latin và không có ký tự tiếng Việt Unicode thật."""
    if not text or _REAL_VI.search(text):
        return False
    hits = sum(1 for ch in text if ch in _TCVN3_CHARS)
    letters = sum(1 for ch in text if ch.isalpha())
    return hits >= 2 and hits >= 0.08 * max(1, letters)


def tcvn3_to_unicode(text: str, upper: bool = False) -> str:
    out = text.translate(_TRANS)
    return out.upper() if upper else out


# ─────────────────────────────────────────────────────────────────────────────
# VNI (VNI-Times, VNI-Helve, VNI-Revue...): chữ gốc ASCII + ký tự DẤU đứng sau.
#   'Tieáng Vieät' = Tiếng Việt, 'ñöôøng' = đường, 'HÖÔÙNG DAÃN' = HƯỚNG DẪN
# ─────────────────────────────────────────────────────────────────────────────
_ACUTE, _GRAVE, _HOOK, _TILDE, _DOT = "́", "̀", "̉", "̃", "̣"
_CIRC, _BREVE = "̂", "̆"
_VNI_TONE = {"ù": _ACUTE, "ø": _GRAVE, "û": _HOOK, "õ": _TILDE, "ï": _DOT,
             "Ù": _ACUTE, "Ø": _GRAVE, "Û": _HOOK, "Õ": _TILDE, "Ï": _DOT}
# Sau a/e/o: dấu mũ (â/ê/ô), có thể kèm thanh
_VNI_CIRC = {"â": "", "á": _ACUTE, "à": _GRAVE, "å": _HOOK, "ã": _TILDE, "ä": _DOT,
             "Â": "", "Á": _ACUTE, "À": _GRAVE, "Å": _HOOK, "Ã": _TILDE, "Ä": _DOT}
# Sau a: dấu trăng (ă), có thể kèm thanh
_VNI_BREVE = {"ê": "", "é": _ACUTE, "è": _GRAVE, "ú": _HOOK, "ü": _TILDE, "ë": _DOT,
              "Ê": "", "É": _ACUTE, "È": _GRAVE, "Ú": _HOOK, "Ü": _TILDE, "Ë": _DOT}
# Ký tự đứng riêng thay cả chữ
_VNI_SINGLE = {"ô": "ơ", "Ô": "Ơ", "ö": "ư", "Ö": "Ư", "ñ": "đ", "Ñ": "Đ",
               "æ": "ỉ", "Æ": "Ỉ", "ó": "ĩ", "Ó": "Ĩ", "ò": "ị", "Ò": "Ị", "î": "ỵ", "Î": "Ỵ"}
_VOWELS = set("aeiouyAEIOUYơưƠƯ")
VNI_CHARS = set(_VNI_TONE) | set(_VNI_CIRC) | set(_VNI_BREVE) | set(_VNI_SINGLE)
# Tổ hợp 'nguyên âm + ký tự dấu' không bao giờ xuất hiện trong tiếng Việt Unicode
_VNI_SIGNATURE = re.compile(r"[aeoAEO][âáàåãäÂÁÀÅÃÄ]|[aA][êéèëÊÉÈË]|[aeiouyöôAEIOUYÖÔ][ùøûõïÙØÛÕÏ]|ñ|Ñ")


def is_vni_font(font_name: str) -> bool:
    return bool(re.search(r"VNI[-_ ]", font_name or "", re.IGNORECASE))


def looks_like_vni(text: str) -> bool:
    """Nhận dạng VNI theo nội dung: nhiều cặp 'chữ gốc + ký tự dấu' đặc trưng."""
    if not text or _REAL_VI.search(text):
        return False
    hits = len(_VNI_SIGNATURE.findall(text))
    words = max(1, len(text.split()))
    if words <= 6:                       # chuỗi ngắn (nhãn bản vẽ, chú thích SHX)
        return hits >= 2
    return hits >= 3 and hits >= 0.1 * words


def _base(ch: str) -> str:
    return unicodedata.normalize("NFD", ch)[:1] if ch else ""


def vni_merge(chars: List[str]) -> List[Tuple[str, List[int]]]:
    """Giải mã dãy ký tự VNI. Trả [(chữ Unicode, [chỉ số ký tự nguồn])] để gộp
    luôn vị trí (bbox) của ký tự dấu vào chữ gốc đứng trước nó."""
    out: List[List[Any]] = []
    for i, ch in enumerate(chars):
        prev = out[-1][0] if out else ""
        pb = _base(prev[-1]) if prev else ""
        if pb in "aeoAEO" and ch in _VNI_CIRC and _CIRC not in prev and _BREVE not in prev:
            out[-1][0] += _CIRC + _VNI_CIRC[ch]
            out[-1][1].append(i)
        elif pb in "aA" and ch in _VNI_BREVE and _CIRC not in prev and _BREVE not in prev:
            out[-1][0] += _BREVE + _VNI_BREVE[ch]
            out[-1][1].append(i)
        elif ch in _VNI_TONE and pb and (pb in _VOWELS or prev[-1] in _VOWELS):
            out[-1][0] += _VNI_TONE[ch]
            out[-1][1].append(i)
        else:
            out.append([_VNI_SINGLE.get(ch, ch), [i]])
    return [(unicodedata.normalize("NFC", t), idx) for t, idx in out]


def vni_to_unicode(text: str) -> str:
    return "".join(t for t, _ in vni_merge(list(text)))
