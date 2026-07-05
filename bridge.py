# bridge.py — Scryptian skill runtime: state, profile, and optional LLM access
# Core layer: state + profile (no LLM knowledge)
# LLM re-exported from llm.py for backward compatibility

import os
import json
import threading

_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Scryptian", "state")
_PROFILE_PATH = os.path.join(_DATA_DIR, "_profile.json")
_state_lock = threading.Lock()


def get_profile() -> dict:
    """Read shared user profile. Readable by all skills."""
    try:
        if os.path.exists(_PROFILE_PATH):
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def set_profile(data: dict) -> None:
    """Merge data into shared user profile."""
    with _state_lock:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            current = get_profile()
            current.update(data)
            with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def get_state(skill_id: str) -> dict:
    """Read per-skill isolated state."""
    try:
        path = os.path.join(_DATA_DIR, f"{skill_id}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def set_state(skill_id: str, data: dict) -> None:
    """Merge data into per-skill isolated state."""
    with _state_lock:
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            current = get_state(skill_id)
            current.update(data)
            path = os.path.join(_DATA_DIR, f"{skill_id}.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# LLM access — optional, re-exported for backward compatibility
# Skills that need LLM: import bridge and use bridge.generate()
# Skills that don't need LLM: import only bridge (state/profile)
from llm import generate, generate_stream, is_model_ready, is_model_in_memory, was_just_downloaded, _get_llm
from config import MODEL_FILE
