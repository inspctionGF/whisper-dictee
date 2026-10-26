"""Chemins de développement et de l'application installée."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "Dictee locale"


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def source_dir() -> Path:
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return source_dir()


def user_dir() -> Path:
    if not frozen():
        return source_dir()
    folder = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_path() -> Path:
    return user_dir() / "settings.json"


def corrections_path() -> Path:
    if not frozen():
        return source_dir() / "corrections.json"
    destination = user_dir() / "corrections.json"
    bundled = bundle_dir() / "corrections.json"
    if not destination.exists() and bundled.exists():
        destination.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
    return destination if destination.exists() else bundled


def launch_command() -> str:
    if frozen():
        return f'"{Path(sys.executable).resolve()}"'
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    executable = windowless if windowless.exists() else python
    return f'"{executable}" "{source_dir() / "main.py"}"'
