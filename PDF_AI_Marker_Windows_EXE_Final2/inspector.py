"""Trình Đối chiếu trực quan (Visual Inspector) — PDF AI Marker v3.

Màn hình chia đôi:
  • Trái : trang PDF gốc (Ctrl + lăn chuột để phóng to, kéo để di chuyển).
  • Phải : Bảng số liệu | Cần đối chiếu | Khung tên.
Click (hoặc dùng phím mũi tên) trên một ô số liệu -> tự chuyển đúng trang, phóng
to và vẽ KHUNG ĐỎ đúng vị trí con số đó trên bản vẽ gốc.

Hệ tọa độ trong du_lieu.json ("base"): điểm PDF × scale (base_scale), gốc trên-trái,
có thể đã xoay rot×90° ngược chiều kim đồng hồ (bản vẽ in dọc giấy). Mỗi trang có
"geom" = {pw, ph, scale, rot}; kết quả cũ không có geom thì suy ra từ chính PDF.
"""
from pathlib import Path
import json
import re

from PySide6.QtCore import Qt, QRectF, QSize, QTimer
from PySide6.QtGui import (QColor, QPen, QBrush, QPixmap, QTransform, QImage, QPainter,
                           QKeySequence, QShortcut)
from PySide6.QtWidgets import (QMainWindow, QWidget, QSplitter, QGraphicsView, QGraphicsScene,
                               QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
                               QTabWidget, QTableWidget, QTableWidgetItem, QListWidget,
                               QListWidgetItem, QCheckBox, QFileDialog, QInputDialog, QLineEdit,
                               QMessageBox, QHeaderView, QAbstractItemView, QApplication)
from PySide6.QtPdf import QPdfDocument

MAX_RENDER_SIDE = 4200          # cạnh dài tối đa của ảnh trang (px) — đủ nét để đọc số trên bản vẽ A1
MAX_PX_PER_PT = 200 / 72.0      # không render quá 200 DPI (trang A4)
MAX_CACHE = 4

META_LABELS = {
    "so_hieu_ban_ve": "Số hiệu bản vẽ", "ten_ban_ve": "Tên bản vẽ", "ty_le": "Tỷ lệ",
    "ngay": "Ngày", "hang_muc": "Hạng mục", "cong_trinh": "Công trình", "du_an": "Dự án",
    "giai_doan": "Giai đoạn", "don_vi_thiet_ke": "Đơn vị thiết kế",
}


def base_scale(pw: float, ph: float) -> float:
    """Giống ocr_tiling.base_scale (hệ tọa độ mà layout_reconstructor dùng)."""
    return min(1.5, max(1.0, 1600.0 / max(1.0, pw, ph)))


def _pen(color, width, style=Qt.SolidLine):
    p = QPen(QColor(*color), width, style)
    p.setCosmetic(True)               # độ dày không đổi khi phóng to
    return p


STYLES = {
    "table": (_pen((37, 99, 235), 1.6, Qt.DashLine), QBrush(QColor(37, 99, 235, 18)), 2),
    "low": (_pen((234, 88, 12), 1.4), QBrush(QColor(234, 88, 12, 45)), 3),
    "sel_table": (_pen((37, 99, 235), 3.0), QBrush(QColor(37, 99, 235, 30)), 5),
    "focus": (_pen((220, 38, 38), 3.2), QBrush(QColor(220, 38, 38, 55)), 10),
    "halo": (_pen((220, 38, 38), 1.6, Qt.DashLine), QBrush(Qt.NoBrush), 9),
}


