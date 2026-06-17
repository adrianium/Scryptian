# @title: Translate to my language
# @description: Translate text to your system language (Google Translate)
# @author: Scryptian

import locale
from urllib import request, parse
import json
import ssl


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get_lang_code():
    """Detect language from active keyboard layout, fallback to system locale."""
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        thread_id = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
        klid = ctypes.windll.user32.GetKeyboardLayout(thread_id)
        lang_id = klid & 0xFFFF
        import locale as _locale
        lang = _locale.windows_locale.get(lang_id, "")
        if lang:
            return lang.split("_")[0]
    except Exception:
        pass
    try:
        code = locale.getdefaultlocale()[0]
        return code.split("_")[0] if code else "en"
    except Exception:
        return "en"


def run(text):
    """
    text: text from clipboard to translate to system language
    """
    try:
        tl = _get_lang_code()
        url = "https://translate.googleapis.com/translate_a/single"
        params = parse.urlencode({"client": "gtx", "sl": "auto", "tl": tl, "dt": "t", "q": text})
        resp = request.urlopen(f"{url}?{params}", timeout=10, context=_ssl_ctx())
        data = json.loads(resp.read())
        return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        return f"[Scryptian Error] Translation failed: {e}"
