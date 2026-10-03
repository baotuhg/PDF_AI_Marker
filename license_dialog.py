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
from license_core import save_license, import_license_file, get_connected_usb_serials, verify_license


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

        # Header & Trạng thái bản quyền
        from license_core import get_license_status
        st = get_license_status()
        status = st.get("status", "EXPIRED")
        days_left = st.get("days_left", 0)

        if status == "ACTIVE":
            title = QLabel("🔑  Bản quyền PDF AI Marker v3 — [ĐÃ KÍCH HOẠT VĨNH VIỄN]")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet("color: #1e3a8a;")
            layout.addWidget(title)

            status_notice = QLabel(
                "🎉 <b>Phần mềm ĐÃ ĐƯỢC KÍCH HOẠT BẢN QUYỀN THƯƠNG MẠI HỢP LỆ!</b><br>"
                "Tác giả: <b>Nguyễn Bảo Tú (23HG)</b>  |  Phiên bản: <b>3.0 Commercial</b><br>"
                "<i>Trạng thái: Hoạt động đầy đủ tính năng. Bạn có thể gia hạn hoặc đổi sang USB nếu cần.</i>"
            )
            status_notice.setTextFormat(Qt.RichText)
            status_notice.setStyleSheet(
                "background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; "
                "border-radius: 6px; padding: 10px 14px; font-size: 10pt;"
            )
            layout.addWidget(status_notice)
        elif status == "TRIAL":
            title = QLabel(f"🎁  Bản quyền PDF AI Marker v3 — [DÙNG THỬ CÒN {days_left} NGÀY]")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet("color: #b45309;")
            layout.addWidget(title)

            status_notice = QLabel(
                f"🎁 <b>BẠN ĐANG TRONG THỜI GIAN DÙNG THỬ MIỄN PHÍ ({days_left} ngày còn lại)!</b><br>"
                "Tác giả: <b>Nguyễn Bảo Tú (23HG)</b>  |  Trải nghiệm đầy đủ 100% tính năng AI và OCR.<br>"
                "Mã máy (Machine ID) <b>đã tự động được sao chép</b>. Bạn có thể mua key bất kỳ lúc nào để mở khóa vĩnh viễn."
            )
            status_notice.setTextFormat(Qt.RichText)
            status_notice.setStyleSheet(
                "background: #fef3c7; color: #92400e; border: 1px solid #fde68a; "
                "border-radius: 6px; padding: 10px 14px; font-size: 10pt;"
            )
            layout.addWidget(status_notice)
        else:
            title = QLabel("🔒  Kích hoạt Bản quyền PDF AI Marker v3")
            title.setFont(QFont("Segoe UI", 14, QFont.Bold))
            title.setStyleSheet("color: #991b1b;")
            layout.addWidget(title)

            copy_notice = QLabel(
                "⚠️ <b>Thời hạn dùng thử miễn phí đã kết thúc hoặc máy chưa kích hoạt key!</b><br>"
                "Tác giả: <b>Nguyễn Bảo Tú (23HG)</b><br>"
                "Mã máy (Machine ID) <b>đã tự động được sao chép vào Clipboard</b>. Mở Zalo/Email ấn <b>Ctrl + V</b> để gửi mã đăng ký key."
            )
            copy_notice.setTextFormat(Qt.RichText)
            copy_notice.setStyleSheet(
                "background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; "
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

        cloud_btn = QPushButton("🌐 Tự động khôi phục (Cloud)")
        cloud_btn.setStyleSheet(
            "QPushButton { background: #0284c7; color: white; border: none; "
            "border-radius: 6px; padding: 9px 16px; font-weight: 600; font-size: 10pt; }"
            "QPushButton:hover { background: #0369a1; }"
        )
        cloud_btn.setToolTip("Tự động kết nối máy chủ để khôi phục bản quyền nếu bạn vừa cài lại Windows hoặc format máy.")
        cloud_btn.clicked.connect(self._restore_from_cloud)
        act_row.addWidget(cloud_btn)
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

        # Footer liên hệ & hướng dẫn
        guide_tip = QLabel(
            "💡 <i>Mẹo: Sau khi Format hoặc Cài lại Win, bạn chỉ cần bấm nút <b>🌐 Tự động khôi phục (Cloud)</b> để hệ thống tự nhận diện lại máy!</i>"
        )
        guide_tip.setTextFormat(Qt.RichText)
        guide_tip.setStyleSheet("color: #0369a1; font-size: 9pt;")
        layout.addWidget(guide_tip)

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

    def _restore_from_cloud(self):
        """Khôi phục bản quyền tự động từ Cloud (cho trường hợp format/cài lại Win)."""
        from license_core import _get_candidate_machine_ids
        from license_cloud import recover_license_from_cloud

        cands = _get_candidate_machine_ids()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg, lic_info = recover_license_from_cloud(cands)
        finally:
            QApplication.restoreOverrideCursor()

        if ok:
            cust = lic_info.get("customer", "")
            name_str = f"khách hàng <b>{cust}</b>" if cust else "máy tính của bạn"
            QMessageBox.information(
                self, "Khôi phục thành công",
                f"🎉 <b>ĐÃ TỰ ĐỘNG KHÔI PHỤC BẢN QUYỀN TỪ CLOUD!</b><br><br>"
                f"Hệ thống máy chủ đã nhận diện {name_str} và kích hoạt bản quyền vĩnh viễn.<br><br>"
                f"Cảm ơn bạn đã tin tưởng sử dụng <b>PDF AI Marker v3</b>!"
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, "Thông báo kích hoạt Cloud",
                f"⚠️ <b>Kết quả kiểm tra máy chủ:</b><br><br>"
                f"{msg}<br><br>"
                f"<i>Nếu bạn vừa cài lại Win, hãy đảm bảo máy tính đã kết nối Internet "
                f"hoặc dán trực tiếp License Key do tác giả cấp vào ô bên trên.</i>"
            )

