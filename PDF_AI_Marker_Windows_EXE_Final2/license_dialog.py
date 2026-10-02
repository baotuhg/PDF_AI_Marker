"""
Dialog kích hoạt bản quyền — Nâng cấp theo trải nghiệm người dùng của HTTKD.
Tính năng:
  - Tự động copy Machine ID vào Clipboard ngay khi mở dialog (khách chỉ cần ấn Ctrl+V gửi Zalo).
  - Hỗ trợ cả 2 cách kích hoạt: Dán chuỗi Key HOẶC Chọn file license (.lic).
  - Hiển thị danh sách USB đang cắm nếu khách muốn đăng ký khóa cứng USB di động.
"""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QMessageBox, QApplication,
    QFileDialog, QTabWidget, QWidget
)
from license_core import save_license, import_license_file, get_connected_usb_serials


class LicenseDialog(QDialog):
    def __init__(self, machine_id: str, parent=None):
        super().__init__(parent)
        self.machine_id = machine_id
        self.setWindowTitle("PDF AI Marker — Kích hoạt bản quyền")
        self.setMinimumWidth(560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setModal(True)

        # ── TỰ ĐỘNG COPY MACHINE ID VÀO CLIPBOARD (Phong cách HTTKD) ───────────
        try:
            QApplication.clipboard().setText(self.machine_id)
            self.auto_copied = True
        except Exception:
            self.auto_copied = False

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(28, 22, 28, 22)

        # Header
        title = QLabel("🔑  Kích hoạt Bản quyền PDF AI Marker v3")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        layout.addWidget(title)

        # Thông báo trạng thái copy tự động
        copy_notice = QLabel(
            "✅ <b>Đã tự động sao chép Mã máy vào bộ nhớ tạm (Clipboard)!</b><br>"
            "Bạn chỉ cần mở Zalo/Email và ấn <b>Ctrl + V</b> để gửi mã kích hoạt."
        )
        copy_notice.setTextFormat(Qt.RichText)
        copy_notice.setStyleSheet(
            "background: #e8f5e9; color: #1b5e20; border: 1px solid #c8e6c9; "
            "border-radius: 6px; padding: 10px 14px; font-size: 10pt;"
        )
        layout.addWidget(copy_notice)

        # Tabs hiển thị mã phần cứng
        tabs = QTabWidget()
        
        # Tab 1: Máy tính (SSD)
        tab_pc = QWidget()
        l_pc = QVBoxLayout(tab_pc)
        l_pc.setContentsMargins(10, 12, 10, 12)
        l_pc.addWidget(QLabel("<b>Mã máy tính (khóa theo ổ cứng SSD - 1 máy cố định):</b>"))
        mid_row = QHBoxLayout()
        self.mid_edit = QLineEdit(self.machine_id)
        self.mid_edit.setReadOnly(True)
        self.mid_edit.setStyleSheet("background: #f1f5f9; font-family: Consolas; font-size: 10.5pt; padding: 6px;")
        mid_row.addWidget(self.mid_edit)
        copy_btn = QPushButton("📋 Sao chép lại")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.machine_id))
        mid_row.addWidget(copy_btn)
        l_pc.addLayout(mid_row)
        tabs.addTab(tab_pc, "🖥️ Khóa theo Máy (SSD)")

        # Tab 2: USB Dongle (Di động)
        tab_usb = QWidget()
        l_usb = QVBoxLayout(tab_usb)
        l_usb.setContentsMargins(10, 12, 10, 12)
        usbs = get_connected_usb_serials()
        if usbs:
            l_usb.addWidget(QLabel("<b>Mã USB phát hiện (cắm USB vào máy nào thì máy đó chạy được):</b>"))
            usb_row = QHBoxLayout()
            self.usb_edit = QLineEdit(usbs[0])
            self.usb_edit.setReadOnly(True)
            self.usb_edit.setStyleSheet("background: #f1f5f9; font-family: Consolas; font-size: 10.5pt; padding: 6px;")
            usb_row.addWidget(self.usb_edit)
            copy_usb_btn = QPushButton("📋 Sao chép mã USB")
            copy_usb_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.usb_edit.text()))
            usb_row.addWidget(copy_usb_btn)
            l_usb.addLayout(usb_row)
        else:
            l_usb.addWidget(QLabel(
                "<i>Chưa cắm USB. Nếu muốn dùng khóa USB di động (như HTTKD), "
                "hãy cắm USB vào máy tính rồi mở lại phần mềm.</i>"
            ))
        tabs.addTab(tab_usb, "🔌 Khóa theo USB (Nhiều máy)")
        layout.addWidget(tabs)

        # Nhập License Key
        layout.addWidget(QLabel("<b>Nhập License Key hoặc Chọn file license do nhà cung cấp gửi:</b>"))
        self.key_input = QTextEdit()
        self.key_input.setPlaceholderText("Dán chuỗi License Key vào đây...")
        self.key_input.setMaximumHeight(70)
        self.key_input.setStyleSheet("font-family: Consolas; font-size: 10pt;")
        layout.addWidget(self.key_input)

        # Hàng nút thao tác
        act_row = QHBoxLayout()
        paste_btn = QPushButton("📋 Dán từ Clipboard")
        paste_btn.clicked.connect(self._paste_clipboard)
        act_row.addWidget(paste_btn)

        import_file_btn = QPushButton("📁 Chọn file pdf_ai.lic")
        import_file_btn.clicked.connect(self._choose_lic_file)
        act_row.addWidget(import_file_btn)
        act_row.addStretch()

        self.activate_btn = QPushButton("✅ Kích hoạt")
        self.activate_btn.setObjectName("primary")
        self.activate_btn.setStyleSheet(
            "QPushButton { background: #205dd8; color: white; border: none; "
            "border-radius: 6px; padding: 9px 22px; font-weight: 600; font-size: 10.5pt; }"
            "QPushButton:hover { background: #1848b0; }"
        )
        self.activate_btn.clicked.connect(self._activate)
        self.activate_btn.setDefault(True)
        act_row.addWidget(self.activate_btn)

        cancel_btn = QPushButton("Thoát")
        cancel_btn.clicked.connect(self.reject)
        act_row.addWidget(cancel_btn)
        layout.addLayout(act_row)

        # Footer liên hệ
        contact = QLabel(
            "Liên hệ mua bản quyền: <b>baotuhg@gmail.com</b> | Hotline/Zalo: 0986.xxx.xxx"
        )
        contact.setTextFormat(Qt.RichText)
        contact.setStyleSheet("color: #64748b; font-size: 9pt;")
        layout.addWidget(contact)

    def _paste_clipboard(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.key_input.setPlainText(text)

    def _choose_lic_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file License", "", "License Files (*.lic);;All Files (*.*)"
        )
        if file_path:
            if import_license_file(file_path):
                QMessageBox.information(
                    self, "Kích hoạt thành công",
                    "✅ Đã nạp file license hợp lệ!\nCảm ơn bạn đã sử dụng PDF AI Marker v3."
                )
                self.accept()
            else:
                QMessageBox.critical(
                    self, "File không hợp lệ",
                    "❌ File license không khớp với máy tính hoặc USB của bạn."
                )

    def _activate(self):
        key = self.key_input.toPlainText().strip()
        if not key:
            QMessageBox.warning(self, "Chưa nhập key", "Vui lòng dán chuỗi License Key hoặc chọn file license.")
            return

        # Thử kích hoạt cho máy hiện tại
        if save_license(self.machine_id, key, "MACHINE"):
            QMessageBox.information(
                self, "Kích hoạt thành công",
                "✅ Bản quyền đã được kích hoạt thành công trên máy tính này!"
            )
            self.accept()
            return

        # Nếu không được, thử kiểm tra xem có khớp với USB đang cắm không
        usbs = get_connected_usb_serials()
        for usb_sn in usbs:
            if save_license(usb_sn, key, "USB"):
                QMessageBox.information(
                    self, "Kích hoạt thành công (USB)",
                    f"✅ Bản quyền USB Dongle ({usb_sn}) đã kích hoạt thành công!\n"
                    "Cắm USB này vào bất kỳ máy nào để sử dụng."
                )
                self.accept()
                return

        QMessageBox.critical(
            self, "Key không hợp lệ",
            "❌ License key không đúng hoặc không khớp với mã phần cứng của máy này.\n"
            "Vui lòng kiểm tra lại key hoặc liên hệ nhà cung cấp."
        )
