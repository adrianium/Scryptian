# llm.py — Local LLM access for Scryptian skills
# Optional module. Skills that don't need LLM don't import this.

import os
import threading
from config import MODEL_PATH, MODELS_DIR, MODEL_URL, MODEL_FILE, MODEL_MIN_BYTES, CONTEXT_SIZE, TEMPERATURE

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
    """Validate the model file: correct GGUF magic AND a plausible size.

    The magic-bytes check alone passes for truncated/incomplete downloads,
    which then crash llama.cpp with "Failed to load model from file". Also
    requiring the file to be at least MODEL_MIN_BYTES rejects such files so
    they get re-downloaded instead of failing to load.
    """
    try:
        if os.path.getsize(path) < MODEL_MIN_BYTES:
            return False
        with open(path, "rb") as f:
            return f.read(4) == b"GGUF"
    except Exception:
        return False


# ── Progress reporting ──
# A single global listener registered once by the UI layer. Every download/load
# reports through it, no matter which background thread triggered the work.
_progress_cb = None
_download_start_cb = None


def set_progress_listener(cb):
    """Register a callback(msg: str) that receives download/load progress."""
    global _progress_cb
    _progress_cb = cb


def set_download_start_listener(cb):
    """Register a callback() fired once when a model download begins."""
    global _download_start_cb
    _download_start_cb = cb


def _report(msg):
    print(f"[Scryptian] {msg}")
    if _progress_cb:
        try:
            _progress_cb(msg)
        except Exception:
            pass


def _ssl_ctx():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _download_model():
    """Download the model file once. Returns True on success. Reports via _report."""
    from urllib import request
    import shutil
    import socket

    os.makedirs(MODELS_DIR, exist_ok=True)
    tmp_path = MODEL_PATH + ".part"

    import telemetry
    telemetry.send("model_download_started")

    if _download_start_cb:
        try:
            _download_start_cb()
        except Exception:
            pass

    # Check free disk space (~2 GB needed)
    try:
        free = shutil.disk_usage(MODELS_DIR).free
        if free < 3 * 1024 * 1024 * 1024:
            free_gb = free / (1024 ** 3)
            telemetry.send("model_download_failed", {"error": "not enough disk space", "free_gb": round(free_gb, 2)})
            _report(f"[Scryptian Error] Not enough disk space. Need ~2 GB, available: {free_gb:.1f} GB")
            return False
    except Exception:
        pass

    _report("Downloading AI model (~2 GB). One time only...")

    try:
        socket.setdefaulttimeout(60)
        with request.urlopen(MODEL_URL, timeout=60, context=_ssl_ctx()) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            last_pct = -1
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(downloaded / total * 100)
                        if pct != last_pct:
                            last_pct = pct
                            mb = downloaded // (1024 * 1024)
                            tot = total // (1024 * 1024)
                            _report(f"Downloading AI model... {pct}%  ({mb}/{tot} MB)")

        # Reject an incomplete download: if the server told us the size and we
        # received fewer bytes, the file is truncated (would pass the magic
        # check but fail to load). Remove it so a retry re-downloads cleanly.
        if total and downloaded != total:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            telemetry.send("model_download_failed", {
                "error": "incomplete download",
                "expected_bytes": total,
                "received_bytes": downloaded,
            })
            _report("[Scryptian Error] Download was incomplete. Please try again.")
            return False

        shutil.move(tmp_path, MODEL_PATH)
        if not _is_valid_gguf(MODEL_PATH):
            os.remove(MODEL_PATH)
            telemetry.send("model_download_failed", {"error": "invalid GGUF after download"})
            _report("[Scryptian Error] Download corrupted. Please try again.")
            return False

        global _just_downloaded
        _just_downloaded = True
        telemetry.send("model_download_finished")
        return True
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        telemetry.send("model_download_failed", {"error": str(e)})
        _report(f"[Scryptian Error] Download failed: {e}")
        return False
    finally:
        socket.setdefaulttimeout(None)


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
    if on_progress:
        set_progress_listener(on_progress)

    if _llm is not None:
        _schedule_unload()
        return _llm

    with _load_lock:
        if _llm is not None:
            _schedule_unload()
            return _llm

        if os.path.exists(MODEL_PATH) and not _is_valid_gguf(MODEL_PATH):
            _report("Removing corrupted model file...")
            os.remove(MODEL_PATH)
            import telemetry
            telemetry.send("model_corrupted")

        if not os.path.exists(MODEL_PATH):
            if not _download_model():
                return None

        from llama_cpp import Llama
        _report("Loading AI model into memory...")
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
            _report(user_msg)
            try:
                os.remove(MODEL_PATH)
                print("[Scryptian] Deleted model file after load failure.")
            except Exception:
                pass
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
