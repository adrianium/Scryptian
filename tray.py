# tray.py — System tray icon for Scryptian

import os
import threading
import webbrowser
import pystray
from PIL import Image
import sys

FEEDBACK_URL = "https://github.com/adrianium/Scryptian/discussions"

def _icon_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

ICON_PATH = os.path.join(_icon_dir(), "icon.ico")


def _load_icon():
    """Load icon.ico as PIL Image."""
    return Image.open(ICON_PATH)


_icon_ref = None
RELEASES_URL = "https://github.com/adrianium/Scryptian/releases/latest"
_update_version = None


def notify(title, message):
    """Show tray notification."""
    if _icon_ref:
        try:
            _icon_ref.notify(message, title)
        except Exception:
            pass


def set_update_available(version):
    """Called when a new version is detected — adds menu item."""
    global _update_version
    _update_version = version
    if _icon_ref:
        try:
            _icon_ref.update_menu()
        except Exception:
            pass


def start(on_quit, on_open=None):
    """Start tray icon in background thread."""
    def _run():
        global _icon_ref

        def _update_visible(item):
            return _update_version is not None

        def _open_update():
            webbrowser.open(RELEASES_URL)

        def _update_label(item):
            return f"Update available: v{_update_version} →" if _update_version else "Up to date"

        icon = pystray.Icon(
            name="Scryptian",
            icon=_load_icon(),
            title="Scryptian - Ctrl+Alt",
            menu=pystray.Menu(
                pystray.MenuItem("Open", lambda: on_open() if on_open else None, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(_update_label, _open_update, visible=_update_visible),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Feedback", lambda: webbrowser.open(FEEDBACK_URL)),
                pystray.MenuItem("Quit", lambda: _quit(icon)),
            ),
        )
        _icon_ref = icon

        def _quit(icon):
            icon.stop()
            on_quit()

        icon.run()

    threading.Thread(target=_run, daemon=True).start()
