# telemetry.py — Lightweight anonymous analytics via PostHog
# Zero dependencies (urllib + threading from stdlib)

import os
import uuid
import json
import hashlib
import platform
import threading
from urllib import request

from config import POSTHOG_KEY, POSTHOG_HOST, BASE_DIR
ID_FILE = os.path.join(BASE_DIR, ".id")


def _get_id():
    """Get or create anonymous user ID."""
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            return f.read().strip()
    uid = str(uuid.uuid4())
    with open(ID_FILE, "w") as f:
        f.write(uid)
    return uid


APP_VERSION = "0.3.8"


def _os_info():
    return f"{platform.system()} {platform.release()}"


def _machine_id():
    """Stable fingerprint based on machine name — survives reinstall."""
    return hashlib.md5(platform.node().encode()).hexdigest()[:16]


_FIRST_LAUNCH_FILE = os.path.join(BASE_DIR, "first_launch_sent.txt")


def _log(msg):
    try:
        import datetime
        with open(os.path.join(BASE_DIR, "first_launch.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now()} {msg}\n")
    except Exception:
        pass


def _registry_first_launch_done():
    """Check registry flag (more reliable than file)."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Scryptian", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "FirstLaunchSent")
        winreg.CloseKey(key)
        return value == "1"
    except Exception:
        return False


def _registry_set_first_launch():
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Scryptian")
        winreg.SetValueEx(key, "FirstLaunchSent", 0, winreg.REG_SZ, "1")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def send_first_launch():
    """Send first_launch event only once ever. Uses registry + file for reliability."""
    reg_done = _registry_first_launch_done()
    file_exists = os.path.exists(_FIRST_LAUNCH_FILE)
    _log(f"check: registry={reg_done} file={file_exists}")
    if reg_done or file_exists:
        # Ensure both are set
        if not reg_done:
            _registry_set_first_launch()
        if not file_exists:
            try:
                with open(_FIRST_LAUNCH_FILE, "w", encoding="utf-8") as f:
                    f.write("sent\n")
            except Exception:
                pass
        return
    try:
        with open(_FIRST_LAUNCH_FILE, "w", encoding="utf-8") as f:
            import datetime
            f.write(f"sent at {datetime.datetime.now().isoformat()}\n")
        _registry_set_first_launch()
        _log("flags set")
    except Exception as e:
        _log(f"flag set failed: {e}")
        return
    send("first_launch")
    _log("event sent")


def send(event: str, properties: dict = None):
    """Send event to PostHog in a background thread."""
    def _post():
        import time
        body = json.dumps({
            "api_key": POSTHOG_KEY,
            "event": event,
            "distinct_id": _get_id(),
            "properties": {
                "os": _os_info(),
                "app_version": APP_VERSION,
                "machine_id": _machine_id(),
                **(properties or {}),
            },
        }).encode()
        import ssl
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        for attempt in range(3):
            try:
                req = request.Request(
                    f"{POSTHOG_HOST}/capture/",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                request.urlopen(req, timeout=5, context=ctx)
                break
            except Exception:
                time.sleep(5)  # Retry after 5s (network may not be ready)

    threading.Thread(target=_post, daemon=True).start()
