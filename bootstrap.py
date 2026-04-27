# bootstrap.py — First-run setup: extract bundled skills to external folder

import os
import sys
import shutil
from config import BASE_DIR

SKILLS_DIR = os.path.join(BASE_DIR, "skills")


def _bundled_skills_dir():
    """Get path to skills bundled inside .exe (PyInstaller _MEIPASS)."""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "skills")
    return None


def setup():
    """Extract bundled skills to external folder on first run."""
    if os.path.isdir(SKILLS_DIR):
        return  # Already exists, nothing to do

    bundled = _bundled_skills_dir()
    if bundled and os.path.isdir(bundled):
        shutil.copytree(bundled, SKILLS_DIR)
    else:
        os.makedirs(SKILLS_DIR, exist_ok=True)
