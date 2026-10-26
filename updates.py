"""Recherche une version plus récente dans les releases GitHub."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from version import APP_VERSION, GITHUB_REPO, SETUP_ASSET

CACHE_NAME = "mises-a-jour.json"


@dataclass(frozen=True)
class Release:
    version: str
    page_url: str
    download_url: str
    notes: str

    def open_url(self) -> str:
        return self.download_url or self.page_url


def version_key(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value or "")
    return tuple(int(part) for part in numbers) or (0,)


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    return version_key(latest) > version_key(current)


def fetch_latest(timeout: float = 12) -> Release | None:
    """Retourne la dernière release, ou None s'il n'y en a pas encore."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"DicteeLocale/{APP_VERSION}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not isinstance(payload, dict):
        return None
    version = str(payload.get("tag_name") or "").lstrip("vV")
    if not version:
        return None
    download = ""
    for asset in payload.get("assets") or []:
        if isinstance(asset, dict) and str(asset.get("name")) == SETUP_ASSET:
            download = str(asset.get("browser_download_url") or "")
            break
    return Release(
        version=version,
        page_url=str(payload.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"),
        download_url=download,
        notes=str(payload.get("body") or "").strip(),
    )


def _cache_path() -> Path:
    folder = Path(os.environ.get("APPDATA", str(Path.home()))) / "Dictee locale"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / CACHE_NAME


def remember(release: Release | None) -> None:
    path = _cache_path()
    if release is None:
        data = {"version": "", "page_url": "", "download_url": ""}
    else:
        data = {
            "version": release.version,
            "page_url": release.page_url,
            "download_url": release.download_url,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remembered() -> Release | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = str(data.get("version") or "")
    if not version or not is_newer(version):
        return None
    return Release(
        version=version,
        page_url=str(data.get("page_url") or ""),
        download_url=str(data.get("download_url") or ""),
        notes="",
    )


class _CheckThread(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.done.emit(fetch_latest())
        except Exception as exc:
            self.failed.emit(str(exc))


class UpdateChecker(QObject):
    """Interroge GitHub sans bloquer la fenêtre."""

    ready = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.release: Release | None = remembered()
        self.manual = False
        self._thread: _CheckThread | None = None

    def check(self, manual: bool = False) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self.manual = manual
        self._thread = _CheckThread()
        self._thread.done.connect(self._on_done)
        self._thread.failed.connect(self.failed)
        self._thread.start()

    def _on_done(self, release: Release | None) -> None:
        if release is not None and not is_newer(release.version):
            release = None
        self.release = release
        remember(release)
        self.ready.emit(release)
