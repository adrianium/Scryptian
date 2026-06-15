# selection_watcher.py — Shows toolbar when user presses Ctrl+C with selected text
# Uses keyboard hook (non-suppressing) + clipboard read

import threading
import time

_on_selection_cb = None
_COOLDOWN = 1.5
_last_fire = 0.0


def _on_copy():
    """Called when Ctrl+C is pressed anywhere. Reads clipboard and fires callback."""
    global _last_fire

    now = time.time()
    if now - _last_fire < _COOLDOWN:
        return

    def _read_and_fire():
        global _last_fire
        try:
            import pyperclip
            before = pyperclip.paste() or ""
        except Exception:
            before = ""

        time.sleep(0.3)  # wait for app to update clipboard

        try:
            import pyperclip
            text = pyperclip.paste() or ""
        except Exception:
            return

        text = text.strip()
        if not text or len(text) < 2:
            return

        _last_fire = time.time()

        try:
            import ctypes
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            cx, cy = pt.x, pt.y
            hwnd = ctypes.windll.user32.GetForegroundWindow()
        except Exception:
            cx, cy, hwnd = 0, 0, 0

        if _on_selection_cb:
            _on_selection_cb(text, cx, cy, hwnd)

    threading.Thread(target=_read_and_fire, daemon=True).start()


def start(on_selection, ignore_hwnd=None):
    """Start Ctrl+C listener. on_selection(text, x, y, hwnd) called on each copy."""
    global _on_selection_cb
    _on_selection_cb = on_selection
    import keyboard
    keyboard.add_hotkey("ctrl+c", _on_copy, suppress=False)


def stop():
    try:
        import keyboard
        keyboard.remove_hotkey("ctrl+c")
    except Exception:
        pass
