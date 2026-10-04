# -*- coding: utf-8 -*-
"""
AEC Automated A/B Evaluation Report Generator
So sánh chi tiết 25 bộ hồ sơ (1.392 trang) công trình Phố Bảng:
Baseline (200 DPI) vs Ultra-Sharp GPU DirectML (240 DPI)
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\KetQua_TuHoc_PhốBảng")
ULTRA_DIR = Path(r"D:\Code\PDF_AI_Marker_v3\KetQua_PhốBảng_UltraSharp")
STATUS_FILE = Path(r"D:\Code\PDF_AI_Marker_v3\ultrasharp_status.json")

def analyze_folder(m_dir):
    warn_count = 0
    warn_f = m_dir / "can_kiem_tra.md"
    if warn_f.exists():
        lines = [l for l in warn_f.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip().startswith("- `")]
        warn_count = len(lines)

    bars_count = 0
    thep_f = m_dir / "thep_cho_to_hop_cat.json"
    if thep_f.exists():
        try:
            d = json.loads(thep_f.read_text(encoding="utf-8", errors="ignore"))
            bars_count = len(d.get("thanh_thep", d.get("items", []))) if isinstance(d, dict) else len(d)
        except Exception:
            pass

    tbl_count = 0
    tbl_f = m_dir / "bang_so_lieu.json"
    if tbl_f.exists():
        try:
            d = json.loads(tbl_f.read_text(encoding="utf-8", errors="ignore"))
            tbl_count = len(d) if isinstance(d, list) else len(d.get("tables", []))
        except Exception:
            pass

    md_chars = 0
    md_f = m_dir / "noi_dung.md"
    if md_f.exists():
        md_chars = len(md_f.read_text(encoding="utf-8", errors="ignore"))

    xlsx_size = 0
    xlsx_f = m_dir / "bang_so_lieu.xlsx"
    if xlsx_f.exists():
        xlsx_size = xlsx_f.stat().st_size

    return {
        "warn": warn_count,
        "rebar": bars_count,
        "tables": tbl_count,
        "chars": md_chars,
        "xlsx_size": xlsx_size,
    }

def main():
    docs = sorted([d.name for d in BASE_DIR.iterdir() if d.is_dir()])
    rows = []

    tot_warn_base, tot_warn_ultra = 0, 0
    tot_rebar_base, tot_rebar_ultra = 0, 0
    tot_tbl_base, tot_tbl_ultra = 0, 0
    tot_chars_base, tot_chars_ultra = 0, 0

    for doc_name in docs:
        b_marker = list((BASE_DIR / doc_name).glob("*_Marker"))
        u_marker = list((ULTRA_DIR / doc_name).glob("*_Marker"))

        b_stat = analyze_folder(b_marker[0]) if b_marker else {"warn": 0, "rebar": 0, "tables": 0, "chars": 0, "xlsx_size": 0}
        u_stat = analyze_folder(u_marker[0]) if u_marker else {"warn": 0, "rebar": 0, "tables": 0, "chars": 0, "xlsx_size": 0}

        tot_warn_base += b_stat["warn"]
        tot_warn_ultra += u_stat["warn"]
        tot_rebar_base += b_stat["rebar"]
        tot_rebar_ultra += u_stat["rebar"]
        tot_tbl_base += b_stat["tables"]
        tot_tbl_ultra += u_stat["tables"]
        tot_chars_base += b_stat["chars"]
        tot_chars_ultra += u_stat["chars"]

        rows.append({
            "name": doc_name,
            "b_warn": b_stat["warn"], "u_warn": u_stat["warn"],
            "b_rebar": b_stat["rebar"], "u_rebar": u_stat["rebar"],
            "b_tbl": b_stat["tables"], "u_tbl": u_stat["tables"],
            "b_chars": b_stat["chars"], "u_chars": u_stat["chars"],
            "u_xlsx": u_stat["xlsx_size"]
        })

    print("=" * 110)
    print("📊 BẢNG TỔNG HỢP SO SÁNH ĐỐI CHỨNG A/B TOÀN DIỆN (25 HỒ SƠ - 1.392 TRANG)")
    print("=" * 110)
    header = f"{'STT':<4} | {'Tên Hồ Sơ':<36} | {'Cần KT (Cũ->Mới)':<17} | {'Thép (Cũ->Mới)':<15} | {'Bảng (Cũ->Mới)':<15} | {'Ký tự MD':<16}"
    print(header)
    print("-" * 110)

    for i, r in enumerate(rows, 1):
        w_d = r['u_warn'] - r['b_warn']
        w_s = f"{r['b_warn']:>3} -> {r['u_warn']:>3} ({w_d:+3d})"
        rb_d = r['u_rebar'] - r['b_rebar']
        rb_s = f"{r['b_rebar']:>3} -> {r['u_rebar']:>3} ({rb_d:+3d})"
        t_d = r['u_tbl'] - r['b_tbl']
        t_s = f"{r['b_tbl']:>3} -> {r['u_tbl']:>3} ({t_d:+3d})"
        c_s = f"{r['u_chars']:,}"
        name_trunc = r['name'][:35]
        print(f"{i:<4} | {name_trunc:<36} | {w_s:<17} | {rb_s:<15} | {t_s:<15} | {c_s:<16}")

    print("-" * 110)
    print(f"TỔNG CỘNG (25 HỒ SƠ):")
    print(f"  • Cảnh báo nghi ngờ (cần kiểm tra) : {tot_warn_base:,} -> {tot_warn_ultra:,} ({tot_warn_ultra - tot_warn_base:+d} dòng, {(tot_warn_ultra - tot_warn_base)/tot_warn_base*100:+.2f}%)")
    print(f"  • Cốt thép phát hiện (BBS)         : {tot_rebar_base:,} -> {tot_rebar_ultra:,} ({tot_rebar_ultra - tot_rebar_base:+d} thanh, {(tot_rebar_ultra - tot_rebar_base)/tot_rebar_base*100:+.2f}%)")
    print(f"  • Bảng biểu kỹ thuật trích xuất   : {tot_tbl_base:,} -> {tot_tbl_ultra:,} ({tot_tbl_ultra - tot_tbl_base:+d} bảng, {(tot_tbl_ultra - tot_tbl_base)/tot_tbl_base*100:+.2f}%)")
    print(f"  • Tổng ký tự văn bản bóc tách      : {tot_chars_base:,} -> {tot_chars_ultra:,} ({tot_chars_ultra - tot_chars_base:+d} ký tự, {(tot_chars_ultra - tot_chars_base)/tot_chars_base*100:+.2f}%)")
    print("=" * 110)

if __name__ == "__main__":
    main()
