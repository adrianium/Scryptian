# skill.py — Translate PDF: pick a PDF, translate its text, save a translated PDF copy.
# Dependencies (pdfminer.six, reportlab) are bundled in this skill's ./libs folder.

import os
import re
import json
import ssl
import subprocess
from collections import Counter
from urllib import request, parse

import bridge


def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _ask_lang():
    """Ask the target language on every run (predictable, visible choice).

    The last used language is pre-filled as the default so it's one keypress
    for repeat users, but always shown and editable. Returns the code, or None
    if the user cancels or leaves it blank.
    """
    default = (bridge.get_profile().get("lang") or "").strip().lower()
    try:
        ps = (
            "[System.Reflection.Assembly]::LoadWithPartialName('Microsoft.VisualBasic') | Out-Null; "
            "$r = [Microsoft.VisualBasic.Interaction]::InputBox("
            "'Translate this PDF to which language? Enter a code (e.g. ru, de, fr, zh, ar).', "
            "'Scryptian - Translate PDF', '" + default + "'); "
            "Write-Output $r"
        )
        r = subprocess.run(["powershell", "-Sta", "-Command", ps],
                           capture_output=True, text=True, timeout=120,
                           creationflags=0x08000000)
        lang = r.stdout.strip().lower()
        if lang:
            bridge.set_profile({"lang": lang})  # remember as next default
            return lang
    except Exception:
        pass
    return None


def _pick_pdf():
    """Open a native file picker (works from any thread via PowerShell)."""
    try:
        print("[translate_pdf] opening file picker...")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$owner = New-Object System.Windows.Forms.Form; "
            "$owner.TopMost = $true; $owner.ShowInTaskbar = $false; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            "$f.Filter = 'PDF files (*.pdf)|*.pdf'; "
            "$f.Title = 'Scryptian - choose a PDF to translate'; "
            "if ($f.ShowDialog($owner) -eq 'OK') { Write-Output $f.FileName }"
        )
        r = subprocess.run(["powershell", "-Sta", "-Command", ps],
                           capture_output=True, text=True, timeout=300,
                           creationflags=0x08000000)
        path = r.stdout.strip()
        print(f"[translate_pdf] picked: {path or '(cancelled)'}")
        return path or None
    except Exception as e:
        print(f"[translate_pdf] picker error: {e}")
        return None


def _translate_chunk(text, tl):
    url = "https://translate.googleapis.com/translate_a/single"
    params = parse.urlencode({"client": "gtx", "sl": "auto", "tl": tl, "dt": "t", "q": text})
    resp = request.urlopen(f"{url}?{params}", timeout=15, context=_ssl_ctx())
    data = json.loads(resp.read())
    return "".join(part[0] for part in data[0] if part[0])


_MAX = 4500


def _reflow(text):
    """
    Rebuild readable paragraphs from raw PDF text so the translator gets whole
    sentences instead of mid-sentence line fragments.

    - blank line  -> paragraph break
    - line ending with '-' -> de-hyphenate (join without space)
    - otherwise    -> join wrapped lines with a single space
    """
    paras, cur = [], ""
    for raw_line in text.split("\n"):
        s = raw_line.strip()
        if not s:
            if cur:
                paras.append(cur)
                cur = ""
            continue
        if not cur:
            cur = s
        elif cur.endswith("-") and len(cur) > 1 and cur[-2].isalpha():
            cur = cur[:-1] + s          # de-hyphenate a wrapped word
        else:
            cur = cur + " " + s
    if cur:
        paras.append(cur)
    cleaned = [re.sub(r"[ \t]+", " ", p).strip() for p in paras]
    return "\n".join(p for p in cleaned if p)


def _translate_para(para, tl):
    """Translate a single paragraph, splitting on sentence boundaries only if huge."""
    if len(para) <= _MAX:
        return _translate_chunk(para, tl)
    sentences = re.split(r"(?<=[.!?…])\s+", para)
    out, buf = [], ""
    for s in sentences:
        if len(buf) + len(s) + 1 > _MAX:
            if buf:
                out.append(_translate_chunk(buf, tl))
                buf = ""
            while len(s) > _MAX:
                out.append(_translate_chunk(s[:_MAX], tl))
                s = s[_MAX:]
        buf += (" " if buf else "") + s
    if buf:
        out.append(_translate_chunk(buf, tl))
    return " ".join(out)


