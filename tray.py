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


def start(on_quit, on_open=None):
    """Start tray icon in background thread. on_quit() called when user clicks Quit."""
    def _run():
        icon = pystray.Icon(
            name="Scryptian",
            icon=_load_icon(),
            title="Scryptian - Ctrl+Alt",
            menu=pystray.Menu(
                pystray.MenuItem("Open", lambda: on_open() if on_open else None, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Feedback", lambda: webbrowser.open(FEEDBACK_URL)),
                pystray.MenuItem("Quit", lambda: _quit(icon)),
            ),
        )

        def _quit(icon):
            icon.stop()
            on_quit()

        icon.run()

    threading.Thread(target=_run, daemon=True).start()
