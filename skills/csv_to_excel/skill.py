import csv
import io
import os
import tempfile
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

import bridge


def run(text):
    """Convert CSV → .xlsx. Accepts file path or raw CSV text."""
    text = text.strip()
    if not text:
        return "[Scryptian Error] No CSV data provided."

    # ── File path input (e.g. from Ctrl+C in Explorer) ──
    if text.endswith(".csv") and os.path.isfile(text):
        src = text
        with open(src, "r", encoding="utf-8-sig") as f:
            raw = f.read()
        rows = list(csv.reader(io.StringIO(raw)))
        if not rows:
            return "[Scryptian Error] Empty CSV file."
        base, _ = os.path.splitext(src)
        out = base + ".xlsx"
        _build_xlsx(rows, out)
        bridge.notify(
            "Scryptian: CSV to Excel Ready",
            f"Saved {os.path.basename(out)} in the same folder as the original.",
        )
        return f"Done! Saved alongside original:\n{out}"

    # ── Raw CSV text input (from clipboard) ──
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return "[Scryptian Error] Empty CSV."

    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="scryptian_")
    os.close(fd)
    _build_xlsx(rows, path)
    bridge.notify(
        "Scryptian: CSV to Excel Ready",
        "Your .xlsx file has been saved. You can find it at the path shown below.",
    )
    return f"Done! Saved Excel file:\n{path}"


# ── XLSX builder (zero dependencies) ─────────────────────────

def _escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _col_letter(n):
    s = ""
    while n >= 0:
        s = chr(ord("A") + n % 26) + s
        n = n // 26 - 1
    return s


def _build_xlsx(rows, path):
    """Build a minimal .xlsx file from a list of lists."""

    # ── [Content_Types].xml ──
    ct = Element("{http://schemas.openxmlformats.org/package/2006/content-types}Types")
    ov = SubElement(ct, "{http://schemas.openxmlformats.org/package/2006/content-types}Override")
    ov.set("PartName", "/xl/worksheets/sheet1.xml")
    ov.set("ContentType", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    ov2 = SubElement(ct, "{http://schemas.openxmlformats.org/package/2006/content-types}Override")
    ov2.set("PartName", "/xl/styles.xml")
    ov2.set("ContentType", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")
    ov3 = SubElement(ct, "{http://schemas.openxmlformats.org/package/2006/content-types}Override")
    ov3.set("PartName", "/xl/sharedStrings.xml")
    ov3.set("ContentType", "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")

    # ── .rels ──
    rels = Element("{http://schemas.openxmlformats.org/package/2006/relationships}Relationships")
    r = SubElement(rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    r.set("Id", "rId1")
    r.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument")
    r.set("Target", "xl/workbook.xml")

    # ── xl/.rels ──
    xl_rels = Element("{http://schemas.openxmlformats.org/package/2006/relationships}Relationships")
    ws = SubElement(xl_rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    ws.set("Id", "rId1")
    ws.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet")
    ws.set("Target", "worksheets/sheet1.xml")
    ss = SubElement(xl_rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    ss.set("Id", "rId2")
    ss.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles")
    ss.set("Target", "styles.xml")
    sh = SubElement(xl_rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    sh.set("Id", "rId3")
    sh.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings")
    sh.set("Target", "sharedStrings.xml")

    # ── xl/workbook.xml ──
    wb = Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook")
    sheets = SubElement(wb, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets")
    sheet = SubElement(sheets, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet")
    sheet.set("name", "Sheet1")
    sheet.set("sheetId", "1")
    sheet.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "rId1")

    # ── xl/styles.xml (minimal) ──
    styles = Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}styleSheet")

    # ── xl/sharedStrings.xml ──
    strings = []
    string_map = {}
    for row in rows:
        for cell in row:
            s = str(cell)
            if s not in string_map:
                string_map[s] = len(strings)
                strings.append(s)

    sst = Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sst")
    sst.set("count", str(len(strings)))
    sst.set("uniqueCount", str(len(strings)))
    for s in strings:
        si = SubElement(sst, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si")
        t = SubElement(si, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        t.text = _escape(s)

    # ── xl/worksheets/sheet1.xml ──
    sheet_xml = Element("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}worksheet")
    sheet_data = SubElement(sheet_xml, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData")
    for r_idx, row in enumerate(rows):
        row_el = SubElement(sheet_data, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row")
        row_el.set("r", str(r_idx + 1))
        for c_idx, cell in enumerate(row):
            col = _col_letter(c_idx)
            cell_el = SubElement(row_el, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
            cell_el.set("r", f"{col}{r_idx + 1}")
            cell_el.set("t", "s")
            v = SubElement(cell_el, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
            v.text = str(string_map[str(cell)])

    # ── Pack into .xlsx (ZIP) ──
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _xml_bytes(ct))
        zf.writestr("_rels/.rels", _xml_bytes(rels))
        zf.writestr("xl/_rels/workbook.xml.rels", _xml_bytes(xl_rels))
        zf.writestr("xl/workbook.xml", _xml_bytes(wb))
        zf.writestr("xl/styles.xml", _xml_bytes(styles))
        zf.writestr("xl/sharedStrings.xml", _xml_bytes(sst))
        zf.writestr("xl/worksheets/sheet1.xml", _xml_bytes(sheet_xml))


def _xml_bytes(el):
    return b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + tostring(el, "utf-8")
