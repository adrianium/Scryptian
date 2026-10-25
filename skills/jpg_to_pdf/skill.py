# JPG to PDF — local Pillow (free, no cloud).

import os

from PIL import Image

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error("jpg_to_pdf", detail)
        except Exception:
            pass

_INPUT_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def measure(file_path):
    """Flat pricing: one unit per result."""
    return 1


def run(text):
    """text: path to an image to convert into a PDF document."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this image. Copy it again and try."
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _INPUT_EXTS:
        return "[Scryptian Error] This image type isn't supported."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}.pdf"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_{counter}.pdf"
        counter += 1

    try:
        img = Image.open(file_path)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        img.save(out_path, "PDF", resolution=150)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        _report(str(e))
        return "[Scryptian Error] Couldn't convert this image. We're on it."