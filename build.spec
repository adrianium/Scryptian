# build.spec — PyInstaller build configuration for Scryptian

import os

block_cipher = None
base_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['main.py'],
    pathex=[base_dir],
    binaries=[(os.path.join(os.path.dirname(__import__('llama_cpp').__file__), 'lib', '*.dll'), 'llama_cpp/lib')],
    datas=[
        ('icon.ico', '.'),
        ('config.py', '.'),
        ('bridge.py', '.'),
        ('telemetry.py', '.'),
        ('tray.py', '.'),
        ('autostart.py', '.'),
        ('bootstrap.py', '.'),
        ('skills/*.py', 'skills'),
    ],
    hiddenimports=[
        'pystray._win32',
        'llama_cpp',
        'certifi',
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
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
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
