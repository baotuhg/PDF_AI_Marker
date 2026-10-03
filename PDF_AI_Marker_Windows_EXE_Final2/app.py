"""
PDF AI Marker v3 — Commercial Edition
Hồ sơ xây dựng sang AI • Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG) — baotuhg@gmail.com
Giao diện Hiện đại chuẩn Windows 11 (Fluent Modern Theme & Dark Mode)
Thanh bên (Sidebar) chuyển 5 Tab:
  1. 📁 Bóc tách hồ sơ (PDF / Word / Excel / Scan OCR tiếng Việt)
  2. 📊 Bảng số liệu Excel (Trình duyệt bảng trích xuất & Đối chiếu trực quan)
  3. 🤖 Trợ lý AI (Local RAG Copilot hỏi đáp hồ sơ thiết kế)
  4. 🔑 Bản quyền & Đám mây (License Dashboard & Cloud Auto-Recovery)
  5. ⚙️ Cài đặt Hệ thống (Dark/Light Theme, GPU NVIDIA, Cloud Endpoint)
"""
from pathlib import Path
import json
import os
import queue
import sys
import threading
import unicodedata
from datetime import datetime
import ctypes

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PDF_AI_Marker.DesktopApp.3.0')
except Exception:
    pass

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QComboBox, QLineEdit,
    QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox,
    QStackedWidget, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QRadioButton, QButtonGroup, QScrollArea, QSplitter
)

from marker_bridge import convert, Cancelled
from license_core import (
    verify_license, get_license_status, _get_machine_id,
    save_license, import_license_file
)
from license_dialog import LicenseDialog
from license_cloud import recover_license_from_cloud, get_cloud_config, save_cloud_config
from license_core import _get_candidate_machine_ids
from fluent_theme import get_current_theme, save_current_theme, get_theme_qss

# (mã chế độ cho marker_worker, nhãn hiển thị)
MODES = [
    ('vn_ocr', '[Khuyến dùng] OCR tiếng Việt có dấu – bản vẽ/scan (~15–40s/trang • cần GPU NVIDIA)'),
    ('rapid_ocr', '[Nhanh] Quét OCR không dấu – bản vẽ/scan (~5–8s/trang)'),
    ('fast_text', '[Siêu nhanh] PDF bản gõ / bản vẽ AutoCAD, tự đọc chữ SHX (~0.3–7s/trang)'),
    ('auto', '[Marker] AI phân tích bố cục + OCR (tài liệu văn bản, sách)'),
    ('ocr', '[Marker OCR] Nhận dạng AI toàn bộ trang'),
    ('text', '[Marker Text] Chỉ text Marker (không OCR)'),
]

_EXTS = ('.pdf', '.docx', '.xlsx', '.xlsm')


