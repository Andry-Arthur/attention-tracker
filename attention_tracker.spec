# PyInstaller spec for Attention Tracker
# Build: pyinstaller attention_tracker.spec
# Output: dist/AttentionTracker/ folder containing AttentionTracker.exe and dependencies.
# Users run AttentionTracker.exe; config and logs are created next to the .exe.

import sys

block_cipher = None

# Collect all MediaPipe submodules, data, and binaries (includes mediapipe.tasks.c and .pyd/.dll)
try:
    from PyInstaller.utils.hooks import collect_all, collect_submodules
    mp_datas, mp_binaries, mp_hiddenimports = collect_all('mediapipe')
    mediapipe_hidden = list(mp_hiddenimports) if mp_hiddenimports else []
except Exception:
    mp_datas = []
    mp_binaries = []
    mediapipe_hidden = []

hidden_imports = [
    'cv2',
    'numpy',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
    'tkinter',
    'mediapipe',
    'mediapipe.tasks',
    'mediapipe.tasks.c',  # Native bindings; PyInstaller does not auto-detect
    'mediapipe.tasks.python',
    'mediapipe.tasks.python.vision',
    'mediapipe.tasks.python.core',
    'matplotlib',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.figure',
    'matplotlib.backends.backend_agg',
] + mediapipe_hidden

a = Analysis(
    ['attention_tracker.py'],
    pathex=[],
    binaries=mp_binaries,
    datas=mp_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Onedir: exe + folder of DLLs (more reliable for MediaPipe/OpenCV than onefile)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AttentionTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AttentionTracker',
)
