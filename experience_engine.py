# -*- coding: utf-8 -*-
"""
AEC Continuous Experience Engine (Bộ Não Tự Đúc Rút Kinh Nghiệm & Tiến Hóa Liên Tục)
PDF AI Marker v3 — Lite & Pro Edition
Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG) — baotuhg@gmail.com

Chức năng:
1. Lưu trữ và tích lũy tri thức kỹ thuật xây dựng (AEC Knowledge Base) qua từng hồ sơ.
2. Tự soi chiếu (Self-Reflection): Tìm các dị biệt OCR, từ thiếu dấu, từ dính nét scan.
3. Đúc rút bài học (Distillation): Học từ vựng chuyên ngành, mẫu tiêu đề bảng, cặp từ sửa lỗi.
4. Tự tiến hóa (Self-Evolution): Nạp tức thì (Hot-Reload) bài học mới vào `vn_diacritics` & `table_agent`.
5. Hiển thị quỹ đạo tiến hóa (Learning Curve): Báo cáo số lượng kinh nghiệm tích lũy qua từng file.
"""
from pathlib import Path
import json
import re
import unicodedata
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

try:
    from app_log import get_logger
    log = get_logger(__name__)
except Exception:                      # app_log luôn import được; phòng xa vẫn không làm vỡ engine
    import logging
    log = logging.getLogger("pdf_ai.experience")


