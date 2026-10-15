# PDF to JPG — local Ghostscript (free). One JPG per page, in its own folder.

import os
import subprocess
import sys
import urllib.request
import zipfile

_GHOSTSCRIPT_URL = "https://qvihfoeouvfveacexcol.supabase.co/storage/v1/object/public/actions/ghostscript.zip"
_GS_DIR_NAME = "_ghostscript"
_DPI = "300"
_JPEG_QUALITY = "90"


def _ensure_gs():
    """Return gswin64c.exe path, downloading & extracting Ghostscript on first use."""
    skill_dir = os.path.dirname(os.path.abspath(__file__))
    skills_root = os.path.dirname(skill_dir)
    gs_dir = os.path.join(skills_root, _GS_DIR_NAME)
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
    """text: path to a PDF; renders each page to a JPG in its own folder."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] This skill accepts PDF files only."

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
        result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=14400)
    except FileNotFoundError:
        return "[Scryptian Error] Ghostscript not found. Place it in skills/_ghostscript/."
    except Exception as e:
        return f"[Scryptian Error] {e}"
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()[-400:]
        return f"[Scryptian Error] Ghostscript failed: {err}"

    first = os.path.join(out_dir, "page_1.jpg")
    if os.path.exists(first):
        return f"[Scryptian File] {first}"
    return "[Scryptian Error] No pages rendered."