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


_root_ref = None


def set_root(root) -> None:
    """Register the Tk root so notify() can render the custom popup on the UI thread.

    Called once by the host at startup. Skills never call this.
    """
    global _root_ref
    _root_ref = root


def notify(title: str, message: str) -> None:
    """Show a Scryptian notification. Safe to call from any skill or thread.

    Uses the custom in-app popup (bottom-right, branded, with sound) when the UI
    is available, marshalling onto the Tk main thread. Falls back to a native
    tray notification if the UI root is not registered.

    Skills should use this for long-running progress (start/finish) feedback.
    """
    import tray
    if _root_ref is not None:
        try:
            _root_ref.after(
                0, lambda: tray.show_notify_popup(title, message, _root_ref)
            )
            return
        except Exception:
            pass
    try:
        tray.notify(title, message)
    except Exception:
        pass


# LLM access — optional, re-exported for backward compatibility
# Skills that need LLM: import bridge and use bridge.generate()
# Skills that don't need LLM: import only bridge (state/profile)
from llm import generate, generate_stream, is_model_ready, is_model_in_memory, was_just_downloaded, _get_llm, set_progress_listener, set_download_start_listener
from config import MODEL_FILE
