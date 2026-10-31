# stub.py — Chrome-style mini installer.
#
# This is NOT Scryptian. It only:
#   1) shows a small download window,
#   2) fetches the real Inno installer (Scryptian_Setup.exe),
#   3) runs it silently,
#   4) launches the installed Scryptian.exe.
#
# Auto-update and autostart stay on the real app. Do not point the Run
# registry key at this stub, and do not name this file Scryptian_Setup.exe.

import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from urllib import request

REPO = "adrianium/Scryptian"
SETUP_ASSET = "Scryptian_Setup.exe"
SETUP_FALLBACK_URL = (
    f"https://github.com/{REPO}/releases/latest/download/{SETUP_ASSET}"
)
INSTALLED_EXE = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Scryptian",
    "Application",
    "Scryptian.exe",
)

_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000

_BG = "#0E171C"
_TEXT = "#EDECEC"
_TEXT_DIM = "#898C8E"
_TRACK = "#20282D"
_FILL = "#EDECEC"
_ERROR = "#E6B3AD"
_W = 380


def _ssl_ctx():
    return ssl.create_default_context()


def _http_json(url):
    req = request.Request(url, headers={"User-Agent": "ScryptianSetup"})
    with request.urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _setup_url():
    try:
        data = _http_json(f"https://api.github.com/repos/{REPO}/releases/latest")
        for asset in data.get("assets") or []:
            if (asset.get("name") or "") == SETUP_ASSET:
                url = asset.get("browser_download_url")
                if url:
                    return url
    except Exception:
        pass
    return SETUP_FALLBACK_URL


def _already_installed():
    return os.path.isfile(INSTALLED_EXE)


def _launch_app():
    subprocess.Popen(
        [INSTALLED_EXE],
        close_fds=True,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
    )


def _download(url, dest, on_progress):
    req = request.Request(url, headers={"User-Agent": "ScryptianSetup"})
    tmp = dest + ".part"
    with request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    on_progress(done / total)
    os.replace(tmp, dest)


def _install(setup_path):
    # Silent first-time install. Do NOT pass /AUTOUPDATE — that flag is
    # reserved for the in-app updater so it can relaunch after a swap.
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else _CREATE_NO_WINDOW
    result = subprocess.run(
        [setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        check=False,
        creationflags=flags,
    )
    return result.returncode == 0 and _already_installed()


_mutex_handle = None


def _single_instance():
    global _mutex_handle
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        _mutex_handle = kernel32.CreateMutexW(None, True, "Local\\ScryptianSetupStub")
        return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def _enable_dpi():
    """Draw at the real screen DPI. Without this Windows stretches the window and it looks soft."""
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _screen_dpi():
    try:
        import ctypes
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi:
            return int(dpi)
    except Exception:
        pass
    return 96


def _round_corners(win):
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)
        pref = ctypes.c_int(3)  # DWMWCP_ROUNDSMALL, about 4px
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref)
        )
    except Exception:
        pass


def _rounded_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return c.create_polygon(pts, smooth=True, **kw)


def _logo_path():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "stub_logo.png")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "stub_logo.png")


