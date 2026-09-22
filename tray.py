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


def _idle_ms():
    """Milliseconds since the last user input (mouse/keyboard) on Windows."""
    try:
        import ctypes
        from ctypes import wintypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            now = ctypes.windll.kernel32.GetTickCount()
            return (now - lii.dwTime) & 0xFFFFFFFF
    except Exception:
        pass
    return 0


def open_in_explorer(path):
    """Open Explorer with the given file selected (Windows)."""
    import subprocess
    try:
        if path and os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])
    except Exception:
        pass


def show_notify_popup(title, message, root=None, duration=5000, action=None):
    """Show a custom in-app notification popup in bottom-right corner.

    action (optional): {"label": "Open file", "hotkey": "alt+e", "callback": callable}
    """
    import tkinter as tk
    import keyboard

    hotkey_handler = None

    def _cleanup():
        nonlocal hotkey_handler
        if hotkey_handler is not None:
            try:
                keyboard.remove_hotkey(hotkey_handler)
            except Exception:
                pass
            hotkey_handler = None
        try:
            win.destroy()
        except Exception:
            pass

    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg="#0e0e10")

        w = 360
        wrap = w - 28

        tk.Label(win, text="Scryptian",
                 bg="#0e0e10", fg="#3b82f6",
                 font=("Manrope", 8, "bold")).place(x=14, y=10)

        tk.Label(win, text=title,
                 bg="#0e0e10", fg="#efeff1",
                 font=("Manrope", 10, "bold"),
                 wraplength=wrap, justify="left").place(x=14, y=28)

        msg = tk.Label(win, text=message,
                       bg="#0e0e10", fg="#adadb8",
                       font=("Manrope", 9),
                       wraplength=wrap, justify="left")
        msg.place(x=14, y=52)

        # Size the popup to fit the (wrapped) message instead of clipping it.
        win.update_idletasks()
        msg_h = max(24, msg.winfo_reqheight())

        # Optional action hint (hotkey + label) below the message.
        action_h = 0
        if action:
            hotkey = (action.get("hotkey") or "").strip()
            callback = action.get("callback")
            label = (action.get("label") or "Open file").strip()
            if hotkey and callable(callback):
                try:
                    hotkey_handler = keyboard.add_hotkey(hotkey, callback)
                except Exception:
                    hotkey_handler = None
            display = hotkey.replace("+", " + ").upper()
            hint_text = f"[{display}] {label}" if display else label
            tk.Label(win, text=hint_text,
                     bg="#0e0e10", fg="#3b82f6",
                     font=("Manrope", 9, "bold")).place(x=14, y=52 + msg_h + 6)
            action_h = 22

        h = 52 + msg_h + action_h + 14

        wa = _get_work_area()
        if wa:
            _, _, right, bottom = wa
        else:
            right = win.winfo_screenwidth()
            bottom = win.winfo_screenheight()
        x = right - w - 16
        y = bottom - h - 12
        win.geometry(f"{w}x{h}+{x}+{y}")

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
                    _cleanup()
                    return
                win.attributes("-alpha", alpha)
                win.after(30, lambda: _fade_out(alpha - 0.05))
            except Exception:
                pass

        win.bind("<Button-1>", lambda e: _cleanup())
        for w_ in win.winfo_children():
            w_.bind("<Button-1>", lambda e: _cleanup())

        # Hold at least `duration`, then wait until the user is active before fading.
        def _wait_for_activity():
            try:
                if not win.winfo_exists():
                    return
                if _idle_ms() < 2000:
                    _fade_out()
                else:
                    win.after(200, _wait_for_activity)
            except Exception:
                pass

        win.after(duration, _wait_for_activity)
    except Exception:
        if hotkey_handler is not None:
            try:
                keyboard.remove_hotkey(hotkey_handler)
            except Exception:
                pass
        pass


def show_update_popup(version, releases_url, root=None):
    """Show a custom in-app update notification popup in bottom-right corner."""
    import tkinter as tk

    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.97)
        win.configure(bg="#0e0e10")

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
                 bg="#0e0e10", fg="#efeff1",
                 font=("Manrope", 10, "bold")).place(x=12, y=10)

        tk.Label(win, text="Click to update →",
                 bg="#0e0e10", fg="#adadb8",
                 font=("Manrope", 9), cursor="hand2").place(x=12, y=34)

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