def _translate_text(text, tl):
    """Reflow into paragraphs, then translate each paragraph as one coherent unit."""
    reflowed = _reflow(text)
    if not reflowed.strip():
        return ""
    out = []
    for para in reflowed.split("\n"):
        if para.strip():
            out.append(_translate_para(para, tl))
    return "\n".join(out)


def _find_unicode_font():
    """A TTF that covers Latin + Cyrillic (and more). Falls back to Arial."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _html_escape(t):
    """Escape text for a reportlab Paragraph and keep line breaks."""
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return t.replace("\n", "<br/>")


_PAGENUM_RE = re.compile(
    r"^[\s\-–—.]*"
    r"(?:page|pg|p|стр|страница|seite|página|page no)?[\s\.\-–—]*"
    r"(?:\d{1,4}|[ivxlcdm]{1,7})"
    r"(?:\s*(?:/|of|из|de)\s*\d{1,4})?"
    r"[\s\-–—.]*$",
    re.IGNORECASE,
)


def _looks_like_page_number(s):
    """True for '3', '- 3 -', 'Page 12', '5 / 40', roman numerals, etc."""
    s = s.strip()
    if not s or len(s) > 20:
        return False
    return bool(_PAGENUM_RE.match(s))


def _in_margin_band(bbox, page_h):
    """True if the block sits in the top or bottom ~10% (header/footer zone)."""
    y0, y1 = bbox[1], bbox[3]
    return y1 > page_h * 0.90 or y0 < page_h * 0.10


def _norm_band(s):
    """Normalize band text (digits -> #) so repeated headers/footers collapse."""
    s = re.sub(r"\d+", "#", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _box_font_size(box, LTChar):
    """Median glyph size inside a text box (fallback 11pt)."""
    sizes = []
    for line in box:
        try:
            for ch in line:
                if isinstance(ch, LTChar):
                    sizes.append(ch.size)
        except TypeError:
            pass
    if not sizes:
        return 11.0
    sizes.sort()
    return sizes[len(sizes) // 2]


def run(text):
    """
    Ignores clipboard text. Lets the user pick a PDF, translates it block by
    block, and rebuilds a clean, flowing translated document (reading order,
    consistent fonts, automatic pagination) so nothing floats or shrinks.
    """
    src = _pick_pdf()
    if not src:
        return "Cancelled — no PDF selected."
    if not os.path.exists(src):
        return "[Scryptian Error] File not found."

    tl = _ask_lang()
    if not tl:
        return "Cancelled — no language chosen."

    # ── Libraries (bundled in ./libs) ──
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer, LTChar, LAParams
    except Exception as e:
        return f"[Scryptian Error] PDF reader missing: {e}"

    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception as e:
        return f"[Scryptian Error] PDF writer missing: {e}"

    font_path = _find_unicode_font()
    if not font_path:
        return "[Scryptian Error] No Unicode font found on this system."

    try:
        pdfmetrics.registerFont(TTFont("uni", font_path))
    except Exception as e:
        return f"[Scryptian Error] Could not load font: {e}"

    base, _ = os.path.splitext(src)
    out_path = f"{base}_translated_{tl}.pdf"

    # ── 1) Extract everything first (fast, no network) ──
    print(f"[translate_pdf] extracting text from: {src}")
    try:
        pages = []  # list of (width, height, [ (bbox, font_size, raw_text) ])
        for page_layout in extract_pages(src, laparams=LAParams()):
            blocks = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    raw = element.get_text()
                    if raw.strip():
                        blocks.append((element.bbox, _box_font_size(element, LTChar), raw))
            pages.append((page_layout.width, page_layout.height, blocks))
    except Exception as e:
        print(f"[translate_pdf] extract failed: {e}")
        return f"[Scryptian Error] Could not read PDF: {e}"

    total = sum(len(b) for _, _, b in pages)
    print(f"[translate_pdf] pages={len(pages)} text-blocks={total}")
    if total == 0:
        return "[Scryptian Error] No selectable text found (scanned/image PDF is not supported)."

    # Let the user know it started — this can be a long job.
    bridge.notify(
        "Scryptian: Translating PDF",
        "Working on your file. Big files can take 10-15 min. "
        "Please wait - you will get a message when it is ready.",
    )

    # ── 2) Translate with a cache for repeated strings; tolerate failures ──
    cache = {}
    failures = [0]

    def translate(raw):
        key = raw.strip()
        if key in cache:
            return cache[key]
        try:
            val = _translate_text(raw, tl)
        except Exception as ex:
            failures[0] += 1
            print(f"[translate_pdf] block translate failed ({failures[0]}): {ex}")
            val = raw  # keep original so the document still builds
        cache[key] = val
        return val

    # ── 3) Build a flowing translated document (variant B) ──
    # Blocks are placed in reading order, each keeping its own font size.
    # ReportLab reflows and paginates automatically, so text never shrinks or
    # overlaps — expansion from translation is absorbed by the page flow.
    _styles = {}

    def style_for(fs):
        key = max(7, round(fs))            # floor so nothing gets microscopic
        if key not in _styles:
            _styles[key] = ParagraphStyle(
                f"s{key}", fontName="uni", fontSize=key,
                leading=key * 1.25, spaceAfter=key * 0.35,
            )
        return _styles[key]

    # Pre-pass: count text that appears in header/footer bands so repeated
    # running headers/footers can be dropped (they vary only by page number).
    band_counter = Counter()
    for (w, h, blocks) in pages:
        for (bbox, fs, raw) in blocks:
            if _in_margin_band(bbox, h):
                band_counter[_norm_band(raw)] += 1
    repeat_threshold = max(2, round(len(pages) * 0.4))

    def is_metadata(bbox, page_h, raw):
        if not _in_margin_band(bbox, page_h):
            return False
        s = raw.strip()
        if _looks_like_page_number(s):
            return True
        # a short line repeated across many pages in the margin = header/footer
        return len(s) < 120 and band_counter[_norm_band(raw)] >= repeat_threshold

    pw, ph = pages[0][0], pages[0][1]
    try:
        doc = SimpleDocTemplate(
            out_path, pagesize=(pw, ph),
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
            title=os.path.basename(base),
        )
        story = []
        done = 0
        skipped_meta = 0
        for (w, h, blocks) in pages:
            # reading order: top-to-bottom, then left-to-right (row-bucketed)
            ordered = sorted(blocks, key=lambda b: (-round(b[0][3] / 8.0), round(b[0][0])))
            for (bbox, fs, raw) in ordered:
                done += 1
                if done == 1 or done % 10 == 0 or done == total:
                    print(f"[translate_pdf] translating {done}/{total} (unique={len(cache)})")
                if is_metadata(bbox, h, raw):
                    skipped_meta += 1
                    continue
                translated = translate(raw)
                if not translated.strip():
                    continue
                for para in translated.split("\n"):
                    if para.strip():
                        story.append(Paragraph(_html_escape(para), style_for(fs)))
                story.append(Spacer(1, max(4, round(fs) * 0.4)))
        doc.build(story)
    except Exception as e:
        print(f"[translate_pdf] build failed: {e}")
        return f"[Scryptian Error] Could not create PDF: {e}"

    print(f"[translate_pdf] done -> {out_path} (failed blocks: {failures[0]}, skipped metadata: {skipped_meta})")
    bridge.notify(
        "Scryptian: PDF Ready",
        "Success! Your translated PDF is saved in the same folder as the original file.",
    )
    note = f"  ({failures[0]} blocks kept original — check internet)" if failures[0] else ""
    return f"Done! Saved translated PDF:\n{out_path}{note}"
