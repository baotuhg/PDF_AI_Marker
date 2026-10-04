# -*- coding: utf-8 -*-
"""
Logger dùng chung cho PDF AI Marker.

Mục tiêu: thay cho các 'except: pass' IM LẶNG. Lỗi vẫn được nuốt để ứng dụng chạy tiếp
(không làm đổi luồng), NHƯNG được GHI LẠI vào file để còn chẩn đoán khi khách gặp sự cố.

Chỉ dùng thư viện chuẩn, import nhẹ, tuyệt đối không làm app lỗi nếu không ghi được log.
Cách dùng:
    from app_log import get_logger
    log = get_logger(__name__)
    try:
        ...
    except Exception as e:
        log.debug("Ngữ cảnh gì đó: %s", e)   # vẫn tiếp tục fallback như cũ
"""
import logging
import sys
from pathlib import Path

_CONFIGURED = False


def _log_dir() -> Path:
    """Thư mục ghi log: cạnh exe/mã nguồn; nếu không được thì dùng thư mục tạm."""
    try:
        base = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
                else Path(__file__).resolve().parent)
        d = base / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        import tempfile
        d = Path(tempfile.gettempdir()) / "pdf_ai_logs"
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return d


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True
    try:
        from logging.handlers import RotatingFileHandler
        handler = RotatingFileHandler(
            _log_dir() / "pdf_ai.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger("pdf_ai")
        root.setLevel(logging.DEBUG)
        if not root.handlers:
            root.addHandler(handler)
        root.propagate = False
    except Exception:
        # Không ghi được file log cũng KHÔNG được làm app lỗi.
        pass


def get_logger(name: str = "pdf_ai") -> logging.Logger:
    _configure()
    short = "pdf_ai" if name in (None, "", "__main__") else f"pdf_ai.{str(name).split('.')[-1]}"
    return logging.getLogger(short)
