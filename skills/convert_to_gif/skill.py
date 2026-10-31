# Convert video — local ffmpeg essentials (free). Target comes from manifest output_type.

import json
import os
import subprocess

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ID = os.path.basename(_SKILL_DIR)


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error(_SKILL_ID, detail)
        except Exception:
            pass


def _output_ext():
    try:
        with open(os.path.join(_SKILL_DIR, "manifest.json"), encoding="utf-8") as f:
            out = json.load(f).get("output_type") or ".mp4"
        if isinstance(out, list):
            out = out[0] if out else ".mp4"
        out = str(out).lower()
        if not out.startswith("."):
            out = "." + out
        return out
    except Exception:
        return ".mp4"


def _ensure_ffmpeg():
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


def _encode_args(ext, out_path):
    if ext == ".gif":
        return [
            "-map", "0:v:0?",
            "-vf", "fps=12,scale=640:-2:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse",
            "-loop", "0",
            out_path,
        ]
    if ext == ".webm":
        return [
            "-map", "0:v?", "-map", "0:a?",
            "-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-cpu-used", "4", "-row-mt", "1",
            "-c:a", "libopus", "-b:a", "128k",
            out_path,
        ]
    if ext == ".avi":
        return [
            "-map", "0:v?", "-map", "0:a?",
            "-c:v", "mpeg4", "-q:v", "5",
            "-c:a", "libmp3lame", "-b:a", "192k",
            out_path,
        ]
    args = [
        "-map", "0:v?", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
    ]
    if ext in (".mp4", ".mov"):
        args += ["-movflags", "+faststart"]
    args.append(out_path)
    return args


def run(text):
    """text: path to a media file. Output extension comes from manifest output_type."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this file. Copy it again and try."

    ext = _output_ext()
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}{ext}"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_{counter}{ext}"
        counter += 1

    cmd = [_ensure_ffmpeg(), "-y", "-i", file_path] + _encode_args(ext, out_path)
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=14400, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        _report("ffmpeg not found")
        return "[Scryptian Error] This action isn't set up yet. We're on it."
    except Exception as e:
        _report(str(e))
        return "[Scryptian Error] Something went wrong. We're on it."
    if result.returncode != 0 or not os.path.isfile(out_path):
        err = (result.stderr or "").strip()[-400:]
        _report(f"ffmpeg failed: {err}")
        return "[Scryptian Error] Couldn't convert this file. We're on it."
    return f"[Scryptian File] {out_path}"
