# Upscale Image — Replicate Real-ESRGAN (4x, optional GFPGAN face enhance).
#
# Flow: local image -> base64 data URI -> Replicate prediction -> poll -> save PNG.

import base64
import json
import os
import sys
import time
import urllib.error
from urllib import request

_MODEL = "nightmareai/real-esrgan"
_PREDICT_URL = f"https://api.replicate.com/v1/models/{_MODEL}/predictions"
_MAX_POLL_SECONDS = 600

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
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
    mime = _MIME.get(ext, "image/png")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _submit(data_uri):
    payload = json.dumps({
        "input": {
            "image": data_uri,
            "scale": 4,
            "face_enhance": True,
        }
    }).encode("utf-8")
    req = request.Request(_PREDICT_URL, data=payload, headers=_headers(), method="POST")
    with request.urlopen(req, timeout=60) as resp:
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
            return None, "Upscale timed out."
        time.sleep(2)


def _download(url, out_path):
    req = request.Request(url, headers={"User-Agent": "Scryptian"})
    with request.urlopen(req, timeout=300) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)


def measure(file_path):
    return 1


def run(text):
    """text: path to an image file to upscale 4x (Replicate Real-ESRGAN)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Image file not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _MIME:
        return "[Scryptian Error] Unsupported image format."
    if not _api_key():
        return "[Scryptian Error] Replicate token not set (REPLICATE_API_TOKEN in .env)."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_upscaled.png"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_upscaled_{counter}.png"
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
