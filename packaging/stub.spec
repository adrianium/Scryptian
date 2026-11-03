# stub.spec — tiny Chrome-style installer (one-file exe).
# Build: pyinstaller packaging/stub.spec --noconfirm
# Output: dist/ScryptianSetup.exe

import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(base_dir, "stub.py")],
    pathex=[base_dir],
    binaries=[],
    datas=[
        (os.path.join(base_dir, "stub_logo.png"), "."),
        (os.path.join(base_dir, "icon.ico"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'transformers', 'torch', 'tensorflow', 'scipy', 'pandas',
        'matplotlib', 'pytest', 'IPython', 'notebook', 'sphinx',
        'setuptools', 'wheel', 'pip', 'numpy',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScryptianSetup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=os.path.join(base_dir, "icon.ico"),
)
