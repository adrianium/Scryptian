# Convert a document or book. The file is sent to convert.scryptian.com.
# PDF to PPTX stays on this computer: LibreOffice saves that pair without slides.

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

try:
    import telemetry as _telemetry
except Exception:
    _telemetry = None

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ID = os.path.basename(_SKILL_DIR)


def _report(detail):
    if _telemetry is not None:
        try:
            _telemetry.report_skill_error(_SKILL_ID, detail)
        except Exception:
            pass


def _output_ext():
    try:
        with open(os.path.join(_SKILL_DIR, "manifest.json"), encoding="utf-8") as f:
            out = json.load(f).get("output_type") or ".pdf"
        if isinstance(out, list):
            out = out[0] if out else ".pdf"
        out = str(out).lower()
        if not out.startswith("."):
            out = "." + out
        return out
    except Exception:
        return ".pdf"


def _pdf_pages_to_pptx(file_path, out_path):
    """PDF opens in LibreOffice as a drawing, and the PowerPoint filter then
    writes a presentation with no slides. PowerPoint refuses that file.
    Render each page and pack those pictures into a real PPTX instead.
    """
    try:
        import runtime_bins
        gs = os.path.join(runtime_bins.runtime_root(), "ghostscript", "bin", "gswin64c.exe")
    except Exception:
        gs = ""
    if not gs or not os.path.isfile(gs):
        _report("ghostscript not found")
        return "[Scryptian Error] This action isn't set up yet. We're on it."

    tmp = tempfile.mkdtemp(prefix="scryptian-pdfpptx-")
    try:
        pattern = os.path.join(tmp, "page_%d.jpg")
        cmd = [
            gs, "-sDEVICE=jpeg", "-dJPEGQ=90", "-r144",
            "-dNOPAUSE", "-dBATCH", "-o", pattern, os.path.abspath(file_path),
        ]
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=14400, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        pages = []
        for name in os.listdir(tmp):
            if name.lower().startswith("page_") and name.lower().endswith(".jpg"):
                pages.append(os.path.join(tmp, name))
        pages.sort(key=lambda p: int(os.path.splitext(os.path.basename(p))[0].split("_")[-1]))
        if result.returncode != 0 or not pages:
            err = (result.stderr or result.stdout or "").strip()[-400:]
            _report(f"ghostscript failed: {err}")
            return "[Scryptian Error] Couldn't convert this file. We're on it."
        _write_image_pptx(pages, out_path)
        return f"[Scryptian File] {out_path}"
    except Exception as e:
        _report(str(e))
        return "[Scryptian Error] Something went wrong. We're on it."
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fit_box(img_w, img_h, slide_cx, slide_cy):
    scale = min(slide_cx / img_w, slide_cy / img_h)
    cx = max(1, int(img_w * scale))
    cy = max(1, int(img_h * scale))
    return (slide_cx - cx) // 2, (slide_cy - cy) // 2, cx, cy


def _write_image_pptx(pages, out_path):
    from PIL import Image

    sizes = []
    for path in pages:
        with Image.open(path) as img:
            sizes.append(img.size)
    slide_cx = max(1, int(sizes[0][0] * 914400 / 144))
    slide_cy = max(1, int(sizes[0][1] * 914400 / 144))
    partial = out_path + ".part"
    with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _pptx_content_types(len(pages)))
        z.writestr("_rels/.rels", _PPTX_ROOT_RELS)
        z.writestr("docProps/core.xml", _PPTX_CORE)
        z.writestr("docProps/app.xml", _pptx_app(len(pages)))
        z.writestr("ppt/presentation.xml", _pptx_presentation(len(pages), slide_cx, slide_cy))
        z.writestr("ppt/_rels/presentation.xml.rels", _pptx_presentation_rels(len(pages)))
        z.writestr("ppt/theme/theme1.xml", _PPTX_THEME)
        z.writestr("ppt/slideMasters/slideMaster1.xml", _PPTX_MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _PPTX_MASTER_RELS)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", _PPTX_LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _PPTX_LAYOUT_RELS)
        for i, path in enumerate(pages, start=1):
            x, y, cx, cy = _fit_box(sizes[i - 1][0], sizes[i - 1][1], slide_cx, slide_cy)
            z.writestr(f"ppt/slides/slide{i}.xml", _pptx_slide(i, x, y, cx, cy))
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", _pptx_slide_rels(i))
            z.write(path, f"ppt/media/image{i}.jpeg")
    os.replace(partial, out_path)


_PPTX_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""

_PPTX_CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Slides</dc:title>
  <dc:creator>Scryptian</dc:creator>
