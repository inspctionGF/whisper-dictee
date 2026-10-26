"""Machine à états : raccourci, micro, transcription et collage."""

from __future__ import annotations

import ctypes
import json
import time
import winreg

import keyboard
import pyautogui
import pyperclip
from PySide6.QtCore import QObject, QThread, QTimer, Signal

from audio import AudioRecorder
from overlay.window import OverlayWindow
from paths import launch_command, settings_path
from transcriber import Transcriber, log

APP_NAME = "WhisperDictee"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MIN_SECONDS = 0.4
SILENCE_PEAK = 0.01

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32.GetForegroundWindow.restype = ctypes.c_void_p
_user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
_user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
_user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.AttachThreadInput.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool]

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0

DEFAULT_SETTINGS = {
    "popup": {
        "position": "bas-centre",
        "largeur": 420,
        "theme": "auto",
        "animations": True,
        "afficher_aide": True,
        "afficher_succes": True,
        "opacite_fond": 0.86,
    },
    "audio": {"micro": "par-defaut", "sons": False},
    "whisper": {
        "modele": "auto",
        "langue": "fr",
        "initial_prompt": "Vocabulaire : implémentation, API, Electron, IGF, OmniLab.",
    },
    "raccourci": "ctrl+alt+space",
}


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"settings.json illisible : {exc}")
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    return _merge(DEFAULT_SETTINGS, data if isinstance(data, dict) else {})


def save_settings(settings: dict) -> None:
    path = settings_path()
    path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def animations_enabled(settings: dict) -> bool:
    if not settings.get("popup", {}).get("animations", True):
        return False
    try:
        value = ctypes.c_int(1)
        _user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(value), 0)
        return bool(value.value)
    except Exception:
        return True


def paste_text(text: str) -> bool:
    backup = ""
    can_restore = False
    try:
        backup = pyperclip.paste()
        can_restore = True
    except pyperclip.PyperclipException as exc:
        log(f"Lecture du presse-papiers impossible : {exc}")
    try:
        pyperclip.copy(text)
    except pyperclip.PyperclipException as exc:
        log(f"Copie impossible : {exc}")
        return False
    time.sleep(0.08)
    try:
        pyautogui.hotkey("ctrl", "v")
    except pyautogui.FailSafeException:
        log("Collage annulé : la souris est dans un coin de l'écran.")
        log("Le texte reste dans le presse-papiers.")
        return False
    except Exception as exc:
        log(f"Collage impossible : {exc}")
        log("Le texte reste dans le presse-papiers.")
        return False
    time.sleep(0.3)
    if can_restore:
        try:
            pyperclip.copy(backup)
        except pyperclip.PyperclipException as exc:
            log(f"Restauration du presse-papiers impossible : {exc}")
    return True


def force_foreground(hwnd: int) -> None:
    if not hwnd:
        return
    current = _kernel32.GetCurrentThreadId()
    target = _user32.GetWindowThreadProcessId(hwnd, None)
    attached = False
    try:
        if target and target != current:
            attached = bool(_user32.AttachThreadInput(current, target, True))
        _user32.ShowWindow(hwnd, 5)
        _user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            _user32.AttachThreadInput(current, target, False)


def autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except (FileNotFoundError, OSError):
        return False