def detect_nvidia_gpu():
    try:
        import subprocess
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return ''


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PDF AI Marker v3 • Hồ sơ xây dựng sang AI — Kỹ sư Nguyễn Bảo Tú (23HG)')
        
        icon_p = Path(__file__).resolve().parent / 'app_icon.ico'
        if not icon_p.exists():
            icon_p = Path(sys.executable).resolve().parent / 'app_icon.ico'
        if icon_p.exists():
            self.setWindowIcon(QIcon(str(icon_p)))

        self.resize(1180, 860)
        self.setMinimumSize(960, 740)
        self.setAcceptDrops(True)

        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.files = []
        self.busy = False
        self.latest = ''
        self.result_dir = None
        self.history = []  # (thư mục kết quả, file gốc, mật khẩu)
        self.inspector = None
        self.chat_win = None
        self.current_loaded_tables = []
        self.filtered_table_indices = []
        self.nav_buttons = []

        # ── 1. KHỞI TẠO THEME FLUENT UI ─────────────────────────────────────
        self.current_theme = get_current_theme()
        self.setStyleSheet(get_theme_qss(self.current_theme))

        # ── 2. XÂY DỰNG LAYOUT CHÍNH: SIDEBAR + STACKED CONTENT ──────────────
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Thanh bên Sidebar (trái)
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        # Vùng nội dung QStackedWidget 5 trang (phải)
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        self.page_extract = self._create_page_extract()
        self.page_tables = self._create_page_tables()
        self.page_chat = self._create_page_chat()
        self.page_license = self._create_page_license()
        self.page_settings = self._create_page_settings()

        self.stack.addWidget(self.page_extract)   # Tab 0
        self.stack.addWidget(self.page_tables)    # Tab 1
        self.stack.addWidget(self.page_chat)      # Tab 2
        self.stack.addWidget(self.page_license)   # Tab 3
        self.stack.addWidget(self.page_settings)  # Tab 4

        # Mặc định mở Tab 0 (Bóc tách hồ sơ)
        self.switch_tab(0)

        # ── 3. KIỂM TRA BẢN QUYỀN KHỞI ĐỘNG ──────────────────────────────────
        self.refresh_license_badge()
        ok, machine_id = verify_license()
        if not ok:
            dlg = LicenseDialog(machine_id, self)
            if dlg.exec() != LicenseDialog.Accepted:
                sys.exit(0)
            self.refresh_license_badge()

        # ── 4. TIMER SỰ KIỆN NỀN ─────────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    # ─────────────────────────────────────────────────────────────────────────
    # XÂY DỰNG THANH BÊN (SIDEBAR) CHUẨN WINDOWS 11 FLUENT UI
    # ─────────────────────────────────────────────────────────────────────────
    def _create_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(236)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 16)
        layout.setSpacing(8)

        # Brand Title & Logo
        lbl_brand = QLabel("PDF AI Marker")
        lbl_brand.setObjectName("brandTitle")
        layout.addWidget(lbl_brand)

        lbl_sub = QLabel("v3 Commercial Edition")
        lbl_sub.setObjectName("brandSub")
        layout.addWidget(lbl_sub)

        lbl_author = QLabel("Tác giả: Nguyễn Bảo Tú (23HG)")
        lbl_author.setStyleSheet("font-size: 8pt; color: #64748b; margin-bottom: 10px;")
        layout.addWidget(lbl_author)

        # Thanh phân cách
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #334155; margin-bottom: 6px;")
        layout.addWidget(sep)

        # Danh sách 5 nút điều hướng
        self.btn_nav_extract = QPushButton("📁  Bóc tách hồ sơ")
        self.btn_nav_extract.setProperty("class", "nav-btn")
        self.btn_nav_extract.clicked.connect(lambda: self.switch_tab(0))
        layout.addWidget(self.btn_nav_extract)
        self.nav_buttons.append(self.btn_nav_extract)

        self.btn_nav_tables = QPushButton("📊  Bảng số liệu Excel")
        self.btn_nav_tables.setProperty("class", "nav-btn")
        self.btn_nav_tables.clicked.connect(lambda: self.switch_tab(1))
        layout.addWidget(self.btn_nav_tables)
        self.nav_buttons.append(self.btn_nav_tables)

        self.btn_nav_chat = QPushButton("🤖  Trợ lý AI (RAG)")
        self.btn_nav_chat.setProperty("class", "nav-btn")
        self.btn_nav_chat.clicked.connect(lambda: self.switch_tab(2))
        layout.addWidget(self.btn_nav_chat)
        self.nav_buttons.append(self.btn_nav_chat)

        self.btn_nav_license = QPushButton("🔑  Bản quyền")
        self.btn_nav_license.setProperty("class", "nav-btn")
        self.btn_nav_license.clicked.connect(lambda: self.switch_tab(3))
        layout.addWidget(self.btn_nav_license)
        self.nav_buttons.append(self.btn_nav_license)

        self.btn_nav_settings = QPushButton("⚙️  Cài đặt")
        self.btn_nav_settings.setProperty("class", "nav-btn")
        self.btn_nav_settings.clicked.connect(lambda: self.switch_tab(4))
        layout.addWidget(self.btn_nav_settings)
        self.nav_buttons.append(self.btn_nav_settings)

        layout.addStretch()

        # Footer của Sidebar: Nút đổi nhanh Theme + Badge Bản quyền + GPU status
        theme_txt = "☀️ Chế độ Sáng" if self.current_theme == "dark" else "🌙 Chế độ Tối"
        self.btn_sidebar_theme = QPushButton(theme_txt)
        self.btn_sidebar_theme.setStyleSheet("font-size: 9pt; padding: 7px 12px; border-radius: 6px;")
        self.btn_sidebar_theme.clicked.connect(self.toggle_theme)
        layout.addWidget(self.btn_sidebar_theme)

        self.lbl_sidebar_license = QPushButton("👑 Bản quyền")
        self.lbl_sidebar_license.setStyleSheet(
            "font-size: 8.5pt; font-weight: 700; color: #38bdf8; padding: 6px 10px; "
            "background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 6px;"
        )
        self.lbl_sidebar_license.clicked.connect(lambda: self.switch_tab(3))
        layout.addWidget(self.lbl_sidebar_license)

        gpu = detect_nvidia_gpu()
        gpu_txt = f"🟢 {gpu[:22]}..." if len(gpu) > 22 else (f"🟢 {gpu}" if gpu else "⚪ Chế độ CPU")
        self.lbl_sidebar_gpu = QLabel(gpu_txt)
        self.lbl_sidebar_gpu.setStyleSheet("font-size: 8pt; color: #94a3b8;")
        self.lbl_sidebar_gpu.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sidebar_gpu)

        return sidebar

    # ─────────────────────────────────────────────────────────────────────────
    # CHUYỂN TAB & CẬP NHẬT TRẠNG THÁI ACTIVE CỦA NÚT SIDEBAR
    # ─────────────────────────────────────────────────────────────────────────
    def switch_tab(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            is_active = (i == index)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if index == 1:
            self.refresh_tables_tab()
        elif index == 2:
            if self.result_dir and Path(self.result_dir).exists():
                if self.chat_win and self.chat_win.current_folder != self.result_dir:
                    self.chat_win.load_project(str(self.result_dir))
        elif index == 3:
            self.refresh_license_page()

    # ─────────────────────────────────────────────────────────────────────────
    # ĐỔI THEME DARK / LIGHT FLUENT MODE
    # ─────────────────────────────────────────────────────────────────────────
    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(new_theme)

    def apply_theme(self, theme_name: str):
        self.current_theme = theme_name
        save_current_theme(theme_name)
        self.setStyleSheet(get_theme_qss(theme_name))
        theme_txt = "☀️ Chế độ Sáng" if theme_name == "dark" else "🌙 Chế độ Tối"
        if hasattr(self, "btn_sidebar_theme"):
            self.btn_sidebar_theme.setText(theme_txt)
        if hasattr(self, "rb_theme_dark") and hasattr(self, "rb_theme_light"):
            self.rb_theme_dark.setChecked(theme_name == "dark")
            self.rb_theme_light.setChecked(theme_name == "light")
        self.refresh_license_badge()

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 0: 📁 BÓC TÁCH HỒ SƠ (XỬ LÝ CHÍNH)
    # ─────────────────────────────────────────────────────────────────────────
    def _create_page_extract(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header trang
        header_row = QHBoxLayout()
        v_head = QVBoxLayout()
        t_page = QLabel("📁 Bóc tách Hồ sơ Xây dựng sang AI")
        t_page.setObjectName("pageTitle")
        sub_page = QLabel("OCR tiếng Việt có dấu • Bảng số liệu kẻ ô viền • Khung tên bản vẽ • Chạy 100% Offline")
        sub_page.setObjectName("pageSubtitle")
        v_head.addWidget(t_page)
        v_head.addWidget(sub_page)
        header_row.addLayout(v_head)
        header_row.addStretch()

        self.btn_license = QPushButton("👑 Bản quyền")
        self.btn_license.clicked.connect(lambda: self.switch_tab(3))
        header_row.addWidget(self.btn_license)
        layout.addLayout(header_row)

        # ── CARD 1: DANH SÁCH FILE ĐẦU VÀO ───────────────────────────────────
        card_files = QFrame()
        card_files.setProperty("class", "card")
        l_files = QVBoxLayout(card_files)
        l_files.setContentsMargins(16, 14, 16, 14)
        l_files.setSpacing(10)

        t_card1 = QLabel("Tài liệu đầu vào (Kéo & thả PDF / Word / Excel vào đây)")
        t_card1.setProperty("class", "card-title")
        l_files.addWidget(t_card1)

        row_fbtns = QHBoxLayout()
        self.add = QPushButton("+ Chọn file (PDF/Word/Excel)")
        self.add.clicked.connect(self.choose)
        self.add_dir = QPushButton("📁 Chọn Thư mục (Batch)")
        self.add_dir.clicked.connect(self.choose_folder)
        self.remove = QPushButton("Xóa danh sách")
        self.remove.clicked.connect(self.clear)
        row_fbtns.addWidget(self.add)
        row_fbtns.addWidget(self.add_dir)
        row_fbtns.addWidget(self.remove)
        row_fbtns.addStretch()
        self.count = QLabel("Chưa chọn file (hoặc kéo thả PDF/Word/Excel/Thư mục vào đây)")
        row_fbtns.addWidget(self.count)
        l_files.addLayout(row_fbtns)

        self.listbox = QListWidget()
        self.listbox.setMaximumHeight(105)
        l_files.addWidget(self.listbox)
        layout.addWidget(card_files)

        # ── CARD 2: CẤU HÌNH OCR & LƯU TRỮ ──────────────────────────────────
        card_cfg = QFrame()
        card_cfg.setProperty("class", "card")
        l_cfg = QVBoxLayout(card_cfg)
        l_cfg.setContentsMargins(16, 14, 16, 14)
        l_cfg.setSpacing(10)

        t_card2 = QLabel("Cấu hình Chế độ nhận dạng & Thư mục lưu kết quả")
        t_card2.setProperty("class", "card-title")
        l_cfg.addWidget(t_card2)

        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Cách đọc:"))
        self.mode = QComboBox()
        self.mode.addItems([m[1] for m in MODES])
        row_mode.addWidget(self.mode, 1)

        row_mode.addWidget(QLabel("Mật khẩu PDF:"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaximumWidth(160)
        row_mode.addWidget(self.password)
        l_cfg.addLayout(row_mode)

        row_save = QHBoxLayout()
        row_save.addWidget(QLabel("Lưu tại:"))
        self.out = QLineEdit(str(Path.home() / 'Documents' / 'PDF_AI_KetQua'))
        row_save.addWidget(self.out, 1)
        self.folder = QPushButton("Chọn thư mục")
        self.folder.clicked.connect(self.output)
        row_save.addWidget(self.folder)

        row_save.addWidget(QLabel("Trang cần đọc:"))
        self.pages = QLineEdit()
        self.pages.setPlaceholderText("Trống = tất cả (vd: 1-3,5)")
        self.pages.setMaximumWidth(160)
        row_save.addWidget(self.pages)
        l_cfg.addLayout(row_save)

        layout.addWidget(card_cfg)

        # ── CARD 3: ĐIỀU KHIỂN & KẾT QUẢ ────────────────────────────────────
        card_run = QFrame()
        card_run.setProperty("class", "card")
        l_run = QVBoxLayout(card_run)
        l_run.setContentsMargins(16, 14, 16, 14)
        l_run.setSpacing(10)

        row_act = QHBoxLayout()
        self.run = QPushButton("Chuyển đổi cho AI")
        self.run.setObjectName("primaryAction")
        self.run.clicked.connect(self.start)
        self.stop = QPushButton("Dừng")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.cancel.set)
        row_act.addWidget(self.run)
        row_act.addWidget(self.stop)
        row_act.addStretch()

        copy = QPushButton("Sao chép nội dung")
        copy.clicked.connect(self.copy)
        row_act.addWidget(copy)

        open_button = QPushButton("Mở thư mục")
        open_button.clicked.connect(self.open_result)
        row_act.addWidget(open_button)

        self.inspect_button = QPushButton("🔍 Đối chiếu trực quan")
        self.inspect_button.setToolTip("Mở bản vẽ gốc song song với bảng số liệu: bấm ô để khoanh đỏ đúng vị trí")
        self.inspect_button.setObjectName("accentAction")
        self.inspect_button.clicked.connect(self.open_inspector)
        row_act.addWidget(self.inspect_button)

        self.chat_button = QPushButton("🤖 Trợ lý AI (RAG)")
        self.chat_button.setToolTip("Hỏi đáp thông minh 100% offline với hồ sơ thiết kế vừa chuyển đổi")
        self.chat_button.clicked.connect(self.open_chat)
        row_act.addWidget(self.chat_button)
        l_run.addLayout(row_act)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        l_run.addWidget(self.progress)

        _gpu = detect_nvidia_gpu()
        self.mode.setCurrentIndex(0 if _gpu else 1)
        self.status = QLabel(
            f'PDF AI v3 | {"GPU: " + _gpu if _gpu else "Không có GPU NVIDIA"} | '
            'Tiếng Việt có dấu ~15–40s/trang (GPU) | OCR nhanh ~5–8s/trang | Bản gõ ~0.3s/trang'
        )
        self.status.setWordWrap(True)
        l_run.addWidget(self.status)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(180)
        self.preview.setPlainText(
            'Chọn file PDF, Word (.docx) hoặc Excel (.xlsx), chọn cách đọc rồi bấm Chuyển đổi cho AI. Chạy 100% offline.\n\n'
            '[Khuyến dùng] OCR tiếng Việt có dấu (~15–40s/trang, cần GPU NVIDIA):\n'
            '  Bản vẽ scan, hồ sơ thiết kế: giữ dấu tiếng Việt, dựng bảng theo đường kẻ ô,\n'
            '  tách khung tên (số hiệu, tên bản vẽ, tỷ lệ), dấu thẩm định, ghi chú kích thước.\n'
            '  Chữ số được kiểm tra chéo giữa 2 bộ OCR; chỗ lệch đánh dấu ⟦OCR khác: ...⟧.\n\n'
            '[Nhanh] Quét OCR không dấu (~5–8s/trang): như trên nhưng không đọc dấu tiếng Việt.\n\n'
            '[Siêu nhanh] Đọc chữ bản gõ PDF (~0.3s/trang): PDF xuất từ Word/Excel/AutoCAD,\n'
            '  vẫn dựng bảng và khung tên; tự chuyển font cũ TCVN3 (.VnTime) và VNI (VNI-Times).\n\n'
            'Kết quả: noi_dung.md • bang_so_lieu.json • bang_so_lieu.xlsx • du_lieu.json • chia_doan.jsonl • can_kiem_tra.md'
        )
        l_run.addWidget(self.preview, 1)

        layout.addWidget(card_run)

        scroll.setWidget(container)
        wrap = QVBoxLayout(page)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(scroll)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1: 📊 BẢNG SỐ LIỆU EXCEL & ĐỐI CHIẾU TRỰC QUAN
    # ─────────────────────────────────────────────────────────────────────────
    def _create_page_tables(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        v_h = QVBoxLayout()
        t_page = QLabel("📊 Bảng Số liệu Trích xuất & Đối chiếu")
        t_page.setObjectName("pageTitle")
        sub_page = QLabel("Duyệt toàn bộ các bảng tính bóc tách từ bản vẽ, dự toán và mở bảng tính Excel")
        sub_page.setObjectName("pageSubtitle")
        v_h.addWidget(t_page)
        v_h.addWidget(sub_page)
        h_box.addLayout(v_h)
        h_box.addStretch()
        layout.addLayout(h_box)

        # Card công cụ bảng
        card_tools = QFrame()
        card_tools.setProperty("class", "card")
        l_tools = QVBoxLayout(card_tools)
        l_tools.setContentsMargins(14, 12, 14, 12)
        l_tools.setSpacing(10)

        # Hàng 1: Bộ lọc phân loại AEC + Chọn bảng
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nhóm nghiệp vụ:"))
        self.combo_table_category = QComboBox()
        self.combo_table_category.addItem("🌐 Tất cả nhóm bảng", "all")
        self.combo_table_category.addItem("🔩 Thống kê Cốt thép (BBS)", "rebar")
        self.combo_table_category.addItem("🧱 Tổng hợp Khối lượng (BoQ)", "boq")
        self.combo_table_category.addItem("📑 Danh mục Bản vẽ", "sheet_index")
        self.combo_table_category.addItem("📐 Tọa độ & Thông số", "specs")
        self.combo_table_category.addItem("📊 Bảng số liệu khác", "general")
        self.combo_table_category.currentIndexChanged.connect(self._on_table_category_changed)
        row1.addWidget(self.combo_table_category)

        row1.addWidget(QLabel("Chọn bảng:"))
        self.combo_tables = QComboBox()
        self.combo_tables.currentIndexChanged.connect(self._on_table_selected)
        row1.addWidget(self.combo_tables, 1)
        l_tools.addLayout(row1)

        # Hàng 2: Các nút hành động
        row2 = QHBoxLayout()
        self.btn_open_excel = QPushButton("📊 Mở Excel (.xlsx) Phân Nhóm")
        self.btn_open_excel.setObjectName("primaryAction")
        self.btn_open_excel.clicked.connect(self.open_excel_file)
        row2.addWidget(self.btn_open_excel)

        self.btn_open_rebar = QPushButton("🔩 Tối ưu Cắt Thép")
        self.btn_open_rebar.setObjectName("accentAction")
        self.btn_open_rebar.clicked.connect(self.open_rebar_cutting_dialog)
        row2.addWidget(self.btn_open_rebar)

        self.btn_open_inspect_tab = QPushButton("🔍 Mở Đối chiếu trực quan")
        self.btn_open_inspect_tab.clicked.connect(self.open_inspector)
        row2.addWidget(self.btn_open_inspect_tab)

        self.btn_reload_tables = QPushButton("🔄 Nạp lại")
        self.btn_reload_tables.clicked.connect(self.refresh_tables_tab)
        row2.addWidget(self.btn_reload_tables)

        self.btn_choose_table_dir = QPushButton("📂 Chọn thư mục khác…")
        self.btn_choose_table_dir.clicked.connect(self.choose_table_folder)
        row2.addWidget(self.btn_choose_table_dir)
        l_tools.addLayout(row2)

        layout.addWidget(card_tools)

        # Bảng dữ liệu QTableWidget
        self.table_view = QTableWidget()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.table_view, 1)

        self.lbl_table_info = QLabel("Chưa nạp bảng số liệu. Sau khi bấm 'Chuyển đổi cho AI', bảng sẽ tự động xuất hiện tại đây.")
        self.lbl_table_info.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        layout.addWidget(self.lbl_table_info)

        return page

    def refresh_tables_tab(self):
        target_dir = self.result_dir or Path(self.out.text())
        if target_dir and Path(target_dir).exists():
            self.load_tables_from_dir(target_dir)

    def choose_table_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Chọn thư mục kết quả (*_Marker)", str(Path(self.out.text()).parent))
        if f:
            self.load_tables_from_dir(Path(f))

    def load_tables_from_dir(self, folder: Path):
        f_json = folder / "bang_so_lieu.json"
        if not f_json.exists():
            sub = next((d for d in folder.glob("*_Marker") if (d / "bang_so_lieu.json").exists()), None)
            if sub:
                f_json = sub / "bang_so_lieu.json"
                folder = sub

        if not f_json.exists():
            self.combo_tables.clear()
            self.table_view.clear()
            self.table_view.setRowCount(0)
            self.table_view.setColumnCount(0)
            self.lbl_table_info.setText(f"Không tìm thấy file bang_so_lieu.json trong: {folder}")
            return

        try:
            data = json.loads(f_json.read_text(encoding="utf-8"))
            if not isinstance(data, list) or not data:
                self.lbl_table_info.setText("Hồ sơ này không có bảng số liệu nào được nhận diện.")
                return

            # Chạy Agent phân loại & thẩm tra nếu dữ liệu cũ chưa có trường category
            try:
                from table_agent import AECTableClassifier, AECTableAuditor
                for tbl in data:
                    if "category" not in tbl:
                        cat, cat_name, conf = AECTableClassifier.classify(tbl)
                        tbl["category"] = cat
                        tbl["category_name"] = cat_name
                        tbl["confidence"] = round(conf, 2)
                        tbl["audit"] = AECTableAuditor.audit(tbl, cat)
            except Exception:
                pass

            self.current_loaded_tables = data
            self._update_category_counts()
            self._filter_tables_by_category()
        except Exception as e:
            self.lbl_table_info.setText(f"Lỗi đọc bang_so_lieu.json: {e}")

    def _update_category_counts(self):
        """Cập nhật số lượng bảng cho từng nhóm phân loại trên combobox."""
        if not self.current_loaded_tables:
            return
        counts = {"all": len(self.current_loaded_tables), "rebar": 0, "boq": 0, "sheet_index": 0, "specs": 0, "general": 0}
        for t in self.current_loaded_tables:
            cat = t.get("category", "general")
            counts[cat] = counts.get(cat, 0) + 1

        self.combo_table_category.blockSignals(True)
        items_map = [
            ("all", f"🌐 Tất cả nhóm bảng ({counts['all']})"),
            ("rebar", f"🔩 Thống kê Cốt thép ({counts.get('rebar', 0)})"),
            ("boq", f"🧱 Tổng hợp Khối lượng ({counts.get('boq', 0)})"),
            ("sheet_index", f"📑 Danh mục Bản vẽ ({counts.get('sheet_index', 0)})"),
            ("specs", f"📐 Tọa độ & Thông số ({counts.get('specs', 0)})"),
            ("general", f"📊 Bảng số liệu khác ({counts.get('general', 0)})"),
        ]
        curr_cat = self.combo_table_category.currentData() or "all"
        self.combo_table_category.clear()
        selected_idx = 0
        for idx, (c_code, c_label) in enumerate(items_map):
            self.combo_table_category.addItem(c_label, c_code)
            if c_code == curr_cat:
                selected_idx = idx
        self.combo_table_category.setCurrentIndex(selected_idx)
        self.combo_table_category.blockSignals(False)

    def _on_table_category_changed(self, _=0):
        self._filter_tables_by_category()

    def _filter_tables_by_category(self):
        """Lọc danh sách bảng hiển thị theo nhóm nghiệp vụ đã chọn."""
        cat = self.combo_table_category.currentData() or "all"
        self.filtered_table_indices = []
        for idx, t in enumerate(self.current_loaded_tables):
            if cat == "all" or t.get("category", "general") == cat:
                self.filtered_table_indices.append(idx)

        self.combo_tables.blockSignals(True)
        self.combo_tables.clear()
        for filtered_pos, orig_idx in enumerate(self.filtered_table_indices, 1):
            t = self.current_loaded_tables[orig_idx]
            pg = t.get("page", "?")
            sheet = t.get("sheet") or ""
            stitle = t.get("sheet_title") or ""
            rows = t.get("rows", [])
            cat_name = t.get("category_name", "Bảng")
            audit_stat = t.get("audit", {}).get("status", "ok")
            warn_icon = "⚠️ " if audit_stat != "ok" else ""

            label = f"{warn_icon}#{orig_idx+1} [{cat_name}] • P{pg}"
            if sheet:
                label += f" • {sheet}"
            label += f" ({len(rows)} dòng)"
            self.combo_tables.addItem(label)
        self.combo_tables.blockSignals(False)

        if self.filtered_table_indices:
            self.combo_tables.setCurrentIndex(0)
            self.display_table_data(self.filtered_table_indices[0])
        else:
            self.table_view.clear()
            self.table_view.setRowCount(0)
            self.table_view.setColumnCount(0)
            self.lbl_table_info.setText("Không có bảng nào trong nhóm nghiệp vụ này.")

    def _on_table_selected(self, combo_idx: int):
        if 0 <= combo_idx < len(self.filtered_table_indices):
            actual_idx = self.filtered_table_indices[combo_idx]
            self.display_table_data(actual_idx)

    def display_table_data(self, idx: int):
        if not self.current_loaded_tables or idx < 0 or idx >= len(self.current_loaded_tables):
            return
        t = self.current_loaded_tables[idx]
        headers = t.get("headers") or t.get("header") or []
        rows = t.get("rows", [])

        col_count = len(headers)
        if col_count == 0 and rows:
            col_count = max(len(r) for r in rows)
            headers = [f"Cột {c+1}" for c in range(col_count)]

        self.table_view.clear()
        self.table_view.setColumnCount(col_count)
        self.table_view.setRowCount(len(rows))
        self.table_view.setHorizontalHeaderLabels(headers)

        for r_i, row in enumerate(rows):
            for c_i, val in enumerate(row):
                if c_i < col_count:
                    item = QTableWidgetItem(str(val if val is not None else ""))
                    self.table_view.setItem(r_i, c_i, item)

        self.table_view.resizeColumnsToContents()
        for c_i in range(col_count):
            if self.table_view.columnWidth(c_i) > 320:
                self.table_view.setColumnWidth(c_i, 320)

        pg = t.get("page", "?")
        sheet = t.get("sheet") or ""
        stitle = t.get("sheet_title") or ""
        cat_name = t.get("category_name", "Bảng số liệu")
        title = t.get("title") or "Bảng không có tiêu đề"

        audit_info = t.get("audit", {})
        warnings = audit_info.get("warnings", [])
        if warnings:
            warn_txt = f" • <span style='color: #f59e0b; font-weight: bold;'>⚠️ {len(warnings)} lưu ý logic: {warnings[0]}</span>"
        else:
            warn_txt = " • <span style='color: #10b981; font-weight: bold;'>✅ Logic toán học khớp</span>"

        info_html = (
            f"<b>[{cat_name}]</b> {title} • Trang {pg} • {len(rows)} dòng x {col_count} cột"
            + (f" • Bản vẽ: <b>{sheet}</b> {stitle}" if sheet or stitle else "")
            + warn_txt
        )
        self.lbl_table_info.setText(info_html)

    def open_excel_file(self):
        target_dir = self.result_dir or Path(self.out.text())
        if not target_dir:
            return
        p_excel = target_dir / "bang_so_lieu.xlsx"
        if not p_excel.exists():
            sub = next((d for d in target_dir.glob("*_Marker") if (d / "bang_so_lieu.xlsx").exists()), None)
            if sub:
                p_excel = sub / "bang_so_lieu.xlsx"

        if p_excel.exists():
            os.startfile(str(p_excel))
        else:
            QMessageBox.information(self, "Chưa có file Excel", f"Không tìm thấy file bang_so_lieu.xlsx trong:\n{target_dir}")

    def open_rebar_cutting_dialog(self):
        target_dir = self.result_dir or Path(self.out.text())
        if not target_dir:
            return
        p_rebar = target_dir / "thep_cho_to_hop_cat.json"
        if not p_rebar.exists():
            sub = next((d for d in target_dir.glob("*_Marker") if (d / "thep_cho_to_hop_cat.json").exists()), None)
            if sub:
                p_rebar = sub / "thep_cho_to_hop_cat.json"

        if not p_rebar or not p_rebar.exists():
            QMessageBox.information(
                self, "Tối ưu Cắt Thép (1D Cutting Stock)",
                "Chưa có file 'thep_cho_to_hop_cat.json' trong thư mục kết quả này.\n\n"
                "👉 Khi bạn xử lý bản vẽ có Bảng Thống kê Cốt thép, "
                "phần mềm sẽ tự động chuẩn hóa danh sách thanh thép để nạp thẳng vào bộ kỹ năng "
                "'aec-rebar-optimizer' giải bài toán cắt thép tiết kiệm đề-xê (< 1.5%)."
            )
            return

        try:
            items = json.loads(p_rebar.read_text(encoding="utf-8"))
            n_bars = len(items)
            tot_qty = sum(it.get("quantity", 0) for it in items)
            tot_w = sum(it.get("total_weight_kg", 0) for it in items)
            msg = (
                f"🔩 DỮ LIỆU CỐT THÉP ĐÃ ĐƯỢC CHUẨN HÓA THÀNH CÔNG!\n\n"
                f"• Tổng số chủng loại thanh: {n_bars} mục\n"
                f"• Tổng số lượng thanh cần cắt: {tot_qty:,} thanh\n"
                f"• Tổng khối lượng cốt thép: {tot_w:,.2f} kg ({tot_w/1000:,.3f} tấn)\n"
                f"• Vị trí lưu: {p_rebar.name}\n\n"
                f"Dữ liệu đã chuẩn hóa 100% theo schema của kỹ năng AI 'aec-rebar-optimizer' "
                f"để tính toán sơ đồ ghép cây thép 11.7m tại công trường.\n\n"
                f"Bạn có muốn mở file dữ liệu này để xem không?"
            )
            ret = QMessageBox.question(self, "Tối ưu Cắt Thép (AEC Rebar)", msg,
                                       QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Cancel)
            if ret == QMessageBox.StandardButton.Open:
                os.startfile(str(p_rebar))
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc dữ liệu cốt thép", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2: 🤖 TRỢ LÝ AI (LOCAL RAG COPILOT)
    # ─────────────────────────────────────────────────────────────────────────
    def _create_page_chat(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        from chat_window import ChatWindow
        self.chat_win = ChatWindow(self, inspector_window=self.inspector)
        layout.addWidget(self.chat_win)
        return page

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 3: 🔑 QUẢN LÝ BẢN QUYỀN & ĐÁM MÂY (LICENSE DASHBOARD)
    # ─────────────────────────────────────────────────────────────────────────
    def _create_page_license(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        t_page = QLabel("🔑 Trung tâm Bản quyền & Quản lý License")
        t_page.setObjectName("pageTitle")
        sub_page = QLabel("Xác thực bản quyền gắn liền máy trạm (Node-locked) & Tự động phục hồi qua Đám Mây")
        sub_page.setObjectName("pageSubtitle")
        layout.addWidget(t_page)
        layout.addWidget(sub_page)

        # Card 1: Trạng thái bản quyền hiện tại
        card_st = QFrame()
        card_st.setProperty("class", "card")
        l_st = QVBoxLayout(card_st)
        l_st.setContentsMargins(18, 16, 18, 16)
        l_st.setSpacing(10)

        t_c1 = QLabel("Trạng thái Bản quyền Hiện tại")
        t_c1.setProperty("class", "card-title")
        l_st.addWidget(t_c1)

        self.lbl_lic_status_banner = QLabel("👑 BẢN QUYỀN VĨNH VIỄN (150 NĂM)")
        self.lbl_lic_status_banner.setStyleSheet(
            "font-size: 12pt; font-weight: 700; color: #38bdf8; padding: 10px 14px; "
            "background: rgba(56, 189, 248, 0.12); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 8px;"
        )
        l_st.addWidget(self.lbl_lic_status_banner)

        self.lbl_lic_details = QLabel("Đang tải thông tin...")
        self.lbl_lic_details.setTextFormat(Qt.RichText)
        self.lbl_lic_details.setStyleSheet("font-size: 10pt; color: #cbd5e1; line-height: 140%;")
        l_st.addWidget(self.lbl_lic_details)

        # Hàng Machine ID
        row_mid = QHBoxLayout()
        row_mid.addWidget(QLabel("Mã máy tính (Machine ID):"))
        self.txt_lic_mid = QLineEdit(_get_machine_id())
        self.txt_lic_mid.setReadOnly(True)
        row_mid.addWidget(self.txt_lic_mid, 1)

        btn_copy_mid = QPushButton("📋 Sao chép Machine ID")
        btn_copy_mid.clicked.connect(self.copy_machine_id)
        row_mid.addWidget(btn_copy_mid)
        l_st.addLayout(row_mid)

        # Bảo mật phần cứng
        hw_info = QLabel(
            "🔒 <b>Cơ chế bảo vệ:</b> CPU + BIOS + Ổ đĩa + Motherboard  |  "
            "Chống lùi đồng hồ (ClockAnchor): <b>Kích hoạt</b>  |  "
            "Sao lưu đa ổ đĩa: <b>Hoạt động</b>"
        )
        hw_info.setTextFormat(Qt.RichText)
        hw_info.setStyleSheet("font-size: 9pt; color: #64748b; margin-top: 4px;")
        l_st.addWidget(hw_info)

        layout.addWidget(card_st)

        # Card 2: Kích hoạt & Gia hạn
        card_act = QFrame()
        card_act.setProperty("class", "card")
        l_act = QVBoxLayout(card_act)
        l_act.setContentsMargins(18, 16, 18, 16)
        l_act.setSpacing(10)

        t_c2 = QLabel("Kích hoạt hoặc Nâng cấp Bản quyền")
        t_c2.setProperty("class", "card-title")
        l_act.addWidget(t_c2)

        desc_act = QLabel(
            "Nếu bạn có chuỗi License Key hoặc file bản quyền (.lic) do tác giả cung cấp, hãy dán hoặc chọn file bên dưới:"
        )
        desc_act.setStyleSheet("font-size: 9.5pt; color: #94a3b8;")
        l_act.addWidget(desc_act)

        row_key = QHBoxLayout()
        self.txt_lic_input = QLineEdit()
        self.txt_lic_input.setPlaceholderText("Dán chuỗi License Key (hoặc mã kích hoạt) vào đây...")
        row_key.addWidget(self.txt_lic_input, 1)

        btn_apply = QPushButton("Kích hoạt ngay")
        btn_apply.setObjectName("primaryAction")
        btn_apply.clicked.connect(self.apply_license_key)
        row_key.addWidget(btn_apply)

        btn_lic_file = QPushButton("Chọn file .lic…")
        btn_lic_file.clicked.connect(self.choose_lic_file)
        row_key.addWidget(btn_lic_file)
        l_act.addLayout(row_key)

        layout.addWidget(card_act)

        # Card 3: Khôi phục qua Đám mây (Cloud Auto-Recovery)
        card_cloud = QFrame()
        card_cloud.setProperty("class", "card")
        l_cloud = QVBoxLayout(card_cloud)
        l_cloud.setContentsMargins(18, 16, 18, 16)
        l_cloud.setSpacing(10)

        t_c3 = QLabel("☁️ Tự động Khôi phục Bản quyền từ Đám Mây (Google Sheets API)")
        t_c3.setProperty("class", "card-title")
        l_cloud.addWidget(t_c3)

        desc_cloud = QLabel(
            "Khi cài lại Windows, đổi ổ đĩa hoặc format máy: Nhấn nút bên dưới để tự động kết nối lên hệ thống Cloud "
            "của Tác giả để tải lại bản quyền của máy tính này mà không cần nhập lại mã."
        )
        desc_cloud.setWordWrap(True)
        desc_cloud.setStyleSheet("font-size: 9.5pt; color: #94a3b8;")
        l_cloud.addWidget(desc_cloud)

        row_cbtns = QHBoxLayout()
        self.btn_cloud_sync = QPushButton("☁️ Khôi phục bản quyền từ Cloud")
        self.btn_cloud_sync.setObjectName("accentAction")
        self.btn_cloud_sync.clicked.connect(self.restore_license_from_cloud)
        row_cbtns.addWidget(self.btn_cloud_sync)

        self.lbl_cloud_status = QLabel("Trạng thái Cloud: Sẵn sàng")
        self.lbl_cloud_status.setStyleSheet("color: #94a3b8; font-size: 9.5pt;")
        row_cbtns.addWidget(self.lbl_cloud_status, 1)
        l_cloud.addLayout(row_cbtns)

        layout.addWidget(card_cloud)

        scroll.setWidget(container)
        wrap = QVBoxLayout(page)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(scroll)
        return page

    def refresh_license_page(self):
        st = get_license_status()
        status = st.get("status", "EXPIRED")
        plan = st.get("plan", "LIFETIME")
        days_left = st.get("days_left", 0)
        exp_date = st.get("expire_date", "")
        customer = st.get("customer", "")

        if status == "ACTIVE":
            if plan == "LIFETIME":
                self.lbl_lic_status_banner.setText("👑 BẢN QUYỀN VĨNH VIỄN (150 NĂM — TRỌN ĐỜI)")
                self.lbl_lic_status_banner.setStyleSheet(
                    "font-size: 12pt; font-weight: 700; color: #38bdf8; padding: 10px 14px; "
                    "background: rgba(56, 189, 248, 0.12); border: 1.5px solid rgba(56, 189, 248, 0.35); border-radius: 8px;"
                )
                self.lbl_lic_details.setText(
                    f"• Khách hàng / Đơn vị: <b>{customer or 'Kỹ sư Xây dựng'}</b><br>"
                    f"• Thời hạn sử dụng: <b>{exp_date}</b> (Còn <b>{days_left}</b> ngày)<br>"
                    "• Quyền lợi: Mở khóa trọn đời toàn bộ tính năng OCR tiếng Việt, bóc tách bảng số liệu, xuất Excel và Trợ lý AI."
                )
            elif plan == "1_YEAR":
                self.lbl_lic_status_banner.setText(f"⭐ BẢN QUYỀN THƯƠNG MẠI 1 NĂM (CÒN {days_left} NGÀY)")
                self.lbl_lic_status_banner.setStyleSheet(
                    "font-size: 12pt; font-weight: 700; color: #34d399; padding: 10px 14px; "
                    "background: rgba(52, 211, 153, 0.12); border: 1.5px solid rgba(52, 211, 153, 0.35); border-radius: 8px;"
                )
                self.lbl_lic_details.setText(
                    f"• Khách hàng / Đơn vị: <b>{customer or 'Quý khách'}</b><br>"
                    f"• Hết hạn vào ngày: <b>{exp_date}</b> (Còn <b>{days_left}</b> ngày)<br>"
                    "• Quyền lợi: Đầy đủ tính năng thương mại. Hỗ trợ gia hạn linh hoạt hàng năm."
                )
            else:
                self.lbl_lic_status_banner.setText(f"🔑 BẢN QUYỀN HỢP LỆ (CÒN {days_left} NGÀY)")
                self.lbl_lic_details.setText(f"Hết hạn vào: <b>{exp_date}</b> (Còn {days_left} ngày)")
        elif status == "TRIAL":
            self.lbl_lic_status_banner.setText(f"🎁 BẢN DÙNG THỬ TRẢI NGHIỆM (CÒN {days_left} NGÀY)")
            self.lbl_lic_status_banner.setStyleSheet(
                "font-size: 12pt; font-weight: 700; color: #fbbf24; padding: 10px 14px; "
                "background: rgba(251, 191, 36, 0.12); border: 1.5px solid rgba(251, 191, 36, 0.35); border-radius: 8px;"
            )
            self.lbl_lic_details.setText(
                f"• Gói: <b>Dùng thử miễn phí 30 ngày</b><br>"
                f"• Còn lại: <b>{days_left}</b> ngày sử dụng<br>"
                "• Hãy liên hệ tác giả Nguyễn Bảo Tú (23HG) để nâng cấp lên bản quyền 1 Năm hoặc Vĩnh Viễn."
            )
        else:
            self.lbl_lic_status_banner.setText("🔒 HẾT HẠN BẢN QUYỀN — VUI LÒNG KÍCH HOẠT")
            self.lbl_lic_status_banner.setStyleSheet(
                "font-size: 12pt; font-weight: 700; color: #f87171; padding: 10px 14px; "
                "background: rgba(248, 113, 113, 0.12); border: 1.5px solid rgba(248, 113, 113, 0.35); border-radius: 8px;"
            )
            self.lbl_lic_details.setText("Thời hạn dùng thử hoặc bản quyền đã hết hạn. Hãy nhập License Key để tiếp tục sử dụng.")

    def copy_machine_id(self):
        mid = _get_machine_id()
        QApplication.clipboard().setText(mid)
        QMessageBox.information(self, "Đã sao chép", f"Đã sao chép Machine ID vào bộ nhớ đệm:\n{mid}\n\nBạn có thể gửi mã này cho tác giả.")

    def apply_license_key(self):
        k = self.txt_lic_input.text().strip()
        if not k:
            QMessageBox.warning(self, "Chưa nhập key", "Vui lòng nhập hoặc dán chuỗi License Key.")
            return
        ok, msg = save_license(k)
        if ok:
            QMessageBox.information(self, "Kích hoạt thành công", f"Chúc mừng! {msg}")
            self.txt_lic_input.clear()
            self.refresh_license_badge()
            self.refresh_license_page()
        else:
            QMessageBox.warning(self, "Kích hoạt thất bại", f"Mã bản quyền không hợp lệ cho máy này:\n{msg}")

    def choose_lic_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file bản quyền", "", "License File (*.lic);;All Files (*.*)")
        if f:
            ok, msg = import_license_file(f)
            if ok:
                QMessageBox.information(self, "Nạp file thành công", f"Đã nạp file bản quyền thành công:\n{msg}")
                self.refresh_license_badge()
                self.refresh_license_page()
            else:
                QMessageBox.warning(self, "Lỗi nạp file", f"Không thể nạp file bản quyền:\n{msg}")

    def restore_license_from_cloud(self):
        cands = _get_candidate_machine_ids()

        self.lbl_cloud_status.setText("Đang kết nối Cloud Google Sheets...")
        QApplication.processEvents()

        ok, msg, lic_dict = recover_license_from_cloud(cands)
        if ok and lic_dict:
            self.lbl_cloud_status.setText("✅ Khôi phục thành công từ Cloud!")
            QMessageBox.information(self, "Khôi phục Cloud thành công", f"Đã tìm thấy bản quyền trên hệ thống Cloud và tự động kích hoạt lại máy tính!\n{msg}")
            self.refresh_license_badge()
            self.refresh_license_page()
            return

        self.lbl_cloud_status.setText(f"Trạng thái: {msg}")
        QMessageBox.information(self, "Kết quả khôi phục Cloud", f"{msg}\n\nNếu bạn đã mua bản quyền, vui lòng liên hệ Tác giả để kiểm tra lại trên Google Sheet.")

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 4: ⚙️ CÀI ĐẶT HỆ THỐNG & THÔNG TIN TÁC GIẢ
    # ─────────────────────────────────────────────────────────────────────────
    def _create_page_settings(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        t_page = QLabel("⚙️ Cài đặt Hệ thống & Tùy biến")
        t_page.setObjectName("pageTitle")
        sub_page = QLabel("Tùy biến giao diện Fluent UI, cấu hình phần cứng và thông tin tác giả")
        sub_page.setObjectName("pageSubtitle")
        layout.addWidget(t_page)
        layout.addWidget(sub_page)

        # Card 1: Giao diện
        card_theme = QFrame()
        card_theme.setProperty("class", "card")
        l_th = QVBoxLayout(card_theme)
        l_th.setContentsMargins(18, 16, 18, 16)
        l_th.setSpacing(10)

        t_th = QLabel("Giao diện Người dùng (Windows 11 Fluent Theme)")
        t_th.setProperty("class", "card-title")
        l_th.addWidget(t_th)

        row_th = QHBoxLayout()
        self.rb_theme_dark = QRadioButton("🌙 Chế độ Tối (Dark Fluent - Slate 900)")
        self.rb_theme_light = QRadioButton("☀️ Chế độ Sáng (Light Clean - Mica)")

        if self.current_theme == "dark":
            self.rb_theme_dark.setChecked(True)
        else:
            self.rb_theme_light.setChecked(True)

        self.rb_theme_dark.toggled.connect(lambda c: self.apply_theme("dark") if c else None)
        self.rb_theme_light.toggled.connect(lambda c: self.apply_theme("light") if c else None)

        row_th.addWidget(self.rb_theme_dark)
        row_th.addWidget(self.rb_theme_light)
        row_th.addStretch()
        l_th.addLayout(row_th)

        layout.addWidget(card_theme)

        # Card 2: Phần cứng GPU
        card_hw = QFrame()
        card_hw.setProperty("class", "card")
        l_hw = QVBoxLayout(card_hw)
        l_hw.setContentsMargins(18, 16, 18, 16)
        l_hw.setSpacing(8)

        t_hw = QLabel("Tăng tốc Phần cứng AI (Hardware Acceleration)")
        t_hw.setProperty("class", "card-title")
        l_hw.addWidget(t_hw)

        gpu = detect_nvidia_gpu()
        gpu_status_str = f"✅ Phát hiện card đồ họa: <b>{gpu}</b> (Hỗ trợ tăng tốc Surya OCR & PyTorch CUDA)" if gpu else "⚪ Không phát hiện GPU NVIDIA rời. Phần mềm chạy ổn định ở chế độ Rapid OCR (CPU)."
        lbl_gpu = QLabel(gpu_status_str)
        lbl_gpu.setTextFormat(Qt.RichText)
        lbl_gpu.setStyleSheet("font-size: 10pt; color: #cbd5e1;")
        l_hw.addWidget(lbl_gpu)

        layout.addWidget(card_hw)

        # Card 3: Cloud Endpoint
        card_cep = QFrame()
        card_cep.setProperty("class", "card")
        l_cep = QVBoxLayout(card_cep)
        l_cep.setContentsMargins(18, 16, 18, 16)
        l_cep.setSpacing(10)

        t_cep = QLabel("Cấu hình Đám Mây (Cloud Auto-Recovery Endpoint)")
        t_cep.setProperty("class", "card-title")
        l_cep.addWidget(t_cep)

        cfg = get_cloud_config()
        row_cep = QHBoxLayout()
        row_cep.addWidget(QLabel("Google Apps Script URL:"))
        self.txt_cloud_url = QLineEdit(cfg.get("api_url", ""))
        row_cep.addWidget(self.txt_cloud_url, 1)

        btn_save_cloud = QPushButton("Lưu cấu hình Cloud")
        btn_save_cloud.clicked.connect(self.save_cloud_settings)
        row_cep.addWidget(btn_save_cloud)
        l_cep.addLayout(row_cep)

        layout.addWidget(card_cep)

        # Card 4: Tác giả & Bản quyền
        card_info = QFrame()
        card_info.setProperty("class", "card")
        l_info = QVBoxLayout(card_info)
        l_info.setContentsMargins(18, 16, 18, 16)
        l_info.setSpacing(8)

        t_info = QLabel("Thông tin Bản quyền & Tác giả")
        t_info.setProperty("class", "card-title")
        l_info.addWidget(t_info)

        info_txt = QLabel(
            "• Phần mềm: <b>PDF AI Marker v3 Commercial Edition</b><br>"
            "• Tác giả: <b>Kỹ sư Nguyễn Bảo Tú (23HG)</b><br>"
            "• Email liên hệ & Hỗ trợ kỹ thuật: <b>baotuhg@gmail.com</b><br>"
            "• Tiêu chuẩn: <b>100% Offline AI</b> — Bảo mật tuyệt đối dữ liệu và hồ sơ thiết kế công trình.<br>"
            "• Phiên bản giao diện: <b>Windows 11 Fluent UI Glassmorphism</b>"
        )
        info_txt.setTextFormat(Qt.RichText)
        info_txt.setStyleSheet("font-size: 10pt; color: #cbd5e1; line-height: 140%;")
        l_info.addWidget(info_txt)

        layout.addWidget(card_info)

        scroll.setWidget(container)
        wrap = QVBoxLayout(page)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.addWidget(scroll)
        return page

    def save_cloud_settings(self):
        url = self.txt_cloud_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Thiếu URL", "Vui lòng nhập URL Web App Google Apps Script.")
            return
        if save_cloud_config(url):
            QMessageBox.information(self, "Đã lưu", "Cấu hình Cloud Endpoint đã được cập nhật thành công.")
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể ghi file cấu hình cloud_config.json.")

    # ─────────────────────────────────────────────────────────────────────────
    # REFRESH BADGE BẢN QUYỀN
    # ─────────────────────────────────────────────────────────────────────────
    def refresh_license_badge(self):
        st = get_license_status()
        status = st.get("status", "EXPIRED")
        plan = st.get("plan", "LIFETIME")
        days_left = st.get("days_left", 0)

        if status == "ACTIVE":
            if plan == "LIFETIME":
                txt = "👑 Bản quyền: [VĨNH VIỄN 150 NĂM]"
                style = (
                    "QPushButton { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1.5px solid #38bdf8; "
                    "font-weight: 700; padding: 7px 16px; border-radius: 8px; font-size: 10pt; } "
                    "QPushButton:hover { background: rgba(56, 189, 248, 0.25); }"
                )
                sidebar_txt = "👑 150 Năm"
            elif plan == "1_YEAR":
                txt = f"⭐ Bản quyền 1 Năm: [CÒN {days_left} NGÀY]"
                style = (
                    "QPushButton { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1.5px solid #34d399; "
                    "font-weight: 700; padding: 7px 16px; border-radius: 8px; font-size: 10pt; } "
                    "QPushButton:hover { background: rgba(52, 211, 153, 0.25); }"
                )
                sidebar_txt = f"⭐ 1 Năm ({days_left}d)"
            else:
                txt = f"🔑 Bản quyền: [CÒN {days_left} NGÀY]"
                style = (
                    "QPushButton { background: rgba(52, 211, 153, 0.15); color: #34d399; border: 1px solid #34d399; "
                    "font-weight: 600; padding: 7px 16px; border-radius: 8px; font-size: 10pt; } "
                    "QPushButton:hover { background: rgba(52, 211, 153, 0.25); }"
                )
                sidebar_txt = f"🔑 Còn {days_left}d"
        elif status == "TRIAL":
            txt = f"🎁 Dùng thử: [CÒN {days_left} NGÀY] — Kích hoạt"
            style = (
                "QPushButton { background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 1px solid #fbbf24; "
                "font-weight: 600; padding: 7px 16px; border-radius: 8px; font-size: 10pt; } "
                "QPushButton:hover { background: rgba(251, 191, 36, 0.25); }"
            )
            sidebar_txt = f"🎁 Dùng thử ({days_left}d)"
        else:
            txt = "🔒 HẾT HẠN BẢN QUYỀN — Nhập key"
            style = (
                "QPushButton { background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid #f87171; "
                "font-weight: 600; padding: 7px 16px; border-radius: 8px; font-size: 10pt; } "
                "QPushButton:hover { background: rgba(248, 113, 113, 0.25); }"
            )
            sidebar_txt = "🔒 Hết hạn"

        if hasattr(self, "btn_license"):
            self.btn_license.setText(txt)
            self.btn_license.setStyleSheet(style)
        if hasattr(self, "lbl_sidebar_license"):
            self.lbl_sidebar_license.setText(sidebar_txt)

    # ─────────────────────────────────────────────────────────────────────────
    # THAO TÁC QUẢN LÝ DANH SÁCH FILE & DRAG-AND-DROP
    # ─────────────────────────────────────────────────────────────────────────
    def _add_files(self, file_paths):
        added = 0
        for f in file_paths:
            f_str = str(Path(f).resolve())
            if f_str.lower().endswith(_EXTS) and f_str not in self.files:
                self.files.append(f_str)
                self.listbox.addItem(f_str)
                added += 1
        if self.files:
            self.count.setText(f'{len(self.files)} file')
        else:
            self.count.setText('Chưa chọn file (hoặc kéo thả PDF/Word/Excel/Thư mục vào đây)')
        return added

    def choose(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, 'Chọn file', '',
            'Hồ sơ (*.pdf *.docx *.xlsx *.xlsm);;PDF (*.pdf);;Word (*.docx);;Excel (*.xlsx *.xlsm)'
        )
        self._add_files(files)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục dự án chứa hồ sơ')
        if not folder:
            return
        p = Path(folder)
        all_paths = []
        for ext in _EXTS:
            all_paths.extend([str(f) for f in p.rglob(f"*{ext}")])
        if not all_paths:
            QMessageBox.information(self, "Không tìm thấy file", f"Không tìm thấy file PDF, Word, Excel nào trong thư mục:\n{folder}")
            return
        added = self._add_files(all_paths)
        self.status.setText(f"Đã quét và thêm {added} file từ thư mục dự án: {p.name}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(os.path.isdir(u.toLocalFile()) or u.toLocalFile().lower().endswith(_EXTS) for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            all_paths = []
            for u in event.mimeData().urls():
                p = Path(u.toLocalFile())
                if p.is_dir():
                    for ext in _EXTS:
                        all_paths.extend([str(f) for f in p.rglob(f"*{ext}")])
                elif p.suffix.lower() in _EXTS:
                    all_paths.append(str(p))
            if all_paths:
                added = self._add_files(all_paths)
                self.status.setText(f"Đã kéo thả và thêm {added} file vào danh sách.")
                event.acceptProposedAction()
                return
        event.ignore()

    def clear(self):
        self.files.clear()
        self.listbox.clear()
        self.count.setText('Chưa chọn file (hoặc kéo thả PDF/Word/Excel/Thư mục vào đây)')

    def output(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục')
        if folder:
            self.out.setText(folder)

    def copy(self):
        if self.latest:
            QApplication.clipboard().setText(self.latest)
            self.status.setText('Đã sao chép toàn bộ nội dung của file thành công gần nhất.')

    def open_result(self):
        path = self.result_dir or Path(self.out.text())
        if path.is_dir():
            os.startfile(str(path))

    def open_inspector(self):
        try:
            from inspector import InspectorWindow
        except Exception as exc:
            QMessageBox.warning(self, 'Đối chiếu trực quan', f'Không khởi động được trình đối chiếu:\n{type(exc).__name__}: {exc}')
            return
        if self.inspector is None:
            self.inspector = InspectorWindow(self)
        if self.history:
            folder, source, password = self.history[-1]
            if self.inspector.result_dir != folder:
                if self.inspector.load_result(folder, source, password):
                    return
            else:
                self.inspector.show()
                self.inspector.raise_()
                self.inspector.activateWindow()
                return
        elif self.inspector.result_dir is not None:
            self.inspector.show()
            self.inspector.raise_()
            self.inspector.activateWindow()
            return
        self.inspector.choose_result()

    def open_chat(self):
        # Chuyển thẳng sang Tab 2 (Trợ lý AI tích hợp)
        self.switch_tab(2)

    def closeEvent(self, event):
        if self.busy:
            self.cancel.set()
            self.status.setText('Đang dừng. Đóng cửa sổ khi xử lý trang hiện tại kết thúc.')
            event.ignore()
        else:
            event.accept()

    # ─────────────────────────────────────────────────────────────────────────
    # TIẾN TRÌNH XỬ LÝ BACKGROUND & QUEUE SỰ KIỆN
    # ─────────────────────────────────────────────────────────────────────────
    def start(self):
        ok, machine_id = verify_license()
        if not ok:
            QMessageBox.warning(
                self, "Hết hạn bản quyền",
                "Thời hạn dùng thử miễn phí đã hết hoặc máy chưa được kích hoạt.\nVui lòng kích hoạt bản quyền để tiếp tục."
            )
            self.switch_tab(3)
            return
        if not self.files:
            QMessageBox.information(self, 'Chọn PDF', 'Hãy chọn ít nhất một file PDF/Word/Excel.')
            return
        if not self.out.text().strip():
            QMessageBox.information(self, 'Thư mục kết quả', 'Hãy chọn thư mục lưu kết quả.')
            return

        self.busy = True
        self.cancel.clear()
        self.progress.setRange(0, 0)
        for control in [self.run, self.add, self.add_dir, self.remove, self.out, self.folder, self.mode, self.password, self.pages]:
            control.setEnabled(False)
        self.stop.setEnabled(True)
        mode = MODES[self.mode.currentIndex()][0]
        args = (list(self.files), self.out.text(), mode, self.password.text(), self.pages.text())
        threading.Thread(target=self.worker, args=args, daemon=True).start()

    def worker(self, files, destination, mode, password, pages):
        done, errors, notices = 0, [], []
        total_files = len(files)
        for index, source in enumerate(files, 1):
            if self.cancel.is_set():
                break
            try:
                def update(n, total, label):
                    file_ratio = (n / max(1, total)) if total > 0 else 0
                    overall_pct = int(((index - 1) + file_ratio) / total_files * 100)
                    self.events.put(('progress', overall_pct, f'File [{index}/{total_files}] • {Path(source).name} • {label}'))
                target, data, markdown = convert(source, destination, mode, password,
                                                cancel=self.cancel, progress=update, pages=pages)
                done += 1
                warned = sum(bool(p['warnings']) for p in data['pages'])
                if warned:
                    notices.append(f'{Path(source).name}: {warned} trang cần kiểm tra')
                self.events.put(('result', markdown, str(target), source, password))
            except Cancelled:
                break
            except Exception as exc:
                errors.append(f'{Path(source).name}: {type(exc).__name__}: {exc}')
        self.events.put(('done', done, errors, notices, self.cancel.is_set()))

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'progress':
                    pct = event[1]
                    if pct > 0:
                        self.progress.setRange(0, 100)
                        self.progress.setValue(pct)
                    else:
                        self.progress.setRange(0, 0)
                    self.status.setText(event[2])
                elif event[0] == 'result':
                    self.latest = event[1]
                    self.result_dir = Path(event[2]).parent
                    if len(event) >= 5:
                        tgt = Path(event[2])
                        self.history.append((tgt if tgt.is_dir() else tgt.parent, event[3], event[4]))
                    preview = self.latest[:150000]
                    if len(self.latest) > 150000:
                        preview += '\n\n[Xem trước rút gọn; file xuất chứa toàn bộ nội dung.]'
                    self.preview.setPlainText(preview)
                    # Tự động nạp bảng số liệu vào Tab 1
                    try:
                        self.load_tables_from_dir(self.result_dir)
                    except Exception:
                        pass
                elif event[0] == 'done':
                    self.busy = False
                    self.progress.setRange(0, 100)
                    for control in [self.run, self.add, self.add_dir, self.remove, self.out, self.folder, self.mode, self.password, self.pages]:
                        control.setEnabled(True)
                    self.stop.setEnabled(False)
                    self.password.clear()
                    label = 'Đã dừng' if event[4] else 'Hoàn tất'
                    self.status.setText(
                        f'{label} • {event[1]} file đã xuất • {len(event[2])} lỗi • {len(event[3])} file cần kiểm tra'
                        + (' • Bấm 📊 Bảng số liệu hoặc 🤖 Trợ lý AI để tra cứu' if event[1] else '')
                    )
                    if event[2] or event[3]:
                        QMessageBox.warning(self, 'Kết quả chuyển đổi', '\n'.join(event[2] + event[3])[:5000])
        except queue.Empty:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# ĐIỂM KHỞI CHẠY ỨNG DỤNG (ENTRY POINT)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    app = QApplication(sys.argv)
    icon_p = Path(__file__).resolve().parent / 'app_icon.ico'
    if not icon_p.exists():
        icon_p = Path(sys.executable).resolve().parent / 'app_icon.ico'
    if icon_p.exists():
        app.setWindowIcon(QIcon(str(icon_p)))

    window = App()
    window.show()

    # --inspect "<thư mục>_Marker" : mở thẳng cửa sổ Đối chiếu trực quan cho kết quả có sẵn
    inspect_dir = None
    if '--inspect' in sys.argv:
        i = sys.argv.index('--inspect')
        if i + 1 < len(sys.argv):
            inspect_dir = sys.argv[i + 1]
            window.history.append((Path(inspect_dir), None, ''))
            window.open_inspector()

    # --chat "<thư mục>_Marker" : mở thẳng cửa sổ Trợ lý AI (RAG Chat)
    chat_dir = None
    if '--chat' in sys.argv:
        i = sys.argv.index('--chat')
        if i + 1 < len(sys.argv):
            chat_dir = sys.argv[i + 1]
            window.history.append((Path(chat_dir), None, ''))
            window.switch_tab(2)

    if '--self-test' in sys.argv:
        import time
        t0 = time.time()
        while time.time() - t0 < (1.5 if (inspect_dir or chat_dir) else 0.2):
            app.processEvents()
            time.sleep(0.02)
        if chat_dir and window.chat_win:
            target = window.chat_win
        elif inspect_dir and window.inspector:
            target = window.inspector
        else:
            target = window
        target.grab().save(sys.argv[-1])
        if window.inspector:
            window.inspector.close()
        window.close()
    else:
        sys.exit(app.exec())
