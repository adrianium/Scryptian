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
    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_BASE, exist_ok=True)

_LANG_FILE = os.path.join(_BASE, "translate_lang.txt")


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _load_lang():
    # Try shared profile first
    lang = bridge.get_profile().get("lang")
    if lang:
        return lang.strip().lower()
    # Fallback: registry (legacy)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Scryptian", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "TranslateLang")
        winreg.CloseKey(key)
        if value:
            return value.strip().lower()
    except Exception:
        pass
    # Fallback: file (legacy)
    try:
        if os.path.exists(_LANG_FILE):
            with open(_LANG_FILE, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return None


def _save_lang(code):
    code = code.strip().lower()
    # Save to shared profile (primary)
    bridge.set_profile({"lang": code})
    # Keep registry as backup (legacy)
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Scryptian")
        winreg.SetValueEx(key, "TranslateLang", 0, winreg.REG_SZ, code)
        winreg.CloseKey(key)
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
        if not bridge.is_model_ready():
            return "[Scryptian Error] Translation failed: no internet connection and AI model is not downloaded yet."
        return bridge.generate(f"Translate the following text to {tl}. Output ONLY the translated text:\n\n{text}")
