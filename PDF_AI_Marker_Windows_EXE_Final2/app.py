"""PDF AI: offline Windows PDF extraction and Vietnamese/English OCR."""
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
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QListWidget, QComboBox, QLineEdit,
    QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox)
from marker_bridge import convert, Cancelled
from license_core import verify_license
from license_dialog import LicenseDialog

# (mã chế độ cho marker_worker, nhãn hiển thị)
MODES = [
    ('vn_ocr', '[Khuyến dùng] OCR tiếng Việt có dấu – bản vẽ/scan (~15–40s/trang • cần GPU NVIDIA)'),
    ('rapid_ocr', '[Nhanh] Quét OCR không dấu – bản vẽ/scan (~5–8s/trang)'),
    ('fast_text', '[Siêu nhanh] PDF bản gõ / bản vẽ AutoCAD, tự đọc chữ SHX (~0.3–7s/trang)'),
    ('auto', '[Marker] AI phân tích bố cục + OCR (tài liệu văn bản, sách)'),
    ('ocr', '[Marker OCR] Nhận dạng AI toàn bộ trang'),
    ('text', '[Marker Text] Chỉ text Marker (không OCR)'),
]


def detect_nvidia_gpu():
    try:
        import subprocess
        r = subprocess.run(['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                           capture_output=True, text=True, timeout=3,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return ''

_EXTS = ('.pdf', '.docx', '.xlsx', '.xlsm')  # .doc/.xls đời cũ: chuyển sang .docx/.xlsx trước

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PDF AI Marker v3 • Hồ sơ xây dựng sang AI — Tác giả: Nguyễn Bảo Tú (23HG)')
        icon_p = Path(__file__).resolve().parent / 'app_icon.ico'
        if not icon_p.exists():
            icon_p = Path(sys.executable).resolve().parent / 'app_icon.ico'
        if icon_p.exists():
            self.setWindowIcon(QIcon(str(icon_p)))
        self.resize(1040, 850)
        self.setMinimumSize(850, 740)
        self.setAcceptDrops(True)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.files = []
        self.busy = False
        self.latest = ''
        self.result_dir = None
        self.history = []  # (thư mục kết quả, file gốc, mật khẩu) để mở Đối chiếu trực quan
        self.inspector = None
        self.chat_win = None
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f3f6fb; color: #19324e; font: 10pt 'Segoe UI'; }
            QPushButton { background: white; border: 1px solid #d7e0ec; border-radius: 7px; padding: 9px 15px; }
            QPushButton:hover { background: #e7effa; }
            QPushButton:disabled { color: #95a0b0; }
            QPushButton#primary { background: #205dd8; color: white; border: none; font-weight: 600; }
            QPushButton#primary:disabled { background: #90a8d7; }
            QListWidget, QPlainTextEdit, QLineEdit, QComboBox { background: white; border: 1px solid #d7e0ec; border-radius: 6px; padding: 7px; }
            QProgressBar { border: none; background: #e0e7f1; height: 6px; border-radius: 3px; }
            QProgressBar::chunk { background: #205dd8; }
        """)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        title = QLabel('PDF → AI  ·  v3')
        title.setStyleSheet("font: bold 26pt 'Segoe UI'; color: #0f2d59;")
        top_row.addWidget(title)
        top_row.addStretch()

        self.btn_license = QPushButton('🔑 Kiểm tra BẢN QUYỀN')
        self.btn_license.clicked.connect(self.show_license_info)
        top_row.addWidget(self.btn_license)
        layout.addLayout(top_row)

        desc = QLabel('Tác giả: <b>Nguyễn Bảo Tú (23HG)</b>  ·  OCR tiếng Việt có dấu, bảng số liệu theo đường kẻ ô, khung tên bản vẽ. Kéo & thả PDF / Word / Excel vào cửa sổ.')
        desc.setTextFormat(Qt.RichText)
        layout.addWidget(desc)
        row = QHBoxLayout()
        self.add = QPushButton('+ Chọn file (PDF/Word/Excel)')
        self.add.clicked.connect(self.choose)
        self.add_dir = QPushButton('📁 Chọn Thư mục (Batch)')
        self.add_dir.clicked.connect(self.choose_folder)
        self.remove = QPushButton('Xóa danh sách')
        self.remove.clicked.connect(self.clear)
        row.addWidget(self.add)
        row.addWidget(self.add_dir)
        row.addWidget(self.remove)
        row.addStretch()
        self.count = QLabel('Chưa chọn file (hoặc kéo thả PDF/Word/Excel/Thư mục vào đây)')
        row.addWidget(self.count)
        layout.addLayout(row)
        self.listbox = QListWidget()
        self.listbox.setMaximumHeight(110)
        layout.addWidget(self.listbox)
        row = QHBoxLayout()
        row.addWidget(QLabel('Cách đọc'))
        self.mode = QComboBox()
        self.mode.addItems([m[1] for m in MODES])
        row.addWidget(self.mode, 1)
        row.addWidget(QLabel('Mật khẩu PDF (nếu có)'))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setMaximumWidth(180)
        row.addWidget(self.password)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel('Lưu tại'))
        self.out = QLineEdit(str(Path.home() / 'Documents' / 'PDF_AI_KetQua'))
        row.addWidget(self.out, 1)
        self.folder = QPushButton('Chọn thư mục')
        self.folder.clicked.connect(self.output)
        row.addWidget(self.folder)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel('Trang cần đọc'))
        self.pages = QLineEdit()
        self.pages.setPlaceholderText('Dể trống = tất cả; ví dụ 1-3,5')
        row.addWidget(self.pages, 1)
        layout.addLayout(row)
        layout.addWidget(QLabel('Xuất: Markdown • Bảng số liệu JSON + Excel (.xlsx) • Khung tên • Chia đoạn cho RAG • Danh sách cần đối chiếu • 🔍 Đối chiếu trực quan với bản vẽ gốc'))
        row = QHBoxLayout()
        self.run = QPushButton('Chuyển đổi cho AI')
        self.run.setObjectName('primary')
        self.run.clicked.connect(self.start)
        self.stop = QPushButton('Dừng')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.cancel.set)
        row.addWidget(self.run)
        row.addWidget(self.stop)
        row.addStretch()
        copy = QPushButton('Sao chép nội dung')
        copy.clicked.connect(self.copy)
        row.addWidget(copy)
        open_button = QPushButton('Mở kết quả')
        open_button.clicked.connect(self.open_result)
        row.addWidget(open_button)
        self.inspect_button = QPushButton('🔍 Đối chiếu trực quan')
        self.inspect_button.setToolTip('Mở bản vẽ gốc song song với bảng số liệu: bấm vào ô/dòng để khoanh đỏ đúng vị trí trên bản vẽ')
        self.inspect_button.setStyleSheet(
            "QPushButton { background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; font-weight: 600; } "
            "QPushButton:hover { background: #ffedd5; }"
        )
        self.inspect_button.clicked.connect(self.open_inspector)
        row.addWidget(self.inspect_button)
        self.chat_button = QPushButton('🤖 Trợ lý AI (RAG)')
        self.chat_button.setToolTip('Hỏi đáp thông minh 100% offline với hồ sơ thiết kế, bản vẽ và dự toán vừa chuyển đổi')
        self.chat_button.setStyleSheet(
            "QPushButton { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; font-weight: 600; } "
            "QPushButton:hover { background: #dbeafe; }"
        )
        self.chat_button.clicked.connect(self.open_chat)
        row.addWidget(self.chat_button)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        _gpu = detect_nvidia_gpu()
        # Không có GPU NVIDIA thì Surya rất chậm -> mặc định chế độ OCR nhanh
        self.mode.setCurrentIndex(0 if _gpu else 1)
        self.status = QLabel(
            f'PDF AI v3 | {"GPU: " + _gpu if _gpu else "Không có GPU NVIDIA"} | '
            'Tiếng Việt có dấu ~15–40s/trang (GPU) | OCR nhanh ~5–8s/trang | Bản gõ ~0.3s/trang'
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(
            'Chọn file PDF, Word (.docx) hoặc Excel (.xlsx), chọn cách đọc rồi bấm Chuyển đổi cho AI. Chạy 100% offline.\n\n'
            '[Khuyến dùng] OCR tiếng Việt có dấu (~15–40s/trang, cần GPU NVIDIA):\n'
            '  Bản vẽ scan, hồ sơ thiết kế: giữ dấu tiếng Việt, dựng bảng theo đường kẻ ô,\n'
            '  tách khung tên (số hiệu, tên bản vẽ, tỷ lệ), dấu thẩm định, ghi chú kích thước.\n'
            '  Chữ số được kiểm tra chéo giữa 2 bộ OCR; chỗ lệch đánh dấu ⟦OCR khác: ...⟧.\n\n'
            '[Nhanh] Quét OCR không dấu (~5–8s/trang): như trên nhưng không đọc dấu tiếng Việt.\n\n'
            '[Siêu nhanh] Đọc chữ bản gõ PDF (~0.3s/trang): PDF xuất từ Word/Excel/AutoCAD,\n'
            '  vẫn dựng bảng và khung tên; tự chuyển font cũ TCVN3 (.VnTime) và VNI (VNI-Times).\n'
            '  Chữ font SHX của AutoCAD: đọc chú thích "AutoCAD SHX Text" nếu có; nếu SHX bị vẽ\n'
            '  thành nét thì tự OCR bổ sung (~7s/trang, không dấu — cần dấu hãy dùng chế độ tiếng Việt).\n\n'
            'Kết quả: noi_dung.md • bang_so_lieu.json • bang_so_lieu.xlsx • du_lieu.json • chia_doan.jsonl • can_kiem_tra.md'
        )
        layout.addWidget(self.preview, 1)
        # ── LICENSE CHECK & BADGE ──────────────────────────────────────
        self.refresh_license_badge()
        ok, machine_id = verify_license()
        if not ok:
            dlg = LicenseDialog(machine_id, self)
            if dlg.exec() != LicenseDialog.Accepted:
                sys.exit(0)
            self.refresh_license_badge()
        # ───────────────────────────────────────────────────────────────
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)

    def refresh_license_badge(self):
        from license_core import get_license_status
        st = get_license_status()
        status = st.get("status", "EXPIRED")
        plan = st.get("plan", "LIFETIME")
        days_left = st.get("days_left", 0)

        if status == "ACTIVE":
            if plan == "LIFETIME":
                self.btn_license.setText("👑 Bản quyền: [VĨNH VIỄN 150 NĂM]")
                self.btn_license.setStyleSheet(
                    "QPushButton { background: #eff6ff; color: #1e3a8a; border: 1.5px solid #93c5fd; "
                    "font-weight: 700; padding: 7px 16px; border-radius: 6px; font-size: 10.5pt; } "
                    "QPushButton:hover { background: #dbeafe; color: #172554; }"
                )
            elif plan == "1_YEAR":
                self.btn_license.setText(f"⭐ Bản quyền 1 Năm: [CÒN {days_left} NGÀY]")
                self.btn_license.setStyleSheet(
                    "QPushButton { background: #ecfdf5; color: #065f46; border: 1.5px solid #a7f3d0; "
                    "font-weight: 700; padding: 7px 16px; border-radius: 6px; font-size: 10.5pt; } "
                    "QPushButton:hover { background: #d1fae5; color: #064e3b; }"
                )
            else:
                self.btn_license.setText(f"🔑 Bản quyền: [CÒN {days_left} NGÀY]")
                self.btn_license.setStyleSheet(
                    "QPushButton { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; "
                    "font-weight: 600; padding: 7px 16px; border-radius: 6px; font-size: 10.5pt; } "
                    "QPushButton:hover { background: #d1fae5; color: #064e3b; }"
                )
        elif status == "TRIAL":
            self.btn_license.setText(f"🎁 Dùng thử: [CÒN {days_left} NGÀY] — Kích hoạt")
            self.btn_license.setStyleSheet(
                "QPushButton { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; "
                "font-weight: 600; padding: 7px 16px; border-radius: 6px; font-size: 10.5pt; } "
                "QPushButton:hover { background: #fef3c7; color: #78350f; }"
            )
        else:
            self.btn_license.setText("🔒 HẾT HẠN BẢN QUYỀN — Nhập key")
            self.btn_license.setStyleSheet(
                "QPushButton { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; "
                "font-weight: 600; padding: 7px 16px; border-radius: 6px; font-size: 10.5pt; } "
                "QPushButton:hover { background: #fee2e2; color: #7f1d1d; }"
            )

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
        files, _ = QFileDialog.getOpenFileNames(self, 'Chọn file', '', 'Hồ sơ (*.pdf *.docx *.xlsx *.xlsm);;PDF (*.pdf);;Word (*.docx);;Excel (*.xlsx *.xlsm)')
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
        try:
            from chat_window import ChatWindow
        except Exception as exc:
            QMessageBox.warning(self, 'Trợ lý AI', f'Không khởi động được Trợ lý AI:\n{type(exc).__name__}: {exc}')
            return
        if self.chat_win is None:
            self.chat_win = ChatWindow(self, inspector_window=self.inspector)
        else:
            self.chat_win.inspector_window = self.inspector

        if self.history:
            folder, source, password = self.history[-1]
            if self.chat_win.current_folder != folder:
                self.chat_win.load_project(str(folder))
        elif self.chat_win.current_folder is None:
            if self.result_dir and Path(self.result_dir).exists():
                self.chat_win.load_project(str(self.result_dir))
            else:
                self.chat_win.choose_folder()

        self.chat_win.show()
        self.chat_win.raise_()
        self.chat_win.activateWindow()

    def show_license_info(self):
        ok, machine_id = verify_license()
        dlg = LicenseDialog(machine_id, self)
        dlg.exec()
        self.refresh_license_badge()

    def closeEvent(self, event):
        if self.busy:
            self.cancel.set()
            self.status.setText('Đang dừng. Đóng cửa sổ khi xử lý trang hiện tại kết thúc.')
            event.ignore()
        else:
            event.accept()

    def start(self):
        ok, machine_id = verify_license()
        if not ok:
            QMessageBox.warning(self, "Hết hạn bản quyền", "Thời hạn dùng thử miễn phí đã hết hoặc máy chưa được kích hoạt.\nVui lòng kích hoạt bản quyền để tiếp tục.")
            self.show_license_info()
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
                elif event[0] == 'done':
                    self.busy = False
                    self.progress.setRange(0, 100)
                    for control in [self.run, self.add, self.add_dir, self.remove, self.out, self.folder, self.mode, self.password, self.pages]:
                        control.setEnabled(True)
                    self.stop.setEnabled(False)
                    self.password.clear()
                    label = 'Đã dừng' if event[4] else 'Hoàn tất'
                    self.status.setText(f'{label} • {event[1]} file đã xuất • {len(event[2])} lỗi • {len(event[3])} file cần kiểm tra'
                                        + (' • Bấm 🔍 Đối chiếu hoặc 🤖 Trợ lý AI để tra cứu' if event[1] else ''))
                    if event[2] or event[3]:
                        QMessageBox.warning(self, 'Kết quả chuyển đổi', '\n'.join(event[2]+event[3])[:5000])
        except queue.Empty:
            pass


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
            window.open_chat()

    if '--self-test' in sys.argv:
        import time
        t0 = time.time()
        while time.time() - t0 < (1.5 if (inspect_dir or chat_dir) else 0.1):
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
        if window.chat_win:
            window.chat_win.close()
        window.close()
    else:
        sys.exit(app.exec())
