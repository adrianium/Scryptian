# Extract Audio — local ffmpeg (free, no cloud cost). Video -> WAV (PCM).

import os
import subprocess

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error("extract_audio", detail)
        except Exception:
            pass

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".3gp"}


def _ensure_ffmpeg():
    """Return essentials ffmpeg.exe from runtimes/ffmpeg, downloading it if needed."""
    try:
        import runtime_bins
        return runtime_bins.ensure_ffmpeg()
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
    """text: path to a video to extract audio from (WAV)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this video. Copy it again and try."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_EXTS:
        return "[Scryptian Error] This video type isn't supported."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_audio.wav"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_audio_{counter}.wav"
        counter += 1

    cmd = [
        _ensure_ffmpeg(), "-y",
        "-i", file_path,
        "-vn", "-map", "0:a:0?", "-c:a", "pcm_s16le",
        out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=14400, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        _report("ffmpeg not found")
        return "[Scryptian Error] This action isn't set up yet. We're on it."
    except Exception as e:
        _report(str(e))
        return "[Scryptian Error] Something went wrong. We're on it."
    if result.returncode != 0:
        err = (result.stderr or "").strip()[-400:]
        _report(f"ffmpeg failed: {err}")
        return "[Scryptian Error] Couldn't convert this video. We're on it."
    return f"[Scryptian File] {out_path}"