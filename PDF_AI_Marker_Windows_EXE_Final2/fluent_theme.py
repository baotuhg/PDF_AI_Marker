"""
Fluent UI Theme Engine — Windows 11 Modern & Dark Mode
Thiết kế theo phong cách Windows 11 Fluent UI / Mica / Glassmorphism
Hỗ trợ chuyển đổi tức thì giữa Chế độ Sáng (Light) và Chế độ Tối (Dark)
"""
import json
import os
import sys
from pathlib import Path

_THEME_FILE = "theme_config.json"


def _get_config_path() -> Path:
    exe = Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False):
        return exe / _THEME_FILE
    return Path(__file__).resolve().parent / _THEME_FILE


def get_current_theme() -> str:
    """Đọc theme đã lưu (mặc định: 'dark' hoặc 'light')."""
    cfg_p = _get_config_path()
    if cfg_p.exists():
        try:
            d = json.loads(cfg_p.read_text(encoding="utf-8"))
            return d.get("theme", "dark")
        except Exception:
            pass
    return "dark"  # Mặc định Dark Mode hiện đại bảo vệ mắt kỹ sư


def save_current_theme(theme_name: str):
    """Lưu theme lựa chọn của người dùng."""
    cfg_p = _get_config_path()
    try:
        data = {"theme": theme_name, "version": "3.0"}
        cfg_p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 🌙 DARK MODE STYLESHEET (Chuẩn Slate 900 / Windows 11 Dark)
# ─────────────────────────────────────────────────────────────────────────────
DARK_THEME_QSS = """
/* Toàn bộ cửa sổ và font chữ Segoe UI */
QMainWindow, QWidget#centralWidget {
    background-color: #0b1120;
    color: #f1f5f9;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 10pt;
}

/* Sidebar bên trái */
QWidget#sidebar {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

/* Logo & Tiêu đề sidebar */
QLabel#brandTitle {
    font-size: 15pt;
    font-weight: 800;
    color: #38bdf8;
    letter-spacing: -0.5px;
}
QLabel#brandSub {
    font-size: 8.5pt;
    font-weight: 500;
    color: #94a3b8;
}

/* Nút điều hướng Sidebar */
QPushButton.nav-btn {
    text-align: left;
    padding: 11px 16px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: #94a3b8;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton.nav-btn:hover {
    background-color: #1e293b;
    color: #f8fafc;
}
QPushButton.nav-btn[active="true"] {
    background-color: #1e293b;
    color: #38bdf8;
    border-left: 3.5px solid #38bdf8;
    font-weight: 700;
}

/* Thẻ Container (Cards) */
QFrame.card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 16px;
}

QFrame.card-highlight {
    background-color: #0f172a;
    border: 1.5px solid #0284c7;
    border-radius: 10px;
    padding: 16px;
}

/* Tiêu đề nhóm trong Card */
QLabel.card-title {
    font-size: 12.5pt;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 4px;
}
QLabel.card-desc {
    font-size: 9.5pt;
    color: #94a3b8;
}

/* Các loại nút bấm */
QPushButton {
    background-color: #1f2937;
    color: #f3f4f6;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 10pt;
}
QPushButton:hover {
    background-color: #374151;
    border-color: #4b5563;
}
QPushButton:disabled {
    background-color: #111827;
    color: #4b5563;
    border-color: #1f2937;
}

/* Nút chính nổi bật (Primary Action) */
QPushButton#primaryAction {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    font-weight: 700;
    font-size: 10.5pt;
    padding: 10px 22px;
    border-radius: 8px;
}
QPushButton#primaryAction:hover {
    background-color: #0369a1;
}
QPushButton#primaryAction:disabled {
    background-color: #0c4a6e;
    color: #7dd3fc;
}

/* Nút Accent phụ */
QPushButton#accentAction {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0369a1;
    font-weight: 600;
}
QPushButton#accentAction:hover {
    background-color: #0369a1;
    color: #ffffff;
}

/* Ô nhập liệu & Danh sách */
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QListWidget, QTableWidget {
    background-color: #030712;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 10pt;
    selection-background-color: #0284c7;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1.5px solid #38bdf8;
}

/* Thanh cuộn (Scrollbar) mỏng hiện đại */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Thanh tiến trình Progress Bar */
QProgressBar {
    border: none;
    background-color: #1f2937;
    height: 8px;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 4px;
}

/* Tiêu đề trang */
QLabel#pageTitle {
    font-size: 16pt;
    font-weight: 800;
    color: #38bdf8;
}
QLabel#pageSubtitle {
    font-size: 9.5pt;
    color: #94a3b8;
}

/* Vùng cuộn QScrollArea */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollArea > QWidget {
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* Radio buttons */
QRadioButton {
    color: #f1f5f9;
    font-size: 10pt;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1.5px solid #4b5563;
    background-color: #0f172a;
}
QRadioButton::indicator:checked {
    border-color: #38bdf8;
    background-color: #0284c7;
}

/* Bảng TableWidget */
QHeaderView::section {
    background-color: #111827;
    color: #94a3b8;
    padding: 8px;
    font-weight: 700;
    border: none;
    border-bottom: 1.5px solid #1f2937;
}
QTableWidget {
    gridline-color: #1f2937;
}
QTableWidget::item:selected {
    background-color: #0369a1;
    color: #ffffff;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# ☀️ LIGHT MODE STYLESHEET (Chuẩn Windows 11 Mica / Clean Slate)
# ─────────────────────────────────────────────────────────────────────────────
LIGHT_THEME_QSS = """
/* Toàn bộ cửa sổ và font chữ Segoe UI */
QMainWindow, QWidget#centralWidget {
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif;
    font-size: 10pt;
}

