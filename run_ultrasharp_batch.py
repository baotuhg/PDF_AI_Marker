# -*- coding: utf-8 -*-
"""
AEC GPU Ultra-Sharp DirectML Batch Re-Runner & Comparative Evaluator
PDF AI Marker v3 — Lite Edition (DirectML GPU Accelerated)
Tác giả: Kỹ sư Nguyễn Bảo Tú (23HG) — baotuhg@gmail.com

Chương trình tái bóc tách toàn bộ 25 bộ hồ sơ (1.392 trang) công trình Phố Bảng:
- Chạy trên GPU DirectML NVIDIA GeForce RTX 4070 Laptop (240 DPI, CLAHE clipLimit 2.5, det_limit 1536)
- Bóc tách ra thư mục độc lập KetQua_PhốBảng_UltraSharp
- So sánh A/B trực tiếp với kết quả chạy cũ (KetQua_TuHoc_PhốBảng - 200 DPI)
- Ghi nhật ký tiến độ liên tục vào ultrasharp_status.json và ultrasharp_rerun.log
"""
import sys
import os
import json
import time
from pathlib import Path

# Cấu hình đường dẫn thư viện Lite
LITE_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\PDF_AI_Marker_v3_Lite")
sys.path.insert(0, str(LITE_DIR))
sys.path.insert(0, str(LITE_DIR / "engine" / "Lib" / "site-packages"))

import pypdfium2 as pdfium
import marker_bridge
from experience_engine import get_experience_engine

SOURCE_DIR = Path(r"D:\Tú\Trường PTTHNT LCTH&THCS Phố Bảng\BV-DT\HS TK CÔNG TRÌNH PHỐ BẢNG\Hồ sơ thiết kế bản vẽ các hạng mục")
BASELINE_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\KetQua_TuHoc_PhốBảng")
OUTPUT_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\KetQua_PhốBảng_UltraSharp")
STATUS_FILE = Path(r"D:\Code\PDF_AI_Marker_v3\ultrasharp_status.json")
LOG_FILE = Path(r"D:\Code\PDF_AI_Marker_v3\ultrasharp_rerun.log")


def log_msg(msg: str):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def evaluate_doc_dir(doc_folder: Path):
    """Trích xuất các chỉ số chất lượng của 1 tài liệu sau bóc tách."""
    marker_dirs = list(doc_folder.glob("*_Marker"))
    if not marker_dirs:
        return None
    m = marker_dirs[0]

    warn_count = 0
    warn_file = m / "can_kiem_tra.md"
    if warn_file.exists():
        lines = [l for l in warn_file.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip().startswith("- `")]
        warn_count = len(lines)

    bars_count = 0
    thep_file = m / "thep_cho_to_hop_cat.json"
    if thep_file.exists():
        try:
            data = json.loads(thep_file.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, dict):
                bars_count = len(data.get("thanh_thep", data.get("items", [])))
            elif isinstance(data, list):
                bars_count = len(data)
        except Exception:
            pass

    tables_count = 0
    bang_file = m / "bang_so_lieu.json"
    if bang_file.exists():
        try:
            data = json.loads(bang_file.read_text(encoding="utf-8", errors="ignore"))
            tables_count = len(data) if isinstance(data, list) else len(data.get("tables", []))
        except Exception:
            pass

    md_chars = 0
    md_file = m / "noi_dung.md"
    if md_file.exists():
        md_chars = len(md_file.read_text(encoding="utf-8", errors="ignore"))

    xlsx_size = 0
    xlsx_file = m / "bang_so_lieu.xlsx"
    if xlsx_file.exists():
        xlsx_size = xlsx_file.stat().st_size

    return {
        "warnings": warn_count,
        "rebar_bars": bars_count,
        "tables": tables_count,
        "md_chars": md_chars,
        "xlsx_size": xlsx_size,
        "completed": md_chars > 500 and xlsx_size > 1000
    }


def is_already_done(doc_folder: Path) -> bool:
    metrics = evaluate_doc_dir(doc_folder)
    return metrics is not None and metrics.get("completed", False)