class StubWindow:
    def __init__(self):
        _enable_dpi()
        self.root = tk.Tk()
        self.win = self.root
        self.win.title("Scryptian")
        self.win.overrideredirect(True)
        self.win.configure(bg=_BG)
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        scale = _screen_dpi() / 96.0
        try:
            scale = max(scale, self.root.winfo_fpixels("1i") / 96.0)
        except Exception:
            pass
        self._scale = scale if scale > 0 else 1.0
        try:
            self.root.tk.call("tk", "scaling", self._scale)
        except Exception:
            pass

        inner = tk.Frame(self.win, bg=_BG)
        inner.pack(fill="both", expand=True)

        self._title_font, self._body_font = self._fonts()
        self._logo = self._load_logo(self.px(32))
        if self._logo is not None:
            tk.Label(inner, image=self._logo, bg=_BG, bd=0, highlightthickness=0).pack(
                pady=(self.px(28), self.px(16))
            )
        else:
            tk.Frame(inner, bg=_BG, height=self.px(28)).pack()

        tk.Label(
            inner, text="Scryptian", bg=_BG, fg=_TEXT, font=self._title_font,
        ).pack()

        self.bar_w = self.px(_W - 56)
        self.status = tk.Label(
            inner, text="Getting Scryptian ready…", bg=_BG, fg=_TEXT_DIM,
            font=self._body_font, wraplength=self.bar_w, justify="center",
        )
        self.status.pack(pady=(self.px(8), 0))

        self.bar_h = max(self.px(4), 2)
        self.bar_r = max(self.px(2), 1)
        self.bar = tk.Canvas(
            inner, width=self.bar_w, height=self.bar_h, bg=_BG,
            highlightthickness=0, bd=0,
        )
        self.bar.pack(pady=(self.px(24), 0))
        self._paint_bar(0)

        self.pct = tk.Label(
            inner, text="0%", bg=_BG, fg=_TEXT_DIM, font=self._body_font,
        )
        self.pct.pack(pady=(self.px(8), self.px(24)))

        self.win.update_idletasks()
        width = self.px(_W)
        height = inner.winfo_reqheight()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        self.win.geometry(f"{width}x{height}+{x}+{y}")
        self.win.update_idletasks()
        _round_corners(self.win)

    def px(self, n):
        return max(1, int(round(n * self._scale)))

    def _fonts(self):
        import tkinter.font as tkfont
        families = set(tkfont.families(self.root))
        if "Segoe UI Semibold" in families:
            title_family = "Segoe UI Semibold"
        elif "Segoe UI" in families:
            title_family = "Segoe UI"
        else:
            title_family = "Segoe UI Variable"
        body_family = "Segoe UI" if "Segoe UI" in families else title_family
        title = tkfont.Font(root=self.root, family=title_family, size=16)
        body = tkfont.Font(root=self.root, family=body_family, size=14)
        return title, body

    def _load_logo(self, size):
        path = _logo_path()
        if not os.path.isfile(path):
            return None
        try:
            img = tk.PhotoImage(file=path)
            src = img.width()
            if src > size:
                img = img.subsample(max(1, int(round(src / size))))
            return img
        except Exception:
            return None

    def _paint_bar(self, frac):
        self.bar.delete("all")
        _rounded_rect(
            self.bar, 0, 0, self.bar_w, self.bar_h, self.bar_r,
            fill=_TRACK, outline="",
        )
        width = int(self.bar_w * max(0.0, min(1.0, frac)))
        if width > 0:
            _rounded_rect(
                self.bar, 0, 0, max(width, self.bar_r * 2), self.bar_h, self.bar_r,
                fill=_FILL, outline="", tags="fill",
            )

    def _set_status(self, text):
        self.win.after(0, lambda: self.status.config(text=text, fg=_TEXT_DIM))

    def _set_progress(self, frac):
        def _apply():
            self.pct.config(text=f"{int(frac * 100)}%", fg=_TEXT_DIM)
            self._paint_bar(frac)
        self.win.after(0, _apply)

    def _fail(self, text):
        def _apply():
            self.status.config(text=text, fg=_ERROR)
            self.pct.config(text="")
            self.bar.delete("all")
        self.win.after(0, _apply)

    def _finish(self):
        def _apply():
            try:
                _launch_app()
            except Exception:
                self._fail("Installed, but couldn't start Scryptian.")
                return
            self._close()
        self.win.after(0, _apply)

    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def _work(self):
        if _already_installed():
            self._set_status("Starting Scryptian…")
            self._set_progress(1)
            self.win.after(400, self._finish)
            return

        dest = os.path.join(tempfile.gettempdir(), SETUP_ASSET)
        try:
            self._set_status("Downloading Scryptian…")
            url = _setup_url()
            _download(url, dest, self._set_progress)
        except Exception:
            self._fail("Download failed. Check your internet and try again.")
            return

        self._set_status("Installing…")
        self._set_progress(1)
        try:
            ok = _install(dest)
        except Exception:
            ok = False
        try:
            os.remove(dest)
        except Exception:
            pass

        if not ok:
            self._fail("Install failed. Try again, or download Scryptian_Setup.exe.")
            return

        self._set_status("Starting Scryptian…")
        self.win.after(300, self._finish)

    def run(self):
        threading.Thread(target=self._work, daemon=True).start()
        self.root.mainloop()


def main():
    if not _single_instance():
        if _already_installed():
            try:
                _launch_app()
            except Exception:
                pass
        return
    StubWindow().run()


if __name__ == "__main__":
    main()
