"""
PDF AI Marker — License Core (RSA-1024 Asymmetric & Hardware/USB Binding)
Mô hình bảo vệ bản quyền lấy cảm hứng từ HTTKD:
  1. Chữ ký số bất đối xứng RSA-1024: Bản phân phối CHỈ CHỨA PUBLIC KEY.
     Không thể tạo keygen dù decompile đọc 100% mã nguồn.
  2. Khóa kép linh hoạt:
     - Khóa theo Ổ cứng SSD (1 máy cố định).
     - Khóa theo USB Dongle (cắm USB vào máy nào thì máy đó chạy được).
  3. Đọc phần cứng qua PowerShell CIM + Win32 Kernel32 (chạy tốt trên cả Win 10 & Win 11).
"""
import base64
import ctypes
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

# ── PUBLIC KEY RSA-1024 (Chỉ dùng để VERIFY — Tuyệt đối an toàn) ───────────────
# Private key nằm RIÊNG ở keygen.py phía người bán, không nhúng vào ứng dụng.
_RSA_N = 0xc507e34d1c98535b2d9cd21cc38aeda04d54192e61ab312622306781555fed2caca8f6ac7f6f4828b3dabfb904eb6f34e91fdfa319c80f4e1c0d28188cf15904183c91a7f324a5a83c26338b4925c410021bc62721ee9f8afb3ccde2585af5cfd17354b432728bbdad65b543e709912a97b19d1de3311b6a72387910bec33f1d
_RSA_E = 0x10001

_LICENSE_FILE = "pdf_ai.lic"
# ─────────────────────────────────────────────────────────────────────────────


def _get_disk_serials() -> list[str]:
    """Lấy danh sách Serial của các ổ đĩa cố định nội bộ (bỏ qua USB/thẻ nhớ)."""
    if sys.platform != "win32":
        return []
    serials = []
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_DiskDrive -Filter \"InterfaceType != 'USB'\" | Sort-Object Index).SerialNumber"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.splitlines():
            sn = line.strip().replace(".", "").replace(" ", "").replace("_", "")
            if len(sn) >= 6:
                clean_sn = sn.upper()
                if clean_sn not in serials:
                    serials.append(clean_sn)
    except Exception:
        pass

    if not serials:
        try:
            vol_serial = ctypes.c_ulong()
            ctypes.windll.kernel32.GetVolumeInformationW(
                "C:\\", None, 0, ctypes.byref(vol_serial), None, None, None, 0
            )
            if vol_serial.value:
                serials.append(f"VOL_{vol_serial.value:08X}")
        except Exception:
            pass

    return serials


def _get_disk_serial() -> str:
    """Lấy số Serial phần cứng của ổ đĩa cài Windows (SSD/HDD chính)."""
    sns = _get_disk_serials()
    return sns[0] if sns else ""


def _get_pure_hardware_id() -> str:
    """Mã máy dựa trên 100% phần cứng vật lý (Serial SSD + Bo mạch chủ).
    Bất biến vĩnh viễn, không thay đổi dù cài lại Win, đổi tên máy hay format ổ đĩa.
    """
    parts = []
    disk_sn = _get_disk_serial()
    if disk_sn:
        parts.append(f"DISK:{disk_sn}")
    if sys.platform == "win32":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_BaseBoard).SerialNumber"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            mb = r.stdout.strip()
            if mb and mb.lower() not in ("to be filled by o.e.m.", "default string", "none"):
                parts.append(f"MB:{mb}")
        except Exception:
            pass
    if not parts:
        parts.append(f"FALLBACK:{platform.node()}")
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32].upper()


def _get_legacy_machine_id() -> str:
    """Mã máy cũ (chứa HOST:node) để tương thích ngược 100% với key đã cấp trước đây."""
    parts = []
    disk_sn = _get_disk_serial()
    if disk_sn:
        parts.append(f"DISK:{disk_sn}")
    if sys.platform == "win32":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_BaseBoard).SerialNumber"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            mb = r.stdout.strip()
            if mb and mb.lower() not in ("to be filled by o.e.m.", "default string", "none"):
                parts.append(f"MB:{mb}")
        except Exception:
            pass
    parts.append(f"HOST:{platform.node()}")
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32].upper()


