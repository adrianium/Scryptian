# Compress Video (Light) — local ffmpeg (free, no cloud cost). CRF 23 = near-lossless.

import os
import subprocess
import sys
import urllib.request

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".3gp"}
_CRF = "23"
_PRESET = "medium"


_FFMPEG_URL = "https://qvihfoeouvfveacexcol.supabase.co/storage/v1/object/public/actions/ffmpeg.exe"


def _ensure_ffmpeg():
    """Return ffmpeg.exe path, downloading it on first use from Supabase Storage."""
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    shared_dir = os.path.join(os.path.dirname(skill_dir), "_ffmpeg")
    ffmpeg_path = os.path.join(shared_dir, "ffmpeg.exe")

    if os.path.exists(ffmpeg_path):
        return ffmpeg_path

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if os.path.exists(bundled):
            return bundled

    try:
        os.makedirs(shared_dir, exist_ok=True)
        tmp = ffmpeg_path + ".part"
        req = urllib.request.Request(_FFMPEG_URL, headers={"User-Agent": "Scryptian"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as f:
            f.write(resp.read())
        os.replace(tmp, ffmpeg_path)
        return ffmpeg_path
    except Exception:
        return "ffmpeg"


def measure(file_path):
    """Return duration in seconds (informational preview)."""
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(file_path)
        for track in info.tracks:
            if track.track_type == "General" and track.duration:
                return float(track.duration) / 1000.0
    except Exception:
        pass
    return None


def run(text):
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Video file not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_EXTS:
        return "[Scryptian Error] Unsupported video format."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_compressed_light.mp4"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_compressed_light_{counter}.mp4"
        counter += 1

    cmd = [
        _ensure_ffmpeg(), "-y",
        "-i", file_path,
        "-c:v", "libx264", "-crf", _CRF, "-preset", _PRESET,
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=14400)
    except FileNotFoundError:
        return "[Scryptian Error] ffmpeg not found. Place ffmpeg.exe in skills/_ffmpeg/ or install ffmpeg."
    except Exception as e:
        return f"[Scryptian Error] {e}"
    if result.returncode != 0:
        err = (result.stderr or "").strip()[-400:]
        return f"[Scryptian Error] ffmpeg failed: {err}"
    return f"[Scryptian File] {out_path}"