# pins.py — Manage pinned skills for SelectionToolbar
import json
import os

MAX_PINS = 3


def _pins_file():
    from config import BASE_DIR
    return os.path.join(BASE_DIR, "pinned.json")


def load() -> set:
    try:
        with open(_pins_file(), "r") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save(pins: set):
    try:
        path = _pins_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(list(pins), f)
    except Exception:
        pass


def toggle(title: str) -> set:
    pins = load()
    if title in pins:
        pins.discard(title)
    elif len(pins) < MAX_PINS:
        pins.add(title)
    _save(pins)
    return pins


def is_pinned(title: str) -> bool:
    return title in load()


def get_pinned_skills(skills: list) -> list:
    """Return skills filtered to pinned ones (in original order)."""
    pins = load()
    if not pins:
        return []
    return [s for s in skills if s["title"] in pins]
