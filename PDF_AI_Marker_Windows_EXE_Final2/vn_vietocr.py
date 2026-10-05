# -*- coding: utf-8 -*-
"""
VietOCR (vgg_seq2seq, ONNX) — đọc lại DẤU tiếng Việt cho kết quả RapidOCR.

Chạy hoàn toàn bằng onnxruntime + numpy + Pillow (KHÔNG cần PyTorch), nên dùng
được trong bản Lite. Model gốc: https://github.com/pbcquoc/vietocr (Apache-2.0),
đã chuyển sang 2 file ONNX (encoder + decoder 1 bước) trong models/vietocr/.

Cách ghép lai (hybrid) theo từng từ, đã đo trên lớp chữ gốc của PDF:
  * Chữ có dấu           -> lấy của VietOCR (RapidOCR mất dấu hoàn toàn).
  * Số liệu / ký hiệu    -> giữ của RapidOCR (VietOCR hay đọc + thành 4, = thành ?).
  * Từ VietOCR tự thêm   -> bỏ (chống "bịa chữ").
  * Cả dòng lệch hẳn     -> giữ nguyên RapidOCR (chữ xoay, nhiễu, ký hiệu bản vẽ).
  * Chữ in hoa/thường    -> theo RapidOCR (VietOCR hay viết hoa lẫn lộn).
  * Chữ dính liền        -> nếu bỏ dấu + bỏ khoảng trắng hai bên trùng nhau và chuỗi
                            chữ số khớp, nhận cách tách từ của VietOCR
                            (GIAIDOAN4LANXE -> GIAI ĐOẠN 4 LÀN XE).
"""
import difflib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "models" / "vietocr"
_FILES = ("encoder.onnx", "decoder.onnx", "vietocr_meta.json")

VN_MARK = re.compile(r"[À-ỹĐđ]")
HAS_DIGIT = re.compile(r"\d")
HAS_ALPHA = re.compile(r"[A-Za-zÀ-ỹĐđ]")
SYMS = set("+=@%/")


def available(model_dir: Path = MODEL_DIR) -> bool:
    if not all((Path(model_dir) / f).is_file() for f in _FILES):
        return False
    try:
        import onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Bộ nhận dạng ONNX
