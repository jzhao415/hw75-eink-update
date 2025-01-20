# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['source\\UpdateInk.pyw'],
    pathex=['.'],
    binaries=[],
    datas=[('icon','icon'),('img','img')],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='UpdateInk',
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
    [
        ('config.ini', 'config.ini', 'DATA'),
    ],
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UpdateInk',
)
