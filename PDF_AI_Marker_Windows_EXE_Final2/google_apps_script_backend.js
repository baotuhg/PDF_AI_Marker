/**
 * GOOGLE APPS SCRIPT — MÁY CHỦ BẢN QUYỀN ĐÁM MÂY (CLOUD LICENSE SERVER)
 * Dự án: PDF AI Marker v3
 * Tác giả: Nguyễn Bảo Tú (23HG)
 * Hỗ trợ 3 gói: 1 Năm (Subscription), Dùng thử 1 Tháng (30 Ngày), Vĩnh viễn (150 Năm - Trọn đời)
 */

const SHEET_NAME = "Licenses";

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

    const queryIds = rawIds.split(",").map(id => id.trim().toUpperCase()).filter(id => id.length > 0);
    const sheet = getOrCreateSheet();
    const data = sheet.getDataRange().getValues();
    const nowUtc = new Date().toISOString();

    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const rowMachineId = String(row[1] || "").trim().toUpperCase();
      const rowCustomer = String(row[2] || "").trim();
      const rowPhone = String(row[3] || "").trim();

      // Nhận diện tự động cột Key (tương thích cả bảng 7 cột cũ và 9 cột mới)
      let rowPlan = "LIFETIME";
      let rowExpireDate = "2176-12-31";
      let rowKey = "";
      let rowStatus = "ACTIVE";

      if (String(row[4] || "").length > 80) {
        // Cấu trúc cũ: Col E = Key, Col F = Status
        rowKey = String(row[4] || "").trim().toUpperCase();
        rowStatus = String(row[5] || "ACTIVE").trim().toUpperCase();
      } else {
        // Cấu trúc mới: Col E = Plan, Col F = Expire Date, Col G = Key, Col H = Status
        rowPlan = String(row[4] || "LIFETIME").trim().toUpperCase();
        rowExpireDate = String(row[5] || "2176-12-31").trim();
        rowKey = String(row[6] || "").trim().toUpperCase();
        rowStatus = String(row[7] || "ACTIVE").trim().toUpperCase();
      }

      if (!rowMachineId || !rowKey) continue;

      for (const qId of queryIds) {
        if (rowMachineId === qId || rowMachineId.includes(qId) || qId.includes(rowMachineId)) {
          if (rowStatus === "BLOCKED" || rowStatus === "KHOA" || rowStatus === "DISABLED") {
            return jsonResponse({
              status: "blocked",
              found: true,
              active: false,
              message: "Bản quyền của máy này đã bị tạm ngưng hoặc thu hồi bởi tác giả."
            });
          }

          // Kiểm tra xem đã quá ngày hết hạn chưa
          if (rowExpireDate && rowExpireDate !== "LIFETIME") {
            const expDate = new Date(rowExpireDate);
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            if (expDate < today) {
              return jsonResponse({
                status: "expired",
                found: true,
                active: false,
                target_id: rowMachineId,
                plan: rowPlan,
                expire_date: rowExpireDate,
                customer: rowCustomer,
                server_time: nowUtc,
                message: "Bản quyền gói " + rowPlan + " đã hết hạn vào ngày " + rowExpireDate + ". Vui lòng gia hạn."
              });
            }
          }

          return jsonResponse({
            status: "success",
            found: true,
            active: true,
            target_id: rowMachineId,
            key: rowKey,
            plan: rowPlan,
            expire_date: rowExpireDate,
            customer: rowCustomer || "Quý khách",
            server_time: nowUtc,
            message: "Xác thực bản quyền thành công."
          });
        }
      }
    }

    return jsonResponse({
      status: "not_found",
      found: false,
      active: false,
      server_time: nowUtc,
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

function doPost(e) {
  try {
    const postData = JSON.parse(e.postData.contents);
    const action = postData.action || "add";

    if (action === "add") {
      const sheet = getOrCreateSheet();
      const machineId = String(postData.machine_id || "").trim().toUpperCase();
      const customer = String(postData.customer || "").trim();
      const phone = String(postData.phone || "").trim();
      const plan = String(postData.plan || "LIFETIME").trim().toUpperCase();
      const expireDate = String(postData.expire_date || "2176-12-31").trim();
      const key = String(postData.key || "").trim().toUpperCase();
      const notes = String(postData.notes || "").trim();

      if (!machineId || !key) {
        return jsonResponse({ status: "error", message: "machine_id và key không được để trống" });
      }

      sheet.appendRow([new Date(), machineId, customer, phone, plan, expireDate, key, "ACTIVE", notes]);
      return jsonResponse({ status: "success", message: "Đã thêm bản quyền thành công!" });
    }

    return doGet(e);
  } catch (err) {
    return jsonResponse({ status: "error", message: err.toString() });
  }
}

function getOrCreateSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }

  if (sheet.getLastRowNum() === 0) {
    const headers = [
      "Thời gian tạo",
      "Mã máy tính (Machine ID)",
      "Tên khách hàng",
      "Số điện thoại / Zalo",
      "Gói bản quyền (1_YEAR / LIFETIME / TRIAL)",
      "Ngày hết hạn (YYYY-MM-DD)",
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

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu("🔑 Quản lý Bản quyền PDF AI")
    .addItem("Khởi tạo cấu trúc bảng chuẩn (3 Gói)", "setupSheetLayout")
    .addToUi();
}

function setupSheetLayout() {
  getOrCreateSheet();
  SpreadsheetApp.getUi().alert("Đã khởi tạo thành công cấu trúc bảng bản quyền 3 gói (1 Năm, Dùng thử 1 Tháng, Vĩnh viễn 150 Năm)!");
}
