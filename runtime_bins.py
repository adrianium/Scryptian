# runtime_bins.py — shared download of local tools into runtimes/.
#
# ffmpeg is the Gyan essentials build (all common codecs), not the old
# stripped ffmpeg.exe. Files land in <app>/runtimes/ffmpeg/.

import os
import subprocess
import sys
import urllib.request

FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z"
_MARKER = "essentials"

def app_root():
    """Folder next to Scryptian.exe when frozen, project root in dev."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.dirname(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def runtime_root():
    return os.path.join(app_root(), "runtimes")


def ffmpeg_dir():
    return os.path.join(runtime_root(), "ffmpeg")


def ffmpeg_exe():
    return os.path.join(ffmpeg_dir(), "ffmpeg.exe")


def sevenzr_path():
    """Bundled 7zr.exe. No install step: it is just a file we run."""
    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "7zr.exe"))
        candidates.append(os.path.join(os.path.dirname(sys._MEIPASS), "7zr.exe"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "tools", "7zr.exe"))
    candidates.append(os.path.join(app_root(), "7zr.exe"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("7zr.exe")


def needs_ffmpeg():
    """True when ffmpeg is missing or still the old stripped build."""
    exe = ffmpeg_exe()
    marker = os.path.join(ffmpeg_dir(), "build.txt")
    if not os.path.isfile(exe):
        return True
    try:
        with open(marker, "r", encoding="utf-8") as f:
            return f.read().strip() != _MARKER
    except Exception:
        return True


def ensure_ffmpeg(on_progress=None):
    """Return path to essentials ffmpeg.exe, downloading it if needed."""
    exe = ffmpeg_exe()
    if not needs_ffmpeg():
        return exe

    dest_dir = ffmpeg_dir()
    os.makedirs(dest_dir, exist_ok=True)
    archive = os.path.join(dest_dir, "essentials.7z.part")
    try:
        _download(FFMPEG_URL, archive, on_progress)
        _extract_bins(archive, dest_dir)
        if not os.path.isfile(exe):
            raise RuntimeError("essentials archive has no ffmpeg.exe")
        with open(os.path.join(dest_dir, "build.txt"), "w", encoding="utf-8") as f:
            f.write(_MARKER + "\n")
        return exe
    finally:
        try:
            os.remove(archive)
        except Exception:
            pass


def _download(url, dest, on_progress, timeout=1800):
    req = urllib.request.Request(url, headers={"User-Agent": "Scryptian"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if on_progress and total:
                    on_progress(done / total)


def _extract_bins(archive, dest_dir):
    # `e` flattens bin/ffmpeg.exe into dest_dir. -y answers yes, so nothing asks the user.
    cmd = [
        sevenzr_path(), "e", archive, f"-o{dest_dir}", "-y", "-r",
        "ffmpeg.exe", "ffprobe.exe",
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(cmd, capture_output=True, creationflags=flags)
    if result.returncode != 0 or not os.path.isfile(os.path.join(dest_dir, "ffmpeg.exe")):
        err = (result.stderr or result.stdout or b"").decode("utf-8", "replace")[-400:]
        raise RuntimeError(err or "7zr failed to extract ffmpeg")