def _get_candidate_machine_ids() -> list[str]:
    """Danh sách các mã máy hợp lệ trên máy tính này (tất cả các ổ cứng nội bộ, Pure HW ID & Legacy ID)."""
    cands = []
    disk_sns = _get_disk_serials()
    mb = ""
    if sys.platform == "win32":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_BaseBoard).SerialNumber"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            mb_raw = r.stdout.strip()
            if mb_raw and mb_raw.lower() not in ("to be filled by o.e.m.", "default string", "none"):
                mb = mb_raw
        except Exception:
            pass

    for d_sn in disk_sns:
        p_hw = []
        if d_sn:
            p_hw.append(f"DISK:{d_sn}")
        if mb:
            p_hw.append(f"MB:{mb}")
        if p_hw:
            hid = hashlib.sha256("|".join(p_hw).encode("utf-8")).hexdigest()[:32].upper()
            if hid not in cands:
                cands.append(hid)

        p_leg = list(p_hw)
        p_leg.append(f"HOST:{platform.node()}")
        lid = hashlib.sha256("|".join(p_leg).encode("utf-8")).hexdigest()[:32].upper()
        if lid not in cands:
            cands.append(lid)

    if not cands:
        hw_id = _get_pure_hardware_id()
        legacy_id = _get_legacy_machine_id()
        cands.append(hw_id)
        if legacy_id != hw_id and legacy_id not in cands:
            cands.append(legacy_id)

    return cands


def _get_machine_id() -> str:
    """
    Trả về Machine ID đại diện của máy tính:
    - Nếu máy đã có key hợp lệ (kể cả key legacy cũ), giữ nguyên ID đó để không gián đoạn bản quyền.
    - Mặc định trả về Pure Hardware ID (vĩnh cửu theo SSD + Mainboard).
    """
    legacy_id = _get_legacy_machine_id()
    # Kiểm tra xem có file license hoặc registry nào khớp với legacy_id không
    try:
        lic_path = _license_path()
        if lic_path.exists():
            data = json.loads(lic_path.read_text(encoding="utf-8"))
            if data.get("target_id", "").strip().upper() == legacy_id:
                if _verify_sig(legacy_id, data.get("key", "")):
                    return legacy_id
        reg_data = _read_registry_license()
        if reg_data and reg_data.get("target_id", "").strip().upper() == legacy_id:
            if _verify_sig(legacy_id, reg_data.get("key", "")):
                return legacy_id
    except Exception:
        pass

    return _get_pure_hardware_id()


def get_connected_usb_serials() -> list[str]:
    """Lấy danh sách Serial của các USB Flash Drive đang cắm vào máy."""
    serials = []
    if sys.platform != "win32":
        return serials
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_DiskDrive | Where-Object { $_.InterfaceType -eq 'USB' } | Select-Object -ExpandProperty SerialNumber"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        for line in r.stdout.splitlines():
            clean = line.strip().replace(".", "").replace(" ", "").replace("_", "").replace("&", "")
            if len(clean) >= 6:
                serials.append(clean.upper())
    except Exception:
        pass
    return serials


def _verify_sig(target_id: str, sig_str: str, expire_date: str = "") -> bool:
    """Xác minh chữ ký số RSA-1024 với Public Key (Pure Python)."""
    try:
        clean_sig = sig_str.strip().upper().replace(" ", "").replace("\n", "").replace("\r", "")
        padding = "=" * (-len(clean_sig) % 8)
        sig_bytes = base64.b32decode(clean_sig + padding)
        sig_int = int.from_bytes(sig_bytes, "big")

        h_actual = pow(sig_int, _RSA_E, _RSA_N)
        tid = target_id.strip().upper()

        # 1. Thử xác minh theo payload có ngày hết hạn
        if expire_date:
            payload = f"PDF_AI_v3:{tid}:{expire_date.strip()}".encode("utf-8")
            if h_actual == int.from_bytes(hashlib.sha256(payload).digest(), "big"):
                return True

        # 2. Thử xác minh Legacy (Không có ngày -> Tự động là Vĩnh viễn 150 Năm)
        payload_legacy = f"PDF_AI_v3:{tid}".encode("utf-8")
        if h_actual == int.from_bytes(hashlib.sha256(payload_legacy).digest(), "big"):
            return True

        return False
    except Exception:
        return False


