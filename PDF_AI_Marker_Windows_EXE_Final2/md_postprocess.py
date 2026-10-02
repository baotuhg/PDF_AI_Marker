# -*- coding: utf-8 -*-
"""
md_postprocess.py -- Loc nhieu & khu trung lap trong markdown dau ra PDF AI Marker v3.

Van de chu yeu o trang bia (scan PDF):
  1. Cung mot cum chu xuat hien 2-4 lan lien nhau trong mot bullet.
  2. Chuoi garbled: UAINOHOIUOIOILNQORNU-IHUIHINULUIHID.
  3. Cac bullet gan-giong nhau lien tiep.

Chi xu ly block "### GHI CHU / CHU KHAC TREN BAN VE".
"""

import difflib
import re
import unicodedata
from typing import List, Tuple, Optional


_GHI_CHU_HEADER = "### GHI CHÚ / CHỮ KHÁC TRÊN BẢN VẼ"
_BULLET = re.compile(r"^(- )(.*)", re.DOTALL)
_MERGE_RATIO = 0.82
_MIN_REP_LEN = 10
_OCR_ALT = re.compile(r"⟦OCR khác:[^⟧]*⟧")

_VOWELS_ASCII = set("aeiouAEIOU")
_VN_VOWELS = set("ăâêôơưĩĩ"
                 "áàảãạắằẳẵặ"
                 "ấầẩẫậéèẻẽẹ"
                 "ếềểễệíìỉĩị"
                 "óòỏõọốồổỗộ"
                 "ớờởỡợúùủũụ"
                 "ứừửữựýỳỷỹỵ")
_ALL_VOWELS = _VOWELS_ASCII | _VN_VOWELS | {c.upper() for c in _VN_VOWELS}


def _strip_acc(text: str) -> str:
    out = []
    for ch in text:
        if ch in "đĐ":
            out.append("d" if ch == "đ" else "D")
            continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch)
                       if not unicodedata.combining(c))
        out.append(base[:1] if base else ch)
    return "".join(out)


def _key(text: str) -> str:
    return re.sub(r"\s+", " ", _strip_acc(text).lower()).strip()


def is_garbled(text: str) -> bool:
    t = text.strip()
    if len(t) < 8:
        return False
    alpha = [c for c in t if c.isalpha()]
    if not alpha:
        return False
    vowels_count = sum(1 for c in alpha if c in _ALL_VOWELS)
    vowel_ratio = vowels_count / len(alpha)
    if vowel_ratio < 0.08 and len(alpha) >= 12:
        return True
    no_space = " " not in t
    all_upper = t.replace("-", "").replace("_", "").isupper()
    if no_space and all_upper and len(alpha) >= 12 and vowel_ratio < 0.20:
        return True
    no_vn = not any(ord(c) > 0x7F for c in t)
    if no_space and no_vn and all_upper and len(t) >= 16:
        return True
    return False


def _count_vn(text: str) -> int:
    return sum(1 for c in text if ord(c) > 0x7F)


def _best_of_two(a: str, b: str) -> str:
    va, vb = _count_vn(a), _count_vn(b)
    if vb > va * 1.1 and len(b) > 5:
        return b
    if len(b) > len(a) * 1.2:
        return b
    return a


