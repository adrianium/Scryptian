import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
from urllib import request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

_ENDPOINT = "https://texttospeech.googleapis.com/v1/text:synthesize"
_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_VOICE = "en-US-Chirp3-HD-Puck"
_DEFAULT_LANG = "en-US"


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


def measure(file_path):
    """Return the number of characters in a text file, or None if it can't be read."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return len(f.read())
    except Exception:
        return None


def run(text):
    """text: path to a .txt file to convert to speech (Google Chirp 3 HD)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found. Copy a .txt file first."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except Exception as e:
        return f"[Scryptian Error] Could not read file: {e}"
    if not content:
        return "[Scryptian Error] File is empty."
    out_dir = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(out_dir, f"{base_name}_tts_male.wav")
    counter = 2
    while os.path.exists(out_path):
        out_path = os.path.join(out_dir, f"{base_name}_tts_male_{counter}.wav")
        counter += 1
    token, err = _access_token()
    if err:
        return f"[Scryptian Error] {err}"
    _load_env()
    voice = os.environ.get("GOOGLE_TTS_VOICE", "").strip() or _DEFAULT_VOICE
    lang = os.environ.get("GOOGLE_TTS_LANG", "").strip() or _DEFAULT_LANG
    try:
        payload = json.dumps({
            "input": {"text": content},
            "voice": {"languageCode": lang, "name": voice},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000},
        }).encode("utf-8")
        req = request.Request(
            _ENDPOINT,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Scryptian",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        audio_b64 = data.get("audioContent", "")
        if not audio_b64:
            return "[Scryptian Error] Google returned no audio."
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return f"[Scryptian Error] {e.code} {detail[:300]}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
