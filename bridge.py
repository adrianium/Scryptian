# bridge.py — Bridge between Scryptian plugins and Ollama
# Connector | Optimizer | Unifier

import requests
import json
from config import OLLAMA_HOST, OLLAMA_PORT, MODEL, TEMPERATURE, KEEP_ALIVE

OLLAMA_URL = f"{OLLAMA_HOST}:{OLLAMA_PORT}/api/generate"


def generate(prompt: str) -> str:
    """
    Single LLM entry point for all plugins.
    Takes a prompt (string), returns model response (string).
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "temperature": TEMPERATURE,
        "keep_alive": KEEP_ALIVE,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.ConnectionError:
        return f"[Scryptian Error] Could not connect to Ollama. Make sure the server is running.\n\nollama run {MODEL}"
    except requests.Timeout:
        return "[Scryptian Error] Ollama did not respond in time (timeout 120s)."
    except Exception as e:
        return f"[Scryptian Error] {e}"


def generate_stream(prompt: str):
    """
    Streaming LLM call. Yields text chunks as they arrive.
    """
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "temperature": TEMPERATURE,
        "keep_alive": KEEP_ALIVE,
        "stream": True,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120, stream=True)
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                chunk = data.get("response", "")
                if chunk:
                    yield chunk
                if data.get("done", False):
                    break
    except requests.ConnectionError:
        yield f"[Scryptian Error] Could not connect to Ollama. Make sure the server is running.\n\nollama run {MODEL}"
    except requests.Timeout:
        yield "[Scryptian Error] Ollama did not respond in time (timeout 120s)."
    except Exception as e:
        yield f"[Scryptian Error] {e}"
