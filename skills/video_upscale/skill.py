# Upscale Video — fal.ai (RealESRGAN video upscaler).
#
# Flow: local video -> fal CDN upload -> queue submit -> poll -> download.

import json
import os
import sys
import time
import urllib.error
from urllib import request

_UPLOAD_INIT = "https://rest.alpha.fal.ai/storage/upload/initiate"
_QUEUE_BASE = "https://queue.fal.run"
_ENDPOINT = "fal-ai/video-upscaler"
_SCALE = 2
_MAX_POLL_SECONDS = 3600

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".3gp"}

_MIME = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
}


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
    return os.environ.get("FAL_KEY", "").strip()


def _headers():
    return {
        "Authorization": f"Key {_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": "Scryptian",
    }


def _upload(file_path, filename, ext):
    mime = _MIME.get(ext, "video/mp4")
    payload = json.dumps({"content_type": mime, "file_name": filename}).encode("utf-8")
    req = request.Request(_UPLOAD_INIT, data=payload, headers=_headers(), method="POST")
    with request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    upload_url = data.get("upload_url")
    file_url = data.get("file_url")
    if not upload_url or not file_url:
        raise Exception("fal upload initiate returned no URLs.")

    with open(file_path, "rb") as f:
        body = f.read()
    put_req = request.Request(upload_url, data=body, method="PUT")
    put_req.add_header("Content-Type", mime)
    put_req.add_header("User-Agent", "Scryptian")
    with request.urlopen(put_req, timeout=3600) as resp:
        resp.read()
    return file_url


def _submit(file_url):
    payload = json.dumps({"video_url": file_url, "scale": _SCALE}).encode("utf-8")
    req = request.Request(f"{_QUEUE_BASE}/{_ENDPOINT}", data=payload, headers=_headers(), method="POST")
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _poll(submit_data):
    status_url = submit_data.get("status_url")
    response_url = submit_data.get("response_url")
    if not status_url:
        return None, "fal.ai returned no status_url."
    start = time.time()
    while True:
        req = request.Request(status_url, headers=_headers())
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        print(f"[Upscale] status: {status}")
        if status == "COMPLETED":
            if not response_url:
                response_url = data.get("response_url")
            if not response_url:
                return None, "fal.ai returned no response_url."
            req2 = request.Request(response_url, headers=_headers())
            with request.urlopen(req2, timeout=60) as resp2:
                return json.loads(resp2.read().decode("utf-8")), None
        if status in ("FAILED", "CANCELLED", "ERROR"):
            return None, str(data.get("error") or data.get("message") or status)
        if time.time() - start > _MAX_POLL_SECONDS:
            return None, "Upscale timed out."
        time.sleep(5)


def _download(url, out_path):
    print("[Upscale] Downloading result...")
    req = request.Request(url, headers={"User-Agent": "Scryptian"})
    total = 0
    with request.urlopen(req, timeout=600) as resp:
        with open(out_path, "wb") as f:
            while True:
                chunk = resp.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                print(f"[Upscale] downloaded {total / (1024 * 1024):.1f} MB")
    print("[Upscale] Download complete.")


def _video_meta(file_path):
    """Return (width, height, fps, frame_count_or_None, duration_seconds_or_None)."""
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(file_path)
        w = h = fps = frames = dur = None
        for track in info.tracks:
            if track.track_type == "General":
                if track.duration:
                    dur = float(track.duration) / 1000.0
                if getattr(track, "frame_count", None):
                    frames = float(track.frame_count)
            elif track.track_type == "Video":
                if track.width:
                    w = float(track.width)
                if track.height:
                    h = float(track.height)
                if track.frame_rate:
                    fps = float(track.frame_rate)
        if w and h and fps:
            return w, h, fps, frames, dur
    except Exception:
        pass
    try:
        import subprocess
        out = subprocess.run(
            ["mediainfo", "--Output=JSON", file_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(out.stdout)
        w = h = fps = frames = dur = None
        for t in data.get("media", {}).get("track", []):
            if t.get("@type") == "General":
                if t.get("Duration"):
                    dur = float(t["Duration"]) / 1000.0
                if t.get("FrameCount"):
                    frames = float(t["FrameCount"])
            elif t.get("@type") == "Video":
                if t.get("Width"):
                    w = float(t["Width"])
                if t.get("Height"):
                    h = float(t["Height"])
                if t.get("FrameRate"):
                    fps = float(t["FrameRate"])
        if w and h and fps:
            return w, h, fps, frames, dur
    except Exception:
        pass
    return None


def measure(file_path):
    """Return output megapixels (width*scale x height*scale x frames) for per-MP pricing."""
    meta = _video_meta(file_path)
    if not meta:
        return None
    w, h, fps, frames, dur = meta
    out_w = w * _SCALE
    out_h = h * _SCALE
    if frames:
        total_frames = frames
    elif dur:
        total_frames = dur * fps
    else:
        return None
    return (out_w * out_h * total_frames) / 1000000.0


def run(text):
    """text: path to a video file to upscale 2x (fal.ai RealESRGAN)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Video file not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_EXTS:
        return "[Scryptian Error] Unsupported video format."
    if not _api_key():
        return "[Scryptian Error] fal.ai key not set (FAL_KEY in .env)."

    filename = os.path.basename(file_path)
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_upscaled.mp4"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_upscaled_{counter}.mp4"
        counter += 1

    try:
        file_url = _upload(file_path, filename, ext)
        print("[Upscale] Uploaded to fal CDN.")
        submit_data = _submit(file_url)
        print("[Upscale] Job submitted.")
        result, err = _poll(submit_data)
        if err:
            return f"[Scryptian Error] {err}"
        video = (result or {}).get("video") or {}
        output_url = video.get("url")
        if not output_url:
            return "[Scryptian Error] fal.ai returned no video URL."
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
