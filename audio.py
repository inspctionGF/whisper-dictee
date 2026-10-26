"""Capture micro et niveau perceptif pour les ondes du popup."""

from __future__ import annotations

import math

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal

SAMPLE_RATE = 16_000
BLOCK = 480


def niveau(bloc: np.ndarray) -> float:
    """RMS converti sur la plage utile de la voix, de 0 à 1."""
    if bloc.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(bloc * bloc)))
    db = 20.0 * math.log10(max(rms, 1e-6))
    return min(1.0, max(0.0, (db + 55.0) / 43.0))


def resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or audio.size == 0:
        return audio.astype(np.float32, copy=False)
    target_size = max(1, int(audio.size * target_rate / source_rate))
    source_x = np.linspace(0.0, 1.0, audio.size, endpoint=False)
    target_x = np.linspace(0.0, 1.0, target_size, endpoint=False)
    return np.interp(target_x, source_x, audio).astype(np.float32)


def mic_name() -> str:
    try:
        default = sd.query_devices(kind="input")
        short = str(default["name"]).strip()
        best = short
        for device in sd.query_devices():
            if int(device["max_input_channels"]) < 1:
                continue
            name = str(device["name"]).strip()
            if name.startswith(short) and len(name) > len(best):
                best = name
        return best
    except Exception:
        return "micro par défaut"


def record_seconds(seconds: float) -> np.ndarray:
    frames: list[np.ndarray] = []
    rate = SAMPLE_RATE

    def callback(indata, _count, _time_info, status) -> None:
        if status:
            print(f"Micro : {status}", flush=True)
        frames.append(np.array(indata[:, 0], dtype=np.float32, copy=True))

    stream = _open_stream(callback)
    rate = int(stream.samplerate)
    with stream:
        import time

        time.sleep(seconds)
    if not frames:
        return np.zeros(0, dtype=np.float32)
    audio = np.concatenate(frames)
    return resample(audio, rate, SAMPLE_RATE)


def _open_stream(callback, device=None) -> sd.InputStream:
    common = {
        "device": device,
        "channels": 1,
        "dtype": "float32",
        "callback": callback,
        "latency": "low",
    }
    try:
        return sd.InputStream(samplerate=SAMPLE_RATE, blocksize=BLOCK, **common)
    except sd.PortAudioError:
        info = sd.query_devices(device if device is not None else None, "input")
        native = int(info["default_samplerate"])
        print(f"16 kHz refusé par le micro. Capture à {native} Hz.", flush=True)
        return sd.InputStream(
            samplerate=native,
            blocksize=max(256, native // 30),
            **common,
        )


class AudioRecorder(QObject):
    """Flux ouvert pour le niveau, tampon rempli seulement pendant une prise."""

    level_changed = Signal(float)
    failed = Signal(str)

    def __init__(self, device: str | int | None = None) -> None:
        super().__init__()
        self.device = None if device in (None, "", "par-defaut") else device
        self.stream: sd.InputStream | None = None
        self.sample_rate = SAMPLE_RATE
        self.frames: list[np.ndarray] = []
        self.recording = False
        self.latest_level = 0.0
        self.peak = 0.0
        self._logged_status = False

    def start(self) -> None:
        if self.stream is not None:
            return
        try:
            self.stream = _open_stream(self._on_audio, self.device)
            self.sample_rate = int(self.stream.samplerate)
            self.stream.start()
        except Exception as exc:
            self.stream = None
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self.recording = False
        stream = self.stream
        self.stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def begin_take(self) -> None:
        self.frames = []
        self.peak = 0.0
        self.recording = True
        if self.stream is None:
            self.start()

    def end_take(self) -> tuple[np.ndarray, float, float]:
        self.recording = False
        if not self.frames:
            return np.zeros(0, dtype=np.float32), 0.0, self.peak
        audio = np.concatenate(self.frames)
        self.frames = []
        audio = resample(audio, self.sample_rate, SAMPLE_RATE)
        duration = audio.size / SAMPLE_RATE
        return audio, duration, self.peak

    def cancel_take(self) -> None:
        self.recording = False
        self.frames = []
        self.peak = 0.0

    def _on_audio(self, indata, _frames, _time_info, status) -> None:
        if status and not self._logged_status:
            self._logged_status = True
            print(f"Micro : {status}", flush=True)
        mono = np.asarray(indata[:, 0], dtype=np.float32)
        level = niveau(mono)
        self.latest_level = level
        if self.recording:
            self.peak = max(self.peak, float(np.max(np.abs(mono))) if mono.size else 0.0)
            self.frames.append(np.array(mono, copy=True))
        self.level_changed.emit(level)
