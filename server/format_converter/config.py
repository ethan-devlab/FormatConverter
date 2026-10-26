from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path

import psutil

VERSION = "0.1.0-dev"
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DATA = Path(os.environ.get("FORMAT_CONVERTER_DATA", Path(os.environ.get("LOCALAPPDATA", Path.home())) / "EthanDevLab" / "FormatConverter"))
TESSDATA = Path(os.environ.get("FORMAT_CONVERTER_TESSDATA", BASE / "resources" / "tessdata"))
DEFAULT_WORKERS = max(1, min(4, (os.cpu_count() or 2) - 1, int(psutil.virtual_memory().available / (512 * 1024**2))))
DEFAULTS = {"language": "en", "roots": [], "show_hidden": False, "workers": DEFAULT_WORKERS,
            "explorer_width": 260, "parameter_width": 360, "memory_mb": 2048, "preview_dark": True, "presets": {}, "text_browser": "edge", "text_browser_path": ""}
SAFE_PRESET_KEYS = {"page_size", "orientation", "margin", "fit", "background", "dpi", "quality", "format",
                   "organize_mode", "split_every", "page_width", "page_height",
                   "text_mode", "text_encoding", "text_font", "text_font_size", "text_line_height",
                   "text_tab_width", "text_color",
                   "frames", "preserve_dpi", "width", "height", "keep_ratio", "resample", "rotation", "sharpen", "optimize", "lossless",
                   "metadata", "color_mode", "text_layout", "page_separator", "ocr_language", "force_ocr",
                   "ocr_output", "ocr_chinese_first", "compression", "target_dpi", "dpi_threshold", "extract_images", "ico_sizes"}
PREFERENCES_LOCK = threading.RLock()


def read_preferences() -> dict:
    try:
        saved = json.loads((DATA / "preferences.json").read_text("utf-8"))
        return DEFAULTS | {k: v for k, v in saved.items() if k in DEFAULTS}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)


def write_preferences(values: dict) -> dict:
    with PREFERENCES_LOCK:
        return _write_preferences(values)


def _write_preferences(values: dict) -> dict:
    prefs = read_preferences() | {k: v for k, v in values.items() if k in DEFAULTS}
    prefs["language"] = "zh-TW" if prefs["language"] == "zh-TW" else "en"
    if prefs["text_browser"] not in {"edge", "chrome", "firefox"}:
        raise ValueError("BROWSER_UNAVAILABLE: Choose Edge, Chrome, or Firefox.")
    prefs["text_browser_path"] = str(prefs["text_browser_path"]).strip()
    prefs["workers"] = max(1, min(16, int(prefs["workers"])))
    prefs["memory_mb"] = max(256, min(32768, int(prefs["memory_mb"])))
    prefs["explorer_width"] = max(190, min(420, int(prefs["explorer_width"])))
    prefs["parameter_width"] = max(300, min(520, int(prefs["parameter_width"])))
    prefs["presets"] = {str(name)[:80]: {k: v for k, v in params.items() if k in SAFE_PRESET_KEYS}
                        for name, params in prefs.get("presets", {}).items() if isinstance(params, dict)}
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = DATA / f"preferences-{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(prefs, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(DATA / "preferences.json")
    return prefs
