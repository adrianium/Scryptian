# Download YouTube Video — GenDownload API (free).

import json
import os
import re
import urllib.error
import urllib.request

_API = "https://gendownload.com/api/extract"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
_TARGET_QUALITY = 1080


def _extract(url):
    payload = json.dumps({"url": url}).encode("utf-8")
    req = urllib.request.Request(_API, data=payload, headers={"Content-Type": "application/json", "User-Agent": _UA}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_video_format(formats):
    videos = [f for f in formats if f.get("type") == "video"]
    def res(f):
        label = (f.get("label") or "").replace("p", "").strip()
        try:
            return int(label)
        except (TypeError, ValueError):
            return 0
    # Predictable: target 1080p exactly if available, else the highest <= 1080p.
    candidates = [f for f in videos if res(f) <= _TARGET_QUALITY]
    candidates.sort(key=res, reverse=True)
    return candidates[0] if candidates else (videos[0] if videos else None)


def _download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=600) as resp, open(out_path, "wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def run(text):
    """text: a YouTube URL to download as MP4."""
    url = (text or "").strip().strip('"')
    if not url.lower().startswith(("http://", "https://")):
        return "[Scryptian Error] Copy a YouTube link first (http/https URL)."

    out_dir = os.path.join(os.path.expanduser("~"), "Downloads", "Scryptian")
    os.makedirs(out_dir, exist_ok=True)

    try:
        data = _extract(url)
    except urllib.error.HTTPError as e:
        return f"[Scryptian Error] Download service error: HTTP {e.code}"
    except Exception as e:
        return f"[Scryptian Error] {e}"

    title = data.get("title") or "video"
    formats = data.get("formats") or []
    fmt = _pick_video_format(formats)
    if not fmt:
        return "[Scryptian Error] No video format available."

    safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip() or "video"
    ext = (fmt.get("ext") or "mp4").lower()
    out_path = os.path.join(out_dir, f"{safe}.{ext}")
    counter = 2
    while os.path.exists(out_path):
        out_path = os.path.join(out_dir, f"{safe}_{counter}.{ext}")
        counter += 1

    try:
        _download(fmt["url"], out_path)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        return f"[Scryptian Error] {e}"