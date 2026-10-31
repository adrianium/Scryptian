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

_BG = "#202020"
_BORDER = "#3C3C3C"
_TEXT = "#FFFFFF"
_TEXT_DIM = "#9A9A9A"
_ACCENT = "#60CDFF"
_ERROR = "#F1707B"


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


def _round_corners(win):
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)
        pref = ctypes.c_int(2)
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


class StubWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Scryptian")

        self.win = tk.Toplevel(self.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=_BORDER)
        self.win.protocol("WM_DELETE_WINDOW", self._close)

        outer = tk.Frame(self.win, bg=_BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=_BG)
        inner.pack(fill="both", expand=True)

        self.W, self.H = 380, 240

        self.spinner = tk.Canvas(
            inner, width=56, height=56, bg=_BG, highlightthickness=0, bd=0
        )
        self.spinner.pack(pady=(36, 8))

        tk.Label(
            inner, text="Scryptian", bg=_BG, fg=_TEXT,
            font=("Segoe UI Variable", 16, "bold"),
        ).pack()

        self.status = tk.Label(
            inner, text="Getting Scryptian ready…", bg=_BG, fg=_TEXT_DIM,
            font=("Segoe UI Variable", 12),
        )
        self.status.pack(pady=(6, 0))

        self.bar = tk.Canvas(
            inner, width=self.W - 72, height=6, bg=_BG, highlightthickness=0, bd=0
        )
        self.bar.pack(pady=(18, 0))
        _rounded_rect(self.bar, 0, 0, self.W - 72, 6, 3, fill="#2B2B2B", outline="")

        self.pct = tk.Label(
            inner, text="0%", bg=_BG, fg=_ACCENT,
            font=("Segoe UI Variable", 12),
        )
        self.pct.pack(pady=(10, 0))

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - self.W) // 2
        y = (sh - self.H) // 2
        self.win.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self.win.update_idletasks()
        _round_corners(self.win)

        self._spinning = True
        self._spin()
        threading.Thread(target=self._work, daemon=True).start()

    def _spin(self, angle=0):
        if not self._spinning or not self.win.winfo_exists():
            return
        self.spinner.delete("all")
        self.spinner.create_arc(
            8, 8, 48, 48, start=angle, extent=110, style="arc",
            outline=_ACCENT, width=4,
        )
        self.win.after(30, lambda: self._spin(angle + 22))

    def _set_status(self, text):
        self.win.after(0, lambda: self.status.config(text=text, fg=_TEXT_DIM))

    def _set_progress(self, frac):
        def _apply():
            self.pct.config(text=f"{int(frac * 100)}%")
            self.bar.delete("fill")
            _rounded_rect(
                self.bar, 0, 0, max(1, int((self.W - 72) * frac)), 6, 3,
                fill=_ACCENT, outline="", tags="fill",
            )
        self.win.after(0, _apply)

    def _fail(self, text):
        def _apply():
            self._spinning = False
            self.status.config(text=text, fg=_ERROR)
            self.pct.config(text="")
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
        self._spinning = False
        try:
            self.win.destroy()
        except Exception:
            pass
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
