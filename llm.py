# llm.py — Local LLM access for Scryptian skills
# Optional module. Skills that don't need LLM don't import this.

import os
import threading
from config import MODEL_PATH, MODELS_DIR, MODEL_URL, MODEL_FILE, CONTEXT_SIZE, TEMPERATURE

_llm = None
_idle_timer = None
_load_lock = threading.Lock()
_last_load_error = None
_just_downloaded = False
IDLE_TIMEOUT = 600


def _schedule_unload():
    global _idle_timer
    if _idle_timer:
        _idle_timer.cancel()
    _idle_timer = threading.Timer(IDLE_TIMEOUT, _unload_model)
    _idle_timer.daemon = True
    _idle_timer.start()


def _unload_model():
    global _llm, _idle_timer
    if _llm is not None:
        _llm = None
        print(f"[Scryptian] Model unloaded from RAM (idle {IDLE_TIMEOUT}s).")
    _idle_timer = None


def _is_valid_gguf(path: str) -> bool:
    """Check GGUF magic bytes — first 4 bytes must be b'GGUF'."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"GGUF"
    except Exception:
        return False


def _download_model(on_progress=None):
    from urllib import request
    import ssl
    import shutil

    os.makedirs(MODELS_DIR, exist_ok=True)
    tmp_path = MODEL_PATH + ".part"

    import telemetry
    telemetry.send("model_download_started")
    print(f"[Scryptian] Starting model download: {MODEL_URL}")

    if on_progress:
        on_progress(f"Downloading {MODEL_FILE} for AI skills (one time only)...")

    try:
        try:
            free_bytes = shutil.disk_usage(MODELS_DIR).free
            if free_bytes < 3 * 1024 * 1024 * 1024:
                free_gb = free_bytes / (1024 ** 3)
                telemetry.send("model_download_failed", {"error": "not enough disk space", "free_gb": round(free_gb, 2)})
                if on_progress:
                    on_progress(f"[Scryptian Error] Not enough disk space. Need ~2 GB, available: {free_gb:.1f} GB")
                return False
        except Exception:
            pass

        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()

        max_retries = 3
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    if on_progress:
                        on_progress(f"Retrying download... (attempt {attempt}/{max_retries})")
                    import time
                    time.sleep(3)
                if on_progress:
                    on_progress(f"Connecting to server...")
                print(f"[Scryptian] Connecting (attempt {attempt}/{max_retries})...")
                import socket
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(30)
                try:
                    resp_obj = request.urlopen(MODEL_URL, timeout=30, context=ctx)
                finally:
                    socket.setdefaulttimeout(old_timeout)
                with resp_obj as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    print(f"[Scryptian] Connected. Content-Length: {total // (1024*1024)} MB")
                    downloaded = 0
                    last_logged_pct = -1
                    with open(tmp_path, "wb") as f:
                        while True:
                            chunk = resp.read(1024 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                pct = int(downloaded / total * 100)
                                mb_done = downloaded // (1024 * 1024)
                                mb_total = total // (1024 * 1024)
                                if on_progress:
                                    on_progress(f"Downloading AI model... {pct}%  ({mb_done}/{mb_total} MB)  —  one time only")
                                if pct != last_logged_pct and pct % 5 == 0:
                                    last_logged_pct = pct
                                    print(f"[Scryptian] Download {pct}% ({mb_done}/{mb_total} MB)")
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f"[Scryptian] Download attempt {attempt} failed: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        if last_error:
            raise last_error

        shutil.move(tmp_path, MODEL_PATH)
        if not _is_valid_gguf(MODEL_PATH):
            os.remove(MODEL_PATH)
            telemetry.send("model_download_failed", {"error": "invalid GGUF after download"})
            if on_progress:
                on_progress("[Scryptian Error] Download corrupted. Please try again.")
            return False
        global _just_downloaded
        _just_downloaded = True
        telemetry.send("model_download_finished")
        if on_progress:
            on_progress("Download complete. Preparing model...")
        return True
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        telemetry.send("model_download_failed", {"error": str(e)})
        if on_progress:
            on_progress(f"[Scryptian Error] Download failed: {e}")
        return False


def is_model_ready():
    return _llm is not None or os.path.exists(MODEL_PATH)


def is_model_in_memory():
    return _llm is not None


def was_just_downloaded() -> bool:
    """Returns True once after model was freshly downloaded. Resets after read."""
    global _just_downloaded
    if _just_downloaded:
        _just_downloaded = False
        return True
    return False


def _get_llm(on_progress=None):
    global _llm
    if _llm is not None:
        _schedule_unload()
        return _llm

    with _load_lock:
        if _llm is not None:
            _schedule_unload()
            return _llm

        if os.path.exists(MODEL_PATH) and not _is_valid_gguf(MODEL_PATH):
            print("[Scryptian] Corrupted model file detected, deleting and re-downloading...")
            os.remove(MODEL_PATH)
            import telemetry
            telemetry.send("model_corrupted")

        if not os.path.exists(MODEL_PATH):
            if not _download_model(on_progress):
                return None

        from llama_cpp import Llama
        if on_progress:
            on_progress("Loading model into memory...")
        try:
            import telemetry as _tel
            import llama_cpp as _lc
            import platform as _pl
            _tel.send("model_load_started", {
                "model_file": MODEL_FILE,
                "llama_cpp_version": getattr(_lc, "__version__", "unknown"),
                "python_arch": _pl.architecture()[0],
            })
            _llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=CONTEXT_SIZE,
                n_threads=os.cpu_count() or 4,
                verbose=False,
            )
            import telemetry
            telemetry.send("model_loaded")
            print("[Scryptian] Model loaded into RAM.")
        except Exception as e:
            global _last_load_error
            _last_load_error = str(e)
            import telemetry
            import platform as _pl2
            _cpu_name = "unknown"
            try:
                import subprocess as _sp
                _r = _sp.run(["wmic", "cpu", "get", "Name"], capture_output=True, text=True, timeout=3, creationflags=0x08000000)
                _lines = [l.strip() for l in _r.stdout.splitlines() if l.strip() and l.strip().lower() != "name"]
                if _lines:
                    _cpu_name = _lines[0]
            except Exception:
                pass
            telemetry.send("model_load_failed", {
                "error": str(e),
                "model_file": MODEL_FILE,
                "cpu_name": _cpu_name,
                "python_arch": _pl2.architecture()[0],
            })
            err_str = str(e)
            if "0xe06d7363" in err_str or "-529697949" in err_str:
                user_msg = "[Scryptian Error] Your CPU does not support the AI model. This requires a processor with AVX2 support (Intel 4th gen+ or AMD Ryzen+)."
            else:
                user_msg = f"[Scryptian Error] Model load failed: {e}"
            if on_progress:
                on_progress(user_msg)
            os.remove(MODEL_PATH)
            print("[Scryptian] Deleted corrupted model file after load failure.")
            return None

        _schedule_unload()
        return _llm


def _messages(prompt: str):
    return [
        {"role": "system", "content": "/no_think\nYou are a helpful assistant. Follow instructions precisely. Output only what is asked, nothing extra. Never ask questions back. This is not a chat."},
        {"role": "user", "content": prompt},
    ]


def generate(prompt: str) -> str:
    try:
        _schedule_unload()
        llm = _get_llm()
        if llm is None:
            err = _last_load_error or "unknown error"
            return f"[Scryptian Error] Model failed to load: {err}"

        result = llm.create_chat_completion(
            messages=_messages(prompt),
            max_tokens=1024,
            temperature=TEMPERATURE,
        )
        import re
        raw = result["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
        return raw
    except Exception as e:
        err_str = str(e)
        if "exceed context window" in err_str or "context window" in err_str:
            return "[Scryptian Error] Text is too long. Try selecting a smaller portion of text."
        return f"[Scryptian Error] {e}"


def generate_stream(prompt: str):
    try:
        _schedule_unload()
        llm = _get_llm()
        if llm is None:
            err = _last_load_error or "unknown error"
            yield f"[Scryptian Error] Model failed to load: {err}"
            return

        buf = ""
        in_think = False
        think_done = False
        for chunk in llm.create_chat_completion(
            messages=_messages(prompt),
            max_tokens=1024,
            temperature=TEMPERATURE,
            stream=True,
        ):
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content", "")
            if not token:
                continue
            buf += token

            if not think_done:
                if "<think>" in buf and not in_think:
                    in_think = True
                if in_think:
                    if "</think>" in buf:
                        in_think = False
                        think_done = True
                        import re
                        after = re.sub(r"<think>[\s\S]*?</think>", "", buf).strip()
                        buf = after
                        if after:
                            yield after
                    continue
                else:
                    think_done = True

            if think_done and not in_think:
                yield token
    except Exception as e:
        err_str = str(e)
        if "exceed context window" in err_str or "context window" in err_str:
            yield "[Scryptian Error] Text is too long. Try selecting a smaller portion of text."
        else:
            yield f"[Scryptian Error] {e}"
