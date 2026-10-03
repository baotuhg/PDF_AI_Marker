"""RAG Engine: Knowledge Base Indexing, Hybrid Search, and LLM Orchestration."""
import os
import sys
import re
import json
import time
import socket
import atexit
import unicodedata
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

# Thư mục gốc ứng dụng (hỗ trợ cả chạy mã nguồn và đóng gói PyInstaller EXE)
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent


def remove_accents(input_str: str) -> str:
    """Chuyển chuỗi tiếng Việt có dấu thành không dấu để tìm kiếm mờ."""
    if not input_str:
        return ""
    nfkd = unicodedata.normalize("NFKD", input_str)
    s = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return s.replace("đ", "d").replace("Đ", "D")


def tokenize(text: str) -> list[str]:
    """Tách từ đơn giản, giữ lại cả số hiệu kỹ thuật như KC-05, D2, Ø20."""
    if not text:
        return []
    words = re.findall(r"[a-zA-Z0-9À-ỹØø]+(?:[-_/][a-zA-Z0-9À-ỹ]+)*", text.lower())
    return words


class RetrievalChunk:
    def __init__(self, chunk_id: str, source: str, page: int, section: str, block_type: str, text: str,
                 so_hieu_ban_ve: str = "", score: float = 0.0, table_info: dict = None):
        self.chunk_id = chunk_id
        self.source = source
        self.page = page
        self.section = section or ""
        self.block_type = block_type or ""
        self.text = text
        self.so_hieu_ban_ve = so_hieu_ban_ve or ""
        self.score = score
        self.table_info = table_info or {}

    def to_citation_label(self) -> str:
        parts = [f"Trang {self.page}"]
        if self.so_hieu_ban_ve:
            parts.append(f"Bản vẽ {self.so_hieu_ban_ve}")
        if self.section:
            parts.append(self.section)
        return " • ".join(parts)


