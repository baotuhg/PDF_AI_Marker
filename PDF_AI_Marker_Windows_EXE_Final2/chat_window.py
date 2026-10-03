"""Cửa sổ Trợ lý AI Công trình (Local RAG Chat) • PDF AI Marker v3
Tác giả: Nguyễn Bảo Tú (23HG) — baotuhg@gmail.com
"""
import os
import sys
import re
import json
import time
from pathlib import Path
import urllib.request
import urllib.error

from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QIcon, QFont, QTextCursor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTextBrowser, QPlainTextEdit, QFileDialog,
    QMessageBox, QFrame, QSplitter, QProgressBar, QApplication
)

from rag_engine import ProjectKnowledgeBase, LlamaServerManager, ROOT


# ─────────────────────────────────────────────────────────────────────────────
# Worker Thread để sinh câu trả lời AI (Streaming) không làm đơ giao diện
# ─────────────────────────────────────────────────────────────────────────────
class ChatWorker(QThread):
    chunk_received = Signal(str)
    finished_stream = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, mode, base_url, api_key, model_name, messages, kb=None, query=""):
        super().__init__()
        self.mode = mode  # "local_server", "service", "cloud", "smart_search"
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name or "local-model"
        self.messages = messages
        self.kb = kb
        self.query = query
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        # 1. Chế độ tra cứu trực tiếp không cần LLM
        if self.mode == "smart_search" or not self.base_url:
            if self.kb:
                ans = self.kb.smart_extract_fallback(self.query)
                self.finished_stream.emit(ans)
            else:
                self.error_occurred.emit("Chưa tải cơ sở dữ liệu hồ sơ.")
            return

        # 2. Gửi request đến OpenAI-compatible endpoint (llama-server / LM Studio / Ollama / Cloud)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or 'no-key'}"
        }
        payload = {
            "model": self.model_name,
            "messages": self.messages,
            "temperature": 0.2,
            "max_tokens": 2048,
            "stream": True
        }

        full_response = []
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=60.0) as resp:
                for raw_line in resp:
                    if self.is_cancelled:
                        break
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_obj = json.loads(data_str)
                        choices = chunk_obj.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta") or {}
                            content = delta.get("content") or ""
                            if content:
                                full_response.append(content)
                                self.chunk_received.emit(content)
                    except Exception:
                        pass
            complete_text = "".join(full_response)
            self.finished_stream.emit(complete_text)
        except urllib.error.URLError as e:
            self.error_occurred.emit(
                f"Không thể kết nối đến máy chủ AI ({url}):\n{e.reason}\n\n"
                "• Nếu dùng llama-server: hãy bấm 'Khởi động AI Offline'.\n"
                "• Nếu dùng LM Studio/Ollama: hãy đảm bảo ứng dụng đang bật và Local Server đã kích hoạt."
            )
        except Exception as e:
            self.error_occurred.emit(f"Lỗi phản hồi từ AI: {type(e).__name__} — {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Cửa sổ chính Trợ lý AI Công trình
# ─────────────────────────────────────────────────────────────────────────────
class ChatWindow(QMainWindow):

    def __init__(self, parent=None, inspector_window=None):
        super().__init__(parent)
        self.setWindowTitle("🤖 Trợ lý AI Công Trình (RAG Chat) • PDF AI Marker v3 — Tác giả: Nguyễn Bảo Tú (23HG)")
        self.resize(1150, 850)
        self.setMinimumSize(850, 650)

        icon_p = ROOT / "app_icon.ico"
        if not icon_p.exists():
            icon_p = Path(sys.executable).resolve().parent / "app_icon.ico"
        if icon_p.exists():
            self.setWindowIcon(QIcon(str(icon_p)))

        self.inspector_window = inspector_window
        self.kb = ProjectKnowledgeBase()
        self.llama_mgr = LlamaServerManager()
        self.current_folder = None
        self.worker = None
        self.chat_history_data = []  # danh sách các cặp (role, text)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f3f6fb; color: #19324e; font: 10pt 'Segoe UI'; }
            QPushButton { background: white; border: 1px solid #d7e0ec; border-radius: 6px; padding: 7px 14px; font-weight: 500; }
            QPushButton:hover { background: #e7effa; }
            QPushButton#primary { background: #205dd8; color: white; border: none; font-weight: 600; }
            QPushButton#primary:hover { background: #1648ad; }
            QPushButton#danger { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
            QPushButton#danger:hover { background: #fecaca; }
            QPushButton.pill { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 14px; padding: 5px 12px; font-size: 9.5pt; color: #334155; }
            QPushButton.pill:hover { background: #eff6ff; border-color: #93c5fd; color: #1d4ed8; }
            QTextBrowser { background: #ffffff; border: 1px solid #d7e0ec; border-radius: 8px; padding: 12px; }
            QPlainTextEdit, QLineEdit, QComboBox { background: white; border: 1px solid #d7e0ec; border-radius: 6px; padding: 6px; }
            QFrame#card { background: white; border: 1px solid #d7e0ec; border-radius: 8px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(10)

        # ── TOP BAR: Thông tin dự án + Hành động ────────────────────────────
        top_bar = QHBoxLayout()
        self.lbl_project = QLabel("📁 Chưa tải hồ sơ kết quả (Hãy chọn thư mục *_Marker)")
        self.lbl_project.setStyleSheet("font-weight: 600; font-size: 11pt; color: #0f2d59;")
        top_bar.addWidget(self.lbl_project, 1)

        self.btn_open_folder = QPushButton("📂 Đổi hồ sơ…")
        self.btn_open_folder.clicked.connect(self.choose_folder)
        top_bar.addWidget(self.btn_open_folder)

        self.btn_open_inspector = QPushButton("🔍 Đối chiếu bản vẽ")
        self.btn_open_inspector.setToolTip("Mở cửa sổ đối chiếu trực quan song song")
        self.btn_open_inspector.clicked.connect(self.open_inspector_window)
        top_bar.addWidget(self.btn_open_inspector)

        self.btn_toggle_settings = QPushButton("⚙️ Cấu hình AI Model")
        self.btn_toggle_settings.setCheckable(True)
        self.btn_toggle_settings.clicked.connect(self._toggle_settings)
        top_bar.addWidget(self.btn_toggle_settings)
        main_layout.addLayout(top_bar)

        # ── SETTINGS PANEL (Có thể ẩn/hiện) ─────────────────────────────────
        self.settings_frame = QFrame()
        self.settings_frame.setObjectName("card")
        self.settings_frame.setVisible(False)
        set_layout = QVBoxLayout(self.settings_frame)
        set_layout.setContentsMargins(14, 12, 14, 12)
        set_layout.setSpacing(8)

        # Hàng 1: Chọn Backend
        row_b = QHBoxLayout()
        row_b.addWidget(QLabel("Bộ máy AI (Backend):"))
        self.cb_backend = QComboBox()
        self.cb_backend.addItems([
            "⚡ llama-server (GGUF Offline - Có sẵn trong gói)",
            "🔌 LM Studio (http://localhost:1234/v1)",
            "🦙 Ollama (http://localhost:11434/v1)",
            "☁️ API Trực tuyến (DeepSeek / OpenAI)",
            "🔍 Chỉ tra cứu thông minh (Offline - Không cần LLM)"
        ])
        self.cb_backend.currentIndexChanged.connect(self._on_backend_changed)
        row_b.addWidget(self.cb_backend, 1)

        self.lbl_server_status = QLabel("⚪ Chưa bật")
        self.lbl_server_status.setStyleSheet("font-weight: 600; padding: 4px 8px; border-radius: 4px; background: #f1f5f9;")
        row_b.addWidget(self.lbl_server_status)
        set_layout.addLayout(row_b)

        # Hàng 2: Tùy chỉnh theo Backend
        self.row_local = QHBoxLayout()
        self.row_local.addWidget(QLabel("Model GGUF:"))
        self.txt_model_path = QLineEdit()
        self.txt_model_path.setPlaceholderText("Đường dẫn đến file .gguf (ví dụ Qwen2.5-7B, Gemma...)")
        self.row_local.addWidget(self.txt_model_path, 1)

        self.btn_browse_model = QPushButton("Chọn file…")
        self.btn_browse_model.clicked.connect(self._browse_model)
        self.row_local.addWidget(self.btn_browse_model)

        self.btn_auto_model = QPushButton("🔍 Tự quét model")
        self.btn_auto_model.clicked.connect(self._auto_find_models)
        self.row_local.addWidget(self.btn_auto_model)

        self.btn_start_server = QPushButton("🚀 Khởi động AI Offline")
        self.btn_start_server.setObjectName("primary")
        self.btn_start_server.clicked.connect(self._toggle_local_server)
        self.row_local.addWidget(self.btn_start_server)
        set_layout.addLayout(self.row_local)

        # Hàng 3: URL & Key (Cho LM Studio / Ollama / Cloud)
        self.row_remote = QHBoxLayout()
        self.lbl_remote_url = QLabel("API URL:")
        self.row_remote.addWidget(self.lbl_remote_url)
        self.txt_remote_url = QLineEdit("http://127.0.0.1:1234/v1")
        self.row_remote.addWidget(self.txt_remote_url, 1)

        self.lbl_remote_key = QLabel("API Key:")
        self.row_remote.addWidget(self.lbl_remote_key)
        self.txt_remote_key = QLineEdit()
        self.txt_remote_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_remote_key.setPlaceholderText("sk-... (nếu cần)")
        self.row_remote.addWidget(self.txt_remote_key)

        self.lbl_remote_model = QLabel("Model Name:")
        self.row_remote.addWidget(self.lbl_remote_model)
        self.txt_remote_model = QLineEdit("qwen2.5-7b-instruct")
        self.row_remote.addWidget(self.txt_remote_model)
        set_layout.addLayout(self.row_remote)
        self.row_remote.setEnabled(False)

        main_layout.addWidget(self.settings_frame)

        # ── QUICK PROMPT TEMPLATES (Pills) ──────────────────────────────────
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(6)
        pills_label = QLabel("Gợi ý câu hỏi:")
        pills_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        pills_layout.addWidget(pills_label)

        templates = [
            ("📋 Quy mô & Danh mục bản vẽ", "Hãy tóm tắt quy mô công trình, chủ đầu tư và lập danh mục các số hiệu bản vẽ có trong hồ sơ."),
            ("📊 Thống kê khối lượng cốt thép", "Tổng hợp toàn bộ khối lượng cốt thép, chiều dài và đường kính của từng cấu kiện có trong bảng thống kê."),
            ("📐 Tiêu chuẩn bê tông & ghi chú", "Liệt kê các tiêu chuẩn kỹ thuật áp dụng, mác bê tông và ghi chú thi công quan trọng trên bản vẽ."),
            ("⚠️ Kiểm tra sai lệch số liệu OCR", "Rà soát xem có những điểm nghi vấn, chữ số cần đối chiếu hoặc ghi chú đặc biệt nào trong tài liệu không?")
        ]

        for title, prompt_text in templates:
            btn = QPushButton(title)
            btn.setProperty("class", "pill")
            btn.clicked.connect(lambda _, txt=prompt_text: self._apply_template(txt))
            pills_layout.addWidget(btn)
        pills_layout.addStretch()
        main_layout.addLayout(pills_layout)

        # ── CHAT HISTORY BROWSER ─────────────────────────────────────────────
        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(False)
        self.chat_view.anchorClicked.connect(self._on_link_clicked)
        main_layout.addWidget(self.chat_view, 1)

        # ── INPUT BAR ───────────────────────────────────────────────────────
        input_box = QVBoxLayout()
        input_box.setSpacing(6)

        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Nhập câu hỏi về bản vẽ, dự toán, khối lượng... (Enter để gửi, Shift+Enter xuống dòng)")
        self.txt_input.setMaximumHeight(80)
        self.txt_input.installEventFilter(self)
        input_box.addWidget(self.txt_input)

        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("💬 Gửi câu hỏi (Enter)")
        self.btn_send.setObjectName("primary")
        self.btn_send.clicked.connect(self.send_query)
        btn_row.addWidget(self.btn_send)

        self.btn_stop = QPushButton("⏹️ Dừng")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_generation)
        btn_row.addWidget(self.btn_stop)

        btn_row.addStretch()

        self.btn_clear = QPushButton("🗑️ Xóa hội thoại")
        self.btn_clear.clicked.connect(self.clear_chat)
        btn_row.addWidget(self.btn_clear)

        self.btn_export = QPushButton("📄 Xuất biên bản Q&A (.md)")
        self.btn_export.clicked.connect(self.export_chat)
        btn_row.addWidget(self.btn_export)

        input_box.addLayout(btn_row)
        main_layout.addLayout(input_box)

        # Quét model ban đầu
        self._auto_find_models(silent=True)
        self._render_welcome()

    def _render_welcome(self):
        html = """
        <div style="font-family: 'Segoe UI', sans-serif; padding: 10px; line-height: 1.6;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #0f2d59; margin-bottom: 4px;">🤖 Trợ Lý AI Kỹ Sư Công Trình (Offline RAG)</h2>
                <div style="color: #64748b; font-size: 10pt;">Hỏi đáp thông minh trực tiếp với hồ sơ thiết kế, bản vẽ thi công & dự toán</div>
            </div>
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                <b style="color: #1e293b;">🎯 Các tính năng nổi bật:</b>
                <ul style="margin: 6px 0; padding-left: 20px; color: #334155;">
                    <li><b>Trích dẫn chuẩn xác:</b> Mọi câu trả lời đều dẫn nguồn <code>[Trang X • Bản vẽ Y]</code>.</li>
                    <li><b>Liên kết trực quan:</b> <u>Nhấp vào số trang</u> để mở ngay bản vẽ gốc và khoanh đỏ vị trí số liệu.</li>
                    <li><b>Đa dạng mô hình:</b> Chạy 100% offline với <i>llama-server</i> (GGUF), kết nối <i>LM Studio</i>, hoặc tra cứu nhanh không cần LLM.</li>
                </ul>
            </div>
            <div style="color: #64748b; font-size: 9.5pt; text-align: center;">
                👉 <i>Hãy chọn một câu hỏi gợi ý ở trên hoặc gõ câu hỏi vào ô bên dưới để bắt đầu!</i>
            </div>
        </div>
        """
        self.chat_view.setHtml(html)

    # ── SỰ KIỆN PHÍM TẮT CHO INPUT ──────────────────────────────────────────
    def eventFilter(self, obj, event):
        if obj == self.txt_input and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False  # Cho phép xuống dòng
                else:
                    self.send_query()
                    return True
        return super().eventFilter(obj, event)

    def _toggle_settings(self):
        self.settings_frame.setVisible(self.btn_toggle_settings.isChecked())

    def _on_backend_changed(self, idx):
        is_local = (idx == 0)
        is_remote = (idx in (1, 2, 3))
        self.row_local.setEnabled(is_local)
        self.row_remote.setEnabled(is_remote)

        if idx == 1:  # LM Studio
            self.txt_remote_url.setText("http://127.0.0.1:1234/v1")
            self.txt_remote_key.clear()
        elif idx == 2:  # Ollama
            self.txt_remote_url.setText("http://127.0.0.1:11434/v1")
            self.txt_remote_key.clear()
        elif idx == 3:  # Cloud
            self.txt_remote_url.setText("https://api.deepseek.com/v1")

    def _browse_model(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file mô hình GGUF", "", "Mô hình GGUF (*.gguf)")
        if f:
            self.txt_model_path.setText(f)

    def _auto_find_models(self, silent=False):
        models = self.llama_mgr.scan_models()
        if models:
            self.txt_model_path.setText(str(models[0]))
            if not silent:
                QMessageBox.information(self, "Tìm thấy mô hình",
                                        f"Đã phát hiện {len(models)} mô hình GGUF trên máy.\nĐã chọn: {models[0].name}")
        elif not silent:
            QMessageBox.information(self, "Chưa thấy mô hình GGUF",
                                    "Chưa tìm thấy file .gguf trong thư mục models/ hoặc LM Studio.\n"
                                    "Bạn có thể chọn file bằng nút 'Chọn file…'.")

    def _toggle_local_server(self, silent=False):
        if self.llama_mgr.is_running():
            self.llama_mgr.stop_server()
            self.btn_start_server.setText("🚀 Khởi động AI Offline")
            self.btn_start_server.setObjectName("primary")
            self.lbl_server_status.setText("⚪ Chưa bật")
            self.lbl_server_status.setStyleSheet("background: #f1f5f9; color: #475569;")
            self.statusBar().showMessage("Đã dừng Server AI.")
            return

        model_path = self.txt_model_path.text().strip()
        if not model_path or not Path(model_path).exists():
            if not silent:
                QMessageBox.warning(self, "Chưa chọn mô hình", "Hãy chỉ định file mô hình .gguf trước khi khởi động.")
            return

        self.btn_start_server.setEnabled(False)
        self.btn_start_server.setText("⏳ Đang tải mô hình...")
        QApplication.processEvents()

        ok, msg = self.llama_mgr.start_server(model_path)
        self.btn_start_server.setEnabled(True)

        if ok:
            self.btn_start_server.setText("⏹️ Dừng Server AI")
            self.btn_start_server.setObjectName("danger")
            self.lbl_server_status.setText(f"🟢 Đang chạy (Port {self.llama_mgr.port})")
            self.lbl_server_status.setStyleSheet("background: #ecfdf5; color: #065f46; font-weight: bold;")
            self.statusBar().showMessage(f"AI Server sẵn sàng: {Path(model_path).name} (Port {self.llama_mgr.port})")
        else:
            self.btn_start_server.setText("🚀 Khởi động AI Offline")
            self.lbl_server_status.setText("🔴 Lỗi khởi động")
            self.lbl_server_status.setStyleSheet("background: #fef2f2; color: #991b1b;")
            if not silent:
                QMessageBox.critical(self, "Lỗi khởi động", msg)

    # ── NẠP HỒ SƠ DỰ ÁN ───────────────────────────────────────────────────
    def choose_folder(self):
        start = str(self.current_folder.parent) if self.current_folder else str(Path.home() / "Documents" / "PDF_AI_KetQua")
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục kết quả (*_Marker)", start)
        if folder:
            self.load_project(folder)

    def load_project(self, folder_path: str):
        folder = Path(folder_path)
        if not self.kb.load(str(folder)):
            QMessageBox.warning(self, "Không có dữ liệu", f"Thư mục này không chứa kết quả phân tích:\n{folder}")
            return False

        self.current_folder = folder
        info = (
            f"📁 Hồ sơ: <b>{self.kb.source_file or folder.name}</b> · "
            f"{len(self.kb.pages)} trang · {len(self.kb.chunks)} đoạn RAG · {len(self.kb.tables)} bảng số liệu"
        )
        self.lbl_project.setText(info)
        self.statusBar().showMessage(f"Đã nạp hồ sơ: {folder.name} ({len(self.kb.chunks)} đoạn trích)")
        return True

    def open_inspector_window(self, page_num=None):
        if not self.current_folder:
            QMessageBox.information(self, "Chưa chọn hồ sơ", "Hãy chọn một thư mục kết quả để mở đối chiếu.")
            return

        if self.inspector_window is None:
            try:
                from inspector import InspectorWindow
                self.inspector_window = InspectorWindow(self)
            except Exception as e:
                QMessageBox.warning(self, "Lỗi đối chiếu", f"Không mở được trình đối chiếu:\n{e}")
                return

        if self.inspector_window.result_dir != self.current_folder:
            self.inspector_window.load_result(str(self.current_folder))

        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()

        if page_num is not None:
            idx = page_num - 1
            if 0 <= idx < len(self.inspector_window.pages):
                self.inspector_window.show_page(idx)

    def _on_link_clicked(self, url: QUrl):
        s = url.toString()
        if s.startswith("page:"):
            try:
                p = int(s.split(":")[1])
                self.open_inspector_window(p)
            except Exception:
                pass

    # ── XỬ LÝ CHAT & STREAMING ───────────────────────────────────────────
    def _apply_template(self, text):
        self.txt_input.setPlainText(text)
        self.send_query()

    def send_query(self):
        query = self.txt_input.toPlainText().strip()
        if not query:
            return

        if not self.current_folder:
            QMessageBox.warning(self, "Chưa nạp hồ sơ", "Hãy chọn một thư mục hồ sơ kết quả trước khi hỏi đáp.")
            self.choose_folder()
            return

        self.txt_input.clear()
        self._append_message("user", query)

        idx = self.cb_backend.currentIndex()
        mode_keys = ["local_server", "service", "service", "cloud", "smart_search"]
        mode = mode_keys[idx]

        base_url = ""
        api_key = ""
        model_name = ""

        if mode == "local_server":
            if not self.llama_mgr.is_running():
                # Hỏi người dùng có muốn khởi động server hay tra cứu nhanh
                ret = QMessageBox.question(
                    self, "Server AI chưa bật",
                    "Server AI Offline (llama-server) chưa được bật.\n\n"
                    "• Bấm 'Yes' để tự động khởi động Server AI.\n"
                    "• Bấm 'No' để tra cứu thông minh tức thì không cần AI.",
                    QMessageBox.Yes | QMessageBox.No
                )
                if ret == QMessageBox.Yes:
                    self._toggle_local_server()
                    if not self.llama_mgr.is_running():
                        return
                    base_url = self.llama_mgr.get_api_base()
                else:
                    mode = "smart_search"
            else:
                base_url = self.llama_mgr.get_api_base()

        elif mode in ("service", "cloud"):
            base_url = self.txt_remote_url.text().strip()
            api_key = self.txt_remote_key.text().strip()
            model_name = self.txt_remote_model.text().strip()

        # Tạo prompt ngữ cảnh
        messages = self.kb.build_prompt_messages(query, history=self._get_history_dict(), top_k=4)

        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.statusBar().showMessage("Trợ lý AI đang tra cứu và suy luận...")

        # Khởi chạy Worker
        self._current_assistant_text = ""
        self.worker = ChatWorker(mode, base_url, api_key, model_name, messages, kb=self.kb, query=query)
        self.worker.chunk_received.connect(self._on_chunk)
        self.worker.finished_stream.connect(self._on_finish)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_chunk(self, chunk):
        self._current_assistant_text += chunk
        self._update_assistant_message(self._current_assistant_text)

    def _on_finish(self, complete_text):
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.statusBar().showMessage("Hoàn tất trả lời.")
        if complete_text:
            self._current_assistant_text = complete_text
            self.chat_history_data.append(("assistant", self._current_assistant_text))
            self._render_full_history()

    def _on_error(self, err_msg):
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.statusBar().showMessage("Có lỗi xảy ra.")
        self._append_message("assistant", f"❌ **Lỗi:** {err_msg}")

    def stop_generation(self):
        if self.worker:
            self.worker.cancel()
            self.btn_stop.setEnabled(False)
            self.btn_send.setEnabled(True)
            self.statusBar().showMessage("Đã dừng sinh câu trả lời.")

    # ── ĐỊNH DẠNG VÀ HIỂN THỊ TIN NHẮN ──────────────────────────────────
    def _append_message(self, role, text):
        self.chat_history_data.append((role, text))
        self._render_full_history()

    def _update_assistant_message(self, text, final=False):
        self._render_full_history(streaming_text=text if not final else None)

    def _render_full_history(self, streaming_text=None):
        out = [
            "<div style=\"font-family: 'Segoe UI', sans-serif; padding: 4px;\">"
        ]

        for role, text in self.chat_history_data:
            if role == "user":
                esc = self._escape_html(text)
                out.append(f"""
                <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin: 8px 0;">
                    <tr>
                        <td width="15%"></td>
                        <td align="right">
                            <table border="0" cellpadding="8" cellspacing="0" style="background-color: #205dd8; border-radius: 8px;">
                                <tr>
                                    <td style="color: #ffffff; font-size: 10pt; font-weight: 500;">
                                        👤 <b>Kỹ sư:</b> {esc}
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
                """)
            else:
                formatted = self._format_assistant_markdown(text)
                out.append(f"""
                <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin: 10px 0;">
                    <tr>
                        <td style="background-color: #ffffff; border: 1px solid #d7e0ec; border-left: 4px solid #205dd8;
                                   padding: 12px 14px; border-radius: 4px;">
                            <div style="font-size: 8.5pt; font-weight: bold; color: #205dd8; margin-bottom: 6px;">
                                🤖 TRỢ LÝ CÔNG TRÌNH 23HG
                            </div>
                            <div style="color: #19324e; font-size: 10pt; line-height: 1.5;">
                                {formatted}
                            </div>
                        </td>
                        <td width="3%"></td>
                    </tr>
                </table>
                """)

        if streaming_text is not None:
            formatted = self._format_assistant_markdown(streaming_text)
            out.append(f"""
            <table width="100%" border="0" cellpadding="0" cellspacing="0" style="margin: 10px 0;">
                <tr>
                    <td style="background-color: #ffffff; border: 1px solid #fed7aa; border-left: 4px solid #f59e0b;
                               padding: 12px 14px; border-radius: 4px;">
                        <div style="font-size: 8.5pt; font-weight: bold; color: #d97706; margin-bottom: 6px;">
                            🤖 ĐANG SOẠN CÂU TRẢ LỜI...
                        </div>
                        <div style="color: #19324e; font-size: 10pt; line-height: 1.5;">
                            {formatted}
                        </div>
                    </td>
                    <td width="3%"></td>
                </tr>
            </table>
            """)

        out.append("</div>")
        self.chat_view.setHtml("".join(out))
        self.chat_view.moveCursor(QTextCursor.End)

    def _format_assistant_markdown(self, text: str) -> str:
        """Chuyển đổi markdown hoàn chỉnh sang HTML kèm bảng biểu và liên kết trích dẫn."""
        # 1. Biến đổi trích dẫn [Trang X] thành thẻ liên kết
        def replace_cite(m):
            txt = m.group(0)
            p_match = re.search(r"Trang\s+(\d+)", txt, re.IGNORECASE)
            if p_match:
                pno = p_match.group(1)
                return f'<a href="page:{pno}" style="color: #205dd8; text-decoration: underline; font-weight: bold;">{txt}</a>'
            return txt

        t = re.sub(r"\[Trang\s+\d+[^\]]*\]", replace_cite, text)

        # 2. Xử lý in đậm, in nghiêng, code
        t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", t)
        t = re.sub(r"`([^`]+)`", r"<code style='background: #f1f5f9; padding: 2px 4px; border-radius: 3px;'>\1</code>", t)

        # 3. Xử lý tiêu đề
        t = re.sub(r"^### (.*)$", r"<h4 style='color: #0f2d59; margin: 10px 0 4px 0;'>\1</h4>", t, flags=re.MULTILINE)
        t = re.sub(r"^#### (.*)$", r"<h5 style='color: #1e293b; margin: 8px 0 3px 0;'>\1</h5>", t, flags=re.MULTILINE)

        # 4. Gom nhóm các dòng bảng Markdown (| a | b |) thành thẻ <table> HTML chuẩn
        lines = t.splitlines()
        out_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            sline = line.strip()
            if sline.startswith("|") and sline.endswith("|"):
                # Bắt đầu khối bảng
                table_lines = []
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                
                # Render table_lines thành HTML table
                tbl_html = ["<table border='1' cellspacing='0' cellpadding='5' style='border-collapse: collapse; border-color: #cbd5e1; width: 100%; margin: 8px 0; font-size: 9.5pt;'>"]
                is_header = True
                for tl in table_lines:
                    # Bỏ qua dòng phân cách |---|---|
                    if re.match(r"^\|(\s*:?-+:?\s*\|)+$", tl):
                        is_header = False
                        continue
                    cells = [c.strip() for c in tl.strip("|").split("|")]
                    tbl_html.append("<tr>")
                    tag = "th" if is_header else "td"
                    bg = "style='background-color: #f1f5f9; font-weight: bold; color: #1e293b;'" if is_header else ""
                    for c in cells:
                        tbl_html.append(f"<{tag} {bg}>{c}</{tag}>")
                    tbl_html.append("</tr>")
                tbl_html.append("</table>")
                out_lines.append("".join(tbl_html))
                continue

            elif sline.startswith("- "):
                out_lines.append(f"<li style='margin-bottom: 3px;'>{sline[2:]}</li>")
            elif sline == "---":
                out_lines.append("<hr style='border: 0; border-top: 1px solid #e2e8f0; margin: 10px 0;'>")
            elif sline:
                out_lines.append(f"<div style='margin-bottom: 4px;'>{sline}</div>")
            else:
                out_lines.append("<br>")
            i += 1

        return "".join(out_lines)

    @staticmethod
    def _escape_html(text: str) -> str:
        return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>"))

    def _get_history_dict(self):
        res = []
        for role, text in self.chat_history_data:
            res.append({"role": role, "content": text})
        return res

    def clear_chat(self):
        self.chat_history_data.clear()
        self._render_welcome()

    def export_chat(self):
        if not self.chat_history_data:
            QMessageBox.information(self, "Chưa có nội dung", "Chưa có cuộc trò chuyện nào để xuất.")
            return
        f, _ = QFileDialog.getSaveFileName(self, "Xuất biên bản hỏi đáp", "Bien_ban_hoi_dap_AI.md", "Markdown (*.md);;Text (*.txt)")
        if f:
            lines = [
                f"# BIÊN BẢN HỎI ĐÁP HỒ SƠ DỰ ÁN — TRỢ LÝ AI 23HG",
                f"- **Hồ sơ:** {self.kb.source_file or (self.current_folder.name if self.current_folder else 'Chưa xác định')}",
                f"- **Thời gian xuất:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- **Tác giả phần mềm:** Nguyễn Bảo Tú (23HG)\n",
                "---\n"
            ]
            for role, text in self.chat_history_data:
                tag = "👤 **KỸ SƯ HỎI:**" if role == "user" else "🤖 **TRỢ LÝ AI 23HG:**"
                lines.append(f"{tag}\n{text}\n")
            Path(f).write_text("\n".join(lines), encoding="utf-8")
            QMessageBox.information(self, "Xuất thành công", f"Đã lưu biên bản tại:\n{f}")
