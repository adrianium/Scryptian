# config.py — Central configuration for Scryptian

import os
import sys

# ── Base directory (works for both .py and .exe) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'Scryptian')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)

# ── Hotkey ──
HOTKEY = "ctrl+alt"

# ── Model (GGUF) ──
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_FILE = "HuggingFaceTB_SmolLM3-3B-Q4_K_M.gguf"
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILE)
MODEL_URL = "https://huggingface.co/bartowski/HuggingFaceTB_SmolLM3-3B-GGUF/resolve/main/HuggingFaceTB_SmolLM3-3B-Q4_K_M.gguf?download=true"
CONTEXT_SIZE = 2048
TEMPERATURE = 0

# ── Telemetry (PostHog) ──
POSTHOG_KEY = "phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei"
POSTHOG_HOST = "https://us.i.posthog.com"