/* Sidebar bên trái */
QWidget#sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}

/* Logo & Tiêu đề sidebar */
QLabel#brandTitle {
    font-size: 15pt;
    font-weight: 800;
    color: #0284c7;
    letter-spacing: -0.5px;
}
QLabel#brandSub {
    font-size: 8.5pt;
    font-weight: 500;
    color: #64748b;
}

/* Nút điều hướng Sidebar */
QPushButton.nav-btn {
    text-align: left;
    padding: 11px 16px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: #475569;
    font-size: 10pt;
    font-weight: 600;
}
QPushButton.nav-btn:hover {
    background-color: #f1f5f9;
    color: #0f172a;
}
QPushButton.nav-btn[active="true"] {
    background-color: #e0f2fe;
    color: #0369a1;
    border-left: 3.5px solid #0284c7;
    font-weight: 700;
}

/* Thẻ Container (Cards) */
QFrame.card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
}

QFrame.card-highlight {
    background-color: #f0f9ff;
    border: 1.5px solid #bae6fd;
    border-radius: 10px;
    padding: 16px;
}

/* Tiêu đề nhóm trong Card */
QLabel.card-title {
    font-size: 12.5pt;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 4px;
}
QLabel.card-desc {
    font-size: 9.5pt;
    color: #64748b;
}

/* Các loại nút bấm */
QPushButton {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 10pt;
}
QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}
QPushButton:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Nút chính nổi bật (Primary Action) */
QPushButton#primaryAction {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    font-weight: 700;
    font-size: 10.5pt;
    padding: 10px 22px;
    border-radius: 8px;
}
QPushButton#primaryAction:hover {
    background-color: #0369a1;
}
QPushButton#primaryAction:disabled {
    background-color: #93c5fd;
    color: #ffffff;
}

/* Nút Accent phụ */
QPushButton#accentAction {
    background-color: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    font-weight: 600;
}
QPushButton#accentAction:hover {
    background-color: #dcfce7;
}

/* Ô nhập liệu & Danh sách */
QLineEdit, QComboBox, QPlainTextEdit, QTextBrowser, QListWidget, QTableWidget {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 10pt;
    selection-background-color: #0284c7;
}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1.5px solid #0284c7;
}

/* Thanh cuộn (Scrollbar) mỏng hiện đại */
QScrollBar:vertical {
    border: none;
    background: #f1f5f9;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Thanh tiến trình Progress Bar */
QProgressBar {
    border: none;
    background-color: #e2e8f0;
    height: 8px;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
    border-radius: 4px;
}

/* Tiêu đề trang */
QLabel#pageTitle {
    font-size: 16pt;
    font-weight: 800;
    color: #0369a1;
}
QLabel#pageSubtitle {
    font-size: 9.5pt;
    color: #64748b;
}

/* Vùng cuộn QScrollArea */
QScrollArea {
    background-color: transparent;
    border: none;
}
QScrollArea > QWidget {
    background-color: transparent;
}
QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* Radio buttons */
QRadioButton {
    color: #0f172a;
    font-size: 10pt;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1.5px solid #94a3b8;
    background-color: #ffffff;
}
QRadioButton::indicator:checked {
    border-color: #0284c7;
    background-color: #0284c7;
}

/* Bảng TableWidget */
QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    padding: 8px;
    font-weight: 700;
    border: none;
    border-bottom: 1.5px solid #e2e8f0;
}
QTableWidget {
    gridline-color: #f1f5f9;
}
QTableWidget::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}
"""


def get_theme_qss(theme_name: str = None) -> str:
    """Trả về chuỗi QSS tương ứng với theme ('dark' hoặc 'light')."""
    if theme_name is None:
        theme_name = get_current_theme()
    if str(theme_name).lower() == "light":
        return LIGHT_THEME_QSS
    return DARK_THEME_QSS

