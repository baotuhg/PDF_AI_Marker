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
            "version": "1.0",
            "last_updated": "",
            "total_documents_read": 0,
            "learned_phrases": {},      # { "tu_khong_dau": "Từ Có Dấu Chuẩn" }
            "ocr_corrections": {},      # { "sai_do_ocr": "sửa_đúng" }
            "unsticking_rules": {},     # { "tudinh": "từ tách" }
            "table_header_aliases": {}, # { "alias": "standard_column" }
            "abbreviations": {},        # { "KTX": "Ký túc xá", "BASTAF": "Bể xử lý nước thải Bastaf" }
            "history_log": []           # [ { "doc": ..., "timestamp": ..., "learned_count": ... } ]
        }
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
                print(f"[ExperienceEngine] Cảnh báo đọc DB: {e}")

    def save_db(self):
        """Lưu trữ dữ liệu kinh nghiệm xuống tệp JSON."""
        self.knowledge["last_updated"] = datetime.now().isoformat()
        try:
            with self.db_path.open("w", encoding="utf-8") as f:
                json.dump(self.knowledge, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ExperienceEngine] Lỗi ghi DB: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # BỘ NÃO SOI CHIẾU & ĐÚC RÚT KINH NGHIỆM TỪ VĂN BẢN
    # ─────────────────────────────────────────────────────────────────────────
    def distill_text_experience(self, text: str, doc_name: str = "") -> Dict[str, int]:
        """
        Phân tích văn bản của một hồ sơ để tự động đúc rút các thuật ngữ mới,
        các từ viết tắt, các lỗi OCR và bổ sung vào Ngân hàng kinh nghiệm.
        """
        new_phrases = 0
        new_unstick = 0
        new_abbr = 0

        # 1. Phát hiện các cụm từ viết hoa / thuật ngữ kỹ thuật đặc thù
        # VD: BASTAF, uPVC, HDPE, BTCT, THCS, PTTHNT, KTX, PCCC, TBA, CB400, CB300, M200, M250, M300
        abbr_patterns = [
            (r"\bBASTAF\b", "Bể tự hoại xử lý nước thải Bastaf"),
            (r"\bPTTHNT\b", "Phổ thông Dân tộc Nội trú"),
            (r"\bTHCS\b", "Trung học Cơ sở"),
            (r"\bKTX\b", "Ký túc xá"),
            (r"\bTH\b", "Tiểu học"),
            (r"\bPCCC\b", "Phòng cháy Chữa cháy"),
            (r"\bTBA\b", "Trạm Biến áp"),
            (r"\buPVC\b", "Ống nhựa uPVC"),
            (r"\bHDPE\b", "Ống nhựa HDPE"),
            (r"\bXLNT\b", "Xử lý nước thải"),
            (r"\bHTKT\b", "Hạ tầng kỹ thuật"),
            (r"\bTMB\b", "Tổng mặt bằng"),
            (r"\bCTST\b", "Công trình sinh hoạt"),
            (r"\bBTXM\b", "Bê tông xi măng"),
            (r"\bBTCT\b", "Bê tông cốt thép"),
            (r"\bCPĐD\b", "Cấp phối đá dăm"),
        ]
        for pat, desc in abbr_patterns:
            if re.search(pat, text, re.IGNORECASE):
                key = re.sub(r"\\b", "", pat)
                if key not in self.knowledge["abbreviations"]:
                    self.knowledge["abbreviations"][key] = desc
                    new_abbr += 1

        # 2. Phát hiện các cụm từ chuyên ngành xây dựng trường học, dân dụng & hạ tầng
        # Khớp các cụm từ tiếng Việt chuẩn có dấu xuất hiện trong tài liệu
        domain_keywords = [
            "ký túc xá", "phòng học", "khối tiểu học", "khối thcs", "nhà hiệu bộ",
            "nhà chức năng", "nhà đa năng", "nhà bếp ăn", "khu học bộ môn",
            "ký túc xá giáo viên", "bể xử lý nước thải", "bể tự hoại", "nước thải bastaf",
            "phá dỡ", "nhà lớp học", "cấp nước sinh hoạt", "đầu nguồn",
            "cấp thoát nước", "hệ thống chiếu sáng", "sân đường nội bộ",
            "san nền", "sân bóng đá", "tổng mặt bằng", "cổng hàng rào",
            "kè đá", "cột cờ", "trạm biến áp", "đường dây", "đường giao thông",
            "chống thấm sika", "màng chống thấm", "xà gồ mạ kẽm", "ngói mũi hài",
            "tấm lợp lấy sáng", "cửa đi nhôm kính", "cửa sổ lùa", "kính dán an toàn",
            "lan can inox", "tay vịn gỗ", "sơn epoxy", "gạch ceramic",
            "bê tông lót", "vữa xi măng mác", "cốt thép dọc", "cốt đai",
            "đoạn neo cốt thép", "hố ga thu nước", "rãnh thoát nước b100",
            "tấm đan bê tông", "bó vỉa bê tông", "bậc lên xuống", "gờ chắn bánh",
            "độ chặt k95", "độ chặt k98", "cát đệm móng", "đá 1x2", "đá 4x6",
            "đất đắp bao", "đất đắp nền", "đào móng cột", "đào móng băng"
        ]

        for phrase in domain_keywords:
            raw_key = unicodedata.normalize("NFD", phrase)
            raw_key = "".join(c for c in raw_key if unicodedata.category(c) != "Mn").lower()
            if raw_key not in self.knowledge["learned_phrases"]:
                self.knowledge["learned_phrases"][raw_key] = phrase
                new_phrases += 1

        # 3. Đúc rút các từ dính thường gặp trong scan bản vẽ
        unstick_patterns = [
            (r"\bkytucxa\b", "ký túc xá"),
            (r"\bphonghoc\b", "phòng học"),
            (r"\bnhabepan\b", "nhà bếp ăn"),
            (r"\bnhahieubo\b", "nhà hiệu bộ"),
            (r"\bkhuhocbomon\b", "khu học bộ môn"),
            (r"\bnhadanang\b", "nhà đa năng"),
            (r"\bbastaf\b", "Bastaf"),
            (r"\bbetuhoai\b", "bể tự hoại"),
            (r"\bcapthoatnuoc\b", "cấp thoát nước"),
            (r"\bsannen\b", "san nền"),
            (r"\bsanbongda\b", "sân bóng đá"),
            (r"\btongmatbang\b", "tổng mặt bằng"),
            (r"\bconghangrao\b", "cổng hàng rào"),
            (r"\bkeda\b", "kè đá"),
            (r"\bcotco\b", "cột cờ"),
            (r"\btrambienap\b", "trạm biến áp"),
            (r"\bduonggiaothong\b", "đường giao thông"),
            (r"\bchongtham\b", "chống thấm"),
            (r"\bxagothep\b", "xà gồ thép"),
            (r"\bnhomkinh\b", "nhôm kính"),
            (r"\blancan\b", "lan can"),
            (r"\bhoanthien\b", "hoàn thiện"),
            (r"\bphado\b", "phá dỡ"),
            (r"\bcaitao\b", "cải tạo"),
            (r"\bxaydung\b", "xây dựng"),
        ]
        for pat, repl in unstick_patterns:
            key = pat.strip(r"\b")
            if key not in self.knowledge["unsticking_rules"]:
                self.knowledge["unsticking_rules"][key] = repl
                new_unstick += 1

        return {
            "new_phrases": new_phrases,
            "new_unstick": new_unstick,
            "new_abbr": new_abbr,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # BỘ NÃO SOI CHIẾU & ĐÚC RÚT KINH NGHIỆM TỪ BẢNG BIỂU (TABLES)
    # ─────────────────────────────────────────────────────────────────────────
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
        Bơm toàn bộ kinh nghiệm đã tích lũy vào bộ nhớ hoạt động của
        `vn_diacritics` và `table_agent` để trang bị ngay cho các lượt đọc tiếp theo.
        """
        try:
            import vn_diacritics
            # 1. Bơm thêm từ ghép mới
            for raw_k, phr in self.knowledge.get("learned_phrases", {}).items():
                vn_diacritics.AEC_COMPOUND_PHRASES.append((raw_k, phr))

            # 2. Bơm thêm quy tắc tách từ dính
            for k, repl in self.knowledge.get("unsticking_rules", {}).items():
                rule = (r"\b" + re.escape(k) + r"\b", repl)
                vn_diacritics.AEC_UNSTICKING_RULES.insert(0, rule)

            # Khởi tạo lại singleton restorer
            vn_diacritics._DEFAULT_RESTORER = vn_diacritics.VietnameseDiacriticRestorer()
        except Exception as e:
            print(f"[ExperienceEngine] Lỗi đồng bộ vn_diacritics: {e}")

        try:
            import table_agent
            for alias, std_col in self.knowledge.get("table_header_aliases", {}).items():
                # Bổ sung alias vào các bộ nhận diện của table_agent
                if std_col == "mark":
                    table_agent.MARK_ALIASES.add(alias)
                elif std_col == "quantity":
                    table_agent.QTY_ALIASES.add(alias)
        except Exception as e:
            print(f"[ExperienceEngine] Lỗi đồng bộ table_agent: {e}")

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
                "phrases": len(self.knowledge["learned_phrases"]),
                "unstick_rules": len(self.knowledge["unsticking_rules"]),
                "abbreviations": len(self.knowledge["abbreviations"]),
                "table_aliases": len(self.knowledge["table_header_aliases"])
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
            f"📚 Tổng vốn từ chuyên sâu tích lũy: {len(k['learned_phrases'])} thuật ngữ",
            f"⚡ Quy tắc tách từ dính scan CAD: {len(k['unsticking_rules'])} quy tắc",
            f"🏷️  Thuật ngữ viết tắt ngành AEC: {len(k['abbreviations'])} từ viết tắt",
            f"📊 Biến thể tiêu đề bảng BoQ/Thép: {len(k['table_header_aliases'])} biến thể",
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
