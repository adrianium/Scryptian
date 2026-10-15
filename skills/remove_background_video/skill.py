# Remove Background (Video) — Replicate Robust Video Matting (RVM).
#
# Flow: local video -> base64 data URI -> Replicate prediction -> poll -> save output video.

import base64
import json
import os
import sys
import time
import urllib.error
from urllib import request

_MODEL = "arielreplicate/robust_video_matting"
_MODEL_VERSION = "73d2128a371922d5d1abf0712a1d974be0e4e2358cc1218e4e34714767232bac"
_PREDICT_URL = f"https://api.replicate.com/v1/models/{_MODEL}/versions/{_MODEL_VERSION}/predictions"
# output_type: "green-screen" | "alpha-mask" | "foreground-mask"
_OUTPUT_TYPE = "green-screen"
_MAX_POLL_SECONDS = 1800

_VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
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
    return os.environ.get("REPLICATE_API_TOKEN", "").strip()


def _headers():
    return {
        "Authorization": f"Token {_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": "Scryptian",
    }


def _data_uri(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    mime = _VIDEO_MIME.get(ext, "video/mp4")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _submit(data_uri):
    payload = json.dumps({
        "input": {
            "input_video": data_uri,
            "output_type": _OUTPUT_TYPE,
        }
    }).encode("utf-8")
    req = request.Request(_PREDICT_URL, data=payload, headers=_headers(), method="POST")
    with request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _poll(prediction_id):
    url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
    start = time.time()
    while True:
        req = request.Request(url, headers=_headers())
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        if status == "succeeded":
            return data.get("output"), None
        if status in ("failed", "canceled"):
            return None, str(data.get("error") or status)
        if time.time() - start > _MAX_POLL_SECONDS:
            return None, "Video background removal timed out."
        time.sleep(3)


def _download(url, out_path):
    req = request.Request(url, headers={"User-Agent": "Scryptian"})
    with request.urlopen(req, timeout=600) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)


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
    return None


def measure(file_path):
    """Return input megapixels (width x height x frames) for per-MP pricing."""
    meta = _video_meta(file_path)
    if not meta:
        return None
    w, h, fps, frames, dur = meta
    if frames:
        total = frames
    elif dur:
        total = dur * fps
    else:
        return None
    return (w * h * total) / 1000000.0


def run(text):
    """text: path to a video to remove the background from (Replicate RVM)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Video file not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _VIDEO_MIME:
        return "[Scryptian Error] Unsupported video format."
    if not _api_key():
        return "[Scryptian Error] Replicate token not set (REPLICATE_API_TOKEN in .env)."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_green_screen.mp4"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_green_screen_{counter}.mp4"
        counter += 1

    try:
        pred = _submit(_data_uri(file_path))
        pred_id = pred.get("id")
        if not pred_id:
            return "[Scryptian Error] Replicate returned no prediction id."
        output_url, err = _poll(pred_id)
        if err:
            return f"[Scryptian Error] {err}"
        if not output_url:
            return "[Scryptian Error] Replicate returned no output."
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