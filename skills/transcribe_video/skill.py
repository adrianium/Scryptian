import json
import os
import sys
import time
import urllib.error
from urllib import request

_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
_MAX_POLL_SECONDS = 900


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
    return os.environ.get("ASSEMBLYAI_KEY", "").strip()


def _headers():
    return {"Authorization": _api_key(), "User-Agent": "Scryptian"}


def _upload(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    headers = _headers()
    headers["Content-Type"] = "application/octet-stream"
    req = request.Request(_UPLOAD_URL, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))["upload_url"]


def _submit(upload_url):
    payload = json.dumps({
        "audio_url": upload_url,
        "speaker_labels": True,
        "speech_models": ["universal-2"],
    }).encode("utf-8")
    headers = _headers()
    headers["Content-Type"] = "application/json"
    req = request.Request(_TRANSCRIPT_URL, data=payload, headers=headers, method="POST")
    with request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))["id"]


def _poll(transcript_id):
    url = f"{_TRANSCRIPT_URL}/{transcript_id}"
    start = time.time()
    while True:
        req = request.Request(url, headers=_headers())
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        if status in ("completed", "error"):
            return data
        if time.time() - start > _MAX_POLL_SECONDS:
            return {"status": "error", "error": "Transcription timed out."}
        time.sleep(3)


def _format(data):
    utterances = data.get("utterances")
    if utterances:
        lines = []
        for u in utterances:
            speaker = u.get("speaker", "?")
            text = (u.get("text") or "").strip()
            if text:
                lines.append(f"Speaker {speaker}: {text}")
        if lines:
            return "\n".join(lines)
    return (data.get("text") or "").strip()


def measure(file_path):
    """Return media duration in seconds (float), or None if it can't be read."""
    # 1) MediaInfo — audio + video (pymediainfo)
    try:
        from pymediainfo import MediaInfo
        info = MediaInfo.parse(file_path)
        for track in info.tracks:
            if track.track_type == "General" and track.duration:
                return float(track.duration) / 1000.0
    except Exception:
        pass
    # 2) MediaInfo CLI fallback
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


def run(text):
    """
    text: path to a video file to transcribe (AssemblyAI).
    """
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Video file not found."
    if not _api_key():
        return "[Scryptian Error] AssemblyAI key not set (ASSEMBLYAI_KEY in .env)."
    try:
        upload_url = _upload(file_path)
        transcript_id = _submit(upload_url)
        data = _poll(transcript_id)
        if data.get("status") == "error":
            return f"[Scryptian Error] {data.get('error', 'Transcription failed.')}"
        result = _format(data)
        if not result:
            return "[Scryptian Error] Empty transcript."
        base, _ = os.path.splitext(file_path)
        out_path = f"{base}_transcript.txt"
        counter = 2
        while os.path.exists(out_path):
            out_path = f"{base}_transcript_{counter}.txt"
            counter += 1
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result)
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as e:
        return f"[Scryptian Error] {e}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