def _find_any_repeat(words: List[str]) -> Optional[Tuple[int, int]]:
    kw = [_key(w) for w in words]
    n = len(kw)
    for plen in range(min(6, n // 2), 2, -1):
        pat = kw[:plen]
        for j in range(plen, n - plen + 1):
            if kw[j:j + plen] == pat:
                return (0, j)
    for plen in range(4, 2, -1):
        for i in range(n - plen):
            for j in range(i + plen, n - plen + 1):
                if kw[i:i + plen] == kw[j:j + plen]:
                    return (i, j)
    return None


def intra_bullet_dedup(text: str) -> str:
    t = text.strip()
    if len(t) < _MIN_REP_LEN * 2:
        return t
    # Strip OCR alt annotations truoc khi tim lap (tranh false positive)
    t_for_search = _OCR_ALT.sub("", t).strip()
    words = t_for_search.split()
    if len(words) < 5:
        return t
    pos = _find_any_repeat(words)
    if pos is None:
        return t  # Giu ban goc co annotation
    i, j = pos
    if i == 0:
        chunk_a = " ".join(words[:j]).strip()
        chunk_b = " ".join(words[j:]).strip()
    else:
        chunk_a = " ".join(words[:i]).strip()
        chunk_b_raw = " ".join(words[j:]).strip()
        chunk_b = intra_bullet_dedup(chunk_b_raw) if chunk_b_raw else ""
        return (chunk_a + " " + chunk_b).strip() if chunk_b else chunk_a
    chunk_b_clean = intra_bullet_dedup(chunk_b)
    return _best_of_two(chunk_a, chunk_b_clean)


def inter_bullet_dedup(bullets: List[str]) -> List[str]:
    if not bullets:
        return bullets
    result: List[str] = []
    used = [False] * len(bullets)
    for i, b in enumerate(bullets):
        if used[i]:
            continue
        best = b
        for j in range(i + 1, len(bullets)):
            if used[j]:
                continue
            ki, kj = _key(b), _key(bullets[j])
            if not ki or not kj:
                continue
            ratio = difflib.SequenceMatcher(None, ki, kj).ratio()
            if ratio >= _MERGE_RATIO:
                best = _best_of_two(best, bullets[j])
                used[j] = True
        result.append(best)
        used[i] = True
    return result


def clean_ghi_chu_block(lines: List[str]) -> List[str]:
    bullets_raw: List[Tuple[str, str, int]] = []
    other_lines: List[Tuple[int, str]] = []
    slot = 0
    for line in lines:
        m = _BULLET.match(line)
        if m:
            bullets_raw.append((m.group(1), m.group(2), slot))
        else:
            other_lines.append((slot, line))
        slot += 1
    cleaned: List[Tuple[str, str, int]] = []
    for prefix, text, pos in bullets_raw:
        text_c = intra_bullet_dedup(text)
        if is_garbled(text_c):
            continue
        if len(text_c.strip()) == 0:
            continue
        cleaned.append((prefix, text_c, pos))
    texts = [t for _, t, _ in cleaned]
    deduped = inter_bullet_dedup(texts)
    seen: set = set()
    final: List[Tuple[int, str]] = []
    for (prefix, _, pos), dt in zip(cleaned, deduped):
        k = _key(dt)[:60]
        if k in seen:
            continue
        seen.add(k)
        final.append((pos, f"{prefix}{dt}"))
    all_out: List[Tuple[int, str]] = final + other_lines
    all_out.sort(key=lambda x: x[0])
    return [line for _, line in all_out]


def postprocess_markdown(md: str) -> str:
    """Loc toan bo markdown, xu ly cac block GHI CHU."""
    lines = md.split("\n")
    result: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.strip() == _GHI_CHU_HEADER:
            result.append(line)
            i += 1
            block: List[str] = []
            while i < n:
                nl = lines[i]
                if (nl.startswith("### ") or nl.startswith("## ") or
                        nl.startswith("# ") or nl.startswith("> ")):
                    break
                block.append(nl)
                i += 1
            result.extend(clean_ghi_chu_block(block))
        else:
            result.append(line)
            i += 1
    return "\n".join(result)


def postprocess_file(input_path: str, output_path=None, inplace: bool = False) -> dict:
    """Doc file markdown, lam sach, ghi ra. Tra dict thong ke."""
    from pathlib import Path
    src = Path(input_path)
    original = src.read_text(encoding="utf-8")
    cleaned = postprocess_markdown(original)
    orig_lines = original.count("\n")
    clean_lines = cleaned.count("\n")
    if inplace:
        src.write_text(cleaned, encoding="utf-8")
        out_path = src
    else:
        dst = Path(output_path) if output_path else src.with_suffix(".clean.md")
        dst.write_text(cleaned, encoding="utf-8")
        out_path = dst
    return {
        "input": str(src),
        "output": str(out_path),
        "lines_before": orig_lines,
        "lines_after": clean_lines,
        "lines_removed": orig_lines - clean_lines,
        "size_before_kb": round(len(original.encode()) / 1024, 1),
        "size_after_kb": round(len(cleaned.encode()) / 1024, 1),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCach dung:")
        print("  python md_postprocess.py <noi_dung.md> [--inplace]")
        print("  python md_postprocess.py <noi_dung.md> <output.md>")
        sys.exit(1)
    inp = sys.argv[1]
    inplace = "--inplace" in sys.argv
    out = None
    if not inplace and len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        out = sys.argv[2]
    stats = postprocess_file(inp, out, inplace=inplace)
    print(f"\nHoan tat lam sach markdown:")
    print(f"  Dau vao : {stats['input']} ({stats['size_before_kb']} KB, {stats['lines_before']} dong)")
    print(f"  Dau ra  : {stats['output']} ({stats['size_after_kb']} KB, {stats['lines_after']} dong)")
    print(f"  Da loc  : {stats['lines_removed']} dong nhieu")
