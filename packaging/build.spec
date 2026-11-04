# build.spec — PyInstaller build configuration for nespatch

import os

import pymediainfo
from PyInstaller.utils.hooks import collect_all, collect_submodules

# pillow-heif bundles libheif for iPhone HEIC photos. Skills import it at
# runtime, so PyInstaller will not see the package or its DLLs on its own.
_heif_datas, _heif_binaries, _heif_hidden = collect_all("pillow_heif")

block_cipher = None
packaging_dir = os.path.dirname(os.path.abspath(SPEC))
base_dir = os.path.dirname(packaging_dir)
app_dir = os.path.join(base_dir, "app")

# MediaInfo.dll ships inside the pymediainfo package and must be bundled for
# file-metadata reading (video/audio duration, resolution, PDF page count).
_media_dll = os.path.join(os.path.dirname(pymediainfo.__file__), 'MediaInfo.dll')

_skills_dir = os.path.join(base_dir, "skills")
_skill_bundles = [
    (os.path.join(_skills_dir, name), os.path.join("skills", name))
    for name in sorted(os.listdir(_skills_dir))
    if os.path.isdir(os.path.join(_skills_dir, name))
    and not name.startswith("_")
    and name not in ("translate_pdf", "video_compress")
]

a = Analysis(
    [os.path.join(base_dir, "main.py")],
    pathex=[base_dir, app_dir],
    binaries=[(_media_dll, ".")] + _heif_binaries,
    datas=[
        (os.path.join(packaging_dir, "icon.ico"), "."),
        (os.path.join(app_dir, "config.py"), "."),
        (os.path.join(app_dir, "bridge.py"), "."),
        (os.path.join(app_dir, "telemetry.py"), "."),
        (os.path.join(app_dir, "tray.py"), "."),
        (os.path.join(app_dir, "autostart.py"), "."),
        (os.path.join(app_dir, "bootstrap.py"), "."),
        (os.path.join(app_dir, "runtime_bins.py"), "."),
        (os.path.join(base_dir, "tools", "7zr.exe"), "."),
        # Archives only. Unpacked runtimes/ffmpeg and runtimes/ghostscript
        # stay out of the exe; first launch extracts these two files.
        (os.path.join(base_dir, "runtimes", "ffmpeg-release-essentials.7z"), "runtimes"),
        (os.path.join(base_dir, "runtimes", "ghostscript.zip"), "runtimes"),
        # Skill bundles are bundled as folders. The 'translate_pdf' bundle
        # (folder + ~22 MB libs/) is intentionally EXCLUDED — it ships via the
        # store (registry + zip) and is downloaded on demand, keeping the
        # installer small.
        (os.path.join(base_dir, "docs", "assets", "scryptian-notification.wav"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "slippers.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "search.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "wish.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "store.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "up-and-down.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "support.png"), "docs/assets"),
        (os.path.join(base_dir, "docs", "assets", "font"), "docs/assets/font"),
        (os.path.join(app_dir, "selection_watcher.py"), "."),
        (os.path.join(app_dir, "pins.py"), "."),
        (os.path.join(app_dir, "main_pins.py"), "."),
        (os.path.join(app_dir, "skill_editor.py"), "."),
        (os.path.join(app_dir, "skill_settings.py"), "."),
        (os.path.join(base_dir, ".env"), "."),
        (os.path.join(base_dir, "gcloud-key.json"), "."),
    ] + _skill_bundles + _heif_datas,
    hiddenimports=[
        'pystray._win32',
        'certifi',
        'keyboard',
        'pyperclip',
        *collect_submodules('cryptography'),
        # Dynamic imports inside skills (file-metadata reading) — not detected
        # by PyInstaller's static analysis, so force-include them here.
        'pymediainfo',
        'pypdf',
        'pillow_heif',
        *_heif_hidden,
        # Stdlib modules used by the store-delivered PDF skill (reportlab +
        # pdfminer.six). Those libraries are NOT analyzed by PyInstaller (they
        # ship in the skill zip), so any stdlib module they import at runtime
        # must be force-included here or the skill fails with
        # "No module named '...'".
        'html',
        'html.parser',
        'html.entities',
        'unicodedata',
        'fnmatch',
        'ast',
        'base64',
        'pprint',
        'binascii',
        'xml',
        'xml.sax',
        'xml.sax.saxutils',
        'xml.parsers.expat',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'transformers',
        'torch',
        'tensorflow',
        'scipy',
        'pandas',
        'matplotlib',
        'pytest',
        'IPython',
        'notebook',
        'sphinx',
        'docutils',
        'setuptools',
        'wheel',
        'pip',
        'pkg_resources',
        'pyarrow',
        'pydantic',
        'pydantic_core',
        'hf_xet',
        'huggingface_hub',
        'grpc',
        'google',
        'boto3',
        'botocore',
        'lz4',
        'zstd',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='nespatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=os.path.join(packaging_dir, "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nespatch',
)
