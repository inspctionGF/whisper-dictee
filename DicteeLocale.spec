# -*- mode: python ; coding: utf-8 -*-
"""Application Windows sans les modèles Whisper.

Le premier lancement choisit et télécharge le modèle selon la carte graphique.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
site = root / ".venv" / "Lib" / "site-packages"

datas = [(str(root / "corrections.json"), ".")]
binaries = []
hidden = [
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "onnxruntime",
    "av",
    "huggingface_hub",
    "sounddevice",
    "keyboard",
    "pyperclip",
    "pyautogui",
    "PIL",
    "numpy",
]

for package in (
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "sounddevice",
    "huggingface_hub",
    "numpy",
    "av",
    "onnxruntime",
):
    data, binary, imports = collect_all(package)
    datas += data
    binaries += binary
    hidden += imports

nvidia = site / "nvidia"
if nvidia.exists():
    for library in nvidia.rglob("*.dll"):
        binaries.append((str(library), str(library.parent.relative_to(site))))

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngine",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "tkinter",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DicteeLocale",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(root / "assets" / "dictee.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DicteeLocale",
)
