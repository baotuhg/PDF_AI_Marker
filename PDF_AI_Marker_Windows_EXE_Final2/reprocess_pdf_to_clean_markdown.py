# -*- coding: utf-8 -*-
"""
Chạy pipeline PDF AI v3 từ dòng lệnh (cùng mã với ứng dụng).
Sử dụng:
    engine\\python.exe reprocess_pdf_to_clean_markdown.py "file.pdf" "thu_muc_xuat" [trang|all] [che_do]
      che_do: vn_ocr (mặc định, có dấu, cần GPU) | rapid_ocr | fast_text
Ví dụ:
    engine\\python.exe reprocess_pdf_to_clean_markdown.py "D:\\Downloads\\cầu môi\\Cầu thôn Khai Hoang 2, Km 14+363.65.pdf" "./output" "20-23"
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
site_packages = ROOT / "engine" / "Lib" / "site-packages"
for p in (ROOT, site_packages):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

import marker_worker


def process_pdf(pdf_path, output_dir, pages_str="", mode="vn_ocr"):
    from license_core import verify_license
    ok, _ = verify_license()
    if not ok:
        print("[LỖI BẢN QUYỀN] Phần mềm chưa được kích hoạt bản quyền. Vui lòng mở giao diện app.py để kích hoạt.")
        return False
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        print(f"[LỖI] Không tìm thấy file PDF: {pdf_path}")
        return False
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    session = Path(tempfile.mkdtemp(prefix="cli_"))
    try:
        marker_worker.configure(session)
        marker_worker.run({"source": str(pdf_path), "mode": mode, "pages": pages_str,
                           "session": str(session), "chunk_size": 3000}, session)
        shutil.copytree(session / "result", out_path, dirs_exist_ok=True)
    finally:
        marker_worker.stop_children()
        shutil.rmtree(session, ignore_errors=True)
    print(f"\n HOÀN TẤT. Kết quả: {out_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    args = sys.argv[1:]
    modes = {"vn_ocr", "rapid_ocr", "fast_text"}
    # PowerShell 5.1 bỏ mất tham số rỗng "" -> cho phép 'all' và cho phép bỏ qua trang
    if len(args) > 2 and args[2] in modes:
        args.insert(2, "all")
    pages = args[2] if len(args) > 2 else ""
    ok = process_pdf(args[0],
                     args[1] if len(args) > 1 else "./output_markdown",
                     "" if pages.lower() in ("all", "*", "-") else pages,
                     args[3] if len(args) > 3 else "vn_ocr")
    sys.exit(0 if ok else 1)
