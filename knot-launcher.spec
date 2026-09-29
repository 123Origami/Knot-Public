# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['backend.settings', 'backend.urls', 'backend.wsgi', 'verify_email', 'verify_email.apps']
hiddenimports += collect_submodules('apps')
hiddenimports += collect_submodules('verify_email')


a = Analysis(
    ['C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\knot_launcher.py'],
    pathex=['C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\backend'],
    binaries=[],
    datas=[('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\db.sqlite3', '.'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\frontend', 'frontend'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\css', 'css'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\assets', 'assets'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\static', 'static'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\media', 'media'), ('C:\\Users\\User\\OneDrive\\Desktop\\Coding Projects\\knot-project\\data', 'data')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='knot-launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