# ─────────────────────────────────────────────────────────────────────────────
class VietOCRRecognizer:
    def __init__(self, model_dir: Path = MODEL_DIR, threads: Optional[int] = None):
        import onnxruntime as ort
        model_dir = Path(model_dir)
        meta = json.loads((model_dir / "vietocr_meta.json").read_text(encoding="utf-8"))
        self.meta = meta
        off = meta["offset"]
        self.i2c = {i + off: c for i, c in enumerate(meta["vocab"])}
        self.sos, self.eos, self.offset = meta["sos"], meta["eos"], off
        self.h = meta["image_height"]
        self.min_w, self.max_w = meta["image_min_width"], meta["image_max_width"]
        self.max_len = meta["max_seq_length"]

        so = ort.SessionOptions()
        so.log_severity_level = 3
        # Đo thực tế (28 luồng CPU): 4–6 luồng nhanh gấp ~3 lần 14–16 luồng vì mỗi bước giải mã rất nhỏ.
        n = threads or int(os.environ.get("PDF_AI_VIETOCR_THREADS", "0")) or min(6, max(2, (os.cpu_count() or 4) // 2))
        so.intra_op_num_threads = n
        so.inter_op_num_threads = 1
        # Vòng giải mã gồm hàng trăm lượt gọi nhỏ -> CPU nhanh & ổn định hơn GPU DirectML.
        prov = ["CPUExecutionProvider"]
        self.enc = ort.InferenceSession(str(model_dir / "encoder.onnx"), so, providers=prov)
        self.dec = ort.InferenceSession(str(model_dir / "decoder.onnx"), so, providers=prov)

    # -- tiền xử lý giống hệt vietocr.tool.translate.process_image --
    def _width(self, w: int, h: int) -> int:
        new_w = int(self.h * float(w) / float(h))
        new_w = -(-new_w // 10) * 10            # làm tròn lên bội số 10
        return min(max(new_w, self.min_w), self.max_w)

    def _prep(self, img):
        from PIL import Image
        img = img.convert("RGB")
        w, h = img.size
        img = img.resize((self._width(w, h), self.h), Image.LANCZOS)
        return (np.asarray(img, dtype=np.float32) / 255.0).transpose(2, 0, 1)

    def _decode(self, ids: List[int]) -> str:
        out = []
        for i in ids:
            if i == self.eos:
                break
            if i >= self.offset:
                out.append(self.i2c.get(i, ""))
        return "".join(out)

    def _run_batch(self, arrs):
        x = np.stack(arrs).astype(np.float32)
        mem, proj, hidden = self.enc.run(None, {"img": x})
        n = x.shape[0]
        seqs = [[] for _ in range(n)]
        probs = [[] for _ in range(n)]
        active = np.arange(n)
        tgt = np.full(n, self.sos, dtype=np.int64)
        for _ in range(self.max_len + 1):
            idx, prob, hidden = self.dec.run(None, {"tgt": tgt, "hidden": hidden, "mem": mem, "proj": proj})
            done = np.zeros(len(active), dtype=bool)
            for k, row in enumerate(active):
                seqs[row].append(int(idx[k]))
                probs[row].append(float(prob[k]))
                done[k] = idx[k] == self.eos
            if done.all():
                break
            keep = ~done
            if keep.sum() <= 0.75 * len(active):      # thu gọn lô khi nhiều dòng đã xong
                active, idx, hidden = active[keep], idx[keep], hidden[keep]
                mem, proj = mem[keep], proj[keep]
            tgt = idx.astype(np.int64)
        res = []
        for s, p in zip(seqs, probs):
            text = self._decode(s)
            pv = [pp for ii, pp in zip(s, p) if ii >= self.offset]
            res.append((text, float(np.mean(pv)) if pv else 0.0))
        return res

    def predict_batch(self, imgs, batch_size: int = 16):
        """Trả [(text, prob)] theo đúng thứ tự ảnh đầu vào."""
        out = [("", 0.0)] * len(imgs)
        buckets = {}
        for i, im in enumerate(imgs):
            a = self._prep(im)
            buckets.setdefault(a.shape[-1], []).append((i, a))
        for _, items in sorted(buckets.items()):
            for s in range(0, len(items), batch_size):
                chunk = items[s:s + batch_size]
                for (i, _), r in zip(chunk, self._run_batch([a for _, a in chunk])):
                    out[i] = r
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Ghép lai RapidOCR + VietOCR theo từng từ
# ─────────────────────────────────────────────────────────────────────────────
def strip_accents(text: str) -> str:
    out = []
    for ch in text:
        if ch in "đĐ":
            out.append("d" if ch == "đ" else "D")
            continue
        base = "".join(c for c in unicodedata.normalize("NFD", ch) if not unicodedata.combining(c))
        out.append(base[:1] if base else ch)
    return "".join(out)


def _key(w: str) -> str:
    return strip_accents(w).lower()


def _digits(s: str) -> str:
    return "".join(re.findall(r"\d", s))


def _apply_case(rw: str, vw: str) -> str:
    """Viết hoa/thường theo RapidOCR (VietOCR hay ra 'XỐP CHèn Khe')."""
    if len(rw) == len(vw):                       # cùng độ dài -> chép kiểu chữ từng ký tự
        return "".join((v.upper() if r.isupper() else v.lower()) if (r.isalpha() and v.isalpha()) else v
                       for r, v in zip(rw, vw))
    letters = [c for c in rw if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return vw.upper()
    if len(letters) >= 2 and all(c.islower() for c in letters):
        return vw.lower()
    return vw


def _pick(rw: str, vw: str) -> str:
    """Chọn 1 từ khi RapidOCR (rw) và VietOCR (vw) khác nhau."""
    if not HAS_ALPHA.search(rw):                 # thuần số / ký hiệu -> RapidOCR
        return rw
    if HAS_DIGIT.search(vw) or any(c in SYMS for c in rw):
        return rw                                # VietOCR đọc số / ký hiệu -> tin RapidOCR
    if HAS_DIGIT.search(rw):
        # RapidOCR hay đọc nhầm dấu thành số (c6=có, s6=số, D0AN=ĐOẠN)
        return _apply_case(rw, vw) if VN_MARK.search(vw) else rw
    return _apply_case(rw, vw)                   # chữ thường -> VietOCR (có dấu)


def _resplit(rws: List[str], vws: List[str]) -> Optional[List[str]]:
    """Hai bên cùng chuỗi ký tự (bỏ dấu, bỏ khoảng trắng) nhưng tách từ khác nhau."""
    rj, vj = "".join(rws), "".join(vws)
    if len(rj) != len(vj) or _key(rj) != _key(vj):
        return None
    # Theo bên tách được NHIỀU từ hơn: VietOCR khi chữ dính liền (GIAIDOAN -> GIAI ĐOẠN),
    # RapidOCR khi VietOCR dính 'SO LE' -> 'SOLE'. Dấu lấy từ VietOCR, hoa/thường + chữ số theo RapidOCR.
    lens = [len(w) for w in (vws if len(vws) >= len(rws) else rws)]
    out, pos = [], 0
    for n in lens:
        seg_r, seg_v = rj[pos:pos + n], vj[pos:pos + n]
        pos += n
        out.append(_apply_case(seg_r, seg_v) if (HAS_ALPHA.search(seg_r) and not HAS_DIGIT.search(seg_r)) else seg_r)
    return out


def merge(rapid: str, viet: str) -> str:
    if not viet or not viet.strip():
        return rapid
    rk, vk = _key(rapid).replace(" ", ""), _key(viet).replace(" ", "")
    if difflib.SequenceMatcher(None, rk, vk, autojunk=False).ratio() < 0.5:
        return rapid                             # VietOCR đọc lệch hẳn (chữ xoay / nhiễu) -> bỏ
    rw, vw = rapid.split(), viet.split()
    out: List[str] = []
    sm = difflib.SequenceMatcher(None, [_key(w) for w in rw], [_key(w) for w in vw], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out += [_apply_case(a, b) for a, b in zip(rw[i1:i2], vw[j1:j2])]
        elif op == "replace":
            rs, vs = rw[i1:i2], vw[j1:j2]
            split = _resplit(rs, vs)
            if split is not None and _digits("".join(rs)) == _digits("".join(split)):
                out += split
            elif len(rs) == len(vs):
                out += [_pick(a, b) for a, b in zip(rs, vs)]
            else:
                block_r = " ".join(rs)
                if HAS_DIGIT.search(block_r) or any(c in SYMS for c in block_r) \
                        or any(HAS_DIGIT.search(w) for w in vs):
                    out += rs
                else:
                    out += [_apply_case(block_r, w) for w in vs]
        elif op == "delete":                     # VietOCR bỏ sót -> giữ RapidOCR
            out += rw[i1:i2]
        # op == "insert": VietOCR tự thêm từ -> bỏ (chống bịa chữ)
    return " ".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Refiner dùng trong ocr_tiling.ocr_pdf_page (cùng giao diện SuryaRefiner)
# ─────────────────────────────────────────────────────────────────────────────
class VietOCRRefiner:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = Path(model_dir)
        self._rec: Optional[VietOCRRecognizer] = None
        self.stats = {"sent": 0, "changed": 0, "kept_rapid": 0, "seconds": 0.0}

    def _get(self) -> VietOCRRecognizer:
        if self._rec is None:
            self._rec = VietOCRRecognizer(self.model_dir)
        return self._rec

    @staticmethod
    def _crop(pil_img, box, W, H):
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        x0, y0 = max(0, int(min(xs)) - 4), max(0, int(min(ys)) - 4)
        x1, y1 = min(W, int(max(xs)) + 4), min(H, int(max(ys)) + 4)
        if x1 - x0 < 6 or y1 - y0 < 6:
            return None
        c = pil_img.crop((x0, y0, x1, y1))
        if (y1 - y0) > 1.5 * (x1 - x0):          # chữ dọc trên bản vẽ
            c = c.rotate(90, expand=True)
        return c

    def refine(self, pil_img, results: List[List[Any]]) -> List[List[Any]]:
        """results: [[box, text, score], ...] theo tọa độ của pil_img. Sửa tại chỗ."""
        import time
        try:
            from vn_refine import needs_refine
        except Exception:                        # pragma: no cover
            def needs_refine(t):
                return bool(re.search(r"[A-Za-z]{2,}", t))
        W, H = pil_img.size
        crops, targets = [], []
        for idx, entry in enumerate(results):
            text = str(entry[1])
            # Không bỏ qua dòng đã có dấu: RapidOCR hay sinh dấu lẻ tẻ sai ('dién', 'tuyén')
            if not needs_refine(text):
                continue
            c = self._crop(pil_img, entry[0], W, H)
            if c is None:
                continue
            crops.append(c)
            targets.append(idx)
        if not crops:
            return results
        t0 = time.perf_counter()
        preds = self._get().predict_batch(crops)
        self.stats["seconds"] = round(self.stats["seconds"] + time.perf_counter() - t0, 1)
        self.stats["sent"] += len(crops)
        for idx, (viet, _prob) in zip(targets, preds):
            entry = results[idx]
            new = merge(str(entry[1]), viet)
            if new != entry[1]:
                entry[1] = new
                self.stats["changed"] += 1
            else:
                self.stats["kept_rapid"] += 1
        return results

    def close(self):
        self._rec = None