def get_all_pdfs_sorted():
    all_pdfs = list(SOURCE_DIR.glob("*.pdf"))
    items = []
    for f in all_pdfs:
        try:
            d = pdfium.PdfDocument(str(f))
            p = len(d)
        except Exception:
            p = 9999
        items.append((f, p, f.stat().st_size / 1024 / 1024))
    items.sort(key=lambda x: x[1])
    return items


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_list = get_all_pdfs_sorted()
    total_files = len(pdf_list)
    total_pages = sum(p for _, p, _ in pdf_list)

    log_msg("=" * 80)
    log_msg("🚀 BẮT ĐẦU CHẠY RE-RUN 25 HỒ SƠ VỚI BỘ MÁY GPU ULTRA-SHARP DIRECTML (240 DPI)")
    log_msg(f"📂 Thư mục nguồn: {SOURCE_DIR}")
    log_msg(f"📂 Thư mục đích : {OUTPUT_DIR}")
    log_msg(f"📊 Tổng số hồ sơ: {total_files} hồ sơ | Tổng số trang: {total_pages} trang")
    log_msg("=" * 80)

    # Đọc trạng thái cũ nếu có
    status_data = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": total_files,
        "total_pages": total_pages,
        "completed_files": 0,
        "completed_pages": 0,
        "results": []
    }
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if loaded.get("results"):
                    status_data["results"] = loaded["results"]
        except Exception:
            pass

    exp_engine = get_experience_engine()

    batch_start = time.time()

    for idx, (pdf_file, pages, mb) in enumerate(pdf_list, 1):
        doc_out = OUTPUT_DIR / pdf_file.stem
        baseline_folder = BASELINE_DIR / pdf_file.stem
        baseline_metrics = evaluate_doc_dir(baseline_folder) if baseline_folder.exists() else None

        log_msg("-" * 80)
        log_msg(f"📄 [HỒ SƠ {idx:02d}/{total_files:02d}] {pdf_file.name}")
        log_msg(f"   Quy mô: {pages} trang | Dung lượng: {mb:.2f} MB")

        # Kiểm tra xem đã hoàn thành từ lượt chạy trước chưa (cho phép resume nếu dừng đột ngột)
        if is_already_done(doc_out):
            curr_metrics = evaluate_doc_dir(doc_out)
            log_msg(f"   ⏩ Đã bóc tách xong trước đó. Bỏ qua để tiết kiệm thời gian.")
            if baseline_metrics and curr_metrics:
                warn_diff = curr_metrics["warnings"] - baseline_metrics["warnings"]
                rebar_diff = curr_metrics["rebar_bars"] - baseline_metrics["rebar_bars"]
                tbl_diff = curr_metrics["tables"] - baseline_metrics["tables"]
                log_msg(f"   📊 [So sánh] Cần KT: {curr_metrics['warnings']} (cũ {baseline_metrics['warnings']}, delta: {warn_diff:+d}) | Thép: {curr_metrics['rebar_bars']} (cũ {baseline_metrics['rebar_bars']}, delta: {rebar_diff:+d}) | Bảng: {curr_metrics['tables']} (cũ {baseline_metrics['tables']}, delta: {tbl_diff:+d})")
            continue

        doc_out.mkdir(parents=True, exist_ok=True)
        t0 = time.time()

        def on_progress(pct, total, msg):
            if pct % 20 == 0 or "Hoàn tất" in msg or "Định vị chữ" in msg:
                log_msg(f"   [{pct:3d}%] {msg}")

        try:
            target, payload, markdown = marker_bridge.convert(
                source=str(pdf_file),
                destination=str(doc_out),
                mode="rapid_ocr",
                chunk_size=3000,
                progress=on_progress
            )
            dt = time.time() - t0
            speed = pages / dt if dt > 0 else 0
            log_msg(f"   ✅ Bóc tách thành công trong {dt:.1f}s (~{dt/pages:.2f}s/trang, tốc độ: {speed*60:.1f} trang/phút)!")

            # Thu thập chỉ số chất lượng
            curr_metrics = evaluate_doc_dir(doc_out)
            if curr_metrics and baseline_metrics:
                warn_old = baseline_metrics["warnings"]
                warn_new = curr_metrics["warnings"]
                warn_delta = warn_new - warn_old
                warn_pct = ((warn_new - warn_old) / warn_old * 100) if warn_old > 0 else 0

                bar_old = baseline_metrics["rebar_bars"]
                bar_new = curr_metrics["rebar_bars"]
                bar_delta = bar_new - bar_old

                tbl_old = baseline_metrics["tables"]
                tbl_new = curr_metrics["tables"]
                tbl_delta = tbl_new - tbl_old

                log_msg(f"   🎯 ĐỐI CHIẾU TRỰC TIẾP VỚI BẢN CŨ (200 DPI vs 240 DPI GPU):")
                log_msg(f"      • Cảnh báo nghi ngờ (cần kiểm tra): {warn_old} -> {warn_new} ({warn_delta:+d} dòng, {warn_pct:+.1f}%)")
                log_msg(f"      • Cốt thép phát hiện: {bar_old} -> {bar_new} thanh ({bar_delta:+d} thanh)")
                log_msg(f"      • Bảng số liệu: {tbl_old} -> {tbl_new} bảng ({tbl_delta:+d} bảng)")
                log_msg(f"      • Ký tự Markdown: {baseline_metrics['md_chars']:,} -> {curr_metrics['md_chars']:,} ký tự")

            # Cập nhật status
            status_entry = {
                "document": pdf_file.name,
                "pages": pages,
                "elapsed_sec": round(dt, 1),
                "metrics_240dpi": curr_metrics,
                "metrics_200dpi_baseline": baseline_metrics
            }
            # Ghi đè hoặc thêm mới
            status_data["results"] = [r for r in status_data["results"] if r.get("document") != pdf_file.name]
            status_data["results"].append(status_entry)
            status_data["completed_files"] = len(status_data["results"])
            status_data["completed_pages"] = sum(r.get("pages", 0) for r in status_data["results"])

            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            log_msg(f"   ❌ LỖI KHI XỬ LÝ '{pdf_file.name}': {e}")
            import traceback
            log_msg(traceback.format_exc())

    total_batch_time = time.time() - batch_start
    log_msg("=" * 80)
    log_msg(f"🏁 ĐÃ HOÀN THÀNH TOÀN BỘ CHU TRÌNH RE-RUN TRONG {total_batch_time:.1f}s ({total_batch_time/60:.1f} phút)!")
    log_msg("=" * 80)


if __name__ == "__main__":
    main()
