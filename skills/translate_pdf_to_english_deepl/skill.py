# Translate PDF to English (DeepL) — preserves layout.
#
# Flow: local PDF -> DeepL document upload -> poll status -> download translated PDF.

import json
import os
import re
import sys
import time
import uuid
import urllib.error
from urllib import request

_TARGET_LANG = "EN"
_MAX_POLL_SECONDS = 1800


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
    return os.environ.get("DEEPL_AUTH_KEY", "").strip()


def _api_url():
    _load_env()
    return os.environ.get("DEEPL_API_URL", "https://api-free.deepl.com").rstrip("/")


def _json_headers():
    return {
        "Authorization": f"DeepL-Auth-Key {_api_key()}",
        "Content-Type": "application/json",
        "User-Agent": "Scryptian",
    }


def _upload(file_path):
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    buf = bytearray()
    buf += f'--{boundary}\r\nContent-Disposition: form-data; name="target_lang"\r\n\r\n{_TARGET_LANG}\r\n'.encode()
    buf += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
    with open(file_path, "rb") as f:
        buf += f.read()
    buf += f"\r\n--{boundary}--\r\n".encode()

    req = request.Request(f"{_api_url()}/v2/document", data=bytes(buf), method="POST")
    req.add_header("Authorization", f"DeepL-Auth-Key {_api_key()}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "Scryptian")
    with request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("document_id"), data.get("document_key")


def _poll(document_id, document_key):
    url = f"{_api_url()}/v2/document/{document_id}"
    payload = json.dumps({"document_key": document_key}).encode("utf-8")
    start = time.time()
    while True:
        req = request.Request(url, data=payload, headers=_json_headers(), method="POST")
        with request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status")
        if status == "done":
            return None
        if status == "error":
            return data.get("message") or "Translation failed."
        if time.time() - start > _MAX_POLL_SECONDS:
            return "Translation timed out."
        time.sleep(3)


def _download(document_id, document_key, out_path):
    url = f"{_api_url()}/v2/document/{document_id}/result"
    payload = json.dumps({"document_key": document_key}).encode("utf-8")
    req = request.Request(url, data=payload, headers=_json_headers(), method="POST")
    with request.urlopen(req, timeout=600) as resp:
        data = resp.read()
    with open(out_path, "wb") as f:
        f.write(data)


def measure(file_path):
    """Return the number of pages in a PDF, or None if it can't be read."""
    try:
        from pypdf import PdfReader
        with open(file_path, "rb") as f:
            return len(PdfReader(f).pages)
    except Exception:
        pass
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
        return pages or None
    except Exception:
        return None


def run(text):
    """text: path to a PDF file to translate to English (DeepL, layout preserved)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] This skill accepts PDF files only."
    if not _api_key():
        return "[Scryptian Error] DeepL key not set (DEEPL_AUTH_KEY in .env)."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_en.pdf"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_en_{counter}.pdf"
        counter += 1

    try:
        document_id, document_key = _upload(file_path)
        if not document_id or not document_key:
            return "[Scryptian Error] DeepL did not return a document id."
        err = _poll(document_id, document_key)
        if err:
            return f"[Scryptian Error] {err}"
        _download(document_id, document_key, out_path)
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return f"[Scryptian Error] {e.code} {detail[:300]}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
