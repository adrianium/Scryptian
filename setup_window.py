# setup_window.py — First-launch runtime downloader (Discord-style centered window).
# Shows a small centered window with a spinner + progress bar while downloading
# ffmpeg + ghostscript into runtimes/. Runs before the main bar on first launch.

import os
import threading
import tkinter as tk
import urllib.request
import zipfile

import runtime_bins

_GHOSTSCRIPT_URL = "https://qvihfoeouvfveacexcol.supabase.co/storage/v1/object/public/actions/ghostscript.zip"

_BG = "#202020"
_BORDER = "#3C3C3C"
_TEXT = "#FFFFFF"
_TEXT_DIM = "#9A9A9A"
_ACCENT = "#60CDFF"

# True while the first-launch downloader is showing (suppresses the main bar).
ACTIVE = False


def _app_root():
    return runtime_bins.app_root()


def _runtime_root():
    return os.path.join(_app_root(), "runtimes")


def _missing():
    """Return a list of (dir_name, file_name, url, is_zip) for missing runtimes."""
    missing = []
    base = _runtime_root()
    if runtime_bins.needs_ffmpeg():
        missing.append(("ffmpeg", "ffmpeg.exe", runtime_bins.FFMPEG_URL, False))
    if not os.path.exists(os.path.join(base, "ghostscript", "bin", "gswin64c.exe")):
        missing.append(("ghostscript", "ghostscript.zip", _GHOSTSCRIPT_URL, True))
    return missing


def _round_corners(win):
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetAncestor(win.winfo_id(), 2)
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


def _rounded_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def show_setup_window(root):
    """Show the first-launch download window if runtimes are missing. Returns the
    Toplevel (blocking the main bar) or None if nothing needs downloading."""
    missing = _missing()
    if not missing:
        return None

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.attributes("-topmost", True)
    win.configure(bg=_BORDER)

    outer = tk.Frame(win, bg=_BORDER, padx=1, pady=1)
    outer.pack(fill="both", expand=True)
    inner = tk.Frame(outer, bg=_BG)
    inner.pack(fill="both", expand=True)

    W = 380
    H = 240

    # Spinner (rotating arc)
    spinner = tk.Canvas(inner, width=56, height=56, bg=_BG, highlightthickness=0, bd=0)
    spinner.pack(pady=(36, 8))

    tk.Label(inner, text="Scryptian", bg=_BG, fg=_TEXT,
             font=("Segoe UI Variable", 16, "bold")).pack()

    status = tk.Label(inner, text="Downloading components…", bg=_BG, fg=_TEXT_DIM,
                      font=("Segoe UI Variable", 12))
    status.pack(pady=(6, 0))

    # Progress bar (thin rounded)
    bar = tk.Canvas(inner, width=W - 72, height=6, bg=_BG, highlightthickness=0, bd=0)
    bar.pack(pady=(18, 0))
    _rounded_rect(bar, 0, 0, W - 72, 6, 3, fill="#2B2B2B", outline="")

    pct = tk.Label(inner, text="0%", bg=_BG, fg=_ACCENT,
                   font=("Segoe UI Variable", 12))
    pct.pack(pady=(10, 0))

    # Center the window
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    win.geometry(f"{W}x{H}+{x}+{y}")
    win.update_idletasks()
    _round_corners(win)

    # Spinner animation
    def _spin(angle=0):
        if not win.winfo_exists():
            return
        spinner.delete("all")
        spinner.create_arc(8, 8, 48, 48, start=angle, extent=110, style="arc",
                           outline=_ACCENT, width=4)
        win.after(30, lambda: _spin(angle + 22))

    _spin()

    # Download in a background thread, reporting progress
    def _download_one(name, filename, url, is_zip):
        base = _runtime_root()
        dest_dir = os.path.join(base, name)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)

        req = urllib.request.Request(url, headers={"User-Agent": "Scryptian"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            tmp = dest + ".part"
            done = 0
            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        yield done / total
            os.replace(tmp, dest)

        if is_zip:
            try:
                with zipfile.ZipFile(dest) as z:
                    z.extractall(dest_dir)
                os.remove(dest)
            except Exception:
                pass

    def _work():
        import queue
        q = queue.Queue()

        def _download_worker():
            try:
                n = len(missing)
                for i, (name, filename, url, is_zip) in enumerate(missing):
                    q.put(("status", f"Downloading {name}…"))
                    if name == "ffmpeg":
                        def _prog(frac, i=i, n=n):
                            q.put(("progress", (i + frac) / n))
                        runtime_bins.ensure_ffmpeg(on_progress=_prog)
                        q.put(("progress", (i + 1) / n))
                        continue
                    for frac in _download_one(name, filename, url, is_zip):
                        q.put(("progress", (i + frac) / n))
            except Exception:
                pass
            finally:
                q.put(("done", None))

        def _poll():
            try:
                while True:
                    kind, val = q.get_nowait()
                    if kind == "status":
                        status.config(text=val)
                    elif kind == "progress":
                        pct.config(text=f"{int(val * 100)}%")
                        bar.delete("fill")
                        _rounded_rect(bar, 0, 0, max(1, int((W - 72) * val)), 6, 3, fill=_ACCENT, outline="")
                    elif kind == "done":
                        win.after(300, lambda: win.destroy())
                        return
            except queue.Empty:
                pass
            if win.winfo_exists():
                root.after(50, _poll)

        threading.Thread(target=_download_worker, daemon=True).start()
        root.after(50, _poll)

    threading.Thread(target=_work, daemon=True).start()
    return win