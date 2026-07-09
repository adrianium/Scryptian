# config.py — Central configuration for Scryptian

import os
import sys

# ── App version (used for skill bundle compatibility checks) ──
APP_VERSION = "0.5.1"

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
MODEL_FILE = "SmolLM3-3B-Q4_K_M.gguf"
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILE)
MODEL_URL = "https://huggingface.co/second-state/SmolLM3-3B-GGUF/resolve/main/SmolLM3-3B-Q4_K_M.gguf?download=true"
# Minimum valid size (bytes) for the model file. The real file is ~1.9 GB;
# anything smaller means a truncated/incomplete download that would pass the
# GGUF magic-bytes check but fail to load. Such files are rejected and
# re-downloaded instead of crashing with "Failed to load model from file".
MODEL_MIN_BYTES = 1_500_000_000
CONTEXT_SIZE = 2048
TEMPERATURE = 0

# ── Instant-skill input guardrail ──
# Instant skills do a single LLM pass inside the small CONTEXT_SIZE window.
# Cap input length so oversized text can't overflow context or hang low-RAM PCs.
# Background skills (long file jobs) are exempt — they chunk/offload themselves.
MAX_SKILL_INPUT_CHARS = 6000

# ── Telemetry (PostHog) ──
POSTHOG_KEY = "phc_nyYF49YRbnnsjJbMqFwZbXxpiPfU249NAnmnZHuPavei"
POSTHOG_HOST = "https://us.i.posthog.com"
