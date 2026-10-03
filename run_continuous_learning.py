# -*- coding: utf-8 -*-
"""
AEC Continuous Learning & Self-Improving Pipeline Runner
PDF AI Marker v3 — Lite Edition
Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG) — baotuhg@gmail.com

Chương trình tự động chạy học tập lũy tiến qua các hồ sơ bản vẽ/dự toán:
- Đọc từng hồ sơ bằng bản Lite (DirectML + CLAHE + Diacritics).
- Tự động đúc rút bài học (kinh nghiệm OCR, từ vựng kỹ thuật, mẫu bảng biểu).
- Tích lũy bài học vào experience_db.json và nạp ngay cho hồ sơ tiếp theo.
- Mô phỏng quá trình lớn lên của hệ thống như một đứa trẻ qua từng lần dạy.
"""
import sys
import os
import json
import time
from pathlib import Path

# Cấu hình đường dẫn thư viện
LITE_DIR = Path(r"d:\Code\PDF_AI_Marker_v3\PDF_AI_Marker_v3_Lite")
sys.path.insert(0, str(LITE_DIR))
sys.path.insert(0, str(LITE_DIR / "engine" / "Lib" / "site-packages"))

from experience_engine import get_experience_engine
import marker_bridge


def run_learning_cycle(file_list, output_base_dir):
    out_dir = Path(output_base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = get_experience_engine()

    print("=" * 70)
    print("🚀 BẮT ĐẦU CHU TRÌNH TỰ TIẾN HÓA & ĐÚC RÚT KINH NGHIỆM (AEC SELF-LEARNING)")
    print("=" * 70)
    print(f"📂 Thư mục xuất kết quả: {out_dir}")
    print(f"📚 Trạng thái ban đầu của bộ não: {len(engine.knowledge['learned_phrases'])} thuật ngữ, {len(engine.knowledge['unsticking_rules'])} luật tách từ\n")

    start_total = time.time()

    for idx, pdf_path in enumerate(file_list, 1):
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            print(f"❌ Không tìm thấy: {pdf_file}")
            continue

        print("-" * 70)
        print(f"📖 [HỒ SƠ {idx}/{len(file_list)}] BẮT ĐẦU ĐỌC: '{pdf_file.name}'")
        print(f"   Dung lượng: {pdf_file.stat().st_size / (1024*1024):.2f} MB")
        
        engine.load_db()
        already_learned = any(h.get("document") == pdf_file.name for h in engine.knowledge.get("history_log", []))
        if already_learned:
            print(f"   ⏩ Đã học hồ sơ '{pdf_file.name}' ở Epoch trước, chuyển tiếp sang hồ sơ mới...")
            continue

        t0 = time.time()
        doc_out = out_dir / pdf_file.stem
        doc_out.mkdir(parents=True, exist_ok=True)

        # Chạy bóc tách bằng bản Lite
        try:
            marker_bridge.convert(
                source=str(pdf_file),
                destination=str(doc_out),
                mode="rapid_ocr",
                chunk_size=3000,
                progress=lambda pct, total, msg: print(f"   [{pct:3d}%] {msg}") if pct % 20 == 0 or "Tiến hóa" in msg or "Tự học" in msg else None
            )
        except Exception as e:
            print(f"   ⚠️ Lỗi trong quá trình xử lý: {e}")
            continue

        dt = time.time() - t0
        print(f"   ✅ Đọc xong trong {dt:.1f}s!")

        # Tải lại cơ sở dữ liệu kinh nghiệm mới nhất từ worker
        engine.load_db()
        exp_db = engine.knowledge
        latest_epoch = exp_db["history_log"][-1] if exp_db["history_log"] else None
        if latest_epoch:
            lessons = latest_epoch.get("lessons_learned", {})
            cum = latest_epoch.get("cumulative_memory", {})
            print(f"   🎓 ĐÚC RÚT BÀI HỌC TỪ HỒ SƠ NÀY:")
            print(f"      • Thuật ngữ chuyên sâu mới học: +{lessons.get('new_phrases', 0)}")
            print(f"      • Quy tắc tách từ dính scan mới: +{lessons.get('new_unstick', 0)}")
            print(f"      • Từ viết tắt kỹ thuật giải mã: +{lessons.get('new_abbr', 0)}")
            print(f"      • Biến thể tiêu đề bảng BoQ/Thép: +{lessons.get('new_headers', 0)}")
            print(f"   🧠 TỔNG DUNG LƯỢNG BỘ NÃO TÍCH LŨY HIỆN TẠI:")
            print(f"      -> Vốn từ vựng: {cum.get('phrases', 0)} thuật ngữ")
            print(f"      -> Luật unstick: {cum.get('unstick_rules', 0)} quy tắc")
            print(f"      -> Bộ não đã nạp sẵn kinh nghiệm này cho hồ sơ tiếp theo! ⚡")

    total_time = time.time() - start_total
    print("\n" + "=" * 70)
    print(f"🎉 HOÀN THÀNH CHU TRÌNH TỰ TIẾN HÓA TRONG {total_time:.1f} GIÂY!")
    print("=" * 70)
    print(engine.get_summary_report())


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
        files = sorted(folder.glob("*.pdf"))
    else:
        # Đọc toàn bộ file trong thư mục công trình Phố Bảng
        base = Path(r"D:\Tú\Trường PTTHNT LCTH&THCS Phố Bảng\BV-DT\HS TK CÔNG TRÌNH PHỐ BẢNG\Hồ sơ thiết kế bản vẽ các hạng mục")
        all_pdfs = list(base.glob("*.pdf"))
        
        # Sắp xếp hồ sơ từ ít trang đến nhiều trang (từ dễ đến khó để bộ não tích lũy dần)
        import pypdfium2 as pdfium
        def get_page_count(f):
            try:
                d = pdfium.PdfDocument(str(f))
                return len(d)
            except Exception:
                return 9999
        all_pdfs.sort(key=get_page_count)
        files = all_pdfs
    
    out_dir = Path(r"D:\Code\PDF_AI_Marker_v3\KetQua_TuHoc_PhốBảng")
    run_learning_cycle(files, out_dir)
