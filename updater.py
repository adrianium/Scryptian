# updater.py — silent auto-update through the existing Inno Setup installer.
#
# Flow (only when running as the installed .exe):
#   1) main.py detects a newer GitHub release.
#   2) We download the Scryptian_Setup.exe asset in the background.
#   3) When the user is idle, main.py launches the installer with
#      /VERYSILENT /AUTOUPDATE and quits; Inno swaps the files and relaunches.
#
# The huge model file lives in a separate data dir and is never touched here,
# so updates only move the small app folder.

import os
import sys
import ssl
import tempfile
import subprocess
import ctypes
from urllib import request

SETUP_ASSET = "Scryptian_Setup.exe"

# Windows process-creation flags: run the installer detached so it survives
# after the main app exits.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def is_frozen() -> bool:
    """True only when running as the packaged .exe (not from source)."""
    return bool(getattr(sys, "frozen", False))


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input. Returns 0.0 on failure."""
    try:
        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, millis / 1000.0)
    except Exception:
        return 0.0


def find_setup_url(assets):
    """Pick the installer download URL from a GitHub release's assets list."""
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if name == SETUP_ASSET.lower() or (name.endswith(".exe") and "setup" in name):
            return a.get("browser_download_url")
    return None


def updates_dir() -> str:
    """Per-user folder where downloaded installers are staged."""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    d = os.path.join(base, "Scryptian", "updates")
    os.makedirs(d, exist_ok=True)
    return d


def download(url: str, dest: str) -> str:
    """Download url to dest atomically (writes .part, then renames)."""
    req = request.Request(url, headers={"User-Agent": "Scryptian"})
    tmp = dest + ".part"
    with request.urlopen(req, timeout=60, context=_ssl_ctx()) as resp, open(tmp, "wb") as f:
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)
    return dest


def launch_installer(setup_path: str) -> None:
    """Start the installer silently in auto-update mode, detached from us."""
    subprocess.Popen(
        [setup_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/AUTOUPDATE"],
        close_fds=True,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP,
    )