def _resolve_license_validity(target_id: str, sig_str: str, declared_exp: str = "") -> tuple[bool, str, str, int, str]:
    """
    Xác thực chữ ký số RSA và tính toán thời hạn, gói bản quyền (1 Năm, 150 Năm Vĩnh Viễn, Dùng thử 1 Tháng).
    Trả về: (is_valid: bool, plan_code: str, expire_date: str, days_left: int, message: str)
    """
    try:
        clean_sig = sig_str.strip().upper().replace(" ", "").replace("\n", "").replace("\r", "")
        padding = "=" * (-len(clean_sig) % 8)
        sig_bytes = base64.b32decode(clean_sig + padding)
        sig_int = int.from_bytes(sig_bytes, "big")

        h_actual = pow(sig_int, _RSA_E, _RSA_N)
        tid = target_id.strip().upper()
        now = datetime.datetime.now(datetime.timezone.utc)
        today = now.date()

        matched_exp = ""
        is_matched = False
        is_legacy = False

        # 1. Thử với declared_exp nếu có
        if declared_exp:
            exp_str = declared_exp.strip()
            payload = f"PDF_AI_v3:{tid}:{exp_str}".encode("utf-8")
            if h_actual == int.from_bytes(hashlib.sha256(payload).digest(), "big"):
                is_matched = True
                matched_exp = exp_str

        # 2. Thử với legacy payload (Không có ngày -> Tự động là Vĩnh viễn 150 năm)
        if not is_matched:
            payload_legacy = f"PDF_AI_v3:{tid}".encode("utf-8")
            if h_actual == int.from_bytes(hashlib.sha256(payload_legacy).digest(), "big"):
                is_matched = True
                is_legacy = True
                matched_exp = "2176-12-31"

        if not is_matched:
            return False, "INVALID", "", 0, "Chữ ký bản quyền không hợp lệ hoặc sai mã máy."

        # Xử lý ngày hết hạn
        if is_legacy:
            days_left = 150 * 365
            return True, "LIFETIME", matched_exp, days_left, "Bản quyền Vĩnh viễn hợp lệ (Thời hạn 150 Năm - Trọn đời)"

        try:
            exp_date = datetime.date.fromisoformat(matched_exp)
        except Exception:
            exp_date = today + datetime.timedelta(days=365)

        days_left = (exp_date - today).days

        if days_left <= 0:
            return False, "EXPIRED", matched_exp, 0, f"Bản quyền đã hết hạn vào ngày {exp_date.strftime('%d/%m/%Y')}. Vui lòng gia hạn."

        if days_left > 36500:
            return True, "LIFETIME", matched_exp, days_left, "Bản quyền Vĩnh viễn hợp lệ (Thời hạn 150 Năm - Trọn đời)"
        elif days_left > 35:
            return True, "1_YEAR", matched_exp, days_left, f"Bản quyền 1 Năm hợp lệ (Còn {days_left} ngày, hết hạn: {exp_date.strftime('%d/%m/%Y')})"
        else:
            return True, "TRIAL_30D", matched_exp, days_left, f"Bản quyền còn {days_left} ngày (hết hạn: {exp_date.strftime('%d/%m/%Y')})"

    except Exception as e:
        return False, "ERROR", "", 0, f"Lỗi xác thực: {e}"



try:
    import winreg
except ImportError:
    winreg = None

_REG_PATH = r"Software\PDF_AI_Marker"
_REG_KEY_NAME = "LicenseData"


def _read_registry_license() -> dict:
    """Đọc dữ liệu bản quyền lưu trong Windows Registry."""
    if not winreg or sys.platform != "win32":
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, _REG_KEY_NAME)
            if val:
                return json.loads(val)
    except Exception:
        pass
    return None