def set_autostart(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
            log("Démarrage avec Windows activé.")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            log("Démarrage avec Windows désactivé.")


def side_down(base: str, ignoring: str | None) -> bool:
    aliases = {base, f"left {base}", f"right {base}"}
    if base == "alt":
        aliases.add("alt gr")
    if ignoring in aliases and ignoring in {base, "alt gr"}:
        return False
    if ignoring == f"left {base}":
        return keyboard.is_pressed(f"right {base}")
    if ignoring == f"right {base}":
        return keyboard.is_pressed(f"left {base}")
    return keyboard.is_pressed(base)


class _PasteThread(QThread):
    done = Signal(bool)

    def __init__(self, text: str, hwnd: int) -> None:
        super().__init__()
        self.text = text
        self.hwnd = hwnd

    def run(self) -> None:
        force_foreground(self.hwnd)
        self.done.emit(paste_text(self.text))


class Controller(QObject):
    def __init__(self, overlay: OverlayWindow, recorder: AudioRecorder, transcriber: Transcriber, settings: dict) -> None:
        super().__init__()
        self.overlay = overlay
        self.recorder = recorder
        self.transcriber = transcriber
        self.settings = settings
        self.state = "loading"
        self.armed = False
        self.preview = False
        self.target_hwnd = 0
        self.elapsed = 0
        self._pending: tuple | None = None
        self._delay_done = False
        self._take: tuple | None = None
        self._paste: _PasteThread | None = None
        hotkey = str(settings.get("raccourci", "ctrl+alt+space")).lower().replace("espace", "space")
        parts = [part.strip() for part in hotkey.split("+") if part.strip()]
        self.trigger = parts[-1] if parts else "space"
        self.modifiers = parts[:-1] or ["ctrl", "alt"]

        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(16)
        self.frame_timer.timeout.connect(self.overlay.tick)
        self.chrono_timer = QTimer(self)
        self.chrono_timer.setInterval(1000)
        self.chrono_timer.timeout.connect(self._tick_chrono)
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(self._finish_hold)
        self.delay_timer = QTimer(self)
        self.delay_timer.setSingleShot(True)
        self.delay_timer.timeout.connect(self._transcription_delay)
        self.help_timer = QTimer(self)
        self.help_timer.setSingleShot(True)
        self.help_timer.timeout.connect(lambda: self.overlay.show_help(False))

        self._heard = False
        self.recorder.level_changed.connect(self._on_level)
        self.recorder.failed.connect(self._on_mic_failed)
        self.transcriber.ready.connect(self._on_model_ready)
        self.transcriber.failed.connect(self._on_model_failed)
        self.transcriber.status.connect(self._on_load_status)
        self.transcriber.transcribed.connect(self._on_transcribed)
        self.transcriber.empty.connect(self._on_empty)
        self.transcriber.error.connect(self._on_transcribe_error)

        overlay.set_reduced_motion(not animations_enabled(settings))
        overlay.set_language(str(settings.get("whisper", {}).get("langue", "fr")))
        overlay.set_elapsed(0)

    def start(self) -> None:
        self._enter("loading")
        self.transcriber.load()
        try:
            keyboard.hook(self._on_key, suppress=True)
        except Exception as exc:
            log(f"Raccourci global indisponible : {exc}")
            log("Relancez ce terminal en tant qu'administrateur.")

    def shutdown(self) -> None:
        self.frame_timer.stop()
        self.chrono_timer.stop()
        self.recorder.stop()
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def _mods_held(self, ignoring: str | None = None) -> bool:
        return all(side_down(modifier, ignoring) for modifier in self.modifiers)

    def _on_key(self, event):
        try:
            return self._handle_key(event)
        except Exception as exc:
            log(f"Raccourci : {exc}")
            return True

    def _handle_key(self, event):
        name = event.name or ""
        if name == "escape" and event.event_type == "down" and self.armed:
            self.armed = False
            QTimer.singleShot(0, self, self._cancel_take)
            return False
        if name == "escape" and event.event_type == "down" and self.preview:
            QTimer.singleShot(0, self, self._finish_hold)
            return True
        if name == self.trigger and self._mods_held():
            if event.event_type == "down":
                if not self.armed:
                    self.target_hwnd = int(_user32.GetForegroundWindow() or 0)
                    self.armed = True
                    QTimer.singleShot(0, self, self._begin_take)
                return False
            if self.armed:
                self.armed = False
                QTimer.singleShot(0, self, self._end_take)
            return False
        if event.event_type == "up" and self.armed and keyboard.is_modifier(event.scan_code):
            if not self._mods_held(name):
                self.armed = False
                QTimer.singleShot(0, self, self._end_take)
        return True

    def _enter(self, state: str, message: str = "") -> None:
        self.state = state
        self.preview = state == "listening" and not self.armed
        self.hold_timer.stop()
        self.overlay.set_state(state, message)
        if not self.overlay.isVisible() or self.overlay.windowOpacity() < 0.2:
            self.overlay.present()
        else:
            self.overlay.place()
            self.overlay._apply_native()
        if not self.frame_timer.isActive():
            self.frame_timer.start()

    def _on_load_status(self, message: str) -> None:
        self.overlay.set_state("loading", message)

    def _on_model_ready(self, model_name: str) -> None:
        log(f"Prêt. Maintenez {self._hotkey_label()} pour dicter.")
        log(f"Modèle retenu : {model_name}.")
        if self._take is not None:
            audio, duration, peak = self._take
            self._take = None
            self._dispatch_take(audio, duration, peak)
            return
        self._show_listening(reset=True)

    def _on_model_failed(self, message: str) -> None:
        log(f"Le modèle n'a pas pu être chargé : {message}")
        self._flash("error", "Une erreur est survenue", 1800)

    def _show_listening(self, reset: bool) -> None:
        if self.recorder.stream is None:
            self.recorder.start()
        if reset:
            self.elapsed = 0
            self.overlay.set_elapsed(0)
        self._enter("listening")
        self.overlay.show_help(True)
        self.help_timer.start(2000)

    def _begin_take(self) -> None:
        self.hold_timer.stop()
        self.delay_timer.stop()
        self._pending = None
        self.elapsed = 0
        self.overlay.set_elapsed(0)
        self.chrono_timer.start()
        self.recorder.begin_take()
        self._show_listening(reset=False)
        self.preview = False

    def _end_take(self) -> None:
        self.chrono_timer.stop()
        audio, duration, peak = self.recorder.end_take()
        log(f"Prise {duration:.1f} s, crête {peak:.3f}")
        if self.transcriber.engine is None:
            self._take = (audio, duration, peak)
            self._enter("loading")
            return
        self._dispatch_take(audio, duration, peak)

    def _cancel_take(self) -> None:
        self.chrono_timer.stop()
        self.recorder.cancel_take()
        self._flash("cancelled", "", 900)

    def _dispatch_take(self, audio, duration: float, peak: float) -> None:
        if duration < MIN_SECONDS:
            self._flash("short", "", 900)
            return
        if peak < SILENCE_PEAK:
            self._flash("silent", "", 1200)
            return
        self._pending = None
        self._delay_done = False
        self.delay_timer.start(120)
        self.transcriber.submit(audio, duration)

    def _transcription_delay(self) -> None:
        self._delay_done = True
        if self._pending is None:
            self._enter("transcribing")
            return
        kind, payload = self._pending
        self._pending = None
        self._deliver(kind, payload)

    def _on_transcribed(self, text: str, duration: float, elapsed: float) -> None:
        log(f"Audio {duration:.1f} s, transcription {elapsed:.2f} s")
        log(text)
        self._queue_result("text", text)

    def _on_empty(self) -> None:
        log("(aucun texte)")
        self._queue_result("silent", "")

    def _on_transcribe_error(self, message: str) -> None:
        log(f"Transcription impossible : {message}")
        self._queue_result("error", message)

    def _queue_result(self, kind: str, payload: str) -> None:
        if not self._delay_done:
            self._pending = (kind, payload)
            return
        self._deliver(kind, payload)

    def _deliver(self, kind: str, payload: str) -> None:
        if kind == "silent":
            self._flash("silent", "", 1200)
            return
        if kind == "error":
            self._flash("error", "Une erreur est survenue", 1800)
            return
        self._paste = _PasteThread(payload, self.target_hwnd)
        self._paste.done.connect(self._on_pasted)
        self._paste.start()

    def _on_pasted(self, ok: bool) -> None:
        if not ok:
            self._flash("error", "Une erreur est survenue", 1800)
            return
        if self.settings.get("popup", {}).get("afficher_succes", True):
            self._flash("success", "", 600)
        else:
            self._finish_hold()

    def _on_level(self, level: float) -> None:
        if self.state == "listening":
            self.overlay.wave.push_level(level)
            if not self._heard and level >= 0.08:
                self._heard = True
                log(f"Le micro réagit (niveau {level:.2f}).")

    def _on_mic_failed(self, message: str) -> None:
        log(f"Micro indisponible : {message}")
        self._flash("error", "Micro indisponible", 1800)

    def _tick_chrono(self) -> None:
        self.elapsed += 1
        self.overlay.set_elapsed(self.elapsed)

    def _flash(self, state: str, message: str, milliseconds: int) -> None:
        self.armed = False
        self.preview = False
        self._enter(state, message)
        self.hold_timer.start(milliseconds)

    def _finish_hold(self) -> None:
        self.state = "hidden"
        self.preview = False
        self.frame_timer.stop()
        self.chrono_timer.stop()
        self.recorder.stop()
        self.overlay.dismiss()

    def _hotkey_label(self) -> str:
        names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Maj", "space": "Espace"}
        parts = [names.get(part, part.capitalize()) for part in [*self.modifiers, self.trigger]]
        return "+".join(parts)
