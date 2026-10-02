# Compress Video (Balanced) — CloudConvert.
#
# Flow: local video -> import/upload -> convert (H.264 CRF 28) -> export/url
#       -> poll -> download compressed MP4.

import json
import os
import sys
import time
import uuid
import urllib.error
from urllib import request

_BASE_URL = "https://api.cloudconvert.com/v2"
_CRF = 28
_MAX_POLL_SECONDS = 18000  # CloudConvert default task timeout is 5 hours

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".3gp"}


def _load_env():
    paths = []
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        paths.append(os.path.join(d, ".env"))
        d = os.path.dirname(d)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        paths.append(os.path.join(sys._MEIPASS, ".env"))
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass
        return


def _api_key():
    _load_env()
    return os.environ.get("CLOUDCONVERT_API_KEY", "").strip()


def _headers():
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": "Scryptian",
    }


def _create_job():
    payload = json.dumps({
        "tasks": {
            "import-file": {"operation": "import/upload"},
            "convert-file": {
                "operation": "convert",
                "input": "import-file",
                "output_format": "mp4",
                "video_codec": "x264",
                "crf": _CRF,
                "audio_codec": "aac",
                "audio_bitrate": 128,
            },
            "export-file": {"operation": "export/url", "input": "convert-file"},
        }
    }).encode("utf-8")
    req = request.Request(f"{_BASE_URL}/jobs", data=payload, headers=_headers(), method="POST")
    with request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))["data"]
    job_id = data.get("id")
    form_url = None
    parameters = {}
    for task in data.get("tasks", []):
        if task.get("operation") == "import/upload":
            form = (task.get("result") or {}).get("form") or {}
            form_url = form.get("url")
            parameters = form.get("parameters") or {}
            break
    return job_id, form_url, parameters


def _upload(form_url, parameters, file_path, filename):
    boundary = uuid.uuid4().hex
    buf = bytearray()
    for key, value in parameters.items():
        buf += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    buf += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f'Content-Type: application/octet-stream\r\n\r\n'
    ).encode()
    with open(file_path, "rb") as f:
        buf += f.read()
    buf += f"\r\n--{boundary}--\r\n".encode()

    req = request.Request(form_url, data=bytes(buf), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "Scryptian")
    with request.urlopen(req, timeout=3600) as resp:
        resp.read()


def _poll(job_id):
    url = f"{_BASE_URL}/jobs/{job_id}"
    start = time.time()
    while True:
        req = request.Request(url, headers=_headers())
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))["data"]
        status = data.get("status")
        if status == "finished":
            for task in data.get("tasks", []):
                if task.get("operation") == "export/url" and task.get("status") == "finished":
                    files = (task.get("result") or {}).get("files") or []
                    if files and files[0].get("url"):
                        return files[0]["url"], None
            return None, "No export URL in finished job."
        if status == "error":
            parts = []
            for task in data.get("tasks", []):
                if task.get("status") == "error":
                    name = task.get("name") or task.get("operation") or "task"
                    code = task.get("code") or ""
                    message = task.get("message") or ""
                    detail = " ".join(x for x in (name, code, message) if x)
                    if detail:
                        parts.append(detail)
            return None, " | ".join(parts) if parts else "Job failed."
        if time.time() - start > _MAX_POLL_SECONDS:
            return None, "Compression timed out."
        time.sleep(3)


def _download(url, out_path):
    req = request.Request(url, headers={"User-Agent": "Scryptian"})
    with request.urlopen(req, timeout=3600) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)


def _duration_seconds(file_path):
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(file_path)
        for track in info.tracks:
            if track.track_type == "General" and track.duration:
                return float(track.duration) / 1000.0
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.run(
            ["mediainfo", "--Output=JSON", file_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        for t in data.get("media", {}).get("track", []):
            if t.get("@type") == "General" and t.get("Duration"):
                return float(t["Duration"]) / 1000.0
    except Exception:
        pass
    return None


def measure(file_path):
    """Return video duration in minutes (used for per-minute pricing)."""
    secs = _duration_seconds(file_path)
    if secs:
        return secs / 60.0
    return None


def run(text):
    """text: path to a video file to compress (CloudConvert, H.264 CRF 28)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Video file not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_EXTS:
        return "[Scryptian Error] Unsupported video format."
    if not _api_key():
        return "[Scryptian Error] CloudConvert key not set (CLOUDCONVERT_API_KEY in .env)."

    filename = os.path.basename(file_path)
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_compressed.mp4"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_compressed_{counter}.mp4"
        counter += 1

    try:
        job_id, form_url, parameters = _create_job()
        if not job_id or not form_url:
            return "[Scryptian Error] CloudConvert did not return an upload form."
        _upload(form_url, parameters, file_path, filename)
        output_url, err = _poll(job_id)
        if err:
            return f"[Scryptian Error] {err}"
        if not output_url:
            return "[Scryptian Error] CloudConvert returned no output."
        _download(output_url, out_path)
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return f"[Scryptian Error] {e.code} {detail[:300]}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
