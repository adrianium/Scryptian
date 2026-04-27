# bridge.py — Bridge between Scryptian skills and local LLM
# Connector | Optimizer | Unifier

import os
from config import MODEL_PATH, MODELS_DIR, MODEL_URL, MODEL_FILE, CONTEXT_SIZE, TEMPERATURE

_llm = None


def _download_model(on_progress=None):
    """Download GGUF model from HuggingFace using stdlib only."""
    from urllib import request
    import shutil

    os.makedirs(MODELS_DIR, exist_ok=True)
    tmp_path = MODEL_PATH + ".part"

    if on_progress:
        on_progress("Downloading Qwen2.5-3B for AI skills (~2GB, one time only)...")

    try:
        with request.urlopen(MODEL_URL, timeout=600) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        mb_done = downloaded // (1024 * 1024)
                        mb_total = total // (1024 * 1024)
                        if on_progress:
                            on_progress(f"Downloading Qwen2.5-3B... {pct}%  ({mb_done}/{mb_total} MB)")
        shutil.move(tmp_path, MODEL_PATH)
        if on_progress:
            on_progress("Download complete. Preparing model...")
        return True
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if on_progress:
            on_progress(f"[Scryptian Error] Download failed: {e}")
        return False


def is_model_ready():
    """Check if model is loaded or file exists."""
    return _llm is not None or os.path.exists(MODEL_PATH)


def _get_llm(on_progress=None):
    """Lazy-load the model on first call. Downloads if missing."""
    global _llm
    if _llm is not None:
        return _llm

    if not os.path.exists(MODEL_PATH):
        if not _download_model(on_progress):
            return None

    from llama_cpp import Llama
    if on_progress:
        on_progress("Loading model...")
    _llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=CONTEXT_SIZE,
        n_threads=os.cpu_count() or 4,
        verbose=False,
    )
    return _llm


def _messages(prompt: str):
    """Format prompt as chat messages for the model."""
    return [
        {"role": "system", "content": "You are a helpful assistant. Follow instructions precisely. Output only what is asked, nothing extra."},
        {"role": "user", "content": prompt},
    ]


def generate(prompt: str) -> str:
    """
    Single LLM entry point for all skills.
    Takes a prompt (string), returns model response (string).
    """
    try:
        llm = _get_llm()
        if llm is None:
            return "[Scryptian Error] Model not found. Run Run_Scryptian.bat to download it."

        result = llm.create_chat_completion(
            messages=_messages(prompt),
            max_tokens=512,
            temperature=TEMPERATURE,
        )
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[Scryptian Error] {e}"


def generate_stream(prompt: str):
    """
    Streaming LLM call. Yields text chunks as they arrive.
    """
    try:
        llm = _get_llm()
        if llm is None:
            yield "[Scryptian Error] Model not found. Run Run_Scryptian.bat to download it."
            return

        for chunk in llm.create_chat_completion(
            messages=_messages(prompt),
            max_tokens=512,
            temperature=TEMPERATURE,
            stream=True,
        ):
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content", "")
            if token:
                yield token
    except Exception as e:
        yield f"[Scryptian Error] {e}"
