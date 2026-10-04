# -*- coding: utf-8 -*-
import json
from pathlib import Path

def evaluate_folder(folder_path):
    base = Path(folder_path)
    results = []
    total_warn = 0
    total_bars = 0
    total_tables = 0
    total_md_chars = 0

    if not base.exists():
        print(f"Folder not found: {base}")
        return {}

    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        marker_dirs = list(d.glob("*_Marker"))
        if not marker_dirs:
            continue
        m = marker_dirs[0]
        
        warn_file = m / "can_kiem_tra.md"
        warn_count = 0
        if warn_file.exists():
            lines = [l for l in warn_file.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip().startswith("- `")]
            warn_count = len(lines)
        
        thep_file = m / "thep_cho_to_hop_cat.json"
        bars = 0
        if thep_file.exists():
            try:
                data = json.loads(thep_file.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(data, dict):
                    bars = len(data.get("thanh_thep", data.get("items", [])))
                elif isinstance(data, list):
                    bars = len(data)
            except Exception:
                pass

        bang_file = m / "bang_so_lieu.json"
        tables = 0
        if bang_file.exists():
            try:
                data = json.loads(bang_file.read_text(encoding="utf-8", errors="ignore"))
                tables = len(data) if isinstance(data, list) else len(data.get("tables", []))
            except Exception:
                pass

        md_file = m / "noi_dung.md"
        md_chars = 0
        if md_file.exists():
            md_chars = len(md_file.read_text(encoding="utf-8", errors="ignore"))

        results.append({
            "name": d.name,
            "warnings": warn_count,
            "rebar": bars,
            "tables": tables,
            "md_chars": md_chars
        })
        total_warn += warn_count
        total_bars += bars
        total_tables += tables
        total_md_chars += md_chars

    summary = {
        "folder": str(base),
        "total_docs": len(results),
        "total_warnings": total_warn,
        "total_rebar": total_bars,
        "total_tables": total_tables,
        "total_md_chars": total_md_chars,
        "details": results
    }
    return summary

if __name__ == "__main__":
    baseline = evaluate_folder(r"D:\Code\PDF_AI_Marker_v3\KetQua_TuHoc_PhốBảng")
    print(f"BASELINE SUMMARY (200 DPI):")
    print(f"Total documents: {baseline.get('total_docs')}")
    print(f"Total warnings: {baseline.get('total_warnings')}")
    print(f"Total rebar bars: {baseline.get('total_rebar')}")
    print(f"Total tables: {baseline.get('total_tables')}")
    print(f"Total Markdown characters: {baseline.get('total_md_chars'):,}")
    print("-" * 80)
    for r in baseline.get("details", []):
        print(f"{r['name'][:42]:<42} | Cần KT: {r['warnings']:<4} | Thép: {r['rebar']:<4} | Bảng: {r['tables']:<3} | Chars: {r['md_chars']:,}")
