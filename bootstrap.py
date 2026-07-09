# bootstrap.py — Clean install: wipe old data (except model) and set up fresh

import os
import sys
import shutil
from config import BASE_DIR

SKILLS_DIR = os.path.join(BASE_DIR, "skills")
MODELS_DIR = os.path.join(BASE_DIR, "models")


def _bundled_skills_dir():
    """Get path to skills bundled inside .exe (PyInstaller _MEIPASS)."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "skills")
    return None


def setup():
    """Clean install: remove everything except models, then extract fresh skills."""
    if not getattr(sys, 'frozen', False):
        os.makedirs(SKILLS_DIR, exist_ok=True)
        return

    # Preserve models, telemetry id, pins, custom skills, and user state.
    # "state" holds the shared profile (e.g. PDF target language) and per-skill
    # data (usage counts, learned profiles) — must survive updates.
    _KEEP_FILES = ("models", ".id", "pinned.json", "state")

    if os.path.isdir(BASE_DIR):
        for item in os.listdir(BASE_DIR):
            path = os.path.join(BASE_DIR, item)
            if item in _KEEP_FILES:
                continue
            if item == "skills":
                continue  # handled below
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception:
                pass

    os.makedirs(SKILLS_DIR, exist_ok=True)

    # Extract fresh built-in skills, but keep custom_*.py files
    bundled = _bundled_skills_dir()
    if bundled and os.path.isdir(bundled):
        for fname in os.listdir(bundled):
            if fname.endswith(".py"):
                shutil.copy2(os.path.join(bundled, fname), os.path.join(SKILLS_DIR, fname))
