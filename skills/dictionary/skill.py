import json
import re
import ssl
from urllib import error, parse, request

import bridge

_API_BASE = "https://api.dictionaryapi.dev/api/v2/entries"
_LANGS = {"en", "es", "fr", "de", "it", "pt-BR", "ru", "tr"}
_MAX_WORD_LENGTH = 100
_MAX_DEFINITIONS = 3
_MAX_MEANINGS = 6
_USER_AGENT = "Scryptian/0.5.2 (https://github.com/adrianium/Scryptian)"


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _language():
    try:
        value = (bridge.get_state("dictionary").get("settings", {}) or {}).get("lang", "en")
    except Exception:
        value = "en"
    return value if value in _LANGS else "en"


def _get_json(url):
    req = request.Request(url, headers={"User-Agent": _USER_AGENT})
    with request.urlopen(req, timeout=10, context=_ssl_ctx()) as response:
        return json.loads(response.read().decode("utf-8"))


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _lookup(word, lang):
    url = f"{_API_BASE}/{parse.quote(lang)}/{parse.quote(word)}"
    try:
        return _get_json(url)
    except error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _format_entry(entry):
    lines = []
    word = _clean(entry.get("word"))
    phonetic = _clean(entry.get("phonetic"))
    if word:
        lines.append(word + (f"  /{phonetic}/" if phonetic else ""))

    meanings = entry.get("meanings") or []
    for meaning in meanings[:_MAX_MEANINGS]:
        part = _clean(meaning.get("partOfSpeech"))
        definitions = meaning.get("definitions") or []
        for index, item in enumerate(definitions[:_MAX_DEFINITIONS], 1):
            definition = _clean(item.get("definition"))
            if not definition:
                continue
            prefix = f"{part} " if part else ""
            lines.append(f"{prefix}{index}. {definition}")
            example = _clean(item.get("example"))
            if example:
                lines.append(f"Example: {example}")

    synonyms = []
    for meaning in meanings:
        for item in meaning.get("definitions") or []:
            synonyms.extend(item.get("synonyms") or [])
        synonyms.extend(meaning.get("synonyms") or [])
    unique_synonyms = list(dict.fromkeys(_clean(item) for item in synonyms if _clean(item)))
    if unique_synonyms:
        lines.append("Synonyms: " + ", ".join(unique_synonyms[:12]))

    return "\n".join(lines).strip()


def run(text):
    query = _clean(text)
    if not query:
        return "[Scryptian Error] Select a word first."
    if len(query) > _MAX_WORD_LENGTH:
        return "[Scryptian Error] The selected word is too long."
    if len(query.split()) != 1:
        return "[Scryptian Error] Select one word, not a phrase."

    try:
        entry = _lookup(query, _language())
    except Exception as exc:
        return f"[Scryptian Error] Could not reach Dictionary API: {exc}"

    if not entry:
        return f"No definition found for: {query}"
    if isinstance(entry, list):
        entry = entry[0] if entry else {}
    result = _format_entry(entry)
    return result or f"No definition found for: {query}"
