# build.spec — PyInstaller build configuration for Scryptian

import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

_skill_bundles = [
    (os.path.join('skills', name), os.path.join('skills', name))
    for name in sorted(os.listdir(os.path.join(base_dir, 'skills')))
    if os.path.isdir(os.path.join(base_dir, 'skills', name))
    and not name.startswith('_')
    and name != 'translate_pdf'
]

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    datas=[
        ('icon.ico', '.'),
        ('config.py', '.'),
        ('bridge.py', '.'),
        ('telemetry.py', '.'),
        ('tray.py', '.'),
        ('autostart.py', '.'),
        ('bootstrap.py', '.'),
        # Skill bundles are bundled as folders. The 'translate_pdf' bundle
        # (folder + ~22 MB libs/) is intentionally EXCLUDED — it ships via the
        # store (registry + zip) and is downloaded on demand, keeping the
        # installer small.
        ('docs/assets/scryptian-notification.wav', 'docs/assets'),
        ('docs/assets/slippers.png', 'docs/assets'),
        ('docs/assets/up-and-down.png', 'docs/assets'),
        ('selection_watcher.py', '.'),
        ('pins.py', '.'),
        ('main_pins.py', '.'),
        ('skill_editor.py', '.'),
        ('skill_settings.py', '.'),
        ('.env', '.')
    ] + _skill_bundles,
    hiddenimports=[
        'pystray._win32',
        'certifi',
        'keyboard',
        'pyperclip',
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
        'cryptography',
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
    name='Scryptian',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Scryptian',
)
