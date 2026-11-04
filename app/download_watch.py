# download_watch.py — Notice a finished browser download without opening Explorer.
#
# The full actions bar stays closed. One short line names the file, then
# goes away. The hotkey, while a browser is in front, opens that file.

import os
import ctypes
import queue
import threading
import time
from ctypes import wintypes

import source_detect
from config import HOTKEY

_BROWSERS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "yandex.exe",
    "browser.exe",
    "chromium.exe",
    "whale.exe",
    "arc.exe",
}

# Installers and files that are still being written.
_SKIP_EXT = {
    ".crdownload",
    ".part",
    ".partial",
    ".tmp",
    ".download",
    ".opdownload",
    ".exe",
    ".msi",
    ".msix",
    ".appx",
    ".bat",
    ".cmd",
    ".lnk",
}

_LATEST_TTL = 15 * 60
_BURST_SEC = 2.0
_ARM_SEC = 0.7
_POLL_SEC = 0.8

_lock = threading.Lock()
_latest_path = ""
_latest_at = 0.0
_events = queue.Queue()


def browser_is_foreground():
    """True when the front window belongs to a browser."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return source_detect._get_exe(hwnd) in _BROWSERS
    except Exception:
        return False


def _browser_box():
    """Client area of the browser window, in screen pixels.

    A small popup is ignored. A narrow or half-screen window is used as it is.
    """
    user32 = ctypes.windll.user32
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    user32.ClientToScreen.restype = wintypes.BOOL

    def _box(hwnd):
        root = user32.GetAncestor(hwnd, 2) or hwnd
        rect = wintypes.RECT()
        if not user32.GetClientRect(root, ctypes.byref(rect)):
            return None
        origin = wintypes.POINT(0, 0)
        if not user32.ClientToScreen(root, ctypes.byref(origin)):
            return None
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        if width < 200 or height < 160:
            return None
        return int(origin.x), int(origin.y), width, height

    fg = user32.GetForegroundWindow()
    if fg and source_detect._get_exe(fg) in _BROWSERS:
        box = _box(fg)
        if box:
            return box

    found = []

    def _enum(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if source_detect._get_exe(hwnd) not in _BROWSERS:
            return True
        box = _box(hwnd)
        if box:
            found.append(box)
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(_enum)
    user32.EnumWindows(callback, 0)
    if not found:
        return None
    return max(found, key=lambda item: item[2] * item[3])


def foreground_exe():
    """Lowercase exe name of the front window."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return source_detect._get_exe(hwnd)
    except Exception:
        return ""


def pop():
    """Next download event, or None. Call this from the UI thread."""
    try:
        return _events.get_nowait()
    except queue.Empty:
        return None


def latest():
    """Path of the newest suitable download, while it is still fresh."""
    with _lock:
        path, at = _latest_path, _latest_at
    if not path or (time.time() - at) > _LATEST_TTL:
        return ""
    if not os.path.isfile(path):
        return ""
    return path


def _remember(path):
    global _latest_path, _latest_at
    with _lock:
        _latest_path = path
        _latest_at = time.time()


def _eligible(name):
    if not name or name.startswith("."):
        return False
    ext = os.path.splitext(name)[1].lower()
    return ext not in _SKIP_EXT


def _downloads_dir():
    """The real Downloads folder, including a localized Windows name."""
    try:
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        folder_id = GUID(
            0x374DE290,
            0x123F,
            0x4565,
            (wintypes.BYTE * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B),
        )
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID),
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        raw = ctypes.c_void_p()
        if shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(raw)) == 0 and raw.value:
            path = ctypes.wstring_at(raw.value)
            ctypes.windll.ole32.CoTaskMemFree(raw)
            if path and os.path.isdir(path):
                return path
    except Exception:
        pass
    fallback = os.path.join(os.path.expanduser("~"), "Downloads")
    return fallback if os.path.isdir(fallback) else ""


