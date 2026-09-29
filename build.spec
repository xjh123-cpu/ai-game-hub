# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（在 Windows 上执行，产出「AI游戏乐园.exe」）
# 用法：pyinstaller build.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

# 1) 前端资源：desktop/ 目录整体打包
datas = [("desktop", "desktop")]

# 2) 收集 pywebview 及其依赖的所有资源、二进制与隐藏导入
webview_datas, webview_binaries, webview_hidden = collect_all("webview")

# 3) 收集 pythonnet/clr（pywebview 在 Windows 用 WebView2 渲染所依赖）
try:
    clr_datas, clr_binaries, clr_hidden = collect_all("clr")
except Exception:
    clr_datas, clr_binaries, clr_hidden = [], [], []

hiddenimports = webview_hidden + clr_hidden + collect_submodules("webview")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=webview_binaries + clr_binaries,
    datas=datas + webview_datas + clr_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AI游戏乐园",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 无控制台黑窗，双击即用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
