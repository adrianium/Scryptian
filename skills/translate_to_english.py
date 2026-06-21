# @title: Translate to English
# @description: Translate any text to English (Google Translate)
# @author: Scryptian

from urllib import request, parse
import json
import ssl
import bridge


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def run(text):
    """
    text: text from clipboard to translate to English
    """
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = parse.urlencode({"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text})
        resp = request.urlopen(f"{url}?{params}", timeout=10, context=_ssl_ctx())
        data = json.loads(resp.read())
        return "".join(part[0] for part in data[0] if part[0])
    except Exception:
        return bridge.generate(f"Translate the following text to English. Output ONLY the translated text:\n\n{text}")
