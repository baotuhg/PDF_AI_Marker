/**
 * GOOGLE APPS SCRIPT — MÁY CHỦ BẢN QUYỀN ĐÁM MÂY (CLOUD LICENSE SERVER)
 * Dự án: PDF AI Marker v3
 * Tác giả: Nguyễn Bảo Tú (23HG)
 * 
 * HƯỚNG DẪN 3 BƯỚC TRIỂN KHAI (HOÀN TOÀN MIỄN PHÍ TRÊN GOOGLE):
 * 1. Mở https://sheets.new để tạo một trang tính Google Sheets mới (Đặt tên: "PDF_AI_Marker_Licenses").
 * 2. Trên thanh menu, chọn: Tiện ích mở rộng (Extensions) > Apps Script.
 * 3. Xóa hết mã cũ trong cửa sổ soạn thảo, dán toàn bộ đoạn mã này vào rồi bấm Lưu (Ctrl + S).
 * 4. Bấm "Triển khai" (Deploy) > "Tùy chọn triển khai mới" (New deployment):
 *    - Loại: Chọn biểu tượng bánh răng ⚙️ > "Ứng dụng web" (Web app).
 *    - Mô tả: "PDF AI Marker Cloud Server v3"
 *    - Thực thi dưới dạng (Execute as): "Tôi" (Me).
 *    - Người có quyền truy cập (Who has access): "Bất kỳ ai" (Anyone).  <-- CỰC KỲ QUAN TRỌNG!
 * 5. Bấm "Triển khai" > Cấp quyền truy cập cho tài khoản Google của bạn.
 * 6. Copy đường link "URL ứng dụng web" (dạng https://script.google.com/macros/s/AKfy.../exec)
 *    và dán vào file "cloud_config.json" cạnh file phần mềm của bạn.
 */

const SHEET_NAME = "Licenses";

// Hàm xử lý yêu cầu GET từ phần mềm gửi lên
function doGet(e) {
  try {
    const params = e ? e.parameter : {};
    const action = params.action || "check";
    const rawIds = params.machine_id || "";

    if (!rawIds) {
      return jsonResponse({
        status: "error",
        found: false,
        message: "Thiếu tham số machine_id"
      });
    }

    // Tách danh sách machine_id (khách có thể gửi cả Pure HW ID và Legacy ID)
    const queryIds = rawIds.split(",").map(id => id.trim().toUpperCase()).filter(id => id.length > 0);

    const sheet = getOrCreateSheet();
    const data = sheet.getDataRange().getValues();

    // Duyệt từ hàng thứ 2 (bỏ qua hàng tiêu đề)
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const rowMachineId = String(row[1] || "").trim().toUpperCase();
      const rowCustomer = String(row[2] || "").trim();
      const rowKey = String(row[4] || "").trim().toUpperCase();
      const rowStatus = String(row[5] || "").trim().toUpperCase();

      if (!rowMachineId) continue;

      // Kiểm tra xem machine_id có khớp với bất kỳ ID nào trong danh sách truy vấn không
      for (const qId of queryIds) {
        if (rowMachineId === qId || rowMachineId.includes(qId) || qId.includes(rowMachineId)) {
          // Kiểm tra trạng thái kích hoạt
          if (rowStatus === "BLOCKED" || rowStatus === "KHOA" || rowStatus === "DISABLED") {
            return jsonResponse({
              status: "blocked",
              found: true,
              active: false,
              message: "Bản quyền của máy này đã bị tạm ngưng hoặc thu hồi bởi tác giả."
            });
          }

          // Kích hoạt hợp lệ
          return jsonResponse({
            status: "success",
            found: true,
            active: true,
            target_id: rowMachineId,
            key: rowKey,
            customer: rowCustomer || "Khách hàng thân thiết",
            message: "Xác thực bản quyền thành công."
          });
        }
      }
    }

    // Không tìm thấy trong bảng
    return jsonResponse({
      status: "not_found",
      found: false,
      active: false,
      message: "Mã máy tính chưa được đăng ký trong danh sách bản quyền của tác giả."
    });

  } catch (err) {
    return jsonResponse({
      status: "error",
      found: false,
      message: "Lỗi xử lý server: " + err.toString()
    });
  }
}

// Xử lý POST (Dùng khi bạn muốn gọi API tự động thêm key từ hệ thống bán hàng)
function doPost(e) {
  try {
    const postData = JSON.parse(e.postData.contents);
    const action = postData.action || "add";

    if (action === "add") {
      const sheet = getOrCreateSheet();
      const machineId = String(postData.machine_id || "").trim().toUpperCase();
      const customer = String(postData.customer || "").trim();
      const phone = String(postData.phone || "").trim();
      const key = String(postData.key || "").trim().toUpperCase();
      const notes = String(postData.notes || "").trim();

      if (!machineId || !key) {
        return jsonResponse({ status: "error", message: "machine_id và key không được để trống" });
      }

      sheet.appendRow([new Date(), machineId, customer, phone, key, "ACTIVE", notes]);
      return jsonResponse({ status: "success", message: "Đã thêm bản quyền thành công!" });
    }

    return doGet(e);
  } catch (err) {
    return jsonResponse({ status: "error", message: err.toString() });
  }
}

// Tạo bảng và hàng tiêu đề chuẩn nếu sheet chưa có
function getOrCreateSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }

  // Nếu sheet rỗng, chèn tiêu đề chuẩn
  if (sheet.getLastRowNum() === 0) {
    const headers = [
      "Thời gian tạo",
      "Mã máy tính (Machine ID)",
      "Tên khách hàng",
      "Số điện thoại / Zalo",
      "License Key (RSA)",
      "Trạng thái (ACTIVE / BLOCKED)",
      "Ghi chú"
    ];
    sheet.appendRow(headers);
    const headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground("#1e3a8a");
    headerRange.setFontColor("#ffffff");
    headerRange.setFontWeight("bold");
    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, headers.length);
  }
  return sheet;
}

// Hàm bổ trợ trả về JSON chuẩn
function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// Thêm menu tiện ích vào giao diện Google Sheets của bạn
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu("🔑 Quản lý Bản quyền PDF AI")
    .addItem("Khởi tạo cấu trúc bảng chuẩn", "setupSheetLayout")
    .addToUi();
}

function setupSheetLayout() {
  getOrCreateSheet();
  SpreadsheetApp.getUi().alert("Đã khởi tạo thành công cấu trúc bảng bản quyền!");
}
