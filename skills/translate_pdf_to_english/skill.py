import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
from urllib import request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_ENDPOINT = "https://translation.googleapis.com/v3/projects/{project}/locations/global:translateDocument"
_TARGET_LANG = "en"
_MIME_PDF = "application/pdf"
_SCOPE = "https://www.googleapis.com/auth/cloud-translation"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def _key_path():
    return os.environ.get("GOOGLE_KEY_PATH", "").strip() or os.path.join(_ROOT, "gcloud-key.json")


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _access_token():
    _load_env()
    path = _key_path()
    if not os.path.exists(path):
        return None, f"Service account key not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            key = json.load(f)
    except Exception as e:
        return None, f"Could not read service account key: {e}"
    client_email = key.get("client_email", "")
    private_key = key.get("private_key", "")
    token_uri = key.get("token_uri", _TOKEN_URI)
    if not client_email or not private_key:
        return None, "Invalid service account key (missing client_email/private_key)."
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": client_email,
        "scope": _SCOPE,
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = _b64url(json.dumps(header).encode()) + "." + _b64url(json.dumps(claims).encode())
    try:
        key_obj = serialization.load_pem_private_key(private_key.encode(), password=None)
        signature = key_obj.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    except Exception as e:
        return None, f"Could not sign JWT: {e}"
    jwt = signing_input + "." + _b64url(signature)
    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode("utf-8")
    req = request.Request(
        token_uri,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            token_resp = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return None, f"Token request failed: {e.code} {detail[:200]}"
    except Exception as e:
        return None, f"Token request failed: {e}"
    token = token_resp.get("access_token", "")
    if not token:
        return None, "Google returned no access token."
    return token, None


def _project_id():
    _load_env()
    pid = os.environ.get("GOOGLE_PROJECT_ID", "").strip()
    if pid:
        return pid
    path = _key_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return (json.load(f).get("project_id") or "").strip()
        except Exception:
            return ""
    return ""


def measure(file_path):
    """Return the number of pages in a PDF, or None if it can't be read."""
    # 1) pypdf — reliable, handles compressed object streams.
    try:
        from pypdf import PdfReader
        with open(file_path, "rb") as f:
            return len(PdfReader(f).pages)
    except Exception:
        pass
    # 2) Raw scan fallback (uncompressed PDFs only).
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
        return pages or None
    except Exception:
        return None


def run(text):
    """text: path to a PDF file to translate to English (Google Cloud Translation)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] This skill accepts PDF files only."
    project_id = _project_id()
    if not project_id:
        return "[Scryptian Error] Google project ID not set (GOOGLE_PROJECT_ID in .env or in the key file)."
    token, err = _access_token()
    if err:
        return f"[Scryptian Error] {err}"
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_en.pdf"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_en_{counter}.pdf"
        counter += 1
    try:
        with open(file_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("ascii")
        payload = json.dumps({
            "documentInputConfig": {
                "content": content_b64,
                "mimeType": _MIME_PDF,
            },
            "targetLanguageCode": _TARGET_LANG,
            "isTranslateNativePdfOnly": True,
        }).encode("utf-8")
        url = _ENDPOINT.format(project=project_id)
        req = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Scryptian",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        doc = data.get("documentTranslation") or {}
        outputs = doc.get("byteStreamOutputs") or []
        if not outputs:
            return "[Scryptian Error] Google returned no translated document."
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(outputs[0]))
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return f"[Scryptian Error] {e.code} {detail[:300]}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
