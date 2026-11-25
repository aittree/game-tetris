# -*- mode: python ; coding: utf-8 -*-
# tetris.spec —— onefile 单文件构建配置
# 用法：pyinstaller tetris.spec --clean --noconfirm

import os
import sys

# conda 环境的 ffi-8.dll 不在默认搜索路径，_ctypes 会报 DLL load failed，需显式入包
_ffi = os.path.join(os.path.dirname(sys.executable), "Library", "bin", "ffi-8.dll")

datas = [
    ("assets", "assets"),          # 图标、字体、图片、音频整体入包
]

binaries = [(_ffi, ".")] if os.path.exists(_ffi) else []

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["pygame.sysfont"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "tools", "numpy", "PIL"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="俄罗斯方块",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # 关掉 UPX，降低杀软误报
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # True 会带黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["assets/icon.ico"],
    version="version_info.txt",
)