class ProjectKnowledgeBase:
    """Quản lý dữ liệu bóc tách của một hồ sơ/dự án để phục vụ RAG."""

    def __init__(self, folder_path: str = None):
        self.folder = None
        self.source_file = ""
        self.pages = []
        self.chunks: list[RetrievalChunk] = []
        self.tables = []
        self.metadata_by_page = {}
        self.full_markdown = ""
        if folder_path:
            self.load(folder_path)

    def load(self, folder_path: str) -> bool:
        p = Path(folder_path)
        if not p.exists():
            return False
        self.folder = p

        # 1. Đọc du_lieu.json
        f_data = p / "du_lieu.json"
        if f_data.exists():
            try:
                data = json.loads(f_data.read_text(encoding="utf-8"))
                self.source_file = data.get("source") or data.get("source_path") or p.name
                self.pages = data.get("pages") or []
                for pg in self.pages:
                    pno = pg.get("page", 1)
                    meta = pg.get("metadata") or {}
                    self.metadata_by_page[pno] = meta
            except Exception as e:
                print(f"[KnowledgeBase] Lỗi nạp du_lieu.json: {e}")

        # 2. Đọc bang_so_lieu.json
        f_tables = p / "bang_so_lieu.json"
        if f_tables.exists():
            try:
                self.tables = json.loads(f_tables.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"[KnowledgeBase] Lỗi nạp bang_so_lieu.json: {e}")

        # 3. Đọc noi_dung.md
        f_md = p / "noi_dung.md"
        if f_md.exists():
            try:
                self.full_markdown = f_md.read_text(encoding="utf-8")
            except Exception as e:
                print(f"[KnowledgeBase] Lỗi nạp noi_dung.md: {e}")

        # 4. Đọc chia_doan.jsonl (các smart chunks)
        f_chunks = p / "chia_doan.jsonl"
        self.chunks.clear()
        if f_chunks.exists():
            try:
                for line in f_chunks.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    pno = item.get("page", 1)
                    meta = self.metadata_by_page.get(pno, {})
                    so_hieu = meta.get("so_hieu_ban_ve", "")
                    chunk = RetrievalChunk(
                        chunk_id=item.get("id", ""),
                        source=item.get("source", ""),
                        page=pno,
                        section=item.get("section", ""),
                        block_type=item.get("block_type", ""),
                        text=item.get("text", ""),
                        so_hieu_ban_ve=so_hieu
                    )
                    self.chunks.append(chunk)
            except Exception as e:
                print(f"[KnowledgeBase] Lỗi nạp chia_doan.jsonl: {e}")

        # Nếu không có chunks từ jsonl thì tạo fallback từ các bảng và trang
        if not self.chunks and self.pages:
            for pg in self.pages:
                pno = pg.get("page", 1)
                meta = pg.get("metadata") or {}
                so_hieu = meta.get("so_hieu_ban_ve", "")
                for t in pg.get("tables") or []:
                    header = " | ".join(t.get("header") or [])
                    rows_str = "\n".join([" | ".join(r) for r in (t.get("rows") or [])])
                    txt = f"### {t.get('title') or 'Bảng số liệu'}\n{header}\n{rows_str}"
                    self.chunks.append(RetrievalChunk(
                        chunk_id=f"page_{pno}_tbl",
                        source=self.source_file,
                        page=pno,
                        section=t.get("title") or "Bảng",
                        block_type="Table",
                        text=txt,
                        so_hieu_ban_ve=so_hieu
                    ))

        return len(self.chunks) > 0 or len(self.pages) > 0

    def search(self, query: str, top_k: int = 4) -> list[RetrievalChunk]:
        """Thuật toán Hybrid Search: BM25/TF-IDF + Entity Boost cho hồ sơ kỹ thuật."""
        if not self.chunks:
            return []

        q_clean = query.strip()
        q_lower = q_clean.lower()
        q_no_accents = remove_accents(q_lower)
        q_tokens = set(tokenize(q_lower) + tokenize(q_no_accents))

        # Phát hiện từ khóa chuyên ngành
        has_table_kw = any(w in q_lower or w in q_no_accents for w in [
            "khối lượng", "khoi luong", "thép", "thep", "bảng", "bang", "thống kê", "thong ke",
            "dài", "dai", "số lượng", "so luong", "đường kính", "duong kinh", "tổng cộng", "tong cong",
            "cốt thép", "cot thep", "vật tư", "vat tu", "đơn giá", "don gia"
        ])
        has_spec_kw = any(w in q_lower or w in q_no_accents for w in [
            "mác", "mac", "bê tông", "be tong", "cb240", "cb400", "b25", "tiêu chuẩn", "tieu chuan",
            "ghi chú", "ghi chu", "bảo vệ", "bao ve", "mối nối", "moi noi"
        ])
        has_title_kw = any(w in q_lower or w in q_no_accents for w in [
            "bản vẽ", "ban ve", "số hiệu", "so hieu", "khung tên", "khung ten", "tỷ lệ", "ty le",
            "chủ đầu tư", "chu dau tu", "công trình", "cong trinh", "tên bản vẽ"
        ])

        scored_chunks: list[tuple[float, RetrievalChunk]] = []

        for ch in self.chunks:
            text_lower = ch.text.lower()
            text_no_accents = remove_accents(text_lower)
            sec_lower = ch.section.lower()
            bve_lower = ch.so_hieu_ban_ve.lower()

            score = 0.0

            # 1. Khớp từ khóa (Exact & Unaccented Token Match)
            for token in q_tokens:
                if len(token) <= 1:
                    continue
                # Khớp trong nội dung
                c_cnt = text_lower.count(token) + text_no_accents.count(token)
                if c_cnt > 0:
                    score += min(c_cnt, 5) * 1.5
                # Khớp trong tiêu đề mục
                if token in sec_lower:
                    score += 4.0
                # Khớp số hiệu bản vẽ (VD: KC-05, D2)
                if token in bve_lower or token in text_lower:
                    if re.match(r"^[a-zA-Z]{1,4}[-_]?\d+$", token):
                        score += 12.0

            # 2. Boost theo mục đích câu hỏi
            if has_table_kw:
                if "|" in ch.text and ("---" in ch.text or "STT" in ch.text):
                    score += 6.0
                if "thống kê" in sec_lower or "thong ke" in sec_lower:
                    score += 5.0

            if has_spec_kw and ("ghi chú" in sec_lower or "tiêu chuẩn" in text_lower or "cb" in text_lower):
                score += 5.0

            if has_title_kw and (ch.so_hieu_ban_ve or "khung tên" in sec_lower or "chủ đầu tư" in text_lower):
                score += 6.0

            # 3. Phạt các đoạn quá ngắn không có dữ liệu
            if len(ch.text.strip()) < 40:
                score *= 0.5

            if score > 0.5:
                # Gán score cho chunk
                ch.score = score
                scored_chunks.append((score, ch))

        # Sắp xếp điểm từ cao xuống thấp
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = [ch for _, ch in scored_chunks[:top_k]]
        return results

    def build_prompt_messages(self, query: str, history: list[dict] = None, top_k: int = 4) -> list[dict]:
        """Tạo danh sách tin nhắn (System, User, Context) chuẩn OpenAI-compatible."""
        retrieved = self.search(query, top_k=top_k)

        # Xây dựng ngữ cảnh dẫn chứng
        context_blocks = []
        for i, ch in enumerate(retrieved, 1):
            header = f"[Dẫn chứng {i}: Trang {ch.page}"
            if ch.so_hieu_ban_ve:
                header += f" · Bản vẽ {ch.so_hieu_ban_ve}"
            if ch.section:
                header += f" · Mục: {ch.section}"
            header += "]"
            context_blocks.append(f"{header}\n{ch.text.strip()}")

        context_str = "\n\n".join(context_blocks) if context_blocks else "(Không tìm thấy đoạn trích phù hợp trong hồ sơ)"

        system_prompt = (
            "Bạn là 'Trợ lý AI Kỹ Sư Công Trình 23HG' — chuyên gia phân tích hồ sơ thiết kế, bản vẽ thi công, "
            "dự toán và tiêu chuẩn kỹ thuật xây dựng Việt Nam.\n\n"
            "NGUYÊN TẮC TRẢ LỜI QUAN TRỌNG NHẤT:\n"
            "1. Căn cứ trả lời: CHỈ dựa trên các đoạn 'DẪN CHỨNG HỒ SƠ' được cung cấp bên dưới.\n"
            "2. Trích dẫn nguồn: LUÔN ghi rõ số trang và số hiệu bản vẽ trong câu trả lời theo cú pháp [Trang X] "
            "hoặc [Trang X • Bản vẽ Y] để người dùng có thể nhấp vào kiểm tra trên bản vẽ gốc.\n"
            "3. Độ chính xác số liệu: Đối với khối lượng, chiều dài, đường kính thép, mác bê tông, giữ nguyên con số "
            "và đơn vị (kg, m, mm, m3...).\n"
            "4. Định dạng: Trình bày rõ ràng bằng Markdown (dùng gạch đầu dòng, bảng nếu có nhiều cấu kiện).\n"
            "5. Tính trung thực: Nếu trong hồ sơ không có thông tin hoặc số liệu không rõ ràng, hãy trả lời thẳng thắn "
            "rằng 'Hồ sơ dự án không đề cập đến thông tin này', tuyệt đối không được tự ý suy đoán hoặc bịa số liệu."
        )

        user_content = (
            f"=== CÁC ĐOẠN DẪN CHỨNG TỪ HỒ SƠ DỰ ÁN ===\n\n"
            f"{context_str}\n\n"
            f"===========================================\n\n"
            f"CÂU HỎI CỦA KỸ SƯ:\n{query}"
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Thêm lịch sử hội thoại gần nhất (nếu có)
        if history:
            for turn in history[-4:]:
                messages.append(turn)

        messages.append({"role": "user", "content": user_content})
        return messages

    def smart_extract_fallback(self, query: str) -> str:
        """Trả lời tức thì không cần LLM (Offline Smart Extraction)."""
        retrieved = self.search(query, top_k=3)
        if not retrieved:
            return (
                "⚠️ **Không tìm thấy thông tin phù hợp trong hồ sơ hiện tại.**\n\n"
                "- Hãy thử tìm theo số hiệu bản vẽ (VD: `KC-05`), tên cấu kiện (`Dầm D1`, `Cột C1`) "
                "hoặc từ khóa (`thép`, `khối lượng`, `ghi chú`)."
            )

        resp = [f"### 🔍 Kết quả tra cứu hồ sơ cho: *“{query}”*\n"]
        resp.append(f"Tìm thấy **{len(retrieved)} vị trí liên quan** trong tài liệu:\n")

        for i, ch in enumerate(retrieved, 1):
            cite = f"[Trang {ch.page}"
            if ch.so_hieu_ban_ve:
                cite += f" • {ch.so_hieu_ban_ve}"
            if ch.section:
                cite += f" • {ch.section}"
            cite += "]"

            resp.append(f"#### 📍 Vị trí {i}: {cite}")
            # Hiển thị nội dung
            lines = [l for l in ch.text.splitlines() if not l.startswith("[Nguồn:")]
            sample = "\n".join(lines).strip()
            resp.append(sample)
            resp.append("\n---\n")

        resp.append(
            "\n💡 *Mẹo: Bạn có thể nhấp vào các số trang [Trang X] ở trên để mở ngay bản vẽ gốc "
            "hoặc bật mô hình AI (llama-server/LM Studio) để nhận câu trả lời tổng hợp tự động.*"
        )
        return "\n".join(resp)


class LlamaServerManager:
    """Quản lý tiến trình llama-server.exe chạy mô hình GGUF offline."""

    def __init__(self, llama_exe_path: str = None):
        if llama_exe_path:
            self.exe_path = Path(llama_exe_path)
        else:
            candidates = [
                ROOT / "llama" / "llama-server.exe",
                ROOT.parent / "llama" / "llama-server.exe",
                Path(__file__).resolve().parent / "llama" / "llama-server.exe",
                Path(__file__).resolve().parent.parent / "llama" / "llama-server.exe",
                Path(sys.executable).resolve().parent / "llama" / "llama-server.exe",
                Path(sys.executable).resolve().parent / "_internal" / "llama" / "llama-server.exe",
            ]
            self.exe_path = next((p for p in candidates if p.exists()), candidates[0])
        self.process = None
        self.port = 8088
        self.model_path = None
        atexit.register(self.stop_server)

    @staticmethod
    def find_free_port(start_port: int = 8088) -> int:
        for p in range(start_port, start_port + 20):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", p)) != 0:
                    return p
        return start_port

    @staticmethod
    def scan_models() -> list[Path]:
        """Tự động tìm kiếm các model GGUF trong thư mục app và máy tính người dùng."""
        found = []
        # 1. Trong app: models/
        app_model_dirs = [
            ROOT / "models",
            ROOT.parent / "models",
            Path(__file__).resolve().parent / "models",
            Path(__file__).resolve().parent.parent / "models",
            Path(sys.executable).resolve().parent / "models",
        ]
        for md in app_model_dirs:
            if md.exists():
                for f in md.glob("*.gguf"):
                    if "mmproj" not in f.name.lower() and "surya" not in f.name.lower() and f not in found:
                        found.append(f)

        # 2. Trong thư mục LM Studio của user nếu có
        lm_dir = Path.home() / ".lmstudio" / "models"
        if lm_dir.exists():
            for f in lm_dir.rglob("*.gguf"):
                if "mmproj" not in f.name.lower() and f not in found:
                    found.append(f)

        # 3. Trong thư mục Ollama / Cache nếu có
        ollama_dir = Path.home() / ".ollama" / "models"
        if ollama_dir.exists():
            for f in ollama_dir.rglob("*.gguf"):
                if f not in found:
                    found.append(f)

        return found

    def start_server(self, model_path: str, port: int = None, ctx_size: int = 4096,
                     ngl: int = 99, threads: int = 4) -> tuple[bool, str]:
        """Khởi động llama-server.exe với mô hình GGUF."""
        if not self.exe_path.exists():
            return False, f"Không tìm thấy llama-server.exe tại:\n{self.exe_path}"

        mp = Path(model_path)
        if not mp.exists():
            return False, f"Không tìm thấy file mô hình GGUF:\n{model_path}"

        self.stop_server()
        self.port = port or self.find_free_port(8088)
        self.model_path = mp

        cmd = [
            str(self.exe_path),
            "-m", str(mp),
            "-c", str(ctx_size),
            "-ngl", str(ngl),
            "-t", str(threads),
            "--port", str(self.port),
            "--host", "127.0.0.1"
        ]

        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
        except Exception as e:
            return False, f"Lỗi khởi chạy tiến trình: {e}"

        # Đợi server sẵn sàng qua /health
        t0 = time.time()
        while time.time() - t0 < 30:
            if self.process.poll() is not None:
                return False, f"Server bị tắt sớm với mã thoát: {self.process.returncode}"
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
                with urllib.request.urlopen(req, timeout=1.0) as res:
                    if res.status == 200:
                        return True, f"Server sẵn sàng tại port {self.port}"
            except Exception:
                time.sleep(0.5)

        return False, "Hết thời gian chờ server khởi động (timeout 30s)."

    def stop_server(self):
        """Dừng tiến trình server."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def is_running(self) -> bool:
        if not self.process:
            return False
        return self.process.poll() is None

    def get_api_base(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"