class AECExperienceEngine:
    """
    Hệ thống Tự Học & Đúc Rút Kinh Nghiệm Tích Lũy cho AI Marker.
    Mỗi lần đọc một hồ sơ, hệ thống tự trích xuất kinh nghiệm và trở nên thông minh hơn.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            self.db_path = Path(__file__).resolve().parent / "experience_db.json"
        else:
            self.db_path = Path(db_path)

        self.knowledge: Dict[str, Any] = {
            "version": "2.0",
            "last_updated": "",
            "total_documents_read": 0,
            "learned_phrases": {},      # { "tu_khong_dau": "Từ Có Dấu Chuẩn" } (gốc, nạp 1 lần)
            "ocr_corrections": {},      # { "sai_do_ocr": "sửa_đúng" } (cần tín hiệu raw↔corrected)
            "unsticking_rules": {},     # { "tudinh": "từ tách" }
            "table_header_aliases": {}, # { "alias": "standard_column" }
            "abbreviations": {},        # { "BTCT": "Bê tông cốt thép" } — học từ ĐỊNH NGHĨA trong văn bản
            "term_glossary": {},        # { "cụm từ có dấu": tần suất tích lũy } — vốn từ corpus học được
            "history_log": []           # [ { "doc": ..., "timestamp": ..., "lessons_learned": ... } ]
        }
        # Theo dõi phần ĐÃ nạp vào engine sống (idempotent — chống phình bộ nhớ khi đọc batch)
        self._injected_phrases: set = set()
        self._injected_unstick: set = set()
        self._injected_aliases: set = set()
        self.load_db()

    def load_db(self):
        """Nạp dữ liệu kinh nghiệm đã tích lũy từ tệp JSON."""
        if self.db_path.exists():
            try:
                with self.db_path.open("r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k in self.knowledge:
                        if k in saved:
                            self.knowledge[k] = saved[k]
            except Exception as e:
                log.warning("Đọc experience_db lỗi: %s", e)

    def save_db(self):
        """Lưu trữ dữ liệu kinh nghiệm xuống tệp JSON."""
        self.knowledge["last_updated"] = datetime.now().isoformat()
        try:
            with self.db_path.open("w", encoding="utf-8") as f:
                json.dump(self.knowledge, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning("Ghi experience_db lỗi: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # HÀM PHỤ TRỢ TRÍCH XUẤT TRI THỨC THẬT TỪ NỘI DUNG
    # ─────────────────────────────────────────────────────────────────────────
    _STOPWORDS = {
        "của", "và", "là", "các", "những", "được", "trong", "theo", "với", "cho",
        "này", "đó", "khi", "đã", "sẽ", "có", "không", "như", "tại", "trên", "dưới",
        "từ", "đến", "để", "một", "hoặc", "nếu", "thì", "mà", "do", "bởi", "vì",
        "nên", "cũng", "rất", "thêm", "gồm", "bao", "sau", "trước", "ra", "vào", "tới",
    }

    @staticmethod
    def _strip_accents(s: str) -> str:
        nfd = unicodedata.normalize("NFD", s)
        out = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
        return out.replace("đ", "d").replace("Đ", "D")

    @classmethod
    def _has_diacritic(cls, word: str) -> bool:
        """True nếu từ có dấu tiếng Việt (để loại chữ OCR không dấu / rác)."""
        return word.lower() != cls._strip_accents(word).lower()

    @classmethod
    def _acronym_matches(cls, acro: str, full: str) -> bool:
        """Kiểm tra ACRO có đúng là chữ cái đầu của cụm từ đầy đủ không (lọc nhiễu)."""
        words = [w for w in re.split(r"\s+", full.strip()) if w and w[:1].isalpha()]
        if len(words) < 2:
            return False
        a = cls._strip_accents(acro).upper()
        initials = "".join(cls._strip_accents(w[0]).upper() for w in words)
        if a == initials:
            return True
        # Cho phép bỏ qua các từ nối ngắn (và, của, các, để, cho...)
        core = [w for w in words if cls._strip_accents(w).lower()
                not in {"va", "cua", "cac", "de", "cho", "cong"}]
        initials2 = "".join(cls._strip_accents(w[0]).upper() for w in core)
        return a == initials2

    @classmethod
    def _best_expansion(cls, acro: str, full: str):
        """Chọn CỬA SỔ từ-cuối khớp acronym (vd 'Hệ thống phòng cháy chữa cháy (PCCC)'
        → 'phòng cháy chữa cháy'), tránh bắt tham lam dư từ đứng trước. None nếu không khớp."""
        words = [w for w in re.split(r"\s+", full.strip()) if w and w[:1].isalpha()]
        if not words:
            return None
        a = cls._strip_accents(acro).upper()
        n = len(a)
        skip = {"va", "cua", "cac", "de", "cho", "cong", "he", "thong"}
        for k in (n, n + 1, n + 2, n + 3):     # thử vài cửa sổ cuối (bù từ nối)
            if 2 <= k <= len(words):
                window = words[-k:]
                ini = "".join(cls._strip_accents(w[0]).upper() for w in window)
                core = [w for w in window if cls._strip_accents(w).lower() not in skip]
                ini_core = "".join(cls._strip_accents(w[0]).upper() for w in core)
                if a == ini:
                    return " ".join(window)
                if a == ini_core and len(core) >= 2:
                    return " ".join(core)
        return cls._acronym_matches(acro, full) and full.strip() or None

    def _learn_abbreviations(self, text: str) -> int:
        """Học từ viết tắt được ĐỊNH NGHĨA ngay trong văn bản (dữ liệu tự gán nhãn)."""
        pairs = []
        # Mẫu 1: "Cụm từ đầy đủ (ACRO)"
        for m in re.finditer(
            r"([A-Za-zÀ-ỹĐđ][\wÀ-ỹĐđ]*(?:\s+[\wÀ-ỹĐđ]+){1,7})\s*\(\s*([A-ZĐ]{2,8})\s*\)", text):
            pairs.append((m.group(2), m.group(1)))
        # Mẫu 2: "ACRO (Cụm từ đầy đủ)"
        for m in re.finditer(
            r"\b([A-ZĐ]{2,8})\s*\(\s*([A-Za-zÀ-ỹĐđ][^)\n]{3,60})\)", text):
            pairs.append((m.group(1), m.group(2)))
        # Mẫu 3: dòng chú thích "ACRO : Cụm từ" / "ACRO = Cụm từ"
        for m in re.finditer(
            r"(?m)^\s*([A-ZĐ]{2,8})\s*[:=]\s*([A-ZÀ-Ỹ][A-Za-zÀ-ỹĐđ ]{3,60})$", text):
            pairs.append((m.group(1), m.group(2)))

        new = 0
        for acro, full in pairs:
            acro = acro.strip().upper()
            full = re.sub(r"\s+", " ", full).strip(" .:-–—")
            exp = self._best_expansion(acro, full)
            if not exp or len(exp.split()) < 2:
                continue
            if acro not in self.knowledge["abbreviations"]:
                self.knowledge["abbreviations"][acro] = exp
                new += 1
        return new

    def _learn_terms(self, text: str) -> int:
        """Học thuật ngữ chuyên ngành: cụm 2–3 từ CÓ DẤU, LẶP LẠI trong hồ sơ."""
        tokens = [t for t in re.findall(r"[A-Za-zÀ-ỹĐđ]+", text) if len(t) >= 2]
        counts: Dict[str, int] = {}
        for n in (2, 3):
            for i in range(len(tokens) - n + 1):
                gram = tokens[i:i + n]
                low = [w.lower() for w in gram]
                if any(w in self._STOPWORDS for w in low):
                    continue
                if sum(1 for w in gram if self._has_diacritic(w)) < (n + 1) // 2:
                    continue
                key = " ".join(low)
                counts[key] = counts.get(key, 0) + 1

        new = 0
        glossary = self.knowledge["term_glossary"]
        for key, c in counts.items():
            if c < 2:                       # chỉ học cụm LẶP LẠI (giảm nhiễu OCR)
                continue
            if key not in glossary:
                glossary[key] = 0
                new += 1
            glossary[key] += c
        return new

    # ─────────────────────────────────────────────────────────────────────────
    # BỘ NÃO SOI CHIẾU & ĐÚC RÚT KINH NGHIỆM TỪ VĂN BẢN
    # ─────────────────────────────────────────────────────────────────────────
    def distill_text_experience(self, text: str, doc_name: str = "") -> Dict[str, int]:
        """
        Đúc rút tri thức THỰC SỰ MỚI từ NỘI DUNG tài liệu (không phải danh sách cứng):
          • Từ viết tắt được ĐỊNH NGHĨA ngay trong văn bản — dữ liệu tự gán nhãn, tin cậy cao.
          • Thuật ngữ chuyên ngành (cụm 2–3 từ có dấu) LẶP LẠI trong hồ sơ — vốn từ corpus.

        LƯU Ý KIẾN TRÚC: trả về 0 khi tài liệu không có gì chưa từng gặp là ĐÚNG. Khác hẳn
        lỗi cũ (luôn = 0 sau vài hồ sơ đầu): bản cũ chỉ dò 3 DANH SÁCH CỨNG rồi thêm lại chính
        các mục cứng đó, không hề đọc nội dung — nên cạn kiệt sau ~10–15 hồ sơ và mãi mãi = 0.
        """
        if not text:
            return {"new_abbr": 0, "new_terms": 0}
        return {
            "new_abbr": self._learn_abbreviations(text),
            "new_terms": self._learn_terms(text),
        }

    def distill_table_experience(self, tables: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Học các biến thể tiêu đề cột từ các bảng biểu mới bóc tách được.
        """
        new_headers = 0
        header_map_rules = [
            ("sô hiệu", "mark"),
            ("so hieu", "mark"),
            ("tên cấu kiện", "element"),
            ("ten cau kien", "element"),
            ("hang muc", "item_name"),
            ("hạng mục công việc", "item_name"),
            ("khôi lượng", "quantity"),
            ("khoi luong", "quantity"),
            ("dơn gia", "unit_price"),
            ("don gia", "unit_price"),
            ("thanh tiên", "total_price"),
            ("thanh tien", "total_price"),
            ("quy cách", "specs"),
            ("quy cach", "specs"),
            ("tiêu chuẩn kỹ thuật", "standard"),
            ("chủng loại", "material_type"),
        ]

        for table in tables:
            headers = table.get("headers", [])
            for h in headers:
                if not h:
                    continue
                h_norm = unicodedata.normalize("NFD", str(h).strip().lower())
                h_ascii = "".join(c for c in h_norm if unicodedata.category(c) != "Mn")
                for pat, std_col in header_map_rules:
                    if pat in h_ascii and h_ascii not in self.knowledge["table_header_aliases"]:
                        self.knowledge["table_header_aliases"][h_ascii] = std_col
                        new_headers += 1

        return {"new_headers": new_headers}

    # ─────────────────────────────────────────────────────────────────────────
    # ĐỒNG BỘ VÀ NẠP TỨC THÌ (HOT-RELOAD) VÀO BỘ MÁY OCR & TABLE AGENT
    # ─────────────────────────────────────────────────────────────────────────
    def sync_to_live_engines(self):
        """
        Nạp tri thức AN TOÀN vào engine đang chạy — CÓ KIỂM SOÁT:
          • Idempotent: chỉ nạp phần CHƯA nạp (dùng self._injected_*). Bản cũ append TẤT CẢ
            learned_phrases vào AEC_COMPOUND_PHRASES MỖI epoch → phình O(n×epoch) và recompile
            toàn bộ regex mỗi lần (rò rỉ bộ nhớ + chậm dần trong chế độ batch).
          • KHÔNG tự bơm `term_glossary` (thuật ngữ học-tự-động) vào bộ khôi phục dấu để tránh
            VÒNG LẶP PHẢN HỒI làm trôi chất lượng. Thuật ngữ mới phục vụ RAG/gợi ý-AI và chờ duyệt.
          • Tái tạo restorer theo kiểu LAZY (đặt _DEFAULT_RESTORER=None) thay vì dựng lại ngay.
        """
        try:
            import vn_diacritics
            changed = False
            # 1. Nạp 1 lần các cụm từ ghép GỐC (learned_phrases nạp sẵn từ DB), không lặp lại
            for raw_k, phr in self.knowledge.get("learned_phrases", {}).items():
                if raw_k in self._injected_phrases:
                    continue
                vn_diacritics.AEC_COMPOUND_PHRASES.append((raw_k, phr))
                self._injected_phrases.add(raw_k)
                changed = True
            # 2. Nạp quy tắc tách từ dính (chỉ phần mới)
            for k, repl in self.knowledge.get("unsticking_rules", {}).items():
                if k in self._injected_unstick:
                    continue
                vn_diacritics.AEC_UNSTICKING_RULES.insert(0, (r"\b" + re.escape(k) + r"\b", repl))
                self._injected_unstick.add(k)
                changed = True
            if changed:
                vn_diacritics._DEFAULT_RESTORER = None   # dựng lại lười ở lần restore kế tiếp
        except Exception as e:
            log.warning("Đồng bộ vn_diacritics lỗi: %s", e)

        try:
            import table_agent
            for alias, std_col in self.knowledge.get("table_header_aliases", {}).items():
                if alias in self._injected_aliases:
                    continue
                if std_col == "mark":
                    table_agent.MARK_ALIASES.add(alias)
                elif std_col == "quantity":
                    table_agent.QTY_ALIASES.add(alias)
                self._injected_aliases.add(alias)
        except Exception as e:
            log.warning("Đồng bộ table_agent lỗi: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # HỌC CÓ GIÁM SÁT: SỬA LỖI OCR TỪ NGƯỜI DÙNG (du_lieu raw ↔ chữ người sửa)
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _has_digit(s: str) -> bool:
        return bool(re.search(r"\d", s or ""))

    def learn_ocr_correction(self, raw: str, corrected: str, source: str = "",
                             min_len: int = 2, persist: bool = True) -> Dict[str, Any]:
        """
        Học MỘT cặp sửa lỗi OCR do NGƯỜI dùng xác nhận trong màn Đối chiếu (có giám sát).

        An toàn: chỉ cặp CHỮ (không chứa số) mới được đánh dấu `safe` để ÁP DỤNG LẠI tự động
        cho các hồ sơ sau. Sửa SỐ chỉ được LƯU để truy vết, KHÔNG tổng quát hóa — vì một con số
        đúng cho ô này có thể sai cho ô/hồ sơ khác.
        """
        res = {"stored": False, "safe": False, "reason": ""}
        raw = re.sub(r"⟦[^⟧]*⟧", "", (raw or "")).strip()   # bỏ ký hiệu ⟦OCR khác: …⟧
        corrected = (corrected or "").strip()
        if not raw or not corrected or raw == corrected:
            res["reason"] = "rỗng hoặc không thay đổi"
            return res
        if len(raw) < min_len:
            res["reason"] = "quá ngắn"
            return res

        safe = (not self._has_digit(raw) and not self._has_digit(corrected)
                and len(raw) <= 60 and "\n" not in raw)
        store = self.knowledge["ocr_corrections"]
        entry = store.get(raw)
        if not isinstance(entry, dict):   # mới, hoặc nâng cấp từ schema cũ (chuỗi)
            entry = {"corrected": corrected, "count": 0, "safe": safe, "source": source}
            store[raw] = entry
        else:
            entry["corrected"] = corrected
            entry["safe"] = safe
            entry["source"] = source or entry.get("source", "")
        entry["count"] = entry.get("count", 0) + 1
        if persist:
            self.save_db()

        # Nạp nóng vào bộ khôi phục dấu đang chạy (nếu có) để hiệu lực ngay
        if safe:
            try:
                import vn_diacritics
                if vn_diacritics._DEFAULT_RESTORER is not None:
                    vn_diacritics._DEFAULT_RESTORER.add_correction(raw, corrected)
                else:
                    vn_diacritics._DEFAULT_RESTORER = None
            except Exception:
                pass

        res.update(stored=True, safe=safe)
        return res

    def get_safe_corrections(self, min_count: int = 1) -> Dict[str, str]:
        """Trả {raw: corrected} cho các cặp sửa lỗi AN TOÀN, đủ tin cậy (áp dụng tự động)."""
        out: Dict[str, str] = {}
        for raw, e in (self.knowledge.get("ocr_corrections", {}) or {}).items():
            if isinstance(e, dict):
                if e.get("safe") and e.get("count", 0) >= min_count and e.get("corrected"):
                    out[raw] = e["corrected"]
            elif not self._has_digit(raw):   # schema cũ dạng chuỗi
                out[raw] = str(e)
        return out

    # ─────────────────────────────────────────────────────────────────────────
    # HUẤN LUYỆN TỪ KHÁC BIỆT: người dùng SỬA THẲNG noi_dung.md → tool tự học
    # ─────────────────────────────────────────────────────────────────────────
    _EDGE_PUNCT = " \t.,;:!?()[]{}\"'«»…·•-–—|*#>"

    def _consider_pair(self, old: str, new: str, source: str, max_words: int,
                       stats: Dict[str, int]):
        # Cắt dấu câu/markdown ở HAI ĐẦU để cặp học tổng quát được (neo \b hoạt động đúng,
        # vd 'chiu lyrc,' -> 'chiu lyrc'); giữ nguyên dấu bên trong từ.
        old = old.strip(self._EDGE_PUNCT)
        new = new.strip(self._EDGE_PUNCT)
        if not old or not new or old == new:
            stats["skipped"] += 1
            return
        # Cả câu viết lại → KHÔNG học (chỉ học sửa mức từ/cụm ngắn, mới tổng quát hóa được)
        if len(old.split()) > max_words or len(new.split()) > max_words:
            stats["skipped"] += 1
            return
        # Chỉ toàn ký hiệu/markdown (| # * …) → bỏ
        if re.fullmatch(r"[\W_]+", old) or re.fullmatch(r"[\W_]+", new):
            stats["skipped"] += 1
            return
        res = self.learn_ocr_correction(old, new, source=source, persist=False)
        if not res.get("stored"):
            stats["skipped"] += 1
        elif res.get("safe"):
            stats["learned"] += 1      # cặp CHỮ → sẽ tự áp dụng cho hồ sơ sau
        else:
            stats["numeric"] += 1      # cặp có SỐ → chỉ lưu truy vết, không tổng quát hóa

    def learn_from_markdown_diff(self, ai_text: str, corrected_text: str,
                                 source: str = "", max_words: int = 6) -> Dict[str, int]:
        """
        Học từ KHÁC BIỆT giữa bản AI xuất ra (`ai_text`) và bản người dùng SỬA ĐÚNG
        (`corrected_text`). Biến việc sửa file `noi_dung.md` thành dữ liệu huấn luyện.

        Chỉ học sửa ở DÒNG THAY ĐỔI (opcode 'replace'); dòng được THÊM/BỚT bị bỏ qua vì đó là
        thay đổi cấu trúc/thứ-tự-đọc — không thể tổng quát hóa bằng tìm-thay-thế. Trong mỗi dòng,
        chỉ lấy các cụm từ bị đổi (token-level), lọc an toàn qua `learn_ocr_correction`.
        """
        import difflib
        stats = {"learned": 0, "numeric": 0, "skipped": 0}
        if not ai_text or not corrected_text or ai_text == corrected_text:
            return stats
        ai_lines = ai_text.splitlines()
        co_lines = corrected_text.splitlines()
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                a=ai_lines, b=co_lines, autojunk=False).get_opcodes():
            if tag != "replace":
                continue
            ot = " ".join(ai_lines[i1:i2]).split()
            nt = " ".join(co_lines[j1:j2]).split()
            for t, a1, a2, b1, b2 in difflib.SequenceMatcher(
                    a=ot, b=nt, autojunk=False).get_opcodes():
                if t == "replace":
                    self._consider_pair(" ".join(ot[a1:a2]), " ".join(nt[b1:b2]),
                                        source, max_words, stats)
        self.save_db()
        return stats

    def learn_from_result_folder(self, folder) -> Dict[str, Any]:
        """Học từ một thư mục kết quả (*_Marker): so `noi_dung.ai.md` (bản AI gốc) với
        `noi_dung.md` (bản người dùng đã sửa). Ghi dấu `.learned` để không học lại cùng bản sửa."""
        from pathlib import Path
        import hashlib
        folder = Path(folder)
        ai_f, cur_f = folder / "noi_dung.ai.md", folder / "noi_dung.md"
        if not ai_f.exists() or not cur_f.exists():
            return {"learned": 0, "numeric": 0, "skipped": 0, "reason": "thiếu noi_dung.ai.md / noi_dung.md"}
        ai_text = ai_f.read_text(encoding="utf-8", errors="ignore")
        cur_text = cur_f.read_text(encoding="utf-8", errors="ignore")
        if ai_text == cur_text:
            return {"learned": 0, "numeric": 0, "skipped": 0, "reason": "chưa chỉnh sửa gì"}
        cur_hash = hashlib.sha256(cur_text.encode("utf-8")).hexdigest()
        marker = folder / ".learned"
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == cur_hash:
                return {"learned": 0, "numeric": 0, "skipped": 0, "reason": "đã học bản sửa này rồi"}
        except Exception:
            pass
        stats = self.learn_from_markdown_diff(ai_text, cur_text, source=folder.name)
        try:
            marker.write_text(cur_hash, encoding="utf-8")
        except Exception:
            pass
        return stats

    def scan_and_learn(self, output_root) -> Dict[str, int]:
        """Quét mọi thư mục `*_Marker` trong thư mục xuất, tự học từ các hồ sơ đã được sửa.
        Gọi ở đầu mỗi lần chuyển đổi → 'tự cập nhật sau mỗi lần đọc hồ sơ mới'."""
        from pathlib import Path
        agg = {"folders": 0, "learned": 0, "numeric": 0, "skipped": 0}
        try:
            out = Path(output_root)
            if not out.exists():
                return agg
            for d in sorted(out.glob("*_Marker")):
                if not d.is_dir():
                    continue
                st = self.learn_from_result_folder(d)
                if st.get("learned") or st.get("numeric"):
                    agg["folders"] += 1
                    agg["learned"] += st.get("learned", 0)
                    agg["numeric"] += st.get("numeric", 0)
                    agg["skipped"] += st.get("skipped", 0)
        except Exception as e:
            log.warning("scan_and_learn lỗi: %s", e)
        return agg

    def apply_corrections_to_text(self, text: str) -> str:
        """Áp dụng các sửa lỗi CHỮ an toàn (đã học) lên markdown CUỐI CÙNG của hồ sơ mới.
        Literal, giữ kiểu hoa/thường; keyed theo đúng dạng văn bản người dùng đã sửa."""
        if not text:
            return text
        try:
            from vn_diacritics import _apply_correction
        except Exception:
            def _apply_correction(span, corrected):   # fallback đơn giản
                return corrected
        for raw, corrected in self.get_safe_corrections().items():
            pat = r"\b" + r"\s+".join(re.escape(w) for w in raw.split()) + r"\b"
            try:
                text = re.sub(pat, lambda m, c=corrected: _apply_correction(m.group(0), c),
                              text, flags=re.IGNORECASE)
            except re.error:
                continue
        return text

    def record_epoch(self, doc_name: str, pages_count: int, lessons: Dict[str, Any]):
        """Ghi nhận phiên học tập hoàn thành một hồ sơ."""
        self.knowledge["total_documents_read"] += 1
        entry = {
            "epoch": self.knowledge["total_documents_read"],
            "document": doc_name,
            "pages": pages_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lessons_learned": lessons,
            "cumulative_memory": {
                "phrases": len(self.knowledge["term_glossary"]),
                "unstick_rules": len(self.knowledge["unsticking_rules"]),
                "abbreviations": len(self.knowledge["abbreviations"]),
                "table_aliases": len(self.knowledge["table_header_aliases"]),
                "terms": len(self.knowledge["term_glossary"]),
                "ocr_corrections": len(self.knowledge.get("ocr_corrections", {})),
            }
        }
        self.knowledge["history_log"].append(entry)
        self.save_db()
        self.sync_to_live_engines()
        return entry

    def get_summary_report(self) -> str:
        """Tạo báo cáo tóm tắt quá trình tiến hóa và tích lũy tri thức."""
        k = self.knowledge
        lines = [
            "==================================================================",
            "🎓 BÁO CÁO TIẾN HÓA BỘ NÃO KINH NGHIỆM AEC (EXPERIENCE ENGINE)",
            "==================================================================",
            f"📁 Tổng số hồ sơ đã học: {k['total_documents_read']}",
            f"📚 Vốn từ chuyên ngành học từ corpus: {len(k.get('term_glossary', {}))} cụm",
            f"🏷️  Từ viết tắt TỰ ĐỊNH NGHĨA học được: {len(k['abbreviations'])} từ",
            f"⚡ Quy tắc tách từ dính scan CAD: {len(k['unsticking_rules'])} quy tắc",
            f"📊 Biến thể tiêu đề bảng BoQ/Thép: {len(k['table_header_aliases'])} biến thể",
            f"✍️  Sửa lỗi OCR người dùng dạy: {len(k.get('ocr_corrections', {}))} cặp "
            f"({len(self.get_safe_corrections())} áp dụng tự động)",
            f"📖 Cụm từ ghép nạp sẵn (gốc): {len(k['learned_phrases'])} cụm",
            "------------------------------------------------------------------",
            "LỊCH SỬ HỌC TẬP GẦN ĐÂY:"
        ]
        for item in k["history_log"][-5:]:
            lines.append(f"  • [Epoch {item['epoch']}] {item['document']} ({item['pages']} trang): Học được {sum(item['lessons_learned'].values())} tri thức mới.")
        lines.append("==================================================================")
        return "\n".join(lines)


# Singleton toàn cục
_DEFAULT_ENGINE: Optional[AECExperienceEngine] = None


def get_experience_engine() -> AECExperienceEngine:
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AECExperienceEngine()
    return _DEFAULT_ENGINE
