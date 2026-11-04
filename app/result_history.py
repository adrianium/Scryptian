# result_history.py — Local list of recent file results the user can rate.
# Stores the skill and the type pair only. No file names or file contents.

import datetime
import json
import os
import threading
import uuid

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "nespatch", "state")
_PATH = os.path.join(_DATA_DIR, "result_history.json")
_LOCK = threading.Lock()
_MAX = 40


def _load():
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(items):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def remember(skill, input_text):
    """Append one successful file result. Ignores text-only runs."""
    raw = (input_text or "").strip().strip('"')
    if not raw or not os.path.isfile(raw):
        return
    ext = os.path.splitext(raw)[1].lower().lstrip(".")
    if not ext:
        return
    out = skill.get("output_type") or ""
    if isinstance(out, (list, tuple)):
        out = out[0] if out else ""
    output_type = str(out).strip().lower().lstrip(".")
    if not output_type:
        return
    skill_id = skill.get("id") or str(skill.get("filename", "")).replace(".py", "")
    entry = {
        "id": uuid.uuid4().hex[:12],
        "skill_id": skill_id,
        "skill_title": skill.get("title") or skill_id,
        "input_type": ext,
        "output_type": output_type,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": "",
    }
    with _LOCK:
        items = _load()
        items.insert(0, entry)
        del items[_MAX:]
        _save(items)


def recent():
    with _LOCK:
        return _load()


def mark_bad(entry_id):
    """Mark one row as a bad result. Returns the row, or None if already marked."""
    with _LOCK:
        items = _load()
        found = None
        for item in items:
            if item.get("id") == entry_id:
                if item.get("verdict") == "bad":
                    return None
                item["verdict"] = "bad"
                found = dict(item)
                break
        if found is None:
            return None
        _save(items)
        return found
