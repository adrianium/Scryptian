# config.py — Central configuration for Scryptian

import os
import sys

# ── Base directory (works for both .py and .exe) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Hotkey ──
HOTKEY = "ctrl+alt"

# ── Model (GGUF) ──
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_FILE = "qwen2.5-3b-instruct-q4_k_m.gguf"
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILE)
MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
CONTEXT_SIZE = 2048
TEMPERATURE = 0

# ── Telemetry (PostHog) ──
POSTHOG_KEY = "phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei"
POSTHOG_HOST = "https://us.i.posthog.com"
