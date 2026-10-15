# Compress Image — local & free (Pillow).
#
# Flow: open -> (downscale if huge) -> save JPEG quality 80 -> result next to original.

import os

from PIL import Image

_INPUT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_MAX_DIM = 4096


def measure(file_path):
    """Flat pricing: one unit per result."""
    return 1


def run(text):
    """text: path to an image to compress (JPEG, quality 80)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _INPUT_EXTS:
        return "[Scryptian Error] Unsupported image format."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_compressed.jpg"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_compressed_{counter}.jpg"
        counter += 1

    try:
        img = Image.open(file_path)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > _MAX_DIM:
            scale = _MAX_DIM / float(max(w, h))
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img.save(out_path, "JPEG", quality=80, optimize=True)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        return f"[Scryptian Error] {e}"