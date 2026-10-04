# -*- coding: utf-8 -*-
"""
Hằng số & tiện ích THUẦN (không phụ thuộc Qt) tách khỏi app.py để giảm kích thước và test được.
"""
import subprocess

# (mã chế độ cho marker_worker, nhãn hiển thị)
MODES = [
    ('rapid_ocr', '[Siêu tốc] OCR Tiếng Việt Chuyên ngành AEC – bản vẽ/scan (~3–5s/trang • Khuyên dùng)'),
    ('vn_ocr', '[Chuyên sâu] VLM Tiếng Việt Chi tiết – bản vẽ/scan (~15–40s/trang • cần GPU NVIDIA)'),
    ('fast_text', '[Siêu nhanh] PDF bản gõ / bản vẽ AutoCAD, tự đọc chữ SHX (~0.3–7s/trang)'),
    ('auto', '[Marker] AI phân tích bố cục + OCR (tài liệu văn bản, sách)'),
    ('ocr', '[Marker OCR] Nhận dạng AI toàn bộ trang'),
    ('text', '[Marker Text] Chỉ text Marker (không OCR)'),
]

_EXTS = ('.pdf', '.docx', '.xlsx', '.xlsm')


def detect_nvidia_gpu() -> str:
    """Tên GPU NVIDIA nếu có (qua nvidia-smi), '' nếu không."""
    try:
        r = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return ''