def _write_registry_license(lic_dict: dict):
    """Lưu dữ liệu bản quyền vào Windows Registry theo người dùng hiện tại."""
    if not winreg or sys.platform != "win32":
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
            winreg.SetValueEx(k, _REG_KEY_NAME, 0, winreg.REG_SZ, json.dumps(lic_dict, ensure_ascii=False))
    except Exception:
        pass


def _get_multi_drive_backup_paths() -> list[Path]:
    """Tìm các file backup bản quyền trên các phân vùng ổ đĩa khác (D:, E:, F:,...)."""
    paths = []
    if sys.platform == "win32":
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                try:
                    p = drive / ".pdf_ai_license_backup" / _LICENSE_FILE
                    paths.append(p)
                except Exception:
                    pass
    return paths


def _get_persistent_license_paths() -> list[Path]:
    """Danh sách các vị trí lưu trữ bản quyền bền vững trên máy tính (AppData/Home/Ổ phụ)."""
    paths = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        paths.append(Path(local_appdata) / "PDF_AI_Marker" / _LICENSE_FILE)
    roaming_appdata = os.environ.get("APPDATA")
    if roaming_appdata:
        p = Path(roaming_appdata) / "PDF_AI_Marker" / _LICENSE_FILE
        if p not in paths:
            paths.append(p)
    home_p = Path.home() / ".pdf_ai_marker" / _LICENSE_FILE
    if home_p not in paths:
        paths.append(home_p)

    # Quét thêm các ổ đĩa phụ (D:, E:, ...) đề phòng cài lại Win chỉ format ổ C
    for bp in _get_multi_drive_backup_paths():
        if bp not in paths:
            paths.append(bp)

    return paths


def _license_path() -> Path:
    """Đường dẫn file license cạnh file thực thi hoặc script."""
    exe = Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False):
        return exe / _LICENSE_FILE
    return Path(__file__).resolve().parent / _LICENSE_FILE


import datetime

_TRIAL_FILE = ".pdf_ai_trial"
_TRIAL_SALT = "PDF_AI_MARKER_V3_TRIAL_PROTECTION_2026_23HG"


def _get_trial_dir() -> Path:
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "PDF_AI_Marker"
    else:
        p = Path.home() / ".pdf_ai_marker"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _sign_trial(machine_id: str, start_iso: str) -> str:
    raw = f"{machine_id}::{start_iso}::{_TRIAL_SALT}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_TIME_ANCHOR_FILE = ".time_anchor"


def _read_time_anchor() -> str:
    """Đọc mốc thời gian hệ thống lớn nhất từng ghi nhận."""
    if winreg and sys.platform == "win32":
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "ClockAnchor")
                if val:
                    return val
        except Exception:
            pass
    p = _get_trial_dir() / _TIME_ANCHOR_FILE
    if p.exists():
        try:
            return p.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""


def _update_time_anchor(dt: datetime.datetime):
    """Cập nhật mốc thời gian lớn nhất vào Registry và File ẩn."""
    iso_val = dt.isoformat()
    if winreg and sys.platform == "win32":
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as k:
                winreg.SetValueEx(k, "ClockAnchor", 0, winreg.REG_SZ, iso_val)
        except Exception:
            pass
    try:
        p = _get_trial_dir() / _TIME_ANCHOR_FILE
        p.write_text(iso_val, encoding="utf-8")
        if sys.platform == "win32":
            ctypes.windll.kernel32.SetFileAttributesW(str(p), 2)
    except Exception:
        pass


def _check_clock_tampering(now: datetime.datetime) -> tuple[bool, str]:
    """Kiểm tra xem người dùng có chỉnh lùi đồng hồ Windows không."""
    anchor = _read_time_anchor()
    if anchor:
        try:
            anchor_dt = datetime.datetime.fromisoformat(anchor)
            if (anchor_dt - now).total_seconds() > 7200:
                return True, "Phát hiện thời gian hệ thống bị chỉnh lùi để gian lận bản quyền! Vui lòng chỉnh lại ngày giờ chuẩn."
        except Exception:
            pass
    _update_time_anchor(now)
    return False, ""