# ─────────────────────────────────────────────────────────────────────────────
# Khung xem trang PDF
# ─────────────────────────────────────────────────────────────────────────────
class PageView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#4b5563"))
        self.setStyleSheet("QGraphicsView { border: none; background: #4b5563; }")
        self._pix = None
        self._items = {}               # kind -> [QGraphicsItem]
        self.on_zoom = None
        self._blink_left = 0
        self._blink = QTimer(self)
        self._blink.setInterval(220)
        self._blink.timeout.connect(self._blink_step)

    # ── nội dung ─────────────────────────────────────────────────────────
    def set_image(self, img: QImage):
        self._blink.stop()
        self.scene().clear()
        self._items = {}
        self._pix = self.scene().addPixmap(QPixmap.fromImage(img))
        self._pix.setTransformationMode(Qt.SmoothTransformation)
        self._pix.setZValue(0)
        r = self._pix.boundingRect()
        self.scene().setSceneRect(r.adjusted(-60, -60, 60, 60))

    def show_message(self, text: str):
        self._blink.stop()
        self.scene().clear()
        self._items = {}
        self._pix = None
        t = self.scene().addText(text)
        t.setDefaultTextColor(QColor("white"))
        f = t.font()
        f.setPointSize(13)
        t.setFont(f)
        t.setTextWidth(520)
        self.scene().setSceneRect(t.boundingRect().adjusted(-40, -40, 40, 40))
        self.resetTransform()
        self.centerOn(t)
        self._notify()

    def has_page(self) -> bool:
        return self._pix is not None

    def add_box(self, rect: QRectF, kind: str, tip: str = ""):
        pen, brush, z = STYLES[kind]
        it = self.scene().addRect(rect, pen, brush)
        it.setZValue(z)
        if tip:
            it.setToolTip(tip)
        self._items.setdefault(kind, []).append(it)
        return it

    def clear_kinds(self, *kinds):
        for k in kinds:
            for it in self._items.pop(k, []):
                self.scene().removeItem(it)

    def set_focus_box(self, rect: QRectF, tip: str = ""):
        self.clear_kinds("focus", "halo")
        pad = max(4.0, min(rect.width(), rect.height()) * 0.25)
        self.add_box(rect.adjusted(-pad, -pad, pad, pad), "halo")
        self.add_box(rect, "focus", tip)
        self.focus_rect(rect)
        self._blink_left = 6
        self._blink.start()

    def _blink_step(self):
        self._blink_left -= 1
        for it in self._items.get("halo", []):
            it.setVisible(self._blink_left % 2 == 0)
        if self._blink_left <= 0:
            self._blink.stop()
            for it in self._items.get("halo", []):
                it.setVisible(True)

    # ── phóng to / thu nhỏ ───────────────────────────────────────────────
    def current_scale(self) -> float:
        return self.transform().m11()

    def _fit_scale(self) -> float:
        if not self._pix:
            return 1.0
        r = self._pix.boundingRect()
        vw, vh = max(1, self.viewport().width() - 16), max(1, self.viewport().height() - 16)
        return min(vw / max(1.0, r.width()), vh / max(1.0, r.height()))

    def set_scale(self, s: float):
        s = max(0.03, min(8.0, s))
        self.setTransform(QTransform.fromScale(s, s))
        self._notify()

    def zoom_by(self, f: float):
        self.set_scale(self.current_scale() * f)

    def fit_page(self):
        if self._pix:
            self.set_scale(self._fit_scale())
            self.centerOn(self._pix.boundingRect().center())

    def fit_width(self):
        if self._pix:
            r = self._pix.boundingRect()
            self.set_scale(max(1, self.viewport().width() - 24) / max(1.0, r.width()))
            self.centerOn(r.center().x(), r.top())

    def focus_rect(self, rect: QRectF):
        """Phóng to vừa đủ để thấy vùng được chọn kèm ngữ cảnh xung quanh."""
        vw, vh = max(1, self.viewport().width()), max(1, self.viewport().height())
        page = self._pix.boundingRect() if self._pix else rect
        # vùng chọn chiếm ~1/6 khung nhìn, nhưng luôn thấy ≥45% bề ngang / ≥30% chiều cao trang
        tw = max(rect.width() * 6 + 120, page.width() * 0.45)
        th = max(rect.height() * 8 + 120, page.height() * 0.30)
        s = min(vw / max(1.0, tw), vh / max(1.0, th))
        fit = self._fit_scale()
        s = max(min(s, 2.5), min(fit, 2.5))
        self.set_scale(s)
        self.centerOn(rect.center())

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.zoom_by(1.2 if e.angleDelta().y() > 0 else 1 / 1.2)
            e.accept()
        else:
            super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._notify()

    def _notify(self):
        if self.on_zoom:
            self.on_zoom(self.current_scale())


