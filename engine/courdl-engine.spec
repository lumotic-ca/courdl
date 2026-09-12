# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hidden = collect_submodules("dl_coursera")
hidden += collect_submodules("dl_coursera.lib")
hidden += collect_submodules("courdl_engine")
hidden += [
    "courdl_engine",
    "dl_coursera_run",
    "bs4",
    "lxml",
    "lxml.etree",
    "jinja2",
    "tqdm",
    "requests",
]

datas = collect_data_files("dl_coursera")

a = Analysis(
    ["courdl_engine/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
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
    a.binaries,
    a.datas,
    [],
    name="courdl-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=sys.platform != "darwin",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
