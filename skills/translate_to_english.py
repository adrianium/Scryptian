# @title: Translate to English
# @description: Translate any text to English (Google Translate)
# @author: Scryptian
# @needs_llm: false

from urllib import request, parse
import json
import bridge

_CACHE = {}

_HOSTS = (
    "translate.googleapis.com",
    "translate.google.com",
    "clients5.google.com",
)

_CLIENTS = ("gtx", "dict-chrome-ex", "at")

_UAS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
)


def _translate(text, tl):
    q = parse.urlencode({"sl": "auto", "tl": tl, "dt": "t", "q": text})
    for client in _CLIENTS:
        for host in _HOSTS:
            for ua in _UAS:
                url = f"https://{host}/translate_a/single?client={client}&{q}"
                req = request.Request(url, headers={"User-Agent": ua})
                try:
                    resp = request.urlopen(req, timeout=10)
                    data = json.loads(resp.read())
                    return "".join(part[0] for part in data[0] if part[0])
                except Exception as e:
                    if getattr(e, "code", None) != 429:
                        return None
    return None


def run(text):
    """
    text: text from clipboard to translate to English
    """
    key = (text or "").strip()
    if key and key in _CACHE:
        return _CACHE[key]

    result = _translate(text, "en")
    if result is not None:
        if key:
            _CACHE[key] = result
        return result

    result = bridge.generate(f"Translate the following text to English. Output ONLY the translated text:\n\n{text}")
    if key:
        _CACHE[key] = result
    return result