# ─────────────────────────────────────────────────────────────────────────────
# Cửa sổ đối chiếu
# ─────────────────────────────────────────────────────────────────────────────
class InspectorWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.Window, True)
        self.setWindowTitle("🔍 Đối chiếu trực quan — PDF AI Marker v3")
        self.resize(1560, 940)
        self.data = {}
        self.result_dir = None
        self.pages = []
        self.page_pos = -1
        self.pdf = QPdfDocument(self)
        self.pdf_ok = False
        self.pdf_note = ""
        self.source_pdf = None
        self._cache = {}                 # page_no -> (QImage, px_per_pt)
        self.tables = []                 # [(page_pos, table)]
        self.cur_table = None
        self._build_ui()

    # ── giao diện ────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f3f6fb; color: #19324e; font: 10pt 'Segoe UI'; }
            QPushButton { background: white; border: 1px solid #d7e0ec; border-radius: 6px; padding: 6px 11px; }
            QPushButton:hover { background: #e7effa; }
            QComboBox, QListWidget, QTableWidget { background: white; border: 1px solid #d7e0ec; border-radius: 5px; }
            QComboBox { padding: 5px 8px; }
            QTabWidget::pane { border: 1px solid #d7e0ec; border-radius: 6px; background: white; }
            QTabBar::tab { padding: 8px 14px; background: #e6ecf5; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; }
            QTabBar::tab:selected { background: white; font-weight: 600; color: #1d4ed8; }
            QHeaderView::section { background: #2f5597; color: white; padding: 5px; border: none; border-right: 1px solid #4a6fb0; font-weight: 600; }
            QTableWidget { gridline-color: #e2e8f0; selection-background-color: #fee2e2; selection-color: #7f1d1d; }
            QListWidget::item { padding: 5px; border-bottom: 1px solid #eef2f7; }
            QListWidget::item:selected { background: #fee2e2; color: #7f1d1d; }
        """)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 8, 10, 6)
        root.setSpacing(6)

        bar = QHBoxLayout()
        b = QPushButton("📂 Mở kết quả…")
        b.setToolTip("Chọn thư mục kết quả (*_Marker) có file du_lieu.json")
        b.clicked.connect(self.choose_result)
        bar.addWidget(b)
        self.btn_pdf = QPushButton("📄 Chọn PDF gốc…")
        self.btn_pdf.clicked.connect(self.choose_pdf)
        bar.addWidget(self.btn_pdf)
        self.lbl_file = QLabel("Chưa mở kết quả")
        self.lbl_file.setStyleSheet("font-weight: 600; color: #0f2d59; padding-left: 8px;")
        bar.addWidget(self.lbl_file, 1)
        bar.addWidget(QLabel("Trang"))
        self.btn_prev = QPushButton("◀")
        self.btn_prev.clicked.connect(lambda: self.step_page(-1))
        bar.addWidget(self.btn_prev)
        self.cb_page = QComboBox()
        self.cb_page.setMinimumWidth(300)
        self.cb_page.currentIndexChanged.connect(self._on_page_combo)
        bar.addWidget(self.cb_page)
        self.btn_next = QPushButton("▶")
        self.btn_next.clicked.connect(lambda: self.step_page(1))
        bar.addWidget(self.btn_next)
        bar.addSpacing(10)
        for text, tip, fn in (("−", "Thu nhỏ (Ctrl −)", lambda: self.view.zoom_by(1 / 1.25)),
                              ("+", "Phóng to (Ctrl +)", lambda: self.view.zoom_by(1.25))):
            zb = QPushButton(text)
            zb.setToolTip(tip)
            zb.setFixedWidth(34)
            zb.clicked.connect(fn)
            bar.addWidget(zb)
        self.lbl_zoom = QLabel("—")
        self.lbl_zoom.setMinimumWidth(52)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        bar.insertWidget(bar.count() - 1, self.lbl_zoom)
        fb = QPushButton("⤢ Vừa trang")
        fb.setToolTip("Ctrl 0")
        fb.clicked.connect(lambda: self.view.fit_page())
        bar.addWidget(fb)
        wb = QPushButton("↔ Vừa ngang")
        wb.clicked.connect(lambda: self.view.fit_width())
        bar.addWidget(wb)
        bar.addSpacing(8)
        self.chk_tables = QCheckBox("Khung bảng")
        self.chk_tables.setChecked(True)
        self.chk_tables.toggled.connect(self._redraw_overlays)
        bar.addWidget(self.chk_tables)
        self.chk_low = QCheckBox("Chữ cần kiểm tra")
        self.chk_low.setChecked(True)
        self.chk_low.toggled.connect(self._redraw_overlays)
        bar.addWidget(self.chk_low)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        self.view = PageView()
        self.view.on_zoom = self._on_zoom
        split.addWidget(self.view)

        self.tabs = QTabWidget()
        # Tab 1: Bảng số liệu
        tw = QWidget()
        tl = QVBoxLayout(tw)
        tl.setContentsMargins(8, 8, 8, 8)
        self.cb_table = QComboBox()
        self.cb_table.currentIndexChanged.connect(self._on_table_combo)
        tl.addWidget(self.cb_table)
        self.lbl_table = QLabel("")
        self.lbl_table.setWordWrap(True)
        self.lbl_table.setStyleSheet("color: #475569;")
        tl.addWidget(self.lbl_table)
        self.tbl = QTableWidget()
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.tbl.setWordWrap(True)
        self.tbl.horizontalHeader().setDefaultAlignment(Qt.AlignCenter | Qt.TextWordWrap)
        self.tbl.currentCellChanged.connect(lambda r, c, *_: self._on_cell(r, c))
        self.tbl.cellClicked.connect(self._on_cell)
        tl.addWidget(self.tbl, 1)
        hint = QLabel("💡 Click vào ô bất kỳ (hoặc dùng phím ↑ ↓ ← →) → khung đỏ hiện đúng vị trí trên bản gốc.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #b45309; background: #fffbeb; border: 1px solid #fde68a; border-radius: 5px; padding: 6px;")
        tl.addWidget(hint)
        self.tabs.addTab(tw, "📊 Bảng số liệu")

        # Tab 2: Cần đối chiếu
        lw = QWidget()
        ll = QVBoxLayout(lw)
        ll.setContentsMargins(8, 8, 8, 8)
        self.chk_digits = QCheckBox("Chỉ hiện mục có chữ số (ưu tiên kiểm tra)")
        self.chk_digits.setChecked(True)
        self.chk_digits.toggled.connect(self._fill_low_list)
        ll.addWidget(self.chk_digits)
        self.lst_low = QListWidget()
        self.lst_low.currentRowChanged.connect(self._on_low)
        self.lst_low.itemClicked.connect(lambda it: self._on_low(self.lst_low.row(it)))
        ll.addWidget(self.lst_low, 1)
        lh = QLabel("Chữ/số OCR độ tin cậy thấp hoặc hai bộ OCR đọc khác nhau ⟦OCR khác: …⟧. "
                    "Click để xem tận nơi trên bản vẽ.")
        lh.setWordWrap(True)
        lh.setStyleSheet("color: #475569;")
        ll.addWidget(lh)
        self.tabs.addTab(lw, "⚠️ Cần đối chiếu")

        # Tab 3: Khung tên
        mw = QWidget()
        ml = QVBoxLayout(mw)
        ml.setContentsMargins(8, 8, 8, 8)
        self.tbl_meta = QTableWidget(0, 2)
        self.tbl_meta.setHorizontalHeaderLabels(["Trường", "Giá trị"])
        self.tbl_meta.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_meta.verticalHeader().setVisible(False)
        self.tbl_meta.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_meta.setWordWrap(True)
        ml.addWidget(self.tbl_meta, 1)
        self.tabs.addTab(mw, "📑 Khung tên")

        split.addWidget(self.tabs)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([920, 620])
        root.addWidget(split, 1)
        self.statusBar().showMessage("Ctrl + lăn chuột: phóng to/thu nhỏ • Kéo chuột: di chuyển • PageUp/PageDown: đổi trang")

        for seq, fn in (("Ctrl++", lambda: self.view.zoom_by(1.25)), ("Ctrl+=", lambda: self.view.zoom_by(1.25)),
                        ("Ctrl+-", lambda: self.view.zoom_by(1 / 1.25)), ("Ctrl+0", lambda: self.view.fit_page()),
                        ("PgDown", lambda: self.step_page(1)), ("PgUp", lambda: self.step_page(-1))):
            QShortcut(QKeySequence(seq), self, activated=fn)

    # ── nạp dữ liệu ──────────────────────────────────────────────────────
    def choose_result(self):
        start = str(self.result_dir.parent) if self.result_dir else str(Path.home() / "Documents" / "PDF_AI_KetQua")
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục kết quả (*_Marker)", start)
        if folder:
            self.load_result(folder)

    def load_result(self, folder, source_path=None, password=""):
        folder = Path(folder)
        f = folder / "du_lieu.json"
        if not f.exists():
            QMessageBox.warning(self, "Không có dữ liệu",
                                f"Thư mục này không có du_lieu.json:\n{folder}\n\n"
                                "Hãy chọn thư mục kết quả dạng <tên file>_Marker.")
            return False
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            QMessageBox.warning(self, "Lỗi đọc dữ liệu", f"{type(e).__name__}: {e}")
            return False
        self.data = data
        self.result_dir = folder
        self.pages = [p for p in data.get("pages", []) if isinstance(p, dict) and p.get("page")]
        self._cache.clear()
        self.lbl_file.setText(f"{data.get('source', folder.name)}  •  {len(self.pages)} trang  •  {folder.name}")
        self._open_pdf(source_path or data.get("source_path") or "", password)

        # danh sách bảng
        self.tables = [(i, t) for i, p in enumerate(self.pages) for t in (p.get("tables") or [])]
        self.cb_table.blockSignals(True)
        self.cb_table.clear()
        for i, t in self.tables:
            nrow = len(t.get("rows") or [])
            ncol = max([len(t.get("header") or [])] + [len(r) for r in (t.get("rows") or [])])
            mark = "📍" if t.get("cell_boxes") else ("▭" if t.get("bbox") else "·")
            self.cb_table.addItem(f"{mark} Tr.{self.pages[i]['page']} • {t.get('title') or 'Bảng'}  ({nrow}×{ncol})")
        self.cb_table.blockSignals(False)
        self.tabs.setTabText(0, f"📊 Bảng số liệu ({len(self.tables)})")

        # trang
        self.cb_page.blockSignals(True)
        self.cb_page.clear()
        for p in self.pages:
            meta = p.get("metadata") or {}
            nt, nl = len(p.get("tables") or []), len(p.get("low_confidence") or [])
            label = f"Trang {p['page']}"
            if meta.get("so_hieu_ban_ve"):
                label += f" — {meta['so_hieu_ban_ve']}"
            label += f"   [{nt} bảng • {nl} cần KT]"
            self.cb_page.addItem(label)
        self.cb_page.blockSignals(False)
        self._fill_low_list()

        self.page_pos = -1
        if self.pages:
            self.show_page(0)
        else:
            self.view.show_message("Kết quả này không có dữ liệu theo trang.")
        if self.tables:
            self.cb_table.setCurrentIndex(0)
            self._on_table_combo(0, focus=False)
        else:
            self.tbl.clear()
            self.tbl.setRowCount(0)
            self.tbl.setColumnCount(0)
            self.lbl_table.setText("Không phát hiện bảng số liệu trong tài liệu này.")
        self.show()
        self.raise_()
        self.activateWindow()
        return True

    def _open_pdf(self, src, password=""):
        self.pdf.close()
        self.pdf_ok = False
        self.pdf_note = ""
        self.source_pdf = None
        p = Path(src) if src else None
        if (not p or not p.exists()) and self.result_dir and self.data.get("source"):
            for cand in (self.result_dir.parent / self.data["source"], self.result_dir / self.data["source"]):
                if cand.exists():
                    p = cand
                    break
        if not p or not p.exists():
            self.pdf_note = ("Không tìm thấy file gốc"
                             + (f":\n{src}" if src else "") +
                             "\n\nBấm “📄 Chọn PDF gốc…” để chỉ định file PDF.")
            return
        if p.suffix.lower() != ".pdf":
            self.pdf_note = (f"Tài liệu gốc là {p.suffix.upper()[1:]} (Word/Excel) — không có trang PDF để hiển thị.\n\n"
                             "Bảng số liệu vẫn xem được ở khung bên phải.")
            return
        self.pdf.setPassword(password or "")
        err = self.pdf.load(str(p))
        tries = 0
        while err == QPdfDocument.Error.IncorrectPassword and tries < 3:
            pwd, ok = QInputDialog.getText(self, "PDF có mật khẩu", f"Nhập mật khẩu để mở:\n{p.name}",
                                           QLineEdit.Password)
            if not ok:
                break
            self.pdf.close()
            self.pdf.setPassword(pwd)
            err = self.pdf.load(str(p))
            tries += 1
        if err != QPdfDocument.Error.None_:
            self.pdf_note = f"Không mở được PDF gốc ({err.name}):\n{p}"
            return
        self.pdf_ok = True
        self.source_pdf = p

    def choose_pdf(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file PDF gốc", str(self.result_dir or ""), "PDF (*.pdf)")
        if f:
            self._cache.clear()
            self._open_pdf(f)
            if self.page_pos >= 0:
                self.show_page(self.page_pos, force=True)

    # ── trang ────────────────────────────────────────────────────────────
    def _geom(self, rec):
        g = rec.get("geom")
        if g and g.get("pw") and g.get("ph"):
            return {"pw": float(g["pw"]), "ph": float(g["ph"]),
                    "scale": float(g.get("scale") or base_scale(g["pw"], g["ph"])),
                    "rot": int(g.get("rot") or 0) % 4}
        sz = self.pdf.pagePointSize(rec["page"] - 1)
        pw, ph = float(sz.width()) or 595.0, float(sz.height()) or 842.0
        return {"pw": pw, "ph": ph, "scale": base_scale(pw, ph), "rot": 0}

    def _render(self, rec):
        pno = rec["page"]
        if pno in self._cache:
            return self._cache[pno]
        idx = pno - 1
        if not self.pdf_ok or not (0 <= idx < self.pdf.pageCount()):
            return None
        g = self._geom(rec)
        z = max(0.5, min(MAX_PX_PER_PT, MAX_RENDER_SIDE / max(g["pw"], g["ph"])))
        size = QSize(max(1, round(g["pw"] * z)), max(1, round(g["ph"] * z)))
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            raw = self.pdf.render(idx, size)
            img = QImage(raw.size(), QImage.Format_RGB32)
            img.fill(QColor("white"))
            painter = QPainter(img)
            painter.drawImage(0, 0, raw)
            painter.end()
            if g["rot"]:
                # Khớp PIL image.rotate(90*k) (ngược chiều kim đồng hồ) dùng khi phân tích
                img = img.transformed(QTransform().rotate({1: -90, 2: 180, 3: 90}[g["rot"]]))
        finally:
            QApplication.restoreOverrideCursor()
        if len(self._cache) >= MAX_CACHE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[pno] = (img, z)
        return self._cache[pno]

    def _to_scene(self, rec, bbox) -> QRectF:
        cached = self._cache.get(rec["page"])
        if not cached or not bbox:
            return QRectF()
        _, z = cached
        f = z / self._geom(rec)["scale"]
        x0, y0, x1, y1 = [float(v) for v in bbox[:4]]
        return QRectF(x0 * f, y0 * f, (x1 - x0) * f, (y1 - y0) * f).normalized()

    def show_page(self, pos, force=False, fit=True):
        if not (0 <= pos < len(self.pages)):
            return
        if pos == self.page_pos and not force:
            return
        self.page_pos = pos
        rec = self.pages[pos]
        self.cb_page.blockSignals(True)
        self.cb_page.setCurrentIndex(pos)
        self.cb_page.blockSignals(False)
        self.btn_prev.setEnabled(pos > 0)
        self.btn_next.setEnabled(pos < len(self.pages) - 1)
        self._fill_meta(rec)
        r = self._render(rec)
        if r is None:
            self.view.show_message(self.pdf_note or "Không hiển thị được trang này.")
            return
        self.view.set_image(r[0])
        self._redraw_overlays()
        if fit:
            QTimer.singleShot(0, self.view.fit_page)

    def step_page(self, d):
        if self.pages:
            self.show_page(max(0, min(len(self.pages) - 1, self.page_pos + d)))

    def _on_page_combo(self, i):
        self.show_page(i)

    def _redraw_overlays(self):
        if not self.view.has_page() or self.page_pos < 0:
            return
        rec = self.pages[self.page_pos]
        self.view.clear_kinds("table", "low")
        if self.chk_tables.isChecked():
            for t in rec.get("tables") or []:
                if t.get("bbox"):
                    self.view.add_box(self._to_scene(rec, t["bbox"]), "table", t.get("title") or "Bảng")
        if self.chk_low.isChecked():
            for x in rec.get("low_confidence") or []:
                if x.get("bbox"):
                    self.view.add_box(self._to_scene(rec, x["bbox"]), "low",
                                      f"{x.get('text', '')}  (điểm {x.get('score', '?')})")

    def _on_zoom(self, s):
        cached = self._cache.get(self.pages[self.page_pos]["page"]) if 0 <= self.page_pos < len(self.pages) else None
        if cached and self.view.has_page():
            # 100% = đúng kích thước giấy trên màn hình 96 DPI
            self.lbl_zoom.setText(f"{round(s * cached[1] * 72 / 96 * 100)}%")
        else:
            self.lbl_zoom.setText("—")

    def _highlight(self, pos, bbox, tip=""):
        if pos != self.page_pos:
            self.show_page(pos, fit=False)
        if not self.view.has_page():
            return False
        rect = self._to_scene(self.pages[pos], bbox)
        if rect.isEmpty():
            return False
        self.view.set_focus_box(rect, tip)
        return True

    # ── bảng số liệu ─────────────────────────────────────────────────────
    def _on_table_combo(self, i, focus=True):
        if not (0 <= i < len(self.tables)):
            return
        pos, t = self.tables[i]
        self.cur_table = (pos, t)
        rows = t.get("rows") or []
        header = list(t.get("header") or [])
        ncol = max([len(header)] + [len(r) for r in rows])
        header += [f"Cột {j + 1}" for j in range(len(header), ncol)]
        header = [h or f"Cột {j + 1}" for j, h in enumerate(header)]
        values = t.get("values") or []
        self.tbl.blockSignals(True)
        self.tbl.clear()
        self.tbl.setRowCount(len(rows))
        self.tbl.setColumnCount(ncol)
        self.tbl.setHorizontalHeaderLabels(header)
        boxes = t.get("cell_boxes") or []
        for r, row in enumerate(rows):
            for c in range(ncol):
                text = row[c] if c < len(row) else ""
                it = QTableWidgetItem(str(text))
                v = values[r][c] if r < len(values) and c < len(values[r]) else None
                if isinstance(v, (int, float)):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                has_box = r < len(boxes) and c < len(boxes[r]) and boxes[r][c]
                if not has_box and text:
                    it.setForeground(QColor("#64748b"))
                if ALT_MARK.search(str(text)):
                    it.setBackground(QColor("#fff7ed"))
                    it.setToolTip("Hai bộ OCR đọc khác nhau — cần đối chiếu bản gốc")
                self.tbl.setItem(r, c, it)
        self.tbl.blockSignals(False)
        self.tbl.resizeColumnsToContents()
        for c in range(ncol):
            if self.tbl.columnWidth(c) > 260:
                self.tbl.setColumnWidth(c, 260)
        self.tbl.resizeRowsToContents()
        rec = self.pages[pos]
        meta = rec.get("metadata") or {}
        info = f"Trang {rec['page']}"
        if meta.get("so_hieu_ban_ve"):
            info += f" • Bản vẽ {meta['so_hieu_ban_ve']}"
        info += f" • {len(rows)} hàng × {ncol} cột • nguồn: {t.get('source', '?')}"
        if not boxes:
            info += " • (bảng này chỉ có tọa độ cả bảng)" if t.get("bbox") else " • (không có tọa độ)"
        self.lbl_table.setText(info)
        if focus:
            self.show_page(pos, fit=False)
            if t.get("bbox") and self.view.has_page():
                self.view.clear_kinds("sel_table", "focus", "halo")
                rect = self._to_scene(rec, t["bbox"])
                self.view.add_box(rect, "sel_table", t.get("title") or "Bảng")
                self.view.focus_rect(rect)
            elif not self.view.has_page():
                pass
            else:
                self.view.fit_page()

    def _on_cell(self, r, c):
        if r < 0 or c < 0 or not self.cur_table:
            return
        pos, t = self.cur_table
        rows = t.get("rows") or []
        if r >= len(rows):
            return
        text = rows[r][c] if c < len(rows[r]) else ""
        boxes = t.get("cell_boxes") or []
        b = boxes[r][c] if r < len(boxes) and c < len(boxes[r]) else None
        hdr = (t.get("header") or [])
        col_name = hdr[c] if c < len(hdr) and hdr[c] else f"Cột {c + 1}"
        values = t.get("values") or []
        v = values[r][c] if r < len(values) and c < len(values[r]) else None
        msg = f"Trang {self.pages[pos]['page']} • Hàng {r + 1} • {col_name}: “{text}”"
        if isinstance(v, (int, float)):
            msg += f"  → giá trị số: {v:g}"
        if b and self._highlight(pos, b, str(text)):
            self.statusBar().showMessage("📍 " + msg)
        elif t.get("bbox") and self.view.has_page() or (t.get("bbox") and pos != self.page_pos):
            self._highlight(pos, t["bbox"], t.get("title") or "Bảng")
            self.statusBar().showMessage(msg + "   (ô trống/ô gộp không có tọa độ riêng — đang chỉ vị trí cả bảng)")
        else:
            self.statusBar().showMessage(msg)

    # ── cần đối chiếu ────────────────────────────────────────────────────
    def _fill_low_list(self):
        self.lst_low.blockSignals(True)
        self.lst_low.clear()
        self._low_index = []
        only_digits = self.chk_digits.isChecked()
        total = 0
        for pos, p in enumerate(self.pages):
            for x in p.get("low_confidence") or []:
                total += 1
                txt = str(x.get("text", ""))
                if only_digits and not re.search(r"\d", txt):
                    continue
                score = x.get("score")
                item = QListWidgetItem(f"Tr.{p['page']}  •  {txt}" + (f"   (điểm {score})" if score is not None else ""))
                if ALT_MARK.search(txt):
                    item.setForeground(QColor("#b91c1c"))
                    item.setToolTip("Hai bộ OCR đọc khác nhau ở chữ số")
                self.lst_low.addItem(item)
                self._low_index.append((pos, x))
        self.lst_low.blockSignals(False)
        self.tabs.setTabText(1, f"⚠️ Cần đối chiếu ({len(self._low_index)}/{total})")

    def _on_low(self, row):
        if not (0 <= row < len(getattr(self, "_low_index", []))):
            return
        pos, x = self._low_index[row]
        if x.get("bbox") and self._highlight(pos, x["bbox"], str(x.get("text", ""))):
            self.statusBar().showMessage(f"📍 Trang {self.pages[pos]['page']} • “{x.get('text', '')}” "
                                         f"(điểm tin cậy {x.get('score', '?')})")
        else:
            self.show_page(pos)

    # ── khung tên ────────────────────────────────────────────────────────
    def _fill_meta(self, rec):
        meta = rec.get("metadata") or {}
        rows = [(META_LABELS.get(k, k), v) for k, v in meta.items() if v not in (None, "", [], {})]
        rows = [("Trang", rec.get("page")), ("Phương pháp đọc", rec.get("method", ""))] + rows
        self.tbl_meta.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.tbl_meta.setItem(i, 0, QTableWidgetItem(str(k)))
            val = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
            self.tbl_meta.setItem(i, 1, QTableWidgetItem(val))
        self.tbl_meta.resizeColumnToContents(0)
        self.tbl_meta.resizeRowsToContents()


ALT_MARK = re.compile("⟦")
