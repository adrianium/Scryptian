# Merge PDF — local pypdf (free, no cloud). Merges all PDFs in the folder (sorted).

import os

from pypdf import PdfWriter


def measure(file_path):
    """Flat pricing: one unit per result."""
    return 1


def run(text):
    """text: path to any PDF in a folder; merges all PDFs in that folder (sorted by name)."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] File not found."
    if os.path.splitext(file_path)[1].lower() != ".pdf":
        return "[Scryptian Error] This skill accepts PDF files only."

    folder = os.path.dirname(os.path.abspath(file_path))
    out_path = os.path.join(folder, "merged.pdf")
    counter = 2
    while os.path.exists(out_path):
        out_path = os.path.join(folder, f"merged_{counter}.pdf")
        counter += 1

    pdfs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".pdf"))
    if len(pdfs) < 2:
        return "[Scryptian Error] Need at least 2 PDFs in the folder to merge."

    try:
        writer = PdfWriter()
        for name in pdfs:
            p = os.path.join(folder, name)
            if os.path.abspath(p) == os.path.abspath(out_path):
                continue
            writer.append(p)
        with open(out_path, "wb") as f:
            writer.write(f)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        return f"[Scryptian Error] {e}"