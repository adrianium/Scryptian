# @title: Translate
# @description: Translate text to your system language
# @author: Scryptian

import locale
import bridge

_LANG_MAP = {
    "en": "English", "ru": "Russian", "de": "German", "fr": "French",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian", "tr": "Turkish",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "pl": "Polish", "nl": "Dutch", "uk": "Ukrainian", "cs": "Czech",
}


def _get_language():
    try:
        code = locale.getdefaultlocale()[0]
        short = code.split("_")[0] if code else "en"
        return _LANG_MAP.get(short, short)
    except Exception:
        return "English"


def prompt(text):
    lang = _get_language()
    return (
        f"Translate the following text to {lang}. "
        "Output ONLY the translation, nothing else:\n\n"
        f"{text}"
    )


def run(text):
    """
    text: text from clipboard to translate
    """
    return bridge.generate(prompt(text))
