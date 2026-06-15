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
        ('selection_watcher.py', '.'),
        ('pins.py', '.'),
        ('skill_editor.py', '.'),
    ],
    hiddenimports=[
        'pystray._win32',
        'llama_cpp',
        'certifi',
        'keyboard',
        'pyperclip',
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
