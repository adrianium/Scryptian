# selection_watcher.py — Shows toolbar when a file is copied to the clipboard.
# Polls the clipboard (CF_HDROP) so it catches both Ctrl+C and right-click → Copy.

import threading
import time
import ctypes
import source_detect

_on_selection_cb = None
_running = False


def _read_clipboard_input():
    """Return the clipboard file path (CF_HDROP) or a URL (text), else None."""
    from core.input import get_input
    try:
        result = get_input()
    except Exception:
        return None
    if not result:
        return None
    if result.get("type") == "file":
        return result.get("data")
    if result.get("type") == "text":
        data = (result.get("data") or "").strip()
        if data.lower().startswith(("http://", "https://")):
            return data
    return None


def _poll():
    try:
        last_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
    except Exception:
        last_seq = 0
    while _running:
        try:
            seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        except Exception:
            seq = 0
        if seq != last_seq:
            last_seq = seq
            path = _read_clipboard_input()
            if path:
                try:
                    pt = ctypes.wintypes.POINT()
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    cx, cy = pt.x, pt.y
                    hwnd = source_detect.get_source_window()
                except Exception:
                    cx, cy, hwnd = 0, 0, 0
                if _on_selection_cb:
                    _on_selection_cb(path, cx, cy, hwnd)
        time.sleep(0.2)


def start(on_selection, ignore_hwnd=None):
    """Start clipboard watcher. on_selection(file_path, x, y, hwnd) on file copy."""
    global _on_selection_cb, _running
    _on_selection_cb = on_selection
    _running = True
    threading.Thread(target=_poll, daemon=True).start()


def stop():
    global _running
    _running = False
