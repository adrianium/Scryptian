# Compress PDF — local Ghostscript (free, no cloud cost). Downsamples images.

import os
import subprocess
import sys
import urllib.request
import zipfile

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error("compress_pdf", detail)
        except Exception:
            pass

_GHOSTSCRIPT_URL = "https://qvihfoeouvfveacexcol.supabase.co/storage/v1/object/public/actions/ghostscript.zip"
_GS_DIR_NAME = "_ghostscript"
_PDFSETTINGS = "/ebook"


def _ensure_gs():
    """Return gswin64c.exe path, downloading & extracting Ghostscript on first use."""
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    skills_root = os.path.dirname(skill_dir)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        app_root = os.path.dirname(sys._MEIPASS)
    else:
        app_root = os.path.dirname(skills_root)
    gs_dir = os.path.join(app_root, "runtimes", "ghostscript")
    gs_exe = os.path.join(gs_dir, "bin", "gswin64c.exe")

    if os.path.exists(gs_exe):
        return gs_exe

    try:
        os.makedirs(gs_dir, exist_ok=True)
        tmp_zip = os.path.join(gs_dir, "_gs.zip")
        req = urllib.request.Request(_GHOSTSCRIPT_URL, headers={"User-Agent": "Scryptian"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp_zip, "wb") as f:
            f.write(resp.read())
        with zipfile.ZipFile(tmp_zip) as z:
            z.extractall(gs_dir)
        if os.path.exists(tmp_zip):
            os.remove(tmp_zip)
        if os.path.exists(gs_exe):
            return gs_exe
    except Exception:
        pass
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
    """text: path to a PDF to compress (Ghostscript pdfwrite /ebook)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this file. Copy it again and try."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] Please copy a PDF file."

    base, _ = os.path.splitext(file_path)
    out_path = f"{base}_compressed.pdf"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_compressed_{counter}.pdf"
        counter += 1

    cmd = [
        _ensure_gs(),
        "-sDEVICE=pdfwrite",
        "-dPDFSETTINGS=" + _PDFSETTINGS,
        "-dNOPAUSE",
        "-dBATCH",
        "-sOutputFile=" + out_path,
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
    if os.path.getsize(out_path) >= os.path.getsize(file_path):
        try:
            os.remove(out_path)
        except Exception:
            pass
        return "[Scryptian Error] This PDF is already as small as it gets."
    return f"[Scryptian File] {out_path}"