# tray.py — System tray icon for Scryptian

import os
import re
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

_notif_stack = []  # active notification windows, bottom to top
_layout_gen = 0


def _stack_offset():
    """Total height taken by active notifications (plus gaps)."""
    gap = 8
    return sum(h for _, h in _notif_stack) + gap * len(_notif_stack)


def _parse_geometry(win):
    m = re.match(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", str(win.geometry()))
    if not m:
        return None
    return tuple(int(g) for g in m.groups())


def _relayout(enter=None):
    """Place the stack from the bottom. Windows above a closed one slide down."""
    global _layout_gen
    _layout_gen += 1
    gen = _layout_gen
    alive = []
    for win, h in _notif_stack:
        try:
            if win.winfo_exists():
                alive.append((win, h))
        except Exception:
            continue
    if not alive:
        return

    sample = alive[0][0]
    gap = 8
    margin_x = 16
    margin_y = 12
    wa = _get_work_area()
    if wa:
        _, _, right, bottom = wa
    else:
        right = sample.winfo_screenwidth()
        bottom = sample.winfo_screenheight()

    offset = 0
    moves = []
    for win, h in alive:
        box = _parse_geometry(win)
        width = getattr(win, "_notif_w", 440)
        target_y = bottom - h - margin_y - offset
        target_x = right - width - margin_x
        start_y = target_y + margin_x if win is enter else (box[3] if box else target_y)
        moves.append((win, width, h, target_x, start_y, target_y))
        offset += h + gap

    def step(i=0):
        if gen != _layout_gen:
            return
        total = 12
        t = min(i / total, 1)
        p = 1 - (1 - t) ** 3
        for win, width, h, tx, sy, ty in moves:
            try:
                if not win.winfo_exists():
                    continue
                ny = int(round(sy + (ty - sy) * p))
                win.geometry(f"{width}x{h}+{tx}+{ny}")
            except Exception:
                continue
        if i < total:
            try:
                sample.after(16, lambda: step(i + 1))
            except Exception:
                pass

    step()


def _round_corners(win, small=False):
    """Native Windows 11 rounded corners via DWM (safe no-op on failure)."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)  # GA_ROOT
        pref = ctypes.c_int(3 if small else 2)  # 3 = about 4px, 2 = default round
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a canvas (smooth polygon)."""
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def _rounded_button(parent, text, command, bg, fg, font, height, radius, pad_x):
    """Flat rounded button. Matches the notification mock."""
    import tkinter as tk
    import tkinter.font as tkfont
    family, size = font
    f = tkfont.Font(family=family, size=size)
    w = f.measure(text) + pad_x * 2
    h = height
    c = tk.Canvas(parent, width=w, height=h, bg=parent.cget("bg"), highlightthickness=0, bd=0)
    _rounded_rect(c, 0, 0, w, h, radius, fill=bg, outline=bg)
    c.create_text(w // 2, h // 2, text=text, fill=fg, font=f)
    c.config(cursor="hand2")
    c.bind("<Button-1>", lambda e: command())
    return c


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
    """Open Explorer with the given file selected (Windows), and bring it to front."""
    import subprocess
    try:
        if path and os.path.isfile(path):
            subprocess.Popen(['explorer', '/select,', os.path.normpath(path)])

            def _focus():
                import ctypes
                import time
                try:
                    time.sleep(0.4)
                    hwnd = ctypes.windll.user32.FindWindowW("CabinetWClass", None)
                    if hwnd:
                        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                        ctypes.windll.user32.BringWindowToTop(hwnd)
                except Exception:
                    pass

            threading.Thread(target=_focus, daemon=True).start()
    except Exception:
        pass


def show_notify_popup(title, message, root=None, duration=5000, action=None):
    """Show a custom in-app notification popup in bottom-right corner.

    action (optional): {"label": "Open file", "hotkey": "alt+q", "callback": callable}
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
        for i, (w_, _h) in enumerate(_notif_stack):
            if w_ is win:
                _notif_stack.pop(i)
                break
        try:
            if root is not None:
                root.after(0, _relayout)
            else:
                _relayout()
        except Exception:
            pass

    try:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)

        # Colors and sizes from notify-preview.html
        bg = "#1A2328"
        fg = "#EDECEC"
        body_fg = "#9DA0A2"
        dim = "#7B7F82"
        btn_bg = "#EDECEC"
        btn_fg = "#14120B"
        win.configure(bg=bg)

        import tkinter.font as tkfont
        families = set(tkfont.families(win))
        semi = "Segoe UI Semibold" if "Segoe UI Semibold" in families else "Segoe UI Variable"
        regular = "Segoe UI Variable" if "Segoe UI Variable" in families else "Segoe UI"
        meta_font = (regular, 12)
        title_font = (regular, 15)
        body_font = (regular, 13)
        btn_font = (semi, 13)

        W = 440
        PAD_X = 14
        PAD_Y = 10
        win._notif_w = W

        inner = tk.Frame(win, bg=bg)
        inner.pack(fill="both", expand=True, padx=PAD_X, pady=PAD_Y)

        header = tk.Frame(inner, bg=bg)
        header.pack(fill="x")
        lead = tk.Frame(header, bg=bg)
        lead.pack(side="left", fill="x", expand=True)

        tk.Label(lead, text=title, bg=bg, fg=fg,
                 font=title_font, anchor="w").pack(side="left", padx=(0, 8))

        close_btn = tk.Label(header, text="✕", bg=bg, fg=dim,
                             font=meta_font, cursor="hand2", padx=4)
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: _cleanup())

        body_row = tk.Frame(inner, bg=bg)
        body_row.pack(fill="x", pady=(2, 0))

        action_btn = None
        if action:
            hotkey = (action.get("hotkey") or "").strip()
            callback = action.get("callback")
            label = (action.get("label") or "Open").strip()

            def _do_action():
                if callable(callback):
                    try:
                        callback()
                    except Exception:
                        pass
                _cleanup()

            if hotkey and callable(callback):
                try:
                    hotkey_handler = keyboard.add_hotkey(hotkey, _do_action)
                except Exception:
                    hotkey_handler = None

            action_btn = _rounded_button(
                body_row, label, _do_action,
                bg=btn_bg, fg=btn_fg, font=btn_font,
                height=28, radius=4, pad_x=10,
            )
            action_btn.pack(side="right")
            if hotkey:
                hint = hotkey.replace("+", " + ").upper()
                tk.Label(body_row, text=hint, bg=bg, fg=dim,
                         font=meta_font, anchor="e").pack(side="right", padx=(0, 12))

        tk.Label(body_row, text=message, bg=bg, fg=body_fg,
                 font=body_font, anchor="w", justify="left",
                 wraplength=W - PAD_X * 2 - (180 if action else 0)).pack(side="left", fill="x", expand=True)

        win.update_idletasks()
        h = inner.winfo_reqheight() + PAD_Y * 2

        wa = _get_work_area()
        if wa:
            _, _, right, bottom = wa
        else:
            right = win.winfo_screenwidth()
            bottom = win.winfo_screenheight()
        x = right - W - 16
        y = bottom - h - 12 - _stack_offset()
        _notif_stack.append((win, h))
        win.geometry(f"{W}x{h}+{x}+{y + 16}")
        win.attributes("-alpha", 0.0)
        _round_corners(win, small=True)
        _relayout(enter=win)

        def _fade_in(step=0):
            total = 14
            p = 1 - (1 - step / total) ** 3
            try:
                win.attributes("-alpha", p)
            except Exception:
                return
            if step < total:
                win.after(16, lambda: _fade_in(step + 1))

        _fade_in()

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

        def _bind_close(widget):
            if widget is action_btn:
                return
            widget.bind("<Button-1>", lambda e: _cleanup(), add="+")
            for child in widget.winfo_children():
                _bind_close(child)

        _bind_close(win)

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
        win.configure(bg="#3C3C3C")
        _round_corners(win)

        W = 320
        PAD = 16
        outer = tk.Frame(win, bg="#3C3C3C", padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg="#202020")
        inner.pack(fill="both", expand=True)

        tk.Label(inner, text="Scryptian", bg="#202020", fg="#60CDFF",
                 font=("Segoe UI Variable", 12, "bold"), anchor="w").pack(fill="x", padx=PAD, pady=(14, 0))

        tk.Label(inner, text=f"Version {version} is available", bg="#202020", fg="#FFFFFF",
                 font=("Segoe UI Variable", 14, "bold"), anchor="w").pack(fill="x", padx=PAD, pady=(2, 0))

        tk.Label(inner, text="Click to update →", bg="#202020", fg="#C5C5C5",
                 font=("Segoe UI Variable", 12), anchor="w", cursor="hand2").pack(fill="x", padx=PAD, pady=(4, 14))

        win.update_idletasks()
        h = inner.winfo_reqheight() + 2

        wa = _get_work_area()
        if wa:
            _, _, right, bottom = wa
        else:
            right = win.winfo_screenwidth()
            bottom = win.winfo_screenheight()
        x = right - W - 16
        y = bottom - h - 12
        win.geometry(f"{W}x{h}+{x}+{y}")

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
