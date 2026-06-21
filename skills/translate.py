# @title: Translate to my language
# @description: Translate text to your language (Google Translate)
# @author: Scryptian

import os
import sys
from urllib import request, parse
import json
import ssl
import bridge

if getattr(sys, "frozen", False):
    _BASE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Scryptian")
else:
    _BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_LANG_FILE = os.path.join(_BASE, "translate_lang.txt")


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _load_lang():
    try:
        if os.path.exists(_LANG_FILE):
            with open(_LANG_FILE, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def _save_lang(code):
    try:
        os.makedirs(os.path.dirname(_LANG_FILE), exist_ok=True)
        with open(_LANG_FILE, "w") as f:
            f.write(code.strip().lower())
    except Exception:
        pass


def _ask_lang():
    """Ask user for target language via PowerShell InputBox — works from any thread."""
    try:
        import subprocess
        ps = (
            "[System.Reflection.Assembly]::LoadWithPartialName('Microsoft.VisualBasic') | Out-Null; "
            "$r = [Microsoft.VisualBasic.Interaction]::InputBox("
            "'Enter your language code (e.g. ru, de, fr, zh, ar)', 'Scryptian — Translate', ''); "
            "Write-Output $r"
        )
        result = subprocess.run(
            ["powershell", "-Sta", "-Command", ps],
            capture_output=True, text=True, timeout=60,
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
        lang = result.stdout.strip()
        if lang:
            return lang.strip().lower()
    except Exception:
        pass
    return None


def _get_lang_code():
    lang = _load_lang()
    if lang:
        return lang
    lang = _ask_lang()
    if not lang:
        lang = "en"
    _save_lang(lang)
    return lang


def run(text):
    """
    text: text from clipboard to translate to your language
    """
    try:
        tl = _get_lang_code()
        url = "https://translate.googleapis.com/translate_a/single"
        params = parse.urlencode({"client": "gtx", "sl": "auto", "tl": tl, "dt": "t", "q": text})
        resp = request.urlopen(f"{url}?{params}", timeout=10, context=_ssl_ctx())
        data = json.loads(resp.read())
        return "".join(part[0] for part in data[0] if part[0])
    except Exception:
        return bridge.generate(f"Translate the following text to {tl}. Output ONLY the translated text:\n\n{text}")
