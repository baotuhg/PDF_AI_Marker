# 🌐 HƯỚNG DẪN THIẾT LẬP MÁY CHỦ BẢN QUYỀN ĐÁM MÂY (CLOUD LICENSE AUTO-RECOVERY)
**Phần mềm:** PDF AI Marker v3  
**Tác giả:** Nguyễn Bảo Tú (23HG)

---

## 🎯 Mục đích
Giải quyết triệt để bài toán: **Khách hàng cài lại Windows, Format toàn bộ ổ cứng hoặc giải nén phần mềm ở bất kỳ máy nào đã mua bản quyền $\rightarrow$ Phần mềm tự động kết nối đám mây, nhận diện máy và kích hoạt vĩnh viễn trong 0.5 giây!**
- Không cần khách phải gõ hay copy-paste lại key.
- Hoàn toàn miễn phí 100% nhờ hạ tầng Google Cloud & Google Sheets.
- Tác giả quản lý toàn bộ danh sách khách hàng tập trung trên 1 trang tính.

---

## 🛠️ Hướng dẫn 3 bước thiết lập (Mất khoảng 2 phút)

### Bước 1: Tạo Google Sheet quản lý
1. Truy cập trình duyệt và mở: **https://sheets.new** (hoặc tạo Google Trang tính mới trên Google Drive của bạn).
2. Đổi tên trang tính thành: **`PDF_AI_Marker_Licenses`**.

### Bước 2: Dán mã Script Webhook
1. Trên thanh menu của Google Sheet, bấm: **Tiện ích mở rộng (Extensions)** > **Apps Script**.
2. Xóa toàn bộ nội dung mẫu có sẵn (`function myFunction() {...}`).
3. Mở file **`google_apps_script_backend.js`** (nằm trong thư mục dự án), sao chép toàn bộ nội dung và dán vào cửa sổ soạn thảo Apps Script.
4. Bấm biểu tượng **Lưu (Save / Ctrl + S)**.

### Bước 3: Triển khai thành Web App (Deploy)
1. Ở góc trên bên phải màn hình Apps Script, bấm nút **Triển khai (Deploy)** > Chọn **Tùy chọn triển khai mới (New deployment)**.
2. Bấm vào biểu tượng bánh răng **⚙️ (Chọn loại)** > Chọn **Ứng dụng web (Web app)**.
3. Thiết lập chính xác như sau:
   - **Mô tả (Description):** `PDF AI Marker Cloud Server v3`
   - **Thực thi dưới dạng (Execute as):** **`Tôi (Me / email của bạn)`**
   - **Người có quyền truy cập (Who has access):** **`Bất kỳ ai (Anyone)`** *(Bắt buộc chọn cái này để phần mềm của khách có thể gửi lệnh kiểm tra máy)*.
4. Bấm nút **Triển khai (Deploy)**.
5. Google sẽ yêu cầu cấp quyền: Bấm **Ủy quyền truy cập (Authorize access)** > Chọn tài khoản Google của bạn > Bấm **Advanced (Nâng cao)** > Chọn **Go to ... (unsafe)** > Bấm **Allow (Cho phép)**.
6. Sao chép dòng **URL ứng dụng web (Web app URL)** (Có định dạng `https://script.google.com/macros/s/AKfy.../exec`).

### Bước 4: Nạp URL vào phần mềm
1. Mở file **`cloud_config.json`** trong thư mục phần mềm:
   ```json
   {
     "enabled": true,
     "api_url": "DÁN_ĐƯỜNG_LINK_WEB_APP_CỦA_BẠN_VÀO_ĐÂY",
     "timeout_sec": 3.5,
     "version": "3.0"
   }
   ```
2. Lưu file lại. Từ giờ, mọi bản EXE bạn đóng gói gửi cho khách sẽ tự động liên kết với Google Sheet của bạn!

---

## 📊 Cách thêm khách hàng vào hệ thống (Hỗ trợ 3 Gói)
Khi chạy `python keygen.py`, công cụ sẽ in sẵn 1 dòng dữ liệu dạng bảng. Bạn chỉ cần **copy dòng đó dán thẳng vào Google Sheet**, các cột sẽ tự động nhảy vào đúng vị trí:
1. **Thời gian tạo:** Ngày giờ cấp key.
2. **Mã máy tính (Machine ID):** Mã máy khách gửi (hoặc mã USB).
3. **Tên khách hàng:** Họ tên khách (để hiển thị lời chào trên app).
4. **Số điện thoại / Zalo:** Liên hệ chăm sóc khách hàng.
5. **Gói bản quyền:** Điền `1_YEAR` (Gói 1 Năm), `LIFETIME` (Vĩnh viễn 150 Năm) hoặc `TRIAL_30D` (Dùng thử 1 Tháng).
6. **Ngày hết hạn:** Định dạng `YYYY-MM-DD` (ví dụ `2027-10-03` hoặc `2176-10-03`).
7. **License Key (RSA):** Key được sinh ra từ `keygen.py`.
8. **Trạng thái:** Điền **`ACTIVE`** (Mặc định).
   - *Mẹo hay:* Nếu khách bùng tiền hoặc muốn thu hồi bản quyền, bạn chỉ cần sửa cột này thành **`BLOCKED`** $\rightarrow$ Phần mềm trên máy khách sẽ tự động bị khóa!
9. **Ghi chú:** Ghi chú thêm (dự án, thỏa thuận...).

---

## 🔒 Tính bảo mật tuyệt đối
Hệ thống này được bảo vệ 2 lớp:
1. **Lớp 1 (Google Apps Script):** Chỉ bạn mới có quyền xem và sửa danh sách khách hàng.
2. **Lớp 2 (Chữ ký điện tử RSA-1024):** Dù có ai đó cố tình can thiệp vào đường truyền mạng hay gửi dữ liệu giả mạo từ server khác, phần mềm trên máy khách **luôn luôn xác minh chữ ký RSA bằng Public Key không thể làm giả** trước khi chấp nhận kích hoạt.
