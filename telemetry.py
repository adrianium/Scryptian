# telemetry.py — Lightweight anonymous analytics via PostHog
# Zero dependencies (urllib + threading from stdlib)

import os
import uuid
import json
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


def _os_info():
    return f"{platform.system()} {platform.release()}"


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
                **(properties or {}),
            },
        }).encode()
        for attempt in range(3):
            try:
                req = request.Request(
                    f"{POSTHOG_HOST}/capture/",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                request.urlopen(req, timeout=5)
                break
            except Exception:
                time.sleep(5)  # Retry after 5s (network may not be ready)

    threading.Thread(target=_post, daemon=True).start()
