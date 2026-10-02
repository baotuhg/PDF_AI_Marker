# Hướng dẫn Bản quyền PDF AI Marker v3 (Cơ chế nâng cao học từ HTTKD)

## 1. Kiến trúc bảo vệ bản quyền

Hệ thống bản quyền được nâng cấp toàn diện dựa trên mô hình của HTTKD kết hợp với mã hóa bất đối xứng hiện đại:

1. **Chữ ký số bất đối xứng RSA-1024 (Toán học Pure Python)**:
   - Ứng dụng phân phối cho khách hàng **CHỈ CHỨA PUBLIC KEY**.
   - **PRIVATE KEY** bí mật tuyệt đối nằm trong `keygen.py` phía người bán.
   - **Chống làm giả Key 100%**: Dù người ngoài có dịch ngược (decompile) đọc hết mã nguồn thì cũng không thể tạo ra keygen, vì việc tính toán Private Key từ Public Key là bất khả thi về mặt toán học.

2. **Khóa 2 chế độ (Đặc sản của HTTKD dành cho kỹ sư AEC)**:
   - **Gói 1: Theo Máy tính (SSD)** — Khóa cố định theo 1 máy tính.
   - **Gói 2: Theo USB Dongle (Di động)** — Đăng ký theo Serial phần cứng của USB (Kingston, Sandisk...). Khách cắm USB vào máy nào thì máy đó chạy được (như khóa cứng dự toán).

3. **Chốt chặn đa tầng (Chống Bypass dòng lệnh)**:
   - Cửa sổ giao diện `app.py` kiểm tra bản quyền.
   - Tiến trình lõi `marker_worker.py` kiểm tra bản quyền trước khi OCR/xử lý.
   - Script dòng lệnh `reprocess_pdf_to_clean_markdown.py` cũng chặn nếu chưa kích hoạt.

4. **Trải nghiệm người dùng mượt mà (UX HTTKD)**:
   - Khi dialog mở lên, **mã máy tự động được sao chép vào Clipboard**.
   - Khách chỉ cần mở Zalo/Email và ấn `Ctrl + V` là xong.
   - Khách có thể kích hoạt bằng cách **dán License Key** HOẶC **chọn file `pdf_ai.lic`** bạn gửi.

---

## 2. Cách tạo Key cho khách (Phía người bán)

File `keygen.py` nằm ở thư mục gốc `D:\Code\PDF_AI_Marker_v3\keygen.py`. **Giữ riêng, không chia sẻ file này!**

### Cách 1: Khách gửi Machine ID (Khóa theo SSD máy tính)
```bash
python keygen.py <MACHINE_ID>
```
Lệnh sẽ in chuỗi License Key và tự sinh luôn file `pdf_ai.lic`.

### Cách 2: Khách mua gói USB Dongle (Dùng nhiều máy)
Khách cắm USB vào máy, mở app chọn tab "🔌 Khóa theo USB" để copy Serial USB:
```bash
python keygen.py --usb <SERIAL_USB>
```

### Cách 3: Chạy tương tác (không cần nhớ lệnh)
Chỉ cần gõ:
```bash
python keygen.py
```
Menu tương tác sẽ hỏi bạn muốn tạo key theo SSD hay theo USB và xuất kết quả.

---

## 3. Quy trình gửi bản quyền cho khách

Sau khi nhận thanh toán:
1. Bạn chạy `keygen.py` với mã khách gửi.
2. Gửi cho khách 1 trong 2 cách:
   - **Cách A (Gửi chuỗi key):** Copy chuỗi License Key gửi qua Zalo, khách bấm "📋 Dán từ Clipboard" rồi bấm "Kích hoạt".
   - **Cách B (Gửi file lic — giống HTTKD):** Gửi file `pdf_ai.lic` vừa sinh ra, khách chỉ cần chép đè vào thư mục app hoặc bấm nút "📁 Chọn file pdf_ai.lic" trên giao diện.

---

## 4. Đóng gói EXE bằng PyInstaller

Chạy script tự động:
```cmd
build_exe.bat
```
Hoặc:
```cmd
pyinstaller PDF_AI_Marker.spec --noconfirm
```
File `keygen.py` đã được cấu hình loại trừ tuyệt đối khỏi EXE (`excludes=['keygen']`).
