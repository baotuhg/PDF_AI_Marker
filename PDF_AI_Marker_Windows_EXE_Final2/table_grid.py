# -*- coding: utf-8 -*-
"""
Phát hiện bảng có đường kẻ ô (ruled table) trên ảnh trang bằng OpenCV.

Bảng trong hồ sơ xây dựng (thống kê cốt thép, khối lượng, khung tên...) hầu
như luôn có lưới kẻ. Dựa vào lưới cho ra ranh giới hàng/cột CHÍNH XÁC, tốt hơn
nhiều so với đoán cột theo tọa độ chữ.

Thuật toán:
1. Nhị phân hóa, tách đường ngang/dọc bằng phép mở hình thái.
2. Các "lỗ" hình chữ nhật trong mặt nạ lưới = ô bảng.
3. Gom các ô chạm cạnh nhau thành nhóm (union-find) = một bảng.
4. Ranh giới hàng/cột = các cạnh ô gom cụm theo dung sai.

Mọi tọa độ trả về đã quy đổi sang hệ tọa độ cơ sở (nhân với `factor`).
"""
from typing import Any, Dict, List


def _cluster_edges(values: List[float], tol: float) -> List[float]:
    values = sorted(values)
    clusters: List[List[float]] = []
    for v in values:
        if clusters and v - clusters[-1][-1] <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return [sum(c) / len(c) for c in clusters]


def _close_open_ends(vert, horiz, unit: float) -> None:
    """Bảng bị cắt sang trang sau thường không có đường kẻ đáy (hoặc đỉnh) nên ô
    thân bảng hở. Nếu >= 3 đường dọc kết thúc ở cùng độ cao thì vẽ thêm một đường
    ngang nối các đầu đó để khép ô."""
    import cv2
    n, _, stats, _ = cv2.connectedComponentsWithStats(vert, connectivity=8)
    segs = [(stats[i][0], stats[i][1], stats[i][1] + stats[i][3]) for i in range(1, n)
            if stats[i][3] >= 60 * unit]
    tol = 6 * unit
    thickness = max(1, int(round(2 * unit)))
    for end in (2, 1):                              # 2 = đầu dưới, 1 = đầu trên
        for y in _cluster_edges([s[end] for s in segs], tol):
            xs = [s[0] for s in segs if abs(s[end] - y) <= tol]
            if len(xs) >= 3:
                yy = int(round(y)) - (1 if end == 2 else 0)
                cv2.line(horiz, (int(min(xs)), yy), (int(max(xs)), yy), 255, thickness)


def detect_ruled_tables(image, factor: float = 1.0, dpi: float = 200.0,
                        allow_tall: bool = False) -> List[Dict[str, Any]]:
    """Trả về [{bbox, row_edges, col_edges, cells}] theo hệ tọa độ cơ sở.

    allow_tall=True: nhận cả ô rất cao (bảng Excel chỉ kẻ đường dọc, các dòng
    không có đường kẻ ngang). Chỉ bật cho trang văn bản, không bật cho bản vẽ
    CAD vì khung hình vẽ lớn sẽ bị nhận nhầm là ô bảng.
    """
    try:
        import cv2
        import numpy as np
    except Exception:
        return []

    gray = np.array(image.convert("L"))
    H, W = gray.shape
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, 25, 15)
    unit = dpi / 200.0
    hk, vk = max(15, int(40 * unit)), max(15, int(30 * unit))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hk, 1)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vk)))
    if allow_tall:
        _close_open_ends(vert, horiz, unit)
    grid = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((3, 3), np.uint8))

    contours, hierarchy = cv2.findContours(grid, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []

    # Ô bảng: lỗ (contour con) gần như chữ nhật, kích thước vừa với 1 ô chữ
    min_h, max_h = 12 * unit, (H * 0.95 if allow_tall else min(H * 0.25, 400 * unit))
    min_w, max_w = 12 * unit, W * 0.6
    cells = []
    for idx, cnt in enumerate(contours):
        if hierarchy[0][idx][3] < 0:          # chỉ lấy lỗ bên trong
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if not (min_h <= h <= max_h and min_w <= w <= max_w):
            continue
        if cv2.contourArea(cnt) < 0.80 * w * h:
            continue
        cells.append((x, y, x + w, y + h))
    if len(cells) < 4:
        return []

    # Gom ô chạm nhau (cách nhau <= độ dày nét kẻ) thành bảng
    gap = 8 * unit
    parent = list(range(len(cells)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(len(cells)), key=lambda i: cells[i][0])
    for a_pos, a in enumerate(order):
        ax0, ay0, ax1, ay1 = cells[a]
        for b in order[a_pos + 1:]:
            bx0, by0, bx1, by1 = cells[b]
            if bx0 > ax1 + gap:
                break
            if by0 <= ay1 + gap and ay0 <= by1 + gap:
                parent[find(a)] = find(b)

    groups: Dict[int, List[int]] = {}
    for i in range(len(cells)):
        groups.setdefault(find(i), []).append(i)

    tol = 6 * unit
    tables = []
    for members in groups.values():
        if len(members) < 4:
            continue
        cs = [cells[i] for i in members]
        row_edges = _cluster_edges([c[1] for c in cs] + [c[3] for c in cs], tol)
        col_edges = _cluster_edges([c[0] for c in cs] + [c[2] for c in cs], tol)
        if len(col_edges) < 3:                         # >= 2 cột
            continue
        # >= 2 hàng kẻ; riêng bảng chỉ kẻ cột (ô cao) chấp nhận 1 hàng nếu >= 3 cột
        if len(row_edges) < 3 and not (allow_tall and len(col_edges) >= 4):
            continue
        x0 = min(c[0] for c in cs); y0 = min(c[1] for c in cs)
        x1 = max(c[2] for c in cs); y1 = max(c[3] for c in cs)
        tables.append({
            "bbox": [x0 * factor, y0 * factor, x1 * factor, y1 * factor],
            "row_edges": [v * factor for v in row_edges],
            "col_edges": [v * factor for v in col_edges],
            "cells": [[c[0] * factor, c[1] * factor, c[2] * factor, c[3] * factor] for c in cs],
        })
    tables.sort(key=lambda t: (t["bbox"][1], t["bbox"][0]))
    return tables
