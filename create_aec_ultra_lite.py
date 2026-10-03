"""
create_aec_ultra_lite.py — Khởi tạo bản phân phối siêu tinh gọn PDF AI Marker v3 Lite (~350 MB)
Tác giả: Nguyễn Bảo Tú (23HG)
"""

import os
import shutil
import sys
from pathlib import Path

SRC_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\PDF_AI_Marker_Windows_EXE_Final2")
DEST_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\PDF_AI_Marker_v3_Lite")

# Danh sách tiền tố các package site-packages BẮT BUỘC cho AEC Hybrid Pipeline
ESSENTIAL_PACKAGES = [
    "pypdfium2",
    "rapidocr_onnxruntime",
    "onnxruntime",
    "cv2",
    "opencv",
    "numpy",
    "openpyxl",
    "et_xmlfile",
    "docx",
    "python_docx",
    "cryptography",
    "requests",
    "urllib3",
    "certifi",
    "idna",
    "charset_normalizer",
    "shapely",
    "pyclipper",
    "PIL",
    "pillow",
    "yaml",
    "pyyaml",
    "pdftext",
    "xlsxwriter",
    "psutil",
    "pydantic",
    "pydantic_core",
    "typing_extensions",
    "annotated_types",
    "packaging",
    "pyasn1",
    "cffi",
    "pycparser",
]

def copy_file_or_dir(src: Path, dest: Path):
    if not src.exists():
        return
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

def build_lite():
    print(f"🚀 Bắt đầu khởi tạo bản phân phối siêu tinh gọn: {DEST_DIR}")
    if DEST_DIR.exists():
        print(f"[*] Dọn dẹp thư mục cũ {DEST_DIR}...")
        shutil.rmtree(DEST_DIR)
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy thư mục GUI _internal (chứa PySide6 & Qt runtime)
    print("[1/5] Sao chép giao diện Fluent UI _internal...")
    src_internal = SRC_DIR / "_internal"
    dest_internal = DEST_DIR / "_internal"
    if src_internal.exists():
        shutil.copytree(src_internal, dest_internal)

    # 2. Copy Python Base Interpreter (python.exe, dlls, Lib chuẩn)
    print("[2/5] Sao chép Python Runtime cốt lõi...")
    src_engine = SRC_DIR / "engine"
    dest_engine = DEST_DIR / "engine"
    dest_engine.mkdir(parents=True, exist_ok=True)

    # Copy files ở gốc engine
    for f in src_engine.glob("*.*"):
        shutil.copy2(f, dest_engine / f.name)

    # Copy DLLs
    if (src_engine / "DLLs").exists():
        shutil.copytree(src_engine / "DLLs", dest_engine / "DLLs")

    # Copy Lib chuẩn (bỏ qua site-packages trước)
    src_lib = src_engine / "Lib"
    dest_lib = dest_engine / "Lib"
    dest_lib.mkdir(parents=True, exist_ok=True)
    for item in src_lib.iterdir():
        if item.name.lower() == "site-packages":
            continue
        copy_file_or_dir(item, dest_lib / item.name)

    # 3. Lọc và copy chỉ các package thiết yếu trong site-packages
    print("[3/5] Lọc và sao chép site-packages thiết yếu (Loại bỏ PyTorch 3.6GB, Transformers, Surya)...")
    src_sp = src_lib / "site-packages"
    dest_sp = dest_lib / "site-packages"
    dest_sp.mkdir(parents=True, exist_ok=True)

    copied_pkgs = 0
    copied_bytes = 0
    for item in src_sp.iterdir():
        name_lower = item.name.lower()
        match = any(name_lower.startswith(pkg.lower()) for pkg in ESSENTIAL_PACKAGES)
        if match:
            copy_file_or_dir(item, dest_sp / item.name)
            copied_pkgs += 1
            if item.is_file():
                copied_bytes += item.stat().st_size
            else:
                for sub in item.rglob("*"):
                    if sub.is_file():
                        copied_bytes += sub.stat().st_size

    print(f"  -> Đã copy {copied_pkgs} gói thiết yếu ({copied_bytes / 1024 / 1024:.1f} MB)")

    # 4. Copy mã nguồn ứng dụng và tài nguyên
    print("[4/5] Sao chép mã nguồn AEC Pipeline & Tài nguyên...")
    source_files = [
        "PDF_AI_Marker.exe",
        "app.py",
        "marker_bridge.py",
        "marker_worker.py",
        "layout_reconstructor.py",
        "vn_diacritics.py",
        "vn_refine.py",
        "ocr_tiling.py",
        "license_core.py",
        "license_dialog.py",
        "license_cloud.py",
        "fluent_theme.py",
        "theme_config.json",
        "cloud_config.json",
        "pdf_ai.lic",
        "table_agent.py",
        "md_postprocess.py",
        "app_icon.png",
        "app_icon.ico",
        "app_preview.png",
        "inspector_preview.png",
        "chat_preview.png",
        "license_preview.png",
        "fluent_ui_dark.png",
        "fluent_ui_light.png",
        "fluent_ui_tables.png",
        "fluent_ui_license.png",
        "HUONG_DAN_SU_DUNG.txt",
    ]

    for fname in source_files:
        src_f = SRC_DIR / fname
        if src_f.exists():
            shutil.copy2(src_f, DEST_DIR / fname)

    # 5. Tạo file kích hoạt nhanh .bat
    print("[5/5] Tạo file khởi chạy tiện lợi...")
    bat_content = (
        "@echo off\r\n"
        "title PDF AI Marker v3 Lite (AEC Ultra-Fast Edition)\r\n"
        "cd /d \"%~dp0\"\r\n"
        "start \"\" \"PDF_AI_Marker.exe\"\r\n"
    )
    (DEST_DIR / "Chay_PDF_AI_Marker_Lite.bat").write_text(bat_content, encoding="utf-8")

    # Đo tổng dung lượng
    total_size = sum(f.stat().st_size for f in DEST_DIR.rglob("*") if f.is_file())
    print("\n" + "="*50)
    print(f"🎉 HOÀN THÀNH KHỞI TẠO BẢN LITE!")
    print(f"📁 Thư mục mới: {DEST_DIR}")
    print(f"📦 Tổng dung lượng thư mục mới: {total_size / 1024 / 1024:.1f} MB (chỉ ~{total_size / 1024 / 1024 / 1024:.2f} GB)")
    print(f"📉 So với bản cũ (7.5 GB), dung lượng đã GIẢM: {(1 - total_size / (7.5 * 1024 * 1024 * 1024)) * 100:.1f}%")
    print("="*50)

if __name__ == "__main__":
    build_lite()