</cp:coreProperties>
"""

_PPTX_THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F4E79"/></a:dk2>
      <a:lt2><a:srgbClr val="EEECE1"/></a:lt2>
      <a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>
      <a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
      <a:accent3><a:srgbClr val="A9D08E"/></a:accent3>
      <a:accent4><a:srgbClr val="FFC000"/></a:accent4>
      <a:accent5><a:srgbClr val="4472C4"/></a:accent5>
      <a:accent6><a:srgbClr val="70AD47"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
        <a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
        <a:effectStyle><a:effectLst/></a:effectStyle>
      </a:effectStyleLst>
      <a:bgFillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
      </a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>
"""

_PPTX_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle><a:lvl1pPr><a:defRPr/></a:lvl1pPr></p:titleStyle>
    <p:bodyStyle><a:lvl1pPr><a:defRPr/></a:lvl1pPr></p:bodyStyle>
    <p:otherStyle><a:lvl1pPr><a:defRPr/></a:lvl1pPr></p:otherStyle>
  </p:txStyles>
</p:sldMaster>
"""

_PPTX_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""

_PPTX_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""

_PPTX_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""


def _pptx_content_types(count):
    slides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
{slides}
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _pptx_app(count):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Scryptian</Application>
  <Slides>{count}</Slides>
</Properties>
"""


def _pptx_presentation(count, cx, cy):
    ids = "\n".join(
        f'    <p:sldId id="{255 + i}" r:id="rId{i + 1}"/>'
        for i in range(1, count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>
{ids}
  </p:sldIdLst>
  <p:sldSz cx="{cx}" cy="{cy}"/>
  <p:notesSz cx="6858000" cy="9144000"/>
</p:presentation>
"""


def _pptx_presentation_rels(count):
    rels = [
        '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    ]
    rels.extend(
        f'  <Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, count + 1)
    )
    body = "\n".join(rels)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{body}
</Relationships>
"""


def _pptx_slide(index, x, y, cx, cy):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      <p:pic>
        <p:nvPicPr>
          <p:cNvPr id="2" name="Page {index}"/>
          <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
          <p:nvPr/>
        </p:nvPicPr>
        <p:blipFill>
          <a:blip r:embed="rId1"/>
          <a:stretch><a:fillRect/></a:stretch>
        </p:blipFill>
        <p:spPr>
          <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
        </p:spPr>
      </p:pic>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""


def _pptx_slide_rels(index):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{index}.jpeg"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>
"""


def _load_env():
    paths = []
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(5):
        paths.append(os.path.join(d, ".env"))
        d = os.path.dirname(d)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        paths.append(os.path.join(sys._MEIPASS, ".env"))
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass
        return


def _remote_convert(file_path, ext, out_path):
    _load_env()
    token = os.environ.get("CONVERT_TOKEN", "").strip()
    if not token:
        _report("convert token missing")
        return "[Scryptian Error] This action isn't set up yet. We're on it."
    fmt = ext.lstrip(".")
    req = urllib.request.Request(
        f"https://convert.scryptian.com/convert?format={fmt}",
        data=open(file_path, "rb").read(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Filename": os.path.basename(file_path),
            "Content-Type": "application/octet-stream",
            "User-Agent": "Scryptian",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            payload = resp.read()
        if not payload:
            _report("empty convert response")
            return "[Scryptian Error] Couldn't convert this file. We're on it."
        with open(out_path, "wb") as handle:
            handle.write(payload)
        return f"[Scryptian File] {out_path}"
    except urllib.error.HTTPError as exc:
        err = exc.read()[:400].decode("utf-8", "replace")
        _report(f"convert http {exc.code}: {err}")
        return "[Scryptian Error] Couldn't convert this file. We're on it."
    except Exception as exc:
        _report(str(exc))
        return "[Scryptian Error] Something went wrong. We're on it."


def run(text):
    """text: path to a document or book. Output extension comes from manifest output_type."""
    file_path = (text or "").strip().strip('"')
    if not file_path or not os.path.isfile(file_path):
        return "[Scryptian Error] Couldn't find this file. Copy it again and try."

    ext = _output_ext()
    base, _ = os.path.splitext(file_path)
    out_path = f"{base}{ext}"
    counter = 2
    while os.path.exists(out_path):
        out_path = f"{base}_{counter}{ext}"
        counter += 1

    if ext == ".pptx" and os.path.splitext(file_path)[1].lower() == ".pdf":
        return _pdf_pages_to_pptx(file_path, out_path)
    return _remote_convert(file_path, ext, out_path)
