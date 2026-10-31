# Convert Image — local Pillow (free).

import json
import os

from PIL import Image

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

_FORMAT_MAP = {
    ".jpg": ("JPEG", "jpg"),
    ".jpeg": ("JPEG", "jpeg"),
    ".png": ("PNG", "png"),
    ".webp": ("WEBP", "webp"),
    ".bmp": ("BMP", "bmp"),
    ".tiff": ("TIFF", "tiff"),
    ".tif": ("TIFF", "tif"),
}


def _output_format():
    try:
        with open(os.path.join(_SKILL_DIR, "manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        out = m.get("output_type") or ".jpg"
        if isinstance(out, list):
            out = out[0] if out else ".jpg"
        return _FORMAT_MAP.get(out.lower(), ("JPEG", "jpg"))
    except Exception:
        return ("JPEG", "jpg")


def run(text):
    """text: path to an image to convert (target format from manifest output_type)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."

    fmt, ext = _output_format()
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}.{ext}"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_{counter}.{ext}"
        counter += 1

    try:
        img = Image.open(file_path)
        if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        img.save(out_path, fmt)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        return f"[Scryptian Error] {e}"
