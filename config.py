# config.py — Central configuration for Scryptian

import os
import sys

# ── App version (used for skill bundle compatibility checks) ──
APP_VERSION = "0.7.1"

# ── Base directory (works for both .py and .exe) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'Scryptian')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)

# ── Hotkey ──
HOTKEY = "ctrl+alt"

# ── Telemetry (PostHog) ──
POSTHOG_KEY = "phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei"
POSTHOG_HOST = "https://us.i.posthog.com"
