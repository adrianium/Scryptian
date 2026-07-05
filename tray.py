# tray.py — System tray icon for Scryptian

import os
import threading
import webbrowser
import pystray
from PIL import Image
import sys

FEEDBACK_URL = "https://github.com/adrianium/Scryptian/discussions"

def _icon_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(_icon_dir(), "icon.ico")


def _load_icon():
    """Load icon.ico as PIL Image."""
    return Image.open(ICON_PATH)


_icon_ref = None
RELEASES_URL = "https://github.com/adrianium/Scryptian/releases/latest"
_update_version = None


def notify(title, message):
    """Show tray notification."""
    if _icon_ref:
        try:
            _icon_ref.notify(message, title)
        except Exception:
            pass


def _get_work_area():
    """Return (left, top, right, bottom) of the usable screen area (excludes taskbar)."""
    try:
        import ctypes
        import ctypes.wintypes
        SPI_GETWORKAREA = 0x0030
        rc = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rc), 0)
        return rc.left, rc.top, rc.right, rc.bottom
    except Exception:
        return None


def show_notify_popup(title, message, root=None, duration=5000):
    """Show a custom in-app notification popup in bottom-right corner."""
    import tkinter as tk

    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg="#161b22")

        w, h = 360, 90
        wa = _get_work_area()
        if wa:
            _, _, right, bottom = wa
        else:
            right = win.winfo_screenwidth()
            bottom = win.winfo_screenheight()
        x = right - w - 16
        y = bottom - h - 12
        win.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(win, text="Scryptian",
                 bg="#161b22", fg="#58a6ff",
                 font=("Segoe UI", 8, "bold")).place(x=14, y=10)

        tk.Label(win, text=title,
                 bg="#161b22", fg="#f0f0f0",
                 font=("Segoe UI", 10, "bold")).place(x=14, y=28)

        tk.Label(win, text=message,
                 bg="#161b22", fg="#8b949e",
                 font=("Segoe UI", 9)).place(x=14, y=52)

        try:
            import winsound
            _snd = os.path.join(_icon_dir(), "docs", "assets", "scryptian-notification.wav")
            if os.path.exists(_snd):
                threading.Thread(target=lambda: winsound.PlaySound(_snd, winsound.SND_FILENAME), daemon=True).start()
        except Exception:
            pass

        def _fade_out(alpha=0.97):
            try:
                if alpha <= 0.0:
                    win.destroy()
                    return
                win.attributes("-alpha", alpha)
                win.after(30, lambda: _fade_out(alpha - 0.05))
            except Exception:
                pass

        win.bind("<Button-1>", lambda e: win.destroy())
        for w_ in win.winfo_children():
            w_.bind("<Button-1>", lambda e: win.destroy())

        win.after(duration, _fade_out)
    except Exception:
        pass


def show_update_popup(version, releases_url, root=None):
    """Show a custom in-app update notification popup in bottom-right corner."""
    import tkinter as tk

    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg="#161b22")

        w, h = 300, 80
        wa = _get_work_area()
        if wa:
            _, _, right, bottom = wa
        else:
            right = win.winfo_screenwidth()
            bottom = win.winfo_screenheight()
        x = right - w - 16
        y = bottom - h - 12
        win.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(win, text=f"Scryptian {version} is available",
                 bg="#161b22", fg="#f5f5f5",
                 font=("Segoe UI", 10, "bold")).place(x=12, y=10)

        tk.Label(win, text="Click to update →",
                 bg="#161b22", fg="#9a9a9a",
                 font=("Segoe UI", 9), cursor="hand2").place(x=12, y=34)

        def _open(e=None):
            try:
                import telemetry
                telemetry.send("update_clicked", {"version": version})
            except Exception:
                pass
            webbrowser.open(releases_url)
            win.destroy()

        win.bind("<Button-1>", _open)
        for w_ in win.winfo_children():
            w_.bind("<Button-1>", _open)

        win.after(8000, win.destroy)
    except Exception:
        pass


def set_update_available(version):
    """Called when a new version is detected — adds menu item."""
    global _update_version
    _update_version = version
    if _icon_ref:
        try:
            _icon_ref.update_menu()
        except Exception:
            pass


def start(on_quit, on_open=None):
    """Start tray icon in background thread."""
    def _run():
        global _icon_ref

        def _update_visible(item):
            return _update_version is not None

        def _open_update():
            webbrowser.open(RELEASES_URL)

        def _update_label(item):
            return f"Update available: v{_update_version} →" if _update_version else "Up to date"

        icon = pystray.Icon(
            name="Scryptian",
            icon=_load_icon(),
            title="Scryptian - Ctrl+Alt",
            menu=pystray.Menu(
                pystray.MenuItem("Open", lambda: on_open() if on_open else None, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(_update_label, _open_update, visible=_update_visible),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Feedback", lambda: webbrowser.open(FEEDBACK_URL)),
                pystray.MenuItem("Quit", lambda: _quit(icon)),
            ),
        )
        _icon_ref = icon

        def _quit(icon):
            icon.stop()
            on_quit()

        icon.run()

    threading.Thread(target=_run, daemon=True).start()
