"""
PDF AI Marker — License Cloud Auto-Recovery Module
Tự động phục hồi bản quyền qua Đám Mây (Google Sheets API / Web App).

Cơ chế:
1. Khi máy tính bị Format, cài lại Win hoặc chạy ở thư mục mới tinh:
   - Ứng dụng tự động gửi Mã máy (Hardware ID) lên Web API Cloud trong 0.5s.
   - Nếu máy tính này đã được Tác giả cấp bản quyền trên Google Sheets:
     Server trả về chuỗi License Key RSA-1024 và tên khách hàng.
   - Ứng dụng xác minh chữ ký RSA cục bộ (đảm bảo an toàn 100%, chống giả mạo API).
   - Tự động lưu License vào Registry + AppData + Thư mục app + Backup ổ đĩa phụ.
   - Tự động mở khóa vĩnh viễn, người dùng KHÔNG CẦN NHẬP MỘT KÝ TỰ NÀO!
2. Hoạt động Hybrid Offline/Online:
   - Nếu không có mạng hoặc máy công trường: Vẫn hoạt động hoàn hảo với Key Offline.
   - Timeout kết nối chỉ 3.5s, không bao giờ gây đơ hay chậm ứng dụng.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# File cấu hình Cloud Endpoint đặt cạnh file thực thi
_CONFIG_FILE = "cloud_config.json"

# URL mặc định của Web App Google Apps Script do Tác giả triển khai
# (Có thể chỉnh sửa tại file cloud_config.json hoặc thay đổi trực tiếp tại đây)
DEFAULT_CLOUD_URL = "https://script.google.com/macros/s/AKfycbz_SAMPLE_REPLACE_WITH_YOUR_URL/exec"


def _get_config_path() -> Path:
    exe = Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False):
        return exe / _CONFIG_FILE
    return Path(__file__).resolve().parent / _CONFIG_FILE


def get_cloud_config() -> dict:
    """Đọc cấu hình Cloud API từ file cloud_config.json."""
    cfg_path = _get_config_path()
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "enabled": True,
        "api_url": DEFAULT_CLOUD_URL,
        "timeout_sec": 3.5
    }


def save_cloud_config(api_url: str, enabled: bool = True) -> bool:
    """Lưu URL cấu hình Cloud API mới."""
    cfg_path = _get_config_path()
    try:
        data = {
            "enabled": enabled,
            "api_url": api_url.strip(),
            "timeout_sec": 3.5,
            "version": "3.0"
        }
        cfg_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def query_cloud_license(machine_ids: list[str]) -> dict:
    """
    Truy vấn thông tin bản quyền từ Cloud Server theo danh sách Machine ID.
    Trả về dict:
    {
        "success": bool,
        "found": bool,
        "active": bool,
        "target_id": str,
        "key": str,
        "customer": str,
        "message": str
    }
    """
    cfg = get_cloud_config()
    if not cfg.get("enabled", True):
        return {"success": False, "found": False, "message": "Cloud Auto-Recovery đang tắt."}

    api_url = cfg.get("api_url", "").strip()
    if not api_url or "REPLACE_WITH_YOUR_URL" in api_url:
        return {
            "success": False,
            "found": False,
            "message": "Chưa thiết lập URL Google Apps Script Web App trong cloud_config.json."
        }

    clean_ids = [m.strip().upper() for m in machine_ids if m.strip()]
    if not clean_ids:
        return {"success": False, "found": False, "message": "Không có Machine ID hợp lệ để tra cứu."}

    query_str = ",".join(clean_ids)
    timeout = float(cfg.get("timeout_sec", 3.5))

    params = urllib.parse.urlencode({"action": "check", "machine_id": query_str})
    full_url = f"{api_url}?{params}" if "?" not in api_url else f"{api_url}&{params}"

    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": "PDF_AI_Marker_v3_Client/3.0",
            "Accept": "application/json"
        },
        method="GET"
    )

    try:
        # urlopen tự động follow HTTP 302/303 redirect của Google Apps Script
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw_body)
            
            # Chuẩn hóa kết quả trả về từ Apps Script
            status = data.get("status", "")
            found = data.get("found", False) or status == "success"
            active = data.get("active", False) or status == "success"
            
            return {
                "success": True,
                "found": found,
                "active": active,
                "target_id": data.get("target_id", clean_ids[0]).strip().upper(),
                "key": data.get("key", "").strip().upper(),
                "plan": data.get("plan", "LIFETIME").strip().upper(),
                "expire_date": data.get("expire_date", "2176-12-31").strip(),
                "customer": data.get("customer", "Quý khách"),
                "message": data.get("message", "Đã tra cứu thành công.")
            }
    except urllib.error.URLError as e:
        return {"success": False, "found": False, "message": f"Không thể kết nối máy chủ Cloud: {e.reason}"}
    except TimeoutError:
        return {"success": False, "found": False, "message": "Kết nối tới máy chủ kích hoạt bị quá thời gian (Timeout)."}
    except json.JSONDecodeError:
        return {"success": False, "found": False, "message": "Dữ liệu máy chủ trả về không đúng định dạng JSON."}
    except Exception as e:
        return {"success": False, "found": False, "message": f"Lỗi truy vấn đám mây: {e}"}


def recover_license_from_cloud(candidate_ids: list[str]) -> tuple[bool, str, dict]:
    """
    Thực hiện toàn bộ quy trình Auto-Recovery:
    1. Hỏi Cloud
    2. Xác thực chữ ký RSA cục bộ
    3. Tự lưu vào Registry, AppData, App Dir và Phân vùng phụ
    Trả về: (ok: bool, message: str, license_data: dict)
    """
    res = query_cloud_license(candidate_ids)
    if not res.get("success"):
        return False, res.get("message", "Kết nối máy chủ thất bại"), {}

    if not res.get("found") or not res.get("active"):
        return False, res.get("message", "Mã máy chưa được đăng ký hoặc đã hết hiệu lực."), {}

    target_id = res.get("target_id", "")
    key = res.get("key", "")
    customer = res.get("customer", "Quý khách")
    plan = res.get("plan", "LIFETIME")
    expire_date = res.get("expire_date", "2176-12-31")

    if not target_id or not key:
        return False, "Máy chủ không trả về thông tin Key hợp lệ.", {}

    # Import cục bộ để tránh circular import
    from license_core import _verify_sig, save_license

    # BẢO MẬT TUYỆT ĐỐI: Phải kiểm tra chữ ký RSA-1024 cục bộ
    if not _verify_sig(target_id, key, expire_date):
        return False, "Chữ ký số RSA nhận từ máy chủ không hợp lệ!", {}

    # Chữ ký chuẩn xác -> Tự động lưu và kích hoạt trên máy tính
    ok = save_license(target_id, key, "MACHINE", expire_date=expire_date, plan=plan, customer=customer)
    if ok:
        plan_desc = "Vĩnh viễn (150 Năm - Trọn đời)" if plan == "LIFETIME" else ("1 Năm" if plan == "1_YEAR" else "Dùng thử 1 Tháng")
        msg = f"Chào mừng {customer}! Bản quyền gói {plan_desc} đã được tự động khôi phục từ hệ thống đám mây."
        return True, msg, {
            "target_id": target_id,
            "key": key,
            "customer": customer,
            "plan": plan,
            "expire_date": expire_date
        }
    else:
        return False, "Không thể ghi dữ liệu bản quyền vào hệ thống máy tính.", {}

