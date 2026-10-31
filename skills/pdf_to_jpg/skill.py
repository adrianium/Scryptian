# PDF to JPG — local Ghostscript (free). One JPG per page, in its own folder.

import os
import subprocess

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error("pdf_to_jpg", detail)
        except Exception:
            pass

_DPI = "300"
_JPEG_QUALITY = "90"


def _ensure_gs():
    """Return gswin64c.exe, unpacking the shipped zip when it is missing."""
    try:
        import runtime_bins
        return runtime_bins.ensure_ghostscript()
    except Exception:
        return "gs"


def measure(file_path):
    """Return the number of pages (informational preview)."""
    try:
        from pypdf import PdfReader
        with open(file_path, "rb") as f:
            return len(PdfReader(f).pages)
    except Exception:
        pass
    return None


def run(text):
    """text: path to a PDF; renders each page to a JPG in its own folder."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this file. Copy it again and try."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] Please copy a PDF file."

    base, _ = os.path.splitext(file_path)
    out_dir = f"{base}_pages"
    counter = 2
    while os.path.exists(out_dir):
        out_dir = f"{base}_pages_{counter}"
        counter += 1
    os.makedirs(out_dir, exist_ok=True)
    out_pattern = os.path.join(out_dir, "page_%d.jpg")

    cmd = [
        _ensure_gs(),
        "-sDEVICE=jpeg",
        f"-dJPEGQ={_JPEG_QUALITY}",
        f"-r{_DPI}",
        "-dNOPAUSE",
        "-dBATCH",
        "-o", out_pattern,
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=14400, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        _report("ghostscript not found")
        return "[Scryptian Error] This action isn't set up yet. We're on it."
    except Exception as e:
        _report(str(e))
        return "[Scryptian Error] Something went wrong. We're on it."
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()[-400:]
        _report(f"ghostscript failed: {err}")
        return "[Scryptian Error] Couldn't convert this PDF. We're on it."

    first = os.path.join(out_dir, "page_1.jpg")
    if os.path.exists(first):
        return f"[Scryptian File] {first}"
    _report("no pages rendered")
    return "[Scryptian Error] Couldn't convert this PDF. We're on it."