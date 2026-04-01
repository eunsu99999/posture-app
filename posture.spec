# -*- mode: python ; coding: utf-8 -*-
import os, site

sp = next(p for p in site.getsitepackages() if 'site-packages' in p)
mp_dir = os.path.join(sp, 'mediapipe')

# mediapipe 모델/데이터 파일 수집
mp_datas = []
for root, dirs, files in os.walk(mp_dir):
    for f in files:
        if not f.endswith(('.py', '.pyc')):
            full = os.path.join(root, f)
            rel  = os.path.relpath(root, sp)
            mp_datas.append((full, rel))

a = Analysis(
    ['posture.py'],
    pathex=[],
    binaries=[],
    datas=mp_datas,
    hiddenimports=[
        'mediapipe',
        'mediapipe.python',
        'mediapipe.python.solutions',
        'mediapipe.python.solutions.pose',
        'mediapipe.python.solutions.drawing_utils',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'matplotlib',
        'matplotlib.backends.backend_tkagg',
        'plyer',
        'plyer.platforms.win.notification',
        'tkinter',
        'tkinter.ttk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PostureMonitor',
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PostureMonitor',
)