def get_license_status() -> dict:
    """
    Trả về trạng thái bản quyền chi tiết:
    {
       "ok": bool,            # True nếu được phép chạy (Bản quyền thật HOẶC Dùng thử hợp lệ)
       "status": str,         # "ACTIVE" | "TRIAL" | "EXPIRED"
       "plan": str,           # "LIFETIME" | "1_YEAR" | "TRIAL_30D" | "EXPIRED"
       "plan_name": str,      # Tên gói hiển thị
       "machine_id": str,     # Mã máy
       "expire_date": str,    # Ngày hết hạn (YYYY-MM-DD)
       "message": str,        # Thông báo trạng thái chi tiết
       "days_left": int,      # Số ngày sử dụng còn lại
       "customer": str        # Tên khách hàng (nếu có)
    }
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    machine_id = _get_machine_id()
    local_lic_path = _license_path()

    # 0. Kiểm tra chống gian lận lùi đồng hồ hệ thống
    tampered, tamper_msg = _check_clock_tampering(now)
    if tampered:
        return {
            "ok": False,
            "status": "EXPIRED",
            "plan": "EXPIRED",
            "plan_name": "Lỗi đồng hồ hệ thống",
            "machine_id": machine_id,
            "expire_date": "",
            "message": tamper_msg,
            "days_left": 0,
            "customer": ""
        }

    # 1. Thu thập tất cả các nguồn license tiềm năng trên máy tính
    candidate_sources: list[tuple[dict, str]] = []

    # a. Thư mục cài đặt hiện tại
    if local_lic_path.exists():
        try:
            candidate_sources.append((json.loads(local_lic_path.read_text(encoding="utf-8")), "LOCAL"))
        except Exception:
            pass

    # b. Các thư mục hệ thống bền vững (AppData, Home, Phân vùng phụ D:, E:...)
    for p in _get_persistent_license_paths():
        if p.exists():
            try:
                candidate_sources.append((json.loads(p.read_text(encoding="utf-8")), "PERSISTENT_FILE"))
            except Exception:
                pass

    # c. Windows Registry
    reg_data = _read_registry_license()
    if reg_data:
        candidate_sources.append((reg_data, "REGISTRY"))

    candidate_ids = _get_candidate_machine_ids()

    # Kiểm tra xem có nguồn nào chứa chữ ký RSA hợp lệ với máy này không
    for data, src in candidate_sources:
        try:
            lic_type = data.get("type", "MACHINE")
            target_id = data.get("target_id", "").strip().upper()
            key = data.get("key", "").strip().upper()
            declared_exp = data.get("expire_date", "").strip()
            customer = data.get("customer", "")

            is_valid = False
            plan_code = "LIFETIME"
            exp_date_str = "2176-12-31"
            days_left = 54750
            msg = ""

            if lic_type == "MACHINE" and (target_id in candidate_ids):
                valid, plan_code, exp_date_str, days_left, msg = _resolve_license_validity(target_id, key, declared_exp)
                if valid:
                    is_valid = True
                    machine_id = target_id
            elif lic_type == "USB":
                connected_usbs = get_connected_usb_serials()
                if any(target_id in usb_sn or usb_sn in target_id for usb_sn in connected_usbs):
                    valid, plan_code, exp_date_str, days_left, msg = _resolve_license_validity(target_id, key, declared_exp)
                    if valid:
                        is_valid = True

            if is_valid:
                # ĐÃ TÌM THẤY BẢN QUYỀN HỢP LỆ THEO MÁY!
                plan_names = {
                    "LIFETIME": "Bản quyền Vĩnh viễn (150 Năm - Trọn đời)",
                    "1_YEAR": "Bản quyền 1 Năm",
                    "TRIAL_30D": "Dùng thử 1 Tháng (30 Ngày)"
                }
                plan_name = plan_names.get(plan_code, f"Bản quyền {plan_code}")

                # 1. Khôi phục lại file pdf_ai.lic vào thư mục app hiện tại nếu chưa có
                if not local_lic_path.exists():
                    try:
                        local_lic_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                # 2. Đồng bộ vào Windows Registry nếu chưa có
                _write_registry_license(data)
                # 3. Đồng bộ vào AppData và Phân vùng phụ D:, E:... nếu chưa có
                for p in _get_persistent_license_paths():
                    if not p.exists():
                        try:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                            if sys.platform == "win32" and ".pdf_ai_license_backup" in str(p):
                                try:
                                    ctypes.windll.kernel32.SetFileAttributesW(str(p.parent), 2)
                                except Exception:
                                    pass
                        except Exception:
                            pass

                return {
                    "ok": True,
                    "status": "ACTIVE",
                    "plan": plan_code,
                    "plan_name": plan_name,
                    "machine_id": machine_id,
                    "expire_date": exp_date_str,
                    "message": msg,
                    "days_left": days_left,
                    "customer": customer
                }
        except Exception:
            continue

    # 1.5. Thử TỰ ĐỘNG KHÔI PHỤC QUA CLOUD (Khi máy vừa cài lại Win sạch hoặc format ổ C)
    try:
        from license_cloud import recover_license_from_cloud
        ok_cloud, msg_cloud, lic_info = recover_license_from_cloud(candidate_ids)
        if ok_cloud:
            p_code = lic_info.get("plan", "LIFETIME")
            p_exp = lic_info.get("expire_date", "2176-12-31")
            p_cust = lic_info.get("customer", "")
            d_left = 54750 if p_code == "LIFETIME" else 365
            return {
                "ok": True,
                "status": "ACTIVE",
                "plan": p_code,
                "plan_name": "Bản quyền Vĩnh viễn (150 Năm - Trọn đời)" if p_code == "LIFETIME" else ("Bản quyền 1 Năm" if p_code == "1_YEAR" else "Dùng thử 1 Tháng"),
                "machine_id": lic_info.get("target_id", machine_id),
                "expire_date": p_exp,
                "message": msg_cloud,
                "days_left": d_left,
                "customer": p_cust
            }
    except Exception:
        pass

    # 2. Cơ chế DÙNG THỬ TỰ ĐỘNG 1 THÁNG (30 ngày từ lần chạy đầu)
    trial_file = _get_trial_dir() / _TRIAL_FILE

    if not trial_file.exists():
        start_iso = now.isoformat()
        sig = _sign_trial(machine_id, start_iso)
        payload = {
            "machine_id": machine_id,
            "start": start_iso,
            "sig": sig,
            "trial_days": 30
        }
        try:
            trial_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if sys.platform == "win32":
                ctypes.windll.kernel32.SetFileAttributesW(str(trial_file), 2)
        except Exception:
            pass
        exp_date_str = (now.date() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        return {
            "ok": True,
            "status": "TRIAL",
            "plan": "TRIAL_30D",
            "plan_name": "Dùng thử miễn phí 1 Tháng (30 Ngày)",
            "machine_id": machine_id,
            "expire_date": exp_date_str,
            "message": "Đang trong thời gian DÙNG THỬ MIỄN PHÍ 1 THÁNG (Còn 30 ngày)",
            "days_left": 30,
            "customer": ""
        }

    try:
        tdata = json.loads(trial_file.read_text(encoding="utf-8"))
        t_mid = tdata.get("machine_id", "")
        t_start = tdata.get("start", "")
        t_sig = tdata.get("sig", "")

        if t_mid != machine_id or _sign_trial(machine_id, t_start) != t_sig:
            return {
                "ok": False,
                "status": "EXPIRED",
                "plan": "EXPIRED",
                "plan_name": "Hết hạn",
                "machine_id": machine_id,
                "expire_date": "",
                "message": "Dữ liệu dùng thử không hợp lệ. Vui lòng kích hoạt gói 1 Năm hoặc Vĩnh viễn (150 Năm).",
                "days_left": 0,
                "customer": ""
            }

        start_dt = datetime.datetime.fromisoformat(t_start)
        elapsed_sec = (now - start_dt).total_seconds()

        trial_duration = 30 * 86400  # 30 ngày = 1 tháng
        if elapsed_sec < trial_duration:
            remain_sec = trial_duration - elapsed_sec
            days_left = max(1, int(remain_sec // 86400) + (1 if remain_sec % 86400 > 0 else 0))
            exp_date_str = (start_dt.date() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            return {
                "ok": True,
                "status": "TRIAL",
                "plan": "TRIAL_30D",
                "plan_name": "Dùng thử miễn phí 1 Tháng (30 Ngày)",
                "machine_id": machine_id,
                "expire_date": exp_date_str,
                "message": f"Dùng thử miễn phí còn {days_left} ngày (Hết hạn: {exp_date_str})",
                "days_left": days_left,
                "customer": ""
            }
        else:
            return {
                "ok": False,
                "status": "EXPIRED",
                "plan": "EXPIRED",
                "plan_name": "Đã hết hạn dùng thử",
                "machine_id": machine_id,
                "expire_date": "",
                "message": "Đã hết thời hạn dùng thử miễn phí 1 tháng (30 ngày). Vui lòng nâng cấp bản quyền 1 Năm hoặc Vĩnh viễn (150 năm) để tiếp tục.",
                "days_left": 0,
                "customer": ""
            }
    except Exception:
        return {
            "ok": False,
            "status": "EXPIRED",
            "plan": "EXPIRED",
            "plan_name": "Hết hạn",
            "machine_id": machine_id,
            "expire_date": "",
            "message": "Hết hạn dùng thử. Vui lòng mua bản quyền.",
            "days_left": 0,
            "customer": ""
        }


def verify_license() -> tuple[bool, str]:
    """
    Kiểm tra bản quyền hợp lệ (bao gồm cả Bản quyền thật và Dùng thử Auto-Trial 30 ngày).
    """
    st = get_license_status()
    return st["ok"], st["machine_id"]


def save_license(target_id: str, key: str, lic_type: str = "MACHINE",
                 expire_date: str = "", plan: str = "", customer: str = "") -> bool:
    """Lưu license vào tất cả các vị trí bền vững trên máy tính sau khi kiểm tra chữ ký RSA hợp lệ."""
    valid, res_plan, res_exp, days_left, msg = _resolve_license_validity(target_id, key, expire_date)
    if not valid:
        return False

    payload = {
        "type": lic_type,
        "target_id": target_id.strip().upper(),
        "key": key.strip().upper(),
        "plan": plan or res_plan,
        "expire_date": res_exp,
        "customer": customer or "",
        "version": "3.0"
    }
    json_str = json.dumps(payload, ensure_ascii=False, indent=2)

    # 1. Lưu vào thư mục ứng dụng hiện tại
    try:
        lic_path = _license_path()
        lic_path.write_text(json_str, encoding="utf-8")
    except Exception:
        pass

    # 2. Lưu vào các vị trí bền vững của hệ thống (AppData / Home / Ổ phụ)
    for p in _get_persistent_license_paths():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
            if sys.platform == "win32" and ".pdf_ai_license_backup" in str(p):
                try:
                    ctypes.windll.kernel32.SetFileAttributesW(str(p.parent), 2)
                except Exception:
                    pass
        except Exception:
            pass

    # 3. Lưu vào Windows Registry (bền vững theo máy kể cả cài lại hay xóa folder)
    _write_registry_license(payload)
    return True


def import_license_file(src_path: str) -> bool:
    """Nhập trực tiếp file pdf_ai.lic do nhà cung cấp gửi (copy đè file cũ)."""
    p = Path(src_path).resolve()
    if not p.exists():
        return False
    try:
        content = json.loads(p.read_text(encoding="utf-8"))
        target_id = content.get("target_id", "")
        key = content.get("key", "")
        lic_type = content.get("type", "MACHINE")
        expire_date = content.get("expire_date", "")
        plan = content.get("plan", "")
        customer = content.get("customer", "")
        return save_license(target_id, key, lic_type, expire_date, plan, customer)
    except Exception:
        return False

