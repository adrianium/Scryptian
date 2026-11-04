# config.py — Central configuration for nespatch

import os
import sys

# ── App version (used for skill bundle compatibility checks) ──
APP_VERSION = "0.1.0"

# ── Base directory (works for both .py and .exe) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'nespatch')
else:
    _here = os.path.dirname(os.path.abspath(__file__))
    # This file lives in app/. The project root is the parent, so skills,
    # docs, and .env stay where they are.
    BASE_DIR = os.path.dirname(_here) if os.path.basename(_here) == "app" else _here
os.makedirs(BASE_DIR, exist_ok=True)

# ── Currency: 1 slipper = 1000 atomic units (micro-slippers) ──
SLIPPER_SCALE = 1000

# ── Hotkey ──
HOTKEY = "ctrl+alt"

# ── Telemetry (PostHog) ──
POSTHOG_KEY = "phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei"
POSTHOG_HOST = "https://us.i.posthog.com"