def _scan(folder):
    found = {}
    try:
        names = os.listdir(folder)
    except Exception:
        return found
    for name in names:
        if not _eligible(name):
            continue
        path = os.path.join(folder, name)
        try:
            if not os.path.isfile(path):
                continue
            st = os.stat(path)
        except Exception:
            continue
        if st.st_size <= 0:
            continue
        found[path] = (st.st_size, getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    return found


def start(has_actions):
    """Watch Downloads on a background thread. The UI thread reads events with pop()."""

    def _run():
        folder = _downloads_dir()
        if not folder:
            return
        snapshot = _scan(folder)
        waiting = {}
        armed_path = ""
        armed_at = 0.0
        last_accept = 0.0
        while True:
            time.sleep(_POLL_SEC)
            try:
                current = _scan(folder)
            except Exception:
                continue
            now = time.time()
            for path, sig in current.items():
                old = snapshot.get(path)
                if old == sig:
                    waiting.pop(path, None)
                    continue
                if waiting.get(path) == sig:
                    waiting.pop(path, None)
                    snapshot[path] = sig
                    try:
                        ok = bool(has_actions(path))
                    except Exception:
                        ok = False
                    if not ok:
                        print(f"[nespatch] Download has no actions: {os.path.basename(path)}")
                        continue
                    _remember(path)
                    gap = now - last_accept if last_accept else _BURST_SEC + 1
                    last_accept = now
                    name = os.path.basename(path)
                    if gap < _BURST_SEC:
                        armed_path = ""
                        print(f"[nespatch] Downloads arrived together, line hidden ({name}).")
                        _events.put(("hide", ""))
                    else:
                        armed_path = path
                        armed_at = now + _ARM_SEC
                        print(f"[nespatch] Download ready: {name}")
                else:
                    waiting[path] = sig
            if armed_path and now >= armed_at:
                path = armed_path
                armed_path = ""
                if os.path.isfile(path):
                    _events.put(("show", path))

    threading.Thread(target=_run, name="scryptian-downloads", daemon=True).start()


def _key_chip(parent, text, bg, fg, key_bg):
    """A hotkey with a small corner radius, not a pill."""
    import tkinter as tk
    import tkinter.font as tkfont

    font = tkfont.Font(family="Segoe UI Variable", size=12)
    width = font.measure(text) + 16
    height = 24
    radius = 4
    canvas = tk.Canvas(
        parent, width=width, height=height, bg=bg,
        highlightthickness=0, bd=0, cursor="hand2",
    )
    points = [
        radius, 0, width - radius, 0, width, 0, width, radius,
        width, height - radius, width, height, width - radius, height, radius, height,
        0, height, 0, height - radius, 0, radius, 0, 0,
    ]
    canvas.create_polygon(points, smooth=True, fill=key_bg, outline=key_bg)
    canvas.create_text(width / 2, height / 2, text=text, fill=fg, font=font)
    return canvas


class DownloadHint:
    """One short filename line. A newer file replaces it. Click opens the bar."""

    def __init__(self, root, on_open):
        self.root = root
        self.on_open = on_open
        self.win = None
        self._after = None
        self._path = ""

    def show(self, path):
        import tkinter as tk

        self._path = path
        name = os.path.basename(path)
        if len(name) > 32:
            ext = os.path.splitext(name)[1]
            head = 32 - len(ext) - 3
            name = name[:max(head, 4)] + "..." + ext
        if self.win is not None and self.win.winfo_exists():
            try:
                self._label.config(text=name)
                self._restart_timer()
                return
            except Exception:
                self.dismiss()

        win = tk.Toplevel(self.root)
        self.win = win
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        bg = "#1A2328"
        fg = "#EDECEC"
        muted = "#C5C8CA"
        key_bg = "#2A343A"
        win.configure(bg=bg, cursor="hand2")
        box = tk.Frame(win, bg=bg, cursor="hand2")
        box.pack(padx=16, pady=12, fill="x")
        self._label = tk.Label(
            box, text=name, bg=bg, fg=fg,
            font=("Segoe UI Variable", 14), anchor="w", cursor="hand2",
        )
        self._label.pack(anchor="w")
        hint = tk.Frame(box, bg=bg, cursor="hand2")
        hint.pack(anchor="w", pady=(8, 0))
        tk.Label(
            hint, text="Ready for actions", bg=bg, fg=muted,
            font=("Segoe UI Variable", 12), anchor="w", cursor="hand2",
        ).pack(side="left")
        for part in HOTKEY.split("+"):
            key = part.strip().capitalize()
            if not key:
                continue
            _key_chip(hint, key, bg, fg, key_bg).pack(side="left", padx=(8, 0))
        win.update_idletasks()
        width = min(max(win.winfo_reqwidth(), 240), 420)
        height = max(win.winfo_reqheight(), 64)
        browser = _browser_box()
        if browser:
            left, top, browser_w, browser_h = browser
            x = left + (browser_w - width) // 2
            y = top + browser_h - height - 28
        else:
            screen_w = win.winfo_screenwidth()
            screen_h = win.winfo_screenheight()
            x = (screen_w - width) // 2
            y = screen_h - height - 48
        win.geometry(f"{width}x{height}+{x}+{y}")
        win.deiconify()
        win.lift()
        win.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        win.lift()

        def _bind(widget):
            widget.bind("<Button-1>", self._click)
            for child in widget.winfo_children():
                _bind(child)

        _bind(win)
        self._restart_timer()

    def dismiss(self):
        if self._after is not None:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        win = self.win
        self.win = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass

    def _restart_timer(self):
        if self._after is not None:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
        self._after = self.root.after(4000, self.dismiss)

    def _click(self, _event=None):
        path = self._path
        self.dismiss()
        if path and os.path.isfile(path):
            try:
                self.on_open(path)
            except Exception:
                pass
