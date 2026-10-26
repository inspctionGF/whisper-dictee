"""faster-whisper, vocabulaire et corrections, hors du thread graphique."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal
from faster_whisper import WhisperModel

from paths import bundle_dir, corrections_path, frozen

BEAM_SIZE = 5
CPU_MODEL = "small"
CPU_COMPUTE = "int8"
AUTO_MODELS = {"", "auto"}


def log(message: str) -> None:
    print(message, flush=True)


def register_cuda_libraries() -> None:
    """CTranslate2 embarque cuDNN, mais pas cuBLAS."""
    if os.name != "nt":
        return
    bases = [Path(sys.prefix) / "Lib" / "site-packages"]
    if frozen():
        bases.insert(0, bundle_dir())
        bases.append(Path(sys.executable).resolve().parent)
    seen: set[str] = set()
    for base in bases:
        folders = [base / "ctranslate2"]
        nvidia = base / "nvidia"
        if nvidia.exists():
            folders.extend(nvidia.glob("*/bin"))
            folders.extend(nvidia.glob("*/lib"))
        for folder in folders:
            if not folder.is_dir():
                continue
            resolved = str(folder.resolve())
            if resolved in seen or not any(folder.glob("*.dll")):
                continue
            seen.add(resolved)
            try:
                os.add_dll_directory(resolved)
            except (OSError, AttributeError):
                pass
            os.environ["PATH"] = resolved + os.pathsep + os.environ.get("PATH", "")


register_cuda_libraries()


@dataclass(frozen=True)
class Backend:
    device: str
    compute_type: str
    model_name: str


@dataclass
class Engine:
    model: WhisperModel
    backend: Backend
    warmup_s: float


def _nvidia_smi(*fields: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    line = result.stdout.strip().splitlines()
    if not line or not line[0].strip():
        return None
    return [part.strip() for part in line[0].split(",")]


def gpu_name() -> str:
    fields = _nvidia_smi("name")
    if fields and fields[0]:
        return fields[0]
    return "NVIDIA"


def gpu_vram_mb() -> int:
    fields = _nvidia_smi("memory.total")
    if not fields:
        return 0
    try:
        return int(float(fields[0]))
    except ValueError:
        return 0


def cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception as exc:
        log(f"CUDA indisponible : {exc}")
        return False


def choose_backend(model_name: str) -> Backend:
    if cuda_available():
        return Backend("cuda", "float16", model_name)
    return Backend("cpu", CPU_COMPUTE, CPU_MODEL)


def resolve_backend(model_name: str) -> Backend:
    """Choisit le modèle. « auto » suit la mémoire de la carte graphique."""
    requested = str(model_name or "auto").strip().lower()
    if requested not in AUTO_MODELS:
        return choose_backend(requested)
    vram = gpu_vram_mb()
    if cuda_available():
        name = gpu_name()
        if vram >= 8000:
            chosen = Backend("cuda", "float16", "large-v3")
            reason = f"{name}, {vram} Mo"
        elif vram == 0 or vram >= 4000:
            chosen = Backend("cuda", "float16", "medium")
            detail = f"{vram} Mo" if vram else "mémoire non lue"
            reason = f"{name}, {detail}"
        else:
            chosen = Backend("cuda", "int8_float16", "small")
            reason = f"{name}, {vram} Mo"
        log(f"Carte graphique : {reason}. Modèle proposé : {chosen.model_name}.")
        return chosen
    log("Pas de carte NVIDIA utilisable. Modèle proposé : small, sur le processeur.")
    return Backend("cpu", CPU_COMPUTE, CPU_MODEL)


def model_cached(model_name: str) -> bool:
    from faster_whisper.utils import download_model

    try:
        download_model(model_name, local_files_only=True)
        return True
    except Exception:
        return False


def load_hints(fallback_prompt: str = "") -> dict:
    empty = {"prompt": fallback_prompt.strip(), "hotwords": "", "corrections": {}}
    path = corrections_path()
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"corrections.json illisible : {exc}")
        return empty
    if not isinstance(data, dict):
        return empty
    corrections = data.get("corrections") or {}
    if not isinstance(corrections, dict):
        corrections = {}
    prompt = str(data.get("prompt") or fallback_prompt).strip()
    return {
        "prompt": prompt,
        "hotwords": str(data.get("hotwords") or "").strip(),
        "corrections": corrections,
    }


def apply_corrections(text: str, corrections: dict) -> str:
    corrected = text
    for pattern, replacement in corrections.items():
        try:
            corrected = re.sub(str(pattern), str(replacement), corrected, flags=re.IGNORECASE)
        except re.error as exc:
            log(f"Motif ignoré ({pattern}) : {exc}")
    if corrected != text:
        log(f"Correction : {text}")
        log(f"         → {corrected}")
    return corrected


def transcribe_array(model: WhisperModel, audio: np.ndarray, language: str, prompt: str) -> str:
    hints = load_hints(prompt)
    segments, _info = model.transcribe(
        audio,
        language=language,
        task="transcribe",
        beam_size=BEAM_SIZE,
        best_of=1,
        temperature=0.0,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": 300,
            "speech_pad_ms": 200,
            "min_speech_duration_ms": 200,
        },
        condition_on_previous_text=False,
        without_timestamps=True,
        initial_prompt=hints["prompt"] or None,
        hotwords=hints["hotwords"] or None,
    )
    parts = [segment.text.strip() for segment in segments if segment.text.strip()]
    return apply_corrections(" ".join(parts), hints["corrections"])


def _consume(model: WhisperModel, audio: np.ndarray, vad_filter: bool, beam_size: int, language: str) -> None:
    segments, _info = model.transcribe(
        audio,
        language=language,
        beam_size=beam_size,
        best_of=1,
        temperature=0.0,
        vad_filter=vad_filter,
        condition_on_previous_text=False,
    )
    for _segment in segments:
        pass


def warmup(model: WhisperModel, language: str) -> float:
    from audio import SAMPLE_RATE

    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    _consume(model, silence, True, 1, language)
    count = SAMPLE_RATE * 2
    timeline = np.arange(count, dtype=np.float32) / SAMPLE_RATE
    tone = (0.05 * np.sin(2 * np.pi * 200 * timeline)).astype(np.float32)
    started = time.perf_counter()
    _consume(model, tone, False, BEAM_SIZE, language)
    return time.perf_counter() - started


def load_model(model_name: str, language: str, on_status=None) -> Engine:
    register_cuda_libraries()
    preferred = resolve_backend(model_name)
    if preferred.device == "cuda":
        attempts = [
            preferred,
            Backend("cuda", "float16", "medium"),
            Backend("cpu", CPU_COMPUTE, CPU_MODEL),
        ]
    else:
        attempts = [preferred]

    last_error: Exception | None = None
    seen: set[tuple[str, str]] = set()
    for backend in attempts:
        key = (backend.device, backend.model_name)
        if key in seen:
            continue
        seen.add(key)
        try:
            if not model_cached(backend.model_name):
                log(f"Téléchargement de {backend.model_name}…")
                if on_status is not None:
                    on_status("Téléchargement…")
            log(f"Chargement de {backend.model_name} ({backend.device}, {backend.compute_type})…")
            model = WhisperModel(
                backend.model_name,
                device=backend.device,
                compute_type=backend.compute_type,
            )
            log("Amorçage du modèle…")
            elapsed = warmup(model, language)
            log(f"Modèle prêt. Amorçage : {elapsed:.2f} s")
            return Engine(model, backend, elapsed)
        except Exception as exc:
            last_error = exc
            log(f"Échec du chargement ({backend.device}) : {exc}")
    raise RuntimeError("Impossible de charger Whisper") from last_error


class _LoadThread(QThread):
    ok = Signal(object)
    bad = Signal(str)
    status = Signal(str)

    def __init__(self, model_name: str, language: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.language = language

    def run(self) -> None:
        try:
            self.ok.emit(load_model(self.model_name, self.language, on_status=self.status.emit))
        except Exception as exc:
            self.bad.emit(str(exc))


class _JobThread(QThread):
    ok = Signal(str, float, float)
    empty = Signal()
    bad = Signal(str)

    def __init__(self, engine: Engine, audio: np.ndarray, duration: float, language: str, prompt: str) -> None:
        super().__init__()
        self.engine = engine
        self.audio = audio
        self.duration = duration
        self.language = language
        self.prompt = prompt

    def run(self) -> None:
        try:
            started = time.perf_counter()
            text = transcribe_array(self.engine.model, self.audio, self.language, self.prompt)
            elapsed = time.perf_counter() - started
            if text:
                self.ok.emit(text, self.duration, elapsed)
            else:
                self.empty.emit()
        except Exception as exc:
            self.bad.emit(str(exc))


class Transcriber(QObject):
    """Charge le modèle puis transcrit les prises. Le thread lui-même ne tourne pas."""

    ready = Signal(str)
    failed = Signal(str)
    status = Signal(str)
    transcribed = Signal(str, float, float)
    empty = Signal()
    error = Signal(str)

    def __init__(self, model_name: str, language: str, prompt: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.language = language
        self.prompt = prompt
        self.engine: Engine | None = None
        self._loader: _LoadThread | None = None
        self._job: _JobThread | None = None

    def load(self) -> None:
        self._loader = _LoadThread(self.model_name, self.language)
        self._loader.ok.connect(self._on_ready)
        self._loader.bad.connect(self.failed)
        self._loader.status.connect(self.status)
        self._loader.start()

    def submit(self, audio: np.ndarray, duration: float) -> None:
        if self.engine is None or self._job is not None and self._job.isRunning():
            return
        self._job = _JobThread(self.engine, audio, duration, self.language, self.prompt)
        self._job.ok.connect(self.transcribed)
        self._job.empty.connect(self.empty)
        self._job.bad.connect(self.error)
        self._job.start()

    def _on_ready(self, engine: Engine) -> None:
        self.engine = engine
        self.ready.emit(engine.backend.model_name)
