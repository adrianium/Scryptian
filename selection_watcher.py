# selection_watcher.py — Shows toolbar when a file is copied to the clipboard.
# Polls the clipboard (CF_HDROP) so it catches both Ctrl+C and right-click → Copy.

import threading
import time
import ctypes
import source_detect

_on_selection_cb = None
_running = False


def _read_clipboard_file():
    """Return the current clipboard file path (CF_HDROP), or None."""
    from core.input import get_file
    try:
        return get_file()
    except Exception:
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
            path = _read_clipboard_file()
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
