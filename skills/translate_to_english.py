# @title: Translate to English
# @description: Translate any text to English (Google Translate)
# @author: Scryptian

from urllib import request, parse
import json


def run(text):
    """
    text: text from clipboard to translate to English
    """
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = parse.urlencode({"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text})
        resp = request.urlopen(f"{url}?{params}", timeout=10)
        data = json.loads(resp.read())
        return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        return f"[Scryptian Error] Translation failed: {e}"
