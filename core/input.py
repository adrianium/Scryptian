# core/input.py — Pluggable input resolver.
#
# Sources are tried in order. The first one that returns a dict wins.
# Add new sources here without touching the bar or skills.
#
#   result = get_input()
#   # → {"type": "file", "data": "C:\\docs\\report.csv"}
#   # → {"type": "text", "data": "hello world"}
#   # → None

import sys
import pyperclip

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import ctypes


# ── Sources ──────────────────────────────────────────────────

class _ClipboardFileSource:
    """Files copied in Explorer (CF_HDROP)."""

    def fetch(self):
        if not IS_WINDOWS:
            return None
        try:
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            user32.GetClipboardData.restype = ctypes.c_void_p
            shell32.DragQueryFileW.argtypes = [
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ]
            if not user32.OpenClipboard(0):
                return None
            CF_HDROP = 15
            handle = user32.GetClipboardData(CF_HDROP)
            if not handle:
                user32.CloseClipboard()
                return None
            count = shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
            if count == 0:
                user32.CloseClipboard()
                return None
            buf = ctypes.create_unicode_buffer(260)
            shell32.DragQueryFileW(handle, 0, buf, 260)
            user32.CloseClipboard()
            return {"type": "file", "data": buf.value}
        except Exception:
            try:
                ctypes.windll.user32.CloseClipboard()
            except Exception:
                pass
            return None


class _ClipboardTextSource:
    """Plain text in clipboard."""

    def fetch(self):
        try:
            text = pyperclip.paste()
            if text.strip():
                return {"type": "text", "data": text}
        except Exception:
            pass
        return None


# ── Resolver ─────────────────────────────────────────────────

SOURCES = [_ClipboardFileSource(), _ClipboardTextSource()]


def get_input():
    """Try every source in priority order.  First hit wins."""
    for src in SOURCES:
        result = src.fetch()
        if result is not None:
            return result
    return None
